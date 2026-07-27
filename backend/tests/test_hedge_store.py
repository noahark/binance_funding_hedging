"""Durable store tests for backend/hedge_open_tasks/store.py.

No HTTP, no network. Covers task persistence round-trip, the default-deleted
list filter, attempt outcome application (success/fail/exposure/status), fill +
record-transport log persistence, the aggregate positions projection, settings,
and crash-style restart recovery (reopen the same DB file).
"""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.executor import AttemptOutcome
from backend.hedge_open_tasks.store import HedgeOpenStore


def _outcome(
    *, category=D.ATTEMPT_SUCCESS, spot_qty="0.5", perp_qty="0.5",
    spot_status=D.LEG_FILLED, perp_status=D.LEG_FILLED, exposure=None,
    attempt_id="att1", spot_oid="os", perp_oid="op",
) -> AttemptOutcome:
    return AttemptOutcome(
        attempt_id=attempt_id,
        category=category,
        spot={"status": spot_status, "filled_qty": spot_qty, "avg_price": "50000",
              "order_id": spot_oid, "client_order_id": f"hgo-{attempt_id}-s"},
        perp={"status": perp_status, "filled_qty": perp_qty, "avg_price": "50000",
              "order_id": perp_oid, "client_order_id": f"hgo-{attempt_id}-p"},
        record_payload={"transport": "dry_run_record", "posted": False,
                        "spot_order_params": {}, "perp_order_params": {}},
        exposure=exposure,
    )


def _apply(
    store: HedgeOpenStore, task_id: str, outcome: AttemptOutcome, now_us: int,
    *, direction=D.DIR_FORWARD, q_common="0.5",
):
    """Durable-before-send + synchronous resolve (the record-transport dispatch
    flow). ``prepare_attempt`` commits the immutable attempt + both deterministic
    client IDs in PREPARED, then ``resolve_attempt`` stamps both legs terminal and
    applies the task counters/pause — mirroring the service's record-transport
    path (no executor call under the lock)."""
    attempt = store.prepare_attempt(
        task_id, outcome.attempt_id, direction, q_common, D.POS_MODE_BOTH,
        {"est_price": "50000"}, f"hgo-{outcome.attempt_id}-s", {"side": "BUY"},
        f"hgo-{outcome.attempt_id}-p", {"side": "SELL"}, now_us,
    )
    assert attempt is not None, "task must be dispatch-eligible when prepared"
    return store.resolve_attempt(attempt["id"], outcome, now_us)


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
    _apply(store, "t1", _outcome(), 1_100)
    _apply(store, "t1", _outcome(attempt_id="att2"), 1_200)
    task = _apply(store, "t1", _outcome(attempt_id="att3"), 1_300)
    assert task["success_count"] == 3
    assert task["accepted_pair_count"] == 3
    assert task["status"] == D.STATUS_DONE
    store.close()


