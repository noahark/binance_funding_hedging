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

from ..domain.normalize import resolve_spot_identity

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

# task_type（功能三 2026-08）：开仓 / 平仓。平仓任务：方向反转 + 合约腿 reduceOnly，
# 完成判定以合约无仓为准；平仓腿绝不进开仓成本基（aggregate 按 task_type 过滤）。
TASK_TYPE_OPEN = "open"
TASK_TYPE_CLOSE = "close"
ALL_TASK_TYPES = (TASK_TYPE_OPEN, TASK_TYPE_CLOSE)

# close_reason 枚举（设计 v1 §4.2 / §3.2）：功能三自动平仓完成 / 人工核实纠偏。
CLOSE_REASON_AUTO_CLOSE = "auto_close"
CLOSE_REASON_MANUAL_VERIFY = "manual_verify"

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
# 51169 / platform collateral cap full (ADR-T3 / 02-collateral-cap-finding.md):
# the asset is above Binance's platform-wide Maximum Collateral Limit, so the
# margin BUY leg cannot bring it into the margin account. NOT an account balance
# fact (adding funds does nothing) — deliberately its own pause reason so the
# display never renders the false "保证金不足" wording of insufficient_margin.
PAUSE_REASON_COLLATERAL_CAP_FULL = "collateral_cap_full"
# 功能三（2026-08）：close 完成核实查仓失败——「查不到」绝不当作「已平完」。
PAUSE_REASON_CLOSE_VERIFY_FAILED = "close_verify_failed"
# 平仓现货卖出重设计（2026-08）：forward close 发单前现货余额检查/划转/复检失败
# → 任务暂停（fail-closed，不重试、不发单），错误原因随 pause_reason 展示。
PAUSE_REASON_CLOSE_SPOT_BALANCE = "close_spot_balance"
# 开单前自动设置合约杠杆（THE -2027 方案 B，Human 拍板）：设置失败 → 任务暂停
# （fail-closed，不创建 attempt、不发单——避免在错误杠杆下开仓，仓位风险不可控）。
PAUSE_REASON_LEVERAGE_SET_FAILED = "leverage_set_failed"
# Retry-counter task (fix-review1-retry-counter): an order-detail query that
# stayed inconclusive (5xx / timeout / malformed 2xx) for all LEG_QUERY_MAX_RETRIES
# attempts. The worker could neither confirm acceptance nor absence, so it pauses
# THIS task for manual verification and leaves the leg non-terminal (never resent,
# never misjudged absent — R2-F2). Recoverable: the operator checks the order on
# the exchange and manually resumes; recovery re-queries by client ID only.
PAUSE_REASON_ORDER_STATE_UNKNOWN = "order_state_unknown"
# Stage 2026-08-06 task 05 (§5, Human decision 4): a preflight read failed and
# the worker exits WITHOUT retrying (the exit-vs-retry contract is documented as
# EXIT). Previously the task stayed RUNNING with zero visible signal — the
# 33-minute silent stall. Now the task PAUSES with a Chinese reason naming the
# failed read, so the stall is visible and recoverable on the card.
PAUSE_REASON_PREFLIGHT_INCOMPLETE = "preflight_incomplete"
ALL_PAUSE_REASONS = (
    PAUSE_REASON_CONSECUTIVE_SUBMISSION_FAILURE,
    PAUSE_REASON_RATE_LIMITED,
    PAUSE_REASON_INSUFFICIENT_BALANCE,
    PAUSE_REASON_INSUFFICIENT_MARGIN,
    PAUSE_REASON_INSUFFICIENT_AVAILABLE_QTY,
    PAUSE_REASON_COLLATERAL_CAP_FULL,
    PAUSE_REASON_ORDER_STATE_UNKNOWN,
    PAUSE_REASON_PREFLIGHT_INCOMPLETE,
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
# A confirmed collateral-cap rejection (51169) on a leg pauses THIS task only
# (ADR-T3): the cap is consumed platform-wide and will not clear in the retry
# window, and it blocks only the forward spot leg — continuing would repeat the
# 2026-07-27 naked-short-growth mechanism. Same task-local-pause shape as a
# SIGNAL_INSUFFICIENT_*; the worker maps either to a pause.
SIGNAL_COLLATERAL_CAP = "signal_collateral_cap"
# Every signal whose correct response is a task-local pause (amendment 21). The
# worker consults this membership to pause THIS task only, then maps the signal
# to its precise pause_reason. Rate-limit is handled separately (its own pause
# with a cooldown kind).
SIGNAL_TASK_LOCAL_PAUSE = SIGNAL_INSUFFICIENT + (SIGNAL_COLLATERAL_CAP,)
SIGNAL_PREFLIGHT_INCOMPLETE = "signal_preflight_incomplete"
SIGNAL_PREFLIGHT_FATAL = "signal_preflight_fatal"
# Retry-counter task: a drain query that stayed inconclusive for the whole
# LEG_QUERY_MAX_RETRIES budget. Handled separately (like SIGNAL_RATE_LIMITED) —
# it pauses THIS task for manual recovery with the leg left non-terminal, and is
# NOT a confirmed-absent signal, so it is deliberately outside
# SIGNAL_TASK_LOCAL_PAUSE.
SIGNAL_ORDER_STATE_UNKNOWN = "signal_order_state_unknown"
# 开单前设置杠杆失败（THE -2027 方案 B）：_dispatch_one_for_task 内已落库暂停
# （PAUSE_REASON_LEVERAGE_SET_FAILED + leverage_set_failed 事件），worker 收到此信号
# 直接退出本轮（不重复暂停、不创建 attempt、不发单）。刻意不在
# SIGNAL_TASK_LOCAL_PAUSE 内（避免 _pause_from_signal 二次暂停）。
SIGNAL_LEVERAGE_SET_FAILED = "signal_leverage_set_failed"

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
WORKER_EXIT_CLOSE_GATE_OFF = "close_gate_off"  # 功能三：平仓闸门关闭（close 任务）
WORKER_EXIT_TARGET_REACHED = "target_reached"
WORKER_EXIT_PREFLIGHT_INCOMPLETE = "preflight_incomplete"  # worker exits WITHOUT retry; task pauses (stage 2026-08-06 task 05 §5)
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

# ---------------------------------------------------------------------------
# Error-classification vocabulary + two-layer code classifier (ADR-T3)
# ---------------------------------------------------------------------------

# The leg-row ``error_category`` values. These are the durable classification a
# rejected leg carries; the live executor maps a Binance ``code`` to one of them
# via :func:`classify_exchange_code`. Values are frozen strings, not enums, so
# the store reads them as plain TEXT.
ERROR_CATEGORY_AUTH = "auth"  # auth/signature/timestamp/permission ambiguity
ERROR_CATEGORY_FATAL = "fatal"  # hard fact -> task stops (rows 1–2)
ERROR_CATEGORY_INSUFFICIENT_FUNDS = "insufficient_funds"  # confirmed -> task-local pause
ERROR_CATEGORY_ABSENT = "absent"  # order was never accepted (query-path 404/-2013)
ERROR_CATEGORY_COLLATERAL_CAP = "collateral_cap"  # 51169 -> task-local pause (ADR-T3)
ERROR_CATEGORY_UNCLASSIFIED = "unclassified"  # a code was present but no rule matched

# Product a leg's endpoint speaks. ``spot`` leg -> margin order endpoint;
# ``perp`` leg -> UM order endpoint. Same enumeration as the fill-figures source
# rule (10-design §1(c)).
PRODUCT_MARGIN = "margin"
PRODUCT_UM = "um"
# Regular spot account product (stage 2026-08-02-spot-order-routing-cap-display-v1
# §4): a positive-funding ``regular_spot`` leg speaks /api/v3/order on
# api.binance.com — a DIFFERENT product from PAPI margin, with its own (empty)
# business-code table so it never inherits margin's 51169 collateral-cap rule.
PRODUCT_SPOT = "spot_product"

# Spot leg account-route vocabulary (design §3 step 4). ``papi_margin`` = the
# existing PAPI cross-margin spot leg (PAPI endpoint, sideEffectType=NO_SIDE_EFFECT);
# ``regular_spot`` = the standard spot account leg (/api/v3/order, no
# sideEffectType). ``regular_spot`` is selected ONLY for a positive-funding BUY
# whose resolved spot base asset hits the platform collateral-cap list, or a
# TRADIFI bStock; the negative-funding direction is always ``papi_margin`` and
# never reads the list.
SPOT_ROUTE_PAPI_MARGIN = "papi_margin"
SPOT_ROUTE_REGULAR_SPOT = "regular_spot"
ALL_SPOT_ROUTES = (SPOT_ROUTE_PAPI_MARGIN, SPOT_ROUTE_REGULAR_SPOT)
# The frozen route-decision reasons recorded on the preflight fingerprint.
ROUTE_REASON_PAPI_DEFAULT = "papi_default"
ROUTE_REASON_TRADIFI_REGULAR_SPOT = "tradifi_regular_spot"
ROUTE_REASON_COLLATERAL_CAP_PRECHECK = "collateral_cap_precheck"
# 平仓现货卖出重设计（2026-08）：forward 平仓卖现货固定走普通现货账户（单一出口，
# 根治 collateral-cap 预检把卖出误导到普通账户的 -2010 事故；cap 语义只对买入有意义）。
ROUTE_REASON_CLOSE_SELL_REGULAR = "close_sell_regular_spot"
# 仅现货（SPOT_ONLY，公开现货 isMarginTradingAllowed=False）前置强制（2026-08）：现货腿
# 必须走普通现货端点 /api/v3/order，不得发到全仓杠杆——THE 51023 根因。这是 provider 层
# 在 decide_spot_route 之前的强制，不是 decide_spot_route 的新规则分支（其规则逐字不变）。
ROUTE_REASON_SPOT_ONLY_REGULAR = "spot_only_regular_spot"

# 开单前自动设置合约杠杆（THE -2027 方案 B，Human 2026-08 拍板）：每任务首个
# attempt 发单前将合约杠杆设为 3 倍（交易所默认 20 倍→现最大 10 倍，10 倍下开仓量
# 超限）。先硬编码 3，后续可配置化（Human：不做杠杆可配置 UI）。
OPEN_LEVERAGE = 3

# Per-product business-code tables — ONLY product-specific codes live here. Codes
# whose margin/UM semantics are identical (insufficient balance/margin, filter /
# min-notional / param violations) are matched product-agnostically by the shared
# layers inside :func:`classify_exchange_code`, so no negative-code verdict can
# change when this stage adds the margin positive-code path. A new product-
# specific code requires live sample evidence before it is seeded (truth
# discipline; 02-collateral-cap-finding.md is 51169's evidence).
MARGIN_BUSINESS_CODES: dict[str, str] = {
    "51169": ERROR_CATEGORY_COLLATERAL_CAP,  # MARGIN_TRADE_COEFF_INSUFFICIENT (platform collateral cap full)
}
# No UM-specific code is seeded this stage: every UM code in production so far is
# a shared negative code already matched by the shared layer. Retained as the
# explicit per-product extension point so a future UM-specific code lands here.
UM_BUSINESS_CODES: dict[str, str] = {}
# Regular-spot /api/v3 order endpoint has no product-specific code seeded this
# stage: a /api/v3/order rejection flows through the shared gateway/business
# layers. Critically it does NOT inherit margin's 51169 rule — 51169 is a PAPI
# margin collateral-cap code that /api/v3/order cannot return (design §4).
SPOT_BUSINESS_CODES: dict[str, str] = {}


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


def classify_exchange_code(product: str, code: str | None, msg: str | None) -> str | None:
    """Classify a Binance PAPI business ``code`` into a leg ``error_category``.

    Two-layer lookup (ADR-T3), consulted in order:

    1. **Shared gateway layer** (product-agnostic): auth/signature/timestamp/
       permission ambiguity. Any papi endpoint — margin included — can return
       these negative codes (e.g. ``-1021``), so this layer precedes the product
       layer.
    2. **Shared business layer** (product-agnostic semantics): a confirmed
       insufficient-funds fact (:func:`is_insufficient_funds_code`) and the
       remaining fatal hard facts (``FATAL_EXCHANGE_CODES``). These codes have
       identical margin/UM semantics, so matching them product-agnostically is
       what GUARANTEES the stage's hard non-regression constraint: no negative
       code's verdict changes when the margin positive-code path is added.
    3. **Per-product business layer**: ``MARGIN_BUSINESS_CODES`` (``51169`` ->
       ``collateral_cap``) and ``UM_BUSINESS_CODES`` (empty this stage). Only a
       product-specific code reaches here.
    4. A code that carries a business value but matches no rule ->
       ``unclassified``.

    Returns ``None`` ONLY when ``code is None`` (the response carried no business
    code at all). That stays distinct from ``unclassified`` (a code was present
    but unrecognized): ``NULL`` means "no code", ``unclassified`` means "code we
    could not classify" — the two must never collapse (the defect this stage
    fixes was exactly that they did).
    """
    if code is None:
        return None
    if code in AUTH_AMBIGUOUS_EXCHANGE_CODES:
        return ERROR_CATEGORY_AUTH
    if is_insufficient_funds_code(code, msg):
        return ERROR_CATEGORY_INSUFFICIENT_FUNDS
    if code in FATAL_EXCHANGE_CODES:
        return ERROR_CATEGORY_FATAL
    if product == PRODUCT_MARGIN and code in MARGIN_BUSINESS_CODES:
        return MARGIN_BUSINESS_CODES[code]
    if product == PRODUCT_UM and code in UM_BUSINESS_CODES:
        return UM_BUSINESS_CODES[code]
    if product == PRODUCT_SPOT and code in SPOT_BUSINESS_CODES:
        return SPOT_BUSINESS_CODES[code]
    return ERROR_CATEGORY_UNCLASSIFIED


# Attempt-row category rollup priority (10-design §2(e)): when a pair settles,
# the two legs' categories roll up to ONE attempt-row category by this rank
# (higher wins). ``collateral_cap`` ranks above ``insufficient_funds``: both
# pause, but the rollup keeps the more specific diagnosis on the attempt row.
# A leg with no category (NULL) ranks below ``absent``.
ERROR_CATEGORY_ROLLUP_PRIORITY = {
    ERROR_CATEGORY_FATAL: 6,
    ERROR_CATEGORY_AUTH: 5,
    ERROR_CATEGORY_COLLATERAL_CAP: 4,
    ERROR_CATEGORY_INSUFFICIENT_FUNDS: 3,
    ERROR_CATEGORY_UNCLASSIFIED: 2,
    ERROR_CATEGORY_ABSENT: 1,
}


def rollup_leg_error_category(
    spot_category: str | None, spot_code: str | None,
    perp_category: str | None, perp_code: str | None,
) -> tuple[str | None, str | None]:
    """Roll up two legs' error categories to one attempt-row ``(category, code)``
    by fixed priority (10-design §2(e)). Higher rank wins; a tie prefers spot.
    Returns ``(None, None)`` when neither leg carries a category. Pure read of
    leg rows — never changes control flow."""
    spot_rank = (
        ERROR_CATEGORY_ROLLUP_PRIORITY.get(spot_category, 0) if spot_category else 0
    )
    perp_rank = (
        ERROR_CATEGORY_ROLLUP_PRIORITY.get(perp_category, 0) if perp_category else 0
    )
    if perp_rank > spot_rank:
        return perp_category, perp_code
    if spot_rank > 0:
        return spot_category, spot_code
    if perp_rank > 0:
        return perp_category, perp_code
    return None, None


# Re-query cadence (ADR-003 / cadence-500ms task): the in-flight leg re-query
# interval defaults to 500ms so fills land sooner. MIN_INTERVAL_US is the floor
# clamped at the read site — a sub-floor misconfiguration can never turn the
# worker into a busy poll, and the settings display applies the same floor so
# the UI never asserts a value below what actually takes effect.
DEFAULT_INTERVAL_SECONDS = "0.5"
DEFAULT_INTERVAL_US = 500_000
MIN_INTERVAL_US = 50_000

# Per-leg in-memory order-detail query retry budget (fix-review1-retry-counter,
# Human decision 2026-08-02). Aligns the legacy JS ``getSpotOrderInfo(id, 10)``:
# the task-local worker asks each non-terminal leg up to LEG_QUERY_MAX_RETRIES
# times. A 404 / -2013 or a 5xx / timeout / malformed-2xx on a freshly POSTed
# leg is eventual-consistency noise, NOT a confirmed-absent signal — this
# mirrors the UM confirm path (``_confirm_um_figures``, whose docstring states a
# POST-just-accepted order 404-ing is noise, not absence). Below the cap both
# stay non-terminal and are re-queried; at the cap the LAST response decides: a
# 404 / -2013 confirms absent (terminal), while a still-inconclusive response
# escalates to manual recovery (never equated with absent — R2-F2). The counter
# is process-local (like the legacy JS loop): a restart resets it to zero and
# the budget is counted afresh. A leg at terminal state or a worker exit clears
# its counter, so the dict cannot grow without bound.
LEG_QUERY_MAX_RETRIES = 10

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
# Regular-spot endpoint (design §4): the standard spot account order path on
# api.binance.com. The leg row ``endpoint`` column carries whichever of this or
# SPOT_ORDER_PATH the resolved route chose; it is the SOLE authority for query +
# raw-response recording, never re-derived from leg name or task-level route.
REGULAR_SPOT_ORDER_PATH = "/api/v3/order"
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


def direction_to_leg_actions(
    direction: str, position_side_mode: str, task_type: str = TASK_TYPE_OPEN,
) -> LegActions:
    """Map a hedge direction + position-mode snapshot to per-leg order actions.

    forward: spot BUY + perp SELL (BOTH one-way / SHORT hedge).
    reverse: spot SELL + perp BUY (BOTH one-way / LONG hedge).
    ``task_type='close'`` 反转双腿方向（平仓）：forward 平仓 = 现货 SELL 卖回 +
    合约 BUY 平空；reverse 平仓 = 现货 BUY 买回 + 合约 SELL 平多。
    ``perp_position_side`` 不变（BOTH / LONG|SHORT 随持仓模式）。
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
    if task_type == TASK_TYPE_CLOSE:
        spot_side, perp_side = perp_side, spot_side  # 反转：卖回/买回
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
    # The spot leg normally uses ``coin``.  bStocks resolve to the public
    # B-suffix pair (for example TSLAUSDT -> TSLABUSDT); keep that resolved
    # symbol in the preflight result so the order path cannot fall back to the
    # futures symbol when building the margin request.
    spot_symbol: str | None = None
    # Regular-spot account route (design §3 step 4). The provider decides the
    # route from a FRESH restricted-asset read (positive funding only) plus the
    # resolved contract type, and records it here so compute_preflight + the
    # executor + the leg-row endpoint all follow ONE decision. Negative funding
    # is always ``papi_margin`` and never reads the list. ``spot_route_endpoint``
    # is the path the spot leg posts/queries (PAPI margin or /api/v3/order).
    spot_route: str = SPOT_ROUTE_PAPI_MARGIN
    spot_route_reason: str = ROUTE_REASON_PAPI_DEFAULT
    spot_route_endpoint: str = SPOT_ORDER_PATH
    # Standard Spot account facts for the regular_spot balance gate (design §3
    # step 5). ``spot_account_usdt`` is the available USDT free balance on the
    # STANDARD spot account (not PAPI crossMarginFree); ``spot_rate_limit_order``
    # is the standard spot order-rate limit. Both are None unless the route is
    # ``regular_spot`` (the provider reads them only on that path), and a None
    # here means the read was not performed — compute_preflight never guesses.
    spot_account_usdt: Decimal | None = None
    spot_rate_limit_order: int | None = None
    # Stage 2026-08-06 task 06 (close+forward 读错钱包修复): the STANDARD spot
    # account's free balance of the sellable base asset (e.g. THE for a
    # close+forward THE sell). The REVERSE branch of the balance gate sizes the
    # SELL against THIS wallet — the regular-spot route sells from the standard
    # spot account, not PAPI ``crossMarginFree`` (the two wallets are distinct).
    # None unless the route is ``regular_spot``; a None here means the read was
    # not performed (compute_preflight never guesses).
    spot_account_base_free: Decimal | None = None


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


def _require_task(task, fn_name: str) -> dict:
    """接口层守卫（symbol-identity-unification 测试 10）：身份取值只接受 task 字典。

    合约名 / 现货名 / 资产名三者都是裸字符串，传错既不报错也不崩，只会静默算出
    一个错答案——方案 §1.3 的类型混淆正是这样发生的（持仓面板把合约名喂给只剥
    USDT 的函数，于是 bStock 永远读不到余额）。守卫落在接口形状上：不是 dict 就
    当场 TypeError。
    """
    if not isinstance(task, dict):
        raise TypeError(
            f"{fn_name}() expects a task dict, got {type(task).__name__} "
            f"—— 现货腿身份必须取自任务的固化列，不能由裸 symbol 现算"
        )
    return task


def spot_symbol_of(task: dict) -> str:
    """任务的现货腿交易对（下单 / 查单 / 划转用）。

    优先读建任务时固化的 ``spot_symbol`` 列——它是该任务的历史真值，平仓必须
    用开仓时的身份（方案 §2.1）。列为空只发生在回填前的旧行，此时回退查表。
    """
    task = _require_task(task, "spot_symbol_of")
    frozen = task.get("spot_symbol")
    if isinstance(frozen, str) and frozen:
        return frozen
    return resolve_spot_identity(task["coin"])[0]


def spot_base_of(task: dict) -> str:
    """任务的现货资产名（余额 / 利息 / 借币记账用），如 bStock 的 ``SNXXB``。

    与 :func:`spot_symbol_of` 同源同策略：固化列优先，旧行回退查表。
    """
    task = _require_task(task, "spot_base_of")
    frozen = task.get("spot_base_asset")
    if isinstance(frozen, str) and frozen:
        return frozen
    return resolve_spot_identity(task["coin"])[1]


def identity_drift(task: dict) -> dict | None:
    """任务固化的现货身份与当前查表结果不一致时返回差异，否则 ``None``（方案 D3）。

    这是**只报不拦**的一致性信号：固化值才是该任务的历史真值，平仓必须用开仓时
    的身份，绝不因表更新而静默切换（那会让两条腿对不上）。它的用途是让「映射表
    变动影响到存量任务」尽早可见，与 ``check-spot-symbol-map.py --verify`` 的
    STALE 一起构成表变动的两侧告警。

    未固化的旧行返回 ``None``——回退查表本就等于当前值，不构成漂移。
    """
    task = _require_task(task, "identity_drift")
    frozen = task.get("spot_symbol")
    if not (isinstance(frozen, str) and frozen):
        return None
    current = resolve_spot_identity(task["coin"])[0]
    if frozen == current:
        return None
    return {"coin": task["coin"], "frozen": frozen, "current": current}


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


def decide_spot_route(
    direction: str,
    contract_type: str,
    spot_base_asset: str | None,
    cap_exceeded: bool | None,
    task_type: str = TASK_TYPE_OPEN,
) -> tuple:
    """Pure spot-leg route decision (design §3 step 4 + 平仓现货卖出重设计).

    Returns ``(route, reason)``:

    * ``task_type='close'``（平仓，Human 已拍板）：
      - close + forward（平仓卖现货）→ ``(regular_spot, close_sell_regular_spot)``
        固定普通现货账户——**不再走 collateral-cap 预检**（cap 只对买入有意义；
        卖出在普通账户是唯一出口，根治 COOKIEUSDT -2010 事故）；
      - close + reverse（平仓买现货还币）→ ``(papi_margin, papi_default)``
        统一杠杆账户（与开仓 reverse 一致）。
    * ``task_type='open'``（开仓，行为逐字不变）：
      - negative funding (``reverse`` / spot SELL) -> ``(papi_margin, papi_default)``.
        The restricted-asset list is NOT consulted and ``regular_spot`` is never
        selected, even when the asset would hit the list or is a bStock (decision
        §E-1). The provider therefore never reads the list for this direction.
      - positive funding (``forward`` / spot BUY):
        - ``cap_exceeded is True`` (the resolved spot base asset is on the platform
          collateral-cap list) -> ``(regular_spot, collateral_cap_precheck)``;
        - else ``contract_type == "TRADIFI_PERPETUAL"`` (bStock) ->
          ``(regular_spot, tradifi_regular_spot)``;
        - else -> ``(papi_margin, papi_default)``.

    ``cap_exceeded`` is ``True``/``False`` for a fresh successful list read and
    ``None`` only when the read could not be completed — the caller MUST treat
    ``None`` on a forward open direction as preflight-incomplete (never guess a
    route); close+forward 不再读取 cap 列表。``spot_base_asset`` is carried for
    API symmetry / future auditing; the cap-membership decision itself is made
    by the caller (the matched asset is the resolved spot base, e.g. ``TSLAB``
    for a bStock — never the contract base).
    """
    if task_type == TASK_TYPE_CLOSE:
        if direction == DIR_FORWARD:
            return SPOT_ROUTE_REGULAR_SPOT, ROUTE_REASON_CLOSE_SELL_REGULAR
        return SPOT_ROUTE_PAPI_MARGIN, ROUTE_REASON_PAPI_DEFAULT
    if direction != DIR_FORWARD:
        return SPOT_ROUTE_PAPI_MARGIN, ROUTE_REASON_PAPI_DEFAULT
    if cap_exceeded is True:
        return SPOT_ROUTE_REGULAR_SPOT, ROUTE_REASON_COLLATERAL_CAP_PRECHECK
    if contract_type == "TRADIFI_PERPETUAL":
        return SPOT_ROUTE_REGULAR_SPOT, ROUTE_REASON_TRADIFI_REGULAR_SPOT
    return SPOT_ROUTE_PAPI_MARGIN, ROUTE_REASON_PAPI_DEFAULT


def spot_route_endpoint(route: str) -> str:
    """The spot leg's POST/GET endpoint path for a route (design §4). The leg
    row ``endpoint`` column carries this verbatim; query + raw-response recording
    read it from the leg row, never from leg name or task-level route."""
    if route == SPOT_ROUTE_REGULAR_SPOT:
        return REGULAR_SPOT_ORDER_PATH
    return SPOT_ORDER_PATH


def build_regular_spot_order_params(
    coin: str, actions: LegActions, quantity: Decimal, client_order_id: str
) -> dict:
    """The exact signed-body params for POST /api/v3/order — the regular-spot
    account leg (design §4). Same shape as the PAPI margin spot builder MINUS
    ``sideEffectType``: a standard spot order is not a margin borrow/repay, so the
    PAPI-only ``sideEffectType=NO_SIDE_EFFECT`` must NOT be sent (sending it to
    /api/v3/order is an unknown parameter). Defined here (pure vocabulary) so the
    service's durable request_shape record and the live executor's actual POST
    share ONE shape definition. The PAPI margin spot shape
    (:func:`backend.hedge_open_tasks.executor.build_spot_order_params`) keeps
    ``sideEffectType``; the two are deliberately distinct so a route mistake shows
    up as a wrong key, not a silent borrow."""
    return {
        "symbol": coin,
        "side": actions.spot_side,
        "type": ORDER_TYPE_MARKET,
        "quantity": fmt_decimal(quantity),
        "newClientOrderId": client_order_id,
        "newOrderRespType": ORDER_RESP_RESULT,
    }


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
    # are fatal rather than a fail-closed exit (stage 2026-08-06 task 05 §5).
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
    # S5 (ADR-H4): each leg's effective MARKET qty bounds (min/max), read with
    # the same per-constraint MARKET_LOT_SIZE -> LOT_SIZE fallback as the step
    # (_qty_bounds), recorded so the dry-run record transport can reject a
    # quantity that violates the symbol's loaded grid/bounds OFFLINE instead of
    # simulating it as a fill. ``None`` == that bound is disabled on this symbol.
    spot_min, spot_max = _qty_bounds(snapshot.spot_filters)
    perp_min, perp_max = _qty_bounds(snapshot.perp_filters)
    snapshot_record = {
        "available": True,
        "spot_step": str(spot_step),
        "perp_step": str(perp_step),
        "spot_min_qty": str(spot_min) if spot_min is not None else None,
        "spot_max_qty": str(spot_max) if spot_max is not None else None,
        "perp_min_qty": str(perp_min) if perp_min is not None else None,
        "perp_max_qty": str(perp_max) if perp_max is not None else None,
        "grid": str(grid),
        "est_price": str(snapshot.est_price) if snapshot.est_price is not None else None,
        "position_mode": snapshot.position_mode,
    }
    # 2026-08-07 身份统一：现货腿 symbol 不再写进预检快照。它是任务的第一等属性
    # （hedge_open_task.spot_symbol，建任务时固化），由 spot_symbol_of(task) 读取。
    # 保留两份会重新回到「多份真相」，正是本次改造要消除的（方案 §3② P3）。
    # Record the resolved spot account route (design §3 step 4) on the immutable
    # preflight fingerprint so the executor, the leg-row endpoint and the audit
    # trail all follow ONE decision. ``spot_route`` is papi_margin | regular_spot;
    # ``spot_endpoint`` is the path the spot leg posts/queries.
    snapshot_record["spot_route"] = snapshot.spot_route
    snapshot_record["spot_route_reason"] = snapshot.spot_route_reason
    snapshot_record["spot_endpoint"] = snapshot.spot_route_endpoint
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
    # Balance gate (ADR-3): forward needs USDT >= q*N*price; reverse needs base
    # >= q*N. maxBorrowable is never sellable. est_price is guaranteed present
    # and positive by the direction-independent check above, so the forward USDT
    # need can always be sized.
    #
    # Route-aware (design §3 steps 5–6): a positive-funding ``regular_spot`` route
    # sizes the USDT need against the STANDARD spot account free USDT
    # (``spot_account_usdt``), NOT PAPI ``crossMarginFree`` — the two wallets are
    # distinct and PAPI's crossMarginFree cannot answer what the regular spot
    # account can buy. Every other path (papi_margin forward USDT, reverse base)
    # keeps the PAPI balance read. The provider already fail-closed the snapshot
    # (returned None) when a regular_spot account/rate-limit read failed, so a
    # non-None snapshot here carries the figure; a shortfall is a readable
    # insufficient-balance fact distinct from a read failure.
    #
    # Stage 2026-08-06 task 06: the REVERSE branch (SELL direction) is symmetric
    # — a ``regular_spot`` route (the ONLY entry is close+forward selling into
    # the standard spot account) sizes the base need against the standard spot
    # account's free base (``spot_account_base_free``), not PAPI
    # ``crossMarginFree``. Every other reverse path (reverse open / close+reverse
    # buy, both papi_margin) keeps ``balances`` verbatim.
    base = base_asset(coin)
    if direction == DIR_FORWARD:
        required = q_common * target_n * snapshot.est_price
        if snapshot.spot_route == SPOT_ROUTE_REGULAR_SPOT:
            available = snapshot.spot_account_usdt or Decimal(0)
        else:
            available = snapshot.balances.get(QUOTE_ASSET, Decimal(0))
    else:
        required = q_common * target_n
        if snapshot.spot_route == SPOT_ROUTE_REGULAR_SPOT:
            available = snapshot.spot_account_base_free or Decimal(0)
        else:
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

    Backstop (10-design §4(a)): a non-positive ``ts_us`` is always a programming
    error — the exposure timestamp is the wall clock at settlement, never the
    1970 epoch a forgotten ``0`` would render. Fail loudly (into the worker's
    exception containment; the task is manually recoverable) rather than emit a
    timestamp indistinguishable from a real one.
    """
    if ts_us <= 0:
        raise invalid_field("ts_us", "exposure timestamp must be positive (wall clock at settlement)")
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


def validate_task_type(value) -> str:
    if value not in ALL_TASK_TYPES:
        raise invalid_field("task_type", f"must be one of {', '.join(ALL_TASK_TYPES)}")
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
    PAUSE_REASON_ORDER_STATE_UNKNOWN: "订单状态经 10 次重试查询仍不明，无法确认是否已被交易所接受，任务已暂停。请到交易所核对订单后手动恢复（恢复后仅按既有 clientOrderId 重查，不重发下单）",
    PAUSE_REASON_CLOSE_VERIFY_FAILED: "平仓完成核实失败（查交易所合约持仓未成功），任务已暂停。请到交易所核对该币种合约仓位后手动恢复——「查不到」绝不视为「已平完」",
    PAUSE_REASON_CLOSE_SPOT_BALANCE: "平仓现货余额检查/划转失败，任务已暂停（fail-closed，未发单）。详情见任务卡日志，请人工核对后手动恢复",
    PAUSE_REASON_LEVERAGE_SET_FAILED: "设置合约杠杆失败，任务已暂停（fail-closed，未发单）。详情见任务卡日志，请人工核对后手动恢复",
    PAUSE_REASON_PREFLIGHT_INCOMPLETE: "预检数据不完整，任务已暂停（fail-closed，未发单）；请检查网络后手动恢复",
}

