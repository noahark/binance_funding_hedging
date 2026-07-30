"""Durable store tests for backend/hedge_open_tasks/store.py.

No HTTP, no network. Covers task persistence round-trip, the default-deleted
list filter, attempt outcome application (success/fail/exposure/status), fill +
record-transport log persistence, the aggregate positions projection, settings,
and crash-style restart recovery (reopen the same DB file).
"""
from __future__ import annotations

import json
import sqlite3
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
# T1 fill-figure NULL contract (10-design §1(d)) — stage 2026-07-hedge-order-truth-v1.
# ---------------------------------------------------------------------------


def test_leg_final_fields_t1_null_contract(tmp_path):
    """T1 §1(d) quote NULL contract, each branch: present value verbatim, a true
    "0" preserved (the old ``not in (..., "0", ...)`` check treated it as missing
    — the defect), a missing figure is NULL even with avg_price present (no
    derivation — review-1 r4), missing+underivable -> NULL. A missing figure is
    NEVER coerced to 0."""
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))

    def quote_of(**leg):
        return store._leg_final_fields(leg)[3]

    # present value -> verbatim
    assert quote_of(status="FILLED", filled_qty="0.5",
                    cumulative_quote="25000", avg_price="50000") == "25000"
    # true zero preserved as a real "0" string (NOT collapsed to missing/NULL)
    assert quote_of(status="FILLED", filled_qty="0", cumulative_quote="0") == "0"
    # missing + avg_price present -> still NULL (review-1 r4: no derivation; the
    # old filled_qty * avg_price fallback is gone)
    assert quote_of(status="FILLED", filled_qty="0.5",
                    cumulative_quote=None, avg_price="50000") is None
    # missing + underivable -> NULL (the T1 fix: unknown, not a fake 0)
    assert quote_of(status="FILLED", filled_qty="0.5",
                    cumulative_quote=None, avg_price=None) is None
    # missing, no fill -> NULL
    assert quote_of(status="NEW", filled_qty="0", cumulative_quote=None) is None
    store.close()


def test_resolve_attempt_persists_null_quote_when_absent_no_derivation(tmp_path):
    """Review-1 r4 (user decision 2026-07-29): a resolved leg whose outcome
    carried no ``cumulative_quote`` but a positive fill + ``avg_price`` used to
    derive ``filled_qty * avg_price`` into ``cumulative_quote_amt``. Under the
    verbatim rule the store records NULL — no derivation, ever. This locks the
    removed fallback at the persistence layer (resolve_attempt -> leg row), not
    just at the helper (covered by test_leg_final_fields_t1_null_contract), so it
    cannot be silently reinstated."""
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "tn", direction=D.DIR_FORWARD, target=1)
    attempt = store.prepare_attempt(
        "tn", "att1", D.DIR_FORWARD, "0.5", D.POS_MODE_BOTH,
        {"est_price": "50000"}, "hgo-att1-s", {"side": "BUY"},
        "hgo-att1-p", {"side": "SELL"}, 1_000,
    )
    # avg_price present and filled_qty > 0, but NO cumulative_quote: the old path
    # derived 0.5 * 50000 = 25000; the verbatim rule stores NULL on both legs.
    outcome = AttemptOutcome(
        attempt_id="att1", category=D.ATTEMPT_SUCCESS,
        spot={"status": D.LEG_FILLED, "filled_qty": "0.5", "avg_price": "50000",
              "order_id": "os", "client_order_id": "hgo-att1-s"},
        perp={"status": D.LEG_FILLED, "filled_qty": "0.5", "avg_price": "50000",
              "order_id": "op", "client_order_id": "hgo-att1-p"},
        record_payload={"transport": "dry_run_record", "posted": False,
                        "spot_order_params": {}, "perp_order_params": {}},
        exposure=None,
    )
    store.resolve_attempt(attempt["id"], outcome, 1_100)
    legs = {leg["leg"]: leg for leg in store.list_legs_for_attempt(attempt["id"])}
    assert legs["spot"]["cumulative_quote_amt"] is None
    assert legs["perp"]["cumulative_quote_amt"] is None
    store.close()


