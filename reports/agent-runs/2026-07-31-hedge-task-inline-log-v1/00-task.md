# 00-task：2026-07-31-hedge-task-inline-log-v1（实现 dispatch packet）

> 定稿状态：**intake 已由 bookkeeper（opus5）定稿，待计划评审（`02-plan-review.dispatch.md`）**。
> 计划评审 ACCEPT 后由 Human 启动本 packet 的实现终端。起草者 claude_glm（fast-fix
> bookkeeper），定稿者 opus5。

## Identity

- task_id: 2026-07-31-hedge-task-inline-log-v1
- target_role: Implementer
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: 3
- required_skill: `agents/skills/senior-developer.md`
- 风险分级: **HIGH_RISK**（读订单/attempt 数据 + 触碰调度与完成判定语义，AGENTS §8）

## Goal

1. **任务卡内嵌日志（真实数据）**：每个开单任务卡在「暂停/启动」按钮行下增加单个
   toggle 按钮（展开日志 ↔ 收起日志），展开后任务卡向下伸出该任务的尝试日志表格。
   列固定为：进展 / 状态 / 成交时间 / 合约订单号 / 现货订单号 / 合约均价 / 现货均价 /
   合约数量 / 现货数量 / 错误原因。倒序（最新在上，进行中那行数据可为空）；失败与
   单腿成交行必须展示错误原因；订单号 / 均价 / 数量按该腿是否受理填充，未受理填 `—`。
   展开状态记入 `state.hedgeLogExpanded`，跨自动刷新保持。视觉与列语义以 fake 原型
   （commit `5871791`，`renderHedgeTaskCardFake`）为准。
   - 「进展」列口径 = 该任务**已调度尝试序号 / 计划次数**（含失败与单腿成交，与
     `scheduled_attempt_count` / `target_n` 同口径），与 Goal 3 的修法保持一致。
   - 数据必须覆盖该任务的**全部**尝试，不得是全局分页里恰好落在当前页的切片。
2. **任务卡展示 `#task-id`**：卡头显示任务唯一 id，便于人工定位与交流。
3. **修复 F10（重启不生效）**：按**方向 B** 修，即**保持** `scheduled_attempt_count`
   = 计划调度上限（A-1 硬上限）的现有语义不变，改为让「计划次数已用尽但未达成」的
   任务进入明确终态、并让「启动」给出明确反馈，而不是静默置 running 后卡死。
   - **方向 A 已被否决**（不得实施）：把 worker 退出线改成 `accepted >= target_n`
     会让失败尝试无限重发新订单，突破用户设定的「计划 N 组」资金上限，属于资金语义
     变更；且 A-1 上限在 `store.py` 的预留事务中原子生效，只改 worker 退出线不会生效。
   - **根因家族必须一次穷举**（AGENTS §8 同根因刹车的预防性应用）：`scheduled_attempt_count
     >= target_n` 这一判据当前至少出现在 `service.py:1116`（worker 退出）、
     `store.py:686`（`list_eligible_tasks` 调度过滤）、`store.py:736`（预留原子上限）、
     `store.py:971`（R2-F1 结算收口为 `done`）。交付必须逐一列出该家族的全部站点，说明
     每处是「修改」还是「保持不变及理由」，清单外站点给出不适用理由。
   - **不得削弱** `failure_pause_threshold`：连续失败仍须暂停；本修复只保证暂停后的
     手动「启动」能真正恢复（worker 重新调度），且计划已用尽的任务不再悬空。
4. **移除 fake 数据**：真实版落地后删除 `renderHedgeTaskCardFake`、`HEDGE_FAKE_TASK_ID`
   及其仅服务于假卡的样式/绑定分支；不得留下未被引用的死代码。

## Allowed Files

