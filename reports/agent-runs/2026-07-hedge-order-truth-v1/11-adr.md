# ADR — Hedge Order Truth And Error Fidelity v1

只记录本 stage 新增/修订的决策。与既有 ADR 的关系逐条显式声明：
`reports/agent-runs/2026-07-hedge-open-real-api-v1/11-adr.md` 的 ADR-1..5
（下称 real-api ADR-N）除本文标注的修订外全部继续有效。

## ADR-T1: UM/CM 成交数据的权威来源改为订单详情 GET，读取发生在终态之前 【契约修订】

**Context**：币安 2026-07-14 起从 `POST /papi/v1/um/order`、`/papi/v1/cm/order`
（及同路径 DELETE）响应移除 `cumBase`/`cumQuote`/`avgPrice`；margin 端点不受
影响。现实现从 POST 响应取成交金额并立即终态（实盘证据：
`hedge_open_leg id=6` FILLED/10000/quote=0，`last_query_at_us == dispatched_at_us`）。

**Decision**：按产品显式分流成交数据来源（`FILL_FIGURES_SOURCE` 映射）——
margin 腿：POST RESULT 响应仍为权威；UM/CM 腿：POST 响应只证明 acceptance，
权威成交数据来自既有 allowlist 内的
`GET /papi/v1/um/order?origClientOrderId=..`。读取时机：acceptance 后立即做一次
inline confirm GET；inconclusive 则腿保持非终态，由既有 worker drain 补齐。
UM 腿「FILLED 且金额已知」才允许 `TERMINAL_RECORDED`。

**Consequences**：常见路径每 attempt 多一次 weight-2 GET（<0.5s）；confirm 持续
失败时 pair 结算推迟（真实未知不结算——有意）；`_send_one_leg`、
`_leg_terminal`、`leg_is_terminal_fill` 收紧为按产品判定。

**与既有 ADR 的关系**：real-api ADR-2（client-ID 对账、never-resend）不变且被
更重依赖；real-api ADR-3（acceptance 口径、observational fill）不变——计数器仍
键在 orderId。**被修订的冻结契约**：real-api 10-design「Durable Attempt Model」
中 leg 记录 actual base/quote/fee 取自 POST 响应的取数口径。

**契约修订所需原始样本**（AGENTS.md 硬门）：
1. 字段移除事实：币安官方 Portfolio Margin changelog（已录于
   `18-live-acceptance-findings.md` §F-1，2026-07-27 核实）+ 实盘记录
   `01-live-record-evidence.md` leg id=6；
2. **新权威来源的响应形状：待补** —— W0 样本（human operator 对
   orderId 888412130 的一次只读订单详情 GET，落
   `reports/api-samples/2026-07-hedge-order-truth-v1/um-order-detail-post-removal-sample.md`）。
   changelog 未列 GET 端点，"GET 仍带这些字段"目前是推断，标记**未验证**。

**Rejected**：user-data WebSocket（无 ws 基础设施；real-api ADR-5 将 ws 保留给
smooth 模式；listenKey 生命周期不值得为 1s 节奏引入）；
`GET /papi/v1/um/userTrades`（不在 allowlist，属契约扩面，仅当 W0 证明订单详情
GET 也丢字段时作为已预声明的 fallback 修订路径）；继续信任 POST 响应 +
文档回填（正是本次事故的形状）。

## ADR-T2: 「取不到」的表示法 = NULL + 非终态重试，"0" 只表示真零

**Context**：`_decimal_str(None, default="0")` 与 `store._leg_final_fields` 把
`"0"` 当缺失，使「字段缺失」与「真实成交为零」不可区分——假 0 因此落库。

**Decision**：金额字段三层改造——`LegDispatch.cumulative_quote` 变
`Optional[str]`（None=响应未携带，金额字段废除 default="0"）；
`hedge_open_leg.cumulative_quote_amt` 经表重建变为可空（NULL=未知，"0"=真零）;
金额未知的 FILLED UM 腿不终态（结合 ADR-T1 的重试）。
`filled_qty * avg_price` 推算回退仅在两个输入都真实存在时保留（由真实数据推算,
非编造）。

**Consequences**：需一次 SQLite 表重建迁移（事务内、幂等、PRAGMA 守卫）；
`aggregate_positions` 跳过 NULL 腿的 notional 并置 additive
`avg_price_incomplete` 标志；wire 契约 `cumulative_quote_amt: string|null`
（additive 放宽）。

**Rejected**：哨兵字符串 "unknown"（魔法值污染全部 Decimal 消费方）；独立
布尔标志列（双源真相）；保持 NOT NULL 用 "0" 兼职（缺陷本体）。

