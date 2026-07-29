# Stage Design — Hedge Order Truth And Error Fidelity v1

Designer: Claude Fable 5（design-only；未写任何产品代码，未访问凭据，未发任何
私有请求，未触碰 `data/hedge-open-tasks.sqlite3`）。事实来源均带路径；未验证的
外部事实显式标注「未验证」。

## 0. 目标与非目标

**目标**：让系统对一笔真实订单的记录与交易所实际发生的事一致——成交金额来自仍然
携带它的数据源（T1）、margin 正数错误码得到结构性分类（T2）、交易所原话与订单
详情全量落库（T3）、实盘敞口时间戳真实（T5）。并为 T4（51169 根因判别实验）给出
可照做的规程与预先钉死的解读，不设计 preflight 修法。

**非目标**（引 `00-task.md` §Non-Goals，不重述）：平单、smooth 模式、重议
ADVISORY、UI 工作、T4 结果前的 preflight 重设计、任何实盘授权、任何对
`data/hedge-open-tasks.sqlite3` 的写入。

**总原则**：宁可显式失败 / 显式未知，也不落一个与真实值无法区分的替代值。本设计
中所有「取不到」一律表示为 NULL 或非终态重试，绝不表示为 `"0"`。

## 1. T1 — 成交金额的权威来源与读取时机

现状根因（已在 intake 核实，此处只列锚点）：`live_hedge_executor.py:242-248`
的 or 链 + `_decimal_str(None)→"0"`（`:136-143`）+ `store.py:660-668` 把 `"0"`
当缺失后回退失败落 `Decimal(0)`。

### 1(a) 权威来源：订单详情 GET（沿用已冻结的按 client ID 查询端点）

**决策**：UM/CM 腿的权威成交数据来自
`GET /papi/v1/um/order?symbol=..&origClientOrderId=..`（margin 腿保持 POST
RESULT 响应为权威，见 1(c)）。该 GET 已在
`hedge_open_live_client.py` ALLOWLIST 中（weight 2），且
`classify_query_response`（`live_hedge_executor.py:288-357`）已实现对
`cummulativeQuoteQty`/`cumQuote`/`avgPrice` 的解析——T1 改变的是**何时**用它和
**怎么表示取不到**，不新增端点。

- 延迟：一次签名 GET，约一个 RTT（<0.5s），在 1s 节奏内。
- 限频：weight 2/次，每 attempt 至多增加 1–2 次 GET，远低于账户限额。
- 失败语义：沿用既有查询语义——inconclusive（超时/5xx/歧义 4xx）→ 腿保持
  非终态继续查（ADR-2 的 query-never-resend 不变）。

**被否决的备选**：
- **user-data WebSocket**：本仓库没有任何 ws 基础设施；ADR-5 把 ws 保留给
  smooth 模式；listenKey 生命周期管理是一整块新面；1s 节奏不需要推送级延迟。
  否决（本 stage）。
- **`GET /papi/v1/um/userTrades`**：能给逐笔成交与手续费，但不在 ALLOWLIST，
  扩 allowlist 属于契约扩面、需要新的 recon+样本；订单详情 GET 已足以取回
  cumQuote/avgPrice。否决（本 stage），但作为 1(a)-fallback 预先声明：**若下述
  W0 样本证明订单详情 GET 也已不带这些字段**，则唯一出路是把 userTrades 列为
  契约修订（见 11-adr.md ADR-T1 的契约修订标注），届时必须先补真实样本。

**⚠️ 未验证的外部事实（本设计最大的假设）**：币安 2026-07-14 的移除公告只列了
POST 与 DELETE 端点（`18-live-acceptance-findings.md` §F-1 引文），**没有列
GET**。据此推断订单详情 GET 仍返回 `cumQuote`/`avgPrice`——这是推断，不是实测。
缓解措施是把「取一份真实订单详情样本」列为实现前置证据步骤 **W0**（见
12-development-breakdown.md）：由 human operator 对已存在的真实订单
`orderId 888412130`（NOMUSDT UM）执行一次只读签名 GET，原始响应（脱敏）落
`reports/api-samples/2026-07-hedge-order-truth-v1/um-order-detail-post-removal-sample.md`。
这一步只读、免费、不产生订单；它同时就是 AGENTS.md 要求的契约修订原始样本。
即使 W0 被推迟，1(d) 的 NULL 表示法保证错误假设的代价是「记为未知」而不是
「记一个假数」。

### 1(b) 读取时机：UM 腿接受后立即确认查询，失败则留在既有 drain 链路

**决策**：
1. `_send_one_leg` 中，UM 腿 POST 返回 acceptance（orderId）后，**立即**用既有
   querier 做一次 figures-confirm GET，把权威成交数据合并进 `LegDispatch`。
   常见情形下结算仍发生在同一次 dispatch 内，只多一个 RTT——不拖慢结算。
2. confirm GET inconclusive 时，UM 腿即使 `status=FILLED` 也**不再**直接
   `TERMINAL_RECORDED`：`service._leg_terminal`（`service.py:1646-1655`）改为
   按产品判定——UM 腿只有在权威金额已知时才算 terminal fill；否则留在
   `ACCEPTED_OR_QUERYING`，由既有 worker drain（`_reconcile_own_legs` →
   `resolve_leg_from_query` → `finalize_attempt`）在下一轮（~1s）补齐。
   `live_hedge_executor.leg_is_terminal_fill` 同步收紧。
