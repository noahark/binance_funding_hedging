# Direction Draft — kimi27 (Kimi) — Real Borrow Execution v1

独立方向草案。视角侧重：现有前端 fake UI 向后端拥有状态的迁移、用户对负债/风险与任务状态的理解、确认/错误/恢复 UX、前端测试边界；同时覆盖派发单要求的全部六个方向议题。

## Problem Statement

上一阶段（`2026-07-borrow-task-ui-fake-v1`）已验收的任务 UI 只存在于浏览器会话内存（`frontend/index.html:2084-2311`）：刷新即丢失、不产生任何请求。用户现在要求进入真实借币：任务可靠保存与恢复、按受控间隔真实借入、失败按策略重试、达到累计成功次数停止、进度回显页面。

本质问题不是"把 fake 接到一个 POST 接口"，而是：**在一个目前构造上就禁止写操作的仓库里，引入最小、可审计、用户授权的自动负债创建能力**。证据：

- 后端唯一签名通道 `backend/services/private_client.py:123-131` 对非 GET 方法在构造签名之前直接 `raise PermissionError`，白名单只有 14 个 GET 端点；
- 服务端路由 `backend/app/server.py:39-56` 只有 `do_GET`；
- 因此本阶段需要新增的是仓库里第一个写路径，其授权、幂等、审计设计必须一次到位，而不是先通后补。

同时，已验收的 UI 语义（资产 + 单次数量 + 目标成功次数；借币中按间隔尝试；失败等下个间隔；达标停止；启动/暂停/删除/编辑/筛选）是产品资产，真实化过程中不得悄悄改变用户已确认的操作模型。

## Target User And Workflow

单一操作者（用户本人），本地工作站，服务绑定 `127.0.0.1:8787`（`backend/config.py:28-29`），launchd 托管（`deploy/launchd/`、`scripts/service-control.py`）。无多用户、无远程访问。

目标工作流：

1. 用户在费率行情表发现机会，在该行「操作」列输入单次借币数量与目标成功次数（现有 UI 已含最小借币量及 USDT 估值占位提示，`frontend/index.html:1621-1627`）。
2. 创建任务后经过一个**显式风险确认**（展示最坏情况总负债、当前利率与估算成本），任务才进入可执行状态。
3. 后端调度器按间隔尝试真实借币；用户在任务页看到成功进度、已借总量、下次尝试倒计时、最近错误；可随时暂停/删除。
4. 全局存在一键停止（kill switch）；服务重启后任务与进行中的尝试可恢复、可对账。
5. 借到币之后的对冲/平仓操作仍由用户在交易所手动完成（非本系统范围）。

## Scope

### 1. "真实借币任务"的用户可见定义

任务 = `{asset, amount_per_attempt, success_target, retry_interval, caps}`，语义与 fake UI 完全一致，差异只在执行体真实化：

- **一次"成功的请求"** = 交易所借币写接口返回业务成功，**且**对账读（借币记录/账户负债）能确认该笔负债已存在。仅 HTTP 2xx 不足以计为成功（计为"待对账"）。
- **系统必须持久化/审计**：任务全量字段与每次状态迁移；每次尝试的请求参数（资产/数量，绝不含签名与凭据）、客户端生成的尝试 ID、派发前时间戳、响应状态/业务码、交易所侧记录 ID、对账结果。审计面沿用 `private_client.py:166-176` 的脱敏日志模式。

### 2. 授权与确认模型（自动重试创建负债的前提）

