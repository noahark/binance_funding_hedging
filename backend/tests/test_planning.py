"""Tests for planning preview."""

from __future__ import annotations

from decimal import Decimal

from backend.domain.planning import PlanningPreview, plan_hedge_rounds


def test_base_qty_rounds_with_coarser_step() -> None:
    preview = plan_hedge_rounds(
        total_base_quantity=Decimal("1.0"),
        futures_price=Decimal("60000"),
        spot_price=Decimal("59900"),
        futures_min_notional=Decimal("100"),
        spot_min_notional=Decimal("5"),
        futures_step_size=Decimal("0.001"),
        spot_step_size=Decimal("0.01"),
        requested_rounds=4,
    )
    assert preview.coarser_step_size == "0.01"
    assert preview.round_count >= 1
    for r in preview.rounds:
        qty = Decimal(r.base_quantity)
        assert qty % Decimal("0.01") == 0


def test_min_notional_correction_recalculates_rounds() -> None:
    preview = plan_hedge_rounds(
        total_base_quantity=Decimal("0.05"),
        futures_price=Decimal("60000"),
        spot_price=Decimal("60000"),
        futures_min_notional=Decimal("100"),
        spot_min_notional=None,
        futures_step_size=Decimal("0.001"),
        spot_step_size=Decimal("0.001"),
        requested_rounds=10,
    )
    assert preview.corrected_min_notional == str(Decimal("100") * Decimal("1.02"))
    assert preview.round_count >= 1


def test_post_round_notional_recheck() -> None:
    preview = plan_hedge_rounds(
        total_base_quantity=Decimal("0.01"),
        futures_price=Decimal("60000"),
        spot_price=Decimal("60000"),
        futures_min_notional=Decimal("100"),
        spot_min_notional=Decimal("100"),
        futures_step_size=Decimal("0.001"),
        spot_step_size=Decimal("0.001"),
        requested_rounds=1,
    )
    for r in preview.rounds:
        fut = Decimal(r.futures_notional or "0")
        spot = Decimal(r.spot_notional or "0")
        if fut > 0:
            assert fut >= Decimal("100") or preview.remainder_merged
        if spot > 0:
            assert spot >= Decimal("100") or preview.remainder_merged


def _allocated_base(preview: PlanningPreview) -> Decimal:
    return sum(
        (Decimal(r.base_quantity) for r in preview.rounds),
        Decimal("0"),
    )


def test_low_total_high_rounds_no_over_allocation() -> None:
    """P1 repro: sum of round base_quantity must not exceed requested total."""
    total = Decimal("0.005")
    preview = plan_hedge_rounds(
        total_base_quantity=total,
        futures_price=Decimal("60000"),
        spot_price=Decimal("60000"),
        futures_min_notional=Decimal("100"),
        spot_min_notional=Decimal("100"),
        futures_step_size=Decimal("0.001"),
        spot_step_size=Decimal("0.001"),
        requested_rounds=10,
    )
    alloc = _allocated_base(preview)
    assert alloc <= total
    assert alloc == total
    assert preview.round_count == 2
    assert preview.remainder_merged is True
    assert [r.base_quantity for r in preview.rounds] == ["0.002", "0.003"]


def test_total_allocated_base_preserved() -> None:
    cases = [
        (Decimal("1.0"), 4),
        (Decimal("0.05"), 10),
        (Decimal("0.01"), 1),
        (Decimal("0.005"), 10),
    ]
    for total, requested_rounds in cases:
        preview = plan_hedge_rounds(
            total_base_quantity=total,
            futures_price=Decimal("60000"),
            spot_price=Decimal("60000"),
            futures_min_notional=Decimal("100"),
            spot_min_notional=Decimal("100"),
            futures_step_size=Decimal("0.001"),
            spot_step_size=Decimal("0.001"),
            requested_rounds=requested_rounds,
        )
        alloc = _allocated_base(preview)
        assert alloc <= total
        assert alloc == total