3. margin 腿维持现状：POST RESULT 携带 `cummulativeQuoteQty`，接受即可终态。

**与既有对账路径是否冲突**：不冲突——复用的正是同一套机制（同一 querier、同一
`resolve_leg_from_query`、幂等的 `finalize_attempt`），只是把「FILLED 就终态」
收紧为「FILLED 且金额已知才终态」。代价被明确接受：当 confirm GET 持续失败时，
pair 结算推迟（与今天 UNKNOWN 腿的行为一致，任务级 in-flight guard 阻塞下一
pair，worker 持续查询）——这是真实的未知，本来就不该结算。ADR-3 的
acceptance 口径不变：计数器仍键在 POST 返回的 orderId 上，成交数据仍是
observational accounting。

### 1(c) margin/UM 不对称：显式的按产品分流规则

**决策**：在 `live_hedge_executor.py` 增加模块级显式映射（示意，命名由实现定）：

```text
PRODUCT_MARGIN = "margin"   # leg "spot" → POST /papi/v1/margin/order
PRODUCT_UM     = "um"       # leg "perp" → POST /papi/v1/um/order
FILL_FIGURES_SOURCE = {
    PRODUCT_MARGIN: "post_response",      # RESULT body 携带 cummulativeQuoteQty（币安 2026-07-14 变更未涉及 margin）
    PRODUCT_UM:     "order_detail_query", # POST body 仅证明 acceptance；金额来自订单详情 GET
}
```

解析函数按产品取字段：margin 读 `cummulativeQuoteQty`；UM 读订单详情 GET 的
`cumQuote`（回退 `cummulativeQuoteQty` 命名兼容）与 `avgPrice`。现在的
`cummulativeQuoteQty or cumQuote` or 链删除。这样当币安再次变更某一产品的响应
时，需要改的是一条**有名字的规则**，而不是一处顺手的取值。

### 1(d) 取不到怎么落库：NULL = 未知，"0" = 真零，且未知不终态

**决策**（三层）：
1. **传输层**：`LegDispatch.cumulative_quote` 类型改为 `Optional[str]`，
   `None` 表示「响应没有携带」。金额类字段不再使用 `_decimal_str` 的
   `default="0"`（`executed_qty` 保留 `"0"` 默认——一条已接受未成交的腿执行量
   确实为 0，那是真值；但 FILLED 腿缺 `executedQty` 属于畸形响应，按既有
   UNKNOWN 语义处理）。
2. **存储层**：`hedge_open_leg.cumulative_quote_amt` 由 `NOT NULL DEFAULT '0'`
   改为可空（需表重建迁移，见 §7）。`store._leg_final_fields` 重写为显式规则：
   `cumulative_quote is None → NULL`；`"0" → "0"`（真零）；
   `filled_qty>0 且 avg_price 非空且 quote 缺失 → filled_qty*avg_price`
   （由真实数据推算，保留）；**永不**把缺失强转为 0。现在把 `"0"` 当缺失的
   判断（`store.py:660`）正是缺陷本体，删除。
3. **状态层**：金额未知的 FILLED UM 腿不终态（1(b)），即「重试」也在——所以
   最终表示法是 **NULL + 重试** 的组合：能查到就查到，查不到期间数据库里是
   诚实的 NULL，绝不出现与真零同形的假 0。

**被否决**：哨兵字符串（如 `"unknown"`）——魔法值，Decimal 消费方全要特判；
独立布尔标志列——与金额列构成双源真相，漂移后更难审计。

**下游影响**：`aggregate_positions`（`store.py:1652-1668`）现把 quote 直接求和;
NULL 腿改为**跳过 notional 求和并在该 bucket 上置** `avg_price_incomplete: true`
（additive 字段）——均价宁可标注不完整，也不因为把未知当 0 而被拉低。wire 契约
上 `cumulative_quote_amt` 变为 `string|null`（additive 放宽）；UI 对 null 的
展示是既有「原话展示 follow-up」的一部分，不在本 stage。

### 1(e) 历史数据 → 见 §6「历史数据处置」（与 T5(d) 合并）。

## 2. T2 — 错误分类的结构性修法

现状根因：`domain.py:306-353` 三个集合全为负数字面量；margin 正数码永远无法
命中，落入 `classify_leg_response` 的 unlisted-4xx 默认分支
（`live_hedge_executor.py:284`），`error_category` 落 NULL。

### 2(a) 统一方案：共享网关层 + (product, code) 业务层，两层查询

**决策**：新增纯函数 `domain.classify_exchange_code(product, code, msg)`，
分类顺序：

1. **共享网关层**（与产品无关、任何 papi 端点都可能返回的负数码）：
   auth/时间戳/权限歧义集合（现 `AUTH_AMBIGUOUS_EXCHANGE_CODES` 原样保留）、
   限频码（-1003/-1008 由既有 HTTP 层逻辑处理，不动）。margin 端点也会返回
   这类负数码（如 -1021 时间戳），所以这层必须先于产品层查询。
