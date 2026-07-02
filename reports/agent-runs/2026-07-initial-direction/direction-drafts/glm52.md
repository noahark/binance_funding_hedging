# glm5.2 阶段设计方向稿

> 本文件为多模型设计评审小组中 GLM5.2 的独立方向草稿，不是最终 PRD，不替用户拍板。
> 会话模型：`glm-5.2[1m]`（经 Claude Code / claude-glm 适配器接入）。model-id：`glm52`。

## 阅读诚实声明

我实际读取了以下文件全文：`docs/product/PRD.md`、`docs/harness-design.md`、`docs/README.md`、`docs/architecture/ARCHITECTURE.md`、`docs/development/DEVELOPMENT_GUIDE.md`、`AGENTS.md`、`prototypes/fake-ui/index.html`。

部分读取的文件（不假装已读全文）：

- `llms-full.txt`：共 193,023 行 / 约 7.4MB，我**没有通读**，仅对借币/还款、PAPI 杠杆下单、503/Unknown order、`@depth` diff+snapshot 重建算法、PAPI 限频等若干端点族做了定向 `grep` 核对。
- `币安套费率策略，逐仓杠杆.js`：共 3,447 行，我只读了前 400 行（账户金额聚合、基金份额、微信通知等结构）。

本文凡引用 Binance 接口，会显式标注依据是「PRD 转述」还是「我亲自在 llms-full.txt 中 grep 核实」。

## 1. Baseline 理解

这是一个面向 Binance Portfolio Margin（统一保证金）账户的**人工资金费率对冲工作台**，不是自动交易机器人。核心约束与不可违背原则，我用一句话和一组红线概括：

一句话：扫描 USDT 计价、可对冲的永续/现货交易对，展示费率机会与真实成本，由人工点击后用 market order 异步同时开双腿，全程记账、留证、对账，异常只高亮不自动处理。

不可违背的产品原则（红线）：

1. **开平仓由人工触发**，不做任何基于阈值的自动开/平/补腿/紧急平仓；v0.1 明确禁止。
2. **双腿对冲是手工命名的执行单元**：正费率=永续空+现货/杠杆买；负费率=借币卖现货+永续多。
3. **bStock 只做正费率**，因为不支持借币。
4. **USDT 计价、单向持仓模式**为唯一形态。
5. **真实成本必须计入**：资金费、手续费、BNB 抵扣、返佣折扣、借币利息、滑点，缺一不可；资金占用成本 v0.1 不计。
6. **双腿不一致只高亮提醒**，绝不自动平仓或补腿。
7. **API key 禁止提现**；每一笔请求/响应在 discovery 与早期实盘阶段都要落盘留证。
8. **文档/草稿分层**：草稿进 `reports/agent-runs/<stage>/`，正式文档进 `docs/`；本稿属于草稿，不写正式文档。

边界（Non-Goals 我认同）：不做自动开平、不做对冲模式双向持仓、不做非 USDT、不做提现/划转自动化、不做回测。

## 2. 我认为当前 PRD 已经明确的内容

可进入开发设计的确定事项：

