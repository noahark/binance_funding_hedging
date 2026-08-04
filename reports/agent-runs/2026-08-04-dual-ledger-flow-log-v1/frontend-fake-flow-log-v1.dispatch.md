Identity:
- task_id: `frontend-fake-flow-log-v1`
- target_role: `Implementer`
- target_model: `grok`
- provider: `xai`
- status_revision: `7`
- required_skill: `agents/skills/senior-developer.md`

Goal

按 Human 2026-08-04 决定（暂停后端任务 A，前端先行、确认后再回真实开发），交付两件前端改动：

**1. 需求 1 — 按钮调整（真实生产改动）**，按设计 `docs/planning/2026-08-04-dual-ledger-flow-log-design.md` §11 执行：
- 把 `#btn-privacy`（显示金额/隐藏金额，现位于 `frontend/index.html:1127-1133` 私有账户面板 `.panel-actions`）移入 `.panel-title` 内、紧邻 `<h2>私有账户</h2>` 右侧同一行；因 `.panel-title` 现为 `display: grid`，在其内新增横向行容器 `.panel-title-row { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }`（仅此一处使用）。
- 原 `.panel-actions` 位置改放新按钮 `#btn-flow-log`（文案「流水日志」，带 `aria-expanded` 与 `aria-controls="flow-log-panel"`）。
- `#btn-privacy` 的 id、`aria-pressed`、`#privacy-label`、`#privacy-icon-path`、点击行为、localStorage 键 `funding_hedging_privacy_hidden` **一律不变**；`#private-pm-source-time` 仍在 `.panel-title` 内、仍在标题下方。既有 self-check 以 id 定位、不断言父元素，移动不得使其失效。

**2. 需求 2 — 流水日志面板 FAKE 原型（纯假数据 UI 探针）**：
- 新增 `#flow-log-panel`，位置在 `#private-panel` 之后、市场表面板之前，仍在 `#market-view` 内，默认 `display:none`；点 `#btn-flow-log` 展开/收起并同步 `aria-expanded`。
- 数据用**内置 JS 假数据常量**直接渲染（**不 fetch、不连币安、无网络、不接后端路由**——后端任务 A/B 已暂停）。假数据形状必须严格按设计 §13.2 冻结契约 `private-ledger/v2` 响应（含 `scheduler_enabled`、`last_run`、`coverage` 的 `by_source`/`gaps`/`pending_tail_ms`/`complete`、`delta`、`today`、`interest`/`um_income` 两栏 rows 与 summary、`row_limit_applied` 等字段），这样 Human 确认后接真实后端时前端改动最小。面板内必须有醒目常驻标识「演示数据（FAKE）——非真实账户流水」，防止假数据被误读为真实资金。
- 双栏：左栏「借币利息流水」（`interest`），右栏「合约资金流水」（`um_income`，**标题不得**写成「资金费率日志」——同接口含手续费/划转/盈亏）。

以下为必须逐条对照的展示硬规则（与设计 §13.7 一致）：

1. **`coverage` 是诚实性护栏**：常驻状态条显示「本地数据：<coverage.start> 起 · 上次刷新：<last_run 时间>（成功／失败短码中文）· 每小时整点后 1 分钟自动刷新」；`pending_tail_ms > 0` 时常驻附注「最近 X 分钟的流水尚未刷新」。覆盖不完整分三种情形渲染（按设计 §13.7）：(a) 起点截断 →「本地数据只到 <日期>，更早的没有」；(b) 区间空洞（`gaps` 与窗口相交）→「<区间> 的流水存在未覆盖空洞」；(c) `complete=false` 且以上均无 → 空态。空态按 §13.2 规则 14 判定表（含 `scheduler_enabled`）区分「私有通道未启用」与「真无流水」。**空结果绝不允许被呈现为「这段时间没有流水」。**（fake 阶段至少演示一种非空态 + 一种「未刷新/空洞」态，便于 Human 看到护栏文案。）
2. **增量区块**：标题写死基准时刻（「自 <baseline 时刻> 以来新增」）；左栏按币种、右栏按（类型，币种）+ 资金费按合约排行；`delta.complete=false` 时显示「统计基准建立中」且不显示数字。
3. **三个口径各自标注**：「本次新增」按入库时间、「今日累计」按发生时间（北京时间当日）、「区间累计」按当前时间窗；不得混用或相加。
4. **不排序、不重算汇总、不做二次截断**：假数据按后端应返回的顺序（两栏时间倒序）直接渲染；汇总用假数据里的 `summary_*`/`delta`/`today`。
5. **金额遮蔽复用 `state.privacyHidden`**：隐藏态下利息、本金、`income`、所有汇总与增量一律 `****`；时间、类型、币种、`symbol` 不遮蔽。
6. **右栏类型筛选纯前端**：`FUNDING_FEE`、`COMMISSION` 默认勾选，`REALIZED_PNL`、`TRANSFER`、其他默认不勾；切换勾选不得发起任何请求。资金费行 `income > 0` 文案「收取」、`< 0`「支付」。
7. **时间窗控件**：`近7天` / `近30天` / `自定义`（起止日期）三档（fake 阶段切换仅过滤假数据或仅切换展示，不请求网络）。
8. **定时器**：fake 阶段不启动任何轮询定时器（无真实刷新）；面板收起时不残留任何定时器。
9. **时间一律 `formatBeijing(ms)`**；`type` 与 `incomeType` 中文文案沿用设计 §3.1 / §3.2 对照表。
10. 加载/展开即时渲染（本地数据无需 skeleton，但保留代码注释说明真实版此处应有 skeleton）；窄屏（≤900px）双栏上下堆叠单列。

