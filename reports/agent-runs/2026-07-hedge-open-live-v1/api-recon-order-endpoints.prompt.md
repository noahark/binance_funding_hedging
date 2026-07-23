# 摸排任务:Binance Portfolio Margin(papi)对冲开单——下单端点 + Filters 事实核查

## 背景与目标
我们要在 Binance **Portfolio Margin 统一账户(papi)** 上实现"现货 + USDⓈ-M 永续
对冲开单":两条腿都用**市价单、并发下单**。方向已锁定(不要改):
- **正向**(正费率):买现货 + 开空永续。
- **反向**(负费率):卖现货(**用已借额度卖,不自动借币**——借币走另一套现有系统)
  + 开多永续。
- 用户输入是**基础币数量**(如 0.01 BTC)× 成功次数 N;每次一笔双腿市价。

你的任务:核实实现真实下单所需的端点、参数、filters、响应、限频等事实。

## 参考资料(优先)
- 仓库内 **`llms-full.txt`**(Binance API 完整中文文档,19.3万行)。可搜关键词精准
  定位:`/papi/v1/um/order`、`/papi/v1/margin/order`、`sideEffectType`、
  `positionSide`、`MARKET_LOT_SIZE`、`LOT_SIZE`、`NOTIONAL`/`MIN_NOTIONAL`、
  `/papi/v1/balance`、`/papi/v1/account`、`exchangeInfo`、`dualSidePosition`。
- 辅以 Binance 官方 Portfolio Margin API 文档 URL 交叉验证。
- **不要臆造**端点/参数/字段;拿不准的标注"需实测确认"。

## 必须回答的问题(逐条给答案 + `llms-full.txt` 出处/章节 + 官方 URL)

### A. 下单端点与参数
1. papi **现货/杠杆**市价单端点(应为 `POST /papi/v1/margin/order`)——完整参数表
   (`symbol`/`side`/`type=MARKET`/`quantity`/`quoteOrderQty`/`sideEffectType`/
   `newClientOrderId` 等),标必填/可选。
2. papi **USDⓈ-M 永续**市价单端点(应为 `POST /papi/v1/um/order`)——完整参数表
   (`symbol`/`side`/`type=MARKET`/`quantity`/`positionSide`/`newClientOrderId`/
   `reduceOnly` 等),标必填/可选。
3. **市价单数量单位**:margin 现货市价 `BUY` 用 `quoteOrderQty`(计价币 USDT)还是
   `quantity`(基础币)?`SELL` 呢?um 永续市价用 `quantity`(基础币)?——我们输入是
   "基础币数量",必须知道每条腿每个方向该填哪个字段、单位是什么。

### B. 方向 → side / sideEffectType / positionSide
4. 正向(买现货+空永续)与反向(卖现货+多永续)各自两条腿的 `side`(BUY/SELL)。
5. margin 的 **`sideEffectType`** 各取值语义(如 `NO_SIDE_EFFECT` / `MARGIN_BUY` /
   `AUTO_REPAY` / `AUTO_BORROW_REPAY` 等)。**关键**:反向要"卖现货但**不自动借币**
   (用已借额度)",应选哪个 `sideEffectType` 才能确保不触发自动借入?正向买现货又该
   用哪个?给出确切取值。
6. um 永续**持仓模式**:单向(One-way,`positionSide=BOTH`)vs 双向(Hedge Mode,
   `LONG`/`SHORT`)。如何查询账户当前模式(`dualSidePosition`)?两种模式下"开空/
   开多"分别怎么用 `side`+`positionSide`(+`reduceOnly`)表达?

### C. 交易所 Filters(下单前校验)
7. 现货/margin 的 symbol filters 从哪个端点取(exchangeInfo)?给出 `LOT_SIZE`、
   **`MARKET_LOT_SIZE`**(市价单专用)、`NOTIONAL`/`MIN_NOTIONAL`、`PRICE_FILTER`
   的字段与含义。
8. um 永续的 symbol filters 从哪个端点取(um exchangeInfo)?同样列出 `LOT_SIZE`、
   `MARKET_LOT_SIZE`、`MIN_NOTIONAL`、`PRICE_FILTER`。
9. **数量取整**:按 `stepSize` 取整的精确规则(市价单看 `MARKET_LOT_SIZE` 还是
   `LOT_SIZE`?),以及 `minNotional` 校验(数量×价格 ≥ 阈值)。现货与合约的 stepSize/
   精度若不同,同一"基础币数量"两腿各自取整会不相等——给出处理建议(取两侧兼容的量)。

### D. 账户 / 余额 / 额度查询(papi)
10. papi 查**现货可用 USDT 余额**(正向开单校验)与**可卖/可借额度**(反向开单校验)
    的端点与字段(如 `/papi/v1/balance`、`/papi/v1/account`、maxBorrowable 类)。
11. um **持仓查询**端点与字段(用于持仓/敞口核对)。

### E. 下单响应与成交确认(单腿敞口检测用)
12. margin 与 um 市价单**下单响应**字段:`orderId`、`status`(FILLED/
    PARTIALLY_FILLED/EXPIRED/REJECTED 等)、`executedQty`、`cummulativeQuoteQty`、
    `fills`(成交价/量,用于算成交均价)。各给一条真实响应样本。
13. **如何可靠判定"一腿成交、另一腿失败"**(单腿敞口):同步下单响应的
    `status`/`executedQty` 是否足够?还是需要再查订单/成交?给出可靠方案。

### F. 权重与限频
14. margin/um 下单端点的权重、下单速率限制(如 X orders/10s、Y orders/min),以及
    papi 统一账户的限频维度。这关系"立即开单每秒一笔 + 双腿同时"会不会触发限频。

### G. 测试 / dry-run
15. papi 是否有 **testnet** 可下测试单(现货 margin + um 各自 testnet base URL)?
    若无,dry-run 就只能靠 record transport(不真发请求)。给出结论,以支撑 stage
    的 dry-run 验证方式。

## 输出要求
- 每条结论附 **`llms-full.txt` 的定位**(端点名/章节/可搜关键词)+ 官方 URL 交叉验证。
- 给出真实**端点路径 + 完整参数表** + 各一条真实**下单响应样本**(margin、um)。
- 一张表对比 **spot(margin)vs perp(um)** 的差异(端点、数量单位、positionSide/
  sideEffectType、filters)。
- **结论段**:针对我们的开单语义(正向/反向、市价双腿、基础币数量、**反向不自动
  借币**),给出每个方向每条腿的确切下单参数组合(endpoint + side + sideEffectType +
  positionSide + 数量字段/单位)+ filters 取整方案 + 单腿敞口判定方式 + 限频注意点。
- 反臆造;文档未明确处标"需实测确认"。

## 交回方式
把完整调研结果原文交回。它将作为 stage `2026-07-hedge-open-live-v1` 的契约事实证据,
由 bookkeeper 归档到 `reports/api-samples/2026-07-hedge-open-live-v1/`,与 websocket
摸排结果一起作为 stage 设计输入。
