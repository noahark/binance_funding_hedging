# 统一账户「转账/资金流水」接口摸排

| 项 | 值 |
|---|---|
| 日期 | 2026-08-10（目录戳 `20260810T062742Z`） |
| 性质 | 只读签名 GET；**无**下单 / 划转 / 改 gate |
| 凭据 | `~/.binance-keys` / `.env` 私有只读 key |
| 账户 | 统一账户（Portfolio Margin）零售版 |
| 触发问题 | 资产互转（现货⇄统一）在 `um/income` 合约流水里看不到；怀疑 `GET /papi/v1/margin/marginAccountFlow` |
| 产品代码 | **未改**；未扩 `PrivateClient.WHITELIST` |

金额在 `sanitized/` 脱敏（保留符号/结构/计数）；`tranId` 在正文中仅用于与本地审计对照的已公开 ID。

---

## 1. 一句话结论

| 问题 | 结论 |
|---|---|
| `GET /papi/v1/margin/marginAccountFlow` 能不能用？ | **不能。** 本 Key 对多种参数组合一律 **HTTP 404**（返回币安 HTML 错误页，不是 JSON 业务码）。官方 Python/Java PM connector 路径表里也**没有**该 path。 |
| 你要的「现货⇄统一」转账记在哪？ | **在** `GET /sapi/v1/margin/capital-flow` 的 `type=TRANSFER`，以及更专的 `GET /sapi/v1/asset/transfer`（按万向划转 type 分方向查）。 |
| 能否对上本地资产互转？ | **能。** 今日两笔 10 USDT 的 `tranId`（`399260281458` / `399260348988`）在上述两个接口里都能命中。 |
| 和 `um/income` 的关系 | **无关。** `um/income` 是 UM 合约损益；其中 `TRANSFER` 是合约侧内部流水，不含 MAIN⇄PM 万向划转。 |

**展示设计建议（本轮只 recon，不定稿）：**

1. **只展示互转明细** → 优先 `GET /sapi/v1/asset/transfer`，分两次拉 `MAIN_PORTFOLIO_MARGIN` + `PORTFOLIO_MARGIN_MAIN`，方向字段清晰，`status=CONFIRMED`。  
2. **展示统一账户全仓侧总流水**（转账+借还+交易+强平等）→ `GET /sapi/v1/margin/capital-flow`，筛 `type`；转账用 `TRANSFER` 且 **正负表示进/出全仓钱包**。  
3. **不要**把产品建在 `papi .../marginAccountFlow` 上（当前不可用）。

---

## 2. 探测矩阵（实盘）

### 2.1 目标 path 与近义 path（papi）

| path | 结果 |
|---|---|
| `GET https://papi.binance.com/papi/v1/margin/marginAccountFlow` | **404** HTML（无参 / 1d / 7d / type=TRANSFER / asset=USDT 全失败） |
| `GET .../papi/v1/margin/capital-flow` | **404** HTML |
| `GET .../papi/v1/margin/capitalFlow` | **404** HTML |
| `GET .../papi/v1/margin/flow` | **404** HTML |

官方 connector（`binance-connector-python` / `binance-connector-java`）PM Account API 已登记 path 含 `um/income`、`margin/marginInterestHistory`、`margin/maxWithdraw` 等，**不含** `marginAccountFlow`。

### 2.2 真正可用的相关接口

| path | 主机 | 结果 | 用途 |
|---|---|---|---|
| `GET /sapi/v1/margin/capital-flow` | `api.binance.com` | **200** | 全仓/逐仓**资金流水**（含 TRANSFER） |
| `GET /sapi/v1/asset/transfer` | `api.binance.com` | **200**（`type` 必填） | **万向划转历史**（按 type 单向） |
| `GET /papi/v1/um/income` | `papi.binance.com` | （既有账本） | UM 合约损益；**无**今日 10U 互转 |

---

## 3. `GET /sapi/v1/margin/capital-flow`（主候选·宽流水）

### 3.1 文档（官方中文，杠杆账户接口）

- 标题：查询全仓/逐仓资金流水 (USER_DATA)  
- 权重：**100 IP**  
- 时间：最近约 **90 天**；`startTime`/`endTime` 最大间隔 **7 天**  
- 分页：`fromId`（`id > fromId`）、`limit` 默认 500、最大 **1000**  
- 逐仓需 `symbol`；本账户统一账户场景按**全仓**用（不传 symbol）

### 3.2 请求参数（实测有效）

