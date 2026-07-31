# 00-task：2026-07-31-hedge-task-inline-log-v1（实现 dispatch packet）

> 定稿状态：**revision 6——Human 2026-07-31 决定收窄范围，本 stage 只做开单任务日志，
> 「任务卡卡住」相关全部移出**（详见 `06-scope-reduction.md`）。待计划评审（新范围首评）。
> 计划评审 ACCEPT 后由 Human 启动实现终端。起草者 claude_glm，定稿者 opus5。

## Identity

- task_id: 2026-07-31-hedge-task-inline-log-v1
- target_role: Implementer
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: 6
- required_skill: `agents/skills/senior-developer.md`
- 风险分级: **HIGH_RISK**（保持不变。理由：本 stage 向用户展示成交价格、成交数量与
  订单号——用户据此判断钱的去向；展示错误等同于错误的账务信息。且 §8 的 `LOW_RISK`
  只适用于「文档或机械性改动」，本 stage 是新功能 + 可能的读接口参数变更，不符合。
  仍走 review-1 + review-2。）

## Goal

1. **任务卡内嵌日志（真实数据）**：每个开单任务卡在「暂停/启动」按钮行下增加单个
   toggle 按钮（展开日志 ↔ 收起日志），展开后任务卡向下伸出该任务的尝试日志表格。
   列固定为：进展 / 状态 / 成交时间 / 合约订单号 / 现货订单号 / 合约均价 / 现货均价 /
   合约数量 / 现货数量 / 错误原因。倒序（最新在上，进行中那行数据可为空）；失败与
   单腿成交行必须展示错误原因；订单号 / 均价 / 数量按该腿是否受理填充。视觉与列语义
   以 fake 原型（commit `5871791`，`frontend/index.html:4229` 起的
   `renderHedgeTaskCardFake`）为准。
   - 「进展」列口径 = 该任务**已调度尝试序号 / 计划次数**（`scheduled_attempt_count` /
     `target_n`，含失败与单腿成交），与 fake 原型的 `n/10` 一致。
   - 数据必须覆盖该任务的**全部**尝试，不得是全局分页里恰好落在当前页的切片。
   - 展开状态记入 `state.hedgeLogExpanded`，跨自动刷新保持。
2. **任务卡展示 `#task-id`**：卡头显示任务唯一 id，便于人工定位与交流。
3. **移除 fake 数据**：真实版落地后删除 `renderHedgeTaskCardFake`、`HEDGE_FAKE_TASK_ID`
   及其仅服务于假卡的样式/绑定分支；不得留下未被引用的死代码。

### 【钱的展示口径 · 硬约束】

日志表格展示的是用户判断资金去向的依据，以下不可协商：

- **数值原样透传**：均价、数量直接取后端 attempt/leg 的原始字符串，前端不做四舍五入、
  不做单位换算、不做精度截断。后端已按币种原生精度存储。
- **未受理的腿显示 `—`，绝不显示 `0`**。`0` 会被读成「成交了 0 个」，而事实是「这条腿
  根本没被受理」——两者对用户的含义完全不同。这条踩过坑（51061 错误码曾被映射成 `0`）。
- **失败与单腿成交行必须有错误原因**，不得留空或显示 `—`。用户必须知道钱为什么没动、
  或者为什么只动了一条腿。
- **单腿成交行必须视觉可辨**（沿用 fake 原型的 warn 徽标），因为它代表**未对冲的裸敞口**。

## Allowed Files

- `frontend/index.html`（任务卡、日志表格、展开状态、`#task-id`、移除 fake 卡）
- `frontend/self-check.js`（前端自测）
- `backend/app/server.py`（**仅**为 `GET /api/hedge-open-logs` 新增**可选**的按任务过滤
  查询参数）
- `backend/hedge_open_tasks/service.py`（**仅** `get_logs` 的读路径接该过滤参数）
- `backend/hedge_open_tasks/store.py`（**仅**读查询；`list_attempts_for_task`
  （`store.py:1403`）已存在，优先复用）
