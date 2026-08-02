# fix-runtime-seam-scan-v1.dispatch

```text
Identity:
  task_id:         fix-runtime-seam-scan-v1
  target_role:     Implementer
  target_model:    deepseek
  provider:        deepseek
  status_revision: 33
  required_skill:  agents/skills/senior-developer.md
```

**本 packet 于 2026-08-02 重写**（投递前修正，`rework_count` 不因此再增）。修法由
「给新路径加守卫」改为**「在 `store.pause_task` 修根，一次覆盖三条路径」**；F1-P1 经
Human 决定**移出范围**。理由见 `32-` §7。

## 读取位置（先确认）

主工作区 `/Users/ark/Desktop/ai code/funding_hedging`，分支
`stage/2026-07-31-hedge-task-lifecycle-v1`。开工前 `pwd && git branch --show-current`。

## Goal

`AGENTS.md` §8 的**同根因刹车已触发**（判定见 `32-` §3），**禁止点补丁**。

**根因（评审者 `31-` §3 原文，逐字引用）**：

> `29-` §8 的 15 项清单覆盖了静态契约，并正确覆盖了 entries、状态、404、429、payload、
> 文案、API、恢复和 schema 边界。但它**不穷尽运行时接缝**：
> - 清单 #3 将 worker 生命周期标为已正确接线，却没有单列「registry 删除 → 计数清理 →
>   新 worker handoff」的并发契约，遗漏 F1-P1；
> - 清单 #2 将状态粘性标为已正确接线，却只验证已有状态快照，遗漏「查询期间状态变更后
>   仍使用旧快照」的契约，遗漏 F2-P1。

`rework_count` 已为 **`2`**（上限 3，**仅剩 1 次**）。若本轮后再出 `REWORK`，须由 Human
在「缩小范围 / 重新设计 / 接受限制 / 停止」中选择，Bookkeeper 不得自行再派修复。
**请据此把握彻底程度。**

## Bookkeeper 已完成的先导扫描（你不必从零摸索，但须验证与补齐）

Human 指出「原设计是暂停/删除在当前查询之后执行」。核实成立——`post_delete` 的实现
注释（Amendment 21 / Review-1 r3 P1-2）原文：

> do NOT interrupt the worker. The task's own bounded worker keeps draining its
> in-flight legs to terminal and settling the pair, **then exits on the status
> check** (opens no new pair once deleted).

**即：drain 期间不得改任务状态，查完到状态检查点才退出。而实现从未完整遵守。**
`_worker_round` 的 drain 阶段有**三个**站点用查询前的旧快照写状态：

| 站点 | 引入 | Bookkeeper 探针（查询进行中 `post_delete`） | 范围分类 |
|---|---|---|---|
| `SIGNAL_RATE_LIMITED`（429） | **早于本 stage** | `deleted` → **`paused`**（`rate_limited`） | `pre-existing-release-critical` |
| `SIGNAL_TASK_LOCAL_PAUSE`（`insufficient_*` / `collateral_cap_full`） | **早于本 stage** | `deleted` → **`paused`**（`insufficient_balance`） | `pre-existing-release-critical` |
| `SIGNAL_ORDER_STATE_UNKNOWN` | 本 stage 新增 | `deleted` → **`paused`**（`order_state_unknown`） | **`in-range`** |

**三条均稳定复现。** 即 F2-P1 不是本次引入的新缺陷，而是**既有缺陷家族**的新成员。

## 修复要求

### 主修：在 `store.pause_task` 加状态条件写（一处覆盖三条）

`store.pause_task` **全项目只有一个调用者**（`service.py:1588`，`_pause_task_local` 内）。
在其 `UPDATE` 上加状态条件——**仅当当前状态为 `running` 或 `paused` 时才更新**。

- 条件**未命中**时：**只记录事件、不改状态**，并让调用方能够区分「已暂停」与「未命中」。
- 三条 drain 收口路径（429 / `insufficient_*` / `order_state_unknown`）**均须受该守卫
  保护**，且各自的事件仍要记录、腿仍保持非终态、**永不重发**。
- **不要在三个调用点各加守卫**——那是点补丁，正是本轮禁止的做法。

### 补齐：运行时接缝穷举扫描

主交付物之一。对本 stage 新增的三样东西（每腿重试计数机制、`SIGNAL_ORDER_STATE_UNKNOWN`、
`PAUSE_REASON_ORDER_STATE_UNKNOWN`）**及上述既有家族**，枚举运行时/并发维度的全部接缝，
每项标注「已正确接线 / 需修复 / 不适用 + 理由」。**清单外遗漏视同未修完。**

至少覆盖：

1. **旧快照写决策族**：确认上述三站点是否穷尽。**已知待确认线索**：
   `_stop_task_fatal_preflight`（`service.py:1828`，经 `_dispatch_one_for_task` 调用）
   同样在网络调用之后用旧 `task` 写 `stopped`；虽位于状态检查之后，仍须确认是否属同族。
