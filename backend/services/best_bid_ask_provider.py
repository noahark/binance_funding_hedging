"""Thread-safe public best-bid/ask snapshots backed by CCXT Pro."""
from __future__ import annotations

import asyncio
import inspect
import threading
import time
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from importlib.util import find_spec
from typing import Callable, Protocol


MarketKey = tuple[str, str, str]
_WATCH_RETRY_DELAY_SECONDS = 0.05


@dataclass(frozen=True)
class BookTickerSnapshot:
    key: MarketKey
    bid_price: Decimal
    bid_qty: Decimal
    ask_price: Decimal
    ask_qty: Decimal
    exchange_ts_ms: int | None
    received_at_us: int
    generation: int
    status: str
    error_zh: str | None


class L1Source(Protocol):
    async def watch(self) -> tuple[dict, object]: ...
    async def close(self) -> None: ...


@dataclass
class _WatchState:
    key: MarketKey
    refs: int
    generation: int
    snapshot: BookTickerSnapshot | None = None
    task: asyncio.Task | None = None
    source: L1Source | None = None
    ready: threading.Event = field(default_factory=threading.Event)


class _CcxtBookTickerSource:
    def __init__(self, client, symbol: str, market_type: str):
        self._client = client
        self._symbol = symbol
        self._market_type = market_type
        self._contract_size = None
        self._loaded = False

    async def watch(self) -> tuple[dict, object]:
        if not self._loaded:
            await self._client.load_markets()
            market = self._client.market(self._symbol)
            self._symbol = market["symbol"]
            self._contract_size = market.get("contractSize")
            self._loaded = True
        books = await self._client.watch_bids_asks([self._symbol])
        item = books.get(self._symbol)
        if item is None and len(books) == 1:
            item = next(iter(books.values()))
        if not isinstance(item, dict):
            raise ValueError("CCXT 未返回目标 bookTicker")
        return item, self._contract_size

    async def close(self) -> None:
        await self._client.close()


def default_source_available() -> bool:
    """Probe package presence without importing CCXT or opening a connection."""
    return find_spec("ccxt") is not None


def _default_source_factory(key: MarketKey) -> L1Source:
    # The dependency stays optional at module-import time. This is the sole CCXT
    # import site; tests and disabled deployments can import the provider without it.
    import ccxt.pro as ccxtpro

    exchange_id, market_type, symbol = key
    if exchange_id != "binance" or market_type not in ("spot", "swap"):
        raise ValueError(f"不支持的公共盘口市场: {key!r}")
    if not symbol.endswith("USDT"):
        raise ValueError(f"不支持的公共盘口 symbol: {symbol}")
    unified = f"{symbol[:-4]}/USDT"
    client_cls = ccxtpro.binance if market_type == "spot" else ccxtpro.binanceusdm
    return _CcxtBookTickerSource(client_cls({"enableRateLimit": True}), unified, market_type)


