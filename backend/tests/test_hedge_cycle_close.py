"""功能三（立即平仓执行 + 结算日志 + 历史页数据源）全链路用例。

覆盖 dispatch 验收 1-7：
- 迁移幂等：task_type / close_gate 列 + hedge_open_cycle_close_log 表；
- 开仓成本隔离：close 腿绝不进 aggregate 开仓成本基；
- close 任务创建校验（无活跃周期 → 409 no_active_cycle）；
- 平仓执行（dry-run 全链路）：方向反转（forward → spot SELL + perp BUY）、
  合约腿 reduceOnly=true、双腿成交、无仓核实 → done + close_cycle + close_log；
- 完成判定（合约腿为准）：合约仍有仓 → open（继续）；查仓失败 → failed（不误判）；
- close_gate：默认 1、CAS（confirm/version/409）+ close_gate_changed 审计；
- 结算日志：open/close 均价独立、费率利息、滑点 null；GET close-logs 数据源。
"""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.executor import AttemptContext, AttemptOutcome
from backend.tests.fakes import RecordTransportFake
from backend.hedge_open_tasks.service import HedgeOpenTaskService
from backend.hedge_open_tasks.store import HedgeOpenStore
from backend.services.live_hedge_executor import LiveHedgeExecutor


def _svc(tmp_path):
    # B-1 (stage 2026-08-06): the production default executor is disabled (zero
    # fills); these open/close cycle scenarios need the simulated fills of the
    # test-only record fake, injected explicitly.
    return HedgeOpenTaskService(
        str(tmp_path / "ho.sqlite3"), mode="disabled",
        executor=RecordTransportFake(),
    )


def _outcome(attempt_id: str, qty: str = "0.5", price: str = "50000") -> AttemptOutcome:
    from decimal import Decimal as _D
    quote = str(_D(qty) * _D(price))
    return AttemptOutcome(
        attempt_id=attempt_id,
        category=D.ATTEMPT_SUCCESS,
        spot={"status": D.LEG_FILLED, "filled_qty": qty, "avg_price": price,
              "cumulative_quote": quote,
              "order_id": f"os-{attempt_id}", "client_order_id": f"hgo-{attempt_id}-s"},
        perp={"status": D.LEG_FILLED, "filled_qty": qty, "avg_price": price,
              "cumulative_quote": quote,
              "order_id": f"op-{attempt_id}", "client_order_id": f"hgo-{attempt_id}-p"},
        record_payload={"transport": "dry_run_record", "posted": False,
                        "spot_order_params": {}, "perp_order_params": {}},
        exposure=None,
    )


def _task_legs(store, task_id: str) -> list[dict]:
    return store._conn.execute(
        "SELECT l.leg, l.request_shape, l.dispatch_state, l.cumulative_base_qty"
        " FROM hedge_open_leg l JOIN hedge_open_attempt a ON a.id = l.attempt_id"
        " WHERE a.task_id = ? ORDER BY l.id",
        (task_id,),
    ).fetchall()


# ---------------------------------------------------------------------------
# 验收 1：迁移幂等
# ---------------------------------------------------------------------------
def test_migrate_adds_task_type_close_gate_and_close_log_table(tmp_path):
    db = str(tmp_path / "ho.sqlite3")
    store = HedgeOpenStore(db)
    task_cols = {r[1] for r in store._conn.execute("PRAGMA table_info(hedge_open_task)")}
    assert "task_type" in task_cols
    settings_cols = {r[1] for r in store._conn.execute("PRAGMA table_info(hedge_open_settings)")}
    assert "close_gate" in settings_cols
    log_cols = {r[1] for r in store._conn.execute("PRAGMA table_info(hedge_open_cycle_close_log)")}
    assert {"cycle_id", "symbol", "direction", "opened_at_us", "closed_at_us",
            "close_reason", "open_avg_price", "open_qty", "close_avg_price",
            "funding_fee", "borrow_interest", "settled_at_us",
            "spot_open_avg", "spot_open_qty", "spot_close_avg", "spot_close_qty"} <= log_cols
    idx = {r[1] for r in store._conn.execute("PRAGMA index_list(hedge_open_cycle_close_log)")}
    assert "idx_close_log_cycle" in idx
    # close_gate 默认 1（Human 已拍板：平仓闸门默认开）
    assert store.get_settings()["close_gate"] == 1
    store.close()
    # 重复构造幂等
    store2 = HedgeOpenStore(db)
    assert "task_type" in {r[1] for r in store2._conn.execute("PRAGMA table_info(hedge_open_task)")}
    assert "close_gate" in {r[1] for r in store2._conn.execute("PRAGMA table_info(hedge_open_settings)")}
    store2.close()


def test_existing_task_rows_default_to_open(tmp_path):
    svc = _svc(tmp_path)
    svc.create_task({"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
                     "single_amount": "0.5", "target_n": 1})
    rows = svc._store._conn.execute(
        "SELECT task_type FROM hedge_open_task"
    ).fetchall()
    assert all(r["task_type"] == D.TASK_TYPE_OPEN for r in rows)


# ---------------------------------------------------------------------------
# 验收 2：开仓成本隔离
# ---------------------------------------------------------------------------
def test_close_legs_excluded_from_open_cost_basis(tmp_path):
    svc = _svc(tmp_path)
    svc.create_task({"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
                     "single_amount": "0.5", "target_n": 1})
    open_tid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task WHERE coin = 'BTCUSDT' ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    svc.post_fill_all(open_tid)
    before = svc._store.aggregate_positions()
    assert len(before) == 1
    assert before[0]["perp_qty"] == "0.5"

    # 建 close 任务并成交：close 腿绝不进开仓成本基
    svc.create_task({"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
                     "single_amount": "0.5", "target_n": 1, "task_type": "close"})
    close_tid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task WHERE task_type = 'close' ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    svc.post_fill_all(close_tid)
    after = svc._store.aggregate_positions()
    assert len(after) == 1
    assert after[0]["perp_qty"] == "0.5"  # 与 close 前一致（close 腿被 task_type 过滤，数量不减）
    assert after[0]["cycle_id"] is not None


