"""Executor seam + dry-run record-transport proofs (10-design §6 / §9 / ADR-5).

Covers DisabledHedgeExecutor and the test-only RecordTransportFake (moved to
backend/tests/fakes.py in stage 2026-08-06): the would-send signed-request param shape (no secrets), the simulated
outcomes and their injectable seeds, the grep/AST-level proof that the package
uses no network or signing primitives, the runtime proof that a full scenario
issues zero urllib calls, and the no-secret-leak proof.
"""
from __future__ import annotations

import json
import urllib.request
from decimal import Decimal
from pathlib import Path

import pytest

from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.executor import (
    AttemptContext,
    DisabledHedgeExecutor,
)
from backend.tests.fakes import (
    OutcomeSpec,
    RecordTransportFake,
    _leg_qty_filters,
)
from backend.hedge_open_tasks.service import HedgeOpenTaskService

REPO_ROOT = Path(__file__).resolve().parents[2]
HEDGE_PKG = REPO_ROOT / "backend" / "hedge_open_tasks"

_FORBIDDEN_SECRET_KEYS = (
    "apiKey", "apikey", "api_key", "timestamp", "signature", "recvWindow", "X-MBX-APIKEY",
)


def _ctx(
    *, attempt_id="abc123", direction=D.DIR_FORWARD, position_side_mode="BOTH",
    q_common="0.5", single_amount="0.5",
) -> AttemptContext:
    return AttemptContext(
        attempt_id=attempt_id,
        task_id="t1",
        coin="BTCUSDT",
        direction=direction,
        single_amount=Decimal(single_amount),
        q_common=Decimal(q_common) if q_common else None,
        position_side_mode=position_side_mode,
        preflight_snapshot={"est_price": "50000", "position_mode": position_side_mode or "BOTH"},
        filter_versions={"spot_step": "0.00001", "perp_step": "0.001"},
        target_n=3,
        ts_us=1_000_000,
    )


# ---------------------------------------------------------------------------
# DisabledHedgeExecutor
# ---------------------------------------------------------------------------

def test_disabled_executor_returns_execution_disabled_no_record():
    out = DisabledHedgeExecutor().execute(_ctx())
    assert out.category == D.ATTEMPT_DISABLED
    assert out.exposure is None
    assert out.record_payload["transport"] == "disabled"


# ---------------------------------------------------------------------------
# RecordTransportFake — default balanced outcome + param shape
# ---------------------------------------------------------------------------

def test_record_transport_default_is_balanced_dual_leg_fill():
    exe = RecordTransportFake()
    out = exe.execute(_ctx())
    assert out.category == D.ATTEMPT_SUCCESS
    assert out.spot["status"] == D.LEG_FILLED
    assert out.spot["filled_qty"] == "0.5"
    assert out.perp["filled_qty"] == "0.5"
    assert out.exposure is None


def test_record_transport_spot_params_shape_forward():
    exe = RecordTransportFake()
    out = exe.execute(_ctx(direction=D.DIR_FORWARD))
    spot = out.record_payload["spot_order_params"]
    # A-4: the endpoint path and every internal field leave the signed body.
    # Only the approved wire keys remain; this exact dict is what the live
    # client signs and posts.
    assert "endpoint" not in spot
    assert set(spot.keys()) == {
        "symbol", "side", "type", "quantity", "sideEffectType",
        "newClientOrderId", "newOrderRespType",
    }
    assert spot["symbol"] == "BTCUSDT"
    assert spot["side"] == "BUY"
    assert spot["type"] == "MARKET"
    assert spot["quantity"] == "0.5"
    assert spot["sideEffectType"] == "NO_SIDE_EFFECT"
    assert spot["newOrderRespType"] == "RESULT"
    # S1 (ADR-H1): hg + attempt_id + leg suffix; at a full 32-hex uuid the id is
    # 35 chars, within Binance's 36-char cap. The pre-fix ``hgo-<hex>-s`` form
    # (38 chars) is gone.
    assert spot["newClientOrderId"] == "hgabc123s"
    # reduceOnly never appears on the spot leg; no secrets are recorded.
    assert "reduceOnly" not in spot
    for key in _FORBIDDEN_SECRET_KEYS:
        assert key not in spot


