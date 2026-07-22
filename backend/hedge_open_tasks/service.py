"""Hedge-open task service — HTTP-facing orchestration over store + executor.

The service is the single hedge-open authority. It owns the store, the executor,
the preflight provider, the scheduler thread and the durable global Start gate,
and exposes the local same-origin API methods consumed by
``backend/app/server.py``. Handlers delegate here only; they never touch SQL or
the executor directly (mirror of borrow_tasks §3.10).

Round-1 safety posture (ADR-5): the default executor is the dry-run record
transport (no network POST); a real POST is reachable only under
``APP_HEDGE_EXECUTOR=live`` AND the durable Start gate AND a passing preflight,
and the live executor is NOT wired this round. The scheduler's automatic tick
respects the Start gate; explicit ``fill-once``/``fill-all`` are operator manual
triggers of the record transport and are not Start-gated (they never POST).
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from typing import Callable, Protocol

from . import domain as D
from .executor import (
    AttemptContext,
    AttemptOutcome,
    DisabledHedgeExecutor,
    HedgeExecutor,
    RecordTransportExecutor,
)
from .scheduler import HedgeOpenScheduler
from .store import HedgeOpenStore, UnknownTaskError


_CREATE_BODY_KEYS = ("coin", "direction", "mode", "single_amount", "target_n")


def _real_mono_us() -> int:
    return int(time.monotonic() * 1_000_000)


def _real_wall_us() -> int:
    return int(time.time() * 1_000_000)


class PreflightProvider(Protocol):
    """Read-only preflight data source (10-design §5). Injected; never called
    by a network path this round. Returns ``None`` when no snapshot is available
    (the dry-run default), in which case tasks are created without a resolved
    ``q_common`` to exercise the record transport.
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
        "leg_exposure": task["leg_exposure"],
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


class HedgeOpenTaskService:
    def __init__(
        self,
        db_path: str,
        *,
        executor: HedgeExecutor | None = None,
        preflight_provider: PreflightProvider | None = None,
        mode: str = "disabled",
        mono_us: Callable[[], int] | None = None,
        wall_us: Callable[[], int] | None = None,
    ):
        self._store = HedgeOpenStore(db_path, executor_mode_snapshot=mode)
        # Round-1 default is the dry-run record transport (ADR-5 / 10-design §6):
        # it records the would-send params and returns a simulated outcome, and
        # performs NO network POST. A real POST is reachable only under
        # APP_HEDGE_EXECUTOR=live AND the Start gate AND a live executor, and the
        # live executor is NOT wired this round, so a real POST is unreachable.
        # DisabledHedgeExecutor is an injectable zero-record alternative.
        self._executor: HedgeExecutor = executor or RecordTransportExecutor()
        self._preflight: PreflightProvider = preflight_provider or DisabledPreflightProvider()
        self._mode = mode
        self._live_mode = mode == "live"
        self._mono_us = mono_us or _real_mono_us
        self._wall_us = wall_us or _real_wall_us
        self._last_tick_mono: int | None = None
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
        if status == D.STATUS_EXPOSURE_ALERT:
            raise D.HedgeError(409, "invalid_state", "clear leg_exposure before starting")
        if status == D.STATUS_DONE:
            return 200, task_to_doc(task)  # idempotent: done stays done
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
        now_us = self._wall_us()
        # Bound the loop by the target so a misconfigured seed cannot spin. The
        # loop continues only while the task is still ``running`` and below its
        # target; a single-leg exposure, a >3-fail termination (-> paused), or
        # reaching ``done`` stops dispatch immediately.
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
        if status == D.STATUS_EXPOSURE_ALERT:
            raise D.HedgeError(409, "invalid_state", "task has a single-leg exposure")
        if status == D.STATUS_DONE:
            raise D.HedgeError(409, "invalid_state", "task already done")

    # ----------------------------------------------------------------- reads

    def get_settings(self) -> tuple[int, dict]:
        return 200, settings_to_doc(self._store.get_settings(), self._mode)

    def get_logs(self, cursor_str, limit_raw) -> tuple[int, dict]:
        limit = self._parse_limit(limit_raw)
        cursor_ts, cursor_id = self._parse_cursor(cursor_str)
        rows, has_more = self._store.list_logs_page(limit, cursor_ts, cursor_id)
        next_cursor = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = D.encode_cursor(last["ts_us"], last["id"])
        return 200, {
            "logs": [log_to_doc(r) for r in rows],
            "next_cursor": next_cursor,
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

    # ------------------------------------------------------------- start gate

    def set_start_gate(self, enabled: bool) -> tuple[int, dict]:
        """Python-level seam to toggle the durable global Start gate (§9).

        Round 1 does not expose an HTTP toggle (settings are read-only per the
        frozen contract); tests and the operator use this seam. Live dispatch
        requires the gate on AND ``APP_HEDGE_EXECUTOR=live`` AND a live executor.
        """
        self._store.set_start_gate(enabled, self._wall_us())
        return self.get_settings()

    # --------------------------------------------------------------- scheduler

    def tick(self) -> bool:
        """Run one due-tick check; dispatch at most one attempt if Start is on.

        The automatic scheduler respects the global Start gate (§9); explicit
        ``fill-once``/``fill-all`` bypass it because they are operator manual
        triggers of the record transport and never POST. ``_last_tick_mono``
        advances to ``now`` so missed time is never replayed as a burst.
        """
        with self._lock:
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
            self._dispatch_one_for_task(eligible[0], self._wall_us())
            return True

    def _dispatch_one_for_task(self, task: dict, now_us: int) -> dict:
        """Build one attempt, invoke the executor, persist fill + outcome.

        The executor is invoked with no store transaction held; the attempt
        outcome is applied and the fill row + record-transport log are written
        after. Containment: an executor/store exception maps to a failed attempt
        (recorded) rather than killing the scheduler.
        """
        attempt_id = uuid.uuid4().hex[:16]
        q_common = D.Decimal(task["q_common"]) if task["q_common"] else None
        ctx = AttemptContext(
            attempt_id=attempt_id,
            task_id=task["id"],
            coin=task["coin"],
            direction=task["direction"],
            single_amount=D.Decimal(task["single_amount"]),
            q_common=q_common,
            position_side_mode=task["position_side_mode"],
            preflight_snapshot=task["preflight_snapshot"] or {},
            filter_versions=task["preflight_snapshot"] or {},
            target_n=task["target_n"],
            ts_us=now_us,
        )
        try:
            outcome = self._executor.execute(ctx)
        except Exception as exc:
            outcome = self._failed_outcome(ctx, f"executor_exception:{type(exc).__name__}")
        try:
            self._store.insert_fill(task["id"], attempt_id, outcome, now_us)
        except Exception:
            pass  # containment: a fill-write failure must not kill dispatch
        try:
            task = self._store.apply_attempt_outcome(task["id"], outcome, now_us)
        except UnknownTaskError:
            pass
        except Exception:
            pass  # containment: an outcome-apply failure must not kill dispatch
        return task

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
