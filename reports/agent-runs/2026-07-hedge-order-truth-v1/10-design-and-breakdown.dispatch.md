# Design + ADR + Breakdown Dispatch — Hedge Order Truth And Error Fidelity v1

Human operator: run this prompt in a fresh **Claude Fable 5** session (backup:
Claude Opus 4.8 if Fable5 quota is exhausted — record which one ran). This is
design-only: it must not implement code or launch another model.

The session produces **three** documents in one response, each fenced by an
explicit file marker. Save each block verbatim as its own file:

- `reports/agent-runs/2026-07-hedge-order-truth-v1/10-design.md`
- `reports/agent-runs/2026-07-hedge-order-truth-v1/11-adr.md`
- `reports/agent-runs/2026-07-hedge-order-truth-v1/12-development-breakdown.md`

Routing note: the user chose Codex for **both** review gates this stage, which
frees the Claude provider to design without creating any Review-2 conflict. Do
not route this packet to Codex — Codex must reach both gates having read only
committed artifacts.

⚠️ **The live surface is OPEN this stage.** The backend service is running in
live mode (PID 96409) and the durable Start gate is `1`. Read-only database
access for evidence is fine; any write, any card, any order, any service
start/stop is forbidden. See the prompt body's 硬性约束.

## Prompt body

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、
   kimi -p、codex exec、grok）。需要其他模型时，只输出交接建议，由 human operator 决定。
2. 你只能做本任务要求的只读检查和指定设计输出；不得写产品源码、访问凭据、发起 Binance
   私有请求、启动服务或下单。
3. 输出必须保留事实来源路径、设计判断和未解决风险；不能把未经验证的假设写成事实。

你是 stage `2026-07-hedge-order-truth-v1` 的 stage designer 兼
development-breakdown author。只做设计与任务拆分，不写任何产品代码，不修改
status.json、70-handoff.md、PRD 或源码。

## 背景

上一个 stage 已验收合并，第一笔真实订单成功发出、合约腿真成交。成交之后暴露的
不是"发不出去"，而是**发出去了但我们记下来的东西是假的**：真成交 10000 张记成
金额 0，真拒单 51169 记成无分类，交易所原话没地方存，唯一一条敞口记录的时间戳
是 1970 年。四项里三项都是"系统把手里已有的信息丢掉、换上一个看起来合理的值"。

这是一个数据真实性 stage，不是功能 stage。设计时的总原则：**宁可显式失败，
也不要替换成一个说得通的值**——这正是上一轮 S5 的教训（静默降级把真问题藏住了）。

## 必读

- AGENTS.md；agents/developer-discipline.md；
- reports/agent-runs/2026-07-hedge-order-truth-v1/{00-intake.md,00-task.md,01-live-record-evidence.md,02-collateral-cap-finding.md,status.json}
  —— 其中 01-live-record-evidence.md 是 bookkeeper 从生产库直接读出的原始记录，
  是本 stage 最高级别的事实来源，优先于任何转述；
  02-collateral-cap-finding.md 是 T4 的根因结论（2026-07-28 新增，附官方 FAQ 原文
  引用），它同时给 T2 的 51169 定了必须满足的语义——**先读它再看 T2 和 T4**；
- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/18-live-acceptance-findings.md（实盘现场记录）；
- reports/agent-runs/2026-07-hedge-open-real-api-v1/{10-design.md,11-adr.md}（已冻结契约，
  尤其 ADR-2 的 clientOrderId 对账语义、ADR-3 的 acceptance-not-fill 口径）；
- reports/api-samples/2026-07-hedge-open-live-v1/order-endpoints-filters-recon.md
  —— 注意 :98 行把 cumQuote/avgPrice 记为存在，采集时属实、现在已过期。这份 recon
  的其余部分是否还有同类过期事实，请在设计里给出你的判断；
- backend/services/live_hedge_executor.py；backend/services/hedge_open_live_client.py；
- backend/hedge_open_tasks/{domain.py,store.py,service.py,executor.py}；
- backend/tests/test_hedge_*.py；backend/tests/test_live_hedge_executor.py。

## 五项范围（细节见 00-task.md，不要重述背景，直接给设计）

