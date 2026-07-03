"""Unit tests for the pure normalization helpers."""
from __future__ import annotations

from backend.domain.normalize import asset_tag_for, filter_of, iso_from_ms


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
