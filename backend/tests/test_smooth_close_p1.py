"""平滑平仓 V1 后端 P1 验收测试（stage 2026-08-14-smooth-close-orders-v1）。

覆盖设计 r3 §8 验收矩阵中属于后端的项：1、2、4、6、7、7a、7b、8、9、10、
10a、11、12、13、14、15、17、18、19、21、22（spec §5 列表）。

全部使用 fake clock / fake market provider / record executor——不发真实订单、
不连接交易所、不启动服务。三条"假绿"陷阱按 spec §5 实现：
- 10a 让"能启动、能订阅、但 gate 永远建不起来、零成交"的实现变红；
- 10 除断言零 attempt / 零 executor 外，还断言任务落暂停且 worker 轮次有上限；
- 15 备料段持仓查询与收尾 `_verify_close_flat` 按调用点分段计数。
"""
from __future__ import annotations

import time
import uuid
from decimal import Decimal

import pytest

from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.service import HedgeOpenTaskService, task_to_doc
from backend.services.live_hedge_executor import (
    LEG_ACCEPTED,
    LEG_REJECTED,
    LegDispatch,
    LiveAttemptDispatch,
)


SPOT = ("binance", "spot", "BTCUSDT")
SWAP = ("binance", "swap", "BTCUSDT")


class _Clock:
    def __init__(self, value=1_000_000):
        self.t = value

    def mono_us(self):
        return self.t

    def wall_us(self):
        return self.t


class _Market:
    """fake 盘口 provider：记录订阅引用，publish 即回调（同 open 侧测试模式）。"""

    def __init__(self):
        self.callback = None
        self.snapshots = {}
        self.refs = {}

    def set_on_change(self, callback):
        self.callback = callback

    def subscribe(self, key):
        self.refs[key] = self.refs.get(key, 0) + 1

    def release(self, key):
        refs = self.refs.get(key, 0) - 1
        if refs <= 0:
            self.refs.pop(key, None)
        else:
            self.refs[key] = refs

    def latest(self, key):
        return self.snapshots.get(key)

    def publish(self, key, *, bid, bid_qty="1", ask=None, ask_qty="1"):
        from backend.services.best_bid_ask_provider import BookTickerSnapshot
        self.snapshots[key] = BookTickerSnapshot(
            key=key,
            bid_price=Decimal(bid),
            bid_qty=Decimal(bid_qty),
            ask_price=Decimal(ask if ask is not None else bid),
            ask_qty=Decimal(ask_qty),
            exchange_ts_ms=None,
            received_at_us=1,
            generation=1,
            status="live",
            error_zh=None,
        )
        if self.callback is not None:
            self.callback(key)

    def close(self):
        return None


class _ClosePreflight:
    """fake preflight provider：可编程 filters step；记录每次调用的方向。
    ``snapshot_result=None`` 模拟预检读失败（get_snapshot → None）。"""

    def __init__(self, step="0.001", snapshot_result="default"):
        self.step = step
        self.snapshot_result = snapshot_result
        self.last_failed_read = None
        self.calls = []

    def get_snapshot(self, coin, direction, task_type="open", position_side_mode=None):
        self.calls.append((coin, direction, task_type, position_side_mode))
        if self.snapshot_result is None:
            return None
        filters = {
            "lot_size": {"min_qty": "0.001", "max_qty": "100000", "step_size": self.step},
            "market_lot_size": {"min_qty": "0.001", "max_qty": "100000",
                                "step_size": self.step},
            "notional": {"min_notional": "1", "apply_min_to_market": True},
        }
        return D.PreflightSnapshot(
            spot_filters=filters,
            perp_filters=filters,
            balances={"USDT": Decimal("1000000"), "BTC": Decimal("1000000")},
            position_mode=D.POS_MODE_BOTH,
            est_price=Decimal("100"),
        )


class _CloseLiveExecutor:
    """live-mode fake：两腿 FILLED（或可编程单腿）；可编程持仓/余额；记录全部
    资金动作计数。绝不联网。"""

    def __init__(self, *, um_qty=-1, spot_free=1, unified_free=10,
                 dispatch_outcome="balanced", query_leg_result=None):
        self.um_qty = um_qty                  # query_symbol_um_qty 返回值
        self.spot_free = spot_free
        self.unified_free = unified_free
        self.dispatch_outcome = dispatch_outcome
        self.query_leg_result = query_leg_result
        self.dispatch_calls = 0
        self.dispatch_ctxs = []
        self.um_calls = 0                     # 备料门 + 收尾核实（按调用点分段）
        self.spot_free_calls = 0
        self.unified_calls = 0
        self.transfers = []                   # (source, asset, amount)
        self.set_leverage_calls = 0
        self.query_leg_calls = 0
        self.on_dispatch_enter = None   # 测试钩子：dispatch 进入时回调

    def set_leverage(self, coin, leverage):
        self.set_leverage_calls += 1

    def dispatch(self, ctx):
        if self.on_dispatch_enter is not None and self.dispatch_calls == 0:
            self.on_dispatch_enter()
        self.dispatch_calls += 1
        self.dispatch_ctxs.append(ctx)
        qty = str(ctx.q_common)
        quote = str(Decimal(qty) * Decimal("100"))

        def leg(name, order_id, filled):
            if filled:
                return LegDispatch(
                    leg=name, dispatch_state=LEG_ACCEPTED, order_id=order_id,
                    exchange_status=D.LEG_FILLED, executed_qty=qty,
                    cumulative_quote=quote, avg_price="100",
                    raw_response={"orderId": order_id},
                )
            return LegDispatch(
                leg=name, dispatch_state=LEG_REJECTED, order_id=None,
                exchange_status=D.LEG_REJECTED, executed_qty="0",
                cumulative_quote="0", avg_price=None,
                raw_response={"code": -2010},
            )

        spot_filled = self.dispatch_outcome not in ("perp_only", "both_failed")
        perp_filled = self.dispatch_outcome not in ("spot_only", "both_failed")
        return LiveAttemptDispatch(
            attempt_id=ctx.attempt_id,
            spot=leg("spot", "s1", spot_filled),
            perp=leg("perp", "p1", perp_filled),
            record_payload={"transport": "test"},
            rate_limited=False,
            retry_after_seconds=None,
        )

    def query_symbol_um_qty(self, coin):
        self.um_calls += 1
        return self.um_qty

    def query_spot_free(self, asset):
        self.spot_free_calls += 1
        return self.spot_free

    def query_unified_free(self, asset):
        self.unified_calls += 1
        return self.unified_free

    def universal_transfer(self, source, asset, amount):
        self.transfers.append((source, asset, amount))
        return 123

    def query_leg(self, leg, symbol, client_order_id, endpoint):
        self.query_leg_calls += 1
        return self.query_leg_result


def _wait(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.005)
    raise AssertionError("condition not reached")


def _seed_cycle(svc, coin="BTCUSDT", direction="forward"):
    """为 close 建卡造活跃周期：手动 prepare 一个 open attempt（周期在
    prepare 事务内创建）。不启动任何 worker / 执行器调用。"""
    store = svc.store
    seed_id = f"seed-{uuid.uuid4().hex[:12]}"
    store.create_task(
        seed_id, coin, direction, D.MODE_IMMEDIATE, "1", 1, "1",
        D.POS_MODE_BOTH, {"est_price": "100"}, 1_000,
        initial_status=D.STATUS_RUNNING,
    )
    store.prepare_attempt(
        seed_id, f"att-{uuid.uuid4().hex[:8]}", direction, "1", D.POS_MODE_BOTH,
        {"est_price": "100"}, f"s-{seed_id}", {"side": "BUY"}, D.SPOT_ORDER_PATH,
        f"p-{seed_id}", {"side": "SELL"}, 1_001,
    )
    return seed_id