T1 (P0) 成交金额来源失效。币安 2026-07-14 起从 POST /papi/v1/um/order 与
        /papi/v1/cm/order 的响应里移除了 cumBase / cumQuote / avgPrice；margin
        端点仍然返回 cummulativeQuoteQty。现状链路已核实：
        live_hedge_executor.py:242-246 取不到值 → _decimal_str(None) 返回 "0"
        → store.py:660-668 把 "0" 当作"没有值"，退回 filled_qty * avg_price，
        而 avg_price 也是 None → 最终落库 Decimal(0)。
        设计必须回答：
        (a) UM/CM 腿的权威成交数据改从哪里取——订单详情 GET、user-data WebSocket，
            还是两者结合？各自的延迟、限频、失败语义是什么？
        (b) 这次读取发生在什么时刻？现在腿在 POST 返回后直接进 TERMINAL_RECORDED
            且再也不查（实盘记录里 last_query_at_us == dispatched_at_us）。改成
            "终态前必须查一次"会不会拖慢结算、会不会与既有对账路径冲突？
        (c) margin 与 UM/CM 的取数来源不同，这个不对称怎么在代码里表达成一条
            **有意的按产品分流规则**，而不是现在这种顺手的 or 链？
        (d) 取不到权威数字时怎么落库？禁止再落一个与真实 0 无法区分的 "0"。
            给出你选的表示法（null / 显式 unknown 标记 / 重试）并说明理由。
        (e) 历史数据怎么办？库里已经有一行 FILLED 但金额为 0 的真实记录
            （hedge_open_leg id=6）。是回填、是打标记、还是不动？给出结论与理由。
            注意：本 stage 禁止任何人手工写生产库；如果你的结论是需要迁移，
            那它必须是代码里的一次性迁移并带测试，不是一条 SQL。

T2 (P1) 错误分类对整条 margin 产品线失明。已核实 domain.py:306-353 的
        FATAL_EXCHANGE_CODES / AUTH_AMBIGUOUS_EXCHANGE_CODES /
        INSUFFICIENT_FUNDS_CODES 三个集合里全是负数字面量；币安在 margin 端点
        用正数码、在 UM/CM 用负数码，是刻意区分。实盘证据：51169 落到
        "未列出 4xx → 已知非致命拒绝(计数器)" 的默认分支，error_category 为 NULL。
        设计必须给出**结构性**修法，不是补一个 51169：
        (a) 正负两套码制怎么统一进分类规则？按端点/产品分表，还是按码值符号分流，
            还是引入显式的 (product, code) 键？给出被否决的方案与理由。
        (b) "未识别的码"必须与"已识别的码"可区分。现在的默认分支把两者等同了，
            这才是缺陷本身，符号不匹配只是它的一个表现。
        (c) 分类不得变得更宽松：今天会停/会暂停的码，不许因为这次改动变成非致命。
            列出任何判定发生变化的码。
        (d) single_leg_exposure 保持 ADVISORY（用户 2026-07-28 已定），T2 不得让
            单腿结果暂停或冻结任务。
        (e) attempt 行自己的 error_category/error_code 现在也是 NULL（见实盘证据），
            腿的分类要不要上卷到 attempt？给出结论。

T3 (P1) 存原始返回与订单详情全量。用户 2026-07-27 的原话：
        「记得增加存储下单原始返回订单信息，以及查询订单详情的全量信息」
        现状已核实：_business_msg()(live_hedge_executor.py:77) 把 msg 抽出来用于
        -2010 消歧后就丢弃；hedge_open_leg 只有 error_code/error_category，没有
        消息列也没有 payload 列；hedge_open_log 只记请求参数，从不记响应。
        设计必须给出：
        (a) 存储形态——加列 / 新建 raw payload 表 / 写进 hedge_open_log？
            结合现有 schema 论证，不要硬塞。
        (b) 成功与失败都要存，含 code 与 msg。验收标准是"以后再遇到 51169 这类
            拒单，光看我们自己的库就能解释"。
        (c) 保留策略：原始 body 会不会把库撑大？要不要有上限或轮转？
        (d) 脱敏：原始 body 里有没有需要脱敏的东西？凭据、签名、API key 一律
            不得落库——说明你怎么保证。
        (e) 存储失败不得改变控制流：写 raw 记录失败不能把一笔成功的单变成失败。

