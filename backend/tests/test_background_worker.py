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
# Split-seam stubs (2026-07-cache-refresh-scheduler-v2 §7.1): the legacy
# _StubPublic / _StubPrivate above stay on the fetch_raw fallback path and keep
# the existing endpoint tests green. These expose the Group A / Group B live
# seams and the enabled private channel so the three-cadence scheduler can be
# exercised directly.
# =========================================================================
class _SeamStubPublic:
    """Public client exposing fetch_premium_index / fetch_exchange_info_group_b
    so the scheduled path exercises the independent Group A (60s) / Group B
    (1800s) cadences. Derived from self._raw so callers can still mutate
    client._raw between ticks. Optional fail_premium / fail_group_b raise OSError
    to assert CC-1 source independence + FR-2 no-cache-on-failure."""
    offline = False

    def __init__(self, raw, history_fn=None, *, fail_premium=False, fail_group_b=False):
        self._raw = raw
        self._history_fn = history_fn or (lambda s, **kw: [])
        self._fail_premium = fail_premium
        self._fail_group_b = fail_group_b
        self.premium_calls = 0
        self.group_b_calls = 0
        self.raw_calls = 0
        self.ticker_calls = 0
        self.history_calls: list = []

    def fetch_raw(self):
        self.raw_calls += 1
        return self._raw

    def fetch_premium_index(self):
        self.premium_calls += 1
        if self._fail_premium:
            raise OSError("premium upstream down")
        return self._raw["premium_index"]

    def fetch_exchange_info_group_b(self):
        self.group_b_calls += 1
        if self._fail_group_b:
            raise OSError("group_b upstream down")
        return {
            "futures_exchange_info": self._raw["futures_exchange_info"],
            "spot_exchange_info": self._raw["spot_exchange_info"],
            "funding_interval_by_sym": self._raw.get("funding_interval_by_sym", {}),
            "warnings": self._raw.get("warnings", []),
        }

    def fetch_funding_rate(self, symbol, *, start_time_ms=None, end_time_ms=None, limit=1000):
        self.history_calls.append(symbol)
        return self._history_fn(symbol, start_time_ms=start_time_ms,
                                end_time_ms=end_time_ms, limit=limit)

    def fetch_premium_index_for(self, symbol):
        return {}

    def fetch_ticker_price_map(self):
        self.ticker_calls += 1
        return {}


class _SeamStubPrivate:
    """Enabled read-only private stub for the §7.1 narrow-seam (INV-1b)
    invariants: every endpoint is counted so tests can assert the scheduled
    borrow path uses ONLY fetch_next_hourly_rates /
    fetch_interest_rate_history_latest / fetch_max_borrowable and NEVER
    fetch_cost_leg_chain (FR-3). classic_ref non-None => channel usable so the
    FR-4 homepage borrow universe is computed."""

    def __init__(self, *, classic_ref=None, account_info=None,
                 next_hourly=None, rate_history=None, max_borrowable=None):
        self.last_error = None if classic_ref is not None else "private_channel_disabled"
        self.enabled = classic_ref is not None
        self._classic_ref = classic_ref
        self._account_info = account_info
        self._next_hourly = next_hourly or {}        # {asset: raw_hourly_str|None}
        self._rate_history = rate_history or {}      # {asset: daily_str|None}
        self._max_borrowable = max_borrowable or {}  # {asset: dict|None}
        self.classic_calls = 0
        self.account_info_calls = 0
        self.next_hourly_calls: list = []   # list of asset-list args
        self.rate_history_calls: list = []
        self.max_borrowable_calls: list = []
        self.balance_calls = 0
        self.position_calls = 0
        self.spot_calls = 0
        self.cost_leg_calls: list = []

    def fetch_classic_reference(self):
        self.classic_calls += 1
        return self._classic_ref

    def fetch_account_info(self):
        self.account_info_calls += 1
        return self._account_info

    def fetch_next_hourly_rates(self, assets):
        self.next_hourly_calls.append(list(assets))
        return {a: self._next_hourly.get(a) for a in assets}

    def fetch_interest_rate_history_latest(self, asset):
        self.rate_history_calls.append(asset)
        return self._rate_history.get(asset)

    def fetch_max_borrowable(self, asset, *, force=False):
        self.max_borrowable_calls.append(asset)
        return self._max_borrowable.get(asset)

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


