from __future__ import annotations

import asyncio
import json
import threading
import time
from decimal import Decimal

import pytest

from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.service import HedgeOpenTaskService
from backend.services.best_bid_ask_provider import (
    BestBidAskProvider,
    BookTickerSnapshot,
)
from backend.services.live_hedge_executor import (
    LEG_ACCEPTED,
    LegDispatch,
    LiveAttemptDispatch,
)
from backend.tests.fakes import RecordTransportFake


SPOT = ("binance", "spot", "BTCUSDT")
SWAP = ("binance", "swap", "BTCUSDT")


class _Clock:
    def __init__(self, value=1_000_000):
        self.t = value

    def mono_us(self):
        return self.t

    def wall_us(self):
        return self.t


class _Preflight:
    def __init__(self):
        self.calls = 0

    def get_snapshot(self, coin, direction, task_type="open", position_side_mode=None):
        self.calls += 1
        filters = {
            "lot_size": {"min_qty": "0.001", "max_qty": "1000", "step_size": "0.001"},
            "market_lot_size": {"min_qty": "0.001", "max_qty": "1000", "step_size": "0.001"},
            "notional": {"min_notional": "1", "apply_min_to_market": True},
        }
        return D.PreflightSnapshot(
            spot_filters=filters,
            perp_filters=filters,
            balances={"USDT": Decimal("1000000"), "BTC": Decimal("1000000")},
            position_mode=D.POS_MODE_BOTH,
            est_price=Decimal("100"),
        )


class _Market:
    def __init__(self):
        self.callback = None
        self.snapshots = {}
        self.refs = {}
        self.closed = False

    def set_on_change(self, callback):
        self.callback = callback

    def subscribe(self, key):
        self.refs[key] = self.refs.get(key, 0) + 1

    def release(self, key):
        refs = self.refs.get(key, 0) - 1
        if refs <= 0:
            self.refs.pop(key, None)
            self.snapshots.pop(key, None)
        else:
            self.refs[key] = refs

    def latest(self, key):
        self.latest_calls = getattr(self, "latest_calls", 0) + 1
        return self.snapshots.get(key)

    def publish(self, key, *, bid, bid_qty="1", ask=None, ask_qty="1", status="live"):
        self.snapshots[key] = BookTickerSnapshot(
            key=key,
            bid_price=Decimal(bid),
            bid_qty=Decimal(bid_qty),
            ask_price=Decimal(ask if ask is not None else bid),
            ask_qty=Decimal(ask_qty),
            exchange_ts_ms=None,
            received_at_us=1,
            generation=1,
            status=status,
            error_zh=None,
        )
        if self.callback is not None:
            self.callback(key)

    def close(self):
        self.closed = True


class _FailSecondSubscriptionMarket(_Market):
    def __init__(self):
        super().__init__()
        self.fail_once = True

    def subscribe(self, key):
        if key == SWAP and self.fail_once:
            self.fail_once = False
            raise RuntimeError("swap subscribe failed")
        super().subscribe(key)


class _ImmediateBookTickerSource:
    def __init__(self, contract_size):
        self.contract_size = contract_size
        self.first = True

    async def watch(self):
        if self.first:
            self.first = False
            return {
                "info": {"b": "100", "B": "1", "a": "100.01", "A": "1"}
            }, self.contract_size
        await asyncio.Event().wait()

    async def close(self):
        pass


class _ConcurrentSubscriptionMarket(_Market):
    def __init__(self):
        super().__init__()
        self.first_subscribers = threading.Barrier(2)
        self.refs_lock = threading.Lock()

    def subscribe(self, key):
        if key == SPOT:
            self.first_subscribers.wait(timeout=1)
        with self.refs_lock:
            super().subscribe(key)

    def release(self, key):
        with self.refs_lock:
            super().release(key)