def test_recalculated_round_count_after_min_notional_bump() -> None:
    preview = plan_hedge_rounds(
        total_base_quantity=Decimal("0.005"),
        futures_price=Decimal("60000"),
        spot_price=Decimal("60000"),
        futures_min_notional=Decimal("100"),
        spot_min_notional=Decimal("100"),
        futures_step_size=Decimal("0.001"),
        spot_step_size=Decimal("0.001"),
        requested_rounds=10,
    )
    assert preview.round_count == len(preview.rounds)
    assert preview.round_count == 2


def test_both_leg_post_rounding_notional_validation() -> None:
    preview = plan_hedge_rounds(
        total_base_quantity=Decimal("0.005"),
        futures_price=Decimal("60000"),
        spot_price=Decimal("60000"),
        futures_min_notional=Decimal("100"),
        spot_min_notional=Decimal("100"),
        futures_step_size=Decimal("0.001"),
        spot_step_size=Decimal("0.001"),
        requested_rounds=10,
    )
    for r in preview.rounds:
        fut = Decimal(r.futures_notional or "0")
        spot = Decimal(r.spot_notional or "0")
        assert fut >= Decimal("100")
        assert spot >= Decimal("100")


def test_asymmetric_prices_final_round_merges_per_leg_min() -> None:
    """Case A: asymmetric prices — no emitted round may violate either leg's min."""
    preview = plan_hedge_rounds(
        total_base_quantity=Decimal("0.005"),
        futures_price=Decimal("120000"),
        spot_price=Decimal("60000"),
        futures_min_notional=Decimal("100"),
        spot_min_notional=Decimal("100"),
        futures_step_size=Decimal("0.001"),
        spot_step_size=Decimal("0.001"),
        requested_rounds=10,
    )
    assert preview.feasible is True
    assert preview.status == "ok"
    assert _allocated_base(preview) == Decimal("0.005")
    assert preview.remainder_merged is True
    for r in preview.rounds:
        fut = Decimal(r.futures_notional or "0")
        spot = Decimal(r.spot_notional or "0")
        assert fut >= Decimal("100")
        assert spot >= Decimal("100")


def test_total_below_single_min_compliant_round_infeasible() -> None:
    """Case B: total too small — explicit infeasible signal, no below-min round."""
    preview = plan_hedge_rounds(
        total_base_quantity=Decimal("0.001"),
        futures_price=Decimal("60000"),
        spot_price=Decimal("60000"),
        futures_min_notional=Decimal("100"),
        spot_min_notional=Decimal("100"),
        futures_step_size=Decimal("0.001"),
        spot_step_size=Decimal("0.001"),
        requested_rounds=1,
    )
    assert preview.feasible is False
    assert preview.status == "infeasible"
    assert preview.round_count == 0
    assert preview.rounds == []


def test_asymmetric_coarser_step_remainder_merge() -> None:
    """Asymmetric step sizes with small final remainder merge into previous round."""
    preview = plan_hedge_rounds(
        total_base_quantity=Decimal("0.01"),
        futures_price=Decimal("120000"),
        spot_price=Decimal("60000"),
        futures_min_notional=Decimal("100"),
        spot_min_notional=Decimal("150"),
        futures_step_size=Decimal("0.001"),
        spot_step_size=Decimal("0.002"),
        requested_rounds=3,
    )
    assert preview.feasible is True
    assert preview.remainder_merged is True
    assert _allocated_base(preview) == Decimal("0.01")
    for r in preview.rounds:
        fut = Decimal(r.futures_notional or "0")
        spot = Decimal(r.spot_notional or "0")
        assert fut >= Decimal("100")
        assert spot >= Decimal("150")


def test_remainder_merge_stays_within_total() -> None:
    preview = plan_hedge_rounds(
        total_base_quantity=Decimal("0.005"),
        futures_price=Decimal("60000"),
        spot_price=Decimal("60000"),
        futures_min_notional=Decimal("100"),
        spot_min_notional=Decimal("100"),
        futures_step_size=Decimal("0.001"),
        spot_step_size=Decimal("0.001"),
        requested_rounds=10,
    )
    assert preview.remainder_merged is True
    assert _allocated_base(preview) == Decimal("0.005")
    merged = preview.rounds[-1]
    assert Decimal(merged.base_quantity) == Decimal("0.003")
    assert Decimal(merged.futures_notional or "0") >= Decimal("100")
    assert Decimal(merged.spot_notional or "0") >= Decimal("100")