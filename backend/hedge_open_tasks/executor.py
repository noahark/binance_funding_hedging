"""Hedge-open executor seam — the dry-run record-transport port (10-design §6/§9).

The executor returns a typed :class:`AttemptOutcome` rather than performing any
HTTP. The runtime-reachable executors are :class:`DisabledHedgeExecutor`
(zero I/O, default) and :class:`RecordTransportExecutor` (the dry-run record
transport). Both perform **no network POST**: the record transport records the
fully-formed signed-request params (without secrets), filter versions, the
preflight snapshot and the client ids, and returns a *simulated* outcome that
the service persists. The live executor (real POST) is reachable only under
``APP_HEDGE_EXECUTOR=live`` AND a durable global Start gate AND a passing
read-only preflight — and is NOT implemented this round (ADR-5 / ADR-6).

This module imports only :mod:`dataclasses`, :mod:`decimal` and :mod:`typing`,
plus the pure :mod:`.domain`. It must never import a network or signing
primitive (grep proof, mirroring borrow_tasks §3.9 / §5.1-9).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Protocol

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


@dataclass(frozen=True)
class OutcomeSpec:
    """A seedable simulated outcome for the record transport (10-design §6).

    Default (no injection) is a balanced dual-leg fill. A spec can force a
    single-leg fill, a total failure, or a qty mismatch to exercise the
    ``exposure_alert`` and ``>3``-fail termination paths end-to-end with no real
    order. This seam is test/ops-only and never affects a live executor.
    """

    spot_status: str = D.LEG_FILLED
    perp_status: str = D.LEG_FILLED
    spot_qty: Decimal | None = None  # None => full q_common (or single_amount)
    perp_qty: Decimal | None = None

    @classmethod
    def balanced(cls) -> "OutcomeSpec":
        return cls()

    @classmethod
    def spot_only_filled(cls) -> "OutcomeSpec":
        return cls(perp_status=D.LEG_REJECTED)

    @classmethod
    def perp_only_filled(cls) -> "OutcomeSpec":
        return cls(spot_status=D.LEG_REJECTED)

    @classmethod
    def both_failed(cls) -> "OutcomeSpec":
        return cls(spot_status=D.LEG_REJECTED, perp_status=D.LEG_REJECTED)

    @classmethod
    def qty_mismatch(cls, spot_qty: Decimal, perp_qty: Decimal) -> "OutcomeSpec":
        return cls(spot_qty=spot_qty, perp_qty=perp_qty)


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
    record transport logs this shape, never sends it.
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
    coin: str, actions: D.LegActions, quantity: Decimal, client_order_id: str
) -> dict:
    """The exact signed-body params for POST /papi/v1/um/order (no secrets).

    ``positionSide`` is BOTH one-way / LONG|SHORT hedge from the preflight
    snapshot; ``reduceOnly`` is never set on opens (ADR-3). Only the approved
    wire keys are present — the endpoint path is metadata recorded on the leg
    row, never signed (A-4).
    """
    return {
        "symbol": coin,
        "side": actions.perp_side,
        "type": D.ORDER_TYPE_MARKET,
        "quantity": D.fmt_decimal(quantity),
        "positionSide": actions.perp_position_side,
        "newClientOrderId": client_order_id,
        "newOrderRespType": D.ORDER_RESP_RESULT,
    }


def _client_order_ids(attempt_id: str) -> tuple[str, str]:
    """Derive the two legs' unique client ids from one attempt id (DI-4 §3).

    ``hg`` + the attempt's uuid4 hex + a leg suffix ``s``/``p`` = 35 chars
    (2+32+1), within Binance's 36-char ``newClientOrderId`` cap and over the
    documented charset (ADR-H1). This is the SINGLE derivation point: the dry-run
    record transport and the live executor both call it, so the offline wire
    validator (wire_constraints) and the live send agree on one rule.
    """
    return f"hg{attempt_id}s", f"hg{attempt_id}p"


def _simulate_leg(
    status: str, qty_override: Decimal | None, full_qty: Decimal, price: Decimal, order_id: str
) -> dict:
    """Simulate one leg's filled result for the record transport (no network)."""
    if status == D.LEG_FILLED:
        filled_qty = qty_override if qty_override is not None else full_qty
        # A-6: persist the actual cumulative quote (= filled_qty * avg_price in
        # Decimal) so the record transport exercises the same end-to-end fill
        # accounting the live path uses.
        cumulative_quote = (filled_qty * price) if price is not None else Decimal(0)
        return {
            "status": D.LEG_FILLED,
            "filled_qty": str(filled_qty),
            "avg_price": str(price),
            "cumulative_quote": str(cumulative_quote),
            "order_id": order_id,
        }
    # Non-FILLED: zero executed qty; the real state machine would reconcile via
    # order/trades/positionRisk queries by client id (ADR-4 §7.2).
    return {
        "status": status,
        "filled_qty": "0",
        "avg_price": None,
        "cumulative_quote": "0",
        "order_id": None,
    }


