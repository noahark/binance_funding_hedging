# Kimi 2.7 阶段设计方向稿

## 1. Baseline 理解

本项目不是自动套利机器人，而是面向 **Binance Portfolio Margin（PM）账户** 的 **人工触发式资金费率对冲工作台**。核心目标是把旧版 FMZ 逐仓杠杆脚本中的套利思路，迁移到一个有明确风险控制、完整记账、可审计执行路径的新系统上。

不可违背的产品原则：

- **开平仓必须由人工触发并确认**，系统不能基于资金费率阈值自动开仓或平仓。
- **只使用市价单（market order）**，websocket 盘口仅用于展示价差/滑点预估，不做限价单。
- **双腿不匹配时只高亮提醒**，不自动补腿、不平仓。
- **收益归因必须真实**：资金费、手续费、BNB 抵扣、返佣折扣、借币利息都要计入。
- **USDT 计价、单向持仓模式** 是 v0.1 的硬边界。
- **bStocks 只支持正费率套利**（空永续 + 买现货），因为不能借币卖现货。

## 2. 你认为当前 PRD 已经明确的内容

以下事项我认为已经清晰到可以进入设计/开发：

- 账户与市场假设：Portfolio Margin、USDⓈ-M 永续、单向持仓、仅 USDT quote。
- 资产分类 4 个类别（`CRYPTO_BIDIRECTIONAL`、`CRYPTO_LONG_SPOT_ONLY`、`BSTOCK_LONG_SPOT_ONLY`、`PERP_ONLY`）及过滤逻辑。
- 正/负费率下的双腿方向：
  - 正费率：永续做空 + 现货/杠杆买入。
  - 负费率：永续做多 + 借币后卖出现货。
- 手动开仓流程的 14 步，包括总名义值、轮数、最低名义值 2% uplift、余数合并。
- 仅支持 market order；execution 是 round-based。
- 持仓监控需要对比的字段：方向、名义值、借币、数量差、名义差、数据时间戳。
- 费用公式：`rebate_adjusted_fee = actual_fee_after_bnb_discount * 0.6`，以及 net funding result 的扣减项。
- 接口发现清单（PAPI REST、spot fallback、UM market data、websocket streams）。
- UI 四大屏幕：Overview、Opportunities、Manual Open、Profit & Fees。
- 风险控制清单：API key 禁提现、per-order/per-symbol/total notional 可配置、borrow 失败即停、leg mismatch 高亮。
- 技术栈倾向：Python asyncio 后端、TypeScript/React 前端、SQLite 起步。
- Phase 1/2/3  acceptance criteria 已有粗略分层。

## 3. 你认为当前 PRD 仍不明确或有风险的内容

### 3.1 "平滑开仓" 的触发与兜底规则未定义

- **问题**：PRD 说"在可接受价差/滑点范围内用 market order 异步同时开双腿"，但没定义：
  - 价差/滑点阈值是多少？由用户输入还是系统默认？
  - 等待多久没触发就执行"立即对冲兜底"？
  - "异步同时"失败时（一条腿成交、一条腿被拒/未响应）如何处理？
- **为什么重要**：这是执行器最核心的状态机，规则不清会导致实现时各模型理解不一致，也会直接影响真实资金风险。
- **建议如何处理**：第一阶段先不实现真实平滑开仓，只做一个 **paper/smoothed-open simulator**，用历史或实时 depth 数据判定"是否满足条件"，输出"会/不会执行"的审计日志；同时让用户明确阈值与兜底时间。

### 3.2 负费率套利在 PM 下的借币-卖出-还币链路不清晰

- **问题**：
  - `POST /papi/v1/marginLoan` 借到的币在哪个账户？是否需要手动划转？
  - `POST /papi/v1/margin/order` 卖出后，负债如何与永续多头匹配显示？
  - 平仓时是先买币 `repayLoan`，还是先平永续再处理现货负债？
  - bStock 不支持借币的判断标准是什么？如何程序化识别？
- **为什么重要**：负费率套利比正费率复杂一个数量级，借币链路错了会直接造成账户风险敞口。
- **建议如何处理**：第一阶段只做正费率场景；负费率流程必须先完成只读接口 discovery（`maxBorrowable`、`marginLoan` 记录、`repayLoan` 记录、`marginInterestHistory`），并在 fake UI 中把负债-还币流程画清楚再开发。

