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
        recv_window=10000, ttl_seconds=3600,
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


def test_whitelist_accepts_exactly_four_get_endpoints():
    assert len(private_client.WHITELIST) == 4
    for method, path in private_client.WHITELIST:
        assert method == "GET"
        assert PrivateClient._require_whitelisted(method, path)


def test_whitelist_matches_status_json_endpoint_whitelist():
    """The four whitelisted pairs must equal status.json endpoint_whitelist."""
    import json as _json
    status = _json.loads(
        (REPO_ROOT / "reports/agent-runs/2026-07-phase2-borrow-sort-v1/status.json").read_text()
    )
    expected = {tuple(pair) for pair in status["endpoint_whitelist"]}
    assert set(private_client.WHITELIST.keys()) == expected


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
    )
    assert client.enabled is False
    assert client.fetch_classic_reference() is None
    assert client.fetch_max_borrowable("BTC") is None
    assert client.last_error == "private_channel_disabled"


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
    assert result == {"max_borrowable": "1.0", "borrow_limit": "60"}
    assert len(client.audit_log) == 2  # both attempts logged


def test_rate_limit_429_also_retries(monkeypatch):
    client = _make_client(monkeypatch, [
        ('{"code":-1003,"msg":"x"}', 429),
        (json.dumps({"amount": "2", "borrowLimit": "5"}), 200),
    ])
    assert client.fetch_max_borrowable("ETH") == {"max_borrowable": "2", "borrow_limit": "5"}


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
    assert client.fetch_max_borrowable("BTC") == {"max_borrowable": "1.5", "borrow_limit": "60"}