2. **产品业务层**，按 `(product, code)` 键查表：
   - `UM_BUSINESS_CODES`：现有负数集合原样迁入（-2010/-2019/-3041/-1013/
     -11xx filter 族），判定完全不变；
   - `MARGIN_BUSINESS_CODES`：正数码表，**只播种已被实盘证实的一条**：
     `51169 → collateral_cap`（**独立新类别**，依据
     `02-collateral-cap-finding.md`：NOM 已打满币安平台级、按币种、全用户
     共享的 Maximum Collateral Limit，margin BUY 因该币抵押容量为零被拒——
     **不是**本账户资金/保证金不足，加钱无效）。未经样本证实的 margin 码
     不预填——本 stage 的纪律是不把文档猜测写成分类事实。

   **为什么是独立类别而不是 insufficient_funds 的子原因**：store 对
   insufficient-funds 路径的文档承诺是「a CONFIRMED insufficient
   balance/margin/available-quantity fact」，而 51169 已被证实**不是**本
   账户的余额/保证金事实——归入该类会让类别名对着库里的行说假话，操作员
   看到的会是「保证金不足」这个伪结论。本 stage 的纪律是未识别与已识别必须
   可区分；同理，**被误述的条件并不比未分类更好**。若做成子原因，父类别的
   文案、pause 原因、信号派生全都要为它特判——一个覆盖父类全部语义的子原因
   就是一个戴错名字的新类别。故独立类别 `collateral_cap`。
3. 两层都未命中 → 显式返回 `unclassified`（见 2(b)）。

`product` 由腿名派生（`spot→margin`，`perp→um`），与 1(c) 共用同一产品枚举。

**被否决的备选**：
- **按码值符号分流**：符号只提示产品，不给语义；且 margin 端点同时会发负数
  网关码，纯符号分流会把 -1021 错投进 margin 业务表。否决。
- **单张扁平合并表**：两产品若出现同值不同义的码会互相污染；且表里看不出每条
  规则是对哪个产品核实的——正是这次「采集时属实、过期没人复查」教训要求的
  可追溯性。否决。
- **按端点各建全套表（不设共享层）**：网关码要在每张表重复，漂移后两表不一致。
  否决。

### 2(b) 未识别 ≠ 已识别：`unclassified` 成为持久化的显式类别

**决策**：默认分支不再产出 `error_category=NULL`。凡携带业务码但两层都未命中
的拒单，落库 `error_category="unclassified"` + 原码。NULL 从此只表示「响应里
根本没有业务码」。控制流上 `unclassified` 与今天的默认分支一致（已知非致命、
计入 submission-failure 计数器）——行为不变宽也不变严，但**可区分**：下一个
未列出的 margin 码不会再被静默吞掉，库里能看见它没被识别。

### 2(c) 判定变化清单（分类不得更宽松）

唯一发生判定变化的码：

| 码 | 产品 | 今天 | 之后 | 方向 |
| --- | --- | --- | --- | --- |
| `51169` | margin | 未列出 → 非致命计数 | `collateral_cap` → task-local pause（`pause_reason=collateral_cap_full`） | **更严** |

所有负数码判定不变（回归测试证明，见 §8）。`unclassified` 与今天的默认分支
控制流相同。没有任何码从停/暂停变为非致命。

### 2(d) 51169 的任务级结果、时变性与操作员文案（ADVISORY 不动）

**任务级结果：task-local pause（停止重试），依据是上限事实本身，不继承
-2019 的理由。** 两条根据：
1. 上限由全平台持仓占满，任务重试窗口（秒级）内不会清空——重试必然再收
   51169，纯耗限频预算；
2. 更要紧的是不对称性：上限只挡**正向**的现货买入腿（买入保证金账户），
   **perp 腿不受影响**。继续重试会重复 2026-07-27 的机制——每对新 attempt
   的 perp SELL 都可能成交而 spot BUY 被拒，裸空随重试增长。pause 在这里
   是止损。

选 pause 而非 stop/fatal：条件时变且按币种（见下），操作员可换币建新任务或
待上限清空后恢复，不该把任务判死。

**接线**：沿用既有 task-local pause 链路的结构（腿分类 → 信号派生 → pause），
为新类别补一条显式映射 `collateral_cap → pause_reason="collateral_cap_full"`；
**不复用** `insufficient_margin`——其展示语义是「保证金不足」，对 51169 是
伪事实。文案作为 additive wire 字段随 pause 状态下发（字段名实现定）；UI 是
本 stage 显式非目标，展示接线归既有「原话展示」follow-up，但绝不允许 51169
走 `insufficient_margin` 的既有展示渲染出伪文案。ADVISORY 不动：pause 的
触发条件是被拒腿上的分类事实，与单腿与否无关；T2 不引入任何以 single_leg
结果为条件的暂停/冻结。

**90–100% 占用带**：占用在 90% 与 100% 之间时，更小的单仍可能成功（单笔上限
50,000 USD 等值），所以 51169 **不**普遍等于「任何数量都不行」——对今天的
NOM 等于，因为 NOM 已超 100%。决定：本 stage 对该带**不做任何机制**——占用
率当前无处可读（T4 recon 待答，§5），读不到占用率的缩量重试就是盲猜；系统
只保证**不作反向声称**：分类与文案都不得写「与数量无关/任何数量都不行」。
缩量重试若将来要做，记 follow-up `p3-collateral-cap-band-smaller-size`
（仅当 recon 发现占用率可读时才可操作），本 stage 不实现。

