Identity:
- task_id: `frontend-dual-ledger-flow-log-v1`
- target_role: `Implementer`
- target_model: `grok`（provider identity `xai`；`agents/roles.md` 的 Grok 实现例外由 Human 2026-08-04 显式启用，fake v1/v2 亦由同一模型交付）
- provider: `xai`
- status_revision: `13`
- required_skill: `agents/skills/senior-developer.md`

Goal

三任务串行（A→B→C）中的第三份，也是最后一份：**把已验收的 fake 独立页换成真实后端数据**。后端任务 A（本地账本 store/domain）与 B（拉取编排 + 每小时调度 + 两条路由）已交付并封存（`delivery_sha=550f8b7`，31 + 194 测试绿）。本任务**只改前端**，不写任何后端代码。

权威三方（冲突时以设计与契约为准，本 packet 只是把它们展开成可执行要求）：
- 布局与展示：`docs/planning/2026-08-04-dual-ledger-flow-log-design.md` **v1.3** §11、§13.2、§13.7、§15.4；
- 接口形状：`docs/api/public-market-contract.md` **v0.12 amendment**；
- 后端实际行为：`evidence/backend-ledger-schedule-api-v1.handoff.md`。

### 0. 起点：fake v2 的哪些东西必须原样保留

当前 `frontend/index.html` 已经是**独立页版 fake 原型**（Human 已目视验收）。**不要重做布局**，下列全部保留：

- 侧栏入口 `#nav-flow-log`、独立视图 `#flow-log-view`（与 `#market-view` / `#borrow-task-view` / `#hedge-task-view` 平级、默认 `display:none`）、其内的 `#flow-log-panel`；
- `setActiveView('flow-log')` 的互斥切换与 `.active` + `aria-current="page"` 高亮；私有账户面板 `#btn-flow-log` 点击同样只做 `setActiveView('flow-log')`（`aria-controls="flow-log-view"`，**不用** `aria-expanded`）；
- 需求 1 的按钮落位：`#btn-privacy` 在 `.panel-title-row` 内标题右侧，`#privacy-label`/`#privacy-icon-path`/`aria-pressed`/localStorage 键 `funding_hedging_privacy_hidden`/点击行为**一律不变**；`#private-pm-source-time` 仍在 `.panel-title` 内标题下方；
- 设计 §13.7 冻结的全部 DOM id（含 v1.3 新增的 `nav-flow-log`、`flow-log-view`）一个不少、不改名；
- 双栏标题「借币利息流水」/「合约资金流水」（**右栏绝不可命名为「资金费率日志」**）、右栏五个类型筛选框及其默认勾选、两个元数据区块（`#flow-log-delta` / `#flow-log-today`）、时间窗三按钮 + 自定义起止、`#flow-log-refresh`、窄屏 ≤900px 双栏改上下堆叠、金额遮蔽复用 `state.privacyHidden`、**每栏默认展示最新 20 条**。

### 1. 数据源：内置假数据 → 真实后端

1. **读**：`GET /api/private-ledger/flow-log?start=<ms>&end=<ms>`（同源相对路径，**纯读本地库、零上游 I/O**）。
2. **手动刷新**：`#flow-log-refresh` → `POST /api/private-ledger/refresh`（无请求体、无参数），**完成后重新 `GET`**；进行中禁用按钮。
3. 删除 fake 数据面：`buildFlowLogFakePayload()`、模块级 `flowLogFakePayload`、`__appHelpers` 里的 `getFlowLogFakePayload` / `buildFlowLogFakePayload` 两个 seam，改为真实状态（例如 `state.flowLogPayload`）与真实 seam（至少暴露：取当前 payload、触发一次加载、触发一次手动刷新、读轮询 id，供 self-check 驱动；命名自定，但必须够 self-check 断言）。
4. **移除全部 FAKE 痕迹**：`.flow-log-fake-banner` 横幅 DOM 与其 CSS 类、面板副标题「假数据探针（不请求网络）」、刷新按钮文案「刷新（演示）」→「刷新」，以及 `renderFlowLogPanel` 上「不 fetch、不启动定时器」一类已失效的注释。**页面上不得再出现「演示」「FAKE」字样。**
5. 横幅位置改由设计 §13.7 的**常驻状态条**（`#flow-log-status-bar`）与**覆盖提示**（`#flow-log-coverage-note`）承担，按下面第 2 节渲染。

