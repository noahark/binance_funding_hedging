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
    assert resp.transport_error.startswith("connection_error")


def test_timeout_is_timeout_error_no_status():
    openr = _CapturingOpen(error=TimeoutError())
    resp = _client(openr).post_margin_order({"symbol": "BTCUSDT"}, timestamp_ms=1)
    assert resp.http_status is None
    assert resp.transport_error.startswith("timeout")


# ---- stage 2026-08-06: transport failures keep exception type + message ----
def test_transport_error_keeps_exception_type_and_reason():
    # URLError.reason is preferred over str(exc); the category word stays first.
    openr = _CapturingOpen(error=urllib.error.URLError(ConnectionResetError(54, "Connection reset by peer")))
    resp = _client(openr).post_margin_order({"symbol": "BTCUSDT"}, timestamp_ms=1)
    assert resp.transport_error.startswith("connection_error:URLError:")
    assert "Connection reset by peer" in resp.transport_error
    assert len(resp.transport_error) <= 200


def test_transport_error_caps_length_at_200():
    long_msg = "x" * 500
    openr = _CapturingOpen(error=urllib.error.URLError(long_msg))
    resp = _client(openr).post_margin_order({"symbol": "BTCUSDT"}, timestamp_ms=1)
    assert resp.transport_error.startswith("connection_error:URLError:")
    assert len(resp.transport_error) <= 200


def test_transport_error_drops_message_when_it_could_carry_a_url():
    # A message containing "http" or "?" could embed a signed URL/query — keep
    # only the exception type name (negative test; a credential leak costs more
    # than the diagnostic value).
    openr = _CapturingOpen(
        error=urllib.error.URLError("http://papi.binance.com/papi/v1/um/order?timestamp=1&signature=abc")
    )
    resp = _client(openr).post_margin_order({"symbol": "BTCUSDT"}, timestamp_ms=1)
    assert resp.transport_error == "connection_error:URLError"
    openr2 = _CapturingOpen(error=urllib.error.URLError("https://x/?apiKey=SECRET"))
    resp2 = _client(openr2).post_margin_order({"symbol": "BTCUSDT"}, timestamp_ms=1)
    assert resp2.transport_error == "connection_error:URLError"


def test_transport_error_keeps_plain_exception_detail():
    # The generic Exception branch keeps "<ExcType>:<ExcType>: <message>" shape.
    openr = _CapturingOpen(error=RuntimeError("proxy tunnel down"))
    resp = _client(openr).post_margin_order({"symbol": "BTCUSDT"}, timestamp_ms=1)
    assert resp.transport_error.startswith("RuntimeError:RuntimeError: proxy tunnel down")
    assert len(resp.transport_error) <= 200


# ---- one-shot transport: never retried here ----
def test_single_transport_attempt_no_retry():
    # A 5xx is returned, NOT retried inside the client (the executor queries by
    # client ID instead). urlopen is called exactly once.
    openr = _CapturingOpen([_FakeResp(503, b'{"msg":"Unknown error"}')])
    _client(openr).post_margin_order({"symbol": "BTCUSDT"}, timestamp_ms=1)
    assert openr.call_count == 1


# ---- regular-spot route allowlist (decision §E-2 / design §4) ----
from backend.services.hedge_open_live_client import ALLOWLIST as _ALLOWLIST  # noqa: E402

_REGULAR_SPOT_ENTRIES = {
    ("GET", "/sapi/v1/margin/restricted-asset"): "https://api.binance.com",
    ("POST", "/api/v3/order"): "https://api.binance.com",
    ("GET", "/api/v3/order"): "https://api.binance.com",
    ("GET", "/api/v3/account"): "https://api.binance.com",
    ("GET", "/api/v3/rateLimit/order"): "https://api.binance.com",
}


def test_allowlist_registers_five_regular_spot_paths_hardbound_to_api_binance():
    # All five exact (method, path) pairs are present and HARDBOUND to the public
    # spot host (never caller-supplied). The PAPI entries stay on papi.binance.com.
    for key, host in _REGULAR_SPOT_ENTRIES.items():
        assert _ALLOWLIST.get(key) == host, f"{key} not hardbound to api.binance.com"
    # PAPI entries are untouched.
    assert _ALLOWLIST[("POST", "/papi/v1/margin/order")] == "https://papi.binance.com"
    assert _ALLOWLIST[("GET", "/papi/v1/rateLimit/order")] == "https://papi.binance.com"


def test_unregistered_path_raises_before_transport():
    # deny-by-default: an unregistered (method, path) raises BEFORE any urlopen
    # call (no signing primitive runs, no request leaves the process).
    openr = _CapturingOpen()
    c = _client(openr)
    # A path that is NOT in the allowlist under any method/host.
    with pytest.raises(PermissionError):
        c._require_whitelisted("POST", "/api/v3/order/oco")
    assert openr.call_count == 0


def test_restricted_asset_is_unsigned_apikey_only():
    # The restricted-asset read carries ONLY X-MBX-APIKEY: no timestamp, no
    # recvWindow, no signature, no query string (recon restricted-asset.raw.json).
    body = (
        b'{"openLongRestrictedAsset":[],"maxCollateralExceededAsset":["LINK","TSLAB"]}'
    )
    openr = _CapturingOpen([_FakeResp(200, body)])
    resp = _client(openr).get_restricted_asset()
    assert resp.http_status == 200
    assert resp.body["maxCollateralExceededAsset"] == ["LINK", "TSLAB"]
    req = openr.requests[0]
    assert req.method == "GET"
    # Exact URL: no query string at all (no timestamp/recvWindow/signature).
    assert req.full_url == "https://api.binance.com/sapi/v1/margin/restricted-asset"
    assert "?" not in req.full_url
    api_header_val = next(
        (v for k, v in req.headers.items() if "mbx" in k.lower()), None
    )
    assert api_header_val == "key"


