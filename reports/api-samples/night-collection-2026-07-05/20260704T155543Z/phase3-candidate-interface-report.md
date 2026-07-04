# Phase 3 候选接口调研报告

> 本报告基于 `llms-full.txt` 做纯文档级梳理，**不调用任何被禁端点**（下单、listenKey、websocket 账户/订单/仓位流）。
> 目标是为后续 claude-glm 进入 Phase 3 时提供接口清单、鉴权方式、事件类型和实现注意点。

## 1. 现货 REST 交易端点

### 1.1 基础信息

- base URL: `https://api.binance.com`（另有 `api1`–`api4`、`api-gcp` 可用）
- 支持 HMAC、RSA、Ed25519 三种 API Key 类型。
- 鉴权类型：
  - `NONE`：公开市场数据
  - `TRADE`：下单、撤单
  - `USER_DATA`：私人账户信息（订单状态、交易历史）
  - `USER_STREAM`：管理用户数据流订阅
- SIGNED 请求需在 query string 或 body 中附带 `signature`、`timestamp`、`recvWindow`。
- `recvWindow` 默认 5000ms，最大 60000ms，不推荐超过 5s。
- 请求超时：10 秒；撮合引擎超时返回 `-1007`。

### 1.2 核心下单端点

| 端点 | 方法 | 鉴权 | 主要用途 |
|---|---|---|---|
| `POST /api/v3/order` | POST | TRADE | 下新订单 |
| `POST /api/v3/order/test` | POST | TRADE | 测试下单（不实际成交） |
| `POST /api/v3/order/oco` | POST | TRADE | 下 OCO 订单 |
| `DELETE /api/v3/order` | DELETE | TRADE | 撤单 |
| `DELETE /api/v3/openOrders` | DELETE | TRADE | 撤销某交易对所有挂单 |
| `GET /api/v3/order` | GET | USER_DATA | 查询订单状态 |
| `GET /api/v3/openOrders` | GET | USER_DATA | 查询当前挂单 |
| `GET /api/v3/allOrders` | GET | USER_DATA | 查询所有订单 |
| `GET /api/v3/myTrades` | GET | USER_DATA | 查询历史成交 |
| `POST /api/v3/order/cancelReplace` | POST | TRADE | 撤单并下单 |

### 1.3 下单关键参数（以 `/api/v3/order` 为例）

| 参数 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `symbol` | STRING | YES | 交易对，如 BTCUSDT |
| `side` | ENUM | YES | BUY / SELL |
| `type` | ENUM | YES | LIMIT, MARKET, STOP_LOSS, STOP_LOSS_LIMIT, TAKE_PROFIT, TAKE_PROFIT_LIMIT, LIMIT_MAKER |
| `timeInForce` | ENUM | NO | GTC, IOC, FOK（LIMIT 单建议必填） |
| `quantity` | DECIMAL | 条件 | 委托数量（与 `quoteOrderQty` 二选一） |
| `quoteOrderQty` | DECIMAL | 条件 | 市价按金额买入时使用 |
| `price` | DECIMAL | 条件 | LIMIT 单必填 |
| `newClientOrderId` | STRING | NO | 客户端自定义订单 ID |
| `stopPrice` | DECIMAL | 条件 | STOP / TAKE_PROFIT 类型必填 |
| `trailingDelta` | LONG | 条件 | 追踪止损单使用 |
| `newOrderRespType` | ENUM | NO | ACK, RESULT, FULL |
| `selfTradePreventionMode` | ENUM | NO | EXPIRE_TAKER, EXPIRE_MAKER, EXPIRE_BOTH, NONE |

### 1.4 响应示例（FULL）

```json
{
  "symbol": "BTCUSDT",
  "orderId": 28,
  "clientOrderId": "6gCrw2kRUAF9CvJDGP16IP",
  "transactTime": 1507725176595,
  "price": "0.00000000",
  "origQty": "10.00000000",
  "executedQty": "10.00000000",
  "cummulativeQuoteQty": "10.00000000",
  "status": "FILLED",
  "timeInForce": "GTC",
  "type": "MARKET",
  "side": "SELL",
  "fills": [
    {
      "price": "4000.00000000",
      "qty": "1.00000000",
      "commission": "4.00000000",
      "commissionAsset": "USDT",
      "tradeId": 56
    }
  ]
}
```

