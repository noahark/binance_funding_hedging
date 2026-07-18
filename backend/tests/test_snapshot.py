"""End-to-end offline snapshot tests.

Covers: schema validity, classification alignment with the frozen normalized
sample for the 6 curated symbols, summary consistency, warnings preservation,
funding history for the top symbol, decimal-string discipline, and no
non-TRADING leakage.
"""
from __future__ import annotations

from collections import Counter

import jsonschema

from backend.config import Config
from backend.domain.normalize import iso_from_ms, resolve_spot_leg
from backend.domain.snapshot import build_rows, select_borrow_candidates, top_symbols_by_abs_rate
from backend.services.snapshot_service import SnapshotService

EXPECTED_6 = {
    "BTCUSDT": ("MARGIN_SPOT_CANDIDATE", "CRYPTO", "PRIVATE_BORROW_VALIDATION_REQUIRED"),
    "ETHUSDT": ("MARGIN_SPOT_CANDIDATE", "CRYPTO", "PRIVATE_BORROW_VALIDATION_REQUIRED"),
    "XVGUSDT": ("SPOT_ONLY_CANDIDATE", "CRYPTO", "DISABLED_SPOT_ONLY"),
    "XMRUSDT": ("PERP_ONLY_EXCLUDED", "CRYPTO", "DISABLED_PERP_ONLY"),
    "MSTRUSDT": ("PERP_ONLY_EXCLUDED", "BSTOCK", "DISABLED_PERP_ONLY"),
    "TSLAUSDT": ("PERP_ONLY_EXCLUDED", "BSTOCK", "DISABLED_PERP_ONLY"),
}

ELIGIBLE = ("PERPETUAL", "TRADIFI_PERPETUAL")


def _eligible(futures):
    return [
        s
        for s in futures["symbols"]
        if s["status"] == "TRADING" and s["contractType"] in ELIGIBLE
    ]


def _build_snapshot(raw_inputs):
    futures = raw_inputs["futures"]
    premium = {p["symbol"]: p for p in raw_inputs["premium"]}
    spot = {s["symbol"]: s for s in raw_inputs["spot"]["symbols"]}
    funding = raw_inputs["funding"]
    elig = _eligible(futures)
    rows = build_rows(elig, premium, spot, funding)
    data_time = iso_from_ms(max(p["time"] for p in raw_inputs["premium"]))
    return rows, data_time


def test_offline_snapshot_validates(schema, raw_inputs):
    rows, data_time = _build_snapshot(raw_inputs)
    from backend.domain.snapshot import assemble_snapshot

    snap = assemble_snapshot(
        rows,
        generated_at="2026-07-03T05:17:38Z",
        data_time=data_time,
        source_sample_id="20260703T051738Z",
    )
    jsonschema.validate(snap, schema)  # raises on invalid


def test_classification_matches_frozen_six(raw_inputs):
    rows, _ = _build_snapshot(raw_inputs)
    by_sym = {r["symbol"]: r for r in rows}
    for sym, (route, tag, neg) in EXPECTED_6.items():
        row = by_sym[sym]
        assert row["route_class"] == route, sym
        assert row["asset_tag"] == tag, sym
        assert row["negative_funding_status"] == neg, sym


def test_summary_aggregates_from_rows(raw_inputs):
    cfg = Config(offline=True)
    snap = SnapshotService(cfg).build_snapshot()
    rows = snap["rows"]
    s = snap["summary"]
    assert s["total_rows"] == len(rows)
    assert dict(Counter(r["route_class"] for r in rows)) == s["route_counts"]
    assert dict(Counter(r["asset_tag"] for r in rows)) == s["asset_tag_counts"]
    assert (
        dict(Counter(r["negative_funding_status"] for r in rows))
        == s["negative_funding_status_counts"]
    )


def test_three_contract_warnings_preserved(raw_inputs):
    snap = SnapshotService(Config(offline=True)).build_snapshot()
    assert len(snap["warnings"]) == 3
    joined = "\n".join(snap["warnings"])
    assert "-2014" in joined  # margin endpoints require API key
    assert "lastFundingRate" in joined  # funding-rate semantics (real-time estimate)
    assert "TRADIFI_PERPETUAL" in joined  # BSTOCK alias spot-leg rule
    # warnings[1] is the evidenced lastFundingRate semantics amendment (Task A,
    # stage 2026-07-public-market-ui-cn-v1): real-time estimate + evidence path.
    w1 = snap["warnings"][1]
    assert "real-time estimate" in w1
    assert "2026-07-public-market-ui-cn-v1/20260704T044945Z" in w1