**与既有 ADR 的关系**：不改任何冻结决策；是 real-api ADR-3 "observational
accounting" 的诚实化实现。

## ADR-T3: 错误码分类 = 共享网关层 + (product, code) 业务层，未识别码显式持久化

**Context**：`domain.py:306-353` 三个码集全为负数字面量；币安在 margin 端点用
正数码、UM/CM 用负数码（刻意区分，客服证实）。实盘 51169 落默认分支,
`error_category=NULL`——未识别与已识别不可区分是缺陷本体。**2026-07-28 补**：
51169 的根因已立（`02-collateral-cap-finding.md`）——NOM 打满币安平台级、按
币种、全用户共享的 Maximum Collateral Limit；不是本账户资金不足，加钱无效；
上限时变，不得缓存为币的静态属性。

**Decision**：新纯函数 `domain.classify_exchange_code(product, code, msg)`，
两层查询：先查产品无关的共享网关层（auth/时间戳/权限歧义负数码，任何 papi
端点都可能返回，含 margin 端点）；再按 `(product, code)` 查产品业务层——
`UM_BUSINESS_CODES`（现有负数集合原样迁入，判定不变）与
`MARGIN_BUSINESS_CODES`（只播种实盘证实的 `51169 → collateral_cap`——**独立
新类别**，映射 pause_reason=`collateral_cap_full`，操作员文案冻结于 10-design
§2(d)，说真话：平台抵押上限已满、现货腿暂时买不进保证金账户、换币或稍后
重试、追加资金无效）。独立类别的理由：insufficient-funds 路径的契约是
「a CONFIRMED insufficient balance/margin/available-quantity fact」，51169
已被证实不是——被误述的条件并不比未分类更好。两层未命中 → 显式
`error_category="unclassified"` 落库（控制流同今日默认分支：非致命计数），NULL
从此只表示「无业务码」。pair 结算时按
`fatal > auth > collateral_cap > insufficient_funds > unclassified > absent`
优先级把腿分类上卷到 attempt 行（`collateral_cap` 高于 `insufficient_funds`：
两者都 pause，上卷取更具体的诊断）。

**Consequences**：唯一判定变化是 51169（计数 → task-local pause，更严）——
pause 的依据是上限事实本身而非 -2019 的语义：上限在任务重试窗口内不会清空，
且它只挡正向现货腿、perp 腿不受影响，继续重试会重复「perp 成交 / spot 被拒」
的裸空增长机制。90–100% 占用带内更小的单仍可能成功（单笔上限 50,000 USD
等值）：分类本身与数量无关，但文案不得声称「任何数量都不行」；缩量重试不在
本 stage（follow-up `p3-collateral-cap-band-smaller-size`）。上限时变：不缓存
为币的静态属性、不永久拉黑；pause 为任务级、可恢复。全部负数码判定由回归
矩阵锁定不变；未来任何未列出的 margin 码可见、可追溯；新增 margin 码进表
需要样本证据（真相纪律）。

**Rejected**：`51169 → insufficient_funds` + pause_reason
`insufficient_margin`（本 ADR 初稿方案，2026-07-28 被
`02-collateral-cap-finding.md` 推翻——会向操作员断言「保证金不足」这一伪
事实，诱导无效的加钱动作）；按符号分流（符号只提示产品不给语义，且 margin
端点也发负数网关码如 -1021）；单张扁平合并表（跨产品同值不同义污染 + 规则的
核实对象不可追溯）; 每端点独立全套表（网关码重复、漂移后不一致）；只加
51169 字面量（`00-task.md` 明文不充分）。

**与既有 ADR 的关系**：amendment 21 的 pause/stop/advisory 控制流全部不变；
`single_leg_exposure` 维持 ADVISORY（用户 2026-07-28 裁定）。

## ADR-T4: 原始响应持久化 = 专用 `hedge_open_raw_response` 表，只存响应体，本 stage 不轮转

**Context**：用户 2026-07-27 明确要求存下单原始返回与订单详情全量。现状：
`_business_msg()` 用后即弃，`hedge_open_leg` 无消息/载荷列，`hedge_open_log`
只记请求参数。诊断 51169 被迫求助币安客服。

**Decision**：新建 `hedge_open_raw_response`
（attempt_id/leg/client_order_id/source∈{order_post,order_query}/endpoint/
http_status/transport_error/business_code/business_msg/body≤16KB/
body_truncated/captured_at_us）。捕获每次真实交互（两腿 POST、inline confirm
GET、drain query GET），成功与失败都存。`LegDispatch` 增 `raw_response` 字段
上传；service 在业务事务之后、独立事务、try/except 包裹写入——存储失败绝不改
控制流，失败时 best-effort 记 `raw_persist_failed` 事件。脱敏按构造保证：唯一
body 来源是 `HedgeHttpResponse.raw_body`（响应体），请求参数/签名/API key 从不
进入该类型。保留策略：不自动删除（数据可信 stage 不引入清删逻辑），体量有界
（≤16KB/行、每 attempt 2–6 行、attempt 受 target_n 上限），修剪记 follow-up。

