"""统一账户全仓杠杆还款 `POST/GET /api/margin-repay` 的契约、幂等与四态测试
（阶段 2026-08-09-pm-margin-repay-v1，T1，全离线）。

进程内 ``ThreadingHTTPServer`` + 桩客户端 + 临时 SQLite：无网络、无凭证、无真实币安调用。
重点证明在**动钱路径**上最容易出事的性质：

1. **金额语义**——页面 ``0`` 外发时省略 amount（绝不发字面量 0）；正数按原字符串透传；
   指定偿还资产固定 USDT，客户端无法覆盖。
2. **幂等**——币安 ``/papi/v1/margin/repay-debt`` 没有客户端幂等键、也无法按请求号查结果，
   同一 ``client_request_id`` 的第二次请求必须**零外发**。
3. **超时不重试 / 严格四态**——超时/5xx/408/418/429 记 ``unknown``（钱可能已还），
   明确 4xx 记 ``failed``，200 必须严格成功才记 ``succeeded``。
"""
from __future__ import annotations

import http.client
import json
import sqlite3
import threading
from contextlib import contextmanager

import pytest

from backend.app.server import _Handler, build_server
from backend.config import Config
from backend.margin_repay.store import MarginRepayStore
from backend.services.hedge_open_live_client import HedgeHttpResponse

_RESULT_KEYS = {
    "client_request_id", "asset", "amount", "repay_asset", "status",
    "repaid_amount", "update_time", "error_code", "error_message",
}

_CRID = "11111111-2222-3333-4444-555555555555"
_CRID2 = "99999999-8888-7777-6666-555555555555"


class _StubSnapshotService:
    """提供借款资产白名单校验需要的快照；``ready=False`` 模拟快照未就绪。

    统一账户里 BNB 借了（cross_margin_borrowed>0），ETH/BTC/DOGE 未借或数值零。
    """

    def __init__(self, *, ready=True):
        self._ready = ready

    def get_snapshot(self):
        if not self._ready:
            raise RuntimeError("snapshot not ready")
        return {
            "rows": [],
            "private_account": {
                "balances_unified": [
                    {"asset": "BNB", "cross_margin_borrowed": "1.5"},
                    {"asset": "ETH", "cross_margin_borrowed": "0"},
                    {"asset": "BTC", "cross_margin_borrowed": "0.0000"},
                    {"asset": "DOGE", "cross_margin_borrowed": None},
                ],
            },
        }


class _StubRepayClient:
    """记录每次外发，按预设脚本回应。``calls`` 的长度即真实外发次数。amount=None 表示全部。"""

    def __init__(self, responses=None, raises=None):
        self.calls = []
        self._responses = list(responses or [])
        self._raises = raises

    def repay_margin_debt(self, asset, amount, *, timestamp_ms, recv_window_ms=None):
        self.calls.append({"asset": asset, "amount": amount})
        if self._raises is not None:
            raise self._raises
        if self._responses:
            return self._responses.pop(0)
        return _resp(200, {
            "success": True, "asset": asset, "amount": "1.0",
            "updateTime": 1700000000000,
        })


class _BlockingStubRepayClient(_StubRepayClient):
    """外发途中阻塞，把并发请求钉在「首笔尚未落终态」的窗口里。"""

    def __init__(self, responses=None):
        super().__init__(responses)
        self.entered = threading.Event()
        self.release = threading.Event()

    def repay_margin_debt(self, asset, amount, *, timestamp_ms, recv_window_ms=None):
        self.entered.set()
        self.release.wait(timeout=5)
        return super().repay_margin_debt(
            asset, amount, timestamp_ms=timestamp_ms, recv_window_ms=recv_window_ms,
        )


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
    repay_store = (
        MarginRepayStore(str(tmp_path / "margin-repay.sqlite3")) if store else None
    )
    _Handler.margin_repay_store = repay_store
    _Handler.margin_repay_client = client
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    host, port = srv.server_address[:2]
    try:
        yield host, port, repay_store
    finally:
        srv.shutdown()
        srv.server_close()
        # 类属性会跨测试泄漏，必须复位。
        _Handler.margin_repay_store = None
        _Handler.margin_repay_client = None