def _close_service(tmp_path, *, clock=None, market=None, executor=None,
                   preflight=None, name="smooth-close.sqlite3", with_market=True):
    clock = clock or _Clock()
    if market is None and with_market:
        market = _Market()
    executor = executor or _CloseLiveExecutor()
    preflight = preflight or _ClosePreflight()
    svc = HedgeOpenTaskService(
        str(tmp_path / name),
        executor=executor,
        preflight_provider=preflight,
        mode="live",
        credentials_present=True,
        mono_us=clock.mono_us,
        wall_us=clock.wall_us,
        market_provider=market,
    )
    _seed_cycle(svc)
    return svc, clock, market, executor, preflight


def _create_close(svc, *, threshold="0.05", amount="1", target=1,
                  direction="forward", mode=D.MODE_SMOOTH):
    body = {
        "coin": "BTCUSDT", "direction": direction, "mode": mode,
        "single_amount": amount, "target_n": target,
        "task_type": D.TASK_TYPE_CLOSE,
    }
    if mode == D.MODE_SMOOTH:
        body["slippage_threshold_pct"] = threshold
    _, doc = svc.create_task(body)
    return doc


def _arm(svc):
    svc.set_start_gate(True)


def _publish_close_bad(market):
    """对 close forward（评估方向=reverse）不放行的行情。

    spot.bid=99.99 / perp.ask=100.01 → reverse 公式 ≈ −0.02%；
    同时 perp.bid=100.10 / spot.ask=99.99 → **未翻转**的 forward 公式
    ≈ +0.11% 会放行——一个未翻方向的任务会在本行情下错误成交。"""
    market.publish(SPOT, bid="99.99", bid_qty="2", ask="99.99", ask_qty="1")
    market.publish(SWAP, bid="100.10", bid_qty="1", ask="100.01", ask_qty="1")


def _publish_close_good(market):
    """对 close forward（评估方向=reverse）放行的行情：spot.bid=100.10 /
    perp.ask=100 → reverse 公式 +0.10% > 0.05%，两腿一档 qty=1 全覆盖。"""
    market.publish(SPOT, bid="100.10", bid_qty="1", ask="100.10", ask_qty="1")
    market.publish(SWAP, bid="100", bid_qty="1", ask="100", ask_qty="1")


def _worker_alive(svc, task_id):
    worker = svc._workers.get(task_id)
    return worker is not None and worker.is_alive()


# ---------------------------------------------------------------------------
# 验收 11（建卡）+ 4（阈值）+ 22（备料状态派生字段）
# ---------------------------------------------------------------------------
def test_create_smooth_close_threshold_and_failure_threshold(tmp_path):
    svc, _, _, _, _ = _close_service(tmp_path)
    try:
        doc = _create_close(svc)
        assert doc["status"] == D.STATUS_PAUSED
        assert doc["pause_reason"] == D.PAUSE_REASON_AWAITING_MANUAL_START
        assert doc["slippage_threshold_pct"] == "0.05"      # 验收 4：落库固化
        assert doc["failure_pause_threshold"] == 1          # 验收 11：仅 smooth close
        assert doc["q_common"] is None                      # 轻量建卡零联网零冻结
        assert doc["close_preparation_state"] == "unprepared"  # 验收 22

        imm = _create_close(svc, mode=D.MODE_IMMEDIATE, threshold="0.05")
        assert imm["failure_pause_threshold"] == 3          # immediate close 默认 3
        assert imm["slippage_threshold_pct"] is None        # 非 smooth 不收阈值
        assert imm["close_preparation_state"] == "realtime_per_round"
    finally:
        svc.close()


def test_create_smooth_close_open_threshold_unchanged(tmp_path):
    svc, _, _, _, _ = _close_service(tmp_path)
    try:
        _, doc = svc.create_task({
            "coin": "BTCUSDT", "direction": D.DIR_FORWARD, "mode": D.MODE_SMOOTH,
            "single_amount": "1", "target_n": 1,
            "slippage_threshold_pct": "0.05",
        })
        assert doc["task_type"] == D.TASK_TYPE_OPEN
        assert doc["failure_pause_threshold"] == 3          # 零回归：open 仍 3
        assert doc["close_preparation_state"] is None       # 验收 22：open 无概念
    finally:
        svc.close()


@pytest.mark.parametrize("raw,expected", [
    ("-0.5", "-0.50"), ("0", "0.00"), ("9" * 30, "9" * 30 + ".00"),
])
def test_create_smooth_close_accepts_valid_thresholds(tmp_path, raw, expected):
    svc, _, _, _, _ = _close_service(tmp_path)
    try:
        doc = _create_close(svc, threshold=raw)
        assert doc["slippage_threshold_pct"] == expected
    finally:
        svc.close()


@pytest.mark.parametrize("raw", ["0.055", "1e-2", "5%", "", None, 1])
def test_create_smooth_close_rejects_bad_thresholds(tmp_path, raw):
    svc, _, _, _, _ = _close_service(tmp_path)
    try:
        with pytest.raises(D.HedgeError) as exc:
            _create_close(svc, threshold=raw)
        assert exc.value.status == 400
        assert exc.value.code == "invalid_field"
    finally:
        svc.close()


def test_smooth_close_requires_market_provider(tmp_path):
    svc, _, _, _, _ = _close_service(
        tmp_path, market=None, with_market=False, name="nomarket.sqlite3",
    )
    try:
        with pytest.raises(D.HedgeError) as exc:
            _create_close(svc)
        assert (exc.value.status, exc.value.code) == (400, "smooth_market_unavailable")
    finally:
        svc.close()


# ---------------------------------------------------------------------------
# 验收 7：同步备料与状态翻转（C5/C13/C14）
# ---------------------------------------------------------------------------
def test_post_start_runs_three_gates_then_conditional_write(tmp_path):
    """forward close 备料在 HTTP 请求内同步完成三道门；q_common 写入发生在
    划转成功之后；成功后 running + worker。"""
    transfers_seen = []
    svc, clock, market, executor, preflight = _close_service(
        tmp_path, executor=_CloseLiveExecutor(spot_free=0, unified_free=10),
    )
    try:
        doc = _create_close(svc, amount="1", target=1)
        _arm(svc)
        orig_arm = svc.store.arm_prepared_close_task

        def arm_after_transfer(*args, **kwargs):
            # C14 末步写入：arm 被调用时划转必须已发生。
            assert executor.transfers, "q_common 写入必须发生在划转成功之后"
            transfers_seen.extend(executor.transfers)
            return orig_arm(*args, **kwargs)

        svc.store.arm_prepared_close_task = arm_after_transfer
        status, started = svc.post_start(doc["id"])
        assert status == 200
        assert started["status"] == D.STATUS_RUNNING
        assert Decimal(started["q_common"]) == Decimal(1)
        assert started["close_preparation_state"] == "prepared"
        # 三道门调用点顺序：fresh preflight → 合约可平量 → 现货余额（划转）。
        assert len(preflight.calls) >= 1
        assert executor.um_calls == 1
        assert executor.transfers == [
            ("PORTFOLIO_MARGIN_MAIN", "BTC", "1"),
        ] and transfers_seen == executor.transfers
        assert _worker_alive(svc, doc["id"]) or svc._workers.get(doc["id"]) is not None
        # 验收 15（前半）：备料段合约可平量查询恰好一次。
    finally:
        svc.close()


