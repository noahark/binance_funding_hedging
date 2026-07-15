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
        "match_type": "exact_symbol",
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


def test_reject_invalid_match_type(schema):
    _expect_rejected(schema, lambda r: r["spot"].__setitem__("match_type", "whatever"))


def test_match_type_null_is_valid(schema):
    # match_type is nullable: a row with no spot leg legitimately carries null.
    row = copy.deepcopy(BASE_ROW)
    row["spot"]["exists"] = False
    row["spot"]["symbol"] = None
    row["spot"]["status"] = None
    row["spot"]["match_type"] = None
    jsonschema.validate(_snapshot_with(row), schema)  # must NOT raise


# =========================================================================
# Stage 2026-07-bookticker-open-columns-v1: opening_quotes is additive. A row
# may omit the whole object (legacy compatibility) or carry a complete object;
# the nested object is closed (additionalProperties: false) and every price/
# spread is decimal-string-or-null (a JSON number must be rejected).
# =========================================================================
_FULL_OPENING_QUOTES = {
    "status": "fresh",
    "updated_at": "2026-07-15T06:51:57Z",
    "spot_bid_price": "100.00",
    "spot_ask_price": "100.01",
    "futures_bid_price": "99.00",
    "futures_ask_price": "99.01",
    "forward_spread_pct": "-1.01",
    "reverse_spread_pct": "1.01",
}


def test_opening_quotes_omitted_is_legacy_compatible(schema):
    # Additive: BASE_ROW (no opening_quotes) still validates.
    jsonschema.validate(_snapshot_with(copy.deepcopy(BASE_ROW)), schema)


def test_opening_quotes_full_object_is_valid(schema):
    row = copy.deepcopy(BASE_ROW)
    row["opening_quotes"] = copy.deepcopy(_FULL_OPENING_QUOTES)
    jsonschema.validate(_snapshot_with(row), schema)


def test_opening_quotes_unavailable_all_null_is_valid(schema):
    row = copy.deepcopy(BASE_ROW)
    row["opening_quotes"] = {
        "status": "unavailable", "updated_at": None,
        "spot_bid_price": None, "spot_ask_price": None,
        "futures_bid_price": None, "futures_ask_price": None,
        "forward_spread_pct": None, "reverse_spread_pct": None,
    }
    jsonschema.validate(_snapshot_with(row), schema)


def test_reject_opening_quotes_unknown_nested_property(schema):
    def mutate(r):
        r["opening_quotes"] = {**_FULL_OPENING_QUOTES, "surprise": "x"}
    _expect_rejected(schema, mutate)


def test_reject_opening_quotes_number_price(schema):
    # prices are decimal_string | null; a JSON number must be rejected (the
    # adapter already drops number-typed raw prices, but the wire contract must
    # also refuse them).
    def mutate(r):
        r["opening_quotes"] = {**_FULL_OPENING_QUOTES, "spot_bid_price": 100.0}
    _expect_rejected(schema, mutate)


def test_reject_opening_quotes_number_spread(schema):
    def mutate(r):
        r["opening_quotes"] = {**_FULL_OPENING_QUOTES, "forward_spread_pct": -0.04}
    _expect_rejected(schema, mutate)


def test_reject_opening_quotes_invalid_status(schema):
    def mutate(r):
        r["opening_quotes"] = {**_FULL_OPENING_QUOTES, "status": "old"}
    _expect_rejected(schema, mutate)


def test_reject_opening_quotes_missing_required_field(schema):
    def mutate(r):
        r["opening_quotes"] = {k: v for k, v in _FULL_OPENING_QUOTES.items()
                               if k != "reverse_spread_pct"}
    _expect_rejected(schema, mutate)