def test_btcusdt_top_symbol_has_funding_history(raw_inputs):
    snap = SnapshotService(Config(offline=True)).build_snapshot()
    btc = next(r for r in snap["rows"] if r["symbol"] == "BTCUSDT")
    assert len(btc["funding_history"]) == 10  # frozen fixture has 10 entries
    assert all(isinstance(e["funding_rate"], str) for e in btc["funding_history"])
    assert all(isinstance(e["funding_time"], int) for e in btc["funding_history"])


def test_only_fixture_symbols_have_funding_history(raw_inputs):
    snap = SnapshotService(Config(offline=True)).build_snapshot()
    # Offline uses every frozen funding fixture; only BTCUSDT has one.
    nonempty = [r["symbol"] for r in snap["rows"] if r["funding_history"]]
    assert nonempty == ["BTCUSDT"]


def test_top_symbols_by_abs_rate_ranks_and_caps(raw_inputs):
    from decimal import Decimal

    premium = {p["symbol"]: p for p in raw_inputs["premium"]}
    elig = _eligible(raw_inputs["futures"])
    top5 = top_symbols_by_abs_rate(elig, premium, 5)
    assert len(top5) == 5
    ranked = sorted(
        elig,
        key=lambda o: abs(
            Decimal(str(premium.get(o["symbol"], {}).get("lastFundingRate", "0")))
        ),
        reverse=True,
    )
    assert top5 == {o["symbol"] for o in ranked[:5]}


def test_decimal_fields_are_strings_not_floats(raw_inputs):
    snap = SnapshotService(Config(offline=True)).build_snapshot()
    for row in snap["rows"]:
        f = row["futures"]
        for key in (
            "mark_price",
            "index_price",
            "last_funding_rate",
            "min_notional",
            "step_size",
        ):
            assert isinstance(f[key], str), (row["symbol"], key)
        assert isinstance(f["next_funding_time"], int)
        assert not isinstance(f["next_funding_time"], bool)


def test_no_non_trading_or_non_perpetual_leakage(raw_inputs):
    snap = SnapshotService(Config(offline=True)).build_snapshot()
    assert snap["summary"]["total_rows"] > 0
    for row in snap["rows"]:
        assert row["futures"]["status"] == "TRADING", row["symbol"]
        assert row["futures"]["contract_type"] in ELIGIBLE, row["symbol"]


def test_get_snapshot_is_schema_valid_and_cached(schema):
    cfg = Config(offline=True, cache_ttl_seconds=60)
    service = SnapshotService(cfg)
    first = service.get_snapshot()  # validates internally before caching
    second = service.get_snapshot()  # served from cache
    assert first is second
    assert first["schema_version"] == "public-market-snapshot/v1"
    jsonschema.validate(first, schema)
    # offline mode performs no HTTP requests
    assert service.request_log() == {}


def test_data_time_matches_frozen_sample(raw_inputs, frozen_normalized):
    snap = SnapshotService(Config(offline=True)).build_snapshot()
    assert snap["data_time"] == frozen_normalized["data_time"]


def test_market_rows_order_regression(raw_inputs):
    # v1.1-ui-polish-2 regression: market rows remain sorted by abs(daily_funding_rate)
    # DESC, nulls last, symbol ASC. Private account balance sorting must not affect rows.
    from backend.domain.snapshot import build_rows, sort_rows, SORT_BASIS_ABS
    futures = raw_inputs["futures"]
    premium = {p["symbol"]: p for p in raw_inputs["premium"]}
    spot = {s["symbol"]: s for s in raw_inputs["spot"]["symbols"]}
    funding = raw_inputs["funding"]
    elig = [
        s for s in futures["symbols"]
        if s.get("status") == "TRADING"
        and s.get("contractType") in ("PERPETUAL", "TRADIFI_PERPETUAL")
        and s.get("quoteAsset") == "USDT"
    ]
    rows = build_rows(elig, premium, spot, funding)
    snap = SnapshotService(Config(offline=True)).build_snapshot()
    order = [r["symbol"] for r in snap["rows"]]
    expected = [r["symbol"] for r in sort_rows(rows, SORT_BASIS_ABS)]
    assert order == expected, f"market rows order changed: {order} != {expected}"


