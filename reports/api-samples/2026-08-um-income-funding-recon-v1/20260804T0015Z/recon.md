# 资金费率收益 / 手续费流水 — 实盘摸排记录

| 项 | 值 |
|---|---|
| 日期 | 2026-08-04（目录戳 `20260804T0015Z`） |
| 性质 | 只读签名 GET；**无**下单 / 改 gate |
| 凭据 | `.env` 私有只读 `BINANCE_API_KEY` / `BINANCE_API_SECRET` |
| 账户 | 统一账户零售版；当前有 **8** 个非零 UM 持仓 |
| 原始策略参考 | `币安套费率策略，逐仓杠杆.js` → `GET /fapi/v1/income` |
| 统一账户对应 | `GET /papi/v1/um/income`（本轮主路径） |
| 代码现状 | `PrivateClient` **未** 白名单 income / commissionRate / feeBurn；产品无资金费累计会计 |

金额在 `sanitized/` 脱敏；正文保留结构、计数、类型分布与累计口径。

---

## 1. 一句话结论

| 问题 | 结论 |
|---|---|
| 资金费率「收益累计」拉哪个接口？ | 统一账户：**`GET /papi/v1/um/income`**，过滤 `incomeType=FUNDING_FEE`，对 `income` 求和。 |
| 原始脚本用什么？ | **`GET /fapi/v1/income`**（经典 U 本位合约）。同一套字段与 `incomeType`。 |
| 本 Key 能否打 fapi？ | **不能**。`-2015` Invalid API-key/IP/permissions。PM 账户应用 **papi**。 |
| 同一接口有没有手续费？ | **有**。不传 `incomeType` 时混排；本轮见 `COMMISSION` / `REALIZED_PNL` / `TRANSFER` / `FUNDING_FEE`。 |
| 手续费率怎么查？ | `GET /papi/v1/um/commissionRate?symbol=` + `GET /papi/v1/um/feeBurn`（是否 BNB 抵扣）。 |

---

## 2. 原始脚本对照（`币安套费率策略，逐仓杠杆.js`）

函数 `getBinanceContractFundingFeeTableInfo`（约 L580–694）：

```text
GET /fapi/v1/income?timestamp=...
```

处理逻辑：

| 脚本行为 | 含义 |
|---|---|
| 拉回数组，按 `incomeType` 分支 | 全类型流水，不只资金费 |
| `FUNDING_FEE` 且 `income>0` | 展示「收取资金费率」；`<0` →「支付」 |
| 仅当 `time > LAST_FUNDING_TIME` | 增量累加到 `symbolInfo.fundingFeeSum` / 开单 `holdInfo.fundingFeeSum` |
| `COMMISSION_REBATE` | 手续费返佣（只展示） |
| `COMMISSION` | 手续费（只展示） |
| `TRANSFER` | 划转 |
| `REALIZED_PNL` | 平仓盈亏 |
| 表格最多 40 行 | UI 截断，不是 API 限制 |
| 若最新一条是新 `FUNDING_FEE` | Sleep 10s 再拉一次（防资金费分批到账） |

全市场展示「历史收取资金费率总额」= 各 symbol 的 `fundingFeeSum` 加总（`ALL_FUTURE_FUNDING_FEE_SUM`）。

**迁移到本产品（统一账户）时：把 `/fapi/v1/income` 换成 `/papi/v1/um/income`，累计语义保持 `Σ FUNDING_FEE.income`。**

---

## 3. 文档与官方模型

### 3.1 `llms-full.txt`

- L186258：`GET /papi/v1/um/income` —「获取 UM 损益资金流水」· `getUmIncomeHistory`
- L186999 / L188941：`GET /fapi/v1/income` — 经典合约同族
- 无完整参数表；完整说明以官方 connector 为准

### 3.2 官方 connector（Portfolio Margin）

`GET /papi/v1/um/income` · Weight(IP): **30** · USER_DATA

| 参数 | 说明 |
|---|---|
| `symbol` | 可选，交易对 |
| `incomeType` | 可选；不传 = 全部类型 |
| `startTime` / `endTime` | 可选 ms |
| `page` | 可选，页码 |
| `limit` | 可选，条数；本轮 **最大 1000**（1001 → `-1130`） |
| `recvWindow` / `timestamp` / `signature` | 签名标准 |

规则（connector + 本轮验证）：

