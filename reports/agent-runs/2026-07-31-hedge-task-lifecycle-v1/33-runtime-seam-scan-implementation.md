# 33-runtime-seam-scan-implementation —— 运行时接缝穷举扫描 + F2-P1 根修复

- 任务：`fix-runtime-seam-scan-v1`（实现者：deepseek）
- 分支：`stage/2026-07-31-hedge-task-lifecycle-v1`（开工时确认）
- 评审来源：`31-review-1-gpt-task3-r2.md`（F1-P1 / F2-P1）；Bookkeeper 先导扫描 `32-` §7
- `rework_count`：**2/3**（同根因刹车触发，本轮为穷举扫描轮；packet 于 2026-08-02 重写，不另计数）

---

## 一、运行时接缝穷举扫描清单（主交付物，放最前）

本轮受审范围：本 stage 新增的**每腿重试计数机制、`SIGNAL_ORDER_STATE_UNKNOWN`、
`PAUSE_REASON_ORDER_STATE_UNKNOWN`**，及**既有缺陷家族**（旧快照写任务状态）。
按 `AGENTS.md` §8 同根因刹车要求，枚举运行时/并发维度全部接缝，逐项标注
「已正确接线 / 需修复（本轮已修）/ 不适用 + 理由」。

### 族 1：旧快照写决策族（worker 在无锁网络调用后，用查询前快照写任务状态）

| # | 站点 | 路径 | 判定 | 处理 |
|---|---|---|---|---|
| 1a | drain 429（`SIGNAL_RATE_LIMITED`） | `_worker_round` 1226 → `_pause_task_local` → `pause_task` | **需修复（pre-existing-release-critical）** | `pause_task` 条件写（running/paused）覆盖；并发回归 `test_concurrent_delete_during_drain_rate_limited_keeps_deleted` |
| 1b | drain insufficient / collateral_cap（`SIGNAL_TASK_LOCAL_PAUSE`） | `_worker_round` 1248 → `_pause_from_signal` → `pause_task` | **需修复（pre-existing-release-critical）** | 同一条件写覆盖；并发回归 `test_concurrent_delete_during_drain_insufficient_keeps_deleted` |
| 1c | drain order_state_unknown（in-range） | `_worker_round` 1235 → `_signal_order_state_unknown_recovery` → `pause_task` | **需修复（in-range）** | 双层保护：service 守卫（每轮重读权威状态，非 running/paused 只记事件）+ store 条件写；并发回归 `test_concurrent_delete_during_drain_order_state_unknown_keeps_deleted` |
| 1d | **dispatch 阶段 429 / insufficient** | `_worker_round` 1263-1270（dispatch 返回 signal 后） | **已正确接线（经同一守卫）** | 与 drain 共用 `_pause_task_local` → 同一条件写；dispatch 期间 post_delete 同样不复活。无独立测试（与 1a/1b 同一代码路径） |
| 1e | **`_stop_task_fatal_preflight`（fatal preflight）** | `_worker_round` → `_dispatch_one_for_task` → `_resolve_fresh_preflight`（无锁网络读）→ `_stop_task_fatal_preflight` → `stop_task_fatal` | **需修复（同族新确认站点）** | packet 要求给出明确结论：**属同族**（preflight 读取期间 post_delete → 旧快照写 `stopped` 复活）。已修：`stop_task_fatal` 条件写（running/paused）+ 并发回归 `test_concurrent_delete_during_fatal_preflight_keeps_deleted` |
| 1f | **结算推进（`_apply_task_counters` 的 done 推进）** | `_dispatch_live` 无 querying 的 pause 类先结算（可能置 done）→ worker 再 pause → 条件写拒绝 | **需修复（同族顺序站点）** | pause 类结算用 `suppress_done=True`（done 推进豁免，让 pause 落地）；test_4×2 / test_4c / test_4g 回归保护。破坏 suppress_done → 4 条红（见 §4） |

**结论**：三站点之外确认了**两个**同族新站点（1e fatal preflight、1f 结算顺序），均已修复；
drain/dispatch 两条 429 与两条 insufficient 路径经同一 `pause_task` 条件写覆盖。

### 族 2：每一处写状态 / 写 pause_reason 的 store 方法

