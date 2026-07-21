"""SQLite-backed durable borrow-task store (breakdown §3.6 / §3.8 / §3.10 / §4.5).

A modular-monolith local store. One connection guarded by a single lock is the
frozen concurrency answer (breakdown §6.2): every public method takes the lock
and write groups use a short ``with self._conn:`` transaction. The executor is
never invoked while a transaction or the lock is held (the service inserts the
pending attempt in one short transaction, releases it, invokes the executor,
then resolves in a second short transaction — amendment §2 / Boundary C §4.5).

Internal time is integer microseconds since epoch (breakdown §3.10). The store
holds no JSON/HTTP/executor concerns; the service serializes rows to documents.

No network imports: only :mod:`sqlite3`, :mod:`threading`, :mod:`time` and
:mod:`decimal` (the latter for exact-amount cross-task attribution only).
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from decimal import Decimal, InvalidOperation
from typing import Any

from . import domain as D
from .executor import ExecutorResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS borrow_task (
    id                          TEXT PRIMARY KEY,
    asset                       TEXT NOT NULL,
    amount_per_attempt          TEXT NOT NULL,
    success_target              INTEGER NOT NULL,
    success_count               INTEGER NOT NULL DEFAULT 0,
    status                      TEXT NOT NULL,
    version                     INTEGER NOT NULL DEFAULT 1,
    creation_seq                INTEGER NOT NULL,
    created_at_us               INTEGER NOT NULL,
    updated_at_us               INTEGER NOT NULL,
    live_authorized             INTEGER NOT NULL DEFAULT 0,
    unresolved_attempt_id       INTEGER,
    latest_result_category      TEXT,
    latest_result_business_code TEXT,
    latest_result_reason        TEXT,
    latest_result_tran_id       TEXT,
    latest_result_finished_at_us INTEGER
);
CREATE TABLE IF NOT EXISTS borrow_attempt (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id           TEXT NOT NULL,
    asset             TEXT NOT NULL,
    sequence          INTEGER NOT NULL,
    outcome           TEXT NOT NULL,
    result_category   TEXT,
    business_code     TEXT,
    reason            TEXT,
    http_status       INTEGER,
    tran_id           TEXT,
    requested_amount  TEXT NOT NULL,
    scheduled_at_us   INTEGER NOT NULL,
    dispatched_at_us  INTEGER,
    finished_at_us    INTEGER,
    latency_ms        INTEGER,
    effective_gap_us  INTEGER,
    reconcile_next_at_us  INTEGER,
    reconcile_step        INTEGER NOT NULL DEFAULT 0,
    reconcile_exhausted   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS borrow_settings (
    id                       INTEGER PRIMARY KEY CHECK (id = 1),
    interval_seconds         TEXT NOT NULL,
    interval_us              INTEGER NOT NULL,
    round_robin_cursor       TEXT,
    global_cooldown_until_us INTEGER,
    execution_enabled        INTEGER NOT NULL DEFAULT 0,
    requires_rearm           INTEGER NOT NULL DEFAULT 0,
    version                  INTEGER NOT NULL DEFAULT 1,
    updated_at_us            INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_borrow_attempt_effective
    ON borrow_attempt (finished_at_us DESC, dispatched_at_us DESC, scheduled_at_us DESC, id DESC);
"""


class StoreError(Exception):
    """Base store-level error."""


class UnknownTaskError(StoreError):
    pass


class VersionConflictError(StoreError):
    pass


def _resolve_status(current_status: str, new_count: int, target: int) -> str:
    """Apply the §5.4 resolve matrix to a success result.

    ``deleted`` always stays ``deleted``; ``completed`` always stays
    ``completed``; reaching the target completes a runnable task; otherwise the
    current status is preserved (borrowing stays borrowing, paused stays paused).
    """
    if current_status == D.STATUS_DELETED:
        return D.STATUS_DELETED
    if current_status == D.STATUS_COMPLETED:
        return D.STATUS_COMPLETED
    if new_count >= target:
        return D.STATUS_COMPLETED
    return current_status


