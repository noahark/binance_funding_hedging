# grok-build 阶段设计方向稿

## 1. Baseline 理解

本项目目标是构建一个**手动触发**的 Binance Portfolio Margin (统一保证金) 下 USDT 计价永续合约与现货/杠杆现货的资金费率对冲工作台。核心是帮助操作者发现资金费率机会、规划执行、人工确认后以市价单“平滑”同时开立双腿（正费率：永续做空 + 现货买入；负费率仅限可借币的 CRYPTO_BIDIRECTIONAL：永续做多 + 借币卖出现货），并持续跟踪持仓匹配度、真实全成本收益（funding + 手续费 + BNB 抵扣 + 返佣 + 借币利息 + 滑点估算），仅做高亮提醒而不自动补腿或平仓。

不可违背的产品原则（从 PRD 提取并确认）：
- 开平仓完全由人工触发，v0.1 无任何自动开/平/紧急平/补腿逻辑。
- 平滑开仓仅在人工点击后启动 websocket 深度订阅，用于展示价差/滑点估算，实际仍用 market order 按轮执行。
- 仅 USDT 计价、单向持仓模式、Portfolio Margin 账户。
- bStock 等不可借品种仅支持正费率。
- 完整会计必须反映真实成本，不能只看毛 funding。
- 所有接口行为以 llms-full.txt + PRD 中列出的端点与约束为准；实际响应以 discovery 实测为准。
- 风险控制前置：无提现权限 key、每单/每 symbol/总 notional 上限、借币失败必须阻断后续下单。

当前项目处于 harness 初始阶段：PRD 已有详细 v0.1 描述，但 architecture、DEVELOPMENT_GUIDE、ROADMAP、DECISIONS 均为 TBD；reports 中仅存在模板与 harness 自身文件；第一个手动 loop 尚未启动。本次是五模型独立方向稿收集环节。

## 2. 你认为当前 PRD 已经明确的内容

- v0.1 严格手动执行边界与非目标（无 auto open/close/repair/emergency close）。
- 资产分类五类（CRYPTO_BIDIRECTIONAL、CRYPTO_LONG_SPOT_ONLY、BSTOCK_LONG_SPOT_ONLY 等）及对应的正/负费率支持规则。
- 执行流程：选择 symbol → 输入总 notional + rounds → 规则归一化 + 2% uplift + 余量合并 → 人工点击 open → ws 深度订阅展示 → 二次确认 → 按轮 market 下单（负费率先 borrow）。
- 必须记录的原始 JSON、funding ledger 字段、rebate 缺省 40% 以及 net 会计公式。
- UI 必须覆盖的四个核心视图：Overview holdings（含 mismatch 高亮）、Opportunity table、Manual open 计划与确认、Profit & fees 明细。
- 关键 Binance 端点家族已在 PRD “Binance Interface Baseline” 中列出（papi 系、fapi exchangeInfo、premiumIndex、marginLoan、um/income、listenKey、depth ws 等），并明确了 503 未知状态处理原则、recvWindow ≤5000ms 缺省、rate limit 头记录要求。
- 技术方向偏好：Python asyncio + Decimal 后端、TS/React 前端、local DB（SQLite 候选）。
- Phase 1~3 验收大纲已存在：fake UI → discovery samples → 小资金手动正费率实盘验证。
- 风控硬约束（API key 权限、notional caps、借币前置阻断、mismatch 只提醒）。

以上已足以支撑后续 stage scope 拆分与设计输入。

## 3. 你认为当前 PRD 仍不明确或有风险的内容

**问题**：Portfolio Margin 下现货腿的实际路由（papi margin order vs 普通 spot /api/v3/order）与统一保证金计价、借币限额、交叉影响尚未实测确认。PRD 优先级描述为“Portfolio Margin / cross-margin spot → 普通 spot 兜底”，但实际账户中 margin route 是否总是可用、是否自动计入 PM 统一风险、bStock 是否可走 margin 腿，均未知。

**为什么重要**：路由错误会导致持仓不进统一保证金、借币失败、或手续费/利息会计路径完全不同，直接影响 leg 对齐与 net P&L 计算。负费率 hedge 尤其依赖 borrow 前置。