def _post(host, port, body):
    conn = http.client.HTTPConnection(host, port, timeout=5)
    data = json.dumps(body).encode("utf-8")
    conn.request("POST", "/api/margin-repay", body=data, headers={
        "Content-Type": "application/json", "Content-Length": str(len(data)),
    })
    resp = conn.getresponse()
    out = resp.status, json.loads(resp.read().decode("utf-8"))
    conn.close()
    return out


def _get(host, port, crid):
    conn = http.client.HTTPConnection(host, port, timeout=5)
    conn.request("GET", f"/api/margin-repay?client_request_id={crid}")
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8")
    out = resp.status, (json.loads(raw) if raw else None)
    conn.close()
    return out


def _body(**over):
    base = {
        "client_request_id": _CRID,
        "asset": "BNB",
        "amount": "0",
        "confirm": True,
    }
    base.update(over)
    return base


# ------------------------------------------------------- 金额语义：0 省略 / 正数透传

def test_repay_all_with_zero_omits_amount_and_succeeds(tmp_path):
    client = _StubRepayClient()
    with _server(tmp_path, client=client) as (host, port, _):
        status, doc = _post(host, port, _body())
    assert status == 200
    assert set(doc) == _RESULT_KEYS
    assert doc["status"] == "succeeded"
    assert doc["repay_asset"] == "USDT"
    assert doc["repaid_amount"] == "1.0"
    assert doc["update_time"] == "1700000000000"
    # 0 -> 外发省略 amount（绝不发字面量 0）
    assert client.calls == [{"asset": "BNB", "amount": None}]
    # 请求金额原样留痕（0 可审计）
    assert doc["amount"] == "0"


def test_positive_amount_passed_through_verbatim(tmp_path):
    client = _StubRepayClient()
    with _server(tmp_path, client=client) as (host, port, _):
        status, doc = _post(host, port, _body(amount="1.25"))
    assert status == 200 and doc["status"] == "succeeded"
    assert client.calls[0]["amount"] == "1.25"
    assert doc["amount"] == "1.25"


def test_positive_amount_with_leading_zero_decimal_passes(tmp_path):
    # 0.050 是正数（>0），按原样透传；不是数值零。
    client = _StubRepayClient()
    with _server(tmp_path, client=client) as (host, port, _):
        status, _doc = _post(host, port, _body(amount="0.050"))
    assert status == 200
    assert client.calls[0]["amount"] == "0.050"


# ------------------------------------------------------------------------ 幂等

def test_replay_of_same_client_request_id_does_not_send_twice(tmp_path):
    """核心防线：第二次请求零外发，并返回首次结果。"""
    client = _StubRepayClient([_resp(200, {"success": True, "asset": "BNB", "amount": "2", "updateTime": 7})])
    with _server(tmp_path, client=client) as (host, port, _):
        first_status, first = _post(host, port, _body())
        second_status, second = _post(host, port, _body())
    assert first_status == 200 and second_status == 200
    assert len(client.calls) == 1, "重放必须零外发，否则会真的还两次"
    assert first["status"] == "succeeded" and second["status"] == "succeeded"
    assert second["repaid_amount"] == first["repaid_amount"] == "2"


def test_replay_ignores_changed_amount_and_returns_first_record(tmp_path):
    """同 id 改金额重放：仍不外发，返回首次记录（id 是幂等键，不是内容哈希）。"""
    client = _StubRepayClient()
    with _server(tmp_path, client=client) as (host, port, _):
        _post(host, port, _body())
        _status, second = _post(host, port, _body(amount="999"))
    assert len(client.calls) == 1
    assert second["amount"] == "0"


