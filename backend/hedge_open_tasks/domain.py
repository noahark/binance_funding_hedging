"""Hedge-open task domain primitives (round 1: immediate, dry-run record transport).

Pure constants, validation, direction mapping, common-grid rounding, preflight
rules and single-leg classification. No SQLite, no network, no executor.

Mirrors the ``borrow_tasks`` purity discipline: this module is imported by the
store, service, executor and tests, and must never import a network transport or
a cryptographic signing/hashing primitive, so the dry-run record transport's
zero-network proof holds (10-design §9 / ADR-5).

Decimal discipline: ``single_amount`` and filter steps cross the boundary as
JSON strings, are parsed with :class:`Decimal`, and the common-grid quantity is
floored in decimal fixed-point. No binary float ever touches a quantity path
(ADR-2 / DI-4).

Time discipline (mirrors borrow_tasks): all API timestamps are UTC ISO-8601
microsecond strings with a trailing ``Z``; internally every timestamp is an
integer count of microseconds since the Unix epoch.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import ROUND_FLOOR, Decimal, InvalidOperation
from math import gcd

# ---------------------------------------------------------------------------
# Frozen vocabulary and constants (10-design §2 / §3 / §7 / breakdown §3.2)
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "hedge-open-tasks/v1"
FILL_SCHEMA_VERSION = "hedge-open-fills/v1"

# Task.status (stage-1 five states carried forward verbatim, ADR-7).
STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"
STATUS_DONE = "done"
STATUS_EXPOSURE_ALERT = "exposure_alert"
STATUS_DELETED = "deleted"
ALL_STATUSES = (
    STATUS_RUNNING,
    STATUS_PAUSED,
    STATUS_DONE,
    STATUS_EXPOSURE_ALERT,
    STATUS_DELETED,
)
# A running task with success_count < target is dispatch-eligible; exposure_alert
# and paused are operator-paused / frozen states (10-design §7).
ACTIVE_RUNNABLE_STATUSES = (STATUS_RUNNING,)
# Statuses excluded from the default list view unless ``status=all|deleted``.
DEFAULT_HIDDEN_STATUS = STATUS_DELETED
# Sentinel :func:`filter_status_for_list` returns for ``status=all`` so the store
# lists every task *including* ``deleted`` (frozen §3.1). It is distinct from
# ``None``, which is the default view and excludes ``deleted``.
LIST_ALL = "__all__"

# direction (DI-4 / ADR-3 locked mapping).
DIR_FORWARD = "forward"  # funding > 0: buy spot + open short perp
DIR_REVERSE = "reverse"  # funding < 0: sell spot + open long perp
ALL_DIRECTIONS = (DIR_FORWARD, DIR_REVERSE)

# mode (ADR-6): immediate this round; smooth (a streaming push channel) is
# reserved for a later round and is NOT wired here.
MODE_IMMEDIATE = "immediate"
MODE_SMOOTH = "smooth"
ALL_MODES = (MODE_IMMEDIATE, MODE_SMOOTH)
DEFAULT_MODE = MODE_IMMEDIATE

# positionSide mode snapshot from GET /papi/v1/um/positionSide/dual (ADR-3).
POS_MODE_BOTH = "BOTH"  # dualSidePosition=false -> one-way
POS_MODE_HEDGE = "hedge"  # dualSidePosition=true -> two-way LONG|SHORT
ALL_POS_MODES = (POS_MODE_BOTH, POS_MODE_HEDGE)

# Leg order status vocabulary (order/trades reconciliation, 10-design §7).
LEG_FILLED = "FILLED"
LEG_NEW = "NEW"
LEG_PARTIALLY_FILLED = "PARTIALLY_FILLED"
LEG_REJECTED = "REJECTED"
LEG_EXPIRED = "EXPIRED"
LEG_UNKNOWN = "UNKNOWN"  # timeout / 5xx / disconnect -> unresolved

# Attempt outcome categories (the single-leg exposure state machine, ADR-4).
ATTEMPT_SUCCESS = "success"  # both legs FILLED at aligned qty
ATTEMPT_SINGLE_LEG_EXPOSURE = "single_leg_exposure"  # one leg filled, other not
ATTEMPT_FAILED = "failed"  # neither leg filled (no exposure)
ATTEMPT_DISABLED = "execution_disabled"  # disabled executor, no record transport
ALL_ATTEMPT_CATEGORIES = (
    ATTEMPT_SUCCESS,
    ATTEMPT_SINGLE_LEG_EXPOSURE,
    ATTEMPT_FAILED,
    ATTEMPT_DISABLED,
)

# Spot leg sideEffectType is always NO_SIDE_EFFECT for BOTH directions (ADR-3):
# forward buys with available USDT; reverse sells only already-borrowed base and
# never auto-borrows. papi enumerates no AUTO_BORROW_REPAY.
SIDE_EFFECT_NO_SIDE_EFFECT = "NO_SIDE_EFFECT"

# Cumulative failure threshold: >3 failed attempts terminate the plan and pause
# (ADR-4 / 10-design §7.5). Single-leg exposure pauses immediately and is not
# counted toward this threshold.
FAIL_TERMINATE_THRESHOLD = 3

# Rejection reasons surfaced by the preflight quantity/balance checks.
REJECT_INSUFFICIENT_BALANCE = "insufficient_balance"
REJECT_BELOW_MIN_QTY = "below_min_qty"
REJECT_ABOVE_MAX_QTY = "above_max_qty"
REJECT_BELOW_MIN_NOTIONAL = "below_min_notional"

# Round-1 scheduler interval is fixed at 1 second (immediate mode, ADR-6).
DEFAULT_INTERVAL_SECONDS = "1"
DEFAULT_INTERVAL_US = 1_000_000

# HTTP body cap and log page bounds (mirror borrow_tasks §3.6 / §3.7).
BODY_MAX_BYTES = 16384
LIMIT_DEFAULT = 50
LIMIT_MIN = 1
LIMIT_MAX = 200

# Quote asset assumption for the round-1 funding-hedging universe (spot/perp
# symbols are USDT-margined). base asset is derived by stripping this suffix.
QUOTE_ASSET = "USDT"

# papi order endpoints (record-transport payload only; never a real POST here).
SPOT_ORDER_PATH = "/papi/v1/margin/order"
PERP_ORDER_PATH = "/papi/v1/um/order"
ORDER_TYPE_MARKET = "MARKET"
ORDER_RESP_RESULT = "RESULT"

_COIN_RE = re.compile(r"^[A-Z0-9]{2,}" + re.escape(QUOTE_ASSET) + r"$")
_AMOUNT_RE = re.compile(r"^[0-9]+(\.[0-9]+)?$")
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Errors (deterministic 4xx mapping, breakdown §3.1)
# ---------------------------------------------------------------------------


class HedgeError(Exception):
    """A deterministic, sanitized hedge-open API error carrying its HTTP shape.

    ``extra`` carries the direction-specific contract fields (e.g. the
    ``required``/``available`` balance figures for ``insufficient_balance``) so
    the handler can emit them verbatim without re-deriving them.
    """

    def __init__(self, status: int, code: str, detail: str, extra: dict | None = None):
        super().__init__(f"{code}: {detail}")
        self.status = status
        self.code = code
        self.detail = detail
        self.extra = extra

    def as_payload(self) -> dict:
        payload = {"error": self.code, "detail": self.detail}
        if self.extra:
            payload.update(self.extra)
        return payload


def invalid_field(name: str, reason: str) -> HedgeError:
    return HedgeError(400, "invalid_field", f"{name}: {reason}")


# ---------------------------------------------------------------------------
# Direction mapping (ADR-3 / DI-4, locked)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LegActions:
    """The signed-request action shape for both legs of one attempt."""

    spot_side: str  # BUY | SELL
    perp_side: str  # BUY | SELL
    perp_position_side: str  # BOTH | LONG | SHORT
    spot_side_effect: str  # always NO_SIDE_EFFECT


def direction_to_leg_actions(direction: str, position_side_mode: str) -> LegActions:
    """Map a hedge direction + position-mode snapshot to per-leg order actions.

    forward: spot BUY + perp SELL (BOTH one-way / SHORT hedge).
    reverse: spot SELL + perp BUY (BOTH one-way / LONG hedge).
    The spot leg is always ``NO_SIDE_EFFECT``; reduceOnly is never set on opens.
    """
    if direction == DIR_FORWARD:
        perp_side = "SELL"
        perp_pos = "SHORT" if position_side_mode == POS_MODE_HEDGE else "BOTH"
        spot_side = "BUY"
    elif direction == DIR_REVERSE:
        perp_side = "BUY"
        perp_pos = "LONG" if position_side_mode == POS_MODE_HEDGE else "BOTH"
        spot_side = "SELL"
    else:  # pragma: no cover - validated upstream
        raise invalid_field("direction", f"unknown direction {direction!r}")
    return LegActions(
        spot_side=spot_side,
        perp_side=perp_side,
        perp_position_side=perp_pos,
        spot_side_effect=SIDE_EFFECT_NO_SIDE_EFFECT,
    )


# ---------------------------------------------------------------------------
# Common-grid quantity rounding (ADR-2 / 10-design §4, correctness-critical)
# ---------------------------------------------------------------------------


def _decimal_units(step: Decimal) -> tuple[int, Decimal]:
    """Return ``(int_units, unit)`` where ``step == int_units * unit`` exactly.

    ``unit`` is ``10**-P`` for the largest place P shared so both legs' steps are
    integer multiples of it. A step that is not a clean decimal multiple of its
    own finest place (non-canonical Decimal input) is rejected.
    """
    sign, digits, exponent = step.as_tuple()
    if sign or exponent >= 0:
        # exponent >= 0 means the step is an integer (e.g. Decimal("1")); unit=1.
        unit = Decimal(1)
    else:
        unit = Decimal(1).scaleb(exponent)  # 10**exponent, exponent<0
    quotient = (step / unit).to_integral_value()
    if quotient * unit != step:
        raise invalid_field("step", f"step {step} is not a canonical decimal multiple")
    return int(quotient), unit


def decimal_lcm(step_a: Decimal, step_b: Decimal) -> Decimal:
    """Decimal fixed-point least common multiple of two filter steps.

    Both steps are scaled to their finest common unit; the integer LCM of the
    two unit counts is the common grid, expressed back as a Decimal. This is the
    one grid both legs send (ADR-2): never round the two legs independently.
    """
    units_a, unit_a = _decimal_units(step_a)
    units_b, unit_b = _decimal_units(step_b)
    # Align to the finer of the two units so both steps stay integer multiples.
    if unit_a == unit_b:
        unit = unit_a
        a_units, b_units = units_a, units_b
    else:
        unit = min(unit_a, unit_b)  # smaller Decimal = finer place
        a_units = int((step_a / unit).to_integral_value())
        b_units = int((step_b / unit).to_integral_value())
    if a_units <= 0 or b_units <= 0:
        raise invalid_field("step", "filter step must be positive")
    lcm_units = a_units * b_units // gcd(a_units, b_units)
    return lcm_units * unit


def floor_to_grid(amount: Decimal, grid: Decimal) -> Decimal:
    """Floor ``amount`` down to the nearest multiple of ``grid`` (decimal)."""
    if grid <= 0:
        raise invalid_field("step", "filter step must be positive")
    floored = (amount / grid).to_integral_value(rounding=ROUND_FLOOR)
    return floored * grid


# ---------------------------------------------------------------------------
# Filter reading + common-quantity validation (10-design §4 / DI-4)
# ---------------------------------------------------------------------------


def effective_market_step(filters: dict) -> Decimal | None:
    """Pick the effective MARKET qty step: ``MARKET_LOT_SIZE`` if its step is
    enabled (non-zero), else ``LOT_SIZE``. A zero stepSize means that filter's
    qty constraint is disabled (DI-4). Returns ``None`` when neither is present.
    """
    market = filters.get("market_lot_size") or {}
    lot = filters.get("lot_size") or {}

    def _step(spec: dict) -> Decimal | None:
        raw = spec.get("step_size")
        if raw is None or raw == 0 or raw == "0":
            return None
        try:
            value = Decimal(str(raw))
        except InvalidOperation:
            return None
        if value <= 0:
            return None
        return value

    market_step = _step(market)
    if market_step is not None:
        return market_step
    return _step(lot)


def _qty_bounds(filters: dict) -> tuple[Decimal | None, Decimal | None]:
    """Return ``(min_qty, max_qty)`` honoring the MARKET filter when enabled,
    else the LOT_SIZE bounds. A 0/None bound means that limit is disabled.
    """
    market = filters.get("market_lot_size") or {}
    lot = filters.get("lot_size") or {}
    source = market if (market.get("step_size") not in (None, 0, "0")) else lot

    def _val(spec: dict, key: str) -> Decimal | None:
        raw = spec.get(key)
        if raw is None or raw == 0 or raw == "0":
            return None
        try:
            value = Decimal(str(raw))
        except InvalidOperation:
            return None
        return value if value > 0 else None

    return _val(source, "min_qty"), _val(source, "max_qty")


def min_notional(filters: dict) -> Decimal | None:
    """Read the minNotional applying to MARKET orders.

    Spot ``NOTIONAL`` carries ``applyMinToMarket``; perp uses ``MIN_NOTIONAL``
    (``notional``). Returns ``None`` when absent or not applied to market.
    """
    notional = filters.get("notional") or {}
    apply = notional.get("apply_min_to_market")
    # Perp MIN_NOTIONAL has no apply flag; spot defaults apply to False.
    if apply in (False, 0, "false", "False"):
        return None
    raw = notional.get("min_notional")
    if raw is None:
        raw = notional.get("notional")
    if raw is None or raw == 0 or raw == "0":
        return None
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        return None
    return value if value > 0 else None


@dataclass(frozen=True)
class PreflightSnapshot:
    """Read-only preflight data (10-design §5). Injected by a provider; the
    default provider returns ``None`` (dry-run, no network). All numeric fields
    are decimal strings or Decimals; never a binary float on a value path.
    """

    spot_filters: dict
    perp_filters: dict
    balances: dict  # asset -> Decimal crossMarginFree (forward: USDT, reverse: base)
    position_mode: str  # BOTH | hedge
    est_price: Decimal | None = None  # conservative price for forward notional
    rate_limit_order: int | None = None  # GET /papi/v1/rateLimit/order limit


@dataclass(frozen=True)
class PreflightResult:
    q_common: Decimal | None
    position_side_mode: str | None
    balance_ok: bool | None  # None = cannot judge (dry-run, no snapshot/price)
    required: Decimal | None
    available: Decimal | None
    rejection: str | None
    snapshot_record: dict  # sanitized preflight snapshot for record transport


def base_asset(coin: str) -> str:
    """Derive the base asset from a USDT-margined symbol (BTCUSDT -> BTC)."""
    if not coin.endswith(QUOTE_ASSET):
        raise invalid_field("coin", f"coin must be a {QUOTE_ASSET}-margined symbol")
    return coin[: -len(QUOTE_ASSET)]


def _check_common_quantity(
    q_common: Decimal,
    spot_filters: dict,
    perp_filters: dict,
    est_price: Decimal | None,
) -> str | None:
    """Return a rejection reason if ``q_common`` violates either leg's qty or
    minNotional filter, else ``None``. min/max/notional use the effective market
    filter per leg; a 0/None bound is disabled (10-design §4).
    """
    if q_common <= 0:
        # single_amount floored below the common grid -> effectively zero qty.
        return REJECT_BELOW_MIN_QTY
    for filters in (spot_filters, perp_filters):
        min_qty, max_qty = _qty_bounds(filters)
        if min_qty is not None and q_common < min_qty:
            return REJECT_BELOW_MIN_QTY
        if max_qty is not None and q_common > max_qty:
            return REJECT_ABOVE_MAX_QTY
    # minNotional estimated at a conservative price per leg (forward buys USDT).
    if est_price is not None and est_price > 0:
        notional = q_common * est_price
        for filters in (spot_filters, perp_filters):
            floor = min_notional(filters)
            if floor is not None and notional < floor:
                return REJECT_BELOW_MIN_NOTIONAL
    return None


def compute_preflight(
    snapshot: PreflightSnapshot | None,
    coin: str,
    direction: str,
    single_amount: Decimal,
    target_n: int,
) -> PreflightResult:
    """Run the pure preflight computation (10-design §5).

    With ``snapshot is None`` (dry-run, no live read), returns an "unknown"
    result: ``q_common``/``position_side_mode`` are ``None`` and nothing is
    rejected, so a task can still be created to exercise the record transport.
    A live Start rejects when any read failed (the provider returns ``None`` in
    live mode is itself a Start-block; here it simply means "no data yet").
    """
    empty_record = {
        "available": False,
        "reason": "no_preflight_snapshot",
    }
    if snapshot is None:
        return PreflightResult(
            q_common=None,
            position_side_mode=None,
            balance_ok=None,
            required=None,
            available=None,
            rejection=None,
            snapshot_record=empty_record,
        )
    spot_step = effective_market_step(snapshot.spot_filters)
    perp_step = effective_market_step(snapshot.perp_filters)
    if spot_step is None or perp_step is None:
        return PreflightResult(
            q_common=None,
            position_side_mode=snapshot.position_mode,
            balance_ok=None,
            required=None,
            available=None,
            rejection=REJECT_BELOW_MIN_QTY,  # cannot read a market step -> reject
            snapshot_record={"available": True, "reason": "step_unreadable"},
        )
    grid = decimal_lcm(spot_step, perp_step)
    q_common = floor_to_grid(single_amount, grid)
    filter_reject = _check_common_quantity(
        q_common, snapshot.spot_filters, snapshot.perp_filters, snapshot.est_price
    )
    snapshot_record = {
        "available": True,
        "spot_step": str(spot_step),
        "perp_step": str(perp_step),
        "grid": str(grid),
        "est_price": str(snapshot.est_price) if snapshot.est_price is not None else None,
        "position_mode": snapshot.position_mode,
    }
    if filter_reject is not None:
        return PreflightResult(
            q_common=q_common,
            position_side_mode=snapshot.position_mode,
            balance_ok=None,
            required=None,
            available=None,
            rejection=filter_reject,
            snapshot_record=snapshot_record,
        )
    # Balance gate (ADR-3): forward needs USDT crossMarginFree >= q*N*price;
    # reverse needs base crossMarginFree >= q*N. maxBorrowable is never sellable.
    base = base_asset(coin)
    if direction == DIR_FORWARD:
        if snapshot.est_price is None or snapshot.est_price <= 0:
            # Cannot size USDT need without a price -> unknown, not a rejection.
            return PreflightResult(
                q_common=q_common,
                position_side_mode=snapshot.position_mode,
                balance_ok=None,
                required=None,
                available=None,
                rejection=None,
                snapshot_record=snapshot_record,
            )
        required = q_common * target_n * snapshot.est_price
        available = snapshot.balances.get(QUOTE_ASSET, Decimal(0))
    else:
        required = q_common * target_n
        available = snapshot.balances.get(base, Decimal(0))
    balance_ok = available >= required
    return PreflightResult(
        q_common=q_common,
        position_side_mode=snapshot.position_mode,
        balance_ok=balance_ok,
        required=required,
        available=available,
        rejection=REJECT_INSUFFICIENT_BALANCE if not balance_ok else None,
        snapshot_record=snapshot_record,
    )


# ---------------------------------------------------------------------------
# Single-leg exposure classification (ADR-4 / 10-design §7)
# ---------------------------------------------------------------------------


def leg_is_filled(leg: dict | None) -> bool:
    """A leg is "filled" only when status is FILLED with positive executed qty."""
    if not leg:
        return False
    if leg.get("status") != LEG_FILLED:
        return False
    qty = leg.get("filled_qty")
    try:
        return Decimal(str(qty)) > 0 if qty is not None else False
    except InvalidOperation:
        return False


def classify_attempt(spot_leg: dict | None, perp_leg: dict | None) -> str:
    """Classify one attempt's two legs (10-design §7.3/7.4).

    Both legs FILLED at aligned qty -> success. Exactly one filled -> single-leg
    exposure. Neither filled -> failed. Qty alignment: the two executed qtys must
    be equal (both legs send the same ``q_common``); a partial on one leg with a
    mismatched qty is treated as exposure even if both report FILLED.
    """
    spot_filled = leg_is_filled(spot_leg)
    perp_filled = leg_is_filled(perp_leg)
    if spot_filled and perp_filled:
        spot_qty = Decimal(str(spot_leg["filled_qty"]))
        perp_qty = Decimal(str(perp_leg["filled_qty"]))
        if spot_qty == perp_qty:
            return ATTEMPT_SUCCESS
        return ATTEMPT_SINGLE_LEG_EXPOSURE  # mismatched filled qtys
    if spot_filled or perp_filled:
        return ATTEMPT_SINGLE_LEG_EXPOSURE
    return ATTEMPT_FAILED


def build_leg_exposure(spot_leg: dict | None, perp_leg: dict | None, ts_us: int) -> dict | None:
    """Build the persisted ``leg_exposure`` document for a single-leg event.

    Records the leg that filled vs the leg that did not, with each leg's actual
    qty/price/order id, so an operator can see the real exposure. ``None`` when
    neither leg filled (a plain failure, not an exposure).
    """
    spot_filled = leg_is_filled(spot_leg)
    perp_filled = leg_is_filled(perp_leg)
    if not (spot_filled or perp_filled):
        return None

    def _leg_doc(leg: dict | None, filled: bool) -> dict:
        leg = leg or {}
        return {
            "status": leg.get("status", LEG_UNKNOWN),
            "filled_qty": str(leg.get("filled_qty", "0")),
            "avg_price": str(leg.get("avg_price", "0")) if leg.get("avg_price") is not None else None,
            "order_id": leg.get("order_id"),
        }

    return {
        "filled_leg": "spot" if spot_filled and not perp_filled else (
            "perp" if perp_filled and not spot_filled else "both_mismatched"
        ),
        "spot": _leg_doc(spot_leg, spot_filled),
        "perp": _leg_doc(perp_leg, perp_filled),
        "ts": us_to_iso(ts_us),
    }


# ---------------------------------------------------------------------------
# Status transitions (10-design §6 / §7)
# ---------------------------------------------------------------------------


def resolve_status_after_attempt(
    current_status: str,
    category: str,
    new_success_count: int,
    target_n: int,
    new_fail_count: int,
) -> str:
    """Apply the attempt outcome to a task's status.

    ``deleted`` is sticky (never revived by an attempt). Success reaching the
    target -> ``done``. Single-leg exposure -> ``exposure_alert`` (pause, no
    auto-remediation). Cumulative failures > threshold -> ``paused`` (terminated).
    Otherwise the running status is preserved.
    """
    if current_status == STATUS_DELETED:
        return STATUS_DELETED
    if category == ATTEMPT_SINGLE_LEG_EXPOSURE:
        return STATUS_EXPOSURE_ALERT
    if category == ATTEMPT_SUCCESS and new_success_count >= target_n:
        return STATUS_DONE
    if category == ATTEMPT_FAILED and new_fail_count > FAIL_TERMINATE_THRESHOLD:
        return STATUS_PAUSED
    return current_status


# ---------------------------------------------------------------------------
# Validation (raises HedgeError on any deviation; deterministic)
# ---------------------------------------------------------------------------


def validate_coin(value) -> str:
    if not isinstance(value, str) or not _COIN_RE.match(value):
        raise invalid_field("coin", f"must be a {QUOTE_ASSET}-margined symbol like BTCUSDT")
    return value


def validate_direction(value) -> str:
    if value not in ALL_DIRECTIONS:
        raise invalid_field("direction", f"must be one of {', '.join(ALL_DIRECTIONS)}")
    return value


def validate_mode(value) -> str:
    if value not in ALL_MODES:
        raise invalid_field("mode", f"must be one of {', '.join(ALL_MODES)}")
    return value


def validate_single_amount(value) -> str:
    if not isinstance(value, str) or not _AMOUNT_RE.match(value):
        raise invalid_field("single_amount", "must be a decimal string ^[0-9]+(\\.[0-9]+)?$")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:  # pragma: no cover - regex already guards
        raise invalid_field("single_amount", "not a finite decimal") from exc
    if not amount.is_finite() or amount <= 0:
        raise invalid_field("single_amount", "must be finite and > 0")
    return value


def validate_target_n(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise invalid_field("target_n", "must be a positive integer")
    if value < 1:
        raise invalid_field("target_n", "must be >= 1")
    return value


def reject_unknown_keys(body: dict, allowed) -> None:
    """Raise ``invalid_field`` naming the first unexpected key, if any."""
    extra = sorted(k for k in body if k not in allowed)
    if extra:
        raise invalid_field(extra[0], f"unexpected field(s): {', '.join(extra)}")


def validate_limit(value):
    if value is None:
        return LIMIT_DEFAULT
    if isinstance(value, bool) or not isinstance(value, int):
        raise HedgeError(400, "invalid_limit", "limit must be an integer")
    if value < LIMIT_MIN or value > LIMIT_MAX:
        raise HedgeError(400, "invalid_limit", f"limit must be in [{LIMIT_MIN}, {LIMIT_MAX}]")
    return value


# ---------------------------------------------------------------------------
# Cursor (opaque, encodes the log/fill page boundary)
# ---------------------------------------------------------------------------


def encode_cursor(ts_us: int, row_id: int) -> str:
    raw = f"{ts_us}:{row_id}".encode("ascii")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        padding = "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(value + padding).decode("ascii")
        ts_str, id_str = decoded.split(":", 1)
        return int(ts_str), int(id_str)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Time representation (mirrors borrow_tasks)
# ---------------------------------------------------------------------------


def us_to_iso(us) -> str | None:
    if us is None:
        return None
    dt = _EPOCH + timedelta(microseconds=int(us))
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def fmt_decimal(value) -> str | None:
    """Format a Decimal as a fixed-point string with no trailing zeros.

    Computed quantities (q_common, required, avg price) carry arithmetic
    trailing zeros (e.g. ``0.500``); this normalizes them to a stable wire form
    (``0.5``) without ever using scientific notation, so decimal discipline holds
    across the JSON boundary. ``None`` passes through.
    """
    if value is None:
        return None
    text = format(Decimal(value), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text if text != "" else "0"


def filter_status_for_list(status: str | None) -> str | None:
    """Map the ``?status=`` query value to a SQL status filter (frozen §3.1).

    ``all`` -> every task including ``deleted`` (returns the :data:`LIST_ALL`
    sentinel so the store applies no deleted exclusion); None/"" -> the default
    view, which excludes ``deleted``; ``deleted`` -> only deleted; any other
    known status -> that status only. Unknown -> invalid_field.
    """
    if status in (None, ""):
        return None
    if status == "all":
        return LIST_ALL
    if status == DEFAULT_HIDDEN_STATUS:
        return STATUS_DELETED
    if status in ALL_STATUSES:
        return status
    raise invalid_field("status", "must be one of all|running|paused|done|deleted|exposure_alert")
