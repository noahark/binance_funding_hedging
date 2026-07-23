# Codex 独立方向草案 — Hedge Open Real API v1

模型：**GPT-5 Codex**  
Provider：`codex`  
Direction panel model-id：`codex`

## 一、结论

建议把本里程碑定义为：

> 在现有 immediate dry-run 骨架上，补齐真实、只读、逐 attempt 的 Portfolio
> Margin preflight，修复持久化与限频缺口，并加入一个默认不可触达、精确
> allowlist、无自动 POST 重试的双腿真实下单 executor。每个 attempt 先提交 durable
> intent，再并发发送两笔固定基础币数量 `quantity=q_common` 的 MARKET 单；任何单腿、
> partial、timeout 或 unknown 结果立即停止后续 dispatch 并进入只读对账。交付和验收
> 不等于授权启用 `live`、打开全局 Start 或执行第一笔真实任务。

本阶段应当落真实 POST 代码，但不执行真实 POST，也不把一次代码合并变成交易授权。
`APP_HEDGE_EXECUTOR=live`、单一执行 owner、专用交易凭据存在、全局 Start、任务级确认、
新鲜 preflight、无未决 attempt、限频可用以及第一笔 live 的单独人类授权，必须同时
成立，才允许 executor 触达 POST。

平滑 WebSocket gate、自动借币、自动还币、自动补腿、自动平仓、手动平仓实现、转账、
完整会计和 PM-Pro 均不进入本阶段。

## 二、事实、当前冻结选择与不得静默合并的冲突

### 2.1 已有事实

- PAPI 真实写端点是 `POST /papi/v1/margin/order` 和
  `POST /papi/v1/um/order`；两者均为签名 TRADE 请求。
- Margin MARKET 支持 `quantity` 或 `quoteOrderQty` 二选一；UM MARKET 仅支持
  `quantity`。因此 `quantity` 路径本身是 API 能力，是否采用是产品选择。
- PAPI 没有可验证统一账户双腿语义的 testnet。CI 只能使用 fake/record transport；
  第一笔真实响应样本必须来自以后单独获批的真实事件，不能伪造。
- Spot 与 UM 的 filters、数量步进、min/max quantity、min notional 和显示精度彼此
  独立；precision 字段不能替代 filter。
- timeout、断连和部分 503 的执行状态可能未知。相同 client order id 不得盲目重发，
  必须先查询订单、成交和持仓。
- 429 必须停止加速请求；418 是更强的持久化停机/重新 arm 信号。

### 2.2 当前阶段的冻结产品选择

- 本阶段目标为 regular Portfolio Margin、immediate mode。
- 前端输入是每次尝试的固定基础币数量和尝试次数。
- 两个方向均先把输入向下取整到 spot MARKET 与 UM MARKET 都合法的 Decimal
  共同网格，得到 `q_common`。
- Forward：margin BUY MARKET `quantity=q_common`,
  `sideEffectType=NO_SIDE_EFFECT`，并发 UM SELL MARKET
  `quantity=q_common`。
- Reverse：margin SELL MARKET `quantity=q_common`,
  `sideEffectType=NO_SIDE_EFFECT`，并发 UM BUY MARKET
  `quantity=q_common`。
- 两腿都确认 `FILLED` 后不以 executed quantity 相等作为成功门槛；仍必须原样记录
  两腿实际数量、实际 quote amount、均价、手续费和 signed residual。
- 单腿、partial、timeout 或 unknown 必须暂停并对账；不得自动补单、关闭、借币或
  还币。

API recon 中“forward 必须 `quoteOrderQty` 且串行”的建议来自随后已被用户覆盖的
产品输入选择。应保留该报告作为接口能力与历史决策证据，但不能把它继续当成本阶段
执行合同。实现仍需用 request-shape 单元测试和 exact-path fake transport 证明
PAPI margin BUY 使用 base `quantity` 的参数形状；不能用真实 POST 来做本阶段测试。

### 2.3 必须由 synthesis / 用户显式裁决的合同冲突