class _OrderedMarket(_Market):
    def __init__(self, events):
        super().__init__()
        self.events = events

    def subscribe(self, key):
        self.events.append("subscribe")
        super().subscribe(key)

    def latest(self, key):
        if "market_evaluation" not in self.events:
            self.events.append("market_evaluation")
        return super().latest(key)


class _OrderedLiveExecutor:
    def __init__(self, events, leverage_error=None):
        self.events = events
        self.leverage_error = leverage_error
        self.leverage_calls = 0
        self.dispatch_calls = 0

    def set_leverage(self, coin, leverage):
        self.events.append("set_leverage")
        self.leverage_calls += 1
        if self.leverage_error is not None:
            raise self.leverage_error

    def dispatch(self, ctx):
        self.events.append("dispatch")
        self.dispatch_calls += 1
        spot = LegDispatch(
            leg="spot", dispatch_state=LEG_ACCEPTED, order_id="1",
            exchange_status=D.LEG_FILLED, executed_qty=str(ctx.q_common),
            cumulative_quote=None, avg_price=None, raw_response={"orderId": 1},
        )
        perp = LegDispatch(
            leg="perp", dispatch_state=LEG_ACCEPTED, order_id="2",
            exchange_status=D.LEG_FILLED, executed_qty=str(ctx.q_common),
            cumulative_quote=None, avg_price=None, raw_response={"orderId": 2},
        )
        return LiveAttemptDispatch(
            attempt_id=ctx.attempt_id, spot=spot, perp=perp,
            record_payload={"transport": "test"}, rate_limited=False,
            retry_after_seconds=None,
        )


def _wait(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.005)
    raise AssertionError("condition not reached")


def _service(tmp_path, *, target=1, clock=None, market=None, executor=None):
    clock = clock or _Clock()
    market = market or _Market()
    executor = executor or RecordTransportFake()
    svc = HedgeOpenTaskService(
        str(tmp_path / "smooth.sqlite3"),
        executor=executor,
        preflight_provider=_Preflight(),
        mode="disabled",
        mono_us=clock.mono_us,
        wall_us=clock.wall_us,
        market_provider=market,
    )
    _, task = svc.create_task({
        "coin": "BTCUSDT", "direction": D.DIR_FORWARD, "mode": D.MODE_SMOOTH,
        "single_amount": "1", "target_n": target,
        "slippage_threshold_pct": "0.05",
    })
    return svc, task, clock, market, executor


def _live_service(tmp_path, events, *, clock=None, leverage_error=None):
    clock = clock or _Clock()
    market = _OrderedMarket(events)
    executor = _OrderedLiveExecutor(events, leverage_error)
    preflight = _Preflight()
    svc = HedgeOpenTaskService(
        str(tmp_path / "smooth-live.sqlite3"),
        executor=executor,
        preflight_provider=preflight,
        mode="live",
        credentials_present=True,
        mono_us=clock.mono_us,
        wall_us=clock.wall_us,
        market_provider=market,
    )
    _, task = svc.create_task({
        "coin": "BTCUSDT", "direction": D.DIR_FORWARD, "mode": D.MODE_SMOOTH,
        "single_amount": "1", "target_n": 1,
        "slippage_threshold_pct": "0.05",
    })
    original_open = svc.store.open_smooth_gate
    original_prepare = svc.store.prepare_attempt

    def open_gate(*args, **kwargs):
        events.append("open_gate")
        return original_open(*args, **kwargs)

    def prepare_attempt(*args, **kwargs):
        events.append("prepare_attempt")
        return original_prepare(*args, **kwargs)

    svc.store.open_smooth_gate = open_gate
    svc.store.prepare_attempt = prepare_attempt
    return svc, task, clock, market, executor, preflight


def _arm_smooth(svc, task_id):
    svc.set_start_gate(True)
    row = svc.store.get_task(task_id)
    if row is not None and row["status"] != D.STATUS_RUNNING:
        svc.post_start(task_id)


def _open_first_gate(svc, task_id):
    _arm_smooth(svc, task_id)
    return _wait(
        lambda: (
            row if (row := svc.store.get_task(task_id))
            and row["smooth_gate_seq"] is not None else None
        )
    )