- **全局默认关闭**：`borrow_execution_enabled` 默认 `false`，配置之外还要求运行时显式开启；未开启时调度器只记录"本应尝试"（纸面模式），不发请求。
- **两级确认**：创建任务 ≠ 授权执行。创建后任务处于待启动态，启动需显式确认对话框，内容含：单次数量 × 剩余次数 = 最坏新增负债、按当前利率估算的持有成本、资产与账户模式。
- **Kill switch**：全局停止开关，生效后调度器在下一次派发前即停（不打断已在途请求，但在途结果照常对账入账）；UI 任务页头部常驻可见。
- **上限（数值冻结前给默认建议）**：单任务总量由 `amount × success_target` 天然封顶；另需全局每资产未偿负债上限与全局 USDT 负债上限（每次派发前校验，超限即暂停该任务并显式提示）；单任务连续失败上限（建议 3 次）触发自动暂停；单任务总尝试次数上限（建议 `success_target × 10`）防无限重试。
- **合法资产/数量**：服务端校验为唯一权威（前端现有 `parseBorrowAmount/parseSuccessTarget` 仅做就近提示）：资产必须存在于最新快照且 `borrow_validation` 未标记不可借；数量 ≥ `user_min_borrow`；每次派发前重新校验可借额度，不满足则本次记失败而非盲目发请求。
- **重试间隔**：fake UI 写死展示"每 30 秒尝试一次"（`frontend/index.html:2272`）。真实化后间隔应成为任务字段（默认沿用 30s），UI 展示改为读后端值。
- **暂停/删除竞态**：调度器在每次派发前的最后一刻复查任务状态；任务存储单写者。"在暂停生效前已派发的尝试"不对用户隐藏：结果照常对账、计入成功次数，并在卡片上可见。删除沿用已验收的软删除语义（先停后删，对象不物理移除，`frontend/index.html:2182-2189`）。

### 3. 正确性：幂等、状态机、对账

- **幂等/防重**：每次尝试在派发**之前**落库（意图记录 + 客户端尝试 ID）。超时/网络错误/5xx 一律进入 `attempt_unknown`，**绝不直接重试**；先通过借币历史/账户负债对账确认该尝试是否实际成交，再决定计成功或放行下次尝试。交易所借币端点是否支持客户端幂等键属待核实语义（见人工门禁）；若不支持，"未知结果先对账"就是唯一安全规则，不可妥协。
- **状态机**：对外（UI）保持已验收的四个状态词 `borrowing/paused/deleted/completed` 不变；内部增加尝试子状态（等待间隔 / 在途 / 未知待对账）与暂停原因字段 `paused_reason: user | failure_limit | unknown_outcome | kill_switch | cap_exceeded`，使自动暂停与用户暂停在 UI 上可区分但不增加状态词。`completed` 由后端在成功次数达标并对账后落终态。
- **崩溃恢复**：服务启动时装载任务，凡上次退出时处于"在途"的尝试一律标记 `attempt_unknown` 并先对账再恢复调度；调度器重启不丢进度、不重复已计成功。
- **对账**：周期性（如每次快照重建时）比对任务侧累计成功量与交易所该资产实际负债增量；不一致则暂停相关任务并产生全局告警横幅，等待人工处置。

### 4. 安全与运维

- **凭据**：仅环境变量注入，沿用现有 Config 模式；任何日志、报告、模型提示中不得出现 key/secret/签名/完整账户数据（沿用 intake 门禁）。建议在交易所侧使用**最小权限 API key**（仅开保证金借币，禁提现）并绑定 IP 白名单——属人工决策。
- **写通道实现**：在 `private_client.py` 的白名单机制上最小扩展（新增 `(POST, borrow路径)` 条目），保留"验白名单先于构造签名"的防御结构；禁止任何形式的 base URL 注入。
- **本地-only**：保持 `127.0.0.1` 绑定与 launchd 单实例；不做任何公网暴露。
- **并发与限流**：调度器全局单飞（同一时刻至多一个在途借币请求）；遵守 sapi 权重池（与现有 GET 共用池，权重预算需纳入设计）。
- **可观测**：结构化生命周期日志（沿用 `_emit_lifecycle` 模式）；UI 全局横幅覆盖：执行未开启 / kill switch 生效 / 对账不一致 / 存在 unknown 尝试。
- **测试策略（绝不触真实账户）**：借币写路径的全部测试使用录制样本与 hermetic stub 交易所；合约测试固定请求形状；前端自检（`frontend/self-check.js`，Node + mock DOM）扩展 mock fetch 覆盖任务 API；另设 PaperExecutor 让完整状态机在 fixtures 上端到端跑通。真实端点的原始请求/响应样本按 Harness 硬门禁落入 `reports/api-samples/<stage>/` 后才允许放行真实写。

