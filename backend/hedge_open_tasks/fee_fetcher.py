"""成交手续费拉取与折算公共组件（stage 2026-08-19-hedge-order-fee-cost-v1）。

回补脚本 ``scripts/backfill-leg-fees.py``（T3）与下单链两写入站点（T5）共用本
模块的「按腿拉成交 → 按币种分组 → 冻结四列」（10-design §4.1/§4.3、§7.1
断点 3：禁止脚本一套、下单链再写一套）。

纯度契约（test_hedge_purity import 扫描）：本文件位于 hedge_open_tasks 包内，
不 import 网络原语、不引用服务层适配器。真实 HTTP 由调用方注入 :class:`FeeTransport`
的四个可调用对象；离线单测注入假实现。

口径（10-design 已拍板，勿再推导）：
- D1/D11：腿上冻结四列 ``fee_bnb_qty`` / ``fee_bnb_price`` / ``fee_other_qty`` /
  ``fee_other_asset``，空 = 未知/没有，缺失不得变 0（money-zero 家族）。
- §2.2 B1a：合约（UM）无 ``orderId`` 参数——窗口按成交时刻分钟级收敛
  （startTime=dispatched_at_us，缺则 last_query_at_us−10min；endTime=
  last_query_at_us，缺则 startTime+10min），跨度 >7 天即判不全（本实现直接
  不发那次注定不可信的 GET，四列保持空）；返回条数 == limit 即截断，禁止对
  截断列表求和；未截断时本地按 ``orderId`` 过滤，滤空 = 未知不当 0。
- §4.1 分组：BNB → ``fee_bnb_qty``；恰一种其他资产且 ∈ {USDT, 该腿 base} →
  ``fee_other_*``；多种其他资产或不可折算资产 → BNB 能定则写、其余两列空、
  该腿不全。真零佣金的资产不参与分类（合计为 0 视为「没有」）。
- §4.3 冻价（回补）：``fee_bnb_price`` 取成交时刻公开 ``BNBUSDT`` 1m K 线收盘价；
  取不到数量仍写、价格空、该腿不全。T5 实时路径换注入 D4 现价，本模块不改。
- 每腿至多 1 次 GET；429/418 抛 :class:`RateLimited`（整个回补立刻停），
  其余失败按「该腿判定失败」处理（进游标失败集合，重跑不再打）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable

from . import domain as D

# 每腿成交明细查询条数上限（§4.1：截断安全阀，不是分页方案）。与服务层
# 成交明细客户端的 TRADES_LIMIT 同值；此处独立声明——本模块不得 import
# 服务层（纯度契约），且该上限是本模块分组语义的一部分。
LIMIT = 1000
# B1a 合约窗口（值域 = 腿上时间的微秒单位）：回退窗 10 分钟；跨度硬上限 7 天。
UM_FALLBACK_WINDOW_US = 10 * 60 * 1_000_000
UM_WINDOW_MAX_US = 7 * 24 * 60 * 60 * 1_000_000
# 回补节流：签名 GET ≤ 1 次/秒（§4.3）。测试注入假 sleep。
THROTTLE_SECONDS = 1.0


class RateLimited(Exception):
    """成交明细 GET 收到 429/418——IP/配额受限，整个回补必须立刻停止。"""

    def __init__(self, status: int):
        super().__init__(f"rate limited: HTTP {status}")
        self.status = status


class FeeFetchError(Exception):
    """单腿成交明细拉取失败（非限速）。该腿判定失败，不重试。"""


@dataclass(frozen=True)
class FeeTransport:
    """注入式传输层（真实 HTTP 由脚本/下单链装配，测试注入假实现）。"""

    spot_trades: Callable[[str, str, int], list]
    margin_trades: Callable[[str, str, int], list]
    um_trades: Callable[[str, int, int, int], list]
    # 回补：公开 1m K 线收盘价（start_ms）→ str|None；T5：D4 现价提供方。
    bnb_close_price: Callable[[int], "str | None"]


@dataclass(frozen=True)
class LegFeeColumns:
    """冻结到腿上的手续费四列（十进制字符串或 None）。"""

    fee_bnb_qty: str | None
    fee_bnb_price: str | None
    fee_other_qty: str | None
    fee_other_asset: str | None


@dataclass(frozen=True)
class LegFeeOutcome:
    """单腿回补结果。``columns`` 为 None 表示四列一列都不写（不全/未知，
    D10：不得写部分和、不当 0）；``incomplete`` 表示已写入的列仍不完整
    （如 BNB 数量在、价格缺）。"""

    columns: LegFeeColumns | None
    incomplete: bool
    reason: str


def _dec_or_none(value) -> Decimal | None:
    """保持未知的手续费数值解析：None/不可解析 → None（绝不变成 0）。"""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def route_for_endpoint(endpoint: str | None) -> str | None:
    """腿的 endpoint → 成交明细路由：'spot' | 'margin' | 'um' | None。"""
    if endpoint == D.REGULAR_SPOT_ORDER_PATH:
        return "spot"
    if endpoint == D.SPOT_ORDER_PATH:
        return "margin"
    if endpoint == D.PERP_ORDER_PATH:
        return "um"
    return None


def um_query_window(dispatched_at_us, last_query_at_us):
    """合约成交查询分钟级窗（B1a）。入参是腿上的微秒时间戳；返回
    ``(start_ms, end_ms, clamped)``（毫秒，签名 GET 直接可用）；``clamped``
    表示原始跨度超过接口 7 天硬上限（该腿按不全处理）；``None`` 表示两列
    时间均缺或窗口为空，无法构造。"""
    start = None
    if dispatched_at_us:
        start = int(dispatched_at_us)
    elif last_query_at_us:
        start = int(last_query_at_us) - UM_FALLBACK_WINDOW_US
    if start is None:
        return None
    if last_query_at_us:
        end = int(last_query_at_us)
    else:
        end = start + UM_FALLBACK_WINDOW_US
    if end <= start:
        return None
    clamped = False
    if end - start > UM_WINDOW_MAX_US:
        end = start + UM_WINDOW_MAX_US
        clamped = True
    return start // 1000, end // 1000, clamped


def group_trades(trades, base_asset: str | None):
    """按币种聚合成交手续费（§4.1 分组）。

    返回 ``(bnb_qty, other_qty, other_asset, incomplete, reason)``；数量为
    Decimal 或 None。真零佣金的资产不参与分类（合计 0 = 没有）。形状坏 /
    数值不可解析 → 全 None + 不全（fail-closed，不臆造）。"""
    if not trades:
        return None, None, None, True, "no_trades"
    totals: dict[str, Decimal] = {}
    for trade in trades:
        if not isinstance(trade, dict):
            return None, None, None, True, "bad_trade_shape"
        asset = trade.get("commissionAsset")
        value = _dec_or_none(trade.get("commission"))
        if not isinstance(asset, str) or not asset or value is None:
            return None, None, None, True, "bad_trade_shape"
        totals[asset] = totals.get(asset, Decimal(0)) + value
    present = {a: v for a, v in totals.items() if v != 0}
    if not present:
        # 全部成交佣金为零：没有可写的列，也没有「完整零」的表达位（D1 空=没有）。
        # 判「未找到」，不当 0、不臆造资产名。
        return None, None, None, True, "no_fee_found"
    bnb_qty = present.get("BNB")
    others = {a: v for a, v in present.items() if a != "BNB"}
    other_qty = None
    other_asset = None
    incomplete = False
    reason = "ok"
    if len(others) == 1:
        asset, qty = next(iter(others.items()))
        if asset == "USDT" or (base_asset and asset == base_asset):
            other_qty, other_asset = qty, asset
        else:
            # 第三种资产（非 USDT、非本腿 base）：不可折算（D5），该腿不全。
            incomplete, reason = True, f"other_asset_unpricable:{asset}"
    elif others:
        # 多种非 BNB 资产：装不下（D1），BNB 能定则写、其余两列空。
        incomplete, reason = True, "multi_other_assets"
    return bnb_qty, other_qty, other_asset, incomplete, reason


def fetch_leg_fees(
    transport: FeeTransport, *, endpoint: str | None, order_id,
    symbol: str | None, base_asset: str | None,
    dispatched_at_us, last_query_at_us,
) -> LegFeeOutcome:
    """按腿拉成交并折算冻结四列（T3/T5 共用，断点 3）。

    ``RateLimited`` 向上抛（整个回补停）；其余失败折叠为 ``columns=None`` 的
    结果（该腿判定失败，进游标失败集合）。"""
    route = route_for_endpoint(endpoint)
    if route is None or not order_id or not symbol:
        return LegFeeOutcome(None, True, "leg_identity_missing")
    try:
        if route == "spot":
            trades = transport.spot_trades(symbol, str(order_id), LIMIT)
        elif route == "margin":
            trades = transport.margin_trades(symbol, str(order_id), LIMIT)
        else:
            window = um_query_window(dispatched_at_us, last_query_at_us)
            if window is None:
                return LegFeeOutcome(None, True, "um_window_unbuildable")
            start_ms, end_ms, clamped = window
            if clamped:
                # 跨度 >7 天：截断后窗口已不可信（B1a「视该腿为不全」），
                # 不为注定不可信的结果消耗签名配额。
                return LegFeeOutcome(None, True, "um_window_clamped_7d")
            trades = transport.um_trades(symbol, start_ms, end_ms, LIMIT)
            trades = [
                t for t in trades
                if isinstance(t, dict) and str(t.get("orderId")) == str(order_id)
            ]
    except RateLimited:
        raise
    except FeeFetchError as exc:
        return LegFeeOutcome(None, True, f"fetch_error:{exc}")
    if len(trades) >= LIMIT:
        # 截断安全阀：可能缺尾部成交，禁止对截断列表求和当完整手续费。
        return LegFeeOutcome(None, True, "truncated_at_limit")
    bnb_qty, other_qty, other_asset, incomplete, reason = group_trades(trades, base_asset)
    fee_bnb_price = None
    if bnb_qty is not None:
        if dispatched_at_us:
            try:
                fee_bnb_price = transport.bnb_close_price(int(dispatched_at_us) // 1000)
            except Exception:
                # 公开 K 线失败只降级价格（数量仍写、该腿不全），不算腿失败。
                fee_bnb_price = None
        if fee_bnb_price is None:
            incomplete = True
            reason = "bnb_price_missing"
    columns = LegFeeColumns(
        fee_bnb_qty=D.fmt_decimal(bnb_qty),
        fee_bnb_price=fee_bnb_price,
        fee_other_qty=D.fmt_decimal(other_qty),
        fee_other_asset=other_asset,
    )
    if columns == LegFeeColumns(None, None, None, None):
        # 无一列可写：保持四列全空（=不全），不写半截。
        return LegFeeOutcome(None, True, reason)
    return LegFeeOutcome(columns, incomplete, reason)


# ------------------------------------------------------------ 回补游标（T3）

def load_progress(path) -> dict:
    """读回补断点 ``{"cursor": int, "failed": {leg_id: reason}}``。无文件/坏文件
    → 从头开始（游标 0、失败集空；已写入腿天然被「四列全空」条件排除）。"""
    p = Path(path)
    if not p.exists():
        return {"cursor": 0, "failed": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"cursor": 0, "failed": {}}
    if not isinstance(data, dict):
        return {"cursor": 0, "failed": {}}
    failed = data.get("failed")
    return {
        "cursor": int(data.get("cursor") or 0),
        "failed": dict(failed) if isinstance(failed, dict) else {},
    }


def save_progress(path, cursor: int, failed: dict) -> None:
    """每腿尝试后落盘断点（§4.3：成功或判定失败都推进游标）。"""
    Path(path).write_text(
        json.dumps({"cursor": int(cursor), "failed": failed}, ensure_ascii=False),
        encoding="utf-8",
    )


class BackfillEngine:
    """一次性回补编排（T3）：选腿 → 拉取折算 → 写四列 / 记失败 → 推进游标。

    绝不改写 ``hedge_open_cycle_close_log``（断点 1）。有 running 对冲任务时
    拒绝启动（§4.3）。签名 GET 之间强制 ``THROTTLE_SECONDS`` 节流。"""

    def __init__(self, *, store, transport: FeeTransport, progress_path,
                 sleep=None, fetch=fetch_leg_fees):
        self._store = store
        self._transport = transport
        self._progress_path = progress_path
        self._sleep = sleep
        self._fetch = fetch

    def run(self, *, dry_run: bool = False, max_legs: int | None = None) -> dict:
        """执行一轮回补。返回摘要 dict；``refused``/``stopped`` 非空即本轮未
        正常走完。``dry_run``：零网络、零写入（含断点文件），只报候选清单。"""
        summary = {
            "refused": None, "stopped": None, "attempted": 0, "written": 0,
            "written_incomplete": 0, "failed": 0, "planned_legs": [],
            "cursor": None, "reasons": {},
        }
        if self._store.count_tasks_by_status(D.STATUS_RUNNING) > 0:
            summary["refused"] = "running_tasks"
            return summary
        progress = load_progress(self._progress_path)
        cursor = progress["cursor"]
        failed = progress["failed"]
        summary["cursor"] = cursor
        legs = self._store.list_legs_missing_fees(
            after_id=cursor, exclude_ids=[int(i) for i in failed], limit=max_legs,
        )
        if dry_run:
            summary["planned_legs"] = [leg["id"] for leg in legs]
            return summary
        for index, leg in enumerate(legs):
            if index > 0 and self._sleep is not None:
                self._sleep(THROTTLE_SECONDS)
            try:
                outcome = self._backfill_one(leg)
            except RateLimited as exc:
                # 限速：立刻停。断点已随上一条腿落盘；本腿未完成，游标不推进，
                # 冷却后重跑会再试这一条。
                summary["stopped"] = f"rate_limited:{exc.status}"
                break
            summary["attempted"] += 1
            if outcome.columns is not None:
                written = self._store.update_leg_fees(
                    leg["id"],
                    fee_bnb_qty=outcome.columns.fee_bnb_qty,
                    fee_bnb_price=outcome.columns.fee_bnb_price,
                    fee_other_qty=outcome.columns.fee_other_qty,
                    fee_other_asset=outcome.columns.fee_other_asset,
                )
                if written:
                    summary["written"] += 1
                    if outcome.incomplete:
                        summary["written_incomplete"] += 1
                else:
                    # 四列已被并发写入占住（幂等守卫）——按已写入计，不改写。
                    summary["written"] += 1
            else:
                failed[str(leg["id"])] = outcome.reason
                summary["failed"] += 1
                summary["reasons"][outcome.reason] = (
                    summary["reasons"].get(outcome.reason, 0) + 1
                )
            cursor = leg["id"]
            summary["cursor"] = cursor
            save_progress(self._progress_path, cursor, failed)
        return summary

    def _backfill_one(self, leg: dict) -> LegFeeOutcome:
        """单腿：解析身份/路由并调用共享拉取折算。``RateLimited`` 不在此捕获、
        向上抛给 :meth:`run` 触发整轮停止。"""
        if route_for_endpoint(leg["endpoint"]) == "um":
            symbol = leg["coin"]
            try:
                base = D.base_asset(leg["coin"])
            except Exception:
                return LegFeeOutcome(None, True, "bad_coin")
        else:
            task = {
                "coin": leg["coin"],
                "spot_symbol": leg["spot_symbol"],
                "spot_base_asset": leg["spot_base_asset"],
            }
            symbol = D.spot_symbol_of(task)
            base = D.spot_base_of(task)
        return self._fetch(
            self._transport,
            endpoint=leg["endpoint"],
            order_id=leg["order_id"],
            symbol=symbol,
            base_asset=base,
            dispatched_at_us=leg["dispatched_at_us"],
            last_query_at_us=leg["last_query_at_us"],
        )
