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


def _make_client(monkeypatch, responses, *, enabled=True):
    """PrivateClient whose urlopen yields `responses` in order.

    Each item is either a (body_str, status_int) tuple or an HTTPError to raise.
    """
    key = "k" * 64 if enabled else None
    secret = "s" * 64 if enabled else None
    client = PrivateClient(
        key, secret, user_agent="test/1.0", timeout=5,
        recv_window=10000, ttl_seconds=3600, fast_ttl_seconds=60,
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
