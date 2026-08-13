"""Service orchestration tests for backend/hedge_open_tasks/service.py.

No HTTP, no network. Covers task create with an injectable preflight provider
(accept / insufficient_balance / filter violation / dry-run no-snapshot), the
task lifecycle (start/pause/delete/fill-once/fill-all) incl. invalid_state, the
single-leg exposure (advisory, never a freeze) and the >=threshold
consecutive-submission-failure pause via injected record-transport seeds, the
Start-gated per-task scheduler tick, and the default-off posture: with no live
executor injected the dry-run record transport stays and a real POST is
unreachable (a real POST requires an injected live executor + Start + a fresh
preflight, wired only by the server under ``APP_HEDGE_EXECUTOR=live``).
"""
from __future__ import annotations

import threading
import time
from decimal import Decimal

import pytest

from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.executor import (
    AttemptOutcome,
    DisabledHedgeExecutor,
)
from backend.tests.fakes import OutcomeSpec, RecordTransportFake
from backend.hedge_open_tasks.service import (
    HedgeOpenTaskService,
    PreflightProvider,
    attempt_to_doc,
    settings_to_doc,
)


class _Clock:
    def __init__(self, t0=0):
        self.t = t0

    def mono_us(self):
        return self.t

    def wall_us(self):
        return self.t


class _StubPreflight(PreflightProvider):
    def __init__(self, snapshot):
        self._snapshot = snapshot

    def get_snapshot(self, coin, direction, task_type="open"):
        return self._snapshot


def _spot_filters():
    return {
        "lot_size": {"min_qty": "0.00001", "max_qty": "9000", "step_size": "0.00001"},
        "market_lot_size": {"min_qty": "0", "max_qty": "9000", "step_size": "0"},
        "notional": {"min_notional": "5", "apply_min_to_market": True},
    }


def _perp_filters():
    return {
        "lot_size": {"min_qty": "0.001", "max_qty": "1000", "step_size": "0.001"},
        "market_lot_size": {"min_qty": "0.001", "max_qty": "120", "step_size": "0.001"},
        "notional": {"notional": "50"},
    }


def _snapshot(balances, *, position_mode="BOTH", est_price="50000", spot_symbol=None):
    return D.PreflightSnapshot(
        spot_filters=_spot_filters(),
        perp_filters=_perp_filters(),
        balances=balances,
        position_mode=position_mode,
        est_price=Decimal(est_price) if est_price else None,
        spot_symbol=spot_symbol,
    )


def _svc(tmp_path, *, executor=None, preflight=None, mode="disabled", clock=None):
    return HedgeOpenTaskService(
        str(tmp_path / "ho.sqlite3"),
        executor=executor,
        preflight_provider=preflight,
        mode=mode,
        mono_us=clock.mono_us if clock else None,
        wall_us=clock.wall_us if clock else None,
    )


def _create_body(direction=D.DIR_FORWARD, single_amount="0.5", target_n=3):
    return {
        "coin": "BTCUSDT", "direction": direction, "mode": "immediate",
        "single_amount": single_amount, "target_n": target_n,
    }


# ---------------------------------------------------------------------------
# create_task + preflight
# ---------------------------------------------------------------------------

def test_create_with_preflight_resolves_q_common(tmp_path):
    svc = _svc(tmp_path, preflight=_StubPreflight(_snapshot({"USDT": Decimal("100000")})))
    status, doc = svc.create_task(_create_body())
    assert status == 201
    assert doc["q_common"] == "0.5"
    assert doc["position_side_mode"] == "BOTH"
    assert doc["status"] == D.STATUS_RUNNING
    assert doc["success_count"] == 0


def test_service_records_resolved_bstock_spot_symbol(tmp_path):
    executor = RecordTransportFake()
    preflight = _StubPreflight(
        _snapshot(
            {"USDT": Decimal("100000")},
            est_price="100",
            spot_symbol="TSLABUSDT",
        )
    )
    svc = _svc(tmp_path, executor=executor, preflight=preflight)
    status, doc = svc.create_task({
        "coin": "TSLAUSDT",
        "direction": D.DIR_FORWARD,
        "mode": "immediate",
        "single_amount": "0.5",
        "target_n": 1,
    })
    assert status == 201
    svc.post_fill_once(doc["id"])
    assert executor.records[0]["spot_order_params"]["symbol"] == "TSLABUSDT"
    assert executor.records[0]["perp_order_params"]["symbol"] == "TSLAUSDT"


def test_create_default_provider_is_dry_run_no_q_common(tmp_path):
    # No preflight provider -> dry-run snapshot absent -> task still created.
    svc = _svc(tmp_path)
    status, doc = svc.create_task(_create_body())
    assert status == 201
    assert doc["q_common"] is None
    assert doc["position_side_mode"] is None


def test_close_create_is_atomic_paused_and_zero_external_reads(tmp_path):
    executor = RecordTransportFake()
    svc = _svc(
        tmp_path,
        executor=executor,
        preflight=_StubPreflight(_snapshot({"USDT": Decimal("100000")})),
    )
    _, opened = svc.create_task(_create_body(target_n=1))
    svc.post_fill_all(opened["id"])

    class _NoCloseCreateReads:
        def check_symbol_legs(self, coin):  # pragma: no cover - must not run
            raise AssertionError("close create must not probe exchangeInfo")

        def get_snapshot(self, *args, **kwargs):  # pragma: no cover - must not run
            raise AssertionError("close create must not read a preflight snapshot")

    svc._preflight = _NoCloseCreateReads()
    status, doc = svc.create_task({
        **_create_body(target_n=2), "task_type": D.TASK_TYPE_CLOSE,
    })
    assert status == 201
    assert doc["status"] == D.STATUS_PAUSED
    assert doc["pause_reason"] == D.PAUSE_REASON_AWAITING_MANUAL_START
    assert doc["pause_reason_zh"] == "任务首次执行必须点击启动"
    assert doc["q_common"] is None
    assert doc["position_side_mode"] == D.POS_MODE_BOTH
    assert svc._store.get_task(doc["id"])["preflight_snapshot"] == {
        "available": False, "reason": "no_preflight_snapshot",
    }
    assert svc._store.list_attempts_for_task(doc["id"]) == []

    # paused 新卡不被重启恢复或 dry-run tick 抓走；fill 也不能绕过首次启动。
    svc._recover_workers()
    assert doc["id"] not in svc._workers
    with pytest.raises(D.HedgeError) as exc:
        svc.post_fill_once(doc["id"])
    assert exc.value.code == "start_required"

    # Live Start itself only arms the existing async worker; it must not call
    # the exploding preflight provider synchronously.
    class _LiveMarker:
        def dispatch(self, ctx):  # pragma: no cover - worker is replaced by spy
            raise AssertionError("not reached")

    handoffs = []
    svc._live_mode = True
    svc._executor = _LiveMarker()
    svc.ensure_worker = lambda task_id: handoffs.append(task_id)
    started = svc.post_start(doc["id"])[1]
    assert started["status"] == D.STATUS_RUNNING
    assert started["pause_reason"] is None
    assert handoffs == [doc["id"]]


