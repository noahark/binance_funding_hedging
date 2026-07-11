"""Stage 2026-07-funding-annualized-history-v1 — Task A tests.

Covers the three additive annualized fields and the settled-history enrichment:
24h estimate-derived annualization (daily_funding_rate * 365); 7D/30D
calendar-window settled annualization (sum * 365/N, Decimal-only, 8 places);
inclusive-window filtering + newest-first serialization; the bounded top-N
deep-history request shape; the dedicated per-symbol successful-result cache;
per-symbol failure degradation (empty history + null 7D/30D + warning, never a
503); and the additive decimal-or-null schema contract (the live service always
emits the three keys; the schema keeps them optional so frozen v0.1 snapshots
stay valid under the unchanged wire version).

Deterministic vectors live under ``backend/tests/fixtures/funding-history/``.
No network: the public client is stubbed where the live deep-history path is
exercised; pure functions and ``build_rows`` are tested directly.
"""
from __future__ import annotations

import json
import urllib.error
from pathlib import Path
from decimal import Decimal

import jsonschema
import pytest

from backend.config import Config
from backend.domain.snapshot import (
    _build_funding_history,
    assemble_snapshot,
    build_rows,
    compute_annualized_funding_24h,
    compute_annualized_funding_window,
    settle_history_view,
)
from backend.services.snapshot_service import SnapshotService

REPO_ROOT = Path(__file__).resolve().parents[2]
FIX_DIR = REPO_ROOT / "backend/tests/fixtures/funding-history"

# Fixed snapshot premium-index time (ms) shared by every window vector below.
T_END = 1783641600000
DAY = 86_400_000


def _fixture(name: str) -> list:
    return json.loads((FIX_DIR / name).read_text())


@pytest.fixture(scope="session")
def schema() -> dict:
    return json.loads(
        (REPO_ROOT / "schemas/api/public-market/snapshot.schema.json").read_text()
    )


# =========================================================================
# 24h annualization — estimate-derived (daily_funding_rate * 365)
# =========================================================================
@pytest.mark.parametrize(
    "daily,expected",
    [
        ("0.00030000", "0.10950000"),   # 0.0003 * 365 = 0.1095
        ("0.00060000", "0.21900000"),   # 0.0006 * 365 = 0.219
        ("-0.00005000", "-0.01825000"),  # sign preserved
        ("0.00000000", "0.00000000"),   # neg-zero normalization
    ],
)
def test_compute_annualized_funding_24h_vectors(daily, expected):
    assert compute_annualized_funding_24h(daily) == expected


@pytest.mark.parametrize("daily", [None, "", "not-a-number"])
def test_compute_annualized_funding_24h_null_inputs(daily):
    assert compute_annualized_funding_24h(daily) is None


def test_compute_annualized_funding_24h_no_float_no_scientific():
    out = compute_annualized_funding_24h("0.00000001")  # 1e-8 * 365
    assert out == "0.00000365"
    assert "e" not in (out or "").lower()
    # exactly eight decimal places, decimal string
    assert out == format(Decimal(out).quantize(Decimal("1E-8")), "f")


# =========================================================================
# 7D / 30D settled-window annualization (sum * 365/N, calendar denominator)
# =========================================================================
def test_seven_day_flat_window_vectors():
    # 7 daily points @ 0.00010000, all inside the 7D window: sum 0.0007.
    wire = _build_funding_history(_fixture("seven-day-flat.json"), T_END)
    assert len(wire) == 7
    assert compute_annualized_funding_window(wire, T_END, 7) == "0.03650000"
    assert compute_annualized_funding_window(wire, T_END, 30) == "0.00851667"


def test_inclusive_boundaries_and_exclusions():
    # Distinct rates trace each point: only on-edge and inside-window points
    # are summed; points 1ms outside either edge (and a future point) drop.
    wire = _build_funding_history(_fixture("boundaries.json"), T_END)
    # 7D keeps on-t_end (0.0001) + 7D-lower-edge (0.0002) -> sum 0.0003.
    assert compute_annualized_funding_window(wire, T_END, 7) == "0.01564286"
    # 30D keeps those two + 30D-lower-edge (0.0003) + 1ms-before-7D (0.0004)
    # -> sum 0.0010. The 1ms-before-30D (0.0005) and future (0.0006) drop.
    assert compute_annualized_funding_window(wire, T_END, 30) == "0.01216667"