def test_concurrent_same_id_sends_only_once(tmp_path):
    """同一编号**同时**打两次，也只能有一次真实外发。

    顺序重放靠 handler 分支挡住；真正的并发只能靠数据库唯一约束。桩客户端在外发途中阻塞，
    保证第二个请求落在「第一次尚未 resolve」的窗口内——此时第一笔还没有终态，天真的实现
    会以为没记录过而再发一次。
    """
    client = _BlockingStubRepayClient()
    with _server(tmp_path, client=client) as (host, port, _):
        first_out = []

        def fire_first():
            first_out.append(_post(host, port, _body()))

        t = threading.Thread(target=fire_first, daemon=True)
        t.start()
        assert client.entered.wait(timeout=5), "第一笔请求未进入外发"
        _second_status, second = _post(host, port, _body())
        client.release.set()
        t.join(timeout=5)

    assert len(client.calls) == 1, "并发同编号必须只外发一次，否则会真的还两次"
    assert first_out[0][1]["status"] == "succeeded"
    assert second["status"] == "pending"  # 第二笔看到的是尚未完成的首笔记录
    assert second["client_request_id"] == _CRID


def test_distinct_client_request_ids_each_send(tmp_path):
    client = _StubRepayClient()
    with _server(tmp_path, client=client) as (host, port, _):
        _post(host, port, _body())
        _post(host, port, _body(client_request_id=_CRID2))
    assert len(client.calls) == 2


# ------------------------------------------------------- 超时 / 失败 / 未知结果

def test_transport_timeout_records_unknown_and_does_not_retry(tmp_path):
    client = _StubRepayClient([_resp(None, None, transport_error="timeout")])
    with _server(tmp_path, client=client) as (host, port, _):
        status, doc = _post(host, port, _body())
    assert status == 200
    assert doc["status"] == "unknown", "超时不等于失败：钱可能已经还了"
    assert doc["repaid_amount"] is None
    assert "timeout" in (doc["error_message"] or "")
    assert len(client.calls) == 1, "one-shot：不得重试"


def test_server_error_records_unknown_not_failed(tmp_path):
    client = _StubRepayClient([_resp(503, {"code": -1001, "msg": "内部错误"})])
    with _server(tmp_path, client=client) as (host, port, _):
        _status, doc = _post(host, port, _body())
    assert doc["status"] == "unknown"
    assert len(client.calls) == 1


def test_client_exception_records_unknown(tmp_path):
    client = _StubRepayClient(raises=OSError("boom"))
    with _server(tmp_path, client=client) as (host, port, store):
        _status, doc = _post(host, port, _body())
    assert doc["status"] == "unknown"
    assert store.get(_CRID)["status"] == "unknown"  # 绝不能停在 pending


def test_http_200_without_success_is_unknown(tmp_path):
    client = _StubRepayClient([_resp(200, {})])
    with _server(tmp_path, client=client) as (host, port, _):
        _status, doc = _post(host, port, _body())
    assert doc["status"] == "unknown", "200 但无 success 不得擅自当成功"


def test_http_200_success_false_is_unknown(tmp_path):
    client = _StubRepayClient([_resp(200, {"success": False, "asset": "BNB"})])
    with _server(tmp_path, client=client) as (host, port, _):
        _status, doc = _post(host, port, _body())
    assert doc["status"] == "unknown"


def test_http_200_success_true_but_asset_mismatch_is_unknown(tmp_path):
    # success=True 但响应资产与请求不一致：结果不明，不擅自当成功。
    client = _StubRepayClient([_resp(200, {"success": True, "asset": "XXX", "amount": "1"})])
    with _server(tmp_path, client=client) as (host, port, _):
        _status, doc = _post(host, port, _body())
    assert doc["status"] == "unknown"


def test_http_200_strict_success_records_repaid_amount_and_update_time(tmp_path):
    client = _StubRepayClient([_resp(200, {
        "success": True, "asset": "BNB", "amount": "1.5", "updateTime": 1700000000000,
        "specifyRepayAssets": ["BNB", "USDT"],
    })])
    with _server(tmp_path, client=client) as (host, port, _):
        _status, doc = _post(host, port, _body())
    assert doc["status"] == "succeeded"
    assert doc["repaid_amount"] == "1.5"
    assert doc["update_time"] == "1700000000000"
    assert doc["repay_asset"] == "USDT"  # 固定，不随响应 specifyRepayAssets 变


def test_business_rejection_records_failed_with_raw_code(tmp_path):
    client = _StubRepayClient([_resp(400, {"code": -3041, "msg": "Amount must be positive"})])
    with _server(tmp_path, client=client) as (host, port, _):
        _status, doc = _post(host, port, _body())
    assert doc["status"] == "failed"
    assert doc["error_code"] == "-3041"
    assert doc["error_message"] == "请求被币安拒绝（HTTP 400）：Amount must be positive"
    assert doc["repaid_amount"] is None