def test_create_insufficient_balance_raises_with_extra(tmp_path):
    svc = _svc(tmp_path, preflight=_StubPreflight(_snapshot({"USDT": Decimal("50000")})))
    with pytest.raises(D.HedgeError) as exc:
        svc.create_task(_create_body())
    assert exc.value.status == 400
    assert exc.value.code == "insufficient_balance"
    assert exc.value.extra == {"direction": "forward", "required": "75000", "available": "50000"}


def test_create_filter_violation_is_invalid_field(tmp_path):
    # 0.0005 floored onto grid 0.001 -> 0 -> below min qty.
    svc = _svc(tmp_path, preflight=_StubPreflight(_snapshot({"USDT": Decimal("100000")})))
    with pytest.raises(D.HedgeError) as exc:
        svc.create_task(_create_body(single_amount="0.0005"))
    assert exc.value.code == "invalid_field"


def test_create_rejects_unknown_and_invalid_fields(tmp_path):
    svc = _svc(tmp_path)
    with pytest.raises(D.HedgeError) as exc:
        svc.create_task({**_create_body(), "noise": 1})
    assert exc.value.code == "invalid_field"
    with pytest.raises(D.HedgeError):
        svc.create_task({"coin": "BTCUSDT", "direction": "up", "mode": "immediate",
                         "single_amount": "0.5", "target_n": 1})


# ---------------------------------------------------------------------------
# S4b (ADR-H5): create_task leg-existence interception
# ---------------------------------------------------------------------------

class _ProbePreflight:
    """A provider that exposes the S4b leg probe but returns no snapshot, to
    isolate the create_task interception from preflight math."""

    def __init__(self, legs):
        self._legs = legs

    def get_snapshot(self, coin, direction, task_type="open"):
        return None  # dry-run path; compute_preflight tolerates a None snapshot

    def check_symbol_legs(self, coin):
        return self._legs


def test_create_blocks_when_spot_leg_confirmed_absent(tmp_path):
    # KORUUSDT case: spot absent (False, -1121), UM present (True).
    svc = _svc(tmp_path, preflight=_ProbePreflight({"spot": False, "perp": True}))
    with pytest.raises(D.HedgeError) as exc:
        svc.create_task({"coin": "KORUUSDT", "direction": "forward", "mode": "immediate",
                         "single_amount": "0.5", "target_n": 1})
    err = exc.value
    assert err.status == 400
    assert err.code == "missing_leg"
    assert err.extra == {"missing": ["spot"]}
    assert err.detail == "该交易对在币安现货市场不存在（缺少现货腿），无法创建对冲任务"


def test_create_open_blocks_multiplier_contract(tmp_path):
    """P0 (2026-08-07): a 1000x contract cannot be opened until the leg-quantity
    conversion exists. The executor sends ONE ``q_common`` to both legs, but one
    ``1000BONKUSDT`` contract is 1000 BONK — opening would leave a 999x naked
    short. Fail closed at create, the earliest point that knows the match type."""
    svc = _svc(tmp_path, preflight=_ProbePreflight({"spot": True, "perp": True}))
    with pytest.raises(D.HedgeError) as exc:
        svc.create_task({"coin": "1000BONKUSDT", "direction": "forward",
                         "mode": "immediate", "single_amount": "0.5", "target_n": 1})
    err = exc.value
    assert err.status == 400
    assert err.code == "multiplier_contract_unsupported"
    assert "1000" in err.detail and "对冲" in err.detail
    assert err.extra == {"coin": "1000BONKUSDT", "spot_symbol": "BONKUSDT"}


def test_create_close_allows_multiplier_contract(tmp_path):
    """Without an active cycle the local no-position check still wins first."""
    svc = _svc(tmp_path, preflight=_ProbePreflight({"spot": True, "perp": True}))
    with pytest.raises(D.HedgeError) as exc:
        svc.create_task({"coin": "1000BONKUSDT", "direction": "forward",
                         "mode": "immediate", "single_amount": "0.5",
                         "target_n": 1, "task_type": "close"})
    assert exc.value.code == "no_active_cycle"


def test_create_close_blocks_multiplier_after_active_cycle_lookup(tmp_path):
    svc = _svc(tmp_path)
    origin = svc._store.create_task(
        "origin-1000", "1000BONKUSDT", D.DIR_FORWARD, D.MODE_IMMEDIATE,
        "1", 1, "1", D.POS_MODE_BOTH, None, 1,
        spot_symbol="BONKUSDT", spot_base_asset="BONK",
        symbol_match_type=None,  # F3: historical nullable column
    )
    svc._store.create_cycle(
        "1000BONKUSDT", D.DIR_FORWARD, 1, origin["id"],
    )
    with pytest.raises(D.HedgeError) as exc:
        svc.create_task({
            "coin": "1000BONKUSDT", "direction": D.DIR_FORWARD,
            "mode": D.MODE_IMMEDIATE, "single_amount": "1", "target_n": 1,
            "task_type": D.TASK_TYPE_CLOSE,
        })
    assert exc.value.code == "multiplier_contract_unsupported"
    assert svc._store._conn.execute(
        "SELECT COUNT(*) FROM hedge_open_task WHERE task_type = 'close'"
    ).fetchone()[0] == 0


