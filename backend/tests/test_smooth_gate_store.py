from __future__ import annotations

import threading

import pytest

from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.executor import AttemptOutcome
from backend.hedge_open_tasks.store import HedgeOpenStore


def _create(store, task_id="smooth", *, mode=D.MODE_SMOOTH, target=2):
    return store.create_task(
        task_id, "BTCUSDT", D.DIR_FORWARD, mode, "1", target, "1",
        D.POS_MODE_BOTH, {"est_price": "100"}, 1_000,
        slippage_threshold_pct="0.05" if mode == D.MODE_SMOOTH else None,
    )


def _prepare(store, suffix, *, gate_seq=None, reason=None):
    return store.prepare_attempt(
        "smooth", f"att-{suffix}", D.DIR_FORWARD, "1", D.POS_MODE_BOTH,
        {"est_price": "100"}, f"spot-{suffix}", {"side": "BUY"},
        D.SPOT_ORDER_PATH, f"perp-{suffix}", {"side": "SELL"}, 2_000,
        expected_gate_seq=gate_seq, smooth_pass_reason=reason,
    )


def _outcome(attempt_id):
    return AttemptOutcome(
        attempt_id=attempt_id,
        category=D.ATTEMPT_SUCCESS,
        spot={"status": D.LEG_FILLED, "filled_qty": "1", "avg_price": "100",
              "order_id": "s", "client_order_id": "s"},
        perp={"status": D.LEG_FILLED, "filled_qty": "1", "avg_price": "100",
              "order_id": "p", "client_order_id": "p"},
        record_payload={}, exposure=None,
    )


def test_smooth_columns_round_trip_and_gate_open_is_idempotent(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "db.sqlite3"))
    task = _create(store)
    assert task["slippage_threshold_pct"] == "0.05"
    assert task["smooth_gate_seq"] is None
    first = store.open_smooth_gate("smooth", 1, 10_000)
    assert first["smooth_gate_started_at_us"] == 10_000
    forced = store.force_smooth_gate("smooth", 1, 10_001)
    assert forced["smooth_gate_force_requested"] is True
    again = store.open_smooth_gate("smooth", 1, 99_999)
    assert again["smooth_gate_started_at_us"] == 10_000
    assert again["smooth_gate_force_requested"] is True


def test_gate_open_rechecks_seq_status_budget_and_inflight(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "db.sqlite3"))
    _create(store, target=1)
    assert store.open_smooth_gate("smooth", 2, 10) is None
    assert store.open_smooth_gate("smooth", 1, 10) is not None
    attempt = _prepare(store, "one", gate_seq=1, reason=D.PASS_REASON_MARKET)
    assert attempt is not None
    assert store.open_smooth_gate("smooth", 2, 20) is None
    assert store.force_smooth_gate("smooth", 1, 20) is None


def test_smooth_prepare_fail_closed_and_consumes_gate_atomically(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "db.sqlite3"))
    _create(store)
    store.open_smooth_gate("smooth", 1, 10)
    assert _prepare(store, "missing") is None
    assert _prepare(store, "wrong", gate_seq=2, reason=D.PASS_REASON_MARKET) is None
    assert store.get_task("smooth")["smooth_gate_seq"] == 1
    attempt = _prepare(store, "ok", gate_seq=1, reason=D.PASS_REASON_MANUAL)
    assert attempt["smooth_pass_reason"] == D.PASS_REASON_MANUAL
    task = store.get_task("smooth")
    assert task["scheduled_attempt_count"] == 1
    assert task["smooth_gate_seq"] is None
    assert task["smooth_gate_started_at_us"] is None
    assert task["smooth_gate_force_requested"] is False


def test_market_manual_race_prepares_exactly_one_attempt(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "db.sqlite3"))
    _create(store)
    store.open_smooth_gate("smooth", 1, 10)
    barrier = threading.Barrier(3)
    results = []

    def run(suffix, reason):
        barrier.wait()
        results.append(_prepare(store, suffix, gate_seq=1, reason=reason))

    threads = [
        threading.Thread(target=run, args=("market", D.PASS_REASON_MARKET)),
        threading.Thread(target=run, args=("manual", D.PASS_REASON_MANUAL)),
    ]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()
    assert sum(result is not None for result in results) == 1
    assert len(store.list_attempts_for_task("smooth")) == 1
    assert store.get_task("smooth")["scheduled_attempt_count"] == 1


