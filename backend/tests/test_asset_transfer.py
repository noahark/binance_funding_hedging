"""资产互转 `POST /api/asset-transfer` 的契约与幂等测试（T1，全离线）。

进程内 ``ThreadingHTTPServer`` + 桩客户端 + 临时 SQLite：无网络、无凭证、
无真实币安调用。重点证明三件在**动钱路径**上最容易出事的性质：

1. **幂等**——币安 `/sapi/v1/asset/transfer` 没有幂等键，重复提交会真的转两次；
   同一 ``client_request_id`` 的第二次请求必须**零外发**（以桩调用计数断言）。
2. **超时不重试**——超时/5xx 记 ``unknown`` 而非 ``failed``：钱可能已经转了，
   把它显示成失败会诱导用户重试，导致转两次。
3. **方向映射在服务端**——请求体不接受币安 transfer type。
"""
from __future__ import annotations

import http.client
import json
import sqlite3
import threading
from contextlib import contextmanager

import pytest

from backend.app.server import _Handler, build_server
from backend.asset_transfer.store import AssetTransferStore
from backend.config import Config
from backend.services.hedge_open_live_client import (
    TRANSFER_TYPE_MAIN_PM,
    TRANSFER_TYPE_PM_MAIN,
    HedgeHttpResponse,
)

_RESULT_KEYS = {
    "client_request_id", "from_account", "to_account", "asset", "amount",
    "status", "tran_id", "error_code", "error_message",
}

_CRID = "11111111-2222-3333-4444-555555555555"
_CRID2 = "99999999-8888-7777-6666-555555555555"


class _StubSnapshotService:
    """只提供白名单校验需要的余额；``ready=False`` 模拟快照未就绪。"""

    def __init__(self, *, ready=True):
        self._ready = ready

    def get_snapshot(self):
        if not self._ready:
            raise RuntimeError("snapshot not ready")
        return {
            "rows": [],
            "private_account": {
                "balances_unified": [{"asset": "USDT"}, {"asset": "BNB"}],
                "balances_spot": [{"asset": "USDT"}, {"asset": "XVG"}],
            },
        }


class _StubTransferClient:
    """记录每次外发，按预设脚本回应。``calls`` 的长度即真实外发次数。"""

    def __init__(self, responses=None, raises=None):
        self.calls = []
        self._responses = list(responses or [])
        self._raises = raises

    def universal_transfer(self, type_, asset, amount, *, timestamp_ms, recv_window_ms=None):
        self.calls.append({"type": type_, "asset": asset, "amount": amount})
        if self._raises is not None:
            raise self._raises
        if self._responses:
            return self._responses.pop(0)
        return _resp(200, {"tranId": 123456789})


def _resp(status, body, *, transport_error=None):
    return HedgeHttpResponse(
        http_status=status,
        body=body,
        raw_body=json.dumps(body) if body is not None else "",
        transport_error=transport_error,
        retry_after_seconds=None,
    )


@contextmanager
def _server(tmp_path, *, client=None, store=True, snapshot_ready=True):
    cfg = Config(bind_port=0)
    srv = build_server(cfg, _StubSnapshotService(ready=snapshot_ready), None, None)
    transfer_store = (
        AssetTransferStore(str(tmp_path / "asset-transfer.sqlite3")) if store else None
    )
    _Handler.asset_transfer_store = transfer_store
    _Handler.asset_transfer_client = client
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    host, port = srv.server_address[:2]
    try:
        yield host, port, transfer_store
    finally:
        srv.shutdown()
        srv.server_close()
        # 类属性会跨测试泄漏，必须复位。
        _Handler.asset_transfer_store = None
        _Handler.asset_transfer_client = None


def _post(host, port, body):
    conn = http.client.HTTPConnection(host, port, timeout=5)
    data = json.dumps(body).encode("utf-8")
    conn.request("POST", "/api/asset-transfer", body=data, headers={
        "Content-Type": "application/json", "Content-Length": str(len(data)),
    })
    resp = conn.getresponse()
    out = resp.status, json.loads(resp.read().decode("utf-8"))
    conn.close()
    return out


def _body(**over):
    base = {
        "client_request_id": _CRID,
        "from_account": "unified",
        "to_account": "spot",
        "asset": "USDT",
        "amount": "10.5",
        "confirm": True,
    }
    base.update(over)
    return base


# --------------------------------------------------------------- 成功与方向映射

def test_forward_transfer_maps_to_pm_main_and_succeeds(tmp_path):
    client = _StubTransferClient([_resp(200, {"tranId": 42})])
    with _server(tmp_path, client=client) as (host, port, _):
        status, doc = _post(host, port, _body())
    assert status == 200
    assert set(doc) == _RESULT_KEYS
    assert doc["status"] == "succeeded"
    assert doc["tran_id"] == "42"
    assert doc["error_code"] is None and doc["error_message"] is None
    # 统一账户 -> 现货账户
    assert client.calls == [{"type": TRANSFER_TYPE_PM_MAIN, "asset": "USDT", "amount": "10.5"}]