def test_create_blocks_when_perp_leg_confirmed_absent(tmp_path):
    svc = _svc(tmp_path, preflight=_ProbePreflight({"spot": True, "perp": False}))
    with pytest.raises(D.HedgeError) as exc:
        svc.create_task(_create_body())
    err = exc.value
    assert err.code == "missing_leg"
    assert err.extra == {"missing": ["perp"]}
    assert err.detail == "该交易对在币安 USDⓈ-M 合约市场不存在（缺少合约腿），无法创建对冲任务"


def test_create_blocks_when_both_legs_confirmed_absent(tmp_path):
    svc = _svc(tmp_path, preflight=_ProbePreflight({"spot": False, "perp": False}))
    with pytest.raises(D.HedgeError) as exc:
        svc.create_task(_create_body())
    err = exc.value
    assert err.extra == {"missing": ["spot", "perp"]}
    assert err.detail == "该交易对在币安现货与 USDⓈ-M 合约市场均不存在，无法创建对冲任务"


def test_create_does_not_block_when_probe_indeterminate(tmp_path):
    # None (read failed) must NOT block — a transient public-marketdata failure
    # is never escalated to a create failure (10-design §2.4b).
    svc = _svc(tmp_path, preflight=_ProbePreflight({"spot": None, "perp": None}))
    status, _ = svc.create_task(_create_body())
    assert status == 201


def test_create_does_not_block_when_legs_present(tmp_path):
    svc = _svc(tmp_path, preflight=_ProbePreflight({"spot": True, "perp": True}))
    status, _ = svc.create_task(_create_body())
    assert status == 201


def test_create_default_provider_has_no_probe_and_does_not_block(tmp_path):
    # The dry-run DisabledPreflightProvider (default) exposes no probe -> no
    # interception -> dry-run create is unchanged.
    svc = _svc(tmp_path)
    status, _ = svc.create_task(_create_body())
    assert status == 201


# ---------------------------------------------------------------------------
# Task lifecycle
# ---------------------------------------------------------------------------

def test_pause_start_delete_transitions(tmp_path):
    svc = _svc(tmp_path)
    _, doc = svc.create_task(_create_body())
    tid = doc["id"]
    assert svc.post_pause(tid)[1]["status"] == D.STATUS_PAUSED
    assert svc.post_start(tid)[1]["status"] == D.STATUS_RUNNING
    assert svc.post_delete(tid)[1]["status"] == D.STATUS_DELETED
    # actions on a deleted task -> invalid_state.
    with pytest.raises(D.HedgeError) as exc:
        svc.post_start(tid)
    assert exc.value.code == "invalid_state"


def test_fill_once_advances_success(tmp_path):
    # B-1: the production default executor is disabled (zero fills); the
    # simulated-fill scenario injects the test-only fake explicitly.
    svc = _svc(tmp_path, executor=RecordTransportFake())
    _, doc = svc.create_task(_create_body(target_n=2))
    assert svc.post_fill_once(doc["id"])[1]["success_count"] == 1


def test_fill_all_runs_to_done(tmp_path):
    # B-1: same as above — the fill scenario needs the injected record fake.
    svc = _svc(tmp_path, executor=RecordTransportFake())
    _, doc = svc.create_task(_create_body(target_n=3))
    out = svc.post_fill_all(doc["id"])[1]
    assert out["success_count"] == 3
    assert out["status"] == D.STATUS_DONE
    # fill on a done task -> invalid_state.
    with pytest.raises(D.HedgeError) as exc:
        svc.post_fill_once(doc["id"])
    assert exc.value.code == "invalid_state"


# ---------------------------------------------------------------------------
# Injectable single-leg exposure (advisory) + >=threshold consecutive-failure pause
# ---------------------------------------------------------------------------

def test_injected_single_leg_exposure_is_advisory(tmp_path):
    exe = RecordTransportFake([OutcomeSpec.spot_only_filled()])
    svc = _svc(tmp_path, executor=exe)
    _, doc = svc.create_task(_create_body(target_n=3))
    out = svc.post_fill_once(doc["id"])[1]
    # Single-leg exposure is ADVISORY (breakdown §4.5): the task is NOT frozen.
    assert out["status"] == D.STATUS_RUNNING
    assert out["leg_exposure"] is not None
    assert set(out["leg_exposure"].keys()) == {"leg", "qty", "price", "ts"}
    assert out["leg_exposure"]["leg"] == "spot"
    assert out["leg_exposure"]["qty"] == "0.5"
    assert out["leg_exposure"]["price"] == "1"  # dry-run placeholder (no preflight)
    # R2-F1: a single_leg records the exposure and counts toward the brake
    # (fail + consecutive ++); below the threshold it does NOT freeze the task.
    assert out["success_count"] == 0
    assert out["fail_count"] == 1
    assert out["consecutive_submission_failures"] == 1
    # a second fill is still allowed (advisory never blocks scheduling).
    out2 = svc.post_fill_once(doc["id"])[1]
    assert out2["status"] == D.STATUS_RUNNING


def test_injected_failures_pause_at_threshold(tmp_path):
    exe = RecordTransportFake([OutcomeSpec.both_failed()] * 4)
    svc = _svc(tmp_path, executor=exe)
    _, doc = svc.create_task(_create_body(target_n=5))
    out = svc.post_fill_all(doc["id"])[1]
    # The 3rd consecutive submission failure reaches the >=3 threshold -> paused;
    # fill-all stops dispatching once the task is no longer running.
    assert out["fail_count"] == 3
    assert out["consecutive_submission_failures"] == 3
    assert out["status"] == D.STATUS_PAUSED
    assert out["pause_reason"] == D.PAUSE_REASON_CONSECUTIVE_SUBMISSION_FAILURE


# ---------------------------------------------------------------------------
# Start-gated scheduler tick
# ---------------------------------------------------------------------------

def test_tick_respects_start_gate(tmp_path):
    clock = _Clock(0)
    # B-1: the tick-to-done scenario needs the injected record fake (the
    # production default executor is disabled / zero fills).
    svc = _svc(tmp_path, clock=clock, executor=RecordTransportFake())
    svc.create_task(_create_body(target_n=1))
    assert svc.tick() is False  # start gate off -> no dispatch
    svc.set_start_gate(True)
    clock.t = 1_000_000  # advance past the 1s interval
    assert svc.tick() is True  # due + gate on -> dispatch
    _, listing = svc.list_tasks(None)
    assert listing["tasks"][0]["status"] == D.STATUS_DONE


