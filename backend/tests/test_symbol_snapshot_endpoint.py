"""``GET /api/public-market/symbol-snapshot`` service contract tests
(2026-07-history-background-refresh-v1, breakdown §9 / §12).

The endpoint submits ONE ``RefreshSymbolCommand`` to the serial worker, waits
within the bounded shared deadline, then projects the selected row from the
LATEST published state (same ``published_version`` as the full snapshot). It
publishes a single ``row`` (no ``rows`` array). The click path reuses the last
private bundle and force-TTLs only the selected asset — it NEVER re-enters the
balance/position/valuation endpoints.

No network: a fake public client is injected; the worker is driven via direct
``_scheduled_tick()`` / ``_handle_refresh_command()`` calls (the same entrypoints
the worker loop uses), and a controllable monotonic clock drives the deadline
publication gate.
"""
from __future__ import annotations

import io
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import jsonschema
import pytest

from backend.config import Config
from backend.services import private_client, snapshot_service
from backend.services.private_client import PrivateClient
from backend.services.snapshot_service import (
    RefreshSymbolCommand,
    SnapshotService,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIX_DIR = REPO_ROOT / "backend/tests/fixtures/funding-history"

T_END = 1783641600000


def _fixture(name: str) -> list:
    return json.loads((FIX_DIR / name).read_text())


def _raw(symbols):
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
_BTC_SEVEN = lambda s, **kw: _fixture("seven-day-flat.json")  # noqa: E731


class _StubPublic:
    offline = False

    def __init__(self, raw, history_fn=None, premium_fn=None):
        self._raw = raw
        self._history_fn = history_fn or (lambda s, **kw: [])
        self._premium_fn = premium_fn or (lambda s: {})
        self.history_calls: list = []
        self.raw_calls = 0
        self.premium_calls = 0

    def fetch_raw(self):
        self.raw_calls += 1
        return self._raw

    def fetch_funding_rate(self, symbol, *, start_time_ms=None, end_time_ms=None, limit=1000):
        self.history_calls.append(symbol)
        return self._history_fn(symbol, start_time_ms=start_time_ms,
                                end_time_ms=end_time_ms, limit=limit)

    def fetch_premium_index_for(self, symbol):
        self.premium_calls += 1
        return self._premium_fn(symbol)

    def fetch_ticker_price_map(self):
        return {}


class _StubPrivate:
    def __init__(self):
        self.last_error = "private_channel_disabled"
        self.balance_calls = 0
        self.position_calls = 0
        self.spot_calls = 0
        self.cost_leg_calls: list = []
        self.max_borrowable_calls: list = []
        self.classic_calls = 0

    def fetch_classic_reference(self):
        self.classic_calls += 1
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


def _service(raw, history_fn=None, premium_fn=None, **cfg):
    service = SnapshotService(Config(offline=False, **cfg))
    service.client = _StubPublic(raw, history_fn, premium_fn)
    service._private = _StubPrivate()
    return service


@pytest.fixture(scope="module")
def schema() -> dict:
    """symbol-snapshot schema with the cross-file row $ref dereferenced against
    the canonical snapshot schema (so jsonschema can validate without a
    registry)."""
    import referencing
    ss = json.loads(
        (REPO_ROOT / "schemas/api/public-market/symbol-snapshot.schema.json").read_text()
    )
    snap = json.loads(
        (REPO_ROOT / "schemas/api/public-market/snapshot.schema.json").read_text()
    )
    registry = referencing.Registry().with_resource(
        snap["$id"], referencing.Resource.from_contents(snap)
    )
    return jsonschema.Draft202012Validator(ss, registry=registry)


# =========================================================================
# Shape: exactly one row, no rows array; schema-valid
# =========================================================================
def test_payload_is_single_row_no_rows_array(schema):
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN)
    service._scheduled_tick()
    status, payload = service.get_symbol_snapshot("BTCUSDT")
    assert status == 200
    assert "row" in payload and isinstance(payload["row"], dict)
    assert "rows" not in payload
    schema.validate(payload)


