#!/usr/bin/env python3
"""
backfill-spot-identity.py
-------------------------
为存量开单/平单任务回填现货腿身份三列（`spot_symbol` / `spot_base_asset` /
`symbol_match_type`）——2026-08-07 symbol-identity-unification 步骤①。

身份自此是任务的第一等属性：建任务时由 `resolve_spot_identity` 解析一次并固化，
下单 / 平单 / 展示三环只读不算。本脚本把回填前创建的任务补齐到同一形态。

**幂等**：只写 `spot_symbol IS NULL` 的行。已固化的身份是该任务的历史真值，绝不
覆盖——表若变动应由 `check-spot-symbol-map.py --verify` 报 STALE 后人工处理，
不在回填里静默改写（平仓必须用开仓时的身份，见方案 §2.1）。

用法：
    python scripts/backfill-spot-identity.py            # 默认库，先自动备份
    python scripts/backfill-spot-identity.py --db PATH
    python scripts/backfill-spot-identity.py --dry-run  # 只报告不写入
    python scripts/backfill-spot-identity.py --no-backup
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_DB = ROOT / "data" / "hedge-open-tasks.sqlite3"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB), help="任务库路径")
    ap.add_argument("--dry-run", action="store_true", help="只报告将要回填的行，不写入")
    ap.add_argument("--no-backup", action="store_true", help="跳过自动备份")
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"库不存在: {db_path}", file=sys.stderr)
        return 1

    from backend.domain.normalize import resolve_spot_identity
    from backend.hedge_open_tasks.store import HedgeOpenStore

    store = HedgeOpenStore(str(db_path))
    try:
        pending = store._conn.execute(
            "SELECT id, coin FROM hedge_open_task WHERE spot_symbol IS NULL"
        ).fetchall()

        if not pending:
            total = store._conn.execute(
                "SELECT COUNT(*) FROM hedge_open_task"
            ).fetchone()[0]
            print(f"无需回填：{total} 个任务的身份列均已固化")
            return 0

        print(f"待回填 {len(pending)} 行：")
        for row in pending:
            spot_symbol, spot_base, match_type = resolve_spot_identity(row["coin"])
            mark = "" if spot_symbol == row["coin"] else "  <- 与合约名不同"
            print("   %-38s %-14s -> %-14s (%s)%s"
                  % (row["id"], row["coin"], spot_symbol, match_type, mark))

        if args.dry_run:
            print("\n--dry-run：未写入")
            return 0

        if not args.no_backup:
            stamp = time.strftime("%Y%m%d-%H%M%S")
            backup = db_path.with_name(db_path.name + f".bak-spotidentity-{stamp}")
            shutil.copy2(db_path, backup)
            print(f"\n已备份: {backup.name}")

        result = store.backfill_spot_identity()
        print(f"回填完成: updated={result['updated']} / total={result['total']}")
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(main())