def test_tick_no_eligible_task_returns_false(tmp_path):
    clock = _Clock(0)
    svc = _svc(tmp_path, clock=clock)
    svc.set_start_gate(True)
    assert svc.tick() is False  # no tasks at all


# ---------------------------------------------------------------------------
# Re-query cadence (ADR-003): subsecond display, floor + display consistency,
# ~100ms cadence, bounded positive jitter.
# ---------------------------------------------------------------------------


def test_settings_doc_renders_subsecond_interval():
    # A sub-second cadence must NOT collapse to 0 (the old integer division did);
    # the UI prints this value verbatim -> "调度间隔 0.5 秒".
    # Since 2026-08-02 the doc reports D.DEFAULT_INTERVAL_US, so a stale row value
    # (here 100_000) is deliberately ignored — one source of truth.
    doc = settings_to_doc(
        {"start_gate": 0, "interval_us": 100_000, "version": 1, "close_gate": 1},
        "disabled",
    )
    assert doc["interval_seconds"] == round(D.DEFAULT_INTERVAL_US / 1_000_000, 3)
    assert doc["interval_seconds"] != 0


def test_default_cadence_seeds_500ms(tmp_path):
    # Acceptance 1: a fresh store seeds the 500ms re-query cadence.
    from backend.hedge_open_tasks.store import HedgeOpenStore

    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    assert store.get_interval_us() == 500_000
    store.close()


def test_floor_clamps_effective_cadence(tmp_path):
    # The floor still guards the worker against a busy poll, but since 2026-08-02
    # the value being clamped is the code constant, not a database row — so a
    # sub-floor row (1000us here) can no longer reach the worker at all.
    from backend.hedge_open_tasks.store import HedgeOpenStore

    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    with store._lock, store._conn:
        store._conn.execute(
            "UPDATE hedge_open_settings SET interval_us = 1000 WHERE id = 1"
        )
    assert store.get_interval_us() == D.DEFAULT_INTERVAL_US
    assert store.get_interval_us() >= D.MIN_INTERVAL_US
    store.close()


def test_floor_display_matches_effective_value(tmp_path):
    # Acceptance 3b (root-cause guard): the settings display reports the clamped
    # EFFECTIVE value, not the raw misconfigured one, and equals what the worker
    # actually honours.
    from backend.hedge_open_tasks.store import HedgeOpenStore

    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    with store._lock, store._conn:
        store._conn.execute(
            "UPDATE hedge_open_settings SET interval_us = 1000 WHERE id = 1"
        )
    effective = store.get_interval_us()
    doc = settings_to_doc(store.get_settings(), "disabled")
    assert doc["interval_seconds"] == round(effective / 1_000_000, 3)
    assert doc["interval_seconds"] != round(1000 / 1_000_000, 3)  # not the raw value
    store.close()


# ---------------------------------------------------------------------------
# Default-off posture: a real POST requires an injected live executor
# ---------------------------------------------------------------------------

def test_live_mode_without_injected_executor_still_disabled(tmp_path):
    # ``mode="live"`` alone (no live executor injected by the caller) keeps the
    # default disabled executor (zero I/O, zero fills): a real POST is
    # unreachable until the server injects a LiveHedgeExecutor under
    # APP_HEDGE_EXECUTOR=live.
    svc = _svc(tmp_path, mode="live")
    assert svc.is_live_mode is True
    assert svc._live_dispatch_capable() is False  # no dispatch() on the executor
    assert isinstance(svc.executor, DisabledHedgeExecutor)


def test_disabled_executor_is_injectable_and_records_no_fill(tmp_path):
    clock = _Clock(0)
    svc = _svc(tmp_path, executor=DisabledHedgeExecutor(), clock=clock)
    svc.set_start_gate(True)
    _, doc = svc.create_task(_create_body(target_n=1))
    svc.tick()
    _, listing = svc.list_tasks(None)
    task = [t for t in listing["tasks"] if t["id"] == doc["id"]][0]
    # A disabled attempt neither fills nor terminates; counts stay zero.
    assert task["success_count"] == 0
    assert task["status"] == D.STATUS_RUNNING


# ---------------------------------------------------------------------------
# R4-1: additive `attempts` timeline projection on the logs read (§3.4 / PRD §9.2)
# ---------------------------------------------------------------------------

def test_get_logs_includes_attempts_projection_for_record_fill(tmp_path):
    # The logs read endpoint carries a first-class additive `attempts` array
    # projecting the durable attempt + both legs (breakdown §3.4), alongside
    # the unchanged legacy logs/cursor.
    exe = RecordTransportFake()
    svc = _svc(tmp_path, executor=exe)
    _, doc = svc.create_task(_create_body(target_n=1))
    svc.post_fill_once(doc["id"])
    status, page = svc.get_logs(None, None)
    assert status == 200
    assert set(page.keys()) == {
        "logs", "attempts", "entries", "next_cursor", "entries_next_cursor",
    }
    assert len(page["attempts"]) == 1
    a = page["attempts"][0]
    # frozen §3.4 attempt fields (task_id is additive for UI linking).
    assert {"attempt_id", "attempt_seq", "direction", "q_common", "pair_outcome",
            "spot", "perp", "residual", "ts", "task_id"} <= set(a.keys())
    assert a["attempt_seq"] == 1
    assert a["direction"] == D.DIR_FORWARD
    assert a["pair_outcome"] == D.PAIR_ACCEPTED
    assert a["task_id"] == doc["id"]
    # frozen per-leg fields; FILLED with cumulative figures + weighted average.
    for leg in (a["spot"], a["perp"]):
        assert {"client_order_id", "order_id", "status", "cumulative_base_qty",
                "cumulative_quote_amt", "avg_price"} <= set(leg.keys())
    assert a["spot"]["status"] == D.LEG_FILLED
    assert a["spot"]["cumulative_base_qty"] == "0.5"
    assert a["spot"]["avg_price"] == "1"  # quote 0.5 / base 0.5
    # residual is a decimal STRING (no float): 0.5 - 0.5 == "0".
    assert a["residual"] == "0"
    assert isinstance(a["residual"], str)
    # legacy logs/cursor still present and unchanged.
    assert len(page["logs"]) == 1
    assert page["logs"][0]["kind"] == "record_transport"
    assert page["next_cursor"] is None  # only one log row -> no next page


