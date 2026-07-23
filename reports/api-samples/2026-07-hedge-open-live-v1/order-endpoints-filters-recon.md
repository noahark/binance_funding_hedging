# Binance Portfolio Margin 对冲开单：下单端点与 Filters 事实核查

调研日期：2026-07-22（只读文档与公开市场数据；**未**读取凭据、未发送订单、未连接生产执行流）。

## 结论摘要

用于本阶段的两腿均为签名 `TRADE` 调用，基址为 `https://papi.binance.com`：

| 腿 | 端点 | 以基础币数量 `q` 下市价单的字段 | 必要的专属字段 |
|---|---|---|---|
| 现货/杠杆 | `POST /papi/v1/margin/order` | `quantity=q`（基础币） | `sideEffectType=NO_SIDE_EFFECT` |
| USDⓈ-M | `POST /papi/v1/um/order` | `quantity=q`（合约数量；对 BTCUSDT 是 BTC 数量） | 单向 `positionSide=BOTH`；双向为 `LONG` 或 `SHORT` |

因此，用户输入的基础币数量不应在正向现货买入时改用 `quoteOrderQty`。该字段虽可选、单位为报价币，适合“花固定 USDT”的市价买入，却不能保证两腿预定的基础币数量相等。两条腿都用经各自 filter 共同兼容取整后的 `quantity`，再以余额预留滑点。

**反向卖现货、只使用已借币的确定取值：`sideEffectType=NO_SIDE_EFFECT`。** 当前 Portfolio Margin 的官方 SDK/OpenAPI 只枚举 `NO_SIDE_EFFECT`、`MARGIN_BUY`、`AUTO_REPAY`；没有把普通 margin 文档中常见的 `AUTO_BORROW_REPAY` 列为本端点的可用值。不得传入未列出的值，也不得把 `MARGIN_BUY` 用在这一语义上。

## A. 下单端点与参数

两端点均为签名接口：除了下表，签名请求还应带 API key、`timestamp`、HMAC `signature`，可带 `recvWindow`。本阶段的 dry-run transport 必须只记录这些参数，不能发出 HTTP POST。

### 1. Margin 市价单

`POST /papi/v1/margin/order`，权重 1。必填：`symbol`、`side`（`BUY`/`SELL`）、`type`（本阶段为 `MARKET`）。

| 参数 | MARKET 时 | 含义/取值 |
|---|---|---|
| `quantity` | 二选一使用；本阶段必传 | 基础币数量 |
| `quoteOrderQty` | 可选，和 `quantity` 不同时使用 | 报价币数量；不用于本阶段的配对数量语义 |
| `price`、`stopPrice`、`timeInForce`、`icebergQty` | 不传 | 限价/条件单相关 |
| `newClientOrderId` | 强烈要求传 | 本地唯一且可按双腿/尝试号追踪；超时后查询它，不能盲目重发 |
| `newOrderRespType` | 强烈要求 `RESULT` | 官方枚举为 `ACK`/`RESULT`，默认 `ACK` |
| `sideEffectType` | 本阶段必传 | `NO_SIDE_EFFECT`、`MARGIN_BUY`、`AUTO_REPAY`；默认 `NO_SIDE_EFFECT` |
| `selfTradePreventionMode` | 可选 | `NONE`、`EXPIRE_TAKER`、`EXPIRE_MAKER`、`EXPIRE_BOTH` |
| `autoRepayAtCancel` | 不传 | 仅自动借款/借还类订单有意义，默认 true |
| `recvWindow` | 可选 | 毫秒 |

