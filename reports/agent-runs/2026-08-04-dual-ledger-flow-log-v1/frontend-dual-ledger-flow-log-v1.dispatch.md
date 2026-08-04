Identity:
- task_id: `frontend-dual-ledger-flow-log-v1`
- target_role: `Implementer`
- target_model: `kimi`
- provider: `moonshot`
- status_revision: `4`
- required_skill: `agents/skills/senior-developer.md`

Goal

交付两件前端改动（三任务串行中的第三份），按 `docs/planning/2026-08-04-dual-ledger-flow-log-design.md` §11、§13.2、§13.7 执行。

**需求 1 — 按钮调整（Human 已拍板语义）。** 把 `#btn-privacy`（显示金额/隐藏金额，现位于 `frontend/index.html:1127-1133` 私有账户面板的 `.panel-actions`）移入 `.panel-title` 内、紧邻 `<h2>私有账户</h2>` 右侧同一行；因 `.panel-title` 现为 `display: grid`（标题上、副标题下），须在其内新增一个只服务此处的横向行容器 `.panel-title-row { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }`。原 `.panel-actions` 位置改放新按钮 `#btn-flow-log`（文案「流水日志」，带 `aria-expanded` 与 `aria-controls="flow-log-panel"`）。`#btn-privacy` 的 id、`aria-pressed`、`#privacy-label`、`#privacy-icon-path`、点击行为与 localStorage 键 `funding_hedging_privacy_hidden` **一律不变**——本需求只搬位置；`#private-pm-source-time` 仍在 `.panel-title` 内、仍在标题下方。既有 self-check 以 id 定位、不断言父元素，移动**不得**使其失效。

**需求 2 — 双栏流水日志面板。** 新增 `#flow-log-panel`，位置在 `#private-panel` 之后、市场表面板之前，**仍在 `#market-view` 内**，默认 `display:none`；点 `#btn-flow-log` 展开/收起并同步 `aria-expanded`，首次展开自动 `GET` 一次（近 7 天）。数据来自**后端本地账本**（不是每次打开都打币安）：`GET /api/private-ledger/flow-log?start=<ms>&end=<ms>`；手动刷新按 `POST /api/private-ledger/refresh` 后重新 `GET`。左栏「借币利息流水」渲染 `interest`，右栏「合约资金流水」渲染 `um_income`（**标题不得**写成「资金费率日志」——同接口含手续费/划转/盈亏）。响应形状是设计 §13.2 的冻结契约，前端只消费、不重塑。

以下为最易出错、必须逐条对照的展示硬规则：

1. **`coverage` 是诚实性护栏，不是装饰**：常驻状态条须显示「本地数据：<coverage.start> 起 · 上次刷新：<last_run 时间>（成功／失败短码中文）· 每小时整点后 1 分钟自动刷新」；`coverage.pending_tail_ms > 0` 时常驻附注「最近 X 分钟的流水尚未刷新」。「覆盖不完整」按设计 §13.7 分**三种情形**渲染：(a) 起点截断（`window.start < coverage.start`，或 `gaps` 含起点侧空洞）→「本地数据只到 <日期>，更早的没有」；(b) 区间空洞（`coverage.gaps` 与查询窗口相交）→「<区间> 的流水存在未覆盖空洞，未拉取的数据不会被计入」；(c) `coverage.complete=false` 且以上均无 → 按空态判定。空态（没数据是因为没开通道／真没流水）按设计 §13.2 规则 14 的五行判定表（含 `scheduler_enabled`）渲染；`scheduler_enabled=false` 时显示「私有通道未启用，不会自动刷新」（本地有历史数据则照常展示历史）。**空结果绝不允许被呈现为「这段时间没有流水」。** 〔Bookkeeper pre-dispatch correction 2026-08-04：按设计 §13.7 待办框补齐 F4 覆盖文案分情形渲染，不改变本 packet 文件边界与交付范围〕
2. **增量区块必须自解释**：标题写死基准时刻（「自 <baseline 时刻> 以来新增」）。左栏显示按币种的新增利息；右栏显示按（类型，币种）的新增资金费/手续费，**再加**资金费按合约的排行。`delta.complete=false` 时改显「统计基准建立中」并**不显示数字**。
3. **三个数字口径不同，必须各自标注**：「本次新增」按**入库时间**、「今日累计」按**发生时间**（北京时间当日）、「区间累计」按当前时间窗；不得混用或相加。
4. **不排序、不重算汇总、不做二次截断**：后端返回顺序即展示顺序；汇总用后端的 `summary_*` / `delta` / `today`；`row_limit_applied=true` 时显示「共 N 条，显示最近 500 条」（`row_count` 是全量条数）。
5. **金额遮蔽复用 `state.privacyHidden`**：隐藏态下利息、本金、`income`、所有汇总与增量一律 `****`；时间、类型、币种、`symbol` 不遮蔽。
6. **右栏类型筛选纯前端**：`FUNDING_FEE`、`COMMISSION` 默认勾选，`REALIZED_PNL`、`TRANSFER`、其他默认不勾；**切换勾选不得发起任何请求**。资金费行 `income > 0` 文案「收取」、`< 0`「支付」。
7. **时间窗**：`近7天` / `近30天` / `自定义`（起止日期）；自定义**不受 30 天限制**（读的是本地库）。
8. **定时器**：面板展开期间**允许且仅允许一个**流水日志专用 60 秒轮询定时器（纯本地读），**收起时必须 `clearInterval`**；除此之外不得新增任何定时器。
9. **时间一律 `formatBeijing(ms)`**（既有函数，入参就是 epoch ms）；`type` 与 `incomeType` 中文文案沿用设计 §3.1 / §3.2 两张对照表。
10. 加载中禁用预设与刷新按钮、栏内 skeleton，且**保留上一次成功数据**不清空；`POST` 得到 `429` 时显示「正在刷新，请稍候」。窄屏（≤900px）双栏改上下堆叠单列。