### 2. 展示硬规则（最易出错，逐条对照；括号内是权威出处）

1. **`coverage` 是诚实性护栏，不是装饰**（§13.2 规则 7/14、§13.7）。两件事分开做，不要合成一个 if：
   - **状态条主文案**按 §13.2 规则 14 的五行判定表**顺序取第一个命中的那一条**（只出一条）：① `scheduler_enabled == false` →「私有通道未启用，不会自动刷新」（本地若有历史数据仍照常展示历史）；② `last_run == null` →「尚未刷新过，等待首次自动刷新」；③ 任一栏 `*_status == "error"` →「上次刷新失败：<短码中文>（连续失败 N 次）」；④ `coverage.complete == false` →「本地数据不完整」；⑤ 都不成立且该栏 `row_count == 0` →「该时间窗无记录」。正常态状态条为「本地数据：<coverage.start> 起 · 上次刷新：<时间>（成功）· 每小时整点后 1 分钟自动刷新」。
   - **`coverage.pending_tail_ms > 0` 的附注**（「最近 X 分钟的流水尚未刷新」）是**独立一行附注**，不参与上面的判定表，也**不**代表数据不完整。
   - **覆盖不完整文案**（`#flow-log-coverage-note`）：**只要 `coverage.complete === false` 就必须渲染**，与判定表命中哪一行无关（§13.7「覆盖不完整文案」写的是「必须提示」）。分两种：**(a) 起点截断**（`gaps` 为空且 `window.start_ms < coverage.start_ms`）→「本地数据只到 <coverage.start 日期>，更早的没有」；**(b) 区间空洞**（`gaps` 非空）→ 逐条列出「<gap.start>–<gap.end> 这段没有拉到（<源名>），下面的列表在这段时间内不代表交易所没有流水」（源名：`interest`→借币利息、`income`→合约资金；最多 20 条）。
   - **绝对红线**：`coverage.complete === false` 时，任何位置（状态条、栏状态行、空列表占位）**都不得**出现「该时间窗无记录」「这段时间没有流水」或等价措辞。
