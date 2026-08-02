# fix-cadence-500ms-and-absent-tolerance-v1.dispatch

```text
Identity:
  task_id:         fix-cadence-500ms-and-absent-tolerance-v1
  target_role:     Implementer
  target_model:    claude_glm
  provider:        zhipu_glm
  status_revision: 25
  required_skill:  agents/skills/senior-developer.md
```

**本 packet 取代 `fix-cadence-existing-db-v1.dispatch.md`（已作废，从未投递）。**

## Goal

Human 于 2026-08-01 改变了本轮方向（D19/D20）。交付目标由「1s → 100ms 提速 10 倍」
改为：

> **1s → 500ms（提速 2 倍），并消除「真实挂单被判定为从不存在」的风险。**

六件事，缺一不可：

1. 默认重查间隔 `1s → 500ms`（**不是** `aac779d` 里的 `100ms`）；
2. 补迁移，使新默认值在**既有数据库**上真正生效（拒收项 BK-T3-001）；
3. **移除抖动**（Human 从未要求，且削减首查安全边界）；
4. `404 / -2013` **不再一次判死**：改为时间窗口内继续重查；
5. 现有**无上限**的「继续查」分支（5xx / 超时 / 畸形 2xx）套同一窗口，但**收口方式
   不同**（见下，这是安全要害）；
6. 与 `_confirm_um_figures` 的既有语义统一。

`rework_count` 因 Human 同意的新交付范围**重置为 0**（`AGENTS.md` §8）。

## 本任务的设计依据（先读这一条，它决定第 4-6 项的正当性）

`backend/services/live_hedge_executor.py` 的 `_confirm_um_figures` docstring **本身
就断言了这件事**（逐字）：

> Any other confirm outcome — inconclusive (timeout / 5xx), a malformed 2xx, or
> even a literal 404/-2013 (**a POST-just-accepted order 404-ing is
> eventual-consistency noise, NOT a real absent signal**) — leaves the leg
> ACCEPTED with `cumulative_quote=None` so it is non-terminal and the worker
> drains it next round (query, never resend).

且已有测试锁定该行为：
`test_live_hedge_executor.py::test_dispatch_um_confirm_404_does_not_overturn_post_acceptance`。

**但同模块的另一条路径判断相反**：worker 的 drain 查询
（`_reconcile_own_legs` → `classify_query_response`）把 `404 / -2013` 判为
`TERMINAL_RECORDED` + `error_category=absent`，`_query_verdict_terminal` 随即返回
`True`，**该腿一次判死**。

即：**离下单最近的那次查询（POST 后立即 confirm）做了保护，隔一个间隔的 drain 查询
反而没有。** 本任务第 4-6 项不是新增防御机制，而是**把已有语义补齐到缺失的那条
路径**。请在实现报告中引用上述 docstring 作为依据。

## Allowed Files

```text
backend/hedge_open_tasks/domain.py     # 默认值 500ms、窗口常量
backend/hedge_open_tasks/store.py      # 既有库迁移、get_interval_us 下限
backend/hedge_open_tasks/service.py    # 移除抖动、窗口判定、两种收口
backend/tests/test_hedge_service.py
backend/tests/test_hedge_store.py
backend/tests/test_hedge_task_local.py
backend/tests/test_hedge_api.py
backend/tests/test_hedge_review2_regressions.py   # 仅限下述受限授权
```

### 关键实现约束：窗口判定必须在 service 层，不得改 executor

`classify_query_response`（`backend/services/live_hedge_executor.py`）**不在允许
清单内，不得修改**。理由：它是网络层分类器，不持有腿的信息（不知道何时下的单）。
窗口判定需要 `dispatched_at_us`，只有 service 层拿得到。

**做法**：让 `_query_verdict_terminal` / `_reconcile_own_legs` 在收到 `absent`
verdict 时，结合腿的 `dispatched_at_us`（`hedge_open_leg` 表，`store.py:97`，字段
已存在，**不要新增字段**）判断窗口是否耗尽。