def _seam_service(
    raw, *, history_fn=None, classic_ref=None, account_info=None,
    next_hourly=None, rate_history=None, max_borrowable=None,
    fail_premium=False, fail_group_b=False, **cfg,
):
    service = SnapshotService(Config(offline=False, **cfg))
    service.client = _SeamStubPublic(
        raw, history_fn, fail_premium=fail_premium, fail_group_b=fail_group_b,
    )
    service._private = _SeamStubPrivate(
        classic_ref=classic_ref, account_info=account_info,
        next_hourly=next_hourly, rate_history=rate_history,
        max_borrowable=max_borrowable,
    )
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


# =========================================================================
# Stage 2026-07-cache-refresh-scheduler-v2: three-cadence scheduler (§7.1).
# Group A (60s) / Group B (1800s) independent cadences, CC-1 per-source due,
# CC-4 next-hourly x24 normalization, FR-4 strict borrow predicate, FR-5 no
# top-50 cap, FR-7 component independence, FR-2 no-cache-on-failure, INV-1b
# narrow-seam isolation, CC-3 cursor-attempt coverage.
# =========================================================================
def test_split_seams_refresh_on_independent_cadences(monkeypatch):
    # Group A premium follows cache_ttl_seconds (60s); Group B public follows
    # the fixed GROUP_B_REFRESH_SECONDS (1800s). The split seams mean the
    # scheduled path NEVER calls fetch_raw.
    t = [0.0]
    monkeypatch.setattr(snapshot_service.time, "monotonic", lambda: t[0])
    service = _seam_service(_raw(_BTC), cache_ttl_seconds=60)
    service._scheduled_tick()                 # t=0: both due -> bootstrap
    assert service.client.premium_calls == 1
    assert service.client.group_b_calls == 1
    assert service.client.raw_calls == 0      # split seams, no fetch_raw
    t[0] = 30.0
    service._scheduled_tick()                 # neither due (A<60, B<1800)
    assert service.client.premium_calls == 1
    assert service.client.group_b_calls == 1
    t[0] = 61.0
    service._scheduled_tick()                 # A due, B still fresh
    assert service.client.premium_calls == 2
    assert service.client.group_b_calls == 1
    t[0] = 1801.0
    service._scheduled_tick()                 # both due
    assert service.client.premium_calls == 3
    assert service.client.group_b_calls == 2


def test_one_public_source_failure_does_not_suppress_the_other(monkeypatch):
    # CC-1: each source_id owns its own due timestamp. premium failing does NOT
    # suppress group_b's success, and the failure is NOT cached (FR-2).
    t = [0.0]
    monkeypatch.setattr(snapshot_service.time, "monotonic", lambda: t[0])
    service = _seam_service(_raw(_BTC), cache_ttl_seconds=60, fail_premium=True)
    service._scheduled_tick()                 # t=0: both due; premium raises
    assert service.client.premium_calls == 1
    assert service.client.group_b_calls == 1
    assert "group_b_public" in service._global_source_cache
    assert "premium_index" not in service._global_source_cache  # FR-2
    assert service._published_state is None   # base_raw needs BOTH sources
    service.client._fail_premium = False
    t[0] = 61.0
    service._scheduled_tick()                 # premium retries; group_b cached
    assert service.client.premium_calls == 2
    assert service.client.group_b_calls == 1  # NOT re-fetched (CC-1)
    assert service._published_state is not None


def test_fr4_predicate_strict_threshold():
    # FR-4: scheduled-borrow predicate is strictly < -0.00030000 (not the
    # select_borrow_candidates < 0), gated on route_class + asset_tag + a usable
    # private channel.
    service = _seam_service(_raw(_BTC), classic_ref={})

    def cand(rate, route="MARGIN_SPOT_CANDIDATE", tag="CRYPTO"):
        return service._is_scheduled_borrow_candidate(
            {"daily_funding_rate": rate, "route_class": route, "asset_tag": tag}, {}
        )

    assert cand("-0.00030001") is True        # strictly below the boundary
    assert cand("-0.00030000") is False        # at the boundary (strict <)
    assert cand("-0.00029999") is False        # above the boundary
    assert cand("0.00050000") is False         # positive funding
    assert cand("-0.00060000", route="PERP_ONLY_EXCLUDED") is False
    assert cand("-0.00060000", tag="BSTOCK") is False
    # classic_ref None -> channel unusable -> never a scheduled candidate
    disabled = _seam_service(_raw(_BTC))
    assert disabled._is_scheduled_borrow_candidate(
        {"daily_funding_rate": "-0.00060000", "route_class": "MARGIN_SPOT_CANDIDATE",
         "asset_tag": "CRYPTO"}, None
    ) is False