def test_aggregate_positions_skips_null_quote_and_flags_incomplete(tmp_path):
    """T1 §1(d): a leg with a real fill but a NULL quote (unknown figure)
    contributes its qty to the position but NOT its notional — averaging an
    unknown as 0 would drag the avg price down. The bucket is flagged
    ``avg_price_incomplete`` instead, so a reader knows the avg is partial."""
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "tn", direction=D.DIR_FORWARD, target=1)
    attempt = store.prepare_attempt(
        "tn", "att1", D.DIR_FORWARD, "0.5", D.POS_MODE_BOTH,
        {"est_price": "50000"}, "hgo-att1-s", {"side": "BUY"},
        "hgo-att1-p", {"side": "SELL"}, 1_000,
    )
    perp_leg = next(l for l in store.list_legs_for_attempt(attempt["id"])
                    if l["leg"] == "perp")
    # Resolve the perp leg FILLED with base>0 but quote=NULL (T1 unknown figure).
    store.resolve_leg_from_query(
        perp_leg["id"], exchange_status=D.LEG_FILLED, order_id="op",
        base_qty="0.5", quote_amt=None, fee_amount=None, fee_asset=None,
        now_us=2_000, terminal=True,
    )
    pos = next(p for p in store.aggregate_positions() if p["coin"] == "BTCUSDT")
    # The perp's real qty contributes (FORWARD perp = a short -> -0.5), but its
    # NULL notional is skipped so the avg is computed over nothing for that side.
    assert Decimal(pos["position_qty"]) == Decimal("-0.5")
    assert pos["perp_avg_price_incomplete"] is True      # flagged incomplete
    assert Decimal(pos["perp_avg"]) == Decimal("0")      # notional skipped -> 0/qty
    assert pos["spot_avg_price_incomplete"] is False      # spot side untouched
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


# ---------------------------------------------------------------------------
# T1/T5(d) historical-data migration (10-design §6) — stage
# 2026-07-hedge-order-truth-v1. M1 (rewrite a FILLED leg's placeholder '0' quote
# to NULL) was REMOVED in review-1 r5: that cross-field rewrite is exactly the
# derivation 00-task.md §T1 (2026-07-29 Scope decision) put out of scope — a
# literal '0' the exchange sent is kept verbatim. M2 remains: it rewrites a 1970
# leg_exposure ts to the accepting leg's real dispatched_at_us ISO. M2's change
# is audited as data_migration; idempotent on a second reopen.
# ---------------------------------------------------------------------------


def test_migrate_m1_m2_repair_defect_rows_audit_then_idempotent(tmp_path):
    db = str(tmp_path / "ho.sqlite3")
    store = HedgeOpenStore(db)
    _create(store, "t1", direction=D.DIR_FORWARD, target=1)
    attempt = store.prepare_attempt(
        "t1", "att1", D.DIR_FORWARD, "0.5", D.POS_MODE_BOTH,
        {"est_price": "50000"}, "hgo-att1-s", {"side": "BUY"},
        "hgo-att1-p", {"side": "SELL"}, 5_000_000,
    )
    perp_leg_id = next(l["id"] for l in store.list_legs_for_attempt(attempt["id"])
                       if l["leg"] == "perp")
    # Plant the defect state: a FILLED perp leg with base>0 and a literal '0'
    # quote, and a leg_exposure frozen at the 1970 epoch (T5). After review-1 r5
    # the '0' is KEPT verbatim (T1 2026-07-29 Scope decision: store what the
    # exchange returned; a literal 0 is the exchange's answer, not a placeholder
    # this stage rewrites); only the 1970 ts is repaired (M2).
    with store._lock:
        store._conn.execute(
            "UPDATE hedge_open_leg SET exchange_status = ?, cumulative_base_qty = '0.5',"
            " cumulative_quote_amt = '0', order_id = 'op',"
            " dispatch_state = ?, dispatched_at_us = ?, terminal = 1 WHERE id = ?",
            (D.LEG_FILLED, D.LEG_TERMINAL_RECORDED, 5_000_000, perp_leg_id),
        )
        store._conn.execute(
            "UPDATE hedge_open_task SET leg_exposure = ? WHERE id = ?",
            (json.dumps({"leg": "perp", "qty": "0.5", "price": None,
                         "ts": "1970-01-01T00:00:00.000000Z"}), "t1"),
        )
        store._conn.commit()
    store.close()

    # Reopen with the opt-in flag (D6) -> M2 fires and repairs the ts; M1 is gone,
    # so the literal '0' stays. A default construction would leave the row untouched.
    store2 = HedgeOpenStore(db, repair_legacy_exposure_ts=True)
    leg = next(l for l in store2.list_legs_for_attempt(attempt["id"]) if l["leg"] == "perp")
    assert leg["cumulative_quote_amt"] == "0"           # M1 removed: literal '0' kept verbatim
    expo = store2.get_task("t1")["leg_exposure"]
    assert expo["ts"] == D.us_to_iso(5_000_000)          # M2: real dispatched_at_us ISO
    assert expo["ts"] != "1970-01-01T00:00:00.000000Z"
    assert expo["price"] is None                         # M2 leaves price null (unknown)
    events = store2.list_task_event_logs(50, kinds=("data_migration",))
    assert len(events) == 1                              # M2 only — M1 was removed
    fields = {json.loads(e["payload"])["field"] for e in events}
    assert fields == {"leg_exposure.ts"}
    store2.close()

    # Second reopen (opt-in again) -> idempotent: the ts is no longer the 1970
    # epoch, so M2's SELECT finds nothing and no new data_migration event is added.
    store3 = HedgeOpenStore(db, repair_legacy_exposure_ts=True)
    assert len(store3.list_task_event_logs(50, kinds=("data_migration",))) == 1
    store3.close()