def _row_to_task(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "asset": row["asset"],
        "amount_per_attempt": row["amount_per_attempt"],
        "success_target": row["success_target"],
        "success_count": row["success_count"],
        "status": row["status"],
        "version": row["version"],
        "creation_seq": row["creation_seq"],
        "created_at_us": row["created_at_us"],
        "updated_at_us": row["updated_at_us"],
        "live_authorized": row["live_authorized"],
        "unresolved_attempt_id": row["unresolved_attempt_id"],
        "latest_result_category": row["latest_result_category"],
        "latest_result_business_code": row["latest_result_business_code"],
        "latest_result_reason": row["latest_result_reason"],
        "latest_result_tran_id": row["latest_result_tran_id"],
        "latest_result_finished_at_us": row["latest_result_finished_at_us"],
    }


def _row_to_attempt(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "asset": row["asset"],
        "sequence": row["sequence"],
        "outcome": row["outcome"],
        "result_category": row["result_category"],
        "business_code": row["business_code"],
        "reason": row["reason"],
        "http_status": row["http_status"],
        "tran_id": row["tran_id"],
        "requested_amount": row["requested_amount"],
        "scheduled_at_us": row["scheduled_at_us"],
        "dispatched_at_us": row["dispatched_at_us"],
        "finished_at_us": row["finished_at_us"],
        "latency_ms": row["latency_ms"],
        "effective_gap_us": row["effective_gap_us"],
        "reconcile_next_at_us": row["reconcile_next_at_us"],
        "reconcile_step": row["reconcile_step"],
        "reconcile_exhausted": row["reconcile_exhausted"],
    }


