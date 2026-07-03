"""Replay determinism: regenerate classification from committed fixtures."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from backend.services.public_market_discovery import discover_from_samples

FIXTURES = Path(__file__).parent / "fixtures"


def test_regenerate_classification_deterministic() -> None:
    first = discover_from_samples(FIXTURES)
    second = discover_from_samples(FIXTURES)
    assert first == second


def test_fixture_route_classes() -> None:
    output = discover_from_samples(FIXTURES)
    by_symbol = {r["symbol"]: r for r in output["candidates"]}

    assert by_symbol["BTCUSDT"]["route_class"] == "MARGIN_SPOT_CANDIDATE"
    assert by_symbol["SPOTONLYUSDT"]["route_class"] == "SPOT_ONLY_CANDIDATE"
    assert by_symbol["PERPONLYUSDT"]["route_class"] == "PERP_ONLY_EXCLUDED"
    assert by_symbol["TSLAUSDT"]["asset_tag"] == "BSTOCK"
    assert by_symbol["STALEUSDT"]["funding_signal_status"] == "STALE_OR_PREVIOUS_PERIOD"


def test_serialization_guard_numeric_fields_are_strings() -> None:
    output = discover_from_samples(FIXTURES)
    numeric_fields = (
        "current_funding_rate",
        "next_funding_time",
        "futures_min_notional",
        "spot_min_notional",
        "effective_min_notional",
        "futures_step_size",
        "spot_step_size",
        "data_timestamp",
    )
    for row in output["candidates"]:
        for field in numeric_fields:
            value = row.get(field)
            if value is not None:
                assert isinstance(value, str), f"{row['symbol']}.{field} not str"
                Decimal(value)
        for key, val in row.get("funding_history_summary", {}).items():
            assert isinstance(val, str), f"{row['symbol']}.funding_history_summary.{key}"
            Decimal(val)

    assert isinstance(output["data_timestamp"], str)
    serialized = json.dumps(output)
    roundtrip = json.loads(serialized)
    assert roundtrip == output