1. **资产分类体系**（5 个值）清晰可落地：`CRYPTO_BIDIRECTIONAL` / `CRYPTO_LONG_SPOT_ONLY` / `BSTOCK_LONG_SPOT_ONLY` / `PERP_ONLY` / `SPOT_ONLY`，以及正/负费率各自支持的分类集合。
2. **对冲方向逻辑**明确：正费率与负费率各自的期货腿、现货腿方向、账户路由优先级（PM/cross-margin 现货优先 → 普通现货兜底）。
3. **手动执行流程**的数值规则明确：按轮次、每轮名义值；低于最低名义值时取 `max(各腿最低名义值) * 1.02` 并重算轮数；末轮不足则并入上一轮。
4. **成本归因公式**已给出：`rebate_adjusted_fee = actual_fee_after_bnb_discount * 0.6`，`net = funding_income - 各项 rebate 调整后费用 - borrow_interest - estimated_slippage_cost`。
5. **资金费流水字段**清单明确（收支时间、标的、结算时方向、费率、名义值、有符号金额、income 类型、Binance ID、原始 payload 引用）。
6. **Binance 接口基线清单**详尽（PAPI account/balance、UM account V2、positionRisk、um/order、um/income、margin/order、myTrades、maxBorrowable、spot/futures exchangeInfo、premiumIndex、depth、用户数据流事件），并给出了限频（6000/min IP、1200/min order）、`recvWindow<=5000`、503 处理原则。
7. **交易规则归一化**规则明确：解析 `LOT_SIZE`/`MARKET_LOT_SIZE`/`MIN_NOTIONAL`/`NOTIONAL`，按 stepSize 取整后再校验名义值。
8. **UI 四屏**已存在可运行的原型（`prototypes/fake-ui/index.html`）：总览持仓、费率行情、手动开仓、收益归因，并已含执行步骤条、借币预检、实时盘口、返佣后手续费等字段。
9. **风险控制**清单明确：禁止提现 key、单笔/单标的/总名义值可配置、UI 标注路由与是否支持负费率、借币失败阻断、腿不匹配高亮保留。
10. **技术方向**已定：Python asyncio 后端、TypeScript/React 前端、SQLite 候选；凭证只留在后端。
11. **Phase 1/2/3 验收标准**已分层给出。

## 3. 我认为当前 PRD 仍不明确或有风险的内容

### 3.1 [严重] Portfolio Margin 借币模型可能与 PRD 描述不符，负费率路径建立在未核实端点上

- **问题**：PRD 把负费率流程写成「先借 base asset，再下现货卖单」，并给出借币端点 `POST /papi/v1/marginLoan`、`GET /papi/v1/margin/marginLoan`、`POST /papi/v1/repayLoan`、`GET /papi/v1/margin/repayLoan`（PRD 第 307–310 行）。
- **核实结果**：我在 `llms-full.txt` 中 `grep` `papi/v1/marginLoan`、`papi/v1/repayLoan` **未命中任何结果**。能确认的只有：
  - 经典杠杆 `POST/GET /sapi/v1/margin/loan`、`/repay` 正在被下架，替换为统一的 `POST/GET /sapi/v1/margin/borrow-repay`（llms-full.txt 第 36945–36959 行，我已 grep 核实）。
  - PAPI 侧明确「新增」的还款接口是 `POST /papi/v1/margin/repay-debt`（llms-full.txt 第 48767、54251、58890 行，我已 grep 核实），PRD 也把它标为「采样但不自动使用」。
  - 此外，统一账户（Portfolio Margin）下，**借币通常是自动发生的**——卖空你没有的币时负债自动产生，并不一定需要显式 `borrow` 调用。这条我是基于币安统一保证金的一般机制推断，**未在 llms-full.txt 中逐字确认**，需 discovery 验证。
- **为什么重要**：这是负费率对冲的命门。如果端点不存在、或借币是自动的，那么 PRD 第 134 行「borrowing must happen before the first market order」就是一个从老逐仓策略继承下来的错误假设，负费率腿根本无法按现描述执行；也可能显式借币在 PM 账户下是冗余甚至不可用的。
- **建议处理**：
  1. 把「PM 负费率借币机制」列为 discovery 的**第一优先级**，必须用真实账户样本确认：是否需要显式借币？走哪个端点（`borrow-repay` / `repay-debt` / 自动负债）？
  2. 在确认前，PRD 中的 `/papi/v1/marginLoan`、`/papi/v1/repayLoan` 应标注为「未核实/疑似不存在」，不要据此写代码。
  3. 在确认前，**负费率执行不进入任何可下单阶段**，只做 discovery 与数据结构预留。

### 3.2 [高] 「平滑开仓 + 长期等待后立即对冲兜底」缺乏明确状态机

