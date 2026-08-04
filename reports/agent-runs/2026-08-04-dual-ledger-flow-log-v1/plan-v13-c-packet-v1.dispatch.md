Identity:
- task_id: `plan-v13-c-packet-v1`
- target_role: `Planner`
- target_model: `opus5`
- provider: `anthropic`
- status_revision: `12`
- required_skill: `agents/skills/software-architect.md`

Goal

按 Human 2026-08-04 已拍板的两个决策与任务 B 已冻结的接口契约，为 C（前端接真实数据）做路由前权威准备。**不写业务代码。**

**1. 设计定稿 v1.2 → v1.3**（`docs/planning/2026-08-04-dual-ledger-flow-log-design.md`）：
- §13.7 UI 布局：流水日志由「嵌入 `#market-view` 内、`#private-panel` 之后」**改为独立展示页**——侧栏导航新增「流水日志」入口（`#nav-flow-log`），点击切换到干净独立视图（`#flow-log-view`），与「费率行情」/借币任务/开单任务互斥切换（复用既有 `setActiveView` 机制）；私有账户面板 `.panel-actions` 的 `#btn-flow-log` 点击切换到该独立页。
- 明细展示条数：两栏**默认展示最新 20 条**（后端按时间倒序返回，前端取前 20 并标注「显示最近 20 条」；`row_count` 为全量、`row_limit_applied` 语义保留）。
- 受影响章节同步（§11 按钮行为、§13.2 如有布局/条数相关描述、§15 定时器轮询语义——真实版在独立页视图激活期间允许 60 秒轮询 GET、切走 `clearInterval`，fake 版无轮询的说明改为真实版约束）；§10 修订记录追加 v1.3 行（Human 2026-08-04 决策：独立页 + 默认 20 条）。草案 §1–§10 原文仍不得改写。

**2. 重写 C packet**（`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/frontend-dual-ledger-flow-log-v1.dispatch.md`）为**真实数据版**（当前版本仍是「嵌入面板 + 展开/收起」的旧布局，与 Human 决策和 fake v2 实现不符；保留 Bookkeeper 之前的覆盖文案 correction，并入新布局）：
- 基础 = 已验收的 fake v2 独立页（`#nav-flow-log` / `#flow-log-view` / `setActiveView('flow-log')` / 默认 20 条 / 双栏 / 右栏筛选 / 隐私遮蔽 / 窄屏堆叠 / §13.7 DOM id 集合全部保留）。
- 数据源：内置假数据 **替换为真实后端**——`GET /api/private-ledger/flow-log?start=<ms>&end=<ms>`（纯读本地库、零上游 I/O），手动刷新 `POST /api/private-ledger/refresh` 后重新 GET；**移除「演示数据（FAKE）」横幅**，改为设计 §13.7 的覆盖状态条与三态判定表（§13.2 规则 14，含 `scheduler_enabled`）。
- 轮询：流水日志视图激活期间**恰好一个** 60 秒轮询 GET（纯本地读）；切走视图 `clearInterval`；不得新增其他定时器。
- 错误与空态：429「正在刷新，请稍候」、409/503 按判定表（`scheduler_enabled=false` →「私有通道未启用，不会自动刷新」）、空态按 §13.2 规则 13/14；**空结果绝不允许呈现为「这段时间没有流水」**。
- 响应消费以任务 B 契约 v0.12 为准（`docs/api/public-market-contract.md`：`scheduler_enabled`、`last_run`、`coverage.by_source/gaps/pending_tail_ms/complete`、`delta`、`today`、两栏 rows/summary、`row_limit_applied`、ID 字符串、缺失 null）。
- self-check：更新为真实版断言（fetch mock 复刻 v0.12 形状：非空/空态/429/409/503、轮询生命周期、20 条、隐私、筛选零请求）。

Allowed Files

- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（v1.3：§11/§13.2/§13.7/§15 受影响处 + §10 修订记录行）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/frontend-dual-ledger-flow-log-v1.dispatch.md`（整份重写为真实数据版）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-v13-c-packet-v1.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`（2026-08-04 20:15 CST）：PASS(absent)；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`（仅可将本任务 `current_task.state` 从 `dispatched` 改为 `reported`；不得改动任何其他字段）

Inputs

- `AGENTS.md`
- 本 dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`（Human 决策与流程调整记录）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`
- `agents/roles.md` 的 Planner 章节与 Task Handoff Evidence Contract 章节
- `agents/skills/software-architect.md`
- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（v1.2，修订对象）
- `docs/api/public-market-contract.md`（v0.12 amendment，C 的接口权威）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-schedule-api-v1.handoff.md`（B 交付事实与 GET/POST 行为、空态）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-fake-flow-log-v2.handoff.md` 与 `frontend/index.html`（fake v2 独立页实现，C 的基础）
- `frontend/self-check.js`

Acceptance Checks

1. 设计 v1.3：§13.7 独立页布局 + 默认 20 条 + 轮询语义 + 修订记录行齐备；草案 §1–§10 未改写；受影响章节（§11/§13.2/§15）与 v1.3 一致。
2. C packet 重写后与设计 v1.3、契约 v0.12 三方一致；fake v2 的 DOM id 集合与展示硬规则保留（去掉 FAKE 横幅）；真实数据源、60 秒轮询、错误/空态判定表、self-check 更新要求齐备；文件边界仍为 `frontend/index.html` + `frontend/self-check.js` + evidence。
3. 交接件与回执：handoff（Source Report + Human Brief）+ 合规 `[TASK_RESULT v2]` + 三行中文交接；`delivery_sha` 写 `none`（文档修订留工作树）；status 仅改本任务状态。
4. 未写业务代码、未动 A/B 文件、未启动终端、未执行实盘/网络/凭据操作。

Stop

只在 Allowed Files 内修改；不得触碰 `backend/`、`frontend/` 业务代码与 A/B packet。完成设计 v1.3 与 C packet 重写后停止，等待 Human 转交 Bookkeeper 封存并路由 C（grok 接真实数据）。
