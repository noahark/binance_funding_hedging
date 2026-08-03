Identity:
- task_id: `plan-review-position-balance-display-v1-deepseek`
- target_role: `Reviewer`（独立计划评审）
- target_model: `deepseek`
- provider: `deepseek`
- status_revision: `8`
- required_skill: `agents/skills/code-reviewer.md`

Goal

只读审查 v4.1 的页面验收后增补（`docs/planning/hedge-status-account-refresh-v4.md` §9），确认它是最小且可验证的展示扩展。重点判断：普通现货/统一账户余额与估值字段是否来自同一已发布账户快照、null 与真零是否诚实、`cross_margin_borrowed` 是否仍只代表借款、时间与 PM 文案迁移是否会破坏现有 source freshness 语义，以及是否意外引入 429、上游 I/O、自动刷新或交易副作用。Human 已明确选择“后端挂字段 + 前端两行”的方案；不要提出第二缓存、前端跨接口拼接、自动补救或假设性重构。

Allowed Files

- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/plan-review-position-balance-display-v1-deepseek.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`，结果为通过；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/plan-review-position-balance-display-v1-deepseek.dispatch.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`
- `agents/roles.md` 的 Planner、Reviewer 与 Task Handoff Evidence Contract 章节
- `agents/skills/code-reviewer.md`
- `docs/planning/hedge-status-account-refresh-v4.md`（尤其 §9）
- `backend/hedge_open_tasks/domain.py`、`backend/app/server.py`、`backend/tests/test_positions_merge.py`、`backend/tests/test_hedge_api.py`
- `backend/domain/snapshot.py`、`docs/api/public-market-contract.md`
- `frontend/index.html`、`frontend/self-check.js`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-cache-refresh-v1.handoff.md`

Acceptance Checks

1. `unified_balance` / `unified_balance_value_usdt` 的真源、类型、null 与真零语义清楚；普通现货的 amount/value 也能同一次 positions 响应完整表达，且不会把 `cross_margin_borrowed` 当余额。
2. 后端投影仍仅消费 published snapshot；`GET /api/hedge-open-positions` 保持零上游 I/O，不改变 cache refresh、60 秒节奏或任何订单/借贷/闸门。
3. 两行 UI、抵押额度徽标迁移、聚合账户时间和 PM 时间迁移有明确唯一位置，并保留隐私、缺失、PM 三态与无自动刷新边界。
4. 测试可覆盖字段值、单侧缺失、未就绪、真零、HTTP 精确 keyset、隐私、DOM 位置和原有离线回归；不要求真实服务或网络。
5. 发现只记录明确的设计矛盾、错误真源或不可验证风险；不要为纯展示任务添加猜测性机制。结论必须是明确 `ACCEPT` 或 `REWORK`；REWORK 逐项标注 AGENTS §8 范围分类和最小修复。

Stop

保持只读；不得修改代码、设计、测试、状态、PROJECT_STATE 或既有证据，不得 commit/merge/push。唯一写入是规定 handoff，其中固定 `base_sha` 填 `990570b7b44b1d4a045627aecd8f9cca0f1c8f5b`、`delivery_sha` 为 `none`，并含 Source Report、Human Brief、明确计划评审结论与可执行下一步。不要自行启动 Implementer、Bookkeeper、Review-1、Review-2、部署或任何实盘/网络操作。