- **问题**：任务背景与 PRD 都强调「平滑开仓」和「长期等待平滑开仓后的立即对冲兜底，避免一直不开单」。但 PRD 的 Manual Execution Flow 只描述了轮次、最低名义值修正和 depth 用于展示，**没有定义**：等待什么条件才开腿？价差/滑点阈值如何判定可执行？「兜底」具体指什么（超时后无视价差按 market 强行补齐双腿？）？两条腿异步同时发，一条成交一条未成交怎么办？
- **为什么重要**：这是真实下单的最高风险路径。状态机不清 → 异步双腿可能留单边裸露 → 这正是对冲策略最该避免的状态。
- **建议处理**：明确一个执行器状态机，例如 `PLAN → BORROW_PRECHECK → ARMED(订阅 depth) → WAIT_FOR_GATE(spread≤阈值) → FIRE_FUTURES ‖ FIRE_SPOT → RECONCILE → DONE|DEGRADED|FLAGGED`；其中「兜底」=等待超时后由人工二次确认是否按 market 强行下单（**默认不自动强下**），任何单边成交不匹配都进入 `FLAGGED` 等人工处理，绝不自动补腿。

### 3.3 [高] HTTP 503 未知执行态 × 异步双腿 = 重复下单 / 裸腿风险，缺幂等键策略

- **问题**：PRD 正确要求 503 不能当失败处理（要先查单/用户流确认）。但在**异步双腿**场景下，一条腿 503、另一条腿已成交，系统可能重复下单或留裸腿。PRD 只提了「记录」与「先查」，没有要求幂等键（`newClientOrderId`）与按 clientOrderId 的查询/重发策略。
- **为什么重要**：503 + 网络抖动 + 异步并发，是对真实资金最容易出事的组合；没有幂等键就无法安全重发。
- **建议处理**：强制每轮每腿用带幂等前缀的 `newClientOrderId`（如 `fh-{planId}-{round}-{leg}`），503/超时后**按 clientOrderId 查询**而非按金额重下；只有查询确认未成交才允许重发；确认的裸腿只高亮，由人工处理。

### 3.4 [高] bStock 路由与账户资格未验证，原型却已展示

- **问题**：原型 UI 已经出现 `TSLAUSDT`、`AAPLUSDT` 的 bStock 行（BSTOCK_LONG_SPOT_ONLY），但 PRD 自己把 bStock 可用性、路由、账户资格列为 Open Question。bStock/代币化股票有强区域、KYC、账户类型门槛。
- **为什么重要**：在未验证账户是否开通、现货路由是否真实存在前就展示「可执行」，会误导操作员。
- **建议处理**：bStock 在 discovery 阶段只做「存在性采样」，**不**默认进入可执行队列；分类为 `BSTOCK_LONG_SPOT_ONLY` 必须有真实 exchangeInfo/路由样本支撑，否则标灰。

### 3.5 [中] 持仓模式 / 账户模式假设无运行时断言

- **问题**：PRD 假设 PM 账户 + 单向持仓。但账户实际可能是普通合约账户（非 PM），或处于 hedge mode。`/papi/v1/um/positionSide/dual` 必须查证；hedge mode 下下单需带 `positionSide`。
- **为什么重要**：假设错误会导致下单参数错、腿方向错。
- **建议处理**：启动时加 fail-closed 断言：确认是 PM 账户、确认单向模式（`dualSidePosition=false`），否则拒绝继续并提示。

### 3.6 [中] 腿一致性容差未定义，且期货/现货币单位需归一

- **问题**：PRD 把容差留到「看到真实成交后再定」。更隐蔽的问题：**期货持仓量单位是合约张数（contract size）**，现货是 base asset 数量，二者不能直接比（原型里 BTCUSDT 直接写 `Short 0.0408` vs `Long 0.0407` 容易误导）。必须先按 contract multiplier 归一到 base 数量再比。
- **为什么重要**：单位不归一 → 容差永远算错 → 要么误报要么漏报裸腿。
- **建议处理**：reconciler 先把双腿都折算成 base asset 数量与 USDT 名义值；定义绝对容差 + 相对容差双阈值；阈值用 discovery 数据种子化。

### 3.7 [中] 资金费流水部分字段需「观测 + 推导」拼接，易重复计数

- **问题**：PRD 要求流水行同时含「该事件所用费率」与「结算时持仓名义值」。但 `/papi/v1/um/income` 的 `FUNDING_FEE` 行通常给 `income`、`time`、`symbol`，不一定直接给费率和名义值；名义值/费率要靠 `positionRisk` 快照或 mark price 回推。PRD 没区分哪些字段是观测、哪些是推导。
- **为什么重要**：join 错位会重复计数或漏计资金费，污染净值。
- **建议处理**：流水行显式标注每字段来源（`observed` / `derived` + 推导所用快照时间），并禁止用估算名义值回算 income。