**时变性与不缓存**：上限被全平台用户共同消耗，打满的币可以之后清空、反之
亦然。分类是对单次响应的无状态判定；任何实现不得把「该币打满」缓存为币的
静态属性，不得永久拉黑币种；pause 为任务级、操作员可恢复。

**操作员文案（冻结，逐字）**：

> {asset} 已达币安平台级抵押金额上限（该上限为全平台所有用户共享，并非本
> 账户保证金不足，追加资金无效）。现货腿当前无法买入保证金账户，可更换
> 其他币种或稍后重试；若该币上限占用未满 100%，调小金额也可能成功。

`{asset}` 为币种占位符。该文案是 `pause_reason="collateral_cap_full"` 的
展示文案，实现与消费方不得改写措辞。

### 2(e) attempt 行上卷：做

**决策**：`resolve_attempt` / `finalize_attempt` / `settle_attempt_no_counters`
在结算 pair 时，把两腿的分类按固定优先级上卷到 attempt 行：
`fatal > auth > collateral_cap > insufficient_funds > unclassified > absent >（无）`
（`collateral_cap` 置于 `insufficient_funds` 之上：两者都 pause，上卷取更
具体的诊断），取优先级最高一腿的 `error_category` + `error_code`。理由：attempt 是 entries/UI 投影读的
行，今天只有 fatal 上卷（`store.py:968`），造成实盘证据里 attempt 行全 NULL 的
现状；上卷是纯读腿行的派生写，不改任何控制流。

## 3. T3 — 原始返回与订单详情全量落库

### 3(a) 存储形态：新建 `hedge_open_raw_response` 表

**决策**：

```text
CREATE TABLE hedge_open_raw_response (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id      INTEGER NOT NULL,      -- hedge_open_attempt.id
    leg             TEXT NOT NULL,         -- spot | perp
    client_order_id TEXT,
    source          TEXT NOT NULL,         -- order_post | order_query
    endpoint        TEXT NOT NULL,
    http_status     INTEGER,               -- NULL = transport 层失败
    transport_error TEXT,
    business_code   TEXT,
    business_msg    TEXT,
    body            TEXT,                  -- 原始响应体，≤ BODY_MAX_BYTES
    body_truncated  INTEGER NOT NULL DEFAULT 0,
    captured_at_us  INTEGER NOT NULL
);
CREATE INDEX idx_hedge_raw_attempt ON hedge_open_raw_response (attempt_id, leg, id);
```

**对照既有 schema 的论证（被否决的两个备选）**：
- **在 `hedge_open_leg` 加 msg/payload 列**：一条腿一生会有多个响应（POST、
  inline confirm GET、多轮 drain GET），单列放不下多次交互；把 16KB 级文本塞进
  最热的业务行也拖累每次 `list_attempts_page` 读取。否决。
- **写 `hedge_open_log`**：该表直接暴露在遗留 `/logs` 分页（`service.get_logs`）
  和 entries 投影的数据源上，原始响应体会灌进操作时间线 UI——UI 是本 stage 显式
  非目标；且 log 的 `attempt_id` 存 uuid 而腿级关联需要 leg 维度。否决。

### 3(b) 成功与失败都存

捕获点覆盖每一次真实交互：两腿 POST 响应（含 margin 拒单——正是 51169 那种）、
UM inline confirm GET、drain 阶段的每次 `query_leg` GET。实现方式：
`HedgeHttpResponse.raw_body` 已存在（`hedge_open_live_client.py:83-98`），
`LegDispatch` 增加 `raw_response: dict | None`（http_status / transport_error /
code / msg / body 截断后），由 service 在业务事务**之后**调用
`store.append_raw_response` 落库。验收口径：出现下一个 51169 时，
`SELECT business_code, business_msg, body FROM hedge_open_raw_response` 即可解释，
不再需要问币安客服。

### 3(c) 保留策略：本 stage 不轮转，体量有界并留 follow-up

单行 ≤ `BODY_MAX_BYTES`（16KB，超出截断并置 `body_truncated=1`）；每 attempt
2–6 行；attempt 数受 `target_n` 硬上限约束、节奏 1 对/秒。最坏情形每 attempt
<100KB，实际币安订单响应 <2KB。**不做自动删除**：本 stage 的主题就是不丢证据,
在数据可信 stage 里引入自动清删逻辑是自相矛盾的。体量若成为现实问题，修剪策略
记为 follow-up（`p3-raw-response-retention-policy`）。

### 3(d) 脱敏：按构造保证——只存响应体

凭据只出现在**请求**侧（header `X-MBX-APIKEY`、签名在 query/body）。
`HedgeHttpResponse` 按构造只含响应体（client 的 docstring 与实现均不保留请求
参数/headers），`append_raw_response` 的唯一 body 来源是
`HedgeHttpResponse.raw_body`。币安响应体（订单 JSON / `{code,msg}`）不含凭据。
测试断言：落库 body 与注入的假响应体逐字节一致，且写入路径不存在任何取请求
参数/签名的调用（对 writer 的入参签名做静态断言 + 用例断言表中无
`signature=`/`X-MBX-APIKEY` 字样）。