def _publish_bad(market):
    market.publish(SPOT, bid="99.99", ask="100", ask_qty="1")
    market.publish(SWAP, bid="100", ask="100.01", bid_qty="1")


def _publish_good(market):
    market.publish(SPOT, bid="99.99", ask="100", ask_qty="1")
    market.publish(SWAP, bid="100.10", ask="100.11", bid_qty="1")


def test_partial_subscription_failure_rolls_back_and_next_call_retries(tmp_path):
    market = _FailSecondSubscriptionMarket()
    svc, task, _, _, _ = _service(tmp_path, market=market)
    try:
        with pytest.raises(RuntimeError, match="swap subscribe failed"):
            svc._ensure_smooth_subscriptions(task)
        assert market.refs == {}
        assert task["id"] not in svc._smooth_subscriptions

        svc._ensure_smooth_subscriptions(task)
        assert market.refs == {SPOT: 1, SWAP: 1}
        assert svc._smooth_subscriptions[task["id"]] == (SPOT, SWAP)
    finally:
        svc.close()


def test_real_provider_subscribes_both_sides_without_blocking_callback(tmp_path):
    provider = BestBidAskProvider(
        source_factory=lambda key: _ImmediateBookTickerSource(
            1 if key[1] == "swap" else None
        )
    )
    svc, task, _, _, _ = _service(tmp_path, market=provider)
    try:
        started = time.monotonic()
        svc._ensure_smooth_subscriptions(task)

        assert time.monotonic() - started < 1
        assert svc._smooth_subscriptions[task["id"]] == (SPOT, SWAP)
        assert {key: provider._states[key].refs for key in (SPOT, SWAP)} == {
            SPOT: 1,
            SWAP: 1,
        }
    finally:
        svc.close()


