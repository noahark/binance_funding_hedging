# 公开端点深度摸排

> 基于已采集样本（`raw/`）和 `llms-full.txt` 做深度字段解析，**不调用任何新端点**。

## 1. 已采集公开样本概览

| 端点 | 文件 | 大小 | 条目数 | 主要用途 |
|---|---|---|---|---|
| `GET /api/v3/exchangeInfo` | `raw/api-v3-exchangeInfo.json` | ~28 MB | 1356 TRADING symbols | 现货交易对元数据、filters、rateLimits |
| `GET /fapi/v1/exchangeInfo` | `raw/fapi-v1-exchangeInfo.json` | ~1.6 MB | 695 TRADING symbols | U 本位合约元数据 |
| `GET /fapi/v1/premiumIndex` | `raw/fapi-v1-premiumIndex.json` | ~222 KB | 823 entries | 标记价格、资金费率、下次结算时间 |
| `GET /fapi/v1/fundingInfo` | `raw/fapi-v1-fundingInfo.json` | ~148 KB | 711 entries | 结算间隔（小时） |
| `GET /fapi/v1/fundingRate` | `raw/fapi-v1-fundingRate-*-limit20.json` | ~2.6 KB × 6 | 20 × 6 | 历史资金费率 |

## 2. 限频策略（来自 exchangeInfo）

### 2.1 现货 /api/v3/exchangeInfo

```json
[
  {"rateLimitType": "REQUEST_WEIGHT", "interval": "MINUTE", "intervalNum": 1, "limit": 6000},
  {"rateLimitType": "ORDERS", "interval": "SECOND", "intervalNum": 10, "limit": 100},
  {"rateLimitType": "ORDERS", "interval": "DAY", "intervalNum": 1, "limit": 200000},
  {"rateLimitType": "RAW_REQUESTS", "interval": "MINUTE", "intervalNum": 5, "limit": 300000}
]
```

### 2.2 U 本位 /fapi/v1/exchangeInfo

```json
[
  {"rateLimitType": "REQUEST_WEIGHT", "interval": "MINUTE", "intervalNum": 1, "limit": 2400},
  {"rateLimitType": "ORDERS", "interval": "MINUTE", "intervalNum": 1, "limit": 1200},
  {"rateLimitType": "ORDERS", "interval": "SECOND", "intervalNum": 10, "limit": 300}
]
```

### 2.3 调用建议

- 公开市场数据使用 `X-MBX-USED-WEIGHT-1M` 头监控。
- `/fapi/v1/exchangeInfo` 权重通常为 20（取决于文档版本），建议本地缓存。
- `/api/v3/exchangeInfo` 权重通常为 20，建议按 symbol 缓存。
- `fundingRate` 单 symbol 权重约 1，适合按需调用。

## 3. 现货交易对字段（以 BTCUSDT 为例）

### 3.1 核心字段

| 字段 | 示例值 | 说明 |
|---|---|---|
| `symbol` | BTCUSDT | 交易对 |
| `status` | TRADING | 交易状态 |
| `baseAsset` | BTC | 基础资产 |
| `quoteAsset` | USDT | 计价资产 |
| `baseAssetPrecision` | 8 | 基础资产精度 |
| `quoteAssetPrecision` | 8 | 计价资产精度 |
| `baseCommissionPrecision` | 8 | 基础资产手续费精度 |
| `quoteCommissionPrecision` | 8 | 计价资产手续费精度 |
| `orderTypes` | ["LIMIT", "MARKET", ...] | 支持的订单类型 |
| ` icebergAllowed` | true | 是否允许冰山单 |
| `ocoAllowed` | true | 是否允许 OCO |
| `otoAllowed` | true | 是否允许 OTO |
| `quoteOrderQtyMarketAllowed` | true | 市价单是否支持按金额下单 |
| `allowTrailingStop` | true | 是否允许追踪止损 |
| `cancelReplaceAllowed` | true | 是否允许撤单并下单 |
| `isSpotTradingAllowed` | true | 是否允许现货交易 |
| `isMarginTradingAllowed` | true | 是否允许杠杆交易 |
| `permissions` | ["SPOT", "MARGIN", ...] | 账户权限要求 |
| `permissionSets` | [["SPOT", "MARGIN"]] | 权限组合 |

### 3.2 BTCUSDT Filters

| filterType | 关键字段 | 说明 |
|---|---|---|
| `PRICE_FILTER` | minPrice=0.01, maxPrice=1000000, tickSize=0.01 | 价格精度与范围 |
| `LOT_SIZE` | minQty=0.00001, maxQty=9000, stepSize=0.00001 | 数量精度与范围 |
| `MARKET_LOT_SIZE` | maxQty=152.76001495 | 市价单最大数量 |
| `NOTIONAL` | minNotional=5, maxNotional=9000000, applyMinToMarket=true | 最小/最大成交额 |
| `PERCENT_PRICE_BY_SIDE` | bid/ask multiplierUp=2, multiplierDown=0.5 | 价格振幅限制 |
| `MAX_NUM_ORDERS` | maxNumOrders=200 | 最大挂单数 |
| `MAX_NUM_ALGO_ORDERS` | maxNumAlgoOrders=5 | 最大条件单数 |
| `MAX_NUM_ORDER_AMENDS` | maxNumOrderAmends=10 | 最大改单次数 |
| `TRAILING_DELTA` | min=10, max=2000 | 追踪止损 delta 范围 |
| `ICEBERG_PARTS` | limit=100 | 冰山单最多拆分份数 |

## 4. U 本位合约交易对字段

### 4.1 核心字段

