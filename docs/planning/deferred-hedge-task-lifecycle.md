# Deferred — Hedge Task Lifecycle (原 Task 2)

Status: **designed, plan-reviewed, deliberately not built.** 2026-08-02.

Human 于 2026-08-02 决定暂缓：「Task 2 看起来也不是很理想，先保持这样」，随后
「暂时还不打算做」。本文件是该工作包的**自包含记录**——原 stage
`2026-07-31-hedge-task-lifecycle-v1` 归档后，重启它只需读本文件。

原始材料（归档分支 `archive/2026-07-31-hedge-task-lifecycle-v1`）：
`10-design.md` P3/P4/P5、`11-adr.md` ADR-002、`12-development-breakdown.md`
Task 2 节、`36-task2-design-reservations-and-inputs.md`、`27-` §4。

---

## 1. 它要解决什么

四件事，全部有已核实的证据：

1. **任务卡会卡死。** 计划下 N 次，配额排满后程序不知道收尾，一直显示「运行中」转圈。
   根因：`post_start` 这一站缺配额守门，而其余三个再武装入口都有。
2. **六种非人工暂停变成僵尸态。** 余额不足、保证金不足、可用数量不足、抵押额度打满、
   连续提交失败、撞限频——全都写 `paused`，要人逐个点恢复。
3. **`resolve_leg_from_query` 无 `COALESCE` 保护**：后一次查询返回 `None` 会覆盖已知的
   `avg_price` / `quote_amt`。当前不可达（币安订单详情 GET 同时返回两者），是上游变化时
   的保险。
4. （原含重查间隔，**已由 Task 3 交付**，见 `PROJECT_STATE.md`。）

## 2. 已定的设计

### P4 死锁修法

在三个再武装入口（`post_start` / `post_fill_once` / `post_fill_all`）汇聚的共享路径加
**与 A-1 同谓词**的守门：`scheduled_attempt_count >= target_n` 时不置 `running`，收口到
`DONE`（复用 `post_start` 既有的 `DONE` 幂等路径）。同时 `post_start` 对 `stopped` 不再
武装。**属收紧非放宽，不切到 `accepted` 口径。**

降级方案（若不接受 `stopped` 变为不可重启）：仅保留配额守门，不动 `stopped`。

### ADR-002 / D16 —— 五种删除 + 限频退避

Human 最初要求「六种非人工暂停全改自动删除」。设计将其细化为**五删一退避**：

| 原因 | 处置 |
|---|---|
| `consecutive_submission_failure` / `insufficient_balance` / `insufficient_margin` / `insufficient_available_qty` / `collateral_cap_full` | **自动 `DELETED`**，保留 `pause_reason` + `pause_reason_zh`（51169 冻结文案在已删卡上仍逐字显示） |
| `rate_limited` | **不删不暂停**，改指数退避 + 抖动重试（用既有 `stop_event.wait`，不新增字段/枚举） |

**偏离字面清单、对齐深层意图**：五种是「不重新配参数即无法成功」的终态失败，删之合理；
`rate_limited` 是**瞬态背压**，删它等于把「等一下」误判为「失败」，且会毁掉已部分成交
任务的资金可见性。Human 已批准（D16）。

### P5 自动删除的边界

走 `post_delete` 同款「只置 `DELETED`、不打断 worker」路径。worker 若在触发时正有在途腿，
继续 drain 到终态后在状态检查点退出——**与人工删完全等价，不杀在途腿**。被删任务的已成交
腿仍两路可见：敞口靠 `um_positions` 真实骨架，成本基靠 D15（`aggregate_positions` 的两条
`WHERE` 已放行已删任务）。

### 红线

不新增**任务状态**枚举（`STATUS_*`）；不放宽 A-1；51169 文案逐字不动。

---

## 3. 设计保留意见（Human 说「不理想」，以下是讨论中实际暴露的问题）

**重启前必须先处理这一节，否则会重蹈覆辙。**

### 3.1 `done` 语义会因本工作包而更容易被误读

D2 曾决定「`done` 语义本轮不处理」。但 P4 的死锁修复会**主动把「配额用尽、零成交」的
任务收口为 `done`**——而在此之前这类任务卡在 `running` 转圈，**用户能一眼看出不对劲**。

**修复把一个可见的症状换成了一个安静的假象。** fake UI 阶段曾试画「计划 N 次 / 实际成功
M 次」的变体，当时决定不做。落地后该问题的频率与隐蔽性都会上升，**建议重启时重新评估 D2**。