def test_row_identical_to_same_version_full_snapshot(schema):
    # The projected row is byte-identical to the same-version full snapshot's
    # row (single source of truth: the immutable PublishedState).
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN)
    service._scheduled_tick()
    status, payload = service.get_symbol_snapshot("BTCUSDT")
    assert status == 200
    full = service.get_snapshot()
    full_row = next(r for r in full["rows"] if r["symbol"] == "BTCUSDT")
    assert payload["row"] == full_row
    assert payload["published_version"] == service._published_version
    schema.validate(payload)


# =========================================================================
# Failure matrix: 400 / 404 / 503 / timeout / partial
# =========================================================================
@pytest.mark.parametrize("symbol", [None, "", "btcusdt", "BTC-USDT", "BTC USDT", "A" * 41])
def test_invalid_symbol_returns_400(symbol):
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN)
    service._scheduled_tick()
    status, payload = service.get_symbol_snapshot(symbol)
    assert status == 400
    assert payload == {"error": "invalid_symbol"}


def test_unknown_symbol_returns_404():
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN)
    service._scheduled_tick()
    status, payload = service.get_symbol_snapshot("ETHUSDT")
    assert status == 404
    assert payload == {"error": "symbol_not_found"}


def test_not_ready_returns_503_before_first_publish():
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN)
    # no _scheduled_tick -> _published_state is None
    status, payload = service.get_symbol_snapshot("BTCUSDT")
    assert status == 503
    assert payload == {"error": "snapshot_not_ready"}


def test_deadline_expired_yields_timeout_and_keeps_last_published(monkeypatch):
    # Case A: upstream I/O completes AFTER the shared deadline (simulated 31st
    # second). The worker may finish I/O, but commits no history/domain-cache
    # change and publishes NOTHING; the endpoint projects the last row.
    monkeypatch.setattr(snapshot_service.time, "monotonic", lambda: 1000.0)
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN)
    service._scheduled_tick()                      # publish v1 (sweep caches BTC history)
    v1 = service._published_version
    state_v1 = service._published_state
    cached_before = service._funding_history_cache.get("BTCUSDT")
    cmd = RefreshSymbolCommand("BTCUSDT", deadline_monotonic=999.0)  # already past
    service._handle_refresh_command(cmd)
    assert cmd.refresh_status == "timeout"
    assert service._published_version == v1        # NOT published
    assert service._published_state is state_v1    # same immutable reference
    # the expired command committed NOTHING: the history cache entry is the
    # same object the scheduled sweep wrote (not replaced by the fresh fetch)
    assert service._funding_history_cache.get("BTCUSDT") is cached_before


def test_deadline_within_window_publishes_exactly_once(monkeypatch):
    # Case B: I/O completes BEFORE the deadline -> exactly one new publication.
    monkeypatch.setattr(snapshot_service.time, "monotonic", lambda: 1000.0)
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN)
    service._scheduled_tick()                      # v1
    v1 = service._published_version
    cmd = RefreshSymbolCommand("BTCUSDT", deadline_monotonic=2000.0)  # future
    service._handle_refresh_command(cmd)
    assert cmd.refresh_status == "ok"
    assert service._published_version == v1 + 1    # exactly one new publication


def test_history_failure_yields_partial_status():
    def _fail(symbol, **kw):
        raise OSError("history upstream down")
    service = _service(_raw(_BTC), history_fn=_fail)
    service._scheduled_tick()
    cmd = RefreshSymbolCommand("BTCUSDT", deadline_monotonic=time.monotonic() + 30)
    service._handle_refresh_command(cmd)
    assert cmd.refresh_status == "partial"
    assert any("funding_history_unavailable" in w for w in cmd.warnings)


def test_premium_failure_yields_partial_status():
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN,
                       premium_fn=lambda s: (_ for _ in ()).throw(OSError("premium down")))
    service._scheduled_tick()
    cmd = RefreshSymbolCommand("BTCUSDT", deadline_monotonic=time.monotonic() + 30)
    service._handle_refresh_command(cmd)
    assert cmd.refresh_status == "partial"
    assert any("premium_refresh_failed" in w for w in cmd.warnings)


