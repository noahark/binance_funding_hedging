"""Pure domain functions for the dual-ledger flow-log (design §13.2 / §14).

Zero I/O: no network, no signing, no sqlite import — only :mod:`decimal` and
:mod:`collections`. Everything here is unit-testable offline against raw
upstream rows captured in the two recon samples.

Normalized row shapes (the single in-memory contract shared with ``store``):

Interest row (from ``GET /sapi/v1/margin/interestHistory`` ``rows[]``)::

    {
      "tx_id": str,                 # txId; 19-digit long -> str (idempotency key)
      "accrued_at_ms": int,         # interestAccuredTime (Binance spelling "Accured")
      "asset": str,
      "raw_asset": Optional[str],
      "principal": Optional[str],   # raw decimal string verbatim, never float
      "interest": Optional[str],    # raw decimal string verbatim
      "interest_rate": Optional[str],
      "type": Optional[str],
      "isolated_symbol": Optional[str],  # isolatedSymbol; "" -> None
    }

UM income row (from ``GET /papi/v1/um/income`` array)::

    {
      "tran_id": str,               # tranId; long -> str (half of idempotency key)
      "income_type": str,           # incomeType
      "time_ms": int,               # time
      "symbol": Optional[str],      # "" (TRANSFER rows) -> None
      "income": Optional[str],      # raw decimal string verbatim
      "asset": Optional[str],
      "info": Optional[str],
      "trade_id": Optional[str],    # tradeId; "" (funding rows) -> None
    }

Store rows additionally carry ``first_seen_run_id`` / ``first_seen_at_ms``;
the summarize functions ignore those storage-meta keys.

Four frozen hard rules (design §13.2 rules 1–5) implemented below:

1. **All IDs are strings.** ``txId`` / ``tranId`` are 19-digit longs
   (``2328408217636413776 > 2**53``); a JSON *number* would be silently
   mutated by a browser ``JSON.parse``, and they are the idempotency keys.
2. **Amounts/rates pass through verbatim** — no round / quantize / float /
   zero-pad; missing is ``None``; empty-string ``symbol`` / ``trade_id`` /
   ``isolated_symbol`` normalize to ``None``.
3. **Summaries use :class:`~decimal.Decimal`** summed inside an explicit
   :func:`~decimal.localcontext` (``prec >= 40``) and emitted via
   ``format(total, "f")``.
4. **One unparseable amount in a group ⇒ that group's ``*_total`` is ``None``
   and ``unparsed_row_count > 0``** — never pass a partial sum off as the
   whole. Missing (``None``) amounts are skipped, NOT counted as unparseable.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, Dict, List, Optional, Tuple

# Decimal context precision for all amount summation (design §13.2 rule 3 /
# §14 rule 6). 40 significant digits is far beyond any realistic accumulated
# funding/interest magnitude and prevents any precision leak in the sum.
_SUM_PREC = 40

# Binance interest ``type`` enum -> Chinese label (design §3.1). Used by the
# service/frontend; kept here so the canonical mapping lives next to the row
# shape it describes. The labels are display-only; normalization never touches
# the raw ``type`` string.
INTEREST_TYPE_LABELS: Dict[str, str] = {
    "PERIODIC": "小时计息",
    "ON_BORROW": "借入首息",
    "PERIODIC_CONVERTED": "小时息(BNB)",
    "ON_BORROW_CONVERTED": "借入首息(BNB)",
    "PORTFOLIO": "负余额日息",
}

# UM income ``incomeType`` enum -> Chinese label (design §3.2).
INCOME_TYPE_LABELS: Dict[str, str] = {
    "FUNDING_FEE": "资金费",
    "COMMISSION": "手续费",
    "REALIZED_PNL": "已实现盈亏",
    "TRANSFER": "划转",
    "COMMISSION_REBATE": "返佣",
    "INSURANCE_CLEAR": "清算保险",
    "API_REBATE": "API返佣",
    "REFERRAL_KICKBACK": "推荐返佣",
}


class WindowValidationError(ValueError):
    """Raised when a query window is malformed (start >= end). The service
    (task B) maps this to HTTP 400 ``invalid_window`` (design §13.3)."""


# --------------------------------------------------------------------------- #
# raw-field coercion helpers (rule 1: IDs as str; rule 2: verbatim / None)
# --------------------------------------------------------------------------- #
def _id_to_str(value: Any) -> Optional[str]:
    """Coerce an idempotency-key field to ``str`` (rule 1).

    ``txId`` / ``tranId`` arrive from Binance as JSON numbers (Python ``int``,
    exact — Python ints are arbitrary precision) or as strings. Both become a
    plain decimal string. ``None`` stays ``None`` (the caller drops such a
    row — it cannot be an idempotency key). A ``float`` is reduced to its
    integral string if integral (defensive; Binance does not send float ids).
    """
    if value is None:
        return None
    # bool is an int subclass; ids are never booleans, but guard anyway.
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    return str(value)


def _opt_text(value: Any) -> Optional[str]:
    """Optional text field: ``None`` or empty string -> ``None``, else the
    raw string verbatim (rule 2 — no trimming, no coercion)."""
    if value is None:
        return None
    s = value if isinstance(value, str) else str(value)
    return s if s != "" else None


def _amount_str(value: Any) -> Optional[str]:
    """Amount / rate field: ``None`` or empty string -> ``None``, else the raw
    string verbatim — no round, no quantize, no float, no zero-pad (rule 2).

    A non-numeric string is preserved as-is here; the summarize step will flag
    it as unparseable (rule 4) rather than silently coerce it.
    """
    if value is None:
        return None
    s = value if isinstance(value, str) else str(value)
    return s if s != "" else None


def _ms(value: Any) -> Optional[int]:
    """Millisecond timestamp: ``None`` -> ``None``; otherwise ``int(value)``."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# normalization (raw camelCase -> snake_case normalized rows)