def test_mixed_interval_sum_independent_of_spacing():
    # 1h/4h-ish spacing, all inside 7D: the sum does not depend on interval.
    wire = _build_funding_history(_fixture("mixed-interval.json"), T_END)
    assert len(wire) == 3
    assert compute_annualized_funding_window(wire, T_END, 7) == "0.00782143"
    assert compute_annualized_funding_window(wire, T_END, 30) == "0.00182500"


def test_negative_rates_sign_preserved():
    wire = _build_funding_history(_fixture("negative-rates.json"), T_END)
    # -0.0001 + 0.00005 = -0.00005
    assert compute_annualized_funding_window(wire, T_END, 7) == "-0.00260714"
    assert compute_annualized_funding_window(wire, T_END, 30) == "-0.00060833"


def test_empty_window_yields_null():
    # Lone point 40d ago -> no in-window entries -> None (no inflation).
    wire = _build_funding_history(_fixture("out-of-window.json"), T_END)
    assert wire == []
    assert compute_annualized_funding_window(wire, T_END, 7) is None
    assert compute_annualized_funding_window(wire, T_END, 30) is None


def test_window_null_when_t_end_unknown():
    wire = _build_funding_history(_fixture("seven-day-flat.json"), None)
    assert compute_annualized_funding_window(wire, None, 7) is None
    assert compute_annualized_funding_window(wire, None, 30) is None


def test_window_skips_unparseable_entries():
    # Malformed funding_time / funding_rate entries are skipped, not raised.
    wire = [
        {"funding_time": T_END - DAY, "funding_rate": "0.00010000"},
        {"funding_time": "oops", "funding_rate": "0.00010000"},
        {"funding_time": T_END - 2 * DAY, "funding_rate": "not-a-number"},
    ]
    assert compute_annualized_funding_window(wire, T_END, 7) == "0.00521429"  # 0.0001*365/7


def test_settle_history_view_available_and_empty():
    # Pure composition reused by the selected-symbol endpoint (Task C): the same
    # 30-day windowing, newest-first ordering, and Decimal calendar-window
    # annualization, plus an explicit available/empty status split.
    history, a7, a30, status = settle_history_view(
        _fixture("seven-day-flat.json"), T_END
    )
    assert status == "available"
    assert len(history) == 7
    assert a7 == "0.03650000"
    assert a30 == "0.00851667"
    # a successful empty window -> "empty" status and null settled annualization
    assert settle_history_view([], T_END) == ([], None, None, "empty")


# =========================================================================
# build_rows — funding_history windowing + annualized fields on the wire
# =========================================================================
_SYM = {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT",
        "contractType": "PERPETUAL", "status": "TRADING", "filters": []}


def test_build_rows_emits_three_annualized_fields_from_history():
    rows = build_rows(
        [_SYM], {"BTCUSDT": {"lastFundingRate": "0.00010000"}}, {},
        {"BTCUSDT": _fixture("seven-day-flat.json")},
        t_end_ms=T_END,
    )
    row = rows[0]
    # daily = lastFundingRate 0.0001 * (24/8h) = 0.0003 -> 24h = 0.0003 * 365
    assert row["daily_funding_rate"] == "0.00030000"
    assert row["annualized_funding_24h"] == "0.10950000"
    assert row["annualized_funding_7d"] == "0.03650000"
    assert row["annualized_funding_30d"] == "0.00851667"


def test_build_rows_funding_history_newest_first_and_windowed():
    rows = build_rows(
        [_SYM], {"BTCUSDT": {"lastFundingRate": "0.00010000"}}, {},
        {"BTCUSDT": _fixture("boundaries.json")},
        t_end_ms=T_END,
    )
    history = rows[0]["funding_history"]
    times = [e["funding_time"] for e in history]
    assert times == sorted(times, reverse=True)   # newest first
    # 30-day window applied: the 40d/31d... points are gone; on-t_end leads.
    assert times[0] == T_END
    assert all(t >= T_END - 30 * DAY for t in times)


