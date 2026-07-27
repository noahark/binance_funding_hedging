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

# Task.status (stage-1 states carried forward + amendment additive `stopped`,
# ADR-7 / breakdown §2.1 I-4). `stopped` = fatal stop (amendment error-matrix
# rows 1–2): final for that task; the operator corrects the cause and creates a
# NEW task. It is not dispatch-eligible and never auto-resumes.
STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"
STATUS_DONE = "done"
STATUS_STOPPED = "stopped"
STATUS_EXPOSURE_ALERT = "exposure_alert"
STATUS_DELETED = "deleted"
ALL_STATUSES = (
    STATUS_RUNNING,
    STATUS_PAUSED,
    STATUS_DONE,
    STATUS_STOPPED,
    STATUS_EXPOSURE_ALERT,
    STATUS_DELETED,
)
# A running task below its target with no in-flight pair is dispatch-eligible;
# exposure_alert/paused are operator-paused/frozen states, stopped is a fatal
# final state (10-design §7 / amendment §Error handling).
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
LEG_CANCELED = "CANCELED"
LEG_UNKNOWN = "UNKNOWN"  # timeout / 5xx / disconnect -> unresolved

# Attempt outcome categories — now keyed on ACCEPTANCE, not fill (breakdown
# §1.3 / ADR-3). A leg is "accepted" when Binance returned an orderId (the
# order was taken); fill state is observational accounting only. Both legs
# accepted = success (an accepted pair); client-ID lookup proved neither leg
# was accepted = failed (a confirmed submission failure); exactly one accepted
# = single_leg_exposure, which is ADVISORY: it records the leg_exposure but
# does not freeze scheduling and is never counted toward the pause threshold.
ATTEMPT_SUCCESS = "success"  # both legs accepted (orderId returned on both)
ATTEMPT_SINGLE_LEG_EXPOSURE = "single_leg_exposure"  # exactly one leg accepted
ATTEMPT_FAILED = "failed"  # neither leg accepted (confirmed submission failure)
ATTEMPT_DISABLED = "execution_disabled"  # disabled executor, no record transport
# Fatal submission (amendment error-matrix rows 1–2): a preflight fact OR an
# exchange code that means insufficient balance/margin/available qty, symbol
# unavailable, invalid account/position mode, or a filter/min-notional violation.
# It stops the task immediately without waiting for the failure threshold (I-2).
ATTEMPT_FATAL = "fatal_submission"
ALL_ATTEMPT_CATEGORIES = (
    ATTEMPT_SUCCESS,
    ATTEMPT_SINGLE_LEG_EXPOSURE,
    ATTEMPT_FAILED,
    ATTEMPT_DISABLED,
    ATTEMPT_FATAL,
)

# Spot leg sideEffectType is always NO_SIDE_EFFECT for BOTH directions (ADR-3):
# forward buys with available USDT; reverse sells only already-borrowed base and
# never auto-borrows. papi enumerates no AUTO_BORROW_REPAY.
SIDE_EFFECT_NO_SIDE_EFFECT = "NO_SIDE_EFFECT"

# Task-snapshotted consecutive *submission*-failure pause threshold (ADR-3 /
# 10-design §7). Default 3; reaching it (>=) pauses future opening. This is NOT
# a module constant compared inline: each task snapshots its own value so a
# later change ("may be 1 or 2", PRD §6.4) does not retroactively move the bar
# for in-flight tasks. Fill/residual/partial values never touch this counter.
DEFAULT_FAILURE_PAUSE_THRESHOLD = 3
# Pause reason recorded on the task when the threshold is reached.
PAUSE_REASON_CONSECUTIVE_SUBMISSION_FAILURE = "consecutive_submission_failure"

# Amendment 21 task-local pause reasons (manual recovery; no cross-task linkage).
# Recorded on the task as ``pause_reason`` alongside ``status=paused``. Unlike a
# fatal stop, a pause is recoverable: the operator clears the cause and manually
# resumes (Start/recover) the SAME task. A Chinese display reason is provided by
# :func:`pause_reason_zh`.
PAUSE_REASON_RATE_LIMITED = "rate_limited"
PAUSE_REASON_INSUFFICIENT_BALANCE = "insufficient_balance"
PAUSE_REASON_INSUFFICIENT_MARGIN = "insufficient_margin"
PAUSE_REASON_INSUFFICIENT_AVAILABLE_QTY = "insufficient_available_qty"
ALL_PAUSE_REASONS = (
    PAUSE_REASON_CONSECUTIVE_SUBMISSION_FAILURE,
    PAUSE_REASON_RATE_LIMITED,
    PAUSE_REASON_INSUFFICIENT_BALANCE,
    PAUSE_REASON_INSUFFICIENT_MARGIN,
    PAUSE_REASON_INSUFFICIENT_AVAILABLE_QTY,
)