def test_next_hourly_normalized_x24_exactly_once():
    # CC-4: the raw next-hourly value is normalized to a daily rate (x24) exactly
    # once inside resolve_cost_leg_rate, not on storage and not again on resolve.
    syms = [("BTCUSDT", "BTC", "-0.00020000")]
    service = _seam_service(
        _raw(syms), classic_ref={}, next_hourly={"BTC": "0.00000500"},
        max_borrowable={"BTC": {"max_borrowable": "1", "borrow_limit": "1",
                                 "error_code": None}},
        history_fn=lambda s, **kw: [],
    )
    service._scheduled_tick()
    # stored raw hourly 0.00000500; resolved daily = 0.00000500 * 24 = 0.00012000
    daily, source = service._resolve_borrow_rate_for_asset("BTC", {}, None)
    assert daily == "0.00012000"
    assert source == "next_hourly"


def test_borrow_rate_falls_back_to_cross_margin_tier():
    # S5 priority ③: no next_hourly / rate_history -> cross_margin_tier[vip_level]
    # from the Group B classic reference (Group C never re-fetches Group B).
    classic_ref = {"cross_margin_daily_by_vip": {"1": {"BTC": "0.00007000"}}}
    service = _seam_service(_raw(_BTC), classic_ref=classic_ref)
    daily, source = service._resolve_borrow_rate_for_asset("BTC", classic_ref, "1")
    assert daily == "0.00007000"
    assert source == "cross_margin_tier"


def test_borrow_rate_falls_back_to_vip0_reference():
    # S5 priority ④: vip_level not in the cross table -> vip0_reference (cross["0"])
    classic_ref = {"cross_margin_daily_by_vip": {"0": {"BTC": "0.00008000"}}}
    service = _seam_service(_raw(_BTC), classic_ref=classic_ref)
    daily, source = service._resolve_borrow_rate_for_asset("BTC", classic_ref, None)
    assert daily == "0.00008000"
    assert source == "vip0_reference"


def test_history_and_borrow_components_tracked_independently():
    # FR-7: history / borrow-rate / max-borrowable are freshness-independent.
    # Once cached (< component TTL), a second tick re-fetches none of them.
    syms = [("BTCUSDT", "BTC", "-0.00020000")]
    service = _seam_service(
        _raw(syms), classic_ref={}, next_hourly={"BTC": "0.00000500"},
        max_borrowable={"BTC": {"max_borrowable": "1", "borrow_limit": "1",
                                 "error_code": None}},
        history_fn=lambda s, **kw: _fixture("seven-day-flat.json"),
        cache_ttl_seconds=60,
    )
    service._scheduled_tick()                 # t=0: history + borrow + max fetched
    assert "BTCUSDT" in service._funding_history_cache
    assert "BTC" in service._borrow_rate_cache
    assert "BTC" in service._max_borrowable_cache
    service._scheduled_tick()                 # all three still fresh -> no re-fetch
    assert service.client.history_calls.count("BTCUSDT") == 1
    assert len(service._private.next_hourly_calls) == 1
    assert service._private.max_borrowable_calls.count("BTC") == 1


def test_failed_borrow_rate_is_not_cached():
    # FR-2: a borrow rate that resolves to nothing is NOT cached, so it retries
    # when next due. Both narrow seams are still attempted (INV-1b fallback).
    syms = [("BTCUSDT", "BTC", "-0.00020000")]
    service = _seam_service(
        _raw(syms), classic_ref={}, next_hourly={"BTC": None},
        rate_history={}, max_borrowable={"BTC": {"max_borrowable": "1",
                                                  "borrow_limit": "1",
                                                  "error_code": None}},
        history_fn=lambda s, **kw: [],
    )
    service._scheduled_tick()
    assert "BTC" not in service._borrow_rate_cache
    assert service._private.next_hourly_calls == [["BTC"]]
    assert service._private.rate_history_calls == ["BTC"]