def test_assemble_failure_yields_timeout_and_keeps_last_published():
    # An assembly/validation failure after the gate must NOT publish; the last
    # published state survives. We force _assemble to raise by monkeypatching it.
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN)
    service._scheduled_tick()
    v1 = service._published_version

    def _boom(*a, **kw):
        raise ValueError("assemble failed")
    original = service._assemble
    service._assemble = _boom
    try:
        cmd = RefreshSymbolCommand("BTCUSDT", deadline_monotonic=time.monotonic() + 30)
        service._handle_refresh_command(cmd)
    finally:
        service._assemble = original
    assert cmd.refresh_status == "timeout"
    assert cmd.error.startswith("assemble_failed")
    assert service._published_version == v1        # NOT published


# =========================================================================
# Click triggers EXACTLY ONE command (no watched set; bounded in-flight)
# =========================================================================
def test_click_submits_exactly_one_command(monkeypatch):
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN)
    service._scheduled_tick()
    submitted: list = []
    fake = RefreshSymbolCommand("BTCUSDT", deadline_monotonic=time.monotonic() + 30)
    fake.refresh_status = "ok"
    fake.done.set()
    monkeypatch.setattr(service, "_worker_running", lambda: True)
    monkeypatch.setattr(service, "submit_refresh",
                        lambda sym: (submitted.append(sym), fake)[1])
    status, payload = service.get_symbol_snapshot("BTCUSDT")
    assert status == 200
    assert submitted == ["BTCUSDT"]                # exactly one command


def test_concurrent_clicks_same_symbol_coalesce_to_one_command():
    # Concurrent clicks for the same symbol share the SAME command and deadline
    # (bounded dedup; the merge key is symbol, not base asset).
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN)
    service._scheduled_tick()
    cmd1 = service.submit_refresh("BTCUSDT")
    cmd2 = service.submit_refresh("BTCUSDT")
    assert cmd1 is cmd2                            # coalesced to one command
    service._release_inflight(cmd1)
    # a different symbol gets its own command
    cmd3 = service.submit_refresh("ETHUSDT")
    assert cmd3 is not cmd1
    service._release_inflight(cmd3)


# =========================================================================
# Click audit: NEVER re-enters balance/position/valuation; force-TTL fires for
# the selected asset only.
# =========================================================================
def test_click_path_never_calls_balance_position_valuation():
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN)
    service._scheduled_tick()                      # sets _last_private_inputs
    before = (service._private.balance_calls,
              service._private.position_calls,
              service._private.spot_calls)
    cmd = RefreshSymbolCommand("BTCUSDT", deadline_monotonic=time.monotonic() + 30)
    service._handle_refresh_command(cmd)
    after = (service._private.balance_calls,
             service._private.position_calls,
             service._private.spot_calls)
    assert before == after                         # no balance/position/valuation
    # the click DID force-TTL the selected asset's cost-leg + max-borrowable
    assert (["BTC"], True) in service._private.cost_leg_calls
    assert ("BTC", True) in service._private.max_borrowable_calls


def test_click_does_not_invoke_full_universe_fetch_raw():
    # The click refreshes only the selected symbol via fetch_premium_index_for;
    # it never triggers a full-universe fetch_raw().
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN)
    service._scheduled_tick()
    raw_before = service.client.raw_calls
    cmd = RefreshSymbolCommand("BTCUSDT", deadline_monotonic=time.monotonic() + 30)
    service._handle_refresh_command(cmd)
    assert service.client.raw_calls == raw_before  # no full-universe read
    assert service.client.premium_calls == 1       # exactly one per-symbol premium read