### 3.3 现货 fallback 路径与 PM 统一视图的关系

- **问题**：PRD 提到如果 PM margin route 不可用则走 normal spot。但 PM 账户下的"普通现货"与 margin 账户的余额、持仓如何在 UI 里统一展示？是否需要 `transfer`？
- **为什么重要**：v0.1 若混用 spot 与 margin，持仓对账会出错。
- **建议如何处理**：v0.1 优先只支持 PM margin route；spot fallback 明确标记为"延迟到 Phase 3 以后"。

### 3.4 返佣、BNB 抵扣的"实际值"与"默认值"冲突

- **问题**：PRD 默认 spot/futures rebate 都是 40%，并直接乘以 0.6。但真实账户的 rebate 取决于 VIP tier、邀请关系、BNB 持仓等；`GET /papi/v1/um/commissionRate` 与 spot commission rate 返回的才是真实 maker/taker 费率。
- **为什么重要**：用固定 40% 会严重失真，且 `COMMISSION_REBATE` income 是事后到账，不能与开仓时预估手续费混用。
- **建议如何处理**：
  - 预估手续费 = 名义值 × taker 费率 ×（1 - BNB burn discount 开关状态）。
  - 实际成本从 fill 的 `commission` 字段读取。
  - 返佣单独作为 funding ledger 的一行 `COMMISSION_REBATE` 收入处理，不直接在开仓预估里扣减。

### 3.5 腿不匹配容忍阈值未定义

- **问题**：PRD 只说"Quantity difference exceeds configured tolerance"，但没给默认值或计算方式。
- **为什么重要**：永续与现货的合约乘数、最小精度、部分成交都会导致微小差异，阈值太紧会频繁误报，太松会漏掉真实风险。
- **建议如何处理**：先以"名义值相对差 > 1% 或 数量绝对差 > max(stepSize) × 2"作为可配置默认值，在接口 discovery 后用真实 fill 数据校准。

### 3.6 HTTP 503 "unknown execution state" 的处理策略不完整

- **问题**：PRD 要求不能简单视为失败，需要通过 user data stream 或 order query 确认。但没有定义：
  - 最多查询几次？
  - 查询间隔多久？
  - 如果一直查不到（网络分区、listenKey 失效）怎么办？
- **为什么重要**：503 处理不当会导致重复下单或永久悬挂订单。
- **建议如何处理**：第一阶段只记录 503 事件到审计日志并进入 `DEGRADED` 状态，明确禁止自动重试；由用户手动确认或取消。

### 3.7 Websocket 本地 order book 维护存在序列一致性风险

- **问题**：PRD 要求结合 `GET /api/v3/depth` snapshot 与 websocket depth diff 维护本地 book。如果 snapshot 与 diff 的 lastUpdateId 对不上，会出现 book 错位。
- **为什么重要**：滑点预估错误会导致用户在不利价差下确认开仓。
- **建议如何处理**：第一阶段先用 REST snapshot 做"快照式"spread 显示，websocket diff 作为增量刷新但不做唯一依据；book 维护模块单独写单测。

### 3.8 收益统计中 "estimated_slippage_cost" 的定义模糊

- **问题**：PRD 把 estimated_slippage_cost 放入 net result 公式，但没说是按下单前 estimated 计算，还是按实际成交价与 mark price 的差计算。
- **为什么重要**：这会影响盈亏数字，且无法与 Binance 账单对账。
- **建议如何处理**：
  - "预估滑点"仅用于开仓前展示。
  - "实现滑点"用实际 fill 价格与当时 mark price/index price 的差计算，作为 accounting 中独立字段，不直接扣减 funding result。

### 3.9 bStocks 的交易规则与账户可用性

- **问题**：PRD 假设 bStocks 不可借币，但没有说明如何识别 bStock、其 spot 交易对是否支持 PM margin、交易时间是否与加密货币不同。
- **为什么重要**：bStocks 可能受传统市场交易时间限制，开盘时资金费已结算，套利窗口可能不存在。
- **建议如何处理**：第一阶段把 bStocks 标记为"待验证"，仅保留在资产分类模型中，不进入 executable 列表。

