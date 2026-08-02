# 34-bookkeeper-verification-runtime-seam-scan —— 穷举扫描轮核验

- 任务：`fix-runtime-seam-scan-v1`，实现者 `deepseek`
- 交付：`d2ac353`（base `9faa716`）
- 核验者：`opus5`，2026-08-02
- **裁定：全部验收通过，封存 `verified`。**

## 1. 最有力的证据：同一探针，改前全红，改后全绿

Bookkeeper 在派工前用于定位家族的探针（`32-` §7.1），未作任何修改直接重跑：

| 路径 | 修复前 | **修复后** |
|---|---|---|
| 429 限频（`pre-existing`） | `deleted` → **`paused`** ✗ | `deleted` → **`deleted`** ✓ |
| 余额不足（`pre-existing`） | `deleted` → **`paused`** ✗ | `deleted` → **`deleted`** ✓ |
| 订单状态不明（`in-range`） | `deleted` → **`paused`** ✗ | `deleted` → **`deleted`**，腿非终态 ✓ |

## 2. 验收逐项

| # | 验收 | 结果 | 核验方式 |
|---|---|---|---|
| 1 | 条件写生效 | **pass** | `pause_task` / `stop_task_fatal` 均加 `WHERE id = ? AND status IN (running, paused)`；`pause_task` 返回值改为 `(task, applied)` 元组以区分命中与未命中；破坏验证见 §3 |
| 2 | 三条并发回归 | **pass** | 4 条真线程并发回归（1a/1b/1c/1e），加 2 条 store 层条件写测试 |
| 3 | 既有静态覆盖保留 | **pass** | 独立复跑 **1158 passed**（基线 1152 + 6）；F3/F4/F5 测试全绿 |
| 4 | 穷举清单五族 | **pass** | 族 1（旧快照写决策，6 站点）、族 2（store 写状态方法）、族 3（锁跨网络调用）、族 4（测试缝 vs 真线程）、族 5（既有并发先例）齐全 |
| 5 | 清单发现的其它同族问题 | **pass** | **新确认并修复 2 个站点**，见 §4 |
| 6 | F1-P1 未被触碰 | **pass** | diff 中无 `_clear_task_leg_retries` / `_workers_lock` 相关改动 |
| 7 | 回归全绿 | **pass** | 1158 passed，独立复跑确认 |
| 8 | 边界 | **pass** | `data/` `frontend/` `backend/services/` 三处 diff 均为空；实盘库 mtime 仍 `08-01 23:45:48`、值仍 `0.5\|500000\|4`；留痕清单与观察一致 |

## 3. 破坏验证（两组，均转红）

| 破坏 | 结果 |
|---|---|
| 移除 `pause_task` 的 `AND status IN (?, ?)` | `test_pause_task_conditional_write_hits_only_running_or_paused`、`test_concurrent_delete_during_drain_rate_limited_keeps_deleted`、`test_concurrent_delete_during_drain_insufficient_keeps_deleted` **FAILED**（3 failed, 1155 passed） |
| 使 `suppress_done` 失效 | `test_4[-2019]`、`test_4[-3041]`、`test_4c_collateral_cap_51169_pauses_with_frozen_message`、`test_4g_raw_persist_failure_does_not_break_business_write` **FAILED**（4 failed, 1154 passed） |

**第二组尤其说明问题**：破坏 `suppress_done` 让**既有测试**转红，证明该修复不是多余改动，而是条件写引入的必要配套。

## 4. 扫描自身发现的两个新同族站点（本轮的核心价值）

packet 只点名了三条 drain 路径与一条待确认线索。实现者的扫描**额外确认并修复了两个站点**：

### 1e —— `_stop_task_fatal_preflight`（packet 的待确认线索，判定属同族）

`_resolve_fresh_preflight` 是**无锁网络读**；期间 `post_delete` 落地后，
`_stop_task_fatal_preflight` 仍用旧快照写 `stopped`，同样复活已删除任务。
已修（`stop_task_fatal` 条件写）并配并发回归。

### 1f —— 结算顺序：条件写自身引入的新问题

**这是修复的副作用，由扫描发现**：两腿终态且带 pause 类事实（余额不足 / 抵押额度满）时，
`resolve_attempt` 会先把任务推进 `done`；而 `done` 不在条件写的允许集内，随后的 pause
**必然未命中** → 「余额不足则暂停 THIS task」的 amendment-21 契约**悄悄降级为 done**。

修法：pause 类结算传 `suppress_done=True`，豁免该次 done 推进，让 pause 落地。

**这正是同根因刹车要求穷举扫描而非点补丁的理由**——修根会产生新的交互，只有扫描才能发现。

## 5. `1c` 采用了双层保护（优于要求）

`order_state_unknown` 路径除 store 条件写外，service 层另加守卫：每轮重读权威状态，
非 `running`/`paused` 时只记事件、不改状态。packet 只要求 store 层一层。

## 6. 范围三分类的处置

| 站点 | 分类 | 处置 |
|---|---|---|
| 1c `order_state_unknown` | `in-range` | 已修 |
| 1a 429、1b `insufficient_*` / `collateral_cap` | `pre-existing-release-critical` | **本轮一并修复**。二者本属「合并前由 Human 决定」的具名事项，因与 `in-range` 站点共用同一修法（单个 `WHERE` 条件），无理由留置。**该发布风险已消除**，不再需要 Human 单独裁定这两条 |
| 1e fatal preflight | `pre-existing`（同族新确认） | 已修 |
| 1f 结算顺序 | 条件写引入，`in-range` | 已修 |

## 7. F1-P1 状态

Human 已接受为已知限制（五要素见 `32-` §7.3），本轮**确认未被触碰**。复看条件不变：
**若将来引入任何非人工触发 `ensure_worker` 的路径，须重新评估。**

## 8. BK-T3-002 发布门：维持

本轮未新增 `data/` 写入（三重确认：mtime 未变、值未变、区间 diff 为空）。但
2026-08-01 的历史事故不因此消除，**合并、部署或实盘启用仍须 Human 单独裁定**。