| 参数 | 必需 | 实测 |
|---|---|---|
| `timestamp` / `signature` / `recvWindow` | 签名标准 | 是 |
| `asset` | 否 | `USDT` 可滤 |
| `type` | 否 | 见枚举；非法 type → **400** `-1102` |
| `startTime` / `endTime` | 否 | 7d 窗 OK |
| `fromId` | 否 | 可翻页 |
| `limit` | 否 | 10 / 50 / 1000 OK |
| `symbol` | 逐仓时 | 本轮未测逐仓 |

### 3.3 响应形状

- 顶层：**JSON 数组**（无 `{total,rows}` 信封）  
- 每行字段（实测 union，仅 6 个）：

| 字段 | 类型 | 含义 |
|---|---|---|
| `id` | number | 流水自增 ID（翻页键） |
| `tranId` | number | 事务 ID；**与资产互转 `tran_id` 可对齐** |
| `timestamp` | number ms | 事件时间 |
| `asset` | string | 资产 |
| `type` | string | 流水类型枚举 |
| `amount` | string | 金额；**可正可负** |

**没有** `symbol`（全仓 TRANSFER 行）、没有方向枚举字段——方向靠 `amount` 符号。

### 3.4 `type` 枚举（文档 + 本账户 7d 实测计数）

| type | 中文（文档） | 本轮 7d 有数据？ |
|---|---|---|
| `TRANSFER` | 转账 | 是（24） |
| `BORROW` | 借款 | 是（8） |
| `REPAY` | 还款 | 是（4） |
| `BUY_INCOME` / `BUY_EXPENSE` | 买单收支 | 是 |
| `SELL_INCOME` / `SELL_EXPENSE` | 卖单收支 | 是 |
| `TRADING_COMMISSION` | 交易手续费 | 是（28） |
| `BUY_LIQUIDATION` / `SELL_LIQUIDATION` / `REPAY_LIQUIDATION` | 强平相关 | 是 |
| `OTHER_LIQUIDATION` / `LIQUIDATION_FEE` | 其他强平/清算费 | 枚举接受，本窗 0 |
| `SMALL_BALANCE_CONVERT` / `COMMISSION_RETURN` | 小额兑换/手续费返还 | 枚举接受，本窗 0 |
| `SMALL_CONVERT` | 强平小额转换 | 是（14） |

`type=INVALID_TYPE_XYZ` → HTTP 400 `code=-1102`（mandatory/malformed type）。

### 3.5 与资产互转对照（关键）

本地 `data/asset-transfer.sqlite3` 成功记录 vs capital-flow：

| 本地方向 | tranId | capital-flow `type` | `amount` 符号 | 时间 (CST) |
|---|---|---|---|---|
| 现货→统一 | `399260348988` | `TRANSFER` | **正**（进全仓） | 2026-08-10 13:55:45 |
| 统一→现货 | `399260281458` | `TRANSFER` | **负**（出全仓） | 2026-08-10 13:55:31 |
| 现货→统一 | `399216264416` | `TRANSFER` | **正** | 2026-08-10 11:08:07 |
| 现货→统一 | `399072495589` | `TRANSFER` | **正** | 2026-08-10 00:47:04 |

解释（账户模型）：

- 统一账户进出走**全仓保证金钱包**；  
- capital-flow 站在**全仓钱包**记账：转入 PM = 正，转出 PM = 负；  
- **同一 `tranId`** 可与万向划转 / 本系统审计对齐。

### 3.6 排序与分页（实测印象）

- 无参 `limit=50`：返回较新片段（含今日互转）。  
- 7d + `limit=1000`：本账户 **149** 行，时间约 `2026-08-05 21:20` … `2026-08-10 13:55`。  
- 精确排序未做双向严格证明；设计时应用 `timestamp`/`id` 本地排序，不依赖隐式序。  
- 翻页用 `fromId`（文档：`id > fromId`）。

### 3.7 权重

文档 **100 IP** / 次；实测有 `X-SAPI-USED-IP-WEIGHT-*` 头（见 probe meta）。密集拉 7d×多 type 要注意限频。

---

## 4. `GET /sapi/v1/asset/transfer`（专候选·万向划转）

### 4.1 行为（实测）

| 条件 | 结果 |
|---|---|
| 不传 `type` | **400** `-1102` Mandatory parameter `type` |
| `type=MAIN_PORTFOLIO_MARGIN` | **200**，现货→统一 |
| `type=PORTFOLIO_MARGIN_MAIN` | **200**，统一→现货 |

### 4.2 响应形状

```text
{ "total": <number>, "rows": [ ... ] }
```

行字段：

