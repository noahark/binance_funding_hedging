"""Tests for the exact-path PM borrow transport (Boundary C §3 / §8.1).

No network: ``urlopen`` is a recording fake injected via the constructor with
DUMMY credentials. Asserts the frozen allowlist (deny-before-signing), exact
host/path/method, the POST body == signed ``application/x-www-form-urlencoded``
bytes, credential presence, transport-error classification, ``Retry-After``
parsing, and one-shot semantics (no internal retry).
"""
from __future__ import annotations

import io
import json
import urllib.error

import pytest

from backend.services import binance_signing
from backend.services.portfolio_margin_borrow_client import (
    ALLOWLIST,
    BorrowHttpResponse,
    PortfolioMarginBorrowClient,
)

DUMMY_KEY = "dummy-borrow-key"
DUMMY_SECRET = "dummy-borrow-secret"


class _CtxResp:
    def __init__(self, body_bytes, status, headers=None):
        self._body = body_bytes
        self.status = status
        self._headers = headers or {}

    def read(self):
        return self._body

    def getcode(self):
        return self.status

    @property
    def headers(self):
        return self._headers

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class RecordingTransport:
    """Injectable urlopen: records every Request and returns scripted responses.

    Each scripted item is either an Exception to raise (HTTPError / TimeoutError /
    URLError) or a ``(status, body_obj, headers)`` tuple.
    """

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        status, body_obj, headers = item
        body_bytes = json.dumps(body_obj).encode("utf-8") if body_obj is not None else b""
        return _CtxResp(body_bytes, status, headers)


def _client(transport, *, key=DUMMY_KEY, secret=DUMMY_SECRET):
    return PortfolioMarginBorrowClient(
        key, secret, user_agent="test/1.0", urlopen=transport,
    )


def _http_error(code, body="", retry_after=None):
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return urllib.error.HTTPError(
        "https://papi.binance.com/papi/v1/marginLoan", code, "err", headers,
        io.BytesIO(body.encode("utf-8")),
    )


# ---------------------------------------------------------------------------
# Allowlist (deny-before-signing)
# ---------------------------------------------------------------------------
def test_allowlist_contains_exactly_the_borrow_post():
    # DEC-2026-08-21: the loan-record GET was removed with the reconciliation
    # subsystem, so the borrow client's only signed endpoint is the POST.
    assert set(ALLOWLIST.keys()) == {("POST", "/papi/v1/marginLoan")}
    assert all(host == "https://papi.binance.com" for host in ALLOWLIST.values())


def test_gate_rejects_unknown_path_before_signing():
    with pytest.raises(PermissionError):
        PortfolioMarginBorrowClient._require_whitelisted("POST", "/papi/v1/marginLoanX")
    with pytest.raises(PermissionError):
        PortfolioMarginBorrowClient._require_whitelisted("GET", "/papi/v1/margin/wrong")


def test_gate_rejects_non_whitelisted_method_on_path():
    # The allowlist is POST-on-the-borrow-path only: no method on the removed
    # loan-record path, and no DELETE anywhere.
    with pytest.raises(PermissionError):
        PortfolioMarginBorrowClient._require_whitelisted("POST", "/papi/v1/margin/marginLoan")
    with pytest.raises(PermissionError):
        PortfolioMarginBorrowClient._require_whitelisted("DELETE", "/papi/v1/marginLoan")


def test_gate_accepts_the_whitelisted_post():
    assert PortfolioMarginBorrowClient._require_whitelisted("POST", "/papi/v1/marginLoan")


# ---------------------------------------------------------------------------
# Exact host / path / method / body (recording transport, dummy creds)
# ---------------------------------------------------------------------------
def test_post_targets_exact_host_path_method():
    transport = RecordingTransport([(200, {"tranId": 12345}, {})])
    client = _client(transport)
    client.post_margin_loan("BTC", "1.5", timestamp_ms=1000)
    assert len(transport.requests) == 1
    req = transport.requests[0]
    assert req.full_url == "https://papi.binance.com/papi/v1/marginLoan"
    assert req.method == "POST"


def test_post_body_is_signed_form_urlencoded_bytes():
    transport = RecordingTransport([(200, {"tranId": 1}, {})])
    client = _client(transport)
    client.post_margin_loan("BTC", "1.5", timestamp_ms=1000, recv_window_ms=60000)
    req = transport.requests[0]
    sent_body = req.data.decode("utf-8")
    # The exact params that were signed (canonical, sorted):
    expected_params = {
        "asset": "BTC", "amount": "1.5", "timestamp": "1000", "recvWindow": "60000",
    }
    assert sent_body == binance_signing.signed_payload(expected_params, DUMMY_SECRET)
    # Content-Type is the archived form; X-MBX-APIKEY carries the key (not the secret)
    assert req.headers.get("Content-type") == "application/x-www-form-urlencoded"
    assert req.headers.get("X-mbx-apikey") == DUMMY_KEY
    # signature is the LAST field of the body
    assert sent_body.endswith("&signature=" + binance_signing.sign(
        binance_signing.build_total_params(expected_params), DUMMY_SECRET))


# ---------------------------------------------------------------------------
# Credential presence
# ---------------------------------------------------------------------------
def test_credentials_present_only_with_both_key_and_secret():
    assert _client(RecordingTransport([])).credentials_present is True
    assert _client(RecordingTransport([]), key="").credentials_present is False
    assert _client(RecordingTransport([]), secret="").credentials_present is False
    assert _client(RecordingTransport([]), key="", secret="").credentials_present is False


# ---------------------------------------------------------------------------
# Transport-error classification + Retry-After parsing
# ---------------------------------------------------------------------------
def test_timeout_yields_transport_error_with_no_status():
    transport = RecordingTransport([TimeoutError("timed out")])
    resp = _client(transport).post_margin_loan("BTC", "1", timestamp_ms=1)
    assert isinstance(resp, BorrowHttpResponse)
    assert resp.http_status is None
    assert resp.transport_error == "timeout"
    assert resp.body is None


def test_connection_error_yields_transport_error():
    transport = RecordingTransport([urllib.error.URLError("refused")])
    resp = _client(transport).post_margin_loan("BTC", "1", timestamp_ms=1)
    assert resp.http_status is None
    assert resp.transport_error == "connection_error"


def test_http_error_status_and_retry_after_captured():
    transport = RecordingTransport([_http_error(429, '{"code":-1003}', retry_after=120)])
    resp = _client(transport).post_margin_loan("BTC", "1", timestamp_ms=1)
    assert resp.http_status == 429
    assert resp.transport_error is None
    assert resp.retry_after_seconds == 120
    assert resp.body == {"code": -1003}


def test_retry_after_non_numeric_is_none():
    transport = RecordingTransport([_http_error(429, "{}", retry_after="soon")])
    resp = _client(transport).post_margin_loan("BTC", "1", timestamp_ms=1)
    assert resp.retry_after_seconds is None


def test_success_body_parsed():
    transport = RecordingTransport([(200, {"tranId": 777}, {})])
    resp = _client(transport).post_margin_loan("BTC", "1", timestamp_ms=1)
    assert resp.http_status == 200
    assert resp.body == {"tranId": 777}


# ---------------------------------------------------------------------------
# One-shot (no internal retry)
# ---------------------------------------------------------------------------
def test_one_transport_attempt_per_call_no_retry():
    transport = RecordingTransport([_http_error(500, "boom")])
    _client(transport).post_margin_loan("BTC", "1", timestamp_ms=1)
    assert len(transport.requests) == 1  # exactly one POST, no retry on 5xx