### 3.10 数据持久化 schema 尚未设计

- **问题**：PRD 提到 SQLite 是 likely candidate，但没有 schema 设计。
- **为什么重要**：execution、fill、commission、borrow、repay、funding income 的关联关系是审计基础。
- **建议如何处理**：第一阶段输出一份不可变的 **事件模型 schema**（Events as source of truth），所有状态通过事件回放生成。

## 4. 关键技术设计建议

### 4.1 后端主策略服务

- 用 Python `asyncio` 单进程事件循环即可，不要过早引入分布式。
- 核心是一个 **事件溯源（Event Sourcing）风格** 的状态机：
  - 事件：`PlanCreated`、`DepthSubscribed`、`OrderSubmitted`、`OrderFilled`、`BorrowRequested`、`BorrowConfirmed`、`FundingReceived`、`MismatchDetected`。
  - 聚合根：`ExecutionPlan` 和 `Position`。
- 所有状态变更必须落盘到 append-only event store，便于回放和审计。

### 4.2 Binance 适配层

- 分层：
  - `HttpClient`：处理签名、recvWindow、rate-limit header 记录、503 特殊处理。
  - `PapiClient` / `SpotClient` / `FapiClient`：按产品线封装端点。
  - `BinanceAdapter`：把原始响应转成内部 domain model。
- 每个端点首次调用后把响应样本写入 `reports/api-samples/`，文件名带时间戳，并自动 redact API key。
- 503 处理：返回 `ExecutionStatus.UNKNOWN`，写入事件日志，禁止自动重试。

### 4.3 资产筛选与交易规则归一化

- 独立模块 `AssetClassifier`，输入：
  - `/fapi/v1/exchangeInfo`
  - `/api/v3/exchangeInfo`
  - `GET /papi/v1/um/account`（确认 one-way mode）
  - `GET /papi/v1/margin/maxBorrowable`（抽样验证借币）
- 输出统一结构：
  - symbol, baseAsset, quoteAsset
  - classification
  - route (`PM_MARGIN` / `SPOT_FALLBACK` / `NONE`)
  - per-leg minNotional, stepSize, tickSize
  - borrowable flag
- 所有数值用 `Decimal`。

### 4.4 手动开仓与平滑开仓执行器

- 执行器状态机：
  - `DRAFT` → `AWAITING_CONFIRMATION` → `SUBSCRIBING_DEPTH` → `WAITING_FOR_SPREAD` → `EXECUTING` → `FILLED` / `DEGRADED` / `FAILED`
- "平滑"逻辑第一阶段用 **模拟/回放模式** 实现：
  - 订阅 depth，实时计算 spread。
  - 当 spread ≤ threshold 持续 N 秒或等待超过 T 秒触发兜底。
  - 输出"would execute at price X/Y"日志，不真正下单。
- 真正下单放在 Phase 3，且必须有用户二次确认。

### 4.5 持仓一致性检测

- 独立 `ReconciliationService`，定时对比：
  - UM position notional vs spot/margin balance notional
  - 永续方向 vs 现货方向
  - 借币数量 vs 现货空头数量（负费率场景）
  - 数据时间戳 freshness
- 输出 `Mismatch` 记录，带类型和严重级别，只写入事件并高亮 UI，不触发交易动作。

### 4.6 收益与成本归因

- 事件模型：
  - `FundingIncomeRecorded`（来自 `/papi/v1/um/income` `FUNDING_FEE`）
  - `CommissionPaid`（来自 fill 的 `commission` 和 `commissionAsset`）
  - `CommissionRebateReceived`（来自 income `COMMISSION_REBATE`）
  - `BorrowInterestAccrued`（来自 `marginInterestHistory`）
- 计算：
  - net per symbol = funding income - actual commission paid - borrow interest
  - "rebate-adjusted fee" 仅用于预估展示，不作为真实净盈亏。
- BNB 抵扣：读取 `GET /papi/v1/um/feeBurn`，若开启则实际 commission 已按 BNB 折扣后计算，无需额外扣减；若 commission asset 是 BNB，按当时 BNB/USDT 价格换算（取 mark price 或最近成交）。

### 4.7 前端 UI 信息架构