def test_regular_spot_writes_and_queries_hit_api_binance():
    # POST/GET /api/v3/order, GET /api/v3/account, GET /api/v3/rateLimit/order
    # all land on api.binance.com (the regular-spot host), distinct from PAPI.
    openr = _CapturingOpen(
        [
            _FakeResp(200, b'{"orderId": 1}'),  # post_spot_order
            _FakeResp(200, b'{"orderId": 1}'),  # query_spot_order
            _FakeResp(200, b'{"balances": []}'),  # get_spot_account
            _FakeResp(200, b'[]'),  # get_spot_rate_limit_order
        ]
    )
    c = _client(openr)
    c.post_spot_order({"symbol": "LINKUSDT", "side": "BUY"}, timestamp_ms=1)
    c.query_spot_order("LINKUSDT", "cid", timestamp_ms=1)
    c.get_spot_account(timestamp_ms=1)
    c.get_spot_rate_limit_order(timestamp_ms=1)
    urls = [r.full_url for r in openr.requests]
    assert urls[0] == "https://api.binance.com/api/v3/order"
    assert urls[1].startswith("https://api.binance.com/api/v3/order?")
    assert urls[2].startswith("https://api.binance.com/api/v3/account")
    assert urls[3].startswith("https://api.binance.com/api/v3/rateLimit/order")
    # All four are SIGNED (the POST carries timestamp+recvWindow+signature in its
    # body; the three GETs carry them in the query string) — unlike the unsigned
    # restricted-asset read.
    sent = [
        r.full_url + " " + (r.data.decode() if getattr(r, "data", None) else "")
        for r in openr.requests
    ]
    assert all("timestamp=" in s for s in sent)
    assert all("signature=" in s for s in sent)


# ---- 统一账户全仓杠杆还款：POST /papi/v1/margin/repay-debt（stage
#      2026-08-09-pm-margin-repay-v1）----
from urllib.parse import parse_qs  # noqa: E402

from backend.services.hedge_open_live_client import (  # noqa: E402
    MARGIN_REPAY_DEBT_PATH,
    REPAY_SPECIFY_ASSET,
)


def _form(req):
    """把 POST 表单 body 解析成单值字典（repay-debt 每个键只出现一次）。"""
    return {k: v[0] for k, v in parse_qs(req.data.decode("utf-8")).items()}


def test_allowlist_registers_margin_repay_debt_hardbound_to_papi():
    # 精确 (POST, /papi/v1/margin/repay-debt) 硬绑定 papi.binance.com；经典逐仓
    # /papi/v1/repayLoan（本通路禁止）不在白名单。
    assert _ALLOWLIST[("POST", MARGIN_REPAY_DEBT_PATH)] == "https://papi.binance.com"
    assert ("POST", "/papi/v1/repayLoan") not in _ALLOWLIST


def test_repay_margin_debt_omits_amount_when_none_and_fixes_usdt():
    # amount=None = 偿还全部：外发必须完全省略 amount（绝不发 amount=0），且固定
    # specifyRepayAssets=USDT。方法签名不接受偿还资产，外部无法覆盖。
    openr = _CapturingOpen([_FakeResp(200, b'{"success": true, "asset": "BNB", "amount": "1.5", "updateTime": 1700000000000}')])
    resp = _client(openr).repay_margin_debt("BNB", None, timestamp_ms=1)
    assert resp.http_status == 200 and resp.body["success"] is True
    req = openr.requests[0]
    assert req.method == "POST"
    assert req.full_url == "https://papi.binance.com" + MARGIN_REPAY_DEBT_PATH
    form = _form(req)
    assert form["asset"] == "BNB"
    assert form["specifyRepayAssets"] == REPAY_SPECIFY_ASSET
    assert "amount" not in form, "amount=None 必须完全省略，绝不发字面量 0"
    assert "signature" in form  # 签名在最后


def test_repay_margin_debt_sends_amount_verbatim_when_provided():
    # 正数十进制按原始字符串透传（全程不用 float）。
    openr = _CapturingOpen([_FakeResp(200, b'{"success": true, "asset": "BNB"}')])
    _client(openr).repay_margin_debt("BNB", "0.1250", timestamp_ms=1)
    form = _form(openr.requests[0])
    assert form["amount"] == "0.1250"  # 原样，不规格化
    assert form["specifyRepayAssets"] == "USDT"


def test_repay_margin_debt_is_one_shot_no_retry():
    # 与订单/划转一致：5xx 不重试，urlopen 恰好一次。
    openr = _CapturingOpen([_FakeResp(503, b'{"msg":"Unknown error"}')])
    _client(openr).repay_margin_debt("BNB", None, timestamp_ms=1)
    assert openr.call_count == 1


def test_repay_margin_debt_never_accepts_caller_specify_repay_assets():
    # 方法只接受 (asset, amount)：偿还资产在内部固定，无法由调用方注入第二个值。
    openr = _CapturingOpen([_FakeResp(200, b'{"success": true, "asset": "BNB"}')])
    _client(openr).repay_margin_debt("BNB", None, timestamp_ms=1)
    values = parse_qs(openr.requests[0].data.decode("utf-8"))["specifyRepayAssets"]
    assert values == ["USDT"]  # 单一值，无重复、无可覆盖
