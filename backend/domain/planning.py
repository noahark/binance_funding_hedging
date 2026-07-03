"""Planning preview: base-qty alignment, step rounding, notional recheck."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN
from typing import Any


@dataclass(frozen=True)
class PlanningRound:
    """One planning round with base quantity and notional estimates."""

    round_index: int
    base_quantity: str
    futures_notional: str | None
    spot_notional: str | None


@dataclass(frozen=True)
class PlanningPreview:
    """Full planning preview result."""

    total_base_quantity: str
    round_count: int
    corrected_min_notional: str | None
    coarser_step_size: str | None
    rounds: list[PlanningRound]
    remainder_merged: bool
    feasible: bool = True
    status: str = "ok"


def _round_down_to_step(qty: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return qty
    steps = (qty / step).to_integral_value(rounding=ROUND_DOWN)
    return steps * step


def _min_base_for_notional(
    min_notional: Decimal,
    futures_price: Decimal,
    spot_price: Decimal,
) -> Decimal:
    """Minimum base qty so both legs meet the notional threshold."""
    return max(
        min_notional / futures_price,
        min_notional / spot_price,
    )


def _leg_below_min_notional(
    fut_notional: Decimal,
    spot_notional: Decimal,
    futures_min_notional: Decimal | None,
    spot_min_notional: Decimal | None,
) -> bool:
    """True when either leg's notional is below its own min filter."""
    if futures_min_notional is not None and fut_notional < futures_min_notional:
        return True
    return spot_min_notional is not None and spot_notional < spot_min_notional


def _bump_qty_for_min_notional(
    qty: Decimal,
    coarser_step: Decimal | None,
    futures_price: Decimal,
    spot_price: Decimal,
    futures_min_notional: Decimal | None,
    spot_min_notional: Decimal | None,
) -> Decimal:
    """Raise qty by one step when post-rounding notionals fail min filters."""
    fut_notional = qty * futures_price
    spot_notional = qty * spot_price
    fut_ok = futures_min_notional is None or fut_notional >= futures_min_notional
    spot_ok = spot_min_notional is None or spot_notional >= spot_min_notional
    if not fut_ok or not spot_ok:
        if coarser_step is not None:
            qty = _round_down_to_step(qty + coarser_step, coarser_step)
    return qty


def plan_hedge_rounds(
    total_base_quantity: Decimal,
    futures_price: Decimal,
    spot_price: Decimal,
    futures_min_notional: Decimal | None,
    spot_min_notional: Decimal | None,
    futures_step_size: Decimal | None,
    spot_step_size: Decimal | None,
    requested_rounds: int = 1,
) -> PlanningPreview:
    """
    Plan hedge rounds with base-qty alignment.

    Applies min-notional correction (max * 1.02), recalculates round count,
    rounds to coarser step, rechecks notional filters, and merges sub-min
    final remainder into the previous round.
    """
    coarser_step: Decimal | None = None
    if futures_step_size is not None and spot_step_size is not None:
        coarser_step = max(futures_step_size, spot_step_size)
    elif futures_step_size is not None:
        coarser_step = futures_step_size
    elif spot_step_size is not None:
        coarser_step = spot_step_size

    mins = [m for m in (futures_min_notional, spot_min_notional) if m is not None]
    corrected_min: Decimal | None = max(mins) * Decimal("1.02") if mins else None

    raw_base_per_round = total_base_quantity / Decimal(max(requested_rounds, 1))
    min_base_per_round = Decimal("0")
    if corrected_min is not None:
        min_base_per_round = _min_base_for_notional(
            corrected_min, futures_price, spot_price
        )

    effective_base = max(raw_base_per_round, min_base_per_round)
    if coarser_step is not None:
        effective_base = _round_down_to_step(effective_base, coarser_step)
        if effective_base <= 0 and min_base_per_round > 0:
            steps = (min_base_per_round / coarser_step).to_integral_value(
                rounding=ROUND_CEILING
            )
            effective_base = steps * coarser_step

    actual_per_round = _bump_qty_for_min_notional(
        effective_base,
        coarser_step,
        futures_price,
        spot_price,
        futures_min_notional,
        spot_min_notional,
    )

    if actual_per_round > total_base_quantity:
        return PlanningPreview(
            total_base_quantity=str(total_base_quantity),
            round_count=0,
            corrected_min_notional=str(corrected_min) if corrected_min else None,
            coarser_step_size=str(coarser_step) if coarser_step else None,
            rounds=[],
            remainder_merged=False,
            feasible=False,
            status="infeasible",
        )

    round_count = max(
        1,
        int(
            (total_base_quantity / actual_per_round).to_integral_value(
                rounding=ROUND_CEILING
            )
        ),
    ) if actual_per_round > 0 else 1

    rounds: list[PlanningRound] = []
    allocated = Decimal("0")
    remainder_merged = False

    for i in range(round_count):
        is_last = i == round_count - 1
        qty = total_base_quantity - allocated if is_last else actual_per_round

        if coarser_step is not None:
            qty = _round_down_to_step(qty, coarser_step)

        if qty <= 0:
            continue

        fut_notional = qty * futures_price
        spot_notional = qty * spot_price

        if is_last and _leg_below_min_notional(
            fut_notional,
            spot_notional,
            futures_min_notional,
            spot_min_notional,
        ):
            if rounds:
                prev = rounds[-1]
                merged = Decimal(prev.base_quantity) + qty
                rounds[-1] = PlanningRound(
                    round_index=prev.round_index,
                    base_quantity=str(merged),
                    futures_notional=str(merged * futures_price),
                    spot_notional=str(merged * spot_price),
                )
                remainder_merged = True
                allocated += qty
                continue
            return PlanningPreview(
                total_base_quantity=str(total_base_quantity),
                round_count=0,
                corrected_min_notional=str(corrected_min) if corrected_min else None,
                coarser_step_size=str(coarser_step) if coarser_step else None,
                rounds=[],
                remainder_merged=False,
                feasible=False,
                status="infeasible",
            )

        rounds.append(
            PlanningRound(
                round_index=len(rounds) + 1,
                base_quantity=str(qty),
                futures_notional=str(fut_notional),
                spot_notional=str(spot_notional),
            )
        )
        allocated += qty

    return PlanningPreview(
        total_base_quantity=str(total_base_quantity),
        round_count=len(rounds),
        corrected_min_notional=str(corrected_min) if corrected_min else None,
        coarser_step_size=str(coarser_step) if coarser_step else None,
        rounds=rounds,
        remainder_merged=remainder_merged,
    )


def planning_preview_to_dict(preview: PlanningPreview) -> dict[str, Any]:
    """Serialize planning preview for JSON output."""
    return {
        "total_base_quantity": preview.total_base_quantity,
        "round_count": preview.round_count,
        "corrected_min_notional": preview.corrected_min_notional,
        "coarser_step_size": preview.coarser_step_size,
        "remainder_merged": preview.remainder_merged,
        "feasible": preview.feasible,
        "status": preview.status,
        "rounds": [
            {
                "round_index": r.round_index,
                "base_quantity": r.base_quantity,
                "futures_notional": r.futures_notional,
                "spot_notional": r.spot_notional,
            }
            for r in preview.rounds
        ],
    }