def test_post_start_failure_pauses_with_chinese_reason_no_worker(tmp_path):
    svc, clock, market, executor, _ = _close_service(
        tmp_path, executor=_CloseLiveExecutor(um_qty=0),
    )
    try:
        doc = _create_close(svc)
        _arm(svc)
        ensure_calls = []
        orig_ensure = svc.ensure_worker

        def ensure_spy(*args, **kwargs):
            ensure_calls.append(args)
            return orig_ensure(*args, **kwargs)

        svc.ensure_worker = ensure_spy
        with pytest.raises(D.HedgeError) as exc:
            svc.post_start(doc["id"])
        assert exc.value.status == 409
        assert "正向平仓需要空头持仓" in exc.value.detail
        row = svc.store.get_task(doc["id"])
        assert row["status"] == D.STATUS_PAUSED
        assert row["pause_reason"] == D.PAUSE_REASON_CLOSE_UM_POSITION
        assert ensure_calls == []                       # 不启 worker
        assert doc["id"] not in svc._smooth_subscriptions   # 零订阅
        assert svc.store.list_attempts_for_task(doc["id"]) == []  # 零 attempt
        assert executor.dispatch_calls == 0
    finally:
        svc.close()


# ---------------------------------------------------------------------------
# Review-1 F1：预检不完整的启动原因落库与回显
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("failed_read", ["spot_filters", None])
def test_post_start_preflight_incomplete_pauses_with_exact_reason(tmp_path, failed_read):
    """Review-1 F1：`get_snapshot` 读失败时，post_start 必须把确切中文暂停
    原因写入数据库（`preflight_incomplete`，含首个失败读取名）并在 409
    detail 返回——不得回显建卡旧文案 `awaiting_manual_start`。"""
    preflight = _ClosePreflight(snapshot_result=None)
    preflight.last_failed_read = failed_read
    svc, clock, market, executor, _ = _close_service(
        tmp_path, preflight=preflight, name=f"f1-{failed_read}.sqlite3",
    )
    try:
        doc = _create_close(svc)
        _arm(svc)
        ensure_calls = []
        orig_ensure = svc.ensure_worker

        def ensure_spy(*args, **kwargs):
            ensure_calls.append(args)
            return orig_ensure(*args, **kwargs)

        svc.ensure_worker = ensure_spy
        with pytest.raises(D.HedgeError) as exc:
            svc.post_start(doc["id"])
        assert exc.value.status == 409
        assert exc.value.code == "smooth_close_start_failed"
        assert "预检数据不完整" in exc.value.detail
        assert "未发单" in exc.value.detail
        assert "任务首次执行必须点击启动" not in exc.value.detail
        if failed_read is not None:
            assert failed_read in exc.value.detail
        row = svc.store.get_task(doc["id"])
        assert row["status"] == D.STATUS_PAUSED
        assert row["pause_reason"] == D.PAUSE_REASON_PREFLIGHT_INCOMPLETE
        assert "预检数据不完整" in row["pause_reason_zh"]
        assert row["q_common"] is None
        assert ensure_calls == []
        assert doc["id"] not in svc._smooth_subscriptions
        assert svc.store.list_attempts_for_task(doc["id"]) == []
        assert executor.dispatch_calls == 0
        assert executor.um_calls == 0
        assert executor.transfers == []
    finally:
        svc.close()


# ---------------------------------------------------------------------------
# 验收 7a：闸门前置（C5）——零预检/零查仓/零划转
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("gate", ["start", "close"])
def test_post_start_rejected_when_either_gate_closed(tmp_path, gate):
    svc, clock, market, executor, preflight = _close_service(tmp_path)
    try:
        doc = _create_close(svc)
        _arm(svc)
        if gate == "start":
            svc.set_start_gate(False)
        else:
            version = svc.get_settings()[1]["version"]
            svc.put_close_gate({"enabled": False, "confirm": True, "version": version})
        with pytest.raises(D.HedgeError) as exc:
            svc.post_start(doc["id"])
        assert exc.value.status == 409
        assert exc.value.detail  # 中文原因
        row = svc.store.get_task(doc["id"])
        assert row["status"] == D.STATUS_PAUSED
        assert row["q_common"] is None
        # 零预检 / 零查仓 / 零划转（get_snapshot / um / transfer 计数全 0）。
        assert preflight.calls == []
        assert executor.um_calls == 0
        assert executor.spot_free_calls == 0
        assert executor.unified_calls == 0
        assert executor.transfers == []
    finally:
        svc.close()


# ---------------------------------------------------------------------------
# 验收 7b：条件写不复活（C14）
# ---------------------------------------------------------------------------
def test_conditional_write_does_not_revive_deleted_task(tmp_path):
    svc, clock, market, executor, _ = _close_service(tmp_path)
    try:
        doc = _create_close(svc)
        _arm(svc)
        orig_arm = svc.store.arm_prepared_close_task
        ensure_calls = []
        orig_ensure = svc.ensure_worker

        def ensure_spy(*args, **kwargs):
            ensure_calls.append(args)
            return orig_ensure(*args, **kwargs)

        svc.ensure_worker = ensure_spy

        def delete_then_arm(*args, **kwargs):
            # 在"备料已完成、条件写尚未执行"处注入一次 post_delete。
            svc.post_delete(doc["id"])
            return orig_arm(*args, **kwargs)

        svc.store.arm_prepared_close_task = delete_then_arm
        with pytest.raises(D.HedgeError) as exc:
            svc.post_start(doc["id"])
        assert exc.value.status == 409
        row = svc.store.get_task(doc["id"])
        assert row["status"] == D.STATUS_DELETED       # 终态 deleted，不复活
        assert row["q_common"] is None                 # q_common 未写入
        assert row["status"] != D.STATUS_RUNNING
        assert ensure_calls == []                      # ensure_worker 调用 0
        assert svc.store.list_attempts_for_task(doc["id"]) == []
        assert executor.dispatch_calls == 0
    finally:
        svc.close()


# ---------------------------------------------------------------------------
# 验收 8：崩溃自愈（C14）——划转已发出、q_common 未写入
# ---------------------------------------------------------------------------
def test_crash_between_transfer_and_write_reruns_preparation_without_second_transfer(
    tmp_path,
):
    executor = _CloseLiveExecutor(spot_free=0, unified_free=10)
    svc, clock, market, executor, _ = _close_service(tmp_path, executor=executor)
    try:
        doc = _create_close(svc)
        _arm(svc)
        orig_arm = svc.store.arm_prepared_close_task

        def arm_crash(*args, **kwargs):
            # 模拟"划转已发出、q_common 尚未写入"处崩溃：条件写不执行。
            return None

        svc.store.arm_prepared_close_task = arm_crash
        with pytest.raises(D.HedgeError):
            svc.post_start(doc["id"])
        row = svc.store.get_task(doc["id"])
        assert row["status"] == D.STATUS_PAUSED      # 不是 running
        assert row["q_common"] is None               # 仍为空
        assert executor.transfers == [("PORTFOLIO_MARGIN_MAIN", "BTC", "1")]

        # "重启"（同进程同库）后再次启动重跑备料；余额已足（划转到账）
        # → 不发生第二次划转。
        svc.store.arm_prepared_close_task = orig_arm
        executor.spot_free = 1
        status, started = svc.post_start(doc["id"])
        assert started["status"] == D.STATUS_RUNNING
        assert Decimal(started["q_common"]) == Decimal(1)
        assert executor.transfers == [("PORTFOLIO_MARGIN_MAIN", "BTC", "1")]  # 仅一次
        assert executor.spot_free_calls == 2              # 两次备料各实时确认一次
    finally:
        svc.close()