# Amendment 21 task-local worker dispatch/drain signals (internal contract between
# the service's task-local worker and its dispatch/drain helpers). A dispatch or
# drain round returns one of these so the worker can apply the task-local pause
# policy (a 429 / a confirmed insufficient-funds fact pauses THIS task only) or
# exit (a fail-closed / fatal preflight), without touching any other task.
SIGNAL_RATE_LIMITED = "signal_rate_limited"
SIGNAL_INSUFFICIENT_BALANCE = "signal_insufficient_balance"
SIGNAL_INSUFFICIENT_MARGIN = "signal_insufficient_margin"
SIGNAL_INSUFFICIENT_AVAILABLE_QTY = "signal_insufficient_available_qty"
SIGNAL_INSUFFICIENT = (
    SIGNAL_INSUFFICIENT_BALANCE,
    SIGNAL_INSUFFICIENT_MARGIN,
    SIGNAL_INSUFFICIENT_AVAILABLE_QTY,
)
SIGNAL_PREFLIGHT_INCOMPLETE = "signal_preflight_incomplete"
SIGNAL_PREFLIGHT_FATAL = "signal_preflight_fatal"

# Fatal-stop reasons (amendment error-matrix rows 1–2 / breakdown I-4). Recorded
# on the task as the nullable `stop_reason` alongside `status=stopped`. A fatal
# stop is final for that task; the operator corrects the cause and creates a new
# task. These mirror the fatal preflight/exchange facts; a Chinese display reason
# is provided by :func:`stop_reason_zh`.
STOP_REASON_INSUFFICIENT_BALANCE = "insufficient_balance"
STOP_REASON_BELOW_MIN_QTY = "below_min_qty"
STOP_REASON_ABOVE_MAX_QTY = "above_max_qty"
STOP_REASON_BELOW_MIN_NOTIONAL = "below_min_notional"
STOP_REASON_SYMBOL_UNAVAILABLE = "symbol_unavailable"
STOP_REASON_POSITION_MODE_INVALID = "position_mode_invalid"
STOP_REASON_EXCHANGE_FATAL = "exchange_fatal"
ALL_STOP_REASONS = (
    STOP_REASON_INSUFFICIENT_BALANCE,
    STOP_REASON_BELOW_MIN_QTY,
    STOP_REASON_ABOVE_MAX_QTY,
    STOP_REASON_BELOW_MIN_NOTIONAL,
    STOP_REASON_SYMBOL_UNAVAILABLE,
    STOP_REASON_POSITION_MODE_INVALID,
    STOP_REASON_EXCHANGE_FATAL,
)

# Worker exit reasons (Review-1 r3 / amendment 21): a stable machine-readable enum
# written to the task's nullable ``last_worker_exit_reason`` column by each worker
# exit branch and the exception containment in ``_run_task_worker``, then cleared
# when the task re-enters RUNNING. It exists so an operator can tell a
# ``status=running`` live card with NO live worker (it exited and awaits a manual
# Start/recover) from one that is actively dispatching — without changing any
# scheduling semantics. A Chinese display reason is a frontend follow-up, so no
# ``_zh`` companion is frozen here.
WORKER_EXIT_STOPPED_EVENT = "stopped_event"  # woken by service stop() / a hard stop
WORKER_EXIT_TASK_MISSING = "task_missing"
WORKER_EXIT_TASK_NOT_RUNNING = "task_not_running"  # done / paused / stopped / deleted
WORKER_EXIT_START_GATE_OFF = "start_gate_off"
WORKER_EXIT_TARGET_REACHED = "target_reached"
WORKER_EXIT_PREFLIGHT_INCOMPLETE = "preflight_incomplete"  # fail-closed retry
WORKER_EXIT_PREFLIGHT_FATAL = "preflight_fatal"
WORKER_EXIT_WORKER_ERROR = "worker_error"  # last-resort exception containment
ALL_WORKER_EXIT_REASONS = (
    WORKER_EXIT_STOPPED_EVENT,
    WORKER_EXIT_TASK_MISSING,
    WORKER_EXIT_TASK_NOT_RUNNING,
    WORKER_EXIT_START_GATE_OFF,
    WORKER_EXIT_TARGET_REACHED,
    WORKER_EXIT_PREFLIGHT_INCOMPLETE,
    WORKER_EXIT_PREFLIGHT_FATAL,
    WORKER_EXIT_WORKER_ERROR,
)