class BestBidAskProvider:
    """Own one asyncio thread and one ref-counted watcher per market key."""

    def __init__(
        self,
        *,
        on_change: Callable[[MarketKey], None] | None = None,
        source_factory: Callable[[MarketKey], L1Source] | None = None,
    ) -> None:
        self._on_change = on_change
        self._source_factory = source_factory or _default_source_factory
        self._lock = threading.RLock()
        self._states: dict[MarketKey, _WatchState] = {}
        self._generations: dict[MarketKey, int] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._closed = False
        self._release_futures = set()

    def set_on_change(self, callback: Callable[[MarketKey], None] | None) -> None:
        self._on_change = callback

    def start(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("公共盘口 provider 已关闭")
            if self._thread is None or not self._thread.is_alive():
                self._ready.clear()
                self._thread = threading.Thread(
                    target=self._run_loop, name="best-bid-ask-provider", daemon=True
                )
                self._thread.start()
        if not self._ready.wait(5):
            raise RuntimeError("公共盘口 event loop 启动超时")

    def subscribe(self, key: MarketKey) -> None:
        self.start()
        created = False
        with self._lock:
            state = self._states.get(key)
            if state is not None:
                state.refs += 1
            else:
                generation = self._generations.get(key, 0) + 1
                self._generations[key] = generation
                state = _WatchState(key=key, refs=1, generation=generation)
                self._states[key] = state
                loop = self._loop
                created = True
        if not created:
            if not state.ready.wait(5):
                raise RuntimeError("公共盘口 watcher 启动超时")
            with self._lock:
                if self._states.get(key) is not state or state.task is None:
                    raise RuntimeError("公共盘口 watcher 启动失败")
            return
        future = None
        try:
            if loop is None:
                raise RuntimeError("公共盘口 event loop 不可用")
            future = asyncio.run_coroutine_threadsafe(self._start_watch(state), loop)
            future.result(5)
            with self._lock:
                if self._states.get(key) is not state or state.task is None:
                    raise RuntimeError("公共盘口 watcher 启动失败")
        except Exception:
            with self._lock:
                self._states.pop(key, None)
            if future is not None:
                future.cancel()
            raise
        finally:
            state.ready.set()

    def release(self, key: MarketKey) -> None:
        with self._lock:
            state = self._states.get(key)
            if state is None:
                return
            state.refs -= 1
            if state.refs > 0:
                return
            self._states.pop(key, None)
            loop = self._loop
            if loop is not None:
                future = asyncio.run_coroutine_threadsafe(
                    self._cancel_state(state), loop
                )
                self._release_futures.add(future)
                future.add_done_callback(self._forget_release_future)
        self._notify(key)

    def _forget_release_future(self, future) -> None:
        with self._lock:
            self._release_futures.discard(future)

    def latest(self, key: MarketKey) -> BookTickerSnapshot | None:
        with self._lock:
            state = self._states.get(key)
            return state.snapshot if state is not None else None

    def close(self, timeout: float = 5.0) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            states = list(self._states.values())
            self._states.clear()
            release_futures = list(self._release_futures)
            loop = self._loop
            thread = self._thread
        if loop is not None and loop.is_running():
            deadline = time.monotonic() + timeout
            try:
                for release_future in release_futures:
                    release_future.result(
                        timeout=max(deadline - time.monotonic(), 0)
                    )
                future = asyncio.run_coroutine_threadsafe(self._shutdown(states), loop)
                future.result(timeout=max(deadline - time.monotonic(), 0))
            finally:
                loop.call_soon_threadsafe(loop.stop)
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
            if thread.is_alive():
                raise TimeoutError("公共盘口 event loop 未在期限内退出")

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with self._lock:
            self._loop = loop
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    async def _start_watch(self, state: _WatchState) -> None:
        with self._lock:
            if self._states.get(state.key) is not state:
                return
            state.task = asyncio.create_task(self._watch(state))

    async def _watch(self, state: _WatchState) -> None:
        try:
            source = self._source_factory(state.key)
            if inspect.isawaitable(source):
                source = await source
            state.source = source
            while self._is_current(state):
                try:
                    item, contract_size = await source.watch()
                    snapshot = self._parse_snapshot(
                        state.key, state.generation, item, contract_size
                    )
                    if snapshot is None:
                        self._set_status(state, "disconnected", "盘口原始字段无效")
                        await asyncio.sleep(_WATCH_RETRY_DELAY_SECONDS)
                        continue
                    self._publish(state, snapshot)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # source reconnects on the next watch call
                    self._set_status(
                        state, "disconnected", f"公共盘口断开：{type(exc).__name__}"
                    )
                    with self._lock:
                        if self._states.get(state.key) is not state:
                            break
                        state.generation += 1
                        self._generations[state.key] = state.generation
                    self._set_status(state, "connecting", None)
                    await asyncio.sleep(_WATCH_RETRY_DELAY_SECONDS)
        finally:
            await self._close_source(state.source)

    def _is_current(self, state: _WatchState) -> bool:
        with self._lock:
            return self._states.get(state.key) is state and not self._closed

    def _publish(self, state: _WatchState, snapshot: BookTickerSnapshot) -> None:
        with self._lock:
            if self._states.get(state.key) is not state:
                return
            state.snapshot = snapshot
        self._notify(state.key)

    def _set_status(self, state: _WatchState, status: str, error_zh: str | None) -> None:
        with self._lock:
            if self._states.get(state.key) is not state:
                return
            if state.snapshot is not None:
                state.snapshot = replace(
                    state.snapshot,
                    generation=state.generation,
                    status=status,
                    error_zh=error_zh,
                )
        self._notify(state.key)

    def _notify(self, key: MarketKey) -> None:
        callback = self._on_change
        if callback is not None:
            try:
                callback(key)
            except Exception:
                pass

    @staticmethod
    def _parse_snapshot(
        key: MarketKey, generation: int, item: dict, contract_size: object
    ) -> BookTickerSnapshot | None:
        if key[1] == "swap":
            try:
                size = Decimal(str(contract_size))
            except (InvalidOperation, ValueError, TypeError):
                return None
            if not size.is_finite() or size != 1:
                return None
        info = item.get("info") if isinstance(item, dict) else None
        if not isinstance(info, dict):
            return None
        values = []
        for name in ("b", "B", "a", "A"):
            raw = info.get(name)
            if not isinstance(raw, str) or not raw:
                return None
            try:
                value = Decimal(raw)
            except InvalidOperation:
                return None
            if not value.is_finite() or value <= 0:
                return None
            values.append(value)
        exchange_ts = None
        if key[1] == "swap" and info.get("E") is not None:
            try:
                exchange_ts = int(info["E"])
            except (TypeError, ValueError):
                exchange_ts = None
        return BookTickerSnapshot(
            key=key,
            bid_price=values[0],
            bid_qty=values[1],
            ask_price=values[2],
            ask_qty=values[3],
            exchange_ts_ms=exchange_ts,
            received_at_us=int(time.time() * 1_000_000),
            generation=generation,
            status="live",
            error_zh=None,
        )

    async def _cancel_state(self, state: _WatchState) -> None:
        task = state.task
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        elif task is None:
            await self._close_source(state.source)

    async def _shutdown(self, states: list[_WatchState]) -> None:
        await asyncio.gather(
            *(self._cancel_state(state) for state in states), return_exceptions=True
        )

    @staticmethod
    async def _close_source(source: L1Source | None) -> None:
        if source is None:
            return
        try:
            result = source.close()
            if inspect.isawaitable(result):
                await result
        except Exception:
            pass
