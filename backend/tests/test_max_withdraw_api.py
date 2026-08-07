"""Wire tests for ``GET /api/private-account/max-withdraw`` (Q4, 2026-08-07).

In-process ``ThreadingHTTPServer`` on an OS-assigned loopback port; the private
client is a stub, so no real Binance call happens.

The contract this pins down is mostly about honesty: an unreadable figure comes
back as ``max_withdraw: null`` with 200 (never a fabricated number, never a
fallback to ``crossMarginFree`` — substituting the available balance for the
max-transferable is exactly the defect this endpoint exists to fix), and the
read is forced (uncached) because the figure moves with price.
"""
from __future__ import annotations

import http.client
import json
import threading
from contextlib import contextmanager

from backend.app.server import _Handler, build_server
from backend.config import Config


class _StubClient:
    def __init__(self, result=None, enabled=True, last_error=None):
        self.enabled = enabled
        self.last_error = last_error
        self._result = result
        self.calls = []

    def fetch_max_withdraw(self, asset, force=False):
        self.calls.append((asset, force))
        return self._result


class _StubSnapshot:
    def __init__(self, client=None):
        self.private_client = client

    def get_snapshot(self):
        return {}


@contextmanager
def _server(snapshot):
    httpd = build_server(Config(bind_port=0), snapshot)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_address[:2]
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(host, port, path):
    conn = http.client.HTTPConnection(host, port, timeout=5)
    conn.request("GET", path)
    resp = conn.getresponse()
    out = (resp.status, resp.read())
    conn.close()
    return out


def test_max_withdraw_returns_the_figure():
    client = _StubClient({"max_withdraw": "222.35"})
    with _server(_StubSnapshot(client)) as (host, port):
        status, body = _get(host, port, "/api/private-account/max-withdraw?asset=USDT")
    assert status == 200
    assert json.loads(body) == {"asset": "USDT", "max_withdraw": "222.35", "error": None}
    # force=True: 该值随价格波动，缓存住就会在转出那一刻给出过期的数。
    assert client.calls == [("USDT", True)]


def test_max_withdraw_unreadable_is_null_not_a_guess():
    client = _StubClient(None, last_error="max_withdraw_failed:USDT:timeout")
    with _server(_StubSnapshot(client)) as (host, port):
        status, body = _get(host, port, "/api/private-account/max-withdraw?asset=USDT")
    payload = json.loads(body)
    assert status == 200  # 读不到不是错误，是「不知道」——调用方要能区分它和 0
    assert payload["max_withdraw"] is None
    assert payload["error"] == "max_withdraw_failed:USDT:timeout"


def test_max_withdraw_normalises_asset_case():
    client = _StubClient({"max_withdraw": "1"})
    with _server(_StubSnapshot(client)) as (host, port):
        _get(host, port, "/api/private-account/max-withdraw?asset=usdt")
    assert client.calls == [("USDT", True)]


def test_max_withdraw_rejects_missing_asset():
    client = _StubClient({"max_withdraw": "1"})
    with _server(_StubSnapshot(client)) as (host, port):
        status, body = _get(host, port, "/api/private-account/max-withdraw")
    assert status == 400
    assert json.loads(body)["error"] == "invalid_asset"
    assert client.calls == []  # 校验先于读取，不拿垃圾参数去打交易所


def test_max_withdraw_503_when_private_client_disabled():
    with _server(_StubSnapshot(_StubClient(enabled=False))) as (host, port):
        status, body = _get(host, port, "/api/private-account/max-withdraw?asset=USDT")
    assert status == 503
    assert json.loads(body)["error"] == "private_account_unavailable"
