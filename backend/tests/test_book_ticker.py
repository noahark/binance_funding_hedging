"""Paired bookTicker adapter, opening-spread formulas, and row join tests
(2026-07-bookticker-open-columns-v1, 10-design §D1/§D3/§D4/§D5/§D6, breakdown §8).

Pure and offline-only: the live adapter seam is exercised by monkeypatching
``_http_get``; the spread helpers and ``build_opening_quotes`` truth table are
pure Decimal functions; the row join is exercised via the service
``_attach_opening_quotes`` projection against a seeded pair cache.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pytest

from backend.adapters.binance_public import BinancePublicClient, _normalize_book_ticker
from backend.config import Config
from backend.domain.snapshot import build_opening_quotes, compute_opening_spread_pct
from backend.services import snapshot_service
from backend.services.snapshot_service import SnapshotService

REPO_ROOT = Path(__file__).resolve().parents[2]

# Frozen deterministic BTC vector (10-design §D6, breakdown §6): the design
# grounds these in normalized/bookticker-summary.json btc_cross_market.
SPOT_BID = "64954.00000000"
SPOT_ASK = "64954.01000000"
FUT_BID = "64925.00"
FUT_ASK = "64925.10"

NULL_PRICE_KEYS = (
    "spot_bid_price",
    "spot_ask_price",
    "futures_bid_price",
    "futures_ask_price",
    "forward_spread_pct",
    "reverse_spread_pct",
)


def _expected_spread(bid, ask) -> str:
    """Oracle: the SAME Decimal expression the implementation uses, so rounding
    cannot drift (breakdown P2-1). Never float, never hand-computed strings."""
    q = (
        (Decimal(str(bid)) - Decimal(str(ask)))
        / Decimal(str(ask))
        * Decimal(100)
    ).quantize(Decimal("0.01"), ROUND_HALF_UP)
    if q == 0:
        q = Decimal("0.00")
    return format(q, "f")


def _client() -> BinancePublicClient:
    return BinancePublicClient(
        offline=False,
        offline_dir=REPO_ROOT / "backend/tests/fixtures",
        futures_base_url="https://fapi.binance.com",
        spot_base_url="https://api.binance.com",
        user_agent="test/1.0",
        timeout=5,
    )


# =========================================================================
# Adapter: paired full bookTicker seam
# =========================================================================
def test_fetch_pair_correct_urls_no_params_and_request_log(monkeypatch):
    client = _client()
    urls = []
    spot = [{"symbol": "BTCUSDT", "bidPrice": SPOT_BID, "bidQty": "1",
             "askPrice": SPOT_ASK, "askQty": "2"}]
    fut = [{"symbol": "BTCUSDT", "bidPrice": FUT_BID, "bidQty": "1",
            "askPrice": FUT_ASK, "askQty": "2", "time": 1, "lastUpdateId": 1}]

    def fake_get(url):
        urls.append(url)
        return spot if "/api/v3/" in url else fut

    monkeypatch.setattr(client, "_http_get", fake_get)
    pair = client.fetch_book_ticker_pair()

    # full (no query string), separate real-URL request-log keys
    assert urls == [
        "https://api.binance.com/api/v3/ticker/bookTicker",
        "https://fapi.binance.com/fapi/v1/ticker/bookTicker",
    ]
    assert client.request_log["GET /api/v3/ticker/bookTicker"] == 1
    assert client.request_log["GET /fapi/v1/ticker/bookTicker"] == 1
    # qty / time / lastUpdateId do NOT enter the contract; prices stay strings
    assert pair == {
        "spot": {"BTCUSDT": {"bid_price": SPOT_BID, "ask_price": SPOT_ASK}},
        "futures": {"BTCUSDT": {"bid_price": FUT_BID, "ask_price": FUT_ASK}},
    }


def test_offline_pair_returns_none():
    client = BinancePublicClient(
        offline=True,
        offline_dir=REPO_ROOT / "backend/tests/fixtures",
        futures_base_url="https://fapi.binance.com",
        spot_base_url="https://api.binance.com",
        user_agent="test/1.0",
        timeout=5,
    )
    assert client.fetch_book_ticker_pair() is None


# =========================================================================
# Adapter normalization: string discipline + shape rejection
# =========================================================================
def test_normalize_preserves_string_prices_only():
    out = _normalize_book_ticker([
        {"symbol": "BTCUSDT", "bidPrice": SPOT_BID, "askPrice": SPOT_ASK},
        {"symbol": "ETHUSDT", "bidPrice": "3000.00", "askPrice": "3001.00"},
    ])
    assert out == {
        "BTCUSDT": {"bid_price": SPOT_BID, "ask_price": SPOT_ASK},
        "ETHUSDT": {"bid_price": "3000.00", "ask_price": "3001.00"},
    }


def test_normalize_rejects_number_price_no_str_coercion():
    # A JSON-number price must NOT be str()-coerced into a computable price.
    out = _normalize_book_ticker([
        {"symbol": "A", "bidPrice": "1", "askPrice": "2"},      # valid
        {"symbol": "B", "bidPrice": 1, "askPrice": "2"},         # number bid -> dropped
        {"symbol": "C", "bidPrice": "1", "askPrice": 2},         # number ask -> dropped
        {"symbol": "D", "bidPrice": 1.5, "askPrice": 2.5},       # both number -> dropped
    ])
    assert out == {"A": {"bid_price": "1", "ask_price": "2"}}


def test_normalize_skips_non_dict_and_missing_symbol():
    out = _normalize_book_ticker([
        "not-a-dict",
        {"bidPrice": "1", "askPrice": "2"},          # no symbol
        {"symbol": 123, "bidPrice": "1", "askPrice": "2"},  # non-string symbol
        {"symbol": "", "bidPrice": "1", "askPrice": "2"},   # empty symbol
        {"symbol": "OK", "bidPrice": "1", "askPrice": "2"},
    ])
    assert out == {"OK": {"bid_price": "1", "ask_price": "2"}}


def test_normalize_rejects_non_list_and_empty_list():
    with pytest.raises(ValueError):
        _normalize_book_ticker({"symbol": "X"})  # dict, not list
    with pytest.raises(ValueError):
        _normalize_book_ticker([])
    with pytest.raises(ValueError):
        _normalize_book_ticker(None)


def test_fetch_pair_raises_when_normalized_map_is_empty(monkeypatch):
    # All spot rows carry number prices -> dropped -> empty spot map -> the pair
    # fails atomically (no partial commit), surfacing as a ValueError the
    # service treats as a non-cacheable failure.
    client = _client()
    spot = [{"symbol": "BTCUSDT", "bidPrice": 1, "askPrice": 2}]
    fut = [{"symbol": "BTCUSDT", "bidPrice": "1", "askPrice": "1"}]
    monkeypatch.setattr(
        client, "_http_get", lambda url: spot if "/api/v3/" in url else fut
    )
    with pytest.raises(ValueError):
        client.fetch_book_ticker_pair()


def test_fetch_pair_propagates_second_endpoint_failure(monkeypatch):
    # Spot succeeds (bumped); futures raises -> the whole pair fails, no result.
    client = _client()
    spot = [{"symbol": "BTCUSDT", "bidPrice": "1", "askPrice": "1"}]

    def fake_get(url):
        if "/fapi/" in url:
            raise OSError("futures upstream down")
        return spot

    monkeypatch.setattr(client, "_http_get", fake_get)
    with pytest.raises(OSError):
        client.fetch_book_ticker_pair()
    # both endpoints were still attempted (each bumps its own request-log key)
    assert client.request_log["GET /api/v3/ticker/bookTicker"] == 1
    assert client.request_log["GET /fapi/v1/ticker/bookTicker"] == 1


# =========================================================================
# Pure spread formula: direction, HALF_UP, negative zero, invalid operands
# =========================================================================
def test_forward_and_reverse_btc_vector():
    # forward = (futures_bid - spot_ask) / spot_ask * 100
    assert compute_opening_spread_pct(FUT_BID, SPOT_ASK) == "-0.04"
    # reverse = (spot_bid - futures_ask) / futures_ask * 100
    assert compute_opening_spread_pct(SPOT_BID, FUT_ASK) == "0.04"
    # oracle: same Decimal expression, no drift
    assert compute_opening_spread_pct(FUT_BID, SPOT_ASK) == _expected_spread(FUT_BID, SPOT_ASK)
    assert compute_opening_spread_pct(SPOT_BID, FUT_ASK) == _expected_spread(SPOT_BID, FUT_ASK)


def test_half_up_carry_vector():
    # 1.005 must round UP to 1.01 (ROUND_HALF_UP), not down to 1.00.
    assert compute_opening_spread_pct("101.005", "100") == "1.01"


def test_equal_prices_normalize_negative_zero():
    assert compute_opening_spread_pct("100", "100") == "0.00"
    assert compute_opening_spread_pct("50.5", "50.5") == "0.00"


def test_invalid_or_zero_operand_returns_null():
    assert compute_opening_spread_pct(None, "100") is None
    assert compute_opening_spread_pct("100", None) is None
    assert compute_opening_spread_pct("", "100") is None
    assert compute_opening_spread_pct("100", "") is None
    assert compute_opening_spread_pct("abc", "100") is None
    assert compute_opening_spread_pct("100", "0.00000000") is None  # zero denominator
    assert compute_opening_spread_pct("0.00000000", "100") is None  # zero bid
    assert compute_opening_spread_pct("-5", "100") is None           # negative bid
    assert compute_opening_spread_pct("100", "-5") is None           # negative denominator


# =========================================================================
# build_opening_quotes truth table (10-design §D5, breakdown §7)
# =========================================================================
def _quotes(spot_bid=SPOT_BID, spot_ask=SPOT_ASK, fut_bid=FUT_BID, fut_ask=FUT_ASK):
    return (
        {"bid_price": spot_bid, "ask_price": spot_ask},
        {"bid_price": fut_bid, "ask_price": fut_ask},
    )


def test_unavailable_when_pair_never_succeeded():
    oq = build_opening_quotes(None, None, usable=False, updated_at=None)
    assert oq["status"] == "unavailable"
    assert oq["updated_at"] is None
    assert all(oq[k] is None for k in NULL_PRICE_KEYS)


def test_stale_retains_updated_at_blanks_prices_and_spreads():
    spot, fut = _quotes()
    oq = build_opening_quotes(spot, fut, usable=False, updated_at="2026-07-15T06:51:57Z")
    assert oq["status"] == "stale"
    assert oq["updated_at"] == "2026-07-15T06:51:57Z"
    assert all(oq[k] is None for k in NULL_PRICE_KEYS)


def test_fresh_all_four_valid():
    spot, fut = _quotes()
    oq = build_opening_quotes(spot, fut, usable=True, updated_at="2026-07-15T06:51:57Z")
    assert oq["status"] == "fresh"
    assert oq["updated_at"] == "2026-07-15T06:51:57Z"
    assert oq["spot_bid_price"] == SPOT_BID
    assert oq["spot_ask_price"] == SPOT_ASK
    assert oq["futures_bid_price"] == FUT_BID
    assert oq["futures_ask_price"] == FUT_ASK
    assert oq["forward_spread_pct"] == "-0.04"
    assert oq["reverse_spread_pct"] == "0.04"


def test_incomplete_forward_only_reverse_null():
    # forward needs futures_bid + spot_ask (both present); reverse needs
    # spot_bid + futures_ask (both absent) -> one direction does NOT blank the
    # other (breakdown §8 direction independence).
    spot = {"bid_price": None, "ask_price": SPOT_ASK}
    fut = {"bid_price": FUT_BID, "ask_price": None}
    oq = build_opening_quotes(spot, fut, usable=True, updated_at="t")
    assert oq["status"] == "incomplete"
    assert oq["forward_spread_pct"] == "-0.04"
    assert oq["reverse_spread_pct"] is None


def test_incomplete_reverse_only_forward_null():
    spot = {"bid_price": SPOT_BID, "ask_price": None}
    fut = {"bid_price": None, "ask_price": FUT_ASK}
    oq = build_opening_quotes(spot, fut, usable=True, updated_at="t")
    assert oq["status"] == "incomplete"
    assert oq["forward_spread_pct"] is None
    assert oq["reverse_spread_pct"] == "0.04"


def test_zero_price_is_incomplete_and_preserves_valid_prices():
    # "0.00000000" is missing liquidity, not a computable zero -> that price is
    # null and only the direction it gates is blanked.
    spot = {"bid_price": SPOT_BID, "ask_price": "0.00000000"}
    fut = {"bid_price": FUT_BID, "ask_price": FUT_ASK}
    oq = build_opening_quotes(spot, fut, usable=True, updated_at="t")
    assert oq["status"] == "incomplete"
    assert oq["spot_ask_price"] is None
    assert oq["forward_spread_pct"] is None      # gated by the zero spot_ask
    assert oq["reverse_spread_pct"] == "0.04"    # spot_bid + futures_ask still valid


def test_no_spot_leg_is_incomplete_but_keeps_futures_prices():
    oq = build_opening_quotes(None, {"bid_price": FUT_BID, "ask_price": FUT_ASK},
                              usable=True, updated_at="t")
    assert oq["status"] == "incomplete"
    assert oq["futures_bid_price"] == FUT_BID    # valid price preserved
    assert oq["futures_ask_price"] == FUT_ASK
    assert oq["spot_bid_price"] is None
    assert oq["forward_spread_pct"] is None
    assert oq["reverse_spread_pct"] is None


# =========================================================================
# Row join via service _attach_opening_quotes (10-design §D4): futures by
# row.futures.symbol, spot by the resolved row.spot.symbol (bStock alias),
# None spot leg -> incomplete without guessing a substitute asset.
# =========================================================================
def _service_with_pair(monkeypatch, now, pair_entry):
    monkeypatch.setattr(snapshot_service.time, "monotonic", lambda: now)
    service = SnapshotService(Config(offline=False))
    if pair_entry is not None:
        service._global_source_cache["book_ticker_pair"] = pair_entry
    return service


def _pair_entry(now, *, spot=None, futures=None, updated_at="2026-07-15T06:51:57Z"):
    return (
        now,
        {
            "updated_at": updated_at,
            "spot": spot or {"BTCUSDT": {"bid_price": SPOT_BID, "ask_price": SPOT_ASK}},
            "futures": futures or {"BTCUSDT": {"bid_price": FUT_BID, "ask_price": FUT_ASK}},
        },
    )


def test_join_exact_crypto_symbol(monkeypatch):
    rows = [{"futures": {"symbol": "BTCUSDT"}, "spot": {"symbol": "BTCUSDT"}}]
    service = _service_with_pair(monkeypatch, 100.0, _pair_entry(100.0))
    service._attach_opening_quotes(rows)
    oq = rows[0]["opening_quotes"]
    assert oq["status"] == "fresh"
    assert oq["forward_spread_pct"] == "-0.04"
    assert oq["reverse_spread_pct"] == "0.04"


def test_join_bstock_alias_uses_resolved_spot_symbol(monkeypatch):
    # futures TSLAUSDT joins futures map; the resolved spot leg TSLABUSDT (B-
    # suffix alias) joins the spot map. Joining spot by the futures symbol
    # would miss; joining by row.spot.symbol hits.
    rows = [{"futures": {"symbol": "TSLAUSDT"}, "spot": {"symbol": "TSLABUSDT"}}]
    pair = _pair_entry(
        100.0,
        spot={"TSLABUSDT": {"bid_price": "100.00", "ask_price": "100.10"}},
        futures={"TSLAUSDT": {"bid_price": "101.00", "ask_price": "101.10"}},
    )
    service = _service_with_pair(monkeypatch, 100.0, pair)
    service._attach_opening_quotes(rows)
    oq = rows[0]["opening_quotes"]
    assert oq["status"] == "fresh"
    assert oq["spot_bid_price"] == "100.00"
    assert oq["futures_bid_price"] == "101.00"
    # forward = (101.00 - 100.10)/100.10*100
    assert oq["forward_spread_pct"] == _expected_spread("101.00", "100.10")


def test_join_perp_only_no_spot_leg_is_incomplete(monkeypatch):
    # spot.symbol is None -> no spot quote; no substitute asset is guessed.
    rows = [{"futures": {"symbol": "XAUUSDT"}, "spot": {"symbol": None}}]
    pair = _pair_entry(
        100.0,
        spot={"PAXGUSDT": {"bid_price": "1", "ask_price": "1"}},  # must NOT be used
        futures={"XAUUSDT": {"bid_price": "1", "ask_price": "1"}},
    )
    service = _service_with_pair(monkeypatch, 100.0, pair)
    service._attach_opening_quotes(rows)
    oq = rows[0]["opening_quotes"]
    assert oq["status"] == "incomplete"
    assert oq["spot_bid_price"] is None
    assert oq["forward_spread_pct"] is None


def test_join_never_succeeded_is_unavailable(monkeypatch):
    rows = [{"futures": {"symbol": "BTCUSDT"}, "spot": {"symbol": "BTCUSDT"}}]
    service = _service_with_pair(monkeypatch, 100.0, None)  # no pair cache
    service._attach_opening_quotes(rows)
    oq = rows[0]["opening_quotes"]
    assert oq["status"] == "unavailable"
    assert oq["updated_at"] is None
    assert all(oq[k] is None for k in NULL_PRICE_KEYS)
