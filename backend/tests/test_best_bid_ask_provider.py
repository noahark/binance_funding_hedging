from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from decimal import Decimal

import pytest

from backend.services.best_bid_ask_provider import (
    BestBidAskProvider,
    BookTickerSnapshot,
)


SPOT = ("binance", "spot", "BTCUSDT")
SWAP = ("binance", "swap", "BTCUSDT")


def _tick(*, b="100.00", B="7.48647000", a="100.01", A="2.000", E=None):
    info = {"b": b, "B": B, "a": a, "A": A}
    if E is not None:
        info["E"] = E
    return {"info": info}


class _Source:
    def __init__(self, *items):
        self._items = deque(items)
        self._lock = threading.Lock()
        self._loop = None
        self._wake = None
        self.closed = False
        self.watch_count = 0

    async def watch(self):
        self._loop = asyncio.get_running_loop()
        while True:
            with self._lock:
                if self._items:
                    item = self._items.popleft()
                    break
                self._wake = asyncio.Event()
                wake = self._wake
            await wake.wait()
        self.watch_count += 1
        if isinstance(item, BaseException):
            raise item
        return item

    def push(self, item):
        with self._lock:
            self._items.append(item)
            loop, wake = self._loop, self._wake
        if loop is not None and wake is not None:
            loop.call_soon_threadsafe(wake.set)

    async def close(self):
        self.closed = True
        with self._lock:
            wake = self._wake
        if wake is not None:
            wake.set()


class _Factory:
    def __init__(self, sources):
        self.sources = {key: deque(value) for key, value in sources.items()}
        self.calls = []

    def __call__(self, key):
        self.calls.append(key)
        return self.sources[key].popleft()


class _SlowCloseSource(_Source):
    async def close(self):
        await asyncio.sleep(0.05)
        await super().close()


class _DelayedStartProvider(BestBidAskProvider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.allow_start = threading.Event()
        self.start_calls = 0
        self.start_calls_lock = threading.Lock()

    def start(self):
        with self.start_calls_lock:
            self.start_calls += 1
        super().start()

    def _run_loop(self):
        self.allow_start.wait()
        super()._run_loop()


class _ImmediateLoopSource:
    def __init__(self, mode):
        self.mode = mode
        self.watch_count = 0
        self.closed = False

    async def watch(self):
        self.watch_count += 1
        if self.mode == "error":
            raise OSError("down")
        return {"info": {}}, None

    async def close(self):
        self.closed = True


def _wait(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.005)
    raise AssertionError("condition not reached")


def test_raw_decimal_snapshot_and_timestamps():
    spot = _Source((_tick(), None))
    swap = _Source((_tick(B="7.370", E="1234"), "1"))
    provider = BestBidAskProvider(source_factory=_Factory({SPOT: [spot], SWAP: [swap]}))
    try:
        provider.subscribe(SPOT)
        provider.subscribe(SWAP)
        s = _wait(lambda: provider.latest(SPOT))
        p = _wait(lambda: provider.latest(SWAP))
        assert isinstance(s, BookTickerSnapshot)
        assert all(isinstance(v, Decimal) for v in (s.bid_price, s.bid_qty, s.ask_price, s.ask_qty))
        assert format(s.bid_qty, "f") == "7.48647000"
        assert s.exchange_ts_ms is None
        assert s.received_at_us > 0
        assert format(p.bid_qty, "f") == "7.370"
        assert p.exchange_ts_ms == 1234
    finally:
        provider.close()


@pytest.mark.parametrize("field", ["b", "B", "a", "A"])
@pytest.mark.parametrize("value", [None, "", "0", "-1", "abc"])
def test_bad_raw_field_never_becomes_live(field, value):
    info = _tick()["info"]
    if value is None:
        info.pop(field)
    else:
        info[field] = value
    source = _Source((({"info": info}, None)))
    provider = BestBidAskProvider(source_factory=_Factory({SPOT: [source]}))
    try:
        provider.subscribe(SPOT)
        _wait(lambda: source.watch_count)
        assert provider.latest(SPOT) is None
    finally:
        provider.close()


@pytest.mark.parametrize("contract_size", [None, "2", "0"])
def test_swap_contract_size_unknown_or_not_one_fails_closed(contract_size):
    source = _Source((_tick(), contract_size))
    provider = BestBidAskProvider(source_factory=_Factory({SWAP: [source]}))
    try:
        provider.subscribe(SWAP)
        _wait(lambda: source.watch_count)
        assert provider.latest(SWAP) is None
    finally:
        provider.close()


def test_same_key_is_shared_until_last_release():
    source = _Source((_tick(), None))
    factory = _Factory({SPOT: [source]})
    provider = BestBidAskProvider(source_factory=factory)
    try:
        provider.subscribe(SPOT)
        provider.subscribe(SPOT)
        _wait(lambda: provider.latest(SPOT))
        assert factory.calls == [SPOT]
        provider.release(SPOT)
        assert provider.latest(SPOT).status == "live"
        provider.release(SPOT)
        _wait(lambda: source.closed)
        assert provider.latest(SPOT) is None
    finally:
        provider.close()


def test_concurrent_cold_subscribers_wait_for_one_ready_watcher():
    source = _Source((_tick(), None))
    factory = _Factory({SPOT: [source]})
    provider = _DelayedStartProvider(source_factory=factory)
    barrier = threading.Barrier(3)
    errors = []

    def subscribe():
        barrier.wait()
        try:
            provider.subscribe(SPOT)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=subscribe) for _ in range(2)]
    try:
        for thread in threads:
            thread.start()
        barrier.wait()
        _wait(lambda: provider.start_calls == 2 and provider._thread)
        time.sleep(0.01)
        assert all(thread.is_alive() for thread in threads)
        assert provider._states == {}
        provider.allow_start.set()
        for thread in threads:
            thread.join(2)
        assert not errors
        assert all(not thread.is_alive() for thread in threads)
        assert _wait(lambda: provider.latest(SPOT)) is not None
        assert factory.calls == [SPOT]
        assert provider._states[SPOT].refs == 2
        assert provider._states[SPOT].task is not None
    finally:
        provider.allow_start.set()
        provider.close()