### 3.8 [中] 返佣默认 40%（×0.6）是假设，且硬编码

- **问题**：PRD 与原型都把现货/合约返佣写死 40%。实际返佣随 VIP 等级、BNB、推荐关系变化，未必是 40%。
- **为什么重要**：返佣直接影响净值与「是否值得开」的判断；写死会系统性偏差。
- **建议处理**：返佣率做成可配置（按账户/标的），默认 40% 但在 UI 标注为「假设值」；discovery 尝试从 income 的返佣/返现行反推真实返佣率。

### 3.9 [中] 滑点估算方法未定义

- **问题**：UI 与会计里都有「预估滑点」和「滑点成本」，但 PRD 没给定义。是 bid/ask 对 mid 的偏移？还是按本轮数量走 depth？已实现滑点怎么算？
- **为什么重要**：滑点是对冲成本里波动最大的项，定义不清则净值不可信。
- **建议处理**：盘前预估=按本轮下单量在本地 depth book 上走量取加权均价 vs mid；已实现=成交均价比对下单瞬时参考价；全程 Decimal。

### 3.10 [中] 架构与开发指南仍是空（TBD），无仓库骨架

- **问题**：`docs/architecture/ARCHITECTURE.md`、`docs/development/DEVELOPMENT_GUIDE.md` 基本全是 TBD。没有项目布局、没有 test/lint/typecheck 命令、没有 ADR、没有 Python/TS 仓库骨架。Phase 2/3 验收预设的代码还没有「家」。
- **为什么重要**：在没定布局与契约前写功能代码，会反复返工，也过不了 Harness 的 diff/测试硬门。
- **建议处理**：第一阶段必须先冻结仓库布局、工具链、数据契约，再写任何功能代码。

### 3.11 [低] 老策略文件含真实个人信息，且仓库已 untracked 存在

- **问题**：`币安套费率策略，逐仓杠杆.js` 内含大量真实微信 openId、姓名、份额（PII），且 `llms-full.txt`、`.DS_Store` 也以未跟踪文件存在于仓库。若仓库分享给其他模型/评审，PII 会泄露。
- **为什么重要**：合规与隐私；也违背「凭证/敏感不进报告」的 Harness 约束精神。
- **建议处理**：不要把老策略导入 docs/code；纳入 `.gitignore` 或脱敏；仅作只读参考。

## 4. 关键技术设计建议

### 4.1 后端主策略服务

- Python + asyncio；核心是一个**显式状态机**（见 3.2），不要把执行逻辑散在回调里。
- 全程 `Decimal`，禁用 float 存金额/费率。
- 仓库分层：`adapters/`（对接币安）→ `domain/`（分类、规则归一、执行计划、账目、对账，纯函数、可测）→ `orchestrator/`（执行器状态机）→ `store/`（事件/快照落盘）。
- 单一事实来源：以「事件流 + 周期快照」重建持仓与账目，UI 只读快照。

### 4.2 Binance 适配层（PAPI / UM / Spot / WS）

- 每个端点一个薄封装：统一签名、`recvWindow`、记录返回的限频头（`X-MBX-USED-WEIGHT-*` 等）、503→`UNRESOLVED` 状态、原始 req/resp 落 `reports/api-samples/`（时间戳文件名、凭证脱敏）。
- **discovery 优先**：适配层从观测到的真实 JSON 构建，不纯靠文档假设（PRD 第 365 行已要求）。对 3.1 的借币端点必须先确认再封装。
- WS：listenKey 生命周期管理（建/续期/删）、断线重连、本地 depth book 按 diff+snapshot 算法重建（llms-full.txt 第 16164–16170 行已核实该算法存在）。用户数据流按事件类型分发到事件总线。

### 4.3 资产筛选与交易规则归一化

