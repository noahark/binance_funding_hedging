"""Offline tests for stage 2026-08-03-hedge-status-account-refresh-v1
(backend-cache-refresh-v1).

Covers the eight acceptance checks of the approved design
(`docs/planning/hedge-status-account-refresh-v4.md`):

1. one worker-only refresh cycle; ``force`` bypasses only the account-panel due
   + the four private transport keys; compose / Group C / assemble / validate /
   publish are reused.
2. ``RefreshCacheCommand`` has its own ``done`` / ``result`` and a fixed
   in-flight key; the worker dispatches both command types; a cache-command
   failure does not kill the worker; POST fails honestly with no worker.
3. ``RefreshResult`` separates ``published`` from complete / partial /
   not_attempted.
4. ``source_checked_at`` advances only on a successful source write; failure
   keeps last-good + old time; never-succeeded is null; PM-absent -> null.
5. snapshot + ``/hedge-open-positions`` account meta carry the field; the JSON
   schema requires it and rejects a missing / extra key.
6. POST success / partial / not_attempted / failure / queued-timeout; GET stays
   zero-upstream.
7. store surfaces a real old/new transition; the service fires the non-waiting
   cache command only on a real ``running -> 非 running``.
8. offline pytest (this file).

No network, no real API key, no running service: fakes are injected and the
worker cycle is driven via direct ``_run_refresh_cycle`` /
``_handle_cache_refresh_command`` calls (the same entrypoints the worker uses).
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from backend.app import server as server_mod
from backend.config import Config
from backend.hedge_open_tasks import HedgeOpenTaskService
from backend.hedge_open_tasks import domain as HD
from backend.hedge_open_tasks.executor import AttemptOutcome
from backend.hedge_open_tasks.store import HedgeOpenStore
from backend.services.private_client import PrivateClient
from backend.services.snapshot_service import (
    RefreshCacheCommand,
    RefreshResult,
    SnapshotNotReady,
    SnapshotService,
)

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas/api/public-market/snapshot.schema.json"


# ---------------------------------------------------------------------------
# fakes
# ---------------------------------------------------------------------------


class _Pub:
    """Split-seam public client: premium / group_b / book_ticker / price_map."""

    offline = False

    def __init__(self, raw, *, price_map=None, fail_price_map=False, fail_premium=False):
        self._raw = raw
        self._price_map = {} if price_map is None else price_map
        self._fail_price_map = fail_price_map
        self._fail_premium = fail_premium
        self.ticker_calls = 0
        self.premium_calls = 0
        self.group_b_calls = 0

    def fetch_premium_index(self):
        self.premium_calls += 1
        if self._fail_premium:
            raise OSError("premium upstream down")
        return self._raw["premium_index"]

    def fetch_exchange_info_group_b(self):
        self.group_b_calls += 1
        return {
            "futures_exchange_info": self._raw["futures_exchange_info"],
            "spot_exchange_info": self._raw["spot_exchange_info"],
            "funding_interval_by_sym": self._raw.get("funding_interval_by_sym", {}),
            "warnings": self._raw.get("warnings", []),
        }

    def fetch_book_ticker_pair(self):
        return None

    def fetch_ticker_price_map(self):
        self.ticker_calls += 1
        if self._fail_price_map:
            raise OSError("price map upstream down")
        return self._price_map

    # unused by the cycle but kept for shape compatibility
    def fetch_premium_index_for(self, symbol):
        return {}

    def fetch_funding_rate(self, symbol, **kw):
        return []


class _PrivBase:
    """Enabled private stub whose account fetchers accept ``force`` and record
    each call's force flag + return canned data so source_checked_at advances.

    This base deliberately has NO ``fetch_pm_account`` method, modeling a client
    without the PM capability (``getattr(..., "fetch_pm_account", None)`` then
    returns None -> pm_account stays null)."""

    def __init__(self, *, classic_ref="present", fails=()):
        self.last_error = None
        self.enabled = True
        self._classic_ref = (
            {
                "pair_listed_by_symbol": {},
                "asset_borrowable_by_name": {},
                "daily_interest_vip0_by_coin": {},
                "cross_margin_daily_by_vip": {},
                "user_min_borrow_by_name": {},
            }
            if classic_ref == "present"
            else None
        )
        if classic_ref != "present":
            self.last_error = "private_channel_disabled"
            self.enabled = False
        self._fails = set(fails)
        self.force_log = []  # (sid, force) for the four private + pm fetchers
        self.calls = {"price_map": 0, "unified": 0, "um": 0, "spot": 0, "pm": 0}

    def fetch_classic_reference(self):
        return self._classic_ref

    def fetch_account_info(self):
        return {"vipLevel": 0}

    def _maybe_fail(self, sid):
        if sid in self._fails:
            raise OSError(f"{sid} upstream down")
        return None

    def fetch_unified_balances(self, *, force=False):
        self.calls["unified"] += 1
        self.force_log.append(("unified_balances", force))
        self._maybe_fail("unified_balances")
        return [{"asset": "USDT", "totalWalletBalance": "60000", "crossMarginBorrowed": "0"}]

    def fetch_um_positions(self, *, force=False):
        self.calls["um"] += 1
        self.force_log.append(("um_positions", force))
        self._maybe_fail("um_positions")
        return []

    def fetch_spot_balances(self, *, force=False):
        self.calls["spot"] += 1
        self.force_log.append(("spot_balances", force))
        self._maybe_fail("spot_balances")
        return [{"asset": "USDT", "free": "60000", "locked": "0"}]

    # scheduled borrow-path stubs (unused by the account-panel cycle)
    def fetch_next_hourly_rates(self, assets):
        return {}

    def fetch_interest_rate_history_latest(self, asset):
        return None

    def fetch_max_borrowable(self, asset, *, force=False):
        return None

    def fetch_cost_leg_chain(self, assets, *, force=False):
        return None


class _Priv(_PrivBase):
    """Adds the PM capability (``fetch_pm_account``)."""

    def fetch_pm_account(self, *, force=False):
        self.calls["pm"] += 1
        self.force_log.append(("pm_account", force))
        self._maybe_fail("pm_account")
        return {"accountEquity": "60000", "actualEquity": "60000"}


def _raw_inputs(raw_inputs):
    return {
        "futures_exchange_info": raw_inputs["futures"],
        "premium_index": raw_inputs["premium"],
        "spot_exchange_info": raw_inputs["spot"],
        "funding_interval_by_sym": {},
        "warnings": [],
    }


def _service(raw_inputs, *, priv=None, price_map=None, fail_price_map=False,
             fail_premium=False, **cfg):
    raw = _raw_inputs(raw_inputs)
    pub = _Pub(raw, price_map=price_map, fail_price_map=fail_price_map,
               fail_premium=fail_premium)
    svc = SnapshotService(Config(offline=False, **cfg), client=pub)
    svc._private = priv if priv is not None else _Priv()
    return svc, pub


# ---------------------------------------------------------------------------
# AC1 — single refresh cycle; force bypasses only account-panel due + keys
# ---------------------------------------------------------------------------


def test_scheduled_cycle_force_false_does_not_force_panels(raw_inputs):
    svc, _ = _service(raw_inputs)
    svc._run_refresh_cycle(force_account_panels=False)
    # panels were read once (cache was cold -> due); none were forced.
    assert all(force is False for _sid, force in svc._private.force_log)
    assert svc._published_state is not None


def test_force_cycle_reads_all_panels_with_force_and_publishes(raw_inputs, schema):
    svc, pub = _service(raw_inputs)
    res = svc._run_refresh_cycle(force_account_panels=True)
    assert res.published is True
    assert res.account_panels == "complete"
    # price_map (public, no force arg) + the four private fetchers all read.
    assert pub.ticker_calls >= 1
    forced = dict(svc._private.force_log)
    assert forced.get("unified_balances") is True
    assert forced.get("um_positions") is True
    assert forced.get("spot_balances") is True
    assert forced.get("pm_account") is True
    # the published snapshot is schema-valid (assemble pipeline intact).
    jsonschema.validate(svc._published_state.snapshot, schema)


def test_force_only_evicts_exact_private_transport_key():
    """Unit: PrivateClient._evict removes EXACTLY one key, never _cache.clear()."""
    client = PrivateClient("k", "s", user_agent="t", timeout=1, recv_window=10,
                           ttl_seconds=60, fast_ttl_seconds=60)
    exact = ("GET", "/papi/v1/balance", ())
    other = ("GET", "/papi/v1/um/positionRisk", ())
    multi = ("GET", "/sapi/v1/margin/next-hourly-interest-rate",
             (("assets", "BTC,ETH"), ("isIsolated", "false")))
    client._cache[exact] = (1.0, [])
    client._cache[other] = (1.0, [])
    client._cache[multi] = (1.0, {})
    client._evict("GET", "/papi/v1/balance")
    assert exact not in client._cache      # evicted
    assert other in client._cache          # untouched
    assert multi in client._cache          # multi-asset scheduled key untouched


def test_force_bypasses_panel_due_when_sources_fresh(raw_inputs):
    svc, _ = _service(raw_inputs)
    svc._run_refresh_cycle(force_account_panels=False)  # warm: all panels cached
    n_before = sum(svc._private.calls.values())
    res = svc._run_refresh_cycle(force_account_panels=True)  # force re-reads
    assert res.account_panels == "complete"
    assert sum(svc._private.calls.values()) > n_before  # panels re-read despite due


# ---------------------------------------------------------------------------
# AC2 — RefreshCacheCommand own done/result; dispatch; isolation; no-worker 503
# ---------------------------------------------------------------------------


def test_refresh_cache_command_initial_state():
    cmd = RefreshCacheCommand()
    assert cmd.done.is_set() is False
    assert cmd.result is None


def test_handle_cache_refresh_command_sets_done_and_result(raw_inputs):
    svc, _ = _service(raw_inputs)
    cmd = RefreshCacheCommand()
    svc._handle_cache_refresh_command(cmd)
    assert cmd.done.is_set() is True
    assert isinstance(cmd.result, RefreshResult)
    assert cmd.result.published is True


def test_cache_command_failure_does_not_kill_worker(raw_inputs):
    svc, _ = _service(raw_inputs)

    def boom(**kw):
        raise RuntimeError("cycle blew up")

    svc._refresh_due_sources = boom  # force an unexpected exception
    cmd = RefreshCacheCommand()
    svc._handle_cache_refresh_command(cmd)  # must catch, record, not raise
    assert cmd.done.is_set() is True
    assert cmd.result.published is False
    assert cmd.result.account_panels == "not_attempted"


def test_submit_cache_refresh_coalesces_inflight_command(raw_inputs):
    svc, _ = _service(raw_inputs)
    a = svc.submit_cache_refresh()
    b = svc.submit_cache_refresh()
    assert a is b  # same in-flight instance reused while not done
    a.done.set()
    svc._release_cache_inflight()
    c = svc.submit_cache_refresh()
    assert c is not a  # after release, a fresh command is created


def test_submit_cache_refresh_inflight_key_distinct_from_symbol(raw_inputs):
    svc, _ = _service(raw_inputs)
    cache_cmd = svc.submit_cache_refresh()
    sym_cmd = svc.submit_refresh("BTCUSDT")
    assert cache_cmd is not sym_cmd
    # the cache in-flight slot does not collide with a symbol slot
    assert sym_cmd in svc._inflight.values()


# ---------------------------------------------------------------------------
# AC3 — RefreshResult separates published from complete/partial/not_attempted
# ---------------------------------------------------------------------------


def test_result_not_attempted_when_private_channel_disabled(raw_inputs):
    svc, _ = _service(raw_inputs, priv=_Priv(classic_ref=None))
    res = svc._run_refresh_cycle(force_account_panels=True)
    assert res.account_panels == "not_attempted"


def test_result_partial_when_um_fails(raw_inputs):
    svc, _ = _service(raw_inputs, priv=_Priv(fails=("um_positions",)))
    res = svc._run_refresh_cycle(force_account_panels=True)
    assert res.account_panels == "partial"


def test_result_partial_when_price_map_fails(raw_inputs):
    svc, _ = _service(raw_inputs, fail_price_map=True)
    res = svc._run_refresh_cycle(force_account_panels=True)
    assert res.account_panels == "partial"


def test_result_partial_when_all_private_fail(raw_inputs):
    svc, _ = _service(
        raw_inputs,
        priv=_Priv(fails=("unified_balances", "um_positions", "spot_balances", "pm_account")),
    )
    res = svc._run_refresh_cycle(force_account_panels=True)
    assert res.account_panels == "partial"


def test_result_partial_when_pm_required_but_fails(raw_inputs):
    svc, _ = _service(raw_inputs, priv=_Priv(fails=("pm_account",)))
    res = svc._run_refresh_cycle(force_account_panels=True)
    assert res.account_panels == "partial"


def test_published_false_when_base_raw_cold(raw_inputs):
    svc, pub = _service(raw_inputs, fail_premium=True)
    res = svc._run_refresh_cycle(force_account_panels=True)
    assert res.published is False
    assert res.account_panels == "not_attempted"


# ---------------------------------------------------------------------------
# AC4 — source_checked_at advances only on success; failure keeps old; PM null
# ---------------------------------------------------------------------------


def test_source_checked_at_all_null_before_first_success(raw_inputs):
    svc, _ = _service(raw_inputs)
    view = svc._source_checked_at_view()
    assert set(view) == {"price_map", "unified_balances", "um_positions",
                         "spot_balances", "pm_account"}
    assert all(v is None for v in view.values())


def test_source_checked_at_advances_on_success(raw_inputs):
    svc, _ = _service(raw_inputs)
    svc._run_refresh_cycle(force_account_panels=True)
    view = svc._source_checked_at_view()
    assert view["price_map"] is not None
    assert view["unified_balances"] is not None
    assert view["um_positions"] is not None
    assert view["spot_balances"] is not None
    assert view["pm_account"] is not None
    # and it is attached to the published private_account
    assert svc._published_state.snapshot["private_account"]["source_checked_at"] == view


def test_source_checked_at_failure_keeps_old_value_and_time(raw_inputs):
    svc, _ = _service(raw_inputs)
    svc._run_refresh_cycle(force_account_panels=True)  # um succeeds -> time set
    um_time = svc._source_checked_at_view()["um_positions"]
    assert um_time is not None
    # now um fails: source_checked_at["um_positions"] must NOT advance (keep old)
    svc._private._fails.add("um_positions")
    svc._run_refresh_cycle(force_account_panels=True)
    assert svc._source_checked_at_view()["um_positions"] == um_time


def test_pm_account_null_when_capability_absent(raw_inputs):
    priv = _PrivBase()  # no fetch_pm_account attribute -> PM capability absent
    svc, _ = _service(raw_inputs, priv=priv)
    svc._run_refresh_cycle(force_account_panels=True)
    # capability absent -> pm_account key present but null; complete still
    # possible (pm not required when capability absent)
    assert svc._source_checked_at_view()["pm_account"] is None
    assert svc._run_refresh_cycle(force_account_panels=True).account_panels == "complete"


def test_checked_at_aggregate_still_set_alongside_source_times(raw_inputs):
    svc, _ = _service(raw_inputs)
    svc._run_refresh_cycle(force_account_panels=True)
    assert svc._account_checked_at is not None  # legacy aggregate preserved


# ---------------------------------------------------------------------------
# AC5 — schema requires source_checked_at; positions account meta carries it
# ---------------------------------------------------------------------------


def _private_account_block():
    return {
        "verified": True,
        "balances_unified": [],
        "balances_spot": [],
        "um_positions": [],
        "total_value_usdt": "0",
        "valuation": {"price_source": "api_v3_ticker_price", "priced_at": None},
        "checked_at": None,
        "source_checked_at": {
            "price_map": None, "unified_balances": None, "um_positions": None,
            "spot_balances": None, "pm_account": None,
        },
        "error": None,
    }


def test_schema_rejects_private_account_without_source_checked_at(schema):
    pa = _private_account_block()
    del pa["source_checked_at"]
    snap = {"private_account": pa}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(snap, {"$defs": schema["$defs"],
                                   "properties": {"private_account": schema["properties"]["private_account"]}})


def test_schema_rejects_extra_key_in_source_checked_at(schema):
    pa = _private_account_block()
    pa["source_checked_at"]["extra"] = None
    snap = {"private_account": pa}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(snap, {"$defs": schema["$defs"],
                                   "properties": {"private_account": schema["properties"]["private_account"]}})


def test_schema_rejects_missing_key_in_source_checked_at(schema):
    pa = _private_account_block()
    del pa["source_checked_at"]["um_positions"]
    snap = {"private_account": pa}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(snap, {"$defs": schema["$defs"],
                                   "properties": {"private_account": schema["properties"]["private_account"]}})


class _CapHandler:
    """Stand-in that captures _send_json / _send_hedge_open without a socket."""

    def __init__(self, service, hedge_open_service=None, content_length="0"):
        self.service = service
        self.hedge_open_service = hedge_open_service
        self.headers = {"Content-Length": content_length}
        self.rfile = _BytesRead(b"")
        self.calls = []

    def _send_json(self, status, body):
        self.calls.append(("json", status, json.loads(body)))

    def _send_hedge_open(self, status, payload):
        self.calls.append(("hedge", status, payload))


class _BytesRead:
    def __init__(self, data):
        self._data = data

    def read(self, n):
        return self._data[:n]


class _FakeService:
    """SnapshotService stand-in for the HTTP handler tests."""

    def __init__(self, *, worker_running, cmd, timeout=5.0, snapshot=None):
        self._worker_running_value = worker_running
        self._cmd = cmd
        self._snapshot = snapshot
        self.config = Config(cache_refresh_timeout_seconds=timeout)

    def _worker_running(self):
        return self._worker_running_value

    def submit_cache_refresh(self):
        return self._cmd

    def get_snapshot(self):
        if isinstance(self._snapshot, Exception):
            raise self._snapshot
        return self._snapshot


def test_positions_account_meta_carries_source_checked_at():
    pa = _private_account_block()
    pa["source_checked_at"]["price_map"] = "2026-08-03T07:34:50Z"
    fake_hedge = type("H", (), {"get_positions": lambda self: (200, {"positions": []})})()
    h = _CapHandler(_FakeService(worker_running=True, cmd=None, snapshot={"private_account": pa}),
                    hedge_open_service=fake_hedge)
    server_mod._Handler._hedge_open_positions(h)
    assert h.calls and h.calls[0][0] == "hedge"
    meta = h.calls[0][2]["account"]
    assert meta["source_checked_at"] == pa["source_checked_at"]


def test_positions_account_meta_all_null_when_snapshot_absent():
    fake_hedge = type("H", (), {"get_positions": lambda self: (200, {"positions": []})})()
    h = _CapHandler(
        _FakeService(worker_running=True, cmd=None, snapshot=SnapshotNotReady("not ready")),
        hedge_open_service=fake_hedge,
    )
    server_mod._Handler._hedge_open_positions(h)
    meta = h.calls[0][2]["account"]
    assert set(meta["source_checked_at"]) == {
        "price_map", "unified_balances", "um_positions", "spot_balances", "pm_account"
    }
    assert all(v is None for v in meta["source_checked_at"].values())


# ---------------------------------------------------------------------------
# AC6 — POST success / partial / not_attempted / failure / queued; GET pure read
# ---------------------------------------------------------------------------


def test_post_cache_refresh_503_when_worker_not_running():
    cmd = RefreshCacheCommand()
    h = _CapHandler(_FakeService(worker_running=False, cmd=cmd))
    server_mod._Handler._handle_cache_refresh(h)
    assert h.calls[0] == ("json", 503, h.calls[0][2])
    assert h.calls[0][2]["error"] == "cache_refresh_unavailable"


def test_post_cache_refresh_200_complete():
    cmd = RefreshCacheCommand()
    cmd.result = RefreshResult(published=True, account_panels="complete")
    cmd.done.set()
    h = _CapHandler(_FakeService(worker_running=True, cmd=cmd))
    server_mod._Handler._handle_cache_refresh(h)
    assert h.calls[0][0] == "json" and h.calls[0][1] == 200
    assert h.calls[0][2] == {"published": True, "account_panels": "complete"}


def test_post_cache_refresh_200_partial():
    cmd = RefreshCacheCommand()
    cmd.result = RefreshResult(published=True, account_panels="partial")
    cmd.done.set()
    h = _CapHandler(_FakeService(worker_running=True, cmd=cmd))
    server_mod._Handler._handle_cache_refresh(h)
    assert h.calls[0][1] == 200
    assert h.calls[0][2] == {"published": True, "account_panels": "partial"}


def test_post_cache_refresh_200_failure_published_false():
    cmd = RefreshCacheCommand()
    cmd.result = RefreshResult(published=False, account_panels="not_attempted")
    cmd.done.set()
    h = _CapHandler(_FakeService(worker_running=True, cmd=cmd))
    server_mod._Handler._handle_cache_refresh(h)
    assert h.calls[0][1] == 200
    assert h.calls[0][2] == {"published": False, "account_panels": "not_attempted"}


def test_post_cache_refresh_202_queued_when_still_running():
    cmd = RefreshCacheCommand()  # not done -> simulates still-in-progress
    h = _CapHandler(_FakeService(worker_running=True, cmd=cmd, timeout=0.01))
    server_mod._Handler._handle_cache_refresh(h)
    assert h.calls[0][1] == 202
    assert h.calls[0][2]["status"] == "queued"


def test_get_snapshot_is_zero_upstream_after_publish(raw_inputs):
    svc, pub = _service(raw_inputs)
    svc._run_refresh_cycle(force_account_panels=True)  # publish once
    pub.ticker_calls = 0
    svc._private.calls = {"price_map": 0, "unified": 0, "um": 0, "spot": 0, "pm": 0}
    # a pure read must not touch any upstream seam
    svc.get_snapshot()
    assert pub.ticker_calls == 0
    assert sum(svc._private.calls.values()) == 0


# ---------------------------------------------------------------------------
# AC7 — store transition + service hook (only real running -> 非 running)
# ---------------------------------------------------------------------------


def _store(tmp_path):
    return HedgeOpenStore(str(tmp_path / "h.sqlite3"), executor_mode_snapshot="disabled")


def _create_running(store, tid="t1"):
    return store.create_task(tid, "BTCUSDT", "forward", "immediate", "10", 1, None, None, None, 1)


def test_store_set_task_status_records_transition(tmp_path):
    store = _store(tmp_path)
    _create_running(store)
    updated = store.set_task_status("t1", HD.STATUS_PAUSED, 2)
    assert updated["_status_transition"] == (HD.STATUS_RUNNING, HD.STATUS_PAUSED)


def test_store_pause_task_records_transition_and_zero_on_same(tmp_path):
    store = _store(tmp_path)
    _create_running(store)
    updated, applied = store.pause_task("t1", "rate_limited", "zh", 2)
    assert applied is True
    assert updated["_status_transition"] == (HD.STATUS_RUNNING, HD.STATUS_PAUSED)
    # paused -> paused is a zero-trigger (old is not running)
    updated2, applied2 = store.pause_task("t1", "rate_limited", "zh2", 3)
    assert applied2 is True
    assert updated2["_status_transition"] == (HD.STATUS_PAUSED, HD.STATUS_PAUSED)


def test_store_stop_task_fatal_records_transition(tmp_path):
    store = _store(tmp_path)
    _create_running(store)
    updated = store.stop_task_fatal("t1", "exchange_fatal", 2)
    assert updated["_status_transition"] == (HD.STATUS_RUNNING, HD.STATUS_STOPPED)


def test_resolve_attempt_records_transition_to_done(tmp_path):
    store = _store(tmp_path)
    _create_running(store)
    attempt = store.prepare_attempt(
        "t1", "u1", "forward", "10", {}, {}, "scid", {}, "/api/v3/order", "pcid", {}, 2,
    )
    outcome = AttemptOutcome(
        attempt_id="u1", category=HD.ATTEMPT_SUCCESS,
        spot={"order_id": "o1", "filled_qty": "1", "status": HD.LEG_FILLED},
        perp={"order_id": "o2", "filled_qty": "1", "status": HD.LEG_FILLED},
        record_payload={}, exposure=None,
    )
    updated = store.resolve_attempt(attempt["id"], outcome, 3)
    # target_n == 1 reached on success -> auto-done (running -> done)
    assert updated["_status_transition"] == (HD.STATUS_RUNNING, HD.STATUS_DONE)


def test_settle_attempt_no_counters_is_zero_trigger(tmp_path):
    store = _store(tmp_path)
    _create_running(store)
    attempt = store.prepare_attempt(
        "t1", "u1", "forward", "10", {}, {}, "scid", {}, "/api/v3/order", "pcid", {}, 2,
    )
    # mark both legs terminal via resolve_leg_from_query (no counters consumed)
    for leg in store.list_legs_for_attempt(attempt["id"]):
        store.resolve_leg_from_query(
            leg["id"], exchange_status=HD.LEG_REJECTED, order_id=None,
            base_qty="0", quote_amt=None, fee_amount=None, fee_asset=None,
            now_us=3, terminal=True,
        )
    settled = store.settle_attempt_no_counters(attempt["id"], 4)
    assert settled is True
    # status unchanged (running) -> the task is still running (zero-trigger)
    assert store.get_task("t1")["status"] == HD.STATUS_RUNNING


def _service_with_hook(tmp_path):
    calls: list = []
    svc = HedgeOpenTaskService(
        str(tmp_path / "h.sqlite3"), mode="disabled",
        cache_refresh_submitter=lambda: calls.append(1),
    )
    return svc, calls


def test_hook_fires_on_post_pause_running_to_paused(tmp_path):
    svc, calls = _service_with_hook(tmp_path)
    svc._store.create_task("t1", "BTCUSDT", "forward", "immediate", "10", 1, None, None, None, 1)
    svc.post_pause("t1")
    assert len(calls) == 1


def test_hook_fires_on_post_delete_running_to_deleted(tmp_path):
    svc, calls = _service_with_hook(tmp_path)
    svc._store.create_task("t1", "BTCUSDT", "forward", "immediate", "10", 1, None, None, None, 1)
    svc.post_delete("t1")
    assert len(calls) == 1


def test_hook_no_fire_on_restore_to_running(tmp_path):
    svc, calls = _service_with_hook(tmp_path)
    svc._store.create_task("t1", "BTCUSDT", "forward", "immediate", "10", 1, None, None, None, 1)
    svc._store.set_task_status("t1", HD.STATUS_PAUSED, 2)
    svc.post_start("t1")  # paused -> running: NOT a trigger
    assert calls == []


def test_hook_swallows_submitter_exception_no_rollback(tmp_path):
    def boom():
        raise RuntimeError("enqueue failed")
    svc = HedgeOpenTaskService(
        str(tmp_path / "h.sqlite3"), mode="disabled", cache_refresh_submitter=boom,
    )
    svc._store.create_task("t1", "BTCUSDT", "forward", "immediate", "10", 1, None, None, None, 1)
    svc.post_pause("t1")  # must not raise
    # the task status still committed (rolled back nowhere)
    assert svc._store.get_task("t1")["status"] == HD.STATUS_PAUSED


def test_hook_no_fire_when_submitter_not_configured(tmp_path):
    svc = HedgeOpenTaskService(str(tmp_path / "h.sqlite3"), mode="disabled")
    svc._store.create_task("t1", "BTCUSDT", "forward", "immediate", "10", 1, None, None, None, 1)
    svc.post_pause("t1")  # no submitter wired -> no-op, no error
    assert svc._store.get_task("t1")["status"] == HD.STATUS_PAUSED
