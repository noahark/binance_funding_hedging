"""Hedge-open task service — HTTP-facing orchestration over store + executor.

The service is the single hedge-open authority. It owns the store, the executor,
the preflight provider, the scheduler thread and the durable global Start gate,
and exposes the local same-origin API methods consumed by
``backend/app/server.py``. Handlers delegate here only; they never touch SQL or
the executor directly (mirror of borrow_tasks §3.10).

Safety posture (ADR-4 / breakdown §3.7): the default executor is the dry-run
record transport (no network POST); a real POST is reachable only under
``APP_HEDGE_EXECUTOR=live`` AND the durable Start gate AND a fresh passing
preflight, AND only through an injected :class:`LiveHedgeExecutor` (constructed
under ``backend/services/``; never imported by this package). The scheduler's
automatic tick respects the Start gate; explicit ``fill-once``/``fill-all`` are
operator manual triggers of the record transport and are not Start-gated (they
never POST in record mode; live ``fill-all`` is prohibited from synchronous POST
and merely arms the task — breakdown §3.8).
"""
from __future__ import annotations

import json
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Callable, Protocol

from ..domain.normalize import SPOT_MATCH_MULTIPLIER, resolve_spot_identity
from . import domain as D
from .executor import (
    AttemptContext,
    AttemptOutcome,
    DisabledHedgeExecutor,
    HedgeExecutor,
    _client_order_ids,
    build_perp_order_params,
    build_spot_order_params,
)
from .scheduler import HedgeOpenScheduler
from .store import HedgeOpenStore, UnknownTaskError


_CREATE_BODY_KEYS = (
    "coin", "direction", "mode", "single_amount", "target_n", "task_type",
    "slippage_threshold_pct",
)


def _leg_query_symbol(leg: dict, task: dict) -> str:
    """Use the immutable symbol recorded for this leg when reconciling it.

    The request shape is persisted before the POST, so it is the authoritative
    symbol for a non-terminal order even if a later public refresh resolves the
    market differently.  The task preflight is the fallback for legacy rows.
    """
    coin = task["coin"]
    if leg.get("leg") != "spot":
        return coin
    shape = leg.get("request_shape")
    if isinstance(shape, str):
        try:
            shape = json.loads(shape)
        except (TypeError, json.JSONDecodeError):
            shape = None
    if isinstance(shape, dict):
        symbol = shape.get("symbol")
        if isinstance(symbol, str) and symbol:
            return symbol
    return D.spot_symbol_of(task)

# S3 (ADR-H2): the start-gate write body. ``confirm`` must be the literal true;
# ``version`` is the CAS guard; ``enabled`` carries both the open and close
# directions on one endpoint.
_START_GATE_BODY_KEYS = ("enabled", "confirm", "version")

# Amendment 21 removed the process-wide rate-limit cooldown: a 429 / -1003 / 418
# surfaced by a live leg now pauses ONLY the task whose worker observed it (the
# worker exits and the operator manually recovers), and never delays, pauses,
# stops, counts, or blocks another task. There is no global cooldown state.

# Task-level lifecycle events surfaced on the additive ``entries`` timeline
# (amendment §5): a fatal stop, a consecutive-failure threshold pause, a
# fail-closed preflight exit/pause (the worker exits WITHOUT retry; the task
# pauses with a Chinese reason — stage 2026-08-06 task 05 §5), and a shared
# 429/Retry-After write delay. These
# share the ``hedge_open_log`` table (attempt_id NULL); an attempt's own row
# projects separately with ``kind="attempt"``.
_ENTRY_EVENT_KINDS = (
    "task_stopped",
    "threshold_paused",
    "task_paused",
    "order_state_unknown_final",
    "preflight_incomplete",
    "rate_limited",
)

# Unified-stream source ranks for the additive ``entries`` timeline (amendment
# 17): the attempt and task-event tables have INDEPENDENT ``id`` autoincrement
# sequences, so a fixed rank disambiguates them inside the stable
# ``(ts_us, rank, id)`` sort key. DESC order: at equal ts a rank-1 event
# precedes a rank-0 attempt (a deterministic same-ts tie-break, never a clash).
_ENTRY_ATTEMPT_RANK = 0
_ENTRY_EVENT_RANK = 1


def _real_mono_us() -> int:
    return int(time.monotonic() * 1_000_000)


def _real_wall_us() -> int:
    return int(time.time() * 1_000_000)


@dataclass(frozen=True)
class _FreshPreflight:
    """Resolved fresh preflight for one dispatch (A-2). ``ok`` means the pair may
    proceed with this exact ``q_common``/snapshot; ``fatal`` means a fatal fact
    stops the task (amendment rows 1–2); a ``None`` result from the resolver
    means an incomplete read -> fail-closed exit (worker exits WITHOUT retry and
    the task pauses — stage 2026-08-06 task 05 §5)."""

    q_common: Decimal | None
    position_side_mode: str | None
    snapshot_record: dict
    rejection: str | None
    ok: bool
    fatal: bool
    stop_reason: str | None


class PreflightProvider(Protocol):
    """Read-only preflight data source (10-design §5). Injected; the default
    returns ``None`` (dry-run, no network read). A live provider assembles a
    fresh snapshot from public filters + signed PM reads immediately before send.

    ``direction`` drives the regular-spot route decision (design §3 step 4): a
    forward (positive-funding) direction may select ``regular_spot`` from a fresh
    collateral-cap list read; a reverse direction never reads the list.
    """

    def get_snapshot(
        self, coin: str, direction: str, task_type: str = "open",
        position_side_mode: str | None = None,
    ) -> D.PreflightSnapshot | None: ...


class DisabledPreflightProvider:
    """The default provider: no preflight data (dry-run, no network read)."""

    def get_snapshot(
        self, coin: str, direction: str, task_type: str = "open",
        position_side_mode: str | None = None,
    ) -> D.PreflightSnapshot | None:
        return None


class _GateWake:
    def __init__(self) -> None:
        self.condition = threading.Condition()
        self.version = 0


# ---------------------------------------------------------------------------
# Document serialization (frozen field names, breakdown §3.2-§3.4)
# ---------------------------------------------------------------------------


def task_to_doc(task: dict, *, worker_active: bool | None = None) -> dict:
    q_common = task["q_common"]
    gate_started = task.get("smooth_gate_started_at_us")
    gate_seq = task.get("smooth_gate_seq")
    gate_forced = bool(task.get("smooth_gate_force_requested"))
    # smooth-close C17：备料状态是 q_common 是否有值的**派生**展示字段（不落
    # 库、不新增列、无第二处真相）。open 任务无此概念（None）；immediate
    # close 每轮实时校验（行为不变）；smooth close 已备料/未备料。前端
    # P2 据此接线：prepared=已备料 / unprepared=未备料 / realtime_per_round=
    # 每轮实时校验。
    task_type = task.get("task_type") or D.TASK_TYPE_OPEN
    if task_type != D.TASK_TYPE_CLOSE:
        close_preparation_state = None
    elif task.get("mode") == D.MODE_SMOOTH:
        close_preparation_state = "prepared" if q_common else "unprepared"
    else:
        close_preparation_state = "realtime_per_round"
    return {
        "id": task["id"],
        "coin": task["coin"],
        "direction": task["direction"],
        "mode": task["mode"],
        "single_amount": task["single_amount"],
        "target_n": task["target_n"],
        "success_count": task["success_count"],
        "fail_count": task["fail_count"],
        "status": task["status"],
        "q_common": q_common,
        "position_side_mode": task["position_side_mode"],
        # leg_exposure stays for backward-compat rendering; it is advisory only
        # (§4.5) and never a scheduler gate.
        "leg_exposure": task["leg_exposure"],
        # Real-API attempt/acceptance/pause counters (breakdown §3.4).
        "scheduled_attempt_count": task["scheduled_attempt_count"],
        "accepted_pair_count": task["accepted_pair_count"],
        "consecutive_submission_failures": task["consecutive_submission_failures"],
        "failure_pause_threshold": task["failure_pause_threshold"],
        "pause_reason": task["pause_reason"],
        # 功能三（2026-08）：任务类型（'open'=开仓 / 'close'=平仓）。
        "task_type": task.get("task_type") or D.TASK_TYPE_OPEN,
        # Amendment 21: the safe Chinese cause of a task-local pause (429 /
        # insufficient balance/margin/available-qty) alongside status=paused.
        "pause_reason_zh": task["pause_reason_zh"],
        # Amendment additive (I-4): a fatal stop's reason alongside status=stopped.
        "stop_reason": task["stop_reason"],
        # Review-1 r3 P2-2 (backend-authoritative observability; frontend display
        # is a follow-up). worker_active is a derived tri-state: True/False while a
        # live worker owns the task, None in dry-run (not applicable). The exit
        # reason is the stable machine enum last written by the worker's own exit
        # branch / error path, cleared on (re-)entering RUNNING.
        "worker_active": worker_active,
        "last_worker_exit_reason": task.get("last_worker_exit_reason"),
        "slippage_threshold_pct": task.get("slippage_threshold_pct"),
        "smooth_gate_seq": gate_seq,
        "smooth_gate_started_at_us": gate_started,
        "smooth_gate_deadline_at_us": (
            gate_started + D.SMOOTH_GATE_WINDOW_US if gate_started is not None else None
        ),
        "smooth_gate_force_requested": gate_forced,
        "smooth_gate_state": (
            "none" if gate_seq is None else ("forced" if gate_forced else "waiting")
        ),
        "close_preparation_state": close_preparation_state,
        "created_at": D.us_to_iso(task["created_at_us"]),
        "updated_at": D.us_to_iso(task["updated_at_us"]),
    }


def fill_to_doc(fill: dict) -> dict:
    return {
        "id": fill["id"],
        "task_id": fill["task_id"],
        "ts": D.us_to_iso(fill["ts_us"]),
        "attempt_id": fill["attempt_id"],
        "spot": fill["spot"],
        "perp": fill["perp"],
    }


def _interval_seconds_doc(interval_us) -> float:
    """The cadence the UI prints, in seconds (ADR-003). Sub-second aware, so a
    500ms cadence renders as 0.5 rather than the 0 the old integer division
    produced.

    The argument is ignored: since 2026-08-02 the cadence has a single source of
    truth (``D.DEFAULT_INTERVAL_US`` via ``store.get_interval_us``), so the UI
    must print the value the worker actually honours — never whatever a database
    row happens to hold. Kept as a parameter so callers need not change."""
    return round(max(int(D.DEFAULT_INTERVAL_US), D.MIN_INTERVAL_US) / 1_000_000, 3)


def settings_to_doc(settings: dict, executor_mode: str) -> dict:
    return {
        "executor_mode": executor_mode,
        "start_gate": bool(settings["start_gate"]),
        "interval_seconds": _interval_seconds_doc(settings["interval_us"]),
        # Additive (S3 / ADR-H2): the settings row's version — the CAS input a
        # concurrency-safe start-gate write must echo back. Existing field names
        # and semantics are unchanged.
        "version": int(settings["version"]),
        # 功能三：平仓闸门（独立于开单闸门，默认开；CAS 写见 put_close_gate）。
        "close_gate": bool(settings["close_gate"]),
    }


def log_to_doc(row: dict) -> dict:
    # The record-transport payload is stored as JSON text; surface it as a
    # parsed object so the wire shape is a structured record, not a stringified
    # blob (consistent with get_log_payload, which also parses).
    raw_payload = row["payload"]
    try:
        payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
    except (TypeError, ValueError):
        payload = raw_payload
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "ts": D.us_to_iso(row["ts_us"]),
        "attempt_id": row["attempt_id"],
        "kind": row["kind"],
        "payload": payload,
    }


def _resolve_avg_price(leg: dict, local_avg: str | None) -> str | None:
    """均价三级优先级（Part B，Human 2026-07-31 决定改用交易所返回的权威均价）：
    ① 库里存的 ``avg_price``（交易所原话，非推导）→ ② 本地 ``quote / base`` 计算
    → ③ ``None``。三处腿投影（``_leg_to_doc`` / ``_entry_spot_leg`` /
    ``_entry_perp_leg``）共用此函数，保证同一笔钱在 attempts 与 entries 两流展示同一价格。

    与 review-1 r6「不得用未知成交额做除法」不冲突：除法只发生在 ``local_avg``（仅当
    quote 在场）；存的是交易所原话。为空/NULL 退回 ``local_avg``，既有历史行不受影响。

    纵深防御（R2-Rerun-F1）：库存值为**数值零**（如遗留脏数据 ``"0.00000"``、或未来别的
    写入路径漏网）时视为未知，退回 ``local_avg``（②），绝不把 ``0`` 当真实成交价展示——
    均价为零在业务上不可能是真实成交。解析层（``_avg_price_decimal``）已挡新数据，此层是
    最后一道关，护住已落库的脏数据与未来路径。
    """
    stored = leg.get("avg_price")
    if stored is None or stored == "":
        return local_avg
    try:
        if D.Decimal(str(stored)) == 0:
            return local_avg
    except Exception:
        pass
    return stored


def _leg_to_doc(leg: dict | None) -> dict:
    """Project one mutable leg row to the frozen §3.4 per-leg shape.

    Decimal fields stay strings; ``avg_price`` 优先取库里存的交易所权威值，否则用
    ``cumulative_quote_amt / cumulative_base_qty`` 本地加权均价（None when there is no
    base fill yet — a PREPARED/REJECTED leg）。The spot leg carries
    ``fee_amount``/``fee_asset`` only when they were recorded.
    """
    leg = leg or {}
    base = D.Decimal(leg.get("cumulative_base_qty") or "0")
    raw_quote = leg.get("cumulative_quote_amt")
    if raw_quote is None:
        # NULL notional passes through as JSON null, not "0" (review-1 r6); the
        # local average stays None (do not divide an unknown notional) — but a
        # stored exchange avg_price still wins via _resolve_avg_price.
        quote_amt = None
        local_avg = None
    else:
        quote = D.Decimal(raw_quote)
        quote_amt = D.fmt_decimal(quote)
        local_avg = D.fmt_decimal(quote / base) if base > 0 else None
    doc = {
        "client_order_id": leg.get("client_order_id"),
        "order_id": leg.get("order_id"),
        "status": leg.get("exchange_status"),
        "cumulative_base_qty": D.fmt_decimal(base),
        "cumulative_quote_amt": quote_amt,
        "avg_price": _resolve_avg_price(leg, local_avg),
    }
    if leg.get("fee_amount") is not None:
        doc["fee_amount"] = leg.get("fee_amount")
        doc["fee_asset"] = leg.get("fee_asset")
    return doc


def attempt_to_doc(
    attempt: dict, spot_leg: dict | None, perp_leg: dict | None,
) -> dict:
    """Project one durable attempt + its two legs to the frozen §3.4 attempt
    timeline document (PRD §9.2 / 00-task Deliverable 5).

    Covers PREPARED / UNKNOWN_QUERYING / ACCEPTED_OR_QUERYING / resolved
    attempts: an unresolved pair has ``pair_outcome=None`` and legs with no
    ``order_id``/``status`` yet, so the UI shows in-flight pairs mid-query.
    ``residual`` is the per-attempt ``spot_base − perp_base`` decimal string
    (sign read per direction), recorded/displayed, never a scheduler gate
    (§4.5). All Decimal fields are strings; no binary float touches the path.
    """
    spot_base = D.Decimal((spot_leg or {}).get("cumulative_base_qty") or "0")
    perp_base = D.Decimal((perp_leg or {}).get("cumulative_base_qty") or "0")
    return {
        "task_id": attempt.get("task_id"),
        "attempt_id": attempt.get("attempt_uuid"),
        "attempt_seq": attempt.get("attempt_seq"),
        "direction": attempt.get("direction"),
        "q_common": attempt.get("q_common"),
        "pair_outcome": attempt.get("pair_outcome"),
        # attempt-level error rollup（store.py:1085-1166 写入）：失败/单腿行的中文原因常为
        # NULL（非 fatal rollup），消费方按 error_reason_zh → error_code/error_category →
        # 占位 回退。仅投影既有列，不改写入语义。
        "error_category": attempt.get("error_category"),
        "error_code": attempt.get("error_code"),
        "error_reason_zh": attempt.get("error_reason_zh"),
        "smooth_pass_reason": attempt.get("smooth_pass_reason"),
        "spot": _leg_to_doc(spot_leg),
        "perp": _leg_to_doc(perp_leg),
        "residual": D.fmt_decimal(spot_base - perp_base),
        "ts": D.us_to_iso(attempt.get("created_at_us")),
    }


# ---------------------------------------------------------------------------
# §5 frozen additive `entries` projection helpers (field names are frozen; a
# change is a bookkeeper escalation, never a local rename).
# ---------------------------------------------------------------------------


def _entry_side(direction: str | None, position_side_mode: str | None) -> tuple[str | None, str | None]:
    """Return ``(spot_side, perp_side)`` for an entry leg, or ``(None, None)``."""
    if not direction:
        return None, None
    actions = D.direction_to_leg_actions(direction, position_side_mode or D.POS_MODE_BOTH)
    return actions.spot_side, actions.perp_side


def _entry_spot_leg(leg: dict | None, spot_side: str | None) -> dict:
    leg = leg or {}
    base = D.Decimal(leg.get("cumulative_base_qty") or "0")
    raw_quote = leg.get("cumulative_quote_amt")
    if raw_quote is None:
        # NULL notional passes through as JSON null, not "0" (review-1 r6); the
        # local average stays None (do not divide an unknown notional) — but a
        # stored exchange avg_price still wins via _resolve_avg_price.
        quote_amt = None
        local_avg = None
    else:
        quote = D.Decimal(raw_quote)
        quote_amt = D.fmt_decimal(quote)
        local_avg = D.fmt_decimal(quote / base) if base > 0 else None
    return {
        "side": spot_side,
        "client_order_id": leg.get("client_order_id"),
        "order_id": leg.get("order_id"),
        "status": leg.get("exchange_status"),
        "cumulative_base_qty": D.fmt_decimal(base),
        "cumulative_quote_amt": quote_amt,
        "avg_price": _resolve_avg_price(leg, local_avg),
        "fee_amount": leg.get("fee_amount"),
        "fee_asset": leg.get("fee_asset"),
    }


def _entry_perp_leg(leg: dict | None, perp_side: str | None) -> dict:
    leg = leg or {}
    base = D.Decimal(leg.get("cumulative_base_qty") or "0")
    raw_quote = leg.get("cumulative_quote_amt")
    if raw_quote is None:
        # NULL notional passes through as JSON null, not "0" (review-1 r6); the
        # local average stays None (do not divide an unknown notional) — but a
        # stored exchange avg_price still wins via _resolve_avg_price.
        quote_amt = None
        local_avg = None
    else:
        quote = D.Decimal(raw_quote)
        quote_amt = D.fmt_decimal(quote)
        local_avg = D.fmt_decimal(quote / base) if base > 0 else None
    return {
        "side": perp_side,
        "client_order_id": leg.get("client_order_id"),
        "order_id": leg.get("order_id"),
        "status": leg.get("exchange_status"),
        "cumulative_base_qty": D.fmt_decimal(base),
        "cumulative_quote_amt": quote_amt,
        "avg_price": _resolve_avg_price(leg, local_avg),
    }


# Null-filled leg shapes for task_event entries (§5: task events carry null
# attempt/leg fields; the UI renders —). Spot carries fee_* keys, perp does not.
_NULL_SPOT_LEG = {
    "side": None, "client_order_id": None, "order_id": None, "status": None,
    "cumulative_base_qty": None, "cumulative_quote_amt": None, "avg_price": None,
    "fee_amount": None, "fee_asset": None,
}
_NULL_PERP_LEG = {
    "side": None, "client_order_id": None, "order_id": None, "status": None,
    "cumulative_base_qty": None, "cumulative_quote_amt": None, "avg_price": None,
}


def _entry_attempt_overall(
    pair_outcome: str | None, spot_status: str | None, perp_status: str | None,
) -> str:
    """Map a pair outcome + leg fill states to the §5 ``overall_result`` enum."""
    if pair_outcome is None or pair_outcome == D.PAIR_QUERYING:
        return "querying"
    if pair_outcome == D.PAIR_SINGLE_LEG:
        return "single_leg"
    if pair_outcome == D.PAIR_CONFIRMED_FAILED:
        return "confirmed_failed"
    if pair_outcome == D.PAIR_ACCEPTED:
        if spot_status == D.LEG_FILLED and perp_status == D.LEG_FILLED:
            return "filled"
        return "both_accepted"
    return "querying"


def _entry_next_action(task_status: str | None, overall: str) -> str:
    """Map the task status + attempt overall to the §5 ``next_action`` enum."""
    if task_status == D.STATUS_STOPPED:
        return "stopped"
    if task_status == D.STATUS_PAUSED:
        return "paused"
    if task_status == D.STATUS_DONE:
        return "completed"
    if overall == "querying":
        return "waiting_query"
    return "continue_next_attempt"