- 启动时（其后每 8 小时）跑分类器：永续存在 ∧ 现货腿存在 → 再判可借币 → 输出 5 类标签之一。
- 规则解析器从 spot/futures exchangeInfo 抽 `LOT_SIZE`/`MARKET_LOT_SIZE`/`MIN_NOTIONAL`/`NOTIONAL`；最低名义值取**双腿最严**再 ×1.02；按 stepSize 取整后**回检**名义值（PRD 已要求）。
- 期货 contract multiplier 必须读出来，供 4.5 归一使用。

### 4.4 手动开仓与平滑开仓执行器

- 状态机：`PLAN → BORROW_PRECHECK → ARMED → WAIT_FOR_GATE → FIRE_FUTURES ‖ FIRE_SPOT → RECONCILE → DONE|DEGRADED|FLAGGED`。
- 每轮每腿幂等 `newClientOrderId`；双腿**并发**下单，单腿超时/503 走「按 clientOrderId 查询」，绝不按金额盲重发。
- 负费率借币前置：在 3.1 确认前**关闭**该路径；确认后把借币（或确认自动负债）插入 `BORROW_PRECHECK`。
- 「兜底」默认只生成人工二次确认入口，不自动强下。

### 4.5 持仓一致性检测

- reconciler 把双腿都折算到 base asset 数量与 USDT 名义值（用 contract multiplier）。
- 检测项：单腿缺失、方向错、数量超绝对/相对容差、有借币无对应期货多、单侧数据陈旧。
- 输出：高亮 + 不匹配类型，**只读**，绝不触发任何补腿/平仓。

### 4.6 收益与成本归因

- 资金费流水 = `um/income` 的 `FUNDING_FEE` 行 + 用 positionRisk 快照推导的名义值/费率，字段标 `observed`/`derived`。
- 手续费按 `um/income` 的 `COMMISSION` 与 margin `myTrades` 的 commission 聚合；BNB 抵扣按 feeBurn 状态与 commissionAsset 判定；返佣按可配置率（默认 0.6）；借币利息按 margin interestHistory；滑点见 3.9。
- 净值 = 资金费收入 − 各项 rebate 调整后费用 − 借币利息 − 已实现滑点；全程 Decimal。

### 4.7 前端 UI 信息架构

- 沿用原型四屏，再补两块：
  1. **执行器状态面板**：把状态机当前阶段、每腿 clientOrderId、查询/重发按钮、503 未决态显式暴露（人工可决策）。
  2. **Discovery/证据面板**：展示已采样端点、未确认端点（尤其借币）、原始样本入口。
- 所有写操作（开仓、借币、查询重发）都在显式二次确认之后；UI 顶部常驻「禁止提现 · 人工确认 · 不自动平仓」。

### 4.8 测试与线上小资金验证策略

- 确定性单测先行：规则归一化（边界、stepSize、最低名义值×1.02、末轮合并）、执行计划计算、账目归因、reconciler 归一与容差——用 fixture，不依赖网络。
- 适配层契约测试：用 discovery 存下的真实 JSON 做回放测试。
- 线上验证放最后、最小：单标的、正费率、极小名义值、硬上限、全量录包；负费率/bStock 在 3.1/3.4 确认前不做线上。

## 5. 第一阶段开发范围建议

我建议第一阶段**只产出可验收的设计/数据/适配骨架，不碰真实下单**：

1. **冻结仓库骨架与契约**：Python+asyncio 后端目录、TS/React 前端目录、SQLite schema 草案、`test/lint/typecheck` 命令、1–2 条 ADR（账户模式断言、幂等下单、事件/快照存储）。→ 验证：`pytest`/`tsc`/lint 可跑空绿。
2. **接口 discovery 脚本**：针对 PRD 接口基线逐族采样到 `reports/api-samples/`，**重点核实 3.1 借币端点族**，产出一份 discovery 报告（哪些已确认、哪些未命中）。→ 验证：每族至少 1 个脱敏 JSON + 时间戳 + 来源文件标注。
3. **领域数据结构（纯函数、强测）**：资产分类、规则归一化结果、执行计划、资金费流水行、净值归因、对账结果，全部 typed + Decimal。→ 验证：单测绿。
4. **核心域逻辑 + fixture 测试**：执行计划（含 ×1.02 与末轮合并）、账目归因（含 BNB 抵扣/返佣/利息/滑点）、reconciler（含 contract multiplier 归一）。→ 验证：`60-test-output.txt` 全绿。
5. **只读适配层样本**：把已确认的读类端点（exchangeInfo、premiumIndex、um/account V2、positionRisk、um/income、depth 快照、用户数据流）封装并回放测试。→ 验证：契约测试绿。
6. **UI 原型精修**：补「执行器状态面板」「Discovery/证据面板」，用真实样本形状驱动。→ 验证：四屏 + 两面板齐全。

