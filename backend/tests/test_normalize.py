"""Unit tests for the pure normalization helpers."""
from __future__ import annotations

from backend.domain.normalize import (
    asset_tag_for,
    filter_of,
    iso_from_ms,
    resolve_spot_leg,
)


def test_asset_tag_tradifi_maps_to_bstock():
    assert asset_tag_for("TRADIFI_PERPETUAL") == (
        "BSTOCK",
        "futures_contractType_tradifi_perpetual",
        "HIGH",
    )


def test_asset_tag_perpetual_maps_to_crypto():
    assert asset_tag_for("PERPETUAL") == (
        "CRYPTO",
        "futures_contractType_perpetual",
        "HIGH",
    )


def test_asset_tag_unmapped_is_unknown():
    tag, _, conf = asset_tag_for("CURRENT_QUARTER")
    assert tag == "UNKNOWN"
    assert conf == "LOW"


# --- METAL asset tag (stage 2026-07-ui-filter-balance-metal-v1) ---
# A real-metal baseAsset is METAL regardless of contractType, and the check runs
# BEFORE the TRADIFI_PERPETUAL -> BSTOCK mapping, so a metal TRADIFI_PERPETUAL is
# never tagged BSTOCK. The base_asset default keeps single-argument callers intact.


def test_asset_tag_metal_perpetual_base_asset():
    assert asset_tag_for("PERPETUAL", "XAU") == (
        "METAL",
        "base_asset_metal_symbol",
        "HIGH",
    )


def test_asset_tag_metal_takes_priority_over_tradifi_bstock():
    # COPPER ships as contractType=TRADIFI_PERPETUAL but is METAL, not BSTOCK.
    assert asset_tag_for("TRADIFI_PERPETUAL", "COPPER") == (
        "METAL",
        "base_asset_metal_symbol",
        "HIGH",
    )


def test_asset_tag_metal_base_asset_is_case_insensitive():
    assert asset_tag_for("PERPETUAL", "xag")[0] == "METAL"


def test_asset_tag_single_arg_callers_still_work():
    # The default base_asset="" preserves the original single-argument contract.
    assert asset_tag_for("TRADIFI_PERPETUAL")[0] == "BSTOCK"
    assert asset_tag_for("PERPETUAL")[0] == "CRYPTO"


def test_filter_of_futures_min_notional_and_lot_size():
    sym = {
        "filters": [
            {"filterType": "MIN_NOTIONAL", "notional": "50"},
            {"filterType": "LOT_SIZE", "stepSize": "0.001"},
        ]
    }
    assert filter_of(sym, "MIN_NOTIONAL", "notional") == "50"
    assert filter_of(sym, "LOT_SIZE", "stepSize") == "0.001"


def test_filter_of_spot_notional_filter():
    sym = {"filters": [{"filterType": "NOTIONAL", "minNotional": "5"}]}
    assert filter_of(sym, "NOTIONAL", "minNotional") == "5"


def test_filter_of_missing_or_none():
    assert filter_of({"filters": []}, "MIN_NOTIONAL", "notional") is None
    assert filter_of(None, "MIN_NOTIONAL", "notional") is None


def test_iso_from_ms_matches_frozen_data_time():
    # 1783055489000 ms is the max premiumIndex.time in the frozen sample; the
    # frozen data_time is "2026-07-03T05:11:29Z". Integer division, no float.
    assert iso_from_ms(1783055489000) == "2026-07-03T05:11:29Z"


def test_iso_from_ms_ignores_subsecond_part():
    assert iso_from_ms(1783055489999) == "2026-07-03T05:11:29Z"


def test_resolve_spot_leg_exact_symbol():
    spot = {"BTCUSDT": {"symbol": "BTCUSDT", "status": "TRADING"}}
    obj, match_type = resolve_spot_leg("PERPETUAL", "BTC", "USDT", spot)
    assert obj["symbol"] == "BTCUSDT"
    assert match_type == "exact_symbol"


def test_resolve_spot_leg_bstock_alias_for_tradifi():
    # Futures TSLAUSDT -> spot TSLABUSDT via baseAsset+"B"+quoteAsset alias.
    spot = {"TSLABUSDT": {"symbol": "TSLABUSDT", "status": "TRADING"}}
    obj, match_type = resolve_spot_leg("TRADIFI_PERPETUAL", "TSLA", "USDT", spot)
    assert obj["symbol"] == "TSLABUSDT"
    assert match_type == "bstock_b_suffix_alias"