# --- bStock B-suffix alias amendment (2026-07-public-market-bstock-alias-v1) ---
# These tests run against the synthetic bstock-alias-raw fixture: the frozen
# curated spot set has no bStock, so the alias join is only exercised here.


def test_bstock_alias_classification(bstock_raw_inputs):
    rows, _ = _build_snapshot(bstock_raw_inputs)
    by_sym = {r["symbol"]: r for r in rows}
    tsla = by_sym["TSLAUSDT"]
    # Alias-joined spot leg -> candidate route; BSTOCK still disables negative.
    assert tsla["route_class"] == "MARGIN_SPOT_CANDIDATE"
    assert tsla["asset_tag"] == "BSTOCK"
    assert tsla["positive_funding_enabled"] is True
    assert tsla["negative_funding_status"] == "DISABLED_BSTOCK"
    assert tsla["spot"]["symbol"] == "TSLABUSDT"
    assert tsla["spot"]["match_type"] == "bstock_b_suffix_alias"
    assert tsla["spot"]["exists"] is True


def test_bstock_negative_rate_still_disabled(bstock_raw_inputs):
    # A bStock with a margin spot leg but a negative funding rate keeps
    # negative_funding_status=DISABLED_BSTOCK (cannot borrow/short a bStock),
    # while the candidate route itself stays open (positive_funding_enabled True).
    rows, _ = _build_snapshot(bstock_raw_inputs)
    by_sym = {r["symbol"]: r for r in rows}
    aapl = by_sym["AAPLUSDT"]
    assert aapl["route_class"] == "MARGIN_SPOT_CANDIDATE"
    assert aapl["negative_funding_status"] == "DISABLED_BSTOCK"
    assert aapl["positive_funding_enabled"] is True
    assert aapl["spot"]["symbol"] == "AAPLBUSDT"
    assert aapl["spot"]["match_type"] == "bstock_b_suffix_alias"


def test_crypto_exact_match_not_aliased(bstock_raw_inputs):
    # Normal crypto must use exact_symbol; the alias never fires for PERPETUAL.
    rows, _ = _build_snapshot(bstock_raw_inputs)
    by_sym = {r["symbol"]: r for r in rows}
    btc = by_sym["BTCUSDT"]
    assert btc["route_class"] == "MARGIN_SPOT_CANDIDATE"
    assert btc["asset_tag"] == "CRYPTO"
    assert btc["spot"]["symbol"] == "BTCUSDT"
    assert btc["spot"]["match_type"] == "exact_symbol"


def test_bstock_no_spot_match_type_null(bstock_raw_inputs):
    # A TRADIFI futures symbol with neither exact nor B-suffix spot -> no leg.
    rows, _ = _build_snapshot(bstock_raw_inputs)
    by_sym = {r["symbol"]: r for r in rows}
    nvda = by_sym["NVDAUSDT"]
    assert nvda["route_class"] == "PERP_ONLY_EXCLUDED"
    assert nvda["spot"]["exists"] is False
    assert nvda["spot"]["symbol"] is None
    assert nvda["spot"]["match_type"] is None
    assert nvda["negative_funding_status"] == "DISABLED_PERP_ONLY"


def test_bstock_alias_snapshot_validates(schema, bstock_raw_inputs):
    rows, data_time = _build_snapshot(bstock_raw_inputs)
    from backend.domain.snapshot import assemble_snapshot

    snap = assemble_snapshot(
        rows,
        generated_at="2026-07-03T05:17:38Z",
        data_time=data_time,
        source_sample_id="bstock-alias-synthetic",
    )
    jsonschema.validate(snap, schema)


def test_bstock_alias_has_funding_history(bstock_raw_inputs):
    rows, _ = _build_snapshot(bstock_raw_inputs)
    by_sym = {r["symbol"]: r for r in rows}
    tsla = by_sym["TSLAUSDT"]
    assert len(tsla["funding_history"]) == 2
    assert all(isinstance(e["funding_rate"], str) for e in tsla["funding_history"])
    assert all(isinstance(e["funding_time"], int) for e in tsla["funding_history"])


# --- rework round 1: spot-leg quoteAsset call-site fix (2026-07-04) ---
# P1 finding spot_leg_quote_asset_hardcode: snapshot.py:70 passed the literal
# "USDT" to resolve_spot_leg, so non-USDT-quoted perpetuals resolved the wrong
# spot leg (e.g. BTCUSDC -> BTCUSDT) labeled exact_symbol. The two tests below
# pin both the call-site fix (build_rows level, isolated from the filter) and
# the user-decision universe filter (service level). See 40-fix-report.md.