def test_get_logs_attempts_includes_prepared_querying_attempt(tmp_path):
    # A PREPARED/QUERYING attempt has no log row yet (it exists from the
    # durable-before-send transaction, before any resolve), but it must still
    # project so the UI shows in-flight pairs mid-query.
    svc = _svc(tmp_path)
    _, doc = svc.create_task(_create_body(target_n=1))
    svc.store.prepare_attempt(
        doc["id"], "uuid-q", D.DIR_FORWARD, "0.5", D.POS_MODE_BOTH,
        {"est_price": "1"}, "hgo-uuid-q-s", {"side": "BUY"},
        D.SPOT_ORDER_PATH,
        "hgo-uuid-q-p", {"side": "SELL"}, 1000,
    )
    status, page = svc.get_logs(None, None)
    assert status == 200
    # logs is empty (nothing resolved yet), but attempts surfaces the PREPARED pair.
    assert page["logs"] == []
    assert len(page["attempts"]) == 1
    a = page["attempts"][0]
    assert a["pair_outcome"] is None  # unresolved
    assert a["spot"]["status"] is None  # PREPARED — no exchange status yet
    assert a["spot"]["order_id"] is None
    assert a["spot"]["client_order_id"] == "hgo-uuid-q-s"
    assert a["spot"]["cumulative_base_qty"] == "0"
    assert a["spot"]["avg_price"] is None  # no base fill -> no weighted average
    assert a["residual"] == "0"  # 0 - 0


def test_get_logs_attempts_residual_is_signed_decimal_no_float(tmp_path):
    # residual = spot_base - perp_base as a decimal string. A single-leg spot
    # fill (perp rejected, 0 base) leaves a non-zero residual; it must be a
    # string, never a float, and the pair_outcome is the advisory single_leg.
    exe = RecordTransportFake([OutcomeSpec.spot_only_filled()])
    svc = _svc(tmp_path, executor=exe)
    _, doc = svc.create_task(_create_body(target_n=2))
    svc.post_fill_once(doc["id"])
    _, page = svc.get_logs(None, None)
    a = page["attempts"][0]
    assert a["spot"]["cumulative_base_qty"] == "0.5"
    assert a["perp"]["cumulative_base_qty"] == "0"  # rejected
    assert a["residual"] == "0.5"  # 0.5 - 0
    assert isinstance(a["residual"], str)
    assert a["pair_outcome"] == D.PAIR_SINGLE_LEG


# ---------------------------------------------------------------------------
# Review-1 round 6: a NULL notional must pass through the projection layer
# (review-1 r6 P1). The store records an unknown notional as NULL; the API
# projection must NOT re-fabricate it as "0" on either the attempts (§3.4) or
# entries (§5) timeline, and avg_price must be null too — dividing an unknown
# by a real quantity is the original defect one layer up. A REAL "0" still
# projects as the string "0".
# ---------------------------------------------------------------------------


class _NullQuoteExecutor:
    """Record/dry-run transport whose FILLED legs carry a positive fill but NO
    ``cumulative_quote`` and NO ``avg_price`` (no price information at all), so
    the store records both notional and avg_price as NULL. r6 反造假内核守卫
    （拆分后第一支，见 test_null_notional_projects_null_on_attempts_and_entries）。"""

    def execute(self, ctx):
        return AttemptOutcome(
            attempt_id=ctx.attempt_id,
            category=D.ATTEMPT_SUCCESS,
            spot={"status": D.LEG_FILLED, "filled_qty": "0.5", "avg_price": None,
                  "order_id": f"s-{ctx.attempt_id}", "client_order_id": f"hgo-{ctx.attempt_id}-s"},
            perp={"status": D.LEG_FILLED, "filled_qty": "0.5", "avg_price": None,
                  "order_id": f"p-{ctx.attempt_id}", "client_order_id": f"hgo-{ctx.attempt_id}-p"},
            record_payload={"transport": "null_quote_test", "posted": False},
            exposure=None,
        )


class _NullQuoteWithAvgExecutor:
    """Record transport whose FILLED legs carry a positive fill and an exchange
    ``avg_price`` but NO ``cumulative_quote`` (the 2026-07-14 UM shape: POST
    drops quote, the order-detail GET supplies avgPrice). Part B 新语义守卫
    （拆分后第二支）：NULL quote + 在场交易所 avg → 两流展示该 avg、值相同；
    quote 仍为 NULL（不推导）。"""

    def execute(self, ctx):
        return AttemptOutcome(
            attempt_id=ctx.attempt_id,
            category=D.ATTEMPT_SUCCESS,
            spot={"status": D.LEG_FILLED, "filled_qty": "0.5", "avg_price": "50000",
                  "order_id": f"s-{ctx.attempt_id}", "client_order_id": f"hgo-{ctx.attempt_id}-s"},
            perp={"status": D.LEG_FILLED, "filled_qty": "0.5", "avg_price": "50000",
                  "order_id": f"p-{ctx.attempt_id}", "client_order_id": f"hgo-{ctx.attempt_id}-p"},
            record_payload={"transport": "null_quote_with_avg_test", "posted": False},
            exposure=None,
        )


class _RealZeroQuoteExecutor:
    """Record transport whose FILLED legs carry an explicit real
    ``cumulative_quote`` of "0" (an exchange that returned a literal zero
    notional), to pin that a REAL "0" still projects as the string "0" —
    distinct from an absent/NULL notional (review-1 r6 regression guard)."""

    def execute(self, ctx):
        return AttemptOutcome(
            attempt_id=ctx.attempt_id,
            category=D.ATTEMPT_SUCCESS,
            spot={"status": D.LEG_FILLED, "filled_qty": "0.5", "avg_price": "0",
                  "cumulative_quote": "0",
                  "order_id": f"s-{ctx.attempt_id}", "client_order_id": f"hgo-{ctx.attempt_id}-s"},
            perp={"status": D.LEG_FILLED, "filled_qty": "0.5", "avg_price": "0",
                  "cumulative_quote": "0",
                  "order_id": f"p-{ctx.attempt_id}", "client_order_id": f"hgo-{ctx.attempt_id}-p"},
            record_payload={"transport": "real_zero_quote_test", "posted": False},
            exposure=None,
        )