- 无时间 → **最近 7 天**（`FUNDING_FEE` default n=108 与显式 7d 集合相等）
- 历史**约近 3 个月**（connector 文案；本轮 90d/100d 有数据，200d 仍 200）
- `tranId` 在**同一 `incomeType` 内**对用户唯一（文档拼写 `trandId`）
- 响应：**数组**（不是 `{total,rows}`）

字段（`GetUmIncomeHistoryResponseInner`）：

| 字段 | 类型 | 含义 |
|---|---|---|
| `symbol` | string | 交易对；TRANSFER 可为空串 |
| `incomeType` | string | 流水类型 |
| `income` | string | 金额（收为正、付/扣为负） |
| `asset` | string | 结算资产 |
| `info` | string | 附加（资金费常为 `FUNDING_FEE`；手续费常为 trade id 文本） |
| `time` | long | 事件时间 ms |
| `tranId` | long/number | 事务 ID（幂等键，**须与 incomeType 组合**） |
| `tradeId` | string | 关联成交；资金费常为 `""` |

### 3.3 相关只读接口（本轮一并测）

| 路径 | 用途 | 实测 |
|---|---|---|
| `GET /papi/v1/um/commissionRate` | UM maker/taker 费率 | 200；样例 maker `0.000200` taker `0.000500` |
| `GET /papi/v1/um/feeBurn` | 是否 BNB 抵扣手续费 | 200；`{"feeBurn": true}` |
| `GET /fapi/v1/income` 等 | 经典合约 | **-2015**（本 PM 只读 Key 无 fapi 权限） |

---

## 4. 实盘矩阵（本账户）

### 4.1 调用结果摘要

| 调用 | status | 条数 / 类型分布 |
|---|---|---|
| papi um/income 默认 | 200 | 100（limit 默认）；COMMISSION+FUNDING 混排 |
| limit=1000 无时间 | 200 | 163：FUNDING 108 / COMMISSION 53 / REALIZED_PNL 2 |
| 7d + limit=1000 | 200 | 163（同默认） |
| 30d + limit=1000 | 200 | 193：FUNDING 134 / COMMISSION 55 / TRANSFER 2 / REALIZED_PNL 2 |
| `incomeType=FUNDING_FEE` 30d | 200 | **134**（单页拉完） |
| `incomeType=COMMISSION` 30d | 200 | **55**（全为 BNB 扣费） |
| `incomeType=COMMISSION_REBATE` | 200 | 0 |
| `incomeType=REALIZED_PNL` | 200 | 2 |
| `incomeType=TRANSFER` | 200 | 2 |
| `symbol=COOKIEUSDT` + FUNDING | 200 | 26 |
| fapi income | **401** | `-2015` |
| um/commissionRate | 200 | maker + maker/taker rates |
| um/feeBurn | 200 | `feeBurn=true` |

### 4.2 排序与分页

| 项 | 实测 |
|---|---|
| 时间序 | **升序**（旧 → 新）；与利息历史 E1 降序相反 |
| 默认 limit | 不传 limit 时样例返回 100；显式最高 **1000** |
| `page` | `page=1` / `page=2` 各 50 条，内容不重复，可拼接 |
| 幂等 | `tranId` 在 FUNDING 内 134/134 唯一；COMMISSION 55/55 唯一；**跨 type 的 tranId 无交集**（仍建议复合键 `(incomeType, tranId)`） |

### 4.3 资金费率业务观察

| 观察 | 值 |
|---|---|
| 结算资产 | 全部 `asset=USDT` |
| 符号 | 有多空敞口的 UM 交易对 |
| 正/负笔数（30d） | 收 105 / 付 29 |
| 30d 净累计 | **+0.57738482 USDT**（全 symbol 加总） |
| 结算间隔 | 依合约：常见 8h / 4h 等（`14400000`=4h、`28800000`=8h） |
| `tradeId` | 资金费行均为空串 |
| `info` | 资金费行多为 `"FUNDING_FEE"` |

按 symbol 净累计（30d FUNDING_FEE，示意排序，金额可脱敏复核）：

- 最大正贡献：如 MUUSDT、COOKIEUSDT、NOMUSDT…
- 净支付：如 RSRUSDT（对冲腿资金费成本）

### 4.4 手续费（COMMISSION）观察

