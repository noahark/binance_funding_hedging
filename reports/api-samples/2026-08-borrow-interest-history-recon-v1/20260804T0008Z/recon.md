# 借币利息历史 / 累计 — 实盘摸排记录

| 项 | 值 |
|---|---|
| 日期 | 2026-08-04（UTC 戳 `20260804T0008Z`） |
| 性质 | 只读签名 GET；**无**下单 / 借还 / 划转 / 改 gate |
| 凭据 | 本地 `.env` 的 `BINANCE_API_KEY` / `BINANCE_API_SECRET`（私有只读通道；`BINANCE_PRIVATE_CHANNEL_ENABLED=true`） |
| 账户类型 | 统一账户零售版：`isPortfolioMarginRetailEnabled=true`，`vipLevel=0` |
| 文档对照 | `llms-full.txt` 仅有目录级一行描述；完整传参/出参以官方 connector OpenAPI 模型 + 本轮 live 为准 |
| 相关代码 | `backend/services/private_client.py`（E1/E1b 已白名单、无 fetcher；sapi interestHistory 未白名单） |
| 历史空样本 | `reports/api-samples/2026-07-private-account-v1/`、`private-account-v1-direction/borrow-rate-endpoint-survey-*`（无活跃借款时 E1/E1b 为空） |

金额类字段在 `sanitized/` 样本中脱敏；正文保留结构、计数、公式与对照结论。

---

## 1. 一句话结论

| 问题 | 结论 |
|---|---|
| 仓库有没有「利息累计」？ | **没有**。只有**利率估算**（开仓成本腿）已实现。 |
| 累计应拉哪个接口？ | **利息历史 ledger**：`GET /papi/v1/margin/marginInterestHistory` 或等价的 `GET /sapi/v1/margin/interestHistory`。 |
| 两套接口是否同一数据？ | **是**。同参同页 `txId` / `interest` / `total` 一致。 |
| 负余额息要不要并入？ | 本账户 **无** 负余额；`portfolio/interest-history` 恒为 `[]`，与普通借币息分离。 |
| 余额上的利息是什么？ | `crossMarginInterest` = **当前未结**利息，**不是**历史累计；曾还息后会与 `Σ history.interest` 分叉。 |

---

## 2. 代码现状（摸排前）

| 能力 | 接口 | 状态 |
|---|---|---|
| 下小时利率 | `GET /sapi/v1/margin/next-hourly-interest-rate` | 已实现，进快照成本腿 |
| 利率历史最新点 | `GET /sapi/v1/margin/interestRateHistory` | 已实现，fallback |
| 杠杆利息历史（E1） | `GET /papi/v1/margin/marginInterestHistory` | **WHITELIST 有，无 fetcher，装配不调用** |
| 负余额收息历史（E1b） | `GET /papi/v1/portfolio/interest-history` | 同上 |
| 经典/统一利息历史 | `GET /sapi/v1/margin/interestHistory` | **未进 WHITELIST** |
| 当前未结利息 | `GET /papi/v1/balance` → `crossMarginInterest` | 余额装配可用，非历史流水 |

设计口径（方向稿）：E1/E1b「仅事后对账，不作净收益输入」。  
产品缺口：`docs/product/PRD.md` / ROADMAP 仍列完整 borrow-interest accounting 为未实现。

---

## 3. 实盘账户侧观察（本轮）

- 余额资产约 13 条。
- **有借款 + 未结利息**的资产：6 个（1 个大仓 + 5 个本金 `1.0` 的小仓）。
- **`negativeBalance` 全 0** → E1b 无记录符合预期。
- 大仓近 7 天与 30 天历史利息合计相同 → 该仓主要利息窗口落在近 7 天。

---

## 4. 端点实测矩阵

### 4.1 利息历史（累计主源）

| # | 方法 / 路径 | base | 鉴权 | 实测权重 | 响应形状 | 本轮结果 |
|---|---|---|---|---|---|---|
| E1 | `GET /papi/v1/margin/marginInterestHistory` | `https://papi.binance.com` | USER_DATA | 约 **+10 / call**（header 累计） | `{ total, rows[] }` | 7d `total=1006`；30d `total=1647` |
| SAPI 等价 | `GET /sapi/v1/margin/interestHistory` | `https://api.binance.com` | USER_DATA | **+1 / call** | 同上 | 与 E1 同页一致；分页拉全 7d=1006、30d=1647 |
| E1b | `GET /papi/v1/portfolio/interest-history` | `https://papi.binance.com` | USER_DATA | **+50 / call** | **数组** `[]` | 30d 仍为空（无负余额息） |

**E1 ≡ SAPI interestHistory（本账户）**

- 同参：`asset=RSR`，7d，`size=10`，`current=1`
- `total` 均为 171；`txIds equal=True`；`interest equal=True`
- `principal` 字符串表示一致

