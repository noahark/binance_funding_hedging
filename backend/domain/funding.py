"""Funding field normalization and staleness guard."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

FundingSignalStatus = Literal["CURRENT_ACTIONABLE", "STALE_OR_PREVIOUS_PERIOD"]

FUNDING_FIELD_SEMANTICS: dict[str, str] = {
    "lastFundingRate": (
        "most recently updated funding rate (not a guaranteed prediction of "
        "the upcoming settlement)"
    ),
    "nextFundingTime": "next funding settlement time, epoch ms",
    "docs_citation": (
        "Binance API docs: dapi/v1/premiumIndex field descriptions "
        "(lastFundingRate, nextFundingTime)"
    ),
}


@dataclass(frozen=True)
class FundingSnapshot:
    """Normalized funding fields for a single symbol."""

    current_funding_rate: Decimal | None
    next_funding_time: int | None
    funding_history_summary: dict[str, str]
    funding_signal_status: FundingSignalStatus


def _to_decimal(value: str | int | float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def normalize_premium_index_entry(
    entry: dict[str, Any],
    data_timestamp: int,
) -> FundingSnapshot:
    """Normalize premiumIndex fields and apply staleness guard."""
    rate = _to_decimal(entry.get("lastFundingRate"))
    next_time_raw = entry.get("nextFundingTime")
    next_time = int(next_time_raw) if next_time_raw is not None else None

    if next_time is not None and next_time <= data_timestamp:
        signal_status: FundingSignalStatus = "STALE_OR_PREVIOUS_PERIOD"
    else:
        signal_status = "CURRENT_ACTIONABLE"

    return FundingSnapshot(
        current_funding_rate=rate,
        next_funding_time=next_time,
        funding_history_summary={},
        funding_signal_status=signal_status,
    )


def summarize_funding_history(
    history: list[dict[str, Any]],
) -> dict[str, str]:
    """Summarize fundingRate history as Decimal strings."""
    rates: list[Decimal] = []
    for entry in history:
        rate = _to_decimal(entry.get("fundingRate"))
        if rate is not None:
            rates.append(rate)

    if not rates:
        return {}

    total = sum(rates, Decimal("0"))
    count = Decimal(len(rates))
    avg = total / count
    return {
        "recent_avg": str(avg),
        "recent_min": str(min(rates)),
        "recent_max": str(max(rates)),
        "sample_count": str(count),
    }


def get_funding_field_semantics() -> dict[str, str]:
    """Return the funding field semantics descriptor."""
    return dict(FUNDING_FIELD_SEMANTICS)