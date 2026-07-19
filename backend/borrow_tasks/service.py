"""Borrow task service — HTTP-facing orchestration over the store + executor.

The service is the single borrow authority for A+B. It owns the store, the
executor and the scheduler thread, and exposes the local same-origin API
methods consumed by ``backend/app/server.py``. Handlers delegate here only;
they never touch SQL or the executor directly (breakdown §3.10).

Dispatch invariant (amendment §2): the pending attempt is persisted in one
short transaction, the executor is invoked with no store lock or transaction
held, and the attempt is resolved in a second short transaction. A+B disabled
execution is synchronous only because it performs no I/O; it is not a
commitment to a synchronous future-C adapter.
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Callable

from . import domain as D
from .executor import BorrowExecutor, DisabledBorrowExecutor
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
    ):
        self._store = BorrowTaskStore(db_path)
        self._executor: BorrowExecutor = executor or DisabledBorrowExecutor()
        self._mono_us = mono_us or _real_mono_us
        self._wall_us = wall_us or _real_wall_us
        self._last_tick_mono: int | None = None
        self._lock = threading.Lock()  # serializes tick() against itself
        self._scheduler = BorrowScheduler(
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
    def store(self) -> BorrowTaskStore:
        return self._store

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
        if task["status"] != D.STATUS_PAUSED:
            raise D.BorrowError(409, "invalid_transition", "start requires status paused")
        updated = self._store.set_task_status(task_id, D.STATUS_BORROWING, self._wall_us())
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

    # --------------------------------------------------------------- scheduler

    def tick(self) -> bool:
        """Run one due-tick check; dispatch at most one attempt.

        Returns whether an attempt was dispatched. Tests drive this directly
        with injected clocks; the scheduler thread calls it on the cadence.
        """
        with self._lock:
            now = self._mono_us()
            interval = self._store.get_interval_us()
            if self._last_tick_mono is None:
                self._last_tick_mono = now
                return self._dispatch_one(self._wall_us())
            if now < self._last_tick_mono + interval:
                return False
            self._last_tick_mono = self._last_tick_mono + interval
            return self._dispatch_one(self._wall_us())

    def _dispatch_one(self, scheduled_us: int) -> bool:
        settings = self._store.get_settings()
        cooldown = settings["global_cooldown_until_us"]
        if cooldown is not None and cooldown > scheduled_us:
            return False
        eligible = self._store.list_eligible_tasks()
        chosen = select_next_task(eligible, settings["round_robin_cursor"])
        if chosen is None:
            return False
        dispatched_us = self._wall_us()
        # Transaction 1: persist pending attempt + advance cursor (no executor).
        attempt = self._store.insert_pending_attempt(
            chosen["id"],
            chosen["asset"],
            chosen["amount_per_attempt"],
            scheduled_us,
            dispatched_us,
            chosen["id"],
        )
        # Executor invoked with NO store lock or transaction held (amendment §2).
        result = self._executor.execute(chosen, attempt)
        # Transaction 2: resolve the attempt + apply task/settings effects.
        self._store.resolve_attempt(attempt["id"], result, self._wall_us())
        return True

    # ------------------------------------------------------------- test seam

    def clear_unresolved(self, task_id: str) -> None:
        """Python-level (not HTTP) seam to clear an unresolved marker.

        Reconciliation of a genuinely unknown outcome is Boundary C; A+B ships
        no HTTP unblock endpoint. Tests use this to restore eligibility.
        """
        try:
            self._store.clear_unresolved(task_id, self._wall_us())
        except UnknownTaskError as exc:
            raise D.BorrowError(404, "unknown_task", f"unknown task {task_id}") from exc