# --------------------------------------------------------------------------- #
def normalize_interest_rows(raw_rows: Any) -> List[Dict[str, Any]]:
    """Normalize raw ``interestHistory`` ``rows[]`` into the interest row shape.

    Drops a row when its idempotency key (``txId``) or timestamp is missing —
    such a row can neither be deduplicated nor placed in time, and the store's
    ``tx_id`` / ``accrued_at_ms`` columns are ``NOT NULL``. Non-dict entries in
    the raw list are skipped. Dedup/sort are separate steps.
    """
    out: List[Dict[str, Any]] = []
    if not isinstance(raw_rows, list):
        return out
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        tx_id = _id_to_str(raw.get("txId"))
        accrued_at_ms = _ms(raw.get("interestAccuredTime"))
        asset = _opt_text(raw.get("asset"))
        if tx_id is None or accrued_at_ms is None or asset is None:
            # Cannot be stored (PK / NOT NULL) or placed in time/window.
            continue
        out.append(
            {
                "tx_id": tx_id,
                "accrued_at_ms": accrued_at_ms,
                "asset": asset,
                "raw_asset": _opt_text(raw.get("rawAsset")),
                "principal": _amount_str(raw.get("principal")),
                "interest": _amount_str(raw.get("interest")),
                "interest_rate": _amount_str(raw.get("interestRate")),
                "type": _opt_text(raw.get("type")),
                "isolated_symbol": _opt_text(raw.get("isolatedSymbol")),
            }
        )
    return out


def normalize_income_rows(raw_rows: Any) -> List[Dict[str, Any]]:
    """Normalize the raw ``um/income`` array into the income row shape.

    Drops a row whose idempotency key half (``incomeType`` or ``tranId``) or
    timestamp (``time``) is missing — same NOT-NULL reasoning as interest.
    """
    out: List[Dict[str, Any]] = []
    if not isinstance(raw_rows, list):
        return out
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        tran_id = _id_to_str(raw.get("tranId"))
        income_type = _opt_text(raw.get("incomeType"))
        time_ms = _ms(raw.get("time"))
        if tran_id is None or income_type is None or time_ms is None:
            continue
        out.append(
            {
                "tran_id": tran_id,
                "income_type": income_type,
                "time_ms": time_ms,
                "symbol": _opt_text(raw.get("symbol")),
                "income": _amount_str(raw.get("income")),
                "asset": _opt_text(raw.get("asset")),
                "info": _opt_text(raw.get("info")),
                "trade_id": _opt_text(raw.get("tradeId")),
            }
        )
    return out


