# 私有账户数据接入 v1 — 端点摸排研究报告

模型：Kimi (`kimi-code/kimi-for-coding`)  
任务来源：`reports/agent-runs/private-account-v1-direction/endpoint-recon.prompt.md`  
输入基线：`docs/private-account-v1-direction-draft.md`（FROZEN，§3.1/§3.3/§3.6）  
输入文档：`llms-full.txt`（币安官方文档 dump）  
输入样本：`reports/api-samples/night-collection-2026-07-05/20260704T155543Z/`  
现有实现：`backend/services/private_client.py`

研究纪律：
- 纯文档研究，**零网络请求、零签名调用、不写代码**。
- 每条主张尽量附 `llms-full.txt` 行号或 night-collection 样本路径；无出处处明确标注「推断，需实测」。
- 权重值找不到文档明确值时，标注「文档未见」，禁止猜测。

---

## A. 端点档案

覆盖基线 §3.6 表中全部端点：既有白名单 4 项 + 本轮新增 8 项 + 公开市场候选。

### 既有白名单 4 项（当前 `backend/services/private_client.py`）

当前白名单硬编码于 `backend/services/private_client.py:41-46`：

```python
WHITELIST = {
    ("GET", "/sapi/v1/margin/allPairs"): "https://api.binance.com",
    ("GET", "/sapi/v1/margin/allAssets"): "https://api.binance.com",
    ("GET", "/sapi/v1/margin/crossMarginData"): "https://api.binance.com",
    ("GET", "/papi/v1/margin/maxBorrowable"): "https://papi.binance.com",
}
```

#### W1. `GET /sapi/v1/margin/allPairs`

- **base_url**: `https://api.binance.com`
- **鉴权类型**: `USER_DATA`（签名 GET）
- **用途**: 获取所有全仓杠杆交易对，判断 symbol 是否支持杠杆交易（`isMarginTrade`）。
- **请求参数（文档级）**: `asset` 可选参数用于过滤（L36963「`GET /sapi/v1/margin/allPairs`：新增参数`symbol`」；L36948 指明其为 `GET /sapi/v1/margin/pair` 的替代）。
  - 参数表：
    | 名称 | 类型 | 必填 | 默认值 | 备注 |
    |---|---|---|---|---|
    | `symbol` | STRING | NO | - | 文档提及新增；推断用于按交易对过滤，需实测 |
- **响应字段（引用 night-collection 样本）**:
  样本路径：`reports/api-samples/night-collection-2026-07-05/20260704T155543Z/raw/classic_allPairs.json`
  | 字段 | 类型 | 语义 | 敏感数值 |
  |---|---|---|---|
  | `id` | INT64 | 交易对 ID | 否 |
  | `symbol` | STRING | 交易对 | 否 |
  | `base` | STRING | 基础资产 | 否 |
  | `quote` | STRING | 计价资产 | 否 |
  | `isMarginTrade` | BOOL | 是否可杠杆交易 | 否 |
  | `isBuyAllowed` | BOOL | 是否允许买 | 否 |
  | `isSellAllowed` | BOOL | 是否允许卖 | 否 |
- **文档权重值**: 文档未见明确权重（sapi 单接口限频模式，见 B 节）。
- **相关错误码**: -2015（无效 API key/IP/权限）、-1002（无权执行）、-1003/429（限频）。
- **统一账户适用性**: 文档未明确说明统一账户下本端点是否仍返回全仓杠杆交易对；基线 §3.6 将其列为「私有-既有白名单」，推断在统一账户下仍可调用，但统一账户的真实可借数据需结合 `papi/v1/margin/maxBorrowable` 验证。标注「需 H_intake 实测」。

#### W2. `GET /sapi/v1/margin/allAssets`

- **base_url**: `https://api.binance.com`
- **鉴权类型**: `USER_DATA`
- **用途**: 获取所有杠杆资产信息，判断资产是否可借（`isBorrowable`）。
- **请求参数**: `asset` 可选参数用于过滤（L36963「新增参数`asset`，新增响应信息」）。
  - 参数表：
    | 名称 | 类型 | 必填 | 默认值 | 备注 |
    |---|---|---|---|---|
    | `asset` | STRING | NO | - | 按资产名过滤，需实测 |