# =========================================================================
# Force-TTL exact-key bypass end-to-end (real PrivateClient, monkeypatched
# urlopen): the click evicts ONLY the 3 single-asset keys; shared multi-asset
# batch + account/info + crossMarginData keys survive.
# =========================================================================
class _Resp:
    def __init__(self, body, status):
        self._b = body.encode("utf-8")
        self.status = status

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _real_private(monkeypatch, responses):
    pc = PrivateClient("k" * 64, "s" * 64, user_agent="test/1.0", timeout=5,
                       recv_window=10000, ttl_seconds=3600, fast_ttl_seconds=60)
    it = iter(responses)

    def fake_urlopen(req, timeout=None):
        item = next(it)
        if isinstance(item, urllib.error.HTTPError):
            raise item
        body, status = item
        return _Resp(body, status)

    monkeypatch.setattr(private_client.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(private_client.time, "sleep", lambda *_: None)
    return pc


def test_click_force_ttl_evicts_only_single_asset_keys(monkeypatch):
    # The force path re-fetches ONLY the 3 single-asset keys (E2 BTC, E2b BTC,
    # maxBorrowable BTC). Shared keys are pre-seeded so they are HIT (never
    # evicted, never re-fetched).
    pc = _real_private(monkeypatch, [
        (json.dumps([{"asset": "BTC", "nextHourlyInterestRate": "0.00000500"}]), 200),  # E2 BTC
        (json.dumps([{"asset": "BTC", "dailyInterestRate": "0.00010000",
                      "timestamp": "1"}]), 200),  # E2b BTC
        (json.dumps({"amount": "9", "borrowLimit": "60"}), 200),  # maxBorrowable BTC
    ])
    inf = float("inf")
    # shared keys that MUST survive the force (seeded -> cache hits, never evicted)
    pc._cache[("GET", "/sapi/v1/account/info", ())] = (inf, {"vipLevel": "0"})
    pc._cache[("GET", "/sapi/v1/margin/allAssets", ())] = (inf, [{"assetName": "BTC", "isBorrowable": True}])
    pc._cache[("GET", "/sapi/v1/margin/allPairs", ())] = (inf, [{"symbol": "BTCUSDT", "isMarginTrade": True}])
    pc._cache[("GET", "/sapi/v1/margin/crossMarginData", ())] = (
        inf, [{"coin": "BTC", "vipLevel": 0, "dailyInterest": "0.0005"}])
    batch_key = ("GET", "/sapi/v1/margin/next-hourly-interest-rate",
                 (("assets", "BTC,ETH"), ("isIsolated", "false")))
    pc._cache[batch_key] = (inf, [{"asset": "BTC", "nextHourlyInterestRate": "stale"}])

    service = _service(_raw(_BTC), history_fn=lambda s, **kw: [])
    service._scheduled_tick()                      # v1 with the disabled stub
    service._private = pc                          # swap in the real client for the click

    cmd = RefreshSymbolCommand("BTCUSDT", deadline_monotonic=time.monotonic() + 30)
    service._handle_refresh_command(cmd)
    assert cmd.refresh_status == "ok"

    # the shared multi-asset batch + account/info + crossMarginData survived
    assert batch_key in pc._cache
    assert ("GET", "/sapi/v1/account/info", ()) in pc._cache
    assert ("GET", "/sapi/v1/margin/crossMarginData", ()) in pc._cache
    # the 3 single-asset keys were evicted and re-fetched with the fresh values
    btc_e2 = ("GET", "/sapi/v1/margin/next-hourly-interest-rate",
              (("assets", "BTC"), ("isIsolated", "false")))
    assert pc._cache[btc_e2][1] == [{"asset": "BTC", "nextHourlyInterestRate": "0.00000500"}]
    btc_max = ("GET", "/papi/v1/margin/maxBorrowable", (("asset", "BTC"),))
    assert pc._cache[btc_max][1] == {"amount": "9", "borrowLimit": "60"}


# =========================================================================
# Pre-review repair (2026-07-history-background-refresh-v1): six timeout
# contract gaps. Deterministic; no real waiting, no network.
# =========================================================================
def test_expired_queued_command_does_no_upstream_io(monkeypatch):
    # (a) A command that already expired while queued starts NO new upstream I/O.
    monkeypatch.setattr(snapshot_service.time, "monotonic", lambda: 1000.0)
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN)
    service._scheduled_tick()                      # publish v1 + set _base_raw
    prem_before = service.client.premium_calls
    hist_before = len(service.client.history_calls)
    raw_before = service.client.raw_calls
    cmd = RefreshSymbolCommand("BTCUSDT", deadline_monotonic=999.0)  # already past
    service._handle_refresh_command(cmd)
    assert cmd.refresh_status == "timeout"
    assert any("refresh_command_expired" in w for w in cmd.warnings)
    # ZERO new upstream I/O of any kind
    assert service.client.premium_calls == prem_before
    assert len(service.client.history_calls) == hist_before
    assert service.client.raw_calls == raw_before


