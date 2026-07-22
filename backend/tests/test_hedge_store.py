"""Durable store tests for backend/hedge_open_tasks/store.py.

No HTTP, no network. Covers task persistence round-trip, the default-deleted
list filter, attempt outcome application (success/fail/exposure/status), fill +
record-transport log persistence, the aggregate positions projection, settings,
and crash-style restart recovery (reopen the same DB file).
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.executor import AttemptOutcome
from backend.hedge_open_tasks.store import HedgeOpenStore


def _outcome(
    *, category=D.ATTEMPT_SUCCESS, spot_qty="0.5", perp_qty="0.5",
    spot_status=D.LEG_FILLED, perp_status=D.LEG_FILLED, exposure=None,
    attempt_id="att1",
) -> AttemptOutcome:
    return AttemptOutcome(
        attempt_id=attempt_id,
        category=category,
        spot={"status": spot_status, "filled_qty": spot_qty, "avg_price": "50000",
              "order_id": "os", "client_order_id": "hgo-att1-s"},
        perp={"status": perp_status, "filled_qty": perp_qty, "avg_price": "50000",
              "order_id": "op", "client_order_id": "hgo-att1-p"},
        record_payload={"transport": "dry_run_record", "posted": False,
                        "spot_order_params": {}, "perp_order_params": {}},
        exposure=exposure,
    )


def _create(store, task_id="t1", direction=D.DIR_FORWARD, target=3, q_common="0.5"):
    return store.create_task(
        task_id, "BTCUSDT", direction, D.MODE_IMMEDIATE, "0.5", target,
        q_common, D.POS_MODE_BOTH, {"est_price": "50000"}, 1_000,
    )


# ---------------------------------------------------------------------------
# Persistence round-trip
# ---------------------------------------------------------------------------

def test_create_then_get_round_trips_fields(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store)
    task = store.get_task("t1")
    assert task["coin"] == "BTCUSDT"
    assert task["direction"] == D.DIR_FORWARD
    assert task["mode"] == D.MODE_IMMEDIATE
    assert task["single_amount"] == "0.5"
    assert task["target_n"] == 3
    assert task["success_count"] == 0
    assert task["fail_count"] == 0
    assert task["status"] == D.STATUS_RUNNING
    assert task["q_common"] == "0.5"
    assert task["position_side_mode"] == D.POS_MODE_BOTH
    assert task["leg_exposure"] is None
    store.close()


def test_list_tasks_excludes_deleted_by_default(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1")
    _create(store, "t2")
    store.set_task_status("t2", D.STATUS_DELETED, 2_000)
    visible = [t["id"] for t in store.list_tasks(None)]
    assert visible == ["t1"]
    only_deleted = [t["id"] for t in store.list_tasks(D.STATUS_DELETED)]
    assert only_deleted == ["t2"]
    all_ids = sorted(t["id"] for t in store.list_tasks(None))
    # deleted stays excluded unless explicitly filtered.
    assert "t2" not in all_ids
    store.close()


# ---------------------------------------------------------------------------
# Attempt outcome application (status machine)
# ---------------------------------------------------------------------------

def test_apply_success_increments_and_completes_at_target(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1", target=3)
    store.apply_attempt_outcome("t1", _outcome(), 1_100)
    store.apply_attempt_outcome("t1", _outcome(attempt_id="att2"), 1_200)
    task = store.apply_attempt_outcome("t1", _outcome(attempt_id="att3"), 1_300)
    assert task["success_count"] == 3
    assert task["status"] == D.STATUS_DONE
    store.close()


def test_apply_single_leg_sets_exposure_and_alert(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1")
    exposure = {"filled_leg": "spot", "spot": {"filled_qty": "0.5"}, "perp": {"status": "REJECTED"}}
    task = store.apply_attempt_outcome(
        "t1",
        _outcome(category=D.ATTEMPT_SINGLE_LEG_EXPOSURE, perp_status=D.LEG_REJECTED,
                 perp_qty="0", exposure=exposure),
        1_100,
    )
    assert task["status"] == D.STATUS_EXPOSURE_ALERT
    assert task["leg_exposure"] == exposure
    assert task["success_count"] == 0  # exposure does not increment counts
    store.close()


def test_apply_failed_over_threshold_terminates(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1", target=5)
    for i in range(3):
        task = store.apply_attempt_outcome(
            "t1", _outcome(category=D.ATTEMPT_FAILED, spot_status=D.LEG_REJECTED,
                           perp_status=D.LEG_REJECTED, spot_qty="0", perp_qty="0",
                           attempt_id=f"f{i}"),
            1_100 + i,
        )
        assert task["status"] == D.STATUS_RUNNING  # 3 failures is not >3
    task = store.apply_attempt_outcome(
        "t1", _outcome(category=D.ATTEMPT_FAILED, spot_status=D.LEG_REJECTED,
                       perp_status=D.LEG_REJECTED, spot_qty="0", perp_qty="0",
                       attempt_id="f3"),
        2_000,
    )
    assert task["fail_count"] == 4
    assert task["status"] == D.STATUS_PAUSED  # >3 -> terminated
    store.close()


# ---------------------------------------------------------------------------
# Fills + record-transport log persistence
# ---------------------------------------------------------------------------

def test_insert_fill_persists_both_legs_and_log(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1")
    fill = store.insert_fill("t1", "att1", _outcome(), 1_100)
    assert fill["spot"]["filled_qty"] == "0.5"
    assert fill["perp"]["filled_qty"] == "0.5"
    assert fill["record_ref"] is not None  # points at the record-transport log row
    fills = store.list_fills_for_task("t1")
    assert len(fills) == 1
    payload = store.get_log_payload(fill["record_ref"])
    assert payload["posted"] is False
    store.close()


def test_list_logs_page_paginates_with_cursor(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1", target=5)
    for i in range(5):
        store.insert_fill("t1", f"att{i}", _outcome(attempt_id=f"att{i}"), 1_000 + i)
    page, has_more = store.list_logs_page(2, None, None)
    assert len(page) == 2
    assert has_more is True
    # newest-first: first page has the two newest log rows.
    assert page[0]["ts_us"] >= page[1]["ts_us"]
    next_ts, next_id = page[-1]["ts_us"], page[-1]["id"]
    page2, has_more2 = store.list_logs_page(2, next_ts, next_id)
    assert len(page2) == 2
    assert has_more2 is True
    store.close()


# ---------------------------------------------------------------------------
# Aggregate positions (stage-1 math)
# ---------------------------------------------------------------------------

def test_aggregate_positions_forward_short_reverse_long(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "tf", direction=D.DIR_FORWARD)
    _create(store, "tr", direction=D.DIR_REVERSE)
    store.insert_fill("tf", "af", _outcome(attempt_id="af"), 1_100)
    store.insert_fill("tr", "ar", _outcome(attempt_id="ar"), 1_200)
    positions = {p["direction"]: p for p in store.aggregate_positions()}
    # forward perp is a SELL -> negative short qty; reverse is a BUY -> positive.
    assert Decimal(positions[D.DIR_FORWARD]["position_qty"]) == Decimal("-0.5")
    assert Decimal(positions[D.DIR_REVERSE]["position_qty"]) == Decimal("0.5")
    assert Decimal(positions[D.DIR_FORWARD]["spot_avg"]) == Decimal("50000")
    assert Decimal(positions[D.DIR_FORWARD]["perp_avg"]) == Decimal("50000")
    store.close()


def test_aggregate_positions_excludes_deleted_tasks(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "tf", direction=D.DIR_FORWARD)
    store.insert_fill("tf", "af", _outcome(attempt_id="af"), 1_100)
    store.set_task_status("tf", D.STATUS_DELETED, 2_000)
    assert store.aggregate_positions() == []
    store.close()


# ---------------------------------------------------------------------------
# Settings + restart recovery
# ---------------------------------------------------------------------------

def test_settings_defaults_and_start_gate(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    s = store.get_settings()
    assert s["start_gate"] == 0
    assert s["interval_us"] == D.DEFAULT_INTERVAL_US
    assert s["executor_mode_snapshot"] == "disabled"
    store.set_start_gate(True, 1_000)
    assert store.get_settings()["start_gate"] == 1
    store.close()


def test_restart_recovers_persisted_state(tmp_path):
    db = str(tmp_path / "ho.sqlite3")
    store = HedgeOpenStore(db)
    _create(store, "t1", target=3)
    store.apply_attempt_outcome("t1", _outcome(), 1_100)
    store.apply_attempt_outcome("t1", _outcome(attempt_id="a2"), 1_200)
    store.close()
    # A new process reopens the same DB and sees the persisted counts.
    store2 = HedgeOpenStore(db)
    task = store2.get_task("t1")
    assert task["success_count"] == 2
    assert task["status"] == D.STATUS_RUNNING
    store2.close()