1. **数字风险上限冲突。** 当前冻结输入明确“不设产品级 amount/count/margin 数字
   cap”；现行 `docs/product/PRD.md` 则要求可配置的 per-order、per-symbol 和 total
   strategy notional 上限。方向稿不能静默选择其一。建议本阶段按最新用户选择实现：
   不增加产品风险 cap，只执行交易所 filters、可用余额、账户状态、限频和多重启动
   gate；同时把这一选择作为 PRD amendment 明示给用户批准，批准后再更新 canonical
   PRD。
2. **真实开仓前的手动平仓门槛。** PRD 明确写有“Manual close is required before
   real manual-open trading ships”。本阶段可以落一个 dormant live adapter，但在
   手动平仓设计落地或用户显式修订该 PRD gate 之前，不能授权第一笔真实 open。
   `APP_HEDGE_EXECUTOR=live` 的代码存在不构成对此门槛的覆盖。
3. **持仓模式冲突。** PRD 的 operating assumption 是 one-way only；round-1
   domain 同时预留了 hedge mode。除非用户在 synthesis 中明确扩大范围，本阶段应
   fail closed：`dualSidePosition` 必须为 `false`，UM 请求固定
   `positionSide=BOTH`，流程不得切换持仓模式。
4. **输入合同变化。** PRD 仍描述 total notional + rounds、2% uplift 和自动重算
   rounds；当前冻结合同是 fixed base quantity + attempt count，并要求向下取整。
   本阶段不应擅自增加数量或重算次数：向下取整后不满足 filter 就拒绝。该变化也应
   随用户批准的 synthesis 进入后续 canonical PRD 更新。

## 三、有界范围与架构边界

### 3.1 本阶段交付

- 一个独立的 live hedge transport，exact allowlist 只含本阶段批准的 PAPI GET/POST
  method-path；host 不接受调用方覆盖。
- 一个真实只读 preflight provider，公共 filters/价格与私有 PM 状态分层采集。
- Decimal filter normalizer 和共同网格计算，修复 F-003。
- 独立 durable `hedge_open_attempt` 状态和每腿发送/响应/对账记录，修复 F-005。
- 持久化 order-rate-limit、429/418 cooldown/rearm 和响应头证据，修复 F-004。
- live 模式下所有可能触发交易的 API 都执行同一 gate；取消同步 `fill-all` 循环，
  修复 F-006。
- 两腿并发 dispatch、无 POST 自动重试、client-id 对账、restart recovery。
- API/UI 展示 effective gate、preflight、attempt、两腿结果与 residual。
- fake transport、故障注入、restart、gate matrix 和前后端合同测试。

### 3.2 明确不交付

- 不访问或落档真实凭据，不进行 Binance 私有请求，不发送任何真实订单。
- 不交付 smooth/WebSocket、自动补腿、自动 close、自动 borrow/repay。
- 不宣称 PM-Pro 兼容。
- 不执行第一笔 live 验证，不伪造真实 PAPI order response 样本。
- 不把 dry-run 模拟 fill 计入真实持仓或真实会计。
- 不在本阶段更名历史 `/api/public-market/snapshot` 或升级其 wire version。

## 四、只读 preflight 合同

Preflight 不是一个布尔值，而是一份带来源、时间、有效期和失败原因的 immutable
snapshot。创建任务时生成 preview；**每个 live attempt 发送前必须重新生成一次
dispatch snapshot**。preview 不能替代 dispatch snapshot。

### 4.1 公共输入

1. Spot `GET /api/v3/exchangeInfo?symbol=<symbol>`：
   - symbol 存在且 `status=TRADING`；
   - base/quote 与任务一致，quote 必须为 USDT；
   - `LOT_SIZE`、`MARKET_LOT_SIZE`、`MIN_NOTIONAL`/`NOTIONAL`；
   - 原始 decimal strings、抓取时间和可复核 filter fingerprint。
2. UM `GET /fapi/v1/exchangeInfo` 的对应 symbol：
   - 永续合约存在且可交易；
   - `LOT_SIZE`、`MARKET_LOT_SIZE`、`MIN_NOTIONAL`；
   - 原始 decimal strings、抓取时间和 filter fingerprint。