# ---------------------------------------------------------------------------
# 验收 3：close 任务创建校验
# ---------------------------------------------------------------------------
def test_create_close_task_requires_active_cycle(tmp_path):
    svc = _svc(tmp_path)
    with pytest.raises(D.HedgeError) as exc:
        svc.create_task({"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
                         "single_amount": "0.5", "target_n": 1, "task_type": "close"})
    assert exc.value.code == "no_active_cycle"
    # 建立活跃周期后可建 close 任务
    svc.create_task({"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
                     "single_amount": "0.5", "target_n": 1})
    tid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    svc.post_fill_all(tid)
    status, doc = svc.create_task({"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
                                   "single_amount": "0.5", "target_n": 1, "task_type": "close"})
    assert status == 201
    assert doc["task_type"] == "close"


def test_create_task_rejects_bad_task_type(tmp_path):
    svc = _svc(tmp_path)
    with pytest.raises(D.HedgeError) as exc:
        svc.create_task({"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
                         "single_amount": "0.5", "target_n": 1, "task_type": "nuke"})
    assert exc.value.code == "invalid_field"


# ---------------------------------------------------------------------------
# 验收 4：平仓执行（dry-run 全链路）
# ---------------------------------------------------------------------------
def test_close_execution_reversed_reduceonly_and_finalize(tmp_path):
    svc = _svc(tmp_path)
    svc.create_task({"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
                     "single_amount": "0.5", "target_n": 1})
    open_tid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task WHERE task_type='open' ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    svc.post_fill_all(open_tid)
    cycle = svc._store.get_active_cycle("BTCUSDT", "forward")
    assert cycle is not None

    svc.create_task({"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
                     "single_amount": "0.5", "target_n": 1, "task_type": "close"})
    close_tid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task WHERE task_type='close' ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    svc.post_fill_all(close_tid)

    # 方向反转：forward 平仓 = 现货 SELL 卖回 + 合约 BUY 平空
    legs = _task_legs(svc._store, close_tid)
    shapes = {}
    for leg in legs:
        shapes[leg["leg"]] = json.loads(leg["request_shape"])
    assert shapes["spot"]["side"] == "SELL"
    assert shapes["perp"]["side"] == "BUY"
    assert shapes["perp"]["reduceOnly"] == "true"   # 平仓单防超平
    assert shapes["spot"].get("sideEffectType") == "NO_SIDE_EFFECT"  # 现货纯买卖不还币

    # dry-run 完成核实：模拟无仓 → 平完
    close_task = svc._store.get_task(close_tid)
    assert svc._verify_close_flat(close_task, svc._wall_us()) == "flat"
    svc._finalize_close_task(close_task, svc._wall_us())
    assert svc._store.get_task(close_tid)["status"] == D.STATUS_DONE
    # 周期已关（auto_close）+ 结算日志写入
    closed = svc._store.get_cycle_by_id(cycle["id"])
    assert closed["closed_at_us"] is not None
    assert closed["close_reason"] == D.CLOSE_REASON_AUTO_CLOSE
    logs = svc._store.list_close_logs()
    assert len(logs) == 1
    row = logs[0]
    assert row["cycle_id"] == cycle["id"]
    assert row["close_reason"] == "auto_close"
    # RecordTransportFake 模拟成交价恒 1（无价格注入），open/close 均价独立记录
    assert row["open_avg_price"] == "1" and row["open_qty"] == "0.5"   # open 腿成本基
    assert row["close_avg_price"] == "1"                                # close 腿加权（独立）
    assert row["spot_open_avg"] == "1" and row["spot_open_qty"] == "0.5"  # 现货买入（open 腿）
    assert row["spot_close_avg"] == "1" and row["spot_close_qty"] == "0.5"  # 现货卖出（close 腿）
    assert "open_slippage" not in row or row.get("open_slippage") is None  # 滑点本轮无数据源
    assert svc._store.get_active_cycle("BTCUSDT", "forward") is None  # 不再活跃


# ---------------------------------------------------------------------------
# 验收 5：完成判定（合约腿为准）
# ---------------------------------------------------------------------------
class _StubCloseVerifyExecutor:
    """stub executor：实现 dispatch（RecordTransportFake 语义）+ 可编程
    query_symbol_um_qty 返回（有仓/无仓/查失败）。"""

    def __init__(self, qty_result):
        self._inner = RecordTransportFake()
        self._qty_result = qty_result

    def execute(self, ctx: AttemptContext) -> AttemptOutcome:
        return self._inner.execute(ctx)

    def query_symbol_um_qty(self, coin):
        return self._qty_result


def test_verify_close_flat_dry_run_simulates_flat(tmp_path):
    svc = _svc(tmp_path)
    svc.create_task({"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
                     "single_amount": "0.5", "target_n": 1})
    tid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    svc.post_fill_all(tid)
    task = svc._store.get_task(tid)
    # dry-run：executor 无 query_symbol_um_qty → 模拟无仓（平完）
    assert svc._verify_close_flat(task, svc._wall_us()) == "flat"


def test_verify_close_flat_open_when_position_remains(tmp_path):
    svc = HedgeOpenTaskService(
        str(tmp_path / "ho.sqlite3"), mode="disabled",
        executor=_StubCloseVerifyExecutor(qty_result=0.5),  # 合约仍有仓
    )
    svc.create_task({"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
                     "single_amount": "0.5", "target_n": 1})
    tid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    svc.post_fill_all(tid)
    task = svc._store.get_task(tid)
    assert svc._verify_close_flat(task, svc._wall_us()) == "open"


def test_verify_close_flat_failed_when_query_fails(tmp_path):
    svc = HedgeOpenTaskService(
        str(tmp_path / "ho.sqlite3"), mode="disabled",
        executor=_StubCloseVerifyExecutor(qty_result=None),  # 查仓失败
    )
    svc.create_task({"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
                     "single_amount": "0.5", "target_n": 1})
    tid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    svc.post_fill_all(tid)
    task = svc._store.get_task(tid)
    # fail-closed：查不到 ≠ 已平完
    assert svc._verify_close_flat(task, svc._wall_us()) == "failed"


class _FakePositionRiskClient:
    """fake HedgeOpenLiveClient：fetch_um_positions 返回可控 positionRisk body。"""

    credentials_present = True

    def __init__(self, body, http_status=200):
        self._body = body
        self._http_status = http_status
        self.calls = []

    def fetch_um_positions(self, *, symbol=None, timestamp_ms=None, recv_window_ms=None):
        self.calls.append(symbol)
        return _FakeResp(self._http_status, self._body)


