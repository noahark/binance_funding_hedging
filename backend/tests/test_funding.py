"""Tests for funding normalization and staleness guard."""

from __future__ import annotations

from decimal import Decimal

from backend.domain.funding import (
    get_funding_field_semantics,
    normalize_premium_index_entry,
    summarize_funding_history,
)


def test_normalize_current_actionable() -> None:
    entry = {"lastFundingRate": "0.00031200", "nextFundingTime": 1700003600000}
    snap = normalize_premium_index_entry(entry, data_timestamp=1700000000000)
    assert snap.current_funding_rate == Decimal("0.00031200")
    assert snap.next_funding_time == 1700003600000
    assert snap.funding_signal_status == "CURRENT_ACTIONABLE"


def test_stale_funding_when_next_time_before_data_timestamp() -> None:
    entry = {"lastFundingRate": "0.00020000", "nextFundingTime": 1699999000000}
    snap = normalize_premium_index_entry(entry, data_timestamp=1700000000000)
    assert snap.funding_signal_status == "STALE_OR_PREVIOUS_PERIOD"


def test_summarize_funding_history_decimal_strings() -> None:
    history = [
        {"fundingRate": "0.00030000"},
        {"fundingRate": "0.00031200"},
        {"fundingRate": "0.00029000"},
    ]
    summary = summarize_funding_history(history)
    assert summary["recent_avg"] == str(
        (Decimal("0.00030000") + Decimal("0.00031200") + Decimal("0.00029000")) / 3
    )
    assert summary["recent_min"] == "0.00029000"
    assert summary["recent_max"] == "0.00031200"


def test_funding_field_semantics_descriptor() -> None:
    semantics = get_funding_field_semantics()
    assert "lastFundingRate" in semantics
    assert "nextFundingTime" in semantics
    assert "most recently updated" in semantics["lastFundingRate"]