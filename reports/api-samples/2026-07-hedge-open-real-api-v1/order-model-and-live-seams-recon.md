# PAPI 对冲开仓真实 API 事实核查 — 下单模型与实时接缝

调研日期：2026-07-23（只读文档与公开市场数据；**未**读取凭据、未发送订单、未连接用户数据流）。

研究模型：Claude Opus 4.6 (Thinking)，在 Antigravity CLI 中执行。

## 结论摘要

**正向对冲（买现货 + 空永续）的两腿参数模型不对称，无法预对齐基础币数量。** 这是
API 事实，不是设计选择：

- 现货/杠杆腿 `POST /papi/v1/margin/order` MARKET BUY 支持 `quantity`（基础币）
  **或** `quoteOrderQty`（报价币），二选一，不能同时传。用户决策为正向 BUY 传
  `quoteOrderQty`（USDT 金额），这在 API 层是合法的。
- UM 永续腿 `POST /papi/v1/um/order` **不支持** `quoteOrderQty`，只接受
  `quantity`（基础币数量）。
- 因此正向开仓的现货成交基础币数量只能在成交后从响应中得知，UM 腿的 `quantity`
  必须事后或保守估算派生，两腿不能共享一个预对齐的 `q_common`。
- 反向（卖现货 + 多永续）两腿都使用 `quantity`，可以预对齐。

**旧 `q_common` 共同网格模型在正向开仓时无效，必须重建。**

---

## 1. `type=MARKET` 参数矩阵

### 1.1 PAPI Margin 市价单 — `POST /papi/v1/margin/order`

| 参数 | 类型 | MARKET 时必填 | 说明 | 来源 |
|---|---|---|---|---|
| `symbol` | STRING | YES | 交易对 | supplied-doc 事实 (llms-full.txt L37459) |
| `side` | ENUM | YES | `BUY` / `SELL` | supplied-doc 事实 |
| `type` | ENUM | YES | `MARKET` | supplied-doc 事实 |
| `quantity` | DECIMAL | 二选一 | 基础币数量；与 `quoteOrderQty` 互斥 | supplied-doc 事实 (L37463); official-current-doc 事实 (SAPI 参数表同构) |
| `quoteOrderQty` | DECIMAL | 二选一 | 报价币数量（USDT）；仅 MARKET 可用；与 `quantity` 互斥 | supplied-doc 事实 (L37464); official-current-doc 事实；公开样本 `quoteOrderQtyMarketAllowed=true` |
| `sideEffectType` | ENUM | 本阶段必传 | `NO_SIDE_EFFECT`（默认）、`MARGIN_BUY`、`AUTO_REPAY` | supplied-doc 事实 (L37470); **注意：SAPI 文档还列出 `AUTO_BORROW_REPAY`，但 PAPI PM SDK v6.0.0 的 `NewMarginOrderRequest` 未列出该值；前次调研已确认 PAPI 未列出** |
| `newClientOrderId` | STRING | 强烈要求传 | 唯一追踪 ID | supplied-doc 事实 |
| `newOrderRespType` | ENUM | 强烈要求 `RESULT` | `ACK` / `RESULT`；MARKET + `RESULT` 直接返回 FILLED 结果 | supplied-doc 事实 (L37469)；**注意：SAPI margin 默认 `FULL`（含 fills），PAPI 官方 SDK 枚举为 `ACK`/`RESULT`** |
| `selfTradePreventionMode` | ENUM | 可选 | `NONE` / `EXPIRE_TAKER` / `EXPIRE_MAKER` / `EXPIRE_BOTH` | supplied-doc 事实 (L49050; L37472) |
| `autoRepayAtCancel` | BOOLEAN | 不传 | 仅自动借款订单有意义 | supplied-doc 事实 (L37473) |
| `recvWindow` | LONG | 可选 | 毫秒，不超过 60000 | supplied-doc 事实 (L37474) |
| `timestamp` | LONG | YES | Unix 毫秒 | supplied-doc 事实 |
| `price` / `stopPrice` / `timeInForce` / `icebergQty` | — | 不传 | MARKET 不适用 | supplied-doc 事实 |

**`quantity` vs `quoteOrderQty` 同时传：** API 会拒绝。supplied-doc 事实
(L19074)：*"两者不能同时使用"*。

