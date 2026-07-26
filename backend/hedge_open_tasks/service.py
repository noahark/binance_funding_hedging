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


_CREATE_BODY_KEYS = ("coin", "direction", "mode", "single_amount", "target_n")

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
    """

    def get_snapshot(self, coin: str) -> D.PreflightSnapshot | None: ...


class DisabledPreflightProvider:
    """The default provider: no preflight data (dry-run, no network read)."""

    def get_snapshot(self, coin: str) -> D.PreflightSnapshot | None:
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


def settings_to_doc(settings: dict, executor_mode: str) -> dict:
    return {
        "executor_mode": executor_mode,
        "start_gate": bool(settings["start_gate"]),
        "interval_seconds": int(settings["interval_us"]) // 1_000_000,
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


def _leg_to_doc(leg: dict | None) -> dict:
    """Project one mutable leg row to the frozen §3.4 per-leg shape.

    Decimal fields stay strings; ``avg_price`` is the weighted average
    ``cumulative_quote_amt / cumulative_base_qty`` (None when there is no base
    fill yet — a PREPARED/REJECTED leg). The spot leg carries
    ``fee_amount``/``fee_asset`` only when they were recorded.
    """
    leg = leg or {}
    base = D.Decimal(leg.get("cumulative_base_qty") or "0")
    quote = D.Decimal(leg.get("cumulative_quote_amt") or "0")
    avg = D.fmt_decimal(quote / base) if base > 0 else None
    doc = {
        "client_order_id": leg.get("client_order_id"),
        "order_id": leg.get("order_id"),
        "status": leg.get("exchange_status"),
        "cumulative_base_qty": D.fmt_decimal(base),
        "cumulative_quote_amt": D.fmt_decimal(quote),
        "avg_price": avg,
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
    quote = D.Decimal(leg.get("cumulative_quote_amt") or "0")
    avg = D.fmt_decimal(quote / base) if base > 0 else None
    return {
        "side": spot_side,
        "client_order_id": leg.get("client_order_id"),
        "order_id": leg.get("order_id"),
        "status": leg.get("exchange_status"),
        "cumulative_base_qty": D.fmt_decimal(base),
        "cumulative_quote_amt": D.fmt_decimal(quote),
        "avg_price": avg,
        "fee_amount": leg.get("fee_amount"),
        "fee_asset": leg.get("fee_asset"),
    }


def _entry_perp_leg(leg: dict | None, perp_side: str | None) -> dict:
    leg = leg or {}
    base = D.Decimal(leg.get("cumulative_base_qty") or "0")
    quote = D.Decimal(leg.get("cumulative_quote_amt") or "0")
    avg = D.fmt_decimal(quote / base) if base > 0 else None
    return {
        "side": perp_side,
        "client_order_id": leg.get("client_order_id"),
        "order_id": leg.get("order_id"),
        "status": leg.get("exchange_status"),
        "cumulative_base_qty": D.fmt_decimal(base),
        "cumulative_quote_amt": D.fmt_decimal(quote),
        "avg_price": avg,
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
    ):
        self._store = HedgeOpenStore(db_path, executor_mode_snapshot=mode)
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
        # Whether the injected live executor holds real credentials (server
        # computes this from the live client; default False for dry-run). The
        # value is a boolean only — never a credential value (Boundary C).
        self._credentials_present = bool(credentials_present)
        self._mono_us = mono_us or _real_mono_us
        self._wall_us = wall_us or _real_wall_us
        self._last_tick_mono: int | None = None
        # Amendment 21 task-local workers: each RUNNING task owns at most ONE
        # bounded-lifetime worker thread (no global guardian/scanner). ``_workers``
        # maps task_id -> live worker thread; ``_stop_events`` carries the per-task
        # interrupt a pause/stop/delete/settle sets to wake a pacing worker. The
        # scheduler/tick no longer drive immediate dispatch through a global scan;
        # an HTTP Start/recover or a one-shot recovery discovery launches a worker.
        self._workers: dict[str, threading.Thread] = {}
        self._stop_events: dict[str, threading.Event] = {}
        self._workers_lock = threading.Lock()
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

    def is_start_gate_on(self) -> bool:
        return bool(self._store.get_settings()["start_gate"])

    # ------------------------------------------------------------------ tasks

    def create_task(self, body) -> tuple[int, dict]:
        if not isinstance(body, dict):
            raise D.HedgeError(400, "invalid_json", "request body must be a JSON object")
        D.reject_unknown_keys(body, _CREATE_BODY_KEYS)
        coin = D.validate_coin(body.get("coin"))
        direction = D.validate_direction(body.get("direction"))
        mode = D.validate_mode(body.get("mode") or D.DEFAULT_MODE)
        # Round-1 freeze (frozen §3.1): only ``immediate`` is dispatchable this
        # round. ``smooth`` remains a reserved vocabulary word (validate_mode
        # accepts it) but is rejected here so the immediate engine never runs a
        # smooth-labeled task.
        if mode != D.MODE_IMMEDIATE:
            raise D.invalid_field("mode", f"round-1 supports only {D.MODE_IMMEDIATE!r}")
        single_amount = D.validate_single_amount(body.get("single_amount"))
        target_n = D.validate_target_n(body.get("target_n"))

        snapshot = self._preflight.get_snapshot(coin)
        preflight = D.compute_preflight(
            snapshot, coin, direction, D.Decimal(single_amount), target_n
        )
        if preflight.rejection == D.REJECT_INSUFFICIENT_BALANCE:
            raise D.HedgeError(
                400,
                "insufficient_balance",
                f"{direction} open balance check failed",
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
        )
        return 201, self._doc(task)

    def list_tasks(self, status_query: str | None) -> tuple[int, dict]:
        status_filter = D.filter_status_for_list(status_query)
        tasks = [self._doc(t) for t in self._store.list_tasks(status_filter)]
        return 200, {"tasks": tasks}

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
    ) -> tuple[int, dict]:
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
        overall = {"task_stopped": "task_stopped", "threshold_paused": "task_paused"}.get(kind)
        if kind == "task_stopped":
            next_action, error_category = "stopped", "fatal"
        elif kind == "threshold_paused":
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
        if drain_signal in D.SIGNAL_INSUFFICIENT:
            self._pause_task_local(
                task, self._insufficient_pause_reason(drain_signal), drain_signal, now_us,
            )
            return False
        own = self._store.list_non_terminal_legs_for_task(task_id)
        if own:
            return False  # still draining this pair; keep querying (pacing in loop)
        # No in-flight legs: decide exit vs. next pair.
        if task["status"] != D.STATUS_RUNNING:
            return self._worker_exit(task_id, D.WORKER_EXIT_TASK_NOT_RUNNING)
        if not self.is_start_gate_on():
            return self._worker_exit(task_id, D.WORKER_EXIT_START_GATE_OFF)
        if task["scheduled_attempt_count"] >= task["target_n"]:
            return self._worker_exit(task_id, D.WORKER_EXIT_TARGET_REACHED)
        # Dispatch the next pair (preflight -> reserve -> two-leg submit).
        _, signal = self._dispatch_one_for_task(task, now_us)
        if signal == D.SIGNAL_RATE_LIMITED:
            self._pause_task_local(
                task, D.PAUSE_REASON_RATE_LIMITED, None, now_us, kind="rate_limited",
            )
            return False  # 429: drain the just-submitted pair next round, then exit
        if signal in D.SIGNAL_INSUFFICIENT:
            self._pause_task_local(
                task, self._insufficient_pause_reason(signal), signal, now_us,
            )
            return False
        if signal == D.SIGNAL_PREFLIGHT_INCOMPLETE:
            return self._worker_exit(task_id, D.WORKER_EXIT_PREFLIGHT_INCOMPLETE)
        if signal == D.SIGNAL_PREFLIGHT_FATAL:
            return self._worker_exit(task_id, D.WORKER_EXIT_PREFLIGHT_FATAL)
        return False  # dispatched -> next round resolves/drains this pair

    def _reconcile_own_legs(self, task_id: str, task: dict, now_us: int) -> str | None:
        """Query ONLY this task's non-terminal legs by client order ID to
        terminal, then settle the pair once (amendment 21: no global scan). The
        executor is called with no store lock held. Returns a drain signal when a
        leg surfaces a 429 (rate_limited) or a confirmed insufficient-funds fact;
        None otherwise. A query that stays inconclusive leaves the leg
        non-terminal (keep querying, never resend — ADR-2)."""
        if not hasattr(self._executor, "query_leg"):
            self._recover_crash_gaps(task_id, now_us)
            return None
        legs = self._store.list_non_terminal_legs_for_task(task_id)
        coin = task["coin"] if task is not None else None
        finalized: set[int] = set()
        drain_signal: str | None = None
        for leg in legs:
            verdict = self._executor.query_leg(leg["leg"], coin, leg["client_order_id"])
            if verdict is None:
                continue  # inconclusive — keep querying
            if getattr(verdict, "rate_limited", False):
                # R2-F2 (user authorization 28 §2.2): a query-phase 429/-1003/418.
                # Leave the leg EXACTLY as it is (non-terminal; the write POST is
                # never resent) and surface the throttle so the worker pauses THIS
                # task and exits for manual recovery instead of polling into the
                # ban. The leg is NOT resolved here and NOT added to finalized.
                if drain_signal is None:
                    drain_signal = D.SIGNAL_RATE_LIMITED
                continue
            terminal = self._query_verdict_terminal(verdict)
            try:
                self._store.resolve_leg_from_query(
                    leg["id"],
                    exchange_status=verdict.exchange_status or D.LEG_UNKNOWN,
                    order_id=verdict.order_id,
                    base_qty=verdict.executed_qty,
                    quote_amt=verdict.cumulative_quote,
                    fee_amount=None,
                    fee_asset=None,
                    now_us=now_us,
                    terminal=terminal,
                    error_code=getattr(verdict, "error_code", None),
                    error_category=getattr(verdict, "error_category", None),
                )
            except Exception:
                continue
            if getattr(verdict, "error_category", None) == "insufficient_funds":
                drain_signal = D.SIGNAL_INSUFFICIENT_BALANCE
            if terminal:
                finalized.add(leg["attempt_id"])
        # Review-1 r3 P1-1: "this pair does not count as a failure" is decided by
        # the ATTEMPT's own rate-limited fact (stamped at the 429 dispatch), NOT by
        # the task-level pause_reason — which a manual resume has already cleared.
        for attempt_id in finalized:
            try:
                attempt = self._store.get_attempt(attempt_id)
                if attempt is not None and attempt.get("rate_limited"):
                    # Amendment 21: a 429 pair is closed WITHOUT consuming the
                    # failure counter; the in-flight guard still clears.
                    self._store.settle_attempt_no_counters(attempt_id, now_us)
                else:
                    self._store.finalize_attempt(attempt_id, now_us)
            except Exception:
                pass
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
                if attempt.get("rate_limited"):
                    self._store.settle_attempt_no_counters(attempt["id"], now_us)
                else:
                    self._store.finalize_attempt(attempt["id"], now_us)
            except Exception:
                pass

    def _pause_task_local(
        self, task: dict, pause_reason: str, insufficient_signal: str | None,
        now_us: int, *, kind: str = "task_paused",
    ) -> None:
        """Persist a task-local pause (amendment 21): status=paused + the precise
        safe reason + an audit event, for THIS task only. No cross-task linkage,
        no consecutive-failure churn. A 429 uses the ``rate_limited`` kind; an
        insufficient-funds fact uses ``task_paused``. Idempotent on status."""
        pause_zh = D.pause_reason_zh(pause_reason)
        updated = self._store.pause_task(task["id"], pause_reason, pause_zh, now_us)
        payload = {
            "reason": pause_reason,
            "reason_zh": pause_zh,
            "coin": task["coin"],
            "direction": task["direction"],
        }
        if insufficient_signal is not None:
            payload["signal"] = insufficient_signal
        self._store.record_task_event(task["id"], kind, payload, now_us)
        if updated is not None:
            task.update(updated)

    @staticmethod
    def _insufficient_pause_reason(signal: str) -> str:
        """Map an insufficient-funds drain/dispatch signal to its pause reason."""
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
        snapshot = self._preflight.get_snapshot(task["coin"])
        if snapshot is None:
            return None
        preflight = D.compute_preflight(
            snapshot,
            task["coin"],
            task["direction"],
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
        actions = D.direction_to_leg_actions(
            task["direction"], position_side_mode or D.POS_MODE_BOTH
        )
        send_qty = q_common if q_common is not None else D.Decimal(task["single_amount"])
        spot_shape = build_spot_order_params(task["coin"], actions, send_qty, spot_cid)
        perp_shape = build_perp_order_params(task["coin"], actions, send_qty, perp_cid)
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
            self._store.resolve_attempt(attempt["id"], outcome, now_us)
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
            except Exception:
                pass
            return D.SIGNAL_RATE_LIMITED
        insufficient = self._insufficient_signal_from_legs(spot, perp)
        if insufficient is not None and not has_querying:
            # Both legs terminal with a confirmed insufficient-funds fact: settle
            # the pair once (clearing the in-flight guard); the worker pauses.
            outcome = self._dispatch_to_outcome(
                attempt["attempt_uuid"], spot, perp, dispatch.record_payload
            )
            try:
                self._store.resolve_attempt(attempt["id"], outcome, now_us)
            except Exception:
                pass
            return insufficient
        if insufficient is not None:
            # Mixed: one leg insufficient-terminal, the other still UNKNOWN — mark
            # the UNKNOWN leg(s); the worker pauses and drains before exit.
            self._mark_legs_querying(attempt, spot, perp, now_us)
            return insufficient
        if has_querying:
            self._mark_legs_querying(attempt, spot, perp, now_us)
            return None
        outcome = self._dispatch_to_outcome(
            attempt["attempt_uuid"], spot, perp, dispatch.record_payload
        )
        leg_terminal = {
            spot.leg: self._leg_terminal(spot),
            perp.leg: self._leg_terminal(perp),
        }
        try:
            self._store.resolve_attempt(
                attempt["id"], outcome, now_us, leg_terminal=leg_terminal
            )
        except Exception:
            pass
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
            except Exception:
                pass

    @staticmethod
    def _insufficient_signal_from_legs(spot, perp) -> str | None:
        """Map a confirmed insufficient-funds leg (``error_category ==
        "insufficient_funds"``) to its amendment-21 pause signal. ``-2019`` ->
        margin; any other confirmed code (``-3041`` / msg-confirmed ``-2010``) ->
        balance. Returns ``None`` when neither leg is insufficient-funds."""
        for leg in (spot, perp):
            if getattr(leg, "error_category", None) == "insufficient_funds":
                if getattr(leg, "error_code", None) == "-2019":
                    return D.SIGNAL_INSUFFICIENT_MARGIN
                return D.SIGNAL_INSUFFICIENT_BALANCE
        return None

    @staticmethod
    def _leg_terminal(leg) -> bool:
        """A live leg is terminal when confirmed rejected, or accepted+FILLED.
        An accepted leg that is NEW/PARTIALLY_FILLED stays non-terminal for the
        reconcile pass to poll to FILLED."""
        if leg.dispatch_state == D.LEG_TERMINAL_RECORDED:
            return True
        if leg.dispatch_state == D.LEG_ACCEPTED_OR_QUERYING:
            return leg.exchange_status == D.LEG_FILLED
        return False

    @staticmethod
    def _dispatch_to_outcome(attempt_uuid, spot, perp, record_payload) -> AttemptOutcome:
        """Build an AttemptOutcome from two resolved live leg dispatches. Keys the
        category off ``order_id`` presence via :func:`domain.classify_attempt`;
        carries the real cumulative quote (A-6) and the machine-readable error
        classification (A-7). A fatal error on either leg surfaces an outcome-
        level ``error_category="fatal"`` so the store stops the task (rows 1–2)."""
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
            D.build_leg_exposure(spot_leg, perp_leg, 0)
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