def test_build_rows_usdc_perp_exact_match_not_aliased_to_usdt(bstock_raw_inputs):
    """build_rows level: feeding the USDC-quoted BTCUSDC futures row DIRECTLY
    (bypassing the universe filter) resolves spot.symbol=='BTCUSDC' /
    match_type=='exact_symbol' via the row's real quoteAsset — never the BTCUSDT
    spot leg. Validates the snapshot.py:70 call-site fix independently of the
    filter (the USDC row is filtered out in production, so this isolates the
    call site)."""
    futures = bstock_raw_inputs["futures"]
    btcusdc = next(s for s in futures["symbols"] if s["symbol"] == "BTCUSDC")
    spot = {s["symbol"]: s for s in bstock_raw_inputs["spot"]["symbols"]}
    rows = build_rows([btcusdc], {}, spot, {})
    row = {r["symbol"]: r for r in rows}["BTCUSDC"]
    assert row["spot"]["symbol"] == "BTCUSDC"
    assert row["spot"]["match_type"] == "exact_symbol"
    assert row["spot"]["exists"] is True
    # Pre-fix this resolved to the USDT-quoted BTC pair (spot.symbol=="BTCUSDT").
    assert row["spot"]["symbol"] != "BTCUSDT"


def test_service_universe_filter_excludes_non_usdt_quote(bstock_raw_inputs):
    """Service level: the universe filter (quoteAsset=='USDT', user decision
    2026-07-04) excludes the USDC-quoted BTCUSDC futures row even though its
    spot pair exists. Every retained row is USDT-quoted, honoring the frozen
    schema row.quote_asset const 'USDT'. Validates the filter via the real
    SnapshotService pipeline with a stub client injecting the bstock fixture."""

    class _StubClient:
        offline = True
        request_log: dict = {}

        def fetch_raw(self):
            return {
                "futures_exchange_info": bstock_raw_inputs["futures"],
                "premium_index": bstock_raw_inputs["premium"],
                "spot_exchange_info": bstock_raw_inputs["spot"],
                "funding_history_by_sym": bstock_raw_inputs["funding"],
            }

        def fetch_ticker_price_map(self):
            return {}

    service = SnapshotService(Config(offline=True))
    service.client = _StubClient()
    snap = service.build_snapshot()
    syms = {r["symbol"] for r in snap["rows"]}
    assert "BTCUSDC" not in syms  # excluded by quoteAsset=='USDT'
    assert "BTCUSDT" in syms  # USDT-quoted, retained
    # All retained rows honor the frozen schema row.quote_asset const 'USDT'.
    for r in snap["rows"]:
        assert r["quote_asset"] == "USDT"


# --- METAL asset tag + borrow-candidate inclusion ---
# (stage 2026-07-ui-filter-balance-metal-v1)
# Synthetic futures/spot dicts exercise the METAL tag and the expanded
# select_borrow_candidates (CRYPTO or METAL) without live HTTP. The real public
# sample currently lists metals as TRADIFI_PERPETUAL with no public spot leg
# (reports/api-samples/2026-07-ui-filter-balance-metal-v1/20260708T0928Z/), so
# they resolve PERP_ONLY_EXCLUDED there; the spot-leg scenarios below are
# deliberate constructs to exercise the borrow-candidate inclusion path.


def _metal_futures(symbol, base_asset, contract_type="TRADIFI_PERPETUAL"):
    return {
        "symbol": symbol,
        "baseAsset": base_asset,
        "quoteAsset": "USDT",
        "contractType": contract_type,
        "status": "TRADING",
    }


def test_metal_base_asset_tagged_metal_over_tradifi():
    """A metal baseAsset on a TRADIFI_PERPETUAL contract is METAL, not BSTOCK;
    with no public spot leg it is PERP_ONLY_EXCLUDED / DISABLED_PERP_ONLY."""
    rows = build_rows(
        [_metal_futures("XAUUSDT", "XAU")],
        {"XAUUSDT": {"lastFundingRate": "0.00010000"}},
        {},
        {},
    )
    row = rows[0]
    assert row["asset_tag"] == "METAL"
    assert row["asset_tag_source"] == "base_asset_metal_symbol"
    assert row["route_class"] == "PERP_ONLY_EXCLUDED"
    assert row["negative_funding_status"] == "DISABLED_PERP_ONLY"
    assert row["spot"]["exists"] is False


