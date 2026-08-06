"""持仓周期轻量表：建表/迁移/回填用例（stage 2026-08-hedge-position-cycle-v1）。

覆盖：
- _SCHEMA/_migrate 幂等：hedge_open_cycle 建表（字段与 DDL 一致）+ attempt.cycle_id
  加列 + idx_cycle_active / idx_attempt_cycle 双索引，重复构造 store 不重复加列/建表；
- 只读方法 get_cycle_by_id / list_cycles；
- scripts/backfill-cycles.py（经 subprocess 以真实 CLI 形态执行）：
  dry-run 只读不写、--apply 回填周期行与 attempt.cycle_id、无成功腿取 attempt
  created_at_us、无 attempt 组不建周期行、--split 人工分段、--audit 审计落盘、
  重复回填防护。
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.executor import AttemptOutcome
from backend.hedge_open_tasks.store import HedgeOpenStore

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "backfill-cycles.py"

CYCLE_COLUMNS = {
    "id", "symbol", "direction", "opened_at_us",
    "closed_at_us", "close_reason", "first_task_id", "last_task_id",
}


def _outcome(attempt_id: str, qty: str = "0.5") -> AttemptOutcome:
    return AttemptOutcome(
        attempt_id=attempt_id,
        category=D.ATTEMPT_SUCCESS,
        spot={"status": D.LEG_FILLED, "filled_qty": qty, "avg_price": "50000",
              "order_id": f"os-{attempt_id}", "client_order_id": f"hgo-{attempt_id}-s"},
        perp={"status": D.LEG_FILLED, "filled_qty": qty, "avg_price": "50000",
              "order_id": f"op-{attempt_id}", "client_order_id": f"hgo-{attempt_id}-p"},
        record_payload={"transport": "dry_run_record", "posted": False,
                        "spot_order_params": {}, "perp_order_params": {}},
        exposure=None,
    )


def _create(store, task_id: str, coin: str, direction: str, created_us: int):
    return store.create_task(
        task_id, coin, direction, D.MODE_IMMEDIATE, "0.5", 3, "0.5",
        D.POS_MODE_BOTH, {"est_price": "50000"}, created_us,
    )


def _apply(store, task_id: str, attempt_uuid: str, now_us: int,
           direction: str = D.DIR_FORWARD):
    """成功 attempt：resolve 时把 dispatched_at_us 写成 now_us（可控派发时间）。"""
    attempt = store.prepare_attempt(
        task_id, attempt_uuid, direction, "0.5", D.POS_MODE_BOTH,
        {"est_price": "50000"}, f"hgo-{attempt_uuid}-s", {"side": "BUY"},
        D.SPOT_ORDER_PATH, f"hgo-{attempt_uuid}-p", {"side": "SELL"}, now_us,
    )
    assert attempt is not None, "task must be dispatch-eligible"
    store.resolve_attempt(attempt["id"], _outcome(attempt_uuid), now_us)
    return attempt["id"]


def _run(*args: str, db: str, expect_rc: int = 0) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--db", db, *args],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == expect_rc, (
        f"rc={proc.returncode} (expect {expect_rc})\nstdout:\n{proc.stdout}"
        f"\nstderr:\n{proc.stderr}"
    )
    return proc


def _strip_cycles(store: HedgeOpenStore) -> None:
    """把 prepare_attempt 自动分配的周期抹掉，回到「无周期历史数据」场景。

    本任务（cycle-core）引入发单分配后，用 store 方法构造的数据天然带
    cycle_id；回填脚本只适用于无周期数据的旧世界（cycle 表空、attempt.cycle_id
    全 NULL），故 populate 后先剥离，回填断言保持不变。
    """
    with store._lock, store._conn:
        store._conn.execute("DELETE FROM hedge_open_cycle")
        store._conn.execute("UPDATE hedge_open_attempt SET cycle_id = NULL")


def _populate_two_groups(tmp_path) -> str:
    """NOMUSDT forward（t1/a1、t2/a2）+ RSRUSDT reverse（t3/a3）+ 无 attempt 任务 t4。"""
    db = str(tmp_path / "ho.sqlite3")
    store = HedgeOpenStore(db)
    _create(store, "t1", "NOMUSDT", D.DIR_FORWARD, 1_000)
    _apply(store, "t1", "a1", 5_000)
    _create(store, "t2", "NOMUSDT", D.DIR_FORWARD, 2_000)
    _apply(store, "t2", "a2", 6_000)
    _create(store, "t3", "RSRUSDT", D.DIR_REVERSE, 1_500)
    _apply(store, "t3", "a3", 7_000, D.DIR_REVERSE)
    _create(store, "t4", "ZZZUSDT", D.DIR_FORWARD, 500)  # 无 attempt → 不建周期行
    _strip_cycles(store)
    store.close()
    return db


# ---------------------------------------------------------------------------
# 建表 / 迁移幂等
# ---------------------------------------------------------------------------

def test_migrate_creates_cycle_schema_idempotent(tmp_path):
    db = str(tmp_path / "ho.sqlite3")
    store = HedgeOpenStore(db)
    cycle_cols = {r[1] for r in store._conn.execute("PRAGMA table_info(hedge_open_cycle)")}
    assert cycle_cols == CYCLE_COLUMNS
    attempt_cols = {r[1] for r in store._conn.execute("PRAGMA table_info(hedge_open_attempt)")}
    assert "cycle_id" in attempt_cols
    cycle_idx = {r[1] for r in store._conn.execute("PRAGMA index_list(hedge_open_cycle)")}
    assert "idx_cycle_active" in cycle_idx
    attempt_idx = {r[1] for r in store._conn.execute("PRAGMA index_list(hedge_open_attempt)")}
    assert "idx_attempt_cycle" in attempt_idx
    store.close()

    # 重复构造：不重复加列、不重复建表、不报错
    store2 = HedgeOpenStore(db)
    cycle_cols2 = {r[1] for r in store2._conn.execute("PRAGMA table_info(hedge_open_cycle)")}
    attempt_cols2 = {r[1] for r in store2._conn.execute("PRAGMA table_info(hedge_open_attempt)")}
    assert cycle_cols2 == CYCLE_COLUMNS
    assert attempt_cols2 == attempt_cols
    assert {r[1] for r in store2._conn.execute("PRAGMA index_list(hedge_open_cycle)")} \
        == cycle_idx
    assert {r[1] for r in store2._conn.execute("PRAGMA index_list(hedge_open_attempt)")} \
        == attempt_idx
    store2.close()


def test_get_cycle_by_id_and_list_cycles_read_methods(tmp_path):
    db = _populate_two_groups(tmp_path)
    _run("--apply", "--audit", str(tmp_path / "audit.json"), db=db)
    store = HedgeOpenStore(db)
    try:
        assert store.get_cycle_by_id("does-not-exist") is None
        cycles = store.list_cycles()
        assert len(cycles) == 2
        # 排序：symbol ASC → direction → opened_at_us ASC
        assert [c["symbol"] for c in cycles] == ["NOMUSDT", "RSRUSDT"]
        nom = store.get_cycle_by_id(cycles[0]["id"])
        assert nom["symbol"] == "NOMUSDT"
        assert nom["direction"] == D.DIR_FORWARD
        assert nom["opened_at_us"] == 5_000
        assert nom["closed_at_us"] is None
        assert nom["close_reason"] is None
        assert nom["first_task_id"] == "t1"
        assert nom["last_task_id"] == "t2"
    finally:
        store.close()


# ---------------------------------------------------------------------------
# 回填脚本：dry-run / apply
# ---------------------------------------------------------------------------

def test_dry_run_writes_nothing(tmp_path):
    db = _populate_two_groups(tmp_path)
    before = Path(db).read_bytes()
    proc = _run(db=db)  # 不带 --apply
    out = proc.stdout
    assert "回填计划（dry-run，未写库）" in out
    assert "周期行：2" in out
    assert "NOMUSDT forward opened_at=1970-01-01T00:00:00.005000Z closed_at=NULL" in out
    assert "RSRUSDT reverse opened_at=1970-01-01T00:00:00.007000Z closed_at=NULL" in out
    assert "attempt.cycle_id 将回填：3 条" in out
    # 字节级证明：dry-run 未写任何内容
    assert Path(db).read_bytes() == before
    store = HedgeOpenStore(db)
    try:
        assert store.list_cycles() == []
        rows = store._conn.execute(
            "SELECT COUNT(*) FROM hedge_open_attempt WHERE cycle_id IS NOT NULL"
        ).fetchone()[0]
        assert rows == 0
    finally:
        store.close()


def test_apply_backfills_cycles_and_attempts(tmp_path):
    db = _populate_two_groups(tmp_path)
    proc = _run("--apply", "--audit", str(tmp_path / "audit.json"), db=db)
    assert "回填完成：周期行 0 -> 2" in proc.stdout
    assert "attempt.cycle_id 0 -> 3" in proc.stdout

    store = HedgeOpenStore(db)
    try:
        cycles = store.list_cycles()
        assert len(cycles) == 2
        by_symbol = {c["symbol"]: c for c in cycles}
        assert by_symbol["NOMUSDT"]["opened_at_us"] == 5_000
        assert by_symbol["NOMUSDT"]["closed_at_us"] is None
        assert by_symbol["NOMUSDT"]["close_reason"] is None
        assert by_symbol["NOMUSDT"]["first_task_id"] == "t1"
        assert by_symbol["NOMUSDT"]["last_task_id"] == "t2"
        assert by_symbol["RSRUSDT"]["opened_at_us"] == 7_000
        assert by_symbol["RSRUSDT"]["first_task_id"] == "t3"
        assert by_symbol["RSRUSDT"]["last_task_id"] == "t3"
        # attempt.cycle_id 按 task 所属 (coin, direction) 回填
        attempts = {
            r[1]: r[2] for r in store._conn.execute(
                "SELECT id, task_id, cycle_id FROM hedge_open_attempt"
            )
        }
        assert attempts["t1"] == by_symbol["NOMUSDT"]["id"]
        assert attempts["t2"] == by_symbol["NOMUSDT"]["id"]
        assert attempts["t3"] == by_symbol["RSRUSDT"]["id"]
        # 全部成功腿所属 attempt 的 cycle_id 非 NULL
        null_cycle = store._conn.execute(
            "SELECT COUNT(*) FROM hedge_open_attempt WHERE cycle_id IS NULL"
        ).fetchone()[0]
        assert null_cycle == 0
    finally:
        store.close()


def test_apply_refuses_second_run(tmp_path):
    db = _populate_two_groups(tmp_path)
    _run("--apply", db=db)
    proc = _run("--apply", db=db, expect_rc=2)
    assert "拒绝回填" in proc.stderr
    # 数据未被重复写：仍 2 行
    store = HedgeOpenStore(db)
    try:
        assert len(store.list_cycles()) == 2
    finally:
        store.close()


def test_apply_no_successful_leg_uses_attempt_created(tmp_path):
    db = str(tmp_path / "ho.sqlite3")
    store = HedgeOpenStore(db)
    _create(store, "t1", "AAAUSDT", D.DIR_FORWARD, 1_000)
    # 只 prepare 不 resolve：legs 保持 cumulative_base_qty='0'（无成功腿）
    attempt = store.prepare_attempt(
        "t1", "a1", D.DIR_FORWARD, "0.5", D.POS_MODE_BOTH,
        {"est_price": "50000"}, "hgo-a1-s", {"side": "BUY"}, D.SPOT_ORDER_PATH,
        "hgo-a1-p", {"side": "SELL"}, 9_999,
    )
    assert attempt is not None
    _strip_cycles(store)  # 剥离 prepare 自动分配的周期，回到回填适用场景
    store.close()

    _run("--apply", db=db)
    store = HedgeOpenStore(db)
    try:
        cycles = store.list_cycles()
        assert len(cycles) == 1
        assert cycles[0]["symbol"] == "AAAUSDT"
        assert cycles[0]["opened_at_us"] == 9_999  # 最早 attempt created_at_us
    finally:
        store.close()


def test_apply_skips_group_without_attempts(tmp_path):
    db = str(tmp_path / "ho.sqlite3")
    store = HedgeOpenStore(db)
    _create(store, "t1", "BBBUSDT", D.DIR_FORWARD, 1_000)  # 无 attempt
    store.close()
    _run("--apply", db=db, expect_rc=2)  # 无周期行可生成 → 拒绝
    store = HedgeOpenStore(db)
    try:
        assert store.list_cycles() == []
    finally:
        store.close()


# ---------------------------------------------------------------------------
# --split 人工分段 / --audit 审计
# ---------------------------------------------------------------------------

def test_split_creates_two_cycles_same_symbol(tmp_path):
    db = str(tmp_path / "ho.sqlite3")
    store = HedgeOpenStore(db)
    _create(store, "t1", "NOMUSDT", D.DIR_FORWARD, 1_000)
    _apply(store, "t1", "a1", 5_000)
    _create(store, "t2", "NOMUSDT", D.DIR_FORWARD, 3_000)
    _apply(store, "t2", "a2", 7_000)
    _strip_cycles(store)  # 剥离自动分配的周期，回到回填适用场景
    store.close()

    # 分段点 2000us：t1(created 1000) 归前段，t2(created 3000) 归后段
    _run("--split", "NOMUSDT,forward,1970-01-01T00:00:00.002000Z", "--apply", db=db)
    store = HedgeOpenStore(db)
    try:
        cycles = store.list_cycles()
        assert len(cycles) == 2
        assert [c["opened_at_us"] for c in cycles] == [5_000, 7_000]
        assert [c["first_task_id"] for c in cycles] == ["t1", "t2"]
        assert [c["last_task_id"] for c in cycles] == ["t1", "t2"]
        attempts = {
            r[1]: r[2] for r in store._conn.execute(
                "SELECT id, task_id, cycle_id FROM hedge_open_attempt"
            )
        }
        assert attempts["t1"] == cycles[0]["id"]
        assert attempts["t2"] == cycles[1]["id"]
    finally:
        store.close()


def test_audit_file_records_before_after_and_sql(tmp_path):
    db = _populate_two_groups(tmp_path)
    audit_path = str(tmp_path / "audit.json")
    _run("--apply", "--audit", audit_path, db=db)
    audit = json.loads(Path(audit_path).read_text(encoding="utf-8"))
    assert audit["before"]["cycle_rows"] == 0
    assert audit["before"]["attempts_with_cycle_id"] == 0
    assert audit["after"]["cycle_rows"] == 2
    assert audit["after"]["attempts_with_cycle_id"] == 3
    assert audit["diff"] == {
        "cycle_rows": "0 -> 2",
        "attempts_with_cycle_id": "0 -> 3",
        "attempts_updated": 3,
    }
    assert len(audit["cycles"]) == 2
    assert all(c["closed_at_us"] is None for c in audit["cycles"])
    sql_text = "\n".join(audit["sql"])
    assert "INSERT INTO hedge_open_cycle" in sql_text
    assert "UPDATE hedge_open_attempt SET cycle_id" in sql_text
    assert len(audit["sql"]) == 2 + 3  # 2 条 INSERT + 3 条 UPDATE


def test_dry_run_works_without_cycle_schema(tmp_path):
    """实盘副本场景：库还没有 hedge_open_cycle 表 / cycle_id 列，dry-run 也能出计划。"""
    db = _populate_two_groups(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE IF EXISTS hedge_open_cycle")
    conn.execute("DROP INDEX idx_attempt_cycle")
    conn.execute("ALTER TABLE hedge_open_attempt DROP COLUMN cycle_id")
    conn.commit()
    conn.close()

    proc = _run(db=db)  # dry-run 只读，不要求周期表已存在
    assert "周期行：2" in proc.stdout
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        has_cycle = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='hedge_open_cycle'"
        ).fetchone()
        assert has_cycle is None  # dry-run 未重建表
    finally:
        conn.close()
