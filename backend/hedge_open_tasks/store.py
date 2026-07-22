"""SQLite-backed durable hedge-open store (10-design §2 / ADR-1).

A modular-monolith local store mirroring ``borrow_tasks.store``: one connection
guarded by a single RLock, short ``with self._conn:`` write transactions, and
the executor never invoked while a transaction or the lock is held. Internal
time is integer microseconds since epoch; money/quantities are decimal strings.

Tables (10-design §2.1-§2.3):
  hedge_open_task  — stage-1 Task fields + q_common/position_side_mode/leg_exposure
  hedge_open_fill  — one row per attempt, both legs' clientOrderId/orderId/qty/price
  hedge_open_log   — append-only record-transport log (would-send params, no secrets)
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
    updated_at_us         INTEGER NOT NULL
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
                "  creation_seq, created_at_us, updated_at_us)"
                " VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, NULL, ?, ?, ?, ?)",
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
        """List tasks, defaulting to exclude ``deleted`` unless requested.

        ``status_filter`` is the resolved SQL status from
        :func:`domain.filter_status_for_list`: ``None`` excludes deleted, a
        concrete status filters to it.
        """
        with self._lock:
            if status_filter is None:
                rows = self._conn.execute(
                    "SELECT * FROM hedge_open_task"
                    " WHERE status != ? ORDER BY creation_seq ASC, id ASC",
                    (D.STATUS_DELETED,),
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

    def clear_leg_exposure(self, task_id: str, now_us: int) -> dict:
        """Clear a recorded single-leg exposure (operator resumes after review)."""
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
        """Tasks the scheduler may dispatch: running, below target, no exposure."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM hedge_open_task"
                " WHERE status = ? AND leg_exposure IS NULL"
                "   AND success_count < target_n"
                " ORDER BY creation_seq ASC, id ASC",
                (D.STATUS_RUNNING,),
            ).fetchall()
            return [_row_to_task(r) for r in rows]

    def apply_attempt_outcome(
        self, task_id: str, outcome: AttemptOutcome, now_us: int
    ) -> dict:
        """Apply one attempt's outcome to the task counters + status (§6/§7).

        success -> success_count++; failed -> fail_count++; single-leg exposure
        sets ``leg_exposure`` (counters unchanged). The new status follows the
        domain resolve matrix (done / exposure_alert / paused-on->3 / running).
        """
        with self._lock, self._conn:
            task = _row_to_task(
                self._conn.execute(
                    "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
                ).fetchone()
            )
            if task is None:
                raise UnknownTaskError(task_id)
            success_count = task["success_count"]
            fail_count = task["fail_count"]
            leg_exposure_json = task["leg_exposure"]
            category = outcome.category
            if category == D.ATTEMPT_SUCCESS:
                success_count += 1
            elif category == D.ATTEMPT_FAILED:
                fail_count += 1
            elif category == D.ATTEMPT_SINGLE_LEG_EXPOSURE and outcome.exposure:
                leg_exposure_json = outcome.exposure
            new_status = D.resolve_status_after_attempt(
                task["status"], category, success_count, task["target_n"], fail_count
            )
            self._conn.execute(
                "UPDATE hedge_open_task SET success_count = ?, fail_count = ?,"
                " status = ?, leg_exposure = ?, updated_at_us = ? WHERE id = ?",
                (
                    success_count,
                    fail_count,
                    new_status,
                    json.dumps(leg_exposure_json) if leg_exposure_json is not None else None,
                    now_us,
                    task_id,
                ),
            )
            row = self._conn.execute(
                "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            return _row_to_task(row)

    # ----------------------------------------------------------- fills + logs

    def insert_fill(
        self, task_id: str, attempt_id: str, outcome: AttemptOutcome, now_us: int
    ) -> dict:
        """Persist one attempt's fill row + its record-transport log row.

        The fill row records both legs' actual state; the log row holds the
        would-send signed-request params (no secrets). The fill's ``record_ref``
        points at the log row id (10-design §2.2 ``raw_ref``).
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

    # ------------------------------------------------------------- positions

    def aggregate_positions(self) -> list[dict]:
        """Aggregate open positions from fills (stage-1 math, 10-design §2.2).

        avg = Σ(qty*price)/Σqty per leg. position_qty is the signed perp net
        (forward SELL -> negative short, reverse BUY -> positive long). Fields
        that need mark-price / funding / borrow data this round has no source
        for are reported as ``"0"`` so the frozen Position JSON shape is stable.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT f.spot_status, f.spot_filled_qty, f.spot_avg_price,"
                " f.perp_status, f.perp_filled_qty, f.perp_avg_price,"
                " t.coin, t.direction"
                " FROM hedge_open_fill f JOIN hedge_open_task t ON t.id = f.task_id"
                " WHERE t.status != ?"
                " ORDER BY f.ts_us ASC, f.id ASC",
                (D.STATUS_DELETED,),
            ).fetchall()

        def _num(value) -> Decimal:
            try:
                return Decimal(str(value)) if value is not None else Decimal(0)
            except InvalidOperation:
                return Decimal(0)

        buckets: dict[tuple[str, str], dict] = {}
        for row in rows:
            key = (row["coin"], row["direction"])
            bucket = buckets.setdefault(
                key,
                {
                    "spot_qty": Decimal(0),
                    "spot_notional": Decimal(0),
                    "perp_qty": Decimal(0),
                    "perp_notional": Decimal(0),
                    "position_qty": Decimal(0),
                },
            )
            if row["spot_status"] == D.LEG_FILLED:
                q = _num(row["spot_filled_qty"])
                bucket["spot_qty"] += q
                bucket["spot_notional"] += q * _num(row["spot_avg_price"])
            if row["perp_status"] == D.LEG_FILLED:
                q = _num(row["perp_filled_qty"])
                bucket["perp_qty"] += q
                bucket["perp_notional"] += q * _num(row["perp_avg_price"])
                # forward perp is a SELL (short -> negative); reverse is a BUY.
                sign = Decimal(-1) if row["direction"] == D.DIR_FORWARD else Decimal(1)
                bucket["position_qty"] += sign * q

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
        # Stable ordering for deterministic tests.
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


def _row_to_log(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "ts_us": row["ts_us"],
        "attempt_id": row["attempt_id"],
        "kind": row["kind"],
        "payload": row["payload"],
    }