| 观察 | 值 |
|---|---|
| 资产 | 本轮 **全部 BNB**（与 `feeBurn=true` 一致） |
| 符号 | 收入为负（扣费） |
| `tradeId` | **全部非空**，与成交绑定 |
| `info` | 常与 tradeId 同数字串 |
| 30d 合计 | 约 **-0.00052270 BNB**（不是 USDT；累计 PnL 时需折算） |
| `COMMISSION_REBATE` | 本账户窗口内 0 |

与资金费**同接口、不同类型**：累计「资金费收益」应用 `FUNDING_FEE`；「交易成本」另 sum `COMMISSION`（并注意资产币种）。

### 4.5 其他类型

| type | 本轮 | 用途提示 |
|---|---|---|
| `REALIZED_PNL` | 2 | 已实现盈亏，勿并入资金费累计 |
| `TRANSFER` | 2 | 划转；`symbol=""` |
| `INSURANCE_CLEAR` / `API_REBATE` / `REFERRAL_KICKBACK` | 0 | 可查，本窗口无 |

---

## 5. 累计口径建议

```text
funding_pnl(symbol?, [t0,t1]) =
  Σ income
  WHERE incomeType == "FUNDING_FEE"
    AND (symbol filter optional)
    AND t0 <= time <= t1
  幂等键: (incomeType, tranId)

commission_cost([t0,t1]) =
  Σ income WHERE incomeType == "COMMISSION"
  注意 asset 可能是 BNB/USDT；feeBurn 影响币种

net_hedge_cashflow_approx =
  funding_pnl + commission_cost(+折算) + realized_pnl(可选)
  — 不要把 TRANSFER 算进策略收益
```

对齐原始脚本：

1. 增量：只累加 `time > last_seen_funding_time` 的 `FUNDING_FEE`
2. 全量重建：按窗口拉全 + `(incomeType, tranId)` upsert 后 sum
3. 结算边界：若最新一条是新资金费，可短暂重试（脚本 Sleep 10s）

**不要**用公开 `fundingRate` / `premiumIndex` 代替真实入账金额——那是市场费率，不是账户入账。

---

## 6. 与借币利息 recon 的对比

| 维度 | 借币利息 E1 | 资金费 income |
|---|---|---|
| 主路径 | papi marginInterestHistory / sapi interestHistory | **papi um/income** |
| 响应 | `{total, rows}` | **数组** |
| 时间序 | 降序 | **升序** |
| 幂等键 | `txId` | `(incomeType, tranId)` |
| 默认窗 | ~7d | ~7d |
| 单次条数上限 | size≤100 | **limit≤1000** |
| 权重 | papi~10 / sapi~1 | **~30** |
| 节拍 | 1h PERIODIC | 4h/8h 等资金费时刻 |
| 本仓库代码 | E1 白名单无 fetcher | **完全未注册** |

---

## 7. 代码缺口与实现落点（未编码）

1. `PrivateClient.WHITELIST` 增加（建议）：
   - `GET /papi/v1/um/income`
   - `GET /papi/v1/um/commissionRate`（可选，费率展示）
   - `GET /papi/v1/um/feeBurn`（可选，解释 COMMISSION 资产）
2. **不要**依赖 `/fapi/v1/income`，除非单独开通经典合约 Key 权限。
3. 定时/按需拉 `incomeType=FUNDING_FEE`，本地 SQLite 按 `(incomeType, tranId)` 去重。
4. UI：按 symbol 累计 + 全账户净资金费；可选并列 COMMISSION（BNB）与折 USDT。
5. 与对冲任务归因：用 `symbol` + 持仓时段过滤；`REALIZED_PNL` / `TRANSFER` 分科目。

---

## 8. 安全

- 仅 GET；签名走 `binance_signing`。
- 未打印密钥；未改 `.env` / gate / 任务库。
- 全量 raw ledger 未落盘；脱敏形状见 `sanitized/`。

---

## 9. 本目录

| 文件 | 内容 |
|---|---|
| `recon.md` | 本文件 |
| `evidence-index.md` | 索引 |
| `sanitized/um-income-shape.json` | 响应形状与 type 样例 |
| `sanitized/funding-fee-summary.json` | 30d 累计结构（金额脱敏） |
| `sanitized/commission-and-feeBurn.json` | 手续费与 feeBurn/commissionRate |
| `sanitized/fapi-rejected.json` | 经典 fapi -2015 |
| `sanitized/prototype-mapping.json` | 原始脚本 → papi 映射 |