def test_record_transport_uses_resolved_bstock_spot_symbol():
    # 2026-08-07 身份统一：现货腿 symbol 由 AttemptContext.spot_symbol 携带
    # （service 从任务固化列取出），不再从预检快照现算。
    ctx = _ctx()
    ctx = AttemptContext(
        **{
            **ctx.__dict__,
            "coin": "TSLAUSDT",
            "spot_symbol": "TSLABUSDT",
        },
    )
    out = RecordTransportFake().execute(ctx)
    assert out.record_payload["spot_order_params"]["symbol"] == "TSLABUSDT"
    assert out.record_payload["perp_order_params"]["symbol"] == "TSLAUSDT"


def test_record_transport_perp_params_shape_reverse_hedge():
    exe = RecordTransportFake()
    out = exe.execute(_ctx(direction=D.DIR_REVERSE, position_side_mode="hedge"))
    perp = out.record_payload["perp_order_params"]
    # A-4: only the approved wire keys; the endpoint path is metadata on the
    # leg row, never signed.
    assert "endpoint" not in perp
    assert set(perp.keys()) == {
        "symbol", "side", "type", "quantity", "positionSide",
        "newClientOrderId", "newOrderRespType",
    }
    assert perp["side"] == "BUY"           # reverse opens long
    assert perp["positionSide"] == "LONG"  # hedge mode
    assert perp["quantity"] == "0.5"
    assert "reduceOnly" not in perp
    for key in _FORBIDDEN_SECRET_KEYS:
        assert key not in perp


def test_record_transport_marks_posted_false_and_q_common():
    exe = RecordTransportFake()
    out = exe.execute(_ctx())
    assert out.record_payload["posted"] is False
    assert out.record_payload["q_common"] == "0.5"
    assert out.record_payload["q_common_resolved"] is True
    assert out.record_payload["client_ids"] == {"spot": "hgabc123s", "perp": "hgabc123p"}


def test_record_transport_unrounded_quantity_when_no_q_common():
    # Dry-run without a resolved preflight still records the would-send quantity
    # using single_amount as the unrounded estimate, flagged so it is visible.
    exe = RecordTransportFake()
    out = exe.execute(_ctx(q_common=None, single_amount="0.555"))
    assert out.record_payload["q_common"] is None
    assert out.record_payload["q_common_resolved"] is False
    assert out.record_payload["send_quantity"] == "0.555"


# ---------------------------------------------------------------------------
# S1 client-order-id derivation (ADR-H1): ≤36 chars, distinct, charset-safe
# ---------------------------------------------------------------------------
def test_client_order_id_derivation_within_cap_distinct_charset_unique():
    """S1: the two derived ids are ≤36 chars, mutually distinct, over Binance's
    documented charset, and unique per attempt; the pre-fix 38-char form is gone."""
    import uuid
    from backend.hedge_open_tasks.executor import _client_order_ids
    from backend.hedge_open_tasks.wire_constraints import CLIENT_ORDER_ID_RE

    seen = set()
    for _ in range(2000):
        aid = uuid.uuid4().hex
        assert len(aid) == 32  # uuid4 hex
        spot, perp = _client_order_ids(aid)
        assert spot == f"hg{aid}s"
        assert perp == f"hg{aid}p"
        assert spot != perp
        assert len(spot) == 35 and len(perp) == 35  # hg(2) + hex(32) + suffix(1)
        assert CLIENT_ORDER_ID_RE.match(spot)
        assert CLIENT_ORDER_ID_RE.match(perp)
        assert spot not in seen and perp not in seen
        seen.add(spot)
        seen.add(perp)
    # The pre-fix form was 38 chars (over the 36-char cap) and -4015'd; it is gone.
    bad = f"hgo-{uuid.uuid4().hex}-s"
    assert len(bad) == 38 > 36


# ---------------------------------------------------------------------------
# Injectable outcomes (single-leg exposure + >3-fail termination paths)
# ---------------------------------------------------------------------------

