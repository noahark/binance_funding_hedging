"""Test-only hedge-open record-transport fake (10-design §6 / §9 / ADR-5).

Lives in the test tree (NOT in the product package), mirroring
``borrow_paper_executor.py``: no runtime configuration can ever select it. The
production executor seam now has exactly two states — live (real POST) and
disabled (zero I/O, zero fills). The simulated "dry-run fill" executor was
removed from production on 2026-08-06 (Human decision, stage
2026-08-06-hedge-order-close-validation: fake fills polluted real accounting);
it survives here only as the test-only :class:`RecordTransportFake`. Tests
inject it through the ``HedgeOpenTaskService`` constructor to exercise
single-leg exposure, consecutive-failure pause, qty-mismatch and the other
end-to-end scenarios with no network I/O.

``RecordTransportFake`` is the original ``RecordTransportExecutor`` moved
verbatim — renamed only. The seeds/``OutcomeSpec`` vocabulary and the
``_simulate_leg`` / ``_rejected_leg`` / ``_snapshot_price`` /
``_leg_qty_filters`` helpers are copied unchanged so test assertions keep their
exact semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.executor import (
    AttemptContext,
    AttemptOutcome,
    _client_order_ids,
    build_perp_order_params,
    build_spot_order_params,
)
from backend.hedge_open_tasks.wire_constraints import validate_order_params


@dataclass(frozen=True)
class OutcomeSpec:
    """A seedable simulated outcome for the record fake (10-design §6).

    Default (no injection) is a balanced dual-leg fill. A spec can force a
    single-leg fill, a total failure, or a qty mismatch to exercise the
    single-leg-exposure and ``>3``-fail termination paths end-to-end with no real
    order. This seam is test-only and never affects a live executor.
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


def _simulate_leg(
    status: str, qty_override: Decimal | None, full_qty: Decimal, price: Decimal, order_id: str
) -> dict:
    """Simulate one leg's filled result for the record fake (no network)."""
    if status == D.LEG_FILLED:
        filled_qty = qty_override if qty_override is not None else full_qty
        # A-6: persist the actual cumulative quote (= filled_qty * avg_price in
        # Decimal) so the record fake exercises the same end-to-end fill
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


class RecordTransportFake:
    """The original dry-run record transport, moved to the test tree (test-only).

    Records the would-send signed-request params (without secrets), filter
    versions, the preflight snapshot and the client ids, and returns a simulated
    outcome. It performs **no network POST**. The simulated outcome is seedable
    via ``outcome_seeds`` (consumed in order, then balanced) so single-leg
    exposures and the ``>3``-fail termination path can be exercised end-to-end
    with no real order. This fake is never reachable at runtime — production has
    exactly two executors: live (real POST) and disabled (zero fills).
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
            ctx.direction, ctx.position_side_mode or D.POS_MODE_BOTH,
            task_type=ctx.task_type,
        )
        # q_common is None only when preflight had no snapshot (disabled). The
        # record still logs the would-send quantity using single_amount as the
        # unrounded estimate, flagged so an operator sees it was not grid-rounded.
        q_resolved = ctx.q_common is not None
        send_qty = ctx.q_common if ctx.q_common is not None else ctx.single_amount
        spot_cid, perp_cid = _client_order_ids(ctx.attempt_id)
        spot_params = build_spot_order_params(
            ctx.spot_symbol,
            actions,
            send_qty,
            spot_cid,
        )
        perp_params = build_perp_order_params(
            ctx.coin, actions, send_qty, perp_cid, task_type=ctx.task_type,
        )
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
        # rejected here in the record fake rather than acted out as a balanced
        # fill — so such defects fail OFFLINE, never survive to a real send.
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
        # preflight est_price when available, else a placeholder of 1.
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
    filter-selection rule. A field absent from the snapshot (a record with no
    loaded filters, or a bound disabled on this symbol) is omitted so the
    validator treats it as disabled — matching ``compute_preflight``.
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