### 5. API / 前端契约与 rollout（保留现有 fake UI 安全接入后端状态）

**契约**：新增独立版本化任务 API 族（建议 `/api/borrow-tasks/...`，wire version 如 `borrow-tasks/v1`，schema 落 `schemas/api/` 新目录）。不复用、也顺手不修 `public-market-snapshot/v1` 的历史命名缺口（AGENTS.md 已知 gap，另行处理）。端点最小集：

- `GET /api/borrow-tasks` — 任务列表（含进度、paused_reason、下次尝试时间、最近错误、执行模式标记）；
- `POST /api/borrow-tasks` — 创建（草稿/待启动）；
- `POST /api/borrow-tasks/{id}/start|pause|delete|edit` — 对齐现有四个操作语义。

**前端迁移**（本草案的核心视角）：

- 两视图结构、操作列入口、按钮矩阵、状态词、筛选、空态、软删除全部保留；`state.borrowTasks` 由内存数组换成后端列表的客户端缓存，渲染函数签名尽量不动。
- 「前端演示」徽章与免责声明（`frontend/index.html:2266,2287`）替换为执行模式徽章：`未接交易所`（纸面）/ `真实借币`（danger 色）；任务页头部放全局执行开关状态与"全部暂停"。
- 任务卡片新增：已借累计（数量 + USDT 估值）、下次尝试倒计时、最近一次失败原因；`unknown` 尝试以阻塞级样式呈现，不允许用户一键忽略。
- 确认 UX：创建走现有行内校验；**启动**弹显式确认（见 §2）；自动暂停（failure_limit/cap_exceeded）的卡片显示原因而非仅换徽章。
- 轮询：任务列表默认并入现有 60s 快照刷新节奏；存在 borrowing 任务时建议前端对任务端点加快轮询（建议 5–10s，数值待冻结），避免 30s 尝试间隔下进度长期滞后。
- fake 内存任务不做迁移（会话数据，可接受丢失），在阶段说明中明示。

**Rollout（建议两段，均在本阶段内先后交付或按用户裁切）**：

- **Phase A — 后端任务核心，不接交易所写**：持久化存储（建议 stdlib sqlite3，单写者）、任务状态机与调度器、任务 API、PaperExecutor；前端完成从内存到后端状态的迁移并以 `未接交易所` 模式运行。此段交付即可完整验收 UI 迁移与状态机，零外部副作用。
- **Phase B — 真实执行**：Binance 借币 Executor、`private_client` POST 白名单扩展、对账循环、kill switch、审计日志；`borrow_execution_enabled` 默认 false；凭据注入与真实样本采集完成后由用户显式开启。Phase B 的每个真实端点必须先有 raw samples，否则按 Harness 规则记 follow-up 并复审。

### 6. 前端测试边界（明确划线）

- `frontend/self-check.js` 保持 Node + mock DOM、无网络：新增任务 API 的 mock fetch 层，状态转换/按钮矩阵/筛选/错误就近展示走现有 `__appHelpers` 直测模式。
- 任务 API 契约用静态 fixture（对齐 `frontend/fixture/public-market-snapshot.json` 模式）做 ingest 校验测试。
- 任何测试不得依赖运行中的真实后端或交易所；真实样本只作为只读 fixture 证据进入仓库。

## Non-goals