| 字段 | 示例值 | 说明 |
|---|---|---|
| `symbol` | BTCUSDT | 交易对 |
| `pair` | BTCUSDT | 标的对 |
| `contractType` | PERPETUAL | PERPETUAL / TRADIFI_PERPETUAL / CURRENT_QUARTER / NEXT_QUARTER |
| `status` | TRADING | 合约状态 |
| `baseAsset` | BTC | 基础资产 |
| `quoteAsset` | USDT | 计价资产 |
| `marginAsset` | USDT | 保证金资产 |
| `pricePrecision` | 2 | 价格精度 |
| `quantityPrecision` | 3 | 数量精度 |
| `baseAssetPrecision` | 8 | 基础资产精度 |
| `quotePrecision` | 8 | 计价精度 |
| `filters` | [...] | 与现货类似 |

### 4.2 合约类型分布（本次样本）

| contractType | 数量 |
|---|---|
| PERPETUAL | 573 |
| TRADIFI_PERPETUAL | 118 |
| CURRENT_QUARTER | 2 |
| NEXT_QUARTER | 2 |

## 5. premiumIndex 字段解析

| 字段 | 类型 | 说明 |
|---|---|---|
| `symbol` | string | 交易对 |
| `markPrice` | string | 标记价格 |
| `indexPrice` | string | 指数价格 |
| `estimatedSettlePrice` | string | 预估结算价 |
| `lastFundingRate` | string | 最近一次资金费率 |
| `interestRate` | string | 利率 |
| `nextFundingTime` | int64 | 下次结算时间（ms） |
| `time` | int64 | 数据时间（ms） |

### 5.1 与 fundingInfo 结合

- `fundingInfo` 提供 `fundingIntervalHours`（本次样本：1h=2, 4h=440, 8h=269）。
- 日费率估算：`abs(lastFundingRate) * 24 / fundingIntervalHours`。
- 项目当前 `snapshot_service.py` 已按此逻辑排序。

## 6. fundingRate 字段解析

单条记录字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `symbol` | string | 交易对 |
| `fundingTime` | int64 | 结算时间（ms） |
| `fundingRate` | string | 结算费率 |
| `markPrice` | string | 该结算点的标记价格（部分返回） |

本次采集 limit=20，可覆盖近 20 次结算历史。

## 7. Filters 深度说明

### 7.1 PRICE_FILTER

- `price >= minPrice`
- `price <= maxPrice`
- `(price - minPrice) % tickSize == 0`（合约）/ `price % tickSize == 0`（现货）

### 7.2 LOT_SIZE / MARKET_LOT_SIZE

- `quantity >= minQty`
- `quantity <= maxQty`
- `(quantity - minQty) % stepSize == 0`（合约）/ `quantity % stepSize == 0`（现货）

### 7.3 NOTIONAL / MIN_NOTIONAL

- `price * quantity >= minNotional`
- `price * quantity <= maxNotional`（如适用）
- 市价单使用参考价或 VWA 价估算价格。

### 7.4 PERCENT_PRICE / PERCENT_PRICE_BY_SIDE

- 买方：`price <= avg * bidMultiplierUp` 且 `price >= avg * bidMultiplierDown`
- 卖方：`price <= avg * askMultiplierUp` 且 `price >= avg * askMultiplierDown`

## 8. 与项目当前实现的对应关系

| 项目文件 | 当前使用的公开端点 | 可扩展的公开端点 |
|---|---|---|
| `backend/adapters/binance_public.py` | exchangeInfo, premiumIndex, fundingInfo, fundingRate | depth, trades, 24hr ticker, klines |
| `backend/services/snapshot_service.py` | 同上 | 可接入 depth 构建本地 order book |
| `backend/domain/classify.py` | 使用 spot `isMarginTradingAllowed` | 未来可结合 `/sapi/v1/margin/allPairs` |

## 9. 建议后续实抓的公开端点（如需）

| 端点 | 用途 | 是否安全 |
|---|---|---|
| `GET /fapi/v1/depth` | 订单簿深度 | ✅ 公开 |
| `GET /fapi/v1/trades` | 近期成交 | ✅ 公开 |
| `GET /fapi/v1/ticker/24hr` | 24h 统计 | ✅ 公开 |
| `GET /api/v3/depth` | 现货深度 | ✅ 公开 |
| `GET /api/v3/ticker/24hr` | 现货 24h 统计 | ✅ 公开 |
| `GET /fapi/v1/klines` | K 线数据 | ✅ 公开 |

## 10. 字段矩阵速查

| 能力 | 所需端点 | 关键字段 |
|---|---|---|
| 资金费率排序 | `/fapi/v1/premiumIndex` + `/fapi/v1/fundingInfo` | `lastFundingRate`, `fundingIntervalHours` |
| 下单前校验 | `/api/v3/exchangeInfo`, `/fapi/v1/exchangeInfo` | filters: PRICE_FILTER, LOT_SIZE, NOTIONAL |
| 市价单金额下单 | `/api/v3/exchangeInfo` | `quoteOrderQtyMarketAllowed` |
| 本地 order book | `/fapi/v1/depth` + `@depth` websocket | `bids`, `asks`, `lastUpdateId` |
| 订单状态跟踪 | `GET /api/v3/order` 或 user data stream | `status`, `executedQty`, `cummulativeQuoteQty` |
| 仓位跟踪（合约） | `GET /fapi/v2/positionRisk` 或 user data stream | `positionAmt`, `entryPrice`, `unRealizedProfit` |

---

本地北京时间: 2026-07-05 00:00:55 CST
下一步模型: Claude-GLM
下一步任务: 参考本报告和 `phase3-candidate-interface-report.md`，在获批后实现 Phase 3 的公开数据扩展或交易/账户流模块。