**每 symbol 能力字段：** 现货 `GET /api/v3/exchangeInfo` 响应中
`quoteOrderQtyMarketAllowed` 布尔值决定该交易对是否支持 `quoteOrderQty`。当前公开
样本 BTCUSDT = `true`（公开只读样本，2026-07-23 读取）。代码 **必须** 在每次
preflight 检查此字段；若为 `false`，正向 BUY 不能用 `quoteOrderQty`，必须 fail
closed。这是 supplied-doc 事实 (L20934 错误消息：*"Quote order qty market orders
are not support for this symbol."*)。

**PAPI vs SAPI 参数一致性：** PAPI `POST /papi/v1/margin/order` 的参数集与 SAPI
`POST /sapi/v1/margin/order` 相同（区别：PAPI 无 `isIsolated` 参数，因为 PM 全仓；
PAPI `sideEffectType` 不包含 `AUTO_BORROW_REPAY`）。来源：supplied-doc 事实
(PAPI change-log L49050 将 `selfTradePreventionMode` 加入
`POST /papi/v1/margin/order`，确认共享相同参数结构)；前次调研 SDK v6.0.0 交叉验证。

### 1.2 PAPI UM 市价单 — `POST /papi/v1/um/order`

| 参数 | 类型 | MARKET 时必填 | 说明 | 来源 |
|---|---|---|---|---|
| `symbol` | STRING | YES | 交易对 | supplied-doc 事实 |
| `side` | ENUM | YES | `BUY` / `SELL` | supplied-doc 事实 |
| `type` | ENUM | YES | `MARKET` | supplied-doc 事实 |
| `positionSide` | ENUM | 条件必填 | 单向 `BOTH`；双向 `LONG`/`SHORT` | supplied-doc 事实 |
| `quantity` | DECIMAL | **YES** | 合约数量（BTCUSDT = BTC 基础币量） | supplied-doc 事实；PAPI 签名示例 (L52164) |
| `reduceOnly` | BOOLEAN | 新开仓不传 | 默认 `false`；双向模式不可传 | supplied-doc 事实 |
| `newClientOrderId` | STRING | 强烈要求传 | | supplied-doc 事实 |
| `newOrderRespType` | ENUM | 强烈要求 `RESULT` | `ACK` / `RESULT` / `FULL`；MARKET + `RESULT` 直返 FILLED | supplied-doc 事实 |
| `selfTradePreventionMode` | ENUM | 可选 | | supplied-doc 事实 (L49048) |
| `recvWindow` | LONG | 可选 | | supplied-doc 事实 |
| `timestamp` | LONG | YES | | supplied-doc 事实 |

**UM 不支持 `quoteOrderQty`：** UM 合约下单参数列表中无此字段。supplied-doc 事实
(L19074 仅描述现货/杠杆的 `quoteOrderQty`；PAPI UM 签名示例 L52164 仅使用
`quantity`)。official-current-doc 事实（UM POST /fapi/v1/order 参数表无
`quoteOrderQty`）。这是已确认的硬限制，不是文档遗漏。

### 1.3 冲突解决

| 冲突项 | 说明 | 解决 |
|---|---|---|
| 前次调研结论 "两腿都用 `quantity`" vs 用户决策 "正向 BUY 用 `quoteOrderQty`" | 前次调研从配对对齐角度推荐两腿都用 `quantity`。用户在 DI-6 中明确覆盖：正向 BUY 传 `quoteOrderQty`。 | **用户决策在 API 能力范围内有效**。`POST /papi/v1/margin/order` MARKET BUY 确实支持 `quoteOrderQty`（在 `quoteOrderQtyMarketAllowed=true` 的 symbol 上）。代码必须按用户决策执行，同时 fail closed 检查该能力标志。来源类型：supplied-doc 事实 + 公开只读样本。 |
| `sideEffectType` PAPI 是否支持 `AUTO_BORROW_REPAY` | SAPI 文档 (L36979) 确认 SAPI 支持。PAPI PM SDK v6.0.0 `NewMarginOrderRequest` 未列出该值。 | **PAPI PM 不应传 `AUTO_BORROW_REPAY`**。只使用 `NO_SIDE_EFFECT`、`MARGIN_BUY`、`AUTO_REPAY`。本阶段固定 `NO_SIDE_EFFECT`。来源类型：前次调研 SDK 事实 + inference（PAPI changelog 无新增该值的记录）。 |
| `newOrderRespType` 默认值 | SAPI margin (L37469) 默认 `FULL`（含 fills）。PAPI 前次调研说枚举为 `ACK`/`RESULT`。 | **MARKET 单显式传 `RESULT`** 以获得确定行为。`FULL` 额外返回 `fills[]` 数组，在 PAPI 上可能不可用或行为不同。来源类型：supplied-doc 事实 + inference。 |

---

## 2. Filters 与数量取整

### 2.1 公开样本 — BTCUSDT（2026-07-23 只读读取）

#### 现货 `GET https://api.binance.com/api/v3/exchangeInfo?symbol=BTCUSDT`

| Filter | 字段 | 值 |
|---|---|---|
| `PRICE_FILTER` | `minPrice` / `maxPrice` / `tickSize` | `0.01` / `1000000.00` / `0.01` |
| `LOT_SIZE` | `minQty` / `maxQty` / `stepSize` | `0.00001` / `9000.00` / `0.00001` |
| `MARKET_LOT_SIZE` | `minQty` / `maxQty` / `stepSize` | `0.00000` / `122.02726120` / `0.00000` |
| `NOTIONAL` | `minNotional` / `applyMinToMarket` / `maxNotional` / `applyMaxToMarket` | `5.00` / `true` / `9000000.00` / `false` |
| 其他 | `quoteOrderQtyMarketAllowed` | `true` |
| 精度 | `baseAssetPrecision` / `quoteAssetPrecision` | `8` / `8` |

来源类型：**公开只读样本**，2026-07-23T14:05+08:00 读取。

#### UM 永续 `GET https://fapi.binance.com/fapi/v1/exchangeInfo` (BTCUSDT)

| Filter | 字段 | 值 |
|---|---|---|
| `PRICE_FILTER` | `minPrice` / `maxPrice` / `tickSize` | `556.80` / `4529764` / `0.10` |
| `LOT_SIZE` | `minQty` / `maxQty` / `stepSize` | `0.001` / `1000` / `0.001` |
| `MARKET_LOT_SIZE` | `minQty` / `maxQty` / `stepSize` | `0.001` / `120` / `0.001` |
| `MIN_NOTIONAL` | `notional` | `50` |
| 精度 | `pricePrecision` / `quantityPrecision` / `baseAssetPrecision` / `quotePrecision` | `2` / `3` / `8` / `8` |

来源类型：**公开只读样本**，2026-07-23T14:05+08:00 读取。

### 2.2 逐腿校验与序列化规则

#### 2.2.1 现货 MARKET BUY（正向，传 `quoteOrderQty`）

1. **`NOTIONAL`**：`quoteOrderQty >= minNotional`（当 `applyMinToMarket=true`）。
   BTCUSDT 当前 `minNotional=5 USDT`。
2. **`MARKET_LOT_SIZE`**：当 `stepSize=0.00000`（零），该 filter
   **约束关闭**——不约束数量步进、min、max。文档事实 (前次调研 §C)：*"一个字段为 0
   表示该项限制关闭"*。
3. **`LOT_SIZE`**：当 `MARKET_LOT_SIZE` 约束关闭时，`LOT_SIZE` 的 min/max/step
   作为后备约束。但对 `quoteOrderQty` BUY，**执行数量由引擎根据订单簿流动性决定**，
   不是用户显式传入的 `quantity`。引擎内部会保证 BTC 步进合规。
4. **序列化**：`quoteOrderQty` 为十进制定点字符串，精度 ≤
   `quoteAssetPrecision`（8 位）。不得使用科学记数法。

**quote-buy 执行数量获取方式：** MARKET BUY + `quoteOrderQty` + `newOrderRespType=RESULT`
的响应中包含 `executedQty`（实际成交的基础币数量）和 `cummulativeQuoteQty`（实际花费
的报价币）。UM 腿的 `quantity` 必须从这个 `executedQty` 派生。

#### 2.2.2 现货 MARKET SELL（反向，传 `quantity`）

1. **`MARKET_LOT_SIZE`**：若 `stepSize > 0`，`quantity` 必须满足
   `minQty <= quantity <= maxQty` 且 `(quantity - minQty) % stepSize == 0`。
   当前 BTCUSDT `stepSize=0`（关闭），后备使用 `LOT_SIZE`。
2. **`LOT_SIZE`**：`minQty=0.00001, stepSize=0.00001, maxQty=9000`。
   `quantity = floor(q / 0.00001) * 0.00001`。
3. **`NOTIONAL`**：`quantity * 估计价格 >= minNotional`（5 USDT，
   `applyMinToMarket=true`）。使用保守价格估计。
4. **序列化**：十进制定点字符串，精度 ≤ `baseAssetPrecision`（8 位）。

#### 2.2.3 UM MARKET（两个方向，传 `quantity`）

1. **`MARKET_LOT_SIZE`**：`minQty=0.001, stepSize=0.001, maxQty=120`。全部启用。
   `quantity = floor(q / 0.001) * 0.001`；`0.001 <= quantity <= 120`。
2. **`LOT_SIZE`**：`minQty=0.001, stepSize=0.001, maxQty=1000`。`MARKET_LOT_SIZE`
   覆盖的部分优先；未覆盖的仍按 `LOT_SIZE`。当前两者 step 相同。
3. **`MIN_NOTIONAL`**：`quantity * markPrice >= 50 USDT`。
4. **序列化**：十进制定点字符串。`quantityPrecision=3`
   但应以 `stepSize` 为准（`0.001` = 3 位小数）。不得以 `quantityPrecision`
   代替 filter。

### 2.3 正向 quote-buy 执行量与 UM sell quantity 推导

**不能使用"虚假的正向共同网格"。** 正确流程：

1. 用户输入 USDT 金额 `Q`。
2. 现货 MARKET BUY `quoteOrderQty=Q`，等待 RESULT 响应。
3. 从响应取 `executedQty`（实际购得的 BTC 数量）。
4. 将 `executedQty` 按 UM 的 `MARKET_LOT_SIZE.stepSize`（0.001）向下取整：
   `q_um = floor(executedQty / 0.001) * 0.001`。
5. 检查 `q_um >= UM MARKET_LOT_SIZE.minQty`（0.001）且
   `q_um * markPrice >= MIN_NOTIONAL`（50）。
6. UM MARKET SELL `quantity=q_um`。

**顺序依赖：** 正向开仓，现货必须先成交才能确定 UM 腿数量。两腿**不能并发**。
反向开仓（两腿都用 `quantity`），可以预对齐后并发。

### 2.4 反向 `q_common` 共同网格

反向两腿都传 `quantity`：

1. 输入基础币数量 `q`。
2. 现货 `stepSize`：当 `MARKET_LOT_SIZE.stepSize=0` 时用
   `LOT_SIZE.stepSize=0.00001`。
3. UM `MARKET_LOT_SIZE.stepSize=0.001`。
4. 共同步进 = `lcm(0.00001, 0.001) = 0.001`（因为 0.001 / 0.00001 = 100 整数倍）。
5. `q_common = floor(q / 0.001) * 0.001`。
6. 检查两边的 min/max 和 notional。
7. 两腿使用相同的 `q_common`。

---

## 3. PAPI 路径、权重、响应字段与超时核对

### 3.1 下单端点

| 端点 | 方法 | 权重 | 鉴权 | 来源 |
|---|---|---|---|---|
| `/papi/v1/margin/order` | POST | 1 | TRADE (HMAC/RSA 签名) | supplied-doc 事实 (前次调研 §A，SDK v6.0.0) |
| `/papi/v1/um/order` | POST | 1 | TRADE | supplied-doc 事实 |
| `/papi/v1/margin/order` | GET | 2 | USER_DATA | inference（与 SAPI 一致，需实测确认） |
| `/papi/v1/um/order` | GET | 2 | USER_DATA | inference |

### 3.2 查询与核对端点

| 用途 | 端点 | 方法 | 权重 | 关键响应字段 | 来源 |
|---|---|---|---|---|---|
| 查询 margin 单笔订单 | `/papi/v1/margin/order` | GET | 2 (inference) | `orderId`, `clientOrderId`, `status`, `executedQty`, `cummulativeQuoteQty`, `side`, `type` | supplied-doc 事实 (L49070: `GET /papi/v1/margin/order` 存在) |
| 查询 UM 单笔订单 | `/papi/v1/um/order` | GET | 2 (inference) | `orderId`, `clientOrderId`, `status`, `executedQty`, `cumQty`, `cumQuote`, `avgPrice`, `side`, `positionSide` | supplied-doc 事实 (L48782, L49056) |
| Margin 成交历史 | `/papi/v1/margin/myTrades` | GET | 5 (inference) | `id`, `orderId`, `symbol`, `price`, `qty`, `commission`, `commissionAsset`, `time` | inference（与 SAPI 一致） |
| UM 成交历史 | `/papi/v1/um/userTrades` | GET | 5 (inference) | `id`, `orderId`, `symbol`, `price`, `qty`, `commission`, `commissionAsset`, `realizedPnl`, `side`, `positionSide` | supplied-doc 事实 (L48910: 确认存在) |
| UM 持仓风险 | `/papi/v1/um/positionRisk` | GET | 5 | `symbol`, `positionAmt`, `positionSide`, `entryPrice`, `markPrice`, `notional`, `unRealizedProfit`, `liquidationPrice`, `updateTime` | supplied-doc 事实 (前次调研 §D; L49109) |
| 余额 | `/papi/v1/balance` | GET | 20 | `asset`, `crossMarginFree`, `crossMarginLocked`, `crossMarginBorrowed`, `crossMarginInterest`, `crossMarginAsset` | supplied-doc 事实 (前次调研 §D) |
| 账户概要 | `/papi/v1/account` | GET | 20 | `uniMMR`, `totalAvailableBalance`, `accountInitialMargin`, `accountMaintMargin`, `accountStatus` | supplied-doc 事实 |
| UM 持仓模式 | `/papi/v1/um/positionSide/dual` | GET | 30 | `dualSidePosition` (boolean) | supplied-doc 事实 (前次调研 §B; L48159) |
| 最大可借 | `/papi/v1/margin/maxBorrowable` | GET | 5 | `amount`, `borrowLimit` | supplied-doc 事实 |
| 下单限频 | `/papi/v1/rateLimit/order` | GET | 1 | `rateLimitType`, `interval`, `intervalNum`, `limit` | supplied-doc 事实 (L48542) |

### 3.3 持久记录与超时核对序列

**Durable record（POST 之前写入）：**

每次尝试（attempt）在发送任何 POST 之前必须持久化以下不可变记录：

```
attempt_id          : UUID 或序列号
margin_client_id    : 从 attempt_id 派生的唯一 newClientOrderId
um_client_id        : 从 attempt_id 派生的唯一 newClientOrderId
direction           : forward | reverse
symbol              : e.g. BTCUSDT
intended_qty        : 正向=quoteOrderQty(USDT)；反向=q_common(BTC)
preflight_snapshot  : { balance, filters_version, position_mode, rate_limit, timestamp }
status              : PENDING
```

**超时/5xx/断连核对序列：**

1. POST 返回 timeout / 5xx / 连接断开 → **不重发该 client_id**。
2. 等待合理间隔（1-2s），然后分别：
   - `GET /papi/v1/margin/order?symbol=X&origClientOrderId=<margin_client_id>`
   - `GET /papi/v1/um/order?symbol=X&origClientOrderId=<um_client_id>`
3. 若查询返回 `status=FILLED` → 记录为已成交。
4. 若查询返回 `status=NEW/PARTIALLY_FILLED` → 等待一段时间后重新查询。
5. 若查询返回 404 / 不存在 → 该订单未被交易所接受，可标记为 REJECTED。
6. 若查询也 timeout → 标记为 UNKNOWN，进入人工核查。
7. **HTTP 503 "Unknown error"** (supplied-doc 事实 L51903-51910)：
   **执行状态未知，可能已成功**。必须查询，不能直接重试。
8. HTTP 503 "Service Unavailable"：**100% 失败**，可退避重试。
9. HTTP 503 -1008 "Request throttled"：**100% 失败**，降低并发后重试。
10. 每一步的查询结果都要持久化更新 attempt 记录。

### 3.4 PAPI 测试端点 / Testnet 状态

| 检查 | 结果 | 来源 |
|---|---|---|
| `https://papi.binance.com/papi/v1/ping` | `{}`（成功） | 公开只读样本 (2026-07-23) |
| `https://papi.binance.com/papi/v1/time` | `{"serverTime":1784787132176}`（成功） | 公开只读样本 |
| `https://papi.binance.com/papi/v1/um/exchangeInfo` | HTML 错误页 (无此端点) | 公开只读样本 |
| `https://testnet.binance.vision/papi/v1/ping` | 404 | 公开只读样本 |
| `https://testnet.binancefuture.com/papi/v1/ping` | 301 重定向（无 PAPI） | 公开只读样本 |
| `https://fapi.binance.com/fapi/v1/pmExchangeInfo` | 404 | 公开只读样本 |

**结论：** 不存在 PAPI Portfolio Margin testnet。普通现货 testnet 和 UM testnet
不是 PM 统一账户，不能验证双腿余额、借款副作用或 PAPI 限频。与前次调研结论一致。

PAPI 没有独立的 `exchangeInfo` 端点，交易规则/filters 必须从各市场的公开端点读取：

- 现货/margin filters：`GET https://api.binance.com/api/v3/exchangeInfo?symbol=X`
- UM filters：`GET https://fapi.binance.com/fapi/v1/exchangeInfo`（全量，按 symbol 过滤）

---

## 4. 签名、时间同步、TRADE 权限、PM 账户状态与限频

### 4.1 签名与时间同步

| 项目 | 事实 | 来源 |
|---|---|---|
| 基址 | `https://papi.binance.com` | supplied-doc 事实 (L51876) |
| 时间端点 | `GET /papi/v1/time` → `{"serverTime": <ms>}` | 公开只读样本 |
| `timestamp` | 签名请求必传，Unix 毫秒 | supplied-doc 事实 (L52012) |
| `recvWindow` | 可选，默认 5000ms，不推荐 >5000 | supplied-doc 事实 (L52013, L52030) |
| 时间窗口检查 | `timestamp < serverTime + 1000 && serverTime - timestamp <= recvWindow` | supplied-doc 事实 (L52019) |
| 签名算法 | HMAC SHA256 (API-Secret) 或 RSA PKCS#8 SHA256 | supplied-doc 事实 (L52005, L52140-52143) |
| API Key 传递 | HTTP Header `X-MBX-APIKEY` | supplied-doc 事实 (L51990) |

### 4.2 TRADE 权限

下单接口鉴权类型为 `TRADE`（需要有效的 API-KEY 和签名）。supplied-doc 事实
(L51997)。API Key 必须具有 TRADE 权限。

### 4.3 PM 账户状态与风险字段

`GET /papi/v1/account` 的关键风险字段：

| 字段 | 说明 |
|---|---|
| `uniMMR` | 统一维持保证金率；低于强平线触发强平 |
| `accountStatus` | 账户状态（`NORMAL` 等） |
| `totalAvailableBalance` | 总可用余额（USDT） |
| `accountInitialMargin` | 账户初始保证金 |
| `accountMaintMargin` | 账户维持保证金 |

来源：supplied-doc 事实（前次调研 §D）。

**PM/PM-Pro 区别：** PAPI 基址同为 `papi.binance.com`。PM-Pro 有独立的
change-log（llms-full.txt L78541 起）和 WebSocket 事件（`PM_PRO_ACCOUNT_UPDATE`，
L53582）。当前实现针对 PM（非 PM-Pro），但两者共享相同的下单端点和参数。
来源类型：inference（change-log 结构推断，需实测确认 PM-Pro 账户是否使用相同的
`/papi/v1/` 路径）。

**账户模式兼容性检查：** 在创建 task 前应 preflight 读取
`GET /papi/v1/um/positionSide/dual`（权重 30）确认持仓模式，以及
`GET /papi/v1/account` 确认 `accountStatus=NORMAL` 和 `uniMMR` 在安全水平。
不得在开单流程中切换持仓模式。

### 4.4 限频行为

| 限制类型 | 约束 | 来源 |
|---|---|---|
| IP 访问限制 | 6000 req/min | supplied-doc 事实 (L51974) |
| 下单频率限制 | 1200 orders/min（账户级别） | supplied-doc 事实 (L51985) |
| 下单限频头 | `X-MBX-ORDER-COUNT-(intervalNum)(intervalLetter)` | supplied-doc 事实 (L51982) |
| IP 限频头 | `X-MBX-USED-WEIGHT-(intervalNum)(intervalLetter)` | supplied-doc 事实 (L51968) |
| 429 | 访问频次超限警告 | supplied-doc 事实 (L51886) |
| 418 | 429 后继续访问被封 IP | supplied-doc 事实 (L51887) |
| 封禁时长 | 重复违反：2 分钟到 3 天递增 | supplied-doc 事实 (L51972) |
| PAPI margin `sideEffectType` 影响权重 | SAPI: `MARGIN_BUY`/`AUTO_BORROW_REPAY` 时 UID 权重 1500，其他时 UID 权重 6 | supplied-doc 事实 (L36800-36801)；**open item：PAPI 是否有同等权重区分需实测确认** |

**实际限额读取：** `GET /papi/v1/rateLimit/order`（权重 1）返回当前账户的下单限额
配置。不能以公开 exchangeInfo 的限额代替。来源：supplied-doc 事实 (L48542)。

**-1008 过载保护：** 适用于 `POST /papi/v1/order`、`POST /papi/v1/um/order`
等。平仓/只减仓订单豁免。来源：supplied-doc 事实 (L51927-51932)。

---

## 5. 需要用户新决策的事实性阻塞项

> **本节不提出 auto-borrow、auto-repay、auto-close、auto-repair、模式切换、
> 转账、或从 `quoteOrderQty` 到 `quantity` 的静默回退。**

| # | 阻塞项 | 原因 | 所需决策 |
|---|---|---|---|
| B-1 | **正向开仓两腿必须串行** | 现货 BUY `quoteOrderQty` 的执行基础币数量未知直到成交。UM SELL `quantity` 必须从现货响应的 `executedQty` 派生。两腿不能并发。 | 确认接受正向串行执行模型？如果现货成交后在发 UM 单之前断连，将产生单腿持仓风险。 |
| B-2 | **正向单腿持仓风险窗口** | 现货 BUY 已 FILLED 但 UM SELL 未发/失败 → 持有裸多现货。反向类似但方向相反。 | 确认单腿持仓的处理方式：仅报警+停止，还是允许有条件的自动 UM 补单？（当前设计意图：仅报警+停止，不自动交易。） |
| B-3 | **`quoteOrderQtyMarketAllowed` 可变** | 该字段可能因 symbol 或市况变化为 `false`。此时正向 BUY 无法使用 `quoteOrderQty`。 | 确认 fail-closed 行为：拒绝该 symbol 的正向 task？还是需要一个 base-quantity 后备路径？（本调研不提出静默回退。） |
| B-4 | **正向 UM 数量损耗** | 现货 `executedQty` 向下取整到 UM stepSize 后，可能比现货实际购得量少。差额 = 未对冲的裸多现货。 | 确认该差额（当前 BTCUSDT 最大 0.000999 BTC ≈ 数十美元）可接受？ |
| B-5 | **sideEffectType PAPI 权重不确定** | SAPI 文档明确 `MARGIN_BUY`/`AUTO_BORROW_REPAY` 时 UID 权重 1500。PAPI 是否同等不确定。本阶段仅用 `NO_SIDE_EFFECT`（UID 权重 6），暂无影响。 | 无需当前决策，但记录为 open item。 |
| B-6 | **PM-Pro 兼容性未验证** | 未确认 PM-Pro 账户是否使用完全相同的 `/papi/v1/` 路径和参数。 | 如果用户账户是 PM-Pro，需要额外验证。否则标记为不适用。 |

---

## 旧 `q_common` 模型必须变更的清单

| # | 旧模型行为 | 变更要求 | 影响范围 |
|---|---|---|---|
| C-1 | 两腿使用相同 `quantity=q_common` | **正向**：现货传 `quoteOrderQty`（USDT），UM 传 `quantity`（从现货成交量派生）。**反向**：保留 `q_common` | 下单参数构建、preflight 计算、attempt 记录 |
| C-2 | 两腿可并发发出 | **正向**：必须串行（现货先，UM 后）。**反向**：可并发 | 执行状态机 |
| C-3 | 共同网格 `lcm(step_spot, step_um)` 预计算 | **正向**：仅 UM 侧取整，应用于 `executedQty`。**反向**：保留共同网格 | filter 计算逻辑 |
| C-4 | 输入语义：基础币数量 | **正向**：输入语义改为 USDT 金额。**反向**：保留基础币数量 | 前端输入、API 路由 |
| C-5 | 成交数量校验 `executed_qty_spot == executed_qty_um` | **正向**：不可能精确相等，记录差额。**反向**：理论可等，但用户已决策不做成交数量校验 | attempt 分类逻辑 |
| C-6 | 单一 notional 估计 | **正向**：现货 notional = `quoteOrderQty` 本身（USDT）；UM notional = `q_um * markPrice`。**反向**：`q_common * price` 单一估计保留 | notional 预检查 |
| C-7 | `MARKET_LOT_SIZE.stepSize=0` 未处理 | 必须将零值 stepSize 解释为"该约束关闭"，后备使用 `LOT_SIZE.stepSize` | filter 解析 |

---

## 来源与可复核定位

### supplied-doc 事实（llms-full.txt 行号）

- PAPI 基本信息与限频：L51867-51985
- PAPI 签名示例（HMAC）：L52033-52138
- PAPI 签名示例（RSA）：L52140-52230
- HTTP 503 状态码处理：L51900-51932
- SAPI margin order 参数表：L37457-37475
- SAPI margin sideEffectType 说明：L37477-37488
- SAPI margin `quoteOrderQty` 加入：L37204
- SAPI margin `sideEffectType` 权重：L36800-36801
- PAPI change-log 确认 `POST /papi/v1/margin/order` 参数一致：L49050
- PAPI change-log 确认 `POST /papi/v1/um/order` 存在：L49048
- PAPI `GET /papi/v1/rateLimit/order` 新增：L48542
- PAPI `GET /papi/v1/um/positionRisk` 确认：L49109
- MARKET `quoteOrderQty` 语义：L19074
- `quoteOrderQty` 不支持错误：L20934

### official-current-doc 事实

- PAPI 下单端点 URL：
  - [New Margin Order](https://developers.binance.com/docs/derivatives/portfolio-margin/trade/New-Margin-Order)
  - [New UM Order](https://developers.binance.com/docs/derivatives/portfolio-margin/trade/New-UM-Order)
- PAPI 账户端点 URL：
  - [Account Balance](https://developers.binance.com/docs/derivatives/portfolio-margin/account/Account-Balance)
  - [Get UM Current Position Mode](https://developers.binance.com/docs/derivatives/portfolio-margin/account/Get-UM-Current-Position-Mode)
  - [Query UM Position Information](https://developers.binance.com/docs/derivatives/portfolio-margin/account/Query-UM-Position-Information)
  - [Margin Max Borrow](https://developers.binance.com/docs/derivatives/portfolio-margin/account/Margin-Max-Borrow)
  - [Query User Rate Limit](https://developers.binance.com/docs/derivatives/portfolio-margin/account/Query-User-Rate-Limit)
- 现货 Filters：[Spot Filters](https://developers.binance.com/docs/binance-spot-api-docs/filters)
- UM Exchange Information：[USDⓈ-M Exchange Information](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information)
- 注：官方页面被 WAF challenge 拒绝正文抓取，URL 通过 SDK v6.0.0 `@see` 链接和搜索结果交叉验证。

### 公开只读样本

- `GET https://api.binance.com/api/v3/exchangeInfo?symbol=BTCUSDT` — 2026-07-23T14:05+08:00
- `GET https://fapi.binance.com/fapi/v1/exchangeInfo` (BTCUSDT) — 2026-07-23T14:05+08:00
- `GET https://papi.binance.com/papi/v1/ping` — 2026-07-23T14:12+08:00
- `GET https://papi.binance.com/papi/v1/time` — 2026-07-23T14:12+08:00

### 前次调研

- `reports/api-samples/2026-07-hedge-open-live-v1/order-endpoints-filters-recon.md`
- `reports/agent-runs/2026-07-hedge-open-live-v1/design-inputs.md` §DI-6
- `reports/agent-runs/2026-07-hedge-open-real-api-v1/00-intake.md`
- `reports/agent-runs/2026-07-hedge-open-real-api-v1/01-design-discussion.md`

---

当前 Session ID: Antigravity CLI conversation 3a6a68e2-87ec-4fd8-907f-7e91f7df7bfe
Session ID 来源: Antigravity CLI (Claude Opus 4.6 Thinking)
原始输出路径: reports/api-samples/2026-07-hedge-open-real-api-v1/order-model-and-live-seams-recon.md
本地北京时间: 2026-07-23 14:13 CST
下一步模型: human operator / bookkeeper
下一步任务: 将本原始调研作为 stage design 输入；正向串行模型和 q_common 重建方案待用户确认阻塞项后进入 direction drafts
