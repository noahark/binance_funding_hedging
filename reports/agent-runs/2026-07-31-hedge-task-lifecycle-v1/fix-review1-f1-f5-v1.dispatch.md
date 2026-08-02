# fix-review1-f1-f5-v1.dispatch

```text
Identity:
  task_id:         fix-review1-f1-f5-v1
  target_role:     Implementer
  target_model:    claude_glm
  provider:        zhipu_glm
  status_revision: 28
  required_skill:  agents/skills/minimal-change-engineer.md
```

## 读取位置（先确认）

本仓库有 **4 个 worktree**，本任务只在**主工作区**
`/Users/ark/Desktop/ai code/funding_hedging` 的
**`stage/2026-07-31-hedge-task-lifecycle-v1`** 分支。开工前执行
`pwd && git branch --show-current`。

## Goal

修复 review-1（`codex`，`28-review-1-codex-task3.md`）的 **F1-F5**，全部为 `in-range`。
Bookkeeper 已**逐条独立复验，五条全部成立**（复验证据见 `27-` §6.3）。

`rework_count` 由 `0` 递增为 **`1`**（`AGENTS.md` §8，上限 3）。

### 根因（Bookkeeper 命名，请在实现报告中原样引用并回应）

三条 P1 是同一个根因：**新增的收口路径没有与既有契约全面接线。**

- **F1** 没接到「腿可能没有 `dispatched_at_us` 锚点」这个既有事实；
- **F2** 没接到「任务状态有粘性，`deleted`/`done`/`stopped` 不可被复活」这个既有语义；
- **F3** 没接到「任务级事件必须进入 `entries` 时间线」这个既有契约。

**因此本次修复不是三个点补丁。** 除 F1-F5 外，你必须交一份**同族扫描清单**（见验收 6）：
本轮新增的三样东西——`ABSENT_TOLERANCE_WINDOW_US` 窗口判定、
`SIGNAL_ORDER_STATE_UNKNOWN`、`PAUSE_REASON_ORDER_STATE_UNKNOWN`——**还触碰了哪些既有
契约**？逐一列出，每项说明「已正确接线」或「不适用及理由」。清单外的遗漏视同未修完。

## 五条修复要求（引自 `28-` 修复要求总表，未改写）

### F1 [P1] 无 `dispatched_at_us` 的在途腿永不耗尽窗口

无锚点时 `window_elapsed` 恒为 `False`，导致 404 被 `terminal = False` 强制改为非终态
且永不确认，也永不进入 `SIGNAL_ORDER_STATE_UNKNOWN` → **无限重查**。覆盖旧库行，以及
`prepare_attempt` 已落库但进程在 `resolve_attempt` / `mark_leg_querying` 前崩溃的真实
crash gap。

**注意实现注释与事实相反**：注释称无锚点行「prior behaviour is unchanged」，但改动前
的行为是「404 立即判 absent 终态」，改动后变成永不终态。请一并订正该注释。

> **修复要求（原文）**：为无锚点腿定义明确且可终止的 fail-closed 行为：可使用已持久化
> 且可靠的 attempt 时间作为锚点，或直接将其转入 `SIGNAL_ORDER_STATE_UNKNOWN`/人工暂停；
> 不得让 404 永久保持非终态，也不得将未知直接判为 absent。补充无锚点、时钟超过窗口、
> 404 与 inconclusive 两类测试，并证明恢复仍不重发。

### F2 [P1] inconclusive 收口会复活 deleted/done/stopped 任务

`service.py:1197-1207` 无条件调用 `_pause_task_local`，`store.py:1765-1769` 的
`pause_task` 无条件 `SET status = 'paused'`。drain 发生在 `_worker_round` 的状态检查
**之前**（Q2 drain-before-exit），故终态任务只要还有非终态腿就会被改回 `paused`。

> **修复要求（原文）**：保留 `deleted`、`done`、`stopped` 的原状态；这些状态仍可保留
> 非终态腿并记录可见人工核对事件，但不得通过 `pause_task` 改成 paused。对 running/paused
> 继续使用人工暂停语义。为三种非运行态分别增加窗口耗尽 inconclusive 测试，断言状态不变、
> 腿非终态、无重发。

### F3 [P1] `order_state_unknown` 暂停事件被 entries 时间线过滤

事件写入 kind `order_state_unknown`，但 `_ENTRY_EVENT_KINDS`（`service.py:84-90`）不含
该值，`_entries_page` 按该集合过滤 → 操作者与 review-2 无法从既有日志契约重建这次安全
收口。

> **修复要求（原文）**：优先让该路径复用已有 `task_paused` kind，确保现有 entries 映射
> 为 `overall_result=task_paused`、`next_action=paused` 并保留 `reason_zh`；或新增 kind
> 时同步加入 `_ENTRY_EVENT_KINDS` 与 `_event_to_entry` 的明确映射。增加 API entries 断言，
> 确认事件可见且显示人工核对语义。