| store 方法 | 条件守卫 | 判定 |
|---|---|---|
| `pause_task` | **本轮新增**：`WHERE status IN (running, paused)` | 已修 |
| `stop_task_fatal` | **本轮新增**：`WHERE status IN (running, paused)` | 已修 |
| `set_task_status` | 无 | **不适用**：唯一调用点（post_start 667 / post_pause 684 / post_delete 695 / post_fill_once/all 706/719）全部「先 `_get_task_or_404` 读**权威**状态 → 状态合法性检查（409）→ 写」；worker 内部不使用。并发覆盖风险仅存在于**人工入口之间**（操作者同时点两个按钮）——是操作者意图冲突而非旧快照族，且各入口有 409 状态校验兜底。完全串行化人工操作属产品决策，超出本轮 |
| `set_failure_pause_threshold` / `clear_leg_exposure` | 无 | **不适用**：辅助字段写（非状态写），调用点读权威状态 |
| `_apply_task_counters`（结算状态推进） | 读 DB 当前状态（非旧快照） | **已正确接线**：结算读权威 `task["status"]`，deleted/done/stopped 不被推进；done 推进与 pause 的冲突已由 `suppress_done` 修复（族 1f） |

### 族 3：锁的持有范围（哪些区间跨越无锁 executor 网络调用）

| 区间 | 网络调用 | 判定 |
|---|---|---|
| `_reconcile_own_legs` | `query_leg`（无 store 锁，Q6 设计） | **设计如此（已正确接线）**：Q6 明确 executor 调用不在 store 事务内；条件写是「网络调用后写状态」的安全网 |
| `_dispatch_live` | `executor.dispatch`（无锁） | 同上 |
| `_resolve_fresh_preflight` | `provider.get_snapshot`（无锁） | 同上；fatal 写 stopped 已有条件写守卫（族 1e） |
| store 全部 SQL | 无网络调用 | 均在 `with self._lock` 内 ✓ |

### 族 4：测试缝与真实线程路径的差异

| 维度 | `_pump_worker`（测试缝） | 真实线程 worker |
|---|---|---|
| 线程 | 无（调用者线程同步） | 有（`_run_task_worker`） |
| pacing | 无 | 有（`ev.wait(interval_s)`） |
| 能覆盖 | 顺序路径全部：计数、收口、静态状态、重启、清理 | 上述 + **查询进行中外部写**的交错 |
| **不能覆盖** | **查询进行中 `post_delete` 等并发写**——上一轮三态测试（drain 前静态设状态）正因如此结构性地漏掉 F2-P1 | 已覆盖 |

本轮新增 4 条真线程并发回归（屏障控制查询中 post_delete 时机），覆盖 1a/1b/1c/1e 四个站点；
`_pump_worker` 保留用于顺序路径。

### 族 5：既有并发先例

| 先例 | 新机制对照 | 判定 |
|---|---|---|
| `_rate_limit_stamp_pending`（in-process，重启丢一次计数） | `_leg_query_retries`（in-process，重启归零） | **已正确接线**：同类「重启重来」模式，代价已记录于 PROJECT_STATE.md；重启语义有测试 |
| F1-P1（worker 交接计数清理竞态） | 本轮范围 | **不适用**：Human 已接受为已知限制（`32-` §7.3 五要素），复看条件（引入非人工触发 `ensure_worker` 路径时）已记录；本轮未触碰、未加测试 |

### 清单结论

旧快照写决策族（族 1）在 packet 已知三站点之外确认 **2 个新站点**（1e、1f），全部修复并配可失败
测试；族 2-5 逐项给出判定。**清单外未发现遗漏。**

---

## 二、主修实现：`store.pause_task` 条件写（一处覆盖三条）

- `pause_task`：`UPDATE ... WHERE id = ? AND status IN ('running', 'paused')`；返回 `(dict | None, bool)`
  ——`applied=True` 命中（已暂停），`applied=False` 未命中（任务不存在或状态不可暂停），调用方可区分。
- `_pause_task_local`：适配新返回形状；未命中时**不更新本地快照、不改状态，事件仍记录**（entries 可见）。
- 三条 drain 收口路径（429 / insufficient / order_state_unknown）与两条 dispatch 路径（1d）共用该守卫，
  **未在调用点各加守卫**（非点补丁）。

## 三、同族修复

1. **`stop_task_fatal` 条件写**（族 1e）：`WHERE status IN (running, paused)`；`None` 覆盖「不存在/不可停」，
   `_stop_task_fatal_preflight` 仍无条件记录 `task_stopped` 事件。
