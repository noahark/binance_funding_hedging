# 36-task2-design-reservations-and-inputs —— Task 2 的设计保留与已确认输入

- 记录者：`opus5`（Bookkeeper），2026-08-02
- 触发：Human 在审视 Task 2 的状态设计后表示「**Task 2 看起来也不是很理想，先保持这样**」
- **Task 2（`hedge-task-lifecycle-v1`）状态由「暂缓」改为「设计存疑，暂缓」**

本文件保存 2026-08-02 状态设计讨论的全部产出。**Task 2 重启前必读**——这些结论不在
`10-design.md` / `11-adr.md` 里，是此后新发现的。

## 1. Human 的保留意见（未展开为具体修改要求）

Human 未逐条指出设计缺陷，只表示整体「不是很理想」。以下是讨论中**实际暴露**的问题，
供重启时判断保留意见的落点。

## 2. 讨论中暴露的五个问题

### 2.1 `done` 语义会因 Task 2 而更容易被误读（已知，但影响被低估）

D2 决定「`done` 语义本轮不处理」。但 P4 的死锁修复会**主动把「配额用尽、零成交」的
任务收口为 `done`**——而在此之前，这类任务卡在 `running` 转圈，**用户能一眼看出不对劲**。

即：修复把一个**可见的症状**换成了一个**安静的假象**。fake UI 阶段曾试画「计划 N 次 /
实际成功 M 次」的变体给 Human 看过，当时决定不做。**Task 2 落地后该问题的发生频率与
隐蔽性都会上升**，建议重启时重新评估 D2。

### 2.2 Human 提出的简化方案及其三个障碍

Human 曾设想：「除启动与人为暂停外，其他非人为暂停的状态全部进已完成；删除只能从暂停
状态点击。」Bookkeeper 指出三点，Human 未再坚持：

1. **把「没做完」说成「做完了」**——计划 10 次、第 2 次余额不足即停，却显示「已完成」。
   这正是本 stage 栽了四次的同一根因（界面断言它并不知道的事）；且 `done` 本已不诚实
   （§2.1），再塞入失败会使该词彻底失效。
2. **`order_state_unknown` 进「已完成」可能盖住裸腿**——该状态的含义是「有一条腿可能真实
   挂在交易所上，但系统不知道」，标为已完成等于宣布事情了结。
3. **设计内部冲突**——若非人为暂停全进「已完成」，而删除只能从「暂停」点击，则那些自动
   完成的任务**永远删不掉**，列表只会堆积。

ADR-002 已定的方案（五种终态原因 → **自动删除**、保留原因文案与成本基）在诚实性上优于
「全进已完成」：「不做了」是实话，「做完了」是假话。

### 2.3 `exposure_alert` 是死状态（本次核实发现）

`grep -rn "EXPOSURE_ALERT" backend/ --include="*.py"`（排除测试）**只有两处命中**：
`domain.py:44` 的定义与 `:51` 加入 `ALL_STATUSES`。**没有任何代码写入该状态。**

`resolve_status_after_attempt` 的返回集为 `DELETED / STOPPED / DONE / PAUSED /
current_status`，不含它；注释亦明写单腿敞口「is never a freeze on its own」、
「exposure_alert is ADVISORY」。单腿敞口的实际处理是记入 `leg_exposure` 字段并计入连续
失败计数。

**结论**：前端 `HEDGE_TASK_STATUS_LABELS` 中的「敞口告警」标签**永远不会出现**。
枚举、前端标签与 API 校验字符串（`domain.py:1329`）三处均在为一个不存在的状态服务。
**Task 2 重启时应决定：删除该死枚举，或补上写入路径。**

### 2.4 前端暂停原因中文缺失 6/7（本次核实发现，与 Task 2 强相关）

`frontend/index.html:4284` 的渲染逻辑：

```js
暂停原因：${escapeHtml(HEDGE_PAUSE_REASON_LABELS[task.pause_reason] || String(task.pause_reason))}
```

`HEDGE_PAUSE_REASON_LABELS`（`:3629`）**只有 `consecutive_submission_failure` 一条**。
其余 **6 个原因全部走 `|| String(...)` 兜底，直接把英文键名显示给操作者**：
`rate_limited` / `insufficient_balance` / `insufficient_margin` /
`insufficient_available_qty` / `collateral_cap_full` / `order_state_unknown`。

**而后端 `_PAUSE_REASON_ZH` 的中文文案一条不缺**，且 API 已返回 `pause_reason_zh` 字段
——**前端根本没有读它**。

最可惜的是 `collateral_cap_full`：它的 51169 文案是专为操作者撰写、带 `{asset}` 占位符、
被标记为**冻结不许改**的一段话，**却从未真正显示过**。

**修法很小**（前端优先读 `pause_reason_zh`，对照表仅作兜底），但属 `frontend/`，本 stage
的 Task 3 明确不动。**Task 2 要改的正是这批暂停原因，应一并处理。**

### 2.5 删除入口的状态限制（Human 提出，未定）

Human 提议「删除只能从暂停状态点击」。现状：`post_delete` 除 `already deleted` 外
**不限制任何状态**。

- **支持**：防止误删正在运行的任务。
- **反对**：`done` 也需可删（否则列表无法清理）；且 Task 2 落地后人工删除的场景本就减少。
- **未决**，重启时由 Human 定。

## 3. 已确认的输入（重启时直接采用）

- **`PAUSE_REASON_ORDER_STATE_UNKNOWN`（第 7 个暂停原因，Task 3 新增）既不属于自动删除
  的五种，也不属于退避的一种，应保留为人工暂停。** 该判断由 Bookkeeper 在 `27-` §4 提出，
  **Human 于 2026-08-02 的状态设计讨论中确认**（理由：它意味着可能有一条腿真实挂在交易所
  上，必须有人核对，不能自动消失）。

## 4. Task 2 落地后的状态全图（供重启时对照）

| 状态 | 来源 | Task 2 带来的变化 |
|---|---|---|
| `running` | 启动、闸门开、配额未尽 | **撞 429 后不再离开该状态**（改退避） |
| `paused` | ① 人工 ② `order_state_unknown` | **由 7 种来源降为 2 种** |
| `done` | ① 计划次数下满 ② 配额耗尽收口 | ②**变多且更隐蔽**（见 §2.1） |
| `stopped` | 7 种致命原因 | 不变 |
| `deleted` | ① 人工 ② **自动删除（5 种原因）** | ②为新增；保留原因文案与成本基 |
| `exposure_alert` | **无**（死状态） | 不变，见 §2.3 |
