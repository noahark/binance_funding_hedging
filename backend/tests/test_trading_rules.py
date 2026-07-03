"""Tests for trading rule parsing."""

from __future__ import annotations

from decimal import Decimal

from backend.domain.trading_rules import (
    compute_effective_rules,
    parse_leg_rules,
)


def test_parse_lot_size_and_min_notional() -> None:
    filters = [
        {"filterType": "LOT_SIZE", "stepSize": "0.001"},
        {"filterType": "MIN_NOTIONAL", "notional": "100"},
    ]
    rules = parse_leg_rules(filters)
    assert rules.step_size == Decimal("0.001")
    assert rules.min_notional == Decimal("100")


def test_parse_notional_filter() -> None:
    filters = [{"filterType": "NOTIONAL", "minNotional": "5"}]
    rules = parse_leg_rules(filters)
    assert rules.min_notional == Decimal("5")


def test_missing_filters_return_null() -> None:
    rules = parse_leg_rules([])
    assert rules.min_notional is None
    assert rules.step_size is None


def test_effective_rules_stricter_notional_coarser_step() -> None:
    futures_filters = [
        {"filterType": "LOT_SIZE", "stepSize": "0.001"},
        {"filterType": "MIN_NOTIONAL", "notional": "100"},
    ]
    spot_filters = [
        {"filterType": "LOT_SIZE", "stepSize": "0.01"},
        {"filterType": "NOTIONAL", "minNotional": "50"},
    ]
    effective = compute_effective_rules(futures_filters, spot_filters)
    assert effective.effective_min_notional == Decimal("100")
    assert effective.coarser_step_size == Decimal("0.01")
    assert effective.futures_step_size == Decimal("0.001")
    assert effective.spot_step_size == Decimal("0.01")


def test_spot_only_leg_null() -> None:
    futures_filters = [{"filterType": "MIN_NOTIONAL", "notional": "10"}]
    effective = compute_effective_rules(futures_filters, None)
    assert effective.spot_min_notional is None
    assert effective.effective_min_notional == Decimal("10")