## 2. 现货 WebSocket 用户数据流

### 2.1 listenKey 管理（REST）

| 端点 | 方法 | 鉴权 | 说明 |
|---|---|---|---|
| `POST /api/v3/userDataStream` | POST | USER_STREAM | 创建 listenKey，有效期 60 分钟 |
| `PUT /api/v3/userDataStream` | PUT | USER_STREAM | 延长 listenKey 有效期 |
| `DELETE /api/v3/userDataStream` | DELETE | USER_STREAM | 关闭数据流 |

- 在已有有效 listenKey 上再次 POST，会返回当前 key 并延长有效期。

### 2.2 WebSocket Stream 连接

- base URL: `wss://stream.binance.com:9443` 或 `:443`
- 连接路径: `/ws/<listenKey>`
- 连接后自动推送账户相关事件，无需额外订阅。
- 每 20 秒收到 PING，需在 60 秒内回复 PONG（payload 与 PING 一致）。
- 单连接最多订阅 1024 个 streams；每 IP 每 5 分钟最多 300 次连接。

### 2.3 事件类型

| 事件 | event type | 触发时机 |
|---|---|---|
| 账户更新 | `outboundAccountPosition` | 账户余额变动 |
| 余额更新 | `balanceUpdate` | 充值、提现、账户间划转 |
| 订单更新 | `executionReport` | 订单创建、成交、撤销、过期等 |
| 订单组状态 | `listStatus` | OCO 订单组状态变化 |
| 外部锁定更新 | `externalLockUpdate` | 现货钱包被外部系统锁定/解锁 |
| 流终止 | `eventStreamTerminated` | listenKey 过期或 session logout |

### 2.4 executionReport 关键字段

| 字段 | 含义 |
|---|---|
| `e` | 事件类型 executionReport |
| `E` | 事件时间 |
| `s` | symbol |
| `c` | clientOrderId |
| `S` | side |
| `o` | order type |
| `f` | timeInForce |
| `q` | original quantity |
| `p` | price |
| `x` | execution type (NEW, CANCELED, REPLACED, REJECTED, TRADE, EXPIRED, TRADE_PREVENTION) |
| `X` | order status (NEW, PARTIALLY_FILLED, FILLED, CANCELED, EXPIRED, EXPIRED_IN_MATCH) |
| `r` | reject reason |
| `I` | orderId |
| `l` | last executed qty |
| `z` | cumulative filled qty |
| `Z` | cumulative quote asset transacted qty |
| `L` | last executed price |
| `n` | commission |
| `N` | commission asset |
| `T` | trade time |
| `t` | trade id |
| `b` | match type（有分配时） |
| `a` | allocation id（有分配时） |
| `uS` | usedSor |
| `gP`, `gOT`, `gOV`, `gp` | pegged 订单相关 |

## 3. 现货 WebSocket API（ws-api）

### 3.1 基本信息

- base URL: `wss://ws-api.binance.com:443/ws-api/v3`
- 测试网: `wss://ws-api.testnet.binance.vision/ws-api/v3`
- 请求格式：JSON text 帧，每帧一个请求
- 支持 HMAC / RSA / Ed25519
- 可直接通过 WebSocket 下单：`order.place`

### 3.2 下单请求示例

```json
{
  "id": "e2a85d9f-07a5-4f94-8d5f-789dc3deb097",
  "method": "order.place",
  "params": {
    "symbol": "BTCUSDT",
    "side": "BUY",
    "type": "LIMIT",
    "price": "0.1",
    "quantity": "10",
    "timeInForce": "GTC",
    "timestamp": 1655716096498,
    "apiKey": "T59MTDLWlpRW16JVeZ2Nju5A5C98WkMm8CSzWC4oqynUlTm1zXOxyauT8LmwXEv9",
    "signature": "5942ad337e6779f2f4c62cd1c26dba71c91514400a24990a3e7f5edec9323f90"
  }
}
```

