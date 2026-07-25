"""SQLite-backed durable hedge-open store (10-design §2 / ADR-1 / breakdown §3.3).

A modular-monolith local store mirroring ``borrow_tasks.store``: one connection
guarded by a single RLock, short ``with self._conn:`` write transactions, and
the executor never invoked while a transaction or the lock is held. Internal
time is integer microseconds since epoch; money/quantities are decimal strings.

Tables:
  hedge_open_task    — stage-1 Task fields + q_common/position_side_mode/leg_exposure
                       + the real-API attempt/acceptance/pause counters (breakdown §3.3)
  hedge_open_attempt — immutable per-pair core written in the pre-send transaction
                       (ADR-2 / breakdown §3.3); one row per dispatched pair
  hedge_open_leg     — one mutable row per leg (spot|perp), advanced through the
                       PREPARED→DISPATCHING→(ACCEPTED_OR_QUERYING|UNKNOWN_QUERYING)
                       →TERMINAL_RECORDED reconciliation cycle (breakdown §3.3/§3.5)
  hedge_open_fill    — round-1 legacy one-row-per-attempt table (additive: still
                       readable by aggregate_positions; the live path writes legs)
  hedge_open_log     — append-only record-transport log (would-send params, no secrets)
  hedge_open_settings — global Start gate + executor-mode snapshot + fixed 1s interval

No network imports: only :mod:`os`, :mod:`sqlite3`, :mod:`threading`, :mod:`time`,
:mod:`json` and :mod:`decimal`.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from decimal import Decimal, InvalidOperation
from typing import Any

from . import domain as D
from .executor import AttemptOutcome

_SCHEMA = """
CREATE TABLE IF NOT EXISTS hedge_open_task (
    id                    TEXT PRIMARY KEY,
    coin                  TEXT NOT NULL,
    direction             TEXT NOT NULL,
    mode                  TEXT NOT NULL,
    single_amount         TEXT NOT NULL,
    target_n              INTEGER NOT NULL,
    success_count         INTEGER NOT NULL DEFAULT 0,
    fail_count            INTEGER NOT NULL DEFAULT 0,
    status                TEXT NOT NULL,
    q_common              TEXT,
    position_side_mode    TEXT,
    leg_exposure          TEXT,
    preflight_snapshot    TEXT,
    creation_seq          INTEGER NOT NULL,
    created_at_us         INTEGER NOT NULL,
    updated_at_us         INTEGER NOT NULL,
    scheduled_attempt_count         INTEGER NOT NULL DEFAULT 0,
    accepted_pair_count             INTEGER NOT NULL DEFAULT 0,
    consecutive_submission_failures INTEGER NOT NULL DEFAULT 0,
    failure_pause_threshold         INTEGER NOT NULL DEFAULT 3,
    pause_reason                    TEXT,
    pause_reason_zh                 TEXT,
    stop_reason                     TEXT,
    last_worker_exit_reason         TEXT
);
CREATE TABLE IF NOT EXISTS hedge_open_attempt (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id               TEXT NOT NULL,
    attempt_uuid          TEXT NOT NULL,
    attempt_seq           INTEGER NOT NULL,
    direction             TEXT NOT NULL,
    q_common              TEXT NOT NULL,
    preflight_fingerprint TEXT NOT NULL,
    position_side_mode    TEXT NOT NULL,
    pair_outcome          TEXT,
    error_category        TEXT,
    error_code            TEXT,
    error_reason_zh       TEXT,
    rate_limited          INTEGER NOT NULL DEFAULT 0,
    log_ref               INTEGER,
    created_at_us         INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS hedge_open_leg (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id           INTEGER NOT NULL,
    leg                  TEXT NOT NULL,
    client_order_id      TEXT NOT NULL UNIQUE,
    endpoint             TEXT NOT NULL,
    request_shape        TEXT NOT NULL,
    dispatch_state       TEXT NOT NULL,
    order_id             TEXT,
    exchange_status      TEXT,
    cumulative_base_qty  TEXT NOT NULL DEFAULT '0',
    cumulative_quote_amt TEXT NOT NULL DEFAULT '0',
    fee_amount           TEXT,
    fee_asset            TEXT,
    error_code           TEXT,
    error_category       TEXT,
    dispatched_at_us     INTEGER,
    last_query_at_us     INTEGER,
    terminal             INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS hedge_open_fill (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id                 TEXT NOT NULL,
    ts_us                   INTEGER NOT NULL,
    attempt_id              TEXT NOT NULL,
    category                TEXT NOT NULL,
    spot_client_order_id    TEXT,
    spot_order_id           TEXT,
    spot_status             TEXT NOT NULL,
    spot_filled_qty         TEXT NOT NULL,
    spot_avg_price          TEXT,
    perp_client_order_id    TEXT,
    perp_order_id           TEXT,
    perp_status             TEXT NOT NULL,
    perp_filled_qty         TEXT NOT NULL,
    perp_avg_price          TEXT,
    record_ref              INTEGER
);
CREATE TABLE IF NOT EXISTS hedge_open_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      TEXT NOT NULL,
    ts_us        INTEGER NOT NULL,
    attempt_id   TEXT,
    kind         TEXT NOT NULL,
    payload      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hedge_open_settings (
    id                       INTEGER PRIMARY KEY CHECK (id = 1),
    start_gate               INTEGER NOT NULL DEFAULT 0,
    executor_mode_snapshot   TEXT NOT NULL,
    interval_seconds         TEXT NOT NULL,
    interval_us              INTEGER NOT NULL,
    rate_limit_order         INTEGER,
    version                  INTEGER NOT NULL DEFAULT 1,
    updated_at_us            INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hedge_open_attempt_task
    ON hedge_open_attempt (task_id, attempt_seq ASC, id ASC);
CREATE INDEX IF NOT EXISTS idx_hedge_open_leg_attempt
    ON hedge_open_leg (attempt_id, leg ASC);
CREATE INDEX IF NOT EXISTS idx_hedge_open_leg_query
    ON hedge_open_leg (terminal, dispatch_state);
CREATE INDEX IF NOT EXISTS idx_hedge_open_fill_task
    ON hedge_open_fill (task_id, ts_us DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_hedge_open_log_ts
    ON hedge_open_log (ts_us DESC, id DESC);
"""


class StoreError(Exception):
    """Base store-level error."""


class UnknownTaskError(StoreError):
    pass


def _row_to_task(row: sqlite3.Row) -> dict:
    leg_exposure = None
    raw_exposure = row["leg_exposure"]
    if raw_exposure:
        leg_exposure = json.loads(raw_exposure)
    preflight = None
    raw_pf = row["preflight_snapshot"]
    if raw_pf:
        preflight = json.loads(raw_pf)
    return {
        "id": row["id"],
        "coin": row["coin"],
        "direction": row["direction"],
        "mode": row["mode"],
        "single_amount": row["single_amount"],
        "target_n": row["target_n"],
        "success_count": row["success_count"],
        "fail_count": row["fail_count"],
        "status": row["status"],
        "q_common": row["q_common"],
        "position_side_mode": row["position_side_mode"],
        "leg_exposure": leg_exposure,
        "preflight_snapshot": preflight,
        "creation_seq": row["creation_seq"],
        "created_at_us": row["created_at_us"],
        "updated_at_us": row["updated_at_us"],
        "scheduled_attempt_count": row["scheduled_attempt_count"],
        "accepted_pair_count": row["accepted_pair_count"],
        "consecutive_submission_failures": row["consecutive_submission_failures"],
        "failure_pause_threshold": row["failure_pause_threshold"],
        "pause_reason": row["pause_reason"],
        "pause_reason_zh": row["pause_reason_zh"],
        "stop_reason": row["stop_reason"],
        "last_worker_exit_reason": row["last_worker_exit_reason"],
    }


def _row_to_fill(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "ts_us": row["ts_us"],
        "attempt_id": row["attempt_id"],
        "category": row["category"],
        "spot": {
            "client_order_id": row["spot_client_order_id"],
            "order_id": row["spot_order_id"],
            "status": row["spot_status"],
            "filled_qty": row["spot_filled_qty"],
            "avg_price": row["spot_avg_price"],
        },
        "perp": {
            "client_order_id": row["perp_client_order_id"],
            "order_id": row["perp_order_id"],
            "status": row["perp_status"],
            "filled_qty": row["perp_filled_qty"],
            "avg_price": row["perp_avg_price"],
        },
        "record_ref": row["record_ref"],
    }


def _row_to_attempt(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "attempt_uuid": row["attempt_uuid"],
        "attempt_seq": row["attempt_seq"],
        "direction": row["direction"],
        "q_common": row["q_common"],
        "preflight_fingerprint": row["preflight_fingerprint"],
        "position_side_mode": row["position_side_mode"],
        "pair_outcome": row["pair_outcome"],
        "error_category": row["error_category"],
        "error_code": row["error_code"],
        "error_reason_zh": row["error_reason_zh"],
        "rate_limited": bool(row["rate_limited"]),
        "log_ref": row["log_ref"],
        "created_at_us": row["created_at_us"],
    }


def _row_to_leg(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "attempt_id": row["attempt_id"],
        "leg": row["leg"],
        "client_order_id": row["client_order_id"],
        "endpoint": row["endpoint"],
        "request_shape": row["request_shape"],
        "dispatch_state": row["dispatch_state"],
        "order_id": row["order_id"],
        "exchange_status": row["exchange_status"],
        "cumulative_base_qty": row["cumulative_base_qty"],
        "cumulative_quote_amt": row["cumulative_quote_amt"],
        "fee_amount": row["fee_amount"],
        "fee_asset": row["fee_asset"],
        "error_code": row["error_code"],
        "error_category": row["error_category"],
        "dispatched_at_us": row["dispatched_at_us"],
        "last_query_at_us": row["last_query_at_us"],
        "terminal": row["terminal"],
    }


def _row_to_log(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "ts_us": row["ts_us"],
        "attempt_id": row["attempt_id"],
        "kind": row["kind"],
        "payload": row["payload"],
    }


def _num(value) -> Decimal:
    try:
        return Decimal(str(value)) if value is not None else Decimal(0)
    except InvalidOperation:
        return Decimal(0)


class HedgeOpenStore:
    def __init__(self, db_path: str, *, executor_mode_snapshot: str = "disabled"):
        self._lock = threading.RLock()
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        with self._lock, self._conn:
            self._migrate()
            cur = self._conn.execute(
                "SELECT COUNT(*) FROM hedge_open_settings WHERE id = 1"
            )
            if cur.fetchone()[0] == 0:
                self._conn.execute(
                    "INSERT INTO hedge_open_settings"
                    " (id, start_gate, executor_mode_snapshot, interval_seconds,"
                    "  interval_us, rate_limit_order, version, updated_at_us)"
                    " VALUES (1, 0, ?, ?, ?, NULL, 1, ?)",
                    (
                        executor_mode_snapshot,
                        D.DEFAULT_INTERVAL_SECONDS,
                        D.DEFAULT_INTERVAL_US,
                        int(time.time() * 1_000_000),
                    ),
                )

    def _migrate(self) -> None:
        """Additive-forward migration (breakdown §3.9). New columns are added
        with per-column ALTER guards and backfilled to the frozen defaults;
        pre-existing rows keep their data and stay readable. Idempotent."""
        task_cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(hedge_open_task)")}
        additions = (
            ("scheduled_attempt_count", "INTEGER NOT NULL DEFAULT 0"),
            ("accepted_pair_count", "INTEGER NOT NULL DEFAULT 0"),
            ("consecutive_submission_failures", "INTEGER NOT NULL DEFAULT 0"),
            ("failure_pause_threshold", "INTEGER NOT NULL DEFAULT 3"),
            ("pause_reason", "TEXT"),
            ("pause_reason_zh", "TEXT"),
            ("stop_reason", "TEXT"),
            ("last_worker_exit_reason", "TEXT"),
        )
        for col, decl in additions:
            if col not in task_cols:
                self._conn.execute(f"ALTER TABLE hedge_open_task ADD COLUMN {col} {decl}")
        attempt_cols = {
            r["name"] for r in self._conn.execute("PRAGMA table_info(hedge_open_attempt)")
        }
        attempt_additions = (
            ("error_category", "TEXT"),
            ("error_code", "TEXT"),
            ("error_reason_zh", "TEXT"),
            ("rate_limited", "INTEGER NOT NULL DEFAULT 0"),
        )
        for col, decl in attempt_additions:
            if col not in attempt_cols:
                self._conn.execute(f"ALTER TABLE hedge_open_attempt ADD COLUMN {col} {decl}")
        leg_cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(hedge_open_leg)")}
        leg_additions = (
            ("error_code", "TEXT"),
            ("error_category", "TEXT"),
        )
        for col, decl in leg_additions:
            if col not in leg_cols:
                self._conn.execute(f"ALTER TABLE hedge_open_leg ADD COLUMN {col} {decl}")

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------ tasks

    def create_task(
        self,
        task_id: str,
        coin: str,
        direction: str,
        mode: str,
        single_amount: str,
        target_n: int,
        q_common: str | None,
        position_side_mode: str | None,
        preflight_snapshot: dict | None,
        now_us: int,
        *,
        failure_pause_threshold: int = D.DEFAULT_FAILURE_PAUSE_THRESHOLD,
    ) -> dict:
        with self._lock, self._conn:
            creation_seq = self._conn.execute(
                "SELECT COALESCE(MAX(creation_seq), 0) + 1 FROM hedge_open_task"
            ).fetchone()[0]
            # New tasks start in the runnable ``running`` status so the scheduler
            # can dispatch them once the global Start gate is on (10-design §6).
            self._conn.execute(
                "INSERT INTO hedge_open_task"
                " (id, coin, direction, mode, single_amount, target_n,"
                "  success_count, fail_count, status, q_common,"
                "  position_side_mode, leg_exposure, preflight_snapshot,"
                "  creation_seq, created_at_us, updated_at_us,"
                "  scheduled_attempt_count, accepted_pair_count,"
                "  consecutive_submission_failures, failure_pause_threshold,"
                "  pause_reason)"
                " VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, NULL, ?, ?, ?, ?,"
                "         0, 0, 0, ?, NULL)",
                (
                    task_id,
                    coin,
                    direction,
                    mode,
                    single_amount,
                    target_n,
                    D.STATUS_RUNNING,
                    q_common,
                    position_side_mode,
                    json.dumps(preflight_snapshot) if preflight_snapshot is not None else None,
                    creation_seq,
                    now_us,
                    now_us,
                    failure_pause_threshold,
                ),
            )
            row = self._conn.execute(
                "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            return _row_to_task(row)

    def get_task(self, task_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            return _row_to_task(row) if row is not None else None

    def list_tasks(self, status_filter: str | None = None) -> list[dict]:
        """List tasks per the resolved status filter from
        :func:`domain.filter_status_for_list` (frozen §3.1).
        """
        with self._lock:
            if status_filter is None:
                rows = self._conn.execute(
                    "SELECT * FROM hedge_open_task"
                    " WHERE status != ? ORDER BY creation_seq ASC, id ASC",
                    (D.STATUS_DELETED,),
                ).fetchall()
            elif status_filter == D.LIST_ALL:
                rows = self._conn.execute(
                    "SELECT * FROM hedge_open_task"
                    " ORDER BY creation_seq ASC, id ASC",
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM hedge_open_task WHERE status = ?"
                    " ORDER BY creation_seq ASC, id ASC",
                    (status_filter,),
                ).fetchall()
            return [_row_to_task(r) for r in rows]

    def set_task_status(self, task_id: str, status: str, now_us: int) -> dict:
        with self._lock, self._conn:
            # Returning to RUNNING clears the sticky pause state and the worker
            # exit reason (Review-1 r3 P1-1 / P2-2): a 429/insufficient pause and
            # a worker-exit reason are NOT sticky across a manual Start/recover —
            # mirroring pause_task clearing stop_reason on a pause. Every other
            # status transition touches status + updated_at_us only.
            if status == D.STATUS_RUNNING:
                cur = self._conn.execute(
                    "UPDATE hedge_open_task SET status = ?,"
                    " pause_reason = NULL, pause_reason_zh = NULL,"
                    " last_worker_exit_reason = NULL, updated_at_us = ? WHERE id = ?",
                    (status, now_us, task_id),
                )
            else:
                cur = self._conn.execute(
                    "UPDATE hedge_open_task SET status = ?, updated_at_us = ? WHERE id = ?",
                    (status, now_us, task_id),
                )
            if cur.rowcount == 0:
                raise UnknownTaskError(task_id)
            row = self._conn.execute(
                "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            return _row_to_task(row)

    def set_failure_pause_threshold(self, task_id: str, threshold: int, now_us: int) -> dict:
        """Task-snapshotted threshold (ADR-3 / PRD §6.4). Defaults to 3 at create
        and may be tightened later without retroactively moving the bar."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE hedge_open_task SET failure_pause_threshold = ?,"
                " updated_at_us = ? WHERE id = ?",
                (int(threshold), now_us, task_id),
            )
            if cur.rowcount == 0:
                raise UnknownTaskError(task_id)
            row = self._conn.execute(
                "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            return _row_to_task(row)

    def clear_leg_exposure(self, task_id: str, now_us: int) -> dict:
        """Clear a recorded single-leg exposure (advisory; operator review)."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE hedge_open_task SET leg_exposure = NULL, updated_at_us = ?"
                " WHERE id = ?",
                (now_us, task_id),
            )
            if cur.rowcount == 0:
                raise UnknownTaskError(task_id)
            row = self._conn.execute(
                "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            return _row_to_task(row)

    def list_eligible_tasks(self) -> list[dict]:
        """Tasks the scheduler may dispatch one pair for this tick (breakdown
        §4.4 / §3.6 + amendment cadence). Eligibility is the per-task serial
        gate: ``running`` AND ``scheduled_attempt_count < target_n`` (the planned-
        attempt hard cap, A-1) AND no unresolved in-flight pair for that task
        (amendment: the next pair of the same task never starts while that task
        has an unresolved pair — A-9 per-task sequentiality). A single-leg
        exposure is advisory and does NOT block dispatch (§4.5); reaching the
        pause threshold sets status ``paused``, so the status filter excludes
        paused tasks. Other tasks stay independent (cross-task concurrency).
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM hedge_open_task t"
                " WHERE t.status = ?"
                "   AND t.scheduled_attempt_count < t.target_n"
                "   AND NOT EXISTS ("
                "       SELECT 1 FROM hedge_open_attempt a"
                "       WHERE a.task_id = t.id AND a.pair_outcome IS NULL)"
                " ORDER BY t.creation_seq ASC, t.id ASC",
                (D.STATUS_RUNNING,),
            ).fetchall()
            return [_row_to_task(r) for r in rows]

    # ---------------------------------------------------- attempt / leg lifecycle

    def prepare_attempt(
        self,
        task_id: str,
        attempt_uuid: str,
        direction: str,
        q_common: str,
        position_side_mode: str,
        preflight_fingerprint: dict,
        spot_client_order_id: str,
        spot_request_shape: dict,
        perp_client_order_id: str,
        perp_request_shape: dict,
        now_us: int,
    ) -> dict | None:
        """Durable-before-send (ADR-2 / breakdown §3.3). ONE transaction commits
        the immutable attempt row + both deterministic client IDs + the sanitized
        would-send request shapes in the ``PREPARED`` state, and advances the
        scheduled-attempt counter. Re-checks eligibility inside the transaction;
        a task that is no longer runnable/under-target returns ``None`` (no row,
        no POST). The executor is invoked AFTER this returns (no lock/txn held).

        A post-commit crash leaves two ``PREPARED``/non-terminal legs — a query
        obligation resolved by client-ID lookup on restart, never by resending.
        """
        with self._lock, self._conn:
            task = self._conn.execute(
                "SELECT status, scheduled_attempt_count, target_n FROM hedge_open_task"
                " WHERE id = ?",
                (task_id,),
            ).fetchone()
            if task is None:
                return None
            if task["status"] != D.STATUS_RUNNING:
                return None
            # A-1: the planned-attempt hard cap, checked atomically inside the
            # same transaction that increments the counter, shared by every entry
            # path (scheduler / fill-once / concurrent workers — I-1). Failed and
            # single-leg outcomes are never replaced, so the count is consumed
            # once a pair is reserved regardless of its later outcome.
            if task["scheduled_attempt_count"] >= task["target_n"]:
                return None
            # I-1 / amendment cadence: never open a second concurrent pair for the
            # same task. An unresolved pair (pair_outcome IS NULL) blocks this
            # task's next pair; it never blocks another task.
            in_flight = self._conn.execute(
                "SELECT 1 FROM hedge_open_attempt"
                " WHERE task_id = ? AND pair_outcome IS NULL LIMIT 1",
                (task_id,),
            ).fetchone()
            if in_flight is not None:
                return None
            seq = self._conn.execute(
                "SELECT COALESCE(MAX(attempt_seq), 0) + 1 FROM hedge_open_attempt"
                " WHERE task_id = ?",
                (task_id,),
            ).fetchone()[0]
            cur = self._conn.execute(
                "INSERT INTO hedge_open_attempt"
                " (task_id, attempt_uuid, attempt_seq, direction, q_common,"
                "  preflight_fingerprint, position_side_mode, pair_outcome,"
                "  log_ref, created_at_us)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)",
                (
                    task_id,
                    attempt_uuid,
                    seq,
                    direction,
                    q_common,
                    json.dumps(preflight_fingerprint, ensure_ascii=False),
                    position_side_mode or D.POS_MODE_BOTH,
                    now_us,
                ),
            )
            attempt_id = cur.lastrowid
            self._conn.execute(
                "INSERT INTO hedge_open_leg"
                " (attempt_id, leg, client_order_id, endpoint, request_shape,"
                "  dispatch_state, order_id, exchange_status,"
                "  cumulative_base_qty, cumulative_quote_amt, fee_amount,"
                "  fee_asset, dispatched_at_us, last_query_at_us, terminal)"
                " VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, '0', '0', NULL, NULL,"
                "         NULL, NULL, 0)",
                (
                    attempt_id,
                    "spot",
                    spot_client_order_id,
                    D.SPOT_ORDER_PATH,
                    json.dumps(spot_request_shape, ensure_ascii=False),
                    D.LEG_PREPARED,
                ),
            )
            self._conn.execute(
                "INSERT INTO hedge_open_leg"
                " (attempt_id, leg, client_order_id, endpoint, request_shape,"
                "  dispatch_state, order_id, exchange_status,"
                "  cumulative_base_qty, cumulative_quote_amt, fee_amount,"
                "  fee_asset, dispatched_at_us, last_query_at_us, terminal)"
                " VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, '0', '0', NULL, NULL,"
                "         NULL, NULL, 0)",
                (
                    attempt_id,
                    "perp",
                    perp_client_order_id,
                    D.PERP_ORDER_PATH,
                    json.dumps(perp_request_shape, ensure_ascii=False),
                    D.LEG_PREPARED,
                ),
            )
            self._conn.execute(
                "UPDATE hedge_open_task SET scheduled_attempt_count ="
                " scheduled_attempt_count + 1, updated_at_us = ? WHERE id = ?",
                (now_us, task_id),
            )
            row = self._conn.execute(
                "SELECT * FROM hedge_open_attempt WHERE id = ?", (attempt_id,)
            ).fetchone()
            return _row_to_attempt(row)

    def _leg_final_fields(
        self, leg_outcome: dict
    ) -> tuple[str, str | None, str, str, str | None, str | None]:
        """Return ``(exchange_status, order_id, base_qty, quote_amt, fee_amount,
        fee_asset)`` for one resolved leg outcome (A-6).

        Persists the ACTUAL cumulative quote when the outcome carries one (the
        live path returns the exchange's ``cummulativeQuoteQty``); otherwise it
        falls back to ``filled_qty * avg_price`` in Decimal (no binary float). A
        non-FILLED leg records zero fill figures but keeps any returned orderId
        (proof of acceptance) and any partial cumulative figures it carried.
        Available fee figures pass through verbatim.
        """
        status = leg_outcome.get("status") or D.LEG_UNKNOWN
        order_id = leg_outcome.get("order_id")
        filled_qty = _num(leg_outcome.get("filled_qty"))
        avg_price = leg_outcome.get("avg_price")
        cumulative_quote = leg_outcome.get("cumulative_quote")
        fee_amount = leg_outcome.get("fee_amount")
        fee_asset = leg_outcome.get("fee_asset")
        if cumulative_quote not in (None, "", "0", 0):
            try:
                quote = Decimal(str(cumulative_quote))
            except InvalidOperation:
                quote = Decimal(0)
        elif filled_qty > 0 and avg_price is not None:
            quote = filled_qty * _num(avg_price)
        else:
            quote = Decimal(0)
        return (
            status,
            order_id,
            str(filled_qty),
            str(quote),
            str(fee_amount) if fee_amount is not None else None,
            str(fee_asset) if fee_asset is not None else None,
        )

    def _apply_task_counters(
        self, task_id: str, category: str, exposure: dict | None, now_us: int,
        *, fatal: bool = False, stop_reason: str | None = None,
        skip_counters: bool = False,
    ) -> tuple[dict, str | None, str | None]:
        """Apply one pair's acceptance verdict to the task counters + status.

        Shared by :meth:`resolve_attempt` (synchronous dispatch resolution) and
        :meth:`finalize_attempt` (reconcile-time resolution). MUST run inside the
        caller's ``with self._lock, self._conn:`` transaction. Returns
        ``(updated_task, pair_outcome, pause_reason)``; the caller stamps
        ``pair_outcome`` onto the attempt row.

        - fatal submission (amendment rows 1–2) -> ``stopped`` + ``stop_reason``
          immediately, no failure-threshold wait, no counter churn.
        - accepted pair (both orderId) -> accepted/success ++, consecutive reset;
          pair_outcome ``accepted_pair``.
        - confirmed failed (neither orderId) -> fail ++, consecutive ++; reaching
          the task threshold pauses with ``consecutive_submission_failure``.
        - single-leg (one orderId) -> ADVISORY: counts unchanged, ``leg_exposure``
          recorded, scheduling never blocked (§4.5).
        """
        task = _row_to_task(
            self._conn.execute(
                "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
        )
        new_accepted = task["accepted_pair_count"]
        new_success = task["success_count"]
        new_fail = task["fail_count"]
        new_consecutive = task["consecutive_submission_failures"]
        leg_exposure_json = task["leg_exposure"]
        pause_reason = task["pause_reason"]
        new_stop_reason: str | None = task["stop_reason"]
        new_status: str = task["status"]
        if skip_counters:
            # Review-1 r3 P2-1 / amendment 21: a rate-limited pair is settled by
            # its own per-attempt facts via settle_attempt_no_counters. Derive
            # ONLY the truthful pair_outcome and the advisory single-leg
            # leg_exposure here; counters, status, threshold, pause_reason,
            # stop_reason and audit events stay untouched. The
            # consecutive-failure brake and fatal-stop remain the job of
            # finalize_attempt for non-rate-limited pairs.
            if category == D.ATTEMPT_SUCCESS:
                pair_outcome = D.PAIR_ACCEPTED
            elif category == D.ATTEMPT_SINGLE_LEG_EXPOSURE:
                pair_outcome = D.PAIR_SINGLE_LEG
                if exposure:
                    leg_exposure_json = exposure
            elif category == D.ATTEMPT_FAILED:
                pair_outcome = D.PAIR_CONFIRMED_FAILED
            else:
                pair_outcome = None
        elif fatal:
            # Amendment rows 1–2 / I-2: stop immediately. The attempt was already
            # counted at reservation; the consecutive-failure counter is untouched
            # (a fatal stop is terminal, not a threshold failure). A fatal pair is
            # not an accepted pair.
            pair_outcome = D.PAIR_CONFIRMED_FAILED
            new_status = D.STATUS_STOPPED
            new_stop_reason = stop_reason or D.STOP_REASON_EXCHANGE_FATAL
        elif category == D.ATTEMPT_SUCCESS:
            new_accepted = task["accepted_pair_count"] + 1
            new_success = task["success_count"] + 1
            new_consecutive = 0
            pair_outcome = D.PAIR_ACCEPTED
            new_status = D.resolve_status_after_attempt(
                task["status"], category, new_accepted, task["target_n"],
                new_consecutive, task["failure_pause_threshold"],
            )
        elif category == D.ATTEMPT_FAILED:
            new_fail = task["fail_count"] + 1
            new_consecutive = task["consecutive_submission_failures"] + 1
            pair_outcome = D.PAIR_CONFIRMED_FAILED
            new_status = D.resolve_status_after_attempt(
                task["status"], category, new_accepted, task["target_n"],
                new_consecutive, task["failure_pause_threshold"],
            )
            if new_status == D.STATUS_PAUSED:
                pause_reason = D.PAUSE_REASON_CONSECUTIVE_SUBMISSION_FAILURE
        elif category == D.ATTEMPT_SINGLE_LEG_EXPOSURE:
            # Advisory (§4.5): record the exposure but do not touch the
            # counters or freeze scheduling.
            pair_outcome = D.PAIR_SINGLE_LEG
            new_status = D.resolve_status_after_attempt(
                task["status"], category, new_accepted, task["target_n"],
                new_consecutive, task["failure_pause_threshold"],
            )
            if exposure:
                leg_exposure_json = exposure
        else:
            # ATTEMPT_DISABLED / unknown: preserve status, no counter change.
            pair_outcome = None
            new_status = task["status"]
        self._conn.execute(
            "UPDATE hedge_open_task SET accepted_pair_count = ?,"
            " success_count = ?, fail_count = ?,"
            " consecutive_submission_failures = ?, status = ?,"
            " leg_exposure = ?, pause_reason = ?, stop_reason = ?,"
            " updated_at_us = ? WHERE id = ?",
            (
                new_accepted,
                new_success,
                new_fail,
                new_consecutive,
                new_status,
                json.dumps(leg_exposure_json) if leg_exposure_json is not None else None,
                pause_reason,
                new_stop_reason,
                now_us,
                task_id,
            ),
        )
        row = self._conn.execute(
            "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
        ).fetchone()
        # Amendment §5 entries: surface the task-level lifecycle events (fatal
        # stop, consecutive-failure threshold pause) on the additive entries
        # timeline. Guarded on the status transition so a repeated call never
        # double-records. These share hedge_open_log with attempt_id NULL.
        if fatal and task["status"] != D.STATUS_STOPPED:
            self._conn.execute(
                "INSERT INTO hedge_open_log (task_id, ts_us, attempt_id, kind, payload)"
                " VALUES (?, ?, NULL, ?, ?)",
                (
                    task_id,
                    now_us,
                    "task_stopped",
                    json.dumps(
                        {
                            "stop_reason": new_stop_reason,
                            "reason_zh": D.stop_reason_zh(new_stop_reason),
                            "source": "submission",
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
        elif (
            new_status == D.STATUS_PAUSED
            and task["status"] != D.STATUS_PAUSED
            and pause_reason == D.PAUSE_REASON_CONSECUTIVE_SUBMISSION_FAILURE
        ):
            self._conn.execute(
                "INSERT INTO hedge_open_log (task_id, ts_us, attempt_id, kind, payload)"
                " VALUES (?, ?, NULL, ?, ?)",
                (
                    task_id,
                    now_us,
                    "threshold_paused",
                    json.dumps(
                        {
                            "reason": D.PAUSE_REASON_CONSECUTIVE_SUBMISSION_FAILURE,
                            "consecutive_submission_failures": new_consecutive,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
        return _row_to_task(row), pair_outcome, pause_reason

    @staticmethod
    def _outcome_error(outcome) -> tuple[bool, str | None, str | None, str | None]:
        """Derive ``(fatal, stop_reason, error_code, error_reason_zh)`` from an
        outcome (amendment rows 1–2). A live outcome whose ``error_category`` is
        ``"fatal"`` (an exchange code for insufficient balance/margin/filter/
        min-notional/symbol/mode) stops the task immediately. The dry-run record
        transport carries no error category, so it is never fatal here."""
        error_category = getattr(outcome, "error_category", None)
        error_code = getattr(outcome, "error_code", None)
        if error_category == "fatal":
            stop_reason = D.STOP_REASON_EXCHANGE_FATAL
            return True, stop_reason, error_code, D.stop_reason_zh(stop_reason)
        return False, None, error_code, getattr(outcome, "error_reason_zh", None)

    def resolve_attempt(
        self, attempt_id: int, outcome: AttemptOutcome, now_us: int,
        *, leg_terminal: dict | None = None,
    ) -> dict:
        """Resolve both legs to their acceptance/fill verdict and apply the task
        counters + pause (breakdown §3.3/§3.6). Runs in a second short transaction
        AFTER the executor returned (no executor call under the lock).

        ``leg_terminal`` (live path) maps ``"spot"``/``"perp"`` -> bool: an
        accepted leg that is NEW/PARTIALLY_FILLED is left non-terminal for the
        reconcile pass, while FILLED and REJECTED legs close immediately. ``None``
        (record/disabled path) closes both legs — the record transport resolves
        both legs synchronously to a terminal simulated verdict.

        - accepted pair (both orderId) -> accepted_pair_count ++, consecutive
          reset; pair_outcome ``accepted_pair``.
        - confirmed failed (neither orderId) -> fail_count ++, consecutive ++;
          reaching the task threshold pauses.
        - single-leg (one orderId) -> advisory: counts unchanged, leg_exposure
          recorded, scheduling never blocked (§4.5).

        The record-transport log row is written here and linked from the attempt.
        """
        category = outcome.category
        fatal, stop_reason, error_code, error_reason_zh = self._outcome_error(outcome)
        with self._lock, self._conn:
            attempt = self._conn.execute(
                "SELECT * FROM hedge_open_attempt WHERE id = ?", (attempt_id,)
            ).fetchone()
            if attempt is None:
                raise UnknownTaskError(f"attempt {attempt_id}")
            task_id = attempt["task_id"]

            spot_status, spot_oid, spot_base, spot_quote, spot_fee, spot_fee_asset = (
                self._leg_final_fields(outcome.spot)
            )
            perp_status, perp_oid, perp_base, perp_quote, perp_fee, perp_fee_asset = (
                self._leg_final_fields(outcome.perp)
            )
            terminal_map = leg_terminal or {}
            for leg_name, oid, status, base, quote, fee_amt, fee_asset in (
                ("spot", spot_oid, spot_status, spot_base, spot_quote, spot_fee, spot_fee_asset),
                ("perp", perp_oid, perp_status, perp_base, perp_quote, perp_fee, perp_fee_asset),
            ):
                leg_outcome = outcome.spot if leg_name == "spot" else outcome.perp
                is_terminal = 1 if terminal_map.get(leg_name, True) else 0
                self._conn.execute(
                    "UPDATE hedge_open_leg SET order_id = ?, exchange_status = ?,"
                    " cumulative_base_qty = ?, cumulative_quote_amt = ?,"
                    " fee_amount = ?, fee_asset = ?,"
                    " error_code = ?, error_category = ?,"
                    " dispatch_state = ?, terminal = ?,"
                    " dispatched_at_us = COALESCE(dispatched_at_us, ?),"
                    " last_query_at_us = COALESCE(last_query_at_us, ?)"
                    " WHERE attempt_id = ? AND leg = ?",
                    (
                        oid,
                        status,
                        base,
                        quote,
                        fee_amt,
                        fee_asset,
                        leg_outcome.get("error_code"),
                        leg_outcome.get("error_category"),
                        D.LEG_TERMINAL_RECORDED if is_terminal else D.LEG_ACCEPTED_OR_QUERYING,
                        is_terminal,
                        now_us,
                        now_us,
                        attempt_id,
                        leg_name,
                    ),
                )

            log_cur = self._conn.execute(
                "INSERT INTO hedge_open_log"
                " (task_id, ts_us, attempt_id, kind, payload)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    task_id,
                    now_us,
                    attempt["attempt_uuid"],
                    "record_transport",
                    json.dumps(outcome.record_payload, ensure_ascii=False),
                ),
            )
            log_id = log_cur.lastrowid
            updated_task, pair_outcome, _ = self._apply_task_counters(
                task_id, category, outcome.exposure, now_us,
                fatal=fatal, stop_reason=stop_reason,
            )
            error_category = "fatal" if fatal else getattr(outcome, "error_category", None)
            self._conn.execute(
                "UPDATE hedge_open_attempt SET pair_outcome = ?, log_ref = ?,"
                " error_category = ?, error_code = ?, error_reason_zh = ?"
                " WHERE id = ?",
                (pair_outcome, log_id, error_category, error_code, error_reason_zh, attempt_id),
            )
            return updated_task

    def mark_leg_querying(
        self, attempt_id: int, leg: str, dispatch_state: str,
        order_id: str | None, now_us: int,
    ) -> None:
        """Record a live leg whose POST gave no usable verdict (timeout / 5xx /
        disconnect), or an accepted leg still filling (NEW/PARTIALLY_FILLED).

        The leg stays non-terminal and ``UNKNOWN_QUERYING`` (no orderId) or
        ``ACCEPTED_OR_QUERYING`` (orderId present, polling to FILLED) so the
        reconcile pass queries it by client ID — never resends the original POST
        (ADR-2). ``order_id`` is folded in only when present, so an accepted leg
        keeps its acceptance proof while it polls to a terminal fill.
        """
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE hedge_open_leg SET dispatch_state = ?,"
                " order_id = COALESCE(?, order_id),"
                " exchange_status = COALESCE(exchange_status, ?),"
                " dispatched_at_us = COALESCE(dispatched_at_us, ?),"
                " last_query_at_us = ? WHERE attempt_id = ? AND leg = ?",
                (
                    dispatch_state,
                    order_id,
                    D.LEG_NEW if order_id else None,
                    now_us,
                    now_us,
                    attempt_id,
                    leg,
                ),
            )

    def finalize_attempt(self, attempt_id: int, now_us: int) -> dict | None:
        """Resolve an attempt whose legs were left querying (reconcile path).

        Called after :meth:`resolve_leg_from_query` closes both legs of an attempt
        that was dispatched live with at least one ``UNKNOWN_QUERYING`` leg. It
        derives the pair's acceptance verdict from the two legs' final orderIds,
        applies the task counters + pause via :meth:`_apply_task_counters`, and
        stamps the attempt's ``pair_outcome``. Returns the updated task, or
        ``None`` when the attempt is already finalized or its legs are not both
        terminal yet (the reconcile pass retries later).
        """
        with self._lock, self._conn:
            attempt = self._conn.execute(
                "SELECT * FROM hedge_open_attempt WHERE id = ?", (attempt_id,)
            ).fetchone()
            if attempt is None:
                return None
            if attempt["pair_outcome"] is not None:
                return None
            legs = self._conn.execute(
                "SELECT * FROM hedge_open_leg WHERE attempt_id = ?", (attempt_id,)
            ).fetchall()
            if len(legs) != 2:
                return None
            if not all(row["terminal"] for row in legs):
                return None
            by_leg = {row["leg"]: row for row in legs}
            spot = by_leg.get("spot")
            perp = by_leg.get("perp")
            if spot is None or perp is None:
                return None
            spot_accepted = bool(spot["order_id"])
            perp_accepted = bool(perp["order_id"])
            if spot_accepted and perp_accepted:
                category = D.ATTEMPT_SUCCESS
            elif spot_accepted or perp_accepted:
                category = D.ATTEMPT_SINGLE_LEG_EXPOSURE
            else:
                category = D.ATTEMPT_FAILED
            exposure = None
            if category == D.ATTEMPT_SINGLE_LEG_EXPOSURE:
                exposure = self._exposure_from_legs(spot, perp, now_us)
            # Amendment rows 1–2: a reconciled leg carrying a fatal exchange code
            # (insufficient balance/margin/filter/etc.) stops the task. The fatal
            # flag may live on either leg's error_category column.
            fatal_leg = next(
                (row for row in legs if row["error_category"] == "fatal"), None
            )
            fatal = fatal_leg is not None
            stop_reason = D.STOP_REASON_EXCHANGE_FATAL if fatal else None
            error_code = fatal_leg["error_code"] if fatal_leg is not None else None
            error_reason_zh = D.stop_reason_zh(stop_reason) if fatal else None
            updated_task, pair_outcome, _ = self._apply_task_counters(
                attempt["task_id"], category, exposure, now_us,
                fatal=fatal, stop_reason=stop_reason,
            )
            error_category = "fatal" if fatal else None
            self._conn.execute(
                "UPDATE hedge_open_attempt SET pair_outcome = ?,"
                " error_category = ?, error_code = ?, error_reason_zh = ?"
                " WHERE id = ?",
                (pair_outcome, error_category, error_code, error_reason_zh, attempt_id),
            )
            return updated_task

    def settle_attempt_no_counters(self, attempt_id: int, now_us: int) -> bool:
        """Close an attempt whose legs are both terminal WITHOUT touching the
        task's counters, threshold or status (amendment 21 / Review-1 r3 P2-1).
        Used for a pair paused by a confirmed 429, where the consecutive-failure
        counter must NOT be consumed: the legs have already been resolved to
        terminal by the worker's own drain, and this only stamps the truthful
        ``pair_outcome`` (derived from the two legs' final orderIds, exactly as
        :meth:`finalize_attempt` does) plus the advisory single-leg
        ``leg_exposure``, so the in-flight guard clears and a resumed worker can
        reserve the next group. Returns True iff the attempt was settled here;
        ``False`` when it is gone, already settled, or its legs are not both
        terminal yet."""
        with self._lock, self._conn:
            attempt = self._conn.execute(
                "SELECT * FROM hedge_open_attempt WHERE id = ?", (attempt_id,)
            ).fetchone()
            if attempt is None or attempt["pair_outcome"] is not None:
                return False
            legs = self._conn.execute(
                "SELECT * FROM hedge_open_leg WHERE attempt_id = ?", (attempt_id,)
            ).fetchall()
            if len(legs) != 2 or not all(row["terminal"] for row in legs):
                return False
            by_leg = {row["leg"]: row for row in legs}
            spot = by_leg.get("spot")
            perp = by_leg.get("perp")
            if spot is None or perp is None:
                return False
            spot_accepted = bool(spot["order_id"])
            perp_accepted = bool(perp["order_id"])
            if spot_accepted and perp_accepted:
                category = D.ATTEMPT_SUCCESS
            elif spot_accepted or perp_accepted:
                category = D.ATTEMPT_SINGLE_LEG_EXPOSURE
            else:
                category = D.ATTEMPT_FAILED
            exposure = None
            if category == D.ATTEMPT_SINGLE_LEG_EXPOSURE:
                exposure = self._exposure_from_legs(spot, perp, now_us)
            _, pair_outcome, _ = self._apply_task_counters(
                attempt["task_id"], category, exposure, now_us,
                skip_counters=True,
            )
            self._conn.execute(
                "UPDATE hedge_open_attempt SET pair_outcome = ? WHERE id = ?",
                (pair_outcome, attempt_id),
            )
            return True

    def mark_attempt_rate_limited(self, attempt_id: int) -> None:
        """Stamp the per-attempt rate-limited flag (amendment 21 / Review-1 r3
        P1-1). The reconcile path reads this flag (not the sticky task-level
        ``pause_reason``) to decide whether a settled pair must skip the
        consecutive-failure counters via :meth:`settle_attempt_no_counters`."""
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE hedge_open_attempt SET rate_limited = 1 WHERE id = ?",
                (attempt_id,),
            )

    def set_worker_exit_reason(
        self, task_id: str, reason: str | None, now_us: int
    ) -> None:
        """Record / clear the last worker exit reason (Review-1 r3 P2-2). Stable
        machine enum from :data:`domain.ALL_WORKER_EXIT_REASONS`; ``None`` clears
        it (on (re-)entering RUNNING / spawning a worker)."""
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE hedge_open_task SET last_worker_exit_reason = ?,"
                " updated_at_us = ? WHERE id = ?",
                (reason, now_us, task_id),
            )

    @staticmethod
    def _exposure_from_legs(spot: sqlite3.Row, perp: sqlite3.Row, ts_us: int) -> dict | None:
        """Build the advisory leg_exposure doc for a reconciled single-leg attempt
        from the two closed leg rows (mirrors :func:`domain.build_leg_exposure`)."""
        spot_accepted = bool(spot["order_id"])
        perp_accepted = bool(perp["order_id"])
        if not (spot_accepted or perp_accepted):
            return None
        if spot_accepted and perp_accepted:
            return None
        leg_row = spot if spot_accepted else perp
        base = _num(leg_row["cumulative_base_qty"])
        quote = _num(leg_row["cumulative_quote_amt"])
        price = str(quote / base) if base > 0 else None
        return {
            "leg": "spot" if spot_accepted else "perp",
            "qty": str(base),
            "price": price,
            "ts": D.us_to_iso(ts_us),
        }

    def list_legs_for_attempt(self, attempt_id: int) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM hedge_open_leg WHERE attempt_id = ?"
                " ORDER BY leg ASC",
                (attempt_id,),
            ).fetchall()
            return [_row_to_leg(r) for r in rows]

    def list_attempts_for_task(self, task_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM hedge_open_attempt WHERE task_id = ?"
                " ORDER BY attempt_seq ASC, id ASC",
                (task_id,),
            ).fetchall()
            return [_row_to_attempt(r) for r in rows]

    def list_attempts_page(
        self, limit: int, cursor_ts: int | None, cursor_id: int | None,
    ) -> list[tuple[dict, dict | None, dict | None]]:
        """Newest-first attempt page with both legs attached (breakdown §3.4).

        Returns up to ``limit`` ``(attempt, spot_leg, perp_leg)`` triples; a leg
        is ``None`` when that leg row is absent. Covers PREPARED / QUERYING /
        resolved attempts alike: the attempt row exists from the
        durable-before-send transaction (before any log row), so an in-flight
        live pair still projects and the UI can show it mid-query. Cursor
        semantics mirror :meth:`list_logs_page` (``ts_us:row_id``) applied to
        ``(created_at_us, id)`` so the attempts page tracks the same read
        window. There is no independent attempts cursor on the response — the
        response's ``next_cursor`` still tracks logs (legacy contract); when the
        attempt set exceeds ``limit`` the older attempts are paged out silently
        only in the sense that this single read returns the newest ``limit``.
        """
        with self._lock:
            if cursor_ts is None:
                rows = self._conn.execute(
                    "SELECT * FROM hedge_open_attempt"
                    " ORDER BY created_at_us DESC, id DESC LIMIT ?",
                    (limit + 1,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM hedge_open_attempt"
                    " WHERE (created_at_us < ?) OR (created_at_us = ? AND id < ?)"
                    " ORDER BY created_at_us DESC, id DESC LIMIT ?",
                    (cursor_ts, cursor_ts, cursor_id, limit + 1),
                ).fetchall()
            out: list[tuple[dict, dict | None, dict | None]] = []
            for row in rows[:limit]:
                attempt = _row_to_attempt(row)
                leg_rows = self._conn.execute(
                    "SELECT * FROM hedge_open_leg WHERE attempt_id = ?"
                    " ORDER BY leg ASC",
                    (attempt["id"],),
                ).fetchall()
                legs = {r["leg"]: _row_to_leg(r) for r in leg_rows}
                out.append((attempt, legs.get("spot"), legs.get("perp")))
            return out

    def list_attempts_entries_page(
        self, limit: int,
        cur_ts: int | None, cur_rank: int | None, cur_id: int | None,
    ) -> list[tuple[dict, dict | None, dict | None]]:
        """Newest-first attempt page for the unified additive ``entries``
        stream (amendment 17). Independent of the legacy logs cursor.

        Ranked by the unified key ``(created_at_us, rank=0, id)`` DESC. The
        caller passes ``limit = entries_limit + 1`` so has-more is read from the
        unified stream. The three-part cursor ``(cur_ts, cur_rank, cur_id)`` is
        SHARED with :meth:`list_task_event_logs_page`; this source's rank is the
        constant 0, so a cursor that just passed an event (rank 1) at the same
        ts still admits same-ts attempts (they rank earlier in DESC order), and
        a cursor at an attempt (rank 0) admits only strictly older-tiebreak
        same-ts attempts. The expanded OR is the lexicographic ``<`` of the two
        three-part keys.
        """
        with self._lock:
            if cur_ts is None:
                rows = self._conn.execute(
                    "SELECT * FROM hedge_open_attempt"
                    " ORDER BY created_at_us DESC, id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM hedge_open_attempt"
                    " WHERE (created_at_us < ?)"
                    "    OR (created_at_us = ? AND 0 < ?)"
                    "    OR (created_at_us = ? AND 0 = ? AND id < ?)"
                    " ORDER BY created_at_us DESC, id DESC LIMIT ?",
                    (cur_ts, cur_ts, cur_rank, cur_ts, cur_rank, cur_id, limit),
                ).fetchall()
            out: list[tuple[dict, dict | None, dict | None]] = []
            for row in rows:
                attempt = _row_to_attempt(row)
                leg_rows = self._conn.execute(
                    "SELECT * FROM hedge_open_leg WHERE attempt_id = ?"
                    " ORDER BY leg ASC",
                    (attempt["id"],),
                ).fetchall()
                legs = {r["leg"]: _row_to_leg(r) for r in leg_rows}
                out.append((attempt, legs.get("spot"), legs.get("perp")))
            return out

    def list_non_terminal_legs(self) -> list[dict]:
        """Legs carrying an unresolved query obligation (DISPATCHING or
        UNKNOWN_QUERYING / ACCEPTED_OR_QUERYING without terminal fill). The
        reconcile pass queries each by client ID; restart recovery finds the
        same set after a crash (ADR-2 / breakdown §3.5)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM hedge_open_leg WHERE terminal = 0"
                " ORDER BY id ASC"
            ).fetchall()
            return [_row_to_leg(r) for r in rows]

    def list_non_terminal_legs_for_task(self, task_id: str) -> list[dict]:
        """Same unresolved-query selection as :meth:`list_non_terminal_legs` but
        scoped to ONE task's in-flight pair (amendment 21: a task-local worker
        queries only its own two legs; no global scan). The ``terminal = 0``
        predicate is the same leg-level obligation the global scan reads, and
        pairs with the ``prepare_attempt`` pair-level in-flight guard
        (``pair_outcome IS NULL``): a worker drains these legs to terminal, then
        finalizes the pair (clearing the in-flight guard) before reserving the
        next group."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM hedge_open_leg"
                " WHERE terminal = 0 AND attempt_id IN"
                " (SELECT id FROM hedge_open_attempt WHERE task_id = ?)"
                " ORDER BY id ASC",
                (task_id,),
            ).fetchall()
            return [_row_to_leg(r) for r in rows]

    def get_attempt(self, attempt_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM hedge_open_attempt WHERE id = ?", (attempt_id,)
            ).fetchone()
            return _row_to_attempt(row) if row is not None else None

    def resolve_leg_from_query(
        self,
        leg_id: int,
        *,
        exchange_status: str,
        order_id: str | None,
        base_qty: str,
        quote_amt: str,
        fee_amount: str | None,
        fee_asset: str | None,
        now_us: int,
        terminal: bool = True,
        error_code: str | None = None,
        error_category: str | None = None,
    ) -> None:
        """Apply one client-ID query result to a leg (breakdown §3.5). A terminal
        status (FILLED/REJECTED/EXPIRED/CANCELED) closes the leg (retaining any
        partial fill); NEW/PARTIALLY_FILLED keeps it querying
        (``terminal=False``); the caller re-derives the task counters via the
        attempt's pair outcome when both legs close. ``error_code``/``error_category``
        carry the exchange business code + its classification (fatal / absent /
        auth) so a fatal reconciled leg can stop the task."""
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE hedge_open_leg SET exchange_status = ?,"
                " order_id = COALESCE(?, order_id),"
                " cumulative_base_qty = ?, cumulative_quote_amt = ?,"
                " fee_amount = ?, fee_asset = ?,"
                " error_code = ?, error_category = ?,"
                " dispatch_state = ?, terminal = ?,"
                " last_query_at_us = ? WHERE id = ?",
                (
                    exchange_status,
                    order_id,
                    base_qty,
                    quote_amt,
                    fee_amount,
                    fee_asset,
                    error_code,
                    error_category,
                    D.LEG_TERMINAL_RECORDED if terminal else D.LEG_ACCEPTED_OR_QUERYING,
                    1 if terminal else 0,
                    now_us,
                    leg_id,
                ),
            )

    # ----------------------------------------------------------- fills + logs
    #
    # Round-1 legacy fill row + log (the record-transport wrote both). Retained
    # additively so existing rows stay readable; the real-API path persists the
    # attempt/leg tables above and writes its log row inside resolve_attempt.

    def insert_fill(
        self, task_id: str, attempt_id: str, outcome: AttemptOutcome, now_us: int
    ) -> dict:
        """Persist one attempt's legacy fill row + its record-transport log row.

        Retained for round-1 compatibility. The live/record dispatch path uses
        :meth:`prepare_attempt` + :meth:`resolve_attempt` (attempt/leg tables).
        """
        with self._lock, self._conn:
            log_cur = self._conn.execute(
                "INSERT INTO hedge_open_log"
                " (task_id, ts_us, attempt_id, kind, payload)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    task_id,
                    now_us,
                    attempt_id,
                    "record_transport",
                    json.dumps(outcome.record_payload, ensure_ascii=False),
                ),
            )
            log_id = log_cur.lastrowid
            cur = self._conn.execute(
                "INSERT INTO hedge_open_fill"
                " (task_id, ts_us, attempt_id, category,"
                "  spot_client_order_id, spot_order_id, spot_status,"
                "  spot_filled_qty, spot_avg_price,"
                "  perp_client_order_id, perp_order_id, perp_status,"
                "  perp_filled_qty, perp_avg_price, record_ref)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    task_id,
                    now_us,
                    attempt_id,
                    outcome.category,
                    outcome.spot.get("client_order_id"),
                    outcome.spot.get("order_id"),
                    outcome.spot.get("status", D.LEG_UNKNOWN),
                    str(outcome.spot.get("filled_qty", "0")),
                    outcome.spot.get("avg_price"),
                    outcome.perp.get("client_order_id"),
                    outcome.perp.get("order_id"),
                    outcome.perp.get("status", D.LEG_UNKNOWN),
                    str(outcome.perp.get("filled_qty", "0")),
                    outcome.perp.get("avg_price"),
                    log_id,
                ),
            )
            row = self._conn.execute(
                "SELECT * FROM hedge_open_fill WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
            return _row_to_fill(row)

    def list_fills_for_task(self, task_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM hedge_open_fill WHERE task_id = ?"
                " ORDER BY ts_us ASC, id ASC",
                (task_id,),
            ).fetchall()
            return [_row_to_fill(r) for r in rows]

    def list_logs_page(self, limit: int, cursor_ts: int | None, cursor_id: int | None):
        """Newest-first log page; returns ``(rows, has_more)``."""
        with self._lock:
            if cursor_ts is None:
                rows = self._conn.execute(
                    "SELECT * FROM hedge_open_log ORDER BY ts_us DESC, id DESC LIMIT ?",
                    (limit + 1,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM hedge_open_log"
                    " WHERE (ts_us < ?) OR (ts_us = ? AND id < ?)"
                    " ORDER BY ts_us DESC, id DESC LIMIT ?",
                    (cursor_ts, cursor_ts, cursor_id, limit + 1),
                ).fetchall()
            has_more = len(rows) > limit
            rows = rows[:limit]
            return [_row_to_log(r) for r in rows], has_more

    def get_log_payload(self, log_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM hedge_open_log WHERE id = ?", (log_id,)
            ).fetchone()
            if row is None:
                return None
            return json.loads(row["payload"])

    def stop_task_fatal(
        self, task_id: str, stop_reason: str, now_us: int,
    ) -> dict | None:
        """Set a task to the additive fatal-stop state (amendment rows 1–2 /
        I-4): ``status=stopped`` + nullable ``stop_reason``. Used when a fatal
        preflight fact or a fatal reconciled leg is detected. Final for that
        task; the operator corrects the cause and creates a NEW task. No counter
        churn — a stopped task never dispatches again. Returns the updated task
        or ``None`` when the task is gone."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE hedge_open_task SET status = ?, stop_reason = ?,"
                " updated_at_us = ? WHERE id = ?",
                (D.STATUS_STOPPED, stop_reason, now_us, task_id),
            )
            if cur.rowcount == 0:
                return None
            row = self._conn.execute(
                "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            return _row_to_task(row) if row is not None else None

    def pause_task(
        self, task_id: str, pause_reason: str, pause_reason_zh: str, now_us: int,
    ) -> dict | None:
        """Set a task to the amendment-21 task-local pause state:
        ``status=paused`` + ``pause_reason`` + ``pause_reason_zh`` (and clear any
        stale ``stop_reason``). Used by a task-local worker when a confirmed
        429/Retry-After or a confirmed insufficient balance/margin/available-
        quantity fact is observed for THIS task only (no cross-task linkage).
        Unlike :meth:`stop_task_fatal`, a pause is recoverable: the operator
        clears the cause and manually resumes the SAME task (Start/recover). No
        consecutive-failure counter churn. Returns the updated task or ``None``
        when the task is gone."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE hedge_open_task SET status = ?, pause_reason = ?,"
                " pause_reason_zh = ?, stop_reason = NULL, updated_at_us = ?"
                " WHERE id = ?",
                (D.STATUS_PAUSED, pause_reason, pause_reason_zh, now_us, task_id),
            )
            if cur.rowcount == 0:
                return None
            row = self._conn.execute(
                "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            return _row_to_task(row) if row is not None else None

    def record_task_event(
        self, task_id: str, kind: str, payload: dict, now_us: int,
    ) -> int:
        """Append a task-level event log row for the additive ``entries``
        projection (breakdown §5): fatal stop, threshold pause, pre-``orderId``
        preflight events, or a 429/Retry-After delay. ``attempt_id`` is NULL
        (these are task events, not per-attempt). Returns the new log row id."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO hedge_open_log"
                " (task_id, ts_us, attempt_id, kind, payload)"
                " VALUES (?, ?, NULL, ?, ?)",
                (task_id, now_us, kind, json.dumps(payload, ensure_ascii=False)),
            )
            return cur.lastrowid

    def list_task_event_logs(
        self, limit: int, kinds: tuple[str, ...] | None = None,
    ) -> list[dict]:
        """Newest-first task-event log rows of the given kinds (the additive
        ``entries`` projection, breakdown §5). ``kinds=None`` returns every
        task-event kind."""
        with self._lock:
            if kinds:
                placeholders = ",".join("?" for _ in kinds)
                rows = self._conn.execute(
                    f"SELECT * FROM hedge_open_log WHERE kind IN ({placeholders})"
                    " ORDER BY ts_us DESC, id DESC LIMIT ?",
                    (*kinds, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM hedge_open_log ORDER BY ts_us DESC, id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [_row_to_log(r) for r in rows]

    def list_task_event_logs_page(
        self, limit: int, kinds: tuple[str, ...] | None,
        cur_ts: int | None, cur_rank: int | None, cur_id: int | None,
    ) -> list[dict]:
        """Newest-first task-event page for the unified additive ``entries``
        stream (amendment 17). Ranked by ``(ts_us, rank=1, id)`` DESC; this
        source's rank is the constant 1. The shared three-part cursor is the
        same as :meth:`list_attempts_entries_page`: a cursor at an event (rank
        1) admits only strictly older-tiebreak same-ts events, and a cursor at
        an attempt (rank 0) admits NO same-ts events (they rank later in DESC
        order, i.e. come after that attempt in the page). ``kinds`` filters the
        event set; the caller passes ``limit = entries_limit + 1`` for has-more.
        """
        with self._lock:
            clauses: list[str] = []
            params: list = []
            if kinds:
                placeholders = ",".join("?" for _ in kinds)
                clauses.append(f"kind IN ({placeholders})")
                params.extend(kinds)
            if cur_ts is not None:
                clauses.append(
                    "((ts_us < ?) OR (ts_us = ? AND 1 < ?)"
                    " OR (ts_us = ? AND 1 = ? AND id < ?))"
                )
                params.extend([cur_ts, cur_ts, cur_rank, cur_ts, cur_rank, cur_id])
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = self._conn.execute(
                f"SELECT * FROM hedge_open_log{where}"
                " ORDER BY ts_us DESC, id DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
            return [_row_to_log(r) for r in rows]

    # ------------------------------------------------------------- positions

    def aggregate_positions(self) -> list[dict]:
        """Aggregate open positions from both the legacy fill rows and the
        attempt/leg rows (breakdown §3.4). avg = Σ(qty*price)/Σqty per leg.
        ``position_qty`` is the signed perp net (forward SELL -> negative short,
        reverse BUY -> positive long). Fields with no source this round stay
        ``"0"`` so the frozen Position JSON shape is stable.
        """
        with self._lock:
            fill_rows = self._conn.execute(
                "SELECT f.spot_status, f.spot_filled_qty, f.spot_avg_price,"
                " f.perp_status, f.perp_filled_qty, f.perp_avg_price,"
                " t.coin, t.direction"
                " FROM hedge_open_fill f JOIN hedge_open_task t ON t.id = f.task_id"
                " WHERE t.status != ?"
                " ORDER BY f.ts_us ASC, f.id ASC",
                (D.STATUS_DELETED,),
            ).fetchall()
            leg_rows = self._conn.execute(
                "SELECT l.leg, l.exchange_status, l.cumulative_base_qty,"
                " l.cumulative_quote_amt, t.coin, t.direction"
                " FROM hedge_open_leg l"
                " JOIN hedge_open_attempt a ON a.id = l.attempt_id"
                " JOIN hedge_open_task t ON t.id = a.task_id"
                " WHERE t.status != ?"
                " ORDER BY a.created_at_us ASC, l.id ASC",
                (D.STATUS_DELETED,),
            ).fetchall()

        buckets: dict[tuple[str, str], dict] = {}

        def _bucket(coin: str, direction: str) -> dict:
            return buckets.setdefault(
                (coin, direction),
                {
                    "spot_qty": Decimal(0),
                    "spot_notional": Decimal(0),
                    "perp_qty": Decimal(0),
                    "perp_notional": Decimal(0),
                    "position_qty": Decimal(0),
                },
            )

        for row in fill_rows:
            b = _bucket(row["coin"], row["direction"])
            if row["spot_status"] == D.LEG_FILLED:
                q = _num(row["spot_filled_qty"])
                b["spot_qty"] += q
                b["spot_notional"] += q * _num(row["spot_avg_price"])
            if row["perp_status"] == D.LEG_FILLED:
                q = _num(row["perp_filled_qty"])
                b["perp_qty"] += q
                b["perp_notional"] += q * _num(row["perp_avg_price"])
                sign = Decimal(-1) if row["direction"] == D.DIR_FORWARD else Decimal(1)
                b["position_qty"] += sign * q
        for row in leg_rows:
            # A-6: aggregate any leg with a POSITIVE actual fill regardless of the
            # literal exchange status — a CANCELED/PARTIALLY_FILLED/EXPIRED leg that
            # filled partially still contributes real base/quote to the position.
            if _num(row["cumulative_base_qty"]) <= 0:
                continue
            b = _bucket(row["coin"], row["direction"])
            q = _num(row["cumulative_base_qty"])
            notional = _num(row["cumulative_quote_amt"])
            if row["leg"] == "spot":
                b["spot_qty"] += q
                b["spot_notional"] += notional
            else:
                b["perp_qty"] += q
                b["perp_notional"] += notional
                sign = Decimal(-1) if row["direction"] == D.DIR_FORWARD else Decimal(1)
                b["position_qty"] += sign * q

        positions = []
        for (coin, direction), b in buckets.items():
            spot_avg = b["spot_notional"] / b["spot_qty"] if b["spot_qty"] > 0 else Decimal(0)
            perp_avg = b["perp_notional"] / b["perp_qty"] if b["perp_qty"] > 0 else Decimal(0)
            positions.append(
                {
                    "coin": coin,
                    "direction": direction,
                    "position_qty": D.fmt_decimal(b["position_qty"]),
                    "spot_avg": D.fmt_decimal(spot_avg),
                    "perp_avg": D.fmt_decimal(perp_avg),
                    "open_basis_rate": "0",
                    "price_pnl": "0",
                    "accrued_funding": "0",
                    "borrow_interest": "0",
                    "net_pnl": "0",
                }
            )
        positions.sort(key=lambda p: (p["coin"], p["direction"]))
        return positions

    # --------------------------------------------------------------- settings

    def get_settings(self) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM hedge_open_settings WHERE id = 1"
            ).fetchone()
            return {
                "start_gate": row["start_gate"],
                "executor_mode_snapshot": row["executor_mode_snapshot"],
                "interval_seconds": row["interval_seconds"],
                "interval_us": row["interval_us"],
                "rate_limit_order": row["rate_limit_order"],
                "version": row["version"],
                "updated_at_us": row["updated_at_us"],
            }

    def get_interval_us(self) -> int:
        with self._lock:
            return self._conn.execute(
                "SELECT interval_us FROM hedge_open_settings WHERE id = 1"
            ).fetchone()[0]

    def set_start_gate(self, enabled: bool, now_us: int) -> dict:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE hedge_open_settings SET start_gate = ?, version = version + 1,"
                " updated_at_us = ? WHERE id = 1",
                (1 if enabled else 0, now_us),
            )
            return self.get_settings()

    def set_rate_limit_order(self, rate_limit_order: int | None, now_us: int) -> dict:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE hedge_open_settings SET rate_limit_order = ?, version = version + 1,"
                " updated_at_us = ? WHERE id = 1",
                (rate_limit_order, now_us),
            )
            return self.get_settings()

    # ---------------------------------------------------------------- counts

    def count_tasks_by_status(self, status: str) -> int:
        with self._lock:
            return self._conn.execute(
                "SELECT COUNT(*) FROM hedge_open_task WHERE status = ?", (status,)
            ).fetchone()[0]