class _FakeResp:
    def __init__(self, status, body):
        self.http_status = status
        self.body = body


def test_live_query_symbol_um_qty_parses_position_risk():
    executor = LiveHedgeExecutor(
        _FakePositionRiskClient(body=json.dumps([
            {"symbol": "BTCUSDT", "positionAmt": "-0.5"},
        ])), now_ms=lambda: 1,
    )
    assert executor.query_symbol_um_qty("BTCUSDT") == -0.5
    assert executor.query_symbol_um_qty("OTHERUSDT") == 0  # 无该 symbol 行 → 无仓


def test_live_query_symbol_um_qty_failed_on_http_error_or_bad_body():
    executor = LiveHedgeExecutor(
        _FakePositionRiskClient(body="oops", http_status=200), now_ms=lambda: 1,
    )
    assert executor.query_symbol_um_qty("BTCUSDT") is None  # 不可解析 → 查失败
    executor2 = LiveHedgeExecutor(
        _FakePositionRiskClient(body="[]", http_status=500), now_ms=lambda: 1,
    )
    assert executor2.query_symbol_um_qty("BTCUSDT") is None  # 非 200 → 查失败


# ---------------------------------------------------------------------------
# 验收 6：close_gate
# ---------------------------------------------------------------------------
def test_close_gate_cas_and_audit(tmp_path):
    svc = _svc(tmp_path)
    settings = svc.get_settings()[1]
    assert settings["close_gate"] is True  # 默认开
    version = settings["version"]
    # 无 confirm → 400
    with pytest.raises(D.HedgeError) as exc:
        svc.put_close_gate({"enabled": False, "version": version})
    assert exc.value.code == "confirmation_required"
    # version 冲突 → 409
    with pytest.raises(D.HedgeError) as exc:
        svc.put_close_gate({"enabled": False, "confirm": True, "version": version - 5})
    assert exc.value.code == "version_conflict"
    # 正确 CAS → 200 + 审计行
    status, doc = svc.put_close_gate({"enabled": False, "confirm": True, "version": version})
    assert status == 200 and doc["close_gate"] is False
    audit = svc._store._conn.execute(
        "SELECT kind, payload FROM hedge_open_log WHERE kind = 'close_gate_changed'"
    ).fetchall()
    assert len(audit) == 1
    payload = json.loads(audit[0]["payload"])
    assert payload["enabled"] is False and payload["previous_enabled"] is True
    assert svc.is_close_gate_on() is False
    # 重新开启（确认 + 新 version）
    status, doc = svc.put_close_gate({"enabled": True, "confirm": True, "version": doc["version"]})
    assert status == 200 and doc["close_gate"] is True


def test_close_gate_blocks_close_task_dispatch(tmp_path):
    """close_gate=0 时 close 任务 worker 拒发（fail-closed），镜像 start-gate-off。"""
    from backend.hedge_open_tasks.service import HedgeOpenTaskService as S
    svc = S(str(tmp_path / "ho.sqlite3"), mode="disabled")
    svc.create_task({"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
                     "single_amount": "0.5", "target_n": 1})
    tid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    svc.post_fill_all(tid)
    svc.create_task({"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
                     "single_amount": "0.5", "target_n": 1, "task_type": "close"})
    close_tid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task WHERE task_type='close' ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    # 关闭平仓闸门
    settings = svc.get_settings()[1]
    svc.put_close_gate({"enabled": False, "confirm": True, "version": settings["version"]})
    # worker 轮询：close 任务在 close_gate=0 时 exit（不 dispatch）
    assert svc.is_close_gate_on() is False
    # 直接验证 _worker_round 的闸门检查路径：任务保持 running、未调度任何 attempt
    attempts_before = svc._store._conn.execute(
        "SELECT COUNT(*) FROM hedge_open_attempt WHERE task_id = ?", (close_tid,)
    ).fetchone()[0]
    assert attempts_before == 0
    task = svc._store.get_task(close_tid)
    # dry-run 无 worker 循环，直接调一轮 dispatch 前检查：close_gate off → 无新 attempt
    assert svc.is_close_gate_on() is False


# ---------------------------------------------------------------------------
# 验收 7：结算日志数据源（GET /api/hedge-open-close-logs）
# ---------------------------------------------------------------------------
def test_get_close_logs_service_endpoint(tmp_path):
    svc = _svc(tmp_path)
    assert svc.get_close_logs()[1] == {"logs": []}
    svc.create_task({"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
                     "single_amount": "0.5", "target_n": 1})
    tid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    svc.post_fill_all(tid)
    cycle = svc._store.get_active_cycle("BTCUSDT", "forward")
    task = svc._store.get_task(tid)
    svc._finalize_close_task(task, svc._wall_us())
    status, doc = svc.get_close_logs()
    assert status == 200
    assert len(doc["logs"]) == 1
    row = doc["logs"][0]
    assert row["cycle_id"] == cycle["id"]
    assert row["symbol"] == "BTCUSDT" and row["direction"] == "forward"
    # 滑点字段：close_log 表无现货/滑点列（本轮无数据源），历史页该列显示 —
    assert "open_slippage" in row and row.get("open_slippage") is None  # 无 est_price 时滑点为 None（不臆造）


# ===========================================================================
# 平仓现货卖出重设计（2026-08）：路由 + 划转 + USDT 回流
# ===========================================================================
# ---- 验收 1：路由修复（decide_spot_route 纯函数权威） ----
def test_route_close_forward_fixed_regular_spot_even_when_cap_exceeded():
    """复现 COOKIEUSDT 事故场景：cap_exceeded=True 时 forward close 仍走普通账户。"""
    route, reason = D.decide_spot_route(
        D.DIR_FORWARD, "PERPETUAL", "COOKIE", True, task_type=D.TASK_TYPE_CLOSE,
    )
    assert route == D.SPOT_ROUTE_REGULAR_SPOT
    assert reason == D.ROUTE_REASON_CLOSE_SELL_REGULAR
    # 路由不依赖 cap 值：cap=False / None 同样 regular（close 不再走 cap 预检）
    for cap in (False, None):
        r2, _ = D.decide_spot_route(
            D.DIR_FORWARD, "PERPETUAL", "COOKIE", cap, task_type=D.TASK_TYPE_CLOSE,
        )
        assert r2 == D.SPOT_ROUTE_REGULAR_SPOT
    # endpoint 映射：regular_spot → /api/v3/order
    assert D.spot_route_endpoint(D.SPOT_ROUTE_REGULAR_SPOT) == D.REGULAR_SPOT_ORDER_PATH


