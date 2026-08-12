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
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from ..domain.normalize import resolve_spot_identity
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
    last_worker_exit_reason         TEXT,
    slippage_threshold_pct          TEXT,
    smooth_gate_seq                 INTEGER,
    smooth_gate_started_at_us       INTEGER,
    smooth_gate_force_requested     INTEGER NOT NULL DEFAULT 0
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
    created_at_us         INTEGER NOT NULL,
    smooth_pass_reason    TEXT
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
    cumulative_quote_amt TEXT,
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
CREATE TABLE IF NOT EXISTS hedge_open_raw_response (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id      INTEGER NOT NULL,
    leg             TEXT NOT NULL,
    client_order_id TEXT,
    source          TEXT NOT NULL,
    endpoint        TEXT NOT NULL,
    http_status     INTEGER,
    transport_error TEXT,
    business_code   TEXT,
    business_msg    TEXT,
    body            TEXT,
    body_truncated  INTEGER NOT NULL DEFAULT 0,
    captured_at_us  INTEGER NOT NULL,
    decisive        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_hedge_open_raw_attempt
    ON hedge_open_raw_response (attempt_id, leg, id);
CREATE TABLE IF NOT EXISTS hedge_open_cycle (
    id            TEXT PRIMARY KEY,      -- 周期 UUID（稳定关联键，不删除）
    symbol        TEXT NOT NULL,         -- 币种（带 USDT 后缀，与任务 coin 一致）
    direction     TEXT NOT NULL,         -- forward / reverse
    opened_at_us  INTEGER NOT NULL,      -- 周期起点 = 首次开仓派发时间（us）
    closed_at_us  INTEGER,               -- NULL=活跃中；全平观察后补写
    close_reason  TEXT,                  -- auto_close（功能三）/ manual_verify（人工纠偏）
    first_task_id TEXT,                  -- 起始任务 id（追溯）
    last_task_id  TEXT                   -- 最后贡献成功腿的任务 id（追溯）
);
CREATE INDEX IF NOT EXISTS idx_cycle_active
    ON hedge_open_cycle (symbol, direction, closed_at_us);
CREATE TABLE IF NOT EXISTS hedge_open_cycle_close_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id        TEXT NOT NULL,      -- 关联 hedge_open_cycle.id
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL,
    opened_at_us    INTEGER NOT NULL,   -- 周期起点（首次开仓派发时间）
    closed_at_us    INTEGER NOT NULL,   -- 平仓观察时间（近似）
    close_reason    TEXT,               -- auto_close / manual_verify（结算日志写入时记录）
    open_avg_price  TEXT,               -- 开单均价快照（周期成本基，关闭时现算写入）
    open_qty        TEXT,               -- 开单累计数量快照
    close_avg_price TEXT,               -- 平单均价：本轮有真值（close 任务成交加权）
    funding_fee     TEXT,               -- 周期内资金费合计（关闭时窗口现算）
    borrow_interest TEXT,               -- 周期内利息合计（资产维度近似）
    spot_open_avg   TEXT,               -- 现货买入均价（2026-08 补充：open 现货腿加权）
    spot_open_qty   TEXT,               -- 现货买入累计数量
    spot_close_avg  TEXT,               -- 现货卖出均价（close 现货腿加权）
    spot_close_qty  TEXT,               -- 现货卖出累计数量
    open_slippage   TEXT,               -- 开单两腿真实成交价差百分比（卖价高于买价为正）
    close_slippage  TEXT,               -- 平单两腿真实成交价差百分比（卖价高于买价为正）
    settled_at_us   INTEGER NOT NULL    -- 结算写入时间
);
CREATE INDEX IF NOT EXISTS idx_close_log_cycle ON hedge_open_cycle_close_log (cycle_id);
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
        "slippage_threshold_pct": row["slippage_threshold_pct"],
        "smooth_gate_seq": row["smooth_gate_seq"],
        "smooth_gate_started_at_us": row["smooth_gate_started_at_us"],
        "smooth_gate_force_requested": bool(row["smooth_gate_force_requested"]),
        # 功能三（2026-08）：任务类型（'open'=开仓 / 'close'=平仓）；旧行迁移默认 'open'。
        "task_type": row["task_type"],
        # 现货腿身份（2026-08-07）：建任务时固化的真值，三环只读不算。旧行为 None
        # （未回填），读取侧回退 resolve_spot_identity。
        "spot_symbol": row["spot_symbol"],
        "spot_base_asset": row["spot_base_asset"],
        "symbol_match_type": row["symbol_match_type"],
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
        "smooth_pass_reason": row["smooth_pass_reason"],
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
        "avg_price": row["avg_price"],
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


def _attach_status_transition(task: dict, old_status, new_status) -> dict:
    """Attach the committed (old_status, new_status) transition to a returned
    task dict (stage 2026-08-03-hedge-status-account-refresh-v1, design §5.2).

    The store reads the old status inside its SQL transaction, completes the
    write, commits, and surfaces the transition ADDITIVELY on the task dict it
    already returns — the existing task / bool return shapes are unchanged, so
    no call site needs repacking. The service reads this key AFTER commit to
    decide whether to fire the non-waiting cache-refresh command, and ONLY for a
    real ``running → 非 running``. It is a private internal key:
    :func:`service.task_to_doc` projects a fixed field set and never reads it, so
    it cannot reach the API response. ``None`` for either status (a conditional
    write that did not hit) yields a transition the service treats as zero-
    trigger (old is not running, or old/new unknown).
    """
    task["_status_transition"] = (old_status, new_status)
    return task


def _num(value) -> Decimal:
    """Quantity / comparison parser only. ``None`` or an unparseable value
    becomes ``Decimal(0)`` — correct for a quantity (a not-yet-filled leg
    genuinely has zero fill) or a magnitude comparison, but NEVER for a money
    figure, where a missing exchange value must stay unknown. Money figures
    (price / notional / quote / avg_price) use :func:`_num_or_none`."""
    try:
        return Decimal(str(value)) if value is not None else Decimal(0)
    except InvalidOperation:
        return Decimal(0)