2. **每一处写状态 / 写 `pause_reason` 的 store 方法**：有无条件守卫？无条件 `UPDATE`
   在并发下会否覆盖更晚的权威状态？（含 `set_task_status` 的各调用点。）
3. **锁的持有范围**：哪些区间跨越了无锁的 executor 网络调用。
4. **测试缝与真实线程路径的差异**：`_pump_worker`（无线程、无 pacing）能覆盖什么、
   **不能**覆盖什么。上一轮三态测试正因在 drain 前静态设状态而结构性地漏掉 F2-P1。
5. **既有并发先例**：`_rate_limit_stamp_pending`（in-process，重启丢一次计数）等，
   新机制是否重复同类问题。

**清单发现的其它同族问题一并修复**——这正是本轮的目的。

### 明确不在本轮范围：F1-P1

worker 交接与计数清理的竞态（`31-` F1-P1）经 **Human 决定接受为已知限制**，五要素记录
见 `32-` §7.3。**不要修它，也不要为它加测试。** 若你的扫描认为该判断有误（例如发现了
非人工触发 `ensure_worker` 的路径），**停下报告**，不要自行扩范围。

## Allowed Files

```text
backend/hedge_open_tasks/service.py
backend/hedge_open_tasks/store.py
backend/hedge_open_tasks/domain.py     # 仅在确需新常量时
backend/tests/test_hedge_service.py
backend/tests/test_hedge_store.py
backend/tests/test_hedge_task_local.py
backend/tests/test_hedge_api.py
backend/tests/test_hedge_review2_regressions.py   # 受限授权，见下
```

**`test_hedge_review2_regressions.py` 受限授权**：仅当你的改动使其中某用例因**机制变化**
失败时，方可调整其**驱动方式**（时钟、轮次、注入序列），**核心断言一字不得改**；每处
改动须在报告中单独列出并说明为何不可避免。超出此范围停下报告。

### 不得改动

```text
backend/services/live_hedge_executor.py
frontend/ 全部
429 / rate_limited 的**分类与信号语义**（本轮只给它加状态守卫，不改它何时触发）
domain.py 的 51169 文案区
backend/hedge_open_tasks/private_client.py
```

**不得新增数据库列。不得改动**已通过 review-1 的四项（500ms 默认值、迁移回填 SQL、
抖动移除、`_confirm_um_figures` 语义对齐）与已修复的 F3/F4/F5。

### `data/` 红线

**绝对禁止对 `data/` 下任何数据库执行写操作**，含「构造 `HedgeOpenStore` 时指向真实
路径」这种间接写入。报告须列出所有可能触及 `data/` 的命令及路径；需要真实数据先复制到
临时目录。不确定就写「不确定」，不要断言未碰。（BK-T3-002 仍为未解除的发布门。）

## Acceptance Checks

1. **条件写生效**：`pause_task` 仅在 `running`/`paused` 命中；未命中时不改状态且仍记录
   事件。**破坏该条件即转红。**
2. **三条并发回归**：429 / `insufficient_*` / `order_state_unknown` 各一条，均在
   **executor 查询进行中**执行 `post_delete`，断言最终状态仍为 `deleted`、腿非终态、
   无重发、entries 有对应事件。**三条均须能失败**（给出破坏输出）。
3. **既有静态覆盖保留**：上一轮的三种静态终态测试保留且仍绿；F3/F4/F5 测试全部保留且绿。
4. **运行时接缝穷举清单**：覆盖上述五族，逐项标注；对 `_stop_task_fatal_preflight`
   线索给出明确结论（属同族则修，不属则给理由）。
5. **清单发现的其它同族问题**：逐条修复并配可失败测试；若认定无其它问题，须逐族给出
   **具体**的不适用理由，不接受「未发现」这类空断言。
6. **F1-P1 未被触碰**（Human 已接受为限制）。
7. **回归全绿**：`python3 -m pytest backend/tests/ -q` 全量通过（基线 **1152 passed**）。
   输出存 `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/65-runtime-seam-scan-test-output.txt`。
8. **边界**：未改 executor / `frontend/` / 429 触发语义 / 51169 / `private_client.py`；
   未新增数据库列；未写入 `data/`（含留痕清单）；`test_hedge_review2_regressions.py`
   改动在受限授权内且逐处说明。

## Stop

实现 → 自测 → 报告写到
`reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/33-runtime-seam-scan-implementation.md`
（**穷举清单放最前**）→ 提交（分支 `stage/2026-07-31-hedge-task-lifecycle-v1`）→ 把
`status.json` 的 `current_task.state` 由 `dispatched` 改为 `reported` → 返回
`[TASK_RESULT v2]`。

**停在这里。** 不启动评审、不写 `verified`、不合并、不碰 `main`。修复后返回 review-1
（`gpt`，`openai`）复审，再走 review-2（`Fable5`）。

提交前自查 `git branch --show-current` 与 `git log --oneline -1`。
**边界不足时停下报告，不要临场扩边界。**