2. **增量区块必须自解释**（§15.4、§13.2 规则 11）。`delta.complete === true` 时标题写死基准时刻「自 <formatBeijing(baseline_ms)> 以来新增（按入库时间）」；左栏按 `asset` 的新增利息、右栏按 `(income_type, asset)` 的新增、**再加** `funding_by_symbol` 的资金费按合约排行。`delta.complete === false` 时显示「统计基准建立中」并**一个数字都不显示**（`baseline_ms` 此时为 `null`，不得渲染成 0 或空日期）。
3. **三个口径不同，各自标注、绝不相加**（§15.4）：「本次新增」按**入库时间**、「今日累计」按**发生时间**（北京时间当日）、「区间累计」（`summary_*`）按当前时间窗。
4. **不排序、不重算汇总、不跨币种相加**（§13.2 规则 3/6、§6）：后端返回顺序即展示顺序；所有合计一律用后端的 `summary_*` / `delta` / `today` 字段；**前端不得对金额做任何算术**。`Number()` 只允许用于判断正负号与着色（资金费 `income > 0`→「收取」、`< 0`→「支付」），**不得**用于展示、格式化、比较大小或求和；金额与利率一律**原样字符串**透传。
5. **缺失即 `—`，绝不画 0**（§13.2 规则 4）：`null` / 缺字段渲染为 `—`；`*_total` 为 `null` 且 `unparsed_row_count > 0` 的分组必须显示为「合计不可用（N 行无法解析）」一类文案，**不得**显示部分和或 0。ID（`tx_id` / `tran_id`）是 19 位字符串，**任何情况下都不得 `Number()` 或参与数值运算**。
6. **明细展示条数**（§13.2 规则 8、§13.7）：两栏各取后端返回的**前 20 条**渲染。左栏状态行「显示最近 20 条（共 <row_count> 条）」；右栏因类型筛选是纯前端、取前 20 发生在**筛选之后**，文案「显示最近 20 条（筛选后共 X 条 / 全量 <row_count> 条）」。`row_limit_applied === true` 时两栏都要再追加「后端最多返回 500 条」。**不做「加载更多」。**
7. **右栏类型筛选纯前端、零请求**（§12 决议 1）：`FUNDING_FEE` / `COMMISSION` 默认勾选，`REALIZED_PNL` / `TRANSFER` / 其他默认不勾；勾选变化**不得发起任何请求**，只重渲染右栏，且**不得**改变右栏 `summary_*`（汇总是全类型全量的，与筛选无关，文案要说清）。
8. **时间窗**（§13.7）：`近7天`（默认）/ `近30天` / `自定义`。切换预设或点「应用」各触发**一次** `GET`：预设 `end = Date.now()`、`start = end − 7d/30d`；自定义按**北京日界** `起 T00:00:00+08:00` → `止 T23:59:59+08:00`，日期为空或 `start >= end` 时**不发请求**（本地拦下，不去撞后端 400）。自定义**不受 30 天限制**。
9. **轮询生命周期**（§13.7、§15.1）：进入流水日志视图时立即 `GET` 一次并启动**恰好一个** 60000ms 轮询 `GET`；**离开视图必须 `clearInterval`**；启动前先清掉自己上一个 id（重复进入不得叠加）。**除此之外不得新增任何定时器**，也不得改动既有的市场 60 秒自动刷新、1 秒倒计时、执行状态轮询。**页面初始化（默认 market 视图）不得请求 `private-ledger`。**
10. **加载中与错误**（§13.7、§13.3、§13.4）：加载中栏内 skeleton、禁用时间窗与刷新按钮，且**保留上一次成功数据不清空**。`GET` 失败一律显示错误、**不得**退化成「无流水」：`400 invalid_window`→「时间窗无效」；`503 flow_log_unavailable`→「流水日志服务未启用」；网络/解析失败→「读取失败，请稍后重试」。`POST` 分支：`200` 后重新 `GET`；`429 flow_log_busy`→「正在刷新，请稍候」；`409 private_channel_disabled`→「私有只读通道未启用」；`503`→「流水日志服务未启用」。
11. **隐私遮蔽**（§13.7）：`state.privacyHidden` 为真时，利息、本金、`income`、**所有汇总与增量**一律 `****`；时间、类型、币种、`symbol` 不遮蔽；切换后立即重渲染且**零请求**。
12. **时间一律 `formatBeijing(ms)`**（既有函数，入参 epoch ms）；`type` / `incomeType` 中文文案沿用设计 §3.1 / §3.2 两张对照表；错误短码中文映射沿用 fake v2 的 `FLOW_LOG_ERROR_ZH`（`interest_history_failed` / `um_income_failed` / `rate_limited` / `private_channel_disabled`）。

### 3. 允许触碰 `setActiveView` 的范围

允许且仅允许在 `setActiveView` 的 **`flow-log` 分支**内加载数据与管理轮询，并在**离开** flow-log 时停轮询。`market` / `borrow-tasks` / `hedge-tasks` 三个分支的既有行为（含进入借币视图的默认筛选与三个 load、开单视图的两个 load）**一字不改**。

### 4. self-check 更新（`frontend/self-check.js`）

`node frontend/self-check.js` 必须全绿。注意 mock 的两个硬约束，不处理必然报错：

- **fetch mock 的兜底分支会 `throw new Error('Unexpected fetch URL')`**（`frontend/self-check.js:835`）。必须为 `GET /api/private-ledger/flow-log?...` 与 `POST /api/private-ledger/refresh` 增加可配置 mock 响应（沿用既有风格：模块级响应变量 + `buildFetchResponse`），否则任何 `setActiveView('flow-log')` 都会炸。
- **98b 现有的三处 fake 断言必须反转或删除**，否则必然失败：`frontend/self-check.js:5380`（断言页面含「演示数据（FAKE）」横幅——横幅已删）、`frontend/self-check.js:5387`（断言页面**不得** fetch `private-ledger`——现在必须 fetch，此断言要反转）、`frontend/self-check.js:5423`（调用 `helpers.getFlowLogFakePayload()`——该 seam 已不存在）。

