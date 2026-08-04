"""HTTP wire tests for the dual-ledger flow-log routes (design §13.1–§13.4).

In-process ``ThreadingHTTPServer`` on an OS-assigned loopback port (no real
network, no real Binance). Proves the frozen contract over the wire:
``GET /api/private-ledger/flow-log`` is a pure local-ledger read (zero upstream
I/O) with ``Cache-Control: no-store`` on 200, the 400 invalid-window /
503-unconfigured branches, the §13.2 rule-13 empty state returned as 200 (never
503), and ``POST /api/private-ledger/refresh`` 200/429/409/503 with no body
field read.
"""
from __future__ import annotations

import http.client
import json
import os
import threading
from contextlib import contextmanager

import pytest

from backend.app import server as server_module
from backend.app.server import _Handler, build_server
from backend.config import Config
from backend.ledger_flow.service import LedgerFlowService
from backend.ledger_flow.store import LedgerStore

NOW = 1785798060000


class _StubSnapshot:
    """Minimal stand-in so build_server's ``service`` arg is satisfied unused."""

    def get_snapshot(self):
        return {}


class _StubClient:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.interest_pages = [{"total": 1, "rows": [
            {"txId": 1, "interestAccuredTime": NOW - 1000, "asset": "HOME",
             "rawAsset": "HOME", "principal": "1.0", "interest": "0.00008975",
             "interestRate": "0.00215396", "type": "PERIODIC"}]}]
        self.income_pages = [[{"symbol": "MUUSDT", "incomeType": "FUNDING_FEE",
                               "income": "0.08", "asset": "USDT", "info": "FUNDING_FEE",
                               "time": NOW - 1000, "tranId": 9, "tradeId": ""}]]

    def fetch_interest_history_page(self, *, start_time, end_time, current, size):
        idx = current - 1
        return self.interest_pages[idx] if idx < len(self.interest_pages) else {"total": 0, "rows": []}

    def fetch_um_income_page(self, *, start_time, end_time, page, limit):
        idx = page - 1
        return self.income_pages[idx] if idx < len(self.income_pages) else []


def _ledger_svc(tmp_path, enabled=True):
    store = LedgerStore(os.path.join(tmp_path, "l.sqlite3"))
    svc = LedgerFlowService(store, _StubClient(enabled=enabled), now_ms=lambda: NOW)
    return svc


@contextmanager
def _server(ledger_flow_service):
    cfg = Config(bind_port=0)
    build_server(cfg, _StubSnapshot())
    saved = _Handler.ledger_flow_service
    _Handler.ledger_flow_service = ledger_flow_service
    httpd = build_server(cfg, _StubSnapshot())
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    try:
        yield host, port
    finally:
        httpd.shutdown()
        httpd.server_close()
        _Handler.ledger_flow_service = saved


def _req(host, port, method, path, body=None, content_type=None):
    conn = http.client.HTTPConnection(host, port, timeout=5)
    headers = {}
    data = None
    if body is not None:
        data = body.encode("utf-8") if isinstance(body, str) else body
        headers["Content-Length"] = str(len(data))
        if content_type:
            headers["Content-Type"] = content_type
    conn.request(method, path, body=data, headers=headers)
    resp = conn.getresponse()
    out = (resp.status, resp.getheader("Cache-Control"), resp.read())
    conn.close()
    return out


# --------------------------------------------------------------------------- #
# GET flow-log
# --------------------------------------------------------------------------- #
def test_get_flow_log_200_has_no_store_and_shape(tmp_path):
    svc = _ledger_svc(tmp_path)
    svc.run_once("backfill")  # populate
    svc.mark_scheduler_enabled()
    with _server(svc) as (host, port):
        status, cache_ctrl, body = _req(host, port, "GET",
                                        f"/api/private-ledger/flow-log?start=0&end={NOW}")
    payload = json.loads(body)
    assert status == 200
    assert cache_ctrl == "no-store"
    assert payload["schema_version"] == "private-ledger/v2"
    assert payload["scheduler_enabled"] is True
    assert payload["interest"]["row_count"] == 1
    assert payload["interest"]["rows"][0]["tx_id"] == "1"           # ID is a string
    assert payload["interest"]["summary_by_asset"][0]["interest_total"] == "0.00008975"