**批量建议**：全量回补优先 **sapi**（权重 1）；若只维护 papi 白名单则用 E1，注意 papi IP 限频（本轮连打触发 `-1003` / 429，提示约 6000 req/min/IP）。

### 4.2 利率（不可替代累计）

| 路径 | 用途 | 实测 |
|---|---|---|
| `GET /sapi/v1/margin/next-hourly-interest-rate` | 预估下小时利率 | 200；权重约 100；`[{asset, nextHourlyInterestRate}]` |
| `GET /sapi/v1/margin/interestRateHistory` | 历史**日利率**点 | 200；UID weight +60；`[{asset, dailyInterestRate, timestamp, vipLevel}]` |

二者**没有扣息金额**，不能做累计。

### 4.3 余额快照

`GET /papi/v1/balance` 每资产关键字段：

| 字段 | 含义 |
|---|---|
| `crossMarginBorrowed` | 当前借款本金 |
| `crossMarginInterest` | **当前未结**利息 |
| `negativeBalance` | 负余额（本轮全 0） |
| `crossMarginAsset` / `totalWalletBalance` | 资产存量 |

---

## 5. 请求参数（实测有效）

### 5.1 E1 / SAPI interestHistory

| 参数 | 必填 | 实测结论 |
|---|---|---|
| `timestamp` / `signature` | 是 | HMAC-SHA256；`X-MBX-APIKEY` |
| `recvWindow` | 否 | 用配置默认 10000 |
| `asset` | 否 | 过滤单币；不传则全资产混排 |
| `startTime` / `endTime` | 否 | 毫秒；**单窗最大 30 天**；都不传 ≈ 最近 7 天 |
| `current` | 否 | 页码从 **1** 起 |
| `size` | 否 | 默认 10；**最大 100**；`size=200` → `-1102` malformed |
| `archived` | 否 | `true` 查约 6 个月前归档；本轮 `total=0` |
| `isolatedSymbol` | 仅 sapi | 统一账户全仓路径未使用 |

时间规则（与官方 connector 文档一致，本轮 7d/30d 与 default 对照吻合）：

- 无时间 → 默认约 7 天（本轮 default `total=1006` = 显式 7d）
- 只传 `startTime` → 到现在，超过 30 天截到近 30 天
- 只传 `endTime` → endTime 前 7 天
- 响应按 `interestAccuredTime` **降序**

### 5.2 E1b portfolio interest-history

| 参数 | 说明 |
|---|---|
| `asset` / `startTime` / `endTime` / `size` | 有；**无** `current` / `archived` |
| 窗口 | 同样 ≤30 天 / 默认 7 天语义 |

### 5.3 分页

- `size=100`，按 `current=1..N` 直到 `len(rows_cum) == total`
- 本轮 sapi：7d **11 页**（1006 条）、30d **17 页**（1647 条），零错误
- `txId` 窗口内唯一（1006/1647 无重复）

---

## 6. 响应字段

### 6.1 E1 / SAPI interestHistory

```json
{
  "total": 1006,
  "rows": [
    {
      "txId": 2328408217636413776,
      "interestAccuredTime": 1785798000000,
      "asset": "HOME",
      "rawAsset": "HOME",
      "principal": "1.0",
      "interest": "0.00008975",
      "interestRate": "0.00215396",
      "type": "PERIODIC"
    }
  ]
}
```

| 字段 | 类型 | 含义 |
|---|---|---|
| `total` | int | 匹配总条数（分页用） |
| `rows[].txId` | long | **幂等键** |
| `rows[].interestAccuredTime` | long | 计息时间 ms（官方拼写 Accured） |
| `rows[].asset` / `rawAsset` | string | 资产 |
| `rows[].principal` | string | 计息时本金 |
| `rows[].interest` | string | **本次计息金额**（累计 sum 此字段） |
| `rows[].interestRate` | string | **日**利率 |
| `rows[].type` | string | 见下表 |

`type` 枚举（文档 5 种；本轮出现 2 种）：

| type | 含义 | 本轮 |
|---|---|---|
| `PERIODIC` | 按小时收取 | 主路径（7d: 940 / 30d: 1576） |
| `ON_BORROW` | 借入时首次计息 | 有（7d: 66 / 30d: 71） |
| `PERIODIC_CONVERTED` | 小时息转 BNB | 未出现 |
| `ON_BORROW_CONVERTED` | 借入首息转 BNB | 未出现 |
| `PORTFOLIO` | 统一账户负余额日息 | 未出现 |

sapi 经典路径还可有 `isolatedSymbol`（全仓不返回）。

### 6.2 E1b（空数组时无元素；模型字段）

数组元素模型：`asset`, `interest`, `interestAccuredTime`, `interestRate`, `principal`（无 `txId` / `type`）。

### 6.3 计息业务规律（本轮硬证据）