# 51169 operator message — FROZEN verbatim (10-design §2(d) / ADR-T3). Only the
# {asset} placeholder is filled at pause time with the leg's base asset. This is
# the pause_reason_zh for PAUSE_REASON_COLLATERAL_CAP_FULL; it must NOT be
# reworded, and it must never be replaced by the insufficient_margin wording
# (which would assert the false "保证金不足" the collateral cap is not).
COLLATERAL_CAP_FULL_REASON_ZH_TEMPLATE = (
    "{asset} 已达币安平台级抵押金额上限（该上限为全平台所有用户共享，并非本"
    "账户保证金不足，追加资金无效）。现货腿当前无法买入保证金账户，可更换"
    "其他币种或稍后重试；若该币上限占用未满 100%，调小金额也可能成功。"
)


def collateral_cap_pause_reason_zh(asset: str) -> str:
    """The frozen 51169 operator message with its ``{asset}`` placeholder filled
    (10-design §2(d)). ``asset`` is the base asset of the blocked coin (NOM for
    NOMUSDT). Verbatim contract — callers must not reword the result."""
    return COLLATERAL_CAP_FULL_REASON_ZH_TEMPLATE.format(asset=asset)


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


# ------------------------------------------------------------------
# Position merge (Task 1 / D14): join aggregate_positions buckets with the
# snapshot's private_account so /api/hedge-open-positions returns one merged
# row per UM symbol (the real exchange position is the skeleton) with
# task-record cost, spot/borrow, unrealized PnL, and position-level markers.
# Pure: no service refs, no I/O — the HTTP handler (server.py) supplies both
# inputs (10-design.md P1 / N1-N5, 11-adr.md ADR-001).
# ------------------------------------------------------------------

