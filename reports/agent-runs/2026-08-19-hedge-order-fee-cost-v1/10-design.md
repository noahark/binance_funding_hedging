# 10-design：成交手续费冻价成本 V1

状态：**Planner 草稿，等待跨 provider 只读计划评审与 Human 批准实现。未授权改源码、重启服务、创建任务、下单、push、merge 或部署。**
日期：2026-08-19
作者：Grok 4.6（xAI），Human 对话拍板
stage：`2026-08-19-hedge-order-fee-cost-v1`

## 1. 为什么要做

对冲成交已经落了数量、成交额、均价，但手续费列是空的。实盘库（查于 2026-08-19）`hedge_open_leg` 282 条、其中 `FILLED` 269 条，`fee_amount` / `fee_asset` 全 NULL；原始回包 417 条没有 `fills` / `commission`。

没有这笔数，持仓和历史仓位只能看资金费、借币利息、开/平滑点，**算不出交易手续费成本**。BNB 抵扣时如果用「现在的 BNB 价 × 当时扣掉的数量」，一年后 BNB 涨 100 倍，去年的手续费会假涨 100 倍。Human 要求：**下单那一刻把成本冻住。**

## 2. 现有事实（不要再推一遍）

### 2.1 币安回包形状

`commission` 和 `commissionAsset` **都不是数组**。数组的是成交列表，每笔两个普通字符串。

现货 `FULL` 示例（仓库样本 `reports/api-samples/night-collection-2026-07-05/.../phase3-candidate-interface-report.md`）：

```json
"fills": [
  { "price": "4000.00000000", "qty": "1.00000000",
    "commission": "4.00000000", "commissionAsset": "USDT", "tradeId": 56 }
]
```

本仓下单固定 `newOrderRespType=RESULT`。实盘 POST/GET 回包键只有 `executedQty` / `cummulativeQuoteQty` 或 `cumQuote` / `avgPrice` 等，**没有 `fills`**。合约订单对象从来没有手续费。

可靠来源是成交历史，按订单号拉：

| 现货路由 | 成交历史 |
|---|---|
| 普通现货 `/api/v3/order` | `GET /api/v3/myTrades` |
| 统一账户杠杆 `/papi/v1/margin/order` | `GET /papi/v1/margin/myTrades` |
| 合约 `/papi/v1/um/order` | `GET /papi/v1/um/userTrades` |

每条成交：`commission` + `commissionAsset`（标量）。一笔订单多笔成交时，按币种相加。可能出现前几笔 BNB、BNB 用尽后改扣 USDT 或本币——这是多笔成交币种不同，不是一个字段里塞数组。

### 2.2 本地表

- `hedge_open_leg` 已有 `fee_amount` / `fee_asset`，写入路径从未填。轮询回写还把它们写死成 `None`（`service.py` `resolve_leg_from_query`）。
- `hedge_open_fill` 是死表（0 行，无手续费列）。成交明细的权威是 **leg**，不要往死表加列。
- 持仓 `aggregate_positions` 已经按未平仓周期读这些腿。
- 历史仓位来自 `hedge_open_cycle_close_log`，关仓时冻资金费、利息、开/平滑点，**没有交易手续费**。
- 持仓净盈亏现算：`accrued_funding − borrow_interest_usdt`。不含交易手续费。利息在「现货余额」格里，资金费和净盈亏是独立列，开单价差率是百分比。

### 2.3 已有价格源

账户快照的 `price_map` 来自公开 `GET /api/v3/ticker/price` 全表（`fetch_ticker_price_map`），含 `BNBUSDT`，大约一分钟一刷新。市场表是费率监控宇宙，**不保证**有 BNB，不能当主价格源。不要再做一份「全局 BNB 价」。

## 3. 已拍板

| 编号 | 决定 | 不选的原因 |
|---|---|---|
| D1 | 腿上加 4 列：`fee_bnb_qty`、`fee_bnb_price`、`fee_other_qty`、`fee_other_asset`。全部 TEXT，空=未知/没有 | 一对 `fee_amount`+`fee_asset` 装不下「BNB + 另一种」。折 U 不另开列 |
| D2 | 停写 `fee_amount` / `fee_asset`，本轮不删列 | 实盘表重建风险；旧列一直是空的 |
| D3 | BNB 折 U 用写入时冻住的 `fee_bnb_price`，永不在展示时用当前价重算 | Human 明确：成本在付款当时已固定 |
| D4 | 取价顺序：进程内 `price_map["BNBUSDT"]` → 没有则公开拉一次 `BNBUSDT` → 还没有则价格空、数量仍记。缺价不当 0，不阻塞成交落库 | 成交确认路径上再打一枪只允许这一种公开行情；失败不影响订单 |
| D5 | 其他币带 `fee_other_asset`（币安已返回）。USDT 数量即 U；本币用该腿已有成交均价折 U | 不靠买/卖方向猜币种 |
| D6 | 持仓表只加开仓腿手续费成本（U），独立列；有 BNB 时第二行写 BNB 数量 | 开单成本；与每天在变的资金费/利息分开 |
| D7 | 历史仓位关仓时冻开仓+平仓全部腿的折 U 合计，独立列 | 持仓期间完整交易成本 |
| D8 | 净盈亏公式本轮不动 | 现有 11 个未平仓周期手续费全空；扣进去会整列「暂无」 |
| D9 | 不回补历史成交；不做 `hedge_open_fill`；不改开单价差率口径 | 最小范围 |
| D10 | 缺任何构成折 U 的数 → 该格「—」，部分和标不全，不当 0 | DEC-2026-07-30-001 同一条：未知不是零 |

