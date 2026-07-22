# Binance 现货 + USDⓈ-M 永续 公共盘口 WebSocket 事实核查报告

**Stage:** `2026-07-hedge-open-live-v1`  
**调研日期:** 2026-07-22  
**文档来源:** `llms-full.txt`（Binance 官方文档 LLM 导出版，行号可溯源）  
**归档路径:** `reports/api-samples/2026-07-hedge-open-live-v1/websocket-bookticker-recon.md`

---

## A. Stream 选择与 Endpoint

### Q1. 现货最优买一/卖一——订阅哪个 stream？

**结论：订阅 `<symbol>@bookTicker`**

- **Stream 名:** `<symbol>@bookTicker`（例：`btcusdt@bookTicker`）
- **更新速度:** 实时（Real-time）
- **单连接可订阅多个 symbol**（同一 WS 连接可订阅多个 `@bookTicker`）
- **完整 Endpoint（生产）:**
  - 单 stream: `wss://stream.binance.com:9443/ws/btcusdt@bookTicker`
  - Combined stream: `wss://stream.binance.com:9443/stream?streams=btcusdt@bookTicker/ethusdt@bookTicker`
  - 备用端口 443: `wss://stream.binance.com:443/ws/btcusdt@bookTicker`
  - 仅市场数据备用: `wss://data-stream.binance.vision/ws/btcusdt@bookTicker`

> **文档出处:** `llms-full.txt` L97620-97640（Spot WebSocket Streams 英文文档）；L15956-15957（中文文档 baseurl 说明）

### Q2. USDⓈ-M 永续最优买一/卖一——订阅哪个 stream？

**结论：同样订阅 `<symbol>@bookTicker`，但走合约专用 host**

- **Stream 名:** `<symbol>@bookTicker`（例：`btcusdt@bookTicker`）
- **更新速度:** 实时（Real-time）
- **完整 Endpoint（生产，新版分流入口）:**
  - `wss://fstream.binance.com/public/ws/btcusdt@bookTicker`
  - Combined: `wss://fstream.binance.com/public/stream?streams=btcusdt@bookTicker/ethusdt@bookTicker`
  - 旧 URL（已于 2026-04-23 下线）: `wss://fstream.binance.com/ws/btcusdt@bookTicker`

> **重要：** 2026-04-23 旧 URL 已下线，`@bookTicker` 属于 `/public` 类，必须使用 `/public` 入口。

> **文档出处:** `llms-full.txt` L141282-141374（WebSocket Base URL 迁移公告）；L141407-141444（市场数据连接文档）；L141332-141335（Public 入口 stream 映射）

### Q3. 是否支持 Combined Stream？各自 host？

| 侧别 | Host | Combined Stream 格式 |
|------|------|---------------------|
| 现货 Spot | `wss://stream.binance.com:9443` | `/stream?streams=btcusdt@bookTicker/ethusdt@bookTicker` |
| USDⓈ-M 合约 | `wss://fstream.binance.com/public` | `/stream?streams=btcusdt@bookTicker/ethusdt@bookTicker` |

Combined stream 消息外层包装格式：`{"stream":"<streamName>","data":<rawPayload>}`

---

## B. 消息格式与字段

### Q4. 现货 bookTicker 消息完整字段

**官方文档样本**（来源: `llms-full.txt` L97631-97639）：

```json
{
    "u": 400900217,         // order book updateId（订单簿更新ID）
    "s": "BNBUSDT",         // symbol（交易对）
    "b": "25.35190000",     // best bid price（最优买价）
    "B": "31.21000000",     // best bid qty（最优买量）
    "a": "25.36520000",     // best ask price（最优卖价）
    "A": "40.66000000"      // best ask qty（最优卖量）
}
```

| 字段 | 含义 | 类型 |
|------|------|------|
| `u` | 订单簿 Update ID | INT |
| `s` | 交易对（大写） | STRING |
| `b` | 最优买价 | STRING |
| `B` | 最优买量 | STRING |
| `a` | 最优卖价 | STRING |
| `A` | 最优卖量 | STRING |

> ⚠️ **关键：现货 `<symbol>@bookTicker` 消息不含任何时间戳字段（无 `E`、无 `T`）**

### Q5. USDⓈ-M 永续 bookTicker 消息完整字段

官方文档中无独立的完整 payload 页，字段从 changelog 推导：

- **2020-05-15**（`llms-full.txt` L50998-51001）：新增 `E`（事件时间）、`T`（撮合时间）
- **2020-12-08**（`llms-full.txt` L50663）：新增 `e`（事件类型）

推导出的完整字段（**需实测抓样确认**）：

```json
{
    "e": "bookTicker",      // 事件类型 — 2020-12-08 新增
    "u": 400900217,         // 订单簿 Update ID
    "E": 1672515782136,     // 事件时间（ms）— 2020-05-15 新增
    "T": 1672515782100,     // 撮合引擎时间（ms）— 2020-05-15 新增
    "s": "BTCUSDT",         // 交易对
    "b": "25.35190000",     // 最优买价
    "B": "31.21000000",     // 最优买量
    "a": "25.36520000",     // 最优卖价
    "A": "40.66000000"      // 最优卖量
}
```