def test_null_notional_projects_null_on_attempts_and_entries(tmp_path):
    # r6 反造假内核（拆分后第一支；Human 2026-07-31 决定改用交易所返回的权威均价）。
    # 一个 FILLED 腿有成交量、但既无成交额也无 avg_price（_NullQuoteExecutor）→ 两流
    # 的 cumulative_quote_amt 与 avg_price 都必须为 null：不得用未知成交额做除法造出
    # 价格（review-1 r6 原意）。有交易所 avg_price 时的相反语义见下一用例。
    svc = _svc(tmp_path, executor=_NullQuoteExecutor())
    _, doc = svc.create_task(_create_body(target_n=1))
    svc.post_fill_once(doc["id"])
    _, page = svc.get_logs(None, None)
    a = page["attempts"][0]
    for leg in (a["spot"], a["perp"]):
        assert leg["cumulative_base_qty"] == "0.5"    # positive fill recorded
        assert leg["cumulative_quote_amt"] is None     # NULL passes through, not "0"
        assert leg["avg_price"] is None                # unknown notional -> no average
    e = next(x for x in page["entries"] if x["entry_type"] == "attempt")
    for leg in (e["spot"], e["perp"]):
        assert leg["cumulative_base_qty"] == "0.5"
        assert leg["cumulative_quote_amt"] is None
        assert leg["avg_price"] is None


def test_null_quote_with_exchange_avg_projects_on_both_streams(tmp_path):
    # r6 拆分第二支 / Part B 新语义（Human 2026-07-31）：一个 FILLED 腿的成交额为 NULL
    # 但带了交易所返回的 avg_price（_NullQuoteWithAvgExecutor，即 2026-07-14 后 UM 的
    # 形态：POST 不带 quote、GET 带回 avgPrice）→ 两流都展示该 avg_price、且值相同；
    # quote 仍为 NULL（不得用 avg_price 反推成交额）。本地算在此为 None，故展示库存值
    # 即证明走了优先级 ①。
    svc = _svc(tmp_path, executor=_NullQuoteWithAvgExecutor())
    _, doc = svc.create_task(_create_body(target_n=1))
    svc.post_fill_once(doc["id"])
    _, page = svc.get_logs(None, None)
    a = page["attempts"][0]
    for leg in (a["spot"], a["perp"]):
        assert leg["cumulative_base_qty"] == "0.5"
        assert leg["cumulative_quote_amt"] is None      # quote NULL 契约不变
        assert leg["avg_price"] == "50000"               # 交易所权威值优先
    e = next(x for x in page["entries"] if x["entry_type"] == "attempt")
    for leg in (e["spot"], e["perp"]):
        assert leg["cumulative_quote_amt"] is None
        assert leg["avg_price"] == "50000"               # entries 流与 attempts 流一致
    # 两流同一笔钱的均价必须相同（不可一个流显示、一个流显示 —）。
    assert a["spot"]["avg_price"] == e["spot"]["avg_price"] == "50000"


def test_real_zero_notional_still_projects_string_zero(tmp_path):
    # Regression guard: a REAL "0" notional (the exchange returned a literal
    # zero) must still project as the STRING "0" and run the existing arithmetic
    # (0 / 0.5 == "0"), distinct from an absent/NULL notional. This is what stops
    # a future "simplification" from collapsing every zero into null.
    svc = _svc(tmp_path, executor=_RealZeroQuoteExecutor())
    _, doc = svc.create_task(_create_body(target_n=1))
    svc.post_fill_once(doc["id"])
    _, page = svc.get_logs(None, None)
    a = page["attempts"][0]
    for leg in (a["spot"], a["perp"]):
        assert leg["cumulative_quote_amt"] == "0"   # real zero stays "0"
        assert leg["avg_price"] == "0"              # 0 / 0.5 == "0"
    e = next(x for x in page["entries"] if x["entry_type"] == "attempt")
    for leg in (e["spot"], e["perp"]):
        assert leg["cumulative_quote_amt"] == "0"
        assert leg["avg_price"] == "0"


# ---------------------------------------------------------------------------
# R4-2: per-task independent asynchronous cadence (PRD §6.3 / 05-cadence-resolution)
# ---------------------------------------------------------------------------

class _BlockingExecutor:
    """Record/dry-run transport that blocks inside execute() until released,
    counting how many task workers have entered dispatch. Thread-safe so two
    task workers can block concurrently. No network."""

    def __init__(self):
        self._count_lock = threading.Lock()
        self.entered_count = 0
        self.release = threading.Event()

    def execute(self, ctx) -> AttemptOutcome:
        with self._count_lock:
            self.entered_count += 1
        # Block until the test releases us. A serial tick() would never reach
        # the second task (the first worker blocks forever), so reaching 2 here
        # proves the two cards dispatch concurrently (R4-2).
        self.release.wait(timeout=10)
        qty = str(ctx.q_common) if ctx.q_common is not None else str(ctx.single_amount)
        return AttemptOutcome(
            attempt_id=ctx.attempt_id,
            category=D.ATTEMPT_SUCCESS,
            spot={"status": D.LEG_FILLED, "filled_qty": qty, "avg_price": "1",
                  "order_id": f"s-{ctx.attempt_id}",
                  "client_order_id": f"hgo-{ctx.attempt_id}-s"},
            perp={"status": D.LEG_FILLED, "filled_qty": qty, "avg_price": "1",
                  "order_id": f"p-{ctx.attempt_id}",
                  "client_order_id": f"hgo-{ctx.attempt_id}-p"},
            record_payload={"transport": "blocking_test", "posted": False},
            exposure=None,
        )