def _leg_row(order_id, base, quote):
    """A minimal hedge_open_leg-shaped sqlite3.Row for ``_exposure_from_legs``
    unit tests — the three columns the adapter reads."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE leg(order_id TEXT, cumulative_base_qty TEXT,"
        " cumulative_quote_amt TEXT)"
    )
    conn.execute("INSERT INTO leg VALUES (?, ?, ?)", (order_id, base, quote))
    return conn.execute("SELECT * FROM leg").fetchone()


# ---------------------------------------------------------------------------
# D1 / D4 — _exposure_from_legs delegates to domain.build_leg_exposure.
# S1: a NULL quote yields price = None, not a fabricated zero (the deleted store
# copy turned _num(NULL) into Decimal(0) and wrote "0E+1"). D4: one rule, not two
# that drift. Backstop: ts_us <= 0 raises (the T5 fix the deleted copy lacked).
# ---------------------------------------------------------------------------


def test_exposure_from_legs_null_quote_is_unknown_not_zero_price():
    """D1/S1 pairing (missing figure): an accepted, filled leg with a NULL quote
    reports ``price = None`` — unknown, never a coerced zero."""
    spot = _leg_row("os", "0.5", None)        # accepted, real qty, NULL quote
    perp = _leg_row(None, "0", None)          # not accepted
    expo = HedgeOpenStore._exposure_from_legs(spot, perp, 5_000_000)
    assert expo["leg"] == "spot"
    assert expo["price"] is None              # S1 fix: unknown, not "0E+1"
    assert expo["qty"] == "0.5"
    assert expo["ts"] == D.us_to_iso(5_000_000)


def test_exposure_from_legs_real_zero_quote_is_zero_price():
    """D1/S1 pairing (real zero): a real exchange ``"0"`` quote on an accepted,
    filled leg is a true zero — ``price = "0"``. This is the r5 category no static
    guard can reach (a real zero vs a fabricated one at rest): only the pairing
    with the test above covers it."""
    spot = _leg_row("os", "0.5", "0")         # accepted, real qty, REAL "0" quote
    perp = _leg_row(None, "0", None)
    expo = HedgeOpenStore._exposure_from_legs(spot, perp, 5_000_000)
    assert Decimal(expo["price"]) == Decimal("0")  # real "0" -> numeric zero (str form varies)


def test_exposure_from_legs_real_figure_price_is_quote_over_base():
    """D4: delegating to domain.build_leg_exposure preserves the deleted store
    copy's observable output for a real figure — ``price = quote / base``."""
    spot = _leg_row("os", "0.5", "25000")     # price = 25000 / 0.5 = 50000
    perp = _leg_row(None, "0", None)
    expo = HedgeOpenStore._exposure_from_legs(spot, perp, 5_000_000)
    assert Decimal(expo["price"]) == Decimal("50000")  # quote / base, value unchanged
    assert expo["qty"] == "0.5"


def test_exposure_from_legs_non_positive_ts_raises():
    """D4 backstop: build_leg_exposure raises on ``ts_us <= 0`` (the T5 fix). The
    deleted store copy did not, so this is a new failure mode on the reconcile
    path, contained by the worker's exception handling. Cover it so a future
    change is not mistaken for a regression."""
    spot = _leg_row("os", "0.5", "25000")
    perp = _leg_row(None, "0", None)
    with pytest.raises(D.HedgeError):
        HedgeOpenStore._exposure_from_legs(spot, perp, 0)