# Boundary C sanitized block_reason enum (never an environment value). Mirrors
# the borrow domain's BLOCK_* set; surfaced in the startup lifecycle event when
# the live executor is configured but cannot execute (no real credential ever
# leaves the process — the live adapter refuses to POST).
BLOCK_EXECUTOR_DISABLED = "executor_disabled"
BLOCK_HEDGE_CREDENTIALS_MISSING = "hedge_credentials_missing"
BLOCK_RATE_LIMITED = "rate_limited"
ALL_BLOCK_REASONS = (
    BLOCK_EXECUTOR_DISABLED,
    BLOCK_HEDGE_CREDENTIALS_MISSING,
    BLOCK_RATE_LIMITED,
)

# Attempt pair outcome (10-design §Dispatch; the scheduler counter keys off this
# resolved state, never off raw fill/residual). Resolved only after both legs
# reach an acceptance verdict: two accepted = accepted_pair; client-ID lookup
# proved both legs never accepted = confirmed_failed. A leg still being queried
# keeps the attempt in the unresolved ``querying`` state — neither success nor a
# counted failure until the lookup proves absence. An asymmetric single-leg
# acceptance resolves to ``single_leg``: ADVISORY only, recorded but never a gate
# (breakdown §4.5; the breakdown's §3.3 list of three values omits this fourth
# advisory state, which is required so a single-leg acceptance is distinguishable
# from a clean failure on the attempt row).
PAIR_ACCEPTED = "accepted_pair"
PAIR_CONFIRMED_FAILED = "confirmed_failed"
PAIR_QUERYING = "querying"
PAIR_SINGLE_LEG = "single_leg"
ALL_PAIR_OUTCOMES = (
    PAIR_ACCEPTED,
    PAIR_CONFIRMED_FAILED,
    PAIR_QUERYING,
    PAIR_SINGLE_LEG,
)

# Per-leg dispatch state (10-design §Dispatch; one row advances through these).
LEG_PREPARED = "PREPARED"
LEG_DISPATCHING = "DISPATCHING"
LEG_ACCEPTED_OR_QUERYING = "ACCEPTED_OR_QUERYING"
LEG_UNKNOWN_QUERYING = "UNKNOWN_QUERYING"
LEG_TERMINAL_RECORDED = "TERMINAL_RECORDED"
ALL_LEG_DISPATCH_STATES = (
    LEG_PREPARED,
    LEG_DISPATCHING,
    LEG_ACCEPTED_OR_QUERYING,
    LEG_UNKNOWN_QUERYING,
    LEG_TERMINAL_RECORDED,
)

# Rejection reasons surfaced by the preflight quantity/balance checks. The fatal
# ones (all facts were readable; a hard rule failed) map 1:1 to a stop reason and
# stop the task (amendment rows 1–2). The incomplete one means a required fact
# could NOT be read (market step / price / rate-limit) — fail-closed: no attempt,
# no POST, no failure count; the still-running task retries its loop after pacing
# (breakdown I-7).
REJECT_INSUFFICIENT_BALANCE = "insufficient_balance"
REJECT_BELOW_MIN_QTY = "below_min_qty"
REJECT_ABOVE_MAX_QTY = "above_max_qty"
REJECT_BELOW_MIN_NOTIONAL = "below_min_notional"
REJECT_SYMBOL_UNAVAILABLE = "symbol_unavailable"
REJECT_POSITION_MODE_INVALID = "position_mode_invalid"
REJECT_PREFLIGHT_INCOMPLETE = "preflight_incomplete"
# Fatal preflight facts: the task stops immediately. A below/above/notional
# violation is fatal only when the market step WAS readable (a real filter rule
# failed); an unreadable step is REJECT_PREFLIGHT_INCOMPLETE, not fatal. A symbol
# that is readable but NOT TRADING, and a non-one-way position mode
# (dualSidePosition != false), are also fatal (amendment rows 1–2).
PREFLIGHT_FATAL_REASONS = frozenset(
    (
        REJECT_INSUFFICIENT_BALANCE,
        REJECT_BELOW_MIN_QTY,
        REJECT_ABOVE_MAX_QTY,
        REJECT_BELOW_MIN_NOTIONAL,
        REJECT_SYMBOL_UNAVAILABLE,
        REJECT_POSITION_MODE_INVALID,
    )
)

