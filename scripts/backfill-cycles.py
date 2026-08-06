#!/usr/bin/env python3
"""历史回填：持仓周期轻量表内部数据初始化（设计 v1 §6 / stage2 §3.7）。

数据源 = 开单任务卡（hedge_open_task + hedge_open_attempt + hedge_open_leg）。
默认每个 (coin, direction) 一条周期行（可用 --split 人工分段）：

  id            = uuid4()
  symbol        = t.coin
  direction     = t.direction
  opened_at_us  = 组内最早【成功腿】的 l.dispatched_at_us
                  （无成功腿 → 最早 a.created_at_us；仍无 → 不建周期行，因无仓位）
  closed_at_us  = NULL（当前无平仓事件，全部「持仓中」；由功能三/人工核实时关闭）
  close_reason  = NULL
  first_task_id = 组内最早任务 id（按 t.created_at_us）
  last_task_id  = 组内最晚任务 id

attempt.cycle_id 回填：按 attempt 所属 task 的 (coin, direction) → 组 cycle_id。
--split "SYMBOL,DIRECTION,ISO时间"（可多次）：把该 (coin, direction) 组在指定时刻
切成两个周期——created_at_us < 分段点的任务归前段，>= 分段点归后段；每段独立计算
opened_at_us / first_task_id / last_task_id，attempt 按所属 task 归段。

安全约束：
- 默认 dry-run：以 SQLite read-only 模式打开目标库，只输出计划，不写任何字节；
- --apply 才写库：先构造 HedgeOpenStore（_SCHEMA/_migrate 幂等建表 + 加列），再在
  同一事务内插入周期行并回填 attempt.cycle_id（失败整体回滚）；
- 重复回填防护：目标库已存在周期行或 attempt.cycle_id 非空时直接退出（exit 2）；
- --audit <path>（须与 --apply 同用）：把回填 SQL 与前后行数核对结果落盘 JSON 审计。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sqlite3
import sys
import time
import uuid
from decimal import Decimal, InvalidOperation

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from backend.hedge_open_tasks import domain as D  # noqa: E402
from backend.hedge_open_tasks.store import HedgeOpenStore  # noqa: E402

LIVE_DB = os.path.join(_ROOT, "data", "hedge-open-tasks.sqlite3")

INSERT_SQL = (
    "INSERT INTO hedge_open_cycle"
    " (id, symbol, direction, opened_at_us, closed_at_us, close_reason,"
    "  first_task_id, last_task_id)"
    " VALUES (?, ?, ?, ?, NULL, NULL, ?, ?)"
)
UPDATE_SQL = "UPDATE hedge_open_attempt SET cycle_id = ? WHERE id = ?"


def _num(value) -> Decimal | None:
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _parse_split(spec: str) -> tuple[str, str, int]:
    """'SYMBOL,DIRECTION,ISO时间' -> (symbol, direction, split_us)。"""
    parts = [p.strip() for p in spec.split(",")]
    if len(parts) != 3:
        raise ValueError(f"--split 格式应为 SYMBOL,DIRECTION,ISO时间：{spec!r}")
    symbol, direction, iso = parts
    iso = iso.replace("Z", "+00:00")
    try:
        dt = _dt.datetime.fromisoformat(iso)
    except ValueError as exc:
        raise ValueError(f"--split 时间无法解析：{iso!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    split_us = int(dt.timestamp() * 1_000_000)
    return symbol, direction, split_us


def _fetch_rows(conn):
    return conn.execute(
        "SELECT t.id AS task_id, t.coin, t.direction, t.created_at_us,"
        "       a.id AS attempt_id, a.created_at_us AS attempt_created_at_us,"
        "       l.id AS leg_id, l.dispatched_at_us, l.cumulative_base_qty"
        " FROM hedge_open_task t"
        " LEFT JOIN hedge_open_attempt a ON a.task_id = t.id"
        " LEFT JOIN hedge_open_leg l ON l.attempt_id = a.id"
        " ORDER BY t.created_at_us, t.id, a.id, l.id"
    ).fetchall()


def compute_plan(conn, split_points: list[tuple[str, str, int]]):
    """按 (coin, direction) 分组生成周期行计划 + attempt 回填映射。

    返回 (cycles, attempt_updates)：cycles 为 dict 列表（含 id/symbol/direction/
    opened_at_us/first_task_id/last_task_id/attempt_count），attempt_updates 为
    [(attempt_id, cycle_id), ...] 列表。
    """
    split_map = {(s, d): us for s, d, us in split_points}
    groups: dict[tuple[str, str], dict[str, dict]] = {}
    for r in _fetch_rows(conn):
        key = (r["coin"], r["direction"])
        tasks = groups.setdefault(key, {})
        tinfo = tasks.setdefault(
            r["task_id"], {"created_at_us": r["created_at_us"], "attempts": {}}
        )
        if r["attempt_id"] is None:
            continue
        ainfo = tinfo["attempts"].setdefault(
            r["attempt_id"],
            {"created_at_us": r["attempt_created_at_us"], "legs": []},
        )
        if r["leg_id"] is not None:
            ainfo["legs"].append(r)

    cycles: list[dict] = []
    attempt_updates: list[tuple[int, str]] = []
    for (coin, direction), tasks in sorted(groups.items()):
        split_us = split_map.get((coin, direction))
        buckets: dict[int, dict[str, dict]] = {}
        for task_id, tinfo in tasks.items():
            idx = 0 if (split_us is None or tinfo["created_at_us"] < split_us) else 1
            buckets.setdefault(idx, {})[task_id] = tinfo
        for idx in sorted(buckets):
            btasks = buckets[idx]
            attempts = [
                a for t in btasks.values() for a in t["attempts"].values()
            ]
            if not attempts:
                continue  # 仍无 attempt → 不建周期行（无仓位）
            successful = []
            for a in attempts:
                for l in a["legs"]:
                    qty = _num(l["cumulative_base_qty"])
                    if qty is not None and qty > 0:
                        successful.append(l)
            dispatched = [
                l["dispatched_at_us"] for l in successful
                if l["dispatched_at_us"] is not None
            ]
            if dispatched:
                opened_at_us = min(dispatched)
            else:
                opened_at_us = min(a["created_at_us"] for a in attempts)
            ordered_tasks = sorted(
                btasks.items(), key=lambda kv: (kv[1]["created_at_us"], kv[0])
            )
            cycle_id = str(uuid.uuid4())
            cycles.append(
                {
                    "id": cycle_id,
                    "symbol": coin,
                    "direction": direction,
                    "opened_at_us": opened_at_us,
                    "closed_at_us": None,
                    "close_reason": None,
                    "first_task_id": ordered_tasks[0][0],
                    "last_task_id": ordered_tasks[-1][0],
                    "attempt_count": len(attempts),
                }
            )
            for t in btasks.values():
                for aid in t["attempts"]:
                    attempt_updates.append((aid, cycle_id))
    return cycles, attempt_updates


def snapshot_counts(conn) -> dict:
    """前后行数核对快照（dry-run 与 apply 共用；只读）。"""
    has_cycle = (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table'"
            " AND name = 'hedge_open_cycle'"
        ).fetchone()
        is not None
    )
    cycle_rows = (
        conn.execute("SELECT COUNT(*) FROM hedge_open_cycle").fetchone()[0]
        if has_cycle else 0
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(hedge_open_attempt)")}
    has_cycle_id = "cycle_id" in cols
    attempts_with_cycle = (
        conn.execute(
            "SELECT COUNT(*) FROM hedge_open_attempt WHERE cycle_id IS NOT NULL"
        ).fetchone()[0]
        if has_cycle_id else 0
    )
    return {
        "cycle_table_exists": has_cycle,
        "cycle_rows": cycle_rows,
        "cycle_id_column_exists": has_cycle_id,
        "attempts_with_cycle_id": attempts_with_cycle,
    }


def run_dry(db: str, split_points: list[tuple[str, str, int]]) -> int:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        cycles, updates = compute_plan(conn, split_points)
        print(f"回填计划（dry-run，未写库）db={db}")
        print(f"周期行：{len(cycles)}")
        for i, c in enumerate(cycles, 1):
            print(
                f"  [{i}/{len(cycles)}] {c['symbol']} {c['direction']}"
                f" opened_at={D.us_to_iso(c['opened_at_us'])} closed_at=NULL"
                f" first_task={c['first_task_id']} last_task={c['last_task_id']}"
                f" attempts={c['attempt_count']}"
            )
        print(f"attempt.cycle_id 将回填：{len(updates)} 条")
        return 0
    finally:
        conn.close()


def _lit(value) -> str:
    return "NULL" if value is None else repr(str(value))


def run_apply(db: str, split_points: list[tuple[str, str, int]],
              audit_path: str | None) -> int:
    ro = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        before = snapshot_counts(ro)
    finally:
        ro.close()
    if before["cycle_rows"] > 0 or before["attempts_with_cycle_id"] > 0:
        print("拒绝回填：目标库已存在周期数据（重复回填防护）。", file=sys.stderr)
        print(json.dumps(before, ensure_ascii=False), file=sys.stderr)
        return 2
    store = HedgeOpenStore(db)  # _SCHEMA 建表 + _migrate 加 cycle_id 列（幂等）
    try:
        with store._lock, store._conn:  # 单事务：插入周期行 + 回填 attempt.cycle_id
            cycles, updates = compute_plan(store._conn, split_points)
            if not cycles:
                print(
                    "拒绝回填：无周期行可生成（没有任何 (coin, direction) 组含 attempt）。",
                    file=sys.stderr,
                )
                return 2
            sql_lines = []
            for c in cycles:
                store._conn.execute(
                    INSERT_SQL,
                    (c["id"], c["symbol"], c["direction"], c["opened_at_us"],
                     c["first_task_id"], c["last_task_id"]),
                )
                sql_lines.append(
                    "INSERT INTO hedge_open_cycle"
                    " (id, symbol, direction, opened_at_us, closed_at_us,"
                    "  close_reason, first_task_id, last_task_id)"
                    f" VALUES ({_lit(c['id'])}, {_lit(c['symbol'])},"
                    f" {_lit(c['direction'])}, {c['opened_at_us']}, NULL, NULL,"
                    f" {_lit(c['first_task_id'])}, {_lit(c['last_task_id'])})"
                )
            for aid, cycle_id in updates:
                store._conn.execute(UPDATE_SQL, (cycle_id, aid))
                sql_lines.append(
                    f"UPDATE hedge_open_attempt SET cycle_id = {_lit(cycle_id)}"
                    f" WHERE id = {aid}"
                )
        after = snapshot_counts(store._conn)
    finally:
        store.close()

    summary = {
        "script": "scripts/backfill-cycles.py",
        "db_path": db,
        "applied_at_us": _now_us(),
        "split_points": [f"{s},{d},{D.us_to_iso(u)}" for s, d, u in split_points],
        "before": before,
        "cycles": cycles,
        "attempt_updates": len(updates),
        "sql": sql_lines,
        "after": after,
        "diff": {
            "cycle_rows": f"{before['cycle_rows']} -> {after['cycle_rows']}",
            "attempts_with_cycle_id":
                f"{before['attempts_with_cycle_id']} -> {after['attempts_with_cycle_id']}",
            "attempts_updated": len(updates),
        },
    }
    if audit_path:
        with open(audit_path, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, ensure_ascii=False, indent=2)
        print(f"审计已落盘：{audit_path}")
    print(f"回填完成：周期行 {before['cycle_rows']} -> {after['cycle_rows']}"
          f"，attempt.cycle_id {before['attempts_with_cycle_id']} ->"
          f" {after['attempts_with_cycle_id']}（更新 {len(updates)} 条）")
    return 0


def _now_us() -> int:
    return int(time.time() * 1_000_000)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="持仓周期轻量表历史回填（默认 dry-run，--apply 才写库）"
    )
    parser.add_argument(
        "--db", default=LIVE_DB,
        help="目标库路径（默认实盘库，dry-run 只读；实盘写库需 Human 单独授权）",
    )
    parser.add_argument(
        "--split", action="append", default=[], metavar="SYMBOL,DIRECTION,ISO时间",
        help="人工分段点（可多次）：把该 (coin, direction) 组按任务创建时间切为两段",
    )
    parser.add_argument(
        "--apply", action="store_true", help="真正写库（否则只输出 dry-run 计划）"
    )
    parser.add_argument(
        "--audit", default=None, metavar="PATH",
        help="审计落盘路径（仅与 --apply 同用）：回填 SQL + 前后行数核对 JSON",
    )
    args = parser.parse_args(argv)
    try:
        split_points = [_parse_split(s) for s in args.split]
    except ValueError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    if not args.apply:
        return run_dry(args.db, split_points)
    if args.audit is None:
        print(
            "提示：建议 --audit <path> 落盘回填 SQL 与前后行数核对（设计 v1 §6）。",
            file=sys.stderr,
        )
    return run_apply(args.db, split_points, args.audit)


if __name__ == "__main__":
    sys.exit(main())