def test_seed_spot_only_filled_is_single_leg_exposure():
    exe = RecordTransportFake([OutcomeSpec.spot_only_filled()])
    out = exe.execute(_ctx())
    assert out.category == D.ATTEMPT_SINGLE_LEG_EXPOSURE
    assert out.exposure is not None
    assert set(out.exposure.keys()) == {"leg", "qty", "price", "ts"}
    assert out.exposure["leg"] == "spot"
    assert out.exposure["qty"] == "0.5"
    assert out.exposure["price"] == "50000"


def test_seed_perp_only_filled_is_single_leg_exposure():
    exe = RecordTransportFake([OutcomeSpec.perp_only_filled()])
    out = exe.execute(_ctx())
    assert out.category == D.ATTEMPT_SINGLE_LEG_EXPOSURE
    assert out.exposure is not None
    assert set(out.exposure.keys()) == {"leg", "qty", "price", "ts"}
    assert out.exposure["leg"] == "perp"
    assert out.exposure["qty"] == "0.5"
    assert out.exposure["price"] == "50000"


def test_seed_both_failed_is_failed():
    exe = RecordTransportFake([OutcomeSpec.both_failed()])
    out = exe.execute(_ctx())
    assert out.category == D.ATTEMPT_FAILED
    assert out.exposure is None


def test_seed_qty_mismatch_is_success():
    exe = RecordTransportFake([OutcomeSpec.qty_mismatch(Decimal("0.5"), Decimal("0.4"))])
    out = exe.execute(_ctx())
    # fix-3 (DI-6): both legs FILLED -> success regardless of filled-qty mismatch.
    assert out.category == D.ATTEMPT_SUCCESS
    # success does not build a leg_exposure document.
    assert out.exposure is None


def test_seeds_consumed_in_order_then_balanced():
    exe = RecordTransportFake([OutcomeSpec.both_failed()])
    assert exe.execute(_ctx()).category == D.ATTEMPT_FAILED
    # subsequent attempts fall back to balanced.
    assert exe.execute(_ctx()).category == D.ATTEMPT_SUCCESS


# ---------------------------------------------------------------------------
# AST-level proof: no network / signing imports in the hedge package
# ---------------------------------------------------------------------------

def test_no_network_or_signing_imports_in_hedge_package():
    import ast

    forbidden_roots = {"urllib", "http", "socket", "hmac", "hashlib", "ssl", "requests"}
    bad = []
    for py in HEDGE_PKG.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden_roots:
                        bad.append((py.name, alias.name))
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root in forbidden_roots:
                    bad.append((py.name, node.module))
    assert bad == [], f"forbidden network/signing imports in hedge_open_tasks: {bad}"


# ---------------------------------------------------------------------------
# Runtime proof: a full scenario issues ZERO urllib calls
# ---------------------------------------------------------------------------

class _Clock:
    def __init__(self, t0=0):
        self.t = t0

    def mono_us(self):
        return self.t

    def wall_us(self):
        return self.t


