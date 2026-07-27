"""Transport tests for the hedge-open live PAPI client (breakdown §3.7 / ADR-4).

No real network: ``urlopen`` is injected. Asserts the single-signer exit (the
POST body / GET query IS the ``signed_payload`` bytes, signature last), the
allowlist method/path -> base-URL mapping, one-shot transport (no retry), and the
typed :class:`HedgeHttpResponse` classification for 2xx / HTTPError / URLError /
timeout. No credential value ever leaves the process (the fake transport is the
only thing that sees the signed bytes).
"""
from __future__ import annotations

import io
import urllib.error

import http.client
import pytest

from backend.services import binance_signing
from backend.services.hedge_open_live_client import (
    DEFAULT_RECV_WINDOW_MS,
    HedgeHttpResponse,
    HedgeOpenLiveClient,
)


class _FakeResp:
    def __init__(self, status, body=b"", headers=None):
        self.status = status
        self._body = body if isinstance(body, bytes) else body.encode("utf-8")
        self.headers = headers if headers is not None else {}

    def read(self):
        return self._body

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _CapturingOpen:
    """Records every Request it sees and returns a queued response (or raises)."""

    def __init__(self, responses=None, error=None):
        self.requests = []
        self._responses = list(responses or [])
        self._error = error
        self.call_count = 0

    def __call__(self, req, timeout=None):
        self.call_count += 1
        self.requests.append(req)
        if self._error is not None:
            raise self._error
        if self._responses:
            return self._responses.pop(0)
        return _FakeResp(200, b"{}")


def _client(opener):
    return HedgeOpenLiveClient(
        api_key="key", api_secret="secret", user_agent="ua", urlopen=opener,
    )


def _http_error(code: int, body: bytes, *, retry_after=None) -> urllib.error.HTTPError:
    hdrs = http.client.HTTPMessage()
    if retry_after is not None:
        hdrs.add_header("Retry-After", str(retry_after))
    return urllib.error.HTTPError("https://papi.binance.com/x", code, "err", hdrs, io.BytesIO(body))


# ---- single signer: POST body / GET query IS the signed_payload bytes ----
def test_post_margin_order_body_is_signed_payload_signature_last():
    openr = _CapturingOpen([_FakeResp(200, b'{"orderId": 123, "status": "FILLED"}')])
    resp = _client(openr).post_margin_order({"symbol": "BTCUSDT", "side": "BUY"}, timestamp_ms=1000)
    assert resp.http_status == 200
    assert resp.body == {"orderId": 123, "status": "FILLED"}
    req = openr.requests[0]
    assert req.method == "POST"
    assert req.full_url == "https://papi.binance.com/papi/v1/margin/order"
    # API key rides in the X-MBX-APIKEY header (urllib normalizes the stored key).
    api_header_val = next(
        (v for k, v in req.headers.items() if "mbx" in k.lower()), None
    )
    assert api_header_val == "key"
    # Body is exactly signed_payload(params + timestamp + recvWindow, secret).
    expected = binance_signing.signed_payload(
        {"symbol": "BTCUSDT", "side": "BUY", "timestamp": "1000",
         "recvWindow": str(DEFAULT_RECV_WINDOW_MS)},
        "secret",
    )
    assert req.data.decode("utf-8") == expected
    assert "signature=" in req.data.decode("utf-8")


def test_post_um_order_hits_um_path():
    openr = _CapturingOpen([_FakeResp(200, b"{}")])
    _client(openr).post_um_order({"symbol": "BTCUSDT", "side": "SELL", "positionSide": "BOTH"},
                                 timestamp_ms=7)
    assert openr.requests[0].full_url == "https://papi.binance.com/papi/v1/um/order"
    assert openr.requests[0].method == "POST"


def test_query_margin_order_builds_orig_client_order_id_query():
    openr = _CapturingOpen([_FakeResp(200, b'{"orderId": 9, "status": "NEW"}')])
    _client(openr).query_margin_order("BTCUSDT", "hgo-x-s", timestamp_ms=5)
    req = openr.requests[0]
    assert req.method == "GET"
    url = req.full_url
    assert url.startswith("https://papi.binance.com/papi/v1/margin/order?")
    qs = url.split("?", 1)[1]
    expected = binance_signing.signed_payload(
        {"symbol": "BTCUSDT", "origClientOrderId": "hgo-x-s", "timestamp": "5",
         "recvWindow": str(DEFAULT_RECV_WINDOW_MS)},
        "secret",
    )
    assert qs == expected