# ---------------------------------------------------------------------------
# 验收 9：跳过备料（C4）
# ---------------------------------------------------------------------------
def test_post_start_with_q_common_skips_preparation(tmp_path):
    svc, clock, market, executor, preflight = _close_service(tmp_path)
    try:
        doc = _create_close(svc)
        _arm(svc)
        _, started = svc.post_start(doc["id"])
        assert started["status"] == D.STATUS_RUNNING
        svc.post_pause(doc["id"])
        baseline = (len(preflight.calls), executor.um_calls,
                    executor.spot_free_calls, len(executor.transfers))
        _, resumed = svc.post_start(doc["id"])
        assert resumed["status"] == D.STATUS_RUNNING
        assert Decimal(resumed["q_common"]) == Decimal(1)
        assert (len(preflight.calls), executor.um_calls,
                executor.spot_free_calls, len(executor.transfers)) == baseline
    finally:
        svc.close()


# ---------------------------------------------------------------------------
# 验收 10 / 10a：无数量不放行（C15）+ gate 对 close 解禁（C10）
# ---------------------------------------------------------------------------
def test_running_close_without_q_common_fails_closed_without_busy_loop(tmp_path):
    """q_common 为空且 running 的 smooth close：fail-closed 落 paused +
    preflight_incomplete；零 attempt / 零 executor；且 _worker_round 轮次
    有上限（不得忙循环）。fill-once 也被数量谓词拒绝。"""
    svc, clock, market, executor, _ = _close_service(tmp_path)
    try:
        svc.store.create_task(
            "c15", "BTCUSDT", D.DIR_FORWARD, D.MODE_SMOOTH, "1", 1, None,
            D.POS_MODE_BOTH, {"available": False}, clock.t,
            task_type=D.TASK_TYPE_CLOSE,
            initial_status=D.STATUS_RUNNING,
            slippage_threshold_pct="0.05",
        )
        _arm(svc)
        rounds = svc._pump_worker("c15", max_rounds=50)
        assert rounds < 50                          # 有上限：暂停后下一轮即退出
        row = svc.store.get_task("c15")
        assert row["status"] == D.STATUS_PAUSED
        assert row["pause_reason"] == D.PAUSE_REASON_PREFLIGHT_INCOMPLETE
        assert row["pause_reason_zh"] is not None
        assert svc.store.list_attempts_for_task("c15") == []
        assert executor.dispatch_calls == 0
        # 即使注入「成交1次」也不放行（store 数量谓词）。
        with pytest.raises(D.HedgeError) as exc:
            svc.post_fill_once("c15", {"gate_seq": 1})
        assert exc.value.status == 409
        assert svc.store.list_attempts_for_task("c15") == []
    finally:
        svc.close()


def test_gate_store_methods_accept_close_with_q_common_and_reject_empty(tmp_path):
    """验收 10a（store 级）：open/force 对 close+smooth+running+q_common 有效
    能建门；q_common 为空仍拒绝。open-only 未解禁的实现在本项变红。"""
    from backend.hedge_open_tasks.store import HedgeOpenStore
    store = HedgeOpenStore(str(tmp_path / "gate.sqlite3"))
    store.create_task(
        "qc", "BTCUSDT", D.DIR_FORWARD, D.MODE_SMOOTH, "1", 1, "1",
        D.POS_MODE_BOTH, {}, 1_000, task_type=D.TASK_TYPE_CLOSE,
        initial_status=D.STATUS_RUNNING,
        slippage_threshold_pct="0.05",
    )
    store.create_task(
        "noqc", "BTCUSDT", D.DIR_FORWARD, D.MODE_SMOOTH, "1", 1, None,
        D.POS_MODE_BOTH, {}, 1_000, task_type=D.TASK_TYPE_CLOSE,
        initial_status=D.STATUS_RUNNING,
        slippage_threshold_pct="0.05",
    )
    assert store.get_task("qc")["status"] == D.STATUS_RUNNING  # 显式 running（2026-08-18 起默认 paused）
    assert store.open_smooth_gate("qc", 1, 10_000) is not None
    assert store.force_smooth_gate("qc", 1, 10_001) is not None
    assert store.open_smooth_gate("noqc", 1, 10_000) is None
    assert store.force_smooth_gate("noqc", 1, 10_000) is None
    store.close()


def test_close_gate_actually_opens_and_dispatches(tmp_path):
    """验收 10a（worker 级）：备料成功的 smooth close 能建门、能放行、能成交
    ——"能启动、能订阅、但每轮建门失败、零成交"的实现（忘了解禁）在本项变红。"""
    svc, clock, market, executor, _ = _close_service(tmp_path)
    try:
        doc = _create_close(svc)
        _arm(svc)
        _, started = svc.post_start(doc["id"])
        assert started["status"] == D.STATUS_RUNNING
        _publish_close_bad(market)
        gate = _wait(
            lambda: (
                row if (row := svc.store.get_task(doc["id"]))
                and row["smooth_gate_seq"] is not None else None
            )
        )
        assert gate["smooth_gate_seq"] == 1            # gate 真的建起来了
        executor.um_qty = 0                            # 备料后无仓（verify flat 用）
        _publish_close_good(market)
        _wait(lambda: executor.dispatch_calls == 1)
        assert svc.store.list_attempts_for_task(doc["id"]) != []
    finally:
        svc.close()


# ---------------------------------------------------------------------------
# 验收 1 / 2 / 6：方向翻转（判定侧、覆盖面、覆盖率分母）
# ---------------------------------------------------------------------------
def test_direction_flip_forward_close_waits_on_reverse_operands(tmp_path):
    """验收 1：forward close 只按 spot.bid + perp.ask 评估。bad 行情（未翻
    方向会误判放行）下不成交；good 行情下成交——"只翻预检不翻 gate"的实现
    在本项变红。"""
    svc, clock, market, executor, _ = _close_service(tmp_path)
    try:
        doc = _create_close(svc)
        _arm(svc)
        svc.post_start(doc["id"])
        _publish_close_bad(market)          # 未翻方向的 forward 公式 ≈ +0.11%
        time.sleep(0.15)
        assert executor.dispatch_calls == 0
        assert svc.store.list_attempts_for_task(doc["id"]) == []
        gate = _wait(
            lambda: (
                row if (row := svc.store.get_task(doc["id"]))
                and row["smooth_gate_seq"] is not None else None
            )
        )
        assert gate["smooth_gate_seq"] == 1
        executor.um_qty = 0
        _publish_close_good(market)
        _wait(lambda: executor.dispatch_calls == 1)
    finally:
        svc.close()