### 3(e) 存储失败不改控制流

`append_raw_response` 在业务事务提交**之后**、独立短事务中执行，调用点
try/except 包裹：失败绝不把成功单变失败、不回滚业务写。为了不让失败本身变成
静默降级，失败时 best-effort 记一条 `hedge_open_log` 任务事件
`kind="raw_persist_failed"`（该记录再失败则放弃——控制流优先级高于审计完备）。
已到 `TERMINAL_RECORDED` 的腿同样有 raw 记录：捕获发生在响应返回的当下，与
终态判定无关。

## 4. T5 — 实盘敞口时间戳

### 4(a) 两条路径统一推导

**决策**：`service._dispatch_to_outcome` 增加必传参数 `ts_us`，由两个调用点
（`service.py:1581,1597`）传入手头的 `now_us`；`service.py:1688` 的字面量 `0`
随之消失。executor 路径已传 `ctx.ts_us`（`executor.py:342`），不动。两条路径由
此汇聚到同一条规则：**敞口时间戳 = 结算该 attempt 时的 wall clock**（与
`store._exposure_from_legs` 的 reconcile 路径同义）。

**Backstop**：`domain.build_leg_exposure` 对 `ts_us <= 0` 直接 raise
`invalid_field`——非正时间戳永远是编程错误，宁可当场炸掉进 worker 的异常收容
（任务可手动恢复），也不再渲染一个 1970。这是「宁可显式失败」原则的字面执行。

### 4(b) 覆盖实盘路径的回归测试

服务层测试（落 `test_hedge_task_local.py` 或 `test_hedge_service.py`，模式仿照
既有 live-path 测试）：构造 `HedgeOpenService`，注入 duck-typed 假 live
executor（`dispatch()` 返回单腿 accepted 的 `LiveAttemptDispatch`）与受控
wall clock；走 `_dispatch_live` 全链路后断言
`task.leg_exposure.ts == 注入时刻的 ISO` 且 `!= 1970-01-01…`。该测试走的是
`service._dispatch_to_outcome`（实盘路径），只测 `executor.py` 的用例不满足本
条（`00-task.md` T5 验收原文）。另加 domain 单测：`build_leg_exposure(ts_us=0)`
raise。

### 4(c) `leg_exposure.price = null` 是 T1 下游症状：确认，不另打补丁

两条恢复路径：inline confirm 成功 → `LegDispatch.avg_price` 来自订单详情 GET →
`build_leg_exposure` 取到真价；confirm 失败走 drain → `_exposure_from_legs`
（`store.py:1146-1165`）由 `quote/base` 推算。两条都经 T1 修复自然恢复，无需碰
敞口文档本身。实现报告须按 `00-task.md` 要求陈述实测结果。

### 4(d) 现存 1970 记录 → §6。

## 5. T4 — 抵押上限的只读 recon（付费判别实验已取消）

**本节不设计 preflight 修法。** preflight（`domain.py:806-825` 的
crossMarginFree 闸门）在 recon 回答前一行不动。

### 5(a) 判别实验取消

原 §5 规定的付费判别单（无并发 UM 单的 NOMUSDT margin BUY）已于 2026-07-28
取消。其解读是预先钉死的：「仍然 51169 ⇒ 与并发无关：原因在抵押折算系数或
钱包位置」——而 `02-collateral-cap-finding.md` 已从交易所自己的 UI（用户
app 报最大买入数量为 0）与官方 FAQ 到达了这个分支。下这笔单是花真钱确认一个
已知答案。并发争用假说未被严格证伪，但已不再需要：上限解释预测了零并发下
完全相同的失败。**本 stage 不下任何单**；不下单不需要任何用户授权。

### 5(b) recon 要回答的问题

**是否存在任何 API 面，暴露按币种的抵押上限（Maximum Collateral Limit）或
其当前占用？** 已知事实：两份官方 FAQ（见 `02-collateral-cap-finding.md`
§Sources）都没有点名任何端点或数据页。FAQ 里的缺席**不是** API 里不存在的
证明——这是一个开放事实，recon 完成前不得把任何一个答案写成结论。

### 5(c) 方法：只读，两类动作

1. **公开文档核读**（无签名）：在币安官方 API 文档（margin/SAPI 与
   Portfolio Margin/PAPI 两处）检索 "collateral" / "Maximum Collateral" /
   "collateral limit" 相关端点，记录每个命中端点的字段清单与文档 URL。
   执行者：bookkeeper 或后续设计会话均可。
2. **签名 GET**（只读；不下单、不写库、不启停服务）：执行者：**human
   operator**（代理不发私有请求，与 W0 同规）。

候选端点（本节依据公开文档知识列出，端点名/权限类型**均未验证**，执行时以
当日官方文档为准，并把核对到的文档 URL 记进证据文件）：

