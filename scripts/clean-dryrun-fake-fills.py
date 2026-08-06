#!/usr/bin/env python3
"""一次性清理：删除 dry-run 假成交数据（THE 事件 attempt 4/5，Human 2026-08-06 授权）。

背景：2026-08-06 服务被误启动成 disabled（漏加载 .env）→ 默认注入
RecordTransportExecutor（dry-run 假成交模拟器，本 stage 已从生产代码移除）→
任务 e22ce275 在 16:38:06 产生 2 笔假成交（4 条 `dryspot-*`/`dryperp-*` leg 行），
污染本地持仓口径（spot 800 / perp 600 / position -600 vs 交易所真实 400 / 200 / -200）。

清理目标（dispatch 03 B-3，已核验）：
- hedge_open_leg    删除 order_id LIKE 'dry%'（4 行，leg id 7-10）
- hedge_open_attempt 删除任务 e22ce275 的 attempt（id 4/5，均带 cycle_id 096232b7 ——
  周期表的 first/last_task_id 指向已删任务是另一条已记录待办，本脚本不动周期表）
- hedge_open_task    e22ce275：success_count / scheduled_attempt_count /
  accepted_pair_count → 0，status → 'deleted'
- hedge_open_raw_response：0 行（dry-run 不发请求），无需清理
- hedge_open_log     16:38:06 两条 record_transport 保留（定性关键证据，不删）
- 不得触碰 attempt 6/7（真实成交 834390514 / 834392365 / 2031628184）及任务
  7eeab9c3 / 89f80678 / 56e7ded9 的任何数据

安全约束（沿用 backfill-cycles.py 风格）：
- 默认 dry-run：只读打开目标库，只输出计划与前后对账，不写任何字节；
- --apply 才写库：先备份到 data/hedge-open-tasks.sqlite3.bak-dryclean-<YYYYMMDD-HHMMSS>，
  再在同一事务内执行（失败整体回滚）；
- 写前强制核验：任务 e22ce275 名下所有 leg 必须都是 dry% 前缀（无真实腿），
  否则拒绝执行（exit 2）；
- --audit <path>（须与 --apply 同用）：把前后对账与行数核对结果落盘 JSON 审计。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from backend.hedge_open_tasks import domain as D  # noqa: E402
from backend.hedge_open_tasks.store import HedgeOpenStore  # noqa: E402

LIVE_DB = os.path.join(_ROOT, "data", "hedge-open-tasks.sqlite3")
TASK_ID = "e22ce275-bdc1-4302-998c-c50acdaa8161"
DRY_PREFIX = "dry%"


def _now_stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _positions_snapshot(db: str) -> dict:
    """THEUSDT forward 持仓对账（读 store 聚合，只读）。"""
    store = HedgeOpenStore(db)
    for p in store.aggregate_positions():
        if p["coin"] == "THEUSDT" and p["direction"] == D.DIR_FORWARD:
            return {
                "coin": p["coin"],
                "direction": p["direction"],
                "spot_qty": p["spot_qty"],
                "perp_qty": p["perp_qty"],
                "position_qty": p["position_qty"],
            }
    return {"coin": "THEUSDT", "direction": "forward",
            "spot_qty": "0", "perp_qty": "0", "position_qty": "0"}


def _row_counts(conn: sqlite3.Connection) -> dict:
    """清理相关表的行数快照（只读）。"""
    out = {}
    out["dry_legs"] = conn.execute(
        "SELECT COUNT(*) FROM hedge_open_leg WHERE order_id LIKE ?",
        (DRY_PREFIX,),
    ).fetchone()[0]
    out["task_attempts"] = conn.execute(
        "SELECT COUNT(*) FROM hedge_open_attempt WHERE task_id = ?", (TASK_ID,)
    ).fetchone()[0]
    out["task_raw"] = conn.execute(
        "SELECT COUNT(*) FROM hedge_open_raw_response"
        " WHERE attempt_id IN (SELECT id FROM hedge_open_attempt WHERE task_id = ?)",
        (TASK_ID,),
    ).fetchone()[0]
    out["task_logs"] = conn.execute(
        "SELECT COUNT(*) FROM hedge_open_log WHERE task_id = ?", (TASK_ID,)
    ).fetchone()[0]
    out["task"] = conn.execute(
        "SELECT COUNT(*) FROM hedge_open_task WHERE id = ?", (TASK_ID,)
    ).fetchone()[0]
    out["attempt_6_7_legs"] = conn.execute(
        "SELECT COUNT(*) FROM hedge_open_leg WHERE attempt_id IN (6, 7)"
    ).fetchone()[0]
    out["attempt_6_7_raw"] = conn.execute(
        "SELECT COUNT(*) FROM hedge_open_raw_response WHERE attempt_id IN (6, 7)"
    ).fetchone()[0]
    return out


def _verify_task_has_only_dry_legs(conn: sqlite3.Connection) -> list[str]:
    """核验：任务 e22ce275 名下 leg 全部为 dry% 前缀（无真实腿）。

    返回非 dry 订单号的 leg 列表；空列表 = 核验通过。任务不存在时返回标记行。
    """
    rows = conn.execute(
        "SELECT l.id, l.order_id FROM hedge_open_leg l"
        " JOIN hedge_open_attempt a ON a.id = l.attempt_id"
        " WHERE a.task_id = ? ORDER BY l.id",
        (TASK_ID,),
    ).fetchall()
    if not rows:
        return [f"task {TASK_ID} 名下没有任何 leg 行（无法确认全假成交，拒绝清理）"]
    bad = []
    for leg_id, order_id in rows:
        if not order_id or not str(order_id).startswith("dry"):
            bad.append(f"leg id={leg_id} order_id={order_id!r} 非 dry 前缀")
    return bad


def run_plan(db: str) -> dict:
    """dry-run：只读输出计划 + 前后对账（聚合为清理后模拟值）。"""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    before_counts = _row_counts(conn)
    problems = _verify_task_has_only_dry_legs(conn)
    before_pos = _positions_snapshot(db)
    conn.close()
    return {
        "mode": "dry-run（未写库）",
        "db": db,
        "before": {"counts": before_counts, "positions": before_pos},
        "verification": problems,
        "planned": {
            "delete_legs": "DELETE FROM hedge_open_leg WHERE order_id LIKE 'dry%'",
            "delete_attempts": f"DELETE FROM hedge_open_attempt WHERE task_id = '{TASK_ID}'",
            "update_task": (
                "UPDATE hedge_open_task SET success_count=0,"
                " scheduled_attempt_count=0, accepted_pair_count=0,"
                f" status='deleted' WHERE id = '{TASK_ID}'"
            ),
            "expected_positions": {
                "spot_qty": "800 -> 400", "perp_qty": "600 -> 200",
                "position_qty": "-600 -> -200",
            },
        },
    }


def run_apply(db: str) -> dict:
    """写库：备份 → 核验 → 单事务清理 → 后对账。"""
    stamp = _now_stamp()
    backup = os.path.join(os.path.dirname(db), f"hedge-open-tasks.sqlite3.bak-dryclean-{stamp}")
    shutil.copy2(db, backup)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    before_counts = _row_counts(conn)
    problems = _verify_task_has_only_dry_legs(conn)
    if problems:
        conn.close()
        raise SystemExit(
            f"核验失败，未执行清理（备份已留 {backup}）：\n" + "\n".join(problems)
        )
    before_pos = _positions_snapshot(db)
    try:
        with conn:  # 单事务；失败整体回滚
            dry_legs = conn.execute(
                "DELETE FROM hedge_open_leg WHERE order_id LIKE ?", (DRY_PREFIX,)
            ).rowcount
            task_attempts = conn.execute(
                "DELETE FROM hedge_open_attempt WHERE task_id = ?", (TASK_ID,)
            ).rowcount
            task_updates = conn.execute(
                "UPDATE hedge_open_task SET success_count = 0,"
                " scheduled_attempt_count = 0, accepted_pair_count = 0,"
                " status = ? WHERE id = ?",
                (D.STATUS_DELETED, TASK_ID),
            ).rowcount
    except Exception as exc:  # pragma: no cover - 回滚路径
        conn.close()
        raise SystemExit(f"清理事务失败，已回滚（备份：{backup}）：{exc}")

    after_counts = _row_counts(conn)
    after_pos = _positions_snapshot(db)
    conn.close()

    task = None
    conn_ro = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn_ro.row_factory = sqlite3.Row
    row = conn_ro.execute(
        "SELECT id, status, success_count, scheduled_attempt_count,"
        " accepted_pair_count FROM hedge_open_task WHERE id = ?",
        (TASK_ID,),
    ).fetchone()
    if row is not None:
        task = dict(row)
    conn_ro.close()

    return {
        "mode": "applied（已写库）",
        "db": db,
        "backup": backup,
        "before": {"counts": before_counts, "positions": before_pos},
        "after": {"counts": after_counts, "positions": after_pos},
        "verification": problems,
        "deleted_rows": {"legs": dry_legs, "attempts": task_attempts,
                         "task_updates": task_updates},
        "task_after": task,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="删除 dry-run 假成交数据（THE attempt 4/5；Human 2026-08-06 授权）"
    )
    parser.add_argument("--db", default=LIVE_DB,
                        help="目标库路径（默认实盘库；dry-run 只读，--apply 先备份再写）")
    parser.add_argument("--apply", action="store_true",
                        help="真正写库（先备份，再单事务清理；否则只输出 dry-run 计划）")
    parser.add_argument("--audit", default=None,
                        help="把结果 JSON 落盘（建议与 --apply 同用）")
    args = parser.parse_args()

    result = run_apply(args.db) if args.apply else run_plan(args.db)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.audit:
        Path(args.audit).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