| 字段 | 含义 |
|---|---|
| `timestamp` | ms |
| `asset` | 资产 |
| `amount` | 金额字符串；**本轮样本恒为正** |
| `type` | 划转 type（即方向） |
| `status` | 如 `CONFIRMED` |
| `tranId` | 与 capital-flow / 本地审计一致 |

方向语义：

| type | 业务方向 | 展示建议 |
|---|---|---|
| `MAIN_PORTFOLIO_MARGIN` | 现货(MAIN) → 统一(PM) | 「现货 → 统一账户」 |
| `PORTFOLIO_MARGIN_MAIN` | 统一 → 现货 | 「统一账户 → 现货」 |

### 4.3 与本地对照

- `399260348988` 出现在 `MAIN_PORTFOLIO_MARGIN` 列表，`status=CONFIRMED`  
- `399260281458` 出现在 `PORTFOLIO_MARGIN_MAIN` 列表，`status=CONFIRMED`  

30 天窗：`MAIN_PORTFOLIO_MARGIN` 约 10 行、`PORTFOLIO_MARGIN_MAIN` 约 11 行（本账户；含非 USDT）。

### 4.4 设计含义

- **优点**：方向枚举清晰、有 `status`、与互转产品一一对应。  
- **缺点**：必须**按 type 分别请求**（至少 2 次）才能拼「双向互转」；其它万向 type（若以后要）还要扩展。  
- 参数名用 `size`/`current` 分页（与 capital-flow 的 `limit`/`fromId` 不同）。

---

## 5. 与现有「合约资金流水」对比

| 维度 | `um/income`（已接入流水日志右栏） | `capital-flow`（本轮） | `asset/transfer`（本轮） |
|---|---|---|---|
| 路径 | `/papi/v1/um/income` | `/sapi/v1/margin/capital-flow` | `/sapi/v1/asset/transfer` |
| 账户视角 | UM 合约钱包损益 | 全仓杠杆钱包资金流水 | 万向划转台账 |
| 现货⇄统一 10U | **无** | **有** `TRANSFER` ± | **有** 分 type |
| 资金费 | 有 `FUNDING_FEE` | 无 | 无 |
| 借还 | 无 | `BORROW`/`REPAY` | 无 |
| 本仓库 | 已白名单 + ledger | **未**白名单 | **未**白名单 |

`um/income` 里旧的 `TRANSFER 0.727…` **仍然**只是合约侧 TRANSFER，不要与 capital-flow 的 TRANSFER 混为一个筛选项而不标注数据源。

---

## 6. 展示设计可用素材（供后续）

### 6.1 若做「资产互转历史」页/块

- 数据源：`asset/transfer` × 两 type，或 capital-flow `type=TRANSFER` 单源。  
- 推荐字段：时间、方向、资产、数量、状态（仅 asset/transfer）、`tranId`。  
- 方向映射：  
  - asset/transfer：看 `type`  
  - capital-flow：`amount>0` → 入统一；`amount<0` → 出统一（文案需写清「相对全仓钱包」）  
- 幂等/去重：`tranId`（capital-flow 另有 `id` 翻页）。  
- 可与 `data/asset-transfer.sqlite3` 左连，补本系统 `client_request_id` / 发起端。

### 6.2 若做「全仓资金流水」宽表

- 数据源：仅 `capital-flow`。  
- 筛选：与文档 type 表对齐；默认可只开 `TRANSFER` + `BORROW` + `REPAY`。  
- 注意：7 天窗限制 → 自定义更长区间要**切片请求**拼。  
- 权重 100：适合手动刷新/小时级，不适合秒级轮询。

### 6.3 明确不要做的

- 不要依赖 `papi/v1/margin/marginAccountFlow`（404）。  
- 不要把互转塞进现有 `um/income` 右栏而不换源（会永远对不齐）。  
- 不要假设 capital-flow 的 `amount` 恒正。

---

## 7. 本仓库代码现状

| 组件 | 状态 |
|---|---|
| `PrivateClient.WHITELIST` | **无** capital-flow / asset/transfer / marginAccountFlow |
| 流水日志 | 只读 `interestHistory` + `um/income` |
| 资产互转写路径 | `POST` 万向划转 + `asset-transfer.sqlite3` 审计；**无**历史拉回 |

接入产品前需要：白名单 + fetcher +（可选）本地落库与 `um/income` 分栏，属新能力，非本 recon 范围。

---

## 8. 证据文件

见同目录 `evidence-index.md` 与 `sanitized/*`。

原始 body **未**落盘（含金额）；脱敏分析 JSON 保留结构与 `tranId` 对照结论。