def test_direction_flip_reverse_close_uses_forward_operands(tmp_path):
    """验收 1：reverse close 只按 perp.bid + spot.ask 评估。"""
    executor = _CloseLiveExecutor(um_qty=1)  # reverse close 需要多头持仓
    svc, _, market, executor, _ = _close_service(
        tmp_path, executor=executor, name="reverse.sqlite3",
    )
    try:
        seed_id = _seed_cycle(svc, direction="reverse")
        assert seed_id
        doc = _create_close(svc, direction="reverse")
        _arm(svc)
        svc.post_start(doc["id"])
        # reverse close 评估方向 = forward：perp.bid=99.99 / spot.ask=100.01 → 负。
        market.publish(SPOT, bid="99.9", bid_qty="1", ask="100.01", ask_qty="1")
        market.publish(SWAP, bid="99.99", bid_qty="1", ask="100.1", ask_qty="1")
        time.sleep(0.15)
        assert executor.dispatch_calls == 0
        # perp.bid=100.10 / spot.ask=100 → (100.10-100)/100 = +0.10% 放行。
        market.publish(SPOT, bid="99.9", bid_qty="1", ask="100", ask_qty="1")
        market.publish(SWAP, bid="100.10", bid_qty="1", ask="100.2", ask_qty="1")
        _wait(lambda: executor.dispatch_calls == 1)
    finally:
        svc.close()


def test_direction_flip_covers_read_model_and_audit_and_preflight(tmp_path):
    """验收 2：§4.2 第 2/4/5 项——读模型"当前方向"取翻转后的 reverse 组、
    审计记录 eval_direction、预检方向为翻转方向（既有行为）。"只翻 gate 不翻
    读模型"的实现在本项变红。"""
    svc, clock, market, executor, preflight = _close_service(tmp_path)
    try:
        doc = _create_close(svc)
        _arm(svc)
        svc.post_start(doc["id"])
        _publish_close_bad(market)
        _wait(
            lambda: (
                row if (row := svc.store.get_task(doc["id"]))
                and row["smooth_gate_seq"] is not None else None
            )
        )
        page = svc.get_logs(None, None, task_id=doc["id"])[1]
        market_doc = page["smooth_market"]
        # 当前方向 = reverse 组（spot.bid + perp.ask）：bad 行情下不放行。
        assert market_doc["gate_pass"] is False
        # spot.bid_qty=2（reverse 组的 spot 覆盖率分子）；forward 组的分子是
        # ask_qty=1——覆盖率取 200% 锁死"当前方向"是 reverse 组。
        assert market_doc["spot_coverage_pct"] == "200.00"
        assert market_doc["perp_coverage_pct"] == "100.00"
        # 验收 3（顺带）：等待原因不出现"开单率"，出现"平仓率"。
        assert "开单率" not in market_doc["wait_reason"]
        assert "平仓率" in market_doc["wait_reason"]
        # §4.2-5：备料预检方向 = 翻转方向（forward close → reverse）。
        close_calls = [c for c in preflight.calls if c[2] == D.TASK_TYPE_CLOSE]
        assert close_calls and all(c[1] == D.DIR_REVERSE for c in close_calls)

        executor.um_qty = 0
        _publish_close_good(market)
        _wait(lambda: executor.dispatch_calls == 1)
        audits = svc.get_logs(None, None, task_id=doc["id"])[1][
            "smooth_dispatch_audits"
        ]
        assert len(audits) == 1
        payload = audits[0]["payload"]
        # §4.2-4（验收 21）：审计显式记录实际参与评估的方向。
        assert payload["direction"] == D.DIR_FORWARD
        assert payload["eval_direction"] == D.DIR_REVERSE
        assert payload["reason"] == D.PASS_REASON_MARKET
        # 快照来自产生放行结论的同一次读取（good 行情本身）。
        assert payload["spot"]["bid"] == "100.10"
        assert payload["perp"]["ask"] == "100"
    finally:
        svc.close()


def test_coverage_denominator_is_q_common_not_single_amount(tmp_path):
    """验收 6：覆盖率分母 = 备料冻结的 q_common（floor 后 1.0，非输入 1.2）；
    实际发送量是 100% 的 q_common。"""
    preflight = _ClosePreflight(step="0.5")
    executor = _CloseLiveExecutor(um_qty=-2)
    svc, clock, market, executor, _ = _close_service(
        tmp_path, executor=executor, preflight=preflight,
        name="coverage.sqlite3",
    )
    try:
        doc = _create_close(svc, amount="1.2", target=2)
        _arm(svc)
        _, started = svc.post_start(doc["id"])
        assert Decimal(started["q_common"]) == Decimal("1.0")
        # qty=0.9：0.9/1.0=90% ≥ 80% 通过；若实现误用 single_amount 1.2 作分母
        # → 0.9/1.2=75% 不通过 → 本测试在错误实现下变红（等待超时）。
        # target=2 时两轮可连续放行，故断言 >= 1（放行发生即可）而非精确 1。
        market.publish(SPOT, bid="100.10", bid_qty="0.9", ask="100.10", ask_qty="0.9")
        market.publish(SWAP, bid="100", bid_qty="0.9", ask="100", ask_qty="0.9")
        _wait(lambda: executor.dispatch_calls >= 1)
        ctx = executor.dispatch_ctxs[0]
        assert Decimal(ctx.q_common) == Decimal("1.0")   # 实际发送量 100% q_common
        attempt = svc.store.list_attempts_for_task(doc["id"])[0]
        assert Decimal(attempt["q_common"]) == Decimal("1.0")
    finally:
        svc.close()


def test_invalid_operand_makes_close_market_unavailable_no_market_pass(tmp_path):
    """验收 1（操作数非法）：现货盘口断流 → 该任务盘口 unavailable，不得按
    市场条件放行（fail-closed 等待，不 timeout 抢跑）。"""
    svc, clock, market, executor, _ = _close_service(tmp_path)
    try:
        doc = _create_close(svc)
        _arm(svc)
        svc.post_start(doc["id"])
        market.publish(SWAP, bid="100", bid_qty="1", ask="100", ask_qty="1")
        time.sleep(0.1)
        page = svc.get_logs(None, None, task_id=doc["id"])[1]
        assert page["smooth_market"]["gate_pass"] is False
        assert executor.dispatch_calls == 0
    finally:
        svc.close()


# ---------------------------------------------------------------------------
# 验收 12：5 分钟窗口（close 版）
# ---------------------------------------------------------------------------
def test_close_gate_window_is_five_minutes_with_fake_clock(tmp_path):
    clock = _Clock(50_000_000)
    svc, clock, market, executor, _ = _close_service(tmp_path, clock=clock)
    try:
        doc = _create_close(svc)
        _arm(svc)
        svc.post_start(doc["id"])
        _publish_close_bad(market)
        gate = _wait(
            lambda: (
                row if (row := svc.store.get_task(doc["id"]))
                and row["smooth_gate_seq"] is not None else None
            )
        )
        # 4:59 不超时。
        clock.t = gate["smooth_gate_started_at_us"] + D.SMOOTH_GATE_WINDOW_US - 1_000_000
        svc._notify_smooth_task(doc["id"])
        time.sleep(0.1)
        assert executor.dispatch_calls == 0
        # 5:00 超时，走既有下单链（timeout 放行）。
        executor.um_qty = 0
        clock.t += 1_000_000
        svc._notify_smooth_task(doc["id"])
        _wait(lambda: executor.dispatch_calls == 1)
        attempt = svc.store.list_attempts_for_task(doc["id"])[0]
        assert attempt["smooth_pass_reason"] == D.PASS_REASON_TIMEOUT
    finally:
        svc.close()


