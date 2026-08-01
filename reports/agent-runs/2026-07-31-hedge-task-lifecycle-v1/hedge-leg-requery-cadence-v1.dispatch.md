# hedge-leg-requery-cadence-v1.dispatch

```text
Identity:
  task_id:         hedge-leg-requery-cadence-v1
  target_role:     Implementer
  target_model:    claude_glm
  provider:        zhipu_glm
  status_revision: 23
  required_skill:  agents/skills/senior-developer.md
```

## Goal

把对冲任务的**腿重查节奏**从 1 秒降到 100 毫秒，让成交数据更早落袋；同时补齐
三道护栏：修亚秒显示、读取处夹下限、worker 节流加抖动。范围与裁定见
`10-design.md` P6 与 `11-adr.md` ADR-003。

**本任务的执行顺序被调整过，你必须知道：** 原计划 Task 3 排在 Task 2
（`hedge-task-lifecycle-v1`）之后并 rebase 于它。Human 于 2026-08-01 决定
**Task 2 暂缓，先做 Task 3**。因此：

- 本任务基于 `9faa716`（含 Task 1 交付 `ef53a02`），**不**基于 Task 2；
- ADR-002 的 **429 指数退避机制尚不存在**，本任务**不实现它**（那是 Task 2 的
  范围，且改动它会推翻 9 个既有锁定测试，见「不得改动」）；
- 因此 `12-development-breakdown.md` Task 3 要点里的「退避节流参数调优」和验收
  标准 5（「429 退避有上限、不死循环」）**本轮不适用**，由 Bookkeeper 明确删除。
  不要为满足它而自行实现退避。

### 本任务的已知代价（不是缺陷，不要试图消除）

重查间隔降到 100ms 会提高撞币安限频（429）的概率。当前 429 的处理是
**把该任务暂停**（`pause_reason = rate_limited`，保留在途腿不重发，等人工恢复）——
fail-closed，不丢钱、不删卡。**后果是任务可能更频繁地自动暂停、需要人工点恢复。**
Human 已知悉并接受。抖动（要点 4）是本轮唯一的缓解手段。

### 根因警戒（本 stage 已连续四次栽在同一处）

本 stage 的 F1/F2/F3/F4 是同一个根因：**展示层断言了它并不知道的事**
（`50-handoff-to-next-bookkeeper.md` §7）。本任务的前置修复对象就是这个根因的
第五个实例：`interval_us = 100_000` 时接口返回 `interval_seconds: 0`，界面印出
「调度间隔 0 秒」——一句假话。

因此本任务对**每一处用户可见的间隔数值**，必须回答：

1. 这个数字向用户断言了什么？
2. 它和**实际生效**的节奏一致吗？
3. 不一致时显示什么？

**判据：不得让界面显示一个与实际生效值不符的间隔。** 尤其见验收 3。

## Allowed Files

```text
backend/hedge_open_tasks/service.py        # 亚秒显示修复、worker 节流抖动
backend/hedge_open_tasks/store.py          # get_interval_us 夹下限
backend/hedge_open_tasks/domain.py         # DEFAULT_INTERVAL_US / DEFAULT_INTERVAL_SECONDS 默认值 + 下限常量
backend/hedge_open_tasks/scheduler.py      # 仅当 poll slice 需随亚秒调整
backend/tests/test_hedge_service.py
backend/tests/test_hedge_task_local.py
```

`domain.py` 是 Bookkeeper 对 `12-development-breakdown.md` 文件边界的**修正**：
默认值常量 `DEFAULT_INTERVAL_US` / `DEFAULT_INTERVAL_SECONDS` 在
`domain.py:513-514`，不在 `store.py`（`store.py:345-346` 只是引用它们）。原边界
漏列该文件，照原文执行会无法完成要点 2。

### 不得改动

```text
frontend/ 全部（含 index.html、self-check.js）
backend/tests/test_hedge_review2_regressions.py
429 / rate_limited 的处理逻辑（service.py:1175-1183、service.py:1199-1203）
domain.py 的 51169 文案区（实际在 :1336-1360，非 12- 所载 :1315-1324）
backend/hedge_open_tasks/private_client.py
reports/agent-runs/**/status.json
```

**关于 429 逻辑**：`test_hedge_task_local.py` 内有 6 个用例
（`test_3` :346、`s2` :629、`4i` :929、`4m` :1063、`r1` :1367、`r2` :1403、
`r6` :1614）与 `test_hedge_review2_regressions.py` 内 3 个用例
（`7d` :551、`7e` :579、`10d` :896）锁定了「429 → `paused` +
`PAUSE_REASON_RATE_LIMITED`」。**它们必须继续全绿。** 若你的改动让其中任何一个
变红，那是回归，不是"需要更新的过时断言"——停下来报告，不要改测试。

**关于前端**：接口返回的 `interval_seconds` 被
`frontend/index.html:3856` 渲染成「调度间隔 ${值} 秒（后端调度）」。你选的表示
形式**必须在不修改前端的前提下正确渲染**（例如返回 `0.1` 会渲染成
「调度间隔 0.1 秒」，可行；新增 `interval_ms` 键则要求改前端，不可行）。你可以
**读**前端确认，但不得改。在报告里写明改完之后那行 UI 的完整文案。

## Inputs

### 已由 Bookkeeper 重新核实的代码锚点

`12-development-breakdown.md` 与两份 ADR 的行号写于 Task 1 合并**之前**，Task 1
改动了同样几个文件，行号已整体漂移。**以下为 `9faa716` 上的实测值，以此为准，
不要照抄方案文档的行号：**