- 现有 `prototypes/fake-ui/index.html` 已经覆盖了 4 个主要视图，结构良好。建议：
  - 保留左侧导航与"禁止提现 · 人工确认 · 不自动平仓"的常驻提示。
  - Overview 增加"事件日志"小面板，显示最近 5 条系统事件（如"Borrow failed"、"503 UNKNOWN"）。
  - Manual Open 增加"模拟执行"模式切换，让用户先看到在什么条件下会触发下单。
  - 所有金额用 monospace 字体并统一显示精度。
  - 负费率交易对在没有完成借币预检前，开仓按钮 disabled。

### 4.8 测试与线上小资金验证策略

- 单元测试优先覆盖：
  - 交易规则归一化（lot size、min notional、step size）
  - per-round notional 计算与 uplift
  - 持仓对账逻辑（各种 mismatch 场景）
  - funding income 与 commission 归因
- 接口 discovery 阶段：先用 public endpoint 获取 exchangeInfo/premiumIndex/depth，再用只读 API key 获取 account/position/income。
- 小资金真实交易前必须先通过：
  - 只读接口样本验证
  - fake UI 全链路走通
  - paper trading（模拟下单）跑通一个完整的 funding interval

## 5. 第一阶段开发范围建议

目标：**在不下真实订单的前提下，建立可审计、可测试、可演示的工作台骨架。**

建议包含：

1. **Fake UI 完整化**
   - 基于现有 `prototypes/fake-ui/index.html` 补全 Manual Open、Profit & Fees 的完整交互态。
   - 所有按钮可点击，但下单按钮弹出"模拟模式：不会发送真实订单"提示。
2. **交易规则归一化模块 + 单元测试**
   - 解析 `/fapi/v1/exchangeInfo` 与 `/api/v3/exchangeInfo`。
   - 输出统一 `TradingRules` 对象，含 minNotional、stepSize、marketLotSize。
   - 单测覆盖 BTC/ETH/小币种边界。
3. **核心 Domain Model 与状态机**
   - `ExecutionPlan`、`Leg`、`Position`、`FundingLedger`、`Mismatch`。
   - `PlanLifecycle` 状态机（DRAFT → ... → FILLED/DEGRADED/FAILED）。
   - 单测覆盖状态流转。
4. **只读接口 Discovery 脚本**
   - Public：exchangeInfo、fundingRate、premiumIndex、depth。
   - Private（需 API key）：account、balance、um/account、um/positionRisk、um/income、margin/maxBorrowable、margin/marginInterestHistory。
   - 所有响应样本写入 `reports/api-samples/`，并 redact 凭证。
5. **模拟执行器（paper mode）**
   - 订阅实时 depth（可回退到 REST snapshot）。
   - 计算 spread、预估滑点、预估手续费。
   - 当满足用户设定条件时输出 "would execute" 事件日志。
   - 不产生真实订单。

不包含：真实下单、borrow、repay、503 重试、完整 accounting UI。

## 6. 不建议第一阶段做的内容

1. **真实 websocket 驱动的自动/半自动下单**：在阈值与兜底规则未明确、503 策略未明确前，真实下单风险过高。
2. **负费率套利全流程**：借币-卖出-还币链路需要先完成 discovery 和 fake UI 流程设计。
3. **bStocks 真实交易**：交易规则、借币限制、交易时间均待验证。
4. **完整的事件持久化数据库**：先以 JSONL/append-only 文件存储事件，schema 稳定后再迁入 SQLite。
5. **503 自动恢复/重试逻辑**：第一阶段只记录和报警，不自动处理。
6. **平仓执行器**：PRD 对平仓流程描述不足，先聚焦开仓模拟与监控。
7. **多 quote/多持仓模式**：超出 v0.1 边界。
8. **返佣的事后归因自动化**：需要先积累真实 `COMMISSION_REBATE` income 样本。

## 7. 验收标准建议

### 7.1 文件级产物

