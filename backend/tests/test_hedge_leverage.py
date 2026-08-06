"""开单前自动设置合约杠杆（THE -2027 方案 B，Human 2026-08 拍板）。

验收面：client 白名单 + set_leverage 签名；executor 失败抛错带详情；service 每任务
一次（仅 live 开单任务首 attempt）、fail-closed 暂停、dry-run/close 跳过。无实盘写。
"""
from __future__ import annotations

import json

import pytest

from backend.hedge_open_tasks import domain as D
from backend.tests.fakes import RecordTransportFake
from backend.hedge_open_tasks.service import HedgeOpenTaskService
from backend.services.hedge_open_live_client import (
    ALLOWLIST,
    HedgeHttpResponse,
    HedgeOpenLiveClient,
)
from backend.services.live_hedge_executor import (
    LEG_ACCEPTED,
    LegDispatch,
    LiveAttemptDispatch,
    LiveHedgeExecutor,
)


# ---------------------------------------------------------------------------
# client 层：白名单 + set_leverage 签名 POST /fapi/v1/leverage（fapi 域名）
# ---------------------------------------------------------------------------
def test_allowlist_registers_leverage_post_hardbound_to_fapi():
    assert ALLOWLIST[("POST", "/papi/v1/um/leverage")] == "https://papi.binance.com"


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
    def __init__(self, responses=None):
        self.requests = []
        self._responses = list(responses or [])
        self.call_count = 0

    def __call__(self, req, timeout=None):
        self.call_count += 1
        self.requests.append(req)
        if self._responses:
            return self._responses.pop(0)
        return _FakeResp(200, b"{}")


def _client(opener):
    return HedgeOpenLiveClient(
        api_key="key", api_secret="secret", user_agent="ua", urlopen=opener,
    )


def test_client_set_leverage_posts_signed_params_to_fapi():
    openr = _CapturingOpen([_FakeResp(200, b'{"symbol":"BTCUSDT","leverage":3}')])
    resp = _client(openr).set_leverage("BTCUSDT", 3, timestamp_ms=1)
    assert resp.http_status == 200
    assert resp.body == {"symbol": "BTCUSDT", "leverage": 3}
    req = openr.requests[0]
    assert req.method == "POST"
    assert req.full_url == "https://papi.binance.com/papi/v1/um/leverage"
    body = req.data.decode("utf-8")
    # 参数冻结：symbol + leverage + timestamp + recvWindow（签名 body 原样发送）
    assert "symbol=BTCUSDT" in body and "leverage=3" in body
    assert "timestamp=1" in body and "recvWindow=60000" in body


def test_client_set_leverage_is_one_shot_no_retry():
    # 写语义与订单一致：超时/5xx 不重试（单次传输尝试），失败判定在 executor 层。
    openr = _CapturingOpen([_FakeResp(503, b'{"msg":"Unknown error"}')])
    resp = _client(openr).set_leverage("BTCUSDT", 3, timestamp_ms=1)
    assert resp.http_status == 503
    assert openr.call_count == 1


# ---------------------------------------------------------------------------
# executor 层：set_leverage 成功无返回值；失败抛错带交易所详情
# ---------------------------------------------------------------------------
class _LeverageFakeClient:
    credentials_present = True

    def __init__(self, resp: HedgeHttpResponse):
        self._resp = resp

    def set_leverage(self, symbol, leverage, *, timestamp_ms, recv_window_ms=None):
        return self._resp


def _lev_ok_resp():
    return HedgeHttpResponse(
        http_status=200, body={"symbol": "BTCUSDT", "leverage": 3},
        raw_body='{"symbol":"BTCUSDT","leverage":3}',
        transport_error=None, retry_after_seconds=None,
    )


def _lev_err_resp(status=400, body=None):
    return HedgeHttpResponse(
        http_status=status, body=body if body is not None else {"code": -2027},
        raw_body=str(body if body is not None else {"code": -2027}),
        transport_error=None, retry_after_seconds=None,
    )


def test_executor_set_leverage_ok_returns_none():
    exe = LiveHedgeExecutor(
        _LeverageFakeClient(_lev_ok_resp()), now_ms=lambda: 1,
    )
    assert exe.set_leverage("BTCUSDT", 3) is None


def test_executor_set_leverage_http_error_raises_with_body_detail():
    exe = LiveHedgeExecutor(
        _LeverageFakeClient(_lev_err_resp(
            400, {"code": -2027, "msg": "Exceeded the maximum allowable position at current leverage"},
        )),
        now_ms=lambda: 1,
    )
    with pytest.raises(RuntimeError) as exc:
        exe.set_leverage("BTCUSDT", 3)
    assert "-2027" in str(exc.value) and "http=400" in str(exc.value)


