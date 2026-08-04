"""SQLite idempotent ledger for the dual-ledger flow-log (design §14).

A modular-monolith local store, mirroring the connection/lock discipline of
``backend/borrow_tasks/store.py``: one connection
(``sqlite3.connect(path, check_same_thread=False)``) guarded by a single
``threading.RLock``; every public method takes the lock and each write group is
a short ``with self._conn:`` transaction.

Four tables (design §14): ``interest_rows``, ``um_income_rows``,
``flow_refresh_runs``, ``ledger_meta``. Amount columns are ``TEXT`` and store
the raw Binance decimal strings verbatim; **no query in this module ever
applies ``SUM`` / ``AVG`` / arithmetic to an amount column** — SQLite would
silently coerce TEXT to float and lose precision. Summaries are computed by
:mod:`backend.ledger_flow.domain` after rows are fetched into Python.

Transaction model (design §14 rule 5 / v1.2 F1):

- :meth:`LedgerStore.insert_run` is its **own** transaction and is never
  rolled back by a detail-write failure — a run that completed (even with a
  failed source) must leave a trace.
- :meth:`LedgerStore.commit_interest` and :meth:`LedgerStore.commit_income`
  are **each** a single transaction covering that source's detail rows AND its
  coverage metadata (+ appended gaps). A mid-transaction failure rolls back
  the whole source (no partial rows, no coverage advance); the other source's
  already-committed details are untouched.

The store is a dumb data layer: it does not decide "success run" semantics,
window intersection, or coverage-advance math — the service (task B) does.
All queries are empty-safe (return ``[]`` / ``None`` on an empty DB, never
raise), which the ``GET flow-log`` empty-state contract depends on
(design §13.2 rule 13).
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS interest_rows (
  tx_id             TEXT PRIMARY KEY,
  accrued_at_ms     INTEGER NOT NULL,
  asset             TEXT NOT NULL,
  raw_asset         TEXT,
  principal         TEXT,
  interest          TEXT,
  interest_rate     TEXT,
  type              TEXT,
  isolated_symbol   TEXT,
  first_seen_run_id INTEGER NOT NULL,
  first_seen_at_ms  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_interest_time ON interest_rows(accrued_at_ms);
CREATE INDEX IF NOT EXISTS idx_interest_seen ON interest_rows(first_seen_at_ms);

CREATE TABLE IF NOT EXISTS um_income_rows (
  income_type       TEXT NOT NULL,
  tran_id           TEXT NOT NULL,
  time_ms           INTEGER NOT NULL,
  symbol            TEXT,
  income            TEXT,
  asset             TEXT,
  info              TEXT,
  trade_id          TEXT,
  first_seen_run_id INTEGER NOT NULL,
  first_seen_at_ms  INTEGER NOT NULL,
  PRIMARY KEY (income_type, tran_id)
);
CREATE INDEX IF NOT EXISTS idx_income_time ON um_income_rows(time_ms);
CREATE INDEX IF NOT EXISTS idx_income_seen ON um_income_rows(first_seen_at_ms);

CREATE TABLE IF NOT EXISTS flow_refresh_runs (
  id                         INTEGER PRIMARY KEY AUTOINCREMENT,
  kind                       TEXT NOT NULL,
  started_at_ms              INTEGER NOT NULL,
  finished_at_ms             INTEGER,
  window_start_ms            INTEGER NOT NULL,
  window_end_ms              INTEGER NOT NULL,
  interest_status            TEXT NOT NULL,
  interest_error             TEXT,
  interest_fetched_row_count INTEGER NOT NULL DEFAULT 0,
  interest_new_row_count     INTEGER NOT NULL DEFAULT 0,
  income_status              TEXT NOT NULL,
  income_error               TEXT,
  income_fetched_row_count   INTEGER NOT NULL DEFAULT 0,
  income_new_row_count       INTEGER NOT NULL DEFAULT 0,
  truncated                  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_runs_finished ON flow_refresh_runs(finished_at_ms);

CREATE TABLE IF NOT EXISTS ledger_meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""

# ledger_meta key set (design §14 / v1.2 F4 — per-source coverage).
_META_SCHEMA_VERSION = "schema_version"
_META_INTEREST_START = "interest_coverage_start_ms"
_META_INTEREST_END = "interest_coverage_end_ms"
_META_INCOME_START = "income_coverage_start_ms"
_META_INCOME_END = "income_coverage_end_ms"
_META_COVERAGE_GAPS = "coverage_gaps"

_SCHEMA_VERSION_VALUE = "private-ledger/v2"


class LedgerStore:
    """The dual-ledger SQLite store. Path is injected (production
    ``data/ledger-flow.sqlite3``; tests use a temp file)."""

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
            # schema_version is a constant; upsert so reopening is idempotent.
            self._upsert_meta_locked(
                self._conn, _META_SCHEMA_VERSION, _SCHEMA_VERSION_VALUE
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------ #
    # internal meta helpers (run INSIDE the caller's locked transaction)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _upsert_meta_locked(conn: sqlite3.Connection, key: str, value: str) -> None:
        conn.execute(
            "INSERT INTO ledger_meta (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    @staticmethod
    def _get_meta_locked(conn: sqlite3.Connection, key: str) -> Optional[str]:
        row = conn.execute(
            "SELECT value FROM ledger_meta WHERE key = ?", (key,)
        ).fetchone()
        return None if row is None else row["value"]

    @staticmethod
    def _append_gaps_locked(
        conn: sqlite3.Connection, new_gaps: Optional[List[Dict[str, Any]]]
    ) -> None:
        """Append ``new_gaps`` to the shared ``coverage_gaps`` JSON list,
        de-duplicating by ``{source, start_ms, end_ms}``."""
        if not new_gaps:
            return
        raw = LedgerStore._get_meta_locked(conn, _META_COVERAGE_GAPS)
        gaps: List[Dict[str, Any]] = json.loads(raw) if raw else []
        for g in new_gaps:
            if g not in gaps:
                gaps.append(g)
        LedgerStore._upsert_meta_locked(conn, _META_COVERAGE_GAPS, json.dumps(gaps))

    # ------------------------------------------------------------------ #
    # run records (own transaction; never rolled back by detail failure)
    # ------------------------------------------------------------------ #
    def insert_run(self, run: Dict[str, Any]) -> int:
        """Insert a complete ``flow_refresh_runs`` record and return its ``id``.

        ``run`` keys (all required unless noted): ``kind``, ``started_at_ms``,
        ``finished_at_ms`` (may be ``None``), ``window_start_ms``,
        ``window_end_ms``, ``interest_status``, ``interest_error`` (nullable),
        ``interest_fetched_row_count``, ``interest_new_row_count``,
        ``income_status``, ``income_error`` (nullable),
        ``income_fetched_row_count``, ``income_new_row_count``, ``truncated``
        (bool → stored as 0/1). This is its own transaction, independent of any
        detail commit, so a source failure cannot erase the run's trace.
        """
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO flow_refresh_runs"
                " (kind, started_at_ms, finished_at_ms, window_start_ms,"
                "  window_end_ms, interest_status, interest_error,"
                "  interest_fetched_row_count, interest_new_row_count,"
                "  income_status, income_error, income_fetched_row_count,"
                "  income_new_row_count, truncated)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run["kind"],
                    run["started_at_ms"],
                    run.get("finished_at_ms"),
                    run["window_start_ms"],
                    run["window_end_ms"],
                    run["interest_status"],
                    run.get("interest_error"),
                    run.get("interest_fetched_row_count", 0),
                    run.get("interest_new_row_count", 0),
                    run["income_status"],
                    run.get("income_error"),
                    run.get("income_fetched_row_count", 0),
                    run.get("income_new_row_count", 0),
                    1 if run.get("truncated") else 0,
                ),
            )
            return int(cur.lastrowid)

    # ------------------------------------------------------------------ #
    # source commits: detail rows + coverage metadata, one transaction each
    # ------------------------------------------------------------------ #
    def commit_interest(
        self,
        *,
        rows: List[Dict[str, Any]],
        run_id: int,
        first_seen_at_ms: int,
        coverage_start_ms: Optional[int],
        coverage_end_ms: Optional[int],
        new_gaps: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, int]:
        """Idempotently insert interest rows and advance interest coverage.

        Rows use ``ON CONFLICT(tx_id) DO NOTHING`` so an already-stored row is
        **never overwritten** — ``first_seen_run_id`` / ``first_seen_at_ms``
        keep their first-insert values (otherwise overlap re-pulls would
        double-count in the delta). All rows in this call share
        ``first_seen_at_ms`` and ``run_id``.

        Within the SAME transaction: rows are inserted, ``interest_coverage_*``
        is upserted to the passed values (the service computes the
        advance/min), and ``new_gaps`` are appended. A failure rolls back the
        whole source; returns ``{"fetched_row_count", "new_row_count"}``.
        """
        with self._lock, self._conn:
            new = 0
            for r in rows:
                cur = self._conn.execute(
                    "INSERT INTO interest_rows"
                    " (tx_id, accrued_at_ms, asset, raw_asset, principal,"
                    "  interest, interest_rate, type, isolated_symbol,"
                    "  first_seen_run_id, first_seen_at_ms)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    " ON CONFLICT(tx_id) DO NOTHING",
                    (
                        r["tx_id"],
                        r["accrued_at_ms"],
                        r["asset"],
                        r.get("raw_asset"),
                        r.get("principal"),
                        r.get("interest"),
                        r.get("interest_rate"),
                        r.get("type"),
                        r.get("isolated_symbol"),
                        run_id,
                        first_seen_at_ms,
                    ),
                )
                new += cur.rowcount
            if coverage_start_ms is not None:
                self._upsert_meta_locked(
                    self._conn, _META_INTEREST_START, str(coverage_start_ms)
                )
            if coverage_end_ms is not None:
                self._upsert_meta_locked(
                    self._conn, _META_INTEREST_END, str(coverage_end_ms)
                )
            self._append_gaps_locked(self._conn, new_gaps)
            return {"fetched_row_count": len(rows), "new_row_count": new}

    def commit_income(
        self,
        *,
        rows: List[Dict[str, Any]],
        run_id: int,
        first_seen_at_ms: int,
        coverage_start_ms: Optional[int],
        coverage_end_ms: Optional[int],
        new_gaps: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, int]:
        """Idempotently insert UM income rows and advance income coverage.

        ``ON CONFLICT(income_type, tran_id) DO NOTHING``; same single-transaction
        guarantee as :meth:`commit_interest`.
        """
        with self._lock, self._conn:
            new = 0
            for r in rows:
                cur = self._conn.execute(
                    "INSERT INTO um_income_rows"
                    " (income_type, tran_id, time_ms, symbol, income, asset,"
                    "  info, trade_id, first_seen_run_id, first_seen_at_ms)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    " ON CONFLICT(income_type, tran_id) DO NOTHING",
                    (
                        r["income_type"],
                        r["tran_id"],
                        r["time_ms"],
                        r.get("symbol"),
                        r.get("income"),
                        r.get("asset"),
                        r.get("info"),
                        r.get("trade_id"),
                        run_id,
                        first_seen_at_ms,
                    ),
                )
                new += cur.rowcount
            if coverage_start_ms is not None:
                self._upsert_meta_locked(
                    self._conn, _META_INCOME_START, str(coverage_start_ms)
                )
            if coverage_end_ms is not None:
                self._upsert_meta_locked(
                    self._conn, _META_INCOME_END, str(coverage_end_ms)
                )
            self._append_gaps_locked(self._conn, new_gaps)
            return {"fetched_row_count": len(rows), "new_row_count": new}

    # ------------------------------------------------------------------ #
    # queries for the service (task B); all empty-safe
    # ------------------------------------------------------------------ #
    def query_interest_rows(
        self, start_ms: int, end_ms: int, *, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Interest rows in ``[start_ms, end_ms]``, ``(accrued_at_ms DESC,
        tx_id DESC)``. ``limit=None`` returns all (use for Decimal summary);
        pass a limit for the ≤500 display slice. Each row dict matches the
        :mod:`domain` interest shape plus ``first_seen_run_id`` /
        ``first_seen_at_ms``."""
        sql = (
            "SELECT * FROM interest_rows"
            " WHERE accrued_at_ms >= ? AND accrued_at_ms <= ?"
            " ORDER BY accrued_at_ms DESC, tx_id DESC"
        )
        params: list = [start_ms, end_ms]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def query_income_rows(
        self, start_ms: int, end_ms: int, *, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """UM income rows in ``[start_ms, end_ms]``, ``(time_ms DESC,
        income_type DESC, tran_id DESC)``. ``limit=None`` for summary."""
        sql = (
            "SELECT * FROM um_income_rows"
            " WHERE time_ms >= ? AND time_ms <= ?"
            " ORDER BY time_ms DESC, income_type DESC, tran_id DESC"
        )
        params: list = [start_ms, end_ms]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def query_interest_since(self, baseline_ms: int) -> List[Dict[str, Any]]:
        """Interest rows with ``first_seen_at_ms > baseline_ms`` (delta slice,
        ordered newest-seen first by ``first_seen_at_ms`` then ``accrued_at_ms``)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM interest_rows WHERE first_seen_at_ms > ?"
                " ORDER BY first_seen_at_ms DESC, accrued_at_ms DESC, tx_id DESC",
                (baseline_ms,),
            ).fetchall()
            return [dict(r) for r in rows]

    def query_income_since(self, baseline_ms: int) -> List[Dict[str, Any]]:
        """UM income rows with ``first_seen_at_ms > baseline_ms`` (delta slice)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM um_income_rows WHERE first_seen_at_ms > ?"
                " ORDER BY first_seen_at_ms DESC, time_ms DESC, income_type DESC,"
                " tran_id DESC",
                (baseline_ms,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_coverage(self) -> Dict[str, Any]:
        """Per-source coverage + the full recorded gaps list.

        Returns ``{"interest_start_ms", "interest_end_ms", "income_start_ms",
        "income_end_ms", "gaps"}`` where each ``*_ms`` is ``int | None``
        (``None`` when that source has never succeeded) and ``gaps`` is the
        list of ``{"source", "start_ms", "end_ms"}`` sorted by ``start_ms``
        ascending. The service filters gaps to the query window and caps at 20.
        """
        with self._lock:
            raw_gaps = self._get_meta_locked(self._conn, _META_COVERAGE_GAPS)
            gaps: List[Dict[str, Any]] = json.loads(raw_gaps) if raw_gaps else []
            gaps.sort(key=lambda g: (g.get("start_ms", 0), g.get("source", "")))
            return {
                "interest_start_ms": _opt_int(
                    self._get_meta_locked(self._conn, _META_INTEREST_START)
                ),
                "interest_end_ms": _opt_int(
                    self._get_meta_locked(self._conn, _META_INTEREST_END)
                ),
                "income_start_ms": _opt_int(
                    self._get_meta_locked(self._conn, _META_INCOME_START)
                ),
                "income_end_ms": _opt_int(
                    self._get_meta_locked(self._conn, _META_INCOME_END)
                ),
                "gaps": gaps,
            }

    def get_meta(self, key: str) -> Optional[str]:
        """Low-level read of a ``ledger_meta`` value (``None`` if absent)."""
        with self._lock:
            return self._get_meta_locked(self._conn, key)

    def recent_runs(self, n: int) -> List[Dict[str, Any]]:
        """The last ``n`` finished runs ordered by ``finished_at_ms`` DESC.
        Only rows with a non-null ``finished_at_ms`` are returned. Empty list
        on an empty DB. The store does NOT judge "success run" semantics — the
        service (task B) classifies by ``kind`` + both statuses."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM flow_refresh_runs WHERE finished_at_ms IS NOT NULL"
                " ORDER BY finished_at_ms DESC LIMIT ?",
                (n,),
            ).fetchall()
            return [dict(r) for r in rows]


def _opt_int(raw: Optional[str]) -> Optional[int]:
    """Parse a meta ms value (stored as TEXT) back to int; ``None`` if absent."""
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
