"""Tests for the exact-path PM borrow transport (Boundary C §3 / §8.1).

No network: ``urlopen`` is a recording fake injected via the constructor with
DUMMY credentials. Asserts the frozen allowlist (deny-before-signing), exact
host/path/method, the POST body == signed ``application/x-www-form-urlencoded``
bytes, the GET query carries the signature, credential presence, transport-error
classification, ``Retry-After`` parsing, ``records_from`` shape, and one-shot
semantics (no internal retry).
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
def test_allowlist_contains_exactly_two_pairs():
    assert set(ALLOWLIST.keys()) == {
        ("POST", "/papi/v1/marginLoan"),
        ("GET", "/papi/v1/margin/marginLoan"),
    }
    assert all(host == "https://papi.binance.com" for host in ALLOWLIST.values())


def test_gate_rejects_unknown_path_before_signing():
    with pytest.raises(PermissionError):
        PortfolioMarginBorrowClient._require_whitelisted("POST", "/papi/v1/marginLoanX")
    with pytest.raises(PermissionError):
        PortfolioMarginBorrowClient._require_whitelisted("GET", "/papi/v1/margin/wrong")


def test_gate_rejects_non_whitelisted_method_on_path():
    # GET-only allowlist has no POST on the loan-record path, and no DELETE anywhere.
    with pytest.raises(PermissionError):
        PortfolioMarginBorrowClient._require_whitelisted("POST", "/papi/v1/margin/marginLoan")
    with pytest.raises(PermissionError):
        PortfolioMarginBorrowClient._require_whitelisted("DELETE", "/papi/v1/marginLoan")


def test_gate_accepts_the_two_whitelisted_pairs():
    assert PortfolioMarginBorrowClient._require_whitelisted("POST", "/papi/v1/marginLoan")
    assert PortfolioMarginBorrowClient._require_whitelisted("GET", "/papi/v1/margin/marginLoan")


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


def test_get_targets_exact_host_path_and_carries_signature():
    transport = RecordingTransport([(200, {"rows": [], "total": 0}, {})])
    client = _client(transport)
    client.fetch_loan_records("BTC", timestamp_ms=2000)
    assert len(transport.requests) == 1
    req = transport.requests[0]
    assert req.method == "GET"
    assert req.full_url.startswith("https://papi.binance.com/papi/v1/margin/marginLoan?")
    assert "&signature=" in req.full_url
    # No Content-Type/body on a GET
    assert req.data is None


def test_get_with_tx_id_precedence():
    transport = RecordingTransport([(200, {"rows": [], "total": 0}, {})])
    client = _client(transport)
    client.fetch_loan_records("BTC", timestamp_ms=2000, tx_id="999")
    url = transport.requests[0].full_url
    assert "txId=999" in url
    assert "startTime=" not in url  # txId path does not add a window


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


# ---------------------------------------------------------------------------
# records_from shape
# ---------------------------------------------------------------------------
def test_records_from_parses_rows_envelope():
    # Documented 200 contract is {"rows": [...], "total": N} (archived evidence).
    resp = BorrowHttpResponse(
        200, {"rows": [{"txId": 1, "status": "CONFIRMED"}], "total": 1}, "{}", None, None
    )
    rows = PortfolioMarginBorrowClient.records_from(resp)
    assert rows == [{"txId": 1, "status": "CONFIRMED"}]


def test_records_from_filters_non_dict_rows():
    resp = BorrowHttpResponse(
        200, {"rows": [{"txId": 1}, "junk", 5, None], "total": 1}, "{}", None, None
    )
    assert PortfolioMarginBorrowClient.records_from(resp) == [{"txId": 1}]


def test_records_from_fail_closed_on_non_envelope_or_error():
    # A real successful GET uses the rows envelope; a top-level list (the old
    # wrong assumption), a transport error, an HTTP error, a malformed rows
    # member, or a missing envelope must all yield [] so nothing proves success.
    assert PortfolioMarginBorrowClient.records_from(
        BorrowHttpResponse(200, [{"txId": 1}], "[]", None, None)) == []  # top-level list
    assert PortfolioMarginBorrowClient.records_from(
        BorrowHttpResponse(200, {"rows": "not-a-list"}, "{}", None, None)) == []
    assert PortfolioMarginBorrowClient.records_from(
        BorrowHttpResponse(200, {"total": 0}, "{}", None, None)) == []  # no rows key
    assert PortfolioMarginBorrowClient.records_from(
        BorrowHttpResponse(400, {"rows": []}, "{}", None, None)) == []
    assert PortfolioMarginBorrowClient.records_from(
        BorrowHttpResponse(None, None, "", "timeout", None)) == []


def test_declared_total_reads_envelope_total():
    resp = BorrowHttpResponse(200, {"rows": [], "total": 3}, "{}", None, None)
    assert PortfolioMarginBorrowClient.declared_total(resp) == 3


def test_declared_total_fail_closed():
    # Missing/bool/non-int/negative total, non-envelope body, transport/HTTP error.
    for body in ({"rows": []}, {"rows": [], "total": True},
                 {"rows": [], "total": "3"}, {"rows": [], "total": -1}):
        assert PortfolioMarginBorrowClient.declared_total(
            BorrowHttpResponse(200, body, "{}", None, None)) is None
    # top-level list (not the envelope) -> None
    assert PortfolioMarginBorrowClient.declared_total(
        BorrowHttpResponse(200, [{"txId": 1}], "[]", None, None)) is None
    assert PortfolioMarginBorrowClient.declared_total(
        BorrowHttpResponse(None, None, "", "timeout", None)) is None
    assert PortfolioMarginBorrowClient.declared_total(
        BorrowHttpResponse(400, {"rows": [], "total": 0}, "{}", None, None)) is None


# ---------------------------------------------------------------------------
# raw_rows — unfiltered envelope rows (matcher fail-closed input)
# ---------------------------------------------------------------------------
def test_raw_rows_returns_unfiltered_envelope_rows():
    # raw_rows returns the rows list AS-IS (no non-dict filtering) so the matcher
    # can fail-closed on a malformed member instead of silently dropping it.
    resp = BorrowHttpResponse(
        200, {"rows": [{"txId": 1}, "junk", 5, None], "total": 4}, "{}", None, None
    )
    assert PortfolioMarginBorrowClient.raw_rows(resp) == [{"txId": 1}, "junk", 5, None]


def test_raw_rows_fail_closed_on_non_envelope_or_error():
    # Any non-envelope shape or transport/HTTP error yields None so the matcher
    # treats the read as unprovable (records_from maps the same inputs to []).
    assert PortfolioMarginBorrowClient.raw_rows(
        BorrowHttpResponse(200, [{"txId": 1}], "[]", None, None)) is None  # top-level list
    assert PortfolioMarginBorrowClient.raw_rows(
        BorrowHttpResponse(200, {"rows": "not-a-list"}, "{}", None, None)) is None
    assert PortfolioMarginBorrowClient.raw_rows(
        BorrowHttpResponse(200, {"total": 0}, "{}", None, None)) is None  # no rows key
    assert PortfolioMarginBorrowClient.raw_rows(
        BorrowHttpResponse(400, {"rows": []}, "{}", None, None)) is None
    assert PortfolioMarginBorrowClient.raw_rows(
        BorrowHttpResponse(None, None, "", "timeout", None)) is None