新 DOM id 必须与设计 §13.7 冻结的集合完全一致（`btn-flow-log`、`flow-log-panel`、`flow-log-status-bar`、`flow-log-coverage-note`、`flow-log-range-7d`、`flow-log-range-30d`、`flow-log-range-custom`、`flow-log-custom-start`、`flow-log-custom-end`、`flow-log-custom-apply`、`flow-log-refresh`、`flow-log-delta`、`flow-log-delta-interest`、`flow-log-delta-income`、`flow-log-delta-symbols`、`flow-log-today`、`flow-log-filters`、`flow-log-filter-funding`、`flow-log-filter-commission`、`flow-log-filter-realized`、`flow-log-filter-transfer`、`flow-log-filter-other`、`flow-log-interest-status`、`flow-log-interest-summary`、`flow-log-interest-body`、`flow-log-income-status`、`flow-log-income-summary`、`flow-log-income-body`），并在 `frontend/self-check.js` 的 id 列表中逐个注册，否则 `eval(script)` 会因未 mock 元素抛错。

不改后端、不改任何既有端点调用、不新增视图切换（不动 `setActiveView`）、不改市场表/借币/开单页行为、浏览器不签名不直连币安、不做下单/借还/划转/gate/凭证/部署/实盘操作。

Allowed Files

- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-dual-ledger-flow-log-v1.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`（2026-08-04 12:55 CST）：PASS(absent)；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-dual-ledger-flow-log-v1.selfcheck.txt`（self-check 原始输出）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`（仅可将本任务 `current_task.state` 从 `dispatched` 改为 `reported`；不得改动任何其他字段）

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/frontend-dual-ledger-flow-log-v1.dispatch.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`
- `agents/roles.md` 的 Implementer 章节与 Task Handoff Evidence Contract 章节
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（§3.1/§3.2 文案表、§11、§12、§13.2、§13.4、§13.7、§15.4）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-schedule-api-v1.handoff.md`（后端实际交付的响应形状）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/plan-dual-ledger-flow-log-v1.handoff.md`
- `frontend/index.html`、`frontend/self-check.js`

Acceptance Checks

1. 需求 1 落位正确：`#btn-privacy` 位于 `.panel-title` 内标题右侧同一行，`#btn-flow-log` 位于原 `.panel-actions`；`#btn-privacy` 的 id/`aria-pressed`/label/icon/点击行为/localStorage 键与 `#private-pm-source-time` 位置全部未变；既有隐私开关相关 self-check 断言不因移动失效。
2. 常驻状态条与覆盖提示：显示本地数据起点、上次刷新时间与成功/失败中文；「覆盖不完整」按 §13.7 分起点截断 / 区间空洞 / pending_tail 三种情形渲染（引用 §13.2 规则 7 与 §13.7 文案行）；空态按 §13.2 规则 14 判定表（含 `scheduler_enabled`）区分「私有通道未启用」与「真无流水」；空列表与「没拉到」在文案上可区分。
3. 增量区块：标题含基准时刻；左栏按币种、右栏按（类型，币种）、并有资金费按合约的排行；`delta.complete=false` 时显示「统计基准建立中」且无数字；「本次新增 / 今日累计 / 区间累计」三者各自标注口径。
4. 展示纪律：前端不排序、不重算汇总、不二次截断；`row_limit_applied=true` 时提示全量条数；两栏渲染互不影响。
5. 交互边界：首次展开发一次 `GET` 且窗口差值为 7 天；切 `近30天` / 应用自定义 / 点刷新各自只发应发的请求（刷新是先 `POST` 后 `GET`）；**类型筛选切换零请求**；加载中按钮禁用且不清空上次成功数据；`429` 有专门文案。
6. 定时器生命周期：展开时恰好新增一个 60 秒轮询定时器，收起时被 `clearInterval`；全程无其它新增定时器。
7. 隐私遮蔽：`state.privacyHidden` 为真时两栏所有金额、汇总与增量为 `****`，时间/类型/币种/`symbol` 仍可见；切换后立即重渲染。
8. 新增 self-check 断言覆盖上述 1–7，且以自带 fetch mock 复刻设计 §13.2 的响应形状；离线运行 `node frontend/self-check.js` 全绿，原始输出保存到 Allowed Files 中的 `.selfcheck.txt`；不启动服务、不访问网络、不读取凭据、不做实盘操作。

Stop

只在 Allowed Files 内修改。创建 handoff 后用其 Human Brief 生成合规 `[TASK_RESULT v2]`；将本任务状态标为 `reported`。在一个 delivery commit 中提交允许的代码、测试输出、status 与 handoff；handoff 的 `delivery_sha` 写 `pending`。不得自行启动 Reviewer、Bookkeeper 或后端任务，不得合并、部署或执行任何实盘/网络/凭据/下单操作。
