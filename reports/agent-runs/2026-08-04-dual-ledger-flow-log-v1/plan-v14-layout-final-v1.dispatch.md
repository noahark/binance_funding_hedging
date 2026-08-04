Identity:
- task_id: `plan-v14-layout-final-v1`
- target_role: `Planner`
- target_model: `opus5`
- provider: `anthropic`
- status_revision: `18`
- required_skill: `agents/skills/software-architect.md`

Goal

Human 2026-08-04 已目视验收最终前端布局（tab-layout v2 + 元数据卡片微调），实现已提交（`5613c4e`）。把设计定稿从 **v1.3 升到 v1.4**，让设计的 UI 布局描述与实际实现一致（v1.3 的「独立整页视图」已被 Human 否决并改为最终形态）。**不写业务代码。**

**v1.4 需要更新的内容**（在 v1.3 基础上）：

1. **§11.1/§11.2 按钮与导航**：`#btn-flow-log` 的职责由「切换到流水日志独立页」修正为「切换 `#market-view` 内的流水日志看板」；**新增**「费率行情」看板按钮 `#btn-market-board`（`role=tab`，默认 `aria-selected=true`），与 `#btn-flow-log` 在私有账户面板 `.panel-actions` 内**紧邻并列**构成页内双看板 tab；**移除**侧栏 `#nav-flow-log`（侧栏恢复费率行情 / 借币任务 / 开单任务三项；费率行情菜单是费率行情页的唯一侧栏入口，激活态不随看板切换变化）。
2. **§13.7 布局形态**：流水日志看板是 `#market-view` **内部**的第二看板（`setMarketBoard` 同页切换，不隐藏整页/侧栏）；新增「元数据卡片」行——「本次新增」与「今日累计」两卡片**左右并排**（`.flow-log-meta-row` 两列 grid），窄屏（≤900px）上下堆叠。
3. **轮询语义**（§13.7/§15.1 指针）：60 秒轮询随「流水日志看板激活」进出（激活期间恰好一个、切回费率行情看板或离开费率行情页 `clearInterval`）。
4. **受影响章节**：§13.2 如有布局引用同步；§10 修订记录追加 v1.4 行（Human 2026-08-04 最终验收：panel-actions 双按钮 tab + 侧栏三项 + market-view 内第二看板 + 元数据卡片左右排，实现提交 `5613c4e`）。草案 §1–§10 原文仍不得改写。
5. **不变**：v1.3 的接口契约/数据语义章节（§13.1–§13.6、§14、§15）一字不动——本轮只改 UI 布局描述。

Allowed Files

- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（v1.4：§11/§13.2/§13.7/§15.1 受影响处 + §10 修订记录行）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-v14-layout-final-v1.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`（2026-08-04 21:50 CST）：PASS(absent)；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`（仅可将本任务 `current_task.state` 从 `dispatched` 改为 `reported`；不得改动任何其他字段）

Inputs

- `AGENTS.md`
- 本 dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`
- `agents/roles.md` 的 Planner 章节与 Task Handoff Evidence Contract 章节
- `agents/skills/software-architect.md`
- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（v1.3，修订对象）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-flow-log-tab-layout-v2.handoff.md` 与 `frontend/index.html`（最终实现，v1.4 的布局权威）

Acceptance Checks

1. 设计 v1.4 的布局描述与实际实现（`frontend/index.html` 提交 `5613c4e`）逐项一致：panel-actions 双按钮、侧栏三项、market-view 内第二看板、元数据卡片左右排（窄屏堆叠）、轮询随看板。
2. 契约/数据语义章节未动；草案 §1–§10 未改写；§10 修订记录追加 v1.4 行。
3. 交接件与回执：handoff（Source Report + Human Brief）+ 合规 `[TASK_RESULT v2]` + 三行中文交接；`delivery_sha` 写 `none`（文档修订留工作树）；status 仅改本任务状态。
4. 未写业务代码、未启动终端、未执行实盘/网络/凭据操作。

Stop

只在 Allowed Files 内修改；不得触碰 `backend/`、`frontend/` 业务代码。完成设计 v1.4 后停止，等待 Human 转交 Bookkeeper 封存并路由统一评审（A+B+C，review-1 避 `zhipu_glm`+`xai`，review-2 避两实现作者）。