**建议如何处理**：第一阶段必须用 discovery 脚本对真实只读 key（或公开 endpoint）采集 GET /papi/v1/margin/maxBorrowable、/papi/v1/account、/papi/v1/margin/marginLoan、普通 spot exchangeInfo + 账户余额等样本；分类器必须把“实际可借 + 实际可下 margin/spot 订单”作为动态输入，而非静态假设。

**问题**：websocket 深度书构建与滑点估算的精确语义与容错未定义。PRD 说“订阅现货和合约 websocket 盘口，在可接受价差/滑点范围内用 market order 异步同时开双腿”，但“可接受”阈值由谁定？本地 order book 如何维护（snapshot + delta 丢包处理、重连策略、top-N 深度是否足够）？市价单实际成交滑点与 ws 展示估算的偏差如何记录？

**为什么重要**：这是平滑开仓的核心用户体验与风险可视化。估算偏差大或 book 脏数据会导致操作者误判，实际成交成本远超预期。异步同时下单还存在腿时序差导致短暂 mismatch。

**建议如何处理**：先在 discovery + fake 阶段用录制样本或公开 depth 流构建可重放的 book 维护器；定义“展示用估算”与“执行前置检查”两个不同严格度；执行器必须在每轮下单前后记录实际 depth snapshot 作为证据。mismatch tolerance 也要在实盘小资金后用数据校准。

**问题**：bStock / tokenized securities 的具体交易对、是否支持 PM margin 路由、funding 结算是否与其他 perp 一致、是否可借，PRD 仅做定性说明。

**为什么重要**：直接影响分类器输出与“正费率 only”决策。若误把不可交易 bStock 放进 opportunity，会导致执行失败或风控绕过。

**建议如何处理**：discovery 阶段必须用 /fapi/v1/exchangeInfo + /api/v3/exchangeInfo + 实际 symbol 列表做启发式 + 人工标记；把 bStock 作为显式配置或从 symbol 名称/权限字段检测的输出；所有分类结果必须带“来源样本时间戳”。

**问题**：手续费、BNB 抵扣、返佣、借息的完整归因在真实响应中的字段路径与 timing 未锁定。PRD 给出了会计公式与 ledger 要求，但实际 UM commissionRate、feeBurn 状态、trades 中的 commission asset、income 中的 funding 事件、marginInterestHistory 的结构在不同 VIP/region 可能有差异。

**为什么重要**：收益统计是产品核心价值。若少算或错算 BNB 折扣/返佣，会产生错误盈亏信号和错误对冲决策。PRD 明确说“不要忽略”这些。

**建议如何处理**：discovery 必须采集并保存：/papi/v1/um/commissionRate、/papi/v1/um/feeBurn、myTrades、um/income、marginInterestHistory 的原始样本；会计模块先做“从样本计算”的纯函数 + fixture 测试；默认 rebate 40% 必须可被实际 commissionRate 覆盖或 override。

**问题**：执行状态机与并发语义模糊。是否支持同时为多个 symbol 维护 open plan？ws 订阅生命周期？执行中用户是否可取消？503 后如何确认（PRD 提到 query 或 user stream），以及 rounds 之间是否有强制延迟/对齐检查？

**为什么重要**：操作者误操作或系统状态不一致会导致资金占用、双腿错位、或重复下单。

**建议如何处理**：stage 设计必须显式画出状态机（idle → planning → ws-live → awaiting-confirm → executing → held/mismatch）；单 symbol 锁或显式多 plan 支持需在第一阶段后由用户决定；执行器必须在每笔订单后强制 query 确认状态，永不只信 POST 返回。

**问题**：listenKey / PM user data stream 的可靠性、事件完整性（ACCOUNT_UPDATE 是否总包含 funding 变化？executionReport for margin leg 是否可靠）、以及作为 holdings 主要来源还是仅 supplement 轮询的策略未定。

**为什么重要**：实时 holdings 与 mismatch 检测依赖它；若 stream 掉线或事件不全，会导致 UI 过时。