def test_reverse_transfer_maps_to_main_pm(tmp_path):
    client = _StubTransferClient()
    with _server(tmp_path, client=client) as (host, port, _):
        status, doc = _post(host, port, _body(from_account="spot", to_account="unified"))
    assert status == 200 and doc["status"] == "succeeded"
    assert client.calls[0]["type"] == TRANSFER_TYPE_MAIN_PM


def test_transfer_type_is_never_taken_from_request_body(tmp_path):
    """请求体里塞 transfer type 不生效：映射只认 from/to（杜绝外部注入）。"""
    client = _StubTransferClient()
    with _server(tmp_path, client=client) as (host, port, _):
        status, _doc = _post(host, port, _body(type="MAIN_UMFUTURE"))
    assert status == 200
    assert client.calls[0]["type"] == TRANSFER_TYPE_PM_MAIN


# ------------------------------------------------------------------------ 幂等

def test_replay_of_same_client_request_id_does_not_send_twice(tmp_path):
    """核心防线：第二次请求零外发，并返回首次结果。"""
    client = _StubTransferClient([_resp(200, {"tranId": 7})])
    with _server(tmp_path, client=client) as (host, port, _):
        first_status, first = _post(host, port, _body())
        second_status, second = _post(host, port, _body())
    assert first_status == 200 and second_status == 200
    assert len(client.calls) == 1, "重放必须零外发，否则会真的转两次钱"
    assert first["status"] == "succeeded" and second["status"] == "succeeded"
    assert second["tran_id"] == first["tran_id"] == "7"


def test_replay_ignores_changed_amount_and_returns_first_record(tmp_path):
    """同 id 改金额重放：仍不外发，返回首次记录（id 是幂等键，不是内容哈希）。"""
    client = _StubTransferClient([_resp(200, {"tranId": 7})])
    with _server(tmp_path, client=client) as (host, port, _):
        _post(host, port, _body())
        _status, second = _post(host, port, _body(amount="999"))
    assert len(client.calls) == 1
    assert second["amount"] == "10.5"


def test_distinct_client_request_ids_each_send(tmp_path):
    client = _StubTransferClient([_resp(200, {"tranId": 1}), _resp(200, {"tranId": 2})])
    with _server(tmp_path, client=client) as (host, port, _):
        _post(host, port, _body())
        _post(host, port, _body(client_request_id=_CRID2))
    assert len(client.calls) == 2


# ------------------------------------------------------- 超时 / 失败 / 未知结果

def test_transport_timeout_records_unknown_and_does_not_retry(tmp_path):
    client = _StubTransferClient([_resp(None, None, transport_error="timeout")])
    with _server(tmp_path, client=client) as (host, port, _):
        status, doc = _post(host, port, _body())
    assert status == 200
    assert doc["status"] == "unknown", "超时不等于失败：钱可能已经转了"
    assert doc["tran_id"] is None
    assert "timeout" in (doc["error_message"] or "")
    assert len(client.calls) == 1, "one-shot：不得重试"


def test_server_error_records_unknown_not_failed(tmp_path):
    client = _StubTransferClient([_resp(503, {"code": -1001, "msg": "内部错误"})])
    with _server(tmp_path, client=client) as (host, port, _):
        _status, doc = _post(host, port, _body())
    assert doc["status"] == "unknown"
    assert len(client.calls) == 1


def test_client_exception_records_unknown(tmp_path):
    client = _StubTransferClient(raises=OSError("boom"))
    with _server(tmp_path, client=client) as (host, port, store):
        _status, doc = _post(host, port, _body())
    assert doc["status"] == "unknown"
    # 绝不能停在 pending：那样前端永远不知道结果。
    assert store.get(_CRID)["status"] == "unknown"


def test_http_200_without_tran_id_is_unknown(tmp_path):
    client = _StubTransferClient([_resp(200, {})])
    with _server(tmp_path, client=client) as (host, port, _):
        _status, doc = _post(host, port, _body())
    assert doc["status"] == "unknown", "200 但无 tranId 不得擅自当成功"


def test_business_rejection_records_failed_with_raw_code(tmp_path):
    client = _StubTransferClient([_resp(400, {"code": -4015, "msg": "余额不足"})])
    with _server(tmp_path, client=client) as (host, port, _):
        _status, doc = _post(host, port, _body())
    assert doc["status"] == "failed"
    assert doc["error_code"] == "-4015"
    assert doc["error_message"] == "余额不足"
    assert doc["tran_id"] is None


# ------------------------------------------------------------------ 请求体校验