# --------------------------------------------------------------------------- #
# dedup (idempotency keys; first occurrence wins — never overwrites)
# --------------------------------------------------------------------------- #
def dedup_interest_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate interest rows by ``tx_id``; the first occurrence wins
    (design §13.2 rule: existing rows are never overwritten)."""
    seen: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    for r in rows:
        key = r["tx_id"]
        if key not in seen:
            seen[key] = r
    return list(seen.values())


def dedup_income_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate income rows by ``(income_type, tran_id)``; first wins."""
    seen: "OrderedDict[Tuple[str, str], Dict[str, Any]]" = OrderedDict()
    for r in rows:
        key = (r["income_type"], r["tran_id"])
        if key not in seen:
            seen[key] = r
    return list(seen.values())


# --------------------------------------------------------------------------- #
# cross-margin capital-flow normalization (stage 2026-08-10-cross-margin-flow-log-v1)
# --------------------------------------------------------------------------- #
# Normalized capital row (from ``GET /sapi/v1/margin/capital-flow`` array):
#
#   {
#     "id": str,         # id; long -> str (PRIMARY KEY + dedup key;翻页键)
#     "tran_id": str,    # tranId; long -> str (与 asset-transfer 审计可对齐;
#                        #   同 tran_id 多 flow_type 行各自有不同 id,全部保留)
#     "time_ms": int,    # timestamp
#     "asset": str,
#     "flow_type": Optional[str],   # type 枚举 (TRANSFER/BORROW/REPAY/...)
#     "amount": Optional[str],      # 原样; 正=入全仓, 负=出全仓
#   }
def normalize_capital_rows(raw_rows: Any) -> List[Dict[str, Any]]:
    """Normalize the raw ``capital-flow`` array into the capital row shape.

    Drops a row whose ``id`` (PRIMARY KEY / dedup key), ``tran_id``, ``timestamp``
    or ``asset`` is missing — ``id``/``time_ms``/``asset``/``tran_id`` are
    ``NOT NULL`` in the store and ``id`` is the idempotency key. Non-dict
    entries are skipped, same as the other two sources. Dedup/sort are separate.
    """
    out: List[Dict[str, Any]] = []
    if not isinstance(raw_rows, list):
        return out
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        row_id = _id_to_str(raw.get("id"))
        tran_id = _id_to_str(raw.get("tranId"))
        time_ms = _ms(raw.get("timestamp"))
        asset = _opt_text(raw.get("asset"))
        if row_id is None or tran_id is None or time_ms is None or asset is None:
            continue
        out.append(
            {
                "id": row_id,
                "tran_id": tran_id,
                "time_ms": time_ms,
                "asset": asset,
                "flow_type": _opt_text(raw.get("type")),
                "amount": _amount_str(raw.get("amount")),
            }
        )
    return out


