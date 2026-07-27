# Direction Draft — Hedge Open Real API v1（Kimi / kimi27 独立草案）

本草案针对"真实 Portfolio Margin 立即开单"里程碑提出有边界的阶段设计。事实（来自
recon 报告、公开样本与前轮已接受文档）与设计选择分开标注。全程只读：未改动源码、
未访问凭据、未发送订单、未发起任何 Binance 私有请求。

## 0. 事实基线（facts，不含设计判断）

1. PAPI margin MARKET 单接受 `quantity` 与 `quoteOrderQty` 二选一（互斥）；UM MARKET
   单只接受 `quantity`，无 quote-order-quantity 模型。（recon §1，supplied-doc 事实）
2. 用户已把执行契约冻结为：**两个方向两腿都传固定基础币 `quantity=q_common`**，
   两腿并发；`quoteOrderQty` 不在本阶段执行契约内。原先 recon 的 B-1/B-2
   （正向必须串行、单腿窗口）因此被用户决策消除，不再成立。
3. PAPI 无 testnet，也没有独立 `exchangeInfo`；filters 必须来自公开
   `api.binance.com/api/v3/exchangeInfo`（现货）与
   `fapi.binance.com/fapi/v1/exchangeInfo`（UM），零值 filter 字段表示该约束关闭
   （MARKET_LOT_SIZE 全零 → 回退 LOT_SIZE）。（recon §2、§3.4；对应 F-003）
4. 任何 timeout/5xx/断连后的订单状态不可信，必须按持久化 client id 查询
   （`/papi/v1/margin/order`、`/papi/v1/um/order`、`myTrades`/`userTrades`、
   `positionRisk`），503 "Unknown error" 语义为"可能已成功，禁止直接重发"。
   （recon §3.3）
5. 前轮 round-1 已接受：durable SQLite 任务、全局 Start 门、`APP_HEDGE_EXECUTOR`
   开关、record transport dry-run、单腿暴露状态机（不自动修复）、以及 F-003…F-006
   四个待修复项。

## 1. 对冻结假设的审查（不静默替换，仅标注）

**1.1 并发双腿 + 固定 `q_common` 是一个可辩护但不免费的取舍。** 并发把单腿暴露窗口
压缩到网络 RTT 量级，但两腿的成交结果是独立的：一条腿 FILLED、另一条 REJECTED
（余额不足、-2011 限频、MARKET_LOT_SIZE max 拦截）时照样产生裸腿。冻结输入中"两腿
并发在 attempt 持久化之后提交"是对"串行 spot-fill→UM 派生"模型的替代，它**假设两腿
都被交易所接受的概率足够高**。这个假设在大额或薄流动性 symbol 上会变差。建议在
设计文档中显式记录：并发的风险对冲是"先持久化 + 按 client id 核对 + 暂停不修复"，
而不是"两腿必然同时成立"。**这不需要推翻冻结决策，只需要求 preflight 在发送前把
可拒绝的原因（余额、min/max、notional、限频余量）尽可能前置拦截。**

**1.2 "两腿 FILLED 即成功、不做成交数量相等校验"与 `q_common` 语义存在轻微内部
张力，但一致。** `q_common` 落在两腿公共网格上，理论上两腿 FILLED 时 executedQty
应当相等（都是全吃对手盘的 MARKET 单）。冻结输入说不做相等校验、只记录差额——这是
对的：若未来出现不等（部分成交+ IOC 语义差异、过滤器边缘），记录胜于断言失败。
**但要澄清一个语义点：MARKET 单的"FILLED"状态意味着全部成交，"部分成交"在正常
MARKET 路径下通常体现为成交数量小于请求但状态仍可能报 FILLED（极端流动性枯竭）。
因此"partial"分类不能只看 status 字段，必须比较 `executedQty` 与 `q_common`。**
建议把冻结输入里的"partial"明确为 `status=FILLED && executedQty < q_common` 或
`status=PARTIALLY_FILLED`，否则状态机会漏分类。这是一个需要用户/设计确认的语义
细化，不是替换。

**1.3 "无产品数值上限"是用户已确认的决策，但它把全部数值风险转移给了操作员输入
与交易所过滤器。** 这与 PRD Risk Controls 中"per-order / per-symbol / total notional
必须可配置"存在文档级冲突。建议在阶段设计中记录：本阶段以用户决策为准（不实现数值
上限），同时把 PRD 的风险控制条款标注为"已被 2026-07-23 用户决策显式覆盖"，避免
后续评审把 PRD 当最高权威时产生矛盾。服务端仍须用新鲜只读数据校验余额与账户状态
（这是冻结输入保留的强制项），只是不校验"金额是否超过某个产品上限"。

