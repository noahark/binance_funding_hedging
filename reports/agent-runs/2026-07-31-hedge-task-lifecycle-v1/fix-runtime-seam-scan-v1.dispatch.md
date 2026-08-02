# fix-runtime-seam-scan-v1.dispatch

```text
Identity:
  task_id:         fix-runtime-seam-scan-v1
  target_role:     Implementer
  target_model:    deepseek
  provider:        deepseek
  status_revision: 32
  required_skill:  agents/skills/senior-developer.md
```

## 读取位置（先确认）

主工作区 `/Users/ark/Desktop/ai code/funding_hedging`，分支
`stage/2026-07-31-hedge-task-lifecycle-v1`。开工前 `pwd && git branch --show-current`。

## Goal —— 这是一次穷举根因扫描，不是两个点补丁

`AGENTS.md` §8 的**同根因刹车已触发**（判定见 `32-` §3）：连续两轮 `REWORK` 归因于
同一根因，**禁止第三次点补丁**。

**根因（评审者 `31-` §3 原文，逐字引用）**：

> `29-` §8 的 15 项清单覆盖了静态契约，并正确覆盖了 entries、状态、404、429、payload、
> 文案、API、恢复和 schema 边界。但它**不穷尽运行时接缝**：
> - 清单 #3 将 worker 生命周期标为已正确接线，却没有单列「registry 删除 → 计数清理 →
>   新 worker handoff」的并发契约，遗漏 F1-P1；
> - 清单 #2 将状态粘性标为已正确接线，却只验证已有状态快照，遗漏「查询期间状态变更后
>   仍使用旧快照」的契约，遗漏 F2-P1。

因此本任务的**主交付物是一份运行时接缝穷举清单**，修复是清单的产物而非清单的替代。

`rework_count` 由 `1` 递增为 **`2`**（扫描本身算一轮，§8）。**上限 3，此后仅剩 1 次。**
若本轮之后再出 `REWORK`，须由 Human 在「缩小范围 / 重新设计 / 接受限制 / 停止」中选择，
Bookkeeper 不得自行再派修复。**请据此把握本轮的彻底程度。**

## 第一交付物：运行时接缝穷举清单

对本 stage 新增的三样东西——**每腿重试计数机制**、`SIGNAL_ORDER_STATE_UNKNOWN`、
`PAUSE_REASON_ORDER_STATE_UNKNOWN`——枚举其在**运行时/并发维度**触碰的**全部**接缝。
每项标注「已正确接线 / 需修复 / 不适用 + 理由」。**清单外的遗漏视同未修完。**

至少须覆盖下列各族（不限于此，缺哪族要说明为何不适用）：

1. **worker 生命周期的每个交接点**：`ensure_worker` 启动、`_run_task_worker` 正常退出、
   异常退出、`stop()`、`close()`、`_recover_workers` 恢复发现、同任务重入。逐点回答：
   此刻谁持有 `_workers_lock`？计数的读写与清理是否与交接原子？
2. **每一处读取 task / leg 快照的地方**：读取时点与**使用时点**之间是否可能发生状态变更？
   变更后旧快照被用于**写决策**的，一律列为需修复。
3. **每一处写状态 / 写 `pause_reason` 的 store 方法**：有无状态条件守卫？无条件 `UPDATE`
   在并发下会不会覆盖更晚的权威状态？
4. **锁的持有范围**：哪些区间持 `_workers_lock` / store 锁，哪些跨越了无锁的 executor
   网络调用。
5. **测试缝与真实线程路径的差异**：`_pump_worker`（无线程、无 pacing）能覆盖什么、
   **不能**覆盖什么。上一轮的三态测试正因在 drain 前静态设状态而结构性地漏掉了 F2-P1。
6. **既有并发先例**：`_rate_limit_stamp_pending`（in-process，重启丢一次计数）等，
   新机制是否重复了同类问题。

## 第二交付物：清单指出的全部修复

已知至少含下列两条（评审者的修复要求，原文引用，不得改写）：

### F1-P1 worker 清理与同任务重入的提前清零竞态

> **修复要求（原文）**：将 worker handoff 与旧计数清理串行化（例如在持有 `_workers_lock`
> 的清理/交接区间内完成，或使用 worker generation 防止旧 worker 清理新 worker 的计数）；
> 并为 `close()` 等退出路径提供确定的 join/清理顺序。新增一个可控 barrier 的并发回归：
> 阻塞旧 worker 清理、启动同 task 新 worker、让新 worker 写入查询计数，断言旧 worker
> 不能删除新计数，并断言新 worker 仍按剩余预算收口。

### F2-P1 状态守卫使用旧快照

