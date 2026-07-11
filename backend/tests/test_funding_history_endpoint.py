"""Stage 2026-07-funding-annualized-history-v1 — Task C endpoint tests.

``GET /api/public-market/funding-history?symbol=<eligible-USDT-perpetual>`` is a
same-origin, public read-only selected-symbol settled-history view. The service
resolves the symbol against the current snapshot's eligible rows, takes the
settled-window end from that snapshot's ``data_time``, and reuses the existing
per-symbol 30-minute successful-result cache.

Status surface:
  400 ``invalid_symbol``       missing/malformed query symbol.
  404 ``symbol_not_found``     well-formed symbol not in the eligible snapshot.
  502 ``funding_history_unavailable`` snapshot unavailable or upstream
                                fundingRate failure (failure NOT cached).
  200                           schema-valid ``public-market-funding-history/v1``;
                                a successful empty window is
                                ``history_status: "empty"`` and IS cached.

No network: the public client is stubbed where the live deep-history path runs.
"""
from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import jsonschema
import pytest

from backend.config import Config
from backend.services.snapshot_service import SnapshotService

REPO_ROOT = Path(__file__).resolve().parents[2]
FIX_DIR = REPO_ROOT / "backend/tests/fixtures/funding-history"

# Snapshot premium-index time (ms) shared with the Task A vectors. The endpoint
# derives its window end from the snapshot, which is built from this time.
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
    """Build raw public inputs for a list of ``(symbol, base_asset, rate)`` rows."""
    syms, prem = [], []
    for sym, base, rate in symbols:
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


_BTC = [("BTCUSDT", "BTC", "0.00010000")]


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


def _service(raw, history_fn=None, **cfg):
    service = SnapshotService(Config(offline=False, **cfg))
    service.client = _StubPublic(raw, history_fn)
    service._private = _StubPrivate()
    return service


# =========================================================================
# 400 invalid_symbol — missing or malformed (no upstream call before validation)
# =========================================================================
@pytest.mark.parametrize(
    "symbol",
    [None, "", "btcusdt", "BTC-USDT", "BTC USDT", "BTCUSDT!", "A" * 41],
)
def test_invalid_symbol_returns_400(symbol):
    service = _service(_raw(_BTC), lambda s, **kw: [])
    status, payload = service.get_funding_history(symbol)
    assert status == 400
    assert payload == {"error": "invalid_symbol"}
    assert service.client.calls == []   # symbol validated before any HTTP


# =========================================================================
# 404 symbol_not_found — well-formed but not an eligible current snapshot row
# =========================================================================
def test_unknown_symbol_returns_404():
    service = _service(_raw(_BTC), lambda s, **kw: [])
    status, payload = service.get_funding_history("ETHUSDT")
    assert status == 404
    assert payload == {"error": "symbol_not_found"}
    # ETHUSDT is well-formed; the endpoint never makes an upstream call for it.
    assert all(c[0] != "ETHUSDT" for c in service.client.calls)


# =========================================================================
# 200 available — settled records present, schema-valid, no 24h estimate
# =========================================================================
def test_available_history_returns_200_and_schema_valid(fh_schema):
    service = _service(_raw(_BTC), lambda s, **kw: _fixture("seven-day-flat.json"))
    status, payload = service.get_funding_history("BTCUSDT")
    assert status == 200
    assert payload["schema_version"] == "public-market-funding-history/v1"
    assert payload["symbol"] == "BTCUSDT"
    assert payload["history_status"] == "available"
    assert payload["annualized_funding_7d"] == "0.03650000"
    assert payload["annualized_funding_30d"] == "0.00851667"
    # newest-first settled history
    times = [e["funding_time"] for e in payload["funding_history"]]
    assert times == sorted(times, reverse=True)
    # the endpoint does NOT return the current-period 24h estimate
    assert "annualized_funding_24h" not in payload
    jsonschema.validate(payload, fh_schema)


# =========================================================================
# 200 empty — successful fetch with no in-window records (distinct from failure)
# =========================================================================
def test_empty_window_returns_200_empty_and_null_annuals(fh_schema):
    service = _service(_raw(_BTC), lambda s, **kw: [])   # upstream returns []
    status, payload = service.get_funding_history("BTCUSDT")
    assert status == 200
    assert payload["history_status"] == "empty"
    assert payload["funding_history"] == []
    assert payload["annualized_funding_7d"] is None
    assert payload["annualized_funding_30d"] is None
    jsonschema.validate(payload, fh_schema)


