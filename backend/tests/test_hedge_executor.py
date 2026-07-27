"""Executor seam + dry-run record-transport proofs (10-design §6 / §9 / ADR-5).

Covers DisabledHedgeExecutor, the dry-run RecordTransportExecutor (the round-1
default): the would-send signed-request param shape (no secrets), the simulated
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
    OutcomeSpec,
    RecordTransportExecutor,
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
# RecordTransportExecutor — default balanced outcome + param shape
# ---------------------------------------------------------------------------

def test_record_transport_default_is_balanced_dual_leg_fill():
    exe = RecordTransportExecutor()
    out = exe.execute(_ctx())
    assert out.category == D.ATTEMPT_SUCCESS
    assert out.spot["status"] == D.LEG_FILLED
    assert out.spot["filled_qty"] == "0.5"
    assert out.perp["filled_qty"] == "0.5"
    assert out.exposure is None


def test_record_transport_spot_params_shape_forward():
    exe = RecordTransportExecutor()
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


def test_record_transport_perp_params_shape_reverse_hedge():
    exe = RecordTransportExecutor()
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
    exe = RecordTransportExecutor()
    out = exe.execute(_ctx())
    assert out.record_payload["posted"] is False
    assert out.record_payload["q_common"] == "0.5"
    assert out.record_payload["q_common_resolved"] is True
    assert out.record_payload["client_ids"] == {"spot": "hgabc123s", "perp": "hgabc123p"}


def test_record_transport_unrounded_quantity_when_no_q_common():
    # Dry-run without a resolved preflight still records the would-send quantity
    # using single_amount as the unrounded estimate, flagged so it is visible.
    exe = RecordTransportExecutor()
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
    exe = RecordTransportExecutor([OutcomeSpec.spot_only_filled()])
    out = exe.execute(_ctx())
    assert out.category == D.ATTEMPT_SINGLE_LEG_EXPOSURE
    assert out.exposure is not None
    assert set(out.exposure.keys()) == {"leg", "qty", "price", "ts"}
    assert out.exposure["leg"] == "spot"
    assert out.exposure["qty"] == "0.5"
    assert out.exposure["price"] == "50000"


def test_seed_perp_only_filled_is_single_leg_exposure():
    exe = RecordTransportExecutor([OutcomeSpec.perp_only_filled()])
    out = exe.execute(_ctx())
    assert out.category == D.ATTEMPT_SINGLE_LEG_EXPOSURE
    assert out.exposure is not None
    assert set(out.exposure.keys()) == {"leg", "qty", "price", "ts"}
    assert out.exposure["leg"] == "perp"
    assert out.exposure["qty"] == "0.5"
    assert out.exposure["price"] == "50000"


def test_seed_both_failed_is_failed():
    exe = RecordTransportExecutor([OutcomeSpec.both_failed()])
    out = exe.execute(_ctx())
    assert out.category == D.ATTEMPT_FAILED
    assert out.exposure is None


def test_seed_qty_mismatch_is_success():
    exe = RecordTransportExecutor([OutcomeSpec.qty_mismatch(Decimal("0.5"), Decimal("0.4"))])
    out = exe.execute(_ctx())
    # fix-3 (DI-6): both legs FILLED -> success regardless of filled-qty mismatch.
    assert out.category == D.ATTEMPT_SUCCESS
    # success does not build a leg_exposure document.
    assert out.exposure is None


def test_seeds_consumed_in_order_then_balanced():
    exe = RecordTransportExecutor([OutcomeSpec.both_failed()])
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
    exe = RecordTransportExecutor(
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


def test_service_default_executor_is_record_transport(tmp_path):
    svc = HedgeOpenTaskService(str(tmp_path / "ho.sqlite3"))
    assert isinstance(svc.executor, RecordTransportExecutor)


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
        executor=RecordTransportExecutor(),
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