def _merge_base_asset(symbol):
    """Strip the USDT quote suffix to get the base asset for spot/borrow matching.

    Does NOT strip the 1000x multiplier prefix (BONK/FLOKI/LUNC/PEPE/SHIB/XEC):
    ``1000PEPEUSDT`` -> ``1000PEPE`` will not equal the spot asset ``PEPE``, which
    is the honest 'no automatic alignment' outcome for those six (non-goal #5 /
    02-scope-decisions.md §2.3)."""
    if not isinstance(symbol, str) or not symbol:
        return None
    return symbol[:-4] if symbol.endswith("USDT") and len(symbol) > 4 else symbol


def _merge_num(value):
    """Parse a wire decimal string to Decimal, or ``None`` (never a coerced 0)."""
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _merge_side_for_direction(direction):
    # forward = buy spot + open SHORT perp; reverse = sell spot + open LONG perp.
    if direction == DIR_FORWARD:
        return "SHORT"
    if direction == DIR_REVERSE:
        return "LONG"
    return None


def _merge_direction_for_side(side):
    if side == "SHORT":
        return DIR_FORWARD
    if side == "LONG":
        return DIR_REVERSE
    return None


def _merge_empty_bucket_row(coin, direction):
    """A merged row's bucket-side defaults when only the UM side exists (no task
    record for this symbol — fake scenario 'no_task').

    G2 (fix-merged-positions-mismatch-labels-v1): there is NO local bookkeeping
    for this symbol, so its cost-basis fields are unknown (``None``), not ``"0"``.
    A ``"0"`` rendered as a real figure reads as "filled at price 0" — a fake
    cost indistinguishable from a real zero (the money-zero family this stage
    keeps closing). The UI renders ``None`` as ``—`` (P7 'unavailable'). The P7
    'no source' placeholders (accrued_funding / borrow_interest / net_pnl) stay
    ``"0"`` because the UI maps them to 「暂无」 via pendingCell, not to a cost."""
    return {
        "coin": coin,
        "direction": direction,
        "position_qty": None,
        "spot_qty": None,
        "perp_qty": None,
        "spot_avg": None,
        "perp_avg": None,
        "spot_avg_price_incomplete": False,
        "perp_avg_price_incomplete": False,
        "includes_deleted_task": False,
        "open_basis_rate": "0",
        "price_pnl": "0",
        "accrued_funding": "0",
        "borrow_interest": "0",
        "net_pnl": "0",
        # 持仓周期（设计 v1 §5.2）：no_task 行无本地账本，周期字段为 None。
        "cycle_id": None,
        "cycle_opened_at": None,
        "cycle_closed_at": None,
    }


