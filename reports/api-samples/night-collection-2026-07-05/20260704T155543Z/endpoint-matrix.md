# Project endpoint matrix

本矩阵汇总当前代码库中所有与 Binance 交互的 REST 端点，包括公开端点和私有只读白名单端点。

## 公开端点（无需 API key）

| 端点 | 方法 | 调用位置 | 入参 | 出参用途 | 样本文件 |
|---|---|---|---|---|---|
| `/fapi/v1/exchangeInfo` | GET | `backend/adapters/binance_public.py:92` | 无 | U 本位合约交易对元数据 | `raw/fapi-v1-exchangeInfo.json` |
| `/fapi/v1/premiumIndex` | GET | `backend/adapters/binance_public.py:94` | 无 | 最新标记价格、资金费率 | `raw/fapi-v1-premiumIndex.json` |
| `/fapi/v1/fundingInfo` | GET | `backend/adapters/binance_public.py:98` | 无 | 结算间隔（小时） | `raw/fapi-v1-fundingInfo.json` |
| `/api/v3/exchangeInfo` | GET | `backend/adapters/binance_public.py:96` | 无 | 现货交易对元数据 | `raw/api-v3-exchangeInfo.json` |
| `/fapi/v1/fundingRate` | GET | `backend/adapters/binance_public.py:120` | `symbol`, `limit` | 历史资金费率 | `raw/fapi-v1-fundingRate-*-limit20.json` |

## 私有只读白名单端点（需 API key + HMAC-SHA256）

| 端点 | 方法 | 调用位置 | 入参 | 出参用途 | 样本文件 |
|---|---|---|---|---|---|
| `/sapi/v1/margin/allPairs` | GET | `backend/services/private_client.py:184` | 无 | 经典杠杆交易对清单 | `raw/classic_allPairs.json` |
| `/sapi/v1/margin/allAssets` | GET | `backend/services/private_client.py:185` | 无 | 资产可借性参考 | `raw/classic_allAssets.json` |
| `/sapi/v1/margin/crossMarginData` | GET | `backend/services/private_client.py:186` | 无 | VIP0 日利率 | `raw/classic_crossMarginData.json` |
| `/papi/v1/margin/maxBorrowable` | GET | `backend/services/private_client.py:214` | `asset` | 统一账户最大可借 | `raw/portfolio_maxBorrowable_BTC.json`, `raw/portfolio_maxBorrowable_ETH.json` |

## 安全约束

- 单一 HMAC 出口：`backend/services/private_client.py` 是仓库唯一构造签名的位置。
- deny-by-default 白名单：仅上表四个 `(method, exact-path)` 可调用。
- GET-only：无 POST/PUT/DELETE 代码路径。
- 审计日志：仅记录逻辑路径、HTTP 状态、错误、延迟；不记录 key/secret/signature/query。
