# 10-design：成交手续费冻价成本 V1

状态：**Planner r2（计划评审 REWORK + Human 2026-08-20 回补决定）。等待再一次跨 provider 只读计划评审与 Human 批准实现。未授权改源码、重启服务、创建任务、下单、push、merge 或部署。**
日期：2026-08-19；r2：2026-08-20
作者：Grok 4.6（xAI），Human 对话拍板
stage：`2026-08-19-hedge-order-fee-cost-v1`
修订依据：`evidence/20-plan-review.handoff.md` 勘误 1 / 勘误 2（R1–R5，O2–O5）

## 1. 为什么要做

对冲成交已经落了数量、成交额、均价，但手续费列是空的。实盘库（Planner 2026-08-19 自述，计划评审未核库）`hedge_open_leg` 约 282 条、其中 `FILLED` 约 269 条，`fee_amount` / `fee_asset` 全 NULL；原始回包没有 `fills` / `commission`。

没有这笔数，持仓和历史仓位只能看资金费、借币利息、开/平滑点，**算不出交易手续费成本**。BNB 抵扣时如果用「现在的 BNB 价 × 当时扣掉的数量」，一年后 BNB 涨 100 倍，去年的手续费会假涨 100 倍。Human 要求：**下单那一刻把成本冻住。** Human 2026-08-20 追加：**上线时回溯全部历史成交，把已成交腿的手续费补齐。**

## 2. 现有事实（不要再推一遍）

### 2.1 币安回包形状

`commission` 和 `commissionAsset` **都不是数组**。数组的是成交列表，每笔两个普通字符串。本仓下单固定 `newOrderRespType=RESULT`，实盘 POST/GET 没有 `fills`。合约订单对象从来没有手续费。可靠来源是成交历史。

每条成交：`commission` + `commissionAsset`（标量）。一笔订单多笔成交时，按币种相加。可能出现前几笔 BNB、BNB 用尽后改扣 USDT 或本币。

### 2.2 按订单查成交的窗口（R4，官方 SDK / 现货 rest-api 原文）

| 腿路由 | 端点 | IP 权重 | 按订单号 | 时间窗 |
|---|---|---|---|---|
| 普通现货 `/api/v3/order` | `GET /api/v3/myTrades` | 带 `orderId`：**5**；不带：20 | `symbol` + `orderId` 是官方支持组合，**不必**带 `startTime`/`endTime` | `startTime`+`endTime` 同时传时跨度 **≤ 24h**。只按 `orderId` 查**没有**这条 24h 限制 |
| 统一账户杠杆 `/papi/v1/margin/order` | `GET /papi/v1/margin/myTrades` | **5** | 参数含 `orderId` | 若传 `startTime`+`endTime`，间隔 **< 24h**。回补时用腿上时间把窗口收在 24h 内，并带 `orderId` |
| 合约 `/papi/v1/um/order` | `GET /papi/v1/um/userTrades` | **5** | **官方 PAPI SDK 无 `orderId` 参数**（与独立 `fapi` 不同） | 都不传时间 → 默认最近 **7 天**；`startTime`/`endTime` 跨度 **不能超过 7 天**；`fromId` 不能与时间窗同传 |

合约必须：用腿的 `dispatched_at_us`（缺则 `last_query_at_us`）构造 ≤7 天窗口，拉回后**在本地**按 `orderId` 过滤。窗口外或过滤后为空 → 该腿手续费未知（D10），不当 0。

因此：**回补不能保证全覆盖**。早于合约 7 天窗、窗口构造不出、或成交历史已丢的腿会失败。R2 的不全载体仍然必需。

### 2.3 本地表与价格源

- `hedge_open_leg` 已有 `fee_amount` / `fee_asset`，写入路径从未填。drain 还把它们写死 `None`。
- `hedge_open_fill` 是死表。成交明细权威是 **leg**。
- 持仓 `aggregate_positions` 已按未平仓周期读这些腿。
- 历史仓位 `hedge_open_cycle_close_log`：`insert_close_log` 一次性 INSERT，无更新路径。`get_close_logs` 是 `SELECT *`，**列名即线上键名**，无 `_POSITION_KEYS`。
- `price_map`：公开全表 ticker。进程内可读（`get_cached_source`），上限先例 `hedge_preflight_provider._CACHE_MAX_AGE_PRICE = 5*60` 秒。
- `hedge_open_leg.avg_price` 只装交易所 `avgPrice` 原话。现货回包不带该字段，现货腿基本为 NULL。**禁止**当折 U 价格。仓内既定均价是 `cumulative_quote_amt / cumulative_base_qty`（`_cycle_leg_basis_locked`）。