# Map a fatal preflight rejection reason to the task stop_reason vocabulary.
REJECT_TO_STOP_REASON = {
    REJECT_INSUFFICIENT_BALANCE: STOP_REASON_INSUFFICIENT_BALANCE,
    REJECT_BELOW_MIN_QTY: STOP_REASON_BELOW_MIN_QTY,
    REJECT_ABOVE_MAX_QTY: STOP_REASON_ABOVE_MAX_QTY,
    REJECT_BELOW_MIN_NOTIONAL: STOP_REASON_BELOW_MIN_NOTIONAL,
    REJECT_SYMBOL_UNAVAILABLE: STOP_REASON_SYMBOL_UNAVAILABLE,
    REJECT_POSITION_MODE_INVALID: STOP_REASON_POSITION_MODE_INVALID,
}

# Exchange business codes (Binance PAPI ``code`` field). Used by the live
# executor to classify a 4xx into fatal-stop vs known-non-fatal-rejection vs
# auth/signature/timestamp ambiguity (the last stays UNKNOWN — keep querying by
# client ID, never resend). These sets are deliberately conservative and named
# for clarity; an unlisted 4xx defaults to a known non-fatal rejection (counter).
# Insufficient balance/margin/available, or a filter/min-notional/param
# violation -> fatal stop (amendment rows 1–2).
FATAL_EXCHANGE_CODES = frozenset(
    (
        "-2010",  # Account has insufficient balance/margin.
        "-2019",  # Margin is insufficient.
        "-3041",  # PM account level insufficient.
        "-1013",  # Invalid quantity (filter/param).
        "-1100", "-1101", "-1102", "-1103", "-1104", "-1105", "-1106", "-1107",
        "-1108", "-1109", "-1110", "-1111", "-1112", "-1113", "-1114", "-1115",
        "-1128", "-1130", "-1136", "-1140", "-1170", "-1180", "-1190", "-1210",
        "-1212", "-1270",  # LOT_SIZE / PRICE_FILTER / MIN_NOTIONAL / etc. families.
    )
)
# Auth/signature/timestamp/permission ambiguity: the response is NOT trustworthy
# as an acceptance verdict, so the leg stays UNKNOWN and is queried by client ID
# (amendment row 5). Rate-limit codes are handled separately (process-wide delay,
# never a business stop — amendment row 6).
AUTH_AMBIGUOUS_EXCHANGE_CODES = frozenset(
    (
        "-1000",  # UNKNOWN
        "-1021",  # Timestamp recvWindow.
        "-1022",  # Timestamp out of recvWindow.
        "-1099",  # Timestamp for this request outside.
        "-2011",  # Unknown order sent.
        "-2014",  # API key format invalid.
        "-2015",  # Invalid API key / permission.
        "-2017",  # No authority / no trading permissions.
        "-2018",  # No authority.
    )
)

# Amendment 21 manual-pause matrix splits the old "fatal balance" set: a
# CONFIRMED insufficient balance/margin/available-quantity fact now PAUSES the
# current task only (worker exits, manual recovery, no cross-task linkage),
# instead of a fatal stop. :func:`is_insufficient_funds_code` decides membership
# and is consulted BEFORE FATAL_EXCHANGE_CODES in the live classifier. -2019
# (margin) and -3041 (PM level) are unambiguous; -2010 is overloaded — it is
# confirmed only by its message, and when the message does NOT prove an
# insufficient balance it stays a fatal stop (user constraint: never mistake an
# unrecoverable fact for a recoverable pause). These codes remain listed in
# FATAL_EXCHANGE_CODES as the conservative fallback so any classification path
# that does not consult :func:`is_insufficient_funds_code` still stops the task
# rather than drops the error.
INSUFFICIENT_FUNDS_CODES = frozenset(
    (
        "-2019",  # Margin is insufficient.
        "-3041",  # PM account level insufficient.
    )
)
INSUFFICIENT_BALANCE_CODE = "-2010"  # Account has insufficient balance/margin (overloaded).
# Message patterns that confirm a -2010 is an insufficient-available-balance
# rejection (Binance: "Account has insufficient balance ..."). Conservative: a
# -2010 whose message does not match is treated as a fatal stop, not a pause.
_INSUFFICIENT_BALANCE_MSG_RE = re.compile(
    r"insufficient\s+(?:available\s+)?balance", re.IGNORECASE
)