@pytest.mark.parametrize("over,expected_error", [
    ({"from_account": "spot", "to_account": "spot"}, "invalid_request"),
    ({"from_account": "unified", "to_account": "unified"}, "invalid_request"),
    ({"from_account": "margin"}, "invalid_request"),
    ({"client_request_id": "not-a-uuid"}, "invalid_request"),
    ({"amount": "-1"}, "invalid_request"),
    ({"amount": "1e3"}, "invalid_request"),
    ({"amount": " 10"}, "invalid_request"),
    ({"amount": "10 "}, "invalid_request"),
    ({"amount": "abc"}, "invalid_request"),
    ({"amount": "0"}, "invalid_request"),
    ({"amount": "0.00"}, "invalid_request"),
    ({"amount": 10.5}, "invalid_request"),
    ({"asset": ""}, "invalid_request"),
    ({"asset": "DOGE"}, "unknown_asset"),
    ({"confirm": False}, "confirm_required"),
    ({"confirm": "true"}, "confirm_required"),
])
def test_invalid_request_is_rejected_without_sending(tmp_path, over, expected_error):
    client = _StubTransferClient()
    with _server(tmp_path, client=client) as (host, port, _):
        status, doc = _post(host, port, _body(**over))
    assert status == 400, f"{over} 应被拒绝"
    assert doc["error"] == expected_error
    assert client.calls == [], "校验失败不得外发"


@pytest.mark.parametrize("missing", [
    "client_request_id", "from_account", "to_account", "asset", "amount", "confirm",
])
def test_missing_required_field_is_rejected(tmp_path, missing):
    client = _StubTransferClient()
    body = _body()
    del body[missing]
    with _server(tmp_path, client=client) as (host, port, _):
        status, doc = _post(host, port, body)
    assert status == 400 and doc["error"] == "invalid_request"
    assert missing in doc["detail"]
    assert client.calls == []


def test_asset_whitelist_follows_the_source_account(tmp_path):
    """XVG 只在现货账户里：从统一账户转出应被拒，从现货账户转出应放行。"""
    client = _StubTransferClient()
    with _server(tmp_path, client=client) as (host, port, _):
        status_unified, _ = _post(host, port, _body(asset="XVG"))
        status_spot, doc_spot = _post(
            host, port,
            _body(asset="XVG", from_account="spot", to_account="unified",
                  client_request_id=_CRID2),
        )
    assert status_unified == 400
    assert status_spot == 200 and doc_spot["status"] == "succeeded"


# ------------------------------------------------------------ 通道未配置 / 未就绪

def test_missing_client_returns_503(tmp_path):
    with _server(tmp_path, client=None) as (host, port, _):
        status, doc = _post(host, port, _body())
    assert status == 503 and doc["error"] == "asset_transfer_unavailable"


def test_missing_store_returns_503(tmp_path):
    with _server(tmp_path, client=_StubTransferClient(), store=False) as (host, port, _):
        status, doc = _post(host, port, _body())
    assert status == 503 and doc["error"] == "asset_transfer_unavailable"


def test_snapshot_not_ready_returns_503_without_sending(tmp_path):
    client = _StubTransferClient()
    with _server(tmp_path, client=client, snapshot_ready=False) as (host, port, _):
        status, doc = _post(host, port, _body())
    assert status == 503 and doc["error"] == "snapshot_not_ready"
    assert client.calls == [], "无法校验币种时不得外发"


# --------------------------------------------------------------- 存储层红线

def test_amount_column_is_text_and_id_is_unique(tmp_path):
    """金额列必须是 TEXT（不得走浮点），幂等键必须有唯一约束。"""
    path = str(tmp_path / "asset-transfer.sqlite3")
    AssetTransferStore(path)
    conn = sqlite3.connect(path)
    cols = {r[1]: r[2] for r in conn.execute("PRAGMA table_info(asset_transfer)")}
    assert cols["amount"] == "TEXT"
    assert cols["tran_id"] == "TEXT"
    # client_request_id 是主键 -> 唯一
    pk = [r[1] for r in conn.execute("PRAGMA table_info(asset_transfer)") if r[5]]
    assert pk == ["client_request_id"]
    conn.close()


def test_store_begin_is_idempotent_at_the_db_level(tmp_path):
    store = AssetTransferStore(str(tmp_path / "asset-transfer.sqlite3"))
    kwargs = dict(
        client_request_id=_CRID, from_account="unified", to_account="spot",
        asset="USDT", amount="1.25",
    )
    first, is_new_first = store.begin(now_us=1, **kwargs)
    second, is_new_second = store.begin(now_us=2, **kwargs)
    assert is_new_first is True and is_new_second is False
    assert first["status"] == "pending" and second["status"] == "pending"
    # 金额原样存取，不做任何规格化。
    assert second["amount"] == "1.25"


def test_store_resolve_writes_terminal_state(tmp_path):
    store = AssetTransferStore(str(tmp_path / "asset-transfer.sqlite3"))
    store.begin(
        client_request_id=_CRID, from_account="spot", to_account="unified",
        asset="USDT", amount="3", now_us=1,
    )
    doc = store.resolve(_CRID, status="succeeded", tran_id="900", now_us=2)
    assert doc["status"] == "succeeded" and doc["tran_id"] == "900"
    assert store.get(_CRID)["status"] == "succeeded"
