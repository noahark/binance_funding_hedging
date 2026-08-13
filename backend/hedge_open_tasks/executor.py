"""Hedge-open executor seam — disabled / live two states (10-design §6/§9).

The executor returns a typed :class:`AttemptOutcome` rather than performing any
HTTP. The runtime-reachable executors are :class:`DisabledHedgeExecutor`
(zero I/O, zero fills, the default) and the services-layer live executor (real
POST, injected through the seam — reachable only under
``APP_HEDGE_EXECUTOR=live`` AND a durable global Start gate AND a passing
read-only preflight). The dry-run record-transport fill simulator was REMOVED
from production on 2026-08-06 (Human decision, stage
2026-08-06-hedge-order-close-validation): its fake fills polluted real
accounting; it survives only as a test-only record-transport fake under
``backend/tests/fakes.py``.

This module imports only :mod:`dataclasses`, :mod:`decimal` and :mod:`typing`,
plus the pure :mod:`.domain`. It must never import a network or signing
primitive (grep proof, mirroring borrow_tasks §3.9 / §5.1-9).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, Optional, Protocol

from . import domain as D
from .wire_constraints import validate_order_params


# ---------------------------------------------------------------------------
# Outcome vocabulary
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AttemptContext:
    """Everything the executor needs to record one hedge attempt's params.

    Built by the service from the task + the preflight snapshot before the
    executor is invoked (the attempt row is persisted first, ADR-4 §7.1).
    """

    attempt_id: str
    task_id: str
    coin: str
    direction: str
    single_amount: Decimal
    q_common: Decimal | None  # None when preflight had no snapshot (dry-run)
    position_side_mode: str | None
    preflight_snapshot: dict  # sanitized record from compute_preflight
    filter_versions: dict  # spot/perp filter values read for this attempt
    target_n: int
    ts_us: int
    # 现货腿交易对（2026-08-07 身份统一）：由 service 从任务固化列取出后传入，
    # executor 不再从 preflight_snapshot 现算。**必填**——给默认值会让任何漏传的
    # 构造点对 bStock 静默用合约名下单买错币，且不留痕迹（方案 §1.3 的静默错答案）。
    spot_symbol: str
    task_type: str = "open"  # 功能三：'open'=开仓 / 'close'=平仓（合约腿 reduceOnly）
    # D19: optional same-round audit carrier + monotonic clock. Immediate/close
    # and existing constructors omit both; live smooth dispatch stamps in place.
    smooth_audit: dict | None = None
    mono_us: Callable[[], int] | None = None


@dataclass(frozen=True)
class AttemptOutcome:
    """The simulated outcome of one attempt plus its record-transport payload."""

    attempt_id: str
    category: str  # ATTEMPT_* from domain
    spot: dict  # leg doc {status, filled_qty, avg_price, order_id, client_order_id}
    perp: dict
    record_payload: dict  # would-send params, filter versions, preflight, ids
    exposure: dict | None  # leg_exposure document when single-leg
    # Machine-readable error classification surfaced by the live path (amendment
    # §Error handling): error_category in {None, "auth", "fatal", "absent"},
    # error_code = the exchange business code when available. A "fatal" category
    # stops the task (amendment rows 1–2). The dry-run record transport leaves
    # these None (no real exchange response to classify).
    error_category: str | None = None
    error_code: str | None = None
    error_reason_zh: str | None = None


# ---------------------------------------------------------------------------
# Signed-request param shape (record only; never a real POST, never secrets)
# ---------------------------------------------------------------------------


def build_spot_order_params(
    coin: str, actions: D.LegActions, quantity: Decimal, client_order_id: str
) -> dict:
    """The exact signed-body params for POST /papi/v1/margin/order (no secrets).

    Records ONLY the approved wire keys (symbol/side/type/quantity/
    sideEffectType/newClientOrderId/newOrderRespType) WITHOUT the API key,
    timestamp, recvWindow or HMAC signature. The endpoint path and every internal
    metadata field are deliberately ABSENT — they are recorded separately on the
    leg row, never signed. The live client adds timestamp/recvWindow/signature to
    this exact shape and posts it verbatim (A-4 wire/metadata separation). The
    service records this shape; the disabled path never sends signed traffic.
    """
    return {
        "symbol": coin,
        "side": actions.spot_side,
        "type": D.ORDER_TYPE_MARKET,
        "quantity": D.fmt_decimal(quantity),
        "sideEffectType": actions.spot_side_effect,
        "newClientOrderId": client_order_id,
        "newOrderRespType": D.ORDER_RESP_RESULT,
    }


def build_perp_order_params(
    coin: str, actions: D.LegActions, quantity: Decimal, client_order_id: str,
    task_type: str = D.TASK_TYPE_OPEN,
) -> dict:
    """The exact signed-body params for POST /papi/v1/um/order (no secrets).

    ``positionSide`` is BOTH one-way / LONG|SHORT hedge from the preflight
    snapshot; ``reduceOnly`` is never set on opens (ADR-3) but IS set on close
    legs (``task_type='close'``) so a close order never over-closes. Only the
    approved wire keys are present — the endpoint path is metadata recorded on
    the leg row, never signed (A-4).
    """
    params = {
        "symbol": coin,
        "side": actions.perp_side,
        "type": D.ORDER_TYPE_MARKET,
        "quantity": D.fmt_decimal(quantity),
        "positionSide": actions.perp_position_side,
        "newClientOrderId": client_order_id,
        "newOrderRespType": D.ORDER_RESP_RESULT,
    }
    if task_type == D.TASK_TYPE_CLOSE:
        params["reduceOnly"] = "true"
    return params


def _client_order_ids(attempt_id: str) -> tuple[str, str]:
    """Derive the two legs' unique client ids from one attempt id (DI-4 §3).

    ``hg`` + the attempt's uuid4 hex + a leg suffix ``s``/``p`` = 35 chars
    (2+32+1), within Binance's 36-char ``newClientOrderId`` cap and over the
    documented charset (ADR-H1). This is the SINGLE derivation point: the live
    executor and the test-only record fake both call it, so the offline wire
    validator (wire_constraints) and the live send agree on one rule.
    """
    return f"hg{attempt_id}s", f"hg{attempt_id}p"


# ---------------------------------------------------------------------------
# Executor port + the runtime-reachable executors
# ---------------------------------------------------------------------------


class HedgeExecutor(Protocol):
    """Executor port. ``execute`` must not hold a store transaction/lock."""

    def execute(self, ctx: AttemptContext) -> AttemptOutcome: ...


class DisabledHedgeExecutor:
    """The default executor: zero I/O, zero signed traffic, no record transport.

    Every scheduled attempt therefore resolves to ``execution_disabled`` and
    never contacts Binance; it is not a simulation of a fill. Use this when the
    global executor mode is ``disabled`` (the round-1 default).
    """

    def execute(self, ctx: AttemptContext) -> AttemptOutcome:
        empty_leg = {"status": D.LEG_UNKNOWN, "filled_qty": "0", "avg_price": None, "order_id": None}
        return AttemptOutcome(
            attempt_id=ctx.attempt_id,
            category=D.ATTEMPT_DISABLED,
            spot=empty_leg,
            perp=empty_leg,
            record_payload={"transport": "disabled", "reason": "executor_disabled"},
            exposure=None,
        )