def test_scheduled_borrow_uses_narrow_seam_only():
    # INV-1b: the scheduled borrow path uses fetch_next_hourly_rates and NEVER
    # fetch_cost_leg_chain (the all-row chain is a click-only / FR-3 path).
    syms = [("BTCUSDT", "BTC", "-0.00020000")]
    service = _seam_service(
        _raw(syms), classic_ref={}, next_hourly={"BTC": "0.00000500"},
        max_borrowable={"BTC": {"max_borrowable": "1", "borrow_limit": "1",
                                 "error_code": None}},
        history_fn=lambda s, **kw: [],
    )
    service._scheduled_tick()
    assert service._private.next_hourly_calls == [["BTC"]]
    assert service._private.cost_leg_calls == []


def test_no_top50_cap_on_scheduled_borrow_path():
    # FR-5: borrow_check_max_calls no longer truncates the scheduled borrow path.
    # 60 FR-4 assets in one tick (batch_size=60) -> all 60 max-borrowable attempts.
    syms = [("A%02dUSDT" % i, "A%02d" % i, "-0.00020000") for i in range(60)]
    service = _seam_service(
        _raw(syms), classic_ref={}, history_fn=lambda s, **kw: [],
        history_sweep_batch_size=60, borrow_check_max_calls=50,
    )
    service._scheduled_tick()
    assert len(service._coverage_attempted) == 60
    assert len(service._private.max_borrowable_calls) == 60


def test_coverage_attempted_counts_failures_and_advances_with_cursor():
    # CC-3: a failed max-borrowable attempt still counts as coverage; the cursor
    # advances so a later tick reaches the remaining universe asset.
    syms = [("AUSDT", "A", "-0.00020000"), ("BUSDT", "B", "-0.00020000"),
            ("CUSDT", "C", "-0.00020000")]
    service = _seam_service(
        _raw(syms), classic_ref={},
        max_borrowable={
            "A": None,  # fails -> attempted but NOT cached (FR-2)
            "B": {"max_borrowable": "1", "borrow_limit": "1", "error_code": None},
        },
        history_fn=lambda s, **kw: [], history_sweep_batch_size=2,
    )
    service._scheduled_tick()                 # cursor covers [A, B]
    assert service._coverage_attempted == {"A", "B"}
    assert "A" not in service._max_borrowable_cache
    assert "B" in service._max_borrowable_cache
    service._scheduled_tick()                 # cursor advances to C
    assert "C" in service._coverage_attempted


def _published_coverage(service) -> dict:
    return service._published_state.snapshot["borrow_validation"]["coverage"]


def test_coverage_ledger_prunes_on_universe_exit(monkeypatch):
    # CC-3 / INV-4: an asset that exits the homepage borrow universe must be
    # removed from the _coverage_attempted ledger (not just masked at read time),
    # so the externally-assembled coverage reflects probed=0 for an empty
    # universe. Verified against BOTH the actual ledger and the published
    # borrow_validation_summary.coverage.
    t = [0.0]
    monkeypatch.setattr(snapshot_service.time, "monotonic", lambda: t[0])
    service = _seam_service(
        _raw([("BTCUSDT", "BTC", "-0.00020000")]), classic_ref={},
        max_borrowable={"BTC": {"max_borrowable": "1", "borrow_limit": "1",
                                 "error_code": None}},
        history_fn=lambda s, **kw: [],
    )
    service._scheduled_tick()                 # BTC is FR-4 -> cursor attempts it
    assert service._coverage_attempted == {"BTC"}              # actual ledger
    assert _published_coverage(service) == {
        "probed": 1, "skipped": 0, "reason": None,
    }
    # BTC exits: rate crosses above -0.00030000 -> no longer an FR-4 candidate.
    service.client._raw = _raw([("BTCUSDT", "BTC", "-0.00005000")])  # daily -0.00015
    t[0] = 61.0                               # premium (60s) due -> re-fetch new rate
    service._scheduled_tick()
    assert service._coverage_attempted == set()                # pruned, not masked
    assert _published_coverage(service) == {
        "probed": 0, "skipped": 0, "reason": None,
    }


