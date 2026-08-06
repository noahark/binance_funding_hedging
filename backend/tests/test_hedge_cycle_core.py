"""持仓周期核心逻辑用例（功能一剩余块，stage 2026-08-hedge-position-cycle-v1）。

覆盖（对应设计 v1 §4/§5 与 stage2 §3.3-§3.6 验收）：
- prepare_attempt 事务内分配：无活跃周期新建（opened_at=now、first/last=task）、
  有活跃复用、失败路径（task 非 RUNNING）不留孤儿 cycle、close 后重开新 cycle；
- aggregate_positions 周期拆桶：输出含 cycle_id/cycle_opened_at/cycle_closed_at、
  同 cycle 加权数值与旧口径一致、多周期独立成行、SQL-A 非零行告警落库；
- merge_positions P0-1：同 (coin, direction) 一已平仓 + 一活跃周期输出两行
  （UM 骨架挂活跃周期 normal，已平仓周期独立 no_um）；同键多活跃取最近 opened；
- close_cycle 契约：幂等（重复不覆盖）、单向（NULL→值）、自带事务。
"""
from __future__ import annotations

import json

from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.executor import AttemptOutcome
from backend.hedge_open_tasks.store import HedgeOpenStore


def _outcome(attempt_id: str, qty: str = "0.5", price: str = "50000") -> AttemptOutcome:
    from decimal import Decimal as _D
    quote = str(_D(qty) * _D(price))  # 已知 notional → avg 可算（T1 契约）
    return AttemptOutcome(
        attempt_id=attempt_id,
        category=D.ATTEMPT_SUCCESS,
        spot={"status": D.LEG_FILLED, "filled_qty": qty, "avg_price": price,
              "cumulative_quote": quote,
              "order_id": f"os-{attempt_id}", "client_order_id": f"hgo-{attempt_id}-s"},
        perp={"status": D.LEG_FILLED, "filled_qty": qty, "avg_price": price,
              "cumulative_quote": quote,
              "order_id": f"op-{attempt_id}", "client_order_id": f"hgo-{attempt_id}-p"},
        record_payload={"transport": "dry_run_record", "posted": False,
                        "spot_order_params": {}, "perp_order_params": {}},
        exposure=None,
    )


def _create(store, task_id: str, coin: str = "BTCUSDT", direction: str = D.DIR_FORWARD,
            created_us: int = 1_000):
    return store.create_task(
        task_id, coin, direction, D.MODE_IMMEDIATE, "0.5", 3, "0.5",
        D.POS_MODE_BOTH, {"est_price": "50000"}, created_us,
    )


def _apply(store, task_id: str, attempt_uuid: str, now_us: int,
           direction: str = D.DIR_FORWARD, qty: str = "0.5"):
    """成功 attempt：dispatched_at_us = resolve 的 now_us（可控派发时间）。"""
    attempt = store.prepare_attempt(
        task_id, attempt_uuid, direction, "0.5", D.POS_MODE_BOTH,
        {"est_price": "50000"}, f"hgo-{attempt_uuid}-s", {"side": "BUY"},
        D.SPOT_ORDER_PATH, f"hgo-{attempt_uuid}-p", {"side": "SELL"}, now_us,
    )
    assert attempt is not None, "task must be dispatch-eligible"
    store.resolve_attempt(attempt["id"], _outcome(attempt_uuid, qty), now_us)
    return attempt


# ---------------------------------------------------------------------------
# 分配（stage2 §3.4）
# ---------------------------------------------------------------------------