3. 本次方向对应的 spot best bid/ask，以及 UM mark price / 可复核市价参考：
   - forward 用 spot ask 估算 margin BUY 的 quote cost；
   - reverse 用 spot bid 估算 spot notional；
   - UM min-notional 估算使用 UM mark price；
   - 这些值只用于 preflight 估算和 UI，不能被描述为成交保证。

公共 filter snapshot 最多缓存 60 秒；进入 live dispatch 时若过期、symbol 状态变化或
fingerprint 变化，必须重新计算 `q_common`。若重新计算结果与任务展示值不同，停止该
attempt，向 UI 返回 `filters_changed_reconfirm_required`，不能静默改量。

合同 amendment 的事实证据需要真正的 raw public JSON。现有 recon 报告给出了数值和
来源，但实现/评审前仍应把对应 spot/UM exchangeInfo 原始响应落到
`reports/api-samples/2026-07-hedge-open-real-api-v1/`；叙述性报告不能代替 raw
sample。

### 4.2 私有 signed GET 输入

每次 live attempt 使用非缓存或强制刷新的同一批只读数据：

- `GET /papi/v1/account`：请求成功、`accountStatus=NORMAL`；保存
  `uniMMR`、`totalAvailableBalance`、initial/maintenance margin 供展示和审计。
  因用户未批准 `uniMMR` 数字阈值，本阶段不得暗自发明阈值；字段缺失或账户非正常
  则 fail closed。
- `GET /papi/v1/balance`：
  - forward 检查 USDT `crossMarginFree`；
  - reverse 检查 base asset `crossMarginFree`；
  - `maxBorrowable` 只能显示/验证，不能当作可卖余额，不能触发自动借币。
- `GET /papi/v1/um/positionSide/dual`：本阶段要求 `false`，请求使用
  `positionSide=BOTH`，不得在流程中改变模式。
- `GET /papi/v1/um/positionRisk`：记录发送前的目标 symbol position baseline，
  供 timeout/unknown 后判断净变化。
- `GET /papi/v1/rateLimit/order`：持久化账户订单限额配置。
- `GET /papi/v1/time` 或等价 server-time 证据：生成满足 Binance timestamp /
  recvWindow 谓词的签名时间；若无法证明满足，不发送。

私有 snapshot 必须记录每个 endpoint 的完成时间、HTTP 分类和 sanitized source
status。整份 snapshot 在最后一个 read 完成后 5 秒内有效；超过 5 秒、任一 read
失败或 Start/gate version 改变，都重新预检。5 秒是技术 staleness guard，不是产品
风险额度，应作为命名常量和可测试设计值，而不是隐藏 magic number。

### 4.3 数量、余额和 plan 检查

- `requested_base_qty` 与 `target_n` 都从 JSON string/integer 边界解析；数量全程
  `Decimal`，禁止 binary float。
- forward preview 同时展示：
  - `estimated_attempt_quote = q_common * spot_ask`；
  - `estimated_remaining_quote = estimated_attempt_quote * remaining_attempts`；
  - 当前 USDT `crossMarginFree`。
- reverse preview 同时展示：
  - `required_attempt_base = q_common`；
  - `required_remaining_base = q_common * remaining_attempts`；
  - 当前 base `crossMarginFree`。
- 创建时如果整个 remaining plan 已明显超过当时可用余额，拒绝并展示 required /
  available；每次发送前仍只以新鲜 snapshot 重新校验剩余 plan 和本 attempt。
- 市价滑点可能让 forward 实际 quote cost 超过 top-of-book 估算。由于用户没有批准
  slippage 或 reserve 数字阈值，本阶段不能声称余额预检能保证成交；交易所仍可能
  reject。该竞态必须列为 residual risk，而不是通过未获批 buffer 静默修改订单。

## 五、Decimal 与 filter 行为（F-003）

### 5.1 逐 constraint 的有效值

不能把 `MARKET_LOT_SIZE` 当作全有或全无。对每条腿的 `stepSize`、`minQty` 和
`maxQty` 分别处理：

