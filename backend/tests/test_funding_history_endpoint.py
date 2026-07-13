"""Legacy ``GET /api/public-market/funding-history`` — pure projection tests.

2026-07-history-background-refresh-v1 (breakdown §8): the endpoint degrades to a
PURE projection from the immutable ``PublishedState``. It performs ZERO upstream
fetch and ZERO cache write (the single-worker ownership invariant — no second
cache producer). The frontend click flow now uses ``symbol-snapshot``; this
endpoint remains for contract compatibility.

Status surface:
  400 ``invalid_symbol``       missing/malformed query symbol.
  404 ``symbol_not_found``     well-formed symbol not in the eligible published
                               rows.
  503 ``snapshot_not_ready``   worker not ready (before first base publication).
  200                           schema-valid ``public-market-funding-history/v1``
                               projected from the published row; ``available``
                               (non-empty history) or ``empty`` (present, empty).

No network: a fake public client is injected and the worker is exercised via a
direct ``_scheduled_tick()`` to publish a state, then the endpoint is asserted
to add no upstream calls and no cache writes.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from backend.config import Config
from backend.services.snapshot_service import SnapshotService

REPO_ROOT = Path(__file__).resolve().parents[2]
FIX_DIR = REPO_ROOT / "backend/tests/fixtures/funding-history"

# Snapshot premium-index time (ms) shared with the funding-history vectors.
T_END = 1783641600000
DAY = 86_400_000


def _fixture(name: str) -> list:
    return json.loads((FIX_DIR / name).read_text())


@pytest.fixture(scope="session")
def fh_schema() -> dict:
    return json.loads(
        (REPO_ROOT / "schemas/api/public-market/funding-history.schema.json").read_text()
    )


def _raw(symbols):
    """Build raw public inputs for a list of ``(symbol, base_asset, rate)`` rows.

    Each row is given a public spot/margin leg so its ``route_class`` is
    ``MARGIN_SPOT_CANDIDATE`` (not ``PERP_ONLY_EXCLUDED``, which the default-view
    selector excludes). Rates above the default-view prewarm boundary
    (abs(daily) > 0.00030000) are then selected by the worker's scheduled sweep,
    so the published row carries settled history for the projection tests.
    """
    syms, prem, spots = [], [], []
    for sym, base, rate in symbols:
        syms.append({"symbol": sym, "baseAsset": base, "quoteAsset": "USDT",
                     "contractType": "PERPETUAL", "status": "TRADING", "filters": []})
        prem.append({"symbol": sym, "lastFundingRate": rate, "markPrice": "1",
                     "indexPrice": "1", "nextFundingTime": T_END + 1, "time": T_END})
        spots.append({"symbol": sym, "status": "TRADING",
                      "isMarginTradingAllowed": True, "filters": []})
    return {
        "futures_exchange_info": {"symbols": syms},
        "premium_index": prem,
        "spot_exchange_info": {"symbols": spots},
        "funding_history_by_sym": {},
        "funding_interval_by_sym": {},
        "warnings": [],
    }


_BTC = [("BTCUSDT", "BTC", "0.00050000")]


class _StubPublic:
    """Records deep-history calls; returns canned entries."""

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

    def fetch_premium_index_for(self, symbol):
        return {}

    def fetch_ticker_price_map(self):
        return {}


class _StubPrivate:
    """Disabled private channel (classic_ref None -> no signed HTTP)."""

    def __init__(self):
        self.last_error = "private_channel_disabled"

    def fetch_classic_reference(self):
        return None

    def fetch_cost_leg_chain(self, assets, *, force=False):
        return None

    def fetch_unified_balances(self):
        return None

    def fetch_um_positions(self):
        return None

    def fetch_spot_balances(self):
        return None

    def fetch_max_borrowable(self, asset, *, force=False):
        return None


def _service(raw, history_fn=None, **cfg):
    service = SnapshotService(Config(offline=False, **cfg))
    service.client = _StubPublic(raw, history_fn)
    service._private = _StubPrivate()
    return service


# =========================================================================
# 400 invalid_symbol — validated before any state consultation
# =========================================================================
@pytest.mark.parametrize(
    "symbol",
    [None, "", "btcusdt", "BTC-USDT", "BTC USDT", "BTCUSDT!", "A" * 41],
)
def test_invalid_symbol_returns_400(symbol):
    service = _service(_raw(_BTC), lambda s, **kw: [])
    service._scheduled_tick()  # publish so 400 is the only reason to fail
    status, payload = service.get_funding_history(symbol)
    assert status == 400
    assert payload == {"error": "invalid_symbol"}


# =========================================================================
# 404 symbol_not_found — well-formed but not an eligible published row
# =========================================================================
def test_unknown_symbol_returns_404():
    service = _service(_raw(_BTC), lambda s, **kw: [])
    service._scheduled_tick()
    status, payload = service.get_funding_history("ETHUSDT")
    assert status == 404
    assert payload == {"error": "symbol_not_found"}


# =========================================================================
# 503 snapshot_not_ready — before the first base publication (live mode)
# =========================================================================
def test_not_ready_returns_503_before_first_publish():
    service = _service(_raw(_BTC), lambda s, **kw: [])
    # no _scheduled_tick -> _published_state is None
    status, payload = service.get_funding_history("BTCUSDT")
    assert status == 503
    assert payload == {"error": "snapshot_not_ready"}


# =========================================================================
# 200 available / empty — projected from the published row
# =========================================================================
def test_available_history_projects_from_published(fh_schema):
    service = _service(_raw(_BTC), lambda s, **kw: _fixture("seven-day-flat.json"))
    service._scheduled_tick()
    status, payload = service.get_funding_history("BTCUSDT")
    assert status == 200
    assert payload["schema_version"] == "public-market-funding-history/v1"
    assert payload["symbol"] == "BTCUSDT"
    assert payload["history_status"] == "available"
    assert payload["annualized_funding_7d"] == "0.03650000"
    assert payload["annualized_funding_30d"] == "0.00851667"
    # the endpoint does NOT return the current-period 24h estimate
    assert "annualized_funding_24h" not in payload
    jsonschema.validate(payload, fh_schema)


def test_empty_history_projects_from_published(fh_schema):
    service = _service(_raw(_BTC), lambda s, **kw: [])
    service._scheduled_tick()
    status, payload = service.get_funding_history("BTCUSDT")
    assert status == 200
    assert payload["history_status"] == "empty"
    assert payload["funding_history"] == []
    assert payload["annualized_funding_7d"] is None
    assert payload["annualized_funding_30d"] is None
    jsonschema.validate(payload, fh_schema)


# =========================================================================
# Pure projection — ZERO upstream fetch, ZERO cache write (breakdown §8/F2)
# =========================================================================
def test_endpoint_triggers_no_upstream_fetch_and_no_cache_write():
    service = _service(_raw(_BTC), lambda s, **kw: _fixture("seven-day-flat.json"))
    service._scheduled_tick()
    calls_before = list(service.client.calls)
    cache_before = dict(service._funding_history_cache)
    rate_calls_before = service.client.request_log["GET /fapi/v1/fundingRate"]
    # multiple endpoint reads must not fetch or write anything
    for _ in range(3):
        status, _ = service.get_funding_history("BTCUSDT")
        assert status == 200
    assert service.client.calls == calls_before
    assert service.client.request_log["GET /fapi/v1/fundingRate"] == rate_calls_before
    assert service._funding_history_cache == cache_before


def test_data_time_taken_from_published_state():
    service = _service(_raw(_BTC), lambda s, **kw: [])
    service._scheduled_tick()
    state = service._published_state
    _, payload = service.get_funding_history("BTCUSDT")
    assert payload["data_time"] == state.snapshot["data_time"]


# =========================================================================
# Non-default-view symbol still projects if its row was published (e.g. loaded
# by a prior click). Eligibility is "in the published rows", not "prewarmed".
# =========================================================================
def test_non_default_symbol_projects_when_present(fh_schema):
    # BBB rate 0.00010000 -> daily 0.0003 -> NOT > 0.0003 -> not prewarmed by
    # the selector. But it is still an eligible published row, so the endpoint
    # projects its (empty) history without any on-demand fetch.
    syms = [("BTCUSDT", "BTC", "0.00050000"), ("BBBUSDT", "BBB", "0.00010000")]
    service = _service(_raw(syms), lambda s, **kw: [])
    service._scheduled_tick()
    snap = service._published_state.snapshot
    assert {"BTCUSDT", "BBBUSDT"} <= {r["symbol"] for r in snap["rows"]}
    status, payload = service.get_funding_history("BBBUSDT")
    assert status == 200
    assert payload["history_status"] == "empty"
    jsonschema.validate(payload, fh_schema)