- 还币、转账、平仓/对冲下单、全自动策略闭环；借后操作仍手动。
- 多用户、鉴权体系、公网部署、移动端。
- 跨账户/子账户、组合保证金借币（除非用户在门禁中明确选择 PM 模式）、利率优化/再融资换仓。
- 修复两个已明确推迟的 P3（同页其他卡片未提交编辑值在重渲染时丢失；表格行内可访问性）。
- 重命名历史 `public-market` 路由/wire version。
- 通用定时任务平台化（调度器只为借币任务服务，不抽象公共框架）。

## Domain Assumptions Requiring Confirmation

1. 借币执行的账户/保证金模式：现有 `borrow_validation.classic_margin` 链路与 `portfolio_account`（papi）并存，fake UI 的额度提示取自 classic；真实借币走 classic cross/isolated 还是 PM，必须用户冻结。
2. 交易所借币端点的幂等语义：是否支持客户端幂等键；成功判定字段；失败后负债是否可能已实际产生。需以 raw samples 核实，不得凭文档记忆实现。
3. "成功"是否必须经对账读二次确认（本草案建议：是）。
4. 重试间隔默认值沿用 30s 是否可接受；是否允许每任务自定义。
5. 全局/单任务上限的具体数值与计价口径（USDT 估值用现有价格规则）。
6. 调度器生命周期：服务进程运行时才尝试；launchd 重启即恢复——用户是否接受"机器睡眠期间不尝试、唤醒后顺延"。
7. 每次派发前是否重新校验 maxBorrowable/可借池（建议：是，失败计一次失败尝试）。

## Acceptance Criteria

Phase A：

1. 任务经 API 创建/启动/暂停/删除/编辑，语义与 fake UI 逐项一致（含软删除与按钮禁用矩阵），服务重启后任务与进度完整恢复。
2. 前端两视图、筛选、空态、行内校验保持不变；任务数据全部来自后端；`未接交易所` 模式徽章可见。
3. PaperExecutor 在 fixtures 上跑通"间隔尝试→失败重试→达标 completed→失败上限自动暂停（paused_reason）"全链路；无真实网络。
4. `frontend/self-check.js` 与后端测试全绿，且无测试触网。

Phase B（在凭据、raw samples、数值冻结完成后才允许开始验收）：

5. 执行默认关闭；未开启时零出站写请求（日志可证）；开启流程需显式确认。
6. 超时/5xx 注入测试：不产生重复借币，进入 `attempt_unknown` 并对账后恢复或暂停。
7. Kill switch 生效后零新派发；在途尝试结果正确入账。
8. 审计日志覆盖每次尝试与状态迁移且不含凭据/签名/完整账户数据（含 grep 级红线测试，沿用 private_client 的断言模式）。
9. 对账不一致 → 相关任务暂停 + UI 全局横幅。

## Open Questions And Human Gates

冻结前不得编码（对齐 intake Human Gates）：

1. 账户/保证金模式与目标借币端点（classic cross/isolated/PM），及该端点幂等与成功判定语义——需 raw samples 证据。
2. 凭据注入方式与 API key 权限范围（建议：仅借币、禁提现、IP 白名单）；样本采集由用户在其环境执行。
3. 各上限数值：单任务连续失败上限、总尝试上限、全局每资产与总 USDT 负债上限。
4. 重试间隔默认值与是否每任务可调；前端任务轮询节奏。
5. "未知结果不自动重试、先对账"是否接受（建议：接受，作为不可妥协项）。
6. 启动确认对话框的文案与确认强度（单击确认 / 勾选确认）。
7. Phase A/B 是否在同一 stage 内连续交付，还是 Phase A 验收后另立 stage。

---

当前 Session ID: unavailable（当前 Kimi CLI 运行时未向模型暴露 provider-native session ID）
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/direction-drafts/kimi27.md
本地北京时间: 2026-07-19 07:31:46 CST
下一步模型: human operator
下一步任务: 将派发单其余分段派发给 Claude、Claude-GLM、Grok Build 并保存原始输出；全部草案齐备后由 Codex/GPT 执行 direction-synthesis