1. `MARKET_LOT_SIZE.<field>` 存在且十进制值 `> 0`，使用它；
2. 否则使用 `LOT_SIZE.<field>` 中存在且 `> 0` 的值；
3. 两者都为 0/缺失时，该 constraint 是 disabled；
4. step 缺失或 disabled 到无法构造合法 quantity 时，live fail closed。

这解决当前实现按一个 `step_size` 选择整组 bounds 的缺口。

### 5.2 共同网格

- 把两腿有效 step 转成整数 fixed-point units，计算精确 Decimal LCM；
- `q_common = floor(requested_base_qty / common_step) * common_step`；
- 不允许浮点、四舍五入或分别把两腿 round 到不同数量；
- `q_common` 必须分别满足两腿有效 min/max；
- spot 和 UM 分别以各自价格参考重做 min-notional 检查；
- 任何结果为 0、低于 min、超过 max、notional 不满足或 serialization 不可表达，
  均在 POST 前拒绝。

向下取整的差量必须回传：

```text
requested_base_qty
common_step
q_common
quantity_remainder = requested_base_qty - q_common
spot_filter_fingerprint
um_filter_fingerprint
```

### 5.3 每腿序列化

同一个数值 `q_common` 分别按 spot/UM 有效 step 的指数输出普通十进制字符串，禁止
科学计数法、尾随无意义二进制误差和以 `quantityPrecision` 代替 step。价格、quote
估算、实际成交 quantity、cumQuote、avgPrice、commission 也全部保留交易所原始
decimal string，并在计算副本中使用 Decimal。

## 六、durable attempt 与状态机（F-005）

现有 round-1 流程是 executor 返回后才写 fill/log，这不满足“发送前 durable”。
本阶段需要新增第一等 `hedge_open_attempt` 记录，而不是继续把 attempt 隐含在 fill
行中。

### 6.1 attempt 最小持久字段

- `attempt_id`、`task_id`、`attempt_no`、direction、symbol；
- requested qty、`q_common`、common step、两份 filter fingerprint；
- immutable preflight snapshot/ref 和 gate version；
- 两个发送前已生成的 deterministic unique client order id；
- 每腿 request params 的 sanitized exact shape；
- 每腿状态、order id、executed qty、cum quote、avg price、commission；
- `created_at`、`dispatch_started_at`、每腿 response time、reconcile times；
- aggregate state、pause reason、residual、`requires_reconciliation`；
- append-only event/log refs。

任务行增加 `unresolved_attempt_id`。同一任务存在未决 attempt 时不能创建下一个
attempt；整个进程同一时刻只 dispatch 一个双腿 attempt，避免多任务并发透支余额和
扩大限频竞态。

### 6.2 发送前事务

1. 取得单一 execution-owner sidecar lock；非 owner 只可服务读/管理 API。
2. 在一个 SQLite transaction 内重新确认 task runnable、无 unresolved attempt、
   global Start/gate version 未变。
3. 插入 aggregate=`PREPARED` 的 attempt、两腿 `NOT_SENT`、client ids、preflight
   和 sanitized request shape；设置 task `unresolved_attempt_id`；commit。
4. 发送前再读 effective gate。若 gate 关闭，把 attempt 终结为
   `BLOCKED_BEFORE_SEND`，两腿仍是 `NOT_SENT`。
5. 在第二个短事务中把两腿都标为 `DISPATCH_STARTED` 并 commit。此后即使进程崩溃，
   两腿都按 unknown 处理，必须查询 client id，绝不直接重发。
6. transaction/DB lock 期间不得做 HTTP。

如果第 3 或第 5 步无法 commit，发送零个 POST。

### 6.3 aggregate 状态

建议使用可审计而非过度简化的状态：

```text
PREPARED
BLOCKED_BEFORE_SEND
DISPATCHING
RECONCILING
BOTH_FILLED
BOTH_KNOWN_NOT_FILLED
EXPOSURE_ALERT
UNKNOWN_MANUAL_REVIEW
```

每腿状态至少包含：

```text
NOT_SENT | DISPATCH_STARTED | NEW | PARTIALLY_FILLED | FILLED
| REJECTED | EXPIRED | UNKNOWN
```