def test_query_um_order_builds_orig_client_order_id_query():
    openr = _CapturingOpen([_FakeResp(200, b'{"orderId": 9}')])
    _client(openr).query_um_order("BTCUSDT", "hgo-x-p", timestamp_ms=5)
    assert openr.requests[0].full_url.startswith("https://papi.binance.com/papi/v1/um/order?")


def test_preflight_gets_hit_their_exact_paths():
    openr = _CapturingOpen([_FakeResp(200, b"[]"), _FakeResp(200, b'{"dualSidePosition": false}'),
                            _FakeResp(200, b"[]")])
    c = _client(openr)
    c.get_balance(timestamp_ms=1)
    c.get_position_side_dual(timestamp_ms=1)
    c.get_rate_limit_order(timestamp_ms=1)
    paths = [r.full_url.split("papi.binance.com", 1)[1].split("?", 1)[0] for r in openr.requests]
    assert paths == ["/papi/v1/balance", "/papi/v1/um/positionSide/dual",
                     "/papi/v1/rateLimit/order"]
    for r in openr.requests:
        assert r.method == "GET"


# ---- typed response classification ----
def test_2xx_body_parsed_to_dict_or_list():
    openr = _CapturingOpen([_FakeResp(200, b'[{"asset":"USDT"}]')])
    resp = _client(openr).get_balance(timestamp_ms=1)
    assert resp.http_status == 200
    assert resp.body == [{"asset": "USDT"}]
    assert resp.transport_error is None


def test_empty_body_is_none_not_error():
    openr = _CapturingOpen([_FakeResp(200, b"")])
    resp = _client(openr).get_balance(timestamp_ms=1)
    assert resp.http_status == 200
    assert resp.body is None


def test_non_json_body_is_none_not_crash():
    openr = _CapturingOpen([_FakeResp(200, b"<html>nope</html>")])
    resp = _client(openr).get_balance(timestamp_ms=1)
    assert resp.http_status == 200
    assert resp.body is None


def test_http_error_surfaces_status_and_body():
    openr = _CapturingOpen(error=_http_error(400, b'{"code":-2010,"msg":"insufficient"}'))
    resp = _client(openr).post_margin_order({"symbol": "BTCUSDT"}, timestamp_ms=1)
    assert resp.http_status == 400
    assert resp.body == {"code": -2010, "msg": "insufficient"}
    assert resp.transport_error is None


def test_http_error_parses_retry_after():
    openr = _CapturingOpen(error=_http_error(429, b'{"code":-1003}', retry_after=5))
    resp = _client(openr).post_margin_order({"symbol": "BTCUSDT"}, timestamp_ms=1)
    assert resp.http_status == 429
    assert resp.retry_after_seconds == 5


def test_urlerror_is_connection_error_no_status():
    openr = _CapturingOpen(error=urllib.error.URLError("connection refused"))
    resp = _client(openr).post_margin_order({"symbol": "BTCUSDT"}, timestamp_ms=1)
    assert resp.http_status is None
    assert resp.body is None
    assert resp.transport_error == "connection_error"


def test_timeout_is_timeout_error_no_status():
    openr = _CapturingOpen(error=TimeoutError())
    resp = _client(openr).post_margin_order({"symbol": "BTCUSDT"}, timestamp_ms=1)
    assert resp.http_status is None
    assert resp.transport_error == "timeout"


# ---- one-shot transport: never retried here ----
def test_single_transport_attempt_no_retry():
    # A 5xx is returned, NOT retried inside the client (the executor queries by
    # client ID instead). urlopen is called exactly once.
    openr = _CapturingOpen([_FakeResp(503, b'{"msg":"Unknown error"}')])
    _client(openr).post_margin_order({"symbol": "BTCUSDT"}, timestamp_ms=1)
    assert openr.call_count == 1