T5 (P1) 实盘敞口记录的时间戳是 1970。这一项**不在原提案里**，是 bookkeeper 在
        对齐 intake 时从生产库发现并已核实根因：
        service.py:1688（_dispatch_to_outcome，**实盘**派单路径）调用
        D.build_leg_exposure(spot_leg, perp_leg, 0)，硬编码字面量 0；
        domain.py:882-910 的 build_leg_exposure 用 us_to_iso(ts_us) 渲染，于是
        变成 Unix epoch。而 executor.py:342 的 dry-run 路径传的是真实 ctx.ts_us
        ——**这就是离线测试永远照不到它的原因**，与上一轮 S1/S5 同形。
        设计必须给出：
        (a) 两条路径的时间戳怎么统一推导，而不是各写各的；
        (b) 如何写一个真正覆盖**实盘路径**的回归测试。只覆盖 executor.py 的测试
            不满足验收标准；
        (c) leg_exposure.price 现在是 null，判断它是不是 T1 的下游症状。如果是，
            说明 T1 修好后它自然恢复；如果不是，单独说明——但不要在这里另打补丁。
        (d) 现存那条 1970 的记录（hedge_open_task a1d0a9ac）与 T1(e) 的历史数据
            问题一起给结论，不要分头处理。

T4 (P2) **根因已查明（2026-07-28，本 packet 派发前）。原来那笔判别实验已取消，
        本 stage 不下任何真实订单。** 必读 02-collateral-cap-finding.md。
        结论：NOM 触及币安的 **Maximum Collateral Limit（平台级、按币种的抵押额度
        上限）**。这是**全平台所有用户共用的一个额度**，官方 FAQ 明确适用于
        Portfolio Margin；用量超过 100% 后，该币种"买入或转入 margin 账户"被直接
        封禁，无例外。用户在币安 app 里手工试转入和试买 NOM，被告知
        「代币NOM已达平台抵押金额上限。最大入/买入数量为0。」
        这就足以解释 51169 = MARGIN_TRADE_COEFF_INSUFFICIENT：可用于追加 NOM 的
        抵押折算能力就是 0。也顺带解释了 2026-07-27 那次的不对称——UM 永续 SELL
        不需要 NOM 当抵押品所以成交，margin BUY 需要所以被封。
        已排除：NOMUSDT 不可杠杆交易（公开 exchangeInfo isMarginTradingAllowed:
        true）。已排除作为解法：PAPI test-order 端点——**不存在**，不要围绕它设计。
        已**不再需要**的假设：并发 UM 单吃掉保证金（没被严格否证，但不再必要，且
        额度上限这个解释预测零并发下也会同样失败）。
        ⚠️ **本 packet 仍然不要求你直接改 preflight。** T4 剩下的工作全是只读：
        (a) 摸排：**有没有任何 API 能读到这个按币种的抵押额度上限或它的当前占用？**
            我今天读的两份官方 FAQ 都没提到任何接口，但"两份 FAQ 没提"不等于
            "API 里没有"——请把它当作待查事实，不要往任何一边写成结论。
            只允许公开文档阅读与签名 **GET**；不得下单、不得写任何东西。原始证据
            落 reports/api-samples/2026-07-hedge-order-truth-v1/。
        (b) preflight 的结论**跟着摸排结果走**，不要抢跑：
            有接口 → 设计一个真正的 preflight 闸门；
            没接口 → preflight **根本看不到**这个约束，那就不许假装看得到，处理
            责任整个落到 T2，并在设计里把这句话明确写出来。
            "preflight 有意不动，理由如下"是一个**完整且可接受**的 T4 结论。
        (c) 记住这个条件是**随时间变化**的：额度被全平台用户的持仓吃掉，今天被封
            的币以后可能解封，反之亦然。不许把它当成某个币的静态属性缓存起来。
        对 T2 的影响（必须在 T2 的设计里体现）：51169 现在有了确定的语义——
        不是本账户保证金不足（加钱没用）；不是任务重试窗口内可重试（额度是全平台
        消耗的，几秒内不会松）；也不是永久性的（会解封，所以不许永久拉黑该币）；
        它是**按币种 + 按方向**的（封的是正向的现货买入腿，合约腿不受影响）。
        还有一个别抹平的细节：额度用量在 **90%–100%** 区间时，**更小的单子仍可能
        成功**（单次上限 5 万美元等值）——所以 51169 不等于"任何数量都不行"；
        NOM 今天是超过 100%，才是任何数量都不行。
        给运维的中文文案必须说真话：这个币的平台抵押额度满了，现货腿现在买不进
        margin 账户，换币或稍后再试。写成"保证金不足"是**误导**。

## 三份输出

=== FILE: 10-design.md ===
stage 设计：目标与非目标、每一项的具体设计决策与理由、文件边界（允许/禁止修改）、
数据契约与 schema 变更（含迁移）、测试策略、风险与未决点。
必须显式回答上面每一项里带 (a)(b)(c)… 的问题，不要跳过。
必须单列一节「历史数据处置」，把 T1(e) 与 T5(d) 合并给结论。

