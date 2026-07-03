"""Trading rule parsing from exchangeInfo filters."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class TradingRules:
    """Parsed trading rules for one leg."""

    min_notional: Decimal | None
    step_size: Decimal | None


@dataclass(frozen=True)
class EffectiveTradingRules:
    """Effective rules across futures and spot legs."""

    futures_min_notional: Decimal | None
    spot_min_notional: Decimal | None
    effective_min_notional: Decimal | None
    futures_step_size: Decimal | None
    spot_step_size: Decimal | None
    coarser_step_size: Decimal | None


def _to_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(value)


def _filter_by_type(filters: list[dict[str, Any]], filter_type: str) -> dict[str, Any] | None:
    for f in filters:
        if f.get("filterType") == filter_type:
            return f
    return None


def parse_leg_rules(filters: list[dict[str, Any]] | None) -> TradingRules:
    """Parse LOT_SIZE/MARKET_LOT_SIZE and MIN_NOTIONAL/NOTIONAL from filters."""
    if not filters:
        return TradingRules(min_notional=None, step_size=None)

    min_notional: Decimal | None = None
    for notional_type in ("MIN_NOTIONAL", "NOTIONAL"):
        filt = _filter_by_type(filters, notional_type)
        if filt is not None:
            min_notional = _to_decimal(filt.get("minNotional") or filt.get("notional"))
            if min_notional is not None:
                break

    step_size: Decimal | None = None
    for step_type in ("LOT_SIZE", "MARKET_LOT_SIZE"):
        filt = _filter_by_type(filters, step_type)
        if filt is not None:
            step = _to_decimal(filt.get("stepSize"))
            if step is not None:
                if step_size is None or step > step_size:
                    step_size = step

    return TradingRules(min_notional=min_notional, step_size=step_size)


def coarser_step(a: Decimal | None, b: Decimal | None) -> Decimal | None:
    """Return the coarser (larger) step size across legs."""
    if a is None:
        return b
    if b is None:
        return a
    return max(a, b)


def stricter_min_notional(a: Decimal | None, b: Decimal | None) -> Decimal | None:
    """Return the stricter (max) min notional across legs."""
    if a is None:
        return b
    if b is None:
        return a
    return max(a, b)


def compute_effective_rules(
    futures_filters: list[dict[str, Any]],
    spot_filters: list[dict[str, Any]] | None,
) -> EffectiveTradingRules:
    """Compute effective min notional and coarser step across legs."""
    futures = parse_leg_rules(futures_filters)
    spot = parse_leg_rules(spot_filters)

    return EffectiveTradingRules(
        futures_min_notional=futures.min_notional,
        spot_min_notional=spot.min_notional,
        effective_min_notional=stricter_min_notional(
            futures.min_notional, spot.min_notional
        ),
        futures_step_size=futures.step_size,
        spot_step_size=spot.step_size,
        coarser_step_size=coarser_step(futures.step_size, spot.step_size),
    )