`PARTIALLY_FILLED` 不归类为普通 failure；它代表已有不可忽略的市场 exposure。
只要任一腿 partial、单腿 filled 或任一腿 unknown，任务和全局后续 dispatch 都暂停。

### 6.4 restart recovery

服务启动后先持有 owner lock，再扫描所有非 terminal attempt；在对账完成前 effective
Start 必须为 false。对于 `DISPATCH_STARTED` 及之后的 attempt，分别按 client id
查询两腿，不依赖旧进程是否来得及写响应。恢复流程只做 GET，不发送修复单，也不创建
新 attempt。任何 unresolved 结果要求人工重新 arm。

## 七、并发 POST 与对账

### 7.1 并发发送

使用固定两 worker 的并发边界（可用标准库 `ThreadPoolExecutor(max_workers=2)`），
在 durable `DISPATCH_STARTED` commit 后同时提交 margin 与 UM callable。设计目标是
减小腿间窗口，不宣称网络级原子性。每腿独立保存 local send start/end、HTTP status、
Binance code 和 sanitized response classification。

每个 HTTP callable 恰好进行一次 POST：

- 无自动 transport retry；
- 不因 timeout/5xx 用相同或新 client id 重发；
- 不把一腿失败作为取消/阻止另一腿的信号，因为两 callable 已并发启动；
- `APP_HEDGE_EXECUTOR` 和 gate 检查只在 service 层不足够，live executor 自身也必须
  在 POST 前接受一个不可伪造的已验证 gate context。

### 7.2 对账

以下任一情况进入 `RECONCILING`：

- POST timeout、connection error、ambiguous 503；
- 响应不是确定 `FILLED`；
- 任一腿 `NEW`、`PARTIALLY_FILLED`、缺少 order id 或响应 schema 异常；
- 进程重启发现非 terminal attempt。

只读对账顺序：

1. `GET /papi/v1/margin/order` 与 `GET /papi/v1/um/order`，按各自
   `origClientOrderId`；
2. 需要补全成交/手续费时查 `margin/myTrades` 与 `um/userTrades`；
3. 读取 `um/positionRisk`，和 preflight baseline 对比；
4. 每次查询结果都 append event 并更新每腿状态。

read-only reconciliation 可以按有界退避继续；到达有界窗口仍 unknown 时进入
`UNKNOWN_MANUAL_REVIEW`。本阶段不调用 cancel，不把“查不到”单独当成一定未成交，也
不自动 POST repair。

### 7.3 结果分类和 residual

- 只有两腿最终都确认 `FILLED` 才计入 success。
- 两腿都确认无成交的 known rejection 可计入 failed；保留现有累计 `>3` failed
  后暂停的规则。
- 一腿 filled/partial、另一腿非 filled，进入 `EXPOSURE_ALERT`。
- 任一腿 unknown，进入 `UNKNOWN_MANUAL_REVIEW`。
- 两腿 filled 时不做 equality gate，不因为数量不同暂停，但必须计算并展示：
  - forward `signed_residual_base = spot_executed_qty - um_executed_qty`；
  - reverse `signed_residual_base = um_executed_qty - spot_executed_qty`；
  - 正值表示基础币等价净多，负值表示净空；
  - 同时保留两腿原始 executedQty/cumQuote/fees，不能只留下 residual。

这个 residual 是运营观察值，不是完整会计或自动行动信号。

## 八、限频与重 arm（F-004）

- 持久化 `GET /papi/v1/rateLimit/order` 的 limit、采集时间和原始分类。
- 每次响应保存 sanitized `X-MBX-ORDER-COUNT-*`、`X-MBX-USED-WEIGHT-*` 与
  `Retry-After`；取所有窗口中最紧的预算。
- 本地 scheduler 只允许一个双腿 attempt in flight，并根据已知 order count 预留两
  个 order event；无法证明预算可用时不发送。
- 429：停止新 dispatch，持久化 cooldown，保留未发送任务；不加速重试。
- 418：立即 effective Stop，持久化 `requires_rearm=true`；进程重启不能自动恢复
  Start。