- `backend/tests/test_hedge_*.py`（新增/修改测试）
- `reports/agent-runs/2026-07-31-hedge-task-inline-log-v1/`（自测与交付证据）

**后端三个文件只允许动读路径。** 不得触碰任务状态机、调度、结算、计数器、暂停/删除
语义、worker 生命周期。超出边界即为 blocker，停下回报，不得自行扩边界。

## Inputs

- fake 原型（UI / 列 / 交互的视觉与语义参考）：commit `5871791`，
  `frontend/index.html:4229` 起的 `renderHedgeTaskCardFake`。
- 现有日志接口：`GET /api/hedge-open-logs`（`backend/app/server.py:588`，
  `service.get_logs`）——当前只有 `cursor/limit` 与 `entries_cursor/entries_limit`，
  **没有**按任务过滤的参数。计划评审已确认：新增可选 `task_id`（或等价）过滤**有必要**，
  只靠前端过滤全局分页页面会漏掉该任务的历史尝试。
- 可复用：`store.list_attempts_for_task`（`store.py:1403`）已存在，不必新写查询。
- attempt / leg 字段与文档投影：`backend/hedge_open_tasks/domain.py`、
  `backend/hedge_open_tasks/store.py`（`list_attempts_page`）。
- 范围收窄说明与被移出项：`06-scope-reduction.md`（本目录）。

## Acceptance Checks

1. **四种状态渲染正确**：进行中 / 已成交 / 失败 / 单腿成交，各有测试；单腿成交行视觉
   可辨（warn 徽标）。
2. **【钱】数值原样透传**：测试证明均价与数量与后端原始字符串逐字一致，无四舍五入、
   无单位换算、无精度截断。
3. **【钱】未受理腿显示 `—` 而非 `0`**：构造一条被拒的腿，断言该行订单号/均价/数量
   显示 `—`，且页面上不出现 `0`。
4. **【钱】失败与单腿成交行有错误原因**：断言错误原因非空、非 `—`。
5. **数据真实且完整**：日志来自后端真实 attempt/leg 数据，覆盖该任务**全部**尝试
   （构造一个尝试数超过默认分页页大小的任务，断言全部可见）。
6. **「进展」列口径**：显示 `已调度序号 / 计划次数`，与 `scheduled_attempt_count` /
   `target_n` 一致。
7. **展开状态**：跨自动刷新保持（`state.hedgeLogExpanded`）；**未新增任何轮询定时器**
   （给出证据）。
8. **`#task-id` 可见**：卡头展示任务唯一 id。
9. **fake 代码已清干净**：`renderHedgeTaskCardFake`、`HEDGE_FAKE_TASK_ID` 及其专属样式/
   绑定分支已删除，全量搜索无残留引用。
10. **后端只动读路径**：给出 `git diff --stat` 与说明，证明未触碰状态机、调度、结算、
    计数器、暂停/删除语义、worker 生命周期。
11. **回归**：`frontend/self-check.js` 全过；`pytest backend/tests` 全过（贴原始输出，
    不得以叙述替代）。既有测试**不应有任何一条因本次改动转红**——若有，说明碰到了
    读路径以外的东西，停下回报。

## Stop

- 不写 live task DB、不下真实单、不碰凭据、不开 live 闸门、不做部署。
- **不做任何「任务卡卡住」相关的修复**（F10、暂停→删除、配额收口、`post_start` /
  `fill-once` / `fill-all` 的再武装检查）——已移出本 stage，见 `06-scope-reduction.md`。
- 不改任务状态机、不改 `PAUSE_REASON_*` 与其中文文案、不改 `aggregate_positions`、
  不改任何计数器或结算逻辑。
- 不新增全局轮询定时器（沿用「日志不随 tick 轮询」原则）；不新增 API 路由（按任务过滤
  只能是既有 `/api/hedge-open-logs` 上的**可选**参数）。
- 不扩 scope：不做平仓 / 补腿 / 借还币 / 自动对冲 / 自动平仓。
- 自测完成后停下回报，不启动评审终端、不合并、不推送。