- **响应字段（引用 night-collection 样本）**:
  样本路径：`reports/api-samples/night-collection-2026-07-05/20260704T155543Z/raw/classic_allAssets.json`
  | 字段 | 类型 | 语义 | 敏感数值 |
  |---|---|---|---|
  | `assetName` | STRING | 资产名 | 否 |
  | `assetFullName` | STRING | 资产全名 | 否 |
  | `isBorrowable` | BOOL | 是否可借 | 否 |
  | `isMortgageable` | BOOL | 是否可质押 | 否 |
  | `userMinBorrow` | STRING | 用户最小借币量 | 否 |
  | `userMinRepay` | STRING | 用户最小还款量 | 否 |
- **文档权重值**: 文档未见。
- **相关错误码**: 同 W1。
- **统一账户适用性**: 同 W1，需 H_intake 实测。

#### W3. `GET /sapi/v1/margin/crossMarginData`

- **base_url**: `https://api.binance.com`
- **鉴权类型**: `USER_DATA`
- **用途**: 获取全仓杠杆利率及限额，提取 VIP0 日利率作为成本腿 fallback 三级来源。
- **请求参数**: 文档未见完整参数表；推断可传 `vipLevel` 或按用户当前 VIP 返回，需实测。基线 §3.1 写明「crossMarginData VIP 表 + E5 档位 → `"cross_margin_tier"`」，说明需要按 VIP 等级过滤。
- **响应字段（引用 night-collection 样本）**:
  样本路径：`reports/api-samples/night-collection-2026-07-05/20260704T155543Z/raw/classic_crossMarginData.json`
  | 字段 | 类型 | 语义 | 敏感数值 |
  |---|---|---|---|
  | `vipLevel` | INT | VIP 等级 | 否 |
  | `coin` | STRING | 币种 | 否 |
  | `transferIn` | BOOL | 是否可转入 | 否 |
  | `borrowable` | BOOL | 是否可借 | 否 |
  | `dailyInterest` | STRING | 日利率（字符串） | 否 |
  | `yearlyInterest` | STRING | 年利率（字符串） | 否 |
  | `borrowLimit` | STRING | 借币限额 | 否 |
  | `marginablePairs` | [STRING] | 支持的交易对列表 | 否 |
- **文档权重值**: 文档未见。
- **相关错误码**: 同 W1。
- **统一账户适用性**: 文档未明确；基线 §3.1 将其作为 fallback 三级来源，说明在统一账户下若 E2/E2b 不可得仍可调用。需 H_intake 实测利率是否与统一账户真实扣息一致。

#### W4. `GET /papi/v1/margin/maxBorrowable`

- **base_url**: `https://papi.binance.com`
- **鉴权类型**: `USER_DATA`
- **用途**: 账户级最大可借贷额度，用于负费率候选借币验证。
- **请求参数**:
  | 名称 | 类型 | 必填 | 默认值 | 备注 |
  |---|---|---|---|---|
  | `asset` | STRING | YES | - | 资产名，如 BTC |
  | `isolatedSymbol` | STRING | NO | - | 逐仓交易对；L37263 新增可选参数 |
- **响应字段（引用 night-collection 样本，已脱敏）**:
  样本路径：`reports/api-samples/night-collection-2026-07-05/20260704T155543Z/raw/portfolio_maxBorrowable_BTC.json`
  | 字段 | 类型 | 语义 | 敏感数值 |
  |---|---|---|---|
  | `amount` | STRING | 最大可借数量 | **是**（账户级） |
  | `borrowLimit` | STRING | 账户借贷限额 | **是**（账户级） |
- **文档权重值**: L36814「`GET /sapi/v1/margin/maxBorrowable` 请求权重从 50(IP) 更新为 750(UID)」。注意：
  - 当前实现调用的是 **papi** 版本 `/papi/v1/margin/maxBorrowable`，文档未见其权重。L36814 描述的是 sapi 同名端点。
  - 推断 papi 版本可能按 UID 统计且权重类似或更高，但**无文档证据**，标注「文档未见，需实测」。
- **相关错误码**: -2015、-1002、-1003/429、-3006（借款超限额，L37421-37424）。
- **统一账户适用性**: 文档 L186278-L186280 明确为「查询账户最大可借贷额度」，Operation ID `marginMaxBorrow`；基线 §3.6 将其列为私有-既有白名单，用于统一账户/组合保证金账户。推断为统一账户适用，但需 H_intake 实测。

---

### 本轮新增 8 项（私有签名 GET）

#### E1. `GET /papi/v1/margin/marginInterestHistory`