def test_endpoint_wait_timeout_returns_timeout_not_ok(monkeypatch):
    # (b) The worker accepts the command but never settles it within the deadline
    # (done never set; deadline already past). The endpoint MUST surface timeout,
    # never a fake "ok"; the row is the last-good projection.
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN)
    service._scheduled_tick()
    v1 = service._published_version
    pending = RefreshSymbolCommand("BTCUSDT", deadline_monotonic=time.monotonic() - 1)
    monkeypatch.setattr(service, "_worker_running", lambda: True)
    monkeypatch.setattr(service, "submit_refresh", lambda sym: pending)
    status, payload = service.get_symbol_snapshot("BTCUSDT")
    assert status == 200
    assert payload["refresh_status"] == "timeout"
    assert "refresh_deadline_exceeded" in payload["warnings"]
    assert payload["published_version"] == v1    # last-good, no new publish


def test_assemble_crossing_deadline_commits_nothing(monkeypatch):
    # (c) I/O finishes within the deadline, but _assemble itself crosses it: the
    # history cache / _last_private_inputs / PublishedState MUST NOT be committed.
    times = [100.0]
    monkeypatch.setattr(snapshot_service.time, "monotonic", lambda: times[0])
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN)
    service._scheduled_tick()                      # v1 at t=100
    v1 = service._published_version
    state_v1 = service._published_state
    cached_before = service._funding_history_cache.get("BTCUSDT")
    cmd = RefreshSymbolCommand("BTCUSDT", deadline_monotonic=110.0)  # future @ t=100
    real_assemble = service._assemble

    def crossing_assemble(*a, **kw):
        result = real_assemble(*a, **kw)
        times[0] = 200.0                           # cross the deadline post-assembly
        return result
    service._assemble = crossing_assemble
    service._handle_refresh_command(cmd)
    assert cmd.refresh_status == "timeout"
    assert cmd.error == "assemble_crossed_deadline"
    assert service._published_version == v1        # NOT published
    assert service._published_state is state_v1    # same immutable reference
    # the history cache entry is the SAME object the scheduled sweep wrote
    assert service._funding_history_cache.get("BTCUSDT") is cached_before


def test_schema_validation_failure_commits_nothing(monkeypatch):
    # (g) BK-6: schema validation runs BEFORE the history-cache commit and the
    # PublishedState swap. If it fails on the click path, the history cache /
    # _last_private_inputs / PublishedState MUST all stay at the last-good
    # values. We DO NOT rely on "_assemble always produces valid schema" — we
    # make the REAL jsonschema.validate raise by injecting a failing schema.
    times = [100.0]
    monkeypatch.setattr(snapshot_service.time, "monotonic", lambda: times[0])
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN)
    service._scheduled_tick()                      # v1 at t=100 (real schema)
    v1 = service._published_version
    state_v1 = service._published_state
    lpi_v1 = service._last_private_inputs
    cached_before = service._funding_history_cache.get("BTCUSDT")

    # Schema the freshly assembled snapshot cannot satisfy -> real
    # jsonschema.validate inside _validate raises ValidationError.
    failing_schema = {"type": "object", "required": ["__forced_validation_failure__"]}
    monkeypatch.setattr(service, "_load_schema", lambda: failing_schema)

    cmd = RefreshSymbolCommand("BTCUSDT", deadline_monotonic=110.0)  # future @ t=100
    service._handle_refresh_command(cmd)
    assert cmd.refresh_status == "timeout"
    assert cmd.error.startswith("assemble_failed")
    assert service._published_version == v1        # NOT published
    assert service._published_state is state_v1    # same immutable reference
    assert service._funding_history_cache.get("BTCUSDT") is cached_before
    assert service._last_private_inputs is lpi_v1  # untouched


