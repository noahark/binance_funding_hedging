"""Offline wire-constraint validator tests (10-design §2.5 / ADR-H4 / §8).

Covers the single offline copy of the Binance new-order wire rules
(:mod:`backend.hedge_open_tasks.wire_constraints`), its consumption by the dry-run
record transport (a format defect fails OFFLINE instead of being acted out as a
fill), the strict fake client (returns a Binance-style ``-4015``), and the A-5
probe: ``str(Decimal)`` of a very small quantity yields scientific notation, so
the params-build seam routes through :func:`domain.fmt_decimal`.

No network: every path is in-memory.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.executor import (
    AttemptContext,
    _client_order_ids,
    build_perp_order_params,
    build_spot_order_params,
)
from backend.tests.fakes import RecordTransportFake
from backend.hedge_open_tasks.wire_constraints import (
    CLIENT_ORDER_ID_MAX,
    validate_client_order_id,
    validate_order_params,
)


def _ctx(
    *, attempt_id="a" * 32, direction=D.DIR_FORWARD, position_side_mode="BOTH",
    q_common="0.5", single_amount="0.5",
) -> AttemptContext:
    # attempt_id defaults to a full 32-hex-length id (as service.prepare_attempt
    # produces from uuid4().hex), so the derived client ids hit their real 35-char
    # length and the cap is exercised at production scale.
    return AttemptContext(
        attempt_id=attempt_id,
        task_id="t1",
        coin="BTCUSDT",
        direction=direction,
        single_amount=Decimal(single_amount),
        q_common=Decimal(q_common) if q_common else None,
        position_side_mode=position_side_mode,
        preflight_snapshot={"est_price": "50000"},
        filter_versions={},
        target_n=3,
        ts_us=1_000_000,
        spot_symbol="BTCUSDT",
    )


# ---------------------------------------------------------------------------
# validate_client_order_id matrix (length + charset)
# ---------------------------------------------------------------------------
def test_validate_client_order_id_accepts_valid_ids():
    assert validate_client_order_id("hg" + "a" * 32 + "s") is None  # 35 chars
    assert validate_client_order_id("a") is None                    # 1 char
    assert validate_client_order_id("A" * CLIENT_ORDER_ID_MAX) is None  # 36 chars
    # Documented charset: letters, digits, . : / _ -
    assert validate_client_order_id("order_1.2:3/4-5") is None


@pytest.mark.parametrize("value", ["", "a" * 37, "ab!", "ab c", "a@b"])
def test_validate_client_order_id_rejects_invalid(value):
    assert validate_client_order_id(value) is not None


@pytest.mark.parametrize("value", [None, 123, 4.5, ["x"]])
def test_validate_client_order_id_rejects_non_string(value):
    assert validate_client_order_id(value) is not None


# ---------------------------------------------------------------------------
# validate_order_params: quantity (fixed-point, positive, no scientific notation)
# ---------------------------------------------------------------------------
def _valid_params(**over):
    base = {
        "symbol": "BTCUSDT", "side": "BUY", "type": "MARKET",
        "quantity": "0.5", "newClientOrderId": "hgxs",
    }
    base.update(over)
    return base


def test_validate_order_params_accepts_clean_market_body():
    assert validate_order_params(_valid_params()) == []


@pytest.mark.parametrize("qty", ["1E-7", "1e-7", "0", "0.0", "-0.5", ".5", "0.5.5"])
def test_validate_order_params_rejects_bad_quantity(qty):
    assert validate_order_params(_valid_params(quantity=qty))


def test_validate_order_params_rejects_scientific_notation_explicitly():
    # The exact pre-fix failure mode: str(Decimal('0.0000001')) == '1E-7'.
    assert validate_order_params(_valid_params(quantity="1E-7")) == [
        "quantity must be a positive fixed-point decimal string",
    ]


# ---------------------------------------------------------------------------
# validate_order_params: symbol / side / type / client id
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("over,key_fragment", [
    ({"symbol": "btcusdt"}, "symbol"),
    ({"side": "buy"}, "side"),
    ({"type": "LIMIT"}, "type"),
    ({"newClientOrderId": "a" * 37}, "newClientOrderId"),
])
def test_validate_order_params_reports_each_field(over, key_fragment):
    violations = validate_order_params(_valid_params(**over))
    assert any(key_fragment in v for v in violations), violations


# ---------------------------------------------------------------------------
# validate_order_params: optional grid (step) + bounds (min/max)
# ---------------------------------------------------------------------------
def test_validate_order_params_grid_accepts_whole_multiple():
    p = _valid_params(quantity="0.5")
    assert validate_order_params(p, step_size="0.001", min_qty="0.001", max_qty="1") == []


def test_validate_order_params_grid_rejects_non_multiple():
    p = _valid_params(quantity="0.0005")
    violations = validate_order_params(p, step_size="0.001")
    assert any("multiple of step_size" in v for v in violations), violations


def test_validate_order_params_bounds_reject_below_and_above():
    assert validate_order_params(_valid_params(quantity="0.0001"), min_qty="0.001")
    assert validate_order_params(_valid_params(quantity="2"), max_qty="1")


# ---------------------------------------------------------------------------
# A-5 probe (10-design §8): str(Decimal) scientific notation -> seam to fmt_decimal
# ---------------------------------------------------------------------------
def test_a5_small_decimal_quantity_is_fixed_point_not_scientific():
    """A-5: ``str(quantity)`` of a very small value yields scientific notation
    (``str(Decimal('0.0000001')) == '1E-7'``); the params-build seam now routes
    through :func:`domain.fmt_decimal` so the wire value stays a plain fixed-point
    decimal the exchange accepts, and the validator rejects the ``1E-7`` form."""
    tiny = Decimal("0.0000001")
    # Evidence the raw str() form WOULD be scientific notation (the pre-fix seam).
    assert str(tiny) == "1E-7"
    actions = D.direction_to_leg_actions(D.DIR_FORWARD, D.POS_MODE_BOTH)
    spot = build_spot_order_params("BTCUSDT", actions, tiny, "hgxs")
    perp = build_perp_order_params("BTCUSDT", actions, tiny, "hgxp")
    # The seam now produces a fixed-point string, accepted by the validator.
    assert spot["quantity"] == "0.0000001"
    assert perp["quantity"] == "0.0000001"
    assert validate_order_params(spot) == []
    assert validate_order_params(perp) == []
    # And the validator rejects the scientific-notation form (pinning the rule).
    assert validate_order_params({**spot, "quantity": "1E-7"})


# ---------------------------------------------------------------------------
# Pre-fix S1 regression: the offline gate makes a format defect fail OFFLINE
# (10-design §2.5 acceptance core). Pins the PROPERTY, not just the number 36.
# ---------------------------------------------------------------------------
def test_prefix_s1_derivation_fails_offline_and_new_derivation_restores(monkeypatch):
    """A 38-char client id (the pre-fix ``hgo-<hex>-s`` derivation) is rejected by
    the offline gate as a two-leg REJECTED outcome with ``offline_constraint``;
    restoring the new ``hg<hex>{s|p}`` derivation returns the same path to a
    balanced fill. This fixes the defect class offline, not on a real send."""
    import backend.tests.fakes as fakes_mod

    aid = "b" * 32
    # New derivation (the shipped code): 35 chars -> passes the offline gate.
    new_exe = RecordTransportFake()
    out_new = new_exe.execute(_ctx(attempt_id=aid))
    assert out_new.category == D.ATTEMPT_SUCCESS
    assert out_new.error_code is None
    assert "constraint_violations" not in out_new.record_payload

    # Pre-fix derivation (38 chars) -> fails the offline gate end-to-end.
    def _old(attempt_id):
        return f"hgo-{attempt_id}-s", f"hgo-{attempt_id}-p"

    # The fake lives in backend/tests/fakes.py and binds _client_order_ids at
    # import time, so the monkeypatch must target the fakes module, not
    # hedge_open_tasks.executor (whose production callers are unaffected).
    monkeypatch.setattr(fakes_mod, "_client_order_ids", _old)
    old_exe = RecordTransportFake()
    out_old = old_exe.execute(_ctx(attempt_id=aid))
    assert out_old.category == D.ATTEMPT_FAILED
    assert out_old.error_code == "offline_constraint"
    assert out_old.error_reason_zh == "离线参数约束校验失败"
    assert out_old.spot["status"] == D.LEG_REJECTED
    assert out_old.perp["status"] == D.LEG_REJECTED
    assert out_old.spot["client_order_id"] == f"hgo-{aid}-s"
    assert out_old.perp["client_order_id"] == f"hgo-{aid}-p"
    violations = out_old.record_payload["constraint_violations"]
    assert violations and any("newClientOrderId length" in v for v in violations)
    assert out_old.record_payload["posted"] is False

    # Restore the new derivation -> the same path returns to a balanced fill.
    monkeypatch.undo()
    assert _client_order_ids(aid) == (f"hg{aid}s", f"hg{aid}p")
    restored_exe = RecordTransportFake()
    out_restored = restored_exe.execute(_ctx(attempt_id=aid))
    assert out_restored.category == D.ATTEMPT_SUCCESS
    assert out_restored.error_code is None


def test_record_transport_records_constraint_violations_only_when_defective():
    """A clean dispatch leaves ``constraint_violations`` absent; only a defective
    one records the evidence list (never swallowed)."""
    exe = RecordTransportFake()
    out = exe.execute(_ctx())
    assert out.category == D.ATTEMPT_SUCCESS
    assert "constraint_violations" not in out.record_payload
    assert out.record_payload["posted"] is False


# ---------------------------------------------------------------------------
# S5 (Review-2 REWORK): the record transport consumes the loaded qty grid/
# bounds END-TO-END — a quantity that violates the symbol filters already
# loaded in the preflight snapshot is rejected OFFLINE, not acted out as a fill.
# ---------------------------------------------------------------------------
def _ctx_with_qty_filters(
    spot: dict, perp: dict, *, q_common: str, single_amount: str | None = None,
) -> AttemptContext:
    """An AttemptContext whose ``preflight_snapshot`` carries each leg's
    effective MARKET qty grid/bounds exactly as :func:`domain.compute_preflight`
    records them (``{leg}_step`` / ``{leg}_min_qty`` / ``{leg}_max_qty``), so the
    record transport's S5 gate can be exercised end-to-end. ``spot``/``perp`` are
    ``{"step": ..., "min_qty": ..., "max_qty": ...}`` dicts; any key optional."""
    snap = {"est_price": "50000"}
    for key, value in spot.items():
        snap[f"spot_{key}"] = value
    for key, value in perp.items():
        snap[f"perp_{key}"] = value
    return AttemptContext(
        attempt_id="a" * 32,  # 32-hex -> 35-char client ids pass the cid gate
        task_id="t1",
        coin="BTCUSDT",
        direction=D.DIR_FORWARD,
        single_amount=Decimal(single_amount or q_common),
        q_common=Decimal(q_common),
        position_side_mode="BOTH",
        preflight_snapshot=snap,
        filter_versions={},
        target_n=3,
        ts_us=1_000_000,
        spot_symbol="BTCUSDT",
    )


_GRID_FILTERS = {"step": "0.001", "min_qty": "0.001", "max_qty": "100"}


@pytest.mark.parametrize("q_common,fragments", [
    # 0.0005 is below step_size 0.001 AND below min_qty 0.001 (two violations).
    ("0.0005", ["multiple of step_size", "below min_qty"]),
    # 200 exceeds max_qty 100 (step/min still satisfied).
    ("200", ["exceeds max_qty"]),
])
def test_record_transport_rejects_quantity_violating_loaded_filters(q_common, fragments):
    """S5: a quantity that violates the symbol filters already loaded in the
    preflight snapshot is rejected OFFLINE — both legs REJECTED with
    ``offline_constraint``, the violations recorded, and NO simulated fill —
    rather than acted out as a balanced success (the pre-fix behavior the
    Review-2 finding reproduced with q_common=0.0005 and step=min=0.001)."""
    exe = RecordTransportFake()
    ctx = _ctx_with_qty_filters(_GRID_FILTERS, _GRID_FILTERS, q_common=q_common)
    out = exe.execute(ctx)
    assert out.category == D.ATTEMPT_FAILED
    assert out.error_code == "offline_constraint"
    assert out.error_reason_zh == "离线参数约束校验失败"
    assert out.spot["status"] == D.LEG_REJECTED
    assert out.perp["status"] == D.LEG_REJECTED
    # No simulated fill on a constraint rejection (zero executed qty on both legs).
    assert out.spot["filled_qty"] == "0"
    assert out.perp["filled_qty"] == "0"
    assert out.record_payload["posted"] is False
    violations = out.record_payload["constraint_violations"]
    for fragment in fragments:
        assert any(fragment in v for v in violations), (fragment, violations)


def test_record_transport_accepts_grid_aligned_quantity_with_loaded_filters():
    """S5 positive case: once the loaded filters are honored, a grid-aligned
    quantity within bounds is still simulated as a balanced fill (success)."""
    exe = RecordTransportFake()
    ctx = _ctx_with_qty_filters(_GRID_FILTERS, _GRID_FILTERS, q_common="0.003")
    out = exe.execute(ctx)
    assert out.category == D.ATTEMPT_SUCCESS
    assert out.error_code is None
    assert "constraint_violations" not in out.record_payload
    assert out.spot["filled_qty"] == "0.003"
    assert out.perp["filled_qty"] == "0.003"


def test_record_transport_applies_per_leg_filters_independently():
    """S5: the two legs carry their OWN filters. A quantity grid-aligned for
    spot (step 0.001) but not for perp (step 0.01) is rejected because the perp
    leg's own filter fails — proving each leg adopts its own loaded filter, not
    a single shared one."""
    exe = RecordTransportFake()
    ctx = _ctx_with_qty_filters(
        {"step": "0.001", "min_qty": "0.001", "max_qty": "100"},
        {"step": "0.01", "min_qty": "0.01", "max_qty": "100"},
        q_common="0.005",  # 5 x 0.001 (spot ok) but 0.5 x 0.01 (perp violates)
    )
    out = exe.execute(ctx)
    assert out.category == D.ATTEMPT_FAILED
    assert out.error_code == "offline_constraint"
    violations = out.record_payload["constraint_violations"]
    # The perp leg is the one that violates; the spot leg is clean.
    assert any(v.startswith("perp:") and "multiple of step_size" in v for v in violations)
    assert any(v.startswith("perp:") and "below min_qty" in v for v in violations)
    assert not any(v.startswith("spot:") for v in violations)
