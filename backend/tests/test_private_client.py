"""Negative tests for private_client security gates (10-design §3.2).

No network: ``urlopen`` is monkeypatched. Asserts the single-HMAC exit,
deny-by-default whitelist, GET-only, gate-fires-before-signing, env-missing
degradation, audit-log credential hygiene, bounded rate-limit backoff, and
that no private-domain path appears outside private_client.py.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest
import urllib.error
import urllib.request

from backend.services import private_client
from backend.services.private_client import PrivateClient, PrivateEndpointError

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"

_HMAC_RE = re.compile(r"\bhmac\b")
_HASHLIB_RE = re.compile(r"hashlib")
_SIGNATURE_ASSIGN_RE = re.compile(r"signature\s*=")


class _FakeResp:
    def __init__(self, body: str, status: int):
        self._body = body.encode("utf-8")
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _make_client(monkeypatch, responses, *, enabled=True, ttl_seconds=3600):
    """PrivateClient whose urlopen yields `responses` in order.

    Each item is either a (body_str, status_int) tuple or an HTTPError to raise.
    """
    key = "k" * 64 if enabled else None
    secret = "s" * 64 if enabled else None
    client = PrivateClient(
        key, secret, user_agent="test/1.0", timeout=5,
        recv_window=10000, ttl_seconds=ttl_seconds, fast_ttl_seconds=60,
    )
    it = iter(responses)

    def fake_urlopen(req, timeout=None):
        item = next(it)
        if isinstance(item, urllib.error.HTTPError):
            raise item
        body, status = item
        return _FakeResp(body, status)

    monkeypatch.setattr(private_client.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(private_client.time, "sleep", lambda *_: None)  # no real sleeps
    return client


def _http_error(code: int, body: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://example.invalid", code, "err", {}, io.BytesIO(body.encode("utf-8"))
    )


# ---- 1. single HMAC exit (grep-level over product code) ----
def test_single_hmac_exit_in_product_code():
    """No product module other than private_client.py touches hmac/hashlib/signature."""
    bad = []
    for py in BACKEND_DIR.rglob("*.py"):
        rel = py.relative_to(REPO_ROOT)
        if "tests" in rel.parts or rel.name == "private_client.py":
            continue
        text = py.read_text(encoding="utf-8")
        if _HMAC_RE.search(text) or _HASHLIB_RE.search(text) or _SIGNATURE_ASSIGN_RE.search(text):
            bad.append(str(rel))
    assert bad == [], f"hmac/hashlib/signature found outside private_client.py: {bad}"


def test_urlopen_only_in_designated_http_clients():
    """Direct-HTTP guard: only private_client.py and binance_public.py may call
    urlopen, so no other product module can bypass them to hit Binance directly
    (with or without a signature)."""
    allowed = {"private_client.py", "binance_public.py"}
    bad = []
    for py in BACKEND_DIR.rglob("*.py"):
        rel = py.relative_to(REPO_ROOT)
        if "tests" in rel.parts or rel.name in allowed:
            continue
        if "urlopen" in py.read_text(encoding="utf-8"):
            bad.append(str(rel))
    assert bad == [], f"urlopen found outside the two HTTP clients: {bad}"


# ---- 2. deny-by-default whitelist + GET-only ----
def test_whitelist_rejects_unknown_path():
    with pytest.raises(PermissionError):
        PrivateClient._require_whitelisted("GET", "/sapi/v1/margin/forbidden")


def test_whitelist_rejects_non_get_on_whitelisted_path():
    with pytest.raises(PermissionError):
        PrivateClient._require_whitelisted("POST", "/sapi/v1/margin/allPairs")


def test_whitelist_rejects_delete_on_whitelisted_path():
    with pytest.raises(PermissionError):
        PrivateClient._require_whitelisted("DELETE", "/papi/v1/margin/maxBorrowable")


def test_whitelist_accepts_exactly_twelve_get_endpoints():
    assert len(private_client.WHITELIST) == 12
    for method, path in private_client.WHITELIST:
        assert method == "GET"
        assert PrivateClient._require_whitelisted(method, path)


def test_whitelist_matches_status_json_endpoint_whitelist():
    """The whitelisted pairs must equal status.json endpoint_whitelist (12)."""
    import json as _json
    status = _json.loads(
        (REPO_ROOT / "reports/agent-runs/2026-07-private-account-v1/status.json").read_text()
    )
    expected = {tuple(pair) for pair in status["endpoint_whitelist"]}
    assert set(private_client.WHITELIST.keys()) == expected


def test_whitelist_base_urls_match_2A_appendix():
    """§2.A.1: api.binance.com (sapi/api) vs papi.binance.com (papi) split."""
    papi = {p for (m, p) in private_client.WHITELIST if private_client.WHITELIST[(m, p)].endswith("papi.binance.com")}
    api = {p for (m, p) in private_client.WHITELIST if private_client.WHITELIST[(m, p)].endswith("api.binance.com")}
    assert papi == {
        "/papi/v1/margin/maxBorrowable",
        "/papi/v1/balance",
        "/papi/v1/um/positionRisk",
        "/papi/v1/margin/marginInterestHistory",
        "/papi/v1/portfolio/interest-history",
    }
    assert "/api/v3/account" in api
    assert "/sapi/v1/margin/next-hourly-interest-rate" in api


def test_whitelist_rejects_unknown_papi_path():
    with pytest.raises(PermissionError):
        PrivateClient._require_whitelisted("GET", "/papi/v1/margin/forbidden")


def test_whitelist_rejects_post_on_new_endpoint():
    with pytest.raises(PermissionError):
        PrivateClient._require_whitelisted("POST", "/papi/v1/balance")


# ---- 3. gate fires BEFORE signature construction ----
def test_gate_fires_before_signature_construction(monkeypatch):
    """An unknown path must raise without ever calling urlopen (no signature sent)."""
    client = _make_client(monkeypatch, [])  # empty: reaching urlopen would StopIteration
    with pytest.raises(PermissionError):
        client._signed_get("GET", "/sapi/v1/margin/forbidden")


# ---- 4. env-missing degradation ----
def test_disabled_when_env_missing():
    client = PrivateClient(
        None, None, user_agent="t", timeout=5, recv_window=10000, ttl_seconds=3600,
        fast_ttl_seconds=60,
    )
    assert client.enabled is False
    assert client.fetch_classic_reference() is None
    assert client.fetch_max_borrowable("BTC") is None
    assert client.last_error == "private_channel_disabled"
    # v0.3 account-balance + chain fetchers also degrade to None when disabled.
    assert client.fetch_unified_balances() is None
    assert client.fetch_um_positions() is None
    assert client.fetch_spot_balances() is None
    assert client.fetch_account_info() is None
    assert client.fetch_cost_leg_chain(["BTC"]) is None
    # S3b scheduled-only narrow seams also degrade to None when disabled.
    assert client.fetch_next_hourly_rates(["BTC"]) is None
    assert client.fetch_interest_rate_history_latest("BTC") is None


# ---- 5. audit-log credential hygiene ----
def test_audit_log_has_no_credentials(monkeypatch):
    client = _make_client(monkeypatch, [
        (json.dumps([{"symbol": "BTCUSDT", "isMarginTrade": True}]), 200),  # allPairs
        ("[]", 200),  # allAssets
        ("[]", 200),  # crossMarginData
    ])
    client.fetch_classic_reference()
    blob = json.dumps(client.audit_log)
    assert "k" * 64 not in blob  # real key never appears
    assert "s" * 64 not in blob  # real secret never appears
    for entry in client.audit_log:
        # only sanitized fields; no query string, no signature, no headers
        assert set(entry.keys()) == {
            "logical_endpoint", "method", "http_status", "error", "latency_ms",
        }
        assert "=" not in entry["logical_endpoint"]
        assert "signature" not in entry["logical_endpoint"].lower()


# ---- 6. bounded rate-limit backoff (retry once, then succeed) ----
def test_rate_limit_backoff_retries_once_then_succeeds(monkeypatch):
    client = _make_client(monkeypatch, [
        (json.dumps({"code": -1003, "msg": "busy"}), 400),  # first: rate-limited
        (json.dumps({"amount": "1.0", "borrowLimit": "60"}), 200),  # retry succeeds
    ])
    result = client.fetch_max_borrowable("BTC")
    assert result == {"max_borrowable": "1.0", "borrow_limit": "60", "error_code": None}
    assert len(client.audit_log) == 2  # both attempts logged


def test_rate_limit_429_also_retries(monkeypatch):
    client = _make_client(monkeypatch, [
        ('{"code":-1003,"msg":"x"}', 429),
        (json.dumps({"amount": "2", "borrowLimit": "5"}), 200),
    ])
    assert client.fetch_max_borrowable("ETH") == {"max_borrowable": "2", "borrow_limit": "5", "error_code": None}


# ---- 7. endpoint failure -> caller degrades (None + last_error) ----
def test_classic_reference_degrades_on_endpoint_failure(monkeypatch):
    client = _make_client(monkeypatch, [_http_error(403, '{"code":-2014}')])  # allPairs 403
    assert client.fetch_classic_reference() is None
    assert client.last_error.startswith("classic_reference_failed")


def test_max_borrowable_degrades_on_endpoint_failure(monkeypatch):
    client = _make_client(monkeypatch, [_http_error(401, '{"code":-2015}')])
    assert client.fetch_max_borrowable("BTC") is None
    assert client.last_error.startswith("max_borrowable_failed:BTC")


# ---- 8. happy-path classic reference mapping (raw camelCase -> snake_case dict) ----
def test_classic_reference_maps_raw_fields(monkeypatch):
    client = _make_client(monkeypatch, [
        (json.dumps([{"symbol": "BTCUSDT", "isMarginTrade": True},
                     {"symbol": "FOOUSDT", "isMarginTrade": False}]), 200),
        (json.dumps([{"assetName": "BTC", "isBorrowable": True}]), 200),
        (json.dumps([{"coin": "BTC", "vipLevel": 0, "dailyInterest": "0.0005"},
                     {"coin": "BTC", "vipLevel": 1, "dailyInterest": "0.0004"}]), 200),
    ])
    ref = client.fetch_classic_reference()
    assert ref == {
        "pair_listed_by_symbol": {"BTCUSDT": True, "FOOUSDT": False},
        "asset_borrowable_by_name": {"BTC": True},
        "daily_interest_vip0_by_coin": {"BTC": "0.0005"},  # only vipLevel 0
        # S3 (§5.1): additive full VIP-level daily-interest table shared with the
        # vip0 view; assembly derives tier③/④ borrow rates from it.
        "cross_margin_daily_by_vip": {"0": {"BTC": "0.0005"}, "1": {"BTC": "0.0004"}},
    }


def test_max_borrowable_maps_raw_fields(monkeypatch):
    client = _make_client(monkeypatch, [
        (json.dumps({"amount": "1.5", "borrowLimit": "60"}), 200),
    ])
    assert client.fetch_max_borrowable("BTC") == {"max_borrowable": "1.5", "borrow_limit": "60", "error_code": None}


def test_max_borrowable_51061_maps_to_zero(monkeypatch):
    # Binance 51061 "insufficient loanable assets" = a CONFIRMED 0 (pool exhausted),
    # not an unknown. Mapped to a definite "0" + error_code (the 400 body has no
    # borrowLimit). See reports/follow-ups/2026-07-borrowability-51061-zero-mapping.md.
    client = _make_client(monkeypatch, [
        _http_error(400, '{"code": 51061, "msg": "insufficient loanable assets"}'),
    ])
    assert client.fetch_max_borrowable("SPELL") == {
        "max_borrowable": "0", "borrow_limit": None, "error_code": "51061",
    }


def test_max_borrowable_unknown_positive_business_code_distinct_log(monkeypatch):
    # A POSITIVE Binance business code NOT in the zero set -> None + a distinct
    # discovery log (max_borrowable_business_error) so a real sample can surface.
    # Negative codes (-1xxx/-2xxx) stay on max_borrowable_failed (see :238).
    client = _make_client(monkeypatch, [_http_error(400, '{"code": 59999}')])
    assert client.fetch_max_borrowable("BTC") is None
    assert client.last_error == "max_borrowable_business_error:BTC:59999"


def test_max_borrowable_system_error_no_business_code(monkeypatch):
    # No business code in the body (network/5xx/timeout) -> None + system error log.
    client = _make_client(monkeypatch, [_http_error(500, "upstream")])
    assert client.fetch_max_borrowable("BTC") is None
    assert client.last_error.startswith("max_borrowable_failed:BTC")


# ---- 9. force-TTL exact-key bypass (2026-07-history-background-refresh-v1 §7) ----
def _inf(value):
    """Cache entry whose TTL never expires under the cached[0] > now check."""
    return (float("inf"), value)


def test_force_max_borrowable_evicts_only_that_assets_key(monkeypatch):
    # Pre-seed two assets' maxBorrowable keys; force BTC -> only BTC re-fetched,
    # the ETH key (and any unrelated key) is preserved.
    client = _make_client(
        monkeypatch,
        [(json.dumps({"amount": "9", "borrowLimit": "60"}), 200)],  # BTC force re-fetch
    )
    btc_key = ("GET", "/papi/v1/margin/maxBorrowable", (("asset", "BTC"),))
    eth_key = ("GET", "/papi/v1/margin/maxBorrowable", (("asset", "ETH"),))
    client._cache[btc_key] = _inf({"amount": "1", "borrowLimit": "2"})
    client._cache[eth_key] = _inf({"amount": "3", "borrowLimit": "4"})
    result = client.fetch_max_borrowable("BTC", force=True)
    assert result == {"max_borrowable": "9", "borrow_limit": "60", "error_code": None}
    # ETH key untouched
    assert client._cache[eth_key][1] == {"amount": "3", "borrowLimit": "4"}


def test_force_cost_leg_chain_evicts_only_single_asset_rate_keys(monkeypatch):
    # The multi-asset scheduled-batch E2 key is preserved; only the single-asset
    # BTC E2 + E2b keys are evicted and re-fetched. account/info and crossMargin-
    # Data are fetched through their normal caches and NOT force-evicted.
    client = _make_client(
        monkeypatch,
        [
            (json.dumps({"vipLevel": "0"}), 200),  # account/info
            (json.dumps([{"asset": "BTC", "nextHourlyInterestRate": "0.00000500"}]), 200),  # E2 BTC
            (json.dumps([{"asset": "BTC", "dailyInterestRate": "0.00010000",
                          "timestamp": "1"}]), 200),  # E2b BTC
            (json.dumps([{"coin": "BTC", "vipLevel": 0, "dailyInterest": "0.0005"}]), 200),  # crossMarginData
        ],
    )
    batch_key = (
        "GET", "/sapi/v1/margin/next-hourly-interest-rate",
        (("assets", "BTC,ETH"), ("isIsolated", "false")),
    )
    client._cache[batch_key] = _inf([{"asset": "BTC", "nextHourlyInterestRate": "stale"}])

    chain = client.fetch_cost_leg_chain(["BTC"], force=True)
    assert chain["chain_hit_tier"] == 1  # next_hourly hit
    # multi-asset batch key preserved (single-asset force never touches it)
    assert client._cache[batch_key][1] == [{"asset": "BTC", "nextHourlyInterestRate": "stale"}]
    # account/info fetched through normal cache, NOT force-evicted
    info_key = ("GET", "/sapi/v1/account/info", ())
    assert client._cache[info_key][1] == {"vipLevel": "0"}
    # the single-asset BTC E2 key now holds the fresh value
    btc_e2 = (
        "GET", "/sapi/v1/margin/next-hourly-interest-rate",
        (("assets", "BTC"), ("isIsolated", "false")),
    )
    assert client._cache[btc_e2][1] == [{"asset": "BTC", "nextHourlyInterestRate": "0.00000500"}]


def test_force_never_clears_whole_cache(monkeypatch):
    client = _make_client(
        monkeypatch,
        [(json.dumps({"amount": "1", "borrowLimit": "2"}), 200)],
    )
    # An unrelated classic key must survive a force refresh.
    classic_key = ("GET", "/sapi/v1/margin/allPairs", ())
    client._cache[classic_key] = _inf([])
    client.fetch_max_borrowable("BTC", force=True)
    assert classic_key in client._cache  # _cache.clear() was NOT called


def test_force_disabled_client_is_noop():
    client = PrivateClient(
        None, None, user_agent="t", timeout=5, recv_window=10000, ttl_seconds=3600,
        fast_ttl_seconds=60,
    )
    # disabled channel: force must not raise and must not mutate the cache.
    assert client.fetch_max_borrowable("BTC", force=True) is None
    assert client.fetch_cost_leg_chain(["BTC"], force=True) is None
    assert client._cache == {}


# ---- 10. S3b scheduled-only narrow seams (next-hourly / interestRateHistory) ----
def test_next_hourly_rates_unpacks_per_asset(monkeypatch):
    # Single batch (<=15 assets): one next-hourly call returns per-asset rows;
    # the narrow seam unpacks them into {asset: raw_hourly} WITHOUT ×24.
    client = _make_client(monkeypatch, [
        (json.dumps([
            {"asset": "BTC", "nextHourlyInterestRate": "0.00000500"},
            {"asset": "ETH", "nextHourlyInterestRate": "0.00000200"},
        ]), 200),
    ])
    rates = client.fetch_next_hourly_rates(["BTC", "ETH"])
    assert rates == {"BTC": "0.00000500", "ETH": "0.00000200"}


def test_next_hourly_rates_batches_at_15(monkeypatch):
    # 20 assets -> 2 batches (15 + 5); each batch is its own signed GET.
    assets = ["A%02d" % i for i in range(20)]
    batch1 = [{"asset": a, "nextHourlyInterestRate": "0.00000001"} for a in assets[:15]]
    batch2 = [{"asset": a, "nextHourlyInterestRate": "0.00000002"} for a in assets[15:]]
    client = _make_client(monkeypatch, [
        (json.dumps(batch1), 200),
        (json.dumps(batch2), 200),
    ])
    rates = client.fetch_next_hourly_rates(assets)
    assert set(rates.keys()) == set(assets)
    assert rates[assets[0]] == "0.00000001"   # batch 1
    assert rates[assets[19]] == "0.00000002"  # batch 2
    nh = [e for e in client.audit_log
          if e["logical_endpoint"] == "/sapi/v1/margin/next-hourly-interest-rate"]
    assert len(nh) == 2  # one signed GET per batch


def test_next_hourly_rates_partial_batch_failure_keeps_merged(monkeypatch):
    # First batch fails (500, not rate-limited -> no retry), second succeeds:
    # failed-batch assets are absent, successful-batch assets are present. No
    # tier-wide downgrade, no _cache.clear().
    assets = ["A%02d" % i for i in range(20)]
    client = _make_client(monkeypatch, [
        _http_error(500, "upstream"),  # batch 1 fails
        (json.dumps([{"asset": a, "nextHourlyInterestRate": "0.00000002"}
                     for a in assets[15:]]), 200),  # batch 2 succeeds
    ])
    rates = client.fetch_next_hourly_rates(assets)
    assert all(a not in rates for a in assets[:15])   # not fabricated
    assert all(rates[a] == "0.00000002" for a in assets[15:])
    assert client.last_error.startswith("next_hourly_batch_failed")


def test_next_hourly_rates_calls_only_next_hourly_endpoint(monkeypatch):
    # INV-1b: the narrow seam touches ONLY next-hourly-interest-rate; no
    # account/info, crossMarginData, or interestRateHistory calls.
    client = _make_client(monkeypatch, [
        (json.dumps([{"asset": "BTC", "nextHourlyInterestRate": "0.00000500"}]), 200),
    ])
    client.fetch_next_hourly_rates(["BTC"])
    endpoints = {e["logical_endpoint"] for e in client.audit_log}
    assert endpoints == {"/sapi/v1/margin/next-hourly-interest-rate"}


def test_next_hourly_rates_transport_reuses_at_1799_expires_at_1800(monkeypatch):
    # §5.5 / INV-5: slow transport TTL <=1800. _cached_get uses cached[0] > now:
    # at t0+1799 reuse, at t0+1800 the strict > fails -> a real signed GET fires
    # (no stale 30-min freshness masquerade).
    t = [0.0]
    monkeypatch.setattr(private_client.time, "monotonic", lambda: t[0])
    client = _make_client(
        monkeypatch,
        [(json.dumps([{"asset": "BTC", "nextHourlyInterestRate": "0.00000500"}]), 200),
         (json.dumps([{"asset": "BTC", "nextHourlyInterestRate": "0.00000600"}]), 200)],
        ttl_seconds=1800,
    )
    first = client.fetch_next_hourly_rates(["BTC"])
    assert first == {"BTC": "0.00000500"}
    t[0] = 1799.0
    reused = client.fetch_next_hourly_rates(["BTC"])
    assert reused == {"BTC": "0.00000500"}  # transport still fresh at 1799
    t[0] = 1800.0
    refreshed = client.fetch_next_hourly_rates(["BTC"])
    assert refreshed == {"BTC": "0.00000600"}  # 1800 -> real signed GET


def test_interest_rate_history_latest_returns_max_timestamp_daily(monkeypatch):
    # FR-6: returns the dailyInterestRate of the latest (max timestamp) point.
    client = _make_client(monkeypatch, [
        (json.dumps([
            {"asset": "BTC", "dailyInterestRate": "0.00010000", "timestamp": "100"},
            {"asset": "BTC", "dailyInterestRate": "0.00020000", "timestamp": "300"},
            {"asset": "BTC", "dailyInterestRate": "0.00015000", "timestamp": "200"},
        ]), 200),
    ])
    assert client.fetch_interest_rate_history_latest("BTC") == "0.00020000"


def test_interest_rate_history_latest_empty_returns_none(monkeypatch):
    client = _make_client(monkeypatch, [("[]", 200)])
    assert client.fetch_interest_rate_history_latest("BTC") is None


def test_interest_rate_history_latest_failure_returns_none(monkeypatch):
    client = _make_client(monkeypatch, [_http_error(500, "upstream")])
    assert client.fetch_interest_rate_history_latest("BTC") is None
    assert client.last_error.startswith("interest_rate_history_failed:BTC")


def test_interest_rate_history_latest_calls_only_that_endpoint(monkeypatch):
    client = _make_client(monkeypatch, [
        (json.dumps([{"asset": "BTC", "dailyInterestRate": "0.0001", "timestamp": "1"}]), 200),
    ])
    client.fetch_interest_rate_history_latest("BTC")
    endpoints = {e["logical_endpoint"] for e in client.audit_log}
    assert endpoints == {"/sapi/v1/margin/interestRateHistory"}


# ---- Stage 2026-07-cache-refresh-scheduler-v2 Correction 1: FR-2 / INV-5 ----
# The business timestamp must be captured at completion (AFTER the transport
# fetch) so transport_ts <= business_ts. Under non-zero clock skew a business-
# age-due (>=1800s) slow source then finds the transport entry already expired
# and makes a REAL signed GET (not a stale transport cache hit); at 1799s the
# slow source is reused; a failed fetch does not advance the business timestamp.
def test_inv5_completion_time_transport_le_business_and_real_get_at_1800(monkeypatch):
    from backend.config import Config
    from backend.services import snapshot_service
    from backend.services.snapshot_service import SnapshotService

    # Shared monotonic that advances a 1ms skew on EVERY call: the tick-now
    # read (refresh start) < transport-now (inside _cached_get) < completion
    # stamp (after the fetch returns).
    SKEW = 0.001
    base = [0.0]
    n = [0]

    def monotonic():
        n[0] += 1
        return base[0] + n[0] * SKEW

    monkeypatch.setattr(private_client.time, "monotonic", monotonic)
    monkeypatch.setattr(snapshot_service.time, "monotonic", monotonic)
    monkeypatch.setattr(private_client.time, "sleep", lambda *_: None)

    signed = [0]

    def fake_urlopen(req, timeout=None):
        signed[0] += 1
        return _FakeResp(json.dumps({"amount": "1.5", "borrowLimit": "2"}), 200)

    monkeypatch.setattr(private_client.urllib.request, "urlopen", fake_urlopen)

    private = PrivateClient(
        "k" * 64, "s" * 64, user_agent="t/1", timeout=5,
        recv_window=10000, ttl_seconds=1800, fast_ttl_seconds=60,
    )
    cfg = Config(offline=False, private_channel_enabled=True,
                 cache_ttl_seconds=60, private_channel_ttl_seconds=1800)
    service = SnapshotService(cfg)
    service._private = private

    # tick1: BTC max-borrowable. transport miss -> REAL signed GET; business
    # cache stamped at completion (INV-5: transport_ts <= business_ts).
    service._refresh_max_borrowable("BTC")
    assert signed[0] == 1
    assert "BTC" in service._max_borrowable_cache
    biz_ts = service._max_borrowable_cache["BTC"][0]
    tkey = ("GET", "/papi/v1/margin/maxBorrowable", (("asset", "BTC"),))
    transport_write_time = private._cache[tkey][0] - 1800  # expiry - lifetime
    assert transport_write_time <= biz_ts  # INV-5

    # 1799s later: business NOT due -> no refresh -> no signed GET (reuse).
    n[0] = 0
    base[0] = biz_ts + 1799
    assert service._max_borrowable_due("BTC", snapshot_service.time.monotonic(), 1800) is False

    # 1800s later: business due -> transport also due (transport_ts <= biz_ts)
    # -> REAL signed GET, NOT a stale transport cache hit.
    n[0] = 0
    base[0] = biz_ts + 1800
    assert service._max_borrowable_due("BTC", snapshot_service.time.monotonic(), 1800) is True
    service._refresh_max_borrowable("BTC")
    assert signed[0] == 2

    # A failed fetch does NOT advance the business timestamp (FR-2).
    def failing_urlopen(req, timeout=None):
        raise _http_error(500, "{}")

    monkeypatch.setattr(private_client.urllib.request, "urlopen", failing_urlopen)
    n[0] = 0
    base[0] = service._max_borrowable_cache["BTC"][0] + 1800  # business due
    before_ts = service._max_borrowable_cache["BTC"][0]
    service._refresh_max_borrowable("BTC")  # upstream fails -> fetch returns None
    assert service._max_borrowable_cache["BTC"][0] == before_ts  # NOT advanced