**建议如何处理**：discovery 阶段必须尝试创建 listenKey、订阅并记录样本事件；后端必须实现“stream + 定期重连 + 兜底轮询 positionRisk + margin balance + loans”的混合策略；所有 holdings 快照必须带数据新鲜度时间戳。

**其他风险**：
- recvWindow 5000ms 在高延迟或 clock skew 下是否够用。
- 市场剧烈波动时 market order 实际 notional 与计划偏差，是否需要 per-round 重新检查。
- 小资金实盘验证的“可接受风险”阈值完全由用户定义，当前 PRD 未量化。

## 4. 关键技术设计建议

**后端主策略服务**：
- 纯 asyncio + anyio，核心循环是“状态机驱动”而非事件循环直接混杂业务。
- 领域模型全部使用 Decimal（quantize 到 exchange stepSize / tickSize 规则）。
- 清晰分层：api adapters（只负责签名/请求/原始记录）、domain services（classifier、planner、accountant、reconciler）、execution（仅在显式人工确认后激活，且可被 feature flag 完全禁用）。
- 每一次外部调用（REST 或 WS）都必须通过统一 recorder 写 reports/api-samples/ 或 runtime event log，文件名带 UTC ts + endpoint 简名 + request hash。

**Binance Portfolio Margin / UM / Spot / websocket 适配层**：
- 两个主要 client：PMApiClient（papi base + 签名）、SpotApiClient（公共或签名）。
- 公共 market data 可复用。
- 必须实现：签名（HMAC SHA256 + query + body）、timestamp + recvWindow 注入、rate limit 头捕获与 backoff（至少记录，不一定全自动节流在 v0.1）。
- WS：独立连接管理器，支持公共 depth（<symbol>@depth 或 @depth@100ms）、PM user stream（wss://fstream.binance.com/pm/ws/<listenKey>）。
- 深度书维护器：必须支持 REST snapshot + WS delta 合并，检测丢包/序列号断层并触发重置；仅需 top 5-10 档用于 spread/slippage 估算。
- 503 + unknown execution 路径必须先做 GET order 查询或等待 user stream 确认，绝不重试 market order。

**资产筛选与交易规则归一化**：
- 启动 + 每 8h 刷新：fapi/v1/exchangeInfo + api/v3/exchangeInfo + fapi/v1/premiumIndex + papi 账户相关。
- 规则提取器必须解析 LOT_SIZE、MARKET_LOT_SIZE、MIN_NOTIONAL、NOTIONAL、PRICE_FILTER 等，输出可直接用于 quantity 舍入与 notional 校验的结构。
- 最小 notional 取“双腿中最严格值” * 1.02 uplift；数量必须 round 后再反算 notional 校验，防止舍入后不达标。
- 分类结果必须携带“数据版本”（exchangeInfo timestamp + 样本文件路径）。

**手动开仓与平滑开仓执行器**：
- 仅当人工二次确认后才实例化执行上下文。
- 执行上下文持有：计划、当前 round、ws book 快照引用、已执行 fills 列表。
- 每轮：更新 book → 计算预估 spread/slippage → 如果超过用户阈值则暂停等人工；否则下 futures market + margin/spot market（异步但记录先后顺序）。
- 负费率：borrow 必须在第一轮任何 market order 之前成功确认（POST /papi/v1/marginLoan + 轮询记录）。
- 所有 fills 必须通过 GET /order 或 myTrades 二次确认数量与 commission。
- 部分成交处理：当前 round 标记 degraded，继续下一 round 或等人工决定。
- 执行完成后把控制权交还 holdings / reconciliation，不自动启动任何后续动作。

**持仓一致性检测**：
- 权威来源优先级建议：PM user stream ACCOUNT_UPDATE + ORDER_TRADE_UPDATE → 定时 GET /papi/v1/um/positionRisk + /papi/v1/margin/account 或 balance → 必要时 GET /papi/v1/margin/marginLoan。
- 比较维度：方向、数量（四舍五入后）、名义价值、borrow 状态。
- Mismatch 类型要可枚举（FUTURES_ONLY、SPOT_ONLY、DIRECTION_MISMATCH、QTY_DELTA_ABOVE_TOL、BORROW_WITHOUT_LONG 等）。
- UI 只高亮 + 显示 delta 与 last update 时间；后台保留历史 mismatch 事件供审计。