def test_validation_crossing_deadline_commits_nothing(monkeypatch):
    # (h) BK-7: _validate itself may consume time. If validation starts
    # in-window but returns out-of-window, the final deadline gate (placed
    # AFTER _validate, BEFORE any commit/publish) must fire: commit NOTHING.
    times = [100.0]
    monkeypatch.setattr(snapshot_service.time, "monotonic", lambda: times[0])
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN)
    service._scheduled_tick()                      # v1 at t=100
    v1 = service._published_version
    state_v1 = service._published_state
    lpi_v1 = service._last_private_inputs
    cached_before = service._funding_history_cache.get("BTCUSDT")

    # Wrap _validate so it begins in-window but returns past the deadline.
    real_validate = service._validate

    def slow_validate(snapshot):
        assert times[0] < 110.0                     # begins in-window
        real_validate(snapshot)                     # real schema check passes
        times[0] = 200.0                            # returns past deadline

    service._validate = slow_validate
    cmd = RefreshSymbolCommand("BTCUSDT", deadline_monotonic=110.0)  # future @ t=100
    service._handle_refresh_command(cmd)
    assert cmd.refresh_status == "timeout"
    assert cmd.error == "validation_crossed_deadline"
    assert service._published_version == v1        # NOT published
    assert service._published_state is state_v1    # same immutable reference
    assert service._funding_history_cache.get("BTCUSDT") is cached_before
    assert service._last_private_inputs is lpi_v1  # untouched


def test_kill_switch_off_with_state_returns_timeout_zero_upstream(monkeypatch):
    # (d) Live worker not running (kill switch off / never started) but a state
    # is published: symbol-snapshot MUST NOT fake "ok". Returns the last-good row
    # with refresh_status=timeout + a diagnostic warning, ZERO upstream calls.
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN,
                       background_refresh_enabled=False)
    service._scheduled_tick()                      # publish v1 directly (no worker)
    assert service._worker_running() is False
    v1 = service._published_version
    prem_before = service.client.premium_calls
    hist_before = len(service.client.history_calls)
    raw_before = service.client.raw_calls
    status, payload = service.get_symbol_snapshot("BTCUSDT")
    assert status == 200
    assert payload["refresh_status"] == "timeout"
    assert "worker_not_running" in payload["warnings"]
    assert payload["published_version"] == v1      # last-good
    # ZERO upstream I/O on the click path (no command was ever submitted)
    assert service.client.premium_calls == prem_before
    assert len(service.client.history_calls) == hist_before
    assert service.client.raw_calls == raw_before


def test_base_raw_none_click_does_no_fetch_raw():
    # (e) The click path has NO full-universe fetch_raw() exception, even
    # defensively. _base_raw is None -> timeout + diagnostic, zero fetch_raw.
    service = _service(_raw(_BTC), history_fn=_BTC_SEVEN)
    # intentionally NO _scheduled_tick() -> _base_raw stays None
    assert service._base_raw is None
    raw_before = service.client.raw_calls
    cmd = RefreshSymbolCommand("BTCUSDT", deadline_monotonic=time.monotonic() + 30)
    service._handle_refresh_command(cmd)
    assert cmd.refresh_status == "timeout"
    assert cmd.error == "base_not_ready"
    assert any("base_raw_unavailable" in w for w in cmd.warnings)
    assert service.client.raw_calls == raw_before  # ZERO full-universe fetch_raw()