| 候选 | 能证明什么 | 不能证明什么 |
| --- | --- | --- |
| `GET /sapi/v1/margin/crossMarginCollateralRatio`（未验证） | 抵押折算率表是否可程序化读取 | 折算率 ≠ 上限占用；即使可读也推不出「打满」 |
| `GET /sapi/v1/margin/available-inventory`（未验证） | 平台可借库存是否可读 | 借币侧库存 ≠ 抵押上限；NOM 显示 0 也只是暗示，不构成闸门依据 |
| `GET /papi/v1/account`、`GET /papi/v1/balance`（已在 allowlist） | 响应里是否存在任何按币种上限/占用字段（预期没有——文档未列） | 字段缺席只说明这两个面看不见，不代表别处没有 |
| PM FAQ 指向的 web「Trading Parameters」页 | 网页上是否展示上限/占用 | 网页数据若无官方 API 镜像，不能成为 preflight 依赖（非官方 bapi 网页端点不是契约材料） |

每条的采集物：请求/检索式（脱敏）、完整响应体或文档截录、一句话判断。
**没有命中也要记录检索式与检索范围**——「查过且没有」与「没查」必须可区分。

### 5(d) 证据落盘

`reports/api-samples/2026-07-hedge-order-truth-v1/collateral-cap-recon.md`，
含北京时间、每条动作的端点/文档 URL、原始内容（脱敏）、结论一段。文档核读
部分与签名 GET 部分可分次补齐，各自署明执行者。

### 5(e) preflight 决策（条件式，recon 回答后才生效）

- **存在**能暴露上限/占用（或直接暴露「最大可入/买数量」——即 app 显示的
  那个数）的端点 ⇒ 下一个设计增量为 preflight 设计真实闸门：对照该端点的
  实际响应形状设计，本节不预先猜测字段。闸门必须每次实时读取（见 5(f)），
  且把「读不到」处理为「不知道」而非「通过」。
- **不存在** ⇒ preflight **看不见这个约束，就不得假装看得见**：不加任何
  基于猜测的闸门，处理完全归 T2（精确分类 + task-local pause + 真话文案）。
  「preflight 有意不动，理由如下」是完整、可验收的 T4 结局；recon 结论段须
  把这句话连同依据显式写出。

两个分支里，preflight（`domain.py:806-825`）在 recon 回答落盘前都一行不动。

### 5(f) 时变性

上限由全平台所有用户的持仓共同占用：今天打满的币可以之后清空，反之亦然。
任何实现（含将来可能的闸门）不得把「某币打满」缓存为币的静态属性，不得永久
拉黑币种；每次判断必须来自当次实时读取或当次交易所拒单。

### 5(g) 机制注记：现存裸空与上限的交互（仅记录事实，本 stage 不行动）

原 §5(a) 曾正确指出：买入 10000 NOM 现货恰好对冲现存 SHORT 10000 NOMUSDT
裸空、不产生新敞口。该观察现在有更尖锐的后果：**NOM 打满上限期间，这条路
不可用**——现货买不进保证金账户，裸空无法用「买现货」压平；压平只能在 UM
上买回永续（perp 腿不受抵押上限影响）。这是机制事实注记：解不解、何时解是
用户的操作；平单功能属于本计划第三个 stage；两者都不在本 stage 范围。

## 6. 历史数据处置（T1(e) + T5(d) 合并结论）

**结论：改——但只通过代码里的一次性迁移，带测试，禁止任何手工 SQL。**
两条坏记录（`hedge_open_leg id=6` 的假 0 金额、`hedge_open_task a1d0a9ac` 的
1970 时间戳）都在污染一笔**现实存在的裸空头寸**的唯一持久记录，"不动"意味着
position/PnL 持续错误、敞口记录持续声称发生在 1970。

迁移作为 `store._migrate()` 的守卫式新步骤（幂等、无网络、随下次服务重启生效）:

1. **M1（T1(e)）**：`hedge_open_leg` 中
   `exchange_status='FILLED' AND cumulative_base_qty > 0 AND
   cumulative_quote_amt = '0'` 的行 → `cumulative_quote_amt = NULL`。
   现库中恰好命中 leg id=6。语义：我们**不知道**那笔的名义金额——NULL 是诚实的
   答案，假 0 不是。**不做网络回填**：迁移必须确定性、离线；真实金额存在于币安
   （orderId 888412130），W0 样本会把它作为证据留在 api-samples 里供人查阅，但
   生产库不由代码硬编码回填单行数据（一次性特判某个 orderId 的代码比诚实的
   NULL 更糟）。若用户将来想恢复该数字，那是一次单独授权的 follow-up。
2. **M2（T5(d)）**：`hedge_open_task` 中 `leg_exposure` JSON 的
   `ts == "1970-01-01T00:00:00.000000Z"` 的行 → `ts` 改写为该 task 单腿接受腿的
   `dispatched_at_us` 对应 ISO（同一事件的真实记录时刻，误差 <1s）。现库中恰好
   命中 a1d0a9ac（perp leg id=6 的 `dispatched_at_us` 存在，实盘证据
   `01-live-record-evidence.md` 已核实 `last_query_at_us == dispatched_at_us`）。
   `price` 保持 null（未知，见 M1）。
3. **审计**：每改一行，同事务内写一条 `hedge_open_log` 任务事件
   `kind="data_migration"`，payload 含表名、行 id、字段、before/after——迁移
   不静默。