def test_tick_dispatches_eligible_tasks_concurrently(tmp_path):
    # R4-2: each running card is an independent async worker; several tasks may
    # submit their own pair in the same second. A blocking executor proves BOTH
    # eligible tasks enter dispatch before either is released — impossible if
    # tick() dispatched them serially (the first worker would block forever and
    # the second would never run). No network, no sleep race: the release Event
    # is the deterministic gate.
    exe = _BlockingExecutor()
    clock = _Clock(0)
    svc = _svc(tmp_path, executor=exe, clock=clock)
    svc.set_start_gate(True)
    _, d1 = svc.create_task(_create_body(target_n=2))
    _, d2 = svc.create_task(_create_body(target_n=2))
    clock.t = 1_000_000  # advance past the 1s interval -> due
    # tick() joins its workers, so run it on a background thread.
    tick_done = threading.Event()
    holder = {}

    def run():
        holder["ret"] = svc.tick()
        tick_done.set()

    th = threading.Thread(target=run)
    th.start()
    # Wait until BOTH task workers entered dispatch. Serial dispatch would leave
    # entered_count stuck at 1 (first worker blocks, second never starts).
    deadline = time.time() + 5
    while exe.entered_count < 2:
        assert time.time() < deadline, (
            f"only {exe.entered_count} task(s) entered dispatch — "
            "tick() dispatched serially, not per-task concurrently (R4-2)"
        )
        time.sleep(0.01)
    assert exe.entered_count >= 2
    # Release both workers; tick() returns True.
    exe.release.set()
    assert tick_done.wait(timeout=5)
    assert holder["ret"] is True
    th.join(timeout=5)
    # Each task issued exactly one pair this tick (one pair per second per task;
    # no same-task re-entry, no cross-task serialization).
    _, listing = svc.list_tasks(None)
    by_id = {t["id"]: t for t in listing["tasks"]}
    assert by_id[d1["id"]]["scheduled_attempt_count"] == 1
    assert by_id[d2["id"]]["scheduled_attempt_count"] == 1


def test_tick_slow_card_does_not_block_other_card_submission(tmp_path):
    # R4-2 corollary: a slow live preflight/POST/query on one card must not
    # delay another card's same-tick submission. Card 1 blocks inside execute();
    # card 2 uses a fast executor and must complete (scheduled_attempt_count == 1)
    # BEFORE card 1 is released.
    class _FastExecutor:
        def execute(self, ctx):
            qty = str(ctx.single_amount)
            return AttemptOutcome(
                attempt_id=ctx.attempt_id, category=D.ATTEMPT_SUCCESS,
                spot={"status": D.LEG_FILLED, "filled_qty": qty, "avg_price": "1",
                      "order_id": f"s-{ctx.attempt_id}", "client_order_id": f"hgo-{ctx.attempt_id}-s"},
                perp={"status": D.LEG_FILLED, "filled_qty": qty, "avg_price": "1",
                      "order_id": f"p-{ctx.attempt_id}", "client_order_id": f"hgo-{ctx.attempt_id}-p"},
                record_payload={"transport": "fast_test", "posted": False}, exposure=None,
            )

    # One shared blocking executor would serialize; instead inject per-task via
    # a router that blocks card 1 and fast-paths card 2.
    blocked = _BlockingExecutor()
    fast = _FastExecutor()

    class _RoutingExecutor:
        def __init__(self, blocked_task_id, fast_task_id):
            self._blocked = blocked_task_id
            self._fast = fast_task_id

        def execute(self, ctx):
            if ctx.task_id == self._blocked:
                return blocked.execute(ctx)
            return fast.execute(ctx)

    clock = _Clock(0)
    svc = _svc(tmp_path, clock=clock)
    svc.set_start_gate(True)
    _, d1 = svc.create_task(_create_body(target_n=2))
    _, d2 = svc.create_task(_create_body(target_n=2))
    svc._executor = _RoutingExecutor(d1["id"], d2["id"])  # inject after build
    clock.t = 1_000_000
    tick_done = threading.Event()

    def run():
        svc.tick()
        tick_done.set()

    th = threading.Thread(target=run)
    th.start()
    # Wait until the blocking card has entered dispatch, then assert the fast
    # card already completed its pair this tick — proving it was not blocked.
    assert _wait_until(lambda: blocked.entered_count >= 1, timeout=5)
    _, listing = svc.list_tasks(None)
    by_id = {t["id"]: t for t in listing["tasks"]}
    assert by_id[d2["id"]]["scheduled_attempt_count"] == 1  # fast card done
    # Release the blocking card so tick() can return and the test cleans up.
    blocked.release.set()
    assert tick_done.wait(timeout=5)
    th.join(timeout=5)
    assert by_id[d1["id"]]["scheduled_attempt_count"] == 1  # blocking card done too