def test_close_gate_stale_feed_times_out_at_five_minutes(tmp_path):
    """断流（无行情）也在 5:00 走既有 timeout 下单链。"""
    clock = _Clock(60_000_000)
    svc, clock, market, executor, _ = _close_service(tmp_path, clock=clock)
    try:
        doc = _create_close(svc)
        _arm(svc)
        svc.post_start(doc["id"])
        gate = _wait(
            lambda: (
                row if (row := svc.store.get_task(doc["id"]))
                and row["smooth_gate_seq"] is not None else None
            )
        )
        executor.um_qty = 0
        clock.t = gate["smooth_gate_started_at_us"] + D.SMOOTH_GATE_WINDOW_US
        svc._notify_smooth_task(doc["id"])
        _wait(lambda: executor.dispatch_calls == 1)
        attempt = svc.store.list_attempts_for_task(doc["id"])[0]
        assert attempt["smooth_pass_reason"] == D.PASS_REASON_TIMEOUT
    finally:
        svc.close()


# ---------------------------------------------------------------------------
# 验收 13：平仓闸门（C12 五项）
# ---------------------------------------------------------------------------
def test_close_gate_off_wakes_waiter_clears_gate_and_worker_exits(tmp_path):
    """① 等待中关闸 → gate 立即唤醒、worker 退出；② 退出时 gate 清空。"""
    clock = _Clock(70_000_000)
    svc, clock, market, executor, _ = _close_service(
        tmp_path, clock=clock, executor=_CloseLiveExecutor(um_qty=-2),
    )
    try:
        doc = _create_close(svc, target=2)
        _arm(svc)
        svc.post_start(doc["id"])
        _publish_close_bad(market)
        gate = _wait(
            lambda: (
                row if (row := svc.store.get_task(doc["id"]))
                and row["smooth_gate_seq"] is not None else None
            )
        )
        assert gate["smooth_gate_seq"] == 1
        version = svc.get_settings()[1]["version"]
        svc.put_close_gate({"enabled": False, "confirm": True, "version": version})
        _wait(
            lambda: svc.store.get_task(doc["id"])["smooth_gate_seq"] is None
        )                                            # ② gate 清空
        _wait(lambda: not _worker_alive(svc, doc["id"]))   # ① worker 退出
        assert executor.dispatch_calls == 0
    finally:
        svc.close()


def test_dispatch_admission_requires_close_gate(tmp_path):
    """③ 关闸后即使放行结论已产生，`_dispatch_one_for_task` 也不发单。"""
    svc, clock, market, executor, _ = _close_service(tmp_path)
    try:
        doc = _create_close(svc)
        _arm(svc)
        _, started = svc.post_start(doc["id"])
        version = svc.get_settings()[1]["version"]
        svc.put_close_gate({"enabled": False, "confirm": True, "version": version})
        task = svc.store.get_task(doc["id"])
        _, signal = svc._dispatch_one_for_task(task, svc._wall_us())
        assert executor.dispatch_calls == 0
        assert signal is None
        assert svc.store.get_task(doc["id"])["status"] == D.STATUS_RUNNING
    finally:
        svc.close()


def test_close_gate_reopen_relaunches_worker_with_full_window(tmp_path):
    """④ 重新开闸后 running 的 smooth close worker 被重新拉起；
    ⑤ 为未调度的同一 seq 建新的完整 5 分钟窗口。"""
    clock = _Clock(80_000_000)
    svc, clock, market, executor, _ = _close_service(
        tmp_path, clock=clock, executor=_CloseLiveExecutor(um_qty=-2),
    )
    try:
        doc = _create_close(svc, target=2)
        _arm(svc)
        svc.post_start(doc["id"])
        _publish_close_bad(market)
        first = _wait(
            lambda: (
                row if (row := svc.store.get_task(doc["id"]))
                and row["smooth_gate_seq"] is not None else None
            )
        )
        version = svc.get_settings()[1]["version"]
        svc.put_close_gate({"enabled": False, "confirm": True, "version": version})
        _wait(lambda: not _worker_alive(svc, doc["id"]))
        assert svc.store.get_task(doc["id"])["smooth_gate_seq"] is None
        # ④⑤ 重新开闸（fake clock 前进，窗口起点应是新时间）。
        clock.t += 123_000_000
        version = svc.get_settings()[1]["version"]
        svc.put_close_gate({"enabled": True, "confirm": True, "version": version})
        _wait(lambda: _worker_alive(svc, doc["id"]))
        second = _wait(
            lambda: (
                row if (row := svc.store.get_task(doc["id"]))
                and row["smooth_gate_seq"] is not None else None
            )
        )
        assert second["smooth_gate_seq"] == first["smooth_gate_seq"]  # 同一 seq
        assert second["smooth_gate_started_at_us"] == clock.t        # 新完整窗口
        assert (
            second["smooth_gate_started_at_us"]
            > first["smooth_gate_started_at_us"]
        )
        assert executor.dispatch_calls == 0
    finally:
        svc.close()


# ---------------------------------------------------------------------------
# 验收 14：放行后零联网（C7）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("pass_reason", ["market", "manual", "timeout"])
def test_no_network_reads_between_pass_and_dispatch(tmp_path, pass_reason):
    executor = _CloseLiveExecutor()
    clock = _Clock(90_000_000)
    svc, clock, market, executor, preflight = _close_service(
        tmp_path, executor=executor, clock=clock,
    )
    balance_calls = []
    violations = []
    try:
        doc = _create_close(svc)
        _arm(svc)
        svc.post_start(doc["id"])
        orig_balance = svc._ensure_close_spot_balance

        def balance_spy(*args, **kwargs):
            balance_calls.append(args)
            return orig_balance(*args, **kwargs)

        svc._ensure_close_spot_balance = balance_spy
        _publish_close_bad(market)
        gate = _wait(
            lambda: (
                row if (row := svc.store.get_task(doc["id"]))
                and row["smooth_gate_seq"] is not None else None
            )
        )
        executor.um_qty = 0

        def counts():
            return {
                "snapshot": len(preflight.calls),
                "um": executor.um_calls,
                "spot_free": executor.spot_free_calls,
                "unified": executor.unified_calls,
                "transfers": len(executor.transfers),
                "leverage": executor.set_leverage_calls,
                "balance_gate": len(balance_calls),
            }

        # C7 断言窗口 = 放行结论产生到两腿提交之间：在 dispatch 进入的瞬间
        # 对比放行前 baseline（此刻收尾核实/回流尚未发生，不产生窗口外噪声）。
        baseline = counts()

        def check_at_dispatch_enter():
            snapshot = counts()
            if snapshot != baseline:
                violations.append((snapshot, baseline))

        executor.on_dispatch_enter = check_at_dispatch_enter
        if pass_reason == "market":
            _publish_close_good(market)
        elif pass_reason == "manual":
            svc.post_fill_once(doc["id"], {"gate_seq": gate["smooth_gate_seq"]})
        else:
            clock.t = gate["smooth_gate_started_at_us"] + D.SMOOTH_GATE_WINDOW_US
            svc._notify_smooth_task(doc["id"])
        _wait(lambda: executor.dispatch_calls == 1)
        assert violations == []   # 放行到两腿提交之间零联网、零 sleep 路径
        attempt = svc.store.list_attempts_for_task(doc["id"])[0]
        assert attempt["smooth_pass_reason"] == pass_reason
    finally:
        svc.close()