class BorrowTaskStore:
    def __init__(self, db_path: str):
        self._lock = threading.RLock()
        # Ensure the parent directory exists (the default path lives under the
        # gitignored ``data/`` dir, which is not created at checkout time).
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        with self._lock, self._conn:
            self._migrate()
            cur = self._conn.execute(
                "SELECT COUNT(*) FROM borrow_settings WHERE id = 1"
            )
            if cur.fetchone()[0] == 0:
                self._conn.execute(
                    "INSERT INTO borrow_settings"
                    " (id, interval_seconds, interval_us, round_robin_cursor,"
                    "  global_cooldown_until_us, execution_enabled, requires_rearm,"
                    "  version, updated_at_us)"
                    " VALUES (1, ?, ?, NULL, NULL, 0, 0, 1, ?)",
                    (
                        D.DEFAULT_INTERVAL_SECONDS,
                        D.DEFAULT_INTERVAL_US,
                        int(time.time() * 1_000_000),
                    ),
                )
            # Fail-closed recovery (breakdown §3.8): a pending attempt orphaned
            # by a crash blocks its task until reconciliation (Boundary C). The
            # pending-orphan marker is added, but an already-persisted marker —
            # e.g. a resolved ``unknown`` outcome — is preserved (COALESCE keeps
            # the existing value when there is no pending row), so the
            # unknown-outcome block holds across close/reopen (acceptance 4 /
            # §6.1-1 invariant-across-restart).
            self._conn.execute(
                "UPDATE borrow_task SET unresolved_attempt_id = COALESCE(("
                "  SELECT MAX(a.id) FROM borrow_attempt a"
                "  WHERE a.task_id = borrow_task.id AND a.outcome = ?),"
                " unresolved_attempt_id)",
                (D.OUTCOME_PENDING,),
            )

    def _migrate(self) -> None:
        """Idempotent PRAGMA user_version schema gate (Boundary C §4.4).

        v1 adds the Boundary C columns and quarantines pre-C tasks once:
        every pre-C ``borrowing`` task is transitioned to ``paused`` (counts and
        logs preserved) and left ``live_authorized=0`` so enabling live mode
        cannot execute old disabled-stage tasks silently. Re-running is a no-op
        (user_version already 1). Per-column ALTER guards make it safe even if a
        column partially exists.
        """
        user_version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if user_version >= 1:
            return
        task_cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(borrow_task)")}
        if "live_authorized" not in task_cols:
            self._conn.execute(
                "ALTER TABLE borrow_task ADD COLUMN live_authorized INTEGER NOT NULL DEFAULT 0"
            )
        settings_cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(borrow_settings)")}
        if "execution_enabled" not in settings_cols:
            self._conn.execute(
                "ALTER TABLE borrow_settings ADD COLUMN execution_enabled INTEGER NOT NULL DEFAULT 0"
            )
        if "requires_rearm" not in settings_cols:
            self._conn.execute(
                "ALTER TABLE borrow_settings ADD COLUMN requires_rearm INTEGER NOT NULL DEFAULT 0"
            )
        attempt_cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(borrow_attempt)")}
        if "reconcile_next_at_us" not in attempt_cols:
            self._conn.execute("ALTER TABLE borrow_attempt ADD COLUMN reconcile_next_at_us INTEGER")
        if "reconcile_step" not in attempt_cols:
            self._conn.execute(
                "ALTER TABLE borrow_attempt ADD COLUMN reconcile_step INTEGER NOT NULL DEFAULT 0"
            )
        if "reconcile_exhausted" not in attempt_cols:
            self._conn.execute(
                "ALTER TABLE borrow_attempt ADD COLUMN reconcile_exhausted INTEGER NOT NULL DEFAULT 0"
            )
        # One-time quarantine of pre-C borrowing tasks (counts/logs preserved).
        self._conn.execute(
            "UPDATE borrow_task SET status = ? WHERE status = ?",
            (D.STATUS_PAUSED, D.STATUS_BORROWING),
        )
        self._conn.execute("PRAGMA user_version = 1")

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------ tasks

    def create_task(
        self, task_id: str, asset: str, amount: str, target: int, now_us: int
    ) -> dict:
        # New post-C tasks are live-authorized by their Confirm action (§4.4):
        # only pre-C rows (via migration) and not-yet-started migrated tasks
        # carry live_authorized=0.
        with self._lock, self._conn:
            seq_row = self._conn.execute(
                "SELECT COALESCE(MAX(creation_seq), 0) + 1 FROM borrow_task"
            ).fetchone()
            creation_seq = seq_row[0]
            self._conn.execute(
                "INSERT INTO borrow_task"
                " (id, asset, amount_per_attempt, success_target, success_count,"
                "  status, version, creation_seq, created_at_us, updated_at_us,"
                "  live_authorized, unresolved_attempt_id, latest_result_category,"
                "  latest_result_business_code, latest_result_reason,"
                "  latest_result_tran_id, latest_result_finished_at_us)"
                " VALUES (?, ?, ?, ?, 0, ?, 1, ?, ?, ?, 1, NULL, NULL, NULL, NULL, NULL, NULL)",
                (
                    task_id,
                    asset,
                    amount,
                    target,
                    D.STATUS_BORROWING,
                    creation_seq,
                    now_us,
                    now_us,
                ),
            )
            row = self._conn.execute(
                "SELECT * FROM borrow_task WHERE id = ?", (task_id,)
            ).fetchone()
            return _row_to_task(row)

    def get_task(self, task_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM borrow_task WHERE id = ?", (task_id,)
            ).fetchone()
            return _row_to_task(row) if row is not None else None

    def list_tasks(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM borrow_task ORDER BY creation_seq ASC, id ASC"
            ).fetchall()
            return [_row_to_task(r) for r in rows]

    def list_eligible_tasks(self) -> list[dict]:
        """Tasks selectable by the round-robin scheduler (breakdown §3.8 / §4.6).

        Eligibility is fail-closed: ``borrowing`` with no unresolved attempt,
        live-authorized, and still below its success target.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM borrow_task"
                " WHERE status = ? AND unresolved_attempt_id IS NULL"
                "   AND live_authorized = 1 AND success_count < success_target"
                " ORDER BY creation_seq ASC, id ASC",
                (D.STATUS_BORROWING,),
            ).fetchall()
            return [_row_to_task(r) for r in rows]

    def set_task_status(
        self, task_id: str, status: str, now_us: int, *, live_authorized: int | None = None
    ) -> dict:
        with self._lock, self._conn:
            if live_authorized is None:
                cur = self._conn.execute(
                    "UPDATE borrow_task SET status = ?, version = version + 1,"
                    " updated_at_us = ? WHERE id = ?",
                    (status, now_us, task_id),
                )
            else:
                cur = self._conn.execute(
                    "UPDATE borrow_task SET status = ?, live_authorized = ?,"
                    " version = version + 1, updated_at_us = ? WHERE id = ?",
                    (status, live_authorized, now_us, task_id),
                )
            if cur.rowcount == 0:
                raise UnknownTaskError(task_id)
            row = self._conn.execute(
                "SELECT * FROM borrow_task WHERE id = ?", (task_id,)
            ).fetchone()
            return _row_to_task(row)

    def edit_task(
        self,
        task_id: str,
        amount: str,
        target: int,
        expected_version: int,
        now_us: int,
    ) -> dict:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE borrow_task SET amount_per_attempt = ?, success_target = ?,"
                " version = version + 1, updated_at_us = ?"
                " WHERE id = ? AND version = ?",
                (amount, target, now_us, task_id, expected_version),
            )
            if cur.rowcount == 0:
                raise VersionConflictError(task_id)
            row = self._conn.execute(
                "SELECT * FROM borrow_task WHERE id = ?", (task_id,)
            ).fetchone()
            return _row_to_task(row)

    def clear_unresolved(self, task_id: str, now_us: int) -> None:
        """Test-seam: clear the unresolved marker so a task is eligible again."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE borrow_task SET unresolved_attempt_id = NULL,"
                " version = version + 1, updated_at_us = ? WHERE id = ?",
                (now_us, task_id),
            )
            if cur.rowcount == 0:
                raise UnknownTaskError(task_id)

    # --------------------------------------------------------------- settings

    def get_settings(self) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM borrow_settings WHERE id = 1"
            ).fetchone()
            return {
                "interval_seconds": row["interval_seconds"],
                "interval_us": row["interval_us"],
                "round_robin_cursor": row["round_robin_cursor"],
                "global_cooldown_until_us": row["global_cooldown_until_us"],
                "execution_enabled": row["execution_enabled"],
                "requires_rearm": row["requires_rearm"],
                "version": row["version"],
                "updated_at_us": row["updated_at_us"],
            }

    def get_interval_us(self) -> int:
        with self._lock:
            return self._conn.execute(
                "SELECT interval_us FROM borrow_settings WHERE id = 1"
            ).fetchone()[0]

    def update_settings(self, seconds_str: str, interval_us: int, now_us: int) -> dict:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE borrow_settings SET interval_seconds = ?, interval_us = ?,"
                " version = version + 1, updated_at_us = ? WHERE id = 1",
                (seconds_str, interval_us, now_us),
            )
            row = self._conn.execute(
                "SELECT * FROM borrow_settings WHERE id = 1"
            ).fetchone()
            return {
                "interval_seconds": row["interval_seconds"],
                "interval_us": row["interval_us"],
                "round_robin_cursor": row["round_robin_cursor"],
                "global_cooldown_until_us": row["global_cooldown_until_us"],
                "execution_enabled": row["execution_enabled"],
                "requires_rearm": row["requires_rearm"],
                "version": row["version"],
                "updated_at_us": row["updated_at_us"],
            }

    # -------------------------------------------------- execution control (C)

    def count_live_authorized_tasks(self) -> int:
        with self._lock:
            return self._conn.execute(
                "SELECT COUNT(*) FROM borrow_task WHERE live_authorized = 1"
            ).fetchone()[0]

    def count_pending_orphan_attempts(self) -> int:
        """Count pending attempts (crash-orphaned in-flight markers).

        At startup these are the attempts a previous process dispatched but never
        resolved; each blocks its task through ``unresolved_attempt_id`` until
        reconciliation. Reported as a sanitized startup recovery count (D7).
        """
        with self._lock:
            return self._conn.execute(
                "SELECT COUNT(*) FROM borrow_attempt WHERE outcome = ?", (D.OUTCOME_PENDING,)
            ).fetchone()[0]

    def set_execution_enabled(self, enabled: bool, now_us: int) -> None:
        """Toggle the durable global switch (§3.3).

        A manual Start NEVER bypasses an active exchange cooldown or a 418 ban's
        local 300s minimum: while ``global_cooldown_until_us`` is still in the
        future only ``execution_enabled`` is set, so ``insert_pending_attempt``'s
        live gate keeps blocking every POST. Only once the local cooldown has
        elapsed does Start also clear ``requires_rearm`` and the cooldown — the
        418 rule requires BOTH local 300s expiry AND a subsequent manual Start,
        and local expiry alone never auto-resumes (the archived ban window is up
        to three days, so local expiry is not evidence the ban ended).
        """
        with self._lock, self._conn:
            if enabled:
                current = self._conn.execute(
                    "SELECT global_cooldown_until_us FROM borrow_settings WHERE id = 1"
                ).fetchone()
                cooldown = current["global_cooldown_until_us"]
                if cooldown is not None and cooldown > now_us:
                    # Active cooldown (ordinary 429/-1003, or a 418 ban whose 300s
                    # minimum has not elapsed): a manual Start must not bypass it.
                    self._conn.execute(
                        "UPDATE borrow_settings SET execution_enabled = 1,"
                        " version = version + 1, updated_at_us = ? WHERE id = 1",
                        (now_us,),
                    )
                else:
                    # Local cooldown elapsed (or none): Start is the single manual
                    # exit from a 418 ban and clears the transient cooldown/re-arm.
                    self._conn.execute(
                        "UPDATE borrow_settings SET execution_enabled = 1, requires_rearm = 0,"
                        " global_cooldown_until_us = NULL, version = version + 1,"
                        " updated_at_us = ? WHERE id = 1",
                        (now_us,),
                    )
            else:
                self._conn.execute(
                    "UPDATE borrow_settings SET execution_enabled = 0,"
                    " version = version + 1, updated_at_us = ? WHERE id = 1",
                    (now_us,),
                )

    def set_requires_rearm(self, now_us: int) -> None:
        """Persist a 418 ban's manual-rearm requirement from a reconciliation GET.

        A reconciliation GET can observe a 418 just like a POST; the durable
        ``requires_rearm`` flag must be set so execution does not auto-resume
        after the 300s local cooldown, exactly as for a POST 418 (§5.1).
        """
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE borrow_settings SET requires_rearm = 1,"
                " version = version + 1, updated_at_us = ? WHERE id = 1",
                (now_us,),
            )

    def set_rate_cooldown(self, retry_after_seconds, now_us: int) -> None:
        """Extend the shared cooldown after a rate-limited reconciliation GET.

        Clamped to the same [60, 300] band as POST responses (a missing or
        nonsensical Retry-After falls back to the 60s floor). The cooldown blocks
        all signed borrow-client traffic including further reconciliation GETs,
        so a single rate-limit pauses the whole pass without advancing it.
        """
        retry = D.clamp_retry_after(retry_after_seconds)
        cooldown_us = now_us + int((retry * 1_000_000).to_integral_value())
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE borrow_settings SET global_cooldown_until_us = ?,"
                " version = version + 1, updated_at_us = ? WHERE id = 1",
                (cooldown_us, now_us),
            )

    # ---------------------------------------------------------------- attempts

    def insert_pending_attempt(
        self,
        task_id: str,
        asset: str,
        requested_amount: str,
        scheduled_at_us: int,
        dispatched_at_us: int,
        new_cursor_task_id: str,
        *,
        live_gates: bool = False,
    ) -> dict | None:
        """Atomically gate, insert the pending attempt, advance the cursor, and
        set the in-flight marker (breakdown §4.5).

        One conditional transaction re-checks execution ownership of the task
        (status ``borrowing``, no unresolved attempt, count below target) and,
        when ``live_gates`` is set, also the durable live gates
        (``live_authorized=1``, ``execution_enabled=1``, not rate-banned, not in
        global cooldown). A failed predicate creates no attempt row and no POST
        (returns ``None``). No transaction is held during I/O. The marker clears
        only on a terminal non-``unknown`` resolution.
        """
        with self._lock, self._conn:
            task = self._conn.execute(
                "SELECT status, live_authorized, unresolved_attempt_id,"
                " success_count, success_target FROM borrow_task WHERE id = ?",
                (task_id,),
            ).fetchone()
            if task is None:
                return None
            if task["status"] != D.STATUS_BORROWING:
                return None
            if task["unresolved_attempt_id"] is not None:
                return None
            if task["success_count"] >= task["success_target"]:
                return None
            if live_gates:
                settings = self._conn.execute(
                    "SELECT execution_enabled, requires_rearm, global_cooldown_until_us"
                    " FROM borrow_settings WHERE id = 1"
                ).fetchone()
                if settings["execution_enabled"] != 1:
                    return None
                if settings["requires_rearm"] != 0:
                    return None
                cooldown = settings["global_cooldown_until_us"]
                if cooldown is not None and cooldown > dispatched_at_us:
                    return None
            seq_row = self._conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM borrow_attempt"
                " WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            sequence = seq_row[0]
            cur = self._conn.execute(
                "INSERT INTO borrow_attempt"
                " (task_id, asset, sequence, outcome, result_category,"
                "  business_code, reason, http_status, tran_id, requested_amount,"
                "  scheduled_at_us, dispatched_at_us, finished_at_us, latency_ms,"
                "  effective_gap_us)"
                " VALUES (?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, ?, ?, ?, NULL,"
                "         NULL, NULL)",
                (
                    task_id,
                    asset,
                    sequence,
                    D.OUTCOME_PENDING,
                    requested_amount,
                    scheduled_at_us,
                    dispatched_at_us,
                ),
            )
            attempt_id = cur.lastrowid
            self._conn.execute(
                "UPDATE borrow_settings SET round_robin_cursor = ?,"
                " version = version + 1, updated_at_us = ? WHERE id = 1",
                (new_cursor_task_id, scheduled_at_us),
            )
            # In-flight marker set inside the same transaction: a crash between
            # this commit and resolution leaves the task blocked (§4.5).
            self._conn.execute(
                "UPDATE borrow_task SET unresolved_attempt_id = ?,"
                " version = version + 1, updated_at_us = ? WHERE id = ?",
                (attempt_id, dispatched_at_us, task_id),
            )
            row = self._conn.execute(
                "SELECT * FROM borrow_attempt WHERE id = ?", (attempt_id,)
            ).fetchone()
            return _row_to_attempt(row)

    def resolve_attempt(
        self, attempt_id: int, result: ExecutorResult, finished_at_us: int
    ) -> dict:
        """Resolve the attempt and apply its task/settings effects.

        Exactly one ledger row per attempt: this updates the pending row in
        place (append-only ledger; no second insert, no delete). The resolve
        matrix (§5.4) is applied on success; the in-flight marker clears on any
        terminal non-``unknown`` resolution and is retained on ``unknown``.
        """
        category = result.result_category
        with self._lock, self._conn:
            attempt = self._conn.execute(
                "SELECT * FROM borrow_attempt WHERE id = ?", (attempt_id,)
            ).fetchone()
            if attempt is None:
                raise UnknownTaskError(f"attempt {attempt_id}")
            dispatched_at_us = attempt["dispatched_at_us"]
            prev_row = self._conn.execute(
                "SELECT dispatched_at_us FROM borrow_attempt"
                " WHERE dispatched_at_us IS NOT NULL AND id < ?"
                " ORDER BY id DESC LIMIT 1",
                (attempt_id,),
            ).fetchone()
            effective_gap_us = (
                dispatched_at_us - prev_row["dispatched_at_us"]
                if (dispatched_at_us is not None and prev_row is not None)
                else None
            )
            latency_ms = (
                (finished_at_us - dispatched_at_us) // 1000
                if dispatched_at_us is not None
                else None
            )
            # Unknown attempts schedule their first reconciliation read at +5s.
            reconcile_next_at_us = None
            if category == D.RESULT_UNKNOWN:
                reconcile_next_at_us = finished_at_us + int(
                    D.RECONCILE_DELAYS_SECONDS[0]
                ) * 1_000_000
            self._conn.execute(
                "UPDATE borrow_attempt SET outcome = ?, result_category = ?,"
                " business_code = ?, reason = ?, http_status = ?, tran_id = ?,"
                " finished_at_us = ?, latency_ms = ?, effective_gap_us = ?,"
                " reconcile_next_at_us = ?"
                " WHERE id = ?",
                (
                    D.OUTCOME_RESOLVED,
                    category,
                    result.business_code,
                    result.reason,
                    result.http_status,
                    result.tran_id,
                    finished_at_us,
                    latency_ms,
                    effective_gap_us,
                    reconcile_next_at_us,
                    attempt_id,
                ),
            )
            task_id = attempt["task_id"]
            task = self._conn.execute(
                "SELECT * FROM borrow_task WHERE id = ?", (task_id,)
            ).fetchone()
            if task is not None:
                new_count = task["success_count"]
                new_status = task["status"]
                if category == D.RESULT_SUCCESS:
                    new_count = task["success_count"] + 1
                    new_status = _resolve_status(
                        task["status"], new_count, task["success_target"]
                    )
                # In-flight marker: cleared on terminal non-unknown resolution;
                # retained on unknown (stays blocked for reconciliation).
                marker = attempt_id if category == D.RESULT_UNKNOWN else None
                self._conn.execute(
                    "UPDATE borrow_task SET"
                    " latest_result_category = ?, latest_result_business_code = ?,"
                    " latest_result_reason = ?, latest_result_tran_id = ?,"
                    " latest_result_finished_at_us = ?, success_count = ?,"
                    " status = ?, unresolved_attempt_id = ?,"
                    " version = version + 1, updated_at_us = ?"
                    " WHERE id = ?",
                    (
                        category,
                        result.business_code,
                        result.reason,
                        result.tran_id,
                        finished_at_us,
                        new_count,
                        new_status,
                        marker,
                        finished_at_us,
                        task_id,
                    ),
                )
            if category == D.RESULT_RATE_LIMITED:
                self._apply_rate_limit(result, finished_at_us)
            row = self._conn.execute(
                "SELECT * FROM borrow_attempt WHERE id = ?", (attempt_id,)
            ).fetchone()
            return _row_to_attempt(row)

    def _apply_rate_limit(self, result: ExecutorResult, finished_at_us: int) -> None:
        """Set the global cooldown (and 418 re-arm flag) for a rate-limited result."""
        retry = result.retry_after_seconds
        if retry is not None:
            cooldown_us = finished_at_us + int(
                (retry * 1_000_000).to_integral_value()
            )
            self._conn.execute(
                "UPDATE borrow_settings SET global_cooldown_until_us = ?,"
                " version = version + 1, updated_at_us = ? WHERE id = 1",
                (cooldown_us, finished_at_us),
            )
        if result.http_status == 418:
            # 418 ban: local 300s minimum cooldown + manual re-arm (no auto-resume).
            self._conn.execute(
                "UPDATE borrow_settings SET requires_rearm = 1,"
                " version = version + 1, updated_at_us = ? WHERE id = 1",
                (finished_at_us,),
            )

    def list_attempts_page(self, limit: int, cursor_ts: int | None, cursor_id: int | None):
        """Return ``(entries, has_more)`` newest-completion-first (amendment §3)."""
        order = (
            " ORDER BY COALESCE(finished_at_us, dispatched_at_us, scheduled_at_us) DESC,"
            " id DESC LIMIT ?"
        )
        with self._lock:
            if cursor_ts is None:
                rows = self._conn.execute(
                    "SELECT * FROM borrow_attempt" + order, (limit + 1,)
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM borrow_attempt"
                    " WHERE (COALESCE(finished_at_us, dispatched_at_us, scheduled_at_us) < ?"
                    "       OR (COALESCE(finished_at_us, dispatched_at_us, scheduled_at_us) = ?"
                    "           AND id < ?))"
                    + order,
                    (cursor_ts, cursor_ts, cursor_id, limit + 1),
                ).fetchall()
        has_more = len(rows) > limit
        entries = [_row_to_attempt(r) for r in rows[:limit]]
        return entries, has_more

    # ----------------------------------------------------- reconciliation (C)

    def get_attempt(self, attempt_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM borrow_attempt WHERE id = ?", (attempt_id,)
            ).fetchone()
            return _row_to_attempt(row) if row is not None else None

    def list_due_reconciliations(self, now_us: int) -> list[dict]:
        """Unresolved unknown attempts due for a reconciliation read (§5.3).

        An attempt is due when it resolved ``unknown``, is not yet exhausted,
        and its scheduled next read is at or before ``now_us``.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM borrow_attempt"
                " WHERE outcome = ? AND result_category = ?"
                "   AND reconcile_exhausted = 0"
                "   AND reconcile_next_at_us IS NOT NULL"
                "   AND reconcile_next_at_us <= ?"
                " ORDER BY reconcile_next_at_us ASC, id ASC",
                (D.OUTCOME_RESOLVED, D.RESULT_UNKNOWN, now_us),
            ).fetchall()
            return [_row_to_attempt(r) for r in rows]

    def resolve_reconciliation_success(
        self, attempt_id: int, tran_id: str, now_us: int
    ) -> dict:
        """Resolve a reconciliation-proven success (unique CONFIRMED match).

        Records the matched id with ``reason=reconciled_unique_txid_match`` so
        audit distinguishes response-proven from history-inferred success, then
        applies the §5.4 matrix (increment, complete at target, deleted stays
        deleted) and clears the in-flight marker.
        """
        with self._lock, self._conn:
            attempt = self._conn.execute(
                "SELECT * FROM borrow_attempt WHERE id = ?", (attempt_id,)
            ).fetchone()
            if attempt is None:
                raise UnknownTaskError(f"attempt {attempt_id}")
            self._conn.execute(
                "UPDATE borrow_attempt SET tran_id = ?, reason = ?,"
                " reconcile_next_at_us = NULL, reconcile_exhausted = 0"
                " WHERE id = ?",
                (tran_id, D.REASON_RECONCILED_UNIQUE_TXID_MATCH, attempt_id),
            )
            task_id = attempt["task_id"]
            task = self._conn.execute(
                "SELECT * FROM borrow_task WHERE id = ?", (task_id,)
            ).fetchone()
            if task is not None:
                new_count = task["success_count"] + 1
                new_status = _resolve_status(
                    task["status"], new_count, task["success_target"]
                )
                self._conn.execute(
                    "UPDATE borrow_task SET"
                    " latest_result_category = ?, latest_result_reason = ?,"
                    " latest_result_tran_id = ?, latest_result_finished_at_us = ?,"
                    " success_count = ?, status = ?, unresolved_attempt_id = NULL,"
                    " version = version + 1, updated_at_us = ?"
                    " WHERE id = ?",
                    (
                        D.RESULT_SUCCESS,
                        D.REASON_RECONCILED_UNIQUE_TXID_MATCH,
                        tran_id,
                        now_us,
                        new_count,
                        new_status,
                        now_us,
                        task_id,
                    ),
                )
            row = self._conn.execute(
                "SELECT * FROM borrow_attempt WHERE id = ?", (attempt_id,)
            ).fetchone()
            return _row_to_attempt(row)

    def advance_reconciliation(self, attempt_id: int, now_us: int) -> bool:
        """Advance to the next reconciliation delay; return ``True`` if now exhausted.

        After the final (+900s) read with no unique match the attempt enters
        terminal ``reconciliation_exhausted``; the task stays blocked.
        """
        with self._lock, self._conn:
            attempt = self._conn.execute(
                "SELECT finished_at_us, reconcile_step FROM borrow_attempt WHERE id = ?",
                (attempt_id,),
            ).fetchone()
            if attempt is None:
                raise UnknownTaskError(f"attempt {attempt_id}")
            next_step = attempt["reconcile_step"] + 1
            if next_step >= len(D.RECONCILE_DELAYS_SECONDS):
                self._conn.execute(
                    "UPDATE borrow_attempt SET reconcile_step = ?,"
                    " reconcile_next_at_us = NULL, reconcile_exhausted = 1"
                    " WHERE id = ?",
                    (next_step, attempt_id),
                )
                return True
            base_us = attempt["finished_at_us"] or now_us
            next_at_us = base_us + int(D.RECONCILE_DELAYS_SECONDS[next_step]) * 1_000_000
            self._conn.execute(
                "UPDATE borrow_attempt SET reconcile_step = ?, reconcile_next_at_us = ?"
                " WHERE id = ?",
                (next_step, next_at_us, attempt_id),
            )
            return False

    def attribution_is_unique(
        self,
        attempt_id: int,
        task_id: str,
        asset: str,
        requested_amount: str,
        candidate_txid: str | None,
    ) -> bool:
        """Return True only if a candidate loan record is unambiguously this
        attempt's (Boundary C §5.3 / risk §11 — no false cross-task attribution).

        Two fail-closed conditions keep the attempt blocked:
        1. the candidate ``txId`` is already claimed by another attempt's
           ``tran_id`` (a different attempt already proved/credited it); or
        2. another task has an unresolved same-asset attempt whose requested
           amount is Decimal-equal — it could also match the same loan record, so
           the single history row cannot be uniquely attributed here.

        Amount comparison is Decimal (not string), so ``"1.5"`` and ``"1.50"``
        are correctly equal. An unparseable requested_amount fails closed.
        """
        with self._lock:
            if candidate_txid is not None:
                claimed = self._conn.execute(
                    "SELECT COUNT(*) FROM borrow_attempt"
                    " WHERE tran_id = ? AND id != ?",
                    (candidate_txid, attempt_id),
                ).fetchone()[0]
                if claimed > 0:
                    return False
            try:
                target = Decimal(requested_amount)
            except (InvalidOperation, TypeError, ValueError):
                return False
            rows = self._conn.execute(
                "SELECT requested_amount FROM borrow_attempt"
                " WHERE task_id != ? AND asset = ? AND id != ?"
                "   AND (outcome = ? OR result_category = ?)",
                (task_id, asset, attempt_id, D.OUTCOME_PENDING, D.RESULT_UNKNOWN),
            ).fetchall()
            for r in rows:
                try:
                    if Decimal(r["requested_amount"]) == target:
                        return False
                except (InvalidOperation, TypeError, ValueError):
                    continue
            return True