@pytest.mark.parametrize("http_status,expected_status", [
    # 408/418/429 与 5xx 归 unknown：钱可能已还，failed 会诱导重试而还两次
    (408, "unknown"),
    (418, "unknown"),
    (429, "unknown"),
    (500, "unknown"),
    (503, "unknown"),
    # 其余 4xx 是明确的业务拒绝
    (400, "failed"),
    (401, "failed"),
    (403, "failed"),
])
def test_http_status_classification(tmp_path, http_status, expected_status):
    client = _StubRepayClient([_resp(http_status, {"code": -1, "msg": "x"})])
    with _server(tmp_path, client=client) as (host, port, _):
        _s, doc = _post(host, port, _body())
    assert doc["status"] == expected_status
    assert len(client.calls) == 1, "任何状态码都不得重试"


# ------------------------------------------------------------------ 请求体校验

@pytest.mark.parametrize("over,expected_error", [
    ({"amount": "0.0"}, "invalid_request"),
    ({"amount": "0.00"}, "invalid_request"),
    ({"amount": "00"}, "invalid_request"),
    ({"amount": "-1"}, "invalid_request"),
    ({"amount": "1e3"}, "invalid_request"),
    ({"amount": " 10"}, "invalid_request"),
    ({"amount": "10 "}, "invalid_request"),
    ({"amount": "abc"}, "invalid_request"),
    ({"amount": 10.5}, "invalid_request"),
    ({"amount": 0}, "invalid_request"),
    ({"asset": ""}, "invalid_request"),
    ({"asset": "ETH"}, "unknown_asset"),     # ETH 在快照里但未借款
    ({"asset": "XYZ"}, "unknown_asset"),     # 未知资产
    ({"client_request_id": "not-a-uuid"}, "invalid_request"),
    ({"confirm": False}, "confirm_required"),
    ({"confirm": "true"}, "confirm_required"),
    ({"specifyRepayAssets": "BNB"}, "invalid_request"),  # 偿还资产字段被拒
    ({"specifyRepayAsset": "BNB"}, "invalid_request"),
    ({"repayAsset": "BNB"}, "invalid_request"),
    ({"extra": 1}, "invalid_request"),       # 任何未知字段被拒
])
def test_invalid_request_is_rejected_without_sending(tmp_path, over, expected_error):
    client = _StubRepayClient()
    with _server(tmp_path, client=client) as (host, port, _):
        status, doc = _post(host, port, _body(**over))
    assert status == 400, f"{over} 应被拒绝"
    assert doc["error"] == expected_error
    assert client.calls == [], "校验失败不得外发"


@pytest.mark.parametrize("missing", ["client_request_id", "asset", "amount", "confirm"])
def test_missing_required_field_is_rejected(tmp_path, missing):
    client = _StubRepayClient()
    body = _body()
    del body[missing]
    with _server(tmp_path, client=client) as (host, port, _):
        status, doc = _post(host, port, body)
    assert status == 400 and doc["error"] == "invalid_request"
    assert missing in doc["detail"]
    assert client.calls == []


# ------------------------------------------------------------ 借款资产白名单

def test_snapshot_not_ready_returns_503_without_sending(tmp_path):
    client = _StubRepayClient()
    with _server(tmp_path, client=client, snapshot_ready=False) as (host, port, _):
        status, doc = _post(host, port, _body())
    assert status == 503 and doc["error"] == "snapshot_not_ready"
    assert client.calls == [], "无法校验借款资产时不得外发"


# ------------------------------------------------------------- 纯本地恢复 GET

def test_get_returns_existing_record(tmp_path):
    client = _StubRepayClient()
    with _server(tmp_path, client=client) as (host, port, _):
        _post(host, port, _body())
        status, doc = _get(host, port, _CRID)
    assert status == 200
    assert doc["client_request_id"] == _CRID
    assert doc["status"] == "succeeded"