def is_insufficient_funds_code(code: str | None, msg: str | None) -> bool:
    """Conservatively classify an exchange code+message as an insufficient-funds
    (balance/margin/available-quantity) fact eligible for task-local pause
    (amendment 21). -2019/-3041 are unambiguous; -2010 is overloaded and must be
    confirmed by its message — when the message does NOT prove an insufficient
    balance, the caller keeps it as a fatal stop (never a recoverable pause).
    Returns ``False`` for any other code (including ``None``).
    """
    if code in INSUFFICIENT_FUNDS_CODES:
        return True
    if code == INSUFFICIENT_BALANCE_CODE and bool(msg) and _INSUFFICIENT_BALANCE_MSG_RE.search(msg):
        return True
    return False

# Round-1 scheduler interval is fixed at 1 second (immediate mode, ADR-6).
DEFAULT_INTERVAL_SECONDS = "1"
DEFAULT_INTERVAL_US = 1_000_000

# HTTP body cap and log page bounds (mirror borrow_tasks §3.6 / §3.7).
BODY_MAX_BYTES = 16384
LIMIT_DEFAULT = 50
LIMIT_MIN = 1
LIMIT_MAX = 200

# Open-log entries timeline page bounds (amendment 17 — opening-log-pagination-
# compatibility). The additive ``entries`` stream paginates INDEPENDENTLY of the
# legacy ``logs``/``attempts`` page: its own ``entries_limit`` (1..100), its own
# opaque ``entries_cursor``, and its own ``entries_next_cursor``. The legacy
# ``limit`` (1..200) keeps driving ``logs``/``attempts``/``next_cursor``.
ENTRIES_LIMIT_DEFAULT = 50
ENTRIES_LIMIT_MAX = 100

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
    """Return ``(min_qty, max_qty)`` with a PER-CONSTRAINT ``MARKET_LOT_SIZE`` →
    ``LOT_SIZE`` fallback (breakdown A-3 / recon §4.3). Each bound (min/max)
    independently honors ``MARKET_LOT_SIZE`` when that constraint carries a
    usable value, and otherwise falls back to ``LOT_SIZE``; a 0/None value at
    both means that one bound is disabled. This is stricter than picking one
    filter wholesale: a symbol whose MARKET max is disabled still honors the
    LOT_SIZE max rather than dropping the upper bound.
    """
    market = filters.get("market_lot_size") or {}
    lot = filters.get("lot_size") or {}

    def _val(market_key: str, lot_key: str) -> Decimal | None:
        for spec, key in ((market, market_key), (lot, lot_key)):
            raw = spec.get(key)
            if raw is None or raw == 0 or raw == "0":
                continue
            try:
                value = Decimal(str(raw))
            except InvalidOperation:
                continue
            return value if value > 0 else None
        return None

    return _val("min_qty", "min_qty"), _val("max_qty", "max_qty")


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
    # True only when the symbol was readable AND both markets report status
    # TRADING. False (read but not tradable) is a fatal fact (amendment rows 1–2);
    # a missing read fails the whole snapshot closed upstream instead.
    symbol_tradable: bool = True


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
    # Fatal preflight facts (amendment rows 1–2): a readable symbol that is NOT
    # TRADING, or a non-one-way position mode (dualSidePosition != false), stop
    # the task immediately. These are READ facts, not unreadable gaps, so they
    # are fatal rather than fail-closed retry.
    if not snapshot.symbol_tradable:
        return PreflightResult(
            q_common=None,
            position_side_mode=snapshot.position_mode,
            balance_ok=None,
            required=None,
            available=None,
            rejection=REJECT_SYMBOL_UNAVAILABLE,
            snapshot_record={"available": False, "reason": "symbol_not_trading"},
        )
    if snapshot.position_mode != POS_MODE_BOTH:
        return PreflightResult(
            q_common=None,
            position_side_mode=snapshot.position_mode,
            balance_ok=None,
            required=None,
            available=None,
            rejection=REJECT_POSITION_MODE_INVALID,
            snapshot_record={"available": False, "reason": "position_mode_not_one_way"},
        )
    spot_step = effective_market_step(snapshot.spot_filters)
    perp_step = effective_market_step(snapshot.perp_filters)
    if spot_step is None or perp_step is None:
        # A required market step could not be read -> fail-closed INCOMPLETE
        # (amendment I-7): this is not a filter violation, so it never stops the
        # task; the still-running task retries its loop after pacing. Returning
        # REJECT_BELOW_MIN_QTY here would wrongly fatal-stop on an unreadable
        # fact, conflating a missing read with a violated rule.
        return PreflightResult(
            q_common=None,
            position_side_mode=snapshot.position_mode,
            balance_ok=None,
            required=None,
            available=None,
            rejection=REJECT_PREFLIGHT_INCOMPLETE,  # cannot read a market step
            snapshot_record={"available": True, "reason": "step_unreadable"},
        )
    grid = decimal_lcm(spot_step, perp_step)
    q_common = floor_to_grid(single_amount, grid)
    snapshot_record = {
        "available": True,
        "spot_step": str(spot_step),
        "perp_step": str(perp_step),
        "grid": str(grid),
        "est_price": str(snapshot.est_price) if snapshot.est_price is not None else None,
        "position_mode": snapshot.position_mode,
    }
    # Price-completeness is direction-independent (amendment 21 / dispatch P1#1):
    # a missing/zero/negative est_price cannot size notional or the USDT need, and
    # is an UNREADABLE fact, so it fails closed to INCOMPLETE (not a filter
    # violation) for BOTH forward and reverse — zero attempt, zero POST, zero
    # failure count. This runs before the notional/balance gates so an unreadable
    # price is never silently skipped: the old reverse branch never checked it,
    # and the old forward minNotional path (``_check_common_quantity``) skipped
    # notional when est_price was None instead of rejecting.
    if snapshot.est_price is None or snapshot.est_price <= 0:
        return PreflightResult(
            q_common=q_common,
            position_side_mode=snapshot.position_mode,
            balance_ok=None,
            required=None,
            available=None,
            rejection=REJECT_PREFLIGHT_INCOMPLETE,
            snapshot_record=snapshot_record,
        )
    filter_reject = _check_common_quantity(
        q_common, snapshot.spot_filters, snapshot.perp_filters, snapshot.est_price
    )
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
    # est_price is guaranteed present and positive by the direction-independent
    # check above, so the forward USDT need can always be sized.
    base = base_asset(coin)
    if direction == DIR_FORWARD:
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
    """A leg is "filled" only when status is FILLED with positive executed qty.

    Used for observational fill accounting (cumulative base/quote, averages,
    residual) — never as the scheduler's pair-success signal (ADR-3).
    """
    if not leg:
        return False
    if leg.get("status") != LEG_FILLED:
        return False
    qty = leg.get("filled_qty")
    try:
        return Decimal(str(qty)) > 0 if qty is not None else False
    except InvalidOperation:
        return False


