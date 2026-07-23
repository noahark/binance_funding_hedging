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


def _real_mono_us() -> int:
    return int(time.monotonic() * 1_000_000)


def _real_wall_us() -> int:
    return int(time.time() * 1_000_000)


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

    def get_logs(self, cursor_str, limit_raw) -> tuple[int, dict]:
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
        return 200, {
            "logs": [log_to_doc(r) for r in rows],
            "attempts": [attempt_to_doc(a, s, p) for (a, s, p) in attempt_rows],
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

    def _enter_rate_limit_cooldown(self, now_mono: int) -> None:
        self._rate_limited_until_mono = now_mono + RATE_LIMIT_COOLDOWN_US

    # --------------------------------------------------------------- scheduler

    def tick(self) -> bool:
        """Run one due-tick check; dispatch one pair for EVERY eligible task.

        The automatic scheduler respects the global Start gate (§9) and the
        shared exchange rate-limit cooldown; explicit ``fill-once``/``fill-all``
        bypass the gate because they are operator manual triggers of the record
        transport and never POST. ``_last_tick_mono`` advances to ``now`` so
        missed time is never replayed as a burst.

        Per-task async cadence (R4-2 / PRD §6.3 / 05-cadence-resolution): each
        eligible running task is dispatched on its OWN worker so a slow live
        preflight/POST/query on one card cannot block another card's same-second
        pair submission. Both legs still dispatch concurrently within one pair
        (the live executor joins its own two-leg threads). The shared Start gate
        and exchange rate-limit cooldown checked above remain the ONLY global
        cadence controls — there is no product-wide one-pair-per-second lock.
        Workers are joined before returning so a task still issues one pair per
        second (no same-task re-entry across ticks) and one card's failure is
        contained (never stops the others). Durable-before-send and the
        timeout→client-ID query (no resend) rule are unchanged.
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
            if self._in_rate_limit_cooldown(now):
                return False
            eligible = self._store.list_eligible_tasks()
            if not eligible:
                return False
            now_us = self._wall_us()
            self._dispatch_eligible_concurrently(eligible, now_us)
            # Reconcile querying legs left by earlier live dispatches (no resend).
            try:
                self._reconcile_pending(now_us)
            except Exception:
                pass
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

    def _fresh_preflight_ok(self, task: dict) -> bool:
        """A live send requires a fresh factual preflight immediately before send
        (breakdown §4.3). Any read gap or rejection fails the pair closed (no
        POST this tick; the scheduler retries next second)."""
        snapshot = self._preflight.get_snapshot(task["coin"])
        if snapshot is None:
            return False
        preflight = D.compute_preflight(
            snapshot,
            task["coin"],
            task["direction"],
            D.Decimal(task["single_amount"]),
            task["target_n"],
        )
        return preflight.rejection is None and preflight.balance_ok is not False

    def _dispatch_one_for_task(self, task: dict, now_us: int) -> dict:
        """Durable-before-send: persist the immutable attempt + both client IDs +
        sanitized request shapes in ONE transaction BEFORE any executor call
        (ADR-2). The executor is then invoked with no store transaction held; the
        outcome is resolved in a second short transaction.

        Live path (real POST) is taken only when a live executor is present AND
        the Start gate is on AND a fresh preflight passes — otherwise the
        record/disabled simulated path runs (no network POST).
        """
        attempt_uuid = uuid.uuid4().hex
        spot_cid, perp_cid = _client_order_ids(attempt_uuid)
        actions = D.direction_to_leg_actions(
            task["direction"], task["position_side_mode"] or D.POS_MODE_BOTH
        )
        q_common = D.Decimal(task["q_common"]) if task["q_common"] else None
        send_qty = q_common if q_common is not None else D.Decimal(task["single_amount"])
        spot_shape = build_spot_order_params(task["coin"], actions, send_qty, spot_cid)
        perp_shape = build_perp_order_params(task["coin"], actions, send_qty, perp_cid)
        q_common_str = D.fmt_decimal(q_common) if q_common is not None else task["single_amount"]
        attempt = self._store.prepare_attempt(
            task["id"],
            attempt_uuid,
            task["direction"],
            q_common_str,
            task["position_side_mode"],
            task["preflight_snapshot"] or {},
            spot_cid,
            spot_shape,
            perp_cid,
            perp_shape,
            now_us,
        )
        if attempt is None:
            # Task is no longer eligible (paused/done/deleted) — no POST.
            return self._store.get_task(task["id"]) or task
        ctx = AttemptContext(
            attempt_id=attempt_uuid,
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
        if (
            self._live_dispatch_capable()
            and self.is_start_gate_on()
            and self._fresh_preflight_ok(task)
        ):
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
        if getattr(dispatch, "rate_limited", False):
            self._enter_rate_limit_cooldown(self._mono_us())
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
        category off ``order_id`` presence via :func:`domain.classify_attempt`."""
        spot_leg = {
            "status": D.LEG_REJECTED if spot.dispatch_state == D.LEG_TERMINAL_RECORDED
            else (spot.exchange_status or D.LEG_NEW),
            "filled_qty": spot.executed_qty,
            "avg_price": spot.avg_price,
            "order_id": spot.order_id,
            "client_order_id": None,
        }
        perp_leg = {
            "status": D.LEG_REJECTED if perp.dispatch_state == D.LEG_TERMINAL_RECORDED
            else (perp.exchange_status or D.LEG_NEW),
            "filled_qty": perp.executed_qty,
            "avg_price": perp.avg_price,
            "order_id": perp.order_id,
            "client_order_id": None,
        }
        category = D.classify_attempt(spot_leg, perp_leg)
        exposure = (
            D.build_leg_exposure(spot_leg, perp_leg, 0)
            if category == D.ATTEMPT_SINGLE_LEG_EXPOSURE
            else None
        )
        return AttemptOutcome(
            attempt_id=attempt_uuid,
            category=category,
            spot=spot_leg,
            perp=perp_leg,
            record_payload=record_payload,
            exposure=exposure,
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
        accepted leg reaches FILLED. NEW/PARTIALLY_FILLED keep querying."""
        if verdict.dispatch_state == D.LEG_TERMINAL_RECORDED:
            return True
        if verdict.dispatch_state == D.LEG_ACCEPTED_OR_QUERYING:
            return verdict.exchange_status in (
                D.LEG_FILLED,
                D.LEG_REJECTED,
                D.LEG_EXPIRED,
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
