"""Background-worker lifecycle, cadence, selector, and cache tests
(2026-07-history-background-refresh-v1, breakdown §12).

Covers the serial single-writer invariant: the worker thread owns every domain
cache write (``_base_raw``, ``_funding_history_cache``, ``_last_private_inputs``)
and the single publication. HTTP request threads only submit commands / read the
published state. No network: a fake public client is injected and the worker is
exercised via direct ``_scheduled_tick()`` calls (the same entrypoint the worker
loop calls); lifecycle cases drive the real thread.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from backend.config import Config
from backend.domain.snapshot import default_view_history_symbols
from backend.services import snapshot_service
from backend.services.snapshot_service import (
    PublishedState,
    RefreshSymbolCommand,
    SnapshotService,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIX_DIR = REPO_ROOT / "backend/tests/fixtures/funding-history"

T_END = 1783641600000
DAY = 86_400_000


def _fixture(name: str) -> list:
    return json.loads((FIX_DIR / name).read_text())


def _raw(symbols):
    """Raw public inputs; each row carries a spot leg -> MARGIN_SPOT_CANDIDATE."""
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
    offline = False

    def __init__(self, raw, history_fn=None):
        self._raw = raw
        self._history_fn = history_fn or (lambda s, **kw: [])
        self.history_calls: list = []
        self.raw_calls = 0
        self.premium_calls = 0
        self.ticker_calls = 0

    def fetch_raw(self):
        self.raw_calls += 1
        return self._raw

    def fetch_funding_rate(self, symbol, *, start_time_ms=None, end_time_ms=None, limit=1000):
        self.history_calls.append(symbol)
        return self._history_fn(symbol, start_time_ms=start_time_ms,
                                end_time_ms=end_time_ms, limit=limit)

    def fetch_premium_index_for(self, symbol):
        self.premium_calls += 1
        return {}

    def fetch_ticker_price_map(self):
        self.ticker_calls += 1
        return {}


class _StubPrivate:
    def __init__(self):
        self.last_error = "private_channel_disabled"
        self.balance_calls = 0
        self.position_calls = 0
        self.spot_calls = 0
        self.cost_leg_calls: list = []
        self.max_borrowable_calls: list = []

    def fetch_classic_reference(self):
        return None

    def fetch_cost_leg_chain(self, assets, *, force=False):
        self.cost_leg_calls.append((list(assets), force))
        return None

    def fetch_unified_balances(self):
        self.balance_calls += 1
        return None

    def fetch_um_positions(self):
        self.position_calls += 1
        return None

    def fetch_spot_balances(self):
        self.spot_calls += 1
        return None

    def fetch_max_borrowable(self, asset, *, force=False):
        self.max_borrowable_calls.append((asset, force))
        return None


def _service(raw, history_fn=None, **cfg):
    service = SnapshotService(Config(offline=False, **cfg))
    service.client = _StubPublic(raw, history_fn)
    service._private = _StubPrivate()
    return service


# =========================================================================
# Lifecycle: construct has no thread; start idempotent; stop timely;
# offline / kill-switch-off never start a worker.
# =========================================================================
def test_construction_has_no_worker_thread():
    service = _service(_raw(_BTC))
    assert service._worker_thread is None
    assert service._worker_running() is False


def test_start_is_idempotent_and_stop_clears_thread():
    service = _service(_raw(_BTC), background_tick_seconds=60)
    service.start_worker()
    assert service._worker_running() is True
    thread = service._worker_thread
    # a second start must not spawn a second thread (idempotent)
    service.start_worker()
    assert service._worker_thread is thread
    service.stop_worker()
    assert service._worker_thread is None
    assert service._worker_running() is False


def test_offline_mode_never_starts_worker():
    # Real offline service (offline client): start_worker is a documented no-op.
    service = SnapshotService(Config(offline=True))
    service.start_worker()
    assert service._worker_thread is None
    assert service._worker_running() is False


def test_kill_switch_off_never_starts_worker():
    service = _service(_raw(_BTC), background_refresh_enabled=False)
    service.start_worker()
    assert service._worker_thread is None
    assert service._worker_running() is False


def test_stop_without_start_is_safe():
    service = _service(_raw(_BTC))
    # stop before any start must not raise and leaves no thread.
    service.stop_worker()
    assert service._worker_thread is None


# =========================================================================
# Cadence: base re-fetched only after cache_ttl_seconds (>=60s default);
# sweep fetches <= history_sweep_batch_size per tick; the rolling cursor is
# stable and does not skip symbols across ticks.
# =========================================================================
def test_base_raw_refreshed_only_after_cache_ttl(monkeypatch):
    t = [0.0]
    monkeypatch.setattr(snapshot_service.time, "monotonic", lambda: t[0])
    service = _service(_raw(_BTC), cache_ttl_seconds=60)
    service._scheduled_tick()                 # bootstrap fetch at t=0
    assert service.client.raw_calls == 1
    t[0] = 30.0
    service._scheduled_tick()                 # base still fresh -> no refetch
    assert service.client.raw_calls == 1
    t[0] = 61.0
    service._scheduled_tick()                 # 61s elapsed -> refetch
    assert service.client.raw_calls == 2


def test_sweep_fetches_at_most_batch_size_per_tick():
    syms = [("S%02dUSDT" % i, "S%02d" % i, "0.00100000") for i in range(15)]
    service = _service(_raw(syms), history_fn=lambda s, **kw: [],
                       history_sweep_batch_size=10)
    service._scheduled_tick()
    # 15 default-view candidates, but only 10 fetched on the first tick.
    assert len(service.client.history_calls) == 10


def test_cursor_advances_across_ticks_without_skipping():
    # 15 candidates, batch 10. Tick 1 fetches [0..9]; tick 2 the cursor has
    # advanced to 10, so it fetches the remaining [10..14] (the first ten are
    # now fresh in the cache and skipped by _history_is_fresh).
    syms = [("S%02dUSDT" % i, "S%02d" % i, "0.00100000") for i in range(15)]
    service = _service(_raw(syms), history_fn=lambda s, **kw: [],
                       history_sweep_batch_size=10)
    service._scheduled_tick()
    tick1 = set(service.client.history_calls)
    service._scheduled_tick()
    tick2 = set(service.client.history_calls) - tick1
    # cursor advanced past the first batch; the second tick served [10..14]
    assert tick2 == {"S10USDT", "S11USDT", "S12USDT", "S13USDT", "S14USDT"}
    # union of both ticks covers the whole candidate set (no skip)
    assert tick1 | (set(service.client.history_calls) - tick1) == {
        "S%02dUSDT" % i for i in range(15)
    }


def test_cursor_wraps_around_on_a_shrinking_candidate_set(monkeypatch):
    # Candidate list shrinks between ticks; cursor mod-n must still not skip.
    t = [0.0]
    monkeypatch.setattr(snapshot_service.time, "monotonic", lambda: t[0])
    syms = [("S%02dUSDT" % i, "S%02d" % i, "0.00100000") for i in range(12)]
    service = _service(_raw(syms), history_fn=lambda s, **kw: [],
                       history_sweep_batch_size=10, cache_ttl_seconds=60)
    service._scheduled_tick()               # cursor -> 10 (fetched [0..9])
    assert service._history_cursor == 10
    calls_after_tick1 = len(service.client.history_calls)
    # shrink the universe to 4 symbols and advance the clock past the base TTL
    # so the base is re-fetched (the worker reads its cached _base_raw, not the
    # client attribute). cursor (10) mod 4 == 2 -> starts at idx 2.
    service.client._raw = _raw(syms[:4])
    service._funding_history_cache.clear()  # force fresh fetches this tick
    t[0] = 61.0
    service._scheduled_tick()
    tick2_new = service.client.history_calls[calls_after_tick1:]
    # cursor wrapped mod-4; every remaining candidate was served (4 <= batch 10)
    assert set(tick2_new) == {"S00USDT", "S01USDT", "S02USDT", "S03USDT"}
    assert len(tick2_new) <= 10


# =========================================================================
# Default-view selector parity (10-design §3.1 / breakdown §12)
# =========================================================================
def test_selector_parity_vector():
    def selected(daily, route="MARGIN_SPOT_CANDIDATE"):
        rows = [{"symbol": "XUSDT", "route_class": route,
                 "daily_funding_rate": daily}]
        return default_view_history_symbols(rows)

    # strictly greater than 0.00030000 -> prewarmed
    assert selected("0.00030001") == ["XUSDT"]
    assert selected("-0.00030001") == ["XUSDT"]
    # at or below the boundary (both signs) -> NOT prewarmed
    assert selected("0.00029999") == []
    assert selected("0.00030000") == []
    assert selected("-0.00030000") == []
    # null / empty / non-numeric -> NOT prewarmed (visible but not prewarmed)
    assert selected(None) == []
    assert selected("") == []
    assert selected("not-a-number") == []
    # PERP_ONLY_EXCLUDED never prewarmed regardless of rate
    assert selected("0.00100000", "PERP_ONLY_EXCLUDED") == []


def test_selector_preserves_row_order_for_stable_cursor():
    rows = [
        {"symbol": "AUSDT", "route_class": "MARGIN_SPOT_CANDIDATE", "daily_funding_rate": "0.001"},
        {"symbol": "BUSDT", "route_class": "MARGIN_SPOT_CANDIDATE", "daily_funding_rate": "0.002"},
        {"symbol": "CUSDT", "route_class": "PERP_ONLY_EXCLUDED", "daily_funding_rate": "0.009"},
        {"symbol": "DUSDT", "route_class": "MARGIN_SPOT_CANDIDATE", "daily_funding_rate": None},
    ]
    assert default_view_history_symbols(rows) == ["AUSDT", "BUSDT"]


# =========================================================================
# all-valid-cache merge: only unexpired successful entries are published
# =========================================================================
def test_all_valid_history_merges_only_unexpired_entries():
    service = _service(_raw(_BTC))
    now = time.monotonic()
    ttl = service.config.funding_history_cache_ttl_seconds
    good = [{"fundingTime": T_END, "fundingRate": "0.0001"}]
    service._funding_history_cache["BTCUSDT"] = (now, good)
    service._funding_history_cache["ETHUSDT"] = (now - ttl - 1, [{"fundingTime": 1}])
    merged = service._all_valid_history()
    assert merged == {"BTCUSDT": good}


def test_scheduled_tick_publishes_merged_history_overlay():
    # Two eligible symbols above the boundary; one has cached history, the other
    # returns fresh entries from the sweep. The published rows carry BOTH.
    syms = [("BTCUSDT", "BTC", "0.00050000"), ("ETHUSDT", "ETH", "0.00050000")]
    service = _service(syms and _raw(syms), history_fn=lambda s, **kw: _fixture("seven-day-flat.json"))
    # pre-seed BTC history as an unexpired cache entry
    service._funding_history_cache["BTCUSDT"] = (
        time.monotonic(), _fixture("seven-day-flat.json")
    )
    service._scheduled_tick()
    rows = {r["symbol"]: r for r in service._published_state.snapshot["rows"]}
    assert len(rows["BTCUSDT"]["funding_history"]) == 7   # from the cache
    assert len(rows["ETHUSDT"]["funding_history"]) == 7   # from the sweep


# =========================================================================
# Per-symbol failure does not poison the cache and does not delete the
# already-published state.
# =========================================================================
def test_failed_history_fetch_is_not_cached():
    def _fail(symbol, **kw):
        raise OSError("upstream down")
    service = _service(_raw(_BTC), history_fn=_fail)
    result = service._fetch_history_for("BTCUSDT", T_END)
    assert result is None
    # the failure is NOT cached -> "BTCUSDT" is absent, not a None entry
    assert "BTCUSDT" not in service._funding_history_cache


def test_failed_symbol_does_not_block_other_symbols_or_delete_publish():
    syms = [("BTCUSDT", "BTC", "0.00050000"), ("ETHUSDT", "ETH", "0.00050000")]

    def hist(symbol, **kw):
        if symbol == "BTCUSDT":
            raise OSError("btc upstream down")
        return _fixture("seven-day-flat.json")

    service = _service(_raw(syms), history_fn=hist)
    service._scheduled_tick()                 # publishes a complete schema-valid snapshot
    state = service._published_state
    assert isinstance(state, PublishedState)
    assert state is service._published_state  # a publication happened
    rows = {r["symbol"]: r for r in state.snapshot["rows"]}
    # ETH succeeded and carries history; BTC failed and carries empty history,
    # but its row is still present (not deleted).
    assert len(rows["ETHUSDT"]["funding_history"]) == 7
    assert rows["BTCUSDT"]["funding_history"] == []
    # BTC's failure was not cached; ETH's success was.
    assert "BTCUSDT" not in service._funding_history_cache
    assert "ETHUSDT" in service._funding_history_cache


def test_published_version_is_monotonic_across_ticks():
    service = _service(_raw(_BTC), history_fn=lambda s, **kw: _fixture("seven-day-flat.json"))
    service._scheduled_tick()
    v1 = service._published_version
    service._scheduled_tick()
    v2 = service._published_version
    assert v2 == v1 + 1


# =========================================================================
# PublishedState immutability: a single reference swap; rows_by_symbol index
# =========================================================================
def test_publish_swaps_single_reference_and_indexes_rows():
    service = _service(_raw(_BTC), history_fn=lambda s, **kw: [])
    assert service._published_state is None
    service._scheduled_tick()
    state_a = service._published_state
    service._scheduled_tick()
    state_b = service._published_state
    assert state_a is not state_b          # a new immutable object per publish
    assert state_b.published_version == state_a.published_version + 1
    assert "BTCUSDT" in state_b.rows_by_symbol