- **base_url**: `https://papi.binance.com`
- **鉴权类型**: `USER_DATA`
- **用途**: 统一账户下杠杆利息历史；基线 §3.1 明确「仅事后对账，不作净收益输入」。
- **文档出处**: L186218-L186222「获取杠杆利息历史；Operation ID: `getMarginBorrowLoanInterestHistory`」。
- **请求参数**: 文档未见完整参数表；推断含 `asset`、`startTime`、`endTime`、`size` 等历史查询常规参数，需实测。
- **响应字段**: 文档未见；推断为数组，元素含 `asset`、`interest`、`interestRate`、`principal`、`time` 等，需实测。
- **文档权重值**: 文档未见。
- **相关错误码**: -2015、-1002、-1003/429。
- **统一账户适用性**: 文档 L186218 位于 papi 文档区域（L186210 附近为 papi 端点列表），基线 §3.1 将其列为统一账户对账用途。标注「需 H_intake 实测是否返回统一账户数据」。

#### E1b. `GET /papi/v1/portfolio/interest-history`

- **base_url**: `https://papi.binance.com`
- **鉴权类型**: `USER_DATA`
- **用途**: 统一账户期货负余额收息历史；与 E1 并抓比对，确定统一账户真实 borrow cost 归属。
- **文档出处**: L186318-L186322「查询统一账户期货负余额收息历史；Operation ID: `queryPortfolioMarginNegativeBalanceInterestHistory`」。
- **请求参数**: 文档未见；推断含时间范围、资产等，需实测。
- **响应字段**: 文档未见；推断为数组，元素含 `asset`、`interest`、`time` 等，需实测。
- **文档权重值**: 文档未见。
- **相关错误码**: -2015、-1002、-1003/429。
- **统一账户适用性**: 文档描述已明确为统一账户期货负余额收息历史，L186320。

#### E2. `GET /sapi/v1/margin/next-hourly-interest-rate`

- **base_url**: `https://api.binance.com`
- **鉴权类型**: `USER_DATA`
- **用途**: 成本腿首选（开仓前估算）；基线 §3.1 四级 fallback 第①级。
- **文档出处**: L37035（中文 changelog）、L151129（英文 changelog）、L189205-L189211（端点列表）；描述为「查询用户币种预估下小时利率 / 查询下小时预估利率」。
- **请求参数**: 文档未见完整参数表；推断必填 `assets`（STRING，逗号分隔币种，如 `BTC,ETH`），可能含 `isIsolated`，需实测。
- **响应字段**: 文档未见；推断返回数组，元素含 `asset`、`nextHourlyInterestRate`（字符串），需实测。
- **文档权重值**: 文档未见。
- **相关错误码**: -2015、-1002、-1003/429。
- **统一账户适用性**: 基线 §3.1 明确标注「统一账户适用性 = BLOCKER 级实测」。文档 L189209「查询用户币种预估下小时利率」未区分账户类型；推断在统一账户下可能返回统一账户利率，也可能返回经典账户利率，必须实测确认。

#### E2b. `GET /sapi/v1/margin/interestRateHistory`

- **base_url**: `https://api.binance.com`
- **鉴权类型**: `USER_DATA`
- **用途**: fallback 二级 / 校验；L150994 明确为 `GET /sapi/v1/portfolio/interest-rate` 的替代端点。
- **文档出处**: L37093（移除 `limit`、时间间隔最大 1 个月）、L37170（新增端点）、L150994（官方指定替代已弃用端点）、L189231-L189235。
- **请求参数**: 文档未见完整参数表；L37093 指明「移除参数 `limit`，查询时间间隔更改为最大 1 个月」。推断必填 `asset`，可选 `startTime`、`endTime`，需实测。
- **响应字段**: 文档未见；推断返回数组，元素含 `asset`、`dailyInterestRate`（或 `interestRate`）、`timestamp` 等，需实测。
- **文档权重值**: 文档未见。
- **相关错误码**: -2015、-1002、-1003/429。
- **统一账户适用性**: 文档未明确；基线 §3.1 作为 fallback 二级。L150994 说可查询 Classic Portfolio Margin Negative Balance Interest Rate，暗示统一账户/专业版可用。需 H_intake 实测。

#### E5. `GET /sapi/v1/account/info`