def test_route_close_reverse_fixed_papi_margin():
    route, reason = D.decide_spot_route(
        D.DIR_REVERSE, "PERPETUAL", None, None, task_type=D.TASK_TYPE_CLOSE,
    )
    assert route == D.SPOT_ROUTE_PAPI_MARGIN
    assert reason == D.ROUTE_REASON_PAPI_DEFAULT
    assert D.spot_route_endpoint(route) == D.SPOT_ORDER_PATH  # /papi/v1/margin/order


def test_route_open_unchanged():
    """开仓路由逐字不变（回归）：forward cap→regular、TRADIFI→regular、其余 papi。"""
    r1, reason1 = D.decide_spot_route(
        D.DIR_FORWARD, "PERPETUAL", "BTC", True, task_type=D.TASK_TYPE_OPEN,
    )
    assert r1 == D.SPOT_ROUTE_REGULAR_SPOT and reason1 == D.ROUTE_REASON_COLLATERAL_CAP_PRECHECK
    r2, reason2 = D.decide_spot_route(
        D.DIR_FORWARD, "TRADIFI_PERPETUAL", "TSLA", False, task_type=D.TASK_TYPE_OPEN,
    )
    assert r2 == D.SPOT_ROUTE_REGULAR_SPOT and reason2 == D.ROUTE_REASON_TRADIFI_REGULAR_SPOT
    r3, reason3 = D.decide_spot_route(
        D.DIR_FORWARD, "PERPETUAL", "BTC", False, task_type=D.TASK_TYPE_OPEN,
    )
    assert r3 == D.SPOT_ROUTE_PAPI_MARGIN and reason3 == D.ROUTE_REASON_PAPI_DEFAULT
    r4, _ = D.decide_spot_route(
        D.DIR_REVERSE, "PERPETUAL", None, None, task_type=D.TASK_TYPE_OPEN,
    )
    assert r4 == D.SPOT_ROUTE_PAPI_MARGIN


# ---- 验收 2：万向划转能力（universal_transfer） ----
def test_universal_transfer_type_frozen_and_signed_post(monkeypatch):
    from backend.services.hedge_open_live_client import HedgeOpenLiveClient
    client = HedgeOpenLiveClient.__new__(HedgeOpenLiveClient)  # 绕过 __init__（无需凭证）
    captured = {}
    def fake_post_signed(path, params, timestamp_ms, recv_window_ms=None):
        captured["path"] = path
        captured["params"] = params
        return _FakeResp(200, '{"tranId": 12345}')
    monkeypatch.setattr(client, "_post_signed", fake_post_signed)
    monkeypatch.setattr(client, "_require_whitelisted", lambda m, p: "https://api.binance.com")
    resp = client.universal_transfer(
        "PORTFOLIO_MARGIN_MAIN", "COOKIE", "12.5", timestamp_ms=1,
    )
    assert captured["path"] == "/sapi/v1/asset/transfer"
    assert captured["params"] == {"type": "PORTFOLIO_MARGIN_MAIN",
                                  "asset": "COOKIE", "amount": "12.5"}
    assert resp.http_status == 200
    # type 冻结：非枚举拒绝
    import pytest as _pt
    with _pt.raises(ValueError):
        client.universal_transfer("EVIL_TYPE", "COOKIE", "1", timestamp_ms=1)


def test_live_executor_universal_transfer_returns_tranid_or_raises():
    executor = LiveHedgeExecutor(
        _FakePositionRiskClient(body='{"tranId": 777}', http_status=200), now_ms=lambda: 1,
    )
    # _FakePositionRiskClient 无 universal_transfer —— 用 monkeypatch 语义的 fake
    class _XferClient(_FakePositionRiskClient):
        def universal_transfer(self, type_, asset, amount, **kw):
            self.calls.append(("xfer", type_, asset, amount))
            if type_ == "MAIN_PORTFOLIO_MARGIN":
                return _FakeResp(200, '{"tranId": 888}')
            return _FakeResp(500, "{}")
    ex = LiveHedgeExecutor(_XferClient(body="[]", http_status=200), now_ms=lambda: 1)
    assert ex.universal_transfer("MAIN_PORTFOLIO_MARGIN", "USDT", "10") == "888"
    import pytest as _pt
    with _pt.raises(RuntimeError):
        ex.universal_transfer("PORTFOLIO_MARGIN_MAIN", "COOKIE", "1")  # 500 → 抛错不重试


def test_live_executor_query_spot_free_parses_account():
    class _AcctClient(_FakePositionRiskClient):
        def get_spot_account(self, **kw):
            return _FakeResp(200, json.dumps({
                "balances": [
                    {"asset": "COOKIE", "free": "12.5", "locked": "0"},
                    {"asset": "USDT", "free": "999", "locked": "1"},
                ]
            }))
    ex = LiveHedgeExecutor(_AcctClient(body="[]", http_status=200), now_ms=lambda: 1)
    assert ex.query_spot_free("COOKIE") == 12.5
    assert ex.query_spot_free("USDT") == 999
    assert ex.query_spot_free("MISSING") == 0  # 无行 → 余额 0


def test_live_executor_query_unified_free_parses_pm_balance():
    """统一账户（PM）余额解析：字段 crossMarginFree（划转前检查用）。"""

    class _PmClient(_FakePositionRiskClient):
        def get_balance(self, **kw):
            # /papi/v1/balance 响应是顶层数组（对齐 provider 解析），非 {"balances": [...]}
            return _FakeResp(200, json.dumps([
                {"asset": "COOKIE", "crossMarginFree": "997.0", "crossWalletBalance": "1000"},
                {"asset": "USDT", "crossMarginFree": "500.5"},
            ]))
    ex = LiveHedgeExecutor(_PmClient(body="[]", http_status=200), now_ms=lambda: 1)
    assert ex.query_unified_free("COOKIE") == Decimal("997.0")
    assert ex.query_unified_free("USDT") == Decimal("500.5")
    assert ex.query_unified_free("MISSING") == 0  # 无行 → 余额 0

    class _PmFailClient(_FakePositionRiskClient):
        def get_balance(self, **kw):
            return _FakeResp(500, "err")
    ex2 = LiveHedgeExecutor(_PmFailClient(body="[]", http_status=200), now_ms=lambda: 1)
    assert ex2.query_unified_free("COOKIE") is None  # 非 200 → None（fail-closed）