# ---------------------------------------------------------------------------
# D2 — fill_rows loop: a NULL avg_price (unknown) adds no fabricated 0 notional
# and sets the incomplete flag (the leg_rows path's policy); a real "0" avg_price
# is a true zero and contributes 0 without flagging.
# ---------------------------------------------------------------------------


def test_aggregate_positions_fill_null_avg_price_excluded_and_flagged(tmp_path):
    """D2/S2 (missing figure): a legacy fill row FILLED with a real qty but a NULL
    avg_price must NOT add a fabricated 0 to its notional. Its qty still counts;
    the bucket is flagged incomplete (same policy as the leg_rows path)."""
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "tn", direction=D.DIR_FORWARD, target=1)
    store.insert_fill(
        "tn", "att1",
        AttemptOutcome(
            attempt_id="att1", category=D.ATTEMPT_SUCCESS,
            spot={"status": D.LEG_FILLED, "filled_qty": "0.5", "avg_price": None,
                  "order_id": "os", "client_order_id": "hgo-att1-s"},
            perp={"status": D.LEG_FILLED, "filled_qty": "0.5", "avg_price": "50000",
                  "order_id": "op", "client_order_id": "hgo-att1-p"},
            record_payload={"transport": "dry_run_record", "posted": False,
                            "spot_order_params": {}, "perp_order_params": {}},
            exposure=None,
        ),
        1_000,
    )
    pos = next(p for p in store.aggregate_positions() if p["coin"] == "BTCUSDT")
    assert pos["spot_avg_price_incomplete"] is True   # NULL avg -> flagged
    assert Decimal(pos["spot_avg"]) == Decimal("0")   # notional skipped -> 0/qty
    assert pos["perp_avg_price_incomplete"] is False  # real perp avg unaffected
    assert Decimal(pos["perp_avg"]) == Decimal("50000")
    store.close()


def test_aggregate_positions_fill_real_zero_avg_price_contributes_zero(tmp_path):
    """D2/S2 pairing (real zero): a real exchange ``"0"`` avg_price is a true zero,
    not missing — it contributes 0 notional (q * 0) and does NOT set the
    incomplete flag. The r5 category: a real zero stays distinct from unknown."""
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "tn", direction=D.DIR_FORWARD, target=1)
    store.insert_fill(
        "tn", "att1",
        AttemptOutcome(
            attempt_id="att1", category=D.ATTEMPT_SUCCESS,
            spot={"status": D.LEG_FILLED, "filled_qty": "0.5", "avg_price": "0",
                  "order_id": "os", "client_order_id": "hgo-att1-s"},
            perp={"status": D.LEG_FILLED, "filled_qty": "0.5", "avg_price": "50000",
                  "order_id": "op", "client_order_id": "hgo-att1-p"},
            record_payload={"transport": "dry_run_record", "posted": False,
                            "spot_order_params": {}, "perp_order_params": {}},
            exposure=None,
        ),
        1_000,
    )
    pos = next(p for p in store.aggregate_positions() if p["coin"] == "BTCUSDT")
    assert pos["spot_avg_price_incomplete"] is False  # real "0" is not unknown
    assert Decimal(pos["spot_avg"]) == Decimal("0")   # 0.5 * 0 / 0.5
    assert Decimal(pos["perp_avg"]) == Decimal("50000")
    store.close()


# ---------------------------------------------------------------------------
# D6 — default construction performs no semantic row rewrite (the 2026-07-28
# incident is structurally impossible, not forbidden by prose). Additive DDL
# still writes the file; this asserts only "no row rewrite".
# ---------------------------------------------------------------------------