# ---------------------------------------------------------------------------
# 验收 15：持仓查询按调用点分段
# ---------------------------------------------------------------------------
def test_um_position_query_segmented_by_call_site(tmp_path):
    """备料段最多一次；次数用完后的 `_verify_close_flat` 是独立且必须保留的
    一次实时查询——按调用点区分，删掉收尾核实的实现变红。"""
    executor = _CloseLiveExecutor()
    svc, clock, market, executor, _ = _close_service(tmp_path, executor=executor)
    try:
        doc = _create_close(svc, target=1)
        _arm(svc)
        svc.post_start(doc["id"])
        assert executor.um_calls == 1                    # 备料段：恰好一次
        _publish_close_bad(market)
        _wait(
            lambda: (
                row if (row := svc.store.get_task(doc["id"]))
                and row["smooth_gate_seq"] is not None else None
            )
        )
        executor.um_qty = 0                              # 平完（verify flat 用）
        _publish_close_good(market)
        _wait(lambda: executor.dispatch_calls == 1)
        _wait(lambda: svc.store.get_task(doc["id"])["status"] == D.STATUS_DONE)
        assert executor.um_calls == 2    # 备料 1 + 收尾核实 1（分段断言）
    finally:
        svc.close()


# ---------------------------------------------------------------------------
# 验收 18：收尾不变（三分支）
# ---------------------------------------------------------------------------
def test_close_full_chain_flat_finalizes_cycle_and_logs(tmp_path):
    executor = _CloseLiveExecutor()
    svc, clock, market, executor, _ = _close_service(tmp_path, executor=executor)
    try:
        doc = _create_close(svc, target=1)
        _arm(svc)
        svc.post_start(doc["id"])
        _publish_close_bad(market)
        _wait(
            lambda: (
                row if (row := svc.store.get_task(doc["id"]))
                and row["smooth_gate_seq"] is not None else None
            )
        )
        executor.um_qty = 0
        _publish_close_good(market)
        _wait(lambda: svc.store.get_task(doc["id"])["status"] == D.STATUS_DONE)
        assert svc.store.get_active_cycle("BTCUSDT", "forward") is None  # 周期已关
        logs = svc.store.list_close_logs()
        assert len(logs) == 1 and logs[0]["close_reason"] == "auto_close"
        # forward 的 USDT 回流不变。
        assert any(t[0] == "MAIN_PORTFOLIO_MARGIN" and t[1] == "USDT"
                   for t in executor.transfers)
    finally:
        svc.close()


def test_close_partial_done_when_position_remains(tmp_path):
    executor = _CloseLiveExecutor(um_qty=-1)   # 收尾时仍有空头仓（available 1）
    svc, clock, market, executor, _ = _close_service(tmp_path, executor=executor)
    try:
        doc = _create_close(svc, target=1)
        _arm(svc)
        svc.post_start(doc["id"])
        _publish_close_good(market)
        _wait(lambda: executor.dispatch_calls == 1)
        _wait(lambda: svc.store.get_task(doc["id"])["status"] == D.STATUS_DONE)
        # open 分支：周期不关。
        assert svc.store.get_active_cycle("BTCUSDT", "forward") is not None
    finally:
        svc.close()


def test_close_verify_failed_pauses_fail_closed(tmp_path):
    executor = _CloseLiveExecutor(um_qty=-1)   # 备料时空头仓充足
    svc, clock, market, executor, _ = _close_service(tmp_path, executor=executor)
    try:
        doc = _create_close(svc, target=1)
        _arm(svc)
        svc.post_start(doc["id"])
        executor.um_qty = None                 # 收尾查仓失败
        _publish_close_good(market)
        _wait(lambda: executor.dispatch_calls == 1)
        _wait(lambda: svc.store.get_task(doc["id"])["status"] == D.STATUS_PAUSED)
        assert (
            svc.store.get_task(doc["id"])["pause_reason"]
            == D.PAUSE_REASON_CLOSE_VERIFY_FAILED
        )
    finally:
        svc.close()


# ---------------------------------------------------------------------------
# 验收 17：重启/崩溃缝
# ---------------------------------------------------------------------------
def test_stop_preserves_gate_and_recovery_never_resends(tmp_path):
    """事务前崩溃（stop）保留同一 gate；事务后崩溃（PREPARED attempt）恢复
    worker 只 query 不 resend。"""
    db = str(tmp_path / "restart.sqlite3")
    clock = _Clock(100_000_000)
    executor = _CloseLiveExecutor(um_qty=-2)
    market = _Market()
    preflight = _ClosePreflight()
    svc = HedgeOpenTaskService(
        db, executor=executor, preflight_provider=preflight, mode="live",
        credentials_present=True, mono_us=clock.mono_us, wall_us=clock.wall_us,
        market_provider=market,
    )
    _seed_cycle(svc)
    try:
        doc = _create_close(svc, target=2)
        _arm(svc)
        svc.post_start(doc["id"])
        _publish_close_bad(market)
        gate = _wait(
            lambda: (
                row if (row := svc.store.get_task(doc["id"]))
                and row["smooth_gate_seq"] is not None else None
            )
        )
        # 事务前崩溃模拟：stop 唤醒 worker 但 gate 持久保留（同 open 契约）。
        svc.stop()
        stored = svc.store.get_task(doc["id"])
        assert stored["smooth_gate_seq"] == gate["smooth_gate_seq"]
        assert stored["smooth_gate_started_at_us"] == gate["smooth_gate_started_at_us"]

        # 事务后崩溃模拟：手动 prepare 一个 attempt（PREPARED、executor 未调）。
        svc.store.force_smooth_gate(doc["id"], gate["smooth_gate_seq"], clock.t)
        prepared = svc.store.prepare_attempt(
            doc["id"], f"att-{uuid.uuid4().hex[:8]}", D.DIR_FORWARD, "1",
            D.POS_MODE_BOTH, {"est_price": "100"}, "cs1", {"side": "SELL"},
            D.SPOT_ORDER_PATH, "cp1", {"side": "BUY"}, clock.t,
            expected_gate_seq=gate["smooth_gate_seq"],
            smooth_pass_reason=D.PASS_REASON_MANUAL,
        )
        assert prepared is not None
        dispatch_before = executor.dispatch_calls
        # 恢复（同库）后 worker 只 query 不 resend。stop() 置位的 stop event
        # 需先清除（P2-1：pump 不动现有 event，这里显式恢复）。
        svc._stop_events[doc["id"]].clear()
        rounds = svc._pump_worker(doc["id"], max_rounds=4)
        assert executor.dispatch_calls == dispatch_before     # 绝不 resend
        assert executor.query_leg_calls >= 1                  # 只 query
    finally:
        svc.close()


