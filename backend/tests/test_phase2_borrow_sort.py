"""Phase 2 tests: fundingInfo daily-rate + row sort + borrow_validation.

Covers 10-design §3.3 (daily-rate vectors), §1.2 (deterministic total order),
§1.3 (three-state borrow_validation), §3.4 (bounded portfolio set), and §3.5
(schema v0.2 validation, disabled-channel degradation, offline 8h default, and
v0.1-fixture backward compatibility). The §3.2 security-gate negative tests live
in ``test_private_client.py``.
"""
from __future__ import annotations

from decimal import Decimal

import jsonschema
import pytest

from backend.config import Config
from backend.domain.snapshot import (
    assemble_borrow_validation,
    build_rows,
    compute_daily_funding_rate,
    sort_rows,
)
from backend.services.snapshot_service import SnapshotService

ELIGIBLE = ("PERPETUAL", "TRADIFI_PERPETUAL")


def _eligible(futures):
    return [
        s for s in futures["symbols"] if s["status"] == "TRADING" and s["contractType"] in ELIGIBLE
    ]


def _row(sym, daily, base=None):
    return {"symbol": sym, "base_asset": base or sym.replace("USDT", ""), "daily_funding_rate": daily}


# --- §3.3 daily-rate vectors (10-design table) ---
@pytest.mark.parametrize(
    "rate,interval,expected",
    [
        ("0.00010000", 8, "0.00030000"),
        ("0.00010000", 4, "0.00060000"),
        ("-0.00005000", 4, "-0.00030000"),
        ("0.00002000", 1, "0.00048000"),
        ("-0.00000000", 8, "0.00000000"),  # negative-zero normalization
        ("", 8, None),
        (None, 8, None),
    ],
)
def test_daily_funding_rate_vectors(rate, interval, expected):
    assert compute_daily_funding_rate(rate, interval) == expected


def test_daily_funding_rate_no_float_no_scientific():
    out = compute_daily_funding_rate("0.00002000", 1)
    assert out == "0.00048000"
    assert "e" not in out.lower()
    # A tiny rate that would render in scientific notation if a float ever touched it.
    assert compute_daily_funding_rate("0.00000001", 8) == "0.00000003"
    assert compute_daily_funding_rate("0.00000001", 4) == "0.00000006"


def test_daily_funding_rate_bad_input_is_none():
    assert compute_daily_funding_rate("not-a-number", 8) is None
    assert compute_daily_funding_rate("0.0001", 0) is None  # non-positive interval
    assert compute_daily_funding_rate("0.0001", -4) is None


# --- §1.2 deterministic total order ---
def test_sort_abs_daily_desc_nulls_last_symbol_tiebreak():
    rows = [
        _row("DUSDT", None),           # null -> last
        _row("CUSDT", "-0.00030000"),  # abs 0.0003
        _row("AUSDT", "0.00060000"),   # abs 0.0006 (highest)
        _row("BUSDT", "0.00060000"),   # abs 0.0006, tie -> symbol ASC (B after A)
        _row("EUSDT", "0.00030000"),   # abs 0.0003, tie with C -> symbol ASC (E after C)
    ]
    assert [r["symbol"] for r in sort_rows(rows)] == ["AUSDT", "BUSDT", "CUSDT", "EUSDT", "DUSDT"]


def test_sort_single_period_lower_but_daily_higher_ranks_first():
    # 10-design §4.3 fixture invariant: A's single-period rate is lower than B's,
    # but A's daily rate is higher (shorter interval) -> A ranks first.
    rows = [
        _row("BUSDT", "0.00045000"),  # 0.00015 x3
        _row("AUSDT", "0.00060000"),  # 0.00010 x6 -> higher daily
    ]
    assert sort_rows(rows)[0]["symbol"] == "AUSDT"


def test_sort_all_null_keeps_symbol_asc():
    rows = [_row("ZUSDT", None), _row("AUSDT", None), _row("MUSDT", None)]
    assert [r["symbol"] for r in sort_rows(rows)] == ["AUSDT", "MUSDT", "ZUSDT"]


def test_sort_does_not_mutate_input():
    rows = [_row("BUSDT", "0.0001"), _row("AUSDT", "0.0009")]
    original = [r["symbol"] for r in rows]
    sort_rows(rows)
    assert [r["symbol"] for r in rows] == original  # returns a new list