明确说明：第一阶段**不进入真实下单**。若要进入，须满足——账户模式断言通过、正费率单标的 discovery 完成、硬名义值上限与全量录包就位、且由用户显式批准一次小资金验证。

## 6. 不建议第一阶段做的内容

- **真实下单/借币**：除非满足第 5 节末尾的验收与用户批准。
- **负费率执行链路**：在 3.1 借币机制确认前不做，连代码骨架都只做数据结构预留。
- **bStock 可执行队列**：在 3.4 路由确认前只做存在性采样，UI 标灰。
- **任何自动开/平/补腿/紧急平仓**：与 Non-Goals 冲突，明确禁止。
- **回测引擎、多计价、对冲模式双向持仓、提现/划转自动化**：v0.1 Non-Goals。
- **返佣/容差硬编码到「最终值」**：第一阶段只用可配置默认值并标「假设」。
- **把老 FMZ 策略代码直接迁入**：含 PII 且账户模型（逐仓）与新系统（PM）不一致，只作只读参考。

## 7. 验收标准建议

不能只靠模型口头声明完成。第一阶段完成应满足：

- **文件级产物**：
  - 仓库骨架（后端/前端目录、工具链、SQLite schema 草案、ADR 1–2 条）。
  - discovery 脚本 + `reports/api-samples/` 下每端点族至少 1 个脱敏 JSON。
  - 一份 `discovery 报告`，列出已确认/未命中端点（**必须显式列出借币端点族的核实结论**）。
  - 领域模块（分类/规则/计划/流水/归因/对账）+ 适配层只读样本模块。
- **测试或模拟输出**：
  - `60-test-output.txt`：规则归一化、执行计划（×1.02、末轮合并）、账目归因、reconciler 归一 全绿，覆盖边界用例。
  - 适配层契约回放测试绿。
- **UI 验收项**：
  - 四屏齐全且数据形状贴合真实样本；
  - 新增「执行器状态面板」（含每腿 clientOrderId、503 未决态、人工二次确认入口）与「Discovery/证据面板」。
- **Binance 接口 discovery 样本验收项**：
  - PRD 基线中**读类端点**每族有脱敏样本 + 时间戳 + 来源文件标注；
  - 借币/还款族有明确「已确认端点 / 未命中 / 推断自动负债」结论；
  - 未命中端点不得在代码中假装可用。
- **明确不做项**：无下单代码、无 API key 入库、无自动开平、无不匹配自动平仓。

## 8. 与现有 PRD 的冲突或修订建议

不直接改 PRD，仅建议：

- **原问题**：PRD 把负费率借币端点写为 `/papi/v1/marginLoan`、`/papi/v1/repayLoan`（第 307–310 行）。
  - **建议改成**：标注「未核实/疑似不存在」，候选改为 `/sapi/v1/margin/borrow-repay`（已确认存在）与 `POST /papi/v1/margin/repay-debt`（已确认新增），并要求 discovery 先确认 PM 是否自动负债。
  - **理由**：我在 llms-full.txt 中 grep 不到 PRD 所列两个 PAPI 借币端点；经典 `/sapi/v1/margin/loan` 正在下架。
- **原问题**：PRD 第 134 行「For negative funding, borrowing must happen before the first market order.」
  - **建议改成**：「负费率需先确认 PM 借币机制；若为自动负债，则改为：卖空后通过用户流 `liabilityChange` 追踪负债，不做显式 borrow；若需显式 borrow，则在首单前完成并校验 `maxBorrowable`。」
  - **理由**：统一保证金借币语义与逐仓不同，可能为自动。