## 3. 已拍板

| 编号 | 决定 | 不选的原因 |
|---|---|---|
| D1 | 腿上加 4 列：`fee_bnb_qty`、`fee_bnb_price`、`fee_other_qty`、`fee_other_asset`。全部 TEXT，空=未知/没有 | 一对旧列装不下「BNB + 另一种」 |
| D2 | 停写 `fee_amount` / `fee_asset`，本轮不删列 | 实盘表重建风险 |
| D3 | BNB 折 U 用**写入时冻住**的 `fee_bnb_price`，展示时不重算 | Human：成本在付款当时已固定 |
| D4 | 实时路径取价：进程内 `price_map["BNBUSDT"]`（max_age **300 秒**）→ 没有则公开拉一次现价 → 还没有则价格空、数量仍记。口径是「**写入时冻价**」，不是撮合瞬时价；相对成交的最大偏离受 300s 缓存 + drain 延迟约束 | 禁止为折 U 阻塞成交落库 |
| D5 | 其他币记 `fee_other_asset`。USDT 数量即 U；本币折 U **只**用该腿 `cumulative_quote_amt ÷ cumulative_base_qty`（两者任一缺失或为零 → 该腿不可定价 → D10）。**禁止使用 `hedge_open_leg.avg_price`。** 仅当 `fee_other_asset ∈ {USDT, 该腿 base 资产}` 时折算，否则该腿手续费折 U 不全 | Human 确认本来就是手动算均价；现货 `avg_price` 列基本为空 |
| D6 | 持仓表只加**开仓腿**手续费成本（U），独立列；有 BNB 时第二行写 BNB 数量 | 开单成本，不和每天在变的资金费混列 |
| D7 | 历史仓位关仓时冻开仓+平仓全部腿的折 U 合计 | 持仓期间完整交易成本 |
| D8 | 净盈亏公式本轮不动（仍是资金费 − 利息折 U） | 手续费独立列；改公式另授 |
| D9 | **上线后回溯全部本地已成交腿的手续费**（见 §4.3）。仍不做 `hedge_open_fill`；不改开单价差率口径 | Human 2026-08-20 取代原「不回补」 |
| D10 | 缺任何构成折 U 的数 → 该格「—」/不全，**不得写部分和，不当 0** | DEC-2026-07-30-001 |
| D11 | `close_log` **新增** `trading_fee_incomplete`（INTEGER，0/1）。任一参与腿缺构成量 → `incomplete=1` 且 `trading_fee_usdt=NULL`。选显式标记列，不用「只靠 NULL」一种载体 | 回补后半截数更隐蔽；`insert_close_log` 无更新路径 |

## 4. 写入

### 4.1 实时路径（开平仓，O1/O2）

腿达到权威 `FILLED` 且 `order_id` 已知之后：

1. **先提交终态事务**（成交数量/均价/状态按现有路径写完并 commit）。
2. **再**发至多 **1 次**成交历史 GET。失败不重试、不进 drain 轮询循环、任何异常只记日志，**不改腿终态**。
3. 用独立方法回写四列（例如 `update_leg_fees`），不要再走把手续费写死 `None` 的 `resolve_leg_from_query`。

两个写入站点都必须接，漏一个就会永久空：

- inline 派发回写：`store.py` `resolve_attempt` 终态提交之后
- drain 查询回写：`service.py` `resolve_leg_from_query` 终态提交之后

查询形状：

- 现货：`symbol` + `orderId`，`limit=1000`
- 杠杆：`symbol` + `orderId`，并用 `dispatched_at_us` 收 24h 窗（若带时间）
- 合约：`symbol` + `startTime`/`endTime`（以 `dispatched_at_us` 为中心，跨度 ≤7 天），本地滤 `orderId`

