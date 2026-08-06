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
from decimal import Decimal
from typing import Callable, Protocol

from . import domain as D
from .executor import (
    AttemptContext,
    AttemptOutcome,
    DisabledHedgeExecutor,
    HedgeExecutor,
    RecordTransportExecutor,
    _client_order_ids,
    build_perp_order_params,
    build_spot_order_params,
)
from .scheduler import HedgeOpenScheduler
from .store import HedgeOpenStore, UnknownTaskError


_CREATE_BODY_KEYS = ("coin", "direction", "mode", "single_amount", "target_n", "task_type")


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
    return D.spot_order_symbol(coin, task.get("preflight_snapshot"))

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
# fail-closed preflight retry, and a shared 429/Retry-After write delay. These
# share the ``hedge_open_log`` table (attempt_id NULL); an attempt's own row
# projects separately with ``kind="attempt"``.
_ENTRY_EVENT_KINDS = (
    "task_stopped",
    "threshold_paused",
    "task_paused",
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
    means an incomplete read -> fail-closed retry (I-7)."""

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
    ) -> D.PreflightSnapshot | None: ...


class DisabledPreflightProvider:
    """The default provider: no preflight data (dry-run, no network read)."""

    def get_snapshot(self, coin: str, direction: str, task_type: str = "open") -> D.PreflightSnapshot | None:
        return None


# ---------------------------------------------------------------------------
# Document serialization (frozen field names, breakdown §3.2-§3.4)
# ---------------------------------------------------------------------------


def task_to_doc(task: dict, *, worker_active: bool | None = None) -> dict:
    q_common = task["q_common"]
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
    ):
        self._mono_us = mono_us or _real_mono_us
        self._wall_us = wall_us or _real_wall_us
        self._store = HedgeOpenStore(
            db_path, executor_mode_snapshot=mode, now_us=self._wall_us(),
        )
        # Default executor is the dry-run record transport (ADR-4): it records
        # the would-send params and returns a simulated outcome, and performs NO
        # network POST. A real POST is reachable only under APP_HEDGE_EXECUTOR=
        # live AND the Start gate AND a live executor (injected by the server
        # with a fresh preflight provider); the default disabled/record executor
        # keeps a real POST unreachable. DisabledHedgeExecutor is an injectable
        # zero-record alternative.
        self._executor: HedgeExecutor = executor or RecordTransportExecutor()
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

    def stop(self) -> None:
        self._scheduler.stop()
        # Wake every task-local worker so its bounded loop exits promptly.
        with self._workers_lock:
            events = list(self._stop_events.values())
        for ev in events:
            ev.set()

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
        # Round-1 freeze (frozen §3.1): only ``immediate`` is dispatchable this
        # round. ``smooth`` remains a reserved vocabulary word (validate_mode
        # accepts it) but is rejected here so the immediate engine never runs a
        # smooth-labeled task.
        if mode != D.MODE_IMMEDIATE:
            raise D.invalid_field("mode", f"round-1 supports only {D.MODE_IMMEDIATE!r}")
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
        task_id = str(uuid.uuid4())
        now_us = self._wall_us()
        print(
            f"[HEDGE-CREATE] success task_id={task_id[:8]} task_type={task_type} "
            f"coin={coin} direction={direction} q={D.fmt_decimal(preflight.q_common)}",
            file=sys.stderr, flush=True,
        )
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
        # exposure_alert is ADVISORY (breakdown §4.5): a single-leg exposure no
        # longer freezes scheduling, so it does not block start.
        updated = self._store.set_task_status(task_id, D.STATUS_RUNNING, self._wall_us())
        # Amendment 21: Start/recover launches THIS task's bounded worker (live
        # mode) and returns immediately — no global scan, no synchronous POST.
        if self._live_dispatch_capable():
            self.ensure_worker(task_id)
        return 200, self._doc(updated)

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
        return 200, self._doc(updated)

    def post_fill_once(self, task_id: str) -> tuple[int, dict]:
        task = self._get_task_or_404(task_id)
        self._require_fillable(task)
        if self._live_dispatch_capable():
            # Amendment 21: every live POST runs through the task-local worker.
            # fill-once arms the task (running) and launches/refreshes its worker;
            # it never performs a synchronous live POST here.
            if task["status"] != D.STATUS_RUNNING:
                task = self._store.set_task_status(task_id, D.STATUS_RUNNING, self._wall_us())
            self.ensure_worker(task_id)
            return 200, self._doc(task)
        task, _ = self._dispatch_one_for_task(task, self._wall_us())
        return 200, self._doc(task)

    def post_fill_all(self, task_id: str) -> tuple[int, dict]:
        task = self._get_task_or_404(task_id)
        self._require_fillable(task)
        if self._live_mode:
            # Amendment 21: live fill-all arms the task and launches its worker;
            # the worker drives every pair (no synchronous live POST loop here).
            if task["status"] != D.STATUS_RUNNING:
                task = self._store.set_task_status(task_id, D.STATUS_RUNNING, self._wall_us())
            if self._live_dispatch_capable():
                self.ensure_worker(task_id)
            return 200, self._doc(task)
        now_us = self._wall_us()
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
        # exposure_alert no longer blocks fill (advisory, §4.5).

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
        }.get(kind)
        if kind == "task_stopped":
            next_action, error_category = "stopped", "fatal"
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
        return 200, settings_to_doc(result, self._mode)

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

    def ensure_worker(self, task_id: str) -> bool:
        """Create or durably claim exactly ONE local worker for ``task_id``
        (amendment 21). Single critical section under ``_workers_lock``: if a
        live worker already owns the task it is reused; a dead/stale registry
        entry is replaced. The worker is a daemon thread bounded to this task
        only — it never scans or queries another task. Returns True iff a worker
        is (now) running for this task."""
        with self._workers_lock:
            existing = self._workers.get(task_id)
            if existing is not None and existing.is_alive():
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
            with self._workers_lock:
                if self._workers.get(task_id) is threading.current_thread():
                    self._workers.pop(task_id, None)
            # F1: worker exit clears this task's per-leg retry counters — a leg
            # left non-terminal (e.g. the manual-recovery pause) must not keep its
            # old count, and a paused/done/deleted card re-drained on recovery
            # starts a fresh budget (never resends). Best-effort: a store read
            # failure here must not mask the exit.
            self._clear_task_leg_retries(task_id)

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
            return self._worker_exit(task_id, D.WORKER_EXIT_START_GATE_OFF)
        # 功能三：close 任务受独立平仓闸门（close_gate）约束（默认开，Human 已拍板）。
        if task.get("task_type") == D.TASK_TYPE_CLOSE and not self.is_close_gate_on():
            return self._worker_exit(task_id, D.WORKER_EXIT_CLOSE_GATE_OFF)
        # 功能三（close 完成判定，以合约腿为准；Human 2026-08：close 任务从 running
        # 变为其他状态必须先走合约无仓核实）：无仓即平完（done + close_cycle +
        # close_log）；还有仓且次数用完 = 部分平完成（done、周期不关、不写结算——
        # 周期未结束）；还有仓且有次数 → 继续下一条 attempt；查仓失败暂停
        # （fail-closed，绝不把「查不到」当「已平完」）。
        if task.get("task_type") == D.TASK_TYPE_CLOSE:
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
            # verdict == "open"：合约仍有仓
            if task["scheduled_attempt_count"] >= task["target_n"]:
                # 次数用完 + 还有仓 = 部分平完成：任务 done、周期不关（用户拍板语义）
                self._store.append_log(
                    task["id"], now_us, "close_partial_done",
                    {"coin": task["coin"], "direction": task["direction"],
                     "reason": "合约仍有仓，本次平仓目标完成，周期未关闭"},
                )
                self._store.set_task_status(task["id"], D.STATUS_DONE, now_us)
                return True
            # 还有次数 → 继续下一条 attempt
        else:
            if task["scheduled_attempt_count"] >= task["target_n"]:
                return self._worker_exit(task_id, D.WORKER_EXIT_TARGET_REACHED)
        # 平仓现货卖出重设计（2026-08）：forward close 首个 attempt 发单前一次性
        # 检查普通现货余额（不足划转补足，失败即停、不重试、不发单）；后续 attempt
        # 不再进入该路径（幂等；paused 后 worker 被既有拦截挡住）。
        if (task.get("task_type") == D.TASK_TYPE_CLOSE
                and task["scheduled_attempt_count"] == 0):
            err = self._ensure_close_spot_balance(task, now_us)
            if err is not None:
                self._pause_task_local(
                    task, D.PAUSE_REASON_CLOSE_SPOT_BALANCE, err, now_us,
                    kind="close_spot_balance",
                )
                return True
        # Dispatch the next pair (preflight -> reserve -> two-leg submit).
        _, signal = self._dispatch_one_for_task(task, now_us)
        if signal == D.SIGNAL_RATE_LIMITED:
            self._pause_task_local(
                task, D.PAUSE_REASON_RATE_LIMITED, None, now_us, kind="rate_limited",
            )
            return False  # 429: drain the just-submitted pair next round, then exit
        if signal in D.SIGNAL_TASK_LOCAL_PAUSE:
            self._pause_from_signal(task, signal, now_us)
            return False
        if signal == D.SIGNAL_PREFLIGHT_INCOMPLETE:
            return self._worker_exit(task_id, D.WORKER_EXIT_PREFLIGHT_INCOMPLETE)
        if signal == D.SIGNAL_PREFLIGHT_FATAL:
            return self._worker_exit(task_id, D.WORKER_EXIT_PREFLIGHT_FATAL)
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
    def _log_close_transfer(self, task_id: str, now_us: int, action: str,
                            coin: str, asset: str, amount: str | None,
                            reason: str | None = None) -> None:
        """close_transfer 审计行（划转发起/成功/失败/回流），任务卡日志页可见。"""
        payload = {
            "action": action,
            "coin": coin,
            "asset": asset,
            "amount": amount,
        }
        if reason is not None:
            payload["reason"] = reason
        self._store.append_log(task_id, now_us, "close_transfer", payload)

    def _ensure_close_spot_balance(self, task: dict, now_us: int) -> str | None:
        """forward close 发单前：普通现货账户余额检查 + 一次性划转补足（Human 拍板）。

        仅 forward close（现货 SELL 走普通账户）；reverse close（买现货走统一账户）跳过：
        - 普通账户该币 free ≥ 计划卖量 → 无需划转，返回 None；
        - 不足 → ``universal_transfer('PORTFOLIO_MARGIN_MAIN', base, 差额)`` 一次 →
          复检普通账户余额 → 仍不足 → 中文错误（fail-closed，防「响应丢失但划转成功」
          误判）；
        - 任一步失败/异常 → 中文错误，**不重试、不发单**。
        dry-run（executor 无 query_spot_free / universal_transfer）→ None（模拟余额足够）。
        """
        if task.get("task_type") != D.TASK_TYPE_CLOSE or task["direction"] != D.DIR_FORWARD:
            return None
        q_spot = getattr(self._executor, "query_spot_free", None)
        q_unified = getattr(self._executor, "query_unified_free", None)
        xfer = getattr(self._executor, "universal_transfer", None)
        if q_spot is None or xfer is None:
            return None  # dry-run：模拟余额足够
        sell_amount = D.Decimal(task["single_amount"])
        base_asset = D._merge_base_asset(task["coin"]) or task["coin"].replace("USDT", "")
        free = q_spot(base_asset)
        if free is None:
            return "现货账户余额查询失败，无法确认平仓现货余额（fail-closed，未发单）"
        if free >= sell_amount:
            return None
        diff = sell_amount - free
        # 划转前检查统一账户余额（2026-08）：不足直接提示，不盲划——
        # 否则划了才知道失败、日志只有 RuntimeError 无详情（COOKIE 现场教训）。
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
        recheck = q_spot(base_asset)  # 复检：防响应丢失误判
        if recheck is None:
            return "划转后复检现货余额失败，无法确认已补足（fail-closed，未发单）"
        if recheck < sell_amount:
            return (f"划转后普通账户现货仍不足"
                    f"（{D.fmt_decimal(recheck)} < {D.fmt_decimal(sell_amount)}），"
                    f"未发单；请人工核对")
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
        # 2026-08：滑点率（%，成交均价 vs 开/平仓 est_price 加权；Human 要求百分比）
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
                base_asset = D._merge_base_asset(task["coin"])
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
        non-terminal for manual verification (never resent)."""
        if task["status"] in (D.STATUS_RUNNING, D.STATUS_PAUSED):
            self._pause_task_local(
                task, D.PAUSE_REASON_ORDER_STATE_UNKNOWN, drain_signal, now_us,
            )
            return
        self._store.record_task_event(
            task["id"],
            "task_paused",
            {
                "reason": D.PAUSE_REASON_ORDER_STATE_UNKNOWN,
                "reason_zh": D.pause_reason_zh(D.PAUSE_REASON_ORDER_STATE_UNKNOWN),
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
            self._pause_task_local(
                task, self._pause_reason_for_signal(signal), signal, now_us, kind=kind,
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
        eligible = self._store.list_eligible_tasks()
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

        Returns ``None`` for an incomplete read -> fail-closed retry (I-7): no
        attempt, no POST, no count, no simulated call. A ``fatal`` result stops
        the task (amendment rows 1–2); an ``ok`` result carries the exact
        ``q_common``/snapshot this pair will post. Non-fatal rejections that are
        not incomplete (e.g. a transient balance gap on a non-fatal path) are
        also treated as fail-closed retry.
        """
        # close 任务：与 create_task 一致用反转方向做余额检查（forward close 卖
        # 现货需现货余额；provider 内 route_dir 再反转回持仓方向做路由决策）。
        preflight_dir = task["direction"]
        if task.get("task_type") == D.TASK_TYPE_CLOSE:
            preflight_dir = (
                D.DIR_REVERSE if task["direction"] == D.DIR_FORWARD
                else D.DIR_FORWARD
            )
        snapshot = self._preflight.get_snapshot(
            task["coin"], preflight_dir,
            task_type=task.get("task_type") or D.TASK_TYPE_OPEN,
        )
        if snapshot is None:
            return None
        preflight = D.compute_preflight(
            snapshot,
            task["coin"],
            preflight_dir,  # 余额校验必须与路由决策同方向（close 用反转方向校验实际资金约束）
            D.Decimal(task["single_amount"]),
            task["target_n"],
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
            # fail-closed retry next tick (no attempt, no POST).
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

    def _record_preflight_incomplete(self, task: dict, now_us: int) -> None:
        """Fail-closed (I-7): a missing preflight fact records a retry event but
        performs no attempt, no POST, and no business-state change."""
        self._store.record_task_event(
            task["id"],
            "preflight_incomplete",
            {
                "reason": "preflight_incomplete",
                "coin": task["coin"],
                "direction": task["direction"],
            },
            now_us,
        )

    def _dispatch_one_for_task(self, task: dict, now_us: int) -> tuple[dict, str | None]:
        """Durable-before-send: a fresh preflight (live path only) -> persist the
        immutable attempt + both client IDs + sanitized request shapes in ONE
        transaction BEFORE any executor call (ADR-2). The executor is then
        invoked with no store transaction held; the outcome is resolved in a
        second short transaction.

        Returns ``(task, signal)`` (amendment 21). ``signal`` tells the task-local
        worker what happened on this pair: ``SIGNAL_RATE_LIMITED`` / a
        ``SIGNAL_INSUFFICIENT_*`` -> pause THIS task only; ``SIGNAL_PREFLIGHT_*``
        are fail-closed / fatal (the worker exits); ``None`` is a normal dispatch.

        Fresh-preflight-first + fail-closed (A-2/A-3) applies ONLY on the live
        POST path. A fatal fact stops the task (no attempt/POST); an incomplete
        read is fail-closed retry (no attempt/POST/count). The dry-run record
        transport reuses the stored q_common/snapshot and never POSTs.
        """
        live = self._live_dispatch_capable() and self.is_start_gate_on()
        if live:
            fresh = self._resolve_fresh_preflight(task)
            if fresh is None or not fresh.ok:
                # incomplete read -> fail-closed retry (I-7); fatal -> stop (rows 1–2).
                if fresh is not None and fresh.fatal:
                    self._stop_task_fatal_preflight(task, fresh, now_us)
                    return self._store.get_task(task["id"]) or task, D.SIGNAL_PREFLIGHT_FATAL
                self._record_preflight_incomplete(task, now_us)
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
        task_type = task.get("task_type") or D.TASK_TYPE_OPEN
        actions = D.direction_to_leg_actions(
            task["direction"], position_side_mode or D.POS_MODE_BOTH,
            task_type=task_type,
        )
        send_qty = q_common if q_common is not None else D.Decimal(task["single_amount"])
        spot_route = (snapshot_record or {}).get(
            "spot_route", D.SPOT_ROUTE_PAPI_MARGIN
        )
        spot_order_symbol = D.spot_order_symbol(task["coin"], snapshot_record)
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
        q_common_str = D.fmt_decimal(q_common) if q_common is not None else task["single_amount"]
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
        )
        if attempt is None:
            # Task is no longer eligible (paused/done/deleted/out-of-budget) — no POST.
            return self._store.get_task(task["id"]) or task, None
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
        )
        signal: str | None = None
        if live:
            signal = self._dispatch_live(attempt, ctx, now_us)
        else:
            self._dispatch_simulated(attempt, ctx, now_us)
        return self._store.get_task(task["id"]) or task, signal

    def _dispatch_simulated(self, attempt: dict, ctx: AttemptContext, now_us: int) -> None:
        """Record/disabled path (no network POST): a synchronous simulated
        outcome resolves both legs to a terminal verdict immediately."""
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
        dispatch = self._executor.dispatch(ctx)
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