def test_executor_set_leverage_missing_field_raises():
    exe = LiveHedgeExecutor(
        _LeverageFakeClient(
            HedgeHttpResponse(
                http_status=200, body={"symbol": "BTCUSDT"},
                raw_body='{"symbol":"BTCUSDT"}',
                transport_error=None, retry_after_seconds=None,
            )
        ),
        now_ms=lambda: 1,
    )
    with pytest.raises(RuntimeError) as exc:
        exe.set_leverage("BTCUSDT", 3)
    assert "missing leverage" in str(exc.value)


# ---------------------------------------------------------------------------
# service 层：时机 / 每任务一次 / fail-closed / dry-run / close 回归
# ---------------------------------------------------------------------------
class _SpyPreflightProvider:
    """可编程 snapshot provider（只记录调用，不做真实读取）。"""

    def __init__(self, snapshot):
        self._snapshot = snapshot
        self.calls = []

    def get_snapshot(self, coin, direction, task_type="open"):
        self.calls.append((coin, direction, task_type))
        return self._snapshot


def _spot_filters_fx():
    return {
        "lot_size": {"min_qty": "0.00001", "max_qty": "9000", "step_size": "0.00001"},
        "market_lot_size": {"min_qty": "0", "max_qty": "9000", "step_size": "0"},
        "notional": {"min_notional": "5", "apply_min_to_market": True},
    }


def _perp_filters_fx():
    return {
        "lot_size": {"min_qty": "0.001", "max_qty": "1000", "step_size": "0.001"},
        "market_lot_size": {"min_qty": "0.001", "max_qty": "120", "step_size": "0.001"},
        "notional": {"notional": "50"},
    }


def _open_snapshot():
    from backend.hedge_open_tasks.domain import PreflightSnapshot as _PS
    return _PS(
        spot_filters=_spot_filters_fx(), perp_filters=_perp_filters_fx(),
        balances={"USDT": D.Decimal("100000")},
        position_mode=D.POS_MODE_BOTH, est_price=D.Decimal("1"),
        symbol_tradable=True,
    )


class _LeverageLiveExecutor:
    """live fake：有 dispatch（满足 _live_dispatch_capable）+ set_leverage spy。"""

    def __init__(self, leverage_error: Exception | None = None):
        self.leverage_calls: list[tuple] = []
        self._leverage_error = leverage_error
        self._seq = 0

    def set_leverage(self, coin: str, leverage: int) -> None:
        self.leverage_calls.append((coin, leverage))
        if self._leverage_error is not None:
            raise self._leverage_error

    def dispatch(self, ctx):
        self._seq += 1
        spot = LegDispatch(
            leg="spot", dispatch_state=LEG_ACCEPTED, order_id="1",
            exchange_status=D.LEG_FILLED, executed_qty=str(ctx.q_common),
            cumulative_quote=None, avg_price=None, raw_response={"orderId": 1},
        )
        perp = LegDispatch(
            leg="perp", dispatch_state=LEG_ACCEPTED, order_id="2",
            exchange_status=D.LEG_FILLED, executed_qty=str(ctx.q_common),
            cumulative_quote=None, avg_price=None, raw_response={"orderId": 2},
        )
        return LiveAttemptDispatch(
            attempt_id=ctx.attempt_id, spot=spot, perp=perp,
            record_payload={"seq": self._seq}, rate_limited=False,
            retry_after_seconds=None,
        )


def _make_svc(tmp_path, executor, snapshot=None, mode="live"):
    provider = _SpyPreflightProvider(snapshot if snapshot is not None else _open_snapshot())
    svc = HedgeOpenTaskService(
        str(tmp_path / "ho.sqlite3"), mode=mode,
        executor=executor, preflight_provider=provider,
    )
    return svc, provider


def _open_start_gate(svc):
    """测试环境 start gate 默认关闭；live 发单路径需显式开启（CAS + confirm）。"""
    status, _ = svc.put_start_gate({
        "enabled": True, "confirm": True,
        "version": svc.get_settings()[1]["version"],
    })
    assert status == 200
    return svc


def _make_open_task(svc, coin="BTCUSDT", target_n=1):
    task = svc._store.create_task(
        "fx-lev", coin, D.DIR_FORWARD, D.MODE_IMMEDIATE, "100", target_n, "100",
        D.POS_MODE_BOTH, None, 1_000, task_type=D.TASK_TYPE_OPEN,
    )
    return svc._store.get_task(task["id"])


def _attempt_count(svc, task_id):
    return svc._store._conn.execute(
        "SELECT COUNT(*) FROM hedge_open_attempt WHERE task_id = ?", (task_id,)
    ).fetchone()[0]


def _events(svc, task_id, kind):
    return svc._store._conn.execute(
        "SELECT payload FROM hedge_open_log WHERE task_id = ? AND kind = ?",
        (task_id, kind),
    ).fetchall()


