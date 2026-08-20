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
import time
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


def _now_ms() -> int:
    return int(time.time() * 1000)


def build_realtime_transport(client, bnb_close_price: Callable[[int], "str | None"]) -> FeeTransport:
    """T5 实时传输装配（duck-typed 签名客户端；本模块不 import 服务层——
    纯度契约）。``client`` 须已具备阶段二加的三个成交明细签名 GET。BNB 冻价
    用 D4 提供方（现价），不用回补的历史 K 线。"""
    def _unwrap(resp) -> list:
        if resp.http_status in (429, 418):
            raise RateLimited(resp.http_status)
        if resp.http_status != 200 or not isinstance(resp.body, list):
            body = str(resp.body)[:120] if resp.body is not None else resp.transport_error
            raise FeeFetchError(f"http={resp.http_status} body={body}")
        return resp.body

    return FeeTransport(
        spot_trades=lambda s, o, l: _unwrap(
            client.get_spot_my_trades(s, o, limit=l, timestamp_ms=_now_ms())),
        margin_trades=lambda s, o, l: _unwrap(
            client.get_margin_my_trades(s, o, limit=l, timestamp_ms=_now_ms())),
        um_trades=lambda s, start, end, l: _unwrap(
            client.get_um_user_trades(
                s, start_time_ms=start, end_time_ms=end, limit=l,
                timestamp_ms=_now_ms())),
        bnb_close_price=bnb_close_price,
    )


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


def _rget(row, key):
    """dict 或 sqlite3.Row 的宽容取值；缺键 → None。"""
    try:
        return row[key]
    except (KeyError, IndexError):
        return None


def resolve_leg_identity(row) -> tuple[str | None, str | None]:
    """腿行（``leg``/``endpoint``/``coin``/``spot_symbol``/``spot_base_asset``；
    dict 或 sqlite3.Row）→ ``(symbol, base_asset)``（§4.1 符号对应）。

    合约腿（um 路由）symbol = ``coin``、base 剥 USDT；现货/杠杆腿用任务固化
    身份（旧行回退查表）。解析失败（路由未知 / coin 非 USDT 后缀）返回
    ``(None, None)``，调用方按腿身份缺失判失败。回补与 T5 实时共用。"""
    if route_for_endpoint(_rget(row, "endpoint")) == "um":
        try:
            return row["coin"], D.base_asset(row["coin"])
        except Exception:
            return None, None
    task = {
        "coin": _rget(row, "coin"),
        "spot_symbol": _rget(row, "spot_symbol"),
        "spot_base_asset": _rget(row, "spot_base_asset"),
    }
    try:
        return D.spot_symbol_of(task), D.spot_base_of(task)
    except Exception:
        return None, None


def um_query_window(dispatched_at_us, last_query_at_us):
    """合约成交查询分钟级窗（B1a）。入参是腿上的微秒时间戳；返回
    ``(start_ms, end_ms, clamped)``（毫秒，签名 GET 直接可用）；``clamped``
    表示原始跨度超过接口 7 天硬上限（该腿按不全处理）；``None`` 表示两列
    时间均缺，无法构造。

    零宽/倒置窗（``end <= start``）：inline ``resolve_attempt`` 用同一个
    now_us 落 dispatched 与 last_query 两列，合约腿的窗恒为零宽——按
    B1a 的「缺 endTime 则 +10 分钟」同款回退向前扩窗：成交必然在
    dispatched 时刻附近，窗内多余成交由本地 orderId 过滤兜底。"""
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
        end = start + UM_FALLBACK_WINDOW_US
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


def _leg_vwap(row: dict) -> Decimal | None:
    """该腿本币折 U 用的成交均价 = ``cumulative_quote_amt ÷ cumulative_base_qty``
    （D5：**严禁** ``hedge_open_leg.avg_price``——交易所 avgPrice 原话，现货基本
    为 NULL，不是折 U 价格）。任一缺失、不可解析或 base 为 0 / quote 为 0
    （G5 哨兵）→ None（该腿不可定价）。"""
    base = _dec_or_none(row.get("cumulative_base_qty"))
    quote = _dec_or_none(row.get("cumulative_quote_amt"))
    if base is None or quote is None or base <= 0 or quote <= 0:
        return None
    return quote / base


def usdt_fee_total(rows) -> tuple[str | None, str | None, bool]:
    """把一组**有成交**腿的冻结四列折算成 USDT 合计（§5.1/§5.2、D10/D11）。

    ``rows`` 为腿 dict（``fee_bnb_qty``/``fee_bnb_price``/``fee_other_qty``/
    ``fee_other_asset``/``cumulative_quote_amt``/``cumulative_base_qty``/
    ``base_asset``）。折 U = Σ(bnb_qty×bnb_price) + Σ(USDT 的 other_qty) +
    Σ(本币 other_qty×该腿 quote/base 均价)。任一参与腿缺必需构成量（四列
    全空=从未查询、BNB 缺价、第三种/多种资产、本币不可定价、半截残留）→
    ``(None, None, False)``——绝不输出半截金额或半截 BNB 数量，不当 0。
    全腿完整才返回 ``(折 U 字符串, BNB 数量字符串, True)``。空列表 → 不全。"""
    if not rows:
        return None, None, False
    total = Decimal(0)
    bnb_total = Decimal(0)
    for row in rows:
        bnb_qty = _dec_or_none(row.get("fee_bnb_qty"))
        bnb_price = _dec_or_none(row.get("fee_bnb_price"))
        other_qty = _dec_or_none(row.get("fee_other_qty"))
        other_asset = row.get("fee_other_asset")
        if (bnb_qty is None and bnb_price is None
                and other_qty is None and not other_asset):
            # 四列全空：该腿从未做过手续费查询——「还没拉」≠「本来没有」（D10）。
            return None, None, False
        if bnb_qty is not None:
            if bnb_price is None:
                return None, None, False  # 数量在、价格缺（写入时冻价失败）
            total += bnb_qty * bnb_price
            bnb_total += bnb_qty
        elif bnb_price is not None:
            return None, None, False  # 有价无量：半截残留
        if other_qty is not None:
            if other_asset == "USDT":
                total += other_qty
            elif other_asset and other_asset == row.get("base_asset"):
                avg = _leg_vwap(row)
                if avg is None:
                    return None, None, False  # 本币不可定价（D5）
                total += other_qty * avg
            else:
                return None, None, False  # 第三种资产 / 资产名缺失
        elif other_asset:
            return None, None, False  # 有资产名无量：半截残留
    return D.fmt_decimal(total), D.fmt_decimal(bnb_total), True


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
        symbol, base = resolve_leg_identity(leg)
        if symbol is None or base is None:
            return LegFeeOutcome(None, True, "leg_identity_missing")
        return self._fetch(
            self._transport,
            endpoint=leg["endpoint"],
            order_id=leg["order_id"],
            symbol=symbol,
            base_asset=base,
            dispatched_at_us=leg["dispatched_at_us"],
            last_query_at_us=leg["last_query_at_us"],
        )