2. **`suppress_done`**（族 1f）：`_apply_task_counters` / `resolve_attempt` 新增 `suppress_done` 参数；
   `_dispatch_live` 对「无 querying 的 pause 类」结算传 `True`——pause 类结算不推进 done，让 amendment-21
   「insufficient → 立即 pause」契约落地。计数器照常推进，仅豁免自动 done 推进。

## 四、破坏验证实际输出（还原后全量复跑 1158 passed）

| 破坏 | 输出（实际） |
|---|---|
| `pause_task` 条件写改回无条件 | `FAILED test_concurrent_delete_during_drain_rate_limited_keeps_deleted`、`FAILED test_concurrent_delete_during_drain_insufficient_keeps_deleted`、`FAILED test_pause_task_conditional_write_hits_only_running_or_paused`（3 failed） |
| `order_state_unknown`：同时破坏 store 条件写 + `_signal_order_state_unknown_recovery` 守卫 | `FAILED test_concurrent_delete_during_drain_order_state_unknown_keeps_deleted`（1 failed；单层破坏有另一层兜底，属防御纵深） |
| `stop_task_fatal` 条件写改回无条件 | `FAILED test_concurrent_delete_during_fatal_preflight_keeps_deleted`、`FAILED test_stop_task_fatal_conditional_write_misses_on_non_running`（2 failed） |
| `_dispatch_live` 去掉 `suppress_done=True` | `FAILED test_4_task_a_insufficient_funds_pauses_and_b_still_dispatches`[-2019]、[-3041]、`FAILED test_4c_collateral_cap_51169_pauses_with_frozen_message`、`FAILED test_4g_raw_persist_failure_does_not_break_business_write`（4 failed） |

## 五、新增测试

- `test_concurrent_delete_during_drain_rate_limited_keeps_deleted`（1a）
- `test_concurrent_delete_during_drain_insufficient_keeps_deleted`（1b）
- `test_concurrent_delete_during_drain_order_state_unknown_keeps_deleted`（1c，双层保护）
- `test_concurrent_delete_during_fatal_preflight_keeps_deleted`（1e）
- `test_pause_task_conditional_write_hits_only_running_or_paused`（store 层）
- `test_stop_task_fatal_conditional_write_misses_on_non_running`（store 层）

并发测试均断言：最终状态 `deleted`（粘性）、腿非终态、无重发（`dispatch_calls` 不变）、
entries 有对应事件（429→`rate_limited`、insufficient→`task_paused`+reason、order_state_unknown→
`task_paused`+reason、fatal→`task_stopped`+stop_reason）。

## 六、回归与边界

- 全量：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider backend/tests/ -q` →
  **1158 passed**（基线 1152 + 6）。输出存 `65-runtime-seam-scan-test-output.txt`。
- 既有静态覆盖保留：上一轮三种静态终态测试（`test_inconclusive_cap_drain_keeps_non_running_status_sticky`×3）
  与 F3/F4/F5 测试全部绿。
- F1-P1 未被触碰（Human 已接受为限制；未改 `_run_task_worker` finally 原子性、未加测试）。
- 边界：未改 `live_hedge_executor.py` / `frontend/` / 429 分类与信号语义 / 51169 文案区 /
  `private_client.py`；未新增数据库列；500ms 默认、迁移回填 SQL、抖动移除、`_confirm_um_figures` 语义未动；
  `test_hedge_review2_regressions.py` 本轮零改动。
- 改动文件：`backend/hedge_open_tasks/store.py`、`backend/hedge_open_tasks/service.py`、
  `backend/tests/test_hedge_task_local.py`、`backend/tests/test_hedge_store.py`。

## 七、`data/` 红线留痕

- 全部测试运行使用 pytest `tmp_path`（系统临时目录），**无任何命令指向 `data/`**；
- 破坏验证：3 个内联 `python3 - <<EOF` 脚本，只改写 `backend/hedge_open_tasks/store.py` 与
  `service.py` 源码（随后从 `/tmp/*.bak` 还原），**不触碰任何数据库**；
- 无 sqlite3 直接调用、无指向 `data/` 的探针或副本命令；`git status --short data/` 为空。
- **结论**：本轮未写入 `data/` 下任何数据库。BK-T3-002 发布门维持（不因本轮解除）。