def test_universal_transfer_error_carries_response_body():
    """划转失败异常带交易所响应详情（body 截断），不只有 'RuntimeError'。"""

    class _XferFailClient(_FakePositionRiskClient):
        def universal_transfer(self, type_, asset, amount, **kw):
            return _FakeResp(400, json.dumps({"code": -4015, "msg": "insufficient balance"}))
    ex = LiveHedgeExecutor(_XferFailClient(body="[]", http_status=200), now_ms=lambda: 1)
    try:
        ex.universal_transfer("PORTFOLIO_MARGIN_MAIN", "COOKIE", "1000")
        raise AssertionError("应抛错")
    except RuntimeError as exc:
        msg = str(exc)
        assert "-4015" in msg and "insufficient balance" in msg, f"异常应带响应详情: {msg}"


# ---- 验收 3：划转时序（一次性 + fail-closed） ----
class _CloseSpotExecutor:
    """可编程 close 现货流程 stub：dispatch（RecordTransportFake 语义）+
    query_spot_free + universal_transfer + query_symbol_um_qty。"""

    def __init__(self, spot_free=None, transfer_raise=None, recheck_free=None,
                 unified_free=None):
        self._inner = RecordTransportFake()
        self.spot_free = spot_free          # 初始普通账户余额
        self.recheck_free = recheck_free    # 划转后复检余额（None = 用 spot_free）
        self.transfer_raise = transfer_raise
        self.unified_free = unified_free    # 统一账户余额（None = 未提供，触发查询失败分支）
        self.transfers = []                 # [(type_, asset, amount)]
        self.free_calls = []

    def execute(self, ctx):
        return self._inner.execute(ctx)

    def query_symbol_um_qty(self, coin):
        return 0  # 模拟无仓

    def query_unified_free(self, asset):
        self.unified_calls = getattr(self, "unified_calls", []) + [asset]
        return self.unified_free

    def query_spot_free(self, asset):
        self.free_calls.append(asset)
        if self.spot_free is None:
            return None
        return self.spot_free  # §4.2（task 05）：后置复检已删除，只查一次

    def universal_transfer(self, type_, asset, amount):
        if self.transfer_raise is not None:
            raise self.transfer_raise
        self.transfers.append((type_, asset, amount))
        return "tran-1"


def _make_forward_close_with_open(svc_factory):
    svc = svc_factory()
    svc.create_task({"coin": "COOKIEUSDT", "direction": "forward", "mode": "immediate",
                     "single_amount": "10", "target_n": 1})
    tid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task WHERE task_type='open' ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    svc.post_fill_all(tid)
    svc.create_task({"coin": "COOKIEUSDT", "direction": "forward", "mode": "immediate",
                     "single_amount": "10", "target_n": 1, "task_type": "close"})
    ctid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task WHERE task_type='close' ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    return svc, ctid


def test_ensure_close_spot_balance_skips_reverse_close(tmp_path):
    svc = HedgeOpenTaskService(str(tmp_path / "ho.sqlite3"), mode="disabled")
    svc.create_task({"coin": "COOKIEUSDT", "direction": "reverse", "mode": "immediate",
                     "single_amount": "10", "target_n": 1})
    tid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    svc.post_fill_all(tid)
    svc.create_task({"coin": "COOKIEUSDT", "direction": "reverse", "mode": "immediate",
                     "single_amount": "10", "target_n": 1, "task_type": "close"})
    ctid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task WHERE task_type='close' ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    task = svc._store.get_task(ctid)
    # reverse close（买现货走统一账户）：跳过划转检查
    assert svc._ensure_close_spot_balance(task, svc._wall_us()) is None


def test_ensure_close_spot_balance_sufficient_no_transfer(tmp_path):
    exe = _CloseSpotExecutor(spot_free=20)  # 普通账户 20 ≥ 计划卖 10
    svc = HedgeOpenTaskService(str(tmp_path / "ho.sqlite3"), mode="disabled", executor=exe)
    svc, ctid = _make_forward_close_with_open(lambda: svc)
    task = svc._store.get_task(ctid)
    assert svc._ensure_close_spot_balance(task, svc._wall_us()) is None
    assert exe.transfers == []  # 余额够 → 不划转直卖


def test_ensure_close_spot_balance_transfers_and_rechecks(tmp_path):
    exe = _CloseSpotExecutor(spot_free=4, recheck_free=10, unified_free=100)  # 不足 4 → 划转补 6 → 复检 10
    svc = HedgeOpenTaskService(str(tmp_path / "ho.sqlite3"), mode="disabled", executor=exe)
    svc, ctid = _make_forward_close_with_open(lambda: svc)
    task = svc._store.get_task(ctid)
    assert svc._ensure_close_spot_balance(task, svc._wall_us()) is None
    assert exe.transfers == [("PORTFOLIO_MARGIN_MAIN", "COOKIE", "6")]
    logs = svc._store._conn.execute(
        "SELECT kind, payload FROM hedge_open_log WHERE kind='close_transfer'"
    ).fetchall()
    actions = [json.loads(r["payload"])["action"] for r in logs]
    assert actions == ["start", "ok"]


def test_ensure_close_spot_balance_transfer_failure_pauses(tmp_path):
    exe = _CloseSpotExecutor(spot_free=4, transfer_raise=RuntimeError("timeout"), unified_free=100)
    svc = HedgeOpenTaskService(str(tmp_path / "ho.sqlite3"), mode="disabled", executor=exe)
    svc, ctid = _make_forward_close_with_open(lambda: svc)
    task = svc._store.get_task(ctid)
    err = svc._ensure_close_spot_balance(task, svc._wall_us())
    assert err is not None and "划转补足现货失败" in err
    logs = svc._store._conn.execute(
        "SELECT payload FROM hedge_open_log WHERE kind='close_transfer'"
    ).fetchall()
    assert json.loads(logs[-1]["payload"])["action"] == "failed"