def leg_is_accepted(leg: dict | None) -> bool:
    """A leg is "accepted" when Binance returned an orderId for it (ADR-3).

    This is the scheduler's pair-success signal: an orderId proves the order
    was taken (it may still be NEW/PARTIALLY_FILLED, polling to terminal). A
    missing orderId means either not-yet-dispatched, querying, or confirmed
    absent — the caller resolves which before counting a submission failure.
    """
    if not leg:
        return False
    return bool(leg.get("order_id"))


def classify_attempt(spot_leg: dict | None, perp_leg: dict | None) -> str:
    """Classify one attempt's two legs on ACCEPTANCE (breakdown §1.3 / ADR-3).

    Both legs accepted (orderId on both) -> success (an accepted pair). Exactly
    one accepted -> single_leg_exposure (advisory; recorded, never a gate).
    Neither accepted -> failed (a confirmed submission failure). No executed-qty
    equality check is applied: both legs send the same Decimal ``q_common`` and
    are submitted concurrently, but actual fills may differ and are recorded
    only — never auto-repaired (ADR-3 / user policy).
    """
    spot_accepted = leg_is_accepted(spot_leg)
    perp_accepted = leg_is_accepted(perp_leg)
    if spot_accepted and perp_accepted:
        return ATTEMPT_SUCCESS
    if spot_accepted or perp_accepted:
        return ATTEMPT_SINGLE_LEG_EXPOSURE
    return ATTEMPT_FAILED