def _num_or_none(value) -> Decimal | None:
    """Money-figure parser: preserve the unknown. ``None`` or an unparseable
    value returns ``None`` instead of ``Decimal(0)``, so a missing exchange
    figure can never become a fabricated zero. A real ``"0"`` from the exchange
    still parses to ``Decimal(0)``. Use this at every money site; :func:`_num`
    stays reserved for quantity and comparison callers — ``_num`` silently
    turning a missing figure into ``Decimal(0)`` was the root (S3) of the
    r4/r5/r6/r7 family this stage closes."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


class HedgeOpenStore:
    def __init__(self, db_path: str, *, executor_mode_snapshot: str = "disabled",
                 now_us: int = 0, repair_legacy_exposure_ts: bool = False):
        self._lock = threading.RLock()
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        self._migrate_now_us = now_us  # T1(e)/T5(d) §6 data-migration audit ts_us
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        with self._lock, self._conn:
            self._migrate(repair_legacy_exposure_ts=repair_legacy_exposure_ts)
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

    def _migrate(self, *, repair_legacy_exposure_ts: bool = False) -> None:
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
            # 功能三（2026-08）：任务类型——'open'=开仓（默认，现有行不回填）/ 'close'=平仓。
            ("task_type", "TEXT NOT NULL DEFAULT 'open'"),
            # 现货腿身份（2026-08-07 symbol-identity-unification 步骤①）：建任务时
            # 由 resolve_spot_identity 解析一次并固化，下单/平单/展示三环只读不算。
            # 存量行为 NULL，由 scripts/backfill-spot-identity.py 回填。
            ("spot_symbol", "TEXT"),
            ("spot_base_asset", "TEXT"),
            ("symbol_match_type", "TEXT"),
            ("slippage_threshold_pct", "TEXT"),
            ("smooth_gate_seq", "INTEGER"),
            ("smooth_gate_started_at_us", "INTEGER"),
            ("smooth_gate_force_requested", "INTEGER NOT NULL DEFAULT 0"),
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
            ("smooth_pass_reason", "TEXT"),
        )
        for col, decl in attempt_additions:
            if col not in attempt_cols:
                self._conn.execute(f"ALTER TABLE hedge_open_attempt ADD COLUMN {col} {decl}")
        # 持仓周期（2026-08 功能 2 阶段 1）：attempt 增加 cycle_id 列 + 索引。
        # 建表在 _SCHEMA（CREATE TABLE IF NOT EXISTS 随 executescript 幂等执行），
        # _migrate 只做 ADD COLUMN + CREATE INDEX IF NOT EXISTS，不重复建表
        # （docs/planning/hedge-open-cycle-stage2-cycle-dev.md §3.2 核对点）。
        if "cycle_id" not in attempt_cols:
            self._conn.execute(
                "ALTER TABLE hedge_open_attempt ADD COLUMN cycle_id TEXT"
            )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_attempt_cycle"
            " ON hedge_open_attempt (cycle_id)"
        )
        leg_cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(hedge_open_leg)")}
        leg_additions = (
            ("error_code", "TEXT"),
            ("error_category", "TEXT"),
            # Part B（Human 2026-07-31）：交易所返回的权威 avgPrice 原话落库——只记观测值，
            # 不推导、不替 cumulative_quote_amt 的 NULL 契约。既有行该列为 NULL。
            ("avg_price", "TEXT"),
        )
        for col, decl in leg_additions:
            if col not in leg_cols:
                self._conn.execute(f"ALTER TABLE hedge_open_leg ADD COLUMN {col} {decl}")
        # T1 §1(d)/§7: ``cumulative_quote_amt`` was NOT NULL DEFAULT '0' — a missing
        # figure stored indistinguishably from a true zero (the T1 defect). SQLite
        # cannot relax NOT NULL in place, so rebuild the leg table inside this
        # transaction (CREATE new -> INSERT SELECT -> DROP -> RENAME -> re-index).
        # The PRAGMA notnull probe guards idempotency: runs once on legacy DBs,
        # no-op once the column is already nullable.
        leg_quote_notnull = next(
            (r["notnull"] for r in self._conn.execute(
                "PRAGMA table_info(hedge_open_leg)") if r["name"] == "cumulative_quote_amt"),
            0,
        )
        if leg_quote_notnull:
            self._conn.execute(
                "CREATE TABLE hedge_open_leg__new ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " attempt_id INTEGER NOT NULL,"
                " leg TEXT NOT NULL,"
                " client_order_id TEXT NOT NULL UNIQUE,"
                " endpoint TEXT NOT NULL,"
                " request_shape TEXT NOT NULL,"
                " dispatch_state TEXT NOT NULL,"
                " order_id TEXT,"
                " exchange_status TEXT,"
                " cumulative_base_qty TEXT NOT NULL DEFAULT '0',"
                " cumulative_quote_amt TEXT,"
                " fee_amount TEXT,"
                " fee_asset TEXT,"
                " error_code TEXT,"
                " error_category TEXT,"
                " dispatched_at_us INTEGER,"
                " last_query_at_us INTEGER,"
                " terminal INTEGER NOT NULL DEFAULT 0)"
            )
            self._conn.execute(
                "INSERT INTO hedge_open_leg__new"
                " (id, attempt_id, leg, client_order_id, endpoint, request_shape,"
                "  dispatch_state, order_id, exchange_status, cumulative_base_qty,"
                "  cumulative_quote_amt, fee_amount, fee_asset, error_code,"
                "  error_category, dispatched_at_us, last_query_at_us, terminal)"
                " SELECT id, attempt_id, leg, client_order_id, endpoint, request_shape,"
                "  dispatch_state, order_id, exchange_status, cumulative_base_qty,"
                "  cumulative_quote_amt, fee_amount, fee_asset, error_code,"
                "  error_category, dispatched_at_us, last_query_at_us, terminal"
                " FROM hedge_open_leg"
            )
            self._conn.execute("DROP TABLE hedge_open_leg")
            self._conn.execute("ALTER TABLE hedge_open_leg__new RENAME TO hedge_open_leg")
            self._conn.execute(
                "CREATE INDEX idx_hedge_open_leg_attempt"
                " ON hedge_open_leg (attempt_id, leg ASC)"
            )
            self._conn.execute(
                "CREATE INDEX idx_hedge_open_leg_query"
                " ON hedge_open_leg (terminal, dispatch_state)"
            )
        # T3 (review-1 r5 P1): hedge_open_raw_response gains a ``decisive`` flag
        # marking rows holding one of the four conclusive verdicts 00-task.md §T3
        # requires persisted (a fill, a confirmed rejection, a confirmed absent
        # order, or a rate-limit signal). A decisive row is never replaced — first
        # decisive wins — and a later decisive response replaces only a prior
        # non-decisive placeholder (NEW / PARTIALLY_FILLED). Additive ALTER guard ->
        # idempotent; legacy rows backfill to 0 (non-decisive), the honest default
        # for rows whose verdict shape this migration cannot reconstruct.
        raw_cols = {
            r["name"] for r in self._conn.execute("PRAGMA table_info(hedge_open_raw_response)")
        }
        if "decisive" not in raw_cols:
            self._conn.execute(
                "ALTER TABLE hedge_open_raw_response"
                " ADD COLUMN decisive INTEGER NOT NULL DEFAULT 0"
            )
        # 功能三（2026-08 补充）：close_log 加现货买/卖均价 4 列（历史仓位页现货列）。
        # 幂等 ADD COLUMN；已存在的结算日志行现货列为 NULL（回填见修正脚本）。
        clog_cols = {
            r["name"] for r in self._conn.execute("PRAGMA table_info(hedge_open_cycle_close_log)")
        }
        for col, decl in (
            ("spot_open_avg", "TEXT"),
            ("spot_open_qty", "TEXT"),
            ("spot_close_avg", "TEXT"),
            ("spot_close_qty", "TEXT"),
            ("open_slippage", "TEXT"),
            ("close_slippage", "TEXT"),
        ):
            if col not in clog_cols:
                self._conn.execute(
                    f"ALTER TABLE hedge_open_cycle_close_log ADD COLUMN {col} {decl}"
                )
        # 功能三（2026-08）：平仓闸门独立于开单闸门，默认开（Human 已拍板）。
        settings_cols = {
            r["name"] for r in self._conn.execute("PRAGMA table_info(hedge_open_settings)")
        }
        if "close_gate" not in settings_cols:
            self._conn.execute(
                "ALTER TABLE hedge_open_settings"
                " ADD COLUMN close_gate INTEGER NOT NULL DEFAULT 1"
            )
        # T5(d) M2 (§6): a leg_exposure ts rendered as the 1970 epoch (a forgotten
        # 0) is rewritten to the accepting leg's dispatched_at_us ISO — the real
        # moment of that single-leg event (within ~1s). price stays null (unknown —
        # the historical avg_price was never stored and cannot be reconstructed).
        # Idempotent on the ts shape. D6: this row-mutating repair is opt-in
        # (``repair_legacy_exposure_ts``); the additive DDL above stays automatic
        # (a database must be usable). No production caller passes the flag —
        # production was migrated 2026-07-28, so a default construction never
        # rewrites a row (the 2026-07-28 silent-rewrite incident).
        if repair_legacy_exposure_ts:
            epoch_ts = "1970-01-01T00:00:00.000000Z"
            m2_rows = self._conn.execute(
                "SELECT id, leg_exposure FROM hedge_open_task"
                " WHERE leg_exposure LIKE ?",
                (f"%{epoch_ts}%",),
            ).fetchall()
            for row in m2_rows:
                task_id = row["id"]
                try:
                    expo = json.loads(row["leg_exposure"])
                except (TypeError, ValueError):
                    continue
                if not isinstance(expo, dict) or expo.get("ts") != epoch_ts:
                    continue
                leg_name = expo.get("leg")
                if leg_name not in ("spot", "perp"):
                    continue
                leg_row = self._conn.execute(
                    "SELECT l.dispatched_at_us FROM hedge_open_leg l"
                    " JOIN hedge_open_attempt a ON a.id = l.attempt_id"
                    " WHERE a.task_id = ? AND l.leg = ?"
                    " AND l.dispatched_at_us IS NOT NULL"
                    " ORDER BY l.dispatched_at_us DESC LIMIT 1",
                    (task_id, leg_name),
                ).fetchone()
                if leg_row is None:
                    continue
                real_ts = D.us_to_iso(leg_row["dispatched_at_us"])
                expo["ts"] = real_ts
                self._conn.execute(
                    "UPDATE hedge_open_task SET leg_exposure = ? WHERE id = ?",
                    (json.dumps(expo, ensure_ascii=False), task_id),
                )
                self._conn.execute(
                    "INSERT INTO hedge_open_log"
                    " (task_id, ts_us, attempt_id, kind, payload)"
                    " VALUES (?, ?, NULL, ?, ?)",
                    (
                        task_id, self._migrate_now_us, "data_migration",
                        json.dumps(
                            {
                                "table": "hedge_open_task", "row_id": task_id,
                                "field": "leg_exposure.ts",
                                "before": epoch_ts, "after": real_ts,
                                "reason": "T5(d): 1970 exposure ts -> accepting leg dispatched_at_us",
                            },
                            ensure_ascii=False,
                        ),
                    ),
                )
        # BK-T3-001's interval backfill was REMOVED here (Human decision
        # 2026-08-02). It rewrote a row unconditionally on every construction,
        # violating DEC-2026-07-30-003 ("a default construction never rewrites a
        # row"), and that is what silently changed the running production
        # database on 2026-08-01 (BK-T3-002). It is not needed any more:
        # get_interval_us() now reads D.DEFAULT_INTERVAL_US directly, so every
        # database — old, new or restored from backup — uses the current cadence
        # without anyone writing to it.

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
        task_type: str = D.TASK_TYPE_OPEN,
        spot_symbol: str | None = None,
        spot_base_asset: str | None = None,
        symbol_match_type: str | None = None,
        initial_status: str = D.STATUS_RUNNING,
        initial_pause_reason: str | None = None,
        initial_pause_reason_zh: str | None = None,
        slippage_threshold_pct: str | None = None,
    ) -> dict:
        with self._lock, self._conn:
            creation_seq = self._conn.execute(
                "SELECT COALESCE(MAX(creation_seq), 0) + 1 FROM hedge_open_task"
            ).fetchone()[0]
            # Open tasks keep the historical runnable default. Close creation may
            # atomically opt into ``paused`` + its display reason so there is
            # never an intermediate runnable row for tick/restart recovery to see.
            self._conn.execute(
                "INSERT INTO hedge_open_task"
                " (id, coin, direction, mode, single_amount, target_n,"
                "  success_count, fail_count, status, q_common,"
                "  position_side_mode, leg_exposure, preflight_snapshot,"
                "  creation_seq, created_at_us, updated_at_us,"
                "  scheduled_attempt_count, accepted_pair_count,"
                "  consecutive_submission_failures, failure_pause_threshold,"
                "  pause_reason, pause_reason_zh, task_type,"
                "  spot_symbol, spot_base_asset, symbol_match_type,"
                "  slippage_threshold_pct)"
                " VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, NULL, ?, ?, ?, ?,"
                "         0, 0, 0, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    task_id,
                    coin,
                    direction,
                    mode,
                    single_amount,
                    target_n,
                    initial_status,
                    q_common,
                    position_side_mode,
                    json.dumps(preflight_snapshot) if preflight_snapshot is not None else None,
                    creation_seq,
                    now_us,
                    now_us,
                    failure_pause_threshold,
                    initial_pause_reason,
                    initial_pause_reason_zh,
                    task_type,
                    spot_symbol,
                    spot_base_asset,
                    symbol_match_type,
                    slippage_threshold_pct,
                ),
            )
            row = self._conn.execute(
                "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            return _row_to_task(row)

    def backfill_spot_identity(self) -> dict:
        """为身份三列为空的存量任务回填 :func:`resolve_spot_identity` 的结果。

        幂等：只写 ``spot_symbol`` 为 NULL 或空串的行，已固化的身份是该任务的历史真值，
        绝不覆盖（表若变动由 ``check-spot-symbol-map.py --verify`` 报 STALE +
        人工处理，不在此处静默改写）。返回 ``{"updated": n, "total": n}``。
        """
        with self._lock, self._conn:
            rows = self._conn.execute(
                "SELECT id, coin FROM hedge_open_task"
                " WHERE spot_symbol IS NULL OR spot_symbol = ''"
            ).fetchall()
            for row in rows:
                spot_symbol, spot_base, match_type = resolve_spot_identity(row["coin"])
                self._conn.execute(
                    "UPDATE hedge_open_task"
                    " SET spot_symbol = ?, spot_base_asset = ?, symbol_match_type = ?"
                    " WHERE id = ?",
                    (spot_symbol, spot_base, match_type, row["id"]),
                )
            total = self._conn.execute(
                "SELECT COUNT(*) FROM hedge_open_task"
            ).fetchone()[0]
        return {"updated": len(rows), "total": total}

    def get_task(self, task_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            return _row_to_task(row) if row is not None else None

    def list_tasks(self, status_filter: str | None = None) -> list[dict]:
        """List tasks per the resolved status filter from
        :func:`domain.filter_status_for_list` (frozen §3.1).

        UI / API listing is newest-first (``creation_seq DESC``). Scheduler
        eligibility uses its own ASC query and is unchanged.
        """
        with self._lock:
            if status_filter is None:
                rows = self._conn.execute(
                    "SELECT * FROM hedge_open_task"
                    " WHERE status != ? ORDER BY creation_seq DESC, id DESC",
                    (D.STATUS_DELETED,),
                ).fetchall()
            elif status_filter == D.LIST_ALL:
                rows = self._conn.execute(
                    "SELECT * FROM hedge_open_task"
                    " ORDER BY creation_seq DESC, id DESC",
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM hedge_open_task WHERE status = ?"
                    " ORDER BY creation_seq DESC, id DESC",
                    (status_filter,),
                ).fetchall()
            return [_row_to_task(r) for r in rows]

    def set_task_status(self, task_id: str, status: str, now_us: int) -> dict:
        with self._lock, self._conn:
            # Capture the pre-update status inside the transaction so the service
            # can judge a real running → 非 running after commit (design §5.2).
            prev = self._conn.execute(
                "SELECT status FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            old_status = prev["status"] if prev is not None else None
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
                    "UPDATE hedge_open_task SET status = ?,"
                    " smooth_gate_seq = NULL, smooth_gate_started_at_us = NULL,"
                    " smooth_gate_force_requested = 0, updated_at_us = ? WHERE id = ?",
                    (status, now_us, task_id),
                )
            if cur.rowcount == 0:
                raise UnknownTaskError(task_id)
            row = self._conn.execute(
                "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            return _attach_status_transition(_row_to_task(row), old_status, status)

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

    def open_smooth_gate(
        self, task_id: str, gate_seq: int, started_at_us: int,
    ) -> dict | None:
        with self._lock, self._conn:
            task = self._conn.execute(
                "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            if (
                task is None
                or task["task_type"] != D.TASK_TYPE_OPEN
                or task["mode"] != D.MODE_SMOOTH
                or task["status"] != D.STATUS_RUNNING
                or task["scheduled_attempt_count"] >= task["target_n"]
                or gate_seq != task["scheduled_attempt_count"] + 1
            ):
                return None
            in_flight = self._conn.execute(
                "SELECT 1 FROM hedge_open_attempt"
                " WHERE task_id = ? AND pair_outcome IS NULL LIMIT 1",
                (task_id,),
            ).fetchone()
            if in_flight is not None:
                return None
            current_seq = task["smooth_gate_seq"]
            if current_seq is not None and current_seq != gate_seq:
                return None
            if current_seq is None:
                self._conn.execute(
                    "UPDATE hedge_open_task SET smooth_gate_seq = ?,"
                    " smooth_gate_started_at_us = ?, smooth_gate_force_requested = 0,"
                    " updated_at_us = ? WHERE id = ?",
                    (gate_seq, started_at_us, started_at_us, task_id),
                )
            row = self._conn.execute(
                "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            return _row_to_task(row)

    def force_smooth_gate(
        self, task_id: str, gate_seq: int, now_us: int,
    ) -> dict | None:
        with self._lock, self._conn:
            task = self._conn.execute(
                "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            if (
                task is None
                or task["task_type"] != D.TASK_TYPE_OPEN
                or task["mode"] != D.MODE_SMOOTH
                or task["status"] != D.STATUS_RUNNING
                or task["scheduled_attempt_count"] >= task["target_n"]
                or task["smooth_gate_seq"] != gate_seq
            ):
                return None
            in_flight = self._conn.execute(
                "SELECT 1 FROM hedge_open_attempt"
                " WHERE task_id = ? AND pair_outcome IS NULL LIMIT 1",
                (task_id,),
            ).fetchone()
            if in_flight is not None:
                return None
            self._conn.execute(
                "UPDATE hedge_open_task SET smooth_gate_force_requested = 1,"
                " updated_at_us = ? WHERE id = ?",
                (now_us, task_id),
            )
            row = self._conn.execute(
                "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            return _row_to_task(row)

    def clear_smooth_gate(self, task_id: str, now_us: int) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE hedge_open_task SET smooth_gate_seq = NULL,"
                " smooth_gate_started_at_us = NULL, smooth_gate_force_requested = 0,"
                " updated_at_us = ? WHERE id = ? AND status = ?",
                (now_us, task_id, D.STATUS_RUNNING),
            )

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
        spot_endpoint: str,
        perp_client_order_id: str,
        perp_request_shape: dict,
        now_us: int,
        *,
        expected_gate_seq: int | None = None,
        smooth_pass_reason: str | None = None,
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
                "SELECT status, scheduled_attempt_count, target_n, coin, direction,"
                " mode, smooth_gate_seq"
                " FROM hedge_open_task"
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
            if task["mode"] == D.MODE_SMOOTH:
                if (
                    expected_gate_seq is None
                    or expected_gate_seq != task["smooth_gate_seq"]
                    or smooth_pass_reason not in D.ALL_SMOOTH_PASS_REASONS
                ):
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
            # 持仓周期分配（stage2 §3.4）：cycle 写入与 attempt 写入同一事务。
            # 有活跃周期（closed_at_us IS NULL）→ 复用其 id；无 → 新建
            # （opened_at_us = 本次派发时间 now_us，first/last_task_id = 当前
            # task_id）。用内部无锁版，不嵌套 ``with self._conn:``。
            cycle = self._get_active_cycle_locked(task["coin"], task["direction"])
            if cycle is None:
                cycle = self._create_cycle_locked(
                    task["coin"], task["direction"], now_us, task_id,
                )
            cur = self._conn.execute(
                "INSERT INTO hedge_open_attempt"
                " (task_id, attempt_uuid, attempt_seq, direction, q_common,"
                "  preflight_fingerprint, position_side_mode, pair_outcome,"
                "  log_ref, created_at_us, cycle_id, smooth_pass_reason)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?)",
                (
                    task_id,
                    attempt_uuid,
                    seq,
                    direction,
                    q_common,
                    json.dumps(preflight_fingerprint, ensure_ascii=False),
                    position_side_mode or D.POS_MODE_BOTH,
                    now_us,
                    cycle["id"],
                    smooth_pass_reason if task["mode"] == D.MODE_SMOOTH else None,
                ),
            )
            attempt_id = cur.lastrowid
            self._conn.execute(
                "INSERT INTO hedge_open_leg"
                " (attempt_id, leg, client_order_id, endpoint, request_shape,"
                "  dispatch_state, order_id, exchange_status,"
                "  cumulative_base_qty, cumulative_quote_amt, fee_amount,"
                "  fee_asset, dispatched_at_us, last_query_at_us, terminal)"
                " VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, '0', NULL, NULL, NULL,"  # money-zero-ok: '0' seeds cumulative_base_qty (qty, NOT NULL DEFAULT '0', non-goal §3); cumulative_quote_amt is NULL (D7), not a fabricated money zero
                "         NULL, NULL, 0)",
                (
                    attempt_id,
                    "spot",
                    spot_client_order_id,
                    spot_endpoint,
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
                " VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, '0', NULL, NULL, NULL,"  # money-zero-ok: '0' seeds cumulative_base_qty (qty, NOT NULL DEFAULT '0', non-goal §3); cumulative_quote_amt is NULL (D7), not a fabricated money zero
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
                " scheduled_attempt_count + 1, smooth_gate_seq = NULL,"
                " smooth_gate_started_at_us = NULL, smooth_gate_force_requested = 0,"
                " updated_at_us = ? WHERE id = ?",
                (now_us, task_id),
            )
            row = self._conn.execute(
                "SELECT * FROM hedge_open_attempt WHERE id = ?", (attempt_id,)
            ).fetchone()
            return _row_to_attempt(row)

    def _leg_final_fields(
        self, leg_outcome: dict
    ) -> tuple[str, str | None, str, str | None, str | None, str | None, str | None]:
        """Return ``(exchange_status, order_id, base_qty, quote_amt, fee_amount,
        fee_asset, avg_price)`` for one resolved leg outcome (A-6 + T1 §1(d) + Part B).

        ``quote_amt`` follows the T1 NULL contract — NULL = unknown (the response
        carried no figure), "0" = a real zero fill, never a missing figure coerced
        to 0:

        * a present ``cumulative_quote`` is stored verbatim (a real figure,
          including a true "0");
        * a MISSING ``cumulative_quote`` (None/empty) is NULL (unknown) — even
          when ``filled_qty`` and ``avg_price`` are present, no figure is derived
          (review-1 r4, 2026-07-29);
        * an unparseable present value is also NULL.

        The old ``not in (None, "", "0", 0)`` check that treated a literal "0" as
        missing was the T1 defect itself and is gone. ``base_qty`` (filled_qty)
        keeps the "0" default — an accepted not-yet-filled leg genuinely executes
        zero. Fee figures pass through verbatim.
        """
        status = leg_outcome.get("status") or D.LEG_UNKNOWN
        order_id = leg_outcome.get("order_id")
        filled_qty = _num(leg_outcome.get("filled_qty"))
        cumulative_quote = leg_outcome.get("cumulative_quote")
        fee_amount = leg_outcome.get("fee_amount")
        fee_asset = leg_outcome.get("fee_asset")
        # avg_price：交易所返回的原话（执行器 _avg_price_decimal 已把 "0"/缺失映射为 None），
        # 原样透传，不推导、不替 quote 的 NULL 契约（Part B，Human 2026-07-31）。
        avg_price = leg_outcome.get("avg_price")
        quote: Decimal | None
        if cumulative_quote is None or cumulative_quote == "":
            # Missing figure: NULL (unknown). Review-1 r4 (2026-07-29) removed the
            # filled_qty * avg_price derivation — the column records what the
            # exchange said, never a substituted figure.
            quote = None
        else:
            try:
                quote = Decimal(str(cumulative_quote))
            except InvalidOperation:
                # Unparseable present value: unknown, never a coerced 0.
                quote = None
        return (
            status,
            order_id,
            str(filled_qty),
            str(quote) if quote is not None else None,
            str(fee_amount) if fee_amount is not None else None,
            str(fee_asset) if fee_asset is not None else None,
            avg_price,
        )

    def _apply_task_counters(
        self, task_id: str, category: str, exposure: dict | None, now_us: int,
        *, fatal: bool = False, stop_reason: str | None = None,
        skip_counters: bool = False, suppress_done: bool = False,
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

        fix-runtime-seam-scan: ``suppress_done`` keeps a just-settled attempt from
        pushing the task to ``done`` when the settlement is a pause-class fact
        (insufficient funds / collateral cap) whose task-local pause is applied
        right after this settlement — a ``done`` here would make the conditional
        pause write (running/paused only) miss and silently drop the pause
        semantics (amendment 21: an insufficient fact pauses THIS task, no
        threshold wait). Counters still advance; only the auto-done promotion is
        suppressed so the pause can land.
        """
        task = _row_to_task(
            self._conn.execute(
                "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
        )
        # Capture the pre-update status (design §5.2) so the returned task carries
        # the real (old, new) transition. resolve_attempt / finalize_attempt
        # surface it to the service; settle_attempt_no_counters runs with
        # skip_counters=True so new_status stays == old (a zero-trigger the
        # service correctly ignores), and it discards the task anyway.
        old_status = task["status"]
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
            # R2-F1 (user authorization 28 §2.1): a non-rate-limited single_leg
            # counts toward the consecutive-submission-failure brake exactly like
            # a confirmed failure. The exposure is still recorded; below the
            # threshold the task keeps running (it is never frozen on one
            # outcome — breakdown §4.5), but the count now advances so the brake
            # can no longer be bypassed by always landing on exactly one
            # accepted leg.
            new_fail = task["fail_count"] + 1
            new_consecutive = task["consecutive_submission_failures"] + 1
            pair_outcome = D.PAIR_SINGLE_LEG
            new_status = D.resolve_status_after_attempt(
                task["status"], category, new_accepted, task["target_n"],
                new_consecutive, task["failure_pause_threshold"],
            )
            if new_status == D.STATUS_PAUSED:
                pause_reason = D.PAUSE_REASON_CONSECUTIVE_SUBMISSION_FAILURE
            if exposure:
                leg_exposure_json = exposure
        else:
            # ATTEMPT_DISABLED / unknown: preserve status, no counter change.
            pair_outcome = None
            new_status = task["status"]
        if (
            not skip_counters
            and not suppress_done
            and pair_outcome is not None
            and new_status == D.STATUS_RUNNING
            and task["scheduled_attempt_count"] >= task["target_n"]
        ):
            # R2-F1: the last planned attempt has been settled (a non-None
            # pair_outcome, the scheduled counter reached target_n at its
            # reservation, A-1) and no higher-priority paused/stopped/deleted
            # state applies — complete the task so its status matches the
            # entries.next_action=completed contract instead of idling in running
            # with no remaining group to reserve. ``skip_counters`` (a rate-limited
            # pair settled without touching the brake), an unsettled/disabled
            # attempt (``pair_outcome is None``), and any non-running status are
            # left untouched.
            new_status = D.STATUS_DONE
        elif (
            suppress_done
            and pair_outcome is not None
            and new_status == D.STATUS_DONE
        ):
            # 功能三（2026-08 修复）：close 任务 success 达标时
            # ``resolve_status_after_attempt`` 会直接返回 DONE（不经本函数的
            # suppress_done 分支）——这里回退为 RUNNING，由 worker 的合约无仓
            # 核实接管完成判定（Human：close 任务从 running 变其他状态必须先
            # 核实合约；flat → done+close_cycle+close_log，open+次数用完 →
            # 部分平 done）。仅 close 任务传 suppress_done，开单任务不受影响。
            new_status = D.STATUS_RUNNING
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
        return (
            _attach_status_transition(_row_to_task(row), old_status, new_status),
            pair_outcome,
            pause_reason,
        )

    def resolve_attempt(
        self, attempt_id: int, outcome: AttemptOutcome, now_us: int,
        *, leg_terminal: dict | None = None, suppress_done: bool = False,
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
        # Attempt-row error classification is the leg-level rollup (10-design
        # §2(e)): the truthful per-pair diagnosis (e.g. 51169 -> collateral_cap)
        # rather than NULL. fatal is derived from the same rollup; the outcome-
        # level code/reason remain the fallback when no leg carries a category
        # (the dry-run record transport's offline_constraint verdict).
        rollup_cat, rollup_code = D.rollup_leg_error_category(
            outcome.spot.get("error_category"), outcome.spot.get("error_code"),
            outcome.perp.get("error_category"), outcome.perp.get("error_code"),
        )
        fatal = rollup_cat == D.ERROR_CATEGORY_FATAL
        stop_reason = D.STOP_REASON_EXCHANGE_FATAL if fatal else None
        if rollup_cat is not None:
            error_category = rollup_cat
            error_code = rollup_code
            error_reason_zh = D.stop_reason_zh(stop_reason) if fatal else None
        else:
            error_category = getattr(outcome, "error_category", None)
            error_code = getattr(outcome, "error_code", None)
            error_reason_zh = (
                D.stop_reason_zh(stop_reason) if fatal
                else getattr(outcome, "error_reason_zh", None)
            )
        with self._lock, self._conn:
            attempt = self._conn.execute(
                "SELECT * FROM hedge_open_attempt WHERE id = ?", (attempt_id,)
            ).fetchone()
            if attempt is None:
                raise UnknownTaskError(f"attempt {attempt_id}")
            task_id = attempt["task_id"]

            spot_status, spot_oid, spot_base, spot_quote, spot_fee, spot_fee_asset, spot_avg = (
                self._leg_final_fields(outcome.spot)
            )
            perp_status, perp_oid, perp_base, perp_quote, perp_fee, perp_fee_asset, perp_avg = (
                self._leg_final_fields(outcome.perp)
            )
            terminal_map = leg_terminal or {}
            for leg_name, oid, status, base, quote, fee_amt, fee_asset, avg_price in (
                ("spot", spot_oid, spot_status, spot_base, spot_quote, spot_fee, spot_fee_asset, spot_avg),
                ("perp", perp_oid, perp_status, perp_base, perp_quote, perp_fee, perp_fee_asset, perp_avg),
            ):
                leg_outcome = outcome.spot if leg_name == "spot" else outcome.perp
                is_terminal = 1 if terminal_map.get(leg_name, True) else 0
                self._conn.execute(
                    "UPDATE hedge_open_leg SET order_id = ?, exchange_status = ?,"
                    " cumulative_base_qty = ?, cumulative_quote_amt = ?, avg_price = ?,"
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
                        avg_price,
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
                suppress_done=suppress_done,
            )
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
            # Attempt-row error classification is the leg-level rollup
            # (10-design §2(e)): the truthful per-pair diagnosis (e.g. 51169 ->
            # collateral_cap) rather than the bare fatal verdict. fatal is derived
            # from the same rollup — fatal has the highest priority, so the rollup
            # surfaces it iff a leg carries it, and the stop semantics are
            # unchanged (a fatal leg still stops the task here, exactly as before).
            rollup_cat, rollup_code = D.rollup_leg_error_category(
                spot["error_category"], spot["error_code"],
                perp["error_category"], perp["error_code"],
            )
            fatal = rollup_cat == D.ERROR_CATEGORY_FATAL
            stop_reason = D.STOP_REASON_EXCHANGE_FATAL if fatal else None
            error_reason_zh = D.stop_reason_zh(stop_reason) if fatal else None
            updated_task, pair_outcome, _ = self._apply_task_counters(
                attempt["task_id"], category, exposure, now_us,
                fatal=fatal, stop_reason=stop_reason,
            )
            self._conn.execute(
                "UPDATE hedge_open_attempt SET pair_outcome = ?,"
                " error_category = ?, error_code = ?, error_reason_zh = ?"
                " WHERE id = ?",
                (pair_outcome, rollup_cat, rollup_code, error_reason_zh, attempt_id),
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
            # Attempt-row error classification is the leg-level rollup
            # (10-design §2(e)): record the truthful per-pair diagnosis. This is a
            # 429-settled pair, so control flow is unchanged — counters stay
            # skipped and the task is NOT stopped here (the 429 pause is the flow
            # control; a genuinely fatal fact re-surfaces on the next dispatch's
            # fresh POST and stops via resolve_attempt). The rollup is a pure
            # derived read of the leg rows; error_reason_zh stays NULL because no
            # stop reason is rendered on this no-stop path.
            rollup_cat, rollup_code = D.rollup_leg_error_category(
                spot["error_category"], spot["error_code"],
                perp["error_category"], perp["error_code"],
            )
            _, pair_outcome, _ = self._apply_task_counters(
                attempt["task_id"], category, exposure, now_us,
                skip_counters=True,
            )
            self._conn.execute(
                "UPDATE hedge_open_attempt SET pair_outcome = ?,"
                " error_category = ?, error_code = ? WHERE id = ?",
                (pair_outcome, rollup_cat, rollup_code, attempt_id),
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
    def _leg_row_to_exposure_input(leg_row: sqlite3.Row) -> dict:
        """Map one ``hedge_open_leg`` row onto the dict shape
        :func:`domain.build_leg_exposure` reads: ``order_id`` (acceptance),
        ``filled_qty`` (the qty figure) and ``avg_price`` (the price figure).

        ``avg_price`` is derived as ``quote / base`` exactly as the deleted store
        copy derived ``price``, so observable output is unchanged for every real
        figure — only a NULL/unknown quote now yields ``price = None`` instead of
        the fabricated zero string S1 produced. ``cumulative_base_qty`` is NOT
        NULL in practice, but a NULL is guarded to ``Decimal(0)`` so it can never
        render as the string ``"None"`` under :func:`domain.build_leg_exposure`.
        """
        base_raw = leg_row["cumulative_base_qty"]
        base = _num(base_raw)  # quantity: _num is correct (NULL -> Decimal(0) guard)
        quote = _num_or_none(leg_row["cumulative_quote_amt"])  # money: keep unknown
        avg_price = quote / base if (base > 0 and quote is not None) else None
        return {
            "order_id": leg_row["order_id"],
            "filled_qty": str(base),
            "avg_price": avg_price,
        }

    @staticmethod
    def _exposure_from_legs(spot: sqlite3.Row, perp: sqlite3.Row, ts_us: int) -> dict | None:
        """Build the advisory leg_exposure doc for a reconciled single-leg attempt
        from the two closed leg rows. Delegates to :func:`domain.build_leg_exposure`
        — the single implementation of the leg-exposure rule (D4 deleted the hand
        copy whose drift produced S1, where a NULL quote became a fabricated zero
        price).

        ``build_leg_exposure`` raises on ``ts_us <= 0`` (the T5 backstop); the
        deleted copy did not, so this is a new failure mode on the reconcile path
        (contained by the worker's exception handling).
        """
        return D.build_leg_exposure(
            HedgeOpenStore._leg_row_to_exposure_input(spot),
            HedgeOpenStore._leg_row_to_exposure_input(perp),
            ts_us,
        )

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

    def list_unsettled_terminal_attempts_for_task(self, task_id: str) -> list[dict]:
        """Return this task's attempts caught in the R2-F4 crash gap
        (user authorization 28 §2.3): BOTH legs already terminal but the pair
        ``pair_outcome`` still NULL. Such an attempt has no non-terminal leg for
        the drain to act on, yet :meth:`prepare_attempt`'s in-flight guard
        (``pair_outcome IS NULL``) blocks the next group — and the real fill stays
        off the counters. The reconcile pass finalizes each one idempotently
        (:meth:`finalize_attempt`, or :meth:`settle_attempt_no_counters` when the
        attempt was rate-limited). Scoped to ONE task (amendment 21: no global
        scan); ordered by ``attempt_seq, id`` so recovery is deterministic."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM hedge_open_attempt"
                " WHERE task_id = ? AND pair_outcome IS NULL"
                " AND NOT EXISTS ("
                "  SELECT 1 FROM hedge_open_leg l"
                "  WHERE l.attempt_id = hedge_open_attempt.id AND l.terminal = 0"
                " )"
                " ORDER BY attempt_seq ASC, id ASC",
                (task_id,),
            ).fetchall()
            return [_row_to_attempt(r) for r in rows]

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
        quote_amt: str | None,
        fee_amount: str | None,
        fee_asset: str | None,
        now_us: int,
        terminal: bool = True,
        error_code: str | None = None,
        error_category: str | None = None,
        avg_price: str | None = None,
    ) -> None:
        """Apply one client-ID query result to a leg (breakdown §3.5). A terminal
        status (FILLED/REJECTED/EXPIRED/CANCELED) closes the leg (retaining any
        partial fill); NEW/PARTIALLY_FILLED keeps it querying
        (``terminal=False``); the caller re-derives the task counters via the
        attempt's pair outcome when both legs close. ``error_code``/``error_category``
        carry the exchange business code + its classification (fatal / absent /
        auth) so a fatal reconciled leg can stop the task. ``quote_amt`` may be
        ``None`` — a FILLED UM leg whose order-detail GET came back without a figure
        stays NULL when no figure was known (T1 §1(d): unknown, not a coerced 0).
        A later incomplete query must not erase a previously recorded quote or
        exchange-provided average price."""
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE hedge_open_leg SET exchange_status = ?,"
                " order_id = COALESCE(?, order_id),"
                " cumulative_base_qty = ?,"
                " cumulative_quote_amt = COALESCE(?, cumulative_quote_amt),"
                " avg_price = COALESCE(?, avg_price),"
                " fee_amount = ?, fee_asset = ?,"
                " error_code = ?, error_category = ?,"
                " dispatch_state = ?, terminal = ?,"
                " last_query_at_us = ? WHERE id = ?",
                (
                    exchange_status,
                    order_id,
                    base_qty,
                    quote_amt,
                    avg_price,
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
        or ``None`` when the task is gone.

        fix-runtime-seam-scan (same stale-snapshot family as :meth:`pause_task`):
        CONDITIONAL write — the stop only applies while the task is currently
        ``running`` or ``paused``. A concurrent ``post_delete`` during the
        no-lock preflight network read cannot be resurrected to ``stopped`` by a
        stale worker snapshot. ``None`` covers both a missing task and a
        non-stoppable state; the caller still records its visible event."""
        with self._lock, self._conn:
            prev = self._conn.execute(
                "SELECT status FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            old_status = prev["status"] if prev is not None else None
            cur = self._conn.execute(
                "UPDATE hedge_open_task SET status = ?, stop_reason = ?,"
                " smooth_gate_seq = NULL, smooth_gate_started_at_us = NULL,"
                " smooth_gate_force_requested = 0,"
                " updated_at_us = ? WHERE id = ? AND status IN (?, ?)",
                (D.STATUS_STOPPED, stop_reason, now_us, task_id,
                 D.STATUS_RUNNING, D.STATUS_PAUSED),
            )
            if cur.rowcount == 0:
                return None
            row = self._conn.execute(
                "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            return _attach_status_transition(
                _row_to_task(row), old_status, D.STATUS_STOPPED
            ) if row is not None else None

    def pause_task(
        self, task_id: str, pause_reason: str, pause_reason_zh: str, now_us: int,
    ) -> tuple[dict | None, bool]:
        """Set a task to the amendment-21 task-local pause state:
        ``status=paused`` + ``pause_reason`` + ``pause_reason_zh`` (and clear any
        stale ``stop_reason``). Used by a task-local worker when a confirmed
        429/Retry-After or a confirmed insufficient balance/margin/available-
        quantity fact is observed for THIS task only (no cross-task linkage).
        Unlike :meth:`stop_task_fatal`, a pause is recoverable: the operator
        clears the cause and manually resumes the SAME task (Start/recover). No
        consecutive-failure counter churn.

        fix-runtime-seam-scan (F2-P1 root fix): CONDITIONAL write — the pause
        only applies while the task is currently ``running`` or ``paused``. A
        concurrent ``post_delete`` / ``post_stop`` / target-``done`` during an
        in-flight executor query therefore cannot be resurrected to ``paused``
        by a stale worker snapshot. Returns ``(updated_task, applied)``:
        ``applied=True`` means the conditional UPDATE hit and the status was
        rewritten; ``applied=False`` means the task was gone or in a
        non-pauseable state and NO status was changed (the caller still records
        its visible event, so the closure is not lost)."""
        with self._lock, self._conn:
            prev = self._conn.execute(
                "SELECT status FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            old_status = prev["status"] if prev is not None else None
            cur = self._conn.execute(
                "UPDATE hedge_open_task SET status = ?, pause_reason = ?,"
                " pause_reason_zh = ?, stop_reason = NULL,"
                " smooth_gate_seq = NULL, smooth_gate_started_at_us = NULL,"
                " smooth_gate_force_requested = 0, updated_at_us = ?"
                " WHERE id = ? AND status IN (?, ?)",
                (D.STATUS_PAUSED, pause_reason, pause_reason_zh, now_us, task_id,
                 D.STATUS_RUNNING, D.STATUS_PAUSED),
            )
            if cur.rowcount == 0:
                return None, False
            row = self._conn.execute(
                "SELECT * FROM hedge_open_task WHERE id = ?", (task_id,)
            ).fetchone()
            return _attach_status_transition(
                _row_to_task(row), old_status, D.STATUS_PAUSED
            ), True

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

    def append_raw_response(
        self, attempt_id: int, leg: str, client_order_id: str | None,
        source: str, endpoint: str, raw: dict, now_us: int,
        *, decisive: bool = False,
    ) -> int:
        """Persist one raw exchange interaction (T3 / 10-design §3). ``raw`` is the
        sanitized response dict from :class:`LegDispatch.raw_response`
        (``http_status`` / ``transport_error`` / ``code`` / ``msg`` / ``body``).
        The body is truncated to ``BODY_MAX_BYTES`` (``body_truncated=1`` if it was
        longer). Runs in its OWN short transaction, AFTER the business transaction
        committed — a failure here MUST NOT change control flow: the caller wraps
        the call in try/except and records a ``raw_persist_failed`` task event
        (this method raises so the caller can react). By construction the only body
        source is the exchange response body; request params / signature / API key
        never reach this table (10-design §3(d)).

        One raw row per leg per ``source`` (review-1 r3 P1-2, user rule
        2026-07-28/29). ``decisive`` marks the incoming response as one of the four
        conclusive verdicts §T3 requires persisted (a fill / confirmed rejection /
        confirmed absent / rate-limit); the CALLER decides it from the verdict it
        already holds — it is never re-derived here from the body. With no row yet
        the response is inserted (``decisive`` stored on the row). If a row already
        exists: a decisive response replaces a prior NON-decisive row's content in
        place (a NEW / PARTIALLY_FILLED placeholder gives way to the conclusive
        verdict that superseded it) and stamps that row decisive; a decisive row is
        never replaced — first decisive wins, so the record cannot churn (a later
        NEW cannot overwrite an earlier FILLED); a non-decisive response leaves the
        existing row untouched. This caps the repeating ``order_query`` (a
        non-terminal leg is re-read every worker round) so the table cannot grow
        without bound, while keeping the conclusive body. The check + replace run
        inside this method's own transaction; a skip is a normal return, not an
        error."""
        body = raw.get("body")
        body_text = body if isinstance(body, str) else (None if body is None else str(body))
        truncated = 0
        if body_text is not None and len(body_text) > D.BODY_MAX_BYTES:
            body_text = body_text[:D.BODY_MAX_BYTES]
            truncated = 1
        decisive_flag = 1 if decisive else 0
        with self._lock, self._conn:
            # Review-1 r3 P1-2 + r5 P1 (user rule 2026-07-28/29): one raw row per
            # leg per source. ``order_post`` / ``order_confirm`` happen once per leg
            # anyway; this caps the repeating ``order_query`` (a non-terminal leg is
            # re-read every worker round) so the table cannot grow without bound,
            # while keeping the conclusive body. The check + replace run inside this
            # method's OWN short transaction, so they can never touch the business
            # write; a skip is a normal return — not an error.
            existing = self._conn.execute(
                "SELECT id, decisive FROM hedge_open_raw_response"
                " WHERE attempt_id = ? AND leg = ? AND source = ? LIMIT 1",
                (attempt_id, leg, source),
            ).fetchone()
            if existing is not None:
                # A decisive response replaces a prior NON-decisive row's content in
                # place (a NEW / PARTIALLY_FILLED placeholder gives way to the
                # conclusive verdict that superseded it). A decisive row is never
                # replaced — first decisive wins — and a non-decisive response never
                # overwrites anything, so the record cannot churn (no later NEW over
                # an earlier FILLED).
                if decisive_flag and not existing["decisive"]:
                    self._conn.execute(
                        "UPDATE hedge_open_raw_response"
                        " SET client_order_id = ?, endpoint = ?, http_status = ?,"
                        " transport_error = ?, business_code = ?, business_msg = ?,"
                        " body = ?, body_truncated = ?, captured_at_us = ?,"
                        " decisive = 1 WHERE id = ?",
                        (
                            client_order_id, endpoint, raw.get("http_status"),
                            raw.get("transport_error"), raw.get("code"),
                            raw.get("msg"), body_text, truncated, now_us,
                            existing["id"],
                        ),
                    )
                return existing["id"]
            cur = self._conn.execute(
                "INSERT INTO hedge_open_raw_response"
                " (attempt_id, leg, client_order_id, source, endpoint,"
                "  http_status, transport_error, business_code, business_msg,"
                "  body, body_truncated, captured_at_us, decisive)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    attempt_id, leg, client_order_id, source, endpoint,
                    raw.get("http_status"), raw.get("transport_error"),
                    raw.get("code"), raw.get("msg"),
                    body_text, truncated, now_us, decisive_flag,
                ),
            )
            return cur.lastrowid

    def latest_auth_error(self, task_id: str) -> tuple:
        """该任务最近一次带业务码的原始响应 ``(business_code, business_msg)``。

        供 ``order_state_unknown`` 暂停时生成精准中文原因：``-2015`` 这类网关层
        拒绝其实**订单未发出**，通用文案让人去交易所核对订单会白跑一趟
        （2026-08-07 实盘：出口 IP 变更导致平仓两腿被 401 拒）。
        无记录时返回 ``(None, None)``。
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT r.business_code, r.business_msg"
                " FROM hedge_open_raw_response r"
                " JOIN hedge_open_attempt a ON a.id = r.attempt_id"
                " WHERE a.task_id = ? AND r.business_code IS NOT NULL"
                " ORDER BY r.id DESC LIMIT 1",
                (task_id,),
            ).fetchone()
        if row is None:
            return None, None
        return row["business_code"], row["business_msg"]

    def list_raw_responses_for_attempt(self, attempt_id: int) -> list[dict]:
        """All raw-response rows for an attempt, oldest-first (T3 verification)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM hedge_open_raw_response WHERE attempt_id = ?"
                " ORDER BY id ASC",
                (attempt_id,),
            ).fetchall()
            return [dict(r) for r in rows]

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

    # ---- 持仓周期（功能一剩余块，stage2 §3.3）----
    # 双版本模式沿用 `_apply_task_counters`（:930）先例：`_*_locked` 内部无锁版
    # MUST run inside the caller's ``with self._lock, self._conn:`` transaction
    # （不得自带 ``with self._conn:``——sqlite3 Connection.__exit__ 会对已执行
    # 语句提前 commit，破坏「cycle 写入与 attempt 写入同一事务」的原子性）；
    # 对外加锁版供非事务调用方（后续任务/人工工具）使用。

    def _get_active_cycle_locked(self, symbol: str, direction: str) -> dict | None:
        """活跃周期 = closed_at_us IS NULL 的最新一条。内部无锁版。"""
        row = self._conn.execute(
            "SELECT * FROM hedge_open_cycle"
            " WHERE symbol = ? AND direction = ? AND closed_at_us IS NULL"
            " ORDER BY opened_at_us DESC LIMIT 1",
            (symbol, direction),
        ).fetchone()
        return dict(row) if row is not None else None

    def _create_cycle_locked(
        self, symbol: str, direction: str, opened_at_us: int, task_id: str,
    ) -> dict:
        """新建周期：id=uuid4()；first_task_id=last_task_id=task_id。内部无锁版。"""
        cycle_id = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO hedge_open_cycle"
            " (id, symbol, direction, opened_at_us, closed_at_us, close_reason,"
            "  first_task_id, last_task_id)"
            " VALUES (?, ?, ?, ?, NULL, NULL, ?, ?)",
            (cycle_id, symbol, direction, opened_at_us, task_id, task_id),
        )
        row = self._conn.execute(
            "SELECT * FROM hedge_open_cycle WHERE id = ?", (cycle_id,)
        ).fetchone()
        return dict(row)

    def get_active_cycle(self, symbol: str, direction: str) -> dict | None:
        with self._lock, self._conn:
            return self._get_active_cycle_locked(symbol, direction)

    def create_cycle(
        self, symbol: str, direction: str, opened_at_us: int, task_id: str,
    ) -> dict:
        with self._lock, self._conn:
            return self._create_cycle_locked(symbol, direction, opened_at_us, task_id)

    def close_cycle(
        self, cycle_id: str, closed_at_us: int, close_reason: str,
    ) -> None:
        """关闭周期：closed_at_us 只允许 NULL→值 的单向写入；幂等（重复调用不覆盖）。

        供功能三平仓任务（close_reason='auto_close'）与人工纠偏（'manual_verify'）
        调用；本阶段只定义方法本身，不接线任何触发逻辑（设计 v1 §4.2）。
        """
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE hedge_open_cycle SET closed_at_us = ?, close_reason = ?"
                " WHERE id = ? AND closed_at_us IS NULL",
                (closed_at_us, close_reason, cycle_id),
            )

    def get_cycle_by_id(self, cycle_id: str) -> dict | None:
        """周期行映射（含 opened_at_us/closed_at_us）。只读；供回填验证与后续任务。"""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM hedge_open_cycle WHERE id = ?", (cycle_id,)
            ).fetchone()
            return dict(row) if row is not None else None

    # ---- 周期结算日志（功能三 ③a，设计 v1 §3.2）----

    def insert_close_log(self, row: dict) -> int:
        """写一条周期结算日志（平仓完成时，与 close_cycle 同事务调用方负责）。"""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO hedge_open_cycle_close_log"
                " (cycle_id, symbol, direction, opened_at_us, closed_at_us,"
                "  close_reason, open_avg_price, open_qty, close_avg_price,"
                "  funding_fee, borrow_interest, spot_open_avg, spot_open_qty,"
                "  spot_close_avg, spot_close_qty, open_slippage, close_slippage,"
                "  settled_at_us)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row["cycle_id"], row["symbol"], row["direction"],
                    row["opened_at_us"], row["closed_at_us"], row["close_reason"],
                    row.get("open_avg_price"), row.get("open_qty"),
                    row.get("close_avg_price"), row.get("funding_fee"),
                    row.get("borrow_interest"),
                    row.get("spot_open_avg"), row.get("spot_open_qty"),
                    row.get("spot_close_avg"), row.get("spot_close_qty"),
                    row.get("open_slippage"), row.get("close_slippage"),
                    row["settled_at_us"],
                ),
            )
            return cur.lastrowid

    def list_close_logs(self, limit: int = 100) -> list[dict]:
        """结算日志，按 closed_at_us 倒序（历史仓位页数据源）。只读。"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM hedge_open_cycle_close_log"
                " ORDER BY closed_at_us DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def append_log(self, task_id: str, ts_us: int, kind: str, payload: dict,
                   attempt_id=None) -> None:
        """通用任务卡日志写入（平仓现货卖出重设计的 close_transfer 等 kind）。"""
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO hedge_open_log (task_id, ts_us, attempt_id, kind, payload)"
                " VALUES (?, ?, ?, ?, ?)",
                (task_id, ts_us, attempt_id, kind,
                 json.dumps(payload, ensure_ascii=False)),
            )

    def close_task_spot_quote_total(self, task_id: str) -> Decimal | None:
        """close 任务全部现货腿成交额（cumulative_quote_amt）合计（USDT 回流统计）。

        任一成交腿 quote 不可解析 → None（不拼部分和）。"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT l.cumulative_quote_amt FROM hedge_open_leg l"
                " JOIN hedge_open_attempt a ON a.id = l.attempt_id"
                " WHERE a.task_id = ? AND l.leg = 'spot'"
                " AND CAST(l.cumulative_base_qty AS REAL) > 0",
                (task_id,),
            ).fetchall()
        total = Decimal(0)
        for r in rows:
            q = _num_or_none(r["cumulative_quote_amt"])
            if q is None:
                return None
            total += q
        return total

    def cycle_perp_basis(self, cycle_id: str, task_type: str) -> dict:
        """该周期内指定 task_type 的合约腿加权均价/累计数量（带锁，供结算日志）。"""
        return self.cycle_leg_basis(cycle_id, task_type, "perp")

    def cycle_spot_basis(self, cycle_id: str, task_type: str) -> dict:
        """该周期内指定 task_type 的现货腿加权均价/累计数量（2026-08：历史页现货列）。"""
        return self.cycle_leg_basis(cycle_id, task_type, "spot")

    def cycle_leg_basis(self, cycle_id: str, task_type: str, leg: str) -> dict:
        """该周期内指定 task_type + 腿的加权均价/累计数量（带锁）。"""
        with self._lock, self._conn:
            return self._cycle_leg_basis_locked(cycle_id, task_type, leg)

    def _cycle_leg_basis_locked(self, cycle_id: str, task_type: str, leg: str) -> dict:
        """该周期内指定 task_type + 腿的加权均价/累计数量（G5：仅已知 notional
        参与均价分母；未知不拖价）。内部无锁版，MUST run inside caller's transaction。
        返回 ``{"avg_price": str|None, "qty": str|None}``。leg='perp' 合约腿 /
        'spot' 现货腿（2026-08 补充）。"""
        rows = self._conn.execute(
            "SELECT l.cumulative_base_qty, l.cumulative_quote_amt"
            " FROM hedge_open_leg l"
            " JOIN hedge_open_attempt a ON a.id = l.attempt_id"
            " JOIN hedge_open_task t ON t.id = a.task_id"
            " WHERE a.cycle_id = ? AND t.task_type = ? AND l.leg = ?"
            " AND CAST(l.cumulative_base_qty AS REAL) > 0",
            (cycle_id, task_type, leg),
        ).fetchall()
        qty = Decimal(0)
        notional = Decimal(0)
        priced = Decimal(0)
        for r in rows:
            q = _num(r["cumulative_base_qty"])
            if q is None:
                continue
            qty += q
            quote = _num_or_none(r["cumulative_quote_amt"])
            if quote is not None and quote != 0:
                notional += quote
                priced += q
        avg = notional / priced if priced > 0 else None
        return {
            "avg_price": D.fmt_decimal(avg) if avg is not None else None,
            "qty": D.fmt_decimal(qty) if qty != 0 else None,
        }

    def cycle_slippage_pct(self, cycle_id: str, task_type: str) -> str | None:
        """该周期内指定 task_type 的两腿真实成交价差百分比。

        ``(卖出腿均价 - 买入腿均价) / min(两腿均价) * 100``；两腿均价
        分别按真实成交数量跨 attempt 加权。任一腿不可定价或非正时返回 None。"""
        with self._lock, self._conn:
            cycle = self._conn.execute(
                "SELECT direction FROM hedge_open_cycle WHERE id = ?", (cycle_id,)
            ).fetchone()
            if (
                cycle is None
                or cycle["direction"] not in D.ALL_DIRECTIONS
                or task_type not in D.ALL_TASK_TYPES
            ):
                return None
            actions = D.direction_to_leg_actions(
                cycle["direction"], D.POS_MODE_BOTH, task_type,
            )
            spot = self._cycle_leg_basis_locked(cycle_id, task_type, "spot")
            perp = self._cycle_leg_basis_locked(cycle_id, task_type, "perp")

        spot_price = _num_or_none(spot["avg_price"])
        perp_price = _num_or_none(perp["avg_price"])
        if (
            spot_price is None
            or perp_price is None
            or not spot_price.is_finite()
            or not perp_price.is_finite()
            or spot_price <= 0
            or perp_price <= 0
        ):
            return None
        sell_price, buy_price = (
            (spot_price, perp_price)
            if actions.spot_side == "SELL"
            else (perp_price, spot_price)
        )
        denominator = min(spot_price, perp_price)
        if denominator <= 0:
            return None
        return f"{(sell_price - buy_price) / denominator * 100:.4f}"

    def list_cycles(self) -> list[dict]:
        """全部周期行，按 (symbol, direction, opened_at_us) 排序。只读。"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM hedge_open_cycle"
                " ORDER BY symbol, direction, opened_at_us"
            ).fetchall()
            return [dict(r) for r in rows]

    def aggregate_positions(self) -> list[dict]:
        """Aggregate open positions from both the legacy fill rows and the
        attempt/leg rows (breakdown §3.4). avg = Σ(qty*price)/Σqty per leg.
        ``position_qty`` is the signed perp REMAINING net (forward SELL -> negative
        short, reverse BUY -> positive long). Fields with no source this round stay
        ``"0"`` so the frozen Position JSON shape is stable. D15 (2026-07-31):
        deleted tasks' already-filled legs are NO LONGER excluded — each bucket
        sets ``includes_deleted_task`` so the UI can mark rows that mix live and
        deleted sources (the deleted task's cost basis must stay visible once ②
        makes auto-delete routine). 2026-08-10 local net position: both open and
        close legs are read, and ``spot_qty``/``perp_qty`` are the LOCAL ledger
        REMAINING qty (Σ open − Σ close per leg) — NOT an exchange reconcile; the
        open-cost basis (notional / priced denominator) still comes from open legs
        only, so close legs reduce the remaining qty without dragging the avg.
        """
        with self._lock, self._conn:
            fill_rows = self._conn.execute(
                "SELECT f.spot_status, f.spot_filled_qty, f.spot_avg_price,"
                " f.perp_status, f.perp_filled_qty, f.perp_avg_price,"
                " t.coin, t.direction, t.status,"
                " t.spot_symbol, t.spot_base_asset"
                " FROM hedge_open_fill f JOIN hedge_open_task t ON t.id = f.task_id"
                " ORDER BY f.ts_us ASC, f.id ASC",
            ).fetchall()
            leg_rows = self._conn.execute(
                "SELECT l.leg, l.exchange_status, l.cumulative_base_qty,"
                " l.cumulative_quote_amt, t.coin, t.direction, t.status,"
                " t.task_type, t.spot_symbol, t.spot_base_asset,"
                " a.cycle_id,"
                " c.opened_at_us AS cycle_opened_at_us,"
                " c.closed_at_us AS cycle_closed_at_us"
                " FROM hedge_open_leg l"
                " JOIN hedge_open_attempt a ON a.id = l.attempt_id"
                " JOIN hedge_open_task t ON t.id = a.task_id"
                " LEFT JOIN hedge_open_cycle c ON c.id = a.cycle_id"
                # Human 2026-08：持仓表只显示「未平仓周期」——已完全平仓的周期
                # 从根源（后端查询）排除，避免已平仓标的回显（如 COOKIE 全平后
                # 仍显示 -5000）；已平仓周期只在历史仓位页（close_log）呈现。
                # 无周期腿（cycle_id NULL，fill 兜底/旧数据）保留不误伤。
                # 2026-08-10 本地净持仓：open 与 close 腿同读，按 task_type 在下方
                # 聚合时分别 +q / -q；close 腿只减剩余量，开仓成本基仍只由 open 腿贡献。
                " WHERE (a.cycle_id IS NULL OR c.closed_at_us IS NULL)"
                " ORDER BY a.created_at_us ASC, l.id ASC",
            ).fetchall()
            # P2-1（stage2 §3.5）：SQL-A（hedge_open_fill legacy 空壳）本应恒为
            # 0 行——fill 行没有 cycle_id，落入含 None 的兜底桶永远无法归入周期，
            # merge 也无法正确处理。非零行数视为异常并落审计告警，而非静默并入聚合。
            if fill_rows:
                self._conn.execute(
                    "INSERT INTO hedge_open_log"
                    " (task_id, ts_us, attempt_id, kind, payload)"
                    " VALUES (?, ?, NULL, ?, ?)",
                    (
                        "aggregate-positions",
                        int(time.time() * 1_000_000),
                        "aggregate_sql_a_nonzero",
                        json.dumps(
                            {
                                "table": "hedge_open_fill",
                                "row_count": len(fill_rows),
                                "reason": "P2-1: SQL-A 非零行（fill 行无 cycle_id，无法归入周期）",
                            },
                            ensure_ascii=False,
                        ),
                    ),
                )

        buckets: dict[tuple[str, str, str | None], dict] = {}
        identity_conflicts: list[dict] = []

        def _take_identity(b: dict, row, coin: str) -> None:
            """桶内身份合并：首个非空胜出；后续非空且不同的值记一条审计事件。

            同一桶会汇聚多个任务的腿（同周期多次开仓）。正常情况下它们的固化身份
            一致；若映射表在两次开仓之间变更，就会分裂——静默取首个会让该桶的余额
            对齐用到旧身份，必须留下信号（不阻断聚合，展示仍以首个为准）。
            """
            incoming = row["spot_symbol"]
            if not incoming:
                return
            if b["spot_symbol"] is None:
                b["spot_symbol"] = incoming
                b["spot_base_asset"] = row["spot_base_asset"]
            elif b["spot_symbol"] != incoming:
                identity_conflicts.append(
                    {"coin": coin, "kept": b["spot_symbol"], "ignored": incoming}
                )


        def _bucket(coin: str, direction: str, cycle_id: str | None) -> dict:
            return buckets.setdefault(
                (coin, direction, cycle_id),
                {
                    "spot_qty": Decimal(0),
                    "spot_notional": Decimal(0),
                    "perp_qty": Decimal(0),
                    "perp_notional": Decimal(0),
                    # G5 (fix-merged-positions-mismatch-labels-v1): the avg-price
                    # denominator counts ONLY legs whose notional is KNOWN. A leg
                    # with an unknown notional (NULL quote, or a literal "0" quote
                    # with a real fill — Binance dropped the UM fill quote on
                    # 2026-07-14 and the live write path persisted the unknown as
                    # "0") still contributes its real qty to spot_qty / perp_qty /
                    # position_qty for DISPLAY, but is excluded here so it cannot
                    # drag the avg to half its true value (RSRUSDT: 12.46/20000).
                    "spot_qty_priced": Decimal(0),
                    "perp_qty_priced": Decimal(0),
                    "position_qty": Decimal(0),
                    "spot_incomplete": False,
                    "perp_incomplete": False,
                    "includes_deleted": False,
                    "cycle_opened_at_us": None,
                    "cycle_closed_at_us": None,
                    # 步骤③：现货腿身份随桶带出，供 merge 层无快照也能对齐余额。
                    # 同一桶的所有腿同属一个 coin，身份一致；取首个非空即可。
                    "spot_symbol": None,
                    "spot_base_asset": None,
                },
            )

        for row in fill_rows:
            b = _bucket(row["coin"], row["direction"], None)
            _take_identity(b, row, row["coin"])
            if row["status"] == D.STATUS_DELETED:
                b["includes_deleted"] = True
            if row["spot_status"] == D.LEG_FILLED:
                q = _num(row["spot_filled_qty"])
                b["spot_qty"] += q
                # T1 §1(d) / S2: a NULL avg_price (unknown figure) must not add a
                # fabricated 0 notional — skip it and set the incomplete flag, the
                # same policy the leg_rows loop below uses. A real "0" avg_price
                # still contributes 0 (q * 0) without flagging (the r5 category).
                spot_avg = _num_or_none(row["spot_avg_price"])
                if spot_avg is not None:
                    b["spot_notional"] += q * spot_avg
                    b["spot_qty_priced"] += q
                else:
                    b["spot_incomplete"] = True
            if row["perp_status"] == D.LEG_FILLED:
                q = _num(row["perp_filled_qty"])
                b["perp_qty"] += q
                perp_avg = _num_or_none(row["perp_avg_price"])
                if perp_avg is not None:
                    b["perp_notional"] += q * perp_avg
                    b["perp_qty_priced"] += q
                else:
                    b["perp_incomplete"] = True
                sign = Decimal(-1) if row["direction"] == D.DIR_FORWARD else Decimal(1)
                b["position_qty"] += sign * q
        for row in leg_rows:
            # A-6: aggregate any leg with a POSITIVE actual fill regardless of the
            # literal exchange status — a CANCELED/PARTIALLY_FILLED/EXPIRED leg that
            # filled partially still contributes real base/quote to the position.
            if _num(row["cumulative_base_qty"]) <= 0:
                continue
            # 2026-08-10 本地净持仓：open 腿 +q、close 腿 -q，每条腿独立计量。close
            # 腿只减剩余量；开仓成本基（notional / priced 分母）仍只由 open 腿贡献，
            # 故 close 绝不会拖动 spot_avg / perp_avg。
            is_open = row["task_type"] == D.TASK_TYPE_OPEN
            leg_sign = Decimal(1) if is_open else Decimal(-1)
            b = _bucket(row["coin"], row["direction"], row["cycle_id"])
            _take_identity(b, row, row["coin"])
            # 周期戳记取组内一致值（同桶所有腿属于同一 cycle；旧数据 cycle_id
            # NULL 时两者均为 None，输出行保持 null，前端不渲染）。
            b["cycle_opened_at_us"] = row["cycle_opened_at_us"]
            b["cycle_closed_at_us"] = row["cycle_closed_at_us"]
            if row["status"] == D.STATUS_DELETED:
                b["includes_deleted"] = True
            q = _num(row["cumulative_base_qty"])
            # T1 §1(d) + G5: an unknown notional contributes its REAL qty (for
            # display / position_qty) but NOT its notional — averaging an unknown
            # as 0 would drag the avg price down. The bucket is flagged
            # avg_price_incomplete instead, so a reader knows the avg is computed
            # over a partial notional set. G5 extends 'unknown' to a literal "0"
            # quote WITH a real fill: Binance dropped the UM fill quote on
            # 2026-07-14 and the live write path persisted the unknown as "0"
            # (not NULL), so a "0" quote is the same sentinel here. It is excluded
            # from the avg's priced denominator + notional (44-runtime-observation
            # §3: RSRUSDT perp = (0 + 12.46) / 20000 = half the true 0.001246).
            # The fill_rows loop above keeps the r5 policy (a real "0" avg_price is
            # a true zero) — a different column with a deliberately different rule.
            # 2026-08-10: close 腿不计 notional（即使有 quote），只减剩余量。
            quote_raw = row["cumulative_quote_amt"]
            notional = _num_or_none(quote_raw)
            known_notional = notional is not None and notional != 0
            if row["leg"] == "spot":
                b["spot_qty"] += leg_sign * q
                if is_open and known_notional:
                    b["spot_notional"] += notional
                    b["spot_qty_priced"] += q
                elif is_open:
                    b["spot_incomplete"] = True
            else:
                b["perp_qty"] += leg_sign * q
                if is_open and known_notional:
                    b["perp_notional"] += notional
                    b["perp_qty_priced"] += q
                elif is_open:
                    b["perp_incomplete"] = True
                sign = Decimal(-1) if row["direction"] == D.DIR_FORWARD else Decimal(1)
                b["position_qty"] += sign * leg_sign * q

        for conflict in identity_conflicts:
            self._conn.execute(
                "INSERT INTO hedge_open_log"
                " (task_id, ts_us, attempt_id, kind, payload)"
                " VALUES (?, ?, NULL, 'identity_conflict', ?)",
                ("", int(time.time() * 1_000_000), json.dumps(conflict)),
            )

        positions = []
        for (coin, direction, cycle_id), b in buckets.items():
            # G5: the avg denominator is the PRICED qty (legs with a known
            # notional), not the full display qty — so an unknown-notional leg
            # can never drag the avg. When every leg on a side is unknown the
            # priced qty is 0 and the avg falls back to 0 (flagged incomplete).
            spot_avg = (
                b["spot_notional"] / b["spot_qty_priced"]
                if b["spot_qty_priced"] > 0 else Decimal(0)
            )
            perp_avg = (
                b["perp_notional"] / b["perp_qty_priced"]
                if b["perp_qty_priced"] > 0 else Decimal(0)
            )
            positions.append(
                {
                    "coin": coin,
                    "direction": direction,
                    "position_qty": D.fmt_decimal(b["position_qty"]),
                    "spot_qty": D.fmt_decimal(b["spot_qty"]),
                    "perp_qty": D.fmt_decimal(b["perp_qty"]),
                    "spot_avg": D.fmt_decimal(spot_avg),
                    "perp_avg": D.fmt_decimal(perp_avg),
                    # T1 §1(d): additive — true when any contributing leg had a NULL
                    # quote, so the avg above is over a partial notional set.
                    "spot_avg_price_incomplete": b["spot_incomplete"],
                    "perp_avg_price_incomplete": b["perp_incomplete"],
                    # D15: true when any contributing leg belongs to a deleted task.
                    "includes_deleted_task": b["includes_deleted"],
                    # 持仓周期（设计 v1 §5.2）：桶键第三元 + ISO 起止时间；NULL=无周期。
                    "cycle_id": cycle_id,
                    # 步骤③：任务固化的现货腿身份（merge 层优先于 asset_map 使用）。
                    "spot_symbol": b["spot_symbol"],
                    "spot_base_asset": b["spot_base_asset"],
                    "cycle_opened_at": D.us_to_iso(b["cycle_opened_at_us"]),
                    "cycle_closed_at": D.us_to_iso(b["cycle_closed_at_us"]),
                    "open_basis_rate": "0",
                    "price_pnl": "0",
                    "accrued_funding": "0",
                    "borrow_interest": "0",
                    "net_pnl": "0",
                }
            )
        positions.sort(
            key=lambda p: (
                p["coin"], p["direction"],
                p.get("cycle_opened_at") or "", p.get("cycle_id") or "",
            )
        )
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
                # 功能三：平仓闸门（默认开，Human 已拍板）
                "close_gate": row["close_gate"],
            }

    def get_interval_us(self) -> int:
        """The effective re-query cadence, read from the code constant — NOT from
        the database (Human decision 2026-08-02).

        The cadence has exactly one source of truth: ``D.DEFAULT_INTERVAL_US``.
        The ``hedge_open_settings.interval_us`` / ``interval_seconds`` columns are
        **dead data**: no API, no endpoint and no UI can write them, so a value
        stored at build time could never be changed — which is why a cadence
        change needed a row-rewriting migration, and that migration is what
        silently rewrote the production database on 2026-08-01 (BK-T3-002) in
        violation of DEC-2026-07-30-003. Reading the constant removes the second
        source, so no migration is needed and constructing a store against any
        database never rewrites it. The columns are left in place on purpose:
        dropping them would itself require a schema migration against the live
        DB — the very thing this change exists to avoid.
        """
        return max(int(D.DEFAULT_INTERVAL_US), D.MIN_INTERVAL_US)

    def set_start_gate(self, enabled: bool, now_us: int) -> dict:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE hedge_open_settings SET start_gate = ?, version = version + 1,"
                " updated_at_us = ? WHERE id = 1",
                (1 if enabled else 0, now_us),
            )
            return self.get_settings()

    def set_start_gate_cas(
        self, enabled: bool, expected_version: int, now_us: int,
    ) -> dict | None:
        """Compare-and-swap the Start gate with a same-transaction audit row
        (ADR-H2 / 10-design §2.3). Returns the updated settings doc on hit, or
        ``None`` on a version mismatch (the caller answers 409 ``version_conflict``).

        The audit row (``hedge_open_log`` kind ``start_gate_changed``, sentinel
        ``task_id="start-gate"``) is written in the SAME store transaction as the
        gate UPDATE, so the change and its audit record share one atomic commit.
        The pre-existing unconditional :meth:`set_start_gate` seam is left
        untouched (tests use it; additive, unchanged signature)."""
        with self._lock, self._conn:
            prev = self._conn.execute(
                "SELECT start_gate, version FROM hedge_open_settings WHERE id = 1"
            ).fetchone()
            if prev is None or prev["version"] != expected_version:
                return None
            previous_enabled = bool(prev["start_gate"])
            cur = self._conn.execute(
                "UPDATE hedge_open_settings SET start_gate = ?, version = version + 1,"
                " updated_at_us = ? WHERE id = 1 AND version = ?",
                (1 if enabled else 0, now_us, expected_version),
            )
            if cur.rowcount == 0:
                return None
            self._conn.execute(
                "INSERT INTO hedge_open_log (task_id, ts_us, attempt_id, kind, payload)"
                " VALUES (?, ?, NULL, ?, ?)",
                (
                    "start-gate",
                    now_us,
                    "start_gate_changed",
                    json.dumps(
                        {
                            "enabled": bool(enabled),
                            "previous_enabled": previous_enabled,
                            "version": expected_version + 1,
                            "source": "api",
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            return self.get_settings()

    def set_close_gate_cas(
        self, enabled: bool, expected_version: int, now_us: int,
    ) -> dict | None:
        """Compare-and-swap the close gate with a same-transaction audit row
        （功能三，镜像 set_start_gate_cas ADR-H2）。Returns the updated settings
        doc on hit, or ``None`` on a version mismatch. Audit kind
        ``close_gate_changed``，sentinel ``task_id="close-gate"``。"""
        with self._lock, self._conn:
            prev = self._conn.execute(
                "SELECT close_gate, version FROM hedge_open_settings WHERE id = 1"
            ).fetchone()
            if prev is None or prev["version"] != expected_version:
                return None
            previous_enabled = bool(prev["close_gate"])
            cur = self._conn.execute(
                "UPDATE hedge_open_settings SET close_gate = ?, version = version + 1,"
                " updated_at_us = ? WHERE id = 1 AND version = ?",
                (1 if enabled else 0, now_us, expected_version),
            )
            if cur.rowcount == 0:
                return None
            self._conn.execute(
                "INSERT INTO hedge_open_log (task_id, ts_us, attempt_id, kind, payload)"
                " VALUES (?, ?, NULL, ?, ?)",
                (
                    "close-gate",
                    now_us,
                    "close_gate_changed",
                    json.dumps(
                        {
                            "enabled": bool(enabled),
                            "previous_enabled": previous_enabled,
                            "version": expected_version + 1,
                            "source": "api",
                        },
                        ensure_ascii=False,
                    ),
                ),
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