def test_live_open_sets_leverage_once_before_first_attempt(tmp_path):
    exe = _LeverageLiveExecutor()
    svc, _ = _make_svc(tmp_path, exe)
    _open_start_gate(svc)
    task = _make_open_task(svc, target_n=2)
    updated, signal = svc._dispatch_one_for_task(task, 2_000)
    # 首 attempt 前设置一次；成功后 attempt 正常创建、正常发单（signal None）
    assert exe.leverage_calls == [("BTCUSDT", D.OPEN_LEVERAGE)]
    assert signal is None
    assert updated["scheduled_attempt_count"] >= 1
    assert _attempt_count(svc, task["id"]) == 1


def test_live_open_sets_leverage_only_once_across_attempts(tmp_path):
    # 每任务一次：target_n>1 时首次设、后续 attempt 不再调（spy 计数 = 1）。
    exe = _LeverageLiveExecutor()
    svc, _ = _make_svc(tmp_path, exe)
    _open_start_gate(svc)
    task = _make_open_task(svc, target_n=2)
    svc._dispatch_one_for_task(task, 2_000)
    task2 = svc._store.get_task(task["id"])
    svc._dispatch_one_for_task(task2, 3_000)
    assert exe.leverage_calls == [("BTCUSDT", D.OPEN_LEVERAGE)]
    assert _attempt_count(svc, task["id"]) == 2


def test_live_open_leverage_failure_pauses_fail_closed(tmp_path):
    # fail-closed：set_leverage 抛错 → 任务暂停（中文原因 + 错误详情）、无 attempt、
    # 不发单、日志落库。
    err = RuntimeError("set_leverage http=400 body={'code': -2027, 'msg': 'Exceeded'}")
    exe = _LeverageLiveExecutor(leverage_error=err)
    svc, _ = _make_svc(tmp_path, exe)
    _open_start_gate(svc)
    task = _make_open_task(svc)
    updated, signal = svc._dispatch_one_for_task(task, 2_000)
    assert signal == D.SIGNAL_LEVERAGE_SET_FAILED
    assert updated["status"] == D.STATUS_PAUSED
    assert updated["pause_reason"] == D.PAUSE_REASON_LEVERAGE_SET_FAILED
    assert "设置合约杠杆失败" in (updated["pause_reason_zh"] or "")
    assert "-2027" in (updated["pause_reason_zh"] or "")  # 错误详情随中文原因落库
    assert _attempt_count(svc, task["id"]) == 0  # 未创建 attempt、未发单
    events = _events(svc, task["id"], "leverage_set_failed")
    assert len(events) == 1
    payload = json.loads(events[0][0])
    assert payload["reason"] == D.PAUSE_REASON_LEVERAGE_SET_FAILED
    assert "-2027" in payload["reason_zh"]


def test_dry_run_skips_leverage(tmp_path):
    # 非 live：默认 executor（DisabledHedgeExecutor）无 set_leverage → 跳过模拟成功。
    svc = HedgeOpenTaskService(str(tmp_path / "ho.sqlite3"), mode="disabled")
    assert not hasattr(svc._executor, "set_leverage")
    task = _make_open_task(svc)
    assert svc._set_leverage_before_open(task, 2_000) is None
    # 非 live 路径整体不发单、不设杠杆
    updated, signal = svc._dispatch_one_for_task(task, 2_000)
    assert updated["status"] in (D.STATUS_DONE, D.STATUS_RUNNING)


def test_close_task_never_sets_leverage(tmp_path):
    # 平仓任务不设杠杆（回归断言）。
    exe = _LeverageLiveExecutor()
    svc, _ = _make_svc(tmp_path, exe)
    _open_start_gate(svc)
    task = svc._store.create_task(
        "fx-close", "BTCUSDT", D.DIR_REVERSE, D.MODE_IMMEDIATE, "100", 1, "100",
        D.POS_MODE_BOTH, None, 1_000, task_type=D.TASK_TYPE_CLOSE,
    )
    task = svc._store.get_task(task["id"])
    updated, signal = svc._dispatch_one_for_task(task, 2_000)
    assert exe.leverage_calls == []  # close 不设杠杆
    assert signal is None  # close 发单路径正常
    assert _attempt_count(svc, task["id"]) == 1


def test_close_task_with_leverage_capable_executor_skips(tmp_path):
    # 即使 executor 有 set_leverage，close 任务也绝不调用（task_type 门控）。
    exe = _LeverageLiveExecutor()
    svc, _ = _make_svc(tmp_path, exe)
    _open_start_gate(svc)
    task = svc._store.create_task(
        "fx-close", "BTCUSDT", D.DIR_FORWARD, D.MODE_IMMEDIATE, "100", 1, "100",
        D.POS_MODE_BOTH, None, 1_000, task_type=D.TASK_TYPE_CLOSE,
    )
    task = svc._store.get_task(task["id"])
    svc._dispatch_one_for_task(task, 2_000)
    assert exe.leverage_calls == []