class HedgeOpenTaskService:
    def __init__(
        self,
        db_path: str,
        *,
        executor: HedgeExecutor | None = None,
        preflight_provider: PreflightProvider | None = None,
        mode: str = "disabled",
        credentials_present: bool = False,
        mono_us: Callable[[], int] | None = None,
        wall_us: Callable[[], int] | None = None,
        cache_refresh_submitter: Callable[[], None] | None = None,
        ledger_flow_service=None,  # 功能三：结算日志费率/利息复用（duck-typed，可选）
        market_provider=None,
    ):
        self._mono_us = mono_us or _real_mono_us
        self._wall_us = wall_us or _real_wall_us
        self._store = HedgeOpenStore(
            db_path, executor_mode_snapshot=mode, now_us=self._wall_us(),
        )
        # 已告警过身份漂移的任务 id（D3 去重，评审核查点 3）。进程内即可——漂移
        # 源于映射表变更，重启后重新提示一次是期望行为而非缺陷。
        self._identity_drift_seen: set[str] = set()
        # Default executor is DisabledHedgeExecutor (zero I/O, zero fills): it
        # resolves every attempt to ATTEMPT_DISABLED with filled_qty=0 and
        # performs NO network POST and NO simulated fill. The dry-run
        # record-transport fill simulator was removed from production
        # (2026-08-06 Human decision); a real POST is reachable only under
        # APP_HEDGE_EXECUTOR=live AND the Start gate AND a live executor
        # (injected by the server with a fresh preflight provider), so the
        # default keeps a real POST unreachable. The test-only record fake lives
        # under backend/tests/fakes.py.
        self._executor: HedgeExecutor = executor or DisabledHedgeExecutor()
        self._preflight: PreflightProvider = preflight_provider or DisabledPreflightProvider()
        self._mode = mode
        self._live_mode = mode == "live"
        self._ledger_flow_service = ledger_flow_service  # 功能三：close_log 费率/利息（可选）
        # Whether the injected live executor holds real credentials (server
        # computes this from the live client; default False for dry-run). The
        # value is a boolean only — never a credential value (Boundary C).
        self._credentials_present = bool(credentials_present)
        self._last_tick_mono: int | None = None
        # Stage 2026-08-03-hedge-status-account-refresh-v1 (design §5.2): an
        # injected non-waiting cache-refresh submitter (SnapshotService's
        # submit_cache_refresh). The service fires it ONLY on a real
        # ``running → 非 running`` task transition, AFTER the status write
        # committed, swallowing any exception so a cache enqueue failure never
        # rolls back the already-committed task status. ``None`` (tests / unwired)
        # -> the hook is a no-op. The server wires it via
        # :meth:`configure_cache_refresh` so the two services stay decoupled
        # (SnapshotService is never imported here).
        self._submit_cache_refresh: Callable[[], None] | None = cache_refresh_submitter
        # Stage 2026-08-06 task 05 (§4.2): read-only SnapshotService cache
        # access for the close-spot-balance GATE (缓存只用于「放行」，不用于触发
        # 有副作用的划转动作). Injected by the server via
        # :meth:`configure_snapshot_reader`; ``None`` (tests / unwired) keeps the
        # real-time confirmation path unchanged.
        self._snapshot_reader: Callable[[str], tuple[float, object] | None] | None = None
        # §4.2（Human 决定 3）：进程内「本任务已完成划转」事实记录（task_id ->
        # (amount, asset)），由 _log_close_transfer 的 ok 事件点写入；forward
        # close 后续余额不足暂停时据此追加「可能是划转尚未到账」提示。
        self._close_transfer_done: dict[str, tuple[str, str]] = {}
        # Amendment 21 task-local workers: each RUNNING task owns at most ONE
        # bounded-lifetime worker thread (no global guardian/scanner). ``_workers``
        # maps task_id -> live worker thread; ``_stop_events`` carries the per-task
        # interrupt a pause/stop/delete/settle sets to wake a pacing worker. The
        # scheduler/tick no longer drive immediate dispatch through a global scan;
        # an HTTP Start/recover or a one-shot recovery discovery launches a worker.
        self._workers: dict[str, threading.Thread] = {}
        self._stop_events: dict[str, threading.Event] = {}
        self._workers_lock = threading.Lock()
        # task1d S2/R3 (review-2 audit): in-process set of attempts whose
        # ``mark_attempt_rate_limited`` stamp FAILED at dispatch and must be retried
        # before settlement, so a 429 pair is never finalized as an ordinary
        # failure (consuming the counter the design exempts). An attempt belongs to
        # exactly one task and that task owns one worker thread, so each id is only
        # ever touched by its own worker; individual set ops are GIL-atomic. Not a
        # new column/status — it is the next-round retry R3 sanctions (a process
        # restart loses it, same crash window the system already has).
        self._rate_limit_stamp_pending: set[int] = set()
        # fix-review1-retry-counter (F1): per-leg in-process order-detail query
        # retry count (``hedge_open_leg.id`` -> attempts so far). The worker asks
        # each non-terminal leg up to ``D.LEG_QUERY_MAX_RETRIES`` times, then the
        # LAST response decides (404 / -2013 -> absent terminal; still inconclusive
        # -> manual recovery). Process-local like the legacy JS loop: a restart
        # resets it to zero and the budget is counted afresh (expected, not a
        # defect). A leg reaching terminal state or a worker exit clears its entry
        # so the dict cannot grow without bound. Each leg belongs to one task's
        # one worker, so individual dict ops need no extra lock.
        self._leg_query_retries: dict[int, int] = {}
        self._market_provider = market_provider
        self._smooth_lock = threading.RLock()
        self._smooth_wakes: dict[str, _GateWake] = {}
        self._smooth_subscriptions: dict[str, tuple[tuple[str, str, str], ...]] = {}
        self._smooth_relaunch_after_exit: set[str] = set()
        set_on_change = getattr(market_provider, "set_on_change", None)
        if callable(set_on_change):
            set_on_change(self._on_smooth_market_change)
        self._scheduler = HedgeOpenScheduler(
            self.tick, self._store.get_interval_us, self._mono_us
        )

    # --------------------------------------------------------------- lifecycle

    def close(self) -> None:
        self.stop()
        self._store.close()

    def start(self) -> None:
        """Start the runtime (amendment 21 + final guardian fix / H-1).

        LIVE-capable mode: perform ONE durable recovery discovery — find tasks
        that need cleanup (RUNNING tasks missing a worker; any-status tasks
        with persisted non-terminal legs), hand each to its own bounded worker,
        then return. The periodic scheduler is NOT started as a long-lived
        all-task recovery scanner; a worker that later exits is relaunched only
        by a manual Start/recover. Packet-62 safety is preserved: pending pairs
        are queried by their saved client order IDs (never re-POSTed) and a
        paused/stopped task mid-pair gets a drain-only worker.

        DRY-RUN mode (record/disabled executor): start the scheduler so its
        synchronous record-transport tick advances cards on the 1s cadence.
        """
        if self._live_dispatch_capable():
            self._recover_workers()
            return
        self._scheduler.start()
        for task in self._store.list_tasks(D.STATUS_RUNNING):
            if task.get("mode") == D.MODE_SMOOTH:
                self.ensure_worker(task["id"])

    def stop(self) -> None:
        self._scheduler.stop()
        # Wake every task-local worker so its bounded loop exits promptly.
        with self._workers_lock:
            events = list(self._stop_events.values())
        for ev in events:
            ev.set()
        with self._smooth_lock:
            self._smooth_relaunch_after_exit.clear()
        self._notify_all_smooth()
        close_market = getattr(self._market_provider, "close", None)
        if callable(close_market):
            close_market()

    @property
    def store(self) -> HedgeOpenStore:
        return self._store

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def executor(self) -> HedgeExecutor:
        return self._executor

    @property
    def is_live_mode(self) -> bool:
        return self._live_mode

    @property
    def credentials_present(self) -> bool:
        return self._credentials_present

    def configure_cache_refresh(self, submitter: Callable[[], None] | None) -> None:
        """Wire the non-waiting cache-refresh submitter (design §5.2).

        The server calls this after both services are built so SnapshotService
        stays uninjected here (the two services are decoupled; only this callback
        crosses them). ``submitter`` should enqueue-or-coalesce and return
        immediately (``wait=False``); the status hook never blocks on a refresh.
        Passing ``None`` disables the hook (the no-op default)."""
        self._submit_cache_refresh = submitter

    def configure_snapshot_reader(
        self, reader: Callable[[str], tuple[float, object] | None] | None,
    ) -> None:
        """Wire the read-only SnapshotService cache reader (stage 2026-08-06
        task 05 §4.2).

        Mirrors :meth:`configure_cache_refresh`: the server calls this after
        both services are built so SnapshotService stays uninjected here. The
        reader is used ONLY for the close-spot-balance GATE's "cache suffices ->
        pass" shortcut — a cached balance NEVER authorizes a real transfer (the
        actual insufficient check still goes real-time before any
        ``universal_transfer``). Passing ``None`` disables the shortcut."""
        self._snapshot_reader = reader

    def configure_preflight_reader(
        self, reader: Callable[[str], tuple[float, object] | None] | None,
    ) -> None:
        """Forward the read-only SnapshotService cache reader to the preflight
        provider (stage 2026-08-06 task 05 §1.3). The provider is built inside
        ``_build_hedge_service`` with ``snapshot_reader=None`` (server builds
        services before wiring), so this setter injects it post-construction;
        a provider without the setter (stub/disabled) is a no-op."""
        setter = getattr(self._preflight, "set_snapshot_reader", None)
        if callable(setter):
            setter(reader)

    def _cached_spot_free(self, base_asset: str) -> Decimal | None:
        """Fresh-enough ``spot_balances`` free for ``base_asset`` (5min ceiling),
        or ``None`` when unknown/stale/unwired — the caller must then confirm
        real-time. Used ONLY as a pass gate (§4.2)."""
        reader = self._snapshot_reader
        if reader is None:
            return None
        entry = reader("spot_balances")
        if entry is None:
            return None
        try:
            ts, value = entry
        except (TypeError, ValueError):
            return None
        if time.monotonic() - float(ts) > 5 * 60.0:
            return None
        if not isinstance(value, list):
            return None
        for row in value:
            if isinstance(row, dict) and row.get("asset") == base_asset:
                free = row.get("free")
                if free is None:
                    return None
                try:
                    return D.Decimal(str(free))
                except (InvalidOperation, ValueError, TypeError):
                    return None
        return None  # 该币不在列表 → 未知，须实时确认

    def _cached_unified_free(self, base_asset: str) -> Decimal | None:
        """Fresh-enough ``unified_balances`` ``crossMarginFree`` for
        ``base_asset`` (5min ceiling), or ``None`` when unknown/stale/unwired.
        The transferable-amount check is a PASS-gate item (§4.2): a cached
        sufficient amount may authorize the transfer, a cached missing amount
        must be confirmed real-time before ANY transfer happens."""
        reader = self._snapshot_reader
        if reader is None:
            return None
        entry = reader("unified_balances")
        if entry is None:
            return None
        try:
            ts, value = entry
        except (TypeError, ValueError):
            return None
        if time.monotonic() - float(ts) > 5 * 60.0:
            return None
        if not isinstance(value, list):
            return None
        for row in value:
            if isinstance(row, dict) and row.get("asset") == base_asset:
                free = row.get("crossMarginFree")
                if free is None:
                    return None
                try:
                    return D.Decimal(str(free))
                except (InvalidOperation, ValueError, TypeError):
                    return None
        return None

    def _notify_cache_refresh(self, task: dict | None) -> None:
        """Fire the cache-refresh hook when ``task`` carries a real
        ``running → 非 running`` transition (design §5.2).

        Reads the additive ``_status_transition`` the store attached AFTER its
        commit. Only ``old == running && new != running`` submits a non-waiting
        cache command; every other transition (same status, restore-to-running,
        a conditional-write miss, or a settle with skip_counters) is zero-
        trigger. The submitter's exceptions are swallowed: a cache-enqueue
        failure must NEVER roll back the already-committed task status.
        """
        cb = self._submit_cache_refresh
        if cb is None or not isinstance(task, dict):
            return
        transition = task.get("_status_transition")
        if not transition:
            return
        old_status, new_status = transition
        if old_status == D.STATUS_RUNNING and new_status != D.STATUS_RUNNING:
            try:
                cb()
            except Exception:
                pass

    def is_start_gate_on(self) -> bool:
        return bool(self._store.get_settings()["start_gate"])

    def is_close_gate_on(self) -> bool:
        return bool(self._store.get_settings()["close_gate"])

    # ------------------------------------------------------------------ tasks

    def create_task(self, body) -> tuple[int, dict]:
        if not isinstance(body, dict):
            raise D.HedgeError(400, "invalid_json", "request body must be a JSON object")
        D.reject_unknown_keys(body, _CREATE_BODY_KEYS)
        coin = D.validate_coin(body.get("coin"))
        direction = D.validate_direction(body.get("direction"))
        mode = D.validate_mode(body.get("mode") or D.DEFAULT_MODE)
        task_type = body.get("task_type") or D.TASK_TYPE_OPEN
        single_amount = body.get("single_amount")
        target_n = body.get("target_n")
        # 诊断日志（2026-08：定位「平仓任务点击后未创建」问题）。stderr 输出，
        # 服务启动终端/重定向可见；不写库（失败时无 task_id 可挂）。
        print(
            f"[HEDGE-CREATE] body task_type={task_type} coin={coin} "
            f"direction={direction} mode={mode} single_amount={single_amount} "
            f"target_n={target_n}",
            file=sys.stderr, flush=True,
        )
        D.validate_task_type(task_type)
        threshold = None
        if mode == D.MODE_SMOOTH:
            # smooth-close C6：解除 open-only——close 同样要求公共盘口 provider
            # 可用（gate 评估依赖一档盘口），否则 400 smooth_market_unavailable。
            if self._market_provider is None:
                raise D.HedgeError(
                    400, "smooth_market_unavailable",
                    "平滑开平仓公共盘口不可用；可继续使用立即开单/立即平仓",
                )
            threshold = D.validate_slippage_threshold_pct(
                body.get("slippage_threshold_pct")
            )
        elif "slippage_threshold_pct" in body:
            raise D.invalid_field(
                "slippage_threshold_pct", "is only valid when mode is smooth"
            )
        single_amount = D.validate_single_amount(body.get("single_amount"))
        target_n = D.validate_target_n(body.get("target_n"))

        # 功能三（close 任务）：必须存在该 (coin, direction) 的活跃周期（无仓不可平）；
        # 平仓方向沿用持仓行方向（forward 仓 → forward 平仓：现货 SELL + 合约 BUY）。
        active_cycle = None
        if task_type == D.TASK_TYPE_CLOSE:
            active_cycle = self._store.get_active_cycle(coin, direction)
            if active_cycle is None:
                print(
                    f"[HEDGE-CREATE] close rejected: no_active_cycle coin={coin} "
                    f"direction={direction}",
                    file=sys.stderr, flush=True,
                )
                raise D.HedgeError(
                    409, "no_active_cycle",
                    f"{direction} {coin} 无活跃持仓周期，不可平仓（无仓不可平）",
                )

        # 现货腿身份是纯本地查表结果。close 优先继承周期首个开仓任务的历史真值，
        # 同时保留当前映射用于 1000x 双判；整个分支零交易所 I/O。
        current_spot_symbol, current_spot_base, current_match = resolve_spot_identity(coin)
        spot_symbol = current_spot_symbol
        spot_base_asset = current_spot_base
        symbol_match_type = current_match
        position_side_mode = None
        if task_type == D.TASK_TYPE_CLOSE and active_cycle is not None:
            origin = self._store.get_task(active_cycle.get("first_task_id") or "")
            inherited = origin.get("spot_symbol") if origin else None
            inherited_match = origin.get("symbol_match_type") if origin else None
            if inherited:
                spot_symbol = inherited
                spot_base_asset = origin.get("spot_base_asset")
                symbol_match_type = inherited_match
            else:
                print(
                    f"[HEDGE-CREATE] close identity fallback: cycle="
                    f"{str(active_cycle.get('id'))[:8]} origin_task="
                    f"{str(active_cycle.get('first_task_id'))[:8]} 无固化身份，"
                    f"回退查表 {spot_symbol}",
                    file=sys.stderr, flush=True,
                )
            position_side_mode = (
                (origin or {}).get("position_side_mode") or D.POS_MODE_BOTH
            )
            if (
                inherited_match == SPOT_MATCH_MULTIPLIER
                or current_match == SPOT_MATCH_MULTIPLIER
            ):
                raise D.HedgeError(
                    400, "multiplier_contract_unsupported",
                    f"{coin} 是 1000 倍乘数合约，两腿数量换算尚未实现，"
                    "自动平仓会产生错误敞口，请人工到交易所处理",
                    extra={"coin": coin, "spot_symbol": current_spot_symbol},
                )

            # 两段式 close：只做上面的本地校验并在同一条 INSERT 中落 paused。
            # 不读 filters/price/balance/position/rate-limit，不划转、不建 attempt，
            # 也不启动 worker；Human 点击任务卡“启动”后才进入完整预检。
            task_id = str(uuid.uuid4())
            now_us = self._wall_us()
            task = self._store.create_task(
                task_id,
                coin,
                direction,
                mode,
                single_amount,
                target_n,
                None,
                position_side_mode,
                {"available": False, "reason": "no_preflight_snapshot"},
                now_us,
                task_type=task_type,
                spot_symbol=spot_symbol,
                spot_base_asset=spot_base_asset,
                symbol_match_type=symbol_match_type,
                # smooth-close C6/§6.1：轻量建卡分支落规范后的阈值（当前分支
                # 此前未传）；C8：仅 smooth close 的连续失败刹车阈值落 1（出现
                # 第一次单腿成交或提交失败即暂停），immediate close 保持默认 3。
                failure_pause_threshold=(
                    1 if mode == D.MODE_SMOOTH else D.DEFAULT_FAILURE_PAUSE_THRESHOLD
                ),
                initial_status=D.STATUS_PAUSED,
                initial_pause_reason=D.PAUSE_REASON_AWAITING_MANUAL_START,
                initial_pause_reason_zh=D.pause_reason_zh(
                    D.PAUSE_REASON_AWAITING_MANUAL_START
                ),
                slippage_threshold_pct=threshold,
            )
            print(
                f"[HEDGE-CREATE] success task_id={task_id[:8]} task_type=close "
                f"coin={coin} direction={direction} status=paused",
                file=sys.stderr, flush=True,
            )
            return 201, self._doc(task)

        # S4b (ADR-H5): when the provider can probe leg existence, block creating
        # a task for a coin confirmed absent on spot and/or UM (e.g. KORUUSDT,
        # which has no spot leg -> Binance -1121). Only a confirmed-absent leg
        # (False) blocks; an indeterminate read (None) does NOT — a transient
        # public-marketdata failure is never escalated to a create-task failure.
        # The probe is duck-typed (mirrors _live_dispatch_capable): the dry-run
        # DisabledPreflightProvider has no probe, so dry-run create is unchanged.
        probe = getattr(self._preflight, "check_symbol_legs", None)
        if callable(probe):
            legs = probe(coin)
            missing = [k for k in ("spot", "perp") if legs.get(k) is False]
            if missing:
                raise D.HedgeError(
                    400, "missing_leg", D.missing_leg_detail(missing),
                    extra={"missing": missing},
                )

        # P0 (2026-08-07)：1000x 乘数合约暂不可开单。执行链两腿发的是同一个
        # q_common（注入的实盘执行器 dispatch 里两腿共用 send_qty），而 1 张
        # 1000BONKUSDT = 1000 个 BONK——现货买 N 个、合约空 N 张，净裸空 999N。
        # SPOT_SYMBOL_MAP 让这 6 个币
        # 通过了上面的存在性探测，但腿量换算从未实现，故在此 fail-closed（「宁可
        # 无腿，不可错腿」）。换算实现后连同本拦截与其两个测试一起移除。
        #
        # open 在这里拦；close 已在上面的轻量建卡分支用“固化值 OR 当前映射”
        # 双判拦截，并在 dispatch 再守一次历史 NULL 行。
        if task_type == D.TASK_TYPE_OPEN:
            mult_spot_symbol, _, mult_match = resolve_spot_identity(coin)
            if mult_match == SPOT_MATCH_MULTIPLIER:
                raise D.HedgeError(
                    400, "multiplier_contract_unsupported",
                    f"{coin} 是 1000 倍乘数合约（1 张 = 1000 个 {mult_spot_symbol[:-4]}），"
                    "两腿数量换算尚未实现，直接下单会留下 999 倍裸空敞口，暂不支持对冲开单",
                    extra={"coin": coin, "spot_symbol": mult_spot_symbol},
                )

        # close 任务按反转方向做余额检查：forward 平仓卖现货需现货持仓，
        # reverse 平仓买现货需 USDT（与开仓检查方向相反）。
        preflight_direction = (
            D.DIR_REVERSE if direction == D.DIR_FORWARD else D.DIR_FORWARD
        ) if task_type == D.TASK_TYPE_CLOSE else direction
        snapshot = self._preflight.get_snapshot(coin, preflight_direction, task_type=task_type)
        preflight = D.compute_preflight(
            snapshot, coin, preflight_direction, D.Decimal(single_amount), target_n
        )
        if preflight.rejection == D.REJECT_INSUFFICIENT_BALANCE:
            raise D.HedgeError(
                400,
                "insufficient_balance",
                f"{direction} {task_type} balance check failed",
                extra={
                    "direction": direction,
                    "required": D.fmt_decimal(preflight.required),
                    "available": D.fmt_decimal(preflight.available),
                },
            )
        if preflight.rejection is not None:
            raise D.invalid_field(
                "single_amount",
                f"common-grid quantity rejected: {preflight.rejection}",
            )
        # 开仓 regular_spot 预划转（Human 2026-08）：所有 USDT 默认在统一账户当保证金，
        # open+forward+regular_spot 建仓前从统一账户一次性划转 1.03 倍所需 USDT 到普通
        # 现货账户（缓冲覆盖下单价格漂移、向下截断两位）。划转失败 → 任务卡不创建，
        # 前端弹窗（统一账户 USDT 不足等）；dry-run（executor 无 universal_transfer）跳过。
        # 不预查统一账户余额——前端已校验，划转本身即资金核验（fail-closed on reject）。
        if (
            snapshot is not None
            and task_type == D.TASK_TYPE_OPEN
            and direction == D.DIR_FORWARD
            and snapshot.spot_route == D.SPOT_ROUTE_REGULAR_SPOT
        ):
            xfer = getattr(self._executor, "universal_transfer", None)
            if xfer is not None:
                need = D.truncate_usdt(
                    preflight.q_common * D.Decimal(target_n) * snapshot.est_price
                    * D.OPEN_SPOT_BUFFER
                )
                try:
                    xfer("PORTFOLIO_MARGIN_MAIN", D.QUOTE_ASSET, str(need))
                except Exception as exc:  # noqa: BLE001
                    detail = str(exc)[:200] or type(exc).__name__
                    print(
                        f"[HEDGE-CREATE] open_spot_transfer failed coin={coin} "
                        f"need={need} detail={detail}",
                        file=sys.stderr, flush=True,
                    )
                    raise D.HedgeError(
                        400, "open_spot_transfer_failed",
                        f"统一账户 USDT 划转到现货账户失败（需 {D.fmt_decimal(need)} USDT）：{detail}",
                        extra={"coin": coin, "need": D.fmt_decimal(need)},
                    )
                print(
                    f"[HEDGE-CREATE] open_spot_transfer ok coin={coin} need={need}",
                    file=sys.stderr, flush=True,
                )
        task_id = str(uuid.uuid4())
        now_us = self._wall_us()
        print(
            f"[HEDGE-CREATE] success task_id={task_id[:8]} task_type={task_type} "
            f"coin={coin} direction={direction} q={D.fmt_decimal(preflight.q_common)}",
            file=sys.stderr, flush=True,
        )
        # Human 2026-08-18 方案 B：开仓一律以 paused 落卡（立即开单不再默认
        # running；建卡后零自动执行，tick/重启恢复不再拾取未启动卡）。close 已
        # 在上方两段式分支 return，此处只剩 open，恒真条件直接内联。立即开单的
        # 成交按钮保持可用（Human 指令：成交1次对执行中/已暂停卡都可点，等价
        # 武装+推进的人工动作），故 zh 文案与平滑的「必须点击启动」区分。
        task = self._store.create_task(
            task_id,
            coin,
            direction,
            mode,
            single_amount,
            target_n,
            D.fmt_decimal(preflight.q_common),
            preflight.position_side_mode,
            preflight.snapshot_record,
            now_us,
            task_type=task_type,
            spot_symbol=spot_symbol,
            spot_base_asset=spot_base_asset,
            symbol_match_type=symbol_match_type,
            slippage_threshold_pct=threshold,
            initial_status=D.STATUS_PAUSED,
            initial_pause_reason=D.PAUSE_REASON_AWAITING_MANUAL_START,
            initial_pause_reason_zh=(
                D.pause_reason_zh(D.PAUSE_REASON_AWAITING_MANUAL_START)
                if mode == D.MODE_SMOOTH
                else D.pause_reason_zh(
                    D.PAUSE_REASON_AWAITING_MANUAL_START_FILLABLE
                )
            ),
        )
        return 201, self._doc(task)

    def list_tasks(self, status_query: str | None) -> tuple[int, dict]:
        status_filter = D.filter_status_for_list(status_query)
        tasks = [self._doc(t) for t in self._store.list_tasks(status_filter)]
        return 200, {"tasks": tasks}

    def get_close_logs(self) -> tuple[int, dict]:
        """功能三 ③a：周期结算日志（按 closed_at 倒序），历史仓位页数据源。只读。"""
        return 200, {"logs": self._store.list_close_logs()}

    def _get_task_or_404(self, task_id: str) -> dict:
        task = self._store.get_task(task_id)
        if task is None:
            raise D.HedgeError(404, "unknown_task", f"unknown task {task_id}")
        return task

    def _worker_active_for(self, task_id: str) -> bool | None:
        """Derive the worker_active tri-state for :func:`task_to_doc` (P2-2). In
        dry-run (no live dispatch) the concept does not apply -> ``None``;
        otherwise reflect whether a live worker thread currently owns this task."""
        if not self._live_dispatch_capable():
            return None
        with self._workers_lock:
            thread = self._workers.get(task_id)
            return bool(thread is not None and thread.is_alive())

    def _doc(self, task: dict) -> dict:
        return task_to_doc(task, worker_active=self._worker_active_for(task["id"]))

    def post_start(self, task_id: str) -> tuple[int, dict]:
        task = self._get_task_or_404(task_id)
        status = task["status"]
        if status == D.STATUS_DELETED:
            raise D.HedgeError(409, "invalid_state", "cannot start a deleted task")
        if status == D.STATUS_DONE:
            return 200, self._doc(task)  # idempotent: done stays done
        # smooth-close C5/C13/C14：启动 = 闸门校验 → 同步备料 → 一次条件写，
        # 与其余任务类型的 post_start（下方原路径，零 diff）分流。
        if (
            task.get("mode") == D.MODE_SMOOTH
            and (task.get("task_type") or D.TASK_TYPE_OPEN) == D.TASK_TYPE_CLOSE
        ):
            if status not in (D.STATUS_PAUSED, D.STATUS_RUNNING):
                raise D.HedgeError(
                    409, "invalid_state",
                    "任务已停止（fatal stop），本启动路径不自动恢复，请核对后另行处理",
                )
            return self._start_smooth_close(task)
        # Single-leg exposure is ADVISORY (breakdown §4.5): it does not freeze
        # scheduling and never blocks start.
        updated = self._store.set_task_status(task_id, D.STATUS_RUNNING, self._wall_us())
        # Amendment 21: Start/recover launches THIS task's bounded worker (live
        # mode) and returns immediately — no global scan, no synchronous POST.
        if self._live_dispatch_capable() or task.get("mode") == D.MODE_SMOOTH:
            if task.get("mode") == D.MODE_SMOOTH:
                self.ensure_worker(task_id, relaunch_after_current=True)
            else:
                self.ensure_worker(task_id)
        self._notify_smooth_task(task_id)
        return 200, self._doc(updated)

    def _start_smooth_close(self, task: dict) -> tuple[int, dict]:
        """smooth close 启动链（C4/C5/C13/C14 §6.2），顺序硬约束：

        1. 【C5】备料**之前**校验 Start gate 与平仓闸门——任一关闭即返回中文
           原因、任务保持 ``paused``、零预检/零查仓/零划转（划转原本发生在
           worker 的 dispatch 路径内受双闸约束，前移后必须在此恢复同等约束）；
        2. ``q_common`` 已有值（备料成功后的人工恢复，C4）→ 跳过备料，仅带
           ``paused`` 谓词置 running；
        3. 否则本请求内同步执行三道门备料（C13：请求会真实等待数秒），任一步
           失败任务保持 ``paused`` 并携带 §2.4 既有中文原因，不置 running、
           不启 worker、零订阅、零 gate；
        4. 【C14】成功收尾一次条件写（``arm_prepared_close_task``，语义等价
           ``WHERE status='paused' AND q_common IS NULL``），未命中重读权威
           状态：已删除/已完成/已停止一律冲突错误且绝不复活；已 running 幂等
           返回；仍 paused 且已有 ``q_common`` 只置 running。
        """
        task_id = task["id"]
        if not self.is_start_gate_on():
            raise D.HedgeError(
                409, "start_gate_closed", "开单闸门已关闭，先开闸再启动任务",
            )
        if not self.is_close_gate_on():
            raise D.HedgeError(
                409, "close_gate_closed", "平仓闸门已关闭，先开闸再启动任务",
            )
        now_us = self._wall_us()
        updated: dict | None
        if task.get("q_common"):
            # C4：备料成功后重启/人工恢复——跳过备料，只带 paused 谓词置 running。
            updated = self._store.resume_paused_task(task_id, now_us)
            if updated is None:
                updated = self._resolve_smooth_close_start_conflict(task_id)
        else:
            prep_q, prep_pos_mode, prep_snapshot, prep_signal = (
                self._run_close_preparation(task, now_us)
            )
            if prep_signal is not None:
                if prep_signal == D.SIGNAL_PREFLIGHT_INCOMPLETE:
                    # Review-1 F1：worker 路径由 `_worker_round` 收口暂停，
                    # 启动路径此前缺这一步——只抛错不落库会让卡片与 HTTP
                    # 回显建卡时的旧文案（awaiting_manual_start）。先落库。
                    self._pause_preflight_incomplete(task, now_us)
                current = self._store.get_task(task_id) or task
                raise D.HedgeError(
                    409, "smooth_close_start_failed",
                    self._start_failure_reason_zh(current),
                )
            if prep_q is None:
                # remaining_attempts <= 0：计划次数已用完，与抽函数前的
                # dispatch 行为一致（不发单也不暂停），启动侧给准确文案。
                raise D.HedgeError(
                    409, "invalid_state",
                    "任务计划执行次数已用完，等待收尾或人工处理，无需再启动",
                )
            updated = self._store.arm_prepared_close_task(
                task_id,
                D.fmt_decimal(prep_q),
                prep_pos_mode,
                prep_snapshot,
                now_us,
            )
            if updated is None:
                # C14：未命中不写、不复活，按当前权威状态裁决。
                updated = self._resolve_smooth_close_start_conflict(task_id)
        self.ensure_worker(task_id, relaunch_after_current=True)
        self._notify_smooth_task(task_id)
        return 200, self._doc(updated)

    @staticmethod
    def _start_failure_reason_zh(current: dict) -> str:
        """启动失败的权威中文原因（Review-1 F1）：fatal 停止读 ``stop_reason``
        的中文文案；其余读刚由备料门/暂停写入的 ``pause_reason_zh``——绝不
        回显建卡时的旧文案（``awaiting_manual_start``）。"""
        if current.get("status") == D.STATUS_STOPPED:
            zh = D.stop_reason_zh(current.get("stop_reason"))
            if zh:
                return zh
        return (
            current.get("pause_reason_zh")
            or "平滑平仓备料失败，任务已暂停（fail-closed，未发单）"
        )

    def _resolve_smooth_close_start_conflict(self, task_id: str) -> dict:
        """C14 条件写未命中后的权威状态裁决：已删除/已完成/已停止 → 冲突错误
        （绝不复活）；已 running → 幂等返回；仍 paused 且已有 ``q_common`` →
        只置 running（同样带 paused 谓词）。"""
        current = self._store.get_task(task_id)
        if current is None or current["status"] in (
            D.STATUS_DELETED, D.STATUS_DONE, D.STATUS_STOPPED,
        ):
            raise D.HedgeError(
                409, "invalid_state",
                "任务已被删除、已完成或已停止，不再启动",
            )
        if current["status"] == D.STATUS_RUNNING:
            return current
        if current.get("q_common"):
            resumed = self._store.resume_paused_task(task_id, self._wall_us())
            if resumed is not None:
                return resumed
        raise D.HedgeError(
            409, "invalid_state", "任务状态已变化，请刷新后重试",
        )

    def post_pause(self, task_id: str) -> tuple[int, dict]:
        task = self._get_task_or_404(task_id)
        if task["status"] == D.STATUS_DELETED:
            raise D.HedgeError(409, "invalid_state", "cannot pause a deleted task")
        if task["status"] == D.STATUS_DONE:
            raise D.HedgeError(409, "invalid_state", "cannot pause a done task")
        # Amendment 21 / Review-1 r3 P1-2: do NOT interrupt the worker. The
        # task's own bounded worker keeps draining its in-flight legs to terminal
        # and settling the pair, then exits on the status check (opens no new
        # pair while paused).
        updated = self._store.set_task_status(task_id, D.STATUS_PAUSED, self._wall_us())
        self._notify_cache_refresh(updated)
        self._notify_smooth_task(task_id)
        return 200, self._doc(updated)

    def post_delete(self, task_id: str) -> tuple[int, dict]:
        task = self._get_task_or_404(task_id)
        if task["status"] == D.STATUS_DELETED:
            raise D.HedgeError(409, "invalid_state", "task already deleted")
        # Amendment 21 / Review-1 r3 P1-2: do NOT interrupt the worker. The
        # task's own bounded worker keeps draining its in-flight legs to terminal
        # and settling the pair, then exits on the status check (opens no new
        # pair once deleted).
        updated = self._store.set_task_status(task_id, D.STATUS_DELETED, self._wall_us())
        self._notify_cache_refresh(updated)
        self._notify_smooth_task(task_id)
        return 200, self._doc(updated)

    def post_fill_once(self, task_id: str, body=None) -> tuple[int, dict]:
        task = self._get_task_or_404(task_id)
        self._require_fillable(task)
        if task.get("mode") == D.MODE_SMOOTH:
            if not isinstance(body, dict):
                raise D.invalid_field("gate_seq", "is required for smooth fill-once")
            D.reject_unknown_keys(body, ("gate_seq",))
            gate_seq = body.get("gate_seq")
            if isinstance(gate_seq, bool) or not isinstance(gate_seq, int):
                raise D.invalid_field("gate_seq", "must be an integer")
            updated = self._store.force_smooth_gate(
                task_id, gate_seq, self._wall_us()
            )
            if updated is None:
                raise D.HedgeError(
                    409, "smooth_gate_conflict",
                    "当前平滑轮次已变化或不可放行，请刷新任务后重试",
                )
            self.ensure_worker(task_id)
            self._notify_smooth_task(task_id)
            return 200, self._doc(updated)
        if self._live_dispatch_capable():
            # Amendment 21: every live POST runs through the task-local worker.
            # fill-once arms the task (running) and launches/refreshes its worker;
            # it never performs a synchronous live POST here.
            if task["status"] != D.STATUS_RUNNING:
                task = self._store.set_task_status(task_id, D.STATUS_RUNNING, self._wall_us())
            self.ensure_worker(task_id)
            return 200, self._doc(task)
        # Human 2026-08-18：与 fill-all 同理——paused 卡（等待人工启动/刹车）先置
        # running 再推进，否则 prepare 被状态门拒绝、返回 200 零推进。
        if task["status"] != D.STATUS_RUNNING:
            task = self._store.set_task_status(
                task_id, D.STATUS_RUNNING, self._wall_us()
            )
        task, _ = self._dispatch_one_for_task(task, self._wall_us())
        return 200, self._doc(task)

    def post_fill_all(self, task_id: str) -> tuple[int, dict]:
        task = self._get_task_or_404(task_id)
        self._require_fillable(task)
        if task.get("mode") == D.MODE_SMOOTH:
            raise D.HedgeError(
                409, "smooth_fill_all_unsupported", "平滑开单不支持立即成交所有"
            )
        if self._live_mode:
            # Amendment 21: live fill-all arms the task and launches its worker;
            # the worker drives every pair (no synchronous live POST loop here).
            if task["status"] != D.STATUS_RUNNING:
                task = self._store.set_task_status(task_id, D.STATUS_RUNNING, self._wall_us())
            if self._live_dispatch_capable():
                self.ensure_worker(task_id)
            return 200, self._doc(task)
        now_us = self._wall_us()
        # Human 2026-08-18：对齐上方 live 分支——paused 卡（等待人工启动/失败
        # 刹车）先置 running 再进循环，否则 while 条件不进、返回 200 却零推进
        # （「点了没反应」）。smooth/close 的 awaiting 卡已被 _require_fillable
        # 拦下，能到这里的只剩允许成交推进的 immediate 卡。
        if task["status"] != D.STATUS_RUNNING:
            task = self._store.set_task_status(
                task_id, D.STATUS_RUNNING, self._wall_us()
            )
        # Record/disabled path only: a bounded synchronous loop that never POSTs.
        # It continues only while the task is still ``running`` and below its
        # target; reaching ``done`` or a >threshold pause stops dispatch.
        guard = 0
        while task["status"] == D.STATUS_RUNNING and guard < 10_000:
            if task["success_count"] >= task["target_n"]:
                break
            task, _ = self._dispatch_one_for_task(task, now_us)
            guard += 1
            now_us += 1  # keep ts strictly increasing within one call
        return 200, self._doc(task)

    def _require_fillable(self, task: dict) -> None:
        status = task["status"]
        if status == D.STATUS_DELETED:
            raise D.HedgeError(409, "invalid_state", "cannot fill a deleted task")
        if status == D.STATUS_DONE:
            raise D.HedgeError(409, "invalid_state", "task already done")
        # Human 2026-08-18：已终止（致命错误，需人工修正后新建任务）的卡也一律
        # 拒绝成交——与前端 inactive 按钮矩阵对齐；此前 live 分支可把 stopped
        # 卡置 running 复活（既有），fill 先置 running 后 dry-run 也染上，此门
        # 补拦两端。Human 裁决的「执行中/已暂停可成交」不含已终止。
        if status == D.STATUS_STOPPED:
            raise D.HedgeError(409, "invalid_state", "cannot fill a stopped task")
        if task.get("pause_reason") == D.PAUSE_REASON_AWAITING_MANUAL_START:
            if task.get("mode") == D.MODE_SMOOTH:
                raise D.HedgeError(
                    409,
                    "start_required",
                    "任务首次执行必须点击启动",
                )
            if task.get("task_type") == D.TASK_TYPE_CLOSE:
                raise D.HedgeError(
                    409,
                    "start_required",
                    "平仓任务首次执行必须点击启动，不能用成交按钮绕过启动确认",
                )
        # Single-leg exposure does not block fill (advisory, §4.5).

    # ----------------------------------------------------------------- reads

    def get_settings(self) -> tuple[int, dict]:
        return 200, settings_to_doc(self._store.get_settings(), self._mode)

    def get_logs(
        self, cursor_str, limit_raw,
        entries_cursor_str=None, entries_limit_raw=None,
        task_id=None,
    ) -> tuple[int, dict]:
        # task_id 模式（开单任务卡内嵌日志）：一次返回该任务的**全部** attempt + 两条腿，
        # 不分页、不与 entries_cursor 共用游标（amendment 17 已证明两套游标共用会重演 R4
        # 缺陷）。内嵌表只消费 attempts；logs/entries 在此模式下为空，避免与全局游标混用。
        # 无 task_id 时下方既有契约完全不变。
        if task_id is not None:
            task = self._store.get_task(task_id)
            task_attempts = []
            for attempt in self._store.list_attempts_for_task(task_id):
                legs = {
                    leg["leg"]: leg
                    for leg in self._store.list_legs_for_attempt(attempt["id"])
                }
                task_attempts.append(
                    attempt_to_doc(attempt, legs.get("spot"), legs.get("perp"))
                )
            return 200, {
                "logs": [],
                "attempts": task_attempts,
                "entries": [],
                "next_cursor": None,
                "entries_next_cursor": None,
                "smooth_market": self._smooth_market_doc(task),
                "smooth_dispatch_audits": [
                    log_to_doc(row)
                    for row in self._store.list_logs_for_task_kind(
                        task_id, "smooth_dispatch_audit",
                    )
                ],
            }
        limit = self._parse_limit(limit_raw)
        cursor_ts, cursor_id = self._parse_cursor(cursor_str)
        rows, has_more = self._store.list_logs_page(limit, cursor_ts, cursor_id)
        next_cursor = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = D.encode_cursor(last["ts_us"], last["id"])
        # Additive first-class attempt timeline (R4-1 / breakdown §3.4 / PRD
        # §9.2): projects the durable attempt + its two legs on the SAME
        # response, alongside the legacy logs/cursor. Covers PREPARED /
        # QUERYING / resolved attempts so the UI shows in-flight pairs mid-query.
        # The legacy logs list and the next_cursor contract are unchanged.
        attempt_rows = self._store.list_attempts_page(limit, cursor_ts, cursor_id)
        # Amendment 17 (opening-log-pagination-compatibility): the additive
        # ``entries`` timeline paginates on its OWN entries_limit /
        # entries_cursor / entries_next_cursor, fully independent of the legacy
        # cursor/limit/next_cursor above. The attempt and task-event tables are
        # two different (ts, id) sequences, so they cannot share the legacy
        # cursor — doing so re-surfaces task events on every page (the R4
        # defect). ``entries_next_cursor`` is derived from THIS page's last
        # unified entry, never from the legacy logs cursor.
        entries_limit = self._parse_entries_limit(entries_limit_raw)
        entries, entries_next_cursor = self._entries_page(
            entries_limit, entries_cursor_str
        )
        return 200, {
            "logs": [log_to_doc(r) for r in rows],
            "attempts": [attempt_to_doc(a, s, p) for (a, s, p) in attempt_rows],
            "entries": entries,
            "next_cursor": next_cursor,
            "entries_next_cursor": entries_next_cursor,
        }

    def _entries_page(
        self, entries_limit: int, entries_cursor_str: str | None,
    ) -> tuple[list[dict], str | None]:
        """§5 frozen additive entries timeline, paginated on its OWN cursor
        (amendment 17). Newest-first; field names frozen.

        Merges each attempt (any status — PREPARED, QUERYING, or resolved) with
        the task-level lifecycle events recorded on ``hedge_open_log`` into one
        stable stream keyed by ``(ts_us, rank, source_id)`` DESC. The two source
        tables have independent ``id`` sequences, so a fixed ``rank`` (attempt=0,
        event=1) is the deterministic same-ts tie-break — never a clash, never a
        duplicate across pages.

        Each source is read with ``entries_limit + 1`` and the SAME decoded
        three-part cursor; merging the two windows and taking the top
        ``entries_limit + 1`` yields the unified page, so has-more is read from
        the unified stream (the (limit+1)th row). ``entries_next_cursor`` is the
        last entry's key when has-more, else ``None``. Legacy logs/attempts/
        next_cursor are untouched by this path.
        """
        cur_ts, cur_rank, cur_id = self._parse_entries_cursor(entries_cursor_str)
        window = entries_limit + 1
        entries: list[dict] = []
        task_briefs: dict[str, dict] = {}

        def _brief(task_id: str) -> dict:
            brief = task_briefs.get(task_id)
            if brief is None:
                row = self._store.get_task(task_id) or {}
                brief = {
                    "coin": row.get("coin"),
                    "direction": row.get("direction"),
                    "position_side_mode": row.get("position_side_mode"),
                    "status": row.get("status"),
                }
                task_briefs[task_id] = brief
            return brief

        for attempt, spot_leg, perp_leg in self._store.list_attempts_entries_page(
            window, cur_ts, cur_rank, cur_id
        ):
            brief = _brief(attempt.get("task_id"))
            entries.append(self._attempt_to_entry(attempt, spot_leg, perp_leg, brief))
        for ev in self._store.list_task_event_logs_page(
            window, _ENTRY_EVENT_KINDS, cur_ts, cur_rank, cur_id
        ):
            brief = _brief(ev["task_id"])
            entries.append(self._event_to_entry(ev, brief))
        entries.sort(
            key=lambda e: (e["_sort_ts"] or 0, e["_sort_rank"], e["_sort_id"] or 0),
            reverse=True,
        )
        has_more = len(entries) > entries_limit
        entries = entries[:entries_limit]
        next_cursor = None
        if has_more and entries:
            last = entries[-1]
            next_cursor = D.encode_entries_cursor(
                last["_sort_ts"] or 0, last["_sort_rank"], last["_sort_id"] or 0
            )
        for e in entries:
            e.pop("_sort_ts", None)
            e.pop("_sort_rank", None)
            e.pop("_sort_id", None)
        return entries, next_cursor

    @staticmethod
    def _attempt_to_entry(
        attempt: dict, spot_leg: dict | None, perp_leg: dict | None, brief: dict,
    ) -> dict:
        """Project one attempt + both legs to the §5 entry shape (entry_type=attempt)."""
        direction = attempt.get("direction") or brief.get("direction")
        spot_side, perp_side = _entry_side(direction, brief.get("position_side_mode"))
        spot_base = D.Decimal((spot_leg or {}).get("cumulative_base_qty") or "0")
        perp_base = D.Decimal((perp_leg or {}).get("cumulative_base_qty") or "0")
        overall = _entry_attempt_overall(
            attempt.get("pair_outcome"),
            (spot_leg or {}).get("exchange_status"),
            (perp_leg or {}).get("exchange_status"),
        )
        # submitted_ts = earliest leg dispatch; final_ts = latest leg query/resolve.
        dispatches = [
            (spot_leg or {}).get("dispatched_at_us"),
            (perp_leg or {}).get("dispatched_at_us"),
        ]
        queries = [
            (spot_leg or {}).get("last_query_at_us"),
            (perp_leg or {}).get("last_query_at_us"),
        ]
        valid_dispatches = [d for d in dispatches if d]
        valid_queries = [q for q in queries if q]
        return {
            "entry_id": f"attempt:{attempt.get('attempt_uuid')}",
            "entry_type": "attempt",
            "task_id": attempt.get("task_id"),
            "coin": brief.get("coin"),
            "direction": direction,
            "attempt_seq": attempt.get("attempt_seq"),
            "created_ts": D.us_to_iso(attempt.get("created_at_us")),
            "submitted_ts": D.us_to_iso(min(valid_dispatches)) if valid_dispatches else None,
            "final_ts": D.us_to_iso(max(valid_queries)) if valid_queries else None,
            "q_common": attempt.get("q_common"),
            "planned_quote_amount": None,
            "spot": _entry_spot_leg(spot_leg, spot_side),
            "perp": _entry_perp_leg(perp_leg, perp_side),
            "residual": D.fmt_decimal(spot_base - perp_base),
            "overall_result": overall,
            "error_category": attempt.get("error_category"),
            "error_code": attempt.get("error_code"),
            "error_reason_zh": attempt.get("error_reason_zh"),
            "next_action": _entry_next_action(brief.get("status"), overall),
            "_sort_ts": attempt.get("created_at_us"),
            "_sort_rank": _ENTRY_ATTEMPT_RANK,
            "_sort_id": attempt.get("id"),
        }

    @staticmethod
    def _event_to_entry(ev: dict, brief: dict) -> dict:
        """Project one task event to the §5 entry shape (entry_type=task_event)."""
        raw = ev["payload"]
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            payload = raw
        payload = payload if isinstance(payload, dict) else {}
        kind = ev["kind"]
        overall = {
            "task_stopped": "task_stopped",
            "threshold_paused": "task_paused",
            # F3: task-local pauses (insufficient funds, collateral cap, and the
            # order_state_unknown manual-verification closure) all record the
            # ``task_paused`` kind; the entries timeline must render them as a
            # pause with next_action=paused (previously this kind fell through to
            # the wait branch with overall_result=None).
            "task_paused": "task_paused",
            # 2026-08-07: a terminal task's order_state_unknown closure is NOT a
            # pause — it has its own result so the timeline stops claiming the
            # task was paused and can be resumed.
            "order_state_unknown_final": "manual_verification",
        }.get(kind)
        if kind == "task_stopped":
            next_action, error_category = "stopped", "fatal"
        elif kind == "order_state_unknown_final":
            next_action, error_category = "verify_manually", None
        elif kind in ("threshold_paused", "task_paused"):
            next_action, error_category = "paused", None
        else:  # rate_limited / preflight_incomplete: a wait, not an attempt outcome
            next_action, error_category = "waiting_query", None
        return {
            "entry_id": f"event:{ev['id']}",
            "entry_type": "task_event",
            "task_id": ev["task_id"],
            "coin": brief.get("coin"),
            "direction": brief.get("direction"),
            "attempt_seq": None,
            "created_ts": D.us_to_iso(ev["ts_us"]),
            "submitted_ts": None,
            "final_ts": None,
            "q_common": None,
            "planned_quote_amount": None,
            "spot": dict(_NULL_SPOT_LEG),
            "perp": dict(_NULL_PERP_LEG),
            "residual": None,
            "overall_result": overall,
            "error_category": error_category,
            "error_code": None,
            "error_reason_zh": payload.get("reason_zh"),
            "next_action": next_action,
            "_sort_ts": ev["ts_us"],
            "_sort_rank": _ENTRY_EVENT_RANK,
            "_sort_id": ev["id"],
        }

    def get_positions(self) -> tuple[int, dict]:
        return 200, {"positions": self._store.aggregate_positions()}

    def _parse_limit(self, limit_raw) -> int:
        if limit_raw is None:
            return D.LIMIT_DEFAULT
        try:
            value = int(str(limit_raw).strip())
        except (TypeError, ValueError) as exc:
            raise D.HedgeError(400, "invalid_limit", "limit must be an integer") from exc
        return D.validate_limit(value)

    def _parse_cursor(self, cursor_str):
        if cursor_str is None or cursor_str == "":
            return None, None
        decoded = D.decode_cursor(cursor_str)
        if decoded is None:
            raise D.HedgeError(400, "invalid_cursor", "cursor is not a valid opaque token")
        return decoded

    def _parse_entries_limit(self, limit_raw) -> int:
        # Amendment 17: same parse/default discipline as the legacy limit, but
        # the entries stream is capped at ENTRIES_LIMIT_MAX (1..100).
        if limit_raw is None:
            return D.validate_entries_limit(None)
        try:
            value = int(str(limit_raw).strip())
        except (TypeError, ValueError) as exc:
            raise D.HedgeError(
                400, "invalid_limit", "entries_limit must be an integer"
            ) from exc
        return D.validate_entries_limit(value)

    def _parse_entries_cursor(self, cursor_str):
        if cursor_str is None or cursor_str == "":
            return None, None, None
        decoded = D.decode_entries_cursor(cursor_str)
        if decoded is None:
            raise D.HedgeError(
                400, "invalid_cursor", "entries_cursor is not a valid opaque token"
            )
        return decoded

    # ------------------------------------------------------------- start gate

    def set_start_gate(self, enabled: bool) -> tuple[int, dict]:
        """Python-level seam to toggle the durable global Start gate (§9).

        Round 1 does not expose an HTTP toggle (settings are read-only per the
        frozen contract); tests and the operator use this seam. Live dispatch
        requires the gate on AND ``APP_HEDGE_EXECUTOR=live`` AND a live executor
        AND a fresh passing preflight.
        """
        self._store.set_start_gate(enabled, self._wall_us())
        self._notify_all_smooth()
        if enabled:
            for task in self._store.list_tasks(D.STATUS_RUNNING):
                if task.get("mode") == D.MODE_SMOOTH:
                    self.ensure_worker(task["id"])
        return self.get_settings()

    def put_start_gate(self, body) -> tuple[int, dict]:
        """Concurrency-safe, confirmation-gated write of the durable Start gate
        (S3 / ADR-H2 / 10-design §2.3). Open and close share one endpoint; each
        direction requires an explicit ``confirm: true``.

        Body ``{"enabled": <bool>, "confirm": true, "version": <int>}``:
        - ``enabled`` strict bool (true=open / false=close);
        - ``confirm`` must be the literal ``true`` (a bare POST cannot open the
          gate) — else 400 ``confirmation_required``;
        - ``version`` strict int (bool excluded) equal to the current settings
          row's ``version`` — else 409 ``version_conflict`` carrying the current
          settings doc so the caller can refresh and retry.

        On a hit the gate UPDATE and its ``start_gate_changed`` audit row land in
        one store transaction; the response is the updated settings doc.
        """
        if not isinstance(body, dict):
            raise D.HedgeError(400, "invalid_json", "request body must be a JSON object")
        D.reject_unknown_keys(body, _START_GATE_BODY_KEYS)
        enabled = body.get("enabled")
        if not isinstance(enabled, bool):
            raise D.invalid_field("enabled", "must be a boolean")
        if body.get("confirm") is not True:
            raise D.HedgeError(
                400, "confirmation_required", "开单闸门变更必须显式确认"
            )
        version = body.get("version")
        if isinstance(version, bool) or not isinstance(version, int):
            raise D.invalid_field("version", "must be an integer")
        result = self._store.set_start_gate_cas(enabled, version, self._wall_us())
        if result is None:
            raise D.HedgeError(
                409, "version_conflict", "设置已被其他会话修改，请刷新后重试",
                extra={"settings": settings_to_doc(self._store.get_settings(), self._mode)},
            )
        self._notify_all_smooth()
        if enabled:
            for task in self._store.list_tasks(D.STATUS_RUNNING):
                if task.get("mode") == D.MODE_SMOOTH:
                    self.ensure_worker(task["id"])
        return 200, settings_to_doc(result, self._mode)

    def put_close_gate(self, body) -> tuple[int, dict]:
        """Concurrency-safe, confirmation-gated write of the close gate
        （功能三，镜像 put_start_gate ADR-H2）。Body
        ``{"enabled": <bool>, "confirm": true, "version": <int>}``：``confirm``
        必须为字面 true（防裸 POST 开闸）；``version`` 为 CAS 守卫（冲突 409）。
        审计 kind ``close_gate_changed``（sentinel ``task_id="close-gate"``）。"""
        if not isinstance(body, dict):
            raise D.HedgeError(400, "invalid_json", "request body must be a JSON object")
        D.reject_unknown_keys(body, _START_GATE_BODY_KEYS)
        enabled = body.get("enabled")
        if not isinstance(enabled, bool):
            raise D.invalid_field("enabled", "must be a boolean")
        if body.get("confirm") is not True:
            raise D.HedgeError(
                400, "confirmation_required", "平仓闸门变更必须显式确认"
            )
        version = body.get("version")
        if isinstance(version, bool) or not isinstance(version, int):
            raise D.invalid_field("version", "must be an integer")
        result = self._store.set_close_gate_cas(enabled, version, self._wall_us())
        if result is None:
            raise D.HedgeError(
                409, "version_conflict", "设置已被其他会话修改，请刷新后重试",
                extra={"settings": settings_to_doc(self._store.get_settings(), self._mode)},
            )
        # smooth-close C12①④（镜像 put_start_gate）：关闸/开闸都唤醒等待中的
        # gate（等待循环检查 is_close_gate_on 并清门退出）；开闸后为 running
        # 的 smooth 任务重新拉起 worker（否则关闸退出后的任务躺死，Human 以为
        # 系统坏了），不需要人工再点一次启动。
        self._notify_all_smooth()
        if enabled:
            for task in self._store.list_tasks(D.STATUS_RUNNING):
                if task.get("mode") == D.MODE_SMOOTH:
                    self.ensure_worker(task["id"])
        return 200, settings_to_doc(result, self._mode)

    # -------------------------------------------------------- smooth-open gate

    @staticmethod
    def _smooth_keys(task: dict) -> tuple[tuple[str, str, str], ...]:
        return (
            ("binance", "spot", D.spot_symbol_of(task)),
            ("binance", "swap", task["coin"]),
        )

    def _smooth_wake(self, task_id: str) -> _GateWake:
        with self._smooth_lock:
            wake = self._smooth_wakes.get(task_id)
            if wake is None:
                wake = _GateWake()
                self._smooth_wakes[task_id] = wake
            return wake

    def _notify_smooth_task(self, task_id: str) -> None:
        with self._smooth_lock:
            wake = self._smooth_wakes.get(task_id)
        if wake is None:
            return
        with wake.condition:
            wake.version += 1
            wake.condition.notify_all()

    def _notify_all_smooth(self) -> None:
        with self._smooth_lock:
            task_ids = list(self._smooth_wakes)
        for task_id in task_ids:
            self._notify_smooth_task(task_id)

    def _on_smooth_market_change(self, key) -> None:
        with self._smooth_lock:
            task_ids = [
                task_id for task_id, keys in self._smooth_subscriptions.items()
                if key in keys
            ]
        for task_id in task_ids:
            self._notify_smooth_task(task_id)

    def _ensure_smooth_subscriptions(self, task: dict) -> None:
        provider = self._market_provider
        if provider is None:
            return
        task_id = task["id"]
        keys = self._smooth_keys(task)
        subscribe = getattr(provider, "subscribe", None)
        if not callable(subscribe):
            return
        with self._smooth_lock:
            if task_id in self._smooth_subscriptions:
                return
        subscribed = []
        registered = False
        try:
            for key in keys:
                subscribe(key)
                subscribed.append(key)
            with self._smooth_lock:
                if task_id not in self._smooth_subscriptions:
                    self._smooth_subscriptions[task_id] = keys
                    registered = True
        finally:
            if not registered:
                release = getattr(provider, "release", None)
                if callable(release):
                    for key in subscribed:
                        try:
                            release(key)
                        except Exception:
                            pass

    def _release_smooth_subscriptions(self, task_id: str) -> None:
        with self._smooth_lock:
            keys = self._smooth_subscriptions.pop(task_id, ())
            self._smooth_wakes.pop(task_id, None)
        release = getattr(self._market_provider, "release", None)
        if callable(release):
            for key in keys:
                try:
                    release(key)
                except Exception:
                    pass

    @staticmethod
    def _snapshot_quote(snapshot) -> D.L1Quote | None:
        if snapshot is None or getattr(snapshot, "status", None) != "live":
            return None
        try:
            quote = D.L1Quote(
                snapshot.bid_price, snapshot.bid_qty,
                snapshot.ask_price, snapshot.ask_qty,
            )
        except AttributeError:
            return None
        return quote if all(value.is_finite() and value > 0 for value in quote) else None

    def _read_smooth_sides(self, task: dict):
        latest = getattr(self._market_provider, "latest", None)
        spot_snap = perp_snap = None
        if callable(latest):
            spot_key, perp_key = self._smooth_keys(task)
            spot_snap, perp_snap = latest(spot_key), latest(perp_key)
        return spot_snap, perp_snap

    def _eval_smooth_from_sides(
        self, task: dict, spot_snap, perp_snap, direction: str | None = None,
    ) -> D.SmoothGateEval:
        try:
            threshold = Decimal(task.get("slippage_threshold_pct") or "0")
            q_common = Decimal(task.get("q_common") or "0")
        except (InvalidOperation, ValueError, TypeError):
            threshold, q_common = Decimal(0), Decimal(0)
        return D.evaluate_smooth_gate(
            direction or task["direction"],
            threshold,
            q_common,
            self._snapshot_quote(spot_snap),
            self._snapshot_quote(perp_snap),
        )

    def _smooth_eval(self, task: dict, direction: str | None = None) -> D.SmoothGateEval:
        spot_snap, perp_snap = self._read_smooth_sides(task)
        return self._eval_smooth_from_sides(task, spot_snap, perp_snap, direction)

    @staticmethod
    def _smooth_audit_side(snapshot) -> dict:
        if snapshot is None:
            return {
                "status": None, "received_at_us": None,
                "bid": None, "bid_qty": None, "ask": None, "ask_qty": None,
            }
        live = getattr(snapshot, "status", None) == "live"
        return {
            "status": getattr(snapshot, "status", None),
            "received_at_us": getattr(snapshot, "received_at_us", None),
            "bid": format(snapshot.bid_price, "f") if live else None,
            "bid_qty": format(snapshot.bid_qty, "f") if live else None,
            "ask": format(snapshot.ask_price, "f") if live else None,
            "ask_qty": format(snapshot.ask_qty, "f") if live else None,
        }

    def _build_smooth_pass_audit(
        self, task: dict, gate_seq: int, reason: str, now_us: int,
        result: D.SmoothGateEval, spot_snap, perp_snap,
    ) -> dict:
        def _dec(value):
            return format(value, "f") if value is not None else None

        return {
            "gate_seq": gate_seq,
            "reason": reason,
            "direction": task["direction"],
            # C16 §4.2-4（验收 21）：审计显式记录实际参与评估的方向（close 为
            # 翻转后方向），读者无须自行换算；open 任务两字段恒等。
            "eval_direction": D.evaluation_direction(task),
            "threshold": task.get("slippage_threshold_pct"),
            "spot": self._smooth_audit_side(spot_snap),
            "perp": self._smooth_audit_side(perp_snap),
            "spread_pct": _dec(result.spread_pct),
            "spot_coverage": _dec(result.spot_coverage),
            "perp_coverage": _dec(result.perp_coverage),
            "spread_pass": result.spread_pass,
            "coverage_pass": result.coverage_pass,
            "market_pass": result.market_pass,
            "gate_pass_at_us": now_us,
            "gate_pass_mono_us": self._mono_us(),
            "marks": {},
        }

    @staticmethod
    def _smooth_audit_mark(audit: dict | None, name: str, mono_us) -> None:
        if audit is None or not callable(mono_us):
            return
        origin = audit.get("gate_pass_mono_us")
        if origin is None:
            return
        audit.setdefault("marks", {})[name] = mono_us() - origin

    @staticmethod
    def _smooth_audit_durations(audit: dict) -> dict:
        marks = audit.get("marks") or {}
        serial = (
            "service_dispatch",
            "request_assembled",
            "prepare_started",
            "prepare_committed",
            "executor_entered",
            "executor_joined",
            "executor_returned",
        )
        durations = {}
        for left, right in zip(serial, serial[1:]):
            if left in marks and right in marks:
                durations[f"{left}_to_{right}"] = marks[right] - marks[left]
        for leg in ("spot", "perp"):
            key = f"{leg}_order_client_call_started"
            if key in marks:
                durations[f"gate_to_{key}"] = marks[key]
            leg_serial = (
                f"{leg}_thread_started",
                f"{leg}_order_client_call_started",
                f"{leg}_order_client_call_returned",
                f"{leg}_thread_finished",
            )
            for left, right in zip(leg_serial, leg_serial[1:]):
                if left in marks and right in marks:
                    durations[f"{left}_to_{right}"] = marks[right] - marks[left]
        return durations

    @staticmethod
    def _smooth_side_doc(snapshot) -> dict | None:
        if snapshot is None:
            return None
        live = getattr(snapshot, "status", None) == "live"
        return {
            "status": getattr(snapshot, "status", "disconnected"),
            "received_at_us": getattr(snapshot, "received_at_us", None),
            "bid": format(snapshot.bid_price, "f") if live else None,
            "bid_qty": format(snapshot.bid_qty, "f") if live else None,
            "ask": format(snapshot.ask_price, "f") if live else None,
            "ask_qty": format(snapshot.ask_qty, "f") if live else None,
        }

    def _smooth_market_doc(self, task: dict | None) -> dict | None:
        if task is None or task.get("mode") != D.MODE_SMOOTH:
            return None
        latest = getattr(self._market_provider, "latest", None)
        spot_snap = perp_snap = None
        if callable(latest):
            spot_key, perp_key = self._smooth_keys(task)
            spot_snap, perp_snap = latest(spot_key), latest(perp_key)
        forward = self._smooth_eval(task, D.DIR_FORWARD)
        reverse = self._smooth_eval(task, D.DIR_REVERSE)
        # C16 §4.2-2：任务卡读模型的"当前方向"取评估方向——close forward 任务
        # 参与判定的是 reverse 那一组价格与数量（spot.bid + perp.ask）。
        current = forward if D.evaluation_direction(task) == D.DIR_FORWARD else reverse

        def coverage_pct(value):
            if value is None:
                return None
            return format(
                (value * Decimal(100)).quantize(Decimal("0.01"), ROUND_HALF_UP), "f"
            )

        wait_reason = current.wait_reason
        if task.get("smooth_gate_seq") is None:
            wait_reason = "当前无活动平滑门"
        elif task.get("smooth_gate_force_requested"):
            wait_reason = "已人工放行，等待 worker 原子消费"
        elif (
            (task.get("task_type") or D.TASK_TYPE_OPEN) == D.TASK_TYPE_CLOSE
            and "开单率" in wait_reason
        ):
            # C16 §4.2-7：平仓卡不得出现"开单率"字样（service 层改写文案，
            # evaluate_smooth_gate 判定逻辑不动；开单任务文案零 diff）。
            wait_reason = wait_reason.replace("开单率", "平仓率")
        return {
            "spot": self._smooth_side_doc(spot_snap),
            "perp": self._smooth_side_doc(perp_snap),
            "forward_spread_pct": (
                format(forward.spread_pct, "f") if forward.spread_pct is not None else None
            ),
            "reverse_spread_pct": (
                format(reverse.spread_pct, "f") if reverse.spread_pct is not None else None
            ),
            "spot_coverage_pct": coverage_pct(current.spot_coverage),
            "perp_coverage_pct": coverage_pct(current.perp_coverage),
            "spread_pass": current.spread_pass,
            "coverage_pass": current.coverage_pass,
            "gate_pass": current.market_pass,
            "wait_reason": wait_reason,
        }

    def _wait_for_smooth_gate(
        self, task: dict, now_us: int,
    ) -> tuple[dict, int, str, int, dict] | None:
        gate_seq = task["scheduled_attempt_count"] + 1
        current = self._store.open_smooth_gate(task["id"], gate_seq, now_us)
        if current is None:
            return None
        try:
            self._ensure_smooth_subscriptions(current)
        except Exception:
            self._pause_task_local(
                current, D.PAUSE_REASON_PREFLIGHT_INCOMPLETE, None,
                self._wall_us(),
                pause_zh=(
                    "公共盘口订阅失败，任务已暂停（fail-closed，未发单）；"
                    "请检查网络后手动恢复"
                ),
            )
            return None
        wake = self._smooth_wake(task["id"])
        while True:
            with wake.condition:
                version = wake.version
            stop_event = self._stop_events.get(task["id"])
            if stop_event is not None and stop_event.is_set():
                return None
            current = self._store.get_task(task["id"])
            if current is None or current["status"] != D.STATUS_RUNNING:
                return None
            if not self.is_start_gate_on():
                self._store.clear_smooth_gate(task["id"], self._wall_us())
                return None
            # smooth-close C12②：等待循环同时受平仓闸门约束——关闸立即唤醒并
            # 清门（否则存在长达 5 分钟的"关闸后仍发出一笔"窗口）；open 任务
            # 不检查（零回归）。
            if (
                (current.get("task_type") or D.TASK_TYPE_OPEN) == D.TASK_TYPE_CLOSE
                and not self.is_close_gate_on()
            ):
                self._store.clear_smooth_gate(task["id"], self._wall_us())
                return None
            if current.get("smooth_gate_seq") != gate_seq:
                return None
            now_us = self._wall_us()
            deadline = current["smooth_gate_started_at_us"] + D.SMOOTH_GATE_WINDOW_US
            spot_snap, perp_snap = self._read_smooth_sides(current)
            # C16 §4.2-1：close 任务用翻转后的评估方向（forward close 的两腿
            # 实际吃 spot 买一 + perp 卖一 = 开单 reverse 公式操作数）。
            result = self._eval_smooth_from_sides(
                current, spot_snap, perp_snap, D.evaluation_direction(current),
            )
            if current.get("smooth_gate_force_requested"):
                reason = D.PASS_REASON_MANUAL
            elif result.market_pass:
                reason = D.PASS_REASON_MARKET
            elif now_us >= deadline:
                reason = D.PASS_REASON_TIMEOUT
            else:
                timeout = max((deadline - now_us) / 1_000_000, 0)
                with wake.condition:
                    wake.condition.wait_for(
                        lambda: wake.version != version, timeout=timeout
                    )
                continue
            audit = self._build_smooth_pass_audit(
                current, gate_seq, reason, now_us, result, spot_snap, perp_snap,
            )
            return current, gate_seq, reason, now_us, audit

    # -------------------------------------------------------- task-local workers
    #
    # Amendment 21 binding runtime contract: there is NO long-lived global
    # guardian/scanner. A task has a bounded-lifetime local worker ONLY while it
    # is actively running or reconciling its own one active pair. The worker owns
    # exactly its own pair: preflight -> durable reserve -> concurrent two-leg
    # submit -> query only its own two legs to terminal -> one atomic settlement
    # -> pair N+1 only while the task remains running. It exits on
    # done / paused / stopped / deleted / Start-gate-off / preflight-incomplete
    # (fail-closed); a one-shot recovery discovery or a manual Start/recover
    # relaunches it. Per-task ownership is durable: the single-worker registry
    # below plus the store's atomic in-flight guard (prepare_attempt) prevent two
    # triggers from owning or sending the same task/pair, and a restart resumes
    # by querying saved client order IDs only (never resends — ADR-2).

    def ensure_worker(
        self, task_id: str, *, relaunch_after_current: bool = False,
    ) -> bool:
        """Create or durably claim exactly ONE local worker for ``task_id``
        (amendment 21). Single critical section under ``_workers_lock``: if a
        live worker already owns the task it is reused; a dead/stale registry
        entry is replaced. The worker is a daemon thread bounded to this task
        only — it never scans or queries another task. Returns True iff a worker
        is (now) running for this task."""
        with self._workers_lock:
            existing = self._workers.get(task_id)
            if existing is not None and existing.is_alive():
                if relaunch_after_current:
                    with self._smooth_lock:
                        self._smooth_relaunch_after_exit.add(task_id)
                return True
            ev = self._stop_events.get(task_id)
            if ev is None:
                ev = threading.Event()
                self._stop_events[task_id] = ev
            else:
                ev.clear()
            thread = threading.Thread(
                target=self._run_task_worker,
                args=(task_id,),
                name=f"hedge-worker-{task_id}",
                daemon=True,
            )
            self._workers[task_id] = thread
            # Review-1 r3 P2-2: a freshly spawned worker has no prior exit
            # reason (also cleared on entering RUNNING in set_task_status).
            try:
                self._store.set_worker_exit_reason(task_id, None, self._wall_us())
            except Exception:
                pass
            thread.start()
            return True

    def _run_task_worker(self, task_id: str) -> None:
        """The bounded worker loop (amendment 21). Repeatedly runs one round
        (:meth:`_worker_round`) until the round says exit. Pacing (a wait on the
        per-task stop event for the scheduler interval) happens ONLY when the
        task still has in-flight legs to re-query — a pair whose legs resolved
        terminal advances immediately to pair N+1 (per-task serial, A-9); a round
        that exits never paces. The executor is invoked with no store transaction
        held (Q6): every executor call sits between short store transactions,
        never inside one."""
        try:
            while not self._worker_round(task_id):
                # Pace only while own non-terminal legs wait to be re-queried; a
                # resolved pair proceeds straight to the next group.
                if self._store.list_non_terminal_legs_for_task(task_id):
                    interval_s = (self._store.get_interval_us() or 1) / 1_000_000
                    ev = self._stop_events.get(task_id)
                    if ev is not None:
                        # Deterministic pacing wait (cadence-500ms task): the
                        # prior [0.75, 1.0] jitter is removed — it was never
                        # requested and it cut the first-query safety margin by
                        # up to 25% while doing nothing for the rate limit.
                        ev.wait(interval_s)
        except Exception:
            # Last-resort containment: a worker error must not leak; the task's
            # durable state is authoritative and a recovery discovery relaunches.
            try:
                self._store.set_worker_exit_reason(
                    task_id, D.WORKER_EXIT_WORKER_ERROR, self._wall_us())
            except Exception:
                pass
        finally:
            self._release_smooth_subscriptions(task_id)
            with self._workers_lock:
                if self._workers.get(task_id) is threading.current_thread():
                    self._workers.pop(task_id, None)
            with self._smooth_lock:
                relaunch = task_id in self._smooth_relaunch_after_exit
                self._smooth_relaunch_after_exit.discard(task_id)
            # Drop the exiting worker's process-local retry counters before a
            # requested resume launches the replacement.
            self._clear_task_leg_retries(task_id)
            if relaunch:
                stop_event = self._stop_events.get(task_id)
                if (
                    stop_event is None or not stop_event.is_set()
                ):
                    task = self._store.get_task(task_id)
                    if (
                        task is not None
                        and task["status"] == D.STATUS_RUNNING
                        and self.is_start_gate_on()
                    ):
                        self.ensure_worker(task_id)

    def _clear_task_leg_retries(self, task_id: str) -> None:
        """F1: drop every per-leg query-retry counter of one task. Called when a
        leg reaches terminal state (in :meth:`_reconcile_own_legs`) and when the
        task's worker exits (:meth:`_run_task_worker` finally) so the in-process
        dict cannot grow without bound. Best-effort: the store reads are for
        enumerating the task's legs only and must never mask a worker exit."""
        try:
            for attempt in self._store.list_attempts_for_task(task_id):
                for leg in self._store.list_legs_for_attempt(attempt["id"]):
                    self._leg_query_retries.pop(leg["id"], None)
        except Exception:
            pass

    def _pump_worker(self, task_id: str, max_rounds: int = 64) -> int:
        """TEST SEAM (amendment 21): synchronously run the task-local worker loop
        body for up to ``max_rounds`` rounds (or until a round exits), with NO
        background thread and NO pacing wait. This is the deterministic offline
        replacement for the old synchronous live tick — it lets the review-2
        regressions drive a task's worker step-by-step without a sleep race.
        Returns the number of rounds actually run."""
        # P2-1 (Review-1 r4): register the per-task stop event ONLY on first
        # use (a fresh threading.Event() is already cleared) and leave an
        # existing one UNTOUCHED. The prior r3 P3 change cleared it on every
        # call, which swallowed any stop event post_pause / post_delete may
        # have set — making R3/R4 vacuous (the second _step wiped the pause's
        # signal, so both passed even with the _wake_worker interrupt present).
        # Keeping an existing event lets those regressions genuinely fail if the
        # interrupt is ever re-introduced, while a fresh task still gets a clean
        # cleared event on its first pump.
        with self._workers_lock:
            if self._stop_events.get(task_id) is None:
                self._stop_events[task_id] = threading.Event()
        rounds = 0
        while rounds < max_rounds:
            rounds += 1
            if self._worker_round(task_id):
                break
        return rounds

    def _worker_exit(self, task_id: str, reason: str) -> bool:
        """Record the stable worker exit reason (Review-1 r3 P2-2) and tell the
        loop to stop. Best-effort: a store failure here must not mask the exit."""
        try:
            self._store.set_worker_exit_reason(task_id, reason, self._wall_us())
        except Exception:
            pass
        return True

    def _worker_round(self, task_id: str) -> bool:
        """One iteration of the worker loop. Returns True when the worker should
        EXIT (bounded lifecycle), False to continue. Order (Q2: drain-before-
        exit): non-terminal own legs are ALWAYS queried to terminal first,
        regardless of task status — so a 429 / insufficient / manual-pause entered
        mid-pair still drains its in-flight orders before the worker leaves.

        Drain signals (a 429 or a confirmed insufficient-funds fact observed on a
        leg) pause THIS task only (worker exits after drain); other tasks are
        untouched. With no in-flight legs, the worker exits unless the task is
        RUNNING, the Start gate is on, and the target is not yet met — in which
        case it dispatches one more pair (durable-before-send; no resend)."""
        stop_event = self._stop_events.get(task_id)
        if stop_event is not None and stop_event.is_set():
            return self._worker_exit(task_id, D.WORKER_EXIT_STOPPED_EVENT)
        task = self._store.get_task(task_id)
        if task is None:
            return self._worker_exit(task_id, D.WORKER_EXIT_TASK_MISSING)
        now_us = self._wall_us()
        # Q2: drain own non-terminal legs first (rate_limited -> pause + exit).
        drain_signal = self._reconcile_own_legs(task_id, task, now_us)
        if drain_signal == D.SIGNAL_RATE_LIMITED:
            self._pause_task_local(
                task, D.PAUSE_REASON_RATE_LIMITED, None, now_us, kind="rate_limited",
            )
            # R2-F2: a query-phase 429 pauses THIS task and EXITS — the pending
            # legs are kept non-terminal (never resent) and the worker does NOT
            # loop back into the throttle. The operator resumes manually; a drain-
            # only worker on recovery re-queries the saved client IDs.
            return True
        if drain_signal == D.SIGNAL_ORDER_STATE_UNKNOWN:
            # Retry-counter task (F1): a leg whose queries stayed inconclusive
            # (5xx / timeout / malformed 2xx / verdict None) for the whole
            # LEG_QUERY_MAX_RETRIES budget. NOT a confirmed-absent signal (R2-F2),
            # so it is NOT terminalized — it is left non-terminal (never resent)
            # and THIS task pauses for manual verification, then the worker exits.
            # The operator checks the order on the exchange and manually resumes;
            # recovery re-queries by client ID only. F2: the pause is applied only
            # to running/paused tasks — deleted/done/stopped keep their sticky
            # status (the event is still recorded, visible on the entries
            # timeline, and the legs stay non-terminal for manual verification).
            self._signal_order_state_unknown_recovery(task, drain_signal, now_us)
            return True
        if drain_signal in D.SIGNAL_TASK_LOCAL_PAUSE:
            self._pause_from_signal(task, drain_signal, now_us)
            return False
        own = self._store.list_non_terminal_legs_for_task(task_id)
        if own:
            return False  # still draining this pair; keep querying (pacing in loop)
        # No in-flight legs: decide exit vs. next pair.
        if task["status"] != D.STATUS_RUNNING:
            return self._worker_exit(task_id, D.WORKER_EXIT_TASK_NOT_RUNNING)
        if not self.is_start_gate_on():
            if task.get("mode") == D.MODE_SMOOTH:
                self._store.clear_smooth_gate(task_id, now_us)
            return self._worker_exit(task_id, D.WORKER_EXIT_START_GATE_OFF)
        # 功能三：close 任务受独立平仓闸门（close_gate）约束（默认开，Human 已拍板）。
        # smooth-close C12⑤：因平仓闸门关闭退出时同样清门（现状只有 Start gate
        # 分支会清）——否则关闸退出后 gate 残留，再开闸可能复用旧窗口。
        if task.get("task_type") == D.TASK_TYPE_CLOSE and not self.is_close_gate_on():
            if task.get("mode") == D.MODE_SMOOTH:
                self._store.clear_smooth_gate(task_id, now_us)
            return self._worker_exit(task_id, D.WORKER_EXIT_CLOSE_GATE_OFF)
        # 功能三（close 完成判定，以合约腿为准；Human 2026-08：close 任务从 running
        # 变为其他状态必须先走合约无仓核实）：stage 2026-08-06 task 05 §4.1
        # （Human 决定 2）——平完判定不再每轮调用，只在「次数用完、准备收尾」这一
        # 状态转换点调用一次（仍实时，禁止读缓存：它决定「关周期 + 写结算日志」这一
        # 不可逆动作）。安全依据（Human 已拍板）：合约腿 reduceOnly=true 使无仓可平
        # 被交易所拒绝；现货腿数量与合约腿一致，多卖场景不成立。三分支语义不变：
        # flat → 关周期 + 结算日志；open → 部分平完成（done、周期不关）；failed →
        # fail-closed 暂停（绝不把「查不到」当「已平完」）。
        if task.get("task_type") == D.TASK_TYPE_CLOSE:
            if task["scheduled_attempt_count"] >= task["target_n"]:
                verdict = self._verify_close_flat(task, now_us)
                if verdict == "flat":
                    self._finalize_close_task(task, now_us)
                    return True
                if verdict == "failed":
                    self._pause_task_local(
                        task, D.PAUSE_REASON_CLOSE_VERIFY_FAILED, None, now_us,
                        kind="close_verify_failed",
                    )
                    return True
                # verdict == "open"：次数用完 + 还有仓 = 部分平完成：任务 done、
                # 周期不关（用户拍板语义）
                self._store.append_log(
                    task["id"], now_us, "close_partial_done",
                    {"coin": task["coin"], "direction": task["direction"],
                     "reason": "合约仍有仓，本次平仓目标完成，周期未关闭"},
                )
                self._store.set_task_status(task["id"], D.STATUS_DONE, now_us)
                return True
        else:
            if task["scheduled_attempt_count"] >= task["target_n"]:
                return self._worker_exit(task_id, D.WORKER_EXIT_TARGET_REACHED)
        # Dispatch the next pair (preflight -> reserve -> two-leg submit).
        gate_seq = None
        smooth_reason = None
        smooth_audit = None
        if task.get("mode") == D.MODE_SMOOTH:
            if (
                self._live_dispatch_capable()
                and (task.get("task_type") or D.TASK_TYPE_OPEN) == D.TASK_TYPE_OPEN
                and task.get("scheduled_attempt_count", 0) == 0
            ):
                lev_err = self._set_leverage_before_open(task, now_us)
                if lev_err is not None:
                    self._pause_task_local(
                        task, D.PAUSE_REASON_LEVERAGE_SET_FAILED,
                        D.SIGNAL_LEVERAGE_SET_FAILED, now_us,
                        kind="leverage_set_failed", pause_zh=lev_err,
                    )
                    return False
            if (
                (task.get("task_type") or D.TASK_TYPE_OPEN) == D.TASK_TYPE_CLOSE
                and not task.get("q_common")
            ):
                # smooth-close C15：无有效 q_common 的 running 任务 fail-closed
                # 落 paused + 既有 preflight_incomplete 中文原因并退出 worker
                # （下一轮 status!=running 即退）。不是"不建门然后返回"——那
                # 会让 _worker_round 在无在途腿时无节流紧密循环，且 timeout/
                # manual 放行仍可能以未取整的 single_amount 走下单链。仅拦
                # close：open smooth 的 NULL-q_common 历史行走 F-A 既有已接受
                # 行为，零回归。
                return self._pause_preflight_incomplete(task, now_us)
            gate = self._wait_for_smooth_gate(task, now_us)
            if gate is None:
                # Pause followed immediately by resume may happen before this
                # worker has left its old gate. If RUNNING is already restored,
                # loop in the same owner and open a fresh full window.
                stop_event = self._stop_events.get(task_id)
                if stop_event is not None and stop_event.is_set():
                    return self._worker_exit(task_id, D.WORKER_EXIT_STOPPED_EVENT)
                current = self._store.get_task(task_id)
                if (
                    current is not None
                    and current["status"] == D.STATUS_RUNNING
                    and self.is_start_gate_on()
                ):
                    return False
                return self._worker_exit(task_id, D.WORKER_EXIT_TASK_NOT_RUNNING)
            task, gate_seq, smooth_reason, now_us, smooth_audit = gate
        _, signal = self._dispatch_one_for_task(
            task,
            now_us,
            expected_gate_seq=gate_seq,
            smooth_pass_reason=smooth_reason,
            smooth_audit=smooth_audit,
        )
        if signal == D.SIGNAL_RATE_LIMITED:
            self._pause_task_local(
                task, D.PAUSE_REASON_RATE_LIMITED, None, now_us, kind="rate_limited",
            )
            return False  # 429: drain the just-submitted pair next round, then exit
        if signal in D.SIGNAL_TASK_LOCAL_PAUSE:
            self._pause_from_signal(task, signal, now_us)
            return False
        if signal == D.SIGNAL_PREFLIGHT_INCOMPLETE:
            # Stage 2026-08-06 task 05 §5 (Human decision 4): preflight failure
            # EXITS the worker WITHOUT retry — but the silent stall is fixed by
            # pausing the task with a Chinese reason naming the failed read.
            return self._pause_preflight_incomplete(task, now_us)
        if signal == D.SIGNAL_PREFLIGHT_FATAL:
            return self._worker_exit(task_id, D.WORKER_EXIT_PREFLIGHT_FATAL)
        if signal == D.SIGNAL_LEVERAGE_SET_FAILED:
            # 杠杆设置失败的暂停已由 _dispatch_one_for_task 落库（中文原因 + 错误
            # 详情 + leverage_set_failed 事件）；worker 直接退出本轮——不创建 attempt、
            # 不发单、不二次暂停。
            return False
        if signal == D.SIGNAL_SPOT_ROUTE_CHANGED:
            # 路由变化暂停已由 _dispatch_one_for_task 落库（spot_route_changed 事件）；
            # worker 直接退出本轮——不发单、不二次暂停（与杠杆失败同构）。
            return False
        if signal == D.SIGNAL_CLOSE_GUARD_FAILED:
            # 1000x / UM 持仓 / forward base 门已在 dispatch 内用精准原因暂停；
            # 不创建 attempt、不发单，也不再用通用原因覆盖。
            return False
        return False  # dispatched -> next round resolves/drains this pair

    # ------------------------------------------------------------------ #
    # 功能三：close 完成判定（以合约腿为准）与结算日志
    # ------------------------------------------------------------------ #
    def _verify_close_flat(self, task: dict, now_us: int) -> str:
        """核实该 symbol 合约是否已无仓。返回 ``"flat"`` / ``"open"`` / ``"failed"``。

        dry-run（executor 无 ``query_symbol_um_qty``）→ 模拟「无仓」（平完）；
        live → 实时查交易所合约持仓：净持仓 0 → flat，非零 → open，查询失败/
        响应不可解析 → failed（fail-closed，绝不把「查不到」当「已平完」）。
        """
        query = getattr(self._executor, "query_symbol_um_qty", None)
        if query is None:
            return "flat"  # dry-run 模拟：双腿成交即视为平完
        qty = query(task["coin"])
        if qty is None:
            return "failed"
        return "flat" if qty == 0 else "open"

    # ------------------------------------------------------------------ #
    # 平仓现货卖出重设计（2026-08）：现货余额检查/划转/复检 + USDT 回流
    # ------------------------------------------------------------------ #
    def _run_close_preparation(
        self, task: dict, now_us: int,
    ) -> tuple[Decimal | None, str | None, dict | None, str | None]:
        """close 备料三道门（smooth-close C4/C5 §4.1）：fresh preflight →
        `_close_um_position_error` → `_ensure_close_spot_balance`。

        两个调用方：立即平仓（immediate close）仍在 `_dispatch_one_for_task`
        的原调用点、**每一轮**执行；平滑平仓（smooth close）仅在 `post_start`
        备料时执行一次（成功后 `q_common` 已写入即跳过，C4）。

        成功返回 ``(q_common, position_side_mode, snapshot_record, None)``；
        任一门失败按既有路径落库（fatal 停止 / preflight_incomplete 记录 /
        两条 close 门 `_pause_task_local` 中文原因）并返回
        ``(None, None, None, signal)``；剩余轮次为 0 返回 ``(None, …, None)``
        （不发单也不暂停，与抽函数前一致）。
        """
        fresh = self._resolve_fresh_preflight(task)
        if fresh is None or not fresh.ok:
            if fresh is not None and fresh.fatal:
                self._stop_task_fatal_preflight(task, fresh, now_us)
                return None, None, None, D.SIGNAL_PREFLIGHT_FATAL
            self._record_preflight_incomplete(
                task, now_us, getattr(self._preflight, "last_failed_read", None),
            )
            return None, None, None, D.SIGNAL_PREFLIGHT_INCOMPLETE
        if fresh.q_common is None:
            self._record_preflight_incomplete(task, now_us, "q_common")
            return None, None, None, D.SIGNAL_PREFLIGHT_INCOMPLETE
        remaining_attempts = task["target_n"] - task["scheduled_attempt_count"]
        if remaining_attempts <= 0:
            return None, None, None, None
        required_qty = fresh.q_common * D.Decimal(remaining_attempts)
        um_err = self._close_um_position_error(task, required_qty)
        if um_err is not None:
            self._pause_task_local(
                task,
                D.PAUSE_REASON_CLOSE_UM_POSITION,
                D.SIGNAL_CLOSE_GUARD_FAILED,
                now_us,
                pause_zh=um_err,
            )
            return None, None, None, D.SIGNAL_CLOSE_GUARD_FAILED
        if task["direction"] == D.DIR_FORWARD:
            balance_err = self._ensure_close_spot_balance(
                task, now_us, required_qty,
            )
            if balance_err is not None:
                self._pause_task_local(
                    task,
                    D.PAUSE_REASON_CLOSE_SPOT_BALANCE,
                    D.SIGNAL_CLOSE_GUARD_FAILED,
                    now_us,
                    pause_zh=balance_err,
                )
                return None, None, None, D.SIGNAL_CLOSE_GUARD_FAILED
        return fresh.q_common, fresh.position_side_mode, fresh.snapshot_record, None

    def _log_close_transfer(self, task_id: str, now_us: int, action: str,
                            coin: str, asset: str, amount: str | None,
                            reason: str | None = None) -> None:
        """close_transfer 审计行（划转发起/成功/失败/回流），任务卡日志页可见。

        §4.2（Human 决定 3）：``ok`` 动作同时记录到进程内
        ``_close_transfer_done``——这是「本任务已划转」的事实记录（复用既有 ok
        事件点，不新增表），供 forward close 后续余额不足暂停时追加「可能是划转
        尚未到账」提示。进程内记录覆盖本任务多轮 worker 循环；重启后丢失只导致
        无提示（保守，不误导）。"""
        payload = {
            "action": action,
            "coin": coin,
            "asset": asset,
            "amount": amount,
        }
        if reason is not None:
            payload["reason"] = reason
        self._store.append_log(task_id, now_us, "close_transfer", payload)
        if action == "ok" and amount is not None:
            self._close_transfer_done[task_id] = (amount, asset)

    def _ensure_close_spot_balance(
        self, task: dict, now_us: int, required_base: Decimal,
    ) -> str | None:
        """forward close 每个 attempt 前：余额检查 + 必要时划转补足。

        仅 forward close（现货 SELL 走普通账户）；reverse close（买现货走统一账户）跳过：
        - 普通账户该币 free ≥ 计划卖量 → 无需划转，返回 None（§4.2：缓存放行——
          新鲜 ``spot_balances`` 缓存显示充足即可放行，0 网络请求；缓存不足/未知
          必须实时读确认）；
        - 实时确认仍不足 → ``universal_transfer('PORTFOLIO_MARGIN_MAIN', base, 差额)``
          一次 → 认划转返回结果（缺 ``tranId`` 内部抛错，异常即暂停路径，语义不变）
          → ``sleep(100ms)`` 让余额同步（经验值非保证）→ 返回 None；
        - 任一步失败/异常 → 中文错误，**不重试、不发单**。
        dry-run（executor 无 query_spot_free / universal_transfer）→ None（模拟余额足够）。

        §4.2（Human 决定 3）：不再做划转后置复检——只认划转返回结果（拿到 tranId
        即成功）；因划转是真实资金动作，缓存**只用于「放行」**，不足判断必须实时
        确认才动手；余额不足暂停文案附「可能是划转尚未到账」提示。
        """
        if task.get("task_type") != D.TASK_TYPE_CLOSE or task["direction"] != D.DIR_FORWARD:
            return None
        q_spot = getattr(self._executor, "query_spot_free", None)
        q_unified = getattr(self._executor, "query_unified_free", None)
        xfer = getattr(self._executor, "universal_transfer", None)
        if q_spot is None or xfer is None:
            if not self._live_dispatch_capable():
                return None  # dry-run：新门放行，且 record transport 永远零 POST
            return "现货余额查询/划转能力不可用（fail-closed，未发单）"
        sell_amount = required_base
        # 统一解析器（2026-08-07 unified-resolver）：平仓侧不再剥合约 coin 字符串，
        # 而是读任务固化的现货资产名（bStock SNXXUSDT -> SNXXB、1000x -> BONK）。
        base_asset = D.spot_base_of(task)
        # §4.2 缓存放行：新鲜 spot_balances 缓存显示充足 → 直接放行（0 请求，
        # 覆盖绝大多数情况）；缓存不足/未知 → 实时确认。
        cached_free = self._cached_spot_free(base_asset)
        if cached_free is not None and cached_free >= sell_amount:
            return None
        free = q_spot(base_asset)
        if free is None:
            return "现货账户余额查询失败，无法确认平仓现货余额（fail-closed，未发单）"
        if free >= sell_amount:
            return None
        diff = sell_amount - free
        # 划转前检查统一账户余额（2026-08）：不足直接提示，不盲划——
        # 否则划了才知道失败、日志只有 RuntimeError 无详情（COOKIE 现场教训）。
        # §4.2：可划转量为放行类，新鲜 unified_balances 缓存足够即放行，否则实时确认。
        unified_free = self._cached_unified_free(base_asset)
        if unified_free is None:
            unified_free = q_unified(base_asset) if q_unified is not None else None
        if unified_free is None:
            return (f"统一账户余额查询失败，无法确认可划转余额（fail-closed，未发单；"
                    f"普通现货账户缺 {D.fmt_decimal(diff)} {base_asset}）")
        if unified_free < diff:
            return (f"统一账户 {base_asset} 余额不足：剩 {D.fmt_decimal(unified_free)}，"
                    f"需划转 {D.fmt_decimal(diff)}（普通现货账户缺 {D.fmt_decimal(free)}），"
                    f"未划转未发单；请人工补充后恢复")
        self._log_close_transfer(task["id"], now_us, "start", task["coin"],
                                 base_asset, D.fmt_decimal(diff))
        try:
            xfer("PORTFOLIO_MARGIN_MAIN", base_asset, str(diff))
        except Exception as exc:
            # 2026-08：日志带交易所响应详情（body 截断 200），不只有异常类型名。
            detail = str(exc)[:200] or type(exc).__name__
            self._log_close_transfer(task["id"], now_us, "failed", task["coin"],
                                     base_asset, D.fmt_decimal(diff),
                                     reason=f"{type(exc).__name__}: {detail}")
            return f"划转补足现货失败（{detail}），未发单；请人工核对后恢复"
        self._log_close_transfer(task["id"], now_us, "ok", task["coin"],
                                 base_asset, D.fmt_decimal(diff))
        # §4.2（Human 决定 3）：不再后置复检——只认划转返回结果（tranId）；加
        # sleep(100ms) 让普通现货账户余额同步（经验值非保证，故余额不足文案带提示）。
        time.sleep(0.1)
        return None

    def _close_um_position_error(
        self, task: dict, required_qty: Decimal,
    ) -> str | None:
        """Validate signed UM position for the close quantity still scheduled.

        A fresh ``um_positions`` cache entry is preferred. Missing, malformed or
        older-than-300s cache data falls back to the executor's real-time symbol
        query. No row is flat (0), never an implicit pass.
        """
        qty = None
        cached = getattr(self._preflight, "cached_um_position_qty", None)
        if callable(cached):
            qty = cached(task["coin"])
        if qty is None:
            query = getattr(self._executor, "query_symbol_um_qty", None)
            if query is None:
                return "合约持仓查询能力不可用，无法确认可平数量（fail-closed，未发单）"
            try:
                qty = query(task["coin"])
            except Exception as exc:  # noqa: BLE001
                detail = str(exc)[:200] or type(exc).__name__
                return f"实时查询合约持仓失败（{detail}），未发单"
        if qty is None:
            return "实时查询合约持仓失败，无法确认可平数量（fail-closed，未发单）"
        try:
            position_qty = Decimal(str(qty))
        except (InvalidOperation, ValueError, TypeError):
            return "合约持仓数量无法解析（fail-closed，未发单）"
        if not position_qty.is_finite():
            return "合约持仓数量无法解析（fail-closed，未发单）"
        if task["direction"] == D.DIR_FORWARD:
            if position_qty >= 0:
                return (
                    f"正向平仓需要空头持仓，当前合约持仓为 "
                    f"{D.fmt_decimal(position_qty)}，未发单"
                )
            available = -position_qty
        else:
            if position_qty <= 0:
                return (
                    f"反向平仓需要多头持仓，当前合约持仓为 "
                    f"{D.fmt_decimal(position_qty)}，未发单"
                )
            available = position_qty
        if available < required_qty:
            return (
                f"合约可平数量不足：当前 {D.fmt_decimal(available)}，"
                f"剩余计划需 {D.fmt_decimal(required_qty)}，未发单"
            )
        return None

    def _transfer_back_usdt(self, task: dict, now_us: int) -> None:
        """forward close 平仓完成后 USDT 回流（Human 拍板：失败不阻塞，平仓已完成是主事实）。

        统计本轮 close 任务全部现货腿成交额 → ``universal_transfer('MAIN_PORTFOLIO_MARGIN',
        'USDT', 合计)`` 划回统一账户；失败写任务卡日志（中文），任务状态不变（done）。
        金额 0/空 → 跳过。dry-run（无 universal_transfer）→ 模拟成功。"""
        if task.get("task_type") != D.TASK_TYPE_CLOSE or task["direction"] != D.DIR_FORWARD:
            return
        xfer = getattr(self._executor, "universal_transfer", None)
        total = self._store.close_task_spot_quote_total(task["id"])
        if total is None or total <= 0:
            return
        if xfer is None:
            return  # dry-run：模拟回流成功
        try:
            xfer("MAIN_PORTFOLIO_MARGIN", "USDT", str(total))
            self._log_close_transfer(task["id"], now_us, "usdt_back_ok",
                                     task["coin"], "USDT", D.fmt_decimal(total))
        except Exception as exc:
            self._log_close_transfer(
                task["id"], now_us, "usdt_back_failed", task["coin"], "USDT",
                D.fmt_decimal(total),
                reason=f"USDT 回流失败，金额 {D.fmt_decimal(total)}，请人工处理"
                       f"（{type(exc).__name__}）",
            )

    def _finalize_close_task(self, task: dict, now_us: int) -> None:
        """平仓完成：任务 done → close_cycle('auto_close') → 写结算日志。

        三个独立短事务顺序执行（dispatch 允许「同一事务内或事务后紧接着」）；
        结算日志失败不阻塞 close_cycle 落库（周期已关是主事实）。
        """
        cycle = self._store.get_active_cycle(task["coin"], task["direction"])
        self._store.set_task_status(task["id"], D.STATUS_DONE, now_us)
        if cycle is None:
            return  # 无活跃周期（异常）→ 仅置 done，不写结算
        closed_at_us = now_us
        self._store.close_cycle(cycle["id"], closed_at_us, D.CLOSE_REASON_AUTO_CLOSE)
        open_basis = self._store.cycle_perp_basis(cycle["id"], D.TASK_TYPE_OPEN)
        close_basis = self._store.cycle_perp_basis(cycle["id"], D.TASK_TYPE_CLOSE)
        # 2026-08：历史页现货列——现货腿加权（买入=open、卖出=close）
        spot_open = self._store.cycle_spot_basis(cycle["id"], D.TASK_TYPE_OPEN)
        spot_close = self._store.cycle_spot_basis(cycle["id"], D.TASK_TYPE_CLOSE)
        # 2026-08：两腿真实成交数量加权均价价差百分比（卖价高于买价为正）
        open_slippage = self._store.cycle_slippage_pct(cycle["id"], D.TASK_TYPE_OPEN)
        close_slippage = self._store.cycle_slippage_pct(cycle["id"], D.TASK_TYPE_CLOSE)
        funding = None
        interest = None
        lsvc = self._ledger_flow_service
        if lsvc is not None and hasattr(lsvc, "sum_funding_by_symbol"):
            try:
                opened_ms = cycle["opened_at_us"] // 1000
                closed_ms = closed_at_us // 1000
                funding = lsvc.sum_funding_by_symbol(task["coin"], opened_ms, closed_ms)
                # 利息按现货 base asset 记账（bStock SNXXUSDT -> SNXXB、1000x ->
                # BONK），读任务固化的身份。
                base_asset = D.spot_base_of(task)
                if base_asset:
                    interest = lsvc.sum_interest_by_asset(base_asset, opened_ms, closed_ms)
            except Exception:
                funding = interest = None  # 统计失败不阻塞平仓完成
        try:
            self._store.insert_close_log(
                {
                    "cycle_id": cycle["id"],
                    "symbol": task["coin"],
                    "direction": task["direction"],
                    "opened_at_us": cycle["opened_at_us"],
                    "closed_at_us": closed_at_us,
                    "close_reason": D.CLOSE_REASON_AUTO_CLOSE,
                    "open_avg_price": open_basis.get("avg_price"),
                    "open_qty": open_basis.get("qty"),
                    "close_avg_price": close_basis.get("avg_price"),
                    "spot_open_avg": spot_open.get("avg_price"),
                    "spot_open_qty": spot_open.get("qty"),
                    "spot_close_avg": spot_close.get("avg_price"),
                    "spot_close_qty": spot_close.get("qty"),
                    "open_slippage": open_slippage,
                    "close_slippage": close_slippage,
                    "funding_fee": funding,
                    "borrow_interest": interest,
                    "settled_at_us": now_us,
                }
            )
        except Exception:
            pass  # 结算日志失败仅丢统计，不丢「周期已关」事实
        # 平仓现货卖出重设计（2026-08）：forward close 现货卖出后 USDT 划回统一
        # 账户——失败不阻塞（平仓已完成是主事实），错误写任务卡日志。
        self._transfer_back_usdt(task, now_us)

    def _reconcile_own_legs(self, task_id: str, task: dict, now_us: int) -> str | None:
        """Query ONLY this task's non-terminal legs by client order ID to
        terminal, then settle the pair once (amendment 21: no global scan). The
        executor is called with no store lock held. Returns a drain signal when a
        leg surfaces a 429 (rate_limited), a confirmed insufficient-funds fact,
        or — after the whole LEG_QUERY_MAX_RETRIES retry budget — an order whose
        state stayed inconclusive; None otherwise. Within that budget a 404 /
        -2013 is eventual-consistency noise (mirrors ``_confirm_um_figures``) and
        an inconclusive response is genuinely unknown, so the leg stays
        non-terminal and is re-queried; only at the budget cap does a 404 / -2013
        confirm absent, while a still-inconclusive leg escalates to manual
        recovery (never resent, never equated with absent — ADR-2 / R2-F2). The
        budget is per-leg, in-process, and needs no ``dispatched_at_us`` anchor,
        so legacy rows and crash gaps without one behave identically (F1)."""
        if not hasattr(self._executor, "query_leg"):
            self._recover_crash_gaps(task_id, now_us)
            return None
        legs = self._store.list_non_terminal_legs_for_task(task_id)
        finalized: set[int] = set()
        drain_signal: str | None = None
        for leg in legs:
            verdict = self._executor.query_leg(
                leg["leg"], _leg_query_symbol(leg, task), leg["client_order_id"],
                leg["endpoint"],
            )
            # Retry counter (fix-review1-retry-counter): each query counts once
            # per leg (in-process; a restart resets it, matching the legacy JS
            # getSpotOrderInfo(id, 10) loop). Below LEG_QUERY_MAX_RETRIES a 404 /
            # -2013 or an inconclusive response stays non-terminal and is
            # re-queried; at the cap the LAST response decides — absent terminal
            # for a 404 / -2013, manual recovery for still-inconclusive. No
            # dispatched_at_us anchor is needed, so legacy rows and crash gaps
            # behave identically (F1 root cause removed).
            retries = self._leg_query_retries.get(leg["id"], 0) + 1
            self._leg_query_retries[leg["id"]] = retries
            retries_exhausted = retries >= D.LEG_QUERY_MAX_RETRIES
            if verdict is None:
                # Inconclusive (transport error / 5xx / ambiguous 4xx): keep
                # querying below the cap; at the cap this is NOT an absent signal
                # (R2-F2) — escalate to manual recovery instead of polling on
                # indefinitely.
                if retries_exhausted and drain_signal is None:
                    drain_signal = D.SIGNAL_ORDER_STATE_UNKNOWN
                continue
            if getattr(verdict, "rate_limited", False):
                # R2-F2 (user authorization 28 §2.2): a query-phase 429/-1003/418.
                # Leave the leg EXACTLY as it is (non-terminal; the write POST is
                # never resent) and surface the throttle so the worker pauses THIS
                # task and exits for manual recovery instead of polling into the
                # ban. The leg is NOT resolved here and NOT added to finalized.
                # Review-1 r3 P1-1: a rate-limited query is a CONCLUSIVE verdict —
                # classify_query_response carries its raw — so persist it before
                # draining. This branch previously `continue`d before reaching the
                # _persist_leg_raw call below, dropping the evidence. The persist is
                # control-flow isolated (it can never change this branch's pause
                # semantics, non-terminal handling, or never-resend guarantee).
                self._persist_leg_raw(
                    task_id, leg["attempt_id"], leg["leg"], leg["client_order_id"],
                    "order_query", leg["endpoint"], getattr(verdict, "raw_response", None), now_us,
                    decisive=True,
                )
                if drain_signal is None:
                    drain_signal = D.SIGNAL_RATE_LIMITED
                continue
            terminal = self._query_verdict_terminal(verdict)
            # Retry budget: a 404 / -2013 below the cap is eventual-consistency
            # noise, NOT a confirmed-absent signal (mirrors _confirm_um_figures).
            # Keep it non-terminal and re-query; only at the cap is a 404 / -2013
            # a confirmed absent terminal (the prior behaviour, deferred up to
            # the budget).
            if (terminal and not retries_exhausted
                    and getattr(verdict, "error_category", None) == D.ERROR_CATEGORY_ABSENT):
                terminal = False
            try:
                self._store.resolve_leg_from_query(
                    leg["id"],
                    exchange_status=verdict.exchange_status or D.LEG_UNKNOWN,
                    order_id=verdict.order_id,
                    base_qty=verdict.executed_qty,
                    quote_amt=verdict.cumulative_quote,
                    avg_price=verdict.avg_price,
                    fee_amount=None,
                    fee_asset=None,
                    now_us=now_us,
                    terminal=terminal,
                    error_code=getattr(verdict, "error_code", None),
                    error_category=getattr(verdict, "error_category", None),
                )
            except Exception as exc:
                # S1 (task1d): a discarded resolve_leg_from_query left the leg in
                # its stale state with nothing visible (R1). R2: do NOT skip the
                # raw capture — append_raw_response runs in its own transaction,
                # isolated from the leg-row write that just failed, so the
                # exchange's own query words are exactly the evidence needed to
                # diagnose (the old ``continue`` dropped them). The leg is not
                # added to ``finalized`` (it was not recorded terminal), so the
                # next worker round re-queries and re-reconciles it; the write POST
                # is never resent (ADR-2).
                self._record_state_write_failure(
                    task_id, leg["attempt_id"], "resolve_leg_from_query", exc, now_us,
                )
                self._persist_leg_raw(
                    task_id, leg["attempt_id"], leg["leg"], leg["client_order_id"],
                    "order_query", leg["endpoint"], getattr(verdict, "raw_response", None), now_us,
                    decisive=self._query_verdict_decisive(verdict),
                )
                continue
            # T3 (10-design §3): capture the sanitized query response (the drain
            # GET that produced this verdict), after the leg-row business write.
            self._persist_leg_raw(
                task_id, leg["attempt_id"], leg["leg"], leg["client_order_id"],
                "order_query", leg["endpoint"], getattr(verdict, "raw_response", None), now_us,
                decisive=self._query_verdict_decisive(verdict),
            )
            if getattr(verdict, "error_category", None) == D.ERROR_CATEGORY_COLLATERAL_CAP:
                drain_signal = D.SIGNAL_COLLATERAL_CAP
            elif getattr(verdict, "error_category", None) == D.ERROR_CATEGORY_INSUFFICIENT_FUNDS:
                drain_signal = D.SIGNAL_INSUFFICIENT_BALANCE
            elif (not terminal and retries_exhausted
                    and verdict.dispatch_state == D.LEG_UNKNOWN_QUERYING
                    and drain_signal is None):
                # Inconclusive (5xx / timeout / malformed 2xx) at the retry cap:
                # NOT a confirmed-absent signal (R2-F2 — never equate "unknown"
                # with "absent"). Escalate to manual recovery instead of polling
                # on; the leg was left non-terminal above.
                drain_signal = D.SIGNAL_ORDER_STATE_UNKNOWN
            if terminal:
                finalized.add(leg["attempt_id"])
                # F1: a terminal leg no longer needs its retry counter — clear it
                # so the in-process dict cannot grow without bound.
                self._leg_query_retries.pop(leg["id"], None)
        # Review-1 r3 P1-1: "this pair does not count as a failure" is decided by
        # the ATTEMPT's own rate-limited fact (stamped at the 429 dispatch), NOT by
        # the task-level pause_reason — which a manual resume has already cleared.
        for attempt_id in finalized:
            try:
                attempt = self._store.get_attempt(attempt_id)
                if attempt is not None and self._rate_limited_for_settlement(
                    task_id, attempt_id, attempt, now_us
                ):
                    # Amendment 21: a 429 pair is closed WITHOUT consuming the
                    # failure counter; the in-flight guard still clears.
                    self._store.settle_attempt_no_counters(attempt_id, now_us)
                else:
                    updated = self._store.finalize_attempt(attempt_id, now_us)
                    self._notify_cache_refresh(updated)
            except Exception as exc:
                # F2 (review-2): stop discarding. A settlement exception left
                # pair_outcome NULL, silently stalling the task on prepare's
                # in-flight guard. Record an operator-visible event before the
                # worker continues (R1); keep catching so the worker survives (R2).
                self._record_settlement_failure(task_id, attempt_id, exc, now_us)
        # R2-F4 (user authorization 28 §2.3): recover any crash-gap attempt left
        # with BOTH legs terminal but pair_outcome still NULL — it has no
        # non-terminal leg for the drain above to act on, yet prepare_attempt's
        # in-flight guard blocks the next group and the real fill stays off the
        # counters. Idempotent (finalize/settle no-op once pair_outcome is set);
        # never resends, never recounts, never opens a new group.
        self._recover_crash_gaps(task_id, now_us)
        return drain_signal

    def _recover_crash_gaps(self, task_id: str, now_us: int) -> None:
        """Idempotently finalize this task's crash-gap attempts (R2-F4, user
        authorization 28 §2.3): attempts whose BOTH legs were closed to terminal
        but whose pair ``pair_outcome`` is still NULL (a crash between
        leg-terminalization and pair settlement). Such a gap has no non-terminal
        leg for the drain to act on, yet ``prepare_attempt``'s in-flight guard
        blocks the next group and the real fill stays off the counters.

        A task-local one-shot scan only — no global guardian, no timer, no busy
        loop (amendment 21 / dispatch 28 finding 4). Each attempt is closed the
        same way the normal drain closes it: rate-limited pairs settle without
        consuming the failure counter (amendment 21); all others finalize and
        book the truthful acceptance verdict. ``finalize``/``settle`` are
        idempotent, so a second pass is a no-op (never recounts, never resends,
        never opens a new group)."""
        gaps = self._store.list_unsettled_terminal_attempts_for_task(task_id)
        for attempt in gaps:
            try:
                if self._rate_limited_for_settlement(
                    task_id, attempt["id"], attempt, now_us
                ):
                    self._store.settle_attempt_no_counters(attempt["id"], now_us)
                else:
                    updated = self._store.finalize_attempt(attempt["id"], now_us)
                    self._notify_cache_refresh(updated)
            except Exception as exc:
                # F2 (review-2): the same discarding defect on the crash-gap
                # recovery loop — the mechanism meant to unstick this exact
                # state. Record an operator-visible event (R1); the worker
                # survives (R2) and the loop retries next round (R3).
                self._record_settlement_failure(task_id, attempt["id"], exc, now_us)

    def _record_settlement_failure(
        self, task_id: str, attempt_id: int, exc: BaseException, now_us: int,
    ) -> None:
        """F2 (review-2): record an operator-visible event for a settlement
        exception the caller caught, so a discarded failure no longer leaves
        ``pair_outcome = NULL`` — ``prepare_attempt``'s in-flight guard — with
        nothing visible to the operator.

        Uses the existing ``record_task_event`` channel the logs page already
        reads, carrying the task, the attempt, and the exception type and message
        — enough to diagnose, without credentials, headers, tokens, or a request
        body. R3: no new pause reason, task status, or product semantics — the
        crash-gap loop already retries every worker round, so a transient cause
        self-heals and a permanent one produces a repeated, visible event.

        R2: the recording itself is guarded so a failure to record cannot raise
        and take the worker down (with every other task). This inner guard wraps
        ONLY this audit write — not settlement business logic — and is not a
        second blanket ``except: pass`` around the settlement call."""
        try:
            self._store.record_task_event(
                task_id,
                "settlement_failed",
                {
                    "attempt_id": attempt_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                now_us,
            )
        except Exception:
            # R2: narrow inner guard. A failure to record this audit event must
            # not raise (it would kill the worker and every other task). It guards
            # ONLY this write; the settlement exception was already caught by the
            # caller and control flow is unaffected.
            pass

    def _record_state_write_failure(
        self, task_id: str, attempt_id: int, operation: str,
        exc: BaseException, now_us: int,
    ) -> None:
        """task1d (review-2 audit, S1-S5): record an operator-visible event for a
        discarded ``self._store.*`` state-write exception the caller caught. A
        discarded failure left the system believing something false about an order
        or a task, with nothing visible — the class-(A) defect family this stage
        closes. Mirrors :meth:`_record_settlement_failure` (F2) but is a DISTINCT
        persisted kind, ``state_write_failed``, so it is an accurate label for
        ``mark_leg_querying`` / ``resolve_leg_from_query`` too, and F2's reviewed
        ``settlement_failed`` rows and assertions stay untouched (no rename, no
        reuse, no data migration).

        ``operation`` names the store call (``resolve_leg_from_query``,
        ``mark_attempt_rate_limited``, ``resolve_attempt``, ``mark_leg_querying``);
        the payload adds it to the attempt / exception-type / message F2 carries —
        enough to diagnose, without credentials, headers, tokens, or a request body.

        R2: the recording itself is guarded so a failure to record cannot raise and
        take the worker down (with every other task). This inner guard wraps ONLY
        this audit write — not the caller's business logic — and is not a second
        blanket ``except: pass`` around the state write."""
        try:
            self._store.record_task_event(
                task_id,
                "state_write_failed",
                {
                    "attempt_id": attempt_id,
                    "operation": operation,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                now_us,
            )
        except Exception:
            # R2: narrow inner guard. A failure to record this audit event must not
            # raise (it would kill the worker and every other task). It guards ONLY
            # this write; the state-write exception was already caught by the caller
            # and control flow is unaffected.
            pass

    def _rate_limited_for_settlement(
        self, task_id: str, attempt_id: int, attempt: dict, now_us: int,
    ) -> bool:
        """task1d S2/R3 (review-2 audit): should this attempt settle WITHOUT the
        consecutive-failure counter (a 429 pair)? The durable ``rate_limited``
        column decides when the dispatch-time stamp succeeded. When that stamp
        FAILED — the attempt is still in ``_rate_limit_stamp_pending`` — R3
        requires a retry of the stamp before settlement (the crash-gap loop
        re-enters every round), so it is retried here; and whether that retry
        succeeds or fails, a 429 pair must NEVER be finalized as an ordinary
        failure, so a still-pending stamp also settles without the counter (the
        repeated failure is re-recorded via :meth:`_record_state_write_failure`,
        not swallowed). No new column, status, or operator copy — the in-process
        retry is the next-round mechanism R3 sanctions.

        ``attempt`` is the row the caller already holds. The pending case ignores
        it (the set is authoritative); the non-pending case reads its
        ``rate_limited`` (authoritative there), so a stale row from the crash-gap
        scan cannot mis-classify a stamp that failed at dispatch."""
        if attempt_id in self._rate_limit_stamp_pending:
            try:
                self._store.mark_attempt_rate_limited(attempt_id)
            except Exception as exc:
                self._record_state_write_failure(
                    task_id, attempt_id, "mark_attempt_rate_limited", exc, now_us,
                )
            else:
                self._rate_limit_stamp_pending.discard(attempt_id)
            return True
        return bool(attempt.get("rate_limited"))

    def _pause_task_local(
        self, task: dict, pause_reason: str, pause_signal: str | None,
        now_us: int, *, kind: str = "task_paused", pause_zh: str | None = None,
    ) -> None:
        """Persist a task-local pause (amendment 21): status=paused + the precise
        safe reason + an audit event, for THIS task only. No cross-task linkage,
        no consecutive-failure churn. A 429 uses the ``rate_limited`` kind; an
        insufficient-funds fact or a collateral-cap rejection uses ``task_paused``.
        ``pause_zh`` overrides the table lookup (used by collateral_cap, whose
        frozen message carries the blocked asset). Idempotent on status.

        fix-runtime-seam-scan (F2-P1 root fix): the store applies the pause as a
        CONDITIONAL write (current status running/paused only). When the
        condition misses — e.g. a concurrent post_delete landed while the worker
        was inside a no-lock executor query — NO status is rewritten, the audit
        event is STILL recorded (the closure stays visible on the entries
        timeline), and the caller's stale snapshot is not refreshed (the next
        worker round re-reads authoritative state)."""
        reason_zh = pause_zh or D.pause_reason_zh(pause_reason)
        updated, applied = self._store.pause_task(
            task["id"], pause_reason, reason_zh, now_us,
        )
        self._notify_cache_refresh(updated)
        payload = {
            "reason": pause_reason,
            "reason_zh": reason_zh,
            "coin": task["coin"],
            "direction": task["direction"],
        }
        if pause_signal is not None:
            payload["signal"] = pause_signal
        self._store.record_task_event(task["id"], kind, payload, now_us)
        if applied and updated is not None:
            task.update(updated)

    def _signal_order_state_unknown_recovery(
        self, task: dict, drain_signal: str, now_us: int,
    ) -> None:
        """F2+F3: apply the order_state_unknown manual-verification closure.

        running/paused tasks are paused (existing task-local pause semantics)
        with a ``task_paused`` event so the closure lands on the additive
        entries timeline as ``overall_result=task_paused`` /
        ``next_action=paused`` with the Chinese reason (F3). deleted/done/stopped
        tasks are sticky: their status is NOT rewritten to paused (F2); the same
        visible manual-verification event is recorded and the legs stay
        non-terminal for manual verification (never resent).

        2026-08-07: the sticky branch records ``order_state_unknown_final``, not
        ``task_paused``. A terminal task was never paused and cannot be resumed,
        so the pause vocabulary printed two false claims on the timeline
        (``任务暂停`` / ``已暂停``) plus a Chinese reason telling the operator to
        resume a task that has no resume path. Only the words changed — the
        sticky status, the non-terminal legs and the never-resend rule stand."""
        # -2015（API-key/IP/权限）是网关层拒绝，订单未发出——通用文案让人去交易所
        # 核对订单会白跑一趟（2026-08-07 实盘：出口 IP 变更）。能精准就精准。
        _code, _msg = self._store.latest_auth_error(task["id"])
        precise_zh = D.order_state_unknown_pause_reason_zh(_code, _msg)
        if task["status"] in (D.STATUS_RUNNING, D.STATUS_PAUSED):
            self._pause_task_local(
                task, D.PAUSE_REASON_ORDER_STATE_UNKNOWN, drain_signal, now_us,
                pause_zh=precise_zh,
            )
            return
        self._store.record_task_event(
            task["id"],
            "order_state_unknown_final",
            {
                "reason": D.PAUSE_REASON_ORDER_STATE_UNKNOWN,
                "reason_zh": D.order_state_unknown_final_reason_zh(
                    task["status"], precise_zh,
                ),
                "coin": task["coin"],
                "direction": task["direction"],
                "signal": drain_signal,
            },
            now_us,
        )

    def _pause_from_signal(
        self, task: dict, signal: str, now_us: int, *, kind: str = "task_paused",
    ) -> None:
        """Map a task-local-pause signal (a confirmed insufficient-funds fact or
        a collateral-cap rejection) to its precise pause_reason + Chinese message
        and persist the pause for THIS task only. collateral_cap carries the
        frozen asset-specific message; insufficient_funds uses the table lookup."""
        if signal == D.SIGNAL_COLLATERAL_CAP:
            self._pause_task_local(
                task, D.PAUSE_REASON_COLLATERAL_CAP_FULL, signal, now_us, kind=kind,
                pause_zh=D.collateral_cap_pause_reason_zh(D.base_asset(task["coin"])),
            )
        else:
            pause_reason = self._pause_reason_for_signal(signal)
            pause_zh = self._close_insufficient_pause_zh(task, pause_reason)
            self._pause_task_local(
                task, pause_reason, signal, now_us, kind=kind, pause_zh=pause_zh,
            )

    def _close_insufficient_pause_zh(
        self, task: dict, pause_reason: str,
    ) -> str | None:
        """§4.2（Human 决定 3）：forward close 下单阶段余额不足暂停时，若本任务
        本轮已完成划转，中文原因追加「可能是划转尚未到账」提示——让操作者能区分
        「真没钱」与「钱还在路上」。无划转记录 → ``None``（沿用表查文案）。"""
        if (
            pause_reason != D.PAUSE_REASON_INSUFFICIENT_BALANCE
            or task.get("task_type") != D.TASK_TYPE_CLOSE
            or task["direction"] != D.DIR_FORWARD
        ):
            return None
        done = self._close_transfer_done.get(task["id"])
        if done is None:
            return None
        amount, asset = done
        return (
            f"{D.pause_reason_zh(pause_reason)}；本轮已完成划转 {amount} {asset}，"
            f"若仍报余额不足，可能是划转尚未到账，请稍后手动恢复重试"
        )

    @staticmethod
    def _pause_reason_for_signal(signal: str) -> str:
        """Map an insufficient-funds drain/dispatch signal to its pause reason.
        (collateral_cap is handled by :meth:`_pause_from_signal`, which carries
        its own asset-specific reason/message.)"""
        return {
            D.SIGNAL_INSUFFICIENT_BALANCE: D.PAUSE_REASON_INSUFFICIENT_BALANCE,
            D.SIGNAL_INSUFFICIENT_MARGIN: D.PAUSE_REASON_INSUFFICIENT_MARGIN,
            D.SIGNAL_INSUFFICIENT_AVAILABLE_QTY: D.PAUSE_REASON_INSUFFICIENT_AVAILABLE_QTY,
        }.get(signal, D.PAUSE_REASON_INSUFFICIENT_BALANCE)

    # --------------------------------------------------------------- scheduler

    def tick(self) -> bool:
        """One scheduler tick (amendment 21 + final guardian fix / H-1).

        LIVE mode: this is a SAFE NO-OP. The one-time durable recovery handoff
        ran at :meth:`start`; live dispatch/reconcile runs only on the per-task
        worker that a manual Start/recover (or that single startup handoff)
        launched. A periodic tick must NEVER scan all tasks, enumerate legs, or
        launch a worker — so even an accidental call cannot become a long-lived
        all-task guardian scanner.

        DRY-RUN mode (record/disabled executor): the synchronous dispatch path is
        preserved (the executor is synchronous and performs no network POST),
        pacing on the scheduler interval; there is no rate-limit cooldown and no
        global reconcile scan. Explicit fill-once/fill-all remain operator
        manual triggers of the record transport and never POST.
        """
        if self._live_dispatch_capable():
            return False
        now = self._mono_us()
        interval = self._store.get_interval_us()
        if self._last_tick_mono is None:
            self._last_tick_mono = now
            due = True
        elif now >= self._last_tick_mono + interval:
            self._last_tick_mono = now
            due = True
        else:
            due = False
        if not due:
            return False
        if not self.is_start_gate_on():
            return False
        eligible = [
            task for task in self._store.list_eligible_tasks()
            if task.get("mode") != D.MODE_SMOOTH
        ]
        if not eligible:
            return False
        now_us = self._wall_us()
        # Dry-run (record/disabled executor): per-task concurrent dispatch + join
        # (R4-2). The executor is synchronous and never POSTs; there is no global
        # reconcile scan and no rate-limit cooldown on this path.
        self._dispatch_eligible_concurrently(eligible, now_us)
        return True

    def _dispatch_eligible_concurrently(self, eligible: list[dict], now_us: int) -> None:
        """Dry-run only: dispatch one pair for every eligible task concurrently
        (R4-2), joined before returning. The record/disabled executor is
        synchronous and performs no network POST; each task is containment-wrapped
        so one card's failure never stops a sibling. Live dispatch is NOT driven
        here — it runs on the task-local worker (amendment 21)."""
        threads = []
        for task in eligible:
            worker = threading.Thread(
                target=self._dispatch_one_for_task_contained,
                args=(task, now_us),
                name=f"hedge-tick-{task['id']}",
                daemon=True,
            )
            worker.start()
            threads.append(worker)
        for worker in threads:
            try:
                worker.join()
            except Exception:  # pragma: no cover - join does not raise normally
                pass

    def _dispatch_one_for_task_contained(self, task: dict, now_us: int) -> None:
        """Dry-run per-task dispatch wrapper (R4-2): contains exceptions so one
        card's failure never stops a sibling. The dispatch itself is
        :meth:`_dispatch_one_for_task` (durable-before-send; no resend)."""
        try:
            self._dispatch_one_for_task(task, now_us)
        except Exception:
            pass

    def _recover_workers(self) -> None:
        """One-shot startup recovery discovery (amendment 21 + final guardian
        fix / H-1): launch a bounded worker for every RUNNING task missing one,
        and a drain-only worker for any task (any status) whose persisted legs
        are still non-terminal. Returns after the handoffs. This is invoked ONCE
        by :meth:`start` (never by a periodic :meth:`tick`); it is NOT a resident
        scanner — a task whose worker exits is relaunched only by a manual
        Start/recover."""
        for task in self._store.list_tasks(D.STATUS_RUNNING):
            tid = task["id"]
            with self._workers_lock:
                has = self._workers.get(tid)
            if has is not None and has.is_alive():
                continue
            self.ensure_worker(tid)
        # Drain-only recovery for non-running tasks still holding in-flight legs
        # (e.g. paused/stopped/deleted/done mid-pair): a worker launched on a non-running
        # task drains its own legs to terminal, then exits (Q2 drain-before-exit).
        # Review-1 r3 P1-2: STATUS_DELETED is included so a deleted card whose
        # legs were left non-terminal is still drained to terminal on the ONE
        # startup handoff (no resident scanner).
        # Review-1 r4 P2-2: STATUS_DONE is included too — a target-reaching pair
        # may leave an accepted leg at NEW/PARTIALLY_FILLED (terminal=0 by design,
        # service._leg_terminal); without this the real filled spot leg is never
        # reconciled after a restart, so a fully hedged final pair would render
        # permanently as a naked short (aggregate_positions only sums FILLED legs).
        for status in (D.STATUS_PAUSED, D.STATUS_STOPPED, D.STATUS_DELETED, D.STATUS_DONE):
            for task in self._store.list_tasks(status):
                tid = task["id"]
                # R2-F4: also relaunch for a crash-gap attempt (both legs terminal
                # but pair_outcome NULL) so the ONE startup handoff finalizes it,
                # not a resident scanner (finding 4).
                has_pending = bool(self._store.list_non_terminal_legs_for_task(tid))
                has_gap = bool(self._store.list_unsettled_terminal_attempts_for_task(tid))
                if not (has_pending or has_gap):
                    continue
                with self._workers_lock:
                    has = self._workers.get(tid)
                if has is None or not has.is_alive():
                    self.ensure_worker(tid)

    def _live_dispatch_capable(self) -> bool:
        """A real POST is reachable only with a live executor + live mode."""
        return self._live_mode and hasattr(self._executor, "dispatch")

    def _resolve_fresh_preflight(self, task: dict) -> _FreshPreflight | None:
        """Compute a fresh factual preflight immediately before send (A-2).

        Returns ``None`` for an incomplete read -> fail-closed: no attempt, no
        POST, no count, no simulated call; the worker then EXITS without retry
        (the exit-vs-retry contract is EXIT — stage 2026-08-06 task 05 §5) and
        the service pauses the task with a Chinese reason naming the first
        failed read (``HedgePreflightProvider.last_failed_read``). A ``fatal``
        result stops the task (amendment rows 1–2); an ``ok`` result carries
        the exact ``q_common``/snapshot this pair will post. Non-fatal
        rejections that are not incomplete (e.g. a transient balance gap on a
        non-fatal path) are also treated as fail-closed exit.
        """
        # close 任务用反转方向表达实际现货动作（forward close 卖、reverse close 买）；
        # forward 的 base 余额改由 dispatch 在 fresh q_common 产生后按 remaining 校验。
        preflight_dir = task["direction"]
        if task.get("task_type") == D.TASK_TYPE_CLOSE:
            preflight_dir = (
                D.DIR_REVERSE if task["direction"] == D.DIR_FORWARD
                else D.DIR_FORWARD
            )
        task_type = task.get("task_type") or D.TASK_TYPE_OPEN
        if task_type == D.TASK_TYPE_CLOSE:
            snapshot = self._preflight.get_snapshot(
                task["coin"], preflight_dir,
                task_type=task_type,
                position_side_mode=task.get("position_side_mode") or D.POS_MODE_BOTH,
            )
        else:
            # Open keeps the existing provider call and all of its real-time
            # fallbacks byte-for-byte.
            snapshot = self._preflight.get_snapshot(
                task["coin"], preflight_dir, task_type=task_type,
            )
        if snapshot is None:
            return None
        preflight = D.compute_preflight(
            snapshot,
            task["coin"],
            preflight_dir,  # 余额校验必须与路由决策同方向（close 用反转方向校验实际资金约束）
            D.Decimal(task["single_amount"]),
            task["target_n"],
            check_balance=not (
                task_type == D.TASK_TYPE_CLOSE
                and task["direction"] == D.DIR_FORWARD
            ),
        )
        if preflight.rejection == D.REJECT_PREFLIGHT_INCOMPLETE:
            return None
        if preflight.rejection in D.PREFLIGHT_FATAL_REASONS:
            stop_reason = D.REJECT_TO_STOP_REASON.get(
                preflight.rejection, D.STOP_REASON_EXCHANGE_FATAL
            )
            return _FreshPreflight(
                q_common=preflight.q_common,
                position_side_mode=preflight.position_side_mode,
                snapshot_record=preflight.snapshot_record,
                rejection=preflight.rejection,
                ok=False,
                fatal=True,
                stop_reason=stop_reason,
            )
        if preflight.rejection is not None or preflight.balance_ok is False:
            # Non-fatal reject or a balance gap that is not a fatal rule failure:
            # fail-closed exit (worker exits, task pauses — stage 2026-08-06
            # task 05 §5; no attempt, no POST).
            return None
        return _FreshPreflight(
            q_common=preflight.q_common,
            position_side_mode=preflight.position_side_mode,
            snapshot_record=preflight.snapshot_record,
            rejection=None,
            ok=True,
            fatal=False,
            stop_reason=None,
        )

    def _stop_task_fatal_preflight(
        self, task: dict, fresh: _FreshPreflight, now_us: int
    ) -> dict | None:
        """A fatal preflight fact stops the task (amendment rows 1–2): no attempt,
        no POST. Records a machine-readable ``stop_reason`` + a task-stopped
        audit event with the safe Chinese cause."""
        stop_reason = fresh.stop_reason or D.STOP_REASON_EXCHANGE_FATAL
        updated = self._store.stop_task_fatal(task["id"], stop_reason, now_us)
        self._notify_cache_refresh(updated)
        self._store.record_task_event(
            task["id"],
            "task_stopped",
            {
                "stop_reason": stop_reason,
                "reason_zh": D.stop_reason_zh(stop_reason),
                "coin": task["coin"],
                "direction": task["direction"],
                "rejection": fresh.rejection,
            },
            now_us,
        )
        return updated

    def _record_preflight_incomplete(
        self, task: dict, now_us: int, failed_read: str | None = None,
    ) -> None:
        """Fail-closed (I-7): a missing preflight fact records the failure event
        (naming the FIRST failed read — stage 2026-08-06 task 05 §5.3's forensic
        fix) but performs no attempt, no POST, and no business-state change.
        The worker then exits WITHOUT retrying (the exit-vs-retry contract is
        EXIT); the pause + Chinese reason are applied by
        :meth:`_pause_preflight_incomplete`."""
        payload = {
            "reason": "preflight_incomplete",
            "coin": task["coin"],
            "direction": task["direction"],
        }
        if failed_read is not None:
            payload["failed_read"] = failed_read
        self._store.record_task_event(
            task["id"],
            "preflight_incomplete",
            payload,
            now_us,
        )

    def _pause_preflight_incomplete(self, task: dict, now_us: int) -> bool:
        """Stage 2026-08-06 task 05 §5 (Human decision 4): a preflight failure
        pauses THIS task with a Chinese reason naming the first failed read,
        then the worker exits this round (``return False``, same as the
        SIGNAL_TASK_LOCAL_PAUSE branch). NO retry is introduced — the
        exit-without-retry contract is kept, only the silent stall is fixed:
        the pause is visible on the card and recoverable by a manual Start."""
        failed_read = getattr(self._preflight, "last_failed_read", None)
        if failed_read:
            reason_zh = (
                f"预检数据不完整（{failed_read}），任务已暂停（fail-closed，未发单）；"
                f"请检查网络后手动恢复"
            )
        else:
            reason_zh = None  # 表查通用文案
        self._pause_task_local(
            task, D.PAUSE_REASON_PREFLIGHT_INCOMPLETE,
            D.SIGNAL_PREFLIGHT_INCOMPLETE, now_us,
            kind="preflight_incomplete", pause_zh=reason_zh,
        )
        return False

    def _set_leverage_before_open(self, task: dict, now_us: int) -> str | None:
        """开单前设置该合约 symbol 杠杆（THE -2027 方案 B，Human 拍板）。

        仅 live executor 有 ``set_leverage``（dry-run/disabled 无 → 跳过，模拟成功）。
        成功返回 ``None``；失败/异常返回中文错误（含交易所详情，截断 200 字符），
        调用方 fail-closed：任务暂停（``PAUSE_REASON_LEVERAGE_SET_FAILED`` + 中文原因 +
        ``leverage_set_failed`` 事件）、不创建 attempt、不发单。每任务只调一次（由调用方
        在 ``scheduled_attempt_count == 0`` 时执行）。
        """
        setter = getattr(self._executor, "set_leverage", None)
        if setter is None:
            return None  # dry-run / disabled：不设杠杆，模拟成功
        try:
            setter(task["coin"], D.OPEN_LEVERAGE)
        except Exception as exc:  # noqa: BLE001 —— 任何失败都 fail-closed，如实记录
            detail = str(exc)[:200]
            return (
                f"设置合约杠杆失败（fail-closed，未发单）：{detail}"
                if detail
                else "设置合约杠杆失败（fail-closed，未发单），无错误详情"
            )
        return None

    def _dispatch_one_for_task(
        self,
        task: dict,
        now_us: int,
        *,
        expected_gate_seq: int | None = None,
        smooth_pass_reason: str | None = None,
        smooth_audit: dict | None = None,
    ) -> tuple[dict, str | None]:
        """Durable-before-send: a fresh preflight (live path only) -> persist the
        immutable attempt + both client IDs + sanitized request shapes in ONE
        transaction BEFORE any executor call (ADR-2). The executor is then
        invoked with no store transaction held; the outcome is resolved in a
        second short transaction.

        Returns ``(task, signal)`` (amendment 21). ``signal`` tells the task-local
        worker what happened on this pair: ``SIGNAL_RATE_LIMITED`` / a
        ``SIGNAL_INSUFFICIENT_*`` -> pause THIS task only; ``SIGNAL_PREFLIGHT_*``
        are fail-closed / fatal (the worker exits WITHOUT retry — stage
        2026-08-06 task 05 §5 aligns the docstring with the EXIT implementation);
        ``None`` is a normal dispatch.

        Fresh-preflight-first + fail-closed (A-2/A-3) applies to live immediate
        and close tasks. Live smooth and dry-run dispatch reuse the task's frozen
        q_common/snapshot; dry-run never POSTs.
        """
        self._smooth_audit_mark(smooth_audit, "service_dispatch", self._mono_us)
        task_type = task.get("task_type") or D.TASK_TYPE_OPEN
        live = self._live_dispatch_capable() and self.is_start_gate_on()
        # smooth-close C12③：发单准入同时要求平仓闸门开启——拦住"等待循环刚
        # 通过闸门检查、放行结论刚产生、此时关闸"的竞态窗口。不发单、不消费
        # gate（worker 下一轮按 C12⑤ 清门退出），任务状态不变。
        if (
            live
            and task_type == D.TASK_TYPE_CLOSE
            and not self.is_close_gate_on()
        ):
            return self._store.get_task(task["id"]) or task, None
        if live and task_type == D.TASK_TYPE_CLOSE:
            # Historical rows may have NULL symbol_match_type. The stored value
            # and today's pure mapping are both authoritative blockers until
            # 1000x leg conversion is implemented.
            current_spot_symbol, _, current_match = resolve_spot_identity(task["coin"])
            if (
                task.get("symbol_match_type") == SPOT_MATCH_MULTIPLIER
                or current_match == SPOT_MATCH_MULTIPLIER
            ):
                self._pause_task_local(
                    task,
                    D.PAUSE_REASON_MULTIPLIER_CLOSE_UNSUPPORTED,
                    D.SIGNAL_CLOSE_GUARD_FAILED,
                    now_us,
                    pause_zh=(
                        f"{task['coin']} 是 1000 倍乘数合约（现货腿 "
                        f"{current_spot_symbol}），两腿数量换算尚未实现，"
                        "已暂停且未发单，请人工到交易所处理"
                    ),
                )
                return (
                    self._store.get_task(task["id"]) or task,
                    D.SIGNAL_CLOSE_GUARD_FAILED,
                )
        if live and task.get("mode") != D.MODE_SMOOTH:
            if task_type == D.TASK_TYPE_CLOSE:
                # 三道门抽函数（smooth-close C4/C5 §4.1）：立即平仓仍在原调用
                # 点、每一轮执行（本分支）；平滑平仓只在 post_start 备料时执行
                # 一次。失败处置（fatal 停止 / preflight_incomplete / 两条 close
                # 门暂停）在函数内落库，与抽函数前逐行等价。
                q_common, position_side_mode, snapshot_record, prep_signal = (
                    self._run_close_preparation(task, now_us)
                )
                if prep_signal is not None or q_common is None:
                    return self._store.get_task(task["id"]) or task, prep_signal
            else:
                fresh = self._resolve_fresh_preflight(task)
                if fresh is None or not fresh.ok:
                    # incomplete read -> fail-closed exit (worker exits, task pauses
                    # with a Chinese reason — stage 2026-08-06 task 05 §5); fatal ->
                    # stop (rows 1–2).
                    if fresh is not None and fresh.fatal:
                        self._stop_task_fatal_preflight(task, fresh, now_us)
                        return self._store.get_task(task["id"]) or task, D.SIGNAL_PREFLIGHT_FATAL
                    self._record_preflight_incomplete(
                        task, now_us, getattr(self._preflight, "last_failed_read", None),
                    )
                    return self._store.get_task(task["id"]) or task, D.SIGNAL_PREFLIGHT_INCOMPLETE
                q_common = fresh.q_common
                position_side_mode = fresh.position_side_mode
                snapshot_record = fresh.snapshot_record
        else:
            q_common = D.Decimal(task["q_common"]) if task["q_common"] else None
            position_side_mode = task["position_side_mode"]
            snapshot_record = task["preflight_snapshot"] or {}

        attempt_uuid = uuid.uuid4().hex
        spot_cid, perp_cid = _client_order_ids(attempt_uuid)
        # 备款/路由一致性核验（Human 2026-08 REWORK 问题1）：regular_spot 下单需已备款
        # （create_task 时划转，固化 frozen route=regular_spot）。若 fresh 要走 regular_spot
        # 但建卡时不是 regular_spot（建卡 PAPI 未备款、或建卡时 snapshot None 未固化路由
        # 又恢复成 regular_spot）→ 暂停不发单，避免裸空。papi 下单不需备款，不拦。
        if live and task_type == D.TASK_TYPE_OPEN:
            frozen_route = (task.get("preflight_snapshot") or {}).get("spot_route")
            fresh_route = (snapshot_record or {}).get("spot_route")
            if (fresh_route == D.SPOT_ROUTE_REGULAR_SPOT
                    and frozen_route != D.SPOT_ROUTE_REGULAR_SPOT):
                self._pause_task_local(
                    task, D.PAUSE_REASON_SPOT_ROUTE_CHANGED,
                    D.SIGNAL_SPOT_ROUTE_CHANGED, now_us,
                    kind="spot_route_changed",
                    pause_zh=f"下单需走普通现货（regular_spot）但建卡时未备款"
                            f"（建卡路由 {frozen_route}），已暂停避免裸空，请核对后恢复",
                )
                return (
                    self._store.get_task(task["id"]) or task,
                    D.SIGNAL_SPOT_ROUTE_CHANGED,
                )
        # 开单前自动设置合约杠杆（THE -2027 方案 B，Human 拍板）：live 开单任务
        # 首个 attempt 发单前设置一次（每任务只设一次）。设置失败 fail-closed——
        # 任务暂停（中文原因 + 错误详情落库）、不创建 attempt、不发单（避免在错误
        # 杠杆下开仓，仓位风险不可控）。dry-run（executor 无 set_leverage）跳过。
        if (
            live
            and task_type == D.TASK_TYPE_OPEN
            and task.get("mode") != D.MODE_SMOOTH
            and task.get("scheduled_attempt_count", 0) == 0
        ):
            lev_err = self._set_leverage_before_open(task, now_us)
            if lev_err is not None:
                self._pause_task_local(
                    task, D.PAUSE_REASON_LEVERAGE_SET_FAILED,
                    D.SIGNAL_LEVERAGE_SET_FAILED, now_us,
                    kind="leverage_set_failed", pause_zh=lev_err,
                )
                return (
                    self._store.get_task(task["id"]) or task,
                    D.SIGNAL_LEVERAGE_SET_FAILED,
                )
        actions = D.direction_to_leg_actions(
            task["direction"], position_side_mode or D.POS_MODE_BOTH,
            task_type=task_type,
        )
        send_qty = D.resolve_send_qty(q_common, task["single_amount"])
        spot_route = (snapshot_record or {}).get(
            "spot_route", D.SPOT_ROUTE_PAPI_MARGIN
        )
        spot_order_symbol = D.spot_symbol_of(task)
        # D3 一致性告警：固化身份与当前查表不一致 → 记录但不阻断（固化值是该任务
        # 的历史真值，平仓必须用它；静默切换会让两条腿对不上）。
        # 漂移是任务级事实而非每次 attempt 的事实：已记过就不再记，避免
        # target_n=10 的任务刷出 10 条重复告警（评审核查点 3）。
        drift = D.identity_drift(task)
        if drift is not None and task["id"] in self._identity_drift_seen:
            drift = None
        if drift is not None:
            self._identity_drift_seen.add(task["id"])
            print(
                f"[HEDGE-IDENTITY-DRIFT] task={task['id'][:8]} coin={drift['coin']} "
                f"frozen={drift['frozen']} current={drift['current']} "
                f"—— 仍按固化身份发单，请核对 SPOT_SYMBOL_MAP 是否变动",
                file=sys.stderr, flush=True,
            )
            self._store.record_task_event(
                task["id"], "identity_drift",
                {"reason": "identity_drift", "reason_zh":
                 f"现货腿身份与当前映射表不一致（固化 {drift['frozen']}，"
                 f"当前 {drift['current']}）；仍按固化身份发单",
                 **drift},
                now_us,
            )
        if spot_route == D.SPOT_ROUTE_REGULAR_SPOT:
            # /api/v3/order shape: no sideEffectType (a standard spot order is not
            # a margin borrow/repay). Defined once in domain.build_regular_spot_order_params.
            spot_shape = D.build_regular_spot_order_params(
                spot_order_symbol, actions, send_qty, spot_cid
            )
        else:
            spot_shape = build_spot_order_params(
                spot_order_symbol, actions, send_qty, spot_cid
            )
        perp_shape = build_perp_order_params(
            task["coin"], actions, send_qty, perp_cid, task_type=task_type,
        )
        self._smooth_audit_mark(smooth_audit, "request_assembled", self._mono_us)
        q_common_str = D.fmt_decimal(q_common) if q_common is not None else task["single_amount"]
        self._smooth_audit_mark(smooth_audit, "prepare_started", self._mono_us)
        attempt = self._store.prepare_attempt(
            task["id"],
            attempt_uuid,
            task["direction"],
            q_common_str,
            position_side_mode,
            snapshot_record,
            spot_cid,
            spot_shape,
            D.spot_route_endpoint(spot_route),
            perp_cid,
            perp_shape,
            now_us,
            expected_gate_seq=expected_gate_seq,
            smooth_pass_reason=smooth_pass_reason,
        )
        if attempt is None:
            # Task is no longer eligible (paused/done/deleted/out-of-budget) — no POST.
            return self._store.get_task(task["id"]) or task, None
        self._smooth_audit_mark(smooth_audit, "prepare_committed", self._mono_us)
        ctx = AttemptContext(
            attempt_id=attempt_uuid,
            task_id=task["id"],
            coin=task["coin"],
            direction=task["direction"],
            single_amount=D.Decimal(task["single_amount"]),
            q_common=q_common,
            position_side_mode=position_side_mode,
            preflight_snapshot=snapshot_record,
            filter_versions=snapshot_record,
            target_n=task["target_n"],
            ts_us=now_us,
            task_type=task_type,
            spot_symbol=spot_order_symbol,
            smooth_audit=smooth_audit,
            mono_us=self._mono_us if smooth_audit is not None else None,
        )
        signal: str | None = None
        if live:
            signal = self._dispatch_live(attempt, ctx, now_us)
        else:
            self._dispatch_simulated(attempt, ctx, now_us)
        return self._store.get_task(task["id"]) or task, signal

    def _dispatch_simulated(self, attempt: dict, ctx: AttemptContext, now_us: int) -> None:
        """Disabled path (no network POST): the default executor resolves the
        attempt to ``ATTEMPT_DISABLED`` — zero I/O, zero simulated fills — so
        every disabled attempt/leg row carries ``filled_qty=0``
        (``cumulative_base_qty=0`` never enters the position aggregate,
        ``store.py`` skips it). The dry-run record-transport fill simulator was
        removed from production (2026-08-06 Human decision); only the test-only
        record-transport fake (``backend/tests/fakes.py``) still simulates
        fills, and it is never reachable at runtime."""
        try:
            outcome = self._executor.execute(ctx)
        except Exception as exc:
            outcome = self._failed_outcome(ctx, f"executor_exception:{type(exc).__name__}")
        try:
            updated = self._store.resolve_attempt(
                attempt["id"], outcome, now_us,
                # 功能三（2026-08 修复）：close 任务成交后不自动 done——完成判定由
                # worker 的合约无仓核实接管（与 _settle_attempt 主路径一致）。
                suppress_done=(
                    getattr(ctx, "task_type", D.TASK_TYPE_OPEN) == D.TASK_TYPE_CLOSE
                ),
            )
            self._notify_cache_refresh(updated)
        except Exception:
            # containment: a resolve failure must not kill dispatch.
            pass

    def _dispatch_live(self, attempt: dict, ctx: AttemptContext, now_us: int) -> str | None:
        """Live path: the executor submits both legs concurrently and returns a
        per-leg dispatch verdict (duck-typed; this package never imports the
        services-layer executor module). Returns an amendment-21 signal:

        * ``SIGNAL_RATE_LIMITED`` — a 429 / -1003 / 418 on a leg. The pair is NOT
          resolved; any UNKNOWN leg is marked so the worker drains it before it
          exits (the write POST is never resent — ADR-2). The worker pauses THIS
          task only and never consumes the failure counter.
        * a ``SIGNAL_INSUFFICIENT_*`` — a confirmed insufficient balance/margin/
          available-quantity fact on a leg. A terminal insufficient pair is
          settled once (clearing the in-flight guard); the worker pauses THIS
          task only.
        * ``None`` — a normal dispatch: legs with a definite verdict resolve the
          pair now; any UNKNOWN leg is marked for the worker's own drain.
        """
        audit = getattr(ctx, "smooth_audit", None)
        self._smooth_audit_mark(audit, "executor_entered", self._mono_us)
        dispatch = self._executor.dispatch(ctx)
        self._smooth_audit_mark(audit, "executor_returned", self._mono_us)
        if audit is not None:
            try:
                audit["durations_us"] = self._smooth_audit_durations(audit)
                self._store.append_log(
                    ctx.task_id, now_us, "smooth_dispatch_audit", audit,
                    attempt_id=ctx.attempt_id,
                )
            except Exception:
                pass
        spot = dispatch.spot
        perp = dispatch.perp
        retry_after = getattr(dispatch, "retry_after_seconds", None)
        rate_limited = bool(getattr(dispatch, "rate_limited", False))
        spot_querying = spot.dispatch_state == D.LEG_UNKNOWN_QUERYING
        perp_querying = perp.dispatch_state == D.LEG_UNKNOWN_QUERYING
        has_querying = spot_querying or perp_querying
        # T3 (10-design §3): capture both legs' sanitized POST responses. This is
        # an isolated short transaction that can never affect the business write
        # below; it lands on every POST — accepted, rejected (the 51169 evidence
        # path), or rate-limited — so the next unexplainable response is readable
        # from the DB alone.
        spot_cid, perp_cid = _client_order_ids(attempt["attempt_uuid"])
        # The leg-row endpoints (design §4 authority): the spot endpoint follows
        # the resolved route (regular_spot /api/v3/order vs PAPI margin); the perp
        # leg is always UM. Raw responses are recorded against these paths so a
        # regular-spot POST/GET is never misattributed to the PAPI margin path.
        spot_endpoint = D.spot_route_endpoint(
            (ctx.preflight_snapshot or {}).get("spot_route", D.SPOT_ROUTE_PAPI_MARGIN)
        )
        perp_endpoint = D.PERP_ORDER_PATH
        self._persist_leg_raw(
            ctx.task_id, attempt["id"], spot.leg, spot_cid, "order_post",
            spot_endpoint, spot.raw_response, now_us,
            decisive=True,
        )
        self._persist_leg_raw(
            ctx.task_id, attempt["id"], perp.leg, perp_cid, "order_post",
            perp_endpoint, perp.raw_response, now_us,
            decisive=True,
        )
        # T1+T3 (§1(b)/§3(b)): the UM leg's inline-confirm GET (the authoritative
        # figures query) is captured with its own source so POST vs confirm stay
        # distinguishable in the raw table.
        self._persist_leg_raw(
            ctx.task_id, attempt["id"], perp.leg, perp_cid, "order_confirm",
            perp_endpoint, getattr(perp, "confirm_raw_response", None), now_us,
            decisive=True,
        )
        # T3 (§3): the UNKNOWN-POST immediate best-effort query GET (the order-detail
        # lookup that resolved an inconclusive POST, carried on query_raw_response) is
        # captured with its own source so the response that decided a leg's fate is
        # never dropped. Distinct from order_post (the POST body) and order_confirm
        # (the UM accepted-confirm); mirrors the drain path's order_query capture. A
        # no-op when the leg carried no such GET (POST was conclusive, or the GET was
        # itself inconclusive and the leg stayed UNKNOWN for the drain path).
        self._persist_leg_raw(
            ctx.task_id, attempt["id"], spot.leg, spot_cid, "order_query",
            spot_endpoint, getattr(spot, "query_raw_response", None), now_us,
            decisive=self._query_verdict_decisive(spot),
        )
        self._persist_leg_raw(
            ctx.task_id, attempt["id"], perp.leg, perp_cid, "order_query",
            perp_endpoint, getattr(perp, "query_raw_response", None), now_us,
            decisive=self._query_verdict_decisive(perp),
        )
        if rate_limited:
            # Amendment 21: pause THIS task only. Do NOT resolve the pair — its
            # UNKNOWN legs are marked so the worker drains them, then settles the
            # pair without consuming the failure counter, before exiting.
            if has_querying:
                self._mark_legs_querying(attempt, spot, perp, now_us)
            self._store.record_task_event(
                ctx.task_id,
                "rate_limited",
                {
                    "reason": "rate_limited",
                    "retry_after_seconds": retry_after,
                    "coin": ctx.coin,
                    "direction": ctx.direction,
                },
                now_us,
            )
            # Review-1 r3 P1-1: stamp the per-attempt rate-limited fact so the
            # reconcile path settles this pair without consuming the failure
            # counter even after a manual resume has cleared pause_reason.
            try:
                self._store.mark_attempt_rate_limited(attempt["id"])
            except Exception as exc:
                # S2 (task1d): the rate-limited fact was lost, so a later reconcile
                # would settle this pair as an ordinary failure and consume the
                # counter the design exempts. Record the failure (R1) and remember
                # the stamp is pending so settlement retries it before deciding and
                # never finalizes a 429 pair as ordinary (R3 — see
                # _rate_limited_for_settlement). Keep catching (R2).
                self._record_state_write_failure(
                    ctx.task_id, attempt["id"], "mark_attempt_rate_limited", exc, now_us,
                )
                self._rate_limit_stamp_pending.add(attempt["id"])
            return D.SIGNAL_RATE_LIMITED
        pause_signal = self._pause_signal_from_legs(spot, perp)
        if pause_signal is not None and not has_querying:
            # Both legs terminal with a confirmed pause-class fact (insufficient
            # funds or a collateral-cap rejection): settle the pair once (clearing
            # the in-flight guard); the worker pauses THIS task only.
            # fix-runtime-seam-scan: ``suppress_done`` — a terminal pause-class
            # settlement must NOT auto-promote the task to done past the pause
            # the worker applies right after (the conditional pause write would
            # then miss and the amendment-21 "insufficient -> pause THIS task,
            # no threshold wait" contract would silently degrade to done).
            outcome = self._dispatch_to_outcome(
                attempt["attempt_uuid"], spot, perp, dispatch.record_payload, now_us
            )
            try:
                updated = self._store.resolve_attempt(
                    attempt["id"], outcome, now_us, suppress_done=True,
                )
                self._notify_cache_refresh(updated)
            except Exception as exc:
                # S3 (task1d): orders already sent and both legs terminal; a
                # discarded resolve_attempt leaves pair_outcome NULL and the
                # in-flight guard stalls the task. Record the failure (R1); keep
                # catching (R2). The crash-gap loop re-enters every round and
                # retries the settlement (R3).
                self._record_state_write_failure(
                    ctx.task_id, attempt["id"], "resolve_attempt", exc, now_us,
                )
            return pause_signal
        if pause_signal is not None:
            # Mixed: one leg pause-class terminal, the other still UNKNOWN — mark
            # the UNKNOWN leg(s); the worker pauses and drains before exit.
            self._mark_legs_querying(attempt, spot, perp, now_us)
            return pause_signal
        if has_querying:
            self._mark_legs_querying(attempt, spot, perp, now_us)
            return None
        outcome = self._dispatch_to_outcome(
            attempt["attempt_uuid"], spot, perp, dispatch.record_payload, now_us
        )
        leg_terminal = {
            spot.leg: self._leg_terminal(spot),
            perp.leg: self._leg_terminal(perp),
        }
        try:
            updated = self._store.resolve_attempt(
                attempt["id"], outcome, now_us, leg_terminal=leg_terminal,
                # 功能三（2026-08 修复）：close 任务 attempt 成交后不自动 done——
                # 完成判定（done/close_cycle/close_log）由 worker 的合约无仓核实接管
                # （Human：close 从 running 变其他状态必须先核实）。开单任务不变。
                suppress_done=(
                    getattr(ctx, "task_type", D.TASK_TYPE_OPEN) == D.TASK_TYPE_CLOSE
                ),
            )
            self._notify_cache_refresh(updated)
        except Exception as exc:
            # S4 (task1d): the main path — a real order placed and its conclusion
            # never persisted. Record the failure (R1); keep catching (R2). Any
            # non-terminal leg is drained and the crash-gap loop retries next round
            # (R3); the write POST is never resent (ADR-2).
            self._record_state_write_failure(
                ctx.task_id, attempt["id"], "resolve_attempt", exc, now_us,
            )
        return None

    def _mark_legs_querying(
        self, attempt: dict, spot, perp, now_us: int,
    ) -> None:
        """Mark a pair's UNKNOWN / accepted-not-yet-final legs for the worker's
        own drain (the write POST is never resent — ADR-2). A leg already
        confirmed terminal (REJECTED) is left untouched."""
        for leg in (spot, perp):
            if leg.dispatch_state == D.LEG_TERMINAL_RECORDED:
                continue
            state = (
                D.LEG_UNKNOWN_QUERYING
                if leg.dispatch_state == D.LEG_UNKNOWN_QUERYING
                else D.LEG_ACCEPTED_OR_QUERYING
            )
            try:
                self._store.mark_leg_querying(
                    attempt["id"], leg.leg, state, leg.order_id, now_us
                )
            except Exception as exc:
                # S5 (task1d): a leg needing drain was never marked, so an in-flight
                # order would never be reconciled by client ID. Record the failure
                # (R1); keep catching (R2). The leg keeps its pre-failure state, so
                # the worker treats it as it already was — ADR-2 still holds (the
                # write POST is never resent); a fatal fact re-surfaces on the next
                # dispatch's fresh POST.
                self._record_state_write_failure(
                    attempt["task_id"], attempt["id"], "mark_leg_querying", exc, now_us,
                )

    def _persist_leg_raw(
        self, task_id: str, attempt_id: int, leg_name: str,
        client_order_id: str | None, source: str, endpoint: str,
        raw: dict | None, now_us: int,
        *, decisive: bool = False,
    ) -> None:
        """Persist one leg's sanitized raw exchange response (T3 / 10-design §3).

        ``endpoint`` is the leg row's persisted endpoint (design §4: the SOLE
        authority for which path a raw response rode on — never re-derived from
        leg name or task-level route, so a regular-spot ``/api/v3/order`` response
        is recorded against that path even though the leg name is still ``spot``).

        ``decisive`` marks this response as one of the four conclusive verdicts §T3
        requires persisted; the caller decides it from the verdict it already holds
        and it governs the store's one-row-per-leg-per-source replace rule (a
        decisive response replaces a prior non-decisive placeholder; a decisive row
        is never replaced).

        Control-flow isolation is absolute: :meth:`store.append_raw_response` runs
        in its OWN short transaction, so a persistence failure can NEVER roll back
        or fail the business write that already committed. The failure is swallowed
        and a ``raw_persist_failed`` task event is best-effort recorded (that record
        failing too is abandoned — control flow outranks audit completeness).
        No-op when the leg carried no raw response (a record/dry-run transport, or
        a query that returned no verdict)."""
        if raw is None:
            return
        try:
            self._store.append_raw_response(
                attempt_id, leg_name, client_order_id, source, endpoint, raw, now_us,
                decisive=decisive,
            )
        except Exception:
            try:
                self._store.record_task_event(
                    task_id, "raw_persist_failed",
                    {"attempt_id": attempt_id, "leg": leg_name, "source": source},
                    now_us,
                )
            except Exception:
                pass

    @staticmethod
    def _pause_signal_from_legs(spot, perp) -> str | None:
        """Map a confirmed pause-class leg classification to its amendment-21
        task-local pause signal. ``insufficient_funds`` -> SIGNAL_INSUFFICIENT_*
        (``-2019`` margin, else balance); ``collateral_cap`` (51169) ->
        SIGNAL_COLLATERAL_CAP. Returns ``None`` when neither leg carries a
        pause-class category."""
        for leg in (spot, perp):
            cat = getattr(leg, "error_category", None)
            if cat == D.ERROR_CATEGORY_COLLATERAL_CAP:
                return D.SIGNAL_COLLATERAL_CAP
            if cat == D.ERROR_CATEGORY_INSUFFICIENT_FUNDS:
                if getattr(leg, "error_code", None) == "-2019":
                    return D.SIGNAL_INSUFFICIENT_MARGIN
                return D.SIGNAL_INSUFFICIENT_BALANCE
        return None

    @staticmethod
    def _leg_terminal(leg) -> bool:
        """A live leg is terminal when confirmed rejected, or accepted+FILLED with
        authoritative figures (T1 §1(b)).

        A UM (perp) FILLED leg whose authoritative quote is still unknown (the
        inline confirm GET came back inconclusive) is NOT terminal — the worker
        drains it next round (query, never resend). The margin (spot) leg reads its
        quote from the POST RESULT, so an accepted+FILLED spot leg is terminal as
        before. An accepted leg that is NEW/PARTIALLY_FILLED stays non-terminal for
        the reconcile pass to poll to FILLED."""
        if leg.dispatch_state == D.LEG_TERMINAL_RECORDED:
            return True
        if leg.dispatch_state == D.LEG_ACCEPTED_OR_QUERYING:
            if leg.exchange_status != D.LEG_FILLED:
                return False
            # T1 §1(b): a UM FILLED leg needs its authoritative quote known.
            if getattr(leg, "leg", None) != "spot" and getattr(leg, "cumulative_quote", None) is None:
                return False
            return True
        return False

    @staticmethod
    def _dispatch_to_outcome(attempt_uuid, spot, perp, record_payload, ts_us) -> AttemptOutcome:
        """Build an AttemptOutcome from two resolved live leg dispatches. Keys the
        category off ``order_id`` presence via :func:`domain.classify_attempt`;
        carries the real cumulative quote (A-6) and the machine-readable error
        classification (A-7). A fatal error on either leg surfaces an outcome-
        level ``error_category="fatal"`` so the store stops the task (rows 1–2).

        ``ts_us`` is the wall clock at settlement (10-design §4(a)): the live
        exposure timestamp, identical in meaning to the reconcile path's
        ``_exposure_from_legs``. Mandatory — there is no safe default."""
        spot_leg = {
            "status": D.LEG_REJECTED if spot.dispatch_state == D.LEG_TERMINAL_RECORDED
            else (spot.exchange_status or D.LEG_NEW),
            "filled_qty": spot.executed_qty,
            "avg_price": spot.avg_price,
            "cumulative_quote": spot.cumulative_quote,
            "order_id": spot.order_id,
            "client_order_id": None,
            "error_code": getattr(spot, "error_code", None),
            "error_category": getattr(spot, "error_category", None),
        }
        perp_leg = {
            "status": D.LEG_REJECTED if perp.dispatch_state == D.LEG_TERMINAL_RECORDED
            else (perp.exchange_status or D.LEG_NEW),
            "filled_qty": perp.executed_qty,
            "avg_price": perp.avg_price,
            "cumulative_quote": perp.cumulative_quote,
            "order_id": perp.order_id,
            "client_order_id": None,
            "error_code": getattr(perp, "error_code", None),
            "error_category": getattr(perp, "error_category", None),
        }
        category = D.classify_attempt(spot_leg, perp_leg)
        exposure = (
            D.build_leg_exposure(spot_leg, perp_leg, ts_us)
            if category == D.ATTEMPT_SINGLE_LEG_EXPOSURE
            else None
        )
        # A fatal exchange fact on either leg (insufficient balance/margin/filter/
        # min-notional/symbol/mode) stops the task (amendment rows 1–2). The leg's
        # error_code is carried up so the stopped task surfaces the exact reason.
        fatal = (
            spot_leg["error_category"] == "fatal"
            or perp_leg["error_category"] == "fatal"
        )
        if fatal:
            fatal_leg = spot_leg if spot_leg["error_category"] == "fatal" else perp_leg
            error_category = "fatal"
            error_code = fatal_leg["error_code"]
            error_reason_zh = D.stop_reason_zh(D.STOP_REASON_EXCHANGE_FATAL)
        else:
            error_category = None
            error_code = None
            error_reason_zh = None
        return AttemptOutcome(
            attempt_id=attempt_uuid,
            category=category,
            spot=spot_leg,
            perp=perp_leg,
            record_payload=record_payload,
            exposure=exposure,
            error_category=error_category,
            error_code=error_code,
            error_reason_zh=error_reason_zh,
        )

    @staticmethod
    def _query_verdict_terminal(verdict) -> bool:
        """A query verdict is terminal when confirmed rejected/absent, or when an
        accepted leg reaches a final outcome (FILLED/CANCELED/EXPIRED/REJECTED),
        retaining any partial fill. NEW/PARTIALLY_FILLED keep querying
        (amendment: query both legs until each has a final outcome)."""
        if verdict.dispatch_state == D.LEG_TERMINAL_RECORDED:
            return True
        if verdict.dispatch_state == D.LEG_ACCEPTED_OR_QUERYING:
            return verdict.exchange_status in (
                D.LEG_FILLED,
                D.LEG_REJECTED,
                D.LEG_EXPIRED,
                D.LEG_CANCELED,
            )
        return False

    @staticmethod
    def _query_verdict_decisive(verdict) -> bool:
        """Whether a query verdict is one of the four conclusive (decisive)
        responses 00-task.md §T3 requires persisted: a fill (FILLED), a confirmed
        rejection (REJECTED / EXPIRED / CANCELED), a confirmed absent order
        (error_category=absent, i.e. 404 / -2013), or a rate-limit signal
        (429 / -1003 / 418). NEW / PARTIALLY_FILLED and inconclusive verdicts
        (UNKNOWN, no status) are NOT decisive: they insert a placeholder row that a
        later decisive response replaces, and they never replace one. Decided here,
        from the verdict the caller already holds — never re-derived from the raw
        body inside the store."""
        if getattr(verdict, "rate_limited", False):
            return True
        if getattr(verdict, "error_category", None) == D.ERROR_CATEGORY_ABSENT:
            return True
        status = getattr(verdict, "exchange_status", None)
        return status in (D.LEG_FILLED, D.LEG_REJECTED, D.LEG_EXPIRED, D.LEG_CANCELED)

    @staticmethod
    def _failed_outcome(ctx: AttemptContext, reason: str) -> AttemptOutcome:
        empty_leg = {
            "status": D.LEG_UNKNOWN,
            "filled_qty": "0",
            "avg_price": None,
            "order_id": None,
            "client_order_id": None,
        }
        return AttemptOutcome(
            attempt_id=ctx.attempt_id,
            category=D.ATTEMPT_FAILED,
            spot=empty_leg,
            perp=empty_leg,
            record_payload={"transport": "failed", "reason": reason},
            exposure=None,
        )
