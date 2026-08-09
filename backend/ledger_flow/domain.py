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