def test_build_rows_eight_place_serialization_no_scientific():
    rows = build_rows(
        [_SYM], {"BTCUSDT": {"lastFundingRate": "0.00000001"}}, {},
        {"BTCUSDT": _fixture("seven-day-flat.json")},
        t_end_ms=T_END,
    )
    for key in ("annualized_funding_24h", "annualized_funding_7d", "annualized_funding_30d"):
        val = rows[0][key]
        assert isinstance(val, str)
        assert "e" not in val.lower()
        # re-quantizing an already-8-place string is idempotent
        assert val == format(Decimal(val).quantize(Decimal("1E-8")), "f")


def test_build_rows_no_t_end_yields_null_window_fields_but_24h():
    rows = build_rows(
        [_SYM], {"BTCUSDT": {"lastFundingRate": "0.00010000"}}, {},
        {"BTCUSDT": _fixture("seven-day-flat.json")},  # t_end_ms default None
    )
    row = rows[0]
    assert row["annualized_funding_24h"] == "0.10950000"   # estimate still computed
    assert row["annualized_funding_7d"] is None
    assert row["annualized_funding_30d"] is None
    # history is passed through unfiltered when no window end is known
    assert len(row["funding_history"]) == 7


def test_build_rows_daily_null_yields_24h_null():
    rows = build_rows(
        [_SYM], {"BTCUSDT": {"lastFundingRate": ""}}, {}, {}, t_end_ms=T_END,
    )
    assert rows[0]["daily_funding_rate"] is None
    assert rows[0]["annualized_funding_24h"] is None


def test_build_rows_always_emits_three_annualized_fields():
    # Service output guarantee (operator direction): the live backend ALWAYS
    # outputs the three annualized keys on every row, even with no history. They
    # are additive/optional on the schema (frozen v0.1 snapshots stay valid), but
    # the current-snapshot service contract is presence.
    rows = build_rows(
        [_SYM], {"BTCUSDT": {"lastFundingRate": "0.00010000"}}, {}, {}, t_end_ms=T_END,
    )
    keys = {"annualized_funding_24h", "annualized_funding_7d", "annualized_funding_30d"}
    assert keys.issubset(rows[0].keys())
    assert rows[0]["annualized_funding_24h"] == "0.10950000"  # estimate present
    assert rows[0]["annualized_funding_7d"] is None            # no history -> null
    assert rows[0]["annualized_funding_30d"] is None


# =========================================================================
# SnapshotService — bounded top-N deep history, exact request, cache, degrade
# =========================================================================
def _raw(rate="0.00010000", symbols=1):
    syms, prem = [], []
    for i in range(symbols):
        sym = "BTCUSDT" if symbols == 1 else f"TST{i}USDT"
        base = "BTC" if symbols == 1 else f"TST{i}"
        syms.append({"symbol": sym, "baseAsset": base, "quoteAsset": "USDT",
                     "contractType": "PERPETUAL", "status": "TRADING", "filters": []})
        prem.append({"symbol": sym, "lastFundingRate": rate, "markPrice": "1",
                     "indexPrice": "1", "nextFundingTime": T_END + 1, "time": T_END})
    return {
        "futures_exchange_info": {"symbols": syms},
        "premium_index": prem,
        "spot_exchange_info": {"symbols": []},
        "funding_history_by_sym": {},
        "funding_interval_by_sym": {},
        "warnings": [],
    }


class _StubPublic:
    """Records deep-history calls; returns canned entries or raises."""

    offline = False

    def __init__(self, raw, history_fn=None):
        self._raw = raw
        self._history_fn = history_fn or (lambda symbol, **kw: [])
        self.request_log: dict = {"GET /fapi/v1/fundingRate": 0}
        self.calls: list = []

    def fetch_raw(self):
        return self._raw

    def fetch_funding_rate(self, symbol, *, start_time_ms=None, end_time_ms=None, limit=1000):
        self.request_log["GET /fapi/v1/fundingRate"] += 1
        self.calls.append((symbol, start_time_ms, end_time_ms, limit))
        return self._history_fn(symbol, start_time_ms=start_time_ms,
                                end_time_ms=end_time_ms, limit=limit)

    def fetch_ticker_price_map(self):
        return {}