def _rejected_leg(client_order_id: str) -> dict:
    """A leg rejected by the offline wire-constraint gate (S5 / ADR-H4).

    Same shape as a :func:`_simulate_leg` REJECTED leg plus the persisted
    ``client_order_id``, so :func:`domain.classify_attempt` reads it as a
    confirmed submission failure (no ``order_id`` -> ATTEMPT_FAILED).
    """
    return {
        "status": D.LEG_REJECTED,
        "filled_qty": "0",
        "avg_price": None,
        "cumulative_quote": "0",
        "order_id": None,
        "client_order_id": client_order_id,
    }


# ---------------------------------------------------------------------------
# Executor port + the two runtime-reachable executors
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


class RecordTransportExecutor:
    """The dry-run record transport (ADR-5 / 10-design §6).

    Records the would-send signed-request params (without secrets), filter
    versions, the preflight snapshot and the client ids, and returns a simulated
    outcome. It performs **no network POST**. The simulated outcome is seedable
    via ``outcome_seeds`` (consumed in order, then balanced) so single-leg
    exposures and the ``>3``-fail termination path can be exercised end-to-end
    with no real order. The live executor is the only place a real POST may
    happen, and it is not wired this round.
    """

    def __init__(self, outcome_seeds: list[OutcomeSpec] | None = None):
        self._seeds = list(outcome_seeds) if outcome_seeds else []
        self._seed_index = 0
        # Tracks every recorded payload so tests can assert shapes/history.
        self.records: list[dict] = []

    def _next_spec(self) -> OutcomeSpec:
        if self._seed_index < len(self._seeds):
            spec = self._seeds[self._seed_index]
        else:
            spec = OutcomeSpec.balanced()
        self._seed_index += 1
        return spec

    def execute(self, ctx: AttemptContext) -> AttemptOutcome:
        actions = D.direction_to_leg_actions(
            ctx.direction, ctx.position_side_mode or D.POS_MODE_BOTH
        )
        # q_common is None only when preflight had no snapshot (dry-run). The
        # record still logs the would-send quantity using single_amount as the
        # unrounded estimate, flagged so an operator sees it was not grid-rounded.
        q_resolved = ctx.q_common is not None
        send_qty = ctx.q_common if ctx.q_common is not None else ctx.single_amount
        spot_cid, perp_cid = _client_order_ids(ctx.attempt_id)
        spot_params = build_spot_order_params(
            D.spot_order_symbol(ctx.coin, ctx.preflight_snapshot),
            actions,
            send_qty,
            spot_cid,
        )
        perp_params = build_perp_order_params(ctx.coin, actions, send_qty, perp_cid)
        record_payload = {
            "transport": "dry_run_record",
            "posted": False,  # never a real POST on this path
            "spot_order_params": spot_params,
            "perp_order_params": perp_params,
            "client_ids": {"spot": spot_cid, "perp": perp_cid},
            "q_common": str(ctx.q_common) if ctx.q_common is not None else None,
            "q_common_resolved": q_resolved,
            "send_quantity": str(send_qty),
            "filter_versions": ctx.filter_versions,
            "preflight_snapshot": ctx.preflight_snapshot,
        }
        # S5 offline wire-constraint gate (ADR-H4): validate BOTH legs against
        # the single offline exchange-rule copy BEFORE simulating any outcome.
        # A format defect (a too-long client id, a quantity in scientific
        # notation, …) OR a quantity that violates this symbol's LOADED grid/
        # bounds (step_size / min_qty / max_qty from the preflight snapshot) is
        # rejected here in the dry-run record transport rather than acted out
        # as a balanced fill — so such defects fail OFFLINE, never survive to a
        # real send.
        violations = [f"spot: {v}" for v in validate_order_params(
            spot_params, **_leg_qty_filters(ctx.preflight_snapshot, "spot")
        )]
        violations += [f"perp: {v}" for v in validate_order_params(
            perp_params, **_leg_qty_filters(ctx.preflight_snapshot, "perp")
        )]
        if violations:
            record_payload["constraint_violations"] = violations
            self.records.append(record_payload)
            spot_leg = _rejected_leg(spot_cid)
            perp_leg = _rejected_leg(perp_cid)
            return AttemptOutcome(
                attempt_id=ctx.attempt_id,
                category=D.classify_attempt(spot_leg, perp_leg),
                spot=spot_leg,
                perp=perp_leg,
                record_payload=record_payload,
                exposure=None,
                error_code="offline_constraint",
                error_reason_zh="离线参数约束校验失败",
            )
        self.records.append(record_payload)

        # Simulated outcome (no network). A conservative price for avg_price: the
        # preflight est_price when available, else a dry-run placeholder of 1.
        price = _snapshot_price(ctx.preflight_snapshot)
        spec = self._next_spec()
        spot_leg = _simulate_leg(
            spec.spot_status, spec.spot_qty, send_qty, price, f"dryspot-{ctx.attempt_id}"
        )
        spot_leg["client_order_id"] = spot_cid
        perp_leg = _simulate_leg(
            spec.perp_status, spec.perp_qty, send_qty, price, f"dryperp-{ctx.attempt_id}"
        )
        perp_leg["client_order_id"] = perp_cid
        category = D.classify_attempt(spot_leg, perp_leg)
        exposure = (
            D.build_leg_exposure(spot_leg, perp_leg, ctx.ts_us)
            if category == D.ATTEMPT_SINGLE_LEG_EXPOSURE
            else None
        )
        return AttemptOutcome(
            attempt_id=ctx.attempt_id,
            category=category,
            spot=spot_leg,
            perp=perp_leg,
            record_payload=record_payload,
            exposure=exposure,
        )


