"""Negative schema tests: tampered rows/snapshots must be rejected.

Mirrors the contract-stage negative-test approach (10 documented mutations),
now packaged as a committed replay script so the rejection is reproducible.
"""
from __future__ import annotations

import copy

import jsonschema
import pytest

BASE_ROW = {
    "symbol": "BTCUSDT",
    "base_asset": "BTC",
    "quote_asset": "USDT",
    "asset_tag": "CRYPTO",
    "asset_tag_source": "futures_contractType_perpetual",
    "asset_tag_confidence": "HIGH",
    "route_class": "MARGIN_SPOT_CANDIDATE",
    "positive_funding_enabled": True,
    "negative_funding_status": "PRIVATE_BORROW_VALIDATION_REQUIRED",
    "futures": {
        "symbol": "BTCUSDT",
        "status": "TRADING",
        "contract_type": "PERPETUAL",
        "mark_price": "60000",
        "index_price": "60001",
        "last_funding_rate": "0.0001",
        "next_funding_time": 1,
        "min_notional": "5",
        "step_size": "0.001",
    },
    "spot": {
        "symbol": "BTCUSDT",
        "status": "TRADING",
        "exists": True,
        "min_notional": "5",
        "step_size": "0.001",
    },
    "margin_public": {"public_cross_margin_pair": None, "source": "unverified"},
    "funding_history": [],
    "ui_flags": [],
}


def _snapshot_with(row):
    return {
        "schema_version": "public-market-snapshot/v1",
        "generated_at": "2026-07-03T00:00:00Z",
        "data_time": "2026-07-03T00:00:00Z",
        "source_sample_id": "negative-test",
        "summary": {
            "total_rows": 1,
            "route_counts": {"MARGIN_SPOT_CANDIDATE": 1},
            "asset_tag_counts": {"CRYPTO": 1},
            "negative_funding_status_counts": {"PRIVATE_BORROW_VALIDATION_REQUIRED": 1},
        },
        "rows": [row],
        "warnings": [],
    }


def _expect_rejected(schema, mutate):
    row = copy.deepcopy(BASE_ROW)
    mutate(row)
    snap = _snapshot_with(row)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(snap, schema)


def test_base_row_is_valid(schema):
    jsonschema.validate(_snapshot_with(copy.deepcopy(BASE_ROW)), schema)


def test_reject_wrong_quote_asset(schema):
    _expect_rejected(schema, lambda r: r.__setitem__("quote_asset", "BUSD"))


def test_reject_invalid_asset_tag(schema):
    _expect_rejected(schema, lambda r: r.__setitem__("asset_tag", "STOCK"))


def test_reject_invalid_route_class(schema):
    _expect_rejected(schema, lambda r: r.__setitem__("route_class", "WHATEVER"))


def test_reject_invalid_negative_status(schema):
    _expect_rejected(schema, lambda r: r.__setitem__("negative_funding_status", "OK"))


def test_reject_float_mark_price(schema):
    _expect_rejected(schema, lambda r: r["futures"].__setitem__("mark_price", 1.5))


def test_reject_float_funding_rate(schema):
    _expect_rejected(schema, lambda r: r["futures"].__setitem__("last_funding_rate", 0.0001))


def test_reject_non_numeric_decimal_string(schema):
    _expect_rejected(schema, lambda r: r["futures"].__setitem__("index_price", "abc"))


def test_reject_negative_next_funding_time(schema):
    _expect_rejected(schema, lambda r: r["futures"].__setitem__("next_funding_time", -1))


def test_reject_missing_required_field(schema):
    def mutate(r):
        del r["futures"]["step_size"]

    _expect_rejected(schema, mutate)


def test_reject_extra_property(schema):
    _expect_rejected(schema, lambda r: r["futures"].__setitem__("unexpected", "x"))