- **base_url**: `https://api.binance.com`
- **鉴权类型**: `USER_DATA`
- **用途**: fallback 三级档位来源（获取 VIP 等级）。
- **文档出处**: L6704（中文 changelog）、L6615（更新 European Options / Portfolio Margin enable status）、L192408-L192414。
- **请求参数**: 文档未见；推断无必填参数，可能含 `recvWindow`、`timestamp`，需实测。
- **响应字段**: 文档未见完整字段表；L6704 明确返回「VIP 等级、是否开启杠杆账户、是否开启合约账户」。推断含 `vipLevel`（INT，敏感）、`isMarginEnabled`、`isFuturesEnabled`、`isPortfolioMarginEnabled`（L6615 新增）等，需实测。
- **文档权重值**: 文档未见。
- **相关错误码**: -2015、-1002、-1003/429。
- **统一账户适用性**: L6615 明确新增「Portfolio Margin enable status」字段，说明可检测统一账户开关状态。VIP 等级用于 crossMarginData 档位查询。

#### E3. `GET /papi/v1/balance`

- **base_url**: `https://papi.binance.com`
- **鉴权类型**: `USER_DATA`
- **用途**: 统一账户余额——已含 U 本位、币本位、全仓杠杆账户的全部资产总和（基线 §3.3）。
- **文档出处**: L186080-L186082「查询账户余额」。
- **请求参数**: 文档未见；推断无必填业务参数，需实测。
- **响应字段**: 文档未见；推断返回数组，元素含 `asset`、`totalWalletBalance`、`crossWalletBalance`、`availableBalance`、`marginAvailable` 等（参考 fapi v2 account 字段 L50340），需实测。
- **文档权重值**: 文档未见。
- **相关错误码**: -2015、-1002、-1003/429。
- **统一账户适用性**: 文档描述「查询账户余额」位于 papi 区域，基线 §3.3 明确将其作为统一账户余额来源。需 H_intake 实测字段结构。

#### E4. `GET /papi/v1/um/positionRisk`

- **base_url**: `https://papi.binance.com`
- **鉴权类型**: `USER_DATA`
- **用途**: UM 永续持仓敞口（基线 §3.3）。
- **文档出处**: L186324-L186328「用户 UM 持仓风险；获取用户 UM 持仓风险」；L49382/L54866/L59232 新增 `liquidationPrice` 字段；L49109/L54593 新增 `breakEvenPrice` 字段。
- **请求参数**: 文档未见；推断可选 `symbol`，需实测。
- **响应字段**: 文档未见完整表；已知字段（来自 changelog）：
  | 字段 | 类型 | 语义 | 敏感数值 |
  |---|---|---|---|
  | `symbol` | STRING | 交易对 | 否 |
  | `positionAmt` | STRING | 持仓数量 | **是** |
  | `entryPrice` | STRING | 开仓均价 | **是** |
  | `breakEvenPrice` | STRING | 盈亏平衡价 | **是** |
  | `liquidationPrice` | STRING | 预估强平价 | **是** |
  | `unRealizedProfit` | STRING | 未实现盈亏 | **是** |
  | `marginType` | STRING | 保证金模式 | 否 |
  | `isolatedWallet` | STRING | 逐仓钱包余额 | **是** |
  | `notional` | STRING | 名义价值 | **是** |
  | 其他仓位字段 | - | - | 部分敏感 |
  
  完整字段需实测。
- **文档权重值**: 文档未见。
- **相关错误码**: -2015、-1002、-1003/429。
- **统一账户适用性**: 文档已明确为 papi 统一账户端点。

#### E6. `GET /api/v3/account`

- **base_url**: `https://api.binance.com`
- **鉴权类型**: `USER_DATA`
- **用途**: 现货账户余额与持有标的（基线 §3.3）。
- **文档出处**: L22771（新增 `omitZeroBalances`）、L23011（权重表）、L23110-L23112（响应字段更新：preventSor、uid）、L104472-L104526（响应示例）、L110551-L110595（参数与响应示例）。
- **请求参数**:
  | 名称 | 类型 | 必填 | 默认值 | 备注 |
  |---|---|---|---|---|
  | `omitZeroBalances` | BOOLEAN | NO | false | L22771、L110553；建议启用以减少响应体 |
  | `recvWindow` | DECIMAL | NO | - | L110554 |
  | `timestamp` | LONG | YES | - | L110555 |
