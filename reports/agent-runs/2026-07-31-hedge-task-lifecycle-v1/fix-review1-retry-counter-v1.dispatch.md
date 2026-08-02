# fix-review1-retry-counter-v1.dispatch

```text
Identity:
  task_id:         fix-review1-retry-counter-v1
  target_role:     Implementer
  target_model:    deepseek
  provider:        deepseek
  status_revision: 29
  required_skill:  agents/skills/minimal-change-engineer.md
```

**本 packet 取代 `fix-review1-f1-f5-v1.dispatch.md`（已作废，从未投递）。** 差异：F1 的
修法由「给无锚点腿定义 fail-closed 行为」改为**把时间窗口整体换成内存重试计数器**
（Human 决定，见 §「为什么换机制」）。F2-F5 的修复要求不变。

## 读取位置（先确认，你在此栽过一次）

本仓库有 **4 个 worktree**。本任务只在**主工作区**
`/Users/ark/Desktop/ai code/funding_hedging` 的
**`stage/2026-07-31-hedge-task-lifecycle-v1`** 分支。`main` 上该 stage 目录停在 `49-`。
开工前执行 `pwd && git branch --show-current`。

## Goal

修复 review-1（`codex`，`28-review-1-codex-task3.md`）的 **F1-F5**（Bookkeeper 已逐条
独立复验，五条全部成立，证据见 `27-` §6.3），其中 **F1 的修法是替换机制**。

`rework_count` 保持 **`1`**（本 packet 是投递前修正，按 `AGENTS.md` §8 的
pre-dispatch packet correction 豁免，不再递增）。

### 为什么换机制（Human 决定，勿重新论证）

Human 原本要求的是**原 JS 的重试计数**（`getSpotOrderInfo(id, 10)`：查不到就
`Sleep(500)` 重试，最多 10 次）。Bookkeeper 在 packet 中**擅自替换为「距下单时间 5 秒」
的时间窗口**，理由是「计数器要新增数据库字段，违反红线」。**该替换是错的**：

| | 计数器（Human 要的） | 时间窗口（已交付的） |
|---|---|---|
| 保证 | **真的问满 N 次** | 只保证「过了 5 秒」 |
| **一次查询超时 10 秒**（`DEFAULT_TIMEOUT_SECONDS = 10`） | 还剩 N-1 次 | **窗口早已耗尽，实际只问了 1 次** |
| 间隔被改动 | 次数不变 | 次数随间隔漂移 |
| 需要时间锚点 | **不需要** | 需要；无锚点即永不耗尽 ← **F1 的根因** |
| 进程重启 | 重新计数（同原 JS） | 按原下单时间算，可能一开机即过期 |

**请求超时是 10 秒，而窗口只有 5 秒**——一次超时就吃光整个窗口，而「超时」恰是最需要
多问几次的情形。且 **F1 这条 P1 正是时间窗口需要锚点而锚点可能缺失的直接产物**：
换成计数器后，**F1 从根上消失**（无锚点的腿照样数满 N 次）。

「不新增字段」的理由不成立：计数器**不需要持久化**。原 JS 的 `for (i=0; i<10; i++)`
就在内存里，进程重启重新数。本仓已有同类先例（`_rate_limit_stamp_pending` 为
in-process，其「重启丢一次计数」的代价已记录在 `PROJECT_STATE.md`）。

## 修复要求

### F1 [P1] —— 用内存重试计数器替换时间窗口

**删除**：`domain.py` 的 `ABSENT_TOLERANCE_WINDOW_US`，以及 `service.py` 中所有基于
`dispatched_at_us` 的 `window_elapsed` 判定。

**新增**：**每条腿独立的、进程内存中的查询重试计数**。

- 计数单位是**腿**（`leg["id"]`），不是任务、不是 attempt。
- 上限 **10 次**（常量放 `domain.py`，与既有常量同区；对齐原 JS 的
  `getSpotOrderInfo(id, 10)`）。
- 计数只在内存中（例如 service 实例上的一个 dict）。**不得新增数据库列**。
- 腿达终态或 worker 退出时清理该腿的计数，**不得无限增长**。
- 未达上限时：`404 / -2013` 与 inconclusive 一律**保持非终态、继续查**（现行窗口内行为）。
- 达到上限时按最后一次结果分流（与已交付实现相同，不要改这部分语义）：
  - 最后一次是 `404 / -2013` → 判 `absent` **终态**；
  - 最后一次是 inconclusive（`verdict is None` / 畸形 2xx）→ `SIGNAL_ORDER_STATE_UNKNOWN`
    → 人工暂停，腿保持非终态，**永不重发**。