### 3.3 响应示例

```json
{
  "id": "e2a85d9f-07a5-4f94-8d5f-789dc3deb097",
  "status": 200,
  "result": { ... },
  "rateLimits": [ ... ]
}
```

### 3.4 用户数据流订阅

- 方法：`userDataStream.subscribe`
- 也可通过 REST listenKey + WebSocket Stream 两种方式获取。

## 4. U 本位合约（USDⓈ-M Futures）

### 4.1 下单端点

| 端点 | 方法 | 说明 |
|---|---|---|
| `POST /fapi/v1/order` | POST | 下新订单 |
| `POST /fapi/v1/order/test` | POST | 测试下单 |
| `DELETE /fapi/v1/order` | DELETE | 撤单 |
| `DELETE /fapi/v1/allOpenOrders` | DELETE | 撤销所有挂单 |
| `PUT /fapi/v1/order` | PUT | 修改订单 |
| `GET /fapi/v1/order` | GET | 查询订单 |
| `GET /fapi/v1/openOrders` | GET | 当前挂单 |
| `GET /fapi/v1/allOrders` | GET | 历史订单 |
| `GET /fapi/v1/userTrades` | GET | 用户成交 |
| `GET /fapi/v2/positionRisk` | GET | 仓位风险 |
| `GET /fapi/v2/account` | GET | 账户信息 |
| `GET /fapi/v1/balance` | GET | 账户余额 |

### 4.2 用户数据流（listenKey）

- REST base: `https://fapi.binance.com`
- `POST /fapi/v1/listenKey`：创建，有效期 60 分钟
- `PUT /fapi/v1/listenKey`：延长
- `DELETE /fapi/v1/listenKey`：关闭
- WebSocket: `wss://fstream.binance.com/private/ws/<listenKey>`

### 4.3 事件类型

| 事件 | 说明 |
|---|---|
| `MARGIN_CALL` | 追加保证金通知 |
| `ACCOUNT_UPDATE` | 余额、仓位、保证金模式变化 |
| `ORDER_TRADE_UPDATE` | 订单创建、成交、状态变化 |
| `ACCOUNT_CONFIG_UPDATE` | 杠杆倍数、联合保证金状态变化 |
| `TRADE_LITE` | 精简交易推送 |
| `CONDITIONAL_ORDER_TRIGGER_REJECT` | 条件单触发后被拒 |
| `STRATEGY_UPDATE` | 策略交易更新 |

### 4.4 ACCOUNT_UPDATE 字段 "m" 原因

DEPOSIT, WITHDRAW, ORDER, FUNDING_FEE, WITHDRAW_REJECT, ADJUSTMENT, INSURANCE_CLEAR, ADMIN_DEPOSIT, ADMIN_WITHDRAW, MARGIN_TRANSFER, MARGIN_TYPE_CHANGE, ASSET_TRANSFER, OPTIONS_PREMIUM_FEE, OPTIONS_SETTLE_PROFIT, AUTO_EXCHANGE, COIN_SWAP_DEPOSIT, COIN_SWAP_WITHDRAW

### 4.5 ORDER_TRADE_UPDATE 执行类型

NEW, CANCELED, CALCULATED, EXPIRED, TRADE, AMENDMENT

### 4.6 订单状态

NEW, PARTIALLY_FILLED, FILLED, CANCELED, EXPIRED, EXPIRED_IN_MATCH

### 4.7 订单类型

LIMIT, MARKET, STOP, STOP_MARKET, TAKE_PROFIT, TAKE_PROFIT_MARKET, TRAILING_STOP_MARKET, LIQUIDATION

## 5. 统一账户 Portfolio Margin（/papi）

### 5.1 关键端点