分组：`BNB` → `fee_bnb_qty`；其余一种且 ∈ {USDT, base} → `fee_other_*`；其余多种或第三种资产 → BNB 能定则写，其他两列空，该腿折 U 不全。

`fee_bnb_price`：仅当 `fee_bnb_qty` 非空时按 D4 取；没有 BNB 手续费则价格也空。

平滑任务每次成交是一对新腿。`target_n=20` 最坏 **40** 次签名 GET。每腿仍至多 1 次、失败不重试。权重不得再写成「一律 5、两腿各一次」——按上表逐端点计。

### 4.2 money-zero（O3）

把 `fee_bnb_price`、`fee_bnb_qty`、`fee_other_qty`、`trading_fee_usdt` 加入 `test_hedge_purity.py` 的 `_MONEY_NAMES`（不要放进 `_QUANTITY_NAMES`）。缺值不得被 `_num(` / `_decimal_str(` / `or "0"` / `.get(…,"0")` 变成 0。合法真零须 `# money-zero-ok:`。

白名单：`hedge_open_live_client.ALLOWLIST` 加三条只读 GET。

### 4.3 历史回补（R1/R5）——独立一次性任务

**范围。** 本地 `hedge_open_leg` 中 `exchange_status=FILLED`、`order_id` 非空、四列仍全空的腿。开仓腿和平仓腿都补。不 invent 没有本地订单号的成交。不改已有非空四列（幂等：已写入则跳过）。

**触发。** 独立脚本（建议 `scripts/backfill-leg-fees.py`），**Human 在操作终端明确授权后才跑**。不挂在下单、平仓、drain、worker、启动闸门上。不新增常开 HTTP 写接口（避免再开一条默认就会打交易所的通路）。服务启动不自动跑。

**控速。** 与交易路径隔离：独立节流（建议签名 GET **≤ 1 次/秒**），不用 hedge worker 的 round。遇到 429/418：**立刻停**，把断点落盘，不得重试顶配额。公开 K 线取历史 BNB 价走无签名接口，与签名配额分开。本机 2026-08-18 已有借币 IP 418、解封时间未知——回补不得在有 running 对冲任务时加速；有 running 任务则拒绝启动或自动降到更慢。

**断点。** 按 `hedge_open_leg.id` 升序。每条腿尝试至多 1 次 GET。成功写入或判定失败后推进游标。中断后从游标接着跑，已写入的腿跳过。进度写本地文件或表（一条游标即可，不新状态机）。

**冻价（回补）。** 实时路径用 D4（写入时价）。回补时「现在的 BNB 价」会改写历史成本，禁止。回补的 `fee_bnb_price` 取成交时刻附近公开 `BNBUSDT` **1 分钟 K 线收盘价**（`startTime`≈腿 `dispatched_at_us`）。取不到：数量仍写、价格空，该腿折 U 不全。两条路径都不是撮合瞬时价，文档必须写明。

**失败/部分缺失。** GET 失败、空列表、合约窗滤不到、本币不可定价、第三种资产 → 该腿四列能写的写、不能写的空，**不当 0**。持仓/历史按 D10/D11 标不全。回补结束后打印：尝试数、成功数、失败/空数、游标。不因为回补失败回滚成交终态。

## 5. 展示

### 5.1 持仓表 `GET /api/hedge-open-positions`

在「开单价差率」和「累计资金费」之间加一列 **手续费成本**。

- 只汇总该周期 `task_type=open` 且有成交的腿
- 该腿成交均价（仅用于本币折 U）= `cumulative_quote_amt ÷ cumulative_base_qty`；**不用 `avg_price` 列**
- 折 U = `Σ(fee_bnb_qty × fee_bnb_price)` + `Σ(USDT 的 fee_other_qty)` + `Σ(本币且可定价的 fee_other_qty × 上式均价)`
- 任一开仓参与腿缺必需构成量 → `trading_fee_incomplete=true`，`trading_fee_usdt=null`，页面「—」或「不全」，禁止输出半截数字
- 主数字两位小数 U，成本着色；有 BNB 时第二行数量
- 键冻死：`trading_fee_usdt`、`fee_bnb_qty`、`trading_fee_incomplete`。同步 `_POSITION_KEYS` 与 self-check