def test_full_scenario_makes_zero_urllib_calls(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("urlopen must never be called on a hedge-open path")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    clock = _Clock(0)
    exe = RecordTransportFake(
        [OutcomeSpec.spot_only_filled(), OutcomeSpec.both_failed(), OutcomeSpec.balanced()]
    )
    svc = HedgeOpenTaskService(
        str(tmp_path / "ho.sqlite3"),
        executor=exe,
        mono_us=clock.mono_us,
        wall_us=clock.wall_us,
    )
    svc.set_start_gate(True)
    svc.create_task(
        {"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
         "single_amount": "0.5", "target_n": 2}
    )
    for t in range(4):
        clock.t = t * 1_000_000
        svc.tick()  # exercises success / single-leg / failed categories
    # exercise the read API surface too
    svc.list_tasks(None)
    svc.get_settings()
    svc.get_logs(None, None)
    svc.get_positions()
    # reaching here proves no hedge-open path attempted a network call


def test_service_default_executor_is_disabled(tmp_path):
    # B-1 (stage 2026-08-06): the production default executor is now
    # DisabledHedgeExecutor — zero I/O, zero fills. The record-transport fill
    # simulator moved to backend/tests/fakes.py (RecordTransportFake).
    svc = HedgeOpenTaskService(str(tmp_path / "ho.sqlite3"))
    assert isinstance(svc.executor, DisabledHedgeExecutor)


# ---------------------------------------------------------------------------
# No-credential proof: poisoned env secrets never reach logs or API bodies
# ---------------------------------------------------------------------------

def test_poisoned_env_secrets_never_leak(tmp_path, monkeypatch):
    secrets = {
        "BINANCE_API_KEY": "SECRETKEY-AAAA",
        "BINANCE_API_SECRET": "SECRETSECRET-BBBB",
        "BINANCE_SIGNATURE": "SIG-CCCC-DDDD",
    }
    for key, value in secrets.items():
        monkeypatch.setenv(key, value)
    clock = _Clock(0)
    svc = HedgeOpenTaskService(
        str(tmp_path / "ho.sqlite3"),
        executor=RecordTransportFake(),
        mono_us=clock.mono_us,
        wall_us=clock.wall_us,
    )
    svc.set_start_gate(True)
    svc.create_task(
        {"coin": "BTCUSDT", "direction": "reverse", "mode": "immediate",
         "single_amount": "0.5", "target_n": 1}
    )
    clock.t = 1_000_000
    svc.tick()
    _, tasks = svc.list_tasks(None)
    _, logs = svc.get_logs(None, None)
    _, settings = svc.get_settings()
    blob = json.dumps([tasks, logs, settings])
    for secret in secrets.values():
        assert secret not in blob


# ---------------------------------------------------------------------------
# W6 — preflight snapshot key-name contract (10-design §5 / §9 S5 / ADR-H4)
# 2026-07-hedge-order-truth-v1. compute_preflight writes one leg's effective
# MARKET qty step/bounds into the sanitized snapshot record as ``{leg}_step`` /
# ``{leg}_min_qty`` / ``{leg}_max_qty``; _leg_qty_filters reads those exact keys
# when sizing each leg's POST params. This test pins the seam so the writer
# (domain) and the reader (executor) cannot drift apart without a failing test,
# and that a bound the writer disables (None) the reader omits (disabled) —
# never coercing a missing bound to 0.
# ---------------------------------------------------------------------------


def test_preflight_snapshot_keys_and_qty_filters_reader_agree():
    # spot: MARKET_LOT_SIZE carries step + min + max (all enabled).
    # perp: MARKET disabled (step/min/max all 0), LOT_SIZE carries step + min;
    #       max disabled. Exercises both "bound present" and "bound disabled"
    #       paths on the same record.
    snapshot = D.PreflightSnapshot(
        spot_filters={
            "market_lot_size": {"step_size": "0.0001", "min_qty": "0.0002", "max_qty": "999"},
            "lot_size": {"step_size": "0.00001", "min_qty": "0.00001", "max_qty": "9000"},
        },
        perp_filters={
            "market_lot_size": {"step_size": "0", "min_qty": "0", "max_qty": "0"},
            "lot_size": {"step_size": "0.001", "min_qty": "0.002", "max_qty": "0"},
        },
        balances={"USDT": Decimal("1000000")},
        position_mode=D.POS_MODE_BOTH,
        est_price=Decimal("50000"),
        symbol_tradable=True,
    )
    pf = D.compute_preflight(snapshot, "BTCUSDT", D.DIR_FORWARD, Decimal("0.5"), 3)
    record = pf.snapshot_record
    assert record["available"] is True

    # Writer↔reader contract per leg: every key the writer emits, the reader
    # consumes with an equal value; every key the writer disables (None), the
    # reader omits. Symmetric across step/min/max and both legs.
    for leg in ("spot", "perp"):
        for record_key, kwarg in (
            (f"{leg}_step", "step_size"),
            (f"{leg}_min_qty", "min_qty"),
            (f"{leg}_max_qty", "max_qty"),
        ):
            filters = _leg_qty_filters(record, leg)
            written = record[record_key]
            if written is not None:
                assert filters[kwarg] == written
            else:
                assert kwarg not in filters

    # Value identity through the seam (string-for-string).
    assert _leg_qty_filters(record, "spot") == {
        "step_size": "0.0001", "min_qty": "0.0002", "max_qty": "999",
    }
    assert _leg_qty_filters(record, "perp") == {
        "step_size": "0.001", "min_qty": "0.002",
    }  # perp max_qty disabled -> absent, never coerced to 0
