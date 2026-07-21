"""Borrow task service — HTTP-facing orchestration over the store + executor.

The service is the single borrow authority. It owns the store, the executor, the
scheduler thread and (for live mode) the execution-owner sidecar lock, and
exposes the local same-origin API methods consumed by ``backend/app/server.py``.
Handlers delegate here only; they never touch SQL or the executor directly
(breakdown §3.10).

Dispatch invariant (amendment §2 / Boundary C §4.5): the pending attempt is
persisted in one short conditional transaction (which re-checks every gate
atomically), the executor is invoked with no store lock or transaction held, and
the attempt is resolved in a second short transaction. A non-owner process never
dispatches even on a forced tick; a rate-limit cooldown blocks every signed
borrow-client call including reconciliation GETs.
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Callable

from . import domain as D
from .executor import BorrowExecutor, DisabledBorrowExecutor, ExecutorResult
from .ownership import BorrowDbOwnership
from .scheduler import BorrowScheduler, select_next_task
from .store import BorrowTaskStore, UnknownTaskError, VersionConflictError

# Whitelisted mutation-body keys (breakdown §3.7): unknown keys are rejected
# deterministically as ``invalid_field`` instead of being silently ignored.
_CREATE_BODY_KEYS = ("asset", "amount_per_attempt", "success_target")
_EDIT_BODY_KEYS = ("amount_per_attempt", "success_target", "version")
_SETTINGS_BODY_KEYS = ("interval_seconds",)


def _real_mono_us() -> int:
    return int(time.monotonic() * 1_000_000)


def _real_wall_us() -> int:
    return int(time.time() * 1_000_000)


def _latest_result_to_doc(task: dict) -> dict | None:
    if task.get("latest_result_category") is None:
        return None
    return {
        "result_category": task["latest_result_category"],
        "business_code": task["latest_result_business_code"],
        "reason": task["latest_result_reason"],
        "tran_id": task["latest_result_tran_id"],
        "finished_at": D.us_to_iso(task["latest_result_finished_at_us"]),
    }


def task_to_doc(task: dict) -> dict:
    return {
        "schema_version": D.SCHEMA_VERSION,
        "id": task["id"],
        "asset": task["asset"],
        "amount_per_attempt": task["amount_per_attempt"],
        "success_target": task["success_target"],
        "success_count": task["success_count"],
        "status": task["status"],
        "version": task["version"],
        "live_authorized": bool(task["live_authorized"]),
        "unresolved_attempt_id": task["unresolved_attempt_id"],
        "latest_result": _latest_result_to_doc(task),
        "created_at": D.us_to_iso(task["created_at_us"]),
        "updated_at": D.us_to_iso(task["updated_at_us"]),
    }


def attempt_to_doc(attempt: dict) -> dict:
    return {
        "id": attempt["id"],
        "task_id": attempt["task_id"],
        "asset": attempt["asset"],
        "sequence": attempt["sequence"],
        "outcome": attempt["outcome"],
        "result_category": attempt["result_category"],
        "business_code": attempt["business_code"],
        "reason": attempt["reason"],
        "http_status": attempt["http_status"],
        "tran_id": attempt["tran_id"],
        "requested_amount": attempt["requested_amount"],
        "scheduled_at": D.us_to_iso(attempt["scheduled_at_us"]),
        "dispatched_at": D.us_to_iso(attempt["dispatched_at_us"]),
        "finished_at": D.us_to_iso(attempt["finished_at_us"]),
        "latency_ms": attempt["latency_ms"],
        "effective_gap_us": attempt["effective_gap_us"],
    }


def settings_to_doc(settings: dict) -> dict:
    return {
        "schema_version": D.SCHEMA_VERSION,
        "interval_seconds": settings["interval_seconds"],
        "interval_us": settings["interval_us"],
        "round_robin_cursor": settings["round_robin_cursor"],
        "global_cooldown_until": D.us_to_iso(settings["global_cooldown_until_us"]),
        "version": settings["version"],
        "updated_at": D.us_to_iso(settings["updated_at_us"]),
    }


class BorrowTaskService:
    def __init__(
        self,
        db_path: str,
        *,
        executor: BorrowExecutor | None = None,
        mono_us: Callable[[], int] | None = None,
        wall_us: Callable[[], int] | None = None,
        mode: str = "disabled",
        credentials_present: bool = False,
        ownership: BorrowDbOwnership | None = None,
    ):
        self._store = BorrowTaskStore(db_path)
        self._executor: BorrowExecutor = executor or DisabledBorrowExecutor()
        self._mono_us = mono_us or _real_mono_us
        self._wall_us = wall_us or _real_wall_us
        self._mode = mode
        self._live_mode = mode == "live"
        self._credentials_present = credentials_present
        # Execution-owner sidecar lock (§4.3): acquired before any scheduler can
        # start and held for process lifetime. A non-owner still constructs and
        # serves read/mutation APIs but never dispatches.
        self._ownership = ownership or BorrowDbOwnership(db_path)
        self._is_execution_owner = self._ownership.try_acquire()
        self._last_tick_mono: int | None = None
        self._in_flight_attempt_id: int | None = None
        self._lock = threading.Lock()  # serializes tick() against itself
        self._scheduler = BorrowScheduler(
            self.tick, self._store.get_interval_us, self._mono_us
        )

    # --------------------------------------------------------------- lifecycle

    def close(self) -> None:
        self.stop()
        try:
            self._ownership.close()
        except Exception:
            pass
        self._store.close()

    def start(self) -> None:
        # Only the execution owner starts a scheduler; a non-owner serves APIs
        # but never schedules or dispatches (§4.3 / acceptance 15).
        if not self._is_execution_owner:
            return
        self._scheduler.start()

    def stop(self) -> None:
        self._scheduler.stop()

    @property
    def store(self) -> BorrowTaskStore:
        return self._store

    @property
    def is_execution_owner(self) -> bool:
        return self._is_execution_owner

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def credentials_present(self) -> bool:
        # Non-secret boolean: whether dedicated borrow credentials are configured.
        # Exposed for sanitized startup lifecycle (the value itself is never logged).
        return self._credentials_present

    # ------------------------------------------------------------------ tasks

    def create_task(self, body) -> tuple[int, dict]:
        if not isinstance(body, dict):
            raise D.BorrowError(400, "invalid_json", "request body must be a JSON object")
        D.reject_unknown_keys(body, _CREATE_BODY_KEYS)
        asset = D.validate_asset(body.get("asset"))
        amount = D.validate_amount(body.get("amount_per_attempt"))
        target = D.validate_success_target(body.get("success_target"))
        task_id = str(uuid.uuid4())
        now_us = self._wall_us()
        task = self._store.create_task(task_id, asset, amount, target, now_us)
        return 201, task_to_doc(task)

    def list_tasks(self) -> tuple[int, dict]:
        tasks = [task_to_doc(t) for t in self._store.list_tasks()]
        return 200, {"schema_version": D.SCHEMA_VERSION, "tasks": tasks}

    def post_start(self, task_id: str) -> tuple[int, dict]:
        task = self._store.get_task(task_id)
        if task is None:
            raise D.BorrowError(404, "unknown_task", f"unknown task {task_id}")
        status = task["status"]
        if status == D.STATUS_BORROWING:
            raise D.BorrowError(409, "invalid_transition", "start requires status paused")
        if status == D.STATUS_DELETED:
            raise D.BorrowError(409, "invalid_transition", "cannot start a deleted task")
        now_us = self._wall_us()
        if status == D.STATUS_COMPLETED:
            # Idempotent: completed stays completed; never re-opens eligibility.
            return 200, task_to_doc(task)
        # status == paused: explicit Start marks the task live-authorized (§4.4).
        # Start-at-target completes instead of moving to borrowing so a task
        # already at its count cannot receive an extra POST (§5.4 belt+braces).
        if task["success_count"] >= task["success_target"]:
            updated = self._store.set_task_status(
                task_id, D.STATUS_COMPLETED, now_us, live_authorized=1
            )
        else:
            updated = self._store.set_task_status(
                task_id, D.STATUS_BORROWING, now_us, live_authorized=1
            )
        return 200, task_to_doc(updated)

    def post_pause(self, task_id: str) -> tuple[int, dict]:
        task = self._store.get_task(task_id)
        if task is None:
            raise D.BorrowError(404, "unknown_task", f"unknown task {task_id}")
        if task["status"] != D.STATUS_BORROWING:
            raise D.BorrowError(409, "invalid_transition", "pause requires status borrowing")
        updated = self._store.set_task_status(task_id, D.STATUS_PAUSED, self._wall_us())
        return 200, task_to_doc(updated)

    def post_delete(self, task_id: str) -> tuple[int, dict]:
        task = self._store.get_task(task_id)
        if task is None:
            raise D.BorrowError(404, "unknown_task", f"unknown task {task_id}")
        if task["status"] == D.STATUS_DELETED:
            raise D.BorrowError(409, "invalid_transition", "task already deleted")
        updated = self._store.set_task_status(task_id, D.STATUS_DELETED, self._wall_us())
        return 200, task_to_doc(updated)

    def post_edit(self, task_id: str, body) -> tuple[int, dict]:
        if not isinstance(body, dict):
            raise D.BorrowError(400, "invalid_json", "request body must be a JSON object")
        D.reject_unknown_keys(body, _EDIT_BODY_KEYS)
        task = self._store.get_task(task_id)
        if task is None:
            raise D.BorrowError(404, "unknown_task", f"unknown task {task_id}")
        if task["status"] not in D.RUNNABLE_STATUSES:
            raise D.BorrowError(409, "invalid_transition", "edit requires status borrowing or paused")
        amount = D.validate_amount(body.get("amount_per_attempt"))
        target = D.validate_success_target(body.get("success_target"))
        if target <= task["success_count"]:
            raise D.invalid_field(
                "success_target", "must be strictly greater than current success_count"
            )
        version = body.get("version")
        if isinstance(version, bool) or not isinstance(version, int):
            raise D.invalid_field("version", "must be an integer")
        try:
            updated = self._store.edit_task(task_id, amount, target, version, self._wall_us())
        except VersionConflictError as exc:
            raise D.BorrowError(409, "version_conflict", "edit version does not match current") from exc
        return 200, task_to_doc(updated)

    # ----------------------------------------------------------------- logs

    def get_logs(self, cursor_str, limit_raw) -> tuple[int, dict]:
        limit = self._parse_limit(limit_raw)
        cursor_ts, cursor_id = self._parse_cursor(cursor_str)
        entries, has_more = self._store.list_attempts_page(limit, cursor_ts, cursor_id)
        next_cursor = None
        if has_more and entries:
            last = entries[-1]
            ets = D.effective_ts_us(
                last["finished_at_us"], last["dispatched_at_us"], last["scheduled_at_us"]
            )
            next_cursor = D.encode_cursor(ets, last["id"])
        return 200, {
            "schema_version": D.SCHEMA_VERSION,
            "entries": [attempt_to_doc(e) for e in entries],
            "next_cursor": next_cursor,
        }

    def _parse_limit(self, limit_raw) -> int:
        if limit_raw is None:
            return D.LIMIT_DEFAULT
        try:
            value = int(str(limit_raw).strip())
        except (TypeError, ValueError) as exc:
            raise D.BorrowError(400, "invalid_limit", "limit must be an integer") from exc
        return D.validate_limit(value)

    def _parse_cursor(self, cursor_str):
        if cursor_str is None or cursor_str == "":
            return None, None
        decoded = D.decode_cursor(cursor_str)
        if decoded is None:
            raise D.BorrowError(400, "invalid_cursor", "cursor is not a valid opaque token")
        return decoded

    # --------------------------------------------------------------- settings

    def get_settings(self) -> tuple[int, dict]:
        return 200, settings_to_doc(self._store.get_settings())

    def put_settings(self, body) -> tuple[int, dict]:
        if not isinstance(body, dict):
            raise D.BorrowError(400, "invalid_json", "request body must be a JSON object")
        D.reject_unknown_keys(body, _SETTINGS_BODY_KEYS)
        if "interval_seconds" not in body:
            raise D.invalid_field("interval_seconds", "is required")
        seconds_str, interval_us = D.parse_interval_seconds(body["interval_seconds"])
        updated = self._store.update_settings(seconds_str, interval_us, self._wall_us())
        return 200, settings_to_doc(updated)

    # --------------------------------------------------- execution control (C)

    def get_execution_status(self) -> tuple[int, dict]:
        """Read-only ``borrow-execution/v1`` projection (§3.3)."""
        settings = self._store.get_settings()
        now_us = self._wall_us()
        execution_enabled = bool(settings["execution_enabled"])
        cooldown_until_us = settings["global_cooldown_until_us"]
        in_cooldown = cooldown_until_us is not None and cooldown_until_us > now_us
        rate_blocked = in_cooldown or bool(settings["requires_rearm"])
        # can_execute deliberately excludes the transient cooldown so the badge
        # does not flicker during ordinary 429 handling (§3.3).
        can_execute = (
            self._live_mode
            and execution_enabled
            and self._credentials_present
            and self._is_execution_owner
        )
        if not self._live_mode:
            block_reason = D.BLOCK_EXECUTOR_DISABLED
        elif not self._credentials_present:
            block_reason = D.BLOCK_BORROW_CREDENTIALS_MISSING
        elif not self._is_execution_owner:
            block_reason = D.BLOCK_NOT_EXECUTION_OWNER
        elif not execution_enabled:
            block_reason = D.BLOCK_GLOBALLY_STOPPED
        elif rate_blocked:
            block_reason = D.BLOCK_RATE_LIMITED
        else:
            block_reason = None
        return 200, {
            "schema_version": D.EXECUTION_SCHEMA_VERSION,
            "mode": self._mode,
            "execution_enabled": execution_enabled,
            "can_execute": can_execute,
            "block_reason": block_reason,
            "in_flight_attempt_id": self._in_flight_attempt_id,
            "global_cooldown_until": D.us_to_iso(cooldown_until_us),
            "live_authorized_task_count": self._store.count_live_authorized_tasks(),
            "updated_at": D.us_to_iso(now_us),
        }

    def post_execution_start(self) -> tuple[int, dict]:
        # Idempotent durable Start; also re-arms after a 418 ban (§5.1).
        self._store.set_execution_enabled(True, self._wall_us())
        return self.get_execution_status()

    def post_execution_stop(self) -> tuple[int, dict]:
        # Idempotent durable Stop: blocks new POSTs, never rewrites an in-flight
        # attempt. Reconciliation GETs may still continue once not rate-limited.
        self._store.set_execution_enabled(False, self._wall_us())
        return self.get_execution_status()

    # --------------------------------------------------------------- scheduler

    def tick(self) -> bool:
        """Run one due-tick check; dispatch at most one attempt, then reconcile.

        Returns whether an attempt was dispatched. Tests drive this directly
        with injected clocks; the scheduler thread calls it on the cadence.
        ``_last_tick_mono`` advances to ``now`` (never by accumulated intervals)
        so missed time is never replayed as a burst of dispatches (§9-6).
        """
        with self._lock:
            now = self._mono_us()
            interval = self._store.get_interval_us()
            if self._last_tick_mono is None:
                self._last_tick_mono = now
                dispatched = self._dispatch_one(self._wall_us())
            elif now < self._last_tick_mono + interval:
                dispatched = False
            else:
                self._last_tick_mono = now
                dispatched = self._dispatch_one(self._wall_us())
            self._reconcile_pass(self._wall_us())
            return dispatched

    def _dispatch_one(self, scheduled_us: int) -> bool:
        # A non-owner process never dispatches even on a forced tick (§4.3).
        if not self._is_execution_owner:
            return False
        # Dedicated-credentials gate (§4.2): live mode never dispatches without
        # credentials, so no signed POST can leave the process with empty keys.
        if self._live_mode and not self._credentials_present:
            return False
        settings = self._store.get_settings()
        cooldown = settings["global_cooldown_until_us"]
        if cooldown is not None and cooldown > scheduled_us:
            return False
        eligible = self._store.list_eligible_tasks()
        chosen = select_next_task(eligible, settings["round_robin_cursor"])
        if chosen is None:
            return False
        dispatched_us = self._wall_us()
        # Transaction 1: atomic conditional pending insert + advance cursor +
        # set the in-flight marker (live gates apply only in live mode).
        attempt = self._store.insert_pending_attempt(
            chosen["id"],
            chosen["asset"],
            chosen["amount_per_attempt"],
            scheduled_us,
            dispatched_us,
            chosen["id"],
            live_gates=self._live_mode,
        )
        if attempt is None:
            return False  # a gate failed atomically — zero row and zero POST
        self._in_flight_attempt_id = attempt["id"]
        try:
            # Executor invoked with NO store lock or transaction held (§4.5).
            result = self._executor.execute(chosen, attempt)
        except Exception as exc:
            # Containment (§5.2): an executor exception maps to unknown, never
            # re-raised, so the scheduler thread cannot be killed by it.
            result = ExecutorResult(
                result_category=D.RESULT_UNKNOWN,
                reason=f"executor_exception:{type(exc).__name__}",
            )
        finally:
            self._in_flight_attempt_id = None
        try:
            # Transaction 2: resolve the attempt + apply task/settings effects.
            self._store.resolve_attempt(attempt["id"], result, self._wall_us())
        except Exception:
            # Containment (§5.2): a store/projection exception must not kill the
            # scheduler; the attempt stays pending and its task stays blocked.
            pass
        return True

    def _reconcile_pass(self, now_us: int) -> None:
        """Prove success for due unresolved unknown attempts (§5.3).

        A rate-limit cooldown blocks ALL signed borrow-client traffic including
        reconciliation GETs, so the pass is skipped while cooling down or while
        a 418 ban awaits manual re-arm.
        """
        settings = self._store.get_settings()
        cooldown = settings["global_cooldown_until_us"]
        if cooldown is not None and cooldown > now_us:
            return
        if settings["requires_rearm"]:
            return
        due = self._store.list_due_reconciliations(now_us)
        for attempt in due:
            task = self._store.get_task(attempt["task_id"])
            if task is None:
                continue
            try:
                outcome = self._executor.reconcile(task, attempt)
            except Exception:
                # Containment: a reconcile exception must not kill the pass.
                outcome = None
            if outcome is None:
                break  # executor cannot reconcile (disabled / non-live)
            if outcome.rate_limited:
                if outcome.retry_after_seconds is not None:
                    self._store.set_rate_cooldown(outcome.retry_after_seconds, now_us)
                if outcome.requires_rearm:
                    # A reconciliation GET can observe a 418 ban; persist the
                    # manual-rearm requirement so execution does not auto-resume
                    # after the 300s local cooldown (§5.1).
                    self._store.set_requires_rearm(now_us)
                break  # stop the pass while rate-limited
            if outcome.matched:
                # Cross-task attribution gate (§5.3 / risk §11): only credit the
                # attempt when the candidate is unambiguously its own — never
                # attribute a loan record another task/attempt could also match.
                if self._store.attribution_is_unique(
                    attempt["id"],
                    attempt["task_id"],
                    attempt["asset"],
                    attempt["requested_amount"],
                    outcome.tran_id,
                ):
                    self._store.resolve_reconciliation_success(
                        attempt["id"], outcome.tran_id, now_us
                    )
                else:
                    self._store.advance_reconciliation(attempt["id"], now_us)
            else:
                self._store.advance_reconciliation(attempt["id"], now_us)

    # ------------------------------------------------------------- test seam

    def clear_unresolved(self, task_id: str) -> None:
        """Python-level (not HTTP) seam to clear an unresolved marker.

        Reconciliation of a genuinely unknown outcome has no HTTP unblock route;
        a blocked task's only operator exit is delete. Tests use this to restore
        eligibility for deterministic scheduling scenarios.
        """
        try:
            self._store.clear_unresolved(task_id, self._wall_us())
        except UnknownTaskError as exc:
            raise D.BorrowError(404, "unknown_task", f"unknown task {task_id}") from exc
