Identity:
- task_id: `frontend-position-balance-display-v1`
- target_role: `Implementer`
- target_model: `grok`
- provider: `xai`
- status_revision: `10`
- required_skill: `agents/skills/senior-developer.md`

Goal

实现 Human 已验收的 v4.1 §9 最小前端展示调整。Human 已明确授权 Grok 执行本前端任务。只改三个已决定的显示点，并消费已验证的后端 positions 字段：

1. 把市场表同一行既有的「抵押额度已满」/「抵押额度未知」徽标从标的单元格移动到「借贷状态 / 资产」单元格；仍只显示一个徽标，保留既有 `collateral_cap` / `ui_flags` 判定、颜色、title、排序、过滤及按钮语义。
2. 将真实「对冲开单持仓」表的既有「现货余额」列改为两行：`现货: <spot_balance> ≈ <spot_balance_value_usdt, 2 位> U` 与 `杠杆: <unified_balance> ≈ <unified_balance_value_usdt, 2 位> U`。数据只能来自同一 `/api/hedge-open-positions` row 的四个字段；不得从 snapshot 拼接、重算估值或改借款列。每侧独立：amount 缺失显示 `—`，amount 有而 value 缺失显示 `≈ — U`，真 `0` 必须显示为 0；隐私模式须同时遮蔽 amount 与估值。`cross_margin_borrowed` 继续只在既有「全仓借款」列显示。
3. 保持唯一的 `#account-asset-updated-at` 与既有 `checked_at` → `valuation.priced_at` 回退，但移动到标题区以替换固定文字「行情公开 · 账户需 key 私有只读」；右侧刷新区只保留倒计时和两个按钮。PM capability 存在时，把既有 PM 数据源时间移动到「私有账户」标题正下方；capability 缺失隐藏，存在但 `pm_account` 时间为空显示未就绪，有时间显示北京时间；该 PM 行不得再出现在概览统计区。

不改后端、API 契约、snapshot 夹具、刷新请求/定时器、自动轮询、缓存、订单、借贷写入、Start gate、凭证、服务或部署。

Allowed Files

- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-position-balance-display-v1.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`，结果为通过；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-position-balance-display-v1.self-check.txt`（测试原始输出）
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`（仅可将本任务 `current_task.state` 从 `dispatched` 改为 `reported`；不得改动任何其他字段）

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/frontend-position-balance-display-v1.dispatch.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`
- `agents/roles.md` 的 Implementer 与 Task Handoff Evidence Contract 章节
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `docs/planning/hedge-status-account-refresh-v4.md`（§9）
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/plan-review-position-balance-display-v1-deepseek.handoff.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-position-balance-display-v1.handoff.md`
- `frontend/index.html`、`frontend/self-check.js`

Acceptance Checks

1. 市场表中已满/未知抵押额度徽标仅出现在同一行「借贷状态 / 资产」单元格，标的单元格不再出现；既有三态、不适用/缺键、title 截至时间、方向无关和零排序/过滤/按钮影响的 self-check 覆盖保持。
2. 真实 positions 表的「现货余额」表头与单元格显示独立的现货/杠杆两行，精确消费 `spot_balance`、`spot_balance_value_usdt`、`unified_balance`、`unified_balance_value_usdt`。self-check 覆盖：双侧完整、任一侧 amount 缺失、amount 有而 value 缺失、两侧真实零、账户未就绪全缺、隐私遮蔽；不从 snapshot 查余额，借款列不改变。
3. `#account-asset-updated-at` 在标题区且替换固定副标题，右侧 `refresh-meta` 不再容纳它；聚合字段/北京时间/回退逻辑不变。PM 时间只在私有账户标题下显示，并覆盖 capability 缺失隐藏、null 未就绪、成功北京时间三态；概览区没有重复 PM 行。
4. 原有「更新缓存」POST、手动刷新 GET、loading、完成后重读与零自动轮询/零新增定时器语义完全不变。
5. 离线执行并保存 `node frontend/self-check.js` 的完整原始输出；不得启动服务、访问网络、读取凭证或操作实盘。

Stop

只在 Allowed Files 内修改。创建 handoff 后用其 Human Brief 生成合规 `[TASK_RESULT v2]`，将本任务状态标为 `reported`，在一个 delivery commit 中提交所有 Allowed Files；handoff 的 `delivery_sha` 写 `pending`。不要自行启动 Reviewer、Bookkeeper、部署或实盘/网络操作。