def test_assign_creates_cycle_when_none_active(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1")
    attempt = _apply(store, "t1", "a1", 5_000)
    cycles = store.list_cycles()
    assert len(cycles) == 1
    c = cycles[0]
    assert c["symbol"] == "BTCUSDT" and c["direction"] == D.DIR_FORWARD
    assert c["opened_at_us"] == 5_000          # opened_at = 本次派发时间
    assert c["closed_at_us"] is None
    assert c["first_task_id"] == "t1" and c["last_task_id"] == "t1"
    assert attempt["id"] is not None
    row = store._conn.execute(
        "SELECT cycle_id FROM hedge_open_attempt WHERE id = ?", (attempt["id"],)
    ).fetchone()
    assert row["cycle_id"] == c["id"]
    store.close()


def test_assign_reuses_active_cycle(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1")
    _apply(store, "t1", "a1", 5_000)
    first = store.list_cycles()[0]
    # 同任务第二次 attempt（同 task 加仓，场景 5）→ 复用同一活跃 cycle
    attempt2 = _apply(store, "t1", "a2", 6_000)
    assert len(store.list_cycles()) == 1
    row = store._conn.execute(
        "SELECT cycle_id FROM hedge_open_attempt WHERE id = ?", (attempt2["id"],)
    ).fetchone()
    assert row["cycle_id"] == first["id"]
    store.close()


def test_assign_no_orphan_cycle_on_failed_path(tmp_path):
    """失败路径（task 非 RUNNING）在 cycle 创建之前返回，不留孤儿 cycle。"""
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1")
    store.set_task_status("t1", D.STATUS_PAUSED, 2_000)
    assert store.prepare_attempt(
        "t1", "a1", D.DIR_FORWARD, "0.5", D.POS_MODE_BOTH,
        {"est_price": "50000"}, "hgo-a1-s", {"side": "BUY"}, D.SPOT_ORDER_PATH,
        "hgo-a1-p", {"side": "SELL"}, 5_000,
    ) is None
    assert store.list_cycles() == []
    store.close()


def test_assign_new_cycle_after_close_scenario_b(tmp_path):
    """场景 B/4：close 后再开 → 新 cycle、新起始时间。"""
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1")
    _apply(store, "t1", "a1", 5_000)
    c1 = store.list_cycles()[0]
    store.close_cycle(c1["id"], 7_000, "manual_verify")
    _create(store, "t2", coin="BTCUSDT", direction=D.DIR_FORWARD, created_us=8_000)
    attempt = _apply(store, "t2", "a2", 9_000)
    cycles = store.list_cycles()
    assert len(cycles) == 2
    c2 = [c for c in cycles if c["id"] != c1["id"]][0]
    assert c2["opened_at_us"] == 9_000
    assert c2["first_task_id"] == "t2"
    row = store._conn.execute(
        "SELECT cycle_id FROM hedge_open_attempt WHERE id = ?", (attempt["id"],)
    ).fetchone()
    assert row["cycle_id"] == c2["id"]
    store.close()


def test_assign_reuse_after_delete_scenario_3(tmp_path):
    """场景 3：删任务重建（仓未平）→ 复用活跃 cycle。"""
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1")
    _apply(store, "t1", "a1", 5_000)
    c1 = store.list_cycles()[0]
    store.set_task_status("t1", D.STATUS_DELETED, 6_000)
    _create(store, "t2", coin="BTCUSDT", direction=D.DIR_FORWARD, created_us=7_000)
    attempt = _apply(store, "t2", "a2", 8_000)
    assert len(store.list_cycles()) == 1  # 无新 cycle
    row = store._conn.execute(
        "SELECT cycle_id FROM hedge_open_attempt WHERE id = ?", (attempt["id"],)
    ).fetchone()
    assert row["cycle_id"] == c1["id"]
    store.close()


# ---------------------------------------------------------------------------
# 聚合拆分（stage2 §3.5）
# ---------------------------------------------------------------------------

def test_aggregate_emits_cycle_fields_and_unchanged_weighting(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1")
    _apply(store, "t1", "a1", 5_000)
    pos = store.aggregate_positions()
    assert len(pos) == 1
    p = pos[0]
    # 新增周期字段
    assert p["cycle_id"] is not None
    assert p["cycle_opened_at"] == D.us_to_iso(5_000)
    assert p["cycle_closed_at"] is None
    # 同 cycle 加权与旧口径一致：spot 0.5@50000、perp 0.5@50000（forward SELL）
    assert p["spot_qty"] == "0.5" and p["spot_avg"] == "50000"
    assert p["perp_qty"] == "0.5" and p["perp_avg"] == "50000"
    assert p["position_qty"].startswith("-")
    assert p["includes_deleted_task"] is False
    store.close()


def test_aggregate_same_cycle_adds_up_scenario_a(tmp_path):
    """场景 A/5：同 cycle 加仓并入同一行，起始时间 = 首次派发时间。"""
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1")
    _apply(store, "t1", "a1", 5_000, qty="0.5")
    _apply(store, "t1", "a2", 6_000, qty="0.5")
    pos = store.aggregate_positions()
    assert len(pos) == 1
    assert pos[0]["spot_qty"] == "1"   # fmt_decimal 去尾零：0.5+0.5 → "1"
    assert pos[0]["perp_qty"] == "1"
    assert pos[0]["spot_avg"] == "50000"
    assert pos[0]["cycle_opened_at"] == D.us_to_iso(5_000)  # 首次派发
    store.close()


def test_aggregate_two_cycles_two_rows_scenario_b(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1")
    _apply(store, "t1", "a1", 5_000)
    c1 = store.list_cycles()[0]
    store.close_cycle(c1["id"], 7_000, "manual_verify")
    _create(store, "t2", coin="BTCUSDT", direction=D.DIR_FORWARD, created_us=8_000)
    _apply(store, "t2", "a2", 9_000)
    pos = store.aggregate_positions()
    # Human 2026-08：持仓表只显示「未平仓周期」——已平仓的旧周期被后端过滤，
    # 只剩新活跃周期一行（已平仓周期只在历史仓位页 close_log 呈现）。
    assert len(pos) == 1, f"已平仓周期应被过滤，只剩新活跃周期: {pos}"
    assert pos[0]["cycle_id"] == store.list_cycles()[1]["id"]
    assert pos[0]["cycle_closed_at"] is None
    assert pos[0]["cycle_opened_at"] == D.us_to_iso(9_000)
    store.close()


def test_aggregate_sql_a_nonzero_writes_warning(tmp_path):
    """P2-1：hedge_open_fill 非零行 → aggregate 落审计告警，而非静默并入。"""
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1")
    store.insert_fill("t1", "att1", _outcome("att1"), 5_000)
    store.aggregate_positions()
    rows = store._conn.execute(
        "SELECT kind, payload FROM hedge_open_log WHERE kind = 'aggregate_sql_a_nonzero'"
    ).fetchall()
    assert len(rows) == 1
    payload = json.loads(rows[0]["payload"])
    assert payload["row_count"] == 1
    store.close()


# ---------------------------------------------------------------------------
# merge 多周期匹配（P0-1，设计 v1 §5.4）
# ---------------------------------------------------------------------------

def _cycle_bucket(cycle_id, opened_us, closed_us=None, coin="BTCUSDT",
                  direction=D.DIR_FORWARD, avg="50000"):
    return {
        "coin": coin, "direction": direction,
        "position_qty": "-0.5", "spot_qty": "0.5", "perp_qty": "0.5",
        "spot_avg": avg, "perp_avg": avg,
        "spot_avg_price_incomplete": False, "perp_avg_price_incomplete": False,
        "includes_deleted_task": False, "open_basis_rate": "0",
        "price_pnl": "0", "accrued_funding": "0", "borrow_interest": "0",
        "net_pnl": "0",
        "cycle_id": cycle_id,
        "cycle_opened_at": D.us_to_iso(opened_us),
        "cycle_closed_at": D.us_to_iso(closed_us) if closed_us is not None else None,
    }


def _um(symbol="BTCUSDT", side="SHORT", amt="-0.5", entry="50000"):
    return {
        "symbol": symbol, "position_side": side, "position_amt": amt,
        "notional_usdt": "-25000", "entry_price": entry, "mark_price": entry,
        "liquidation_price": None, "unrealized_profit": "-1.2",
    }


def test_merge_2b_closed_and_active_cycles_two_rows(tmp_path):
    """验收用例 2b：同 (coin, direction) 一已平仓周期 + 一活跃周期 → 两行。"""
    closed_bucket = _cycle_bucket("c-old", 1_000, closed_us=3_000, avg="40000")
    active_bucket = _cycle_bucket("c-new", 5_000, closed_us=None, avg="50000")
    pa = {"verified": True, "um_positions": [_um()],
          "balances_unified": [], "balances_spot": [], "checked_at": 1, "error": None}
    merged, _ = D.merge_positions([closed_bucket, active_bucket], pa)
    assert len(merged) == 2
    # 排序：cycle_opened_at ASC → 已平仓（旧）在前，活跃（新）在后
    old, new = merged
    assert old["cycle_id"] == "c-old" and old["match_status"] == "no_um"
    assert old["cycle_closed_at"] == D.us_to_iso(3_000)
    assert old["spot_avg"] == "40000"
    assert new["cycle_id"] == "c-new" and new["match_status"] == "normal"
    assert new["cycle_closed_at"] is None
    assert new["um_entry_price"] == "50000"
    assert new["spot_avg"] == "50000"  # 活跃周期均价挂到 UM 骨架行
    # 无静默丢弃：两个周期桶都出现在输出
    assert {r["cycle_id"] for r in merged} == {"c-old", "c-new"}


def test_merge_active_only_matches_um_normal(tmp_path):
    active = _cycle_bucket("c-new", 5_000)
    pa = {"verified": True, "um_positions": [_um()],
          "balances_unified": [], "balances_spot": [], "checked_at": 1, "error": None}
    merged, _ = D.merge_positions([active], pa)
    assert len(merged) == 1
    assert merged[0]["match_status"] == "normal"
    assert merged[0]["cycle_id"] == "c-new"


def test_merge_no_active_bucket_um_row_is_no_task(tmp_path):
    """该 (coin, direction) 只有已平仓周期 → UM 行 no_task，已平仓周期独立 no_um。"""
    closed = _cycle_bucket("c-old", 1_000, closed_us=3_000)
    pa = {"verified": True, "um_positions": [_um()],
          "balances_unified": [], "balances_spot": [], "checked_at": 1, "error": None}
    merged, _ = D.merge_positions([closed], pa)
    assert len(merged) == 2
    by_id = {r["cycle_id"]: r for r in merged}
    assert by_id[None]["match_status"] == "no_task"   # UM 骨架行（无匹配周期桶）
    assert by_id["c-old"]["match_status"] == "no_um"
    assert by_id["c-old"]["cycle_closed_at"] == D.us_to_iso(3_000)
    # no_task 行周期字段为 None（_merge_empty_bucket_row）
    assert by_id[None]["cycle_opened_at"] is None
    assert by_id[None]["cycle_closed_at"] is None


def test_merge_two_active_cycles_matches_newest(tmp_path):
    """异常场景：同键多个活跃周期 → UM 只挂最近 opened 者，其余 no_um 独立输出。"""
    old_active = _cycle_bucket("c-a", 1_000, closed_us=None, avg="40000")
    new_active = _cycle_bucket("c-b", 5_000, closed_us=None, avg="50000")
    pa = {"verified": True, "um_positions": [_um()],
          "balances_unified": [], "balances_spot": [], "checked_at": 1, "error": None}
    merged, _ = D.merge_positions([old_active, new_active], pa)
    assert len(merged) == 2
    by_id = {r["cycle_id"]: r for r in merged}
    assert by_id["c-b"]["match_status"] == "normal"      # 最近 opened 被消费
    assert by_id["c-a"]["match_status"] == "no_um"       # 其余独立 no_um
    assert by_id["c-b"]["spot_avg"] == "50000"


# ---------------------------------------------------------------------------
# close 契约（stage2 §3.6）
# ---------------------------------------------------------------------------

def test_close_cycle_idempotent_one_way_transactional(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1")
    _apply(store, "t1", "a1", 5_000)
    c = store.list_cycles()[0]

    store.close_cycle(c["id"], 7_000, "manual_verify")
    row = store.get_cycle_by_id(c["id"])
    assert row["closed_at_us"] == 7_000
    assert row["close_reason"] == "manual_verify"

    # 幂等：重复关闭（不同值）不覆盖
    store.close_cycle(c["id"], 8_000, "auto_close")
    row = store.get_cycle_by_id(c["id"])
    assert row["closed_at_us"] == 7_000
    assert row["close_reason"] == "manual_verify"

    # 单向：NULL→值 后不再变（已由幂等断言覆盖）；close 后不再活跃
    assert store.get_active_cycle("BTCUSDT", D.DIR_FORWARD) is None
    store.close()


def test_close_cycle_unknown_id_is_noop(tmp_path):
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    store.close_cycle("no-such-cycle", 7_000, "manual_verify")  # 不抛错、无副作用
    assert store.list_cycles() == []
    store.close()