# --- §1.3 three-state borrow_validation semantics ---
_CLASSIC_LISTED = {
    "pair_listed_by_symbol": {"BTCUSDT": True, "ETHUSDT": False},
    "asset_borrowable_by_name": {"BTC": True},
    "daily_interest_vip0_by_coin": {"BTC": "0.0005"},
}


def test_borrow_validation_disabled_state():
    bv = assemble_borrow_validation(
        {"symbol": "BTCUSDT", "base_asset": "BTC"}, None, {}, None, "private_channel_disabled"
    )
    assert bv["verified"] is False
    assert bv["classic_margin"]["pair_listed"] is None
    assert bv["classic_margin"]["asset_borrowable"] is None
    assert bv["classic_margin"]["daily_interest_vip0"] is None
    assert bv["portfolio_account"]["max_borrowable"] is None
    assert bv["portfolio_account"]["borrow_limit"] is None
    assert bv["checked_at"] is None
    assert bv["error"] == "private_channel_disabled"
    assert bv["classic_margin"]["source"] == "sapi_reference"
    assert bv["portfolio_account"]["source"] == "papi_max_borrowable"


def test_borrow_validation_verified_not_listed_data_null():
    bv = assemble_borrow_validation(
        {"symbol": "ETHUSDT", "base_asset": "ETH"}, _CLASSIC_LISTED, {}, "2026-07-04T13:00:00Z", None
    )
    assert bv["verified"] is True
    assert bv["classic_margin"]["pair_listed"] is False
    # pair not listed -> asset/interest null even though other coins have data
    assert bv["classic_margin"]["asset_borrowable"] is None
    assert bv["classic_margin"]["daily_interest_vip0"] is None
    assert bv["checked_at"] == "2026-07-04T13:00:00Z"
    assert bv["error"] is None


def test_borrow_validation_verified_listed_carries_data():
    bv = assemble_borrow_validation(
        {"symbol": "BTCUSDT", "base_asset": "BTC"}, _CLASSIC_LISTED, {}, "2026-07-04T13:00:00Z", None
    )
    assert bv["verified"] is True
    assert bv["classic_margin"]["pair_listed"] is True
    assert bv["classic_margin"]["asset_borrowable"] is True
    assert bv["classic_margin"]["daily_interest_vip0"] == "0.0005"


def test_borrow_validation_portfolio_bounded_only():
    portfolio = {"BTC": {"max_borrowable": "1.5", "borrow_limit": "60"}}
    btc = assemble_borrow_validation(
        {"symbol": "BTCUSDT", "base_asset": "BTC"}, _CLASSIC_LISTED, portfolio, "t", None
    )
    eth = assemble_borrow_validation(
        {"symbol": "ETHUSDT", "base_asset": "ETH"}, _CLASSIC_LISTED, portfolio, "t", None
    )
    assert btc["portfolio_account"]["max_borrowable"] == "1.5"
    assert btc["portfolio_account"]["borrow_limit"] == "60"
    # ETH is outside the bounded set -> null amounts, block still present
    assert eth["portfolio_account"]["max_borrowable"] is None
    assert eth["portfolio_account"]["borrow_limit"] is None
    assert eth["portfolio_account"]["source"] == "papi_max_borrowable"


def test_borrow_validation_portfolio_failed_endpoint_null_amounts():
    # bounded candidate whose maxBorrowable call failed -> None amounts recorded
    portfolio = {"BTC": {"max_borrowable": None, "borrow_limit": None}}
    bv = assemble_borrow_validation(
        {"symbol": "BTCUSDT", "base_asset": "BTC"}, _CLASSIC_LISTED, portfolio, "t", None
    )
    assert bv["verified"] is True
    assert bv["portfolio_account"]["max_borrowable"] is None
    assert bv["portfolio_account"]["borrow_limit"] is None