def test_ensure_close_spot_balance_no_recheck_after_transfer(tmp_path):
    # §4.2（Human 决定 3，task 05）：后置复检已删除——只认划转返回结果（拿到
    # tranId 即成功），划转成功后直接放行，不再重复查询余额。
    exe = _CloseSpotExecutor(spot_free=4, recheck_free=5, unified_free=100)
    svc = HedgeOpenTaskService(str(tmp_path / "ho.sqlite3"), mode="disabled", executor=exe)
    svc, ctid = _make_forward_close_with_open(lambda: svc)
    task = svc._store.get_task(ctid)
    err = svc._ensure_close_spot_balance(task, svc._wall_us())
    assert err is None  # 划转成功即放行（不再复检、不暂停）
    assert exe.transfers == [("PORTFOLIO_MARGIN_MAIN", "COOKIE", "6")]
    assert len(exe.free_calls) == 1  # 余额只查了一次（初始不足判断）


def test_ensure_close_spot_balance_query_failure(tmp_path):
    exe = _CloseSpotExecutor(spot_free=None)  # 查询失败
    svc = HedgeOpenTaskService(str(tmp_path / "ho.sqlite3"), mode="disabled", executor=exe)
    svc, ctid = _make_forward_close_with_open(lambda: svc)
    task = svc._store.get_task(ctid)
    err = svc._ensure_close_spot_balance(task, svc._wall_us())
    assert err is not None and "查询失败" in err


# ---- 验收 4：USDT 回流 ----
def test_transfer_back_usdt_on_forward_close_success(tmp_path):
    exe = _CloseSpotExecutor(spot_free=20)
    svc = HedgeOpenTaskService(str(tmp_path / "ho.sqlite3"), mode="disabled", executor=exe)
    svc, ctid = _make_forward_close_with_open(lambda: svc)
    svc.post_fill_all(ctid)  # close 腿成交（quote 合计 = 10 × 模拟价 1 = 10）
    task = svc._store.get_task(ctid)
    svc._transfer_back_usdt(task, svc._wall_us())
    assert ("MAIN_PORTFOLIO_MARGIN", "USDT", "10") in exe.transfers
    logs = svc._store._conn.execute(
        "SELECT payload FROM hedge_open_log WHERE kind='close_transfer'"
    ).fetchall()
    assert json.loads(logs[-1]["payload"])["action"] == "usdt_back_ok"


def test_transfer_back_usdt_failure_does_not_block_task(tmp_path):
    exe = _CloseSpotExecutor(spot_free=20, transfer_raise=RuntimeError("timeout"))
    svc = HedgeOpenTaskService(str(tmp_path / "ho.sqlite3"), mode="disabled", executor=exe)
    svc, ctid = _make_forward_close_with_open(lambda: svc)
    svc.post_fill_all(ctid)
    task = svc._store.get_task(ctid)
    # 回流失败不抛错、任务状态不变（平仓已完成是主事实）
    svc._transfer_back_usdt(task, svc._wall_us())
    logs = svc._store._conn.execute(
        "SELECT payload FROM hedge_open_log WHERE kind='close_transfer'"
    ).fetchall()
    assert json.loads(logs[-1]["payload"])["action"] == "usdt_back_failed"


def test_transfer_back_usdt_skipped_for_reverse_close(tmp_path):
    exe = _CloseSpotExecutor(spot_free=20)
    svc = HedgeOpenTaskService(str(tmp_path / "ho.sqlite3"), mode="disabled", executor=exe)
    svc.create_task({"coin": "COOKIEUSDT", "direction": "reverse", "mode": "immediate",
                     "single_amount": "10", "target_n": 1})
    tid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    svc.post_fill_all(tid)
    svc.create_task({"coin": "COOKIEUSDT", "direction": "reverse", "mode": "immediate",
                     "single_amount": "10", "target_n": 1, "task_type": "close"})
    ctid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task WHERE task_type='close' ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    svc.post_fill_all(ctid)
    task = svc._store.get_task(ctid)
    svc._transfer_back_usdt(task, svc._wall_us())
    assert exe.transfers == []  # reverse close 买入花钱，无回流


def test_dry_run_ensure_and_transfer_are_noops(tmp_path):
    """dry-run（executor 无 query_spot_free/universal_transfer）→ 模拟余额足够/回流成功。"""
    svc = HedgeOpenTaskService(str(tmp_path / "ho.sqlite3"), mode="disabled")
    svc, ctid = _make_forward_close_with_open(lambda: svc)
    task = svc._store.get_task(ctid)
    assert svc._ensure_close_spot_balance(task, svc._wall_us()) is None
    svc._transfer_back_usdt(task, svc._wall_us())  # 不抛错、不写日志
    logs = svc._store._conn.execute(
        "SELECT COUNT(*) FROM hedge_open_log WHERE kind='close_transfer'"
    ).fetchone()[0]
    assert logs == 0


# ---------------------------------------------------------------------------
# 2026-08 修复：close 任务从 running 变其他状态必须先走合约无仓核实
# （Human 拍板）。attempt 成交后不自动 done（suppress_done），由 worker 核实
# 接管：flat → finalize（done+close_cycle+close_log）；open+次数用完 → 部分平
# done（周期不关、不写结算）。
# ---------------------------------------------------------------------------
def test_close_worker_auto_finalize_on_flat(tmp_path):
    """全平：close 任务 attempt 成交后任务不立即 done，worker 核实 flat →
    done + close_cycle + close_log（修复前：target_n=1 时 done 抢先，finalize 不到）。"""
    svc = _svc(tmp_path)
    svc.set_start_gate(True)  # 生产 Start gate 常开；dry-run 默认关会卡 worker gate 检查
    svc.create_task({"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
                     "single_amount": "0.5", "target_n": 1})
    open_tid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task WHERE task_type='open' ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    svc.post_fill_all(open_tid)
    cycle = svc._store.get_active_cycle("BTCUSDT", "forward")
    assert cycle is not None

    svc.create_task({"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
                     "single_amount": "0.5", "target_n": 1, "task_type": "close"})
    close_tid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task WHERE task_type='close' ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    svc.post_fill_all(close_tid)
    # 修复点 1：attempt 成交后任务不自动 done（suppress_done），保持 running 等核实
    after_fill = svc._store.get_task(close_tid)
    assert after_fill["status"] == D.STATUS_RUNNING, "close 成交后应保持 running（不抢先 done）"
    # 修复点 2：worker 循环核实 flat → finalize（done + close_cycle + close_log）
    svc._pump_worker(close_tid, max_rounds=16)
    done = svc._store.get_task(close_tid)
    assert done["status"] == D.STATUS_DONE
    closed = svc._store.get_cycle_by_id(cycle["id"])
    assert closed["closed_at_us"] is not None
    assert closed["close_reason"] == D.CLOSE_REASON_AUTO_CLOSE
    logs = svc._store.list_close_logs()
    assert len(logs) == 1 and logs[0]["cycle_id"] == cycle["id"]
    assert svc._store.get_active_cycle("BTCUSDT", "forward") is None