# ---------------------------------------------------------------------------
# 验收 19：模式隔离（零回归）
# ---------------------------------------------------------------------------
def test_immediate_close_runs_three_gates_every_round(tmp_path):
    """立即平仓：三道门仍在 `_dispatch_one_for_task` 原调用点、每轮执行。"""
    executor = _CloseLiveExecutor(um_qty=-2, spot_free=2, unified_free=10)
    svc, clock, market, executor, preflight = _close_service(
        tmp_path, executor=executor,
    )
    try:
        doc = _create_close(svc, mode=D.MODE_IMMEDIATE, target=2)
        _arm(svc)
        # 不起后台线程：post_start 只置 running（原路径本身不备料），worker 由
        # pump 确定性驱动，保证"每轮"计数不被并发 worker 污染。
        svc.ensure_worker = lambda *a, **k: True
        svc.post_start(doc["id"])       # 原路径：不触发备料（immediate close）
        assert executor.um_calls == 0   # post_start 零备料
        assert len(preflight.calls) == 0
        rounds = svc._pump_worker(doc["id"], max_rounds=8)
        assert executor.dispatch_calls == 2             # 两轮各发一对
        close_snapshots = [c for c in preflight.calls if c[2] == D.TASK_TYPE_CLOSE]
        assert len(close_snapshots) == 2                # 每轮一次 fresh preflight
        assert all(c[1] == D.DIR_REVERSE for c in close_snapshots)  # 翻转方向预检
        assert executor.um_calls == 3                   # 每轮一道门 + 收尾一次
        assert executor.transfers == []                 # spot_free 足额零划转
    finally:
        svc.close()


def test_immediate_close_failure_pause_threshold_still_three(tmp_path):
    """immediate close 单腿后 consecutive=1 < 3 不暂停（零回归对照）。"""
    executor = _CloseLiveExecutor(
        um_qty=-2, spot_free=2, dispatch_outcome="spot_only",
    )
    svc, clock, market, executor, _ = _close_service(tmp_path, executor=executor)
    try:
        doc = _create_close(svc, mode=D.MODE_IMMEDIATE, target=1)
        _arm(svc)
        svc.ensure_worker = lambda *a, **k: True
        svc.post_start(doc["id"])
        svc._pump_worker(doc["id"], max_rounds=6)
        row = svc.store.get_task(doc["id"])
        assert row["leg_exposure"] is not None          # 单腿敞口已记录
        assert row["status"] != D.STATUS_PAUSED         # 阈值 3：一次单腿不暂停
        assert row["consecutive_submission_failures"] == 1
    finally:
        svc.close()


def test_smooth_close_single_leg_brakes_at_threshold_one(tmp_path):
    """验收 11：smooth close 一次单腿成交即暂停并记录敞口。"""
    executor = _CloseLiveExecutor(
        um_qty=-2, spot_free=2, dispatch_outcome="spot_only",
    )
    svc, clock, market, executor, _ = _close_service(tmp_path, executor=executor)
    try:
        doc = _create_close(svc, target=2)
        _arm(svc)
        svc.post_start(doc["id"])
        _publish_close_good(market)
        _wait(lambda: executor.dispatch_calls == 1)
        _wait(lambda: svc.store.get_task(doc["id"])["status"] == D.STATUS_PAUSED)
        row = svc.store.get_task(doc["id"])
        assert row["failure_pause_threshold"] == 1
        assert row["leg_exposure"] is not None
        assert row["consecutive_submission_failures"] == 1
        assert executor.dispatch_calls == 1            # 暂停后不再发第 N+1 单
    finally:
        svc.close()


def test_smooth_close_confirmed_failure_brakes_at_threshold_one(tmp_path):
    """验收 11：smooth close 一次确认提交失败即暂停。"""
    executor = _CloseLiveExecutor(
        um_qty=-2, spot_free=2, dispatch_outcome="both_failed",
    )
    svc, clock, market, executor, _ = _close_service(tmp_path, executor=executor)
    try:
        doc = _create_close(svc, target=2)
        _arm(svc)
        svc.post_start(doc["id"])
        _publish_close_good(market)
        _wait(lambda: executor.dispatch_calls == 1)
        _wait(lambda: svc.store.get_task(doc["id"])["status"] == D.STATUS_PAUSED)
        row = svc.store.get_task(doc["id"])
        assert (
            row["pause_reason"]
            == D.PAUSE_REASON_CONSECUTIVE_SUBMISSION_FAILURE
        )
    finally:
        svc.close()


# ---------------------------------------------------------------------------
# 验收 21：延迟审计（同源快照；方向已由 read-model 测试覆盖）
# ---------------------------------------------------------------------------
def test_smooth_close_audit_uses_same_gate_snapshot(tmp_path):
    executor = _CloseLiveExecutor()
    svc, clock, market, executor, _ = _close_service(tmp_path, executor=executor)
    try:
        doc = _create_close(svc)
        _arm(svc)
        svc.post_start(doc["id"])
        _publish_close_bad(market)
        _wait(
            lambda: (
                row if (row := svc.store.get_task(doc["id"]))
                and row["smooth_gate_seq"] is not None else None
            )
        )
        executor.um_qty = 0
        _publish_close_good(market)
        _wait(lambda: executor.dispatch_calls == 1)
        payload = svc.get_logs(None, None, task_id=doc["id"])[1][
            "smooth_dispatch_audits"
        ][0]["payload"]
        # 快照来自产生放行结论的同一次读取（放行时刻的 good 行情）。
        assert payload["spot"]["bid"] == "100.10"
        assert payload["perp"]["ask"] == "100"
        assert payload["eval_direction"] == D.DIR_REVERSE
        # 放行之后行情再变，审计不重读。
        market.publish(SPOT, bid="1", bid_qty="1", ask="2", ask_qty="1")
        market.publish(SWAP, bid="9", bid_qty="1", ask="10", ask_qty="1")
        time.sleep(0.05)
        payload2 = svc.get_logs(None, None, task_id=doc["id"])[1][
            "smooth_dispatch_audits"
        ][0]["payload"]
        assert payload2["spot"]["bid"] == "100.10"
    finally:
        svc.close()


# ---------------------------------------------------------------------------
# 验收 22：备料状态派生字段（纯投影）
# ---------------------------------------------------------------------------
def test_close_preparation_state_derived_field_projection():
    base = {
        "id": "t", "coin": "BTCUSDT", "direction": "forward",
        "single_amount": "1", "target_n": 1, "success_count": 0,
        "fail_count": 0, "status": "paused", "q_common": None,
        "position_side_mode": None, "leg_exposure": None,
        "scheduled_attempt_count": 0, "accepted_pair_count": 0,
        "consecutive_submission_failures": 0, "failure_pause_threshold": 3,
        "pause_reason": None, "pause_reason_zh": None, "stop_reason": None,
        "created_at_us": 1, "updated_at_us": 1,
    }

    def doc(**over):
        row = {**base, **over}
        return task_to_doc(row)

    assert doc(task_type="close", mode="smooth")["close_preparation_state"] == "unprepared"
    assert doc(task_type="close", mode="smooth", q_common="1")[
        "close_preparation_state"
    ] == "prepared"
    assert doc(task_type="close", mode="immediate")[
        "close_preparation_state"
    ] == "realtime_per_round"
    assert doc(task_type="open", mode="smooth")["close_preparation_state"] is None
    assert doc(task_type="open", mode="immediate")["close_preparation_state"] is None