### 5.2 历史仓位 `GET /api/hedge-open-close-logs`

关仓写 `close_log` 时按开+平全部腿算折 U。`insert_close_log` **之前**这些腿必须已经做过手续费查询（实时或回补）；尚未查询不得把「还没拉」当成「本来没有」。

后端一次定死的新列（即线上键名，前端不得猜）：

| 列 | 类型 | 含义 |
|---|---|---|
| `trading_fee_usdt` | TEXT NULL | 开+平完整折 U；不全时必须 NULL |
| `trading_fee_incomplete` | INTEGER NOT NULL | 0=完整，1=不全 |
| `fee_bnb_qty` | TEXT NULL | 开+平 BNB 数量合计，供第二行 |

表头加一列「手续费成本」放在「总借币利息 / 总资金费率收益」旁。空表 `colspan` **16 → 17**。本轮不新造周期净额列。已关闭且回补仍缺数的行：`incomplete=1`、金额 NULL →「—」/「不全」。`close_log` 无更新路径，回补若发生在某周期已写入 close_log **之后**，本轮**不改写**旧结算行（避免给一次性表加 UPDATE）；该限制写进验收，后续若 Human 要刷新历史行另开任务。

## 6. 非目标

- 不把手续费扣进持仓 `net_pnl`
- 不改资金费/利息账本
- 不在下单 POST 改 `FULL`
- 不展示冻价来源时间戳
- 不授权实盘下单来验收；回补脚本须 Human 另授才对 live 库执行
- 不把回补挂进 worker / 启动闸门
- 不回写已关闭 `close_log` 行

## 7. 风险与拆分

HIGH_RISK：账务含义、成交确认路径上新的签名 GET、历史回补数百次签名 GET、持仓/历史展示。

拆包顺序（契约先冻）：

1. **后端**（`claude_glm`）：建列（腿 4 列 + close_log 3 列）、白名单、终态后一次 GET、两站点回写、持仓聚合、close_log 快照、money-zero 名单、回补脚本与断点、pytest（含两站点夹具、平滑调用上界、回补跳过已写腿）。
2. **前端**（`kimi`）：持仓列 + 历史列 + 空表 colspan=17 + `self-check.js`。排在后端之后。键名以前端 dispatch 抄后端冻名，不得推断。

计划评审再一次：跨 provider、只读；作者 xAI，评审者不能是 Grok。

下一份 dispatch 的 Inputs **禁止**再写不存在的 `backend/store.py`、`backend/services/hedge_open_live_service.py`、`backend/domain/positions.py`。实际路径：`backend/hedge_open_tasks/store.py`、`backend/hedge_open_tasks/service.py`、`backend/services/hedge_open_live_client.py`、`backend/services/live_hedge_executor.py`、`frontend/index.html`、`frontend/self-check.js`。

## 8. 验收（实现时写入 dispatch）

- 夹具：纯 BNB、纯 USDT、BNB+USDT、本币、第三种资产、拉成交失败、缺 BNB 价、合约窗滤不到 orderId。数量对，缺价不当 0，失败不挡 FILLED。
- 终态两个站点都有夹具：手续费 GET 在 commit 之后；失败不改 `terminal`/`exchange_status`。
- 每腿至多 1 次 GET；平滑 `target_n=20` 断言 ≤40 次。
- 新费用字段误写成 0 时 money-zero 检查变红。
- 持仓只加 open 腿；close_log 加 open+close；不全时金额 NULL 且 `trading_fee_incomplete=1`。
- 回补：已写腿跳过、断点续跑、running 任务时拒绝或降速、不碰 close_log 旧行。
- 旧 `fee_amount` 新写入保持空。
- `node frontend/self-check.js`：两列展示、「—」/不全、历史空表 colspan=17。
- 不跑实盘下单，除非 Human 另授。回补打 live 库须单独授权。

## 9. 活文档

实现收口时由 Bookkeeper 同步：`docs/product/PRD.md`、`docs/api/public-market-contract.md`（positions / close-logs 键）。本文件在计划评审 ACCEPT 前仍是草稿，不写入 `DECISIONS.md`。