def test_apply_single_leg_records_exposure_advisory(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1")
    exposure = {"leg": "spot", "qty": "0.5", "price": "50000", "ts": "2026-07-22T08:00:00.000000Z"}
    # Spot accepted (orderId present), perp confirmed not accepted -> single-leg.
    # R2-F1: the exposure is recorded AND the attempt counts toward the
    # consecutive-submission-failure brake (fail + consecutive ++); below the
    # threshold the task is still NOT frozen (breakdown §4.5).
    task = _apply(
        store, "t1",
        _outcome(category=D.ATTEMPT_SINGLE_LEG_EXPOSURE, perp_status=D.LEG_REJECTED,
                 perp_qty="0", perp_oid=None, exposure=exposure),
        1_100,
    )
    assert task["status"] == D.STATUS_RUNNING  # below threshold: not frozen
    assert task["leg_exposure"] == exposure
    assert task["success_count"] == 0  # a single_leg is not an accepted pair
    assert task["fail_count"] == 1  # R2-F1: counted toward the brake
    assert task["consecutive_submission_failures"] == 1  # R2-F1: counted toward pause
    store.close()


def test_apply_single_leg_at_threshold_pauses(tmp_path):
    # R2-F1 (user authorization 28 §2.1): a non-rate-limited single_leg counts
    # toward the consecutive-submission-failure brake, exactly like a confirmed
    # failure. The default threshold is 3; reaching it pauses the task.
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1", target=5)
    exposure = {"leg": "spot", "qty": "0.5", "price": "50000",
                "ts": "2026-07-22T08:00:00.000000Z"}
    # Two single-leg outcomes below the threshold keep the task running but DO
    # increment the failure + consecutive counters (defect proof: today they do not).
    for i in range(2):
        task = _apply(
            store, "t1",
            _outcome(category=D.ATTEMPT_SINGLE_LEG_EXPOSURE, perp_status=D.LEG_REJECTED,
                     perp_qty="0", perp_oid=None, exposure=exposure,
                     attempt_id=f"sl{i}"),
            1_100 + i,
        )
        assert task["status"] == D.STATUS_RUNNING
        assert task["fail_count"] == i + 1
        assert task["consecutive_submission_failures"] == i + 1
    # The 3rd consecutive single_leg (>= threshold) pauses the task.
    task = _apply(
        store, "t1",
        _outcome(category=D.ATTEMPT_SINGLE_LEG_EXPOSURE, perp_status=D.LEG_REJECTED,
                 perp_qty="0", perp_oid=None, exposure=exposure, attempt_id="sl2"),
        2_000,
    )
    assert task["fail_count"] == 3
    assert task["consecutive_submission_failures"] == 3
    assert task["status"] == D.STATUS_PAUSED
    assert task["pause_reason"] == D.PAUSE_REASON_CONSECUTIVE_SUBMISSION_FAILURE
    store.close()


def test_apply_single_leg_drains_planned_to_done(tmp_path):
    # R2-F1: the last planned attempt (scheduled reaches target_n) resolved as a
    # single_leg, with the brake NOT yet triggered, completes the task to done —
    # matching the entries.next_action=completed contract (no higher-priority
    # paused/stopped/deleted state applies).
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1", target=1)
    exposure = {"leg": "spot", "qty": "0.5", "price": "50000",
                "ts": "2026-07-22T08:00:00.000000Z"}
    task = _apply(
        store, "t1",
        _outcome(category=D.ATTEMPT_SINGLE_LEG_EXPOSURE, perp_status=D.LEG_REJECTED,
                 perp_qty="0", perp_oid=None, exposure=exposure, attempt_id="sl0"),
        1_100,
    )
    assert task["scheduled_attempt_count"] == 1  # the only planned group, now spent
    assert task["fail_count"] == 1
    assert task["consecutive_submission_failures"] == 1  # below threshold 3
    assert task["status"] == D.STATUS_DONE
    store.close()


def test_apply_failed_at_threshold_pauses(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1", target=5)
    # 2 consecutive submission failures below the threshold (default 3): running.
    for i in range(2):
        task = _apply(
            store, "t1",
            _outcome(category=D.ATTEMPT_FAILED, spot_status=D.LEG_REJECTED,
                     perp_status=D.LEG_REJECTED, spot_qty="0", perp_qty="0",
                     spot_oid=None, perp_oid=None, attempt_id=f"f{i}"),
            1_100 + i,
        )
        assert task["status"] == D.STATUS_RUNNING
        assert task["consecutive_submission_failures"] == i + 1
    # 3rd consecutive failure (>= threshold) -> paused.
    task = _apply(
        store, "t1",
        _outcome(category=D.ATTEMPT_FAILED, spot_status=D.LEG_REJECTED,
                 perp_status=D.LEG_REJECTED, spot_qty="0", perp_qty="0",
                 spot_oid=None, perp_oid=None, attempt_id="f2"),
        2_000,
    )
    assert task["fail_count"] == 3
    assert task["consecutive_submission_failures"] == 3
    assert task["status"] == D.STATUS_PAUSED
    assert task["pause_reason"] == D.PAUSE_REASON_CONSECUTIVE_SUBMISSION_FAILURE
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


# ---------------------------------------------------------------------------
# S3 (ADR-H2): compare-and-swap Start-gate write + same-transaction audit row
# ---------------------------------------------------------------------------

def test_set_start_gate_cas_hits_and_writes_audit_in_same_transaction(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    assert store.get_settings()["version"] == 1
    result = store.set_start_gate_cas(True, 1, 1_000)
    assert result is not None
    assert result["start_gate"] == 1
    assert result["version"] == 2
    # The audit row landed in hedge_open_log (the full legacy projection).
    rows, _ = store.list_logs_page(10, None, None)
    audits = [r for r in rows if r["kind"] == "start_gate_changed"]
    assert len(audits) == 1
    a = audits[0]
    assert a["task_id"] == "start-gate"  # sentinel: a global fact, no owning task
    assert a["attempt_id"] is None
    assert json.loads(a["payload"]) == {
        "enabled": True, "previous_enabled": False, "version": 2, "source": "api",
    }
    store.close()


def test_set_start_gate_cas_miss_returns_none_and_writes_nothing(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    # A wrong expected_version -> None, no gate change, no audit row.
    assert store.set_start_gate_cas(True, 99, 1_000) is None
    assert store.get_settings()["start_gate"] == 0
    assert store.get_settings()["version"] == 1
    rows, _ = store.list_logs_page(10, None, None)
    assert not any(r["kind"] == "start_gate_changed" for r in rows)
    store.close()


def test_set_start_gate_cas_close_records_previous_enabled_true(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    store.set_start_gate_cas(True, 1, 1_000)       # open (v1 -> v2)
    result = store.set_start_gate_cas(False, 2, 2_000)  # close (v2 -> v3)
    assert result["start_gate"] == 0
    assert result["version"] == 3
    rows, _ = store.list_logs_page(10, None, None)
    close = next(r for r in rows if json.loads(r["payload"])["enabled"] is False)
    assert json.loads(close["payload"])["previous_enabled"] is True
    store.close()


# M-1: pin the implicit dependency. The start_gate_changed audit payload's key
# set is exactly the four frozen keys AND is disjoint from the attempt-shape keys
# the frontend (extractHedgeAttempts) uses to detect an attempt card — so a gate
# event carried in the legacy `logs` array never renders as an attempt.
_ATTEMPT_SHAPE_KEYS = {"attempt_seq", "pair_outcome", "spot", "perp"}


def test_m1_start_gate_audit_payload_keys_disjoint_from_attempt_shape(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    store.set_start_gate_cas(True, 1, 1_000)
    rows, _ = store.list_logs_page(10, None, None)
    a = next(r for r in rows if r["kind"] == "start_gate_changed")
    payload = json.loads(a["payload"])
    assert set(payload.keys()) == {"enabled", "previous_enabled", "version", "source"}
    assert set(payload.keys()).isdisjoint(_ATTEMPT_SHAPE_KEYS)
    store.close()


def test_restart_recovers_persisted_state(tmp_path):
    db = str(tmp_path / "ho.sqlite3")
    store = HedgeOpenStore(db)
    _create(store, "t1", target=3)
    _apply(store, "t1", _outcome(), 1_100)
    _apply(store, "t1", _outcome(attempt_id="a2"), 1_200)
    store.close()
    # A new process reopens the same DB and sees the persisted counts.
    store2 = HedgeOpenStore(db)
    task = store2.get_task("t1")
    assert task["success_count"] == 2
    assert task["accepted_pair_count"] == 2
    assert task["status"] == D.STATUS_RUNNING
    store2.close()


# ---------------------------------------------------------------------------
# Additive-forward migration (breakdown §3.9): a round-1 DB opens cleanly
# ---------------------------------------------------------------------------

def test_migrate_adds_new_columns_to_round1_db_and_keeps_rows(tmp_path):
    import sqlite3

    db = str(tmp_path / "round1.sqlite3")
    # Build a round-1-shaped DB: task table WITHOUT the 5 new columns, no
    # attempt/leg tables, plus a settings row and one persisted task row.
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE hedge_open_task ("
        " id TEXT PRIMARY KEY, coin TEXT, direction TEXT, mode TEXT,"
        " single_amount TEXT, target_n INTEGER, success_count INTEGER DEFAULT 0,"
        " fail_count INTEGER DEFAULT 0, status TEXT, q_common TEXT,"
        " position_side_mode TEXT, leg_exposure TEXT, preflight_snapshot TEXT,"
        " creation_seq INTEGER, created_at_us INTEGER, updated_at_us INTEGER)"
    )
    conn.execute(
        "CREATE TABLE hedge_open_settings ("
        " id INTEGER PRIMARY KEY, start_gate INTEGER, executor_mode_snapshot TEXT,"
        " interval_seconds TEXT, interval_us INTEGER, rate_limit_order INTEGER,"
        " version INTEGER, updated_at_us INTEGER)"
    )
    conn.execute(
        "INSERT INTO hedge_open_task (id, coin, direction, mode, single_amount,"
        " target_n, success_count, fail_count, status, q_common,"
        " position_side_mode, leg_exposure, preflight_snapshot,"
        " creation_seq, created_at_us, updated_at_us)"
        " VALUES ('legacy','BTCUSDT','forward','immediate','0.5',3,2,0,'running',"
        "         '0.5','BOTH',NULL,NULL,1,1000,2000)"
    )
    conn.commit()
    conn.close()
    # Open with the new store: additive-forward migration runs idempotently.
    store = HedgeOpenStore(db)
    task = store.get_task("legacy")
    assert task is not None
    assert task["success_count"] == 2            # round-1 data preserved
    assert task["status"] == D.STATUS_RUNNING
    assert task["q_common"] == "0.5"
    assert task["failure_pause_threshold"] == 3   # backfilled frozen default
    assert task["scheduled_attempt_count"] == 0
    assert task["accepted_pair_count"] == 0
    assert task["consecutive_submission_failures"] == 0
    assert task["pause_reason"] is None
    # New attempt/leg tables exist and are empty for the legacy task.
    assert store.list_attempts_for_task("legacy") == []
    # Reopening again is idempotent (no double-ALTER error).
    store.close()
    store_again = HedgeOpenStore(db)
    assert store_again.get_task("legacy")["success_count"] == 2
    store_again.close()
