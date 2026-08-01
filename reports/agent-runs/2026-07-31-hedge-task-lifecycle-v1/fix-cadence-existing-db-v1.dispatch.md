# fix-cadence-existing-db-v1.dispatch

```text
Identity:
  task_id:         fix-cadence-existing-db-v1
  target_role:     Implementer
  target_model:    claude_glm
  provider:        zhipu_glm
  status_revision: 24
  required_skill:  agents/skills/minimal-change-engineer.md
```

## Goal

修 `24-bookkeeper-rejection-task3.md` 的 **BK-T3-001**：让 `aac779d` 的节奏下调
**在既有数据库上真正生效**。

现状：`DEFAULT_INTERVAL_US = 100_000` 只在建库种子插入处被引用，`_migrate()` 不触碰
`hedge_open_settings`，且该表**没有任何运行时写入途径**。因此已存在 settings 行的库
（含实盘库 `data/hedge-open-tasks.sqlite3`，实测 `interval_us = 1000000`）永远停在
1 秒——交付目标零效果。

**这是 packet 与已批准设计（ADR-003）共同的遗漏，不是你上一轮的实现错误。**
上一轮的其余七项验收已由 Bookkeeper 独立核验通过（含破坏验证），**不要重做、不要
重构、不要"顺手改进"**。本任务只补这一个洞。

`rework_count` 不因本任务递增（裁定见 `24-` §4）。

## Allowed Files

```text
backend/hedge_open_tasks/store.py     # _migrate 内补一处 settings 回填
backend/tests/test_hedge_store.py     # 迁移的新断言
backend/tests/test_hedge_api.py       # 上一轮已改此文件；正式纳入边界
```

### 不得改动

```text
backend/hedge_open_tasks/domain.py    # 常量已正确，不要动
backend/hedge_open_tasks/service.py   # 显示/抖动已通过核验，不要动
frontend/ 全部
backend/tests/test_hedge_review2_regressions.py
429 / rate_limited 处理逻辑（service.py:1175-1183、:1199-1203）
domain.py 的 51169 文案区（:1336-1360）
reports/agent-runs/**/status.json 之外的任何 reports/ 文件
data/ 下的任何数据库文件（实盘库只读，见下）
```

**实盘库红线**：`data/hedge-open-tasks.sqlite3` 是**活的实盘库**（`PROJECT_STATE.md`
Live Risks）。**不得写入、不得就地迁移、不得用它跑测试。** 需要真实数据验证时
**复制到临时目录**再操作，并在报告中写明你用的是副本。

## Inputs

### 迁移语义（必须按此实现，不要自行扩大）

在 `_migrate()`（`store.py:351`）内补一处**保守回填**：

- **仅当** `hedge_open_settings.interval_us` 恰等于旧默认值 `1_000_000` 时，
  更新为 `D.DEFAULT_INTERVAL_US`，并同步 `interval_seconds` 为
  `D.DEFAULT_INTERVAL_SECONDS`。
- 其他任何值**一律不动**（可能是将来某个刻意设定的值）。
- 与 `_migrate` 既有风格一致：幂等、可重复执行、无副作用日志。
- **不新增**设置写入端点或运行时配置入口（红线 #6，ADR-003 Decision 5）。

**为什么是"仅当等于旧默认"而不是无条件覆盖**：无条件覆盖会在将来悄悄推翻一个人为
设定的值——那正是本 stage 反复栽的同一类问题（系统替用户做了它无权做的判断）。

### 抖动方向（一并修，见 `24-` 观察 A）

`service.py` 的 `_PACING_JITTER_MIN = 0.75` 使平均实际间隔 `87.5ms` < 标称 `100ms`，
请求量比标称高约 14%。在本轮**不做 429 退避**的前提下方向反了，抖动应偏保守。

**但 `service.py` 在本 packet 的「不得改动」内。** 若你认为该调整应与本修复同轮进行，
**不要自行动手**——在 `TASK_RESULT` 的 `阻塞项` 里提出，由 Bookkeeper 决定是否扩
边界。本条列在这里是让你知情，不是授权。

### 已核实锚点（`aac779d` 上实测）

| 目标 | 位置 |
|---|---|
| 种子插入（条件 `COUNT(*) == 0`） | `store.py:337-350` |
| `_migrate` 定义 | `store.py:351` |
| `get_interval_us`（已夹下限，勿动） | `store.py:2119-2128` |
| 默认值常量（勿动） | `domain.py:513-515` |

## Acceptance Checks

1. **既有库生效**：构造一个 `interval_us = 1_000_000` 的既有库（先建库再 UPDATE，
   或直接建表插行），用新代码打开后 `get_interval_us() == 100_000`、接口
   `interval_seconds == 0.1`。**这条必须能失败**——去掉迁移即转红。
2. **不覆盖非默认值**：`interval_us` 为 `250_000`（既非旧默认也非新默认）的库，
   打开后仍为 `250_000`。
3. **幂等**：同一个库连续打开两次，结果一致，无重复写入副作用。
4. **新库不受影响**：全新空库仍为 `100_000` / `0.1`（种子路径未被破坏）。
5. **真实数据验证**：把 `data/hedge-open-tasks.sqlite3` **复制**到临时目录，用新代码
   打开副本，报告中给出 `get_interval_us()` 与 `interval_seconds` 的实际输出。
   原库不得被写入（报告中说明你如何保证）。
6. **回归全绿**：`python3 -m pytest backend/tests/ -q` 全量通过（上一轮基线
   **1140 passed**；新增用例后总数应上升）。输出存
   `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/63-cadence-migration-test-output.txt`。
7. **边界**：未改 `domain.py`、`service.py`、`frontend/`、`test_hedge_review2_regressions.py`、
   51169 文案区；未新增配置入口；未写入 `data/` 下任何库。

## Stop

实现 → 自测 → 追加实现报告到
`reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/25-cadence-migration-implementation.md`
→ 提交（分支 `stage/2026-07-31-hedge-task-lifecycle-v1`）→ 把 `status.json` 的
`current_task.state` 由 `dispatched` 改为 `reported` → 返回 `[TASK_RESULT v2]`。

**停在这里。** 不要启动评审、不要写 `verified`、不要合并、不要碰 `main`。

提交前自查：`git branch --show-current` 与 `git log --oneline -1` 确认提交真的落在
`stage/2026-07-31-hedge-task-lifecycle-v1` 上（本 stage 出过游离提交事故，见 `45-`）。

**边界不足时停下报告，不要临场扩边界**（上一轮 `test_hedge_api.py` 即属此情形，见
`24-` §3 程序说明）。