- `reports/agent-runs/2026-07-initial-direction/20-implementation.md` 或等效文件记录第一阶段实现范围。
- `reports/api-samples/` 下存在带时间戳的以下样本（public + private 只读）：
  - `fapi_v1_exchangeInfo_*.json`
  - `api_v3_exchangeInfo_*.json`
  - `papi_v1_account_*.json`
  - `papi_v2_um_account_*.json`
  - `papi_v1_um_positionRisk_*.json`
  - `papi_v1_um_income_*.json`
  - `papi_v1_margin_maxBorrowable_*.json`（至少一个可借币种）
  - `api_v3_depth_*.json` 或 websocket depth snapshot
- 后端代码存在 `domain/`、`adapters/binance/`、`services/` 目录，且每个目录都有对应单测。

### 7.2 测试或模拟输出

- `pytest` 或类似测试套件通过，覆盖：
  - 交易规则解析（≥10 个交易对样本）
  - per-round notional 计算（含 uplift 与余数合并）
  - 持仓对账（≥6 种 mismatch 类型）
- 模拟执行器日志：展示至少一个 symbol 在 1 分钟 depth 数据下触发/未触发"would execute"的判断。

### 7.3 UI 验收项

- Fake UI 4 个视图均可访问，无占位符 "TBD"。
- Manual Open 页面必须显示：
  - 修正后的 per-round notional
  - 现货/期货 route 标签
  - 是否支持负费率
  - 实时 spread 与预估手续费
  - "模拟模式"横幅
- Overview 持仓对账表必须高亮至少一种 mismatch 样例。

### 7.4 Binance 接口 discovery 样本验收项

- 样本中必须能提取出至少 3 个可双向套利的 CRYPTO 交易对。
- 样本中必须能提取出至少 1 个 bStock 或不可借币的交易对，并正确标记为 `*_LONG_SPOT_ONLY`。
- 样本中必须展示 UM position risk 返回的字段结构，包括 `positionAmt`、`notional`、`liquidationPrice`。
- 样本中必须展示 funding income 的 `incomeType == FUNDING_FEE` 行，字段包括 `symbol`、`income`、`asset`、`time`、`tranId`。

### 7.5 明确不能只靠模型口头声明完成

- 必须提交 git diff 或 patch。
- 必须提交测试命令的 stdout（`60-test-output.txt` 或 CI 日志）。
- 必须提交接口样本文件路径清单。
- 必须提交 fake UI 的截图或运行命令输出（可 `python -m http.server` 本地访问）。

## 8. 与现有 PRD 的冲突或修订建议

### 8.1 Phase 1 Acceptance Criteria 过于宽泛

- **原问题**："UI fake prototype shows all required screens with realistic sample data. No real trading code is required." 这已经部分完成，且没有限定接口发现与 domain model。
- **建议改成**：
  > Phase 1 delivers: (a) complete fake UI for all four screens in simulation mode; (b) read-only Binance API discovery with timestamped JSON samples; (c) trading-rule normalizer with unit tests; (d) core domain model and execution-plan state machine with unit tests; (e) paper-mode smoothed-open simulator that logs would-execute decisions against live depth but does not submit orders.
- **理由**：让 Phase 1 有可验收的文件、测试、样本，而不是只剩 UI。

### 8.2 返佣计算方式可能误导

- **原问题**：默认 40% rebate 并直接乘以 0.6 得到 rebate-adjusted fee。
- **建议改成**：
  - 预估手续费 = 名义值 × taker rate × (1 - BNB burn discount if enabled)。
  - 真实手续费从 fill 读取。
  - `COMMISSION_REBATE` 作为独立收入事件计入 funding ledger。
- **理由**：真实账户的 commission rate 和 rebate 结构差异很大，固定折扣会失真。

### 8.3 平仓流程缺失

- **原问题**：PRD 详细描述开仓，但对平仓（无论是用户手动触发还是部分减仓）流程描述极少。
- **建议改成**：新增 "Manual Close Flow" 章节，明确：
  - 用户输入平仓轮数/数量。
  - 负费率场景必须先买币 `repayLoan` 还是先平永续？
  - 系统是否允许部分平仓？
  - 平仓后如何更新 position 与 ledger？
- **理由**：平仓是完整生命周期的必要部分，不应延迟到实现阶段才设计。

### 8.4 "estimated_slippage_cost" 定义

- **原问题**：直接扣减 net funding result，但无法与 Binance 对账。
- **建议改成**：
  - 新增"实现滑点"字段，按 fill price 与 mark/index price 差计算。
  - "estimated_slippage_cost" 仅用于开仓前展示，不计入净盈亏。