- `-1008` 或明确 service unavailable 虽可能是 known failure，本阶段仍不自动再次
  POST；它可以成为一次 known failed attempt，由正常任务规则决定是否以后创建新
  attempt。
- reconciliation GET 看到 429/418 也必须持久化 cooldown/rearm，但不能把未决订单
  推断为失败。

## 九、真实 POST gate 证明

### 9.1 必须全部为真

1. 进程启动配置严格解析为 `APP_HEDGE_EXECUTOR=live`；非法值 fail closed。
2. 使用独立 hedge TRADE credentials；缺失时进程可读运行但 `can_execute=false`。
   配置、repr、日志和 API 永不回显 credential/signature。
3. 当前进程持有 hedge DB 的唯一 execution-owner lock。
4. durable global Start 为 ON，且没有 `requires_rearm`。
5. 任务为 running、已做 task-level live acknowledgement、无未决 attempt。
6. 第一笔 live 的 one-shot human authorization 已由以后单独的人类动作写入；本阶段
   交付时默认 false。
7. manual-close PRD gate 已满足，或存在用户明确批准的 PRD amendment。
8. 最新 preflight 通过且未过 5 秒；filters/gate version 未变。
9. position mode、account status、balance、rate limit 全部通过。
10. request method/path 在 exact allowlist 中，且 request body 正是签名字节。

任一条件不满足都在 durable attempt 的 `BLOCKED_BEFORE_SEND` 或创建 attempt 前返回
明确 block reason，并保证 POST count 为 0。

### 9.2 配置与人工控制

建议把 `APP_HEDGE_EXECUTOR` 和独立 hedge credentials 正式纳入
`backend/config.py`，不要继续由 `server.py` 临时读取环境。第一笔 live arm 不应做成
普通页面默认按钮；使用一个明确的本地 operator 命令或一次性确认流程，并把 task id、
symbol、direction、`q_common`、target_n、filter fingerprints 和批准时间落 durable
audit。授权只适用于被确认的任务，不能泛化成永久账户豁免。

### 9.3 可机械验证的零 POST matrix

fake client 记录调用数，逐一证明以下任一条件为 false 时 POST count 恒为 0：

- mode；
- credentials-present；
- execution-owner；
- global Start；
- requires-rearm；
- first-live authorization；
- task acknowledgement；
- fresh preflight；
- account/position mode；
- balance；
- rate-limit budget；
- allowlisted method/path；
- durable PREPARED/DISPATCH_STARTED commit。

## 十、API 与 UI 合同

### 10.1 创建任务

保留兼容 route：

```http
POST /api/hedge-open-tasks
{
  "coin": "BTCUSDT",
  "direction": "forward",
  "mode": "immediate",
  "single_amount": "0.001",
  "target_n": 3
}
```

但在 schema、UI 和响应中明确：

- `single_amount` 是 legacy field name，语义固定为
  `requested_base_quantity_per_attempt`；
- `input_unit="base_asset"`；
- 响应展示 requested quantity、common step、`q_common`、remainder；
- 数量必须是 decimal string；`target_n` 必须是正整数。存储表示的整数范围校验是
  技术完整性约束，不应被宣传为产品风险 cap。

### 10.2 执行控制

增加与 borrow control 同等级的显式 API：

```text
GET  /api/hedge-open-execution
POST /api/hedge-open-execution/start
POST /api/hedge-open-execution/stop
POST /api/hedge-open-tasks/<id>/acknowledge-live
GET  /api/hedge-open-tasks/<id>/attempts
```

execution 投影至少包含：

```text
executor_mode
start_requested
can_execute
block_reason
execution_owner
credentials_present
requires_rearm
first_live_authorized
cooldown_until
active_attempt_id
preflight_status
```

`credentials_present` 只返回 boolean。

### 10.3 F-006：移除 live `fill-all`

当前 `fill-all` 在一个 HTTP 请求内循环最多 10,000 次，而且 round-1 manual action
绕过 Start gate。真实执行不能保留此语义：