- **响应字段（引用 L104475-L104516、L110562-L110595）**:
  | 字段 | 类型 | 语义 | 敏感数值 |
  |---|---|---|---|
  | `makerCommission` | INT | maker 手续费率（万分之一表示） | 否 |
  | `takerCommission` | INT | taker 手续费率 | 否 |
  | `buyerCommission` | INT | buyer 手续费率 | 否 |
  | `sellerCommission` | INT | seller 手续费率 | 否 |
  | `commissionRates` | OBJECT | 手续费率对象 | 否 |
  | `canTrade` | BOOL | 是否可以交易 | 否 |
  | `canWithdraw` | BOOL | 是否可以提现 | 否 |
  | `canDeposit` | BOOL | 是否可以充值 | 否 |
  | `brokered` | BOOL | 是否经纪商账户 | 否 |
  | `requireSelfTradePrevention` | BOOL | 是否需要 STP | 否 |
  | `preventSor` | BOOL | 是否禁用 SOR | 否 |
  | `updateTime` | LONG | 更新时间 | 否 |
  | `accountType` | STRING | 账户类型（如 SPOT） | 否 |
  | `balances` | [OBJECT] | 余额列表 | **是** |
  | `permissions` | [STRING] | 账户权限 | 否 |
  | `uid` | INT | 用户 ID | 是 |
  
  `balances` 子字段：
  | 字段 | 类型 | 语义 |
  |---|---|---|
  | `asset` | STRING | 资产名 |
  | `free` | STRING | 可用余额 |
  | `locked` | STRING | 冻结余额 |
- **文档权重值**: L23011「`GET /api/v3/account` weight = 10（旧）/ 20（新）」；L152545「weight increased to 10」。按最新权重表 L23011 应取 **20**（变更后值），但需注意 llms-full.txt 存在新旧值。建议 H_intake 实测响应头。
- **相关错误码**: -2015、-1002、-1003/429。
- **统一账户适用性**: 文档未明确禁止统一账户调用；基线 §3.3 明确将其作为「现货账户」余额来源，与统一账户余额（E3）互斥相加。需 H_intake 实测统一账户下是否仍返回独立现货钱包余额。

---

### 公开市场候选（本轮涉及）

#### P1. `GET /fapi/v1/exchangeInfo`

- **base_url**: `https://fapi.binance.com`
- **鉴权类型**: `NONE`
- **用途**: 合约市场数据，获取 symbol 精度、状态、filters 等。
- **文档出处**: L46284（rateLimits 说明）、L48283、L50428、L50476、L50672、L50721 等字段更新记录。
- **请求参数**: 无必填；可选 `symbol`、`symbols`。
- **响应字段（引用 night-collection 样本）**:
  样本路径：`reports/api-samples/night-collection-2026-07-05/20260704T155543Z/raw/fapi-v1-exchangeInfo.json`
  | 字段 | 类型 | 语义 |
  |---|---|---|
  | `symbols` | [OBJECT] | 交易对列表 |
  | `symbol` | STRING | 交易对 |
  | `status` | STRING | 交易状态 |
  | `baseAsset` | STRING | 基础资产 |
  | `quoteAsset` | STRING | 计价资产 |
  | `filters` | [OBJECT] | 交易规则过滤器 |
  | `rateLimits` | [OBJECT] | 限频规则 |
- **文档权重值**: 文档未见明确值；night-collection 已实抓，可实测响应头。
- **相关错误码**: 429（限频，公开端点）。

#### P2. `GET /fapi/v1/premiumIndex`

- **base_url**: `https://fapi.binance.com`
- **鉴权类型**: `NONE`
- **用途**: 获取标记价格、资金费率、指数价格等。
- **文档出处**: L50670（新增 `estimatedSettlePrice`）、L50841（新增 `indexPrice`）。
- **文档权重值**: 文档未见。
- **相关错误码**: 429。

#### P3. `GET /fapi/v1/fundingInfo`

- **base_url**: `https://fapi.binance.com`
- **鉴权类型**: `NONE`
- **用途**: 查询有调整的资金费率信息。
- **文档出处**: L49303（新增）、L49242-L49243（限频 500/5min/IP）。
- **文档权重值**: 限频 500/5min/IP（L49242）；权重值文档未见。
- **相关错误码**: 429。

#### P4. `GET /api/v3/exchangeInfo`

- **base_url**: `https://api.binance.com`
- **鉴权类型**: `NONE`
- **用途**: 现货市场数据，用于估值价格源和 symbol 精度。
- **文档出处**: L4715、L7270 等（rateLimits 说明）；L23013（权重表 weight = 10/20）。
- **文档权重值**: L23013「10（旧）/ 20（新）」；L152547「weight increased to 10」。建议按最新值 20 估算，实测响应头确认。
- **相关错误码**: 429。

---

## B. 限频预算表初稿

### 官方限额（文档级）