| 字段 | 含义 | 类型 | 说明 |
|------|------|------|------|
| `e` | 事件类型 | STRING | `"bookTicker"` |
| `u` | 订单簿 Update ID | INT | 单调递增 |
| `E` | 事件时间（Event time） | INT | ms，消息发出时刻 |
| `T` | 撮合引擎时间（Transaction time） | INT | ms，撮合引擎处理时刻 |
| `s` | 交易对 | STRING | 大写 |
| `b`/`B` | 最优买价/量 | STRING | 字符串小数 |
| `a`/`A` | 最优卖价/量 | STRING | 字符串小数 |

### Q6. ⭐ 时间戳字段对比（最关键）

| 字段 | 现货 `@bookTicker` | USDⓈ-M `@bookTicker` |
|------|:------------------:|:---------------------:|
| `e`（事件类型） | ❌ 无 | ✅ `"bookTicker"` |
| `E`（事件时间，ms） | ❌ **无** | ✅ **有** |
| `T`（撮合时间，ms） | ❌ **无** | ✅ **有** |
| `u`（Update ID） | ✅ 有 | ✅ 有 |

**结论：现货 `@bookTicker` 完全不带时间戳，合约 `@bookTicker` 带 `E`（事件时间）和 `T`（撮合时间）。**

---

## C. 期现延迟测量方案

### Q7. 如何计算期现时间差 ≤ 200ms？

**直接困难：** 现货 `@bookTicker` 不含任何服务器时间戳，无法与合约 `E`/`T` 直接比较。

#### 方案一：现货改用 `@depth5@100ms`（带 `E` 字段）⭐ 推荐

现货 diff depth stream 包含 `E` 字段（`llms-full.txt` L97701-97720）：

```json
{
    "e": "depthUpdate",
    "E": 1672515782136,   // Event time（ms）✅
    "s": "BNBBTC",
    "U": 157,
    "u": 160,
    "b": [["0.0024", "10"]],
    "a": [["0.0026", "100"]]
}
```

- 使用 `btcusdt@depth5@100ms`，取 `E` 与合约 `@bookTicker` 的 `E` 比较
- 从 depth5 消息取 `bids[0]`/`asks[0]` 作为 bid1/ask1，无需维护完整订单簿

**优点：** 两侧均为服务器时间戳，可比性强  
**缺点：** depth@100ms 最坏滞后 ≤100ms；`depth5` 是否带 `E` **需实测确认**

#### 方案二：现货用本地接收时刻近似（退选方案）

- 记录收到现货 `@bookTicker` 的本地时间 `t_local_spot`
- 与合约 `E_perp` 比较：`|E_perp - t_local_spot| ≤ 200ms`
- 误差由网络延迟引入（通常 1-20ms），对 200ms 阈值通常够用
- 实现最简单，无需改变现货 stream

#### 延迟测量对比

| 方案 | 现货时间口径 | 合约时间口径 | 准确性 |
|------|------------|------------|--------|
| 一（推荐） | depth5@100ms 的 `E` | bookTicker 的 `E` | 高（均为服务器时间） |
| 二（退选） | 本地接收时刻 | bookTicker 的 `E` | 中（引入网络延迟误差） |

### Q8. 各 stream 更新频率与门控影响

| Stream | 频率 | 对 200ms 门控的影响 |
|--------|------|-----------------|
| 现货/合约 `@bookTicker` | 实时 | 无固有延迟；现货无时间戳 |
| 现货 `@depth@100ms` | 每 100ms | 最坏滞后 99ms；建议将有效阈值收紧到 150ms |
| 现货 `@depth@250ms` | 每 250ms | ❌ 不适用（单次延迟即超 200ms 阈值） |

---

## D. 连接与运维

### Q9. 是否免鉴权？

**是。** 公共行情 stream 完全免鉴权，无需 API key。

### Q10. 心跳、断连规则、stream 数量、IP 限制

| 项目 | 现货 | USDⓈ-M 合约 |
|------|------|------------|
| 服务器 Ping 间隔 | 每 **20 秒** | 每 **3 分钟** |
| 客户端 Pong 期限 | **1 分钟**内须回复 | **10 分钟**内须回复 |
| 单连接有效期 | **24 小时** | **24 小时** |
| 单连接最大 stream 数 | **1024** | **1024** |
| IP 连接限制 | 300 连接/5 分钟/IP | 10 订阅消息/秒 |
| 控制消息频率 | 5 消息/秒 | 10 消息/秒 |

> 文档出处：现货 `llms-full.txt` L97046-97070；合约 `llms-full.txt` L141440-141444

### Q11. 断线重连与丢包检测