- live 模式下 `/fill-all` 返回 409 `live_batch_dispatch_forbidden`；
- UI 在 live 模式隐藏/禁用“立即成交所有”；
- `/fill-once` 若保留，只能 enqueue/dispatch 一个 attempt，且经过与 scheduler
  完全相同的所有 gate；
- task `start` 只改变 durable task intent，不得绕过 global Start；
- scheduler 每 tick 最多一个 attempt，不补跑错过的 tick，不同步旋转到 target_n。

dry-run 测试注入如需批量推进，应使用 test-only helper，不能共享 live HTTP 路径。

### 10.4 运营 UI

- 输入文案改为“单次基础币数量”，展示 base asset 单位、requested → q_common 变化。
- modal 展示 direction、两腿 side、`NO_SIDE_EFFECT`、positionSide=BOTH、attempt
  count、预估 remaining balance requirement。
- execution badge 不只显示 `live/disabled`，必须显示 `can_execute` 和首要 block
  reason。
- attempt 时间线逐腿展示 NOT_SENT/DISPATCH_STARTED/FILLED/PARTIAL/UNKNOWN、
  client id、order id、actual qty、cum quote、fee、reconcile 状态。
- `EXPOSURE_ALERT` 和 `UNKNOWN_MANUAL_REVIEW` 明显置顶；没有“自动修复”按钮。
- 两腿 filled 时展示 signed residual，但不渲染成自动阈值告警。
- manual-close gate 未满足时，即使 mode=live，也明确显示
  `manual_close_gate_unresolved`。

## 十一、测试与证据

### 11.1 纯逻辑

- `MARKET_LOT_SIZE` 的 step/min/max 分别为 0、缺失、非零的组合回退；
- 不同 decimal exponent、非整倍 step、极小数量、零、min/max 边界；
- `q_common` 只向下取整，两腿序列化无科学计数法、无 float；
- spot/UM 独立 min-notional 和 price source；
- forward/reverse request shape 都是同一 `quantity=q_common`；
- both-filled unequal quantity 为 success + residual；partial/unknown 不为普通 success。

### 11.2 store / crash

- PREPARED commit 失败 => 0 POST；
- DISPATCH_STARTED commit 失败 => 0 POST；
- commit 后、第一腿调用前崩溃 => restart 按两腿 unknown 查询；
- 一腿返回后崩溃 => restart 查询两腿，不重发；
- client id 唯一、重复结果幂等、一个 task 只有一个 unresolved attempt；
- owner/non-owner 两进程模型；
- 429/418/cooldown/rearm 跨 restart 保持。

### 11.3 transport / executor

- exact host + method/path allowlist，未知 GET/POST 在签名前被拒绝；
- 一个 serializer 产生签名和实际发送的完全相同 bytes；
- 两个 POST callable 确实重叠执行，但各自最多调用一次；
- timeout、connection loss、ambiguous 503、malformed JSON、partial、单腿 fill；
- order/trades/positionRisk 对账按 client id，禁止 POST retry；
- sanitized logs 无 API key、secret、signature、完整私有 payload。

### 11.4 gate / API / UI

- 完整零 POST matrix；
- live `/fill-all` 409，`fill-once` 和 scheduler gate 等价；
- Stop 在新 attempt 之前立即阻断，已有 unknown attempt 只允许 GET reconcile；
- task/create、execution、attempt wire contract；
- UI 单位、q_common、block reason、residual、exposure/unknown 展示；
- 既有 backend 全量测试、frontend self-check、stage validator 全部通过。

所有自动测试都注入 fake URL opener/client；禁止真实 Binance 请求。实现阶段如修改
public filter contract，必须把 raw public samples 纳入 stage evidence。真实 private
order response 继续标记为“等待单独人类授权后的事实证据”，不能用 fixture 宣称已验证。

## 十二、建议文件与任务拆分

### Backend Task A — filter/preflight（Claude-GLM）

允许范围：

- `backend/hedge_open_tasks/domain.py`
- 新增 `backend/hedge_open_tasks/preflight.py`
- 必要的公共 adapter 只读接缝
- `backend/tests/test_hedge_domain.py`
- 新增 `backend/tests/test_hedge_preflight.py`
- 对应 raw public samples / fixtures