def dedup_capital_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate capital rows by ``id``; first occurrence wins (an already-
    stored row is never overwritten). The same ``tran_id`` with different
    ``flow_type`` has a different ``id`` and is fully retained."""
    seen: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    for r in rows:
        key = r["id"]
        if key not in seen:
            seen[key] = r
    return list(seen.values())


# --------------------------------------------------------------------------- #
# summarize (Decimal sum; rule 3 localcontext; rule 4 unparseable -> null)
# --------------------------------------------------------------------------- #
def _sum_amounts(amounts: List[Optional[str]]) -> Tuple[Optional[str], int]:
    """Sum a list of raw amount strings under an explicit ``localcontext``.

    Returns ``(total_str_or_None, unparsed_count)``. ``None`` entries are
    skipped (missing, not unparseable). If any entry is present but
    unparseable, ``total_str`` is ``None`` and ``unparsed_count > 0`` — never a
    partial sum masquerading as the whole.
    """
    unparsed = 0
    total = Decimal(0)
    with localcontext() as ctx:
        ctx.prec = _SUM_PREC
        for a in amounts:
            if a is None:
                continue
            try:
                total += Decimal(a)
            except (InvalidOperation, ValueError, TypeError):
                unparsed += 1
    if unparsed:
        return None, unparsed
    return format(total, "f"), unparsed


def summarize_interest_by_asset(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group interest rows by ``asset`` and sum ``interest`` (Decimal).

    Each group: ``{"asset", "interest_total", "row_count", "unparsed_row_count"}``.
    ``interest_total`` is ``None`` iff the group has any unparseable amount
    (rule 4). Groups are returned ordered by ``asset`` ascending for
    determinism; the service/frontend may re-sort for display.
    """
    groups: "OrderedDict[str, List[Optional[str]]]" = OrderedDict()
    for r in rows:
        groups.setdefault(r["asset"], []).append(r.get("interest"))
    out: List[Dict[str, Any]] = []
    for asset in sorted(groups):
        amounts = groups[asset]
        total, unparsed = _sum_amounts(amounts)
        out.append(
            {
                "asset": asset,
                "interest_total": total,
                "row_count": len(amounts),
                "unparsed_row_count": unparsed,
            }
        )
    return out


