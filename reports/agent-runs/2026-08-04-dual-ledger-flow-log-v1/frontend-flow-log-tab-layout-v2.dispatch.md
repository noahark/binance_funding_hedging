Identity:
- task_id: `frontend-flow-log-tab-layout-v2`
- target_role: `Implementer`
- target_model: `grok`
- provider: `xai`
- status_revision: `15`
- required_skill: `agents/skills/senior-developer.md`

Goal

v1 版 tab 布局（`frontend-flow-log-tab-layout-v1`）把「费率行情 | 流水日志」两个按钮放到了「排序基准: 日净收益优先」旁的 `.badge-row`，被 Human 验收为**不合格并已回退**（`git checkout f23368b -- frontend/index.html frontend/self-check.js`；当前工作树 = 任务 C 的合格交付）。本任务按 Human 重新说明的意图实现布局，**代码起点 = 任务 C 交付（f23368b 的 `frontend/index.html` 与 `frontend/self-check.js`），不得在 v1 的错误实现上改**。

**Human 的原始意图（2026-08-04 重述，已澄清）**：

1. **页内双看板按钮的位置 = 私有账户面板右上角（`.panel-actions`），不是顶部 `.badge-row`**。「第一个设计出来的流水日志按钮」指私有账户面板 `.panel-actions` 内的 `#btn-flow-log`。把**新增的「费率行情」按钮放到 `#btn-flow-log` 旁边**（同一 `.panel-actions` 内、紧邻并列），两个按钮构成页内双看板切换：点「费率行情」显示费率行情看板（私有账户面板 + 市场表，默认），点「流水日志」显示流水日志看板（`#flow-log-*` 内容）。激活中的按钮有高亮/`aria-current`。
2. **移除侧栏「流水日志」主菜单**：删除 `#nav-flow-log` 侧栏入口及其注册/逻辑，侧栏恢复为费率行情 / 借币任务 / 开单任务三个菜单（与 Human「隐藏掉流水日志在左侧菜单栏…同级的主菜单栏」一致）。费率行情菜单（`#nav-market`）保持为费率行情页的唯一侧栏入口，激活态不因看板切换变化。
3. **流水日志内容就在费率行情页内展示**：`#flow-log-view`（或等价容器）不再是独立整页视图（不再走 `setActiveView('flow-log')` 隐藏整个 `#market-view`），而是 `#market-view` **内部**的第二个看板容器；看板切换只切换 `#market-view` 内的内容区，侧栏与页面骨架保持不变。
4. `#btn-privacy`（显示金额，位于 `.panel-title` 内）位置不变；`#btn-flow-log` 保留在 `.panel-actions` 并承担「切到流水日志看板」职责。

**保留清单（任务 C 的功能硬规则，零回退）**：真实 `GET /api/private-ledger/flow-log` + `POST /refresh` 数据源（同源白名单、零 Binance 直连）；默认最新 20 条与三数字文案；右栏类型筛选零请求；隐私遮蔽 `state.privacyHidden`；护栏三情形（起点截断 / 区间空洞 / 空态判定表含 `scheduler_enabled`）+ `pending_tail_ms` 附注；「本次新增/今日累计/区间累计」三口径标注；时间窗 `近7天/近30天/自定义`（请求带参）；`formatBeijing(ms)`；§3.1/§3.2 中文文案；窄屏（≤900px）双栏堆叠；§13.7 冻结 DOM id 集合（`flow-log-*` 全部保留，仅容器层级可随「market-view 内看板」调整）。

**轮询生命周期**：流水日志**看板激活**期间恰好一个 60 秒轮询（仅本地 `GET`）；切回「费率行情」看板或离开费率行情页时 `clearInterval`；不得叠加其他定时器。

**self-check**：更新为双看板按钮断言（默认费率行情看板、点「流水日志」发一次 GET、点「费率行情」切回且轮询清理、`#nav-flow-log` 已移除、功能断言全部保留）；fetch mock 覆盖 `GET flow-log` / `POST refresh`。

不改后端、不改契约、不改既有端点调用、不启动服务、不发真实请求、**不得触发真实 `POST /refresh`**（联调与真实拉取由 Human 之后单独主持并授权）、不做下单/借还/划转/gate/凭证/部署/实盘操作。

风险等级：**LOW_RISK**（`AGENTS.md` §8 记录理由：纯前端布局/导航修正，功能层为已获 Human 认可的 C 交付，不改后端与契约、无网络资金动作；v1 不合格源于 packet 表述缺陷，不递增 `rework_count`）。交付后 Human 目视确认，随后设计落 v1.4 并进入前后端联调与统一评审（A+B+C）。

Allowed Files

- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-flow-log-tab-layout-v2.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`（2026-08-04 21:09 CST）：PASS(absent)；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-flow-log-tab-layout-v2.selfcheck.txt`（self-check 原始输出）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`（仅可将本任务 `current_task.state` 从 `dispatched` 改为 `reported`；不得改动任何其他字段）

Inputs

- `AGENTS.md`
- 本 dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`（Human 布局反馈与回退记录）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`
- `agents/roles.md` 的 Implementer 章节与 Task Handoff Evidence Contract 章节
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-flow-log-tab-layout-v1.handoff.md`（**必读**：v1 不合格原因与回退事实，避免重犯——按钮位置错误、侧栏未移除）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-dual-ledger-flow-log-v1.handoff.md`（任务 C 交付，代码起点）
- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（v1.3 §11/§13.2/§13.7——本轮布局以本 dispatch 为准，设计 v1.4 待 Human 确认后落定）
- `frontend/index.html`、`frontend/self-check.js`（当前为 f23368b = 任务 C 交付）

Acceptance Checks

1. 按钮位置正确：新增「费率行情」按钮在私有账户面板 `.panel-actions` 内、与 `#btn-flow-log` 紧邻并列（**不在** `.badge-row` / 排序基准旁）；两按钮互斥高亮/`aria-current`；默认激活「费率行情」。
2. 侧栏已移除：`#nav-flow-log` 及其注册/逻辑删除；侧栏仅费率行情 / 借币任务 / 开单任务；`#nav-market` 激活态不随看板切换变化。
3. 同页双看板：流水日志内容在 `#market-view` 内展示；看板切换不隐藏整页/侧栏、不走整页视图切换；切回费率行情看板恢复私有账户面板 + 市场表。
4. 功能硬规则零回退（对照任务 C 的 self-check 断言逐条保留，仅布局相关调整）。
5. 轮询生命周期：流水日志看板激活期间恰好一个 60 秒轮询；切走 `clearInterval`；无其他新增定时器。
6. `node frontend/self-check.js` 全绿（含双按钮/侧栏移除/看板切换断言），原始输出存 `.selfcheck.txt`；零网络真实请求。
7. 边界未越：未改后端/契约/既有端点调用、未启动服务、未触发真实 POST refresh、未做实盘操作。
8. 交接件与回执：handoff（Source Report + Human Brief）+ 合规 `[TASK_RESULT v2]` + 三行中文交接；`delivery_sha` 写 `none`（或 `pending` 若被授予提交权）；status 仅改本任务状态。

Stop

只在 Allowed Files 内修改；代码起点必须是 f23368b（任务 C 交付），不得基于 v1 的错误实现。创建 handoff 后用其 Human Brief 生成合规 `[TASK_RESULT v2]`；将本任务状态标为 `reported`。不得自行启动 Reviewer/Bookkeeper/后端任务，不得合并、部署或执行任何实盘/网络/凭据/下单操作。完成后停止，等待 Human 目视确认。