职责：F-003、Decimal、每腿价格/notional、regular PM one-way preflight、sanitized
snapshot。不得写 POST transport。

### Backend Task B — durable state/control（Claude-GLM）

允许范围：

- `backend/hedge_open_tasks/store.py`
- `backend/hedge_open_tasks/service.py`
- `backend/hedge_open_tasks/scheduler.py`
- 新增 `backend/hedge_open_tasks/ownership.py`
- `backend/app/server.py` 的 hedge routes
- hedge store/service/API tests

职责：attempt 表、unresolved pointer、owner、gate、F-004/F-005/F-006、restart
reconciliation orchestration。不得实现签名。

### Backend Task C — exact transport/live executor（Claude-GLM）

允许范围：

- `backend/config.py`
- 新增 `backend/services/portfolio_margin_hedge_client.py`
- 新增 `backend/services/live_hedge_executor.py`
- `backend/services/binance_signing.py` 仅在现有单一签名合同确需扩展时修改
- `backend/hedge_open_tasks/executor.py`
- 对应 transport/executor/config tests

职责：exact allowlist、单 serializer、两个 one-shot POST、只读 query、分类和 gate
context；不得添加自动 repair/retry。

Backend A/B/C 可以在合同冻结后按文件边界拆分，但 B/C 的 attempt/executor interface
必须先写入设计与测试 fixture；合并前由 bookkeeper 做 diff reconciliation。

### Frontend Task D — operator UI（Kimi）

允许范围：

- `frontend/index.html`
- `frontend/self-check.js`
- 必要 fixture

职责：base quantity 语义、q_common/remainder、execution Start/Stop、block reason、
attempt 双腿时间线、live fill-all 禁用、residual/exposure/unknown 展示。浏览器不得
签名、调度或直连 Binance。

### Bookkeeper / evidence

- 先合成方向稿并取得用户对第 2.3 节冲突的明确批准；
- 再产出正式 `10-design.md`、ADR、开发 breakdown 和精确 wire schema；
- 按 Harness 分派给人类操作的模型终端；
- 实现前补 raw public filter 样本；
- 本阶段不采集凭据、不运行真实 POST、不启用 live/Start、不执行第一笔任务。

## 十三、残余风险

- 双腿并发不是原子事务，仍存在不可消除的单腿窗口。
- 固定相同 request quantity 不保证相同 executed quantity；用户选择了记录 residual
  而不以数值阈值暂停。
- 无 slippage/margin/notional 产品 cap 时，preflight 只能提供时点估算；快速行情和
  账户变化仍可能导致 rejection 或更高成本。
- 没有 PAPI testnet；真实账户权限、区域限制、响应细节和手续费只能在以后获批的极小
  真实事件中最终验证。
- 当前没有手动 close 实现；按 canonical PRD，这仍阻塞第一笔真实 open，除非用户
  明确修订该 gate。
- 没有 PM-Pro 事实样本；PM-Pro 必须 fail closed。
- 仅靠代码无法证明某次“first live authorization”确实来自人类，最终保证仍依赖
  Harness 保存的用户授权原文和 operator 审核。

## 十四、进入实现前的最小人类决策

1. 明确批准“本阶段无产品级数字 caps”是对现行 PRD risk-control 条款的修订，或改回
   可配置 caps。
2. 明确第一笔 live open 是否继续受“manual close 先落地”约束；若不受，需显式修订
   PRD，而不是由实现模型推断。
3. 确认 one-way-only；若账户实际是 hedge mode，应另做范围变更，不能在本阶段静默
   兼容。
4. 批准 dormant real-POST adapter 可以合入，但 activation、Start 和第一笔 task
   仍是后续三个独立的人类动作。

当前 Session ID: 019f8e94-a17e-7210-9d4a-462a45471554
Session ID 来源: runtime_env
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/direction-drafts/codex.md
本地北京时间: 2026-07-23 18:50:29 CST
下一步模型: bookkeeper
下一步任务: archive this raw direction draft; do not implement code