def summarize_income_by_type_asset(
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Group income rows by ``(income_type, asset)`` and sum ``income``.

    Each group: ``{"income_type", "asset", "income_total", "row_count",
    "unparsed_row_count"}`` — never cross-currency (a USDT funding fee and a
    BNB commission stay in separate groups). Ordered by
    ``(income_type, asset)`` ascending.
    """
    groups: "OrderedDict[Tuple[str, Optional[str]], List[Optional[str]]]" = OrderedDict()
    for r in rows:
        key = (r["income_type"], r.get("asset"))
        groups.setdefault(key, []).append(r.get("income"))
    out: List[Dict[str, Any]] = []
    for (income_type, asset) in sorted(groups):
        amounts = groups[(income_type, asset)]
        total, unparsed = _sum_amounts(amounts)
        out.append(
            {
                "income_type": income_type,
                "asset": asset,
                "income_total": total,
                "row_count": len(amounts),
                "unparsed_row_count": unparsed,
            }
        )
    return out


def summarize_funding_by_symbol(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group ``FUNDING_FEE`` income rows by ``(symbol, asset)`` and sum
    ``income`` (design §15.4 N2 — funding-by-symbol ranking, still never
    cross-currency).

    Only ``FUNDING_FEE`` rows participate. Each group:
    ``{"symbol", "asset", "income_total", "row_count"}`` (note: no
    ``unparsed_row_count`` per the frozen §13.2 shape; ``income_total`` is
    still ``None`` if the group has any unparseable amount). Ordered by
    ``income_total`` descending with ``None`` last, then symbol, to reflect
    the ranking intent.
    """
    groups: "OrderedDict[Tuple[Optional[str], Optional[str]], List[Optional[str]]]" = (
        OrderedDict()
    )
    for r in rows:
        if r["income_type"] != "FUNDING_FEE":
            continue
        key = (r.get("symbol"), r.get("asset"))
        groups.setdefault(key, []).append(r.get("income"))
    out: List[Dict[str, Any]] = []
    for (symbol, asset) in groups:
        amounts = groups[(symbol, asset)]
        total, _unparsed = _sum_amounts(amounts)
        out.append(
            {
                "symbol": symbol,
                "asset": asset,
                "income_total": total,
                "row_count": len(amounts),
            }
        )
    # Rank by income_total DESC (None treated as 0 -> sinks), then symbol ASC.
    # Negating the total yields descending order in a single stable sort while
    # keeping the symbol tie-breaker ascending.
    out.sort(
        key=lambda g: (
            -(Decimal(g["income_total"]) if g["income_total"] is not None else Decimal(0)),
            g.get("symbol") or "",
        )
    )
    return out


# --------------------------------------------------------------------------- #
# window validation (design §13.3 — service maps failure to HTTP 400)
# --------------------------------------------------------------------------- #
def validate_window(start_ms: int, end_ms: int) -> Tuple[int, int]:
    """Validate a query window: both ints, ``start_ms < end_ms``.

    Raises :class:`WindowValidationError` otherwise. There is NO 30-day cap:
    the page reads the local ledger, so custom windows may exceed 30 days
    (design §13.3 / §12 decision Q2). The caller (service) parses the raw
    query params and handles missing / non-numeric before calling this.
    """
    if not isinstance(start_ms, int) or not isinstance(end_ms, int):
        raise WindowValidationError("start_ms and end_ms must be integers")
    if start_ms >= end_ms:
        raise WindowValidationError(f"start_ms ({start_ms}) must be < end_ms ({end_ms})")
    return start_ms, end_ms


# --------------------------------------------------------------------------- #
# 资金费率收益曲线（2026-08-20）：四条构成 + 合成净收益的累计时间序列
# --------------------------------------------------------------------------- #
# 口径与持仓级 net_pnl（server.py `_hedge_open_positions`）一致：
#   净收益 = 资金费 − 手续费 − 借币利息 − 开平滑点
# 三点约定：
#   1. 成本在序列里一律记为**负值**，净收益 = 四条直接相加（不再做符号翻转）。
#   2. 币本位金额（利息、BNB 手续费）按 ``price_map`` 现价折 USDT；缺价资产
#      不计入并登记在 ``unpriced_assets``——绝不按 0 处理，那会把成本凭空抹掉。
#   3. 合约 REALIZED_PNL 不进净收益：对冲下它由现货腿反向盈亏抵消，单列供对账。


def _dec(value: Any) -> Optional[Decimal]:
    """宽松解析为 Decimal；None / 空串 / 不可解析 → None（调用方按缺失处理）。"""
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def slippage_pnl(direction: str, kind: str,
                 spot_price: Any, perp_price: Any, qty: Any) -> Optional[Decimal]:
    """开/平单两腿价差折 USDT。

    与前端 ``computeHedgeSlippagePnl``（frontend/index.html）**逐分支等价**，
    改动必须两处同步：卖出腿均价 − 买入腿均价，再乘该腿成交量。
      open  + forward → (perp − spot) · qty      open  + reverse → (spot − perp) · qty
      close + forward → (spot − perp) · qty      close + reverse → (perp − spot) · qty
    任一价格/数量缺失或非正 → None（该腿不计入，绝不当 0）。
    """
    spot, perp, quantity = _dec(spot_price), _dec(perp_price), _dec(qty)
    if spot is None or perp is None or quantity is None:
        return None
    if spot <= 0 or perp <= 0 or quantity <= 0:
        return None
    if kind == "open":
        sell, buy = (perp, spot) if direction == "forward" else (spot, perp)
    elif kind == "close":
        sell, buy = (spot, perp) if direction == "forward" else (perp, spot)
    else:
        return None
    return (sell - buy) * quantity


def build_pnl_series(*, interest_rows, income_rows, capital_rows, close_logs,
                     price_map, start_ms, end_ms, bucket_ms,
                     open_cycle_fills=None) -> Dict[str, Any]:
    """把四类流水折算并按 ``bucket_ms`` 聚成累计序列。纯函数，零 I/O。

    返回 ``points``：``[bucket_start_ms, 资金费, 手续费, 利息, 滑点, 净收益,
    partial]``，全部为累计值字符串（成本为负）。``partial=1`` 表示该点早于现货
    流水入库起点——那之前现货手续费与滑点尚未入库，净收益偏高，前端须显式区分。

    出点节拍是**有资金费结算的桶**（Human 2026-08-20）：没产生费率的小时不出点。
    累加仍逐桶进行，所以两次结算之间的利息/手续费/滑点不会丢，只是累积到下一个
    结算点一起体现——曲线画的是前缀和，末值恒等于全部之和。

    ``open_cycle_fills`` 是**未平仓**周期的成交批次两腿配对
    （``{direction, kind, spot_avg, perp_avg, qty, at_ms, incomplete}``，来自
    ``HedgeOpenStore.list_open_cycle_fill_pairs``）。必须传：持仓期间它们的资金费/
    手续费/利息已经进了另外三条线，滑点却锁在 close-log 里（那张表要整周期关闭才
    写），漏掉净收益就不完整。**不要**改用持仓聚合的加权均价×剩余量——两条腿数量
    可能不同（实测 TSTUSDT 现货 7000 / 合约 6500），乘出来的数不对应任何真实事件。
    单腿批次（一条腿被拒）计入 ``slippage_incomplete_count``：它只驱动脚注说明，
    **不**遮蔽净收益；遮蔽只发生在数据源读失败或缺行情价时。
    """
    validate_window(start_ms, end_ms)
    unpriced: set = set()

    def to_usdt(amount: Any, asset: Optional[str]) -> Optional[Decimal]:
        """币本位 → USDT。USDT 原样；真零无需价格；其余查 price_map。"""
        value = _dec(amount)
        if value is None or not asset:
            return None
        if asset == "USDT" or value == 0:
            return value
        price = _dec(price_map.get(f"{asset}USDT"))
        if price is None:
            unpriced.add(asset)
            return None
        return value * price

    def bucket_of(ms: int) -> int:
        return (int(ms) // bucket_ms) * bucket_ms

    funding: Dict[int, Decimal] = {}
    fees: Dict[int, Decimal] = {}
    interest: Dict[int, Decimal] = {}
    slip: Dict[int, Decimal] = {}

    def add(target: Dict[int, Decimal], ms: Any, value: Optional[Decimal]) -> None:
        if value is None or ms is None:
            return
        # 事件时间必须落在窗口内。流水三表已由查询层按窗口取，但 close_logs /
        # open_cycle_fills 是**全量**传进来的（按周期读，不按时间窗），只按「桶与
        # 窗口相交」过滤挡不住桶内、窗口外的事件——那会把窗口外的滑点算进来。
        if int(ms) < start_ms or int(ms) > end_ms:
            return
        key = bucket_of(ms)
        target[key] = target.get(key, Decimal(0)) + value

    with localcontext() as ctx:
        ctx.prec = _SUM_PREC
        for row in income_rows:
            kind = row.get("income_type")
            if kind == "FUNDING_FEE":
                add(funding, row.get("time_ms"), to_usdt(row.get("income"), row.get("asset")))
            elif kind == "COMMISSION":
                # 上游 income 已是负数（成本），直接累加保持“成本为负”约定
                add(fees, row.get("time_ms"), to_usdt(row.get("income"), row.get("asset")))
        for row in capital_rows:
            if row.get("flow_type") == "TRADING_COMMISSION":
                add(fees, row.get("time_ms"), to_usdt(row.get("amount"), row.get("asset")))
        for row in interest_rows:
            # 账本把利息记为正数，成本取负
            value = to_usdt(row.get("interest"), row.get("asset"))
            add(interest, row.get("accrued_at_ms"), None if value is None else -value)

        # 在持仓周期：逐笔配对补开/平滑点，归到各自成交时刻
        slippage_incomplete = 0
        for fill in (open_cycle_fills or []):
            at_ms = fill.get("at_ms")
            # 先判窗口：窗口外的批次不属于这个区间，既不计入也不算「算不出」，
            # 否则脚注会为一笔根本不该出现在本区间的成交提示漏算。
            if at_ms is not None and not (start_ms <= int(at_ms) <= end_ms):
                continue
            value = None if fill.get("incomplete") else slippage_pnl(
                fill.get("direction"), fill.get("kind"),
                fill.get("spot_avg"), fill.get("perp_avg"), fill.get("qty"))
            if value is None or at_ms is None:
                slippage_incomplete += 1
                continue
            add(slip, at_ms, value)

        for log in close_logs:
            direction = log.get("direction")
            for kind, at_us, args in (
                ("open", log.get("opened_at_us"),
                 (log.get("spot_open_avg"), log.get("open_avg_price"), log.get("open_qty"))),
                ("close", log.get("closed_at_us"),
                 (log.get("spot_close_avg"), log.get("close_avg_price"),
                  log.get("spot_close_qty"))),
            ):
                # 同上：时间可知时先判窗口，窗外直接跳过（不计入、不计数）
                at_ms = None if at_us is None else int(at_us) // 1000
                if at_ms is not None and not (start_ms <= at_ms <= end_ms):
                    continue
                value = slippage_pnl(direction, kind, *args)
                # close-log 的价格/数量列允许 NULL：算不出就登记，绝不静默跳过——
                # 少计一条腿的滑点会让净收益偏离且没有任何痕迹。
                if value is None or at_ms is None:
                    slippage_incomplete += 1
                    continue
                add(slip, at_ms, value)

        buckets = set(funding) | set(fees) | set(interest) | set(slip)
        # 桶键是桶起点：start_ms 未对齐到桶边界时，首个桶的起点会小于 start_ms，
        # 用 `start_ms <= b` 会把整桶连同桶内落在窗口里的流水一起丢掉。
        buckets = {b for b in buckets if b + bucket_ms > start_ms and b <= end_ms}
        if not buckets:
            return {"points": [], "bucket_ms": bucket_ms,
                    "unpriced_assets": sorted(unpriced), "totals": None,
                    "slippage_incomplete_count": slippage_incomplete}

        lo, hi = min(buckets), max(buckets)
        # 出点节拍 = 有资金费结算的桶；末桶总是保留，否则最后一次结算之后新增的
        # 成本不会出现在末值与区间累计里。
        emit = {b for b in funding if b in buckets} | {hi}
        # 现货流水（现货手续费与滑点的来源）入库起点：早于它的净收益缺两项成本。
        capital_times = [int(r["time_ms"]) for r in capital_rows if r.get("time_ms") is not None]
        spot_start = min(capital_times) if capital_times else None

        # 零起点：不插它，"区间累计 = 末值 − 首值" 会把首桶自身的增量当成期初存量。
        points = [[lo - bucket_ms, "0", "0", "0", "0", "0", 1]]
        cum = {"f": Decimal(0), "c": Decimal(0), "i": Decimal(0), "s": Decimal(0)}
        t = lo
        while t <= hi:
            cum["f"] += funding.get(t, Decimal(0))
            cum["c"] += fees.get(t, Decimal(0))
            cum["i"] += interest.get(t, Decimal(0))
            cum["s"] += slip.get(t, Decimal(0))
            net = cum["f"] + cum["c"] + cum["i"] + cum["s"]
            if t in emit:
                points.append([
                    t, format(cum["f"], "f"), format(cum["c"], "f"), format(cum["i"], "f"),
                    format(cum["s"], "f"), format(net, "f"),
                    1 if (spot_start is None or t < spot_start) else 0,
                ])
            t += bucket_ms

        last = points[-1]
        return {
            "points": points,
            "bucket_ms": bucket_ms,
            "spot_flow_start_ms": spot_start,
            "unpriced_assets": sorted(unpriced),
            # 算不出的批次数（单腿等）。只驱动脚注说明，**不**遮蔽净收益——
            # 遮蔽只发生在数据源读失败或缺行情价时，见 docstring。
            "slippage_incomplete_count": slippage_incomplete,
            "totals": {"funding": last[1], "fees": last[2], "interest": last[3],
                       "slippage": last[4], "net": last[5]},
        }