def test_default_construction_leaves_legacy_exposure_ts_untouched(tmp_path):
    """D6: a default ``HedgeOpenStore`` construction mutates no existing row. The
    1970-epoch leg_exposure ts that M2 would rewrite stays exactly as planted —
    the row-mutating repair is opt-in, and no production caller passes the flag."""
    db = str(tmp_path / "ho.sqlite3")
    store = HedgeOpenStore(db)
    _create(store, "t1", direction=D.DIR_FORWARD, target=1)
    with store._lock:
        store._conn.execute(
            "UPDATE hedge_open_task SET leg_exposure = ? WHERE id = ?",
            (json.dumps({"leg": "perp", "qty": "0.5", "price": None,
                         "ts": "1970-01-01T00:00:00.000000Z"}), "t1"),
        )
        store._conn.commit()
    store.close()

    # Default reopen -> the repairable row is untouched (no M2, no data_migration).
    store2 = HedgeOpenStore(db)
    expo = store2.get_task("t1")["leg_exposure"]
    assert expo["ts"] == "1970-01-01T00:00:00.000000Z"   # untouched
    assert store2.list_task_event_logs(50, kinds=("data_migration",)) == []
    store2.close()


# ---------------------------------------------------------------------------
# D7 — prepare_attempt seeds an UNKNOWN quote (NULL), not a self-authored '0'.
# S4: the dispatch-state update never touches either figure column, so the seeded
# unknown survives into the in-flight projection the UI reads.
# ---------------------------------------------------------------------------


def test_prepare_attempt_seeds_unknown_quote_not_zero(tmp_path):
    """D7/S4: a freshly prepared leg carries an UNKNOWN quote (NULL) — no exchange
    contact has happened, so seeding a zero figure would fabricate money the
    exchange never returned. cumulative_base_qty keeps its '0' seed (NOT NULL
    column; quantity is a non-goal §3)."""
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1", target=1)
    attempt = store.prepare_attempt(
        "t1", "att1", D.DIR_FORWARD, "0.5", D.POS_MODE_BOTH,
        {"est_price": "50000"}, "hgo-att1-s", {"side": "BUY"},
        "hgo-att1-p", {"side": "SELL"}, 1_000,
    )
    legs = {leg["leg"]: leg for leg in store.list_legs_for_attempt(attempt["id"])}
    assert legs["spot"]["cumulative_quote_amt"] is None    # D7: NULL, not '0'
    assert legs["perp"]["cumulative_quote_amt"] is None
    assert legs["spot"]["cumulative_base_qty"] == "0"      # qty seed unchanged
    assert legs["perp"]["cumulative_base_qty"] == "0"
    store.close()


def test_inflight_leg_projects_unknown_notional_not_zero(tmp_path):
    """D7/S4 (the live consequence): a dispatched leg holding a real order_id and
    sitting at exchange_status = NEW — not yet resolved — still projects an
    UNKNOWN notional (NULL), not the self-authored '0' it was seeded with before
    D7. list_attempts_page is the projection the UI reads for in-flight legs."""
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1", target=1)
    attempt = store.prepare_attempt(
        "t1", "att1", D.DIR_FORWARD, "0.5", D.POS_MODE_BOTH,
        {"est_price": "50000"}, "hgo-att1-s", {"side": "BUY"},
        "hgo-att1-p", {"side": "SELL"}, 1_000,
    )
    # Spot sent + accepted (real order_id, NEW/polling); perp still querying. The
    # dispatch-state update moves neither figure column.
    store.mark_leg_querying(
        attempt["id"], "spot", D.LEG_ACCEPTED_OR_QUERYING, "os", 2_000,
    )
    store.mark_leg_querying(
        attempt["id"], "perp", D.LEG_UNKNOWN_QUERYING, None, 2_000,
    )
    page = store.list_attempts_page(10, None, None)
    _attempt, spot_leg, perp_leg = page[0]
    assert spot_leg["order_id"] == "os"                    # in-flight, accepted
    assert spot_leg["cumulative_quote_amt"] is None        # unknown, not '0'
    assert perp_leg["cumulative_quote_amt"] is None
    store.close()


# ---------------------------------------------------------------------------
# T2 attempt-row category rollup (10-design §2(e)) — stage
# 2026-07-hedge-order-truth-v1. The attempt row carries the truthful per-pair
# diagnosis (e.g. 51169 -> collateral_cap) rather than the all-NULL verdict the
# live evidence showed. The rollup is a pure derived read of the leg rows.
# ---------------------------------------------------------------------------