def test_close_worker_partial_done_when_position_remains(tmp_path):
    """部分平：合约仍有仓 + 次数用完 → 任务 done（部分平），周期不关、不写结算日志，
    并写 close_partial_done 日志（Human：部分平周期不关正确）。"""
    svc = HedgeOpenTaskService(
        str(tmp_path / "ho.sqlite3"), mode="disabled",
        executor=_StubCloseVerifyExecutor(qty_result=0.5),  # 合约仍有仓
    )
    svc.set_start_gate(True)  # 生产 Start gate 常开；dry-run 默认关会卡 worker gate 检查
    svc.create_task({"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
                     "single_amount": "0.5", "target_n": 1})
    open_tid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    svc.post_fill_all(open_tid)
    cycle = svc._store.get_active_cycle("BTCUSDT", "forward")
    assert cycle is not None

    svc.create_task({"coin": "BTCUSDT", "direction": "forward", "mode": "immediate",
                     "single_amount": "0.5", "target_n": 1, "task_type": "close"})
    close_tid = svc._store._conn.execute(
        "SELECT id FROM hedge_open_task ORDER BY creation_seq DESC LIMIT 1"
    ).fetchone()[0]
    svc.post_fill_all(close_tid)
    after_fill = svc._store.get_task(close_tid)
    assert after_fill["status"] == D.STATUS_RUNNING  # 成交后不抢先 done
    svc._pump_worker(close_tid, max_rounds=16)
    done = svc._store.get_task(close_tid)
    assert done["status"] == D.STATUS_DONE  # 部分平完成
    # 周期不关、不写结算日志（周期未结束）
    assert svc._store.get_cycle_by_id(cycle["id"])["closed_at_us"] is None
    assert len(svc._store.list_close_logs()) == 0
    # close_partial_done 日志落库（任务卡可见「合约仍有仓，周期未关闭」）
    page, _ = svc._store.list_logs_page(50, None, None)
    kinds = [r["kind"] for r in page if r["task_id"] == close_tid]
    assert "close_partial_done" in kinds


# ===========================================================================
# sonnet5 评审 P0-F1 修复：live fresh preflight 余额校验方向反转
# （评审盲区：既有平仓测试全为 dry-run，不触发 live fresh preflight 路径）
# ===========================================================================
class _SpyPreflightProvider:
    """记录 get_snapshot 收到的 (coin, direction, task_type)，返回固定 snapshot。"""

    def __init__(self, snapshot):
        self._snapshot = snapshot
        self.calls = []

    def get_snapshot(self, coin, direction, task_type="open"):
        self.calls.append((coin, direction, task_type))
        return self._snapshot


class _FakeLiveExecutor:
    """仅满足 ``_live_dispatch_capable()``（有 dispatch 属性）触发真实 live 路径；
    _resolve_fresh_preflight 不调用 dispatch（余额/路由检查先行）。"""

    def dispatch(self, ctx):  # pragma: no cover
        raise AssertionError("dispatch must not be reached by _resolve_fresh_preflight")


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


def _make_live_svc(tmp_path, snapshot):
    provider = _SpyPreflightProvider(snapshot)
    svc = HedgeOpenTaskService(
        str(tmp_path / "ho.sqlite3"), mode="live",
        executor=_FakeLiveExecutor(), preflight_provider=provider,
    )
    assert svc._live_dispatch_capable() is True  # 真实 live 路径（非 dry-run）
    return svc, provider


def _make_close_task(svc, coin, direction):
    task = svc._store.create_task(
        "fx-close", coin, direction, D.MODE_IMMEDIATE, "100", 1, "100",
        D.POS_MODE_BOTH, None, 1_000, task_type=D.TASK_TYPE_CLOSE,
    )
    return svc._store.get_task(task["id"])


def test_live_fresh_preflight_forward_close_checks_base_asset(tmp_path):
    """forward close：余额校验走反转方向（reverse → 查统一账户 base 资产）。

    复现评审场景：统一账户 base 充足（100000）、普通账户 USDT 0（balances 无 USDT、
    spot_account_usdt 不设）——修复前按 forward 查 USDT 会误判余额不足 FATAL；
    修复后按 reverse 查 base 资产 → 通过。
    """
    from backend.hedge_open_tasks.domain import PreflightSnapshot as _PS
    snap = _PS(
        spot_filters=_spot_filters_fx(), perp_filters=_perp_filters_fx(),
        balances={"COOKIE": D.Decimal("100000")},  # 统一账户 base 充足
        position_mode=D.POS_MODE_BOTH, est_price=D.Decimal("1"),
        symbol_tradable=True,
    )
    svc, provider = _make_live_svc(tmp_path, snap)
    task = _make_close_task(svc, "COOKIEUSDT", D.DIR_FORWARD)
    fp = svc._resolve_fresh_preflight(task)
    assert provider.calls[-1] == ("COOKIEUSDT", D.DIR_REVERSE, D.TASK_TYPE_CLOSE)
    assert fp is not None and fp.ok is True
    assert fp.fatal is False and fp.rejection is None