**重启行为是预期而非缺陷**：进程重启后计数清零、重新数满 10 次。这与原 JS 一致，且比
时间窗口更安全（时间窗口在崩溃恢复时可能一上来就已过期，导致一次都没真正查过就收口）。
**请为此写一条断言重启后重新计数的测试。**

**同时订正**已交付实现中那句与事实相反的注释（称无锚点行「prior behaviour is
unchanged」——改动前是「404 立即判 absent 终态」，改动后变成永不终态）。

### F2 [P1] inconclusive 收口不得复活 deleted/done/stopped

`service.py:1197-1207` 无条件调用 `_pause_task_local`，`store.py:1765-1769` 的
`pause_task` 无条件 `SET status = 'paused'`；drain 发生在 `_worker_round` 的状态检查
**之前**（Q2 drain-before-exit），故终态任务只要还有非终态腿就会被改回 `paused`。

已复验实测：

```text
{"before": "deleted", "after": "paused", "pause_reason": "order_state_unknown"}
{"before": "done",    "after": "paused", "pause_reason": "order_state_unknown"}
{"before": "stopped", "after": "paused", "pause_reason": "order_state_unknown"}
```

> **修复要求（引自 `28-`，未改写）**：保留 `deleted`、`done`、`stopped` 的原状态；这些
> 状态仍可保留非终态腿并记录可见人工核对事件，但不得通过 `pause_task` 改成 paused。对
> running/paused 继续使用人工暂停语义。为三种非运行态分别增加窗口耗尽 inconclusive 测试，
> 断言状态不变、腿非终态、无重发。

（「窗口耗尽」在本 packet 下读作「计数达上限」。）

### F3 [P1] 人工核对事件必须进入 entries 时间线

事件写入 kind `order_state_unknown`，但 `_ENTRY_EVENT_KINDS`（`service.py:84-90`）不含
该值，`_entries_page` 按该集合过滤 → 操作者与 review-2 无法从既有日志契约重建这次收口。

> **修复要求（引自 `28-`，未改写）**：优先让该路径复用已有 `task_paused` kind，确保现有
> entries 映射为 `overall_result=task_paused`、`next_action=paused` 并保留 `reason_zh`；
> 或新增 kind 时同步加入 `_ENTRY_EVENT_KINDS` 与 `_event_to_entry` 的明确映射。增加 API
> entries 断言，确认事件可见且显示人工核对语义。

### F4 [P2] 两个 signal 产生点各需独立测试

`service.py:1274-1275` 处理 `verdict is None`（传输错误 / 5xx / 超时），`:1351-1358`
处理有 verdict 但 `dispatch_state == UNKNOWN_QUERYING` 的畸形 2xx。**两者是不同输入
形状，不是冗余保险**（Bookkeeper 先前判为「双保险」是错的，已在 `27-` §6.1 更正）。

> **修复要求（引自 `28-`，未改写）**：新增一条 `query_leg` 返回 `None` 的独立测试，断言
> 任务人工暂停、腿非终态、失败计数不变、无重发；保留现有畸形 2xx 测试，确保删除任一
> signal 产生点都会使对应测试失败。

### F5 [P2] 迁移缺自动回归断言

迁移 SQL 语义正确，但 Bookkeeper 复验：**删掉整段回填后全量 1140 测试仍全绿**。

> **修复要求（引自 `28-`，未改写）**：在 `backend/tests/test_hedge_store.py` 中加入旧默认
> 回填、自定义值保留、重开幂等和 `interval_seconds` API 形状测试；至少让删除
> `HedgeOpenStore._migrate` 的回填 SQL 使测试失败。

## 根因（请在实现报告中原样引用并回应）

三条 P1 是同一个根因：**新增的收口路径没有与既有契约全面接线**——F1 未接「腿可能没有
时间锚点」、F2 未接「任务状态有粘性」、F3 未接「任务级事件须进 entries」。

**因此本次不接受三个点补丁。** 除 F1-F5 外须交一份**同族扫描清单**（验收 7）：本轮新增
的三样东西——重试计数机制、`SIGNAL_ORDER_STATE_UNKNOWN`、`PAUSE_REASON_ORDER_STATE_UNKNOWN`
——**还触碰了哪些既有契约**？逐项标注「已正确接线」或「不适用 + 理由」。清单外的遗漏
视同未修完。