def _rejected_outcome(
    *, attempt_id="att1", spot_cat=None, spot_code=None,
    perp_cat=None, perp_code=None,
) -> AttemptOutcome:
    """A failed pair (neither orderId) whose legs may carry a classified exchange
    code. Mirrors the live dispatch path's rejected LegDispatch shape (status /
    filled_qty / avg_price / order_id / client_order_id + optional error_*)."""
    spot = {"status": D.LEG_REJECTED, "filled_qty": "0", "avg_price": "0",
            "order_id": None, "client_order_id": f"hgo-{attempt_id}-s"}
    perp = {"status": D.LEG_REJECTED, "filled_qty": "0", "avg_price": "0",
            "order_id": None, "client_order_id": f"hgo-{attempt_id}-p"}
    if spot_cat is not None:
        spot["error_category"] = spot_cat
        spot["error_code"] = spot_code
    if perp_cat is not None:
        perp["error_category"] = perp_cat
        perp["error_code"] = perp_code
    return AttemptOutcome(
        attempt_id=attempt_id, category=D.ATTEMPT_FAILED,
        spot=spot, perp=perp,
        record_payload={"transport": "dry_run_record", "posted": False,
                        "spot_order_params": {}, "perp_order_params": {}},
        exposure=None,
    )


def test_resolve_attempt_rolls_up_collateral_cap_to_attempt_row(tmp_path):
    # The core §2(e) fix: a 51169 spot leg surfaces on the ATTEMPT row as
    # collateral_cap (with its code), not NULL.
    store = HedgeOpenStore(tmp_path / "h.db")
    _create(store, task_id="t1", target=5)
    outcome = _rejected_outcome(
        spot_cat=D.ERROR_CATEGORY_COLLATERAL_CAP, spot_code="51169",
    )
    attempt = store.prepare_attempt(
        "t1", outcome.attempt_id, D.DIR_FORWARD, "0.5", D.POS_MODE_BOTH,
        {"est_price": "50000"}, f"hgo-{outcome.attempt_id}-s", {"side": "BUY"},
        f"hgo-{outcome.attempt_id}-p", {"side": "SELL"}, 1_000,
    )
    store.resolve_attempt(attempt["id"], outcome, 2_000)
    row = store.get_attempt(attempt["id"])
    assert row["error_category"] == D.ERROR_CATEGORY_COLLATERAL_CAP
    assert row["error_code"] == "51169"


def test_resolve_attempt_rollup_fatal_beats_collateral_cap_and_stops(tmp_path):
    # Priority fatal > collateral_cap: a fatal perp leg wins the attempt row AND
    # stops the task (the rollup derives fatal the same way the old single-fatal
    # scan did, so stop semantics are unchanged).
    store = HedgeOpenStore(tmp_path / "h.db")
    _create(store, task_id="t1", target=5)
    outcome = _rejected_outcome(
        spot_cat=D.ERROR_CATEGORY_COLLATERAL_CAP, spot_code="51169",
        perp_cat=D.ERROR_CATEGORY_FATAL, perp_code="-1013",
    )
    attempt = store.prepare_attempt(
        "t1", outcome.attempt_id, D.DIR_FORWARD, "0.5", D.POS_MODE_BOTH,
        {"est_price": "50000"}, f"hgo-{outcome.attempt_id}-s", {"side": "BUY"},
        f"hgo-{outcome.attempt_id}-p", {"side": "SELL"}, 1_000,
    )
    store.resolve_attempt(attempt["id"], outcome, 2_000)
    row = store.get_attempt(attempt["id"])
    assert row["error_category"] == D.ERROR_CATEGORY_FATAL
    assert row["error_code"] == "-1013"
    task = store.get_task("t1")
    assert task["status"] == D.STATUS_STOPPED
    assert task["stop_reason"] == D.STOP_REASON_EXCHANGE_FATAL


def test_finalize_attempt_rolls_up_category_from_leg_rows(tmp_path):
    # The reconcile/drain path: both legs were left querying, then resolved to
    # terminal by client-ID queries. finalize_attempt rolls the leg rows' categories
    # up to the attempt row — the 51169 spot leg surfaces as collateral_cap.
    store = HedgeOpenStore(tmp_path / "h.db")
    _create(store, task_id="t1", target=5)
    attempt = store.prepare_attempt(
        "t1", "att1", D.DIR_FORWARD, "0.5", D.POS_MODE_BOTH,
        {"est_price": "50000"}, "hgo-att1-s", {"side": "BUY"},
        "hgo-att1-p", {"side": "SELL"}, 1_000,
    )
    legs = {row["leg"]: row for row in store.list_legs_for_attempt(attempt["id"])}
    store.resolve_leg_from_query(
        legs["spot"]["id"], exchange_status=D.LEG_REJECTED, order_id=None,
        base_qty="0", quote_amt="0", fee_amount=None, fee_asset=None,
        now_us=2_000, terminal=True,
        error_code="51169", error_category=D.ERROR_CATEGORY_COLLATERAL_CAP,
    )
    store.resolve_leg_from_query(
        legs["perp"]["id"], exchange_status=D.LEG_REJECTED, order_id=None,
        base_qty="0", quote_amt="0", fee_amount=None, fee_asset=None,
        now_us=2_000, terminal=True, error_code=None, error_category=None,
    )
    store.finalize_attempt(attempt["id"], 3_000)
    row = store.get_attempt(attempt["id"])
    assert row["pair_outcome"] is not None
    assert row["error_category"] == D.ERROR_CATEGORY_COLLATERAL_CAP
    assert row["error_code"] == "51169"