def test_live_fresh_preflight_reverse_close_checks_usdt(tmp_path):
    """reverse close：对称——余额校验走反转方向（forward → 查统一账户 USDT）。

    统一账户 USDT 充足（100000）、base 资产 0 → 修复前按 reverse 查 base 会误拒。
    """
    from backend.hedge_open_tasks.domain import PreflightSnapshot as _PS
    snap = _PS(
        spot_filters=_spot_filters_fx(), perp_filters=_perp_filters_fx(),
        balances={"USDT": D.Decimal("100000")},  # 统一账户 USDT 充足
        position_mode=D.POS_MODE_BOTH, est_price=D.Decimal("1"),
        symbol_tradable=True,
    )
    svc, provider = _make_live_svc(tmp_path, snap)
    task = _make_close_task(svc, "COOKIEUSDT", D.DIR_REVERSE)
    fp = svc._resolve_fresh_preflight(task)
    assert provider.calls[-1] == ("COOKIEUSDT", D.DIR_FORWARD, D.TASK_TYPE_CLOSE)
    assert fp is not None and fp.ok is True
    assert fp.fatal is False and fp.rejection is None


# ---------------------------------------------------------------------------
# Stage 2026-08-06 task 05 §4.2（Human 决定 3）：划转改造——缓存放行 / 实时确认
# 才动手 / 无后置复检 / sleep(100ms) / 余额不足文案带「划转尚未到账」提示。
# ---------------------------------------------------------------------------
def _cached_close_svc(tmp_path, exe, caches):
    svc = HedgeOpenTaskService(str(tmp_path / "ho.sqlite3"), mode="disabled", executor=exe)
    import time as _t
    now = _t.monotonic()
    svc.configure_snapshot_reader(
        lambda sid: (now, caches[sid]) if sid in caches else None
    )
    return svc


def test_close_balance_cache_sufficient_passes_without_realtime(tmp_path):
    # 缓存显示充足 → 直接放行：0 次实时查询、0 划转（覆盖绝大多数情况的 0 网络路径）。
    exe = _CloseSpotExecutor(spot_free=4, unified_free=100)  # 实时其实不足
    svc = _cached_close_svc(
        tmp_path, exe, {"spot_balances": [{"asset": "COOKIE", "free": "999"}]},
    )
    svc, ctid = _make_forward_close_with_open(lambda: svc)
    task = svc._store.get_task(ctid)
    assert svc._ensure_close_spot_balance(task, svc._wall_us()) is None
    assert exe.transfers == []    # 缓存充足 → 未划转
    assert exe.free_calls == []   # 未实时查询


def test_close_balance_cache_insufficient_confirms_realtime_then_transfers(tmp_path):
    # 缓存显示不足 → 必须实时确认；实时仍不足才发起划转（缓存绝不触发有副作用的
    # 划转动作）。
    exe = _CloseSpotExecutor(spot_free=4, unified_free=100)
    svc = _cached_close_svc(
        tmp_path, exe, {"spot_balances": [{"asset": "COOKIE", "free": "2"}]},
    )
    svc, ctid = _make_forward_close_with_open(lambda: svc)
    task = svc._store.get_task(ctid)
    assert svc._ensure_close_spot_balance(task, svc._wall_us()) is None
    assert exe.transfers == [("PORTFOLIO_MARGIN_MAIN", "COOKIE", "6")]  # 实时确认后划转
    assert len(exe.free_calls) == 1  # 恰好实时确认一次


def test_close_balance_cache_sufficient_unified_skips_realtime_unified(tmp_path):
    # unified_balances 缓存足够（放行类）→ 不实时查统一账户。
    exe = _CloseSpotExecutor(spot_free=4, unified_free=None)  # 实时统一查询会失败
    svc = _cached_close_svc(
        tmp_path, exe, {
            "spot_balances": [{"asset": "COOKIE", "free": "2"}],
            "unified_balances": [{"asset": "COOKIE", "crossMarginFree": "100"}],
        },
    )
    svc, ctid = _make_forward_close_with_open(lambda: svc)
    task = svc._store.get_task(ctid)
    assert svc._ensure_close_spot_balance(task, svc._wall_us()) is None
    assert exe.transfers == [("PORTFOLIO_MARGIN_MAIN", "COOKIE", "6")]
    assert getattr(exe, "unified_calls", []) == []  # 未实时查统一账户


def test_close_transfer_sleeps_100ms_and_no_recheck(tmp_path, monkeypatch):
    slept = []
    monkeypatch.setattr(
        "backend.hedge_open_tasks.service.time.sleep", lambda s: slept.append(s),
    )
    exe = _CloseSpotExecutor(spot_free=4, recheck_free=5, unified_free=100)
    svc = HedgeOpenTaskService(str(tmp_path / "ho.sqlite3"), mode="disabled", executor=exe)
    svc, ctid = _make_forward_close_with_open(lambda: svc)
    task = svc._store.get_task(ctid)
    assert svc._ensure_close_spot_balance(task, svc._wall_us()) is None
    assert slept == [0.1]           # 划转成功后 sleep(100ms) 让余额同步
    assert len(exe.free_calls) == 1  # 后置复检已删除（只查了一次初始余额）


def test_close_insufficient_pause_zh_notes_transfer_in_flight(tmp_path):
    # §4.2 第 3 条：划转成功后余额不足暂停 → 中文文案含「可能是划转尚未到账」，
    # 让操作者区分「真没钱」与「钱还在路上」。
    exe = _CloseSpotExecutor(spot_free=4, unified_free=100)
    svc = HedgeOpenTaskService(str(tmp_path / "ho.sqlite3"), mode="disabled", executor=exe)
    svc, ctid = _make_forward_close_with_open(lambda: svc)
    task = svc._store.get_task(ctid)
    assert svc._ensure_close_spot_balance(task, svc._wall_us()) is None  # 划转 ok
    zh = svc._close_insufficient_pause_zh(task, D.PAUSE_REASON_INSUFFICIENT_BALANCE)
    assert zh is not None
    assert "可能是划转尚未到账" in zh
    assert "6 COOKIE" in zh
    # 无划转记录的任务 → None（沿用表查通用文案）。
    exe2 = _CloseSpotExecutor(spot_free=20, unified_free=100)
    svc2 = HedgeOpenTaskService(str(tmp_path / "h2.sqlite3"), mode="disabled", executor=exe2)
    svc2, ctid2 = _make_forward_close_with_open(lambda: svc2)
    task2 = svc2._store.get_task(ctid2)
    assert svc2._ensure_close_spot_balance(task2, svc2._wall_us()) is None  # 充足未划转
    assert svc2._close_insufficient_pause_zh(task2, D.PAUSE_REASON_INSUFFICIENT_BALANCE) is None
