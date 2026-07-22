"""Service orchestration tests for backend/hedge_open_tasks/service.py.

No HTTP, no network. Covers task create with an injectable preflight provider
(accept / insufficient_balance / filter violation / dry-run no-snapshot), the
task lifecycle (start/pause/delete/fill-once/fill-all) incl. invalid_state, the
single-leg exposure drill and >3-fail termination via injected record-transport
seeds, the Start-gated scheduler tick, and the round-1 safety posture: even in
``live`` mode the executor is the dry-run record transport, so a real POST is
unreachable this round.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.executor import (
    DisabledHedgeExecutor,
    OutcomeSpec,
    RecordTransportExecutor,
)
from backend.hedge_open_tasks.service import HedgeOpenTaskService, PreflightProvider


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

    def get_snapshot(self, coin):
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


def _snapshot(balances, *, position_mode="BOTH", est_price="50000"):
    return D.PreflightSnapshot(
        spot_filters=_spot_filters(),
        perp_filters=_perp_filters(),
        balances=balances,
        position_mode=position_mode,
        est_price=Decimal(est_price) if est_price else None,
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


def test_create_default_provider_is_dry_run_no_q_common(tmp_path):
    # No preflight provider -> dry-run snapshot absent -> task still created.
    svc = _svc(tmp_path)
    status, doc = svc.create_task(_create_body())
    assert status == 201
    assert doc["q_common"] is None
    assert doc["position_side_mode"] is None


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
    svc = _svc(tmp_path)
    _, doc = svc.create_task(_create_body(target_n=2))
    assert svc.post_fill_once(doc["id"])[1]["success_count"] == 1


def test_fill_all_runs_to_done(tmp_path):
    svc = _svc(tmp_path)
    _, doc = svc.create_task(_create_body(target_n=3))
    out = svc.post_fill_all(doc["id"])[1]
    assert out["success_count"] == 3
    assert out["status"] == D.STATUS_DONE
    # fill on a done task -> invalid_state.
    with pytest.raises(D.HedgeError) as exc:
        svc.post_fill_once(doc["id"])
    assert exc.value.code == "invalid_state"


# ---------------------------------------------------------------------------
# Injectable single-leg exposure + >3-fail termination
# ---------------------------------------------------------------------------

def test_injected_single_leg_exposure_drills_alert(tmp_path):
    exe = RecordTransportExecutor([OutcomeSpec.spot_only_filled()])
    svc = _svc(tmp_path, executor=exe)
    _, doc = svc.create_task(_create_body(target_n=3))
    out = svc.post_fill_once(doc["id"])[1]
    assert out["status"] == D.STATUS_EXPOSURE_ALERT
    assert out["leg_exposure"] is not None
    assert out["leg_exposure"]["filled_leg"] == "spot"
    # a second fill on an exposure-alert task -> invalid_state.
    with pytest.raises(D.HedgeError):
        svc.post_fill_once(doc["id"])


def test_injected_failures_terminate_over_threshold(tmp_path):
    exe = RecordTransportExecutor([OutcomeSpec.both_failed()] * 4)
    svc = _svc(tmp_path, executor=exe)
    _, doc = svc.create_task(_create_body(target_n=5))
    out = svc.post_fill_all(doc["id"])[1]
    assert out["fail_count"] == 4
    assert out["status"] == D.STATUS_PAUSED  # >3 -> terminated


# ---------------------------------------------------------------------------
# Start-gated scheduler tick
# ---------------------------------------------------------------------------

def test_tick_respects_start_gate(tmp_path):
    clock = _Clock(0)
    svc = _svc(tmp_path, clock=clock)
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
# Round-1 safety posture (ADR-5): real POST unreachable this round
# ---------------------------------------------------------------------------

def test_live_mode_still_uses_record_transport_no_real_post(tmp_path):
    # Even with mode="live", round 1 wires no live executor: the default dry-run
    # record transport stays, so no real POST is reachable.
    svc = _svc(tmp_path, mode="live")
    assert svc.is_live_mode is True
    assert isinstance(svc.executor, RecordTransportExecutor)


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