> **修复要求（原文）**：在应用 `SIGNAL_ORDER_STATE_UNKNOWN` 前重新读取权威 task 状态，
> 或让 store 层采用仅在当前状态为 `running/paused` 时才更新的条件写；若条件更新未命中，
> 仍只记录事件、不改状态。保留三种静态状态测试，并增加在 executor 查询阻塞期间执行
> `post_delete` 的并发回归，断言最终状态仍为 `deleted`、腿非终态、无重发且 entries 有
> 人工核对事件。

**Bookkeeper 已独立实证 F2-P1**（在第 `2N-1` 次查询进行中改 `deleted`）：

```text
{"期望": "deleted", "实际": "paused", "pause_reason": "order_state_unknown", "terminal": [0, 0]}
```

**清单若发现第三、第四条同族问题，一并修复**——这正是本轮的目的。

## Allowed Files

```text
backend/hedge_open_tasks/service.py
backend/hedge_open_tasks/store.py
backend/hedge_open_tasks/domain.py     # 仅在确需新常量时
backend/tests/test_hedge_service.py
backend/tests/test_hedge_store.py
backend/tests/test_hedge_task_local.py
backend/tests/test_hedge_api.py
backend/tests/test_hedge_review2_regressions.py   # 见下方受限授权
```

**`test_hedge_review2_regressions.py` 受限授权**：仅当你的改动使其中某个用例因**机制
变化**而失败时，方可调整其**驱动方式**（时钟、轮次、注入序列），**核心断言一字不得改**；
每处改动须在实现报告中单独列出并说明为何不可避免。超出此范围停下报告。
（上一轮 packet 因删除常量却禁改引用文件而自相矛盾，本轮预先授权，见 `30-` §7。）

### 不得改动

```text
backend/services/live_hedge_executor.py
frontend/ 全部
429 / rate_limited 处理逻辑
domain.py 的 51169 文案区
backend/hedge_open_tasks/private_client.py
```

**不得新增数据库列**（计数器保持纯内存）。**不得改动**已通过 review-1 的四项：500ms
默认值、迁移回填 SQL、抖动移除、`_confirm_um_figures` 语义对齐；以及已修复的 F3/F4/F5。

### `data/` 红线

**绝对禁止对 `data/` 下任何数据库执行写操作**，含「构造 `HedgeOpenStore` 时指向真实
路径」这种间接写入。实现报告须列出所有可能触及 `data/` 的命令及其路径；需要真实数据
先复制到临时目录。不确定就写「不确定」，不要断言未碰。
（BK-T3-002 仍为未解除的发布门。）

## Acceptance Checks

1. **运行时接缝穷举清单**：覆盖上述六族，每项标注「已接线 / 需修复 / 不适用 + 理由」；
   清单外遗漏视同未修完。
2. **F1-P1**：worker 交接与计数清理原子化或加 generation 防护；**含可控 barrier 的并发
   回归测试**，断言旧 worker 不能清除新 worker 的计数、新 worker 按剩余预算收口。
   **该测试须能失败**（给出破坏输出）。
3. **F1-P1 关闭路径**：`close()` / `stop()` 有确定的 join / 清理顺序，计数不残留。
4. **F2-P1**：收口前重读权威状态，或 store 层条件写（仅 `running`/`paused` 命中）；
   未命中时只记事件、不改状态。**含在 executor 查询阻塞期间执行 `post_delete` 的并发
   回归**，断言最终仍为 `deleted`、腿非终态、无重发、entries 有人工核对事件。
   **该测试须能失败**（给出破坏输出）。
5. **保留既有覆盖**：三种静态终态测试保留；F3/F4/F5 的测试全部保留且仍绿。
6. **清单发现的其它同族问题**：逐条修复并配可失败测试；若清单认定无其它问题，须逐族
   给出「不适用」的具体理由，不接受「未发现」这类空断言。
7. **回归全绿**：`python3 -m pytest backend/tests/ -q` 全量通过（基线 **1152 passed**）。
   输出存 `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/65-runtime-seam-scan-test-output.txt`。
8. **边界**：未改 executor / `frontend/` / 429 / 51169 / `private_client.py`；未新增
   数据库列；未写入 `data/`（含留痕清单）；`test_hedge_review2_regressions.py` 的改动
   在受限授权内且逐处说明。

## Stop

实现 → 自测 → 实现报告写到
`reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/33-runtime-seam-scan-implementation.md`
（**穷举清单是报告的主体，放在最前**）→ 提交（分支
`stage/2026-07-31-hedge-task-lifecycle-v1`）→ 把 `status.json` 的 `current_task.state`
由 `dispatched` 改为 `reported` → 返回 `[TASK_RESULT v2]`。

**停在这里。** 不启动评审、不写 `verified`、不合并、不碰 `main`。修复后返回 review-1
（`gpt`，`openai`）复审，再走 review-2（`Fable5`）。

提交前自查 `git branch --show-current` 与 `git log --oneline -1`。
**边界不足时停下报告，不要临场扩边界。**