@pytest.mark.parametrize("status", [D.STATUS_PAUSED, D.STATUS_DELETED, D.STATUS_DONE])
def test_set_non_running_clears_gate_but_running_preserves_it(tmp_path, status):
    store = HedgeOpenStore(str(tmp_path / f"{status}.sqlite3"))
    _create(store)
    store.open_smooth_gate("smooth", 1, 10)
    store.force_smooth_gate("smooth", 1, 11)
    store.set_task_status("smooth", D.STATUS_RUNNING, 12)
    assert store.get_task("smooth")["smooth_gate_seq"] == 1
    store.set_task_status("smooth", status, 13)
    task = store.get_task("smooth")
    assert task["smooth_gate_seq"] is None
    assert task["smooth_gate_started_at_us"] is None
    assert task["smooth_gate_force_requested"] is False


def test_pause_and_fatal_stop_clear_gate_only_when_update_hits(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "hit.sqlite3"))
    _create(store)
    store.open_smooth_gate("smooth", 1, 10)
    store.force_smooth_gate("smooth", 1, 11)
    task, applied = store.pause_task("smooth", "x", "x", 12)
    assert applied and task["smooth_gate_seq"] is None

    store = HedgeOpenStore(str(tmp_path / "fatal.sqlite3"))
    _create(store)
    store.open_smooth_gate("smooth", 1, 10)
    stopped = store.stop_task_fatal("smooth", D.STOP_REASON_EXCHANGE_FATAL, 12)
    assert stopped["smooth_gate_seq"] is None


@pytest.mark.parametrize(
    "terminal,method",
    [(D.STATUS_DELETED, "pause"), (D.STATUS_DONE, "pause"),
     (D.STATUS_STOPPED, "fatal")],
)
def test_conditional_status_miss_preserves_nonempty_gate_sentinels(tmp_path, terminal, method):
    store = HedgeOpenStore(str(tmp_path / f"{terminal}-{method}.sqlite3"))
    _create(store)
    store.set_task_status("smooth", terminal, 2)
    with store._lock, store._conn:
        store._conn.execute(
            "UPDATE hedge_open_task SET smooth_gate_seq=777,"
            " smooth_gate_started_at_us=123456789, smooth_gate_force_requested=1"
            " WHERE id='smooth'"
        )
    if method == "pause":
        assert store.pause_task("smooth", "x", "x", 3) == (None, False)
    else:
        assert store.stop_task_fatal("smooth", D.STOP_REASON_EXCHANGE_FATAL, 3) is None
    task = store.get_task("smooth")
    assert task["status"] == terminal
    assert (task["smooth_gate_seq"], task["smooth_gate_started_at_us"],
            task["smooth_gate_force_requested"]) == (777, 123456789, True)


def test_settlement_path_neither_clears_again_nor_revives_gate(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "db.sqlite3"))
    _create(store, target=1)
    store.open_smooth_gate("smooth", 1, 10)
    attempt = _prepare(store, "ok", gate_seq=1, reason=D.PASS_REASON_TIMEOUT)
    before = store.get_task("smooth")
    assert before["smooth_gate_seq"] is None
    store.resolve_attempt(attempt["id"], _outcome(attempt["attempt_uuid"]), 3_000)
    after = store.get_task("smooth")
    assert after["status"] == D.STATUS_DONE
    assert after["smooth_gate_seq"] is None
    assert after["smooth_gate_started_at_us"] is None
    assert after["smooth_gate_force_requested"] is False


def test_immediate_prepare_behavior_and_gate_defaults_are_unchanged(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "db.sqlite3"))
    task = _create(store, mode=D.MODE_IMMEDIATE)
    assert task["slippage_threshold_pct"] is None
    attempt = store.prepare_attempt(
        "smooth", "att", D.DIR_FORWARD, "1", D.POS_MODE_BOTH,
        {}, "spot", {}, D.SPOT_ORDER_PATH, "perp", {}, 2_000,
    )
    assert attempt is not None
    assert attempt["smooth_pass_reason"] is None
    assert store.get_task("smooth")["scheduled_attempt_count"] == 1