**收益与成本归因**：
- 事件源优先：um/income（funding）、marginInterestHistory、myTrades / um/trades（commission）、feeBurn 状态。
- 会计为纯函数：给定一组事件 + 当时 position notional + 费率表 → 计算 gross funding、rebate_adjusted_fee、borrow_interest、est_slippage、net。
- 必须保留到每一个 funding 结算事件的 raw payload 引用（文件路径或 db id）。
- BNB 抵扣：如果 commission asset = BNB 且 feeBurn 开启，则按实际扣减后的 fee 计算；否则按 USDT 路径。
- 返佣：先用实际 /commissionRate 返回值，若不可用再用 PRD 缺省 40%（0.6 系数）。

**前端 UI 信息架构**：
- 侧边导航 + 主要内容区；状态用 badge 清晰展示（route: PM-MARGIN / SPOT、negative support: yes/no、data freshness）。
- Opportunity table：可排序过滤 funding rate、classification、最小 notional、next funding。
- Manual open 面板：表单（notional, rounds, max-slippage）→ 实时计算 per-round + 修正后数量 + 预估总成本（含 fee+borrow 估算）→ 按钮触发 ws 订阅 → 展示 live spread 仪表 + “确认执行”按钮（有二次确认模态）。
- Holdings / Overview：表格显示每 leg 数量、方向、借币、mismatch 显眼高亮行 + 全局摘要卡片（total funding net、未实现估算等）。
- Profit & Fees：ledger 表格（可按 symbol/time 过滤） + 汇总公式可视化。
- 所有操作必须产生可审计的 action log（本地或后端）；无真实 credential 暴露给前端。
- 建议初期用 mock server 或静态样本驱动 UI，真实 ws 仅在明确小资金阶段后通过后端代理。

**测试与线上小资金验证策略**：
- 单元：规则归一化、round 计算、会计纯函数（大量 fixture）。
- 契约：使用 vcr 或自定义 recorder 冻结真实响应样本做集成测试。
- 执行流程：dry-run 模式（只走到“准备下单”不发送）+ 状态机测试。
- 线上小资金：必须先有用户明确批准的最大风险额度、明确“只做正费率 BTC/ETH 等高流动性品种”白名单、执行前后全量 snapshot + 人工 close 预案、并且 UI 有明确“一键导出本次执行证据包”功能。
- 强烈建议先用完全模拟环境验证状态机与会计，再小资金。

## 5. 第一阶段开发范围建议

范围必须极小、可落地、可验收，且**绝不包含可执行的真实下单路径**。

推荐第一阶段目标（命名为“接口发现 + 领域模型 + 原型验证”）：

- 建立 reports/api-samples/ 目录结构与命名规范。
- 实现一个只读 discovery 脚本（python），能对 PRD 列出的主要 GET 端点（无需密钥或用只读 public + account GET）采集原始响应，保存为带时间戳的 .json（自动红acted 任何 key/secret）。至少覆盖：exchangeInfo（fapi+spot）、premiumIndex、um/account、um/positionRisk、um/commissionRate、um/feeBurn、margin maxBorrowable、um/income（采样）、margin interest、listenKey 创建、depth 快照。
- 定义并实现核心 domain 数据结构与纯函数（使用 Decimal）：
  - SymbolClassification、TradingRules、HedgeDirection、ExecutionPlan、RoundSpec、Fill、FundingEvent、AccountingSnapshot。
  - planner：给定总 notional + rounds + rules → 计算 per-round + uplift + merge remainder。
  - accountant：给定事件列表 → net result + 分项。
  - normalizer：exchangeInfo → 统一规则。
- 编写对应单元测试 + fixture（从 api-samples 加载），全部通过。
- 将现有 prototypes/fake-ui/index.html 扩展或重构为更完整的静态/可交互原型，满足 PRD UI Requirements 中的四个屏幕，使用从 discovery 或硬编码样本驱动的数据。支持：
  - 输入 notional/rounds 后正确展示修正 per-round。
  - Mismatch 高亮示例。
  - 模拟“点击 open → 显示 live depth 估算 → 确认后更新 holdings”流程（前端 mock 状态转换）。