- **原问题**：「平滑开仓 + 立即对冲兜底」缺少状态机。
  - **建议改成**：新增「执行器状态机」小节（见 3.2 / 4.4），明确 gate、超时、兜底=人工二次确认、单边成交只高亮。
  - **理由**：异步双腿最高风险，必须可枚举状态。
- **原问题**：返佣默认 40% 被当作确定值。
  - **建议改成**：标为「可配置默认值，discovery 期间尝试反推真实返佣率」。
  - **理由**：返佣随账户等级变化。
- **原问题**：执行规则未要求幂等键。
  - **建议改成**：在 Execution Rules 增一条「每轮每腿必须使用幂等 `newClientOrderId`，503/超时按 clientOrderId 查询，禁止按金额盲重发」。
  - **理由**：防重复下单与裸腿。
- **原问题**：腿一致性比较未要求单位归一。
  - **建议改成**：明确 reconciler 先按 contract multiplier 折算到 base 数量与 USDT 名义值再比。
  - **理由**：期货张数 ≠ 现货 base 数量。

## 9. 需要用户拍板的问题

### Q1. 负费率链路在第一阶段的范围？
- A（推荐）：**整体后置**，待 3.1 借币机制 discovery 确认后再启用，第一阶段只做数据结构预留。
- B：仅做 discovery 与只读采样，不下单。
- C：按 PRD 现描述（显式 borrow 前置）直接纳入。
- 取舍：A 最稳但交付面窄；B 折中；C 风险高（端点未核实）。

### Q2. bStock 的范围？
- A（推荐）：**discovery 存在性采样**，UI 标灰，不进可执行队列。
- B：正费率可执行（需先确认账户开通与现货路由）。
- C：完全排除。
- 取舍：A 最安全；B 收益面大但依赖账户资格；C 最简。

### Q3. 首次真实小资金验证的时机与规模？
- A（推荐）：正费率、单标的、极小名义值、硬上限、全量录包，且 discovery 完成后由用户单次批准。
- B：本里程碑完全跳过线上，仅 fake UI + discovery。
- C：放宽到多标的/较大金额。
- 取舍：A 平衡验证与风险；B 最保守；C 风险高。

### Q4. 技术栈与存储确认？
- A（推荐）：Python asyncio + TypeScript/React + SQLite（先作原始事件/快照存储）。
- B：换其他后端语言/换 Postgres。
- 取舍：A 与 PRD 一致、上手快；B 需重估。

### Q5. 老 FMZ 策略文件如何处置？
- A（推荐）：**只读参考 + 脱敏/纳入 .gitignore**，不导入 docs/code。
- B：保留明文在仓库。
- C：从仓库移除。
- 取舍：A 兼顾参考价值与隐私；B 有 PII 泄露风险；C 最干净但失参考。

## 10. 最终建议

1. **把 PM 负费率借币机制列为 discovery 第一优先级**，PRD 所列 PAPI 借币端点我未能核实，疑不存在或语义不同。
2. **第一阶段不碰真实下单**，只交付仓库骨架 + discovery + 数据契约 + 核心域逻辑 + 只读适配样本 + UI 精修。
3. **冻结一个显式执行器状态机**，把「平滑开仓/兜底/单边成交」全部枚举化，默认不自动强下、不自动补腿。
4. **强制幂等 `newClientOrderId`**，503/超时一律按 clientOrderId 查询，禁止金额盲重发。
5. **启动 fail-closed 断言**：PM 账户 + 单向模式 + 禁提现 key，否则拒绝继续。
6. **reconciler 先做单位归一**（contract multiplier → base 数量/USDT 名义），再判绝对+相对容差。
7. **账目全程 Decimal**，字段标 `observed`/`derived`，返佣/容差只作可配置默认并标「假设」。
8. **bStock 与负费率在确认前只采样不下单**，UI 标灰，不误导操作员。
9. **老 FMZ 策略只读参考并脱敏**，因其含真实 PII 且账户模型与 PM 不一致。
10. **所有写操作显式二次确认**，UI 常驻「禁止提现 · 人工确认 · 不自动平仓」，绝不自动平仓或补腿。