# =========================================================================
# 502 funding_history_unavailable — upstream failure, NOT cached (retries)
# =========================================================================
def test_upstream_failure_returns_502_and_retries():
    # BBB is a non-top-N eligible row (AAA is preloaded); the endpoint fetches
    # BBB on demand, so its retry count is isolated from the top-N preload.
    syms = [("AAAUSDT", "AAA", "0.00050000"), ("BBBUSDT", "BBB", "0.00000001")]

    def hist(symbol, **kw):
        if symbol == "BBBUSDT":
            raise urllib.error.URLError("boom")
        return []

    service = _service(_raw(syms), hist, top_n=1)
    status, payload = service.get_funding_history("BBBUSDT")
    assert status == 502
    assert payload == {"error": "funding_history_unavailable"}
    status, payload = service.get_funding_history("BBBUSDT")
    assert status == 502
    # failure NOT cached -> every endpoint call retries the upstream fetch
    bbb_calls = [c for c in service.client.calls if c[0] == "BBBUSDT"]
    assert len(bbb_calls) == 2


def test_snapshot_unavailable_returns_502(monkeypatch):
    service = _service(_raw(_BTC), lambda s, **kw: [])

    def boom():
        raise RuntimeError("snapshot broken")

    monkeypatch.setattr(service, "get_snapshot", boom)
    status, payload = service.get_funding_history("BTCUSDT")
    assert status == 502
    assert payload == {"error": "funding_history_unavailable"}


# =========================================================================
# Cache reuse — successful results (incl. empty) cached within the 1800s TTL
# =========================================================================
def test_success_cached_within_ttl():
    service = _service(_raw(_BTC), lambda s, **kw: _fixture("seven-day-flat.json"))
    service.get_funding_history("BTCUSDT")
    service.get_funding_history("BTCUSDT")
    assert service.client.request_log["GET /fapi/v1/fundingRate"] == 1


def test_empty_success_cached_within_ttl():
    service = _service(_raw(_BTC), lambda s, **kw: [])
    service.get_funding_history("BTCUSDT")
    service.get_funding_history("BTCUSDT")
    assert service.client.request_log["GET /fapi/v1/fundingRate"] == 1


# =========================================================================
# Window boundary — reused from the snapshot data_time; exact request shape
# =========================================================================
def test_data_time_taken_from_snapshot():
    service = _service(_raw(_BTC), lambda s, **kw: [])
    snap = service.get_snapshot()
    _, payload = service.get_funding_history("BTCUSDT")
    assert payload["data_time"] == snap["data_time"]


def test_request_uses_snapshot_time_boundary():
    captured = {}

    def hist(symbol, *, start_time_ms, end_time_ms, limit):
        captured.update(symbol=symbol, start=start_time_ms, end=end_time_ms, limit=limit)
        return []

    service = _service(_raw(_BTC), hist)
    service.get_funding_history("BTCUSDT")
    assert captured["symbol"] == "BTCUSDT"
    assert captured["limit"] == 1000
    assert captured["end"] == T_END                       # snapshot data_time
    assert captured["start"] == T_END - 30 * DAY          # inclusive 30-day window


# =========================================================================
# No full-universe prefetch — a non-top-N eligible row is served on demand
# =========================================================================
def test_non_topn_symbol_served_on_demand(fh_schema):
    syms = [("AAAUSDT", "AAA", "0.00050000"), ("BBBUSDT", "BBB", "0.00000001")]
    service = _service(_raw(syms), lambda s, **kw: _fixture("seven-day-flat.json"), top_n=1)
    snap = service.get_snapshot()
    # build_snapshot preloaded only the top-1 (AAA, higher abs rate); BBB was not.
    assert [c[0] for c in service.client.calls] == ["AAAUSDT"]
    assert {"AAAUSDT", "BBBUSDT"} <= {r["symbol"] for r in snap["rows"]}
    # the endpoint still serves the non-preloaded eligible symbol on demand
    status, payload = service.get_funding_history("BBBUSDT")
    assert status == 200
    assert payload["history_status"] == "available"
    jsonschema.validate(payload, fh_schema)
    assert "BBBUSDT" in [c[0] for c in service.client.calls]