def test_settle_attempt_no_counters_records_rollup_without_stopping(tmp_path):
    # A 429-settled pair (amendment 21): control flow is unchanged — counters stay
    # skipped and the task is NOT stopped, even when a leg carries a fatal code.
    # But §2(e) still records the truthful rolled-up diagnosis on the attempt row.
    store = HedgeOpenStore(tmp_path / "h.db")
    _create(store, task_id="t1", target=5)
    attempt = store.prepare_attempt(
        "t1", "att1", D.DIR_FORWARD, "0.5", D.POS_MODE_BOTH,
        {"est_price": "50000"}, "hgo-att1-s", {"side": "BUY"},
        "hgo-att1-p", {"side": "SELL"}, 1_000,
    )
    store.mark_attempt_rate_limited(attempt["id"])
    legs = {row["leg"]: row for row in store.list_legs_for_attempt(attempt["id"])}
    store.resolve_leg_from_query(
        legs["spot"]["id"], exchange_status=D.LEG_REJECTED, order_id=None,
        base_qty="0", quote_amt="0", fee_amount=None, fee_asset=None,
        now_us=2_000, terminal=True,
        error_code="51169", error_category=D.ERROR_CATEGORY_COLLATERAL_CAP,
    )
    store.resolve_leg_from_query(
        legs["perp"]["id"], exchange_status=D.LEG_REJECTED, order_id=None,
        base_qty="0", quote_amt="0", fee_amount=None, fee_asset=None,
        now_us=2_000, terminal=True,
        error_code="-1013", error_category=D.ERROR_CATEGORY_FATAL,
    )
    settled = store.settle_attempt_no_counters(attempt["id"], 3_000)
    assert settled is True
    row = store.get_attempt(attempt["id"])
    assert row["pair_outcome"] is not None
    # Priority fatal > collateral_cap on the recorded category...
    assert row["error_category"] == D.ERROR_CATEGORY_FATAL
    assert row["error_code"] == "-1013"
    # ...yet the task is NOT stopped (429 settle never stops; a fatal fact would
    # re-surface and stop on the next dispatch's fresh POST via resolve_attempt).
    task = store.get_task("t1")
    assert task["status"] != D.STATUS_STOPPED
    assert task["stop_reason"] is None
    assert task["fail_count"] == 0  # counters skipped


# ---------------------------------------------------------------------------
# T3 raw-response persistence (10-design §3) — stage 2026-07-hedge-order-truth-v1.
# Every real exchange interaction is persisted verbatim (sanitized to the response
# body only) so the next 51169 is explainable from the DB alone.
# ---------------------------------------------------------------------------


def _prepared_attempt(store, task_id="t1", attempt_id="att1"):
    _create(store, task_id=task_id, target=5)
    return store.prepare_attempt(
        task_id, attempt_id, D.DIR_FORWARD, "0.5", D.POS_MODE_BOTH,
        {"est_price": "50000"}, f"hgo-{attempt_id}-s", {"side": "BUY"},
        f"hgo-{attempt_id}-p", {"side": "SELL"}, 1_000,
    )