def _snapshot_price(preflight_snapshot: dict) -> Decimal:
    """Pull a conservative price from the preflight record, else Decimal(1)."""
    raw = preflight_snapshot.get("est_price") if preflight_snapshot else None
    if raw is None:
        return Decimal(1)
    try:
        return Decimal(str(raw))
    except Exception:  # pragma: no cover - record is sanitized by compute_preflight
        return Decimal(1)


def _leg_qty_filters(preflight_snapshot: dict, leg: str) -> dict:
    """Pull one leg's effective MARKET qty grid/bounds from the sanitized
    preflight snapshot as :func:`validate_order_params` kwargs (S5 / ADR-H4).

    The snapshot's ``{leg}_step`` / ``{leg}_min_qty`` / ``{leg}_max_qty`` are the
    effective MARKET values computed ONCE by :func:`domain.compute_preflight`
    (MARKET_LOT_SIZE -> LOT_SIZE fallback via ``effective_market_step`` /
    ``_qty_bounds``); this seam consumes them and does NOT re-derive a second
    filter-selection rule. A field absent from the snapshot (a dry-run record
    with no loaded filters, or a bound disabled on this symbol) is omitted so
    the validator treats it as disabled — matching ``compute_preflight``.
    """
    if not preflight_snapshot:
        return {}
    kwargs: dict = {}
    step = preflight_snapshot.get(f"{leg}_step")
    if step is not None:
        kwargs["step_size"] = step
    min_qty = preflight_snapshot.get(f"{leg}_min_qty")
    if min_qty is not None:
        kwargs["min_qty"] = min_qty
    max_qty = preflight_snapshot.get(f"{leg}_max_qty")
    if max_qty is not None:
        kwargs["max_qty"] = max_qty
    return kwargs