| 端点 | 方法 | 说明 |
|---|---|---|
| `GET /papi/v1/account` | GET | 统一账户信息 |
| `GET /papi/v1/balance` | GET | 统一账户余额 |
| `GET /papi/v1/margin/maxBorrowable` | GET | 已用于 Phase 2 |
| `POST /papi/v1/um/order` | POST | U 本位合约下单 |
| `POST /papi/v1/cm/order` | POST | 币本位合约下单 |
| `POST /papi/v1/margin/order` | POST | 杠杆下单 |
| `DELETE /papi/v1/um/order` | DELETE | 撤单 |
| `GET /papi/v1/um/order` | GET | 查询订单 |
| `GET /papi/v1/um/positionRisk` | GET | 仓位风险 |

### 5.2 用户数据流

- 文档位置：`/products/derivatives-trading-portfolio-margin/user-data-streams`
- 同样使用 listenKey 机制，WebSocket base 需查文档确认。

## 6. 公开市场数据端点（已部分实抓）

| 端点 | 方法 | 说明 | 当前样本 |
|---|---|---|---|
| `GET /api/v3/exchangeInfo` | GET | 现货交易对元数据、filters、rateLimits | ✅ |
| `GET /fapi/v1/exchangeInfo` | GET | U 本位合约交易对元数据 | ✅ |
| `GET /fapi/v1/premiumIndex` | GET | 标记价格、资金费率 | ✅ |
| `GET /fapi/v1/fundingInfo` | GET | 结算间隔 | ✅ |
| `GET /fapi/v1/fundingRate` | GET | 历史资金费率 | ✅ |
| `GET /fapi/v1/ticker/24hr` | GET | 24 小时滚动统计 | 待抓 |
| `GET /fapi/v1/depth` | GET | 订单簿深度 | 待抓 |
| `GET /fapi/v1/trades` | GET | 近期成交 | 待抓 |
| `GET /api/v3/depth` | GET | 现货订单簿深度 | 待抓 |
| `GET /api/v3/ticker/24hr` | GET | 现货 24 小时统计 | 待抓 |

## 7. 限频与可靠性

### 7.1 REST IP 限频

- `X-MBX-USED-WEIGHT-(intervalNum)(intervalLetter)` 响应头显示当前 IP 已用权重。
- 429 后继续请求会被封 IP，返回 418。
- `Retry-After` 头给出等待秒数。
- 访问限制基于 IP，不是 API Key。

### 7.2 订单限频

- `X-MBX-ORDER-COUNT-(intervalNum)(intervalLetter)` 响应头显示未成交订单计数。
- 可通过 `GET /api/v3/rateLimit/order` 查询。

### 7.3 WebSocket 限频

- WebSocket 服务器每秒最多接受 5 个消息（PING/PONG/JSON 控制请求）。
- 单连接最多 1024 streams。
- 每 IP 每 5 分钟最多 300 次连接请求。

## 8. 给后续 claude-glm 的实现建议

1. **签名通道隔离**：延续 `backend/services/private_client.py` 的单一 HMAC 出口设计；Phase 3 下单需新增 `(method, exact-path)` 白名单项，但签名构造仍集中一处。
2. **先 test 后 live**：所有下单接口先用 `.../order/test` 验证签名和参数格式。
3. **WebSocket 连接管理**：listenKey 每 60 分钟续期；连接每 24 小时重建；PING/PONG 心跳必须实现。
4. **事件去重/排序**：使用 `E` 字段排序；订单状态机基于 `executionReport.x` / `X`。
5. **限频预算**：下单前检查 `rateLimits` 和 `X-MBX-ORDER-COUNT-*`，避免 429/418。
6. **测试网优先**：现货可用 `testnet.binance.vision`，合约可用 `testnet.binancefuture.com`。
7. **SBE 可选**：如果延迟敏感，后续可考虑 SBE 市场数据流，但实现复杂度高。

## 9. 风险与红线

- 当前阶段禁止：实际下单、创建 listenKey、订阅账户/订单/仓位 websocket。
- 后续进入 Phase 3 必须：用户批准、修订 `phase2-direction-draft.md` §3、新增 ADR、扩展白名单。
- 所有金额字段脱敏；API key/secret/signature 不落档。

---

本地北京时间: 2026-07-05 00:00:55 CST
下一步模型: Claude-GLM
下一步任务: 基于本报告和白名单安全设计，在获批后实现 Phase 3 下单/账户流模块。