### 不得改动

```text
backend/services/live_hedge_executor.py        # 分类器语义不动，见上
frontend/ 全部
domain.py 的 51169 文案区（:1336-1360）
429 / rate_limited 处理逻辑（service.py:1175-1183、:1199-1203）
backend/hedge_open_tasks/private_client.py
data/ 下任何数据库文件（实盘库只读，验证须先复制到临时目录）
reports/agent-runs/**/status.json 之外的 reports/ 文件
```

## Inputs

### 两种收口方式（第 5 项的要害，不要合并成一种）

窗口耗尽之后：

| 腿最后一次查询的结果 | 收口 | 理由 |
|---|---|---|
| `404 / -2013` | **判 `absent` 终态**（即现行行为，只是推迟约 5 秒） | 5 秒后仍明确回「不存在」，是**确认不存在**的信号 |
| 5xx / 超时 / 畸形 2xx | **不得判 `absent`**；转非终态的人工处理（暂停任务并留腿，走既有 task-local pause 语义） | 它们**从来不是**「确认不存在」的信号。判 `absent` 等于把「不知道」当成「确认没有」——这正是 R2-F2 明令禁止的错误 |

`test_query_2xx_without_order_id_stays_unknown` 的注释已写明该红线：
「绝不把一个可能已被接受的订单误判为不存在」。窗口耗尽不改变这条腿「是否确认不存在」
的性质，只改变「还要不要继续等」。

### 窗口参数

- 长度：**约 5 秒**（= 原 JS 的 10 次 × 500ms 容忍窗口）。
- 实现：**时间窗口**，不是次数计数器。锚点用既有的
  `hedge_open_leg.dispatched_at_us`。**不新增数据库字段**（项目红线）。
- 常量放 `domain.py`，与 `DEFAULT_INTERVAL_US` 同区。

### 已知会受影响的锁定回归（**必须先分析再动手**）

`test_hedge_review2_regressions.py::test_5b_auth_ambiguity_stays_unknown_then_absent_confirms_failure`
（`:400-424`）注入一个 `error_category="absent"` 的 verdict，随即断言
`task["fail_count"] == 1`。**加窗口后该 absent 很可能不再立即终态，此测试会变红。**

**受限授权**：若你确认变红是窗口语义的必然结果，允许**仅**调整该测试的时钟推进
（让它跨过窗口），**不得改变它断言的核心事实**——absent 被确认之后 `fail_count`
加 1。任何超出「推进时钟」的改动，停下来报告，不要自行处理。

其余 `test_hedge_review2_regressions.py` 内容一律不得改动。

请一并检查（本 packet 未穷举）：`test_hedge_task_local.py::test_4l_...`
（`:1052`）断言 absent 是 decisive、替换占位行——这是**证据落库**语义，与终态语义
不同，预计不受影响，但请确认。

### 原 JS 对照（本方案的来源，`币安套费率策略，逐仓杠杆.js`）

| | 首查延迟 | 查不到怎么办 | 容忍窗口 |
|---|---|---|---|
| 原 JS | `Sleep(500)`（4 条路径中 3 条） | `getSpotOrderInfo` 重试 **10 次**，每次 500ms | **约 5 秒** |
| 后端（改前） | 1000ms | **一次判死** | 1 秒 |
| 后端（本任务后） | **500ms** | **窗口内继续查** | **约 5 秒** |

### 已核实锚点（`aac779d` 上实测，方案文档的行号已过期，勿照抄）