- 产出一个最小后端 stub（FastAPI 或 Flask + 静态数据）或纯前端可直接打开的增强版，使 UI 可演示完整信息架构。
- 产出 60-test-output.txt 风格的运行日志、样本列表、测试结果。
- 更新本阶段的 status.json / 70-handoff.md（由 controller 负责，但 implementer 提供内容素材）。
- 明确产出物清单与“如何复现验收”说明。

这个阶段能真实落地、产生可审查的证据（样本、代码、测试、UI 原型）、且零交易风险。后续阶段再决定是否进入带真实 key 的 discovery 深度测试或小资金执行。

## 6. 不建议第一阶段做的内容

- 任何包含 POST /papi/v1/um/order、POST /papi/v1/margin/order、POST /api/v3/order 或 marginLoan 的可执行代码（即使被 if False 包裹或 feature flag 也容易被误触发；建议完全不写这些路径的骨架）。
- 真实 websocket 连接到 Binance 公共或用户流（使用预录制样本或 mock）。
- 任何持久化 DB schema 迁移或生产级存储；jsonl 或内存 + 文件即可。
- 真实 holdings 轮询或 listenKey 后台刷新。
- 多 symbol 并发 plan 支持。
- BNB 费率 burn 实际切换的动态处理（先用样本里的 feeBurn 状态做静态计算）。
- 任何“自动”逻辑或阈值判断的残留。
- 前端直接持有 API key 或直接调用签名接口。
- 部署、CI、监控、告警等运维层。
- 尝试 bStock 实盘或负费率路径（先把正费率高流动性品种走通）。

原因：当前最大风险是“模型自信地认为代码安全而实际触发交易”。第一阶段必须把界面、数据模型、规则计算、会计、样本证据做扎实，再谈执行。过早写下单代码会违反 PRD “Phase 1 No real trading code” 并增加不必要的审查负担。

## 7. 验收标准建议

完成第一阶段后，必须通过以下**具体、可检查**的产物来证明，而非口头声明：

**文件级产物**：
- reports/agent-runs/2026-07-initial-direction/ 下存在完整 direction drafts + 本阶段的 00-task.md、10-design.md（如果 workflow 已推进）、api-samples/ 目录内至少 12 个带时间戳的原始 JSON（含 exchangeInfo、premium、account 相关、depth 等）。
- Python 模块布局清晰：e.g. src/binance_funding_hedge/{adapters/, domain/, planner.py, accountant.py, models.py} 或等效；__init__.py 暴露主要类型。
- 至少一个 discovery.py 或 scripts/ 下脚本 + README 说明如何用只读方式运行并生成样本。
- 增强后的 fake UI 文件（或新 static/ 目录下的完整可打开 html + js/css），或配套的 mock server。

**测试或模拟输出**：
- pytest 或等效运行输出（60-test-output.txt 或同等）显示所有 domain 测试（normalize、plan_rounds、compute_net、mismatch_detect）全部 PASS。
- 至少 3 个会计场景的 fixture 验证：正费率无 BNB、含 BNB 折扣、负费率含 borrow interest。
- Planner 边界用例：小 notional 触发 uplift 合并、余量合并、stepSize 舍入后仍满足 min notional。

**UI 验收项**：
- 浏览器打开 fake UI，能看到：
  - 机会表，显示至少 5 个模拟 symbol，含 classification badge、funding rate、route（PM-MARGIN / SPOT）、borrowable 指示。
  - 选择一个 symbol 后，Manual Open 表单输入总 notional 与 rounds，实时显示“修正后每轮金额”和预计费用。
  - 模拟点击 open 后出现“Live spread / 滑点估算”面板（用 mock 数据刷新）。
  - Holdings 表格中存在至少一个 mismatch 高亮行，显示 delta 数量与 notional。
  - Profit & Fees 页显示 ledger 行 + 汇总 net 计算。
- UI 必须有明确文字说明“本阶段为模拟，无真实下单”。