def _merge_build_row(coin, direction, bucket, um, spot_by_asset,
                     spot_value_by_asset, unified_row_by_asset, asset_map=None):
    """Build one merged row: bucket fields + matched UM position + the four
    account-derived balance fields (v4.1 §9.2) + unrealized PnL + the
    single-leg / drift markers.

    The four account fields are pure projections of the SAME published
    ``private_account`` rows, looked up by the row's base asset. The base asset
    comes from the composition root's ``asset_map`` ({coin: spot base asset} —
    the snapshot rows' resolved spot ``base_asset``, the single-point truth of
    ``resolve_spot_leg``: ``TSLAB`` for bStock ``TSLAUSDT``, ``BONK`` for
    ``1000BONKUSDT``) when present; otherwise it falls back to the
    ``_merge_base_asset`` rule (which only strips the USDT quote suffix —
    1000x assets do NOT auto-align without the map, by design).
    ``spot_balance`` (free+locked), ``spot_balance_value_usdt`` (that spot row's
    existing ``value_usdt``), ``unified_balance`` (the unified row's
    ``total_balance`` — the full-cross leveraged balance, NOT the borrow), and
    ``unified_balance_value_usdt`` (that unified row's existing ``value_usdt``).
    ``cross_margin_borrowed`` stays borrow-only. No price is recomputed and the
    source snapshot is never mutated; null vs a real decimal-string zero is
    preserved on both sides independently (a missing asset on one side leaves
    only that side's amount/value null).
    """
    row = dict(bucket) if bucket else _merge_empty_bucket_row(coin, direction)
    if coin is not None:
        row["coin"] = coin
    if direction is not None:
        row["direction"] = direction

    if um is not None:
        row["um_position_side"] = um.get("position_side")
        row["um_position_amt"] = um.get("position_amt")
        row["um_notional_usdt"] = um.get("notional_usdt")
        row["um_entry_price"] = um.get("entry_price")
        row["um_mark_price"] = um.get("mark_price")
        row["um_liquidation_price"] = um.get("liquidation_price")
        # P7: unrealized PnL has a real source — surface it and overlay the "0"
        # placeholder so the UI renders a true figure, not 0.00.
        upnl = um.get("unrealized_profit")
        row["unrealized_profit"] = upnl
        # R2 (fix-merged-positions-n2-ui-v1): a missing/unparseable upnl must NOT
        # masquerade as the bucket's "0" placeholder. Surface the real figure
        # (including a true "0") only when it is parseable; otherwise price_pnl is
        # None so the UI renders 暂无 and a real 0 stays distinguishable from missing.
        row["price_pnl"] = upnl if _merge_num(upnl) is not None else None
    else:
        row["um_position_side"] = None
        row["um_position_amt"] = None
        row["um_notional_usdt"] = None
        row["um_entry_price"] = None
        row["um_mark_price"] = None
        row["um_liquidation_price"] = None
        row["unrealized_profit"] = None

    base_asset = (asset_map or {}).get(row.get("coin")) or _merge_base_asset(row.get("coin"))
    real_spot = spot_by_asset.get(base_asset) if base_asset else None
    row["spot_balance"] = fmt_decimal(real_spot) if real_spot is not None else None
    row["spot_balance_value_usdt"] = (
        spot_value_by_asset.get(base_asset) if base_asset else None
    )
    unified_row = unified_row_by_asset.get(base_asset) if base_asset else None
    row["unified_balance"] = (
        unified_row.get("total_balance") if unified_row else None
    )
    row["unified_balance_value_usdt"] = (
        unified_row.get("value_usdt") if unified_row else None
    )
    row["cross_margin_borrowed"] = (
        unified_row.get("cross_margin_borrowed") if unified_row else None
    )

    # single_leg_exposure: the task filled its spot leg but not its perp leg
    # (one orderId) — a real naked-spot exposure. Derived from the task bucket
    # (spot_qty>0, perp_qty==0), not re-derived on the frontend.
    spot_qty = _merge_num(row.get("spot_qty")) or Decimal(0)
    perp_qty = _merge_num(row.get("perp_qty")) or Decimal(0)
    row["single_leg_exposure"] = bucket is not None and spot_qty > 0 and perp_qty == 0

    # drift: the real spot balance is LESS than the task-record accumulation —
    # the operator manually reduced the hedge's spot leg (P2). Only the
    # risk-relevant direction is flagged (real < recorded); no auto-action.
    recorded_spot = _merge_num(row.get("spot_qty"))
    row["drift"] = (
        recorded_spot is not None
        and recorded_spot > 0
        and real_spot is not None
        and real_spot < recorded_spot
    )

    # G1 (fix-merged-positions-mismatch-labels-v1): an explicit match-status so
    # the UI never has to infer 'no task record' / 'no UM position' from
    # all-zero fields — that inference is exactly the ambiguity this stage kept
    # tripping on. The merge layer is the one place that knows BOTH sides.
    #   normal  : UM position + task bucket both present
    #   no_task : UM position but no task record (manual order / card deleted)
    #   no_um   : task record but no UM position (possibly liquidated / closed)
    if um is not None and bucket is not None:
        row["match_status"] = "normal"
    elif um is not None and bucket is None:
        row["match_status"] = "no_task"
    elif um is None and bucket is not None:
        row["match_status"] = "no_um"
    else:
        row["match_status"] = "normal"
    return row