| 目标 | 位置 |
|---|---|
| 默认值常量 | `domain.py:513-515`（`DEFAULT_INTERVAL_SECONDS` / `DEFAULT_INTERVAL_US` / `MIN_INTERVAL_US`） |
| 种子插入（条件 `COUNT(*)==0`） | `store.py:337-350` |
| `_migrate` 定义 | `store.py:351`（**不触碰 `hedge_open_settings`，这是 BK-T3-001 的根因**） |
| `get_interval_us`（已夹下限） | `store.py:2119-2128` |
| worker 节流（抖动在此） | `service.py:1123` 的 `paced_wait_seconds` |
| 抖动定义 | `service.py` 的 `_PACING_JITTER_MIN` / `paced_wait_seconds` |
| `_reconcile_own_legs` | `service.py:1213` |
| `_query_verdict_terminal` | `service.py`（`_query_verdict_decisive` 之前） |
| 腿的下单时间锚点 | `hedge_open_leg.dispatched_at_us`（`store.py:97`） |

### 迁移语义（保守，不要扩大）

`_migrate()` 内补一处回填：**仅当** `hedge_open_settings.interval_us` 恰等于旧默认
`1_000_000` 时更新为 `D.DEFAULT_INTERVAL_US`，并同步 `interval_seconds`。其他值
一律不动（可能是刻意设定）。幂等、可重复执行。

**不新增设置写入端点或运行时配置入口**（红线 #6 / ADR-003 Decision 5）。

## Acceptance Checks

1. **既有库生效**：`interval_us = 1_000_000` 的既有库，新代码打开后
   `get_interval_us() == 500_000`、接口 `interval_seconds == 0.5`。**去掉迁移即转红。**
2. **不覆盖非默认值**：`interval_us = 250_000` 的库打开后仍为 `250_000`。
3. **新库**：全新空库为 `500_000` / `0.5`；前端 `index.html:3856` **未修改**即渲染
   出正确文案（报告中写出原文）。
4. **抖动已移除**：`_PACING_JITTER_MIN`、`paced_wait_seconds` 及其单测均不复存在；
   节流等待为确定值。
5. **404 窗口容忍**：下单后窗口内收到 `404 / -2013` → 腿**保持非终态、继续查**；
   窗口耗尽后再收到 → 判 `absent` 终态。**两条都要能失败。**
6. **不知道 ≠ 不存在**：窗口耗尽时最后结果为 5xx / 超时 / 畸形 2xx 的腿
   **不得**被判 `absent`，须转人工路径。**这条必须有独立的、能失败的测试。**
7. **语义统一**：实现报告说明本改动如何与 `_confirm_um_figures` 的既有保护一致，
   并引用其 docstring。
8. **锁定回归**：9 个 `rate_limited` 用例全绿；`test_4l` 全绿；`5b` 若调整，仅调整
   时钟推进且核心断言不变，并在报告中单独说明。
9. **真实数据验证**：复制 `data/hedge-open-tasks.sqlite3` 到临时目录后验证，报告给出
   实际输出并说明原库未被写入。
10. **回归全绿**：`python3 -m pytest backend/tests/ -q` 全量通过（基线
    **1140 passed**）。输出存
    `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/63-cadence-500ms-test-output.txt`。
11. **边界**：未改 `live_hedge_executor.py`、`frontend/`、51169 文案区、429 逻辑；
    未新增数据库字段、配置入口、状态枚举；未写入 `data/` 下任何库。

## Stop

实现 → 自测 → 实现报告写到
`reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/25-cadence-500ms-implementation.md`
→ 提交（分支 `stage/2026-07-31-hedge-task-lifecycle-v1`）→ 把 `status.json` 的
`current_task.state` 由 `dispatched` 改为 `reported` → 返回 `[TASK_RESULT v2]`。

**停在这里。** 不要启动评审、不要写 `verified`、不要合并、不要碰 `main`。
后续为 review-1（`grok`）→ review-2（`codex`）。

提交前自查 `git branch --show-current` 与 `git log --oneline -1`，确认提交真的落在
stage 分支上（本 stage 出过游离提交事故，见 `45-`）。

**边界不足时停下报告，不要临场扩边界**（上一轮 `test_hedge_api.py` 即属此情形，见
`24-` §3）。