def test_borrow_validation_each_state_validates_in_full_snapshot(schema):
    # borrow_validation always lives inside a row, so validate each state through
    # a full snapshot (not the isolated $def, whose $ref to $defs/decimal_string
    # only resolves under the root schema).
    snap = SnapshotService(Config(offline=True)).build_snapshot()
    rows = snap["rows"]
    # state 1 (disabled) is the offline default -> snapshot already valid.
    jsonschema.validate(snap, schema)

    # state 3: verified, listed + bounded portfolio on a known symbol.
    btc = next((r for r in rows if r["symbol"] == "BTCUSDT"), rows[0])
    listed = {
        "pair_listed_by_symbol": {btc["symbol"]: True},
        "asset_borrowable_by_name": {btc["base_asset"]: True},
        "daily_interest_vip0_by_coin": {btc["base_asset"]: "0.0005"},
    }
    btc["borrow_validation"] = assemble_borrow_validation(
        btc, listed, {btc["base_asset"]: {"max_borrowable": "1.5", "borrow_limit": "60"}}, "t", None
    )

    # state 2: verified, not listed on a different row.
    other = next((r for r in rows if r is not btc), None)
    if other is not None:
        not_listed = {
            "pair_listed_by_symbol": {other["symbol"]: False},
            "asset_borrowable_by_name": {},
            "daily_interest_vip0_by_coin": {},
        }
        other["borrow_validation"] = assemble_borrow_validation(other, not_listed, {}, "t", None)

    jsonschema.validate(snap, schema)


# --- schema v0.2 validates a full Phase-2 snapshot (offline) ---
def test_offline_full_snapshot_validates_v02_schema(schema):
    snap = SnapshotService(Config(offline=True)).build_snapshot()
    jsonschema.validate(snap, schema)
    assert snap["private_channel"] == "disabled"
    assert snap["rows"]
    for r in snap["rows"]:
        assert r["funding_interval_hours"] in (1, 4, 8)
        assert isinstance(r["daily_funding_rate"], (str, type(None)))
        bv = r["borrow_validation"]
        assert set(bv) == {"verified", "classic_margin", "portfolio_account", "checked_at", "error"}
        assert set(bv["classic_margin"]) == {
            "pair_listed",
            "asset_borrowable",
            "daily_interest_vip0",
            "source",
        }
        assert set(bv["portfolio_account"]) == {"max_borrowable", "borrow_limit", "source"}


def test_offline_private_channel_disabled_all_rows_verified_false():
    snap = SnapshotService(Config(offline=True)).build_snapshot()
    assert snap["private_channel"] == "disabled"
    for r in snap["rows"]:
        bv = r["borrow_validation"]
        assert bv["verified"] is False
        assert bv["classic_margin"]["pair_listed"] is None
        assert bv["portfolio_account"]["max_borrowable"] is None
        assert bv["checked_at"] is None
        assert bv["error"] == "private_channel_disabled"


def test_offline_build_rows_defaults_8h_without_funding_info(raw_inputs):
    # The offline raw dir has no fundingInfo sample -> every row defaults to 8h.
    elig = _eligible(raw_inputs["futures"])
    premium = {p["symbol"]: p for p in raw_inputs["premium"]}
    spot = {s["symbol"]: s for s in raw_inputs["spot"]["symbols"]}
    rows = build_rows(elig, premium, spot, raw_inputs["funding"])  # no interval map
    assert rows
    assert all(r["funding_interval_hours"] == 8 for r in rows)
    assert all(isinstance(r["daily_funding_rate"], (str, type(None))) for r in rows)


def test_offline_snapshot_rows_sorted_abs_daily_desc_nulls_last():
    snap = SnapshotService(Config(offline=True)).build_snapshot()
    daily = [r["daily_funding_rate"] for r in snap["rows"]]

    def absv(d):
        return None if d is None else abs(Decimal(d))

    absvals = [absv(d) for d in daily]
    non_null = [a for a in absvals if a is not None]
    # non-null prefix is non-increasing (abs daily DESC)
    assert all(non_null[i] >= non_null[i + 1] for i in range(len(non_null) - 1))
    # nulls (if any) are all after the non-null prefix
    if None in absvals:
        first_null = absvals.index(None)
        assert all(a is None for a in absvals[first_null:])


def test_offline_get_snapshot_no_private_http_and_cached(schema):
    # Offline private channel is disabled in __init__, so no signed HTTP fires;
    # the public client also performs no HTTP offline. Snapshot is cached.
    service = SnapshotService(Config(offline=True, cache_ttl_seconds=60))
    first = service.get_snapshot()
    second = service.get_snapshot()
    assert first is second
    assert service.request_log() == {}
    jsonschema.validate(first, schema)


# --- v0.1 frozen fixture stays valid under v0.2 schema (additive amendment) ---
def test_frozen_v01_normalized_validates_under_v02_schema(schema, frozen_normalized):
    # The v0.1 fixture has none of the v0.2 fields; they are all optional, so it
    # must still validate. Locks the additive-only / backward-compatible guarantee.
    jsonschema.validate(frozen_normalized, schema)