- `frontend/index.html`（任务卡、日志表格、展开状态、`#task-id`、移除 fake 卡）
- `frontend/self-check.js`（前端自测）
- `backend/hedge_open_tasks/service.py`（F10：worker 退出条件、`post_start` 反馈）
- `backend/hedge_open_tasks/store.py`（F10：调度过滤 / 预留上限 / 结算收口三处判据）
- `backend/hedge_open_tasks/domain.py`（口径常量、状态解析、注释同步）
- `backend/app/server.py`（仅当日志接口需要新增**可选**的按任务过滤查询参数时）
- `backend/tests/test_hedge_*.py`（新增/修改测试）
- `reports/agent-runs/2026-07-31-hedge-task-inline-log-v1/`（自测与交付证据）

超出上述边界即为 blocker，停下并回报，不得自行扩边界。

## Inputs

- F10 诊断：`reports/agent-runs/2026-07-hedge-fast-fix-v1/findings.md`（F10 行）。
  实例：COOKIEUSDT，计划 1 / 已调度 1 / 已受理 0 / 连续失败 1，卡在 running 且无 worker。
- 根因站点：`backend/hedge_open_tasks/service.py:1116`、`backend/hedge_open_tasks/store.py:686`
  `:736`、`:971`、`backend/hedge_open_tasks/domain.py:1087`（`resolve_status_after_attempt`）。
- fake 原型（UI / 列 / 交互的视觉与语义参考）：commit `5871791`，
  `frontend/index.html:4229` 起的 `renderHedgeTaskCardFake`。
- 现有日志接口：`GET /api/hedge-open-logs`（`backend/app/server.py:588`，
  `service.get_logs`）——当前只有 `cursor/limit` 与 `entries_cursor/entries_limit`，
  **没有**按任务过滤的参数。
- attempt / leg 字段与文档投影：`backend/hedge_open_tasks/domain.py`、
  `backend/hedge_open_tasks/store.py`（`list_attempts_page`）。

## Acceptance Checks

1. **F10 复现在先**：先写一个失败测试复现当前悬空态（计划次数已用尽、未达成、
   `consecutive_failures < failure_pause_threshold`，任务停留 running 且无 worker，
   `post_start` 后仍无进展），提交该测试的失败输出，再修复使其转绿。
2. **F10 恢复路径**：因连续失败 `paused`、且计划次数**未**用尽的任务，手动「启动」后
   worker 重新调度并继续尝试（测试证明，不靠人工观察）。
3. **F10 终态与反馈**：计划次数已用尽且未达成的任务进入明确终态；对该任务点「启动」
   返回明确结果（不再静默置 running），前端展示可理解的中文反馈。
4. **根因家族清单**：交付回报中列出 `scheduled >= target_n` 家族的全部站点及每处的
   处理/不适用理由；`failure_pause_threshold` 的暂停语义有测试证明未被削弱。
5. **日志表格**：可展开/收起；四种状态（进行中 / 已成交 / 失败 / 单腿成交）渲染正确；
   倒序；失败与单腿行显示错误原因；未受理腿的订单号/均价/数量显示 `—`。
6. **数据真实且完整**：日志来自后端真实 attempt/leg 数据，覆盖该任务全部尝试；
   `renderHedgeTaskCardFake` 等假数据代码已删除且无残留引用。
7. **展开状态**：跨自动刷新保持（`state.hedgeLogExpanded`）；未新增全局轮询定时器。
8. **回归**：`frontend/self-check.js` 全过；`pytest backend/tests` 全过（贴原始输出，
   不得以叙述替代）。

## Stop

- 不写 live task DB、不下真实单、不碰凭据、不开 live 闸门、不做部署。
- 不实施方向 A（不得把调度上限改成 `accepted` 口径），不放宽 A-1 计划上限。
- 不绕过或削弱 `failure_pause_threshold`。
- 不新增全局轮询定时器（沿用「日志不随 tick 轮询」原则）；不新增 API 路由（按任务
  过滤只能是既有 `/api/hedge-open-logs` 上的**可选**参数）。
- 不扩 scope：不做平仓 / 补腿 / 借还币 / 自动对冲 / 自动平仓。
- 自测完成后停下回报，不启动评审终端、不合并、不推送。