def test_resolve_spot_leg_alias_not_triggered_for_perpetual():
    # A normal PERPETUAL falls back to the B-suffix alias only when a tradable
    # spot pair actually exists (MUUUSDT -> MUBUSDT case, 2026-08-05 follow-up);
    # an untradable B-suffix record must NOT be matched.
    spot = {"TSLABUSDT": {"symbol": "TSLABUSDT", "status": "BREAK"}}
    obj, match_type = resolve_spot_leg("PERPETUAL", "TSLA", "USDT", spot)
    assert obj is None
    assert match_type is None


def test_resolve_spot_leg_bstock_alias_for_perpetual_when_tradable():
    # The alias fallback is no longer gated on TRADIFI_PERPETUAL (2026-08-07
    # unified-resolver): a plain PERPETUAL whose spot pair carries the B suffix
    # resolves when the pair is tradable. (Real MUUSDT is TRADIFI — see
    # test_resolve_spot_leg_bstock_alias_mu_case; this asserts the general rule.)
    spot = {"FOOBUSDT": {"symbol": "FOOBUSDT", "status": "TRADING"}}
    obj, match_type = resolve_spot_leg("PERPETUAL", "FOO", "USDT", spot)
    assert obj["symbol"] == "FOOBUSDT"
    assert match_type == "bstock_b_suffix_alias"


def test_resolve_spot_leg_bstock_alias_mu_case():
    # Real 2026-08-05 follow-up case: futures MUUSDT (TRADIFI, baseAsset MU) ->
    # spot MUBUSDT. PROJECT_STATE's "MUUUSDT" spelling was a typo; the
    # exchangeInfo sample (public-market-bstock-alias-v1) confirms MU + "B".
    spot = {"MUBUSDT": {"symbol": "MUBUSDT", "status": "TRADING"}}
    obj, match_type = resolve_spot_leg("TRADIFI_PERPETUAL", "MU", "USDT", spot)
    assert obj["symbol"] == "MUBUSDT"
    assert match_type == "bstock_b_suffix_alias"


def test_resolve_spot_leg_multiplier_strip():
    # 1000BONKUSDT futures -> spot BONKUSDT via the literal "1000" prefix strip.
    spot = {"BONKUSDT": {"symbol": "BONKUSDT", "status": "TRADING"}}
    obj, match_type = resolve_spot_leg("PERPETUAL", "1000BONK", "USDT", spot)
    assert obj["symbol"] == "BONKUSDT"
    assert match_type == "multiplier_strip_alias"


def test_resolve_spot_leg_multiplier_exact_beats_strip():
    # If a spot pair literally named 1000BONKUSDT exists (it does not today),
    # exact matching wins; the strip is a fallback, never a replacement.
    spot = {
        "1000BONKUSDT": {"symbol": "1000BONKUSDT", "status": "TRADING"},
        "BONKUSDT": {"symbol": "BONKUSDT", "status": "TRADING"},
    }
    obj, match_type = resolve_spot_leg("PERPETUAL", "1000BONK", "USDT", spot)
    assert obj["symbol"] == "1000BONKUSDT"
    assert match_type == "exact_symbol"


def test_resolve_spot_leg_multiplier_no_spot_none():
    # Strip yields no tradable spot pair -> (None, None), never a guess.
    obj, match_type = resolve_spot_leg("PERPETUAL", "1000BONK", "USDT", {})
    assert obj is None
    assert match_type is None


def test_resolve_spot_leg_none_when_no_spot():
    obj, match_type = resolve_spot_leg("TRADIFI_PERPETUAL", "NVDA", "USDT", {})
    assert obj is None
    assert match_type is None


def test_resolve_spot_leg_exact_beats_alias_for_tradifi():
    # If a TRADIFI futures symbol coincidentally also has an EXACT spot symbol,
    # exact-symbol matching wins (alias is a fallback, never a replacement).
    spot = {
        "TSLAUSDT": {"symbol": "TSLAUSDT", "status": "TRADING"},
        "TSLABUSDT": {"symbol": "TSLABUSDT", "status": "TRADING"},
    }
    obj, match_type = resolve_spot_leg("TRADIFI_PERPETUAL", "TSLA", "USDT", spot)
    assert obj["symbol"] == "TSLAUSDT"
    assert match_type == "exact_symbol"