def test_metal_margin_spot_candidate_enters_borrow_candidates():
    """A metal row that is MARGIN_SPOT_CANDIDATE with a negative daily rate
    enters both rate_probe_assets and borrowability_probe_assets — METAL is not
    a borrow prohibition; borrowability/cost come from the private read-only
    interface (here just the candidate-set membership)."""
    from decimal import Decimal

    rows = build_rows(
        [_metal_futures("COPPERUSDT", "COPPER")],
        {"COPPERUSDT": {"lastFundingRate": "-0.00060000"}},  # 8h -> daily -0.00180000
        {"COPPERUSDT": {"symbol": "COPPERUSDT", "status": "TRADING", "isMarginTradingAllowed": True}},
        {},
    )
    row = rows[0]
    assert row["asset_tag"] == "METAL"
    assert row["route_class"] == "MARGIN_SPOT_CANDIDATE"
    assert row["negative_funding_status"] == "PRIVATE_BORROW_VALIDATION_REQUIRED"
    assert Decimal(row["daily_funding_rate"]) < 0
    probe = select_borrow_candidates(rows, max_calls=10)
    assert "COPPER" in probe["rate_probe_assets"]
    assert "COPPER" in probe["borrowability_probe_assets"]


def test_bstock_remains_excluded_from_borrow_candidates():
    """bStock (TRADIFI_PERPETUAL, non-metal baseAsset) with a margin spot leg
    and negative rate stays excluded from select_borrow_candidates."""
    rows = build_rows(
        [_metal_futures("TSLAUSDT", "TSLA")],
        {"TSLAUSDT": {"lastFundingRate": "-0.00060000"}},
        {"TSLABUSDT": {"symbol": "TSLABUSDT", "status": "TRADING", "isMarginTradingAllowed": True}},
        {},
    )
    row = rows[0]
    assert row["asset_tag"] == "BSTOCK"
    assert row["route_class"] == "MARGIN_SPOT_CANDIDATE"
    assert row["negative_funding_status"] == "DISABLED_BSTOCK"
    probe = select_borrow_candidates(rows, max_calls=10)
    assert "TSLA" not in probe["rate_probe_assets"]
    assert "TSLA" not in probe["borrowability_probe_assets"]


def test_metal_and_crypto_compose_in_borrow_candidates():
    """A mixed pool (one CRYPTO + one METAL, both negative MARGIN_SPOT_CANDIDATE)
    includes both base_assets, deduped/sorted by abs daily rate DESC."""
    rows = build_rows(
        [
            _metal_futures("COPPERUSDT", "COPPER"),
            {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT",
             "contractType": "PERPETUAL", "status": "TRADING"},
        ],
        {"COPPERUSDT": {"lastFundingRate": "-0.00060000"},  # daily -0.00180000
         "BTCUSDT": {"lastFundingRate": "-0.00040000"}},    # daily -0.00120000
        {"COPPERUSDT": {"symbol": "COPPERUSDT", "status": "TRADING", "isMarginTradingAllowed": True},
         "BTCUSDT": {"symbol": "BTCUSDT", "status": "TRADING", "isMarginTradingAllowed": True}},
        {},
    )
    probe = select_borrow_candidates(rows, max_calls=10)
    # abs daily DESC: COPPER (0.0018) before BTC (0.0012)
    assert probe["rate_probe_assets"] == ["COPPER", "BTC"]


def test_metal_snapshot_row_validates_schema(schema):
    """A snapshot containing a METAL row validates against the schema."""
    from backend.domain.snapshot import assemble_snapshot

    rows = build_rows(
        [_metal_futures("XAUUSDT", "XAU")],
        {"XAUUSDT": {"lastFundingRate": "0.00010000"}},
        {},
        {},
    )
    snap = assemble_snapshot(
        rows,
        generated_at="2026-07-08T09:28:00Z",
        data_time="2026-07-08T09:28:00Z",
        source_sample_id="metal-synthetic",
    )
    jsonschema.validate(snap, schema)
    assert snap["summary"]["asset_tag_counts"].get("METAL") == 1


# --- tradable spot-leg status gate (2026-07-tradable-spot-leg-v1) ---
# Frozen public evidence: reports/api-samples/2026-07-tradable-spot-leg-v1/
# 20260718T042314Z/ — AERGOUSDT/XMRUSDT/LITUSDT remain in spot exchangeInfo with
# status="BREAK" (isMarginTradingAllowed=false) and a zero bookTicker while their
# perpetuals quote normally. Symbol presence alone is therefore not evidence of a
# tradable spot leg: resolve_spot_leg must resolve only status=="TRADING" spot
# records, and a non-trading exact record must not block a trading B-suffix alias.