def test_release_then_resubscribe_increments_generation():
    first = _Source((_tick(), None))
    second = _Source((_tick(b="101"), None))
    factory = _Factory({SPOT: [first, second]})
    provider = BestBidAskProvider(source_factory=factory)
    try:
        provider.subscribe(SPOT)
        assert _wait(lambda: provider.latest(SPOT)).generation == 1
        provider.release(SPOT)
        _wait(lambda: first.closed)
        provider.subscribe(SPOT)
        snap = _wait(lambda: provider.latest(SPOT))
        assert snap.generation == 2
        assert snap.bid_price == Decimal("101")
    finally:
        provider.close()


def test_close_waits_for_last_release_cleanup_before_stopping_loop():
    source = _SlowCloseSource((_tick(), None))
    provider = BestBidAskProvider(source_factory=_Factory({SPOT: [source]}))
    provider.subscribe(SPOT)
    _wait(lambda: provider.latest(SPOT))
    provider.release(SPOT)
    provider.close()
    assert source.closed


def test_exception_invalidates_then_first_new_generation_tick_recovers():
    source = _Source((_tick(), None), OSError("down"))
    provider = BestBidAskProvider(source_factory=_Factory({SPOT: [source]}))
    try:
        provider.subscribe(SPOT)
        disconnected = _wait(
            lambda: (snap if (snap := provider.latest(SPOT)) and snap.status != "live" else None)
        )
        assert disconnected.generation == 2
        assert disconnected.bid_price == Decimal("100.00")
        source.push((_tick(b="102"), None))
        recovered = _wait(
            lambda: (snap if (snap := provider.latest(SPOT)) and snap.status == "live" and snap.bid_price == 102 else None)
        )
        assert recovered.generation == 2
    finally:
        provider.close()


def test_blocked_spot_does_not_block_swap_or_other_symbol():
    spot = _Source()
    swap = _Source((_tick(E="1"), "1"), (_tick(b="101", E="2"), "1"))
    eth = ("binance", "spot", "ETHUSDT")
    eth_source = _Source((_tick(b="200"), None))
    provider = BestBidAskProvider(
        source_factory=_Factory({SPOT: [spot], SWAP: [swap], eth: [eth_source]})
    )
    try:
        for key in (SPOT, SWAP, eth):
            provider.subscribe(key)
        _wait(lambda: swap.watch_count >= 2)
        assert provider.latest(SPOT) is None
        assert provider.latest(SWAP).bid_price == 101
        assert _wait(lambda: provider.latest(eth)).bid_price == 200
    finally:
        provider.close()


def test_on_change_runs_for_updates_and_invalidation():
    changes = []
    source = _Source((_tick(), None), OSError("down"))
    provider = BestBidAskProvider(
        source_factory=_Factory({SPOT: [source]}), on_change=changes.append
    )
    try:
        provider.subscribe(SPOT)
        _wait(lambda: len(changes) >= 3)
        assert changes == [SPOT, SPOT, SPOT]
    finally:
        provider.close()


@pytest.mark.parametrize("mode,max_changes", [("error", 10), ("invalid", 5)])
def test_failed_watch_retries_are_bounded_and_close_interrupts_wait(mode, max_changes):
    source = _ImmediateLoopSource(mode)
    changes = []
    provider = BestBidAskProvider(
        source_factory=_Factory({SPOT: [source]}), on_change=changes.append
    )
    provider.subscribe(SPOT)
    _wait(lambda: source.watch_count >= 2)
    time.sleep(0.12)
    started = time.monotonic()
    provider.close()
    assert time.monotonic() - started < 0.2
    assert source.watch_count <= 5
    assert len(changes) <= max_changes
    assert source.closed
    assert provider._thread is not None and not provider._thread.is_alive()


def test_close_joins_thread_closes_all_sources_and_is_idempotent():
    spot = _Source((_tick(), None))
    swap = _Source((_tick(E="1"), "1"))
    provider = BestBidAskProvider(source_factory=_Factory({SPOT: [spot], SWAP: [swap]}))
    provider.subscribe(SPOT)
    provider.subscribe(SWAP)
    _wait(lambda: provider.latest(SPOT) and provider.latest(SWAP))
    thread = provider._thread
    provider.close()
    provider.close()
    assert spot.closed and swap.closed
    assert thread is not None and not thread.is_alive()
    assert provider.latest(SPOT) is None