| 目标 | 方案文档所载 | **实际（`9faa716`）** |
|---|---|---|
| 整除显示 bug | `service.py:178` | **`service.py:201`** |
| worker 节流 `ev.wait` | `service.py:1079` | **`service.py:1102-1105`** |
| DRY-RUN `tick()` 取间隔 | `service.py:1519` | **`service.py:1543`** |
| `get_interval_us` 定义 | `store.py`（未给行号） | **`store.py:2119-2124`** |
| 种子插入引用默认值 | `store.py`（未给行号） | **`store.py:345-346`** |
| 默认值常量本体 | 未提及（边界遗漏） | **`domain.py:513-514`** |
| scheduler 唤醒切片 | `scheduler.py:51-56` | **`scheduler.py:51-57`** |
| 查询期 429 站点 | `service.py:1152-1160` | **`service.py:1175-1183`** |
| 派发期 429 站点 | `service.py:1176-1180` | **`service.py:1199-1203`** |

### 五个实现要点（ADR-003 Decision，退避一条已移除）

1. **前置：修亚秒显示。** `service.py:201` 现为
   `int(settings["interval_us"]) // 1_000_000`，`interval_us=100_000` 时得 `0`。
   改为能表达亚秒的形式。约束见上「关于前端」。
2. **下调默认。** `domain.py:514` `DEFAULT_INTERVAL_US` 由 `1_000_000` →
   `100_000`。注意 `domain.py:513` `DEFAULT_INTERVAL_SECONDS = "1"` 是同一行
   种子插入的另一个字段（`store.py:345`），两者必须保持自洽。
3. **加下限。** 在 `store.py:2119` `get_interval_us` 的**读取处**夹下限（建议
   50ms）。防未来误配把 worker 转成忙轮询。
4. **加抖动。** `service.py:1102-1105` 的 `ev.wait(interval_s)` 加随机抖动，
   避免多 worker 对齐成脉冲。
5. **不新增运行时配置入口**（红线 #6）；**不拆分双间隔**（ADR-003 Decision 2）。

### 已核实的两条背景事实（不必重挖）

- LIVE 模式 `tick()` 是空操作，`interval_us` 在 live **只**节流腿重查
  （`service.py:1102`），**不**驱动下单节奏。下单频率由 A-9 保证（一对腿终态才进
  下一对），本次改动**不**抬高下单频率。
- `scheduler.py:56` 的唤醒切片由 `interval_us` 推导
  （`max(min(interval_us/1e6/2, 0.25), 0.005)`）。降到 100ms 会让调度线程唤醒频率
  上升约 5 倍（有 5ms 下限；live 下 `tick()` 立即返回，故不产生交易所请求）。
  这是**已知且可接受**的，除非你发现它有别的后果，否则不需要改 `scheduler.py`。

### 参考文档（按需取，不要通读）

- `10-design.md` P6（§107-118）、`11-adr.md` ADR-003（§98-132）
- `12-development-breakdown.md` Task 3 一节（**行号已过期，见上表**）
- `agents/developer-discipline.md`

## Acceptance Checks

1. **亚秒显示**：`interval_us = 100_000` 时设置接口返回的间隔**不是 `0`**，且
   `frontend/index.html:3856` 在**未修改前端**的情况下渲染出正确文案。报告中写出
   该文案原文。
2. **节奏**：在途腿重查间隔 ≈100ms。用 `_pump_worker` 或可控时钟确定性断言，
   不用 sleep 竞态。
3. **下限与显示一致性**（根因警戒的落点）：把 `interval_us` 误配为极小值
   （如 `1_000`）时，(a) 实际生效被夹到下限、不忙轮询；(b) **接口返回的间隔值
   等于实际生效值，而不是用户误配的原值**。若二者当前不一致，这是必须修的缺陷，
   不是可接受现状。
4. **抖动**：断言抖动确实存在（多次取值不恒等），且**始终为正、有界**，不会退化
   成 0 或超过标称间隔。
5. **下单频率不变**：断言 A-9 不受影响——一对腿终态才进下一对，改动前后下单次数
   一致。
6. **429 行为未被触碰**：上列 9 个锁定用例全绿；`service.py:1175-1183` 与
   `:1199-1203` 逐字未改。
7. **既有回归全绿**：`backend/tests/` 全量通过。报告附完整测试输出到
   `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/62-cadence-test-output.txt`。
8. **边界**：未改 `frontend/`、未改 `test_hedge_review2_regressions.py`、未改
   51169 文案区、未新增运行时配置入口、未拆分间隔字段、未新增状态枚举。

## Stop

实现 → 自测 → 写实现报告到
`reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/23-cadence-implementation.md`
→ 提交（分支 `stage/2026-07-31-hedge-task-lifecycle-v1`）→ 把 `status.json` 的
`current_task.state` 由 `dispatched` 改为 `reported` → 返回
`[TASK_RESULT v2]`。

**停在这里。** 不要启动评审、不要写 `verified`、不要合并、不要碰 `main`。
后续为 review-1（`grok`）→ review-2（`codex`），由 Human 启动。

提交前自查：`git branch --show-current` 确认在
`stage/2026-07-31-hedge-task-lifecycle-v1` 上，`git log --oneline -1` 确认你的提交
真的落在该分支（本 stage 发生过派工单更正提交脱离分支的事故，见 `45-`）。