def test_get_missing_returns_404(tmp_path):
    with _server(tmp_path, client=_StubRepayClient()) as (host, port, _):
        status, doc = _get(host, port, _CRID2)
    assert status == 404 and doc["error"] == "not_found"


def test_get_invalid_uuid_returns_400(tmp_path):
    with _server(tmp_path, client=_StubRepayClient()) as (host, port, _):
        status, doc = _get(host, port, "not-a-uuid")
    assert status == 400 and doc["error"] == "invalid_request"


def _get_raw(host, port, query):
    conn = http.client.HTTPConnection(host, port, timeout=5)
    conn.request("GET", f"/api/margin-repay?{query}")
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8")
    out = resp.status, (json.loads(raw) if raw else None)
    conn.close()
    return out


def test_get_missing_param_returns_400(tmp_path):
    with _server(tmp_path, client=_StubRepayClient()) as (host, port, _):
        status, doc = _get_raw(host, port, "")
    assert status == 400 and doc["error"] == "invalid_request"


def test_get_extra_param_returns_400(tmp_path):
    with _server(tmp_path, client=_StubRepayClient()) as (host, port, _):
        status, doc = _get_raw(host, port, f"client_request_id={_CRID}&foo=1")
    assert status == 400 and doc["error"] == "invalid_request"


def test_get_is_zero_upstream_without_client_or_snapshot(tmp_path):
    """GET 不依赖 client 与快照：即便无 client 且快照未就绪，仍按本地记录返回 404。"""
    with _server(tmp_path, client=None, snapshot_ready=False) as (host, port, _):
        status, doc = _get(host, port, _CRID2)
    assert status == 404 and doc["error"] == "not_found"


# ------------------------------------------------------------ 通道未配置

def test_post_missing_client_returns_503(tmp_path):
    with _server(tmp_path, client=None) as (host, port, _):
        status, doc = _post(host, port, _body())
    assert status == 503 and doc["error"] == "margin_repay_unavailable"


def test_get_missing_store_returns_503(tmp_path):
    with _server(tmp_path, client=_StubRepayClient(), store=False) as (host, port, _):
        status, doc = _get(host, port, _CRID)
    assert status == 503 and doc["error"] == "margin_repay_unavailable"


# --------------------------------------------------------------- 存储层红线

def test_amount_columns_are_text_and_id_is_unique(tmp_path):
    """金额列必须是 TEXT（不得走浮点），幂等键必须有唯一约束。"""
    path = str(tmp_path / "margin-repay.sqlite3")
    MarginRepayStore(path)
    conn = sqlite3.connect(path)
    cols = {r[1]: r[2] for r in conn.execute("PRAGMA table_info(margin_repay)")}
    assert cols["amount"] == "TEXT"
    assert cols["repaid_amount"] == "TEXT"
    assert cols["update_time"] == "TEXT"
    pk = [r[1] for r in conn.execute("PRAGMA table_info(margin_repay)") if r[5]]
    assert pk == ["client_request_id"]
    conn.close()


def test_store_begin_is_idempotent_at_the_db_level(tmp_path):
    store = MarginRepayStore(str(tmp_path / "margin-repay.sqlite3"))
    kwargs = dict(client_request_id=_CRID, asset="BNB", amount="0", repay_asset="USDT")
    first, is_new_first = store.begin(now_us=1, **kwargs)
    second, is_new_second = store.begin(now_us=2, **kwargs)
    assert is_new_first is True and is_new_second is False
    assert first["status"] == "pending" and second["status"] == "pending"
    assert second["amount"] == "0"  # 原样存取
    assert second["repay_asset"] == "USDT"


def test_store_resolve_writes_terminal_state(tmp_path):
    store = MarginRepayStore(str(tmp_path / "margin-repay.sqlite3"))
    store.begin(client_request_id=_CRID, asset="BNB", amount="1.5", repay_asset="USDT", now_us=1)
    doc = store.resolve(
        _CRID, status="succeeded", repaid_amount="1.5", update_time="1700000000000", now_us=2,
    )
    assert doc["status"] == "succeeded"
    assert doc["repaid_amount"] == "1.5"
    assert doc["update_time"] == "1700000000000"
    assert store.get(_CRID)["status"] == "succeeded"