**1.4 `NO_SIDE_EFFECT` 下正向 BUY 的隐含前提。** 正向 margin BUY `quantity=q_common`
+ `NO_SIDE_EFFECT` 不会自动借款，因此 preflight 必须验证 USDT 端
`crossMarginFree(USDT) >= q_common × 保守估计价`（且建议乘 N 次尝试的总量，或至少
单次量并逐次复查），否则交易所侧 REJECTED 才暴露。反向 SELL 同理要求
`crossMarginFree(base) >= q_common`（沿用 ADR-3：`maxBorrowable` 仅作旁证）。这与
冻结输入"available balance/account status 强制"一致，但应在设计中写成逐方向的
显式不等式，而不是笼统的"balance check"。

## 2. 建议的阶段设计（design choices）

### 2.1 范围边界

- 本里程碑：regular PM、立即模式、真实 PAPI POST 适配器（含 record transport 保留为
  默认）、真实只读 preflight、F-003…F-006 修复、UI 接线。激活（live 开关 + 全局
  Start + 首个真实任务）仍是独立的人类动作，与 00-intake 的用户决策一致。
- 非目标：smooth/websocket 模式、自动借还、自动平仓、自动修复、PM-Pro 适配、
  `quoteOrderQty` 执行路径、任何数值风控上限。

### 2.2 Preflight / 只读输入（每次 attempt 前、TTL 受限）

1. 公开 exchangeInfo 双市场（带缓存与版本戳，filter 变更 fail-closed 重新读取）；
   计算两腿有效 MARKET_LOT_SIZE/LOT_SIZE 网格与公共步进
   `grid = lcm(step_spot_eff, step_um_eff)`（Decimal）。
2. `GET /papi/v1/balance`：方向相关余额不等式（§1.4）。
3. `GET /papi/v1/account`：`accountStatus == NORMAL`，记录 `uniMMR` 快照。
4. `GET /papi/v1/um/positionSide/dual`：快照到任务；流程内永不切换模式。
5. `GET /papi/v1/rateLimit/order`：持久化限频快照，进入调度节流（F-004）。
6. 新鲜价格源用于 notional 预估（公开 bookTicker 或标记价，仅作校验用途，不构成
   下单参数）。
7. preflight 快照整体写入 attempt 记录（不可变），供事后审计与复核。

### 2.3 Decimal 与 filter 行为

- 全部数量/价格/金额走 `Decimal` 定点，逐腿序列化，禁科学记数法；不以
  `quantityPrecision`/`baseAssetPrecision` 代替 filter stepSize。
- `q_common = floor(input / grid) * grid`；随后逐项校验：两腿 min/max、现货
  `NOTIONAL`（`applyMinToMarket` 时用保守价）、UM `MIN_NOTIONAL`（用 mark price）。
  任一不满足 → attempt 在持久化前拒绝（`rejected_preflight`），不发送任何 POST。
- F-003 修复并入：零值 filter 字段归一化为"约束关闭"，MARKET_LOT_SIZE 关闭时回退
  LOT_SIZE；该逻辑必须有逐 filter 的单测覆盖公开样本（BTCUSDT 现货
  MARKET_LOT_SIZE 全零的案例）。

### 2.4 Durable attempt 与状态机

- 复用并强化 round-1 的 attempt 结构：`attempt_id`、两腿确定性 client id（由
  attempt_id 派生）、方向、symbol、`q_common`、preflight 快照、状态。
  **F-005：持久化必须先于任何 POST 落盘并可见（先 commit 再 send），用事务顺序
  测试证明。**
- 状态机（沿用 round-1 骨架，按本阶段语义细化）：
  - `persisted` → 并发双腿 POST → 逐腿响应分类。
  - 两腿均 `FILLED` → 记录实际 executedQty/cummulativeQuoteQty/均价/费率（若有），
    记录差额（不校验相等）；若任一 `executedQty < q_common` 或状态非 FILLED →
    `partial_or_unresolved` → 暂停 + 按 client id 核对。
  - timeout/5xx/断连 → `unknown`，按 recon §3.3 序列核对（绝不重发同 client id；
    503 Unknown error 必须先查后定）。
  - 单腿成立、另一腿 REJECTED/不存在/核对后仍未知 → `exposure_alert` + 暂停
    全局调度，记录两腿真实状态与 positionRisk 快照；无自动修复。
  - 两腿 FILLED 但 executedQty 不等 → 新增可复核表示（替换
    `both_mismatched_contract_gap`）：记录双腿实际值与残差，**不**谎报某腿缺失；
    按用户决策不因此暂停，但 UI 需可见。
- F-006：移除 fill-all 空转；live 模式下每个人工动作（start/pause/fill-once 等）
  重新审计是否过全局 Start 门。

### 2.5 并发派发与核对

- 两腿并发用 asyncio 单事件循环（与 round-1 设计一致），两个 POST 共享一个
  attempt 上下文；响应按 client id 归位。
- 限频：一次 attempt = 2 个下单事件，调度器消费持久化的 `/rateLimit/order` 快照；
  429/418 → 停止派发、保留未发任务、不为追赶而重试（F-004）。