| 族 | 限频模式 | 限额 | 出处 |
|---|---|---|---|
| `api.binance.com` (spot) | REQUEST_WEIGHT | 6,000 / min / IP | L22993 |
| `api.binance.com` (spot) | RAW_REQUESTS | 61,000 / 5min / IP | L22994 |
| `sapi/*` | 单接口按 IP 权重 | 12,000 / min / IP | L4767 |
| `sapi/*` | 单接口按 UID 权重 | 180,000 / min / UID | L4767 |
| `fapi.binance.com` | `fundingRate`/`fundingInfo` | 500 / 5min / IP | L49242 |
| `papi.binance.com` | order rate limit | 1,200 orders/min（仅 POST 下单，L49399） | - |
| 全 Websocket 连接 | 连接数 | 300 / 5min / IP | L22992 |

### 本轮涉及端点权重汇总（文档已知 + 推断）

| 端点 | 族 | 文档权重 | 推断/实测 |
|---|---|---|---|
| `/fapi/v1/exchangeInfo` | fapi | 文档未见 | 推断 ≤ 20；需实测 |
| `/fapi/v1/premiumIndex` | fapi | 文档未见 | 推断 ≤ 10；需实测 |
| `/fapi/v1/fundingInfo` | fapi | 限频 500/5min/IP | 权重未见；需实测 |
| `/api/v3/exchangeInfo` | api | 20 | L23011（新值） |
| `/api/v3/ticker/price` | api | 2（不带 symbol）/ 1（带 symbol） | L23025-L23026 |
| `/api/v3/ticker/bookTicker` | api | 4（不带 symbol）/ 2（带 symbol） | L23023-L23024 |
| `/api/v3/account` | api | 20 | L23011 |
| `/sapi/v1/margin/allPairs` | sapi | 文档未见 | 推断按 IP 低权重；需实测 |
| `/sapi/v1/margin/allAssets` | sapi | 文档未见 | 推断按 IP 低权重；需实测 |
| `/sapi/v1/margin/crossMarginData` | sapi | 文档未见 | 推断按 IP 中权重；需实测 |
| `/sapi/v1/margin/next-hourly-interest-rate` | sapi | 文档未见 | 推断按 IP/UID；需实测 |
| `/sapi/v1/margin/interestRateHistory` | sapi | 文档未见 | 推断按 IP/UID；需实测 |
| `/sapi/v1/account/info` | sapi | 文档未见 | 推断按 IP/UID；需实测 |
| `/papi/v1/margin/maxBorrowable` | papi | 文档未见（sapi 同名端点 750 UID，L36814） | 需实测 |
| `/papi/v1/margin/marginInterestHistory` | papi | 文档未见 | 需实测 |
| `/papi/v1/portfolio/interest-history` | papi | 文档未见 | 需实测 |
| `/papi/v1/balance` | papi | 文档未见 | 需实测 |
| `/papi/v1/um/positionRisk` | papi | 文档未见 | 需实测 |

### 三场景用量估算

**假设条件（H_intake 需全部实测修订）**：
- 公开端点按文档权重或推断值。
- 私有端点权重未文档化处暂按「1」保守占位（实际可能更高）。
- borrow 探测每 1h 一轮，单轮上限 50 调用（基线 §3.2）。
- 稳态每 60s 一轮刷新 E3/E4/E6 与 E2（成本腿）。

#### 场景 1：初始化一轮

| 调用 | 次数 | 单次权重（假设） | 合计权重 |
|---|---|---|---|
| `/fapi/v1/exchangeInfo` | 1 | 20 | 20 |
| `/fapi/v1/premiumIndex` | 1 | 10 | 10 |
| `/fapi/v1/fundingInfo` | 1 | 10 | 10 |
| `/api/v3/exchangeInfo` | 1 | 20 | 20 |
| `/api/v3/ticker/price`（全量，估值用） | 1 | 2 | 2 |
| `/sapi/v1/margin/allPairs` | 1 | 1 | 1 |
| `/sapi/v1/margin/allAssets` | 1 | 1 | 1 |
| `/sapi/v1/margin/crossMarginData` | 1 | 1 | 1 |
| `/sapi/v1/margin/next-hourly-interest-rate` | 1 | 1 | 1 |
| `/sapi/v1/account/info` | 1 | 1 | 1 |
| `/papi/v1/balance` | 1 | 1 | 1 |
| `/papi/v1/um/positionRisk` | 1 | 1 | 1 |
| **合计** | - | - | **约 69** |

#### 场景 2：稳态每 60s 一轮