def merge_positions(positions, private_account, asset_map=None):
    """Merge task-record position buckets with the snapshot's private_account.

    ``positions`` is the list from :func:`HedgeOpenStore.aggregate_positions`
    (buckets keyed by ``(coin, direction)``). ``private_account`` is the snapshot
    block (``verified``, ``um_positions``, ``balances_unified``, ``balances_spot``,
    ``checked_at``, ``error``) or ``None`` when the account snapshot is not ready
    or not verified.

    Returns ``(merged_rows, account_meta)``. The UM positions are the skeleton
    (one row per real exchange position); task buckets with no matching UM
    position are appended as 'no_um' rows so their cost basis stays visible (D15).
    Each row keeps the bucket fields and adds the matched UM position, the four
    account-derived balance fields (v4.1 §9.2: ``spot_balance`` /
    ``spot_balance_value_usdt`` / ``unified_balance`` /
    ``unified_balance_value_usdt``), cross-margin borrow, unrealized PnL, and the
    ``single_leg_exposure`` / ``drift`` markers. ``account_meta`` reports
    availability so the caller never has to 503 on a cold account (N2): when
    ``private_account`` is ``None`` or ``verified`` is false the local
    bookkeeping rows are still returned with the account-derived fields nulled.

    Pure: takes plain dicts, returns plain dicts, holds no service reference and
    performs no I/O — directly unit-testable.

    ``asset_map`` (optional) is ``{coin: spot base asset}`` built by the
    composition root from the snapshot rows' resolved spot ``base_asset`` — the
    single-point truth of ``resolve_spot_leg`` (``SNXXB`` for bStock
    ``SNXXUSDT``, ``BONK`` for ``1000BONKUSDT``). When it is absent or lacks the
    coin, the merge falls back to the local ``_merge_base_asset`` rule (only
    strips the USDT quote suffix), preserving today's behaviour for a cold
    snapshot / tests.
    """
    pa = private_account or {}
    verified = bool(pa.get("verified"))
    um_positions = pa.get("um_positions") if verified else None
    unified = pa.get("balances_unified") if verified else None
    spot = pa.get("balances_spot") if verified else None
    account_meta = {
        "verified": verified,
        "error": None if verified else (pa.get("error") or "snapshot_not_ready"),
        "checked_at": pa.get("checked_at"),
    }

    spot_by_asset = {}
    spot_value_by_asset = {}
    for row in spot or []:
        if isinstance(row, dict) and row.get("asset"):
            free = _merge_num(row.get("free")) or Decimal(0)
            locked = _merge_num(row.get("locked")) or Decimal(0)
            spot_by_asset[row["asset"]] = free + locked
            # v4.1 §9.2: the same spot balance row's existing value_usdt, passed
            # through verbatim (null vs a real "0.00000000" preserved — no
            # recompute, no coercion).
            spot_value_by_asset[row["asset"]] = row.get("value_usdt")
    # v4.1 §9.2: keep the whole unified balance row per asset so one lookup
    # yields total_balance (the full-cross leveraged balance, NOT the borrow),
    # its value_usdt, and cross_margin_borrowed (which stays borrow-only).
    unified_row_by_asset = {}
    for row in unified or []:
        if isinstance(row, dict) and row.get("asset"):
            unified_row_by_asset[row["asset"]] = row

    # P0-1（设计 v1 §5.4）：桶键与匹配都以周期为粒度。同一 (coin, direction)
    # 存在多个周期桶（场景 B：全平再开）时，二元组 setdefault 会静默丢弃其余
    # 周期桶、matched 也会连带跳过同键所有桶——必须按桶身份记账，不丢任何周期。
    merged = []
    matched_buckets = set()

    # 1. UM skeleton rows (the real exchange positions). 只匹配「活跃周期」桶
    #    （cycle_closed_at 为 null）；同键多个活跃周期（异常）取最近 opened 者，
    #    其余按未匹配处理（step 2 各自独立 no_um 输出）。
    for u in um_positions or []:
        if not isinstance(u, dict):
            continue
        symbol = u.get("symbol")
        direction = _merge_direction_for_side(u.get("position_side"))
        bucket = None
        if direction is not None and symbol is not None:
            active = [
                p for p in positions or []
                if p.get("coin") == symbol and p.get("direction") == direction
                and p.get("cycle_closed_at") is None
            ]
            if active:
                bucket = max(
                    active, key=lambda p: p.get("cycle_opened_at") or "",
                )
                matched_buckets.add(
                    (symbol, direction, bucket.get("cycle_id"))
                )
        merged.append(
            _merge_build_row(
                symbol, direction, bucket, u, spot_by_asset,
                spot_value_by_asset, unified_row_by_asset, asset_map,
            )
        )

    # 2. 未被 UM 骨架消费的周期桶各自作为独立 no_um 行输出——已平仓周期行带
    #    cycle_closed_at（标「已平仓」）、无对应交易所仓位的活跃周期行照常展示；
    #    不合并、不丢弃（D15 精神从「币种行」细化为「周期行」）。
    for p in positions or []:
        key = (p.get("coin"), p.get("direction"), p.get("cycle_id"))
        if key in matched_buckets:
            continue
        merged.append(
            _merge_build_row(
                p.get("coin"), p.get("direction"), p, None, spot_by_asset,
                spot_value_by_asset, unified_row_by_asset, asset_map,
            )
        )

    merged.sort(
        key=lambda r: (
            (r.get("coin") or ""), (r.get("direction") or ""),
            (r.get("cycle_opened_at") or ""),
        )
    )
    return merged, account_meta