def build_leg_exposure(spot_leg: dict | None, perp_leg: dict | None, ts_us: int) -> dict | None:
    """Build the advisory ``leg_exposure`` document (frozen §3.2 shape, ADR-3).

    Emits ``{leg, qty, price, ts}`` for a single-leg event: the one leg that was
    ACCEPTED (orderId returned) while the other was not, with that leg's actual
    filled quantity and average price as observational figures. ``leg`` is
    ``"spot"`` when only the spot leg was accepted, ``"perp"`` when only the
    perp leg was accepted. ``qty``/``price`` are decimal strings.

    Advisory only (breakdown §4.5): recording an exposure does NOT freeze the
    task or count toward the pause threshold. Returns ``None`` when neither leg
    was accepted (a plain failure, not an exposure) and when both were accepted
    (an accepted pair). The full per-leg detail always lives in the attempt/leg
    tables (§3.3).
    """
    spot_accepted = leg_is_accepted(spot_leg)
    perp_accepted = leg_is_accepted(perp_leg)
    if not (spot_accepted or perp_accepted):
        return None
    if spot_accepted and perp_accepted:
        return None

    leg = (spot_leg if spot_accepted else perp_leg) or {}
    return {
        "leg": "spot" if spot_accepted else "perp",
        "qty": str(leg.get("filled_qty", "0")),
        "price": str(leg.get("avg_price")) if leg.get("avg_price") is not None else None,
        "ts": us_to_iso(ts_us),
    }


# ---------------------------------------------------------------------------
# Status transitions (10-design §6 / §7)
# ---------------------------------------------------------------------------


def resolve_status_after_attempt(
    current_status: str,
    category: str,
    accepted_count: int,
    target_n: int,
    consecutive_failures: int,
    failure_pause_threshold: int,
) -> str:
    """Apply one attempt's resolved acceptance verdict to a task's status.

    ``deleted`` is sticky. A fatal submission (amendment rows 1–2) -> ``stopped``
    immediately, regardless of the failure threshold. An accepted pair reaching
    the target -> ``done``. Confirmed consecutive *submission* failures OR
    non-rate-limited single-leg exposures reaching the task-snapshotted threshold
    (``>=``, i.e. the threshold-th) -> ``paused`` (R2-F1 / user authorization 28
    §2.1: a single_leg counts toward the brake, so it can no longer bypass the
    consecutive-failure pause by always landing on exactly one accepted leg). A
    single-leg exposure below the threshold keeps the task running — it is never a
    freeze on its own (breakdown §4.5) — and the exposure is still recorded.
    Fill / residual / partial values are observational and never reach this
    function.
    """
    if current_status == STATUS_DELETED:
        return STATUS_DELETED
    if category == ATTEMPT_FATAL:
        return STATUS_STOPPED
    if category == ATTEMPT_SUCCESS and accepted_count >= target_n:
        return STATUS_DONE
    if (
        category in (ATTEMPT_FAILED, ATTEMPT_SINGLE_LEG_EXPOSURE)
        and consecutive_failures >= failure_pause_threshold
    ):
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


def validate_entries_limit(value):
    """Same parsing/default discipline as :func:`validate_limit`, but the
    additive ``entries`` stream is capped at ``ENTRIES_LIMIT_MAX`` (amendment
    17). ``None`` -> ``ENTRIES_LIMIT_DEFAULT``."""
    if value is None:
        return ENTRIES_LIMIT_DEFAULT
    if isinstance(value, bool) or not isinstance(value, int):
        raise HedgeError(400, "invalid_limit", "entries_limit must be an integer")
    if value < LIMIT_MIN or value > ENTRIES_LIMIT_MAX:
        raise HedgeError(
            400,
            "invalid_limit",
            f"entries_limit must be in [{LIMIT_MIN}, {ENTRIES_LIMIT_MAX}]",
        )
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