def _wait_until(predicate, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_attempt_to_doc_projects_error_fields():
    # The task-card inline log (2026-07-31-hedge-task-inline-log-v1) consumes
    # error_reason_zh / error_code / error_category off the attempts projection,
    # so attempt_to_doc must pass the attempt row's columns through verbatim.
    # error_reason_zh is frequently NULL for non-fatal rollups (store.py:1088).
    attempt = {
        "task_id": "t1", "attempt_uuid": "u1", "attempt_seq": 7,
        "direction": D.DIR_FORWARD, "q_common": "0.5",
        "pair_outcome": D.PAIR_CONFIRMED_FAILED,
        "error_category": "fatal", "error_code": "-2010",
        "error_reason_zh": "账户余额不足", "created_at_us": 1000,
    }
    doc = attempt_to_doc(attempt, None, None)
    assert doc["error_category"] == "fatal"
    assert doc["error_code"] == "-2010"
    assert doc["error_reason_zh"] == "账户余额不足"
    # NULL passthrough — the common non-fatal case (must stay None, not "0"/"—").
    attempt_null = dict(attempt, error_category=None, error_code=None, error_reason_zh=None)
    doc_null = attempt_to_doc(attempt_null, None, None)
    assert doc_null["error_category"] is None
    assert doc_null["error_code"] is None
    assert doc_null["error_reason_zh"] is None


def test_get_logs_task_id_returns_all_attempts_unpaged(tmp_path):
    # task_id mode (AC5) returns the task's FULL attempt set in one shot: not
    # bounded by the default page size (50), not mixed with the entries cursor,
    # and scoped to just that task. Without task_id the legacy contract is
    # unchanged (newest LIMIT_DEFAULT page). Read path only — no state machine.
    exe = RecordTransportFake()  # balanced accepted_pair fills
    svc = _svc(tmp_path, executor=exe)
    _, t1 = svc.create_task(_create_body(target_n=60))
    _, t2 = svc.create_task(_create_body(target_n=60))
    for _ in range(51):
        svc.post_fill_once(t1["id"])
    svc.post_fill_once(t2["id"])  # one attempt on another task
    status, page = svc.get_logs(None, None, task_id=t1["id"])
    assert status == 200
    assert set(page.keys()) == {
        "logs", "attempts", "entries", "next_cursor", "entries_next_cursor",
        "smooth_market", "smooth_dispatch_audits",
    }
    assert page["smooth_market"] is None
    assert page["smooth_dispatch_audits"] == []
    # task_id mode empties the secondary streams and uses no cursor.
    assert page["logs"] == []
    assert page["entries"] == []
    assert page["next_cursor"] is None
    assert page["entries_next_cursor"] is None
    # Full set (51 > LIMIT_DEFAULT=50), all from t1, distinct sequences 1..51.
    assert len(page["attempts"]) == 51
    assert all(a["task_id"] == t1["id"] for a in page["attempts"])
    assert sorted(a["attempt_seq"] for a in page["attempts"]) == list(range(1, 52))
    # error fields are projected on this path too (NULL for accepted fills).
    for a in page["attempts"]:
        assert "error_reason_zh" in a and "error_code" in a and "error_category" in a
    # Contrast: no task_id -> the legacy global page is capped at LIMIT_DEFAULT.
    _, global_page = svc.get_logs(None, None)
    assert len(global_page["attempts"]) == 50


def test_avg_price_priority_three_levels_both_streams():
    # Part B（Human 2026-07-31）：avg_price 三级优先级 ① 库存交易所值 → ② 本地 quote/base
    # → ③ None。attempts 流（_leg_to_doc）与 entries 流（_entry_spot_leg/_entry_perp_leg）
    # 必须用完全相同的优先级——同一笔钱在两处显示同一价格。
    from backend.hedge_open_tasks.service import (
        _leg_to_doc, _entry_spot_leg, _entry_perp_leg,
    )
    # ① 库存 avg 在场，且刻意与本地算不同（本地 25000/0.5=50000，库存 99999）→ 展示库存值。
    leg_stored = {"cumulative_base_qty": "0.5", "cumulative_quote_amt": "25000",
                  "avg_price": "99999"}
    assert _leg_to_doc(leg_stored)["avg_price"] == "99999"
    assert _entry_spot_leg(leg_stored, "BUY")["avg_price"] == "99999"
    assert _entry_perp_leg(leg_stored, "SELL")["avg_price"] == "99999"
    # ② 库存 avg 为 NULL、quote/base 齐全（既有历史行）→ 本地计算，与修复前完全一致。
    leg_local = {"cumulative_base_qty": "0.5", "cumulative_quote_amt": "25000",
                 "avg_price": None}
    assert _leg_to_doc(leg_local)["avg_price"] == "50000"
    assert _entry_spot_leg(leg_local, "BUY")["avg_price"] == "50000"
    assert _entry_perp_leg(leg_local, "SELL")["avg_price"] == "50000"
    # ② 变体：库存 avg 缺键（旧行没这列的等价）→ 同样退回本地计算。
    leg_no_key = {"cumulative_base_qty": "0.5", "cumulative_quote_amt": "25000"}
    assert _leg_to_doc(leg_no_key)["avg_price"] == "50000"
    # ③ 库存 avg 与 quote 均缺失 → None（不是 "0"）。
    leg_none = {"cumulative_base_qty": "0.5", "cumulative_quote_amt": None,
                "avg_price": None}
    assert _leg_to_doc(leg_none)["avg_price"] is None
    assert _entry_spot_leg(leg_none, "BUY")["avg_price"] is None
    assert _entry_perp_leg(leg_none, "SELL")["avg_price"] is None


def test_resolve_avg_price_zero_stored_falls_back_to_local_both_streams():
    # R2-Rerun-F1 展示层纵深防御：库存均价为数值零（遗留脏数据 "0.00000"，或未来别的写入
    # 路径漏网）时视为未知，退回本地 quote/base 计算；非零库存仍优先。attempts 与 entries
    # 两流一致——页面上该单元格不出现 0。
    from backend.hedge_open_tasks.service import (
        _leg_to_doc, _entry_spot_leg, _entry_perp_leg,
    )
    # 库存为零、quote/base 齐全 -> 退回本地算（不展示 0.00000）
    leg_zero = {"cumulative_base_qty": "0.5", "cumulative_quote_amt": "25000",
                "avg_price": "0.00000"}
    assert _leg_to_doc(leg_zero)["avg_price"] == "50000"         # 25000/0.5
    assert _entry_spot_leg(leg_zero, "BUY")["avg_price"] == "50000"
    assert _entry_perp_leg(leg_zero, "SELL")["avg_price"] == "50000"
    # 库存为零、quote 也缺失 -> None（不是 "0"/"0.00000"）
    leg_zero_no_quote = {"cumulative_base_qty": "0.5", "cumulative_quote_amt": None,
                         "avg_price": "0"}
    assert _leg_to_doc(leg_zero_no_quote)["avg_price"] is None
    assert _entry_spot_leg(leg_zero_no_quote, "BUY")["avg_price"] is None
    assert _entry_perp_leg(leg_zero_no_quote, "SELL")["avg_price"] is None
    # 非零库存仍优先（Part B 主语义不受影响）
    leg_real = {"cumulative_base_qty": "0.5", "cumulative_quote_amt": "25000",
                "avg_price": "99999"}
    assert _leg_to_doc(leg_real)["avg_price"] == "99999"
    assert _entry_spot_leg(leg_real, "BUY")["avg_price"] == "99999"
    assert _entry_perp_leg(leg_real, "SELL")["avg_price"] == "99999"