- **理由**：净盈亏必须与 Binance 资金流水可对账。

## 9. 需要用户拍板的问题

### 9.1 平滑开仓的触发与兜底规则

- **选项 A**：设定一个固定 spread 阈值（如 0.02%），满足即双开；若 60 秒内未满足，直接按市价兜底。
  - 取舍：简单，但可能在极端行情下兜底滑点大。
- **选项 B**：设定 spread 阈值 + 时间加权恶化容忍（如每多等 10 秒，阈值放宽 0.005%）。
  - 取舍：更灵活，但实现复杂。
- **选项 C**：第一阶段只做"实时 spread 展示"，用户手动点击"立即执行"，没有自动兜底。
  - 取舍：最保守，完全规避自动执行风险，但操作体验下降。

### 9.2 负费率场景是否纳入 Phase 2

- **选项 A**：Phase 2 包含负费率全流程（借币、卖出、监控、还币）。
  - 取舍：进度快，但借币链路风险高。
- **选项 B**：Phase 2 只做正费率真实交易；负费率延后到 Phase 3，期间只做接口 discovery 与 fake UI 流程。
  - 取舍：更稳妥，优先验证最简单的闭环。
- **选项 C**：同时开发，但负费率默认 disabled，需用户显式开启。
  - 取舍：折中，但增加测试矩阵。

### 9.3 第一阶段是否允许使用真实 API key 进行只读 discovery

- **选项 A**：允许，只读权限，不下单，样本 redact 凭证。
  - 取舍：能拿到真实 account/position/income 数据，验收价值高。
- **选项 B**：只允许 public endpoint discovery，private 接口用本地 mock/fixture。
  - 取舍：更安全，但会缺失真实账户结构样本。
- **选项 C**：允许，但 API key 由用户单独提供且不出现在任何 report 中。
  - 取舍：与 A 类似，更强调密钥隔离。

### 9.4 收益统计中 BNB 抵扣的换算方式

- **选项 A**： commission asset 为 BNB 时，按成交瞬间 BNB/USDT mark price 换算。
  - 取舍：实时性强，但需要额外订阅 BNB price。
- **选项 B**：按该 funding interval 内的平均 BNB/USDT 价格换算。
  - 取舍：更稳定，但与实际成本有偏差。
- **选项 C**：不换算，在 UI 中同时显示"USDT 成本"与"BNB 成本"两列。
  - 取舍：最直观，但 net result 不唯一。

### 9.5 平仓流程是否需要在第一阶段设计文档

- **选项 A**：是，第一阶段必须输出平仓流程设计文档，即使不实现。
  - 取舍：提前发现架构问题。
- **选项 B**：否，先聚焦开仓，平仓在 Phase 2 设计。
  - 取舍：减少第一阶段范围，但可能遗漏数据模型约束。

## 10. 最终建议

- 第一阶段聚焦 **"接口发现 + 交易规则归一化 + 核心 domain model + fake UI 完整化 + paper-mode 模拟执行"**，绝不触碰真实下单。
- 先只做 **正费率 CRYPTO_BIDIRECTIONAL** 场景，把最简单的闭环跑通；负费率、bStocks 延后。
- 把 **事件溯源/append-only event log** 作为数据模型基础，所有状态变更可回放、可审计。
- 费用归因必须以 **实际 fill commission** 和 **income history** 为准，固定 40% rebate 只作 UI 预估默认值。
- **503 与未知执行状态** 第一阶段只记录报警，不自动重试，避免重复下单。
- websocket depth 本地 book 维护先降级为 **REST snapshot + 增量刷新**，不要把它作为唯一 truth。
- 每条接口调用第一次都要落盘到 `reports/api-samples/`，并自动 redact 凭证。
- 单元测试必须覆盖交易规则解析、per-round 计算、持仓对账，不能等到真实交易才验证。
- PRD 需要补充 **平仓流程设计** 和 **平滑开仓触发/兜底规则**，否则实现阶段会产生分歧。
- 用户必须拍板：平滑开仓规则、负费率是否进入 Phase 2、是否允许真实 API key 只读 discovery。