def test_spot_leg_exact_trading_resolves():
    """Case 1: an exact TRADING spot record remains eligible (exact_symbol)."""
    spot = {"FOOUSDT": {"symbol": "FOOUSDT", "status": "TRADING", "isMarginTradingAllowed": True}}
    leg, match = resolve_spot_leg("PERPETUAL", "FOO", "USDT", spot)
    assert leg is spot["FOOUSDT"]
    assert match == "exact_symbol"


def test_spot_leg_exact_break_does_not_resolve_and_excludes_route():
    """Case 2: an exact BREAK record resolves to no leg, and a TRADING futures row
    builds the expected PERP_ONLY_EXCLUDED excluded shape (spot.exists=false,
    spot fields null, negative_funding_status=DISABLED_PERP_ONLY)."""
    spot = {"FOOUSDT": {"symbol": "FOOUSDT", "status": "BREAK", "isMarginTradingAllowed": False}}
    leg, match = resolve_spot_leg("PERPETUAL", "FOO", "USDT", spot)
    assert leg is None
    assert match is None
    rows = build_rows(
        [{"symbol": "FOOUSDT", "baseAsset": "FOO", "quoteAsset": "USDT",
          "contractType": "PERPETUAL", "status": "TRADING"}],
        {"FOOUSDT": {"lastFundingRate": "0.00010000"}},
        spot,
        {},
    )
    row = rows[0]
    assert row["route_class"] == "PERP_ONLY_EXCLUDED"
    assert row["negative_funding_status"] == "DISABLED_PERP_ONLY"
    assert row["positive_funding_enabled"] is False
    assert row["spot"]["exists"] is False
    assert row["spot"]["symbol"] is None
    assert row["spot"]["status"] is None
    assert row["spot"]["match_type"] is None


def test_spot_leg_exact_halt_does_not_resolve():
    """Case 3: an exact HALT record does not resolve (even with margin allowed)."""
    spot = {"FOOUSDT": {"symbol": "FOOUSDT", "status": "HALT", "isMarginTradingAllowed": True}}
    leg, match = resolve_spot_leg("PERPETUAL", "FOO", "USDT", spot)
    assert leg is None
    assert match is None


def test_spot_leg_non_trading_exact_does_not_block_trading_alias():
    """Case 4: for TRADIFI_PERPETUAL a non-trading exact record is skipped and a
    trading B-suffix alias still resolves (bstock_b_suffix_alias)."""
    spot = {
        "TSLAUSDT": {"symbol": "TSLAUSDT", "status": "BREAK", "isMarginTradingAllowed": False},
        "TSLABUSDT": {"symbol": "TSLABUSDT", "status": "TRADING", "isMarginTradingAllowed": True},
    }
    leg, match = resolve_spot_leg("TRADIFI_PERPETUAL", "TSLA", "USDT", spot)
    assert leg is spot["TSLABUSDT"]
    assert match == "bstock_b_suffix_alias"


def test_spot_leg_non_trading_alias_does_not_resolve():
    """Case 5: a non-trading B-suffix alias does not resolve (exact non-trading +
    alias non-trading -> no leg)."""
    spot = {
        "TSLAUSDT": {"symbol": "TSLAUSDT", "status": "BREAK", "isMarginTradingAllowed": False},
        "TSLABUSDT": {"symbol": "TSLABUSDT", "status": "HALT", "isMarginTradingAllowed": True},
    }
    leg, match = resolve_spot_leg("TRADIFI_PERPETUAL", "TSLA", "USDT", spot)
    assert leg is None
    assert match is None


def test_spot_leg_missing_or_unknown_status_fails_closed():
    """Case 6: a record with a missing status field, and one with an unrecognized
    status value, both fail closed (not treated as tradable)."""
    missing = {"FOOUSDT": {"symbol": "FOOUSDT", "isMarginTradingAllowed": True}}
    leg, match = resolve_spot_leg("PERPETUAL", "FOO", "USDT", missing)
    assert leg is None
    assert match is None
    unknown = {"BARUSDT": {"symbol": "BARUSDT", "status": "AUCTION_MATCHING", "isMarginTradingAllowed": True}}
    leg, match = resolve_spot_leg("PERPETUAL", "BAR", "USDT", unknown)
    assert leg is None
    assert match is None