**断线重连：**
- 监听 `serverShutdown` 事件，立即建立新连接
- 24 小时强制断开，需应用层实现自动重连
- 重连后重新发送 SUBSCRIBE 消息

**丢包检测（update-id）：**
- `@bookTicker` 中的 `u` 字段**不适合**直接做丢包检测——bookTicker 是最优挂单快照，跳过中间更新属正常
- 若需严格丢包检测，改用 `@depth` stream（相邻事件应满足 `U[n+1] == u[n]+1`）

### Q12. Symbol 大小写格式

- **stream 名中 symbol 全小写：** `btcusdt@bookTicker`（现货与合约一致）
- **payload `s` 字段为大写：** `"BTCUSDT"`
- 现货与合约规则相同

---

## E. 测试网（Testnet）

### Q13. Testnet WebSocket Endpoints

| 侧别 | Testnet Host | 可用性 |
|------|-------------|--------|
| 现货 | `wss://stream.testnet.binance.vision/ws` | ✅ 公共行情可用 |
| USDⓈ-M 合约 | `wss://demo-fstream.binance.com/public` | ✅ 公共行情可用 |

- 现货 testnet 数据有一定流动性，由模拟交易驱动，可用于 dry-run
- 合约 testnet `wss://demo-fstream.binance.com` 与生产同架构，分流 `/public`/`/market`/`/private` 入口

> 文档出处：现货 `llms-full.txt` L97069-97108；合约 `llms-full.txt` L46174, L57182-57184

---

## Spot vs USDⓈ-M 差异对比表

| 维度 | 现货 Spot | USDⓈ-M 永续 |
|------|-----------|------------|
| Stream 名 | `<symbol>@bookTicker` | `<symbol>@bookTicker` |
| WS Host（生产） | `wss://stream.binance.com:9443` | `wss://fstream.binance.com/public` |
| WS Testnet | `wss://stream.testnet.binance.vision` | `wss://demo-fstream.binance.com/public` |
| 更新速度 | 实时 | 实时 |
| Symbol 格式（stream） | 全小写 | 全小写 |
| **`E` 事件时间** | ❌ **无** | ✅ **有**（ms）|
| **`T` 撮合时间** | ❌ **无** | ✅ **有**（ms）|
| `e` 事件类型 | ❌ 无 | ✅ `"bookTicker"` |
| `u` Update ID | ✅ 有 | ✅ 有 |
| Ping 间隔 | 20 秒 | 3 分钟 |
| Pong 期限 | 1 分钟 | 10 分钟 |
| 控制消息限速 | 5/秒 | 10/秒 |
| 连接 stream 上限 | 1024 | 1024 |
| Combined Stream | ✅ 支持 | ✅ 支持 |

---

## 结论段：针对「basis ≥ 0.05% 且期现延迟 ≤ 200ms」的门控实现建议

### 推荐 Stream 组合

```
现货侧:  wss://stream.binance.com:9443/stream?streams=btcusdt@depth5@100ms
合约侧:  wss://fstream.binance.com/public/stream?streams=btcusdt@bookTicker
```

- 从现货 `depth5@100ms` 取 `bids[0][0]` 和 `asks[0][0]` 作为 spot_bid1/spot_ask1，`E` 作为现货时间戳
- 从合约 `@bookTicker` 取 `b`/`a` 作为 perp_bid1/perp_ask1，`E` 作为合约时间戳
- 时间门控：`|E_perp - E_spot| ≤ 200ms`（**建议收紧到 ≤ 150ms** 为 100ms 推送窗口留余量）

### 备选方案（若 depth5 不带 E 字段）

```
现货侧:  wss://stream.binance.com:9443/stream?streams=btcusdt@bookTicker    ← 用本地时刻
合约侧:  wss://fstream.binance.com/public/stream?streams=btcusdt@bookTicker ← 用 E 字段
```

### 主要坑

1. **现货 bookTicker 无时间戳（最大坑）：** 必须改用 depth stream 或本地时刻近似
2. **depth@100ms 天然滞后：** 行情变动在推送周期内不实时，有效时间门控应更保守（150ms）
3. **合约 WS Host 已迁移：** 旧 `/ws` 路径 2026-04-23 已下线，必须用 `/public` 入口
4. **价格字段为 STRING：** 需 `float()` 转换后计算基差
5. **Combined stream 外层包装：** 需解包 `data` 字段

### 需实测抓样确认的遗留项

- [ ] 合约 `<symbol>@bookTicker` 完整 JSON 真实样本（确认 `e`/`E`/`T` 字段）
- [ ] 现货 `@depth5@100ms` 是否包含 `E` 字段
- [ ] Testnet 行情流动性是否足以用于 dry-run 基差计算
- [ ] 合约 `T` vs `E` 的实际时差分布

---

*文档来源：Binance 官方 LLM 文档 `llms-full.txt`，关键行号已标注。推导字段处标注「需实测确认」。*