4. **测试**：用旧 schema + 上述两行同形数据构造 fixture 库，断言迁移后
   NULL/真实 ts/审计事件齐备，且二次运行为 no-op。

有意的良性性质：生产服务（PID 96409）仍跑旧代码，重启前还可能写入新的
「FILLED+假 0」行；M1 是规则式而非点名式，升级后首次重启会把间隙期的行一并
修正。

## 7. 数据契约与 schema 变更汇总

| 变更 | 方式 | 迁移 |
| --- | --- | --- |
| `hedge_open_leg.cumulative_quote_amt` NOT NULL → 可空 | SQLite 不支持改约束 → 事务内表重建（CREATE new → INSERT SELECT → DROP → RENAME → 重建三个索引），`_migrate()` 内以 PRAGMA `notnull` 探测守卫，幂等 | 是（结构） |
| 新表 `hedge_open_raw_response` + 索引 | `CREATE TABLE IF NOT EXISTS` | 是（additive） |
| 历史数据 M1/M2 | 见 §6 | 是（一次性数据） |
| `LegDispatch.cumulative_quote: Optional[str]`、`+ raw_response` | seam 内部契约（live_hedge_executor ↔ service ↔ store） | 否 |
| attempt 行 error 上卷 | 既有可空列，写入逻辑变化 | 否 |
| wire：leg doc `cumulative_quote_amt: string\|null`；position doc `+ avg_price_incomplete`（additive） | API 文档口径放宽/新增 | 否 |

**与冻结契约的关系**：ADR-2（client-ID 对账）不变且被更重地依赖；ADR-3
（acceptance 口径、advisory）不变。被修订的是 real-api-v1 设计中「terminal
fill/residual 数据记录自 POST 响应」的取数口径——单列为契约修订，见
11-adr.md ADR-T1，所需原始样本 = W0。

## 8. 测试策略

既有 9 个套件保持全绿（清单见 `00-task.md` §Tests，含
`test_hedge_purity.py`——domain/store/executor 仍不得引入网络/签名 import，本
设计所有新逻辑均满足）。新增（按验收标准逐条锁）：

- **T1**：给 live executor 注入 2026-07-27 实盘形状的 UM POST 响应（有
  orderId/status/executedQty、无 cumQuote/cumBase/avgPrice）→ 断言腿不落 0
  名义：inline confirm 成功场景金额来自 GET 注入体；confirm 失败场景腿非终态、
  库中 quote 为 NULL；margin POST 带 `cummulativeQuoteQty` 场景直接终态。
  `_leg_final_fields` 规则表逐条单测（None→NULL、"0"→"0"、推算回退、拒绝
  缺失强转 0）。`aggregate_positions` 对 NULL 腿的跳过 + `avg_price_incomplete`。
- **T2**：正数 fatal（表内暂无→用注入表测机制）、正数 insufficient-funds
  （margin 表内暂无实证码→同样用注入表测机制，覆盖 `00-task.md` 该验收行）、
  `51169 → collateral_cap`（task-local pause + `pause_reason=collateral_cap_full`
  + §2(d) 冻结文案逐字断言，且不落 `insufficient_margin`）、正数未列出
  （`unclassified` 落库、计数器行为与今天一致）、全部负数码判定不变的回归
  矩阵、attempt 上卷优先级（含 `collateral_cap` 位次）。
- **T3**：假 51169 拒单 → `hedge_open_raw_response` 行可查出 `business_msg`
  与全文 body；成功单同样有行；截断标志；raw 写失败（注入抛错的 store 方法）
  不改变 attempt/leg/task 任何业务结果；脱敏断言（§3(d)）。
- **T5**：§4(b) 的实盘路径服务级测试 + `build_leg_exposure(0)` raise +
  dry-run 路径回归不变。
- **迁移**：§6(4) + 表重建幂等 + 旧库数据完整保留。
- **fold-in（若采纳，见 breakdown）**：`compute_preflight` 输出
  `spot_min_qty/spot_max_qty/perp_min_qty/perp_max_qty` 键名与
  `_leg_qty_filters` 读取键的契约测试。

## 9. recon 过期事实复查（dispatch 指定问题）

对 `reports/api-samples/2026-07-hedge-open-live-v1/order-endpoints-filters-recon.md`
逐节判断（该文件是证据，不修改；本节结论供实现与评审引用）：

| 节 | 判断 |
| --- | --- |
| §E UM RESULT schema（:98） | **已过期**（cumQuote/avgPrice/cumBase 被移除；DELETE 端点同批被移除——将来做平单 stage 时同样适用，预先记入） |
| §E margin RESULT schema | 文档层面仍有效（changelog 未列 margin），**但未经我方实盘证实**——两次真实 margin 单都被拒，从未见过成功体。T3 落库后第一笔真实 margin 成交将自动产生首个实证样本 |
| §E `fills[]` 可选字段 | 未验证 |
| §A/§B 请求参数表 | 实盘间接证实（2026-07-27 两腿请求均通过格式校验；51169 是格式校验之后的业务拒绝） |
| §C 公开 filters | 每次 preflight 实时读取，机制上不陈化；样本数值已标注不可硬编码 |
| §F 权重/限频 | 未验证漂移，影响面小（既有 429 处理覆盖） |
| §G 无 PAPI testnet / 无 test 端点 | 2026-07-27 复核仍成立 |