| 调用 | 次数 | 单次权重（假设） | 合计权重/60s |
|---|---|---|---|
| `/fapi/v1/premiumIndex` | 1 | 10 | 10 |
| `/fapi/v1/fundingInfo` | 1 | 10 | 10 |
| `/api/v3/ticker/price` | 1 | 2 | 2 |
| `/sapi/v1/margin/next-hourly-interest-rate` | 1 | 1 | 1 |
| `/papi/v1/balance` | 1 | 1 | 1 |
| `/papi/v1/um/positionRisk` | 1 | 1 | 1 |
| `/api/v3/account` | 1 | 20 | 20 |
| **合计** | - | - | **约 45 / min** |

#### 场景 3：borrow 探测每 1h 一轮（上限 50 调用）

| 调用 | 次数 | 单次权重（假设） | 合计权重/h |
|---|---|---|---|
| `/papi/v1/margin/maxBorrowable` | ≤50 | 1（papi 未见，保守占位） | ≤50 |

### 安全余量结论（初稿）

- **api.binance.com REQUEST_WEIGHT 6,000/min**：稳态约 45/min，余量 > 99%；即使 E6 权重 20 属实，仍极宽松。
- **sapi 单接口 IP 12,000/min / UID 180,000/min**：单个 sapi 端点调用量极低，余量充足；但 `/sapi/v1/margin/maxBorrowable` 的 sapi 版本权重已改为 750(UID)（L36814），而项目实际调用的是 papi 版本，需重点实测其权重。
- **fapi fundingRate/fundingInfo 500/5min/IP**：若后续需要调用 `/fapi/v1/fundingRate`，需注意该限制；本轮主用 `/fapi/v1/fundingInfo`，同限 500/5min，足够。
- **最紧瓶颈端点（已知）**: `/sapi/v1/margin/maxBorrowable`（sapi 版本 750 UID）和 `/api/v3/account`（20 weight）。项目实际调用的是 `/papi/v1/margin/maxBorrowable`，权重文档未见，**需在 H_intake 实测并作为预算表关键修订项**。

---

## C. 现货估值价格源建议

候选端点对比（仅引用文档权重与字段）：

| 端点 | 权重（全量） | 权重（单 symbol） | 字段 | 更新语义 |
|---|---|---|---|---|
| `GET /api/v3/ticker/price` | 2 | 1 | `symbol`, `price` | 最新成交价 |
| `GET /api/v3/ticker/bookTicker` | 4 | 2 | `symbol`, `bidPrice`, `bidQty`, `askPrice`, `askQty` | 最优买卖盘 |
| `GET /api/v3/ticker/24hr` | 40~80 | 1 | `lastPrice`, `weightedAvgPrice`, `openPrice`, `highPrice`, `lowPrice` 等 | 24h 统计 |

出处：L23023-L23026。

**建议**：
- **首选 `GET /api/v3/ticker/price`**（单 symbol 权重 1，全量权重 2），字段 `price` 直接满足 USDT 估值需求，权重最低。
- 若后续需要盘口中间价或滑点建模，可降级使用 `bookTicker`（权重 2/4），但本轮仅做综合资产视图估值，`ticker/price` 足够。
- `ticker/24hr` 权重过高，不建议作为高频刷新价格源。

**需冻结的口径**：
- 价格源端点：`GET /api/v3/ticker/price`
- 调用方式：稳态每 60s 一次全量（`symbols` 或全量，权重 2~4）或按资产列表分批；stage design 需明确。
- 折算逻辑：非 USDT 资产按 `price` × 数量 → USDT；stablecoin（USDT/USDC/FDUSD 等）按 1:1 或额外 price 确认。

---

## D. websocket 订阅研究附录（纯研究，本轮不实现）

> 明确声明：本附录仅为未来「只读账户 websocket 修正案」的研究输入。根据当前冻结基线 §2/§8，`listenKey` 创建/保活/删除所涉及的 POST/PUT/DELETE 以及 `user data stream` 代码**在本轮永久禁止实现**。

### listenKey 生命周期（papi 统一账户）

| 动作 | HTTP 动词 | 端点 | 有效期/说明 | 文档出处 |
|---|---|---|---|---|
| 创建 | POST | `/papi/v1/listenKey` | 60 分钟 | L51381 |
| 保活 | PUT | `/papi/v1/listenKey` | 延长 60 分钟；收到 `-1125` 需重新 POST | L51382 |
| 失效/关闭 | DELETE | `/papi/v1/listenKey` | 立即关闭数据流 | L51383 |
| 重复 POST | POST | `/papi/v1/listenKey` | 返回当前有效 listenKey 并延长 60 分钟 | L51384 |