def test_coverage_reentry_starts_unattempted(monkeypatch):
    # CC-3: re-entry starts unattempted. After exit/prune, a re-entering asset
    # is NOT probed until a real scheduled max-borrowable attempt. While the
    # max-borrowable component is still fresh, a cursor-only pass is not a new
    # attempt (ledger stays empty) -> coverage reports skipped=1.
    t = [0.0]
    monkeypatch.setattr(snapshot_service.time, "monotonic", lambda: t[0])
    service = _seam_service(
        _raw([("BTCUSDT", "BTC", "-0.00020000")]), classic_ref={},
        max_borrowable={"BTC": {"max_borrowable": "1", "borrow_limit": "1",
                                 "error_code": None}},
        history_fn=lambda s, **kw: [],
    )
    service._scheduled_tick()                 # BTC attempted at t=0
    assert service._coverage_attempted == {"BTC"}
    service.client._raw = _raw([("BTCUSDT", "BTC", "-0.00005000")])  # exit
    t[0] = 61.0                               # premium due -> re-fetch exit rate
    service._scheduled_tick()                 # prune -> ledger empty
    assert service._coverage_attempted == set()
    service.client._raw = _raw([("BTCUSDT", "BTC", "-0.00020000")])  # re-enter
    t[0] = 122.0                              # premium due -> re-fetch negative rate
    pre = service._private.max_borrowable_calls.count("BTC")
    service._scheduled_tick()                 # cursor passes but max fresh -> no attempt
    assert service._coverage_attempted == set()                # re-entry unattempted
    assert service._private.max_borrowable_calls.count("BTC") == pre
    assert _published_coverage(service) == {
        "probed": 0, "skipped": 1, "reason": "rate_limit_budget",
    }


def test_coverage_reason_rate_limit_budget_iff_skipped(monkeypatch):
    # CC-3: reason == "rate_limit_budget" iff skipped > 0 (current universe).
    t = [0.0]
    monkeypatch.setattr(snapshot_service.time, "monotonic", lambda: t[0])
    syms = [("AUSDT", "A", "-0.00020000"), ("BUSDT", "B", "-0.00020000")]
    service = _seam_service(
        _raw(syms), classic_ref={},
        max_borrowable={"A": {"max_borrowable": "1", "borrow_limit": "1",
                              "error_code": None},
                        "B": {"max_borrowable": "1", "borrow_limit": "1",
                              "error_code": None}},
        history_fn=lambda s, **kw: [], history_sweep_batch_size=1,
    )
    service._scheduled_tick()                 # cursor covers 1 of 2 -> B skipped
    assert _published_coverage(service)["reason"] == "rate_limit_budget"
    service._scheduled_tick()                 # cursor reaches B -> none skipped
    assert _published_coverage(service)["reason"] is None


def test_global_source_cache_stamps_completion_time(monkeypatch):
    # FR-2/INV-5: every _global_source_cache success write captures
    # time.monotonic() AFTER the fetch returns (completion), not the pre-fetch
    # tick now. Under a strictly-increasing clock the Group B classic, Group B
    # account_info, and Group A price_map stamps must all exceed the tick-now
    # read and reflect fetch order (each is its own completion stamp).
    n = [0]

    def monotonic():
        n[0] += 1
        return n[0] * 1.0

    monkeypatch.setattr(snapshot_service.time, "monotonic", monotonic)
    service = _seam_service(_raw(_BTC), classic_ref={}, account_info={"vipLevel": 1})
    service._scheduled_tick()
    cache = service._global_source_cache
    # tick now = call #1 (1.0); every success write is a later call -> > 1.0
    assert cache["classic_reference"][0] > 1.0
    assert cache["account_info"][0] > 1.0
    assert cache["price_map"][0] > 1.0
    # per-source completion stamps reflect fetch order (classic -> account ->
    # price_map), proving each source owns its own completion-time timestamp.
    assert (
        cache["classic_reference"][0]
        < cache["account_info"][0]
        < cache["price_map"][0]
    )