**Consequences**：下一个 51169 类拒单只看自己的库即可解释；每 attempt 新增
数 KB 存储；schema additive（CREATE TABLE IF NOT EXISTS，无重建）。

**Rejected**：`hedge_open_leg` 加大文本列（一腿多次交互放不下一列 + 拖累最热
业务行读取）；写 `hedge_open_log`（直接灌进遗留 /logs 分页与 entries 投影的
UI 面——UI 是非目标；且 log 无 leg 维度）；只存 msg 不存全文（下次遇到未知码
又要问客服）。

**与既有 ADR 的关系**：additive，不触碰任何冻结契约；不改
`hedge_open_live_client` 的传输面。

## ADR-T5: 敞口时间戳单点推导，非正时间戳直接失败

**Context**：`service.py:1688`（实盘路径）硬编码 `build_leg_exposure(.., 0)`
渲染成 1970；`executor.py:342`（dry-run 路径）传真 `ctx.ts_us`——离线测试因此
永远照不到实盘路径（与上一轮 S1/S5 同形）。实盘证据：task a1d0a9ac 的
`leg_exposure.ts = 1970-01-01`。

**Decision**：`service._dispatch_to_outcome` 增加必传 `ts_us`（调用点传
`now_us`），两条路径汇聚到同一规则：敞口时间戳 = 结算时 wall clock（与
`store._exposure_from_legs` 的 reconcile 路径同义）。Backstop：
`domain.build_leg_exposure` 对 `ts_us <= 0` raise `invalid_field`——宁可炸进
worker 异常收容也不再渲染 epoch。回归锁：服务级测试走
`_dispatch_live → _dispatch_to_outcome` 实盘路径断言真实 ts（只测 executor.py
不满足验收）。

**Consequences**：`_dispatch_to_outcome` 签名变化（内部 seam，无 wire 影响）;
未来任何路径忘传时间戳会显式失败而非静默 1970。

**Rejected**：只把 0 改成 now（不锁死推导单点，第三条路径还会再犯）；在
`build_leg_exposure` 里静默用当前时间兜底（又一个看似合理的替代值——正是本
stage 反对的形状）。

**与既有 ADR 的关系**：`leg_exposure` 文档形状 `{leg, qty, price, ts}` 不变；
ADVISORY 语义不变。

## ADR-T6: 历史坏记录由一次性代码迁移修复（假 0 → NULL；1970 → 该腿 dispatched_at_us）

**Context**：生产库现存 leg id=6（FILLED/10000/quote='0'）与 task a1d0a9ac
（leg_exposure.ts=1970）——一笔现实裸空头寸的唯一持久记录持续错误。本 stage
禁止任何手工写生产库。

**Decision**：`store._migrate()` 新增守卫式、幂等、离线的一次性数据迁移：
M1 把「FILLED 且 base>0 且 quote='0'」的腿行 quote 置 NULL（诚实的未知，规则式
匹配，非点名 orderId）；M2 把 `leg_exposure.ts == epoch` 的任务行 ts 改写为该
单腿接受腿的 `dispatched_at_us`（同一事件的真实记录时刻，误差 <1s），price 保持
null；每行改动同事务写 `data_migration` 审计事件；fixture 测试锁行为与幂等。
**不做网络回填**：迁移必须确定性离线；leg 6 的真实金额由 W0 样本作为证据留档,
生产库不硬编码回填。

**Consequences**：迁移随下次服务重启生效；规则式 M1 会一并修正升级前间隙期
（旧代码仍在跑）可能新写入的同形行；若用户要求恢复 leg 6 的真实金额，是单独
授权的 follow-up。

**Rejected**：不动（持续污染 position/PnL 与真实敞口记录）；手工 SQL（stage
明令禁止）；迁移内做签名 GET 回填（迁移不得有网络副作用）；硬编码单行真值
（比诚实 NULL 更糟的特判）。

---

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/10-design.md, 11-adr.md, 12-development-breakdown.md
本地北京时间: 2026-07-28 17:29 CST（ADR-T3 于此时刻按 16-design-revision.dispatch.md 修订；其余 ADR 为 14:45:33 原稿）
下一步模型: bookkeeper
下一步任务: 归档修订后的三份产物并核对 diff 是否只落在指定章节