### 3.2 「非人为暂停全进已完成」方案的三个障碍

Human 曾设想更激进的简化：除启动与人为暂停外，其余状态全进「已完成」；删除只能从暂停态
点击。三个障碍（Human 未再坚持）：

1. **把「没做完」说成「做完了」**——计划 10 次、第 2 次余额不足即停却显示「已完成」。
   这是本 stage 栽了四次的同一根因；且 `done` 本已不诚实（§3.1）。
2. **`order_state_unknown` 进「已完成」可能盖住裸腿**——该状态意味着可能有一条腿真实挂在
   交易所上。
3. **内部冲突**——若非人为暂停全进「已完成」而删除只能从「暂停」点，那些任务**永远删不掉**。

ADR-002 的「自动删除」在诚实性上优于「全进已完成」：「不做了」是实话，「做完了」是假话。

### 3.3 `exposure_alert` 是死状态

全后端**无任何写入路径**（仅 `domain.py` 的枚举定义与 `ALL_STATUSES`）；
`resolve_status_after_attempt` 的返回集不含它；单腿敞口实际记入 `leg_exposure` 字段并计入
连续失败计数。**前端「敞口告警」标签永不出现。** 引入 `d90f2f1`。

重启时应决定：**删除该死枚举，或补上写入路径。**

### 3.4 前端暂停原因中文缺失 6/7

`HEDGE_PAUSE_REASON_LABELS` 只有 `consecutive_submission_failure` 一条，其余全部走
`|| String(...)` 兜底**直接显示英文键名**；而后端 `_PAUSE_REASON_ZH` 文案一条不缺、API 已
返回 `pause_reason_zh`——**前端从未读取它**。

日志时间线是通的（经 `error_reason_zh`），所以完整中文在日志页可见，**缺的只是任务卡那一
行**。引入 `d873699`。**两行级前端修法，已作为独立 follow-up 记入 `PROJECT_STATE.md`，
不必等本工作包。**

### 3.5 删除入口的状态限制（未定）

Human 提议「删除只能从暂停状态点击」。现状 `post_delete` 除 `already deleted` 外不限制
任何状态。支持：防误删运行中任务。反对：`done` 也需可删（否则列表无法清理）。**未决。**

---

## 4. 已确认的输入（重启时直接采用）

**`PAUSE_REASON_ORDER_STATE_UNKNOWN`（第 7 个暂停原因，由 Task 3 引入）既不属于自动删除
的五种，也不属于退避的一种，应保留为人工暂停。** Human 于 2026-08-02 确认，理由：它意味
着可能有一条腿真实挂在交易所上，必须有人核对，不能自动消失。

因此 `ALL_PAUSE_REASONS` 现有**七**个值，本工作包处理的是其中六个。

**另一条来自 Task 3 的观察**：已删除任务的 `order_state_unknown` 收口事件复用
`kind=task_paused`，文案却说「任务已暂停…请手动恢复」——对已删任务既没暂停也不可恢复。
本工作包动暂停原因时应一并换成如实文案。

---

## 5. 落地后的状态全图（供对照）

| 状态 | 来源 | 本工作包带来的变化 |
|---|---|---|
| `running` | 启动、闸门开、配额未尽 | **撞 429 后不再离开该状态**（改退避） |
| `paused` | ① 人工 ② `order_state_unknown` | **由 7 种来源降为 2 种** |
| `done` | ① 计划次数下满 ② 配额耗尽收口 | ② **变多且更隐蔽**（见 §3.1） |
| `stopped` | 7 种致命原因 | 不变（除非采纳「`stopped` 不可重启」） |
| `deleted` | ① 人工 ② **自动删除（5 种原因）** | ② 为新增；保留原因文案与成本基 |
| `exposure_alert` | **无**（死状态） | 见 §3.3 |

## 6. 文件边界（原设计，行号已过期）

`backend/hedge_open_tasks/{service,store,domain}.py` +
`backend/tests/test_hedge_{service,store,task_local,domain}.py`。
**不得改动** `frontend/`（§3.4 的修法除外，且应独立成任务）、51169 文案区。

风险等级 `HIGH_RISK`（任务状态机 + 资金可见性 + 实盘写路径），按 `AGENTS.md` §8 需
review-1 + review-2。

**注意**：所有原始设计文档中的行号写于 Task 1 / Task 3 合并之前，`service.py` 与
`store.py` 已大幅变动，**重启时必须重新核实全部锚点**。