**纪律**：实现与评审不得把 recon §E 的响应 schema 当作现行事实引用；现行事实
以 W0 样本与 T3 落库的真实响应为准。

## 10. 文件边界

**允许修改**：

```text
backend/hedge_open_tasks/domain.py
backend/hedge_open_tasks/store.py
backend/hedge_open_tasks/service.py
backend/hedge_open_tasks/executor.py
backend/services/live_hedge_executor.py
backend/tests/test_hedge_domain.py
backend/tests/test_hedge_store.py
backend/tests/test_hedge_service.py
backend/tests/test_hedge_executor.py
backend/tests/test_hedge_task_local.py
backend/tests/test_hedge_api.py
backend/tests/test_live_hedge_executor.py
```

**禁止修改**（重点项）：`backend/services/hedge_open_live_client.py`（本设计
不需要动它——`raw_body` 与两个查询端点均已存在；把安全审计过的传输面锁死，若
实现中发现确需改动（唯一可预见触发：W0 证明 GET 也丢字段 → userTrades 契约
修订），停下来走契约修订流程，不得顺手扩 allowlist）；`binance_signing.py`；
`frontend/**`；`backend/borrow_tasks/**` 与全部借款/公共快照面；`schemas/**`；
`scripts/**`；`docs/**`；`reports/**`（除本 stage 目录）；
`data/**`（**任何**对生产库的写入，含迁移的"顺手试跑"——迁移只在测试的临时库
上验证）。

## 11. 风险与未决点

1. **（最大）订单详情 GET 的 post-2026-07-14 响应形状未验证** —— W0 样本
   缓解；NULL 表示法兜底；fallback 分支（userTrades 契约修订）已预声明。
2. **margin 成功响应体从未实测** —— 文档口径实现 + T3 自动取证；首笔真实
   margin 成交前，margin 腿金额契约标记「documented, unverified live」。
3. **表重建迁移作用于生产库（下次重启时）** —— 单事务、幂等、fixture 测试；
   风险窗口是重启瞬间，失败则事务回滚、旧表原样。
4. **51169 → pause 的行为变化** —— 有意变严，依据是平台级抵押上限事实
   （`02-collateral-cap-finding.md`），已在 §2(c) 枚举；评审须确认用户对
   「触发平台抵押上限的币会暂停任务（文案见 §2(d)：换币或稍后重试、追加
   资金无效）」无异议。**不是**「margin 保证金不足会暂停任务」——那个提法
   的前提已被证伪。
5. **金额未知时 pair 结算推迟** —— 有意（真实未知不该结算）；极端情况需操作员
   介入，与今天 UNKNOWN 腿一致，无新增停摆模式。
6. **wire 上 `cumulative_quote_amt` 可为 null** —— 前端展示未知值的方式属
   既有「原话展示」follow-up；本 stage 只保证不骗。
7. **T4 recon 未执行** —— 付费判别实验已取消（§5(a)），本 stage 不下单，
   不下单不需要任何授权；剩余只读 recon 的签名 GET 部分需 human operator
   排期，文档核读部分 bookkeeper 即可做。recon 迟迟不做时 preflight 保持
   不动是安全默认（看不见的约束不假装看见），不阻塞 T1/T2/T3/T5。

## 修订记录

- **2026-07-28 17:29 CST，窄幅修订**（执行模型：Claude Fable 5，依据
  `16-design-revision.dispatch.md`）。原设计产于 14:45:33，未见 14:46 才入
  packet 的 `02-collateral-cap-finding.md`（NOM 打满平台级抵押上限）。本次
  修订仅限以下章节，其余原样：
  - **§2(a)/(c)/(d)/(e)**：`51169` 由 `insufficient_funds`（pause_reason
    `insufficient_margin`）改为独立新类别 `collateral_cap`（pause_reason
    `collateral_cap_full`）——原归类是事实错误：51169 不是本账户资金不足，
    是平台级按币种抵押上限打满，加钱无效。补 90–100% 占用带、时变不缓存、
    冻结中文文案；上卷优先级插入 `collateral_cap`。
  - **§5**：付费判别实验取消（结果已知，花真钱确认已知答案），整节替换为
    只读 recon 规程（上限/占用是否有 API 可见面）+ 条件式 preflight 决策 +
    现存裸空的机制注记。
  - **§8 T2 测试行、§11 风险 4/7**：随上述决定同步。
  - 同批修订 `11-adr.md` 的分类 ADR（文件内编号 **ADR-T3**；dispatch 称
    ADR-T2 系笔误，ADR 编号与任务号本就错位）与
    `12-development-breakdown.md` §3.5 T2 测试行、§4。
  - 注：§0 目标段仍保留立项时对 T4 的一句旧描述，dispatch 将修订面限定于
    §2/§5/§8-T2/§11，未授权改 §0；以本文件 §5 为准。

---

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/10-design.md, 11-adr.md, 12-development-breakdown.md
本地北京时间: 2026-07-28 17:29 CST
下一步模型: bookkeeper
下一步任务: 归档修订后的三份产物并核对 diff 是否只落在指定章节