98b 重写为真实版，至少覆盖（可拆多个小节，异步渲染用既有 `await new Promise(r => setTimeout(r, 0))` 模式冲刷）：

1. **id 与布局**：§13.7 冻结 id 全在；`#flow-log-panel` 不在 `#market-view` 内；导航互斥（切 flow-log 隐藏 market、`nav-flow-log` 得到 `aria-current="page"`，切回恢复；borrow/hedge 视图不被破坏）；页面不含「演示」/「FAKE」字样；不含「资金费率日志」。
2. **请求生命周期**：初始化零 `private-ledger` 请求；进入视图**恰好一次** `GET`，URL 前缀正确且 `end - start` ≈ 7 天；离开视图后不再有新 `GET`；`#btn-flow-log` 与 `#nav-flow-log` 都能进入该视图。
3. **轮询**：进入视图后 `intervalCalls` 新增**恰好一个** `delay === 60000` 的 id，离开视图后该 id 落入 `clearedIntervalIds`；重复进入不叠加。**不要断言「全局只有一个 60000 定时器」**——既有市场自动刷新就是 60000ms。
4. **20 条**：mock 返回 > 20 行时两栏各渲染 20 行（数 `<tbody>` 内 `<tr>`），状态行含全量 `row_count`；`row_limit_applied=true` 时含「500」提示。
5. **覆盖与空态**（用不同 mock payload 各跑一次）：(a) 起点截断文案；(b) `gaps` 非空的空洞文案；(c) `complete=true` 且 `row_count=0` →「该时间窗无记录」；(d) **`complete=false` + 空 `rows` 时页面不得出现「该时间窗无记录」/「没有流水」**；(e) `pending_tail_ms > 0` 的独立附注；(f) §13.2 规则 13 的空态 payload（`scheduler_enabled=false`、`last_run=null`、两栏空）逐条命中判定表第 ①/② 行。
6. **增量**：`delta.complete=false` → 「统计基准建立中」且渲染结果中无金额数字；`complete=true` → 标题含 `formatBeijing(baseline_ms)`，三个分组（按币种 / 按类型币种 / 按合约）都渲染。
7. **手动刷新**：点击后 `fetchCallLog` 顺序为先 `POST /api/private-ledger/refresh` 后 `GET /api/private-ledger/flow-log`；`429` / `409` / `503` 各有对应文案且不清空上次成功数据。
8. **零请求断言**：类型筛选切换、隐私开关切换均不新增任何 fetch；隐私隐藏时金额为 `****` 而资产名/时间仍可见。
9. **时间窗**：切 `近30天` 发一次 `GET` 且窗口 ≈30 天；自定义留空或 `start >= end` 时零请求。

原始输出保存到 `evidence/frontend-dual-ledger-flow-log-v1.selfcheck.txt`。

### 5. 红线

不改后端任何文件（`backend/**`）、不改契约文档、不改 A/B 的交付与 evidence；浏览器不签名、不直连币安、不读凭据；**不得启动服务、不得发真实网络请求、不得触发真实的 `POST /api/private-ledger/refresh`**（连币安拉真实数据需 Human 单独授权，前后端联调是本任务之后由 Human 主持的独立步骤）；不做下单/借还/划转/gate/部署/实盘操作。全部验证离线完成。

Allowed Files

- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-dual-ledger-flow-log-v1.handoff.md`（create-only；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件。**Bookkeeper 路由前须复跑 `test ! -e <path>` 并把结果与时间写在本行**——先前 2026-08-04 12:55 CST 记录为 `PASS(absent)`，本 packet 已整份重写，需复验；**Bookkeeper 已于 2026-08-04 20:32 CST 复跑：PASS(absent)**）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-dual-ledger-flow-log-v1.selfcheck.txt`（self-check 原始输出）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`（仅可将本任务 `current_task.state` 从 `dispatched` 改为 `reported`；不得改动任何其他字段）

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/frontend-dual-ledger-flow-log-v1.dispatch.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`
- `agents/roles.md`（Implementer 章节 + Task Handoff Evidence Contract 章节）
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md` **v1.3**（§3.1/§3.2 文案表、§11、§12 决议 1/2、§13.2、§13.3、§13.4、§13.7、§15.4）
- `docs/api/public-market-contract.md`（v0.12 amendment：两条路由、非 200、200 响应字段、空态、硬规则）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-schedule-api-v1.handoff.md`（后端**实际**交付的行为与响应形状）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-fake-flow-log-v2.handoff.md`（本任务的起点：独立页 fake 实现）
- `frontend/index.html`、`frontend/self-check.js`

Acceptance Checks

1. **接真实数据**：页面数据全部来自 `GET /api/private-ledger/flow-log?start=&end=`；手动刷新走 `POST /api/private-ledger/refresh` 后重新 `GET`；`buildFlowLogFakePayload` / `flowLogFakePayload` / 两个 fake helper seam 已删除；页面与代码中不再有「演示」/「FAKE」横幅、副标题与按钮文案。
2. **布局与需求 1 未回退**：独立视图（`#nav-flow-log` / `#flow-log-view` / `setActiveView` 互斥 / `#btn-flow-log` 切页）、§13.7 冻结 id 全集、双栏标题、右栏五筛选、两个元数据区块、窄屏堆叠、`#btn-privacy` 落位与其 id/`aria-pressed`/label/icon/localStorage 键/`#private-pm-source-time` 位置全部保持不变。
3. **诚实性护栏**：状态条主文案按 §13.2 规则 14 顺序取第一个命中；`pending_tail_ms` 为独立附注；`coverage.complete=false` 必渲染覆盖提示且按 (a) 起点截断 / (b) 区间空洞分别成文；`complete=false` 时全页无「该时间窗无记录」/「没有流水」措辞；空态 payload（`scheduler_enabled=false` / `last_run=null`）与「真无流水」在文案上可区分。
4. **口径与算术纪律**：增量标题含基准时刻、`delta.complete=false` 时零数字；三口径各自标注；前端不排序、不重算汇总、不对金额做任何算术（`Number()` 仅用于正负号着色）；`null` 渲染 `—` 而非 0；`*_total=null` + `unparsed_row_count>0` 显示「合计不可用」；ID 不被数值化。
5. **展示条数**：两栏各 20 条，左栏文案含全量 `row_count`，右栏文案含「筛选后 X / 全量 N」，`row_limit_applied=true` 时含 500 提示；右栏 `summary_*` 不随筛选变化。
6. **请求与定时器边界**：初始化零 `private-ledger` 请求；进入视图恰好一次 `GET`（窗口 7 天）+ 恰好一个 60000ms 轮询；离开视图 `clearInterval` 且不再请求；重复进入不叠加定时器；类型筛选与隐私切换零请求；时间窗切换/自定义应用各一次 `GET`，非法自定义零请求；既有定时器未被改动。
7. **错误与加载**：`GET` 的 400/503/网络失败与 `POST` 的 429/409/503 各有专门中文文案、均不清空上次成功数据、均不退化为「无流水」；加载中禁用按钮 + skeleton。
8. **离线自检与边界**：`node frontend/self-check.js` 全绿，原始输出已存 `evidence/frontend-dual-ledger-flow-log-v1.selfcheck.txt`，新增断言覆盖上述 1–7（含 mock 两条新路由、98b 两条 fake 断言已反转）；未改 `backend/**`、未改契约文档、未启动服务、未访问网络、未读凭据、未执行任何实盘/下单/借还/划转/gate/部署操作。

Stop

只在 Allowed Files 内修改。先创建 handoff，再用其 Human Brief 生成合规 `[TASK_RESULT v2]`（含三行中文交接），并把本任务 `current_task.state` 标为 `reported`。在**一个** delivery commit 中提交允许的代码、self-check 输出、`status.json` 与 handoff；handoff 的 `delivery_sha` 写 `pending`。完成后停止：不得自行启动 Reviewer、Bookkeeper 或任何其他终端，不得合并、部署、启动服务或执行任何实盘/网络/凭据/下单操作；前后端联调（含真实 `POST /refresh`）由 Human 在本任务之后单独主持并授权。