class _StubPrivate:
    """Disabled private channel (classic_ref None -> no signed HTTP)."""

    def __init__(self):
        self.last_error = "private_channel_disabled"

    def fetch_classic_reference(self):
        return None

    def fetch_cost_leg_chain(self, assets):
        return None

    def fetch_unified_balances(self):
        return None

    def fetch_um_positions(self):
        return None

    def fetch_spot_balances(self):
        return None

    def fetch_max_borrowable(self, asset):
        return None


def _service_with(raw, history_fn=None, **cfg):
    service = SnapshotService(Config(offline=False, **cfg))
    service.client = _StubPublic(raw, history_fn)
    service._private = _StubPrivate()
    return service


def test_service_requests_exact_deep_history_parameters():
    captured = {}

    def hist(symbol, *, start_time_ms, end_time_ms, limit):
        captured.update(symbol=symbol, start=start_time_ms, end=end_time_ms, limit=limit)
        return []   # empty -> null 7D/30D

    service = _service_with(_raw(), hist)
    service.build_snapshot()
    assert captured["symbol"] == "BTCUSDT"
    assert captured["limit"] == 1000
    assert captured["end"] == T_END
    assert captured["start"] == T_END - 30 * DAY   # startTime = t_end - 30d


def test_service_history_feeds_annualized_fields(schema):
    service = _service_with(
        _raw(), lambda symbol, **kw: _fixture("seven-day-flat.json"),
    )
    snap = service.build_snapshot()
    jsonschema.validate(snap, schema)
    btc = snap["rows"][0]
    assert btc["annualized_funding_24h"] == "0.10950000"
    assert btc["annualized_funding_7d"] == "0.03650000"
    assert btc["annualized_funding_30d"] == "0.00851667"


def test_service_top_n_caps_deep_history_calls():
    service = _service_with(_raw(symbols=5), lambda symbol, **kw: [], top_n=2)
    service.build_snapshot()
    fetched = [c[0] for c in service.client.calls]
    assert len(fetched) == 2          # only the top-N by abs(rate)


def test_service_history_cache_avoids_refetch_within_ttl():
    service = _service_with(_raw(), lambda symbol, **kw: _fixture("seven-day-flat.json"))
    service.build_snapshot()
    service.build_snapshot()           # second rebuild -> served from history cache
    assert service.client.request_log["GET /fapi/v1/fundingRate"] == 1


def test_service_history_failure_degrades_row_not_snapshot(schema):
    def fail(symbol, **kw):
        raise urllib.error.URLError("boom")

    service = _service_with(_raw(), fail)
    snap = service.build_snapshot()    # must NOT raise
    jsonschema.validate(snap, schema)
    btc = snap["rows"][0]
    assert btc["funding_history"] == []
    assert btc["annualized_funding_7d"] is None
    assert btc["annualized_funding_30d"] is None
    assert btc["annualized_funding_24h"] is not None        # estimate still computed
    assert "funding_history_unavailable:BTCUSDT" in snap["warnings"]


def test_service_history_failure_is_not_cached_retries_next_rebuild():
    calls = {"n": 0}

    def fail(symbol, **kw):
        calls["n"] += 1
        raise urllib.error.URLError("boom")

    service = _service_with(_raw(), fail)
    service.build_snapshot()
    service.build_snapshot()
    assert calls["n"] == 2             # failure not cached -> retried


# =========================================================================
# Schema — additive decimal-or-null properties (optional). The live service
# always emits these keys; the schema keeps them optional so frozen v0.1
# snapshots (which lack them) stay valid under the unchanged wire version.
# =========================================================================
_FULL_ROW = {
    "symbol": "BTCUSDT", "base_asset": "BTC", "quote_asset": "USDT",
    "asset_tag": "CRYPTO", "asset_tag_source": "x", "asset_tag_confidence": "HIGH",
    "route_class": "MARGIN_SPOT_CANDIDATE", "positive_funding_enabled": True,
    "negative_funding_status": "PRIVATE_BORROW_VALIDATION_REQUIRED",
    "futures": {"symbol": "BTCUSDT", "status": "TRADING", "contract_type": "PERPETUAL",
                "mark_price": "60000", "index_price": "60000", "last_funding_rate": "0.0001",
                "next_funding_time": 1, "min_notional": "5", "step_size": "0.001"},
    "spot": {"symbol": "BTCUSDT", "status": "TRADING", "exists": True,
             "match_type": "exact_symbol", "min_notional": "5", "step_size": "0.001"},
    "margin_public": {"public_cross_margin_pair": None, "source": "unverified"},
    "funding_history": [], "ui_flags": [],
    "annualized_funding_24h": "0.10950000",
    "annualized_funding_7d": "0.03650000",
    "annualized_funding_30d": "0.00851667",
}