def encode_entries_cursor(ts_us: int, rank: int, row_id: int) -> str:
    """Opaque cursor for the additive ``entries`` unified stream (amendment 17).

    Encodes the three-part stable sort key ``(ts_us, rank, row_id)`` — ``rank``
    disambiguates the two source tables (attempt vs task event) whose own
    ``row_id`` autoincrement sequences collide. Distinct from the two-part
    :func:`encode_cursor` so an entries cursor can never be confused with a
    legacy logs cursor.
    """
    raw = f"{ts_us}:{rank}:{row_id}".encode("ascii")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_entries_cursor(value):
    """Inverse of :func:`encode_entries_cursor`; returns ``(ts, rank, id)`` or
    ``None`` on any malformed input (the service raises ``invalid_cursor``)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        padding = "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(value + padding).decode("ascii")
        ts_str, rank_str, id_str = decoded.split(":", 2)
        ts = int(ts_str)
        rank = int(rank_str)
        rid = int(id_str)
        if rank not in (0, 1):
            return None
        return ts, rank, rid
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
    raise invalid_field(
        "status",
        "must be one of all|running|paused|done|stopped|deleted|exposure_alert",
    )


def stop_reason_zh(reason: str | None) -> str | None:
    """Safe Chinese display reason for a fatal-stop reason (amendment §Error
    handling: every recorded error carries a machine-readable code + a safe
    Chinese reason; never a key/signature/secret)."""
    if reason is None:
        return None
    return _STOP_REASON_ZH.get(reason, "致命错误，任务已终止，请修正后新建任务")


_STOP_REASON_ZH = {
    STOP_REASON_INSUFFICIENT_BALANCE: "账户余额/保证金不足，任务已终止，请补充后新建任务",
    STOP_REASON_BELOW_MIN_QTY: "下单数量低于最小成交量，任务已终止，请调整后新建任务",
    STOP_REASON_ABOVE_MAX_QTY: "下单数量超过最大成交量，任务已终止，请调整后新建任务",
    STOP_REASON_BELOW_MIN_NOTIONAL: "下单金额低于最小名义价值，任务已终止，请调整后新建任务",
    STOP_REASON_SYMBOL_UNAVAILABLE: "交易对不可用，任务已终止，请确认后新建任务",
    STOP_REASON_POSITION_MODE_INVALID: "仓位模式无效（需单向 BOTH），任务已终止，请修正后新建任务",
    STOP_REASON_EXCHANGE_FATAL: "交易所致命错误，任务已终止，请检查后新建任务",
}


def pause_reason_zh(reason: str | None) -> str | None:
    """Safe Chinese display reason for an amendment-21 task-local pause reason.
    Unlike a stop reason, a pause is recoverable: the operator clears the cause
    and manually resumes the SAME task."""
    if reason is None:
        return None
    return _PAUSE_REASON_ZH.get(reason, "任务已暂停，请检查后手动恢复")


_PAUSE_REASON_ZH = {
    PAUSE_REASON_CONSECUTIVE_SUBMISSION_FAILURE: "连续提交失败达到阈值，任务已暂停，请检查后手动恢复",
    PAUSE_REASON_RATE_LIMITED: "触发交易所限频（429），任务已暂停，请等待限频解除后手动恢复",
    PAUSE_REASON_INSUFFICIENT_BALANCE: "账户可用余额不足，任务已暂停，请补充后手动恢复",
    PAUSE_REASON_INSUFFICIENT_MARGIN: "保证金不足，任务已暂停，请补充后手动恢复",
    PAUSE_REASON_INSUFFICIENT_AVAILABLE_QTY: "可用数量不足，任务已暂停，请补充后手动恢复",
}


def missing_leg_detail(missing: list[str]) -> str:
    """Frozen Chinese detail for the create-task ``missing_leg`` error (S4b /
    10-design §2.4b). Names exactly which leg(s) are confirmed absent on Binance.

    ``missing`` is a subset of ``["spot", "perp"]`` — only legs a probe read
    succeeded on and found absent (``False``); an indeterminate ``None`` leg
    never reaches here (the service does not block on None).
    """
    has_spot = "spot" in missing
    has_perp = "perp" in missing
    if has_spot and has_perp:
        return "该交易对在币安现货与 USDⓈ-M 合约市场均不存在，无法创建对冲任务"
    if has_spot:
        return "该交易对在币安现货市场不存在（缺少现货腿），无法创建对冲任务"
    if has_perp:
        return "该交易对在币安 USDⓈ-M 合约市场不存在（缺少合约腿），无法创建对冲任务"
    # No confirmed-absent leg -> the caller should not have raised; return the
    # neutral both-absent wording rather than raise from the detail helper.
    return "该交易对在币安现货与 USDⓈ-M 合约市场均不存在，无法创建对冲任务"