def test_append_raw_response_stores_body_byte_for_byte(tmp_path):
    # 10-design §3(d): the body is the exchange RESPONSE only, persisted verbatim.
    store = HedgeOpenStore(tmp_path / "h.db")
    attempt = _prepared_attempt(store)
    body = '{"code":51169,"msg":"MARGIN_TRADE_COEFF_INSUFFICIENT"}'
    raw = {"http_status": 400, "transport_error": None, "code": "51169",
           "msg": "MARGIN_TRADE_COEFF_INSUFFICIENT", "body": body}
    store.append_raw_response(
        attempt["id"], "spot", "hgo-att1-s", "order_post", D.SPOT_ORDER_PATH, raw, 2_000,
    )
    rows = store.list_raw_responses_for_attempt(attempt["id"])
    assert len(rows) == 1
    r = rows[0]
    assert r["attempt_id"] == attempt["id"]
    assert r["leg"] == "spot"
    assert r["client_order_id"] == "hgo-att1-s"
    assert r["source"] == "order_post"
    assert r["endpoint"] == D.SPOT_ORDER_PATH
    assert r["http_status"] == 400
    assert r["transport_error"] is None
    assert r["business_code"] == "51169"
    assert r["business_msg"] == "MARGIN_TRADE_COEFF_INSUFFICIENT"
    assert r["body"] == body  # byte-for-byte, no rewriting
    assert r["body_truncated"] == 0
    assert r["captured_at_us"] == 2_000


def test_append_raw_response_truncates_oversized_body(tmp_path):
    # 10-design §3(c): body is capped at BODY_MAX_BYTES; the cap is signalled.
    store = HedgeOpenStore(tmp_path / "h.db")
    attempt = _prepared_attempt(store)
    big = "x" * (D.BODY_MAX_BYTES + 100)
    raw = {"http_status": 200, "transport_error": None, "code": None,
           "msg": None, "body": big}
    store.append_raw_response(
        attempt["id"], "perp", None, "order_query", D.PERP_ORDER_PATH, raw, 3_000,
    )
    r = store.list_raw_responses_for_attempt(attempt["id"])[0]
    assert len(r["body"]) == D.BODY_MAX_BYTES
    assert r["body_truncated"] == 1


def test_append_raw_response_decisive_row_not_overwritten_by_later_non_decisive(tmp_path):
    # Review-1 r5 P1 (00-task.md §T3): a decisive row is never replaced — first
    # decisive wins. A first FILLED (decisive) row must survive a later NEW
    # (non-decisive) response for the same (attempt, leg, source): same row id, the
    # FILLED body kept, the row still stamped decisive. This is the guard that
    # proves the flag is real and not a last-write-wins overwrite.
    store = HedgeOpenStore(tmp_path / "h.db")
    attempt = _prepared_attempt(store)
    raw_filled = {"http_status": 200, "transport_error": None, "code": None,
                  "msg": None, "body": '{"status":"FILLED"}'}
    raw_new = {"http_status": 200, "transport_error": None, "code": None,
               "msg": None, "body": '{"status":"NEW"}'}
    rid = store.append_raw_response(
        attempt["id"], "spot", "cid", "order_query", D.SPOT_ORDER_PATH, raw_filled, 1_000,
        decisive=True,
    )
    rid2 = store.append_raw_response(
        attempt["id"], "spot", "cid", "order_query", D.SPOT_ORDER_PATH, raw_new, 2_000,
        decisive=False,
    )
    assert rid == rid2  # same row — the decisive row was not replaced
    rows = store.list_raw_responses_for_attempt(attempt["id"])
    assert len(rows) == 1
    r = rows[0]
    assert r["body"] == raw_filled["body"]  # FILLED kept, not the later NEW
    assert r["decisive"] == 1
    assert r["captured_at_us"] == 1_000     # untouched (not overwritten at 2_000)
    store.close()


def test_raw_response_table_has_no_credential_columns(tmp_path):
    # 10-design §3(d): credentials live only on the REQUEST side; the raw table
    # persists the response only. No signature / api key / request column exists.
    store = HedgeOpenStore(tmp_path / "h.db")
    cols = {
        r["name"] for r in store._conn.execute("PRAGMA table_info(hedge_open_raw_response)")
    }
    for secret in ("signature", "apikey", "api_key", "x_mbx_apikey", "secret", "request_body"):
        assert secret not in cols, f"raw table must not carry a {secret!r} column"
    # The persisted columns are exactly the response-derived set (plus the
    # ``decisive`` verdict flag — review-1 r5 — which is response-derived, not a
    # credential).
    assert cols == {
        "id", "attempt_id", "leg", "client_order_id", "source", "endpoint",
        "http_status", "transport_error", "business_code", "business_msg",
        "body", "body_truncated", "captured_at_us", "decisive",
    }
