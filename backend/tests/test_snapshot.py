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
from backend.domain.normalize import iso_from_ms
from backend.domain.snapshot import build_rows, top_symbols_by_abs_rate
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
    assert "lastFundingRate" in joined  # funding-rate semantics ambiguity
    assert "TRADIFI_PERPETUAL" in joined  # BSTOCK has no spot leg


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