def test_concurrent_subscription_keeps_only_one_ref_per_side(tmp_path):
    market = _ConcurrentSubscriptionMarket()
    svc, task, _, _, _ = _service(tmp_path, market=market)
    errors = []

    def subscribe():
        try:
            svc._ensure_smooth_subscriptions(task)
        except Exception as exc:
            errors.append(exc)

    try:
        threads = [threading.Thread(target=subscribe) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == []
        assert market.refs == {SPOT: 1, SWAP: 1}
        assert svc._smooth_subscriptions[task["id"]] == (SPOT, SWAP)
    finally:
        svc.close()


def test_subscription_failure_pauses_without_attempt_and_can_restart(tmp_path):
    market = _FailSecondSubscriptionMarket()
    svc, task, _, _, executor = _service(tmp_path, market=market)
    try:
        _arm_smooth(svc, task["id"])
        paused = _wait(
            lambda: (
                row if (row := svc.store.get_task(task["id"]))
                and row["pause_reason"] == D.PAUSE_REASON_PREFLIGHT_INCOMPLETE else None
            )
        )
        assert paused["pause_reason"] == D.PAUSE_REASON_PREFLIGHT_INCOMPLETE
        assert "公共盘口订阅失败" in paused["pause_reason_zh"]
        assert "未发单" in paused["pause_reason_zh"]
        assert paused["smooth_gate_seq"] is None
        assert svc.store.list_attempts_for_task(task["id"]) == []
        assert executor.records == []
        assert market.refs == {}
        assert task["id"] not in svc._smooth_subscriptions

        _wait(
            lambda: task["id"] not in svc._workers
            or not svc._workers[task["id"]].is_alive()
        )
        svc.post_start(task["id"])
        _wait(lambda: task["id"] in svc._smooth_subscriptions)
        restarted = svc.store.get_task(task["id"])
        assert restarted["status"] == D.STATUS_RUNNING
        assert restarted["smooth_gate_seq"] == 1
        assert market.refs == {SPOT: 1, SWAP: 1}
    finally:
        svc.close()


@pytest.mark.parametrize("pass_reason", ["market", "manual", "timeout"])
def test_live_smooth_orders_leverage_gate_and_frozen_dispatch(
    tmp_path, pass_reason,
):
    events = []
    svc, task, clock, market, executor, preflight = _live_service(
        tmp_path, events
    )
    try:
        if pass_reason == "market":
            _publish_good(market)
        else:
            _publish_bad(market)
        _arm_smooth(svc, task["id"])
        if pass_reason != "market":
            gate = _wait(
                lambda: (
                    row if (row := svc.store.get_task(task["id"]))
                    and row["smooth_gate_seq"] is not None else None
                )
            )
            if pass_reason == "manual":
                svc.post_fill_once(task["id"], {"gate_seq": gate["smooth_gate_seq"]})
            else:
                clock.t = gate["smooth_gate_started_at_us"] + D.SMOOTH_GATE_WINDOW_US
                svc._notify_smooth_task(task["id"])
        _wait(lambda: executor.dispatch_calls == 1)

        assert preflight.calls == 1  # create-task only; no fresh read after gate pass
        assert executor.leverage_calls == 1
        assert events.index("set_leverage") < events.index("open_gate")
        assert events.index("set_leverage") < events.index("subscribe")
        assert events.index("subscribe") < events.index("market_evaluation")
        assert events.index("market_evaluation") < events.index("prepare_attempt")
        assert events.index("prepare_attempt") < events.index("dispatch")
        attempt = svc.store.list_attempts_for_task(task["id"])[0]
        assert attempt["smooth_pass_reason"] == pass_reason
        assert attempt["q_common"] == task["q_common"]
        assert attempt["position_side_mode"] == task["position_side_mode"]
    finally:
        svc.close()


def test_live_smooth_leverage_failure_precedes_all_gate_state_and_can_retry(tmp_path):
    events = []
    error = RuntimeError("set leverage failed")
    svc, task, _, market, executor, preflight = _live_service(
        tmp_path, events, leverage_error=error
    )
    try:
        _publish_bad(market)
        _arm_smooth(svc, task["id"])
        paused = _wait(
            lambda: (
                row if (row := svc.store.get_task(task["id"]))
                and row["pause_reason"] == D.PAUSE_REASON_LEVERAGE_SET_FAILED else None
            )
        )
        assert paused["pause_reason"] == D.PAUSE_REASON_LEVERAGE_SET_FAILED
        assert paused["smooth_gate_seq"] is None
        assert market.refs == {}
        assert task["id"] not in svc._smooth_subscriptions
        assert svc.store.list_attempts_for_task(task["id"]) == []
        assert executor.dispatch_calls == 0
        assert preflight.calls == 1

        _wait(
            lambda: task["id"] not in svc._workers
            or not svc._workers[task["id"]].is_alive()
        )
        executor.leverage_error = None
        svc.post_start(task["id"])
        gate = _wait(
            lambda: (
                row if (row := svc.store.get_task(task["id"]))
                and row["smooth_gate_seq"] is not None else None
            )
        )
        svc.post_fill_once(task["id"], {"gate_seq": gate["smooth_gate_seq"]})
        _wait(lambda: executor.dispatch_calls == 1)
        assert executor.leverage_calls == 2
        assert preflight.calls == 1
    finally:
        svc.close()


def test_market_pass_waits_then_reuses_existing_dispatch_chain(tmp_path):
    svc, task, _, market, executor = _service(tmp_path)
    try:
        gate = _open_first_gate(svc, task["id"])
        assert gate["smooth_gate_seq"] == 1
        _publish_bad(market)
        time.sleep(0.03)
        assert executor.records == []
        _publish_good(market)
        _wait(lambda: len(executor.records) == 1)
        attempt = svc.store.list_attempts_for_task(task["id"])[0]
        assert attempt["smooth_pass_reason"] == D.PASS_REASON_MARKET
        assert svc.store.get_task(task["id"])["scheduled_attempt_count"] == 1
    finally:
        svc.close()


def test_manual_force_is_seq_bound_and_never_dispatches_in_http_thread(tmp_path):
    svc, task, _, market, executor = _service(tmp_path)
    try:
        _publish_bad(market)
        gate = _open_first_gate(svc, task["id"])
        status, doc = svc.post_fill_once(task["id"], {"gate_seq": gate["smooth_gate_seq"]})
        assert status == 200
        assert doc["smooth_gate_force_requested"] is True
        _wait(lambda: len(executor.records) == 1)
        attempt = svc.store.list_attempts_for_task(task["id"])[0]
        assert attempt["smooth_pass_reason"] == D.PASS_REASON_MANUAL
        with pytest.raises(D.HedgeError) as exc:
            svc.post_fill_once(task["id"], {"gate_seq": 1})
        assert exc.value.status == 409
    finally:
        svc.close()


def test_deadline_is_full_five_minutes_and_exact_boundary_times_out(tmp_path):
    clock = _Clock(10_000_000)
    svc, task, _, market, executor = _service(tmp_path, clock=clock)
    try:
        _publish_bad(market)
        gate = _open_first_gate(svc, task["id"])
        assert gate["smooth_gate_started_at_us"] == 10_000_000
        clock.t += D.SMOOTH_GATE_WINDOW_US - 1_000_000
        svc._notify_smooth_task(task["id"])
        time.sleep(0.03)
        assert executor.records == []
        clock.t += 1_000_000
        svc._notify_smooth_task(task["id"])
        _wait(lambda: len(svc.store.list_attempts_for_task(task["id"])) == 1)
        assert svc.store.list_attempts_for_task(task["id"])[0]["smooth_pass_reason"] == D.PASS_REASON_TIMEOUT
    finally:
        svc.close()


def test_pause_resume_same_seq_opens_a_new_full_window_and_clears_force(tmp_path):
    clock = _Clock(20_000_000)
    svc, task, _, market, _ = _service(tmp_path, target=2, clock=clock)
    try:
        _publish_bad(market)
        first = _open_first_gate(svc, task["id"])
        svc.store.force_smooth_gate(task["id"], 1, clock.t)
        svc.post_pause(task["id"])
        paused = svc.store.get_task(task["id"])
        assert paused["smooth_gate_seq"] is None
        clock.t += 123_000_000
        svc.post_start(task["id"])
        reopened = _wait(
            lambda: (
                row if (row := svc.store.get_task(task["id"]))
                and row["smooth_gate_seq"] == 1 else None
            )
        )
        assert reopened["smooth_gate_started_at_us"] == clock.t
        assert reopened["smooth_gate_started_at_us"] != first["smooth_gate_started_at_us"]
        assert reopened["smooth_gate_force_requested"] is False
    finally:
        svc.close()


def test_start_gate_close_wakes_waiter_and_reopen_restarts_window(tmp_path):
    clock = _Clock(30_000_000)
    svc, task, _, market, _ = _service(tmp_path, target=2, clock=clock)
    try:
        _publish_bad(market)
        first = _open_first_gate(svc, task["id"])
        svc.set_start_gate(False)
        _wait(lambda: svc.store.get_task(task["id"])["smooth_gate_seq"] is None)
        clock.t += 1_000_000
        svc.set_start_gate(True)
        second = _wait(
            lambda: (
                row if (row := svc.store.get_task(task["id"]))
                and row["smooth_gate_seq"] == 1 else None
            )
        )
        assert second["smooth_gate_started_at_us"] == clock.t
        assert second["smooth_gate_started_at_us"] != first["smooth_gate_started_at_us"]
    finally:
        svc.close()


def test_service_stop_wakes_waiter_but_preserves_durable_gate(tmp_path):
    svc, task, _, market, executor = _service(tmp_path)
    try:
        _publish_bad(market)
        gate = _open_first_gate(svc, task["id"])
        worker = svc._workers[task["id"]]
        svc.stop()
        _wait(lambda: not worker.is_alive())
        stored = svc.store.get_task(task["id"])
        assert stored["smooth_gate_seq"] == gate["smooth_gate_seq"]
        assert stored["smooth_gate_started_at_us"] == gate["smooth_gate_started_at_us"]
        assert executor.records == []
        assert market.closed is True
    finally:
        svc.close()


def test_existing_smooth_task_without_provider_can_still_timeout(tmp_path):
    clock = _Clock(40_000_000)
    executor = RecordTransportFake()
    svc = HedgeOpenTaskService(
        str(tmp_path / "existing.sqlite3"), executor=executor, mode="disabled",
        mono_us=clock.mono_us, wall_us=clock.wall_us, market_provider=None,
    )
    svc.store.create_task(
        "existing", "BTCUSDT", D.DIR_FORWARD, D.MODE_SMOOTH, "1", 1, "1",
        D.POS_MODE_BOTH, {}, clock.t, slippage_threshold_pct="0.05",
    )
    try:
        gate = _open_first_gate(svc, "existing")
        clock.t = gate["smooth_gate_started_at_us"] + D.SMOOTH_GATE_WINDOW_US
        svc._notify_smooth_task("existing")
        _wait(lambda: len(svc.store.list_attempts_for_task("existing")) == 1)
        assert svc.store.list_attempts_for_task("existing")[0]["smooth_pass_reason"] == D.PASS_REASON_TIMEOUT
    finally:
        svc.close()


def test_tenth_gate_market_manual_race_never_creates_eleventh_attempt(tmp_path):
    svc, task, _, market, executor = _service(tmp_path, target=10)
    try:
        _publish_bad(market)
        _open_first_gate(svc, task["id"])
        for seq in range(1, 10):
            _wait(
                lambda seq=seq: (
                    row if (row := svc.store.get_task(task["id"]))
                    and row["smooth_gate_seq"] == seq else None
                )
            )
            svc.post_fill_once(task["id"], {"gate_seq": seq})
            _wait(lambda seq=seq: svc.store.get_task(task["id"])["scheduled_attempt_count"] == seq)
        _wait(lambda: svc.store.get_task(task["id"])["smooth_gate_seq"] == 10)
        barrier = threading.Barrier(3)

        def market_pass():
            barrier.wait()
            _publish_good(market)

        def manual_pass():
            barrier.wait()
            try:
                svc.post_fill_once(task["id"], {"gate_seq": 10})
            except D.HedgeError as exc:
                assert exc.status == 409

        threads = [threading.Thread(target=market_pass), threading.Thread(target=manual_pass)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()
        _wait(lambda: svc.store.get_task(task["id"])["status"] == D.STATUS_DONE)
        assert svc.store.get_task(task["id"])["scheduled_attempt_count"] == 10
        assert len(svc.store.list_attempts_for_task(task["id"])) == 10
        assert len(executor.records) == 10
    finally:
        svc.close()


def test_smooth_fill_all_is_rejected(tmp_path):
    svc, task, _, _, _ = _service(tmp_path)
    try:
        svc.post_start(task["id"])
        with pytest.raises(D.HedgeError) as exc:
            svc.post_fill_all(task["id"])
        assert (exc.value.status, exc.value.code) == (409, "smooth_fill_all_unsupported")
    finally:
        svc.close()


def test_smooth_create_is_paused_with_zero_execution_resources(tmp_path):
    xfers = []

    class _RegularPreflight(_Preflight):
        def get_snapshot(self, coin, direction, task_type="open", position_side_mode=None):
            snap = super().get_snapshot(coin, direction, task_type, position_side_mode)
            return D.PreflightSnapshot(
                spot_filters=snap.spot_filters,
                perp_filters=snap.perp_filters,
                balances=snap.balances,
                position_mode=snap.position_mode,
                est_price=snap.est_price,
                spot_route=D.SPOT_ROUTE_REGULAR_SPOT,
                spot_account_usdt=Decimal("1000000"),
            )

    class _XferExec(RecordTransportFake):
        def universal_transfer(self, *args, **kwargs):
            xfers.append(args or kwargs)

    market = _Market()
    clock = _Clock()
    svc = HedgeOpenTaskService(
        str(tmp_path / "paused-create.sqlite3"),
        executor=_XferExec(),
        preflight_provider=_RegularPreflight(),
        mode="disabled",
        mono_us=clock.mono_us,
        wall_us=clock.wall_us,
        market_provider=market,
    )
    try:
        _, task = svc.create_task({
            "coin": "BTCUSDT", "direction": D.DIR_FORWARD, "mode": D.MODE_SMOOTH,
            "single_amount": "1", "target_n": 1,
            "slippage_threshold_pct": "0.05",
        })
        assert task["status"] == D.STATUS_PAUSED
        assert task["pause_reason"] == D.PAUSE_REASON_AWAITING_MANUAL_START
        assert task["pause_reason_zh"] == "任务首次执行必须点击启动"
        assert task["id"] not in svc._workers
        assert task["id"] not in svc._smooth_subscriptions
        assert market.refs == {}
        assert svc.store.get_task(task["id"])["smooth_gate_seq"] is None
        assert svc.store.list_attempts_for_task(task["id"]) == []
        assert xfers  # create-time regular-spot transfer happened once
        create_xfers = list(xfers)
        svc._recover_workers()
        assert task["id"] not in svc._workers
        with pytest.raises(D.HedgeError) as exc:
            svc.post_fill_once(task["id"], {"gate_seq": 1})
        assert exc.value.code == "start_required"
        svc.post_start(task["id"])
        assert svc.store.get_task(task["id"])["status"] == D.STATUS_RUNNING
        assert xfers == create_xfers
    finally:
        svc.close()


def test_immediate_create_lands_paused_awaiting_manual_start(tmp_path):
    # 2026-08-18 方案 B：立即开单建卡一律 paused + awaiting_manual_start（差异化
    # 文案），不起 worker；与 smooth open 建卡同形，仅 zh 文案不同。
    svc, _, _, _, _ = _service(tmp_path)
    try:
        _, task = svc.create_task({
            "coin": "ETHUSDT", "direction": D.DIR_FORWARD, "mode": D.MODE_IMMEDIATE,
            "single_amount": "1", "target_n": 1,
        })
        assert task["status"] == D.STATUS_PAUSED
        assert task["pause_reason"] == D.PAUSE_REASON_AWAITING_MANUAL_START
        assert task["pause_reason_zh"] == D.pause_reason_zh(
            D.PAUSE_REASON_AWAITING_MANUAL_START_FILLABLE
        )
        assert task["id"] not in svc._workers
    finally:
        svc.close()


@pytest.mark.parametrize("pass_reason", ["market", "manual", "timeout"])
def test_smooth_audit_uses_same_gate_snapshot_and_no_second_latest(
    tmp_path, pass_reason,
):
    events = []
    svc, task, clock, market, executor, _ = _live_service(tmp_path, events)
    try:
        if pass_reason == "market":
            _publish_good(market)
        else:
            _publish_bad(market)
        _arm_smooth(svc, task["id"])
        if pass_reason != "market":
            gate = _wait(
                lambda: (
                    row if (row := svc.store.get_task(task["id"]))
                    and row["smooth_gate_seq"] is not None else None
                )
            )
            if pass_reason == "manual":
                svc.post_fill_once(task["id"], {"gate_seq": gate["smooth_gate_seq"]})
            else:
                clock.t = gate["smooth_gate_started_at_us"] + D.SMOOTH_GATE_WINDOW_US
                svc._notify_smooth_task(task["id"])
        _wait(lambda: executor.dispatch_calls == 1)
        calls_after_pass = market.latest_calls
        market.publish(SPOT, bid="1", ask="2", ask_qty="9")
        market.publish(SWAP, bid="9", ask="10", bid_qty="9")
        time.sleep(0.02)
        assert market.latest_calls == calls_after_pass
        page = svc.get_logs(None, None, task_id=task["id"])[1]
        audits = page["smooth_dispatch_audits"]
        assert len(audits) == 1
        payload = audits[0]["payload"]
        assert payload["reason"] == pass_reason
        assert payload["gate_seq"] == 1
        assert payload["spot"]["ask"] == ("100" if pass_reason == "market" else "100")
        if pass_reason == "market":
            assert payload["perp"]["bid"] == "100.10"
        else:
            assert payload["perp"]["bid"] == "100"
        assert "100.1" not in json.dumps(payload.get("spot"))
    finally:
        svc.close()


def test_smooth_audit_prepare_delay_grows_only_prepare_segment(tmp_path):
    events = []
    clock = _Clock(8_000_000)
    svc, task, clock, market, executor, _ = _live_service(
        tmp_path, events, clock=clock,
    )
    try:
        inner = svc.store.prepare_attempt

        def delayed(*args, **kwargs):
            clock.t += 77_000
            return inner(*args, **kwargs)

        svc.store.prepare_attempt = delayed
        _publish_good(market)
        _arm_smooth(svc, task["id"])
        _wait(lambda: executor.dispatch_calls == 1)
        payload = svc.get_logs(None, None, task_id=task["id"])[1][
            "smooth_dispatch_audits"
        ][0]["payload"]
        durations = payload["durations_us"]
        assert durations["prepare_started_to_prepare_committed"] >= 77_000
        marks = payload["marks"]
        assert marks["prepare_started"] < marks["prepare_committed"]
        assert marks["prepare_committed"] >= marks["service_dispatch"] + 77_000
    finally:
        svc.close()


def test_smooth_audit_append_failure_does_not_change_business(tmp_path):
    events = []
    svc, task, _, market, executor, _ = _live_service(tmp_path, events)
    try:
        inner = svc.store.append_log

        def boom(task_id, ts_us, kind, payload, attempt_id=None):
            if kind == "smooth_dispatch_audit":
                raise RuntimeError("audit write failed")
            return inner(task_id, ts_us, kind, payload, attempt_id)

        svc.store.append_log = boom
        _publish_good(market)
        _arm_smooth(svc, task["id"])
        _wait(lambda: executor.dispatch_calls == 1)
        row = svc.store.get_task(task["id"])
        assert row["scheduled_attempt_count"] == 1
        assert row["status"] in (D.STATUS_RUNNING, D.STATUS_DONE)
        assert len(svc.store.list_attempts_for_task(task["id"])) == 1
        assert svc.get_logs(None, None, task_id=task["id"])[1][
            "smooth_dispatch_audits"
        ] == []
    finally:
        svc.close()


def test_immediate_live_dispatch_creates_no_smooth_audit(tmp_path):
    events = []
    clock = _Clock()
    executor = _OrderedLiveExecutor(events)
    svc = HedgeOpenTaskService(
        str(tmp_path / "imm.sqlite3"),
        executor=executor,
        preflight_provider=_Preflight(),
        mode="live",
        credentials_present=True,
        mono_us=clock.mono_us,
        wall_us=clock.wall_us,
    )
    try:
        _, task = svc.create_task({
            "coin": "BTCUSDT", "direction": D.DIR_FORWARD, "mode": D.MODE_IMMEDIATE,
            "single_amount": "1", "target_n": 1,
        })
        svc.set_start_gate(True)
        # 2026-08-18 方案 B：建卡 paused，先人工启动（post_start 置 running 并拉
        # worker）再验证 immediate 路径不产 smooth 审计。
        svc.post_start(task["id"])
        _wait(lambda: executor.dispatch_calls == 1)
        assert svc.get_logs(None, None, task_id=task["id"])[1][
            "smooth_dispatch_audits"
        ] == []
    finally:
        svc.close()
