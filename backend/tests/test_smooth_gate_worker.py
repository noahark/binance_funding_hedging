from __future__ import annotations

import threading
import time
from decimal import Decimal

import pytest

from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.service import HedgeOpenTaskService
from backend.services.best_bid_ask_provider import BookTickerSnapshot
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
    def get_snapshot(self, coin, direction, task_type="open", position_side_mode=None):
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


def _open_first_gate(svc, task_id):
    svc.set_start_gate(True)
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
        with pytest.raises(D.HedgeError) as exc:
            svc.post_fill_all(task["id"])
        assert (exc.value.status, exc.value.code) == (409, "smooth_fill_all_unsupported")
    finally:
        svc.close()