- 重启恢复：启动时扫描非终态 attempt，按 client id 重查归类后再决定是否恢复调度；
  永不自动补发。

### 2.6 真实 POST 门（gate proof）

真实 POST 可达当且仅当以下全部成立（任一不满足 fail-closed）：
`APP_HEDGE_EXECUTOR=live`（进程启动时固定）∧ 持久化全局 Start 门 ON ∧ preflight
新鲜（TTL 内，建议 ≤30s，由设计定值）∧ attempt 已先于 POST 持久化 ∧ 首个 live 任务
有人类显式确认记录。**必须有一个测试证明：去掉任意一个门，真实 POST 路径不可达
（record transport 是唯一路径）。** 该测试是 review 的核心证据。

### 2.7 API / UI 契约

- 后端沿用 `hedge_open_tasks` 路由族（创建/list/pause/start/delete/fill-once），
  请求体把 round-1 的 `single_amount` 语义明确为**单次尝试基础币数量**（与前端
  "每单数量 + 次数"输入一致），响应返回服务端算出的 `q_common` 与拒绝原因。
- 新增/更新：执行徽标（executor 模式 + Start 门 + preflight 新鲜度）、attempt 明细
  （双腿 client id、实际成交、差额、核对轨迹）、`exposure_alert` 展示（含
  both-filled-mismatch 的可复核表示）。
- 前端不改 contract 字段名之外的东西；输入校验只做展示，所有数值判定在服务端。

### 2.8 测试策略

- CI 禁真网：公开样本 fixture（现货/UM exchangeInfo）+ record transport + 注入式
  结果；真实下单响应样本留给后续人类授权的真实订单（不伪造）。
- 单测：filter 解析（含零值关闭与回退）、公共网格 floor、逐腿 notional 校验、
  余额不等式、client id 派生确定性。
- 状态机测试：两腿 FILLED、单腿、partial（`executedQty < q_common`）、timeout→
  核对→FILLED、核对→不存在→REJECTED、核对超时→UNKNOWN、429/418 停止、重启
  恢复路径。
- 门测试：§2.6 的五门缺一不可达真实 POST。
- 回归：F-003…F-006 每项至少一个定向测试。

### 2.9 文件 / 任务切分建议（供 breakdown 参考）

- 后端（Claude-GLM）：`backend/hedge_open_tasks/` 内 filters 模块（解析/回退/网格）、
  preflight 模块、live executor（PAPI 签名 POST + record transport 复用）、状态机与
  核对查询、限频节流、F-003…F-006 修复、后端测试。
- 前端（Kimi）：任务创建输入语义调整（基础币数量 + 次数）、attempt 明细与
  exposure 展示、执行徽标扩展、self-check 契约更新。
- 契约先冻结（API 形状 + attempt 字段），两端再并行。

### 2.10 残余风险（明确列出）

1. 并发双腿仍可能在交易所侧一条成立一条被拒（余额边缘、限频竞争、流动性瞬变）——
   只能靠核对+暂停兜底，不能靠设计消除。
2. `q_common` 低于 UM `MARKET_LOT_SIZE.minQty` 或 `MIN_NOTIONAL` 时整单被拒是正确
   行为，但操作员可能困惑：UI 必须把拒绝原因（哪个 filter、差多少）讲清楚。
3. 无 testnet 意味着真实签名/真实响应形状只有首次人类授权的 live 单才能验证；
   record transport 与真实 POST 的参数序列化必须共用同一代码路径，降低"dry-run
   对了、live 错了"的风险。
4. 时钟偏移影响签名 recvWindow 与 preflight TTL 判定；本阶段不含 websocket 门，
   但应保留 serverTime 校准日志（DI-1 的监控要求延续）。
5. 无产品数值上限意味着误输入（多打一个零）没有软件兜底——这是已确认的用户决策，
   建议在创建确认弹窗中回显 notional 估值（显示用，非限额），成本极低、防呆价值高。
6. PM-Pro 账户未验证；设计文档应写明"regular PM only，PM-Pro 出范围"。

## 3. 与推荐方向的关系

01-design-discussion 的"控制面优先 + 数值上限"提案已被 2026-07-23 用户决策取代
（无数值上限、固定基础币数量、两腿并发）。本草案以冻结输入为准；其中"控制面先于
POST 激活"的精神保留为 §2.6 的五门结构与首个 live 任务的人类确认，但不再主张
把 POST 适配器拆到单独的激活阶段——用户已明确本里程碑包含真实适配器，激活本身是
独立人类动作。

当前 Session ID: unavailable (Kimi Code CLI 运行时未暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/direction-drafts/kimi27.md
本地北京时间: 2026-07-23 16:23:03 CST
下一步模型: bookkeeper
下一步任务: archive this raw direction draft; do not implement code