## 4. 写入

在腿达到权威 `FILLED`（含 drain 查询）且 `order_id` 已知后，按该腿 endpoint 拉成交历史，过滤 `orderId`，按 `commissionAsset` 分组求和：

- `BNB` → `fee_bnb_qty`
- 其余若只有一种 → `fee_other_qty` + `fee_other_asset`
- 其余若多于一种（极罕见）→ 记不全，能确定的 BNB 仍写，其他两列空，并打不全标记（可用现有 error/日志，或一条布尔；计划评审若认为布尔多余则只用空列 + 日志）

`fee_bnb_price`：仅当 `fee_bnb_qty` 非空时取 D4；没有 BNB 手续费则价格也空（不要为了空数量去拉价）。

成交历史调用失败：手续费四列保持空，成交数量/均价仍按现有路径写。**不得因为手续费拉不到而把腿卡成非终态。**

白名单：`hedge_open_live_client` 目前没有 myTrades / userTrades，本轮要加三条 GET，只读。权重大约 5/次，两腿各一次。只对已接受且有成交的腿发。

## 5. 展示

### 5.1 持仓表 `GET /api/hedge-open-positions`

在「开单价差率」和「累计资金费」之间加一列 **手续费成本**。

- 只汇总该周期 `task_type=open` 且有成交的腿
- 折 U = `Σ(fee_bnb_qty × fee_bnb_price)` + `Σ(USDT 的 fee_other_qty)` + `Σ(非 USDT 的 fee_other_qty × 该腿 avg_price)`
- 任一参与腿缺必需价格 → 整格「—」或标「不全」，不要输出半截数字冒充完整
- 主数字两位小数 U，成本着色；有 BNB 时第二行数量（与利息格同形）
- `_POSITION_KEYS` 与 self-check 必须同步。建议键：`trading_fee_usdt`、`fee_bnb_qty`、`trading_fee_incomplete`

### 5.2 历史仓位 `GET /api/hedge-open-close-logs`

关仓写 `close_log` 时按开+平全部腿算出同一个折 U，冻进新列（建议 `trading_fee_usdt`，可另冻 `fee_bnb_qty`）。已关闭、没有腿手续费的历史行保持空 → 页面「—」。

表头加在「总借币利息 / 总资金费率收益」旁。本轮不新造「周期净额」列。

## 6. 非目标

- 不把手续费扣进持仓 `net_pnl`
- 不回补 2026-08-19 之前的成交
- 不改资金费/利息账本
- 不在下单 POST 改 `FULL`（PAPI 枚举是 ACK/RESULT；合约订单本来就没有 fills）
- 不展示折 U 所用 BNB 价的盘口来源时间（写入时冻价即可；评审若要求审计字段再加，不预加）
- 不授权实盘下单来验收；离线用夹具成交明细。实盘是否试一笔由 Human 另授

## 7. 风险与拆分

HIGH_RISK：账务含义、成交确认路径上新的签名 GET、持仓/历史展示。

建议拆两包，契约先冻：

1. **后端**（默认 `claude_glm`）：建列、拉成交、写四列、持仓聚合、close_log 快照、API 键、pytest。
2. **前端**（默认 `kimi`）：持仓列 + 历史列 + `self-check.js`。不得猜测键名。

计划评审要独立、跨 provider、只读；设计作者是 xAI，评审者不能是 Grok。

## 8. 验收（实现时写入 dispatch，此处是意图）

- 夹具：一笔纯 BNB、一笔纯 USDT、一笔 BNB+USDT、一笔本币、拉成交失败、缺 BNB 价。数量对，缺价不当 0，失败不挡 FILLED。
- 持仓聚合只加 open 腿；close_log 加 open+close。
- 旧 `fee_amount` 新写入保持空。
- `node frontend/self-check.js` 覆盖两列展示与「—」。
- 不跑实盘下单，除非 Human 另授。

## 9. 活文档

实现收口时由 Bookkeeper 同步：`docs/product/PRD.md`（持仓/历史字段）、`docs/api/public-market-contract.md`（positions / close-logs 键）、必要时开发指南一行。本文件在计划评审 ACCEPT 前仍是草稿，不写入 `DECISIONS.md`。