### F4 [P2] 缺 `verdict is None` 分支的独立测试

两个产生点处理**不同输入形状**（`:1274-1275` 传输无结论 / `:1351-1358` 畸形 2xx），不是
冗余保险。现有新测试只注入 `LEG_UNKNOWN_QUERYING` 对象。

> **修复要求（原文）**：新增一条窗口耗尽后 `query_leg` 返回 `None` 的独立测试，断言任务
> 人工暂停、腿非终态、失败计数不变、无重发；保留现有畸形 2xx 测试，确保删除任一 signal
> 产生点都会使对应测试失败。

### F5 [P2] 既有数据库迁移没有自动回归断言

迁移 SQL 语义正确，但**删掉整段回填后全量 1140 测试仍全绿**（Bookkeeper 已复验）。

> **修复要求（原文）**：在允许的 `backend/tests/test_hedge_store.py` 中加入旧默认回填、
> 自定义值保留、重开幂等和 `interval_seconds` API 形状测试；至少让删除
> `HedgeOpenStore._migrate` 的回填 SQL 使测试失败。

## Allowed Files

```text
backend/hedge_open_tasks/service.py    # F1 锚点兜底、F2 状态守卫、F3 事件接线
backend/hedge_open_tasks/store.py      # F2 若需在 store 层加状态守卫
backend/hedge_open_tasks/domain.py     # 仅在 F1/F3 确需新常量时
backend/tests/test_hedge_service.py
backend/tests/test_hedge_store.py
backend/tests/test_hedge_task_local.py
backend/tests/test_hedge_api.py        # F3 的 entries 断言
```

### 不得改动

```text
backend/services/live_hedge_executor.py        # 分类器语义不动
frontend/ 全部（F3 的前端标签缺失是已记录的非阻塞后续项，不在本轮）
backend/tests/test_hedge_review2_regressions.py
429 / rate_limited 处理逻辑
domain.py 的 51169 文案区
backend/hedge_open_tasks/private_client.py
```

### `data/` 红线（本轮加严，因 BK-T3-002）

**绝对禁止对 `data/` 下任何数据库执行写操作**，包括「构造 `HedgeOpenStore` 时指向真实
路径」这种间接写入——上一轮正是这样触发了迁移、改了实盘库，且事后无法确定是哪次运行。

**本轮新增留痕要求**：实现报告中必须列出**你运行过的、任何可能触及 `data/` 的命令**
（含 python 探针、pytest 参数、sqlite3 调用）及其使用的路径。需要真实数据时**先复制到
临时目录**并在报告中给出复制命令。若你不确定某次运行是否碰过实盘库，如实写「不确定」，
不要断言未碰。

## Acceptance Checks

1. **F1**：无 `dispatched_at_us` 的腿，时钟超过窗口后——(a) 404 不再永久非终态；
   (b) inconclusive 不再永久重查；(c) 两类均不得把未知判为 `absent`。
   **两条测试均须能失败。** 并断言恢复路径不重发。
2. **F2**：`deleted` / `done` / `stopped` 三种状态各一条测试，断言窗口耗尽的 inconclusive
   drain 后**状态不变**、腿非终态、无重发。**三条均须能失败。**
3. **F3**：人工核对事件出现在 `entries` 时间线，携带 `reason_zh`，语义为人工暂停。
   须有 **API 层**断言（`test_hedge_api.py`），且能失败。
4. **F4**：窗口耗尽后 `query_leg` 返回 `None` 的独立测试；**删除任一个
   `SIGNAL_ORDER_STATE_UNKNOWN` 产生点，都必须有对应测试转红**（报告中给出两次单点破坏
   的实际输出）。
5. **F5**：删除迁移回填 SQL 后必须有测试转红（报告中给出破坏后的实际输出）。
6. **同族扫描清单**：按 Goal 的根因，列出本轮三样新增物触碰的全部既有契约，逐项标注
   「已接线」或「不适用 + 理由」。清单外的遗漏视同未修完。
7. **回归全绿**：`python3 -m pytest backend/tests/ -q` 全量通过（基线 **1140 passed**，
   新增用例后应上升）。输出存
   `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/64-fix-f1-f5-test-output.txt`。
8. **边界**：未改 executor / `frontend/` / `test_hedge_review2_regressions.py` / 429 /
   51169；**未写入 `data/` 下任何库**（含留痕清单）。

## Stop

实现 → 自测 → 实现报告写到
`reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/29-fix-f1-f5-implementation.md`
→ 提交（分支 `stage/2026-07-31-hedge-task-lifecycle-v1`）→ 把 `status.json` 的
`current_task.state` 由 `dispatched` 改为 `reported` → 返回 `[TASK_RESULT v2]`。

**停在这里。** 不启动评审、不写 `verified`、不合并、不碰 `main`。修复后按 §8 返回
**review-1**（同一评审者复审），再走 review-2。

提交前自查 `git branch --show-current` 与 `git log --oneline -1`。
**边界不足时停下报告，不要临场扩边界。**