def test_get_flow_log_empty_state_returns_200_not_503(tmp_path):
    svc = _ledger_svc(tmp_path)  # empty store, never run
    with _server(svc) as (host, port):
        status, cache_ctrl, body = _req(host, port, "GET",
                                        f"/api/private-ledger/flow-log?start=0&end={NOW}")
    payload = json.loads(body)
    assert status == 200                                  # never 503 on empty
    assert cache_ctrl == "no-store"
    assert payload["last_run"] is None
    assert payload["coverage"]["start_ms"] is None and payload["coverage"]["end_ms"] is None
    assert payload["coverage"]["by_source"] == {"interest": None, "income": None}
    assert payload["delta"]["complete"] is False


def test_get_flow_log_400_missing_param(tmp_path):
    svc = _ledger_svc(tmp_path)
    with _server(svc) as (host, port):
        status, cache_ctrl, body = _req(host, port, "GET", "/api/private-ledger/flow-log?start=0")
    assert status == 400
    assert cache_ctrl is None                             # no-store only on 200
    assert json.loads(body)["error"] == "invalid_window"


def test_get_flow_log_400_non_numeric_and_start_ge_end(tmp_path):
    svc = _ledger_svc(tmp_path)
    with _server(svc) as (host, port):
        s1, _, b1 = _req(host, port, "GET", f"/api/private-ledger/flow-log?start=abc&end={NOW}")
        s2, _, b2 = _req(host, port, "GET", f"/api/private-ledger/flow-log?start={NOW}&end={NOW}")
    assert s1 == 400 and json.loads(b1)["error"] == "invalid_window"
    assert s2 == 400 and json.loads(b2)["error"] == "invalid_window"


def test_get_flow_log_503_when_unconfigured(tmp_path):
    with _server(None) as (host, port):
        status, _, body = _req(host, port, "GET", f"/api/private-ledger/flow-log?start=0&end={NOW}")
    assert status == 503
    assert json.loads(body)["error"] == "flow_log_unavailable"


def test_post_flow_log_not_routed_as_get(tmp_path):
    # POST to the GET-only flow-log path must not produce a flow-log response.
    svc = _ledger_svc(tmp_path)
    with _server(svc) as (host, port):
        status, _, body = _req(host, port, "POST",
                               f"/api/private-ledger/flow-log?start=0&end={NOW}")
    assert status == 404                                 # falls through, not handled


# --------------------------------------------------------------------------- #
# POST refresh
# --------------------------------------------------------------------------- #
def test_post_refresh_200_advances_coverage(tmp_path):
    svc = _ledger_svc(tmp_path, enabled=True)
    with _server(svc) as (host, port):
        status, cache_ctrl, body = _req(host, port, "POST", "/api/private-ledger/refresh",
                                        body="{}", content_type="application/json")
    payload = json.loads(body)
    assert status == 200
    assert cache_ctrl == "no-store"
    assert payload["kind"] == "manual"
    assert payload["interest_new_row_count"] == 1
    assert svc._store.get_coverage()["interest_end_ms"] == NOW


def test_post_refresh_drains_body_and_ignores_fields(tmp_path):
    svc = _ledger_svc(tmp_path, enabled=True)
    # A body carrying a forbidden window field is read and discarded, never used.
    with _server(svc) as (host, port):
        status, _, body = _req(host, port, "POST", "/api/private-ledger/refresh",
                               body=json.dumps({"start": 1, "end": 2, "window": "evil"}),
                               content_type="application/json")
    assert status == 200


def test_post_refresh_429_when_busy(tmp_path):
    svc = _ledger_svc(tmp_path, enabled=True)
    svc._flight_lock.acquire()  # pretend a run is in flight
    try:
        with _server(svc) as (host, port):
            status, cache_ctrl, body = _req(host, port, "POST", "/api/private-ledger/refresh")
    finally:
        svc._flight_lock.release()
    assert status == 429
    assert cache_ctrl is None
    assert json.loads(body)["error"] == "flow_log_busy"


def test_post_refresh_409_when_disabled(tmp_path):
    svc = _ledger_svc(tmp_path, enabled=False)
    with _server(svc) as (host, port):
        status, cache_ctrl, body = _req(host, port, "POST", "/api/private-ledger/refresh")
    assert status == 409
    assert cache_ctrl is None
    assert json.loads(body)["error"] == "private_channel_disabled"


def test_post_refresh_503_when_unconfigured(tmp_path):
    with _server(None) as (host, port):
        status, _, body = _req(host, port, "POST", "/api/private-ledger/refresh",
                               body="{}", content_type="application/json")
    assert status == 503
    assert json.loads(body)["error"] == "flow_log_unavailable"
