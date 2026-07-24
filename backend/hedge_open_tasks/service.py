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

# Conservative shared exchange rate-limit cooldown (breakdown §3.6 / recon §4.4).
# A 429 / -1003 / -1008 surfaced by a live leg blocks new sends for this window;
# it is a local fail-safe, not a Binance SLA.
RATE_LIMIT_COOLDOWN_US = 60 * 1_000_000

# Task-level lifecycle events surfaced on the additive ``entries`` timeline
# (amendment §5): a fatal stop, a consecutive-failure threshold pause, a
# fail-closed preflight retry, and a shared 429/Retry-After write delay. These
# share the ``hedge_open_log`` table (attempt_id NULL); an attempt's own row
# projects separately with ``kind="attempt"``.
_ENTRY_EVENT_KINDS = (
    "task_stopped",
    "threshold_paused",
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


def task_to_doc(task: dict) -> dict:
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
        # Amendment additive (I-4): a fatal stop's reason alongside status=stopped.
        "stop_reason": task["stop_reason"],
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
        self._rate_limited_until_mono: int | None = None
        self._lock = threading.Lock()  # serializes tick() against itself
        self._scheduler = HedgeOpenScheduler(
            self.tick, self._store.get_interval_us, self._mono_us
        )

    # --------------------------------------------------------------- lifecycle

    def close(self) -> None:
        self.stop()
        self._store.close()

    def start(self) -> None:
        self._scheduler.start()

    def stop(self) -> None:
        self._scheduler.stop()

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
        return 201, task_to_doc(task)

    def list_tasks(self, status_query: str | None) -> tuple[int, dict]:
        status_filter = D.filter_status_for_list(status_query)
        tasks = [task_to_doc(t) for t in self._store.list_tasks(status_filter)]
        return 200, {"tasks": tasks}

    def _get_task_or_404(self, task_id: str) -> dict:
        task = self._store.get_task(task_id)
        if task is None:
            raise D.HedgeError(404, "unknown_task", f"unknown task {task_id}")
        return task

    def post_start(self, task_id: str) -> tuple[int, dict]:
        task = self._get_task_or_404(task_id)
        status = task["status"]
        if status == D.STATUS_DELETED:
            raise D.HedgeError(409, "invalid_state", "cannot start a deleted task")
        if status == D.STATUS_DONE:
            return 200, task_to_doc(task)  # idempotent: done stays done
        # exposure_alert is ADVISORY (breakdown §4.5): a single-leg exposure no
        # longer freezes scheduling, so it does not block start.
        updated = self._store.set_task_status(task_id, D.STATUS_RUNNING, self._wall_us())
        return 200, task_to_doc(updated)

    def post_pause(self, task_id: str) -> tuple[int, dict]:
        task = self._get_task_or_404(task_id)
        if task["status"] == D.STATUS_DELETED:
            raise D.HedgeError(409, "invalid_state", "cannot pause a deleted task")
        if task["status"] == D.STATUS_DONE:
            raise D.HedgeError(409, "invalid_state", "cannot pause a done task")
        updated = self._store.set_task_status(task_id, D.STATUS_PAUSED, self._wall_us())
        return 200, task_to_doc(updated)

    def post_delete(self, task_id: str) -> tuple[int, dict]:
        task = self._get_task_or_404(task_id)
        if task["status"] == D.STATUS_DELETED:
            raise D.HedgeError(409, "invalid_state", "task already deleted")
        updated = self._store.set_task_status(task_id, D.STATUS_DELETED, self._wall_us())
        return 200, task_to_doc(updated)

    def post_fill_once(self, task_id: str) -> tuple[int, dict]:
        task = self._get_task_or_404(task_id)
        self._require_fillable(task)
        task = self._dispatch_one_for_task(task, self._wall_us())
        return 200, task_to_doc(task)

    def post_fill_all(self, task_id: str) -> tuple[int, dict]:
        task = self._get_task_or_404(task_id)
        self._require_fillable(task)
        if self._live_mode:
            # Live fill-all is PROHIBITED (breakdown §3.8): every send must pass
            # the one-second scheduler + Start/executor gate. Arm the task
            # (ensure running) and let the scheduler drive; no synchronous POST
            # loop may run here.
            if task["status"] != D.STATUS_RUNNING:
                task = self._store.set_task_status(task_id, D.STATUS_RUNNING, self._wall_us())
            return 200, task_to_doc(task)
        now_us = self._wall_us()
        # Record/disabled path only: a bounded synchronous loop that never POSTs.
        # It continues only while the task is still ``running`` and below its
        # target; reaching ``done`` or a >threshold pause stops dispatch.
        guard = 0
        while task["status"] == D.STATUS_RUNNING and guard < 10_000:
            if task["success_count"] >= task["target_n"]:
                break
            task = self._dispatch_one_for_task(task, now_us)
            guard += 1
            now_us += 1  # keep ts strictly increasing within one call
        return 200, task_to_doc(task)

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

    # ----------------------------------------------------- rate-limit cooldown

    def _in_rate_limit_cooldown(self, now_mono: int) -> bool:
        return (
            self._rate_limited_until_mono is not None
            and now_mono < self._rate_limited_until_mono
        )

    def _enter_rate_limit_cooldown(
        self, now_mono: int, retry_after_seconds: float | None = None
    ) -> None:
        """Enter the shared exchange rate-limit cooldown (breakdown §3.6 / I-5).

        When the live executor surfaces a server ``Retry-After`` (seconds) we
        honor it exactly; otherwise we fall back to the conservative fixed
        window. This is a process-wide technical write delay only — it never
        marks a task failed/paused/stopped/done, and it never alters another
        task's business state (amendment row 6)."""
        if retry_after_seconds:
            wait_us = int(float(retry_after_seconds) * 1_000_000)
        else:
            wait_us = RATE_LIMIT_COOLDOWN_US
        self._rate_limited_until_mono = now_mono + wait_us

    # --------------------------------------------------------------- scheduler

    def tick(self) -> bool:
        """Run one tick: reconcile first, then dispatch one pair for EVERY
        eligible task if due.

        The automatic scheduler respects the global Start gate (§9) and the
        shared exchange rate-limit cooldown; explicit ``fill-once``/``fill-all``
        bypass the gate because they are operator manual triggers of the record
        transport and never POST.

        Reconciliation runs FIRST on EVERY tick (amendment I-6): already-
        persisted non-terminal legs are polled to a final outcome independent of
        the Start gate, the pacing floor, and the eligible set. A task's
        unresolved pair blocks only that task's next pair; polling continues even
        when Start is off, the task is done/paused/stopped, or no task is
        dispatch-eligible.

        Per-task async cadence (R4-2 / amendment): each eligible running task is
        dispatched on its OWN worker so a slow live preflight/POST/query on one
        card cannot block another card's same-tick pair submission. Both legs
        dispatch concurrently within one pair. The per-task serial rule (one
        in-flight pair, A-9) — not the interval timer — is the pair-N+1 gate
        (amendment I-3: ``interval_seconds`` is a worker/poll pacing floor only).
        Workers are joined before returning so a task still issues at most one
        pair per tick (no same-task re-entry). Durable-before-send and the
        timeout→client-ID query (no resend) rule are unchanged.
        """
        with self._lock:
            now = self._mono_us()
            # Reconcile is never abandoned (I-6): runs every tick, unconditionally.
            try:
                self._reconcile_pending(self._wall_us())
            except Exception:
                pass
            # Dispatch pacing baseline (I-3): interval_seconds paces new
            # submissions uniformly; it never gates pair finality or another task.
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
            if self._in_rate_limit_cooldown(now):
                return False
            eligible = self._store.list_eligible_tasks()
            if not eligible:
                return False
            now_us = self._wall_us()
            self._dispatch_eligible_concurrently(eligible, now_us)
            return True

    def _dispatch_eligible_concurrently(self, eligible: list[dict], now_us: int) -> None:
        """Dispatch one pair for every eligible task concurrently (R4-2).

        Each task runs on its own worker thread so a slow live preflight/POST/
        query on one card does not block another card's same-second submission.
        The workers are joined before this returns: the scheduler therefore
        advances to the next second only after this tick's pairs are submitted
        (one pair per second per task, no same-task re-entry across ticks). Each
        worker is containment-wrapped so one card's failure never stops the
        others. The executor is invoked with no service lock held by the worker
        — the store's own RLock still guards its transactions, so
        durable-before-send and the no-resend client-ID query rule are unchanged.
        """
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
        """Per-task dispatch wrapper (R4-2): contains exceptions so one card's
        failure never stops a sibling card's worker. The dispatch itself is
        :meth:`_dispatch_one_for_task` (durable-before-send; no resend)."""
        try:
            self._dispatch_one_for_task(task, now_us)
        except Exception:
            pass

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

    def _dispatch_one_for_task(self, task: dict, now_us: int) -> dict:
        """Durable-before-send: a fresh preflight (live path only) -> persist the
        immutable attempt + both client IDs + sanitized request shapes in ONE
        transaction BEFORE any executor call (ADR-2). The executor is then
        invoked with no store transaction held; the outcome is resolved in a
        second short transaction.

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
                else:
                    self._record_preflight_incomplete(task, now_us)
                return self._store.get_task(task["id"]) or task
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
            return self._store.get_task(task["id"]) or task
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
        if live:
            self._dispatch_live(attempt, ctx, now_us)
        else:
            self._dispatch_simulated(attempt, ctx, now_us)
        return self._store.get_task(task["id"]) or task

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

    def _dispatch_live(self, attempt: dict, ctx: AttemptContext, now_us: int) -> None:
        """Live path: the executor submits both legs concurrently and returns a
        per-leg dispatch verdict (duck-typed; this package never imports the
        services-layer executor module). Legs with a definite acceptance verdict
        resolve the pair now; any UNKNOWN_QUERYING leg is marked and left for the
        reconcile pass — the write POST is never resent (ADR-2).
        """
        dispatch = self._executor.dispatch(ctx)
        retry_after = getattr(dispatch, "retry_after_seconds", None)
        if getattr(dispatch, "rate_limited", False):
            # Amendment row 6 / I-5: a process-wide technical write delay for the
            # stated exchange wait (shared account/IP limit). Never marks any
            # task failed/paused/stopped/done, never alters another task's state.
            self._enter_rate_limit_cooldown(self._mono_us(), retry_after)
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
        spot = dispatch.spot
        perp = dispatch.perp
        spot_querying = spot.dispatch_state == D.LEG_UNKNOWN_QUERYING
        perp_querying = perp.dispatch_state == D.LEG_UNKNOWN_QUERYING
        if spot_querying or perp_querying:
            for leg in (spot, perp):
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
            return
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

    def _reconcile_pending(self, now_us: int) -> None:
        """Query non-terminal legs by client ID and close them when resolved.

        Runs each tick under the scheduler. A leg whose query is still
        inconclusive stays non-terminal (keep querying, never resend). When both
        legs of an attempt close, :meth:`finalize_attempt` stamps its pair
        outcome + counters. Only a live executor (``query_leg``) reconciles.
        """
        if not hasattr(self._executor, "query_leg"):
            return
        legs = self._store.list_non_terminal_legs()
        finalized: set[int] = set()
        for leg in legs:
            attempt = self._store.get_attempt(leg["attempt_id"])
            if attempt is None:
                continue
            task = self._store.get_task(attempt["task_id"])
            if task is None:
                continue
            verdict = self._executor.query_leg(
                leg["leg"], task["coin"], leg["client_order_id"]
            )
            if verdict is None:
                continue  # inconclusive — keep querying
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
            if terminal:
                finalized.add(leg["attempt_id"])
        for attempt_id in finalized:
            try:
                self._store.finalize_attempt(attempt_id, now_us)
            except Exception:
                pass

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