- 连接地址：`wss://fstream.binance.com/pm/ws/<listenKey>`（L51386-L51388）。
- 连接有效期：不超过 24 小时（L51389）。
- 消息顺序：同一连接、同一事件类型下，`T`（撮合时间）和 `E`（事件生成时间）严格有序；建议用 `E` 排序跨事件类型（L51390-L51397）。

### spot 账户 listenKey（未来修正案备选）

| 动作 | HTTP 动词 | 端点 | 权重 | 文档出处 |
|---|---|---|---|---|
| 创建 | POST | `/api/v3/userDataStream` | 2 | L23033 |
| 保活 | PUT | `/api/v3/userDataStream` | 2 | L23034 |
| 关闭 | DELETE | `/api/v3/userDataStream` | 2 | L23035 |

### user data stream 事件类型与消息结构

#### 统一账户（papi / UM futures）事件

- `ACCOUNT_UPDATE`：账户更新，推送余额 `B` 与持仓 `P` 变动（L51407-L51446）。
  - 字段 `m` 表示事件原因：DEPOSIT / WITHDRAW / ORDER / FUNDING_FEE / MARGIN_TRANSFER / ASSET_TRANSFER 等。
  - 字段 `bc` 表示钱包余额改变量（不含仓位盈亏及手续费）。
- `ORDER_TRADE_UPDATE`：订单/成交更新（papi 文档区域提及，具体字段需实测）。

#### 现货（spot）账户事件

- `outboundAccountPosition`：账户余额变动时发送，含变动的资产列表（L17493、L16450-L16464 示例）。
  - 字段：`e`（事件类型）、`E`（事件时间）、`u`（更新时间）、`B`（余额数组）。
  - 余额子字段：`a`（资产）、`f`（可用）、`l`（锁定）。
- `balanceUpdate`：充值/提现/账户间划转时发送（L17500-L17512）。
- `executionReport`：订单更新（L17514-L17523）；字段繁多，含 `x`（订单状态）、`X`（当前状态）、`q`（数量）、`p`（价格）、`z`（累计成交数量）、`Z`（累计成交金额）等。

### 统一账户与经典账户的流差异

| 维度 | 统一账户（papi） | 经典/现货账户（spot） |
|---|---|---|
| listenKey 端点 | `/papi/v1/listenKey` | `/api/v3/userDataStream` |
| websocket base | `wss://fstream.binance.com/pm` | `wss://stream.binance.com:9443/ws/<listenKey>` |
| 余额事件 | `ACCOUNT_UPDATE.B` | `outboundAccountPosition` / `balanceUpdate` |
| 持仓事件 | `ACCOUNT_UPDATE.P` | 无（现货无合约持仓） |
| 订单事件 | `ORDER_TRADE_UPDATE` | `executionReport` |

### 后续修正案需决策点

1. 是否同时维护 spot + papi 两个 listenKey？
2. 保活策略：前端/后端谁持有 listenKey？
3. 断线重连与消息乱序处理（用 `E` 排序）。
4. 只读监听下如何防止误用为交易触发器（仅展示，不自动下单）。

---

## 汇总：H_intake 硬交付前必须实测项

1. **权重实测**：所有新增私有端点（E1/E1b/E2/E2b/E5/E3/E4）及 papi 版 `maxBorrowable` 的响应头 `X-MBX-USED-WEIGHT-*` / `X-SAPI-USED-*-WEIGHT-*`。
2. **响应字段实测**：E1/E1b/E2/E2b/E5/E3/E4 的 JSON 结构与敏感字段分类。
3. **统一账户适用性实测**：
   - E2 在统一账户下是否返回统一账户利率；
   - E6 在统一账户下是否仍返回独立现货余额；
   - E3 是否真实包含 U 本位/币本位/全仓杠杆全部资产。
4. **限频预算修正**：基于实测权重重新计算三场景安全余量。
5. **现货估值 price source 实测**：`/api/v3/ticker/price` 全量 vs 单 symbol 的延迟与字段稳定性。

---

本地北京时间: 2026-07-05 23:50:00 CST
模型身份: Kimi (`kimi-code/kimi-for-coding`)
下一步模型: Fable5 / Claude-GLM（消费本报告出 stage design）
下一步任务: 用户审阅本报告后，由 bookkeeper 在 H_intake 组织 live discovery 实测并修正限频预算表