def _snapshot_with(row):
    return {
        "schema_version": "public-market-snapshot/v1",
        "generated_at": "2026-07-10T00:00:00Z",
        "data_time": "2026-07-10T00:00:00Z",
        "source_sample_id": "annualized-test",
        "summary": {"total_rows": 1, "route_counts": {"MARGIN_SPOT_CANDIDATE": 1},
                    "asset_tag_counts": {"CRYPTO": 1},
                    "negative_funding_status_counts": {"PRIVATE_BORROW_VALIDATION_REQUIRED": 1}},
        "rows": [row], "warnings": [],
    }


def test_full_row_with_annualized_validates(schema):
    jsonschema.validate(_snapshot_with(dict(_FULL_ROW)), schema)


@pytest.mark.parametrize("field", [
    "annualized_funding_24h", "annualized_funding_7d", "annualized_funding_30d",
])
def test_annualized_field_accepts_null(schema, field):
    # Additive decimal-or-null: null is valid (must NOT raise). The three fields
    # are optional on the schema, preserving the v1 additive/backward-compatible
    # guarantee for frozen v0.1 snapshots. The live service guarantees presence;
    # the schema does not reject absence.
    row = dict(_FULL_ROW)
    row[field] = None
    jsonschema.validate(_snapshot_with(row), schema)


def test_row_without_annualized_fields_still_validates(schema):
    # A row lacking all three fields (frozen v0.1 shape) stays valid: they are
    # optional, NOT required. The additive guarantee is held at the schema layer.
    row = dict(_FULL_ROW)
    for field in ("annualized_funding_24h", "annualized_funding_7d", "annualized_funding_30d"):
        del row[field]
    jsonschema.validate(_snapshot_with(row), schema)


# =========================================================================
# Authentic captured multi-week public sample — grounds the contract amendment.
# reports/api-samples/2026-07-funding-annualized-history-v1/<stamp>/raw/
# fapi-v1-fundingRate-BTCUSDT-limit1000.json — captured live (no API key) on
# 2026-07-10 with the exact deep-history request shape the service sends.
# =========================================================================
def _real_btcusdt_entries():
    base = REPO_ROOT / "reports/api-samples/2026-07-funding-annualized-history-v1"
    candidates = sorted(base.glob("*/raw/fapi-v1-fundingRate-BTCUSDT-limit1000.json"))
    assert candidates, (
        "raw BTCUSDT deep-history sample missing under "
        "reports/api-samples/2026-07-funding-annualized-history-v1/"
    )
    return json.loads(candidates[-1].read_text())


def test_real_btcusdt_sample_processes_through_pipeline(schema):
    entries = _real_btcusdt_entries()
    assert len(entries) >= 50            # multi-week: 8h cadence -> ~90 in 30d
    t_end = max(e["fundingTime"] for e in entries)
    rows = build_rows([_SYM], {"BTCUSDT": {"lastFundingRate": "0.00010000"}}, {},
                       {"BTCUSDT": entries}, t_end_ms=t_end)
    row = rows[0]
    # all three annualized fields are 8-place decimal strings on the real data
    for key in ("annualized_funding_24h", "annualized_funding_7d", "annualized_funding_30d"):
        assert isinstance(row[key], str)
        assert row[key] == format(Decimal(row[key]).quantize(Decimal("1E-8")), "f")
    # funding_history newest-first, filtered to the inclusive 30-day window
    times = [e["funding_time"] for e in row["funding_history"]]
    assert times == sorted(times, reverse=True)
    assert all(t_end - 30 * DAY <= t <= t_end for t in times)
    # end-to-end schema validity
    snap = assemble_snapshot(rows, generated_at="2026-07-10T00:00:00Z",
                             data_time="2026-07-10T00:00:00Z",
                             source_sample_id="real-btcusdt-deep-history")
    jsonschema.validate(snap, schema)