=== FILE: 11-adr.md ===
本 stage 的架构决策记录。至少覆盖：T1 的权威成交数据来源与读取时机、T1(d) 的
"取不到时怎么表示"、T2 的正负码制统一方案、T3 的原始载荷存储形态与保留策略、
T5 的时间戳统一。每条给出 context / decision / consequences，并写明被否决的备选。
不要复制上一 stage 的 ADR，只写本 stage 新增或修订的决策，并显式声明与既有 ADR
的关系——尤其 ADR-2（clientOrderId 对账）与 ADR-3（以"被接受"而非"成交"为口径）。
如果 T1 的改动实质上修订了某条已冻结契约，单独标注为契约修订，并说明需要哪些
原始样本来支撑（AGENTS.md 要求契约修订必须有 reports/api-samples/ 下的真实样本）。

=== FILE: 12-development-breakdown.md ===
实现拆分。必须包含：
1. 串行还是并行的建议。当前 intake 的判断是**单 owner 串行**（claude_glm,
   glm-5.2[1m]）：四项都在 backend，且共用 live_hedge_executor.py / store.py /
   domain.py / service.py，切不出不相交的边界；UI 是明确非目标。
   如果你认为存在真正可分的第二个任务，可以推翻这个判断，但必须给出不相交的
   文件边界与需要先冻结的共享契约面；否则明确写"串行"并说明理由。
2. 每个任务：owner 模型/provider、精确的允许与禁止文件清单、数据契约、
   确定性测试命令、证据与报告路径、风险点、评审关注点。
3. 实现顺序。特别注意 T1 与 T5 在 leg_exposure 上有依赖，T2 与 T3 在错误路径上
   有交叉，给出一个不会互相踩的顺序。
4. 是否建议把上一 stage 遗留的 p3-preflight-snapshot-key-contract-untested
   折进来（它与 T1/T2 同属"静默降级"形状，但属于额外范围）。只在真的便宜时建议。
5. 硬性测试约束：不得发真实 POST、不得访问凭据、不得发私有请求、不得起服务、
   不得写生产库。

## 硬性约束

- ⚠️ **本 stage 实盘面是开着的**：服务 PID 96409 以 live 模式运行中，持久化
  Start 闸门 start_gate=1（version 4），库里还有 3 张 paused 的卡。用户被问过
  是否关闸停服务，选择了保持现状——这是用户自己的风险，不是缺陷。
  因此：不得建卡、不得点启动、不得下单、不得碰凭据、不得启停服务、不得写
  data/hedge-open-tasks.sqlite3（任何表，包括 settings 行）。为取证做**只读**
  查询是允许的。
- 还有一笔真实裸空挂着（SHORT 10000 NOMUSDT, orderId 888412130），系统没有平单
  功能。本 stage 不解决它，也不要设计平单。
- 不改任何被 real-api-v1 冻结的契约。若你认为 T1 或 T3 必须改，单列为「契约修订
  建议」并说明需要的原始样本，不要直接写进设计当成既定事实。
- 本 stage 不授予任何实盘权限，且**本 stage 不下任何真实订单**——原来 T4 的那笔
  判别实验已于 2026-07-28 取消（根因已从交易所 UI 与官方文档查明）。T4 剩下的
  只读摸排可以做签名 GET，仅此而已。
- 设计要能被 Claude-GLM 在边界内独立实现，被 Codex 独立复核。
- 事实来源必须带路径。不确定的地方写「未验证」，不要写成事实。上一轮就是因为一份
  采集时属实的 recon 过期了没人复查，才让 T1 溜到实盘。

最后附上下面的 footer，且不做任何代码改动。

当前 Session ID: 报告你的 provider-native id，取不到就写 unavailable 并说明原因
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/10-design.md, 11-adr.md, 12-development-breakdown.md
本地北京时间: 用本地 date 命令取
下一步模型: bookkeeper
下一步任务: 归档三份原始设计产物，不要实现代码
```

Current dispatch executor: **human operator**. The bookkeeper does not execute
Claude commands or relay this prompt to a model.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/10-design-and-breakdown.dispatch.md
本地北京时间: 2026-07-28 07:26:35 CST
下一步模型: human operator
下一步任务: 在全新的 Claude Fable 5 终端执行本 packet，并把三个文件块原样保存到指定路径