**Binance 接口 discovery 样本验收项**：
- 存在至少以下端点的样本（文件名可带 ts）：
  - fapi/v1/exchangeInfo（USDT 永续规则）
  - api/v3/exchangeInfo
  - fapi/v1/premiumIndex（含 fundingRate）
  - papi/v1/um/account 或 v2
  - papi/v1/um/positionRisk
  - papi/v1/um/commissionRate
  - papi/v1/um/feeBurn
  - papi/v1/margin/maxBorrowable（至少一个币）
  - 一个 depth 快照（fapi 或 spot）
  - um/income 或 margin interest history 示例（如权限允许）
- 每个样本文件必须有注释或同目录 meta 说明采集时间、llms-full.txt 版本引用、是否含敏感信息（已 redacted）。
- 提供一个简单脚本或 notebook，能从样本加载并跑通一次 classifier + planner + accountant 端到端。

**其他硬性**：
- Git diff 中没有任何可执行的真实交易 POST 代码。
- 所有货币计算使用 Decimal，测试中证明无 float 泄漏。
- 70-handoff.md / status.json 更新，明确列出“本阶段产生证据”与“下一阶段进入条件”（用户批准 + 更多样本审查）。

只有以上全部可检查通过，才算第一阶段完成。

## 8. 与现有 PRD 的冲突或修订建议

- 原问题：PRD 中“Phase 1 Acceptance Criteria”只说了“UI fake prototype... No real trading code is required.”，但未明确“是否允许写下单函数骨架”。
  建议改成：“Phase 1 严禁在代码库中出现任何指向真实 market order 或 borrow 的可执行路径（包括被注释、flag 保护的代码）。只允许只读 discovery、规划计算、会计函数与完全 mock 的 UI 流程。”
  理由：防止后续阶段误用或 review 遗漏。

- 原问题：PRD 执行流程中“系统异步同时开双腿”与“按轮”之间存在歧义。
  建议改成：在“平滑开仓”小节增加：“每轮内部，futures leg 与 spot/margin leg 尝试在可接受价差窗口内近同时提交 market order；轮与轮之间串行，上一轮 fill 确认后再进入下一轮。执行器必须在每轮前后记录实际 depth 作为证据。”
  理由：异步同时有风险，需明确对齐与确认机制。

- 原问题：UI Requirements 提到“Manual open”但未明确是否包含“人工平仓”流程描述。
  建议增加：在 v0.1 必须提供对称的“手动平仓计划”UI 入口（至少占位 + 状态），即使平仓本身仍用 market 且人工触发。
  理由：持有后必须能对称退出，否则操作者被困。

- 原问题：会计公式中 rebate 硬编码 0.6。
  建议增加：“默认 rebate 系数为 0.6（对应 40% 返佣）。当 /papi/v1/um/commissionRate 可用时，必须优先使用该接口返回的 maker/taker 费率与实际 rebate 情况计算；仅在样本缺失时回退到默认值。”
  理由：与“反映真实成本”原则一致。

- 原问题：PRD 提到“bStocks”但未给检测方法。
  建议在 Asset Classification 小节增加：分类器必须输出符号来源（从 exchangeInfo 的 permission 或已知 bStock 列表），并在 opportunity table 中显式标“bStock / tokenized”。
  理由：操作者需要知道为什么某个品种不支持负费率。

- 其他小点：recvWindow 建议在 architecture 中作为可配置项记录（缺省 5000）；明确“capital occupation cost”在 v0.1 排除是正确的，但应在会计 UI 中有占位说明“未计入资金占用”。

以上仅建议，不直接修改 PRD。

## 9. 需要用户拍板的问题

1. **第一阶段后进入小资金实盘验证的资本与品种限制**
   方案 A：极保守（≤100 USDT 总 notional，仅 BTCUSDT / ETHUSDT 正费率，单 symbol ≤30 USDT）。
   方案 B：适度（≤300-500 USDT，允许 3-4 个高流动性品种）。
   方案 C：由用户在每次执行前通过 UI 表单显式输入“本次最大允许 notional”，系统只做显示不做额外硬编码限制。
   取舍：A 最安全但可能无法暴露真实滑点/借币/部分成交问题；C 最灵活但依赖操作者纪律。建议至少有全局 config 上限 + 每次执行前显式确认。