| 观察 | 值 |
|---|---|
| 计息节拍 | `interestAccuredTime` 相邻差恒为 **3_600_000 ms = 1 小时** |
| 7d 计息时点数 | 167（跨约 166 h） |
| 30d 计息时点数 | 311（跨约 310 h） |
| PERIODIC 公式 | `interest ≈ principal × interestRate / 24` |
| 公式误差 | 大仓多点 ratio ∈ (0.99998, 1.00002)；**ON_BORROW / 同秒多笔** 不可用该小时均摊公式硬套 |

---

## 7. 累计口径：历史 sum vs 余额未结

| 口径 | 数据源 | 公式 | 本轮对照 |
|---|---|---|---|
| **区间已计息累计** | interestHistory `rows` | `Σ interest`（`txId` 去重） | 产品「利息累计」主口径 |
| **当前未结利息** | `balance.crossMarginInterest` | 快照 | 负债展示 |
| **当前借款本金** | `balance.crossMarginBorrowed` | 快照 | 与最新流水 `principal` 对齐 |

对照结论：

1. **从未还息的小仓**：`hist30 Σ interest` **精确等于** `crossMarginInterest`（5 个本金为 1 的资产均命中）。
2. **大仓**：`hist Σ` **>** `crossMarginInterest` → 差额表示**已还过部分利息**；历史 ledger 保留已计息，余额只剩未结。
3. 因此：**禁止**用 `crossMarginInterest` 当「历史总利息」；也**禁止**假设 `Σ history == outstanding` 恒成立。

伪代码：

```text
cumulative_interest(asset, t0, t1):
  pages = pull interestHistory(asset, startTime=t0, endTime=t1, size=100)
  upsert by txId
  return sum(interest)

outstanding_interest(asset):
  return balance[asset].crossMarginInterest   # 未结，非累计
```

长期回补：≤30 天滑动窗口 + 分页；可选 `archived=true`（本轮无数据）。

---

## 8. 与旧 discovery 对比

| 项 | 2026-07 private-account / gate-b | 2026-08-04 本轮 |
|---|---|---|
| E1 | `{"total":0,"rows":[]}` | 7d 1006 / 30d 1647 条 |
| E1b | `[]` | 仍 `[]`（仍无负余额） |
| 字段 | 推断 `rows[].interest` 等 | 全字段 + type 分布 + 公式验证 |
| papi vs sapi | 未比 | **同页完全一致** |
| 权重 | E1 +10；E1b +50 | 再确认；sapi interestHistory **+1** |

空样本不代表接口不可用，只代表**当时无活跃计息**。

---

## 9. 实现落点建议（未编码，仅结论）

1. **主数据源**：`GET /sapi/v1/margin/interestHistory`（批量）或 `GET /papi/v1/margin/marginInterestHistory`（与现有 papi 白名单一致）。
2. **幂等键**：`txId`。
3. **累计**：`SUM(interest)`，可按 `asset` / 日 / 任务归因（任务归因需另绑借还记录，本轮未摸排 loan/repay 历史）。
4. **并行展示**：余额 `crossMarginInterest` / `crossMarginBorrowed` 作「当前未结 / 本金」。
5. **不要默认合并 E1b**；仅在 `negativeBalance≠0` 或产品明确要求时并抓。
6. **代码缺口**：
   - E1/E1b：扩 fetcher（已在 WHITELIST）
   - 走 sapi 时：把 `/sapi/v1/margin/interestHistory` 加入 WHITELIST
7. **限频**：全量优先 sapi；papi 需节流，避免 429。
8. **与净收益成本腿分离**：next-hourly / rateHistory 继续服务开仓前估算；累计会计走历史 ledger。

---

## 10. 安全与操作记录

- 仅 GET；签名经 `backend.services.binance_signing`。
- 未打印 key/secret/signature/完整 query。
- 未改 `.env`、gate、DB、服务进程。
- 短时 papi 连打曾触发 IP 限频；sapi 全量分页未触发。

---

## 11. 本目录文件

| 路径 | 内容 |
|---|---|
| `recon.md` | 本文件（权威结论） |
| `evidence-index.md` | 索引与摘要 |
| `sanitized/e1-page-shape.json` | E1 响应形状（脱敏） |
| `sanitized/e1b-empty.json` | E1b 空数组 |
| `sanitized/balance-interest-fields.json` | 余额利息相关字段形状 |
| `sanitized/sapi-vs-papi-compare.json` | 同页等价结论 |
| `sanitized/rate-model-check.json` | PERIODIC 小时息公式抽检 |

---

## 12. 待 Human 决定（实现前）

1. 主通道：**sapi**（省权重）还是 **papi**（与现有私有通道一致）？
2. 累计范围：全账户 / 仅有借款资产 / 按借币任务归因？
3. 是否把 E1b 负余额息纳入同一「利息」科目（当前账户无样本，建议默认否）？