新 DOM id 必须与设计 §13.7 冻结集合完全一致（`btn-flow-log`、`flow-log-panel`、`flow-log-status-bar`、`flow-log-coverage-note`、`flow-log-range-7d`、`flow-log-range-30d`、`flow-log-range-custom`、`flow-log-custom-start`、`flow-log-custom-end`、`flow-log-custom-apply`、`flow-log-refresh`、`flow-log-delta`、`flow-log-delta-interest`、`flow-log-delta-income`、`flow-log-delta-symbols`、`flow-log-today`、`flow-log-filters`、`flow-log-filter-funding`、`flow-log-filter-commission`、`flow-log-filter-realized`、`flow-log-filter-transfer`、`flow-log-filter-other`、`flow-log-interest-status`、`flow-log-interest-summary`、`flow-log-interest-body`、`flow-log-income-status`、`flow-log-income-summary`、`flow-log-income-body`），并在 `frontend/self-check.js` 的 id 列表中逐个注册，否则 `eval(script)` 会因未 mock 元素抛错。

不改后端、不改任何既有端点调用、不新增视图切换（不动 `setActiveView`）、不改市场表/借币/开单页行为、浏览器不签名不直连币安、不启动服务、不访问网络、不做下单/借还/划转/gate/凭证/部署/实盘操作。

风险等级：**LOW_RISK**（`AGENTS.md` §8 记录理由：纯前端 UI 探针，假数据无真实资金/PnL 语义，不改后端与契约、无网络与资金动作；需求 1 按钮移动为位置性改动且既有 self-check 断言不失效）。实现后由一次独立 final review（跨 provider，与 xai 不同）加 Human 目视确认。

Allowed Files

- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-fake-flow-log-v1.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`（2026-08-04 15:06 CST）：PASS(absent)；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-fake-flow-log-v1.selfcheck.txt`（self-check 原始输出）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`（仅可将本任务 `current_task.state` 从 `dispatched` 改为 `reported`；不得改动任何其他字段）

Inputs

- `AGENTS.md`
- 本 dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`
- `agents/roles.md` 的 Implementer 章节与 Task Handoff Evidence Contract 章节
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（§3.1/§3.2 文案表、§11 按钮落点、§13.2 冻结响应形状与规则 7/10/13/14、§13.7 文案行与 DOM id 集合）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-review-r2-dual-ledger-flow-log-v1.handoff.md`（N1–N10 观察项，fake 版只需考虑与展示相关的 N1/N5/N6）
- `frontend/index.html`、`frontend/self-check.js`

Acceptance Checks

1. 需求 1 落位正确：`#btn-privacy` 位于 `.panel-title` 内标题右侧同一行，`#btn-flow-log` 位于原 `.panel-actions`；`#btn-privacy` 的 id/`aria-pressed`/label/icon/点击行为/localStorage 键与 `#private-pm-source-time` 位置全部未变；既有隐私开关相关 self-check 断言不因移动失效。
2. 面板与交互：`#flow-log-panel` 在 `#private-panel` 之后、市场表之前，默认隐藏；点 `#btn-flow-log` 展开/收起且 `aria-expanded` 同步；面板内有醒目「演示数据（FAKE）」标识；无任何网络请求（可静态 grep 确认无 `fetch(` 到 `/api/private-ledger/`、无 binance 直连）。
3. 展示纪律：假数据形状含设计 §13.2 关键字段（`scheduler_enabled`、`last_run`、`coverage.by_source`/`gaps`/`pending_tail_ms`/`complete`、`delta`、两栏 rows 与 summary）；两栏时间倒序；右栏类型筛选纯前端零请求；「本次新增/今日累计/区间累计」口径各自标注；`delta.complete=false` 时不显示数字。
4. 护栏文案：至少演示「起点截断」与「pending_tail/未刷新」两种覆盖提示（fake 数据里造一种）；空态与「私有通道未启用」可区分；无「空结果呈现为没有流水」的文案。
5. 隐私遮蔽：`state.privacyHidden` 为真时面板内所有金额/汇总/增量为 `****`，时间/类型/币种/`symbol` 仍可见；切换后立即重渲染。
6. 新增 self-check 断言覆盖上述 1–5，且以自带 fetch mock 或直接构造假数据复刻设计 §13.2 响应形状；离线运行 `node frontend/self-check.js` 全绿，原始输出保存到 Allowed Files 中的 `.selfcheck.txt`；不启动服务、不访问网络、不读取凭据、不做实盘操作。
7. 边界未越：未改后端、未改任何既有端点调用、未动 `setActiveView`、未改市场表/借币/开单页行为、未新增除面板展开/收起外的行为或定时器。
8. 交接件与回执：创建 handoff（Source Report + Human Brief），控制台回执含合规 `[TASK_RESULT v2]` 与三行中文交接；`delivery_sha` 写 `pending`（若你不提交交付，则写 `none` 并说明产物留在工作树）；status 仅将本任务状态改为 `reported`。

Stop

只在 Allowed Files 内修改。创建 handoff 后用其 Human Brief 生成合规 `[TASK_RESULT v2]`；将本任务状态标为 `reported`。若被授予提交权，在一个 delivery commit 中提交允许的文件、self-check 输出、status 与 handoff。不得自行启动 Reviewer/Bookkeeper/后端任务，不得合并、部署或执行任何实盘/网络/凭据/下单操作。完成后停止，等待 Human 目视确认 fake 原型；确认后才恢复后端真实开发（A → B → C）。