来源：`llms-full.txt` 的 *Portfolio Margin REST API → trade → POST /papi/v1/margin/order*（约 186,300 行）；官方页 [New Margin Order](https://developers.binance.com/docs/derivatives/portfolio-margin/trade/New-Margin-Order)。官方发布的 TypeScript SDK `@binance/derivatives-trading-portfolio-margin` v6.0.0 的 `NewMarginOrderRequest` 也列出相同字段、枚举和值域。

### 2. UM 市价单

`POST /papi/v1/um/order`，权重 1。必填：`symbol`、`side`、`type`（`MARKET`）。

| 参数 | MARKET 时 | 含义/取值 |
|---|---|---|
| `positionSide` | 单向应显式传 `BOTH`；双向**必须**传 | `BOTH`/`LONG`/`SHORT` |
| `quantity` | 本阶段必传 | 合约数量；BTCUSDT 为 BTC 基础币数量 |
| `reduceOnly` | 新开仓不传（或单向显式 false） | 默认 false；**双向模式不可传** |
| `timeInForce`、`price`、`priceMatch`、`goodTillDate` | 不传 | 不适用于普通市价单 |
| `newClientOrderId` | 强烈要求传 | 与 margin 腿分开、但可共享同一 hedge-attempt 前缀 |
| `newOrderRespType` | 强烈要求 `RESULT` | 官方明确：`MARKET` + `RESULT` 直接返回最终 `FILLED` 结果 |
| `selfTradePreventionMode`、`recvWindow` | 可选 | 枚举同上；STP 只在指定 TIF 下有效 |

来源：`llms-full.txt` *Portfolio Margin REST API → trade → POST /papi/v1/um/order*（约 186,300 行）；官方页 [New UM Order](https://developers.binance.com/docs/derivatives/portfolio-margin/trade/New-UM-Order)。

## B. 方向映射、借款副作用与持仓模式

| 策略方向 | margin 请求 | UM：单向模式 | UM：双向模式 |
|---|---|---|---|
| 正向：买现货 + 开空永续 | `BUY`, `MARKET`, `quantity=q`, `sideEffectType=NO_SIDE_EFFECT` | `SELL`, `MARKET`, `quantity=q`, `positionSide=BOTH`, 不传 `reduceOnly` | `SELL`, `MARKET`, `quantity=q`, `positionSide=SHORT`, 不传 `reduceOnly` |
| 反向：卖现货 + 开多永续 | `SELL`, `MARKET`, `quantity=q`, `sideEffectType=NO_SIDE_EFFECT` | `BUY`, `MARKET`, `quantity=q`, `positionSide=BOTH`, 不传 `reduceOnly` | `BUY`, `MARKET`, `quantity=q`, `positionSide=LONG`, 不传 `reduceOnly` |

`MARGIN_BUY` 会为买入发生自动借款；`AUTO_REPAY` 是自动还款语义。两者都不满足“反向绝不自动借币”，正向在已有可用 USDT 时也应为 `NO_SIDE_EFFECT`。反向 preflight 必须确认基础币的 `crossMarginFree >= q`，并把既有借款任务/借款记录作为“已借额度”证据；`maxBorrowable` 仅是还能借多少，不能证明当前可卖额度。

先签名查询 `GET /papi/v1/um/positionSide/dual`（权重 30），响应 `{"dualSidePosition": true|false}`。`false` 是单向；`true` 是双向。不得在开单流程中改变模式：模式切换是账户全局状态变更，属于本阶段非目标。来源：[Get UM Current Position Mode](https://developers.binance.com/docs/derivatives/portfolio-margin/account/Get-UM-Current-Position-Mode)，以及 `llms-full.txt` 约 186,146 行。

## C. Filters 与数量取整

PAPI 文档没有 `margin/exchangeInfo` 或 `um/exchangeInfo`。应在每个尝试前/缓存刷新时读取对应公开交易规则：

| 市场 | 公开端点 | 本次真实公开样本（2026-07-22） |
|---|---|---|
| 现货/margin | `GET https://api.binance.com/api/v3/exchangeInfo?symbol=BTCUSDT` | `PRICE_FILTER` tick `0.01`；`LOT_SIZE` min/step `0.00001000`；`MARKET_LOT_SIZE` 的 `stepSize=0`（该字段约束关闭）；`NOTIONAL.minNotional=5`，`applyMinToMarket=true` |
| USDⓈ-M | `GET https://fapi.binance.com/fapi/v1/exchangeInfo` | `PRICE_FILTER` tick `0.10`；`LOT_SIZE` min/step `0.001`；`MARKET_LOT_SIZE` min/step `0.001`、max `120`；`MIN_NOTIONAL.notional=50` |

这两条 JSON 是只读实时公共样本，数值只可用作 BTCUSDT 当时的例子，不能硬编码，也不能代替每个目标 symbol 的即时读取。官方规则页：[Spot Filters](https://developers.binance.com/docs/binance-spot-api-docs/filters) 和 [USDⓈ-M Exchange Information](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information)。

- `PRICE_FILTER`：`minPrice`、`maxPrice`、`tickSize`；普通市价单不传 price，但可用于预估名义金额。
- `LOT_SIZE`：`minQty`、`maxQty`、`stepSize`。
- `MARKET_LOT_SIZE`：市价单专属的同三字段；一个字段为 0 表示该项限制关闭。对市价单优先使用其启用的 qty 约束；任何未被该 filter 覆盖的 qty 约束仍应按 `LOT_SIZE` 校验。不能拿 `quantityPrecision` 代替 filter。
- 现货 `NOTIONAL`：`minNotional`、`maxNotional`、`applyMinToMarket`、`applyMaxToMarket`、`avgPriceMins`。UM 当前样本为 `MIN_NOTIONAL.notional`；代码须同时兼容该字段名，不能假设两市场 schema 相同。

精确算法：用十进制定点（不是二进制 float）计算 `floor(q / stepSize) * stepSize`，并逐项检查 min/max。市价的名义金额按保守价格估计并满足最小 notional；现货买入还要预留滑点和费用。若两腿 step 不同，必须将输入向下取到两边都接受的共同网格（十进制 `lcm(step_spot, step_um)`），然后同时使用同一个 `q_common`；若小于任一 min 或超过任一 max，拒绝尝试。绝不能分别向下取整后以不同数量发两腿，否则会主动制造方向敞口。

## D. 余额、额度与持仓

| 用途 | 端点（均签名） | 应读取的字段 |
|---|---|---|
| 正向现货可用 USDT、反向可卖基础币 | `GET /papi/v1/balance`（权重 20） | 目标 asset 的 `crossMarginFree`、`crossMarginLocked`、`crossMarginBorrowed`、`crossMarginInterest`、`crossMarginAsset`；`totalWalletBalance` 不是可下单余额 |
| 组合风险/总体可用性 | `GET /papi/v1/account`（权重 20） | `uniMMR`、`totalAvailableBalance`、`accountInitialMargin`、`accountMaintMargin`、`accountStatus` |
| 最大可借（只作验证，不触发借款） | `GET /papi/v1/margin/maxBorrowable?asset=<BASE>`（权重 5） | `amount`、`borrowLimit` |
| 永续开单后核对 | `GET /papi/v1/um/positionRisk?symbol=<SYMBOL>`（权重 5） | `positionAmt`、`positionSide`、`entryPrice`、`markPrice`、`notional`、`unRealizedProfit`、`liquidationPrice`、`updateTime` |

来源：`llms-full.txt` 约 186,080–186,155 行的 Portfolio Margin account 清单；[Account Balance](https://developers.binance.com/docs/derivatives/portfolio-margin/account/Account-Balance)、[Margin Max Borrow](https://developers.binance.com/docs/derivatives/portfolio-margin/account/Margin-Max-Borrow)、[Query UM Position Information](https://developers.binance.com/docs/derivatives/portfolio-margin/account/Query-UM-Position-Information)。

## E. 响应、成交确认与单腿敞口

Margin 的 `RESULT` 响应 schema 包含 `symbol`、`orderId`、`clientOrderId`、`transactTime`、`price`、`origQty`、`executedQty`、`cummulativeQuoteQty`、`status`、`side`、`type`、`marginBuyBorrowAmount`、`marginBuyBorrowAsset` 与可选 `fills[]`（`price`、`qty`、`commission`、`commissionAsset`）。UM 的 schema 包含 `clientOrderId`、`orderId`、`status`、`executedQty`、`cumQty`、`cumQuote`、`avgPrice`、`origQty`、`side`、`positionSide`、`reduceOnly`、`updateTime` 等。

本次没有、也不应伪造“真实下单响应样本”：该样本必须来自已授权的真实 PAPI 下单，而当前 intake 明确禁止真实订单和凭据访问。上段是官方发布的响应 schema，不是实测证据。将来若用户单独批准受控的最小真实单，原始 HTTP 响应（删除签名/敏感 header）才能补入本证据；在此之前该问题的“真实样本”项状态为 **需实测确认**。

可靠的单腿判定不能只信 POST 返回：

1. 每腿使用唯一 `newClientOrderId`，并以 `newOrderRespType=RESULT` 发起；持久化发送前的 attempt/id。
2. 任何 timeout、5xx、连接断开或非 `FILLED` 都视为“未知/异常”，不得重发同 client id；分别 `GET /papi/v1/margin/order` 和 `GET /papi/v1/um/order` 按 symbol + `origClientOrderId`/`orderId` 查询。
3. 分别查 `GET /papi/v1/margin/myTrades`、`GET /papi/v1/um/userTrades` 得到实际成交量和加权均价，并以 `GET /papi/v1/um/positionRisk` 核对最终永续敞口。用户数据流应作为后续 websocket 调研所定义的异步确认补充，而非唯一事实源。
4. 一腿 `FILLED` 而另腿 `REJECTED`、`EXPIRED`、零成交、部分成交或未知，即锁定为单腿风险事件；停止后续 N 次，不自动补仓/平仓（后者是新的交易授权），记录两腿实际 quantities、orders、trades 与 positionRisk。

## F. 权重与限频

官方 PAPI OpenAPI/SDK 将两个 POST 都标为 **weight 1**。一笔对冲会提交两张订单，所以“每秒一次 hedge”至少是每秒两次下单事件；不能以“每 hedge weight 1”估算。账户实际下单限额应在启动 preflight 以 `GET /papi/v1/rateLimit/order`（权重 1）读取，其响应为 `rateLimitType`、`interval`、`intervalNum`、`limit`，并由持久化节流器按最紧限制执行。

本次公开样本的非 PAPI 参考值为：现货 exchangeInfo 的 `ORDERS=100/10s`、`200000/day`，UM exchangeInfo 的 `ORDERS=300/10s`、`1200/min`。它们**不是**对 PAPI 统一账户的授权承诺，不能硬编码为生产阈值。实现还应记录交易响应中的速率 header（若有），遇到 429/限频立即停止排队、保留未发送任务，不重试为“加速”。来源：[Query User Rate Limit](https://developers.binance.com/docs/derivatives/portfolio-margin/account/Query-User-Rate-Limit)。

## G. 测试与 dry-run

未找到 Binance 官方文档所列的 PAPI Portfolio Margin testnet 基址；PAPI 官方 SDK 的 Portfolio Margin REST 路径以 `https://papi.binance.com` 为基址。普通现货 testnet 和 `testnet.binancefuture.com` 的 UM demo/testnet 不是共享的 Portfolio Margin margin + UM 账户，因此不能验证本任务的双腿、余额、借款副作用或 PAPI 限频。

结论：本阶段 dry-run 应使用 record transport，在本地 durable task 中记录将要签名/发送的两条请求、filters 版本、preflight 快照与客户端 ID，且不作网络 POST。任何最小真实 PAPI 验证都需要后续独立的人类授权。

## 设计输入（可直接采用）

1. 先读公开 `exchangeInfo`、PAPI balance/account/position-mode/rate-limit，得出 `q_common` 和余额/风险结论；任何一个读取失败均拒绝 Start。
2. 固定 `NO_SIDE_EFFECT`；反向在发单前只接受已有 `crossMarginFree` 基础币，绝不将 max borrow 当成可直接卖出数量。
3. 用同一 attempt id 派生 `marginClientOrderId` 与 `umClientOrderId`；双腿可并发发起，但结果必须进入上述查询/核对状态机。
4. 初版将模式切换、自动借、自动还、自动补救交易全部列为非目标；出现不对称成交只报警/持久化，不自动下反向单。

## 来源与可复核定位

- 本仓库 `llms-full.txt`：*Portfolio Margin REST API → account*（`GET /papi/v1/balance`、`/account`、`/um/positionSide/dual`、`/margin/maxBorrowable`、`/um/positionRisk`，约 186,080–186,155 行）；*trade*（两 POST，约 186,300 行）。
- 官方 Portfolio Margin 文档：上列各 endpoint URL；官方页面在本环境被 WAF challenge 拒绝正文抓取，但 URL 由 Binance 官方 SDK v6.0.0 的 `@see` 链接交叉验证。
- 官方发布 SDK：[`@binance/derivatives-trading-portfolio-margin` v6.0.0](https://www.npmjs.com/package/@binance/derivatives-trading-portfolio-margin)，其 `NewMarginOrderRequest`、`NewUmOrderRequest`、响应类型和 endpoint 权重与上述表一致。
- 公开只读样本：`https://api.binance.com/api/v3/exchangeInfo?symbol=BTCUSDT` 与 `https://fapi.binance.com/fapi/v1/exchangeInfo`，读取于 2026-07-22。

当前 Session ID: unavailable (current Codex runtime does not expose a provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/api-samples/2026-07-hedge-open-live-v1/order-endpoints-filters-recon.md
本地北京时间: 2026-07-22 23:20:31 CST
下一步模型: bookkeeper / human
下一步任务: 将本原始调研与 websocket 调研作为 stage design 输入；“真实下单响应样本”须等待单独的人类授权。