## Allowed Files

```text
backend/hedge_open_tasks/service.py    # 计数器、F2 状态守卫、F3 事件接线
backend/hedge_open_tasks/store.py      # F2 若需 store 层状态守卫
backend/hedge_open_tasks/domain.py     # 删 ABSENT_TOLERANCE_WINDOW_US、加重试上限常量
backend/tests/test_hedge_service.py
backend/tests/test_hedge_store.py
backend/tests/test_hedge_task_local.py
backend/tests/test_hedge_api.py        # F3 的 entries 断言
```

### 不得改动

```text
backend/services/live_hedge_executor.py        # 分类器语义不动
frontend/ 全部（前端缺 order_state_unknown 标签是已记录的非阻塞后续项）
backend/tests/test_hedge_review2_regressions.py
429 / rate_limited 处理逻辑
domain.py 的 51169 文案区
backend/hedge_open_tasks/private_client.py
```

**不得新增数据库列**（计数器只在内存）。**不得改动 500ms 默认值、迁移 SQL 语义、抖动
移除、`_confirm_um_figures` 语义对齐**——这四项 review-1 已通过。

### `data/` 红线（本轮加严，因 BK-T3-002）

**绝对禁止对 `data/` 下任何数据库执行写操作**，包括「构造 `HedgeOpenStore` 时指向真实
路径」这种间接写入——上一轮正是这样触发迁移改了实盘库，且事后无法确定是哪次运行。

**留痕要求**：实现报告须列出**你运行过的、任何可能触及 `data/` 的命令**（python 探针、
pytest 参数、sqlite3 调用）及其路径。需要真实数据时**先复制到临时目录**并给出复制命令。
若不确定某次运行是否碰过实盘库，如实写「不确定」，**不要断言未碰**。

## Acceptance Checks

1. **F1 机制替换**：`ABSENT_TOLERANCE_WINDOW_US` 与所有 `dispatched_at_us` 窗口判定已
   删除；改为每腿内存计数、上限 10 次。**无 `dispatched_at_us` 的腿同样能数满并收口**
   （两条测试：404 与 inconclusive，均须能失败）。
2. **F1 重启语义**：断言进程/service 重建后计数从零重新开始，且恢复路径**不重发**。
3. **F1 计数不泄漏**：腿终态或 worker 退出后计数被清理（断言 dict 不无限增长）。
4. **F2**：`deleted` / `done` / `stopped` 三条测试，断言计数达上限的 inconclusive drain
   后**状态不变**、腿非终态、无重发。**三条均须能失败。**
5. **F3**：人工核对事件出现在 `entries` 时间线并携带 `reason_zh`；须有 **API 层**断言且
   能失败。
6. **F4**：`verdict is None` 的独立测试；**删除任一个 `SIGNAL_ORDER_STATE_UNKNOWN` 产生
   点都必须有对应测试转红**（报告给出两次单点破坏的实际输出）。
7. **同族扫描清单**：见根因一节。
8. **F5**：删除迁移回填 SQL 后必须有测试转红（报告给出破坏后的实际输出）。
9. **回归全绿**：`python3 -m pytest backend/tests/ -q` 全量通过（基线 **1140 passed**）。
   输出存 `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/64-fix-retry-counter-test-output.txt`。
10. **边界**：未改 executor / `frontend/` / `test_hedge_review2_regressions.py` / 429 /
    51169；未新增数据库列；**未写入 `data/` 下任何库**（含留痕清单）。

## Stop

实现 → 自测 → 实现报告写到
`reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/29-fix-retry-counter-implementation.md`
→ 提交（分支 `stage/2026-07-31-hedge-task-lifecycle-v1`）→ 把 `status.json` 的
`current_task.state` 由 `dispatched` 改为 `reported` → 返回 `[TASK_RESULT v2]`。

**停在这里。** 不启动评审、不写 `verified`、不合并、不碰 `main`。修复后按 §8 返回
**review-1**（`codex` 复审），再走 review-2。

提交前自查 `git branch --show-current` 与 `git log --oneline -1`，确认提交真的落在 stage
分支上。**边界不足时停下报告，不要临场扩边界。**

**注意**：你执行本任务后即成为本交付的 fix author，按 `AGENTS.md` §3 #4 将**永久失去
对本交付的评审资格**。这是 Human 已知并接受的决定。
