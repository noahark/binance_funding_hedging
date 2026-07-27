"""Offline wire-constraint validator for hedge-open order params (10-design §2.5
/ ADR-H4).

A single pure copy of the Binance new-order wire rules, consumed by the dry-run
record transport and by the test fake client so a format-class defect (a
too-long ``newClientOrderId``, a quantity in scientific notation, …) fails OFFLINE
instead of being acted out as a fill. The live send path does NOT consume this
module: on the real-money path Binance remains the sole arbiter of param rules
(ADR-H4).

Purity: this module imports ONLY ``re`` and ``decimal`` — no network, no signing,
no services-layer adapter — so it satisfies the ``hedge_open_tasks`` purity guard
(``test_hedge_purity.py``) and may be imported by the record transport.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

# Binance newClientOrderId cap: 1..36 chars over the documented charset
# `^[\.A-Z\:/a-z0-9_-]{1,36}$`. Source: Binance spot order docs + the live
# `-4015` rejection of a 38-char id (see reports/api-samples/<this-stage>/
# client-order-id-cap.md). The UM side shares the 36-char length cap (same
# `-4015` measured on the UM leg); its charset regex is not separately measured,
# so the validator uses the spot-documented charset (the system's own ids use
# only lowercase hex + a few letters, well inside the safe set).
CLIENT_ORDER_ID_MAX = 36
CLIENT_ORDER_ID_RE = re.compile(r"^[\.A-Z\:/a-z0-9_-]{1,36}$")

# A positive plain fixed-point decimal string: optional integer part, optional
# fractional part, NO sign, NO scientific notation (rejects ``1E-7``). This is
# the form Binance expects for ``quantity``; ``str(Decimal)`` of a very small
# value yields ``1E-7`` which would be rejected by the exchange.
_PLAIN_POSITIVE_DECIMAL_RE = re.compile(r"^(0|[1-9][0-9]*)(\.[0-9]+)?$")

_ORDER_SIDES = ("BUY", "SELL")
# Round-1 freeze: only MARKET orders are dispatched (10-design §2.1 / ADR-1).
_ORDER_TYPES = ("MARKET",)


def validate_client_order_id(value) -> str | None:
    """Return a violation description if ``value`` is not a valid Binance
    ``newClientOrderId``, else ``None``.

    Checks length (1..36) and the documented charset. Callers treat a
    non-``None`` return as a hard rejection (the exchange would return
    ``-4015``).
    """
    if not isinstance(value, str):
        return "newClientOrderId must be a string"
    if not 1 <= len(value) <= CLIENT_ORDER_ID_MAX:
        return f"newClientOrderId length must be 1..{CLIENT_ORDER_ID_MAX}"
    if not CLIENT_ORDER_ID_RE.match(value):
        return "newClientOrderId has illegal characters"
    return None


def validate_order_params(
    params, *, step_size=None, min_qty=None, max_qty=None,
) -> list[str]:
    """Validate the wire shape of one signed order body against the offline
    exchange rules. Returns a list of human-readable violation strings (empty
    list == valid).

    ``step_size`` / ``min_qty`` / ``max_qty`` are optional decimal grid
    constraints: when provided, ``quantity`` is additionally checked to be a
    whole multiple of ``step_size`` and within ``[min_qty, max_qty]``. A MARKET
    open carries no ``price`` key, so price precision is intentionally not
    validated here.
    """
    if not isinstance(params, dict):
        return ["order params must be a dict"]
    violations: list[str] = []

    cid_violation = validate_client_order_id(params.get("newClientOrderId"))
    if cid_violation is not None:
        violations.append(cid_violation)

    qty = params.get("quantity")
    qty_decimal: Decimal | None = None
    if not isinstance(qty, str) or not _PLAIN_POSITIVE_DECIMAL_RE.match(qty):
        violations.append("quantity must be a positive fixed-point decimal string")
    else:
        try:
            qty_decimal = Decimal(qty)
        except InvalidOperation:
            violations.append("quantity must be a positive fixed-point decimal string")
            qty_decimal = None
        if qty_decimal is not None and qty_decimal <= 0:
            violations.append("quantity must be > 0")

    symbol = params.get("symbol")
    if not isinstance(symbol, str) or not symbol or symbol != symbol.upper():
        violations.append("symbol must be a non-empty uppercase string")

    if params.get("side") not in _ORDER_SIDES:
        violations.append(f"side must be one of {','.join(_ORDER_SIDES)}")

    if params.get("type") not in _ORDER_TYPES:
        violations.append(f"type must be one of {','.join(_ORDER_TYPES)}")

    if qty_decimal is not None and step_size is not None:
        try:
            step = Decimal(str(step_size))
            if step > 0 and qty_decimal % step != 0:
                violations.append("quantity is not a whole multiple of step_size")
        except InvalidOperation:
            pass  # a malformed step is not a param-side violation
    if qty_decimal is not None and min_qty is not None:
        try:
            if qty_decimal < Decimal(str(min_qty)):
                violations.append("quantity is below min_qty")
        except InvalidOperation:
            pass
    if qty_decimal is not None and max_qty is not None:
        try:
            if qty_decimal > Decimal(str(max_qty)):
                violations.append("quantity exceeds max_qty")
        except InvalidOperation:
            pass

    return violations