2. **v0.1 是否支持同时规划/监控多个 symbol 的持仓与执行计划**
   方案 A：严格单 symbol 模式（一次只能有一个 active plan，切换需先完成或取消）。
   方案 B：支持多 symbol 机会表 + 独立 holdings 行，但执行时串行化（一次只能在一个 symbol 上走 ws + confirm）。
   方案 C：完全并行（多个 ws 订阅 + 多个执行上下文）。
   取舍：A 最简单，风险最低，适合第一轮验证；B 是合理中间态；C 增加状态机复杂度与 UI 混乱。建议先 A，后续用户确认后再松绑。

3. **leg mismatch 的高亮容差阈值初始如何设置**
   方案 A：固定绝对值（例如数量差 > 0.0001 或 notional 差 > 0.1 USDT）。
   方案 B：相对百分比（例如 0.05% 或 0.1%）。
   方案 C：双阈值（绝对 + 相对，取更严格），并在 UI 上显示“当前 delta / 阈值”。
   取舍：加密交易 rounding 与部分成交很常见，纯相对在小头寸时过于敏感，纯绝对在大头寸时可能漏。建议 C + 可配置 + 所有 mismatch 事件必须记录原始数量用于事后分析。

4. **早期数据持久化策略**
   方案 A：纯文件 + jsonl（api-samples + events/ 目录），零 DB 依赖，最容易 review 与 replay。
   方案 B：SQLite 从第一天开始（表：raw_events、fills、funding_income、positions、plans）。
   方案 C：内存优先 + 显式“导出/导入”按钮，DB 推迟到 Phase 3 之后。
   取舍：A 最匹配当前 harness “证据优先”文化，也最容易 diff；B 方便查询但增加 schema 变更成本。建议 A 开始，后续如果 ledger 查询痛点明显再迁移。

5. **websocket 深度数据源**
   方案 A：仅使用公共 market ws（wss://fstream... / stream.binance...），后端不代理签名。
   方案 B：所有 ws 都走后端代理（便于记录、统一重连、未来可加用户 stream）。
   方案 C：前端直连公共 market，后端仅处理用户数据与订单。
   取舍：A 最简单安全；B 增加后端复杂度但 audit 更好。建议初期 A + 后端 recorder 可选。

以上问题请用户在方向合成审查时明确选择或给出新方案。

## 10. 最终建议

- 把本次方向稿收集作为正式第一阶段的触发器：在五稿 + synthesis 获得用户批准前，不要开始任何设计或实现任务。
- 第一阶段目标严格限定为“只读 discovery + 可测试的领域模型 + 增强 fake UI 验证”，绝不触碰任何可执行交易代码。
- 把 reports/api-samples/ 作为一等公民证据，与测试、diff 同等重要；所有后续会计、planner、reconciler 都必须能从这些样本重放。
- 会计与规划逻辑必须先作为纯函数 + 大量边界 fixture 实现并通过测试，再考虑任何集成。
- websocket book 维护与 spread 估算要尽早有可重放的样本驱动实现，作为平滑开仓可视化的基础。
- UI 信息架构要完整覆盖 PRD 要求的四个屏幕 + 明确的数据新鲜度 + mismatch 视觉提示；用 mock 把完整流程演示出来。
- 明确区分“展示/规划用估算”与“执行前置检查”的严格程度，并在 UI 文案中体现。
- 小资金实盘必须是后续独立阶段，且进入前需用户再次显式批准风险参数与白名单品种。
- 任何时候都保留“人工随时接管”的能力：即使系统在执行中，也必须能立即停止后续轮次并让操作者手动平仓。
- 严格遵守 harness：本稿只放 reports/agent-runs/.../direction-drafts/grok-build.md；后续 synthesis 由 codex 负责；任何批准后的设计才进入 10-design.md 等。
- 保持极简：能用文件+jsonl+纯函数解决的，不要急着上 DB、ORM、复杂状态管理。

本稿仅代表 grok-build 作为独立评审者的当前判断，不构成最终决策输入。等待用户对 synthesis 的批准后再推进。

---

生成的文件：reports/agent-runs/2026-07-initial-direction/direction-drafts/grok-build.md