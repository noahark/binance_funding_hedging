# 摸排任务:Binance 现货 + USDⓈ-M 永续 公共盘口 WebSocket 事实核查

## 背景与目标
我们要为一个"现货 + USDⓈ-M 永续对冲开单"系统实现**平滑开单**的下单时机门控:
只有当**期现基差达标**且**期现盘口时间对齐**时才下单。具体门控规则(已锁定,
不要改):
- 正向(正费率):basis = (perp_bid1 − spot_ask1) / mid(perp_bid1, spot_ask1)
- 反向(负费率):basis = (spot_bid1 − perp_ask1) / mid(spot_bid1, perp_ask1)
- 触发条件:对应方向 basis ≥ 0.05%(0.0005) **且** 期现两条行情流的时间戳
  abs 差 ≤ 200ms。

你的任务:用 **Binance 官方文档**(必要时可实测抓一条真实消息)核实实现这套门控
所需的 WebSocket 事实。**不要臆造字段或 endpoint**;拿不准的明确标注"需实测确认"。

## 必须回答的问题(逐条给答案 + 官方文档出处 URL)

### A. Stream 选择与 endpoint
1. 现货最优买一/卖一价量,应订阅哪个 stream?(`<symbol>@bookTicker` 还是
   `<symbol>@depth`?)完整 endpoint host 与 URL 形式是什么?
2. USDⓈ-M 永续最优买一/卖一价量,应订阅哪个 stream?完整 endpoint host 与 URL
   形式?
3. 现货与合约能否各用一条 combined stream(`/stream?streams=...`)一次订阅多个
   symbol?各自的 host 是什么?

### B. 消息格式与字段(关键)
4. 现货 bookTicker 消息的完整字段(逐个:symbol、bid price/qty、ask price/qty、
   update id 等)。给一条**真实样本**并逐字段解释。
5. USDⓈ-M 永续 bookTicker 消息的完整字段。给一条真实样本并逐字段解释。
6. **最关键**:这两类消息里**有没有事件时间戳字段**(如 `E` event time、
   `T` transaction time)?现货 bookTicker 与合约 bookTicker 在"是否带时间戳"
   上是否不同?请明确指出各自有哪些时间字段、单位(ms?)、含义。

### C. 期现"延迟"如何测量(门控核心)
7. 基于问题 6 的结论:要计算"期现两条流 abs 时间差 ≤ 200ms",应该用哪个时间口径?
   - 若两条流都带可比的事件时间戳(E/T),给出推荐字段。
   - 若现货 bookTicker **不带**时间戳,给出可行替代:是否改用现货
     `@depth@100ms`(带 E)?还是只能用**本地接收时刻**近似?各方案的准确性与
     局限说明清楚。
8. 各 stream 的更新推送频率(bookTicker 实时?depth 有 100ms/250ms/500ms 档?),
   以及这对 200ms 门控的影响。

### D. 连接与运维
9. 公共行情流是否**免鉴权**(无需 API key)?确认。
10. 心跳机制(服务器 ping 间隔、客户端 pong 期限)、单连接强制断连规则(如 24h)、
    单连接可订阅的 stream 数量上限、单 IP 连接数限制。
11. 断线重连的官方建议做法;是否有 sequence/update-id 用于检测丢包。
12. symbol 在 stream 名里的大小写/格式(如 `btcusdt@bookTicker`)。现货与合约是否
    一致。

### E. 测试网(用于 dry-run 验证)
13. 现货与 USDⓈ-M 永续是否各有 **testnet** WebSocket endpoint?host 是什么?
    公共行情流在 testnet 上是否可用、数据是否有意义?

## 输出要求
- 每条结论附**官方文档 URL**(Binance API docs;区分 Spot 与 USDⓈ-M Futures 两套
  文档)。
- 给出至少各一条**真实消息样本**(现货 bookTicker、合约 bookTicker),逐字段解释。
- 用一张小表对比 **spot vs USDⓈ-M perp** 的差异,重点标注**时间戳字段**差异。
- 最后给一个**结论段**:针对"基差 ≥0.05% 且期现延迟 ≤200ms"这套门控,推荐的
  stream 组合 + 延迟测量口径 + 需要注意的坑(尤其现货侧时间戳问题)。
- 拿不准或文档未明确处,标注"需实测抓样确认",不要编造。

## 交回方式
把完整调研结果原文交回。它将作为 stage `2026-07-hedge-open-live-v1` 的契约事实
证据,由 bookkeeper 归档到 `reports/api-samples/2026-07-hedge-open-live-v1/` 与
stage 设计输入,支撑平滑开单的真实实现。
