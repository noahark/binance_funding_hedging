# Task Handoff: 21-plan-review-r2

## Source Report (author-only; immutable after task end)

- task_id: `21-plan-review-r2`
- role: `Reviewer`（HIGH_RISK 跨 provider 只读计划评审，第二轮）
- target model: Opus 5 / Anthropic（provider `anthropic`，窗口 `claude` / `claude-review`）
- stage_id: `2026-08-19-hedge-order-fee-cost-v1`
- created_at: `2026-08-20 00:26:53 CST`
- base_sha: `1f7612e79065685f243feebaa900e9820f679bce`
- delivery_sha: `none`（计划评审无交付提交；受审对象是 `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md` 的 r2 修订版，commit `1f7612e`）
- status_revision 核对: `4`（与 dispatch 声明一致；`phase=plan_review`、`checkpoint=plan-review-r2-dispatched`、`current_task.state=dispatched`、`rework_count=0`）
- 评审结论: **REWORK（返工）**

### 隔离与只读范围

设计作者 Grok 4.6（`xai`）、Bookkeeper Gemini 3.7 Flash（`google`）、本 Reviewer Opus 5（`anthropic`），三方跨 provider 隔离成立。本 Reviewer 是第一轮计划评审（`20-plan-review`）的作者，未参与本 stage 的设计撰写，不是任何实现或修复的作者。

本次为**纯只读**：未修改任何代码、测试、既有文档、`status.json`、`PROJECT_STATE.md`、`ACTIVE.json`；未 commit / merge / push；未下单、未重启服务、未部署；未访问真实凭据；未读取或查询 live DB。唯一写入是本文件（create-only 授权；Bookkeeper 预检记为 ABSENT，本会话开始时复核 `test ! -e` 仍 ABSENT）。

### 上一轮必改清单的落实核验

| 项 | r2 落实 | 判定 |
|---|---|---|
| **R1** 回补方案取代 D9「不回补」 | D9 改写；新增 §4.3 独立一次性任务：范围（`FILLED` + `order_id` 非空 + 四列全空、开平腿都补、已写跳过）、触发（独立脚本 + Human 明确授权 + 不挂 worker/启动闸门/常开 HTTP 写接口）、控速（签名 GET ≤1/s、429/418 立停落盘、有 running 任务拒启或降速、公开 K 线与签名配额分开）、断点（按 `leg.id` 升序游标）、回补冻价（成交时刻 1 分钟 K 线收盘价，禁用当前现价）、不回写已关闭 `close_log` 旧行 | **落实**（附 O1/O2/O3） |
| **R2** `close_log` 不全载体 | 新增 D11：`trading_fee_incomplete` INTEGER 0/1；「任一参与腿缺构成量 → `incomplete=1` 且 `trading_fee_usdt=NULL`」；§5.2 写死 `insert_close_log` 前参与腿必须已查询 | **部分落实**，见 B1b |
| **R3** 折 U 均价口径 + 禁用 `avg_price` | D5 写死 `cumulative_quote_amt ÷ cumulative_base_qty`；显式「**禁止使用 `hedge_open_leg.avg_price`**」；限定 `fee_other_asset ∈ {USDT, 该腿 base 资产}` 否则判不全 | **完全落实**（三点逐字核对成立） |
| **R4** 时间窗与不可全覆盖认知 | §2.2 新增逐端点权重/按订单号/时间窗表；明确 UM 无 `orderId` 参数须按窗拉取本地过滤；明确「回补不能保证全覆盖」并保留 D10 兜底 | **部分落实**，见 B1a 与 O7 |
| **R5/O1** 每腿至多 1 次、不重试、平滑 ≤40 次 | §4.1 写死；§8 加断言「平滑 `target_n=20` 断言 ≤40 次」 | 落实 |
| **O2** 终态提交后调用 + 两个写入站点 | §4.1 三步顺序明确；两站点点名 `store.py resolve_attempt` 与 `service.py resolve_leg_from_query`。**本 Reviewer 核实 `resolve_attempt` 确实存在于 `backend/hedge_open_tasks/store.py:1435`**，函数名引用正确 | 落实 |
| **O3** money-zero 名单 | §4.2 明确加四个字段进 `_MONEY_NAMES` 且不得放进 `_QUANTITY_NAMES`。核实 `backend/tests/test_hedge_purity.py:239-253` 的 `_is_money_name` 先查 `_QUANTITY_NAMES` 再查 `_MONEY_NAMES`，故该写法有效；四个新名均不在既有 `_QUANTITY_NAMES` 内，不破坏既有断言 | 落实（附 O4） |
| **O4** 冻价口径写明 | D4 写死「写入时冻价、非撮合瞬时价」+ `max_age 300 秒`，与既有 `hedge_preflight_provider._CACHE_MAX_AGE_PRICE = 5*60`（`:54`）一致 | 落实 |
| **O5** colspan 与 `close_log` 键名先定死 | `close_log` 三列表格化冻死（`trading_fee_usdt` / `trading_fee_incomplete` / `fee_bnb_qty`）；colspan 只写了历史表 16→17 | **部分落实**，见 O5-残留 |
| **O6** dispatch Inputs 路径 | §7 明列禁止路径与真实路径；本轮 dispatch Inputs 逐条 `test -e` 全部存在 | 落实 |

---

### 阻塞发现（必须本轮修，in-range）

#### B1 — 「部分和冒充完整」的根因在两个新站点未覆盖 · in-range · 阻塞

本 stage 连续两轮 `REWORK` 均可归因于同一根因：**一个由多个来源相加而成的钱数，在其中某些来源缺失时，仍以完整值的形态输出**。按 `AGENTS.md` §8「同根因刹车」，本轮不再逐点补丁，下面给出该缺陷家族在本设计范围内的**穷举清单**，其中两站点未覆盖，构成本次阻塞。

**站点穷举（本设计范围内，含已覆盖项）**

| # | 站点 | r2 覆盖情况 |
|---|---|---|
| 1 | 持仓表跨腿 open 合计 | ✅ `trading_fee_incomplete` + 金额 NULL（§5.1） |
| 2 | `close_log` 开+平合计 | ✅ D11（§5.2） |
| 3 | 单腿内部：多笔成交求和 | ❌ **未覆盖 → B1a** |
| 4 | 单腿内部：多资产手续费仅 BNB 可定价 | ✅ §4.1「其他两列空，该腿折 U 不全」 |
| 5 | 回补失败/跳过/窗滤为空的腿 | ✅ §4.3 明确走 D10/D11，不当 0 |
| 6 | `fee_bnb_qty` 合计（持仓第二行与 `close_log` 列） | ❌ **未覆盖 → B1b** |

**清单外站点及不适用理由**：资金费 / 借币利息 / 开平滑点三列本轮不触碰（§6 非目标），其合计口径由既有交付负责；`net_pnl` 按 D8 不含手续费，无新增求和；回补脚本结束打印的「尝试/成功/失败」计数仅为日志，不入账不展示，不构成账务输出。

---

**B1a — 合约腿按时间窗拉成交时，缺少窗口收敛与截断检测**

事实：设计 §2.2 认定 UM 官方 PAPI 无 `orderId` 参数、且 `fromId` 不能与时间窗同传；§4.1 因此规定「合约：`symbol` + `startTime`/`endTime`（以 `dispatched_at_us` 为中心，跨度 **≤7 天**），本地滤 `orderId`」。

两个问题：

1. **窗口口径把「接口允许的最大跨度」当成了「应当使用的跨度」。** 一条腿的成交只可能发生在其 `dispatched_at_us` 之后的秒级到分钟级窗口内（`hedge_open_leg` 有 `dispatched_at_us` 与 `last_query_at_us` 两个时间戳，`store.py:88-107`）。开到 7 天既无必要，又把「窗内该 symbol 的**全部**成交」拉了回来——注意这与现货/杠杆路径有本质区别：那两条按 `orderId` 查，返回的就是**该订单**的成交，笔数极小；UM 这条返回的是**该 symbol 七天内所有订单**的成交。
2. **没有任何 limit / 分页 / 截断检测规则。** 由于 `fromId` 与时间窗互斥，一旦窗内成交条数达到接口 limit，返回列表即被截断，而设计要求「拉回后在本地按 `orderId` 过滤」——过滤到的可能只是该订单成交的一部分。分组求和随后给出一个**偏小、却带着完整值形态**的手续费数，没有任何字段表达「我可能漏了」。

这与 D10「不得写部分和，不当 0」正面冲突，且落在本 stage 两轮都在消除的同一根因上。本 Reviewer 离线无法核验币安 UM `userTrades` 的 limit 具体数值，故不引用数字；但「列表接口存在 limit 上限」这一点不依赖具体数值即成立，且设计自己在现货那条写了 `limit=1000`，说明 Planner 已知该参数存在，只是 UM 这条漏写。

**修复要求（Planner 在 §4.1 / §2.2 拍板并写死两条规则）：**
- 窗口按成交时刻收敛（以 `dispatched_at_us` 为起点的分钟级窗口，缺则用 `last_query_at_us`），不再以 7 天上限为默认；7 天只作为接口硬约束记录，不作为查询口径。
- 给出截断判据并写进验收：明确所用 `limit`，且**当返回条数达到 `limit` 时，该腿判定为不全**（`fee_*` 不写入或写入后标不全），不得对可能被截断的列表求和后当作完整值。

**为何必须本轮修而非留作观察**：产出的是账务数值本身且无载体标注不全，一旦冻进 `close_log` 即不可纠正（`insert_close_log` 一次性 INSERT，无更新路径，`store.py:2443-2470`；§5.2 又明确不回写旧行）。这两条属查询口径与安全判据，是 Planner 拍板范围，不是实现细节。

---

**B1b — `fee_bnb_qty` 未纳入不全语义**

事实：D11 只规定「任一参与腿缺构成量 → `incomplete=1` 且 `trading_fee_usdt=NULL`」，对同为聚合输出的 `fee_bnb_qty` 未作规定。而 §5.1 要求「有 BNB 时第二行写 BNB 数量」，§5.2 把 `fee_bnb_qty`（开+平 BNB 数量合计）冻为 `close_log` 的线上键。

场景：腿 A 有可定价的 BNB 手续费、腿 B 完全查不到 → `incomplete=1`、`trading_fee_usdt=NULL`，但 `fee_bnb_qty` 若照常输出腿 A 的数量，第二行就展示了一个**部分的 BNB 数量合计**，与主数字「—」并存，读起来像「金额未知但 BNB 数量确定」。这是同一根因换了个格子。

**修复要求**：在 D11 里补一句——`incomplete=1` 时 `fee_bnb_qty` 一并置 NULL（或明确规定它是「已知部分的下界」并在前端标注不全）。二选一，写死，不留给实现者判断。

---

### 非阻塞发现与实现前必须冻结项

**O5-残留 · 持仓表空态 `colspan` 漏了。** §5.2 只写了历史表 `16 → 17`，但 §5.1 同样给**持仓表**加一列，而持仓表空态当前是 `colspan="17"`（`frontend/index.html:7146`），须改 `18`。该值有硬断言把守：`frontend/self-check.js:8588-8590` 断言「持仓空态须只有一个 td 且 colspan=17」，不同步即跑红。历史表空态 `colspan="16"` 在 `frontend/index.html:5719`，self-check 无对应断言（本次 grep 未发现历史表相关断言），故历史表侧只能靠人工核对。请在前端 dispatch 里同时点名这两个数字与那条断言的更新。

**O6-新 · money-zero tripwire 覆盖不到回补脚本。** `backend/tests/test_hedge_purity.py:217-218` 的扫描范围是 `_MONEY_ZERO_SCOPE = [HEDGE_PKG, _LIVE_EXECUTOR]`，`HEDGE_PKG = backend/hedge_open_tasks`（`:29`）——**`scripts/` 不在范围内**。而 §4.3 的回补脚本恰恰要写 `fee_bnb_price`（K 线收盘价，money name）。脚本里若出现 `price = data.get("close", "0")` 之类，tripwire 不会报。修法是把该脚本路径加进 `_MONEY_ZERO_SCOPE` 列表（一行，零新状态/契约/依赖，贴合既有结构）。仓内已有同类回补脚本先例 `scripts/backfill-spot-identity.py`。

**O7 · §2.2 的权重与时间窗数字本 Reviewer 无法离线核验。** 表中「现货带 `orderId` 权重 5 / 不带 20」「margin 5」「UM 5」「现货 `startTime`+`endTime` ≤24h」「margin <24h」「UM 默认最近 7 天、跨度 ≤7 天、`fromId` 不与时间窗同传」「UM 无 `orderId` 参数」均标注来源为官方 SDK / 现货 rest-api 原文，但本会话无外网、仓内亦无这些端点的样本或契约记录（`docs/api/public-market-contract.md` 未覆盖 trade-list 端点）。故标 contested 而非 fail。**不阻塞的理由**：设计已据此得出「回补不能保证全覆盖」并保留 D10/D11 兜底，即使个别数字有偏差，系统行为仍是 fail-closed（拿不到 → 标不全 → 不当 0）。**但 UM「无 `orderId` 参数」这一条是 B1a 整条设计分支的承重墙**——若它其实支持 `orderId`，则窗口/截断问题自动消失、方案可大幅简化。建议在实现 dispatch 里列为「动手前先用一次真实只读调用或官方文档确认」的前置项。

**O8 · 回补的幂等判据与游标语义冲突。** §4.3 同时规定范围是「四列仍全空的腿」与「按 `leg.id` 升序游标、成功写入**或判定失败后**推进游标」。对一条**永久取不到**的老腿（设计自己承认必然存在：早于 UM 7 天窗、成交历史已丢），单次运行内游标能跳过，但**重跑脚本时若以「四列全空」为范围判据，会再次全量重试**。在一台 2026-08-18 刚吃过借币 IP 418、交易所解封时间至今未知的机器上（`PROJECT_STATE.md` Current Status），这意味着每次重跑都重打数百次注定失败的签名 GET。请在设计或实现 dispatch 中定死其一：游标文件是唯一推进权威，重跑从游标继续、不因四列仍空而回头重试；或为「已尝试且失败」留一个可持久化的判据。

**O9 · 回补的 K 线端点未计入新增外部依赖。** §4.2 只说「白名单 `ALLOWLIST` 加三条只读 GET」，但 §4.3 的回补冻价要用公开 `BNBUSDT` 1 分钟 K 线——这是**第四条**新增外部端点。核实结果：仓内当前**没有任何 klines 调用**（`backend/adapters/binance_public.py` 仅有 `fetch_ticker_price_map` 等既有公开端点，无 `fetch_klines`）。设计未说明它挂在哪条通路（`hedge_open_live_client` 是签名通路，`binance_public` 是快照通路），也未说明它是否需要进任何白名单。请在实现 dispatch 中明确归属，避免实现者在第三条之外静默新开一条打交易所的通路。

**O10 · 查询用的 `symbol` 来源须点名，两腿不同名。** `hedge_open_leg` 表**没有 symbol 列**（`store.py:88-107` 核实，0 处匹配），三条查询都要 `symbol`，须经 `attempt → task` 取。关键：**现货腿与合约腿的 symbol 可能不同**（bStock 类标的现货是 `SNXXBUSDT`、合约是 `SNXXUSDT`，任务上固化了 `spot_symbol` / `spot_base_asset`）。若现货腿误用合约名查 `myTrades`，会返回空 → 该标的手续费永久缺失。这是 fail-closed（不出错数），故不阻塞，但请在实现 dispatch 写死：现货腿用 `task.spot_symbol`，合约腿用 `task.coin`。

**O11 · `trading_fee_incomplete` 的迁移默认值方向未定。** §5.2 声明该列为 `INTEGER NOT NULL`。SQLite 对已有数据的表 `ALTER TABLE … ADD COLUMN … NOT NULL` 必须带 `DEFAULT`。默认值方向有安全含义：`DEFAULT 0` 会把所有既有历史结算行标成「完整」，而它们的 `trading_fee_usdt` 是 NULL，前端会读到「完整 + 无金额」的矛盾态；**应取 `DEFAULT 1`（不全）**，与 D10 的 fail-closed 方向一致。仓内有现成先例：`store.py:580-584` 的 `ADD COLUMN close_gate INTEGER NOT NULL DEFAULT 1`。请在实现 dispatch 写死默认值。

**O12 · 观察（不阻塞）。** 本 stage 控制产物仍未提交：`reports/agent-runs/ACTIVE.json` 已修改未提交，`20-plan-review.dispatch.md`、`21-plan-review-r2.dispatch.md`、`status.json`、`evidence/` 为未跟踪。设计正文本身已在 `1f7612e` 提交，与 `status.json.base_sha` 一致，计划评审锚点成立。进入实现阶段前 Bookkeeper 需要一个已提交的基线。

**未核实项（证据边界）。** 设计 §1 的实盘库计数（约 282 条腿 / 约 269 条 `FILLED`）r2 已自行标注为「Planner 自述，计划评审未核库」，本 Reviewer 按 dispatch 禁令同样未核。该数字只影响回补规模估算，不承载设计正确性。重开触发：若需以回补条数作为验收基线，由有授权角色另行只读取数。

---

### 逐项验收检查结果（对应 dispatch Acceptance Checks）

1. **R1 历史回补方案** — **pass**：范围、触发、控速、断点、冻价、不回写旧行六项均明确且方向 fail-closed；回补冻价用成交时刻 K 线而非当前现价，与 D3 一致。附 O8/O9 两项须在 dispatch 冻结。
2. **R2 `close_log` 不全载体** — **fail**：D11 主体成立（新增标记列 + 金额 NULL + `insert_close_log` 前必须已查询），但聚合输出 `fee_bnb_qty` 未纳入同一不全语义（B1b），迁移默认值方向未定（O11）。
3. **R3 折 U 均价口径与禁用 `avg_price`** — **pass**：三点全部写死并与仓内既定算法 `_cycle_leg_basis_locked`（`store.py:2532-2562`）一致；`avg_price` 禁用理由与 `live_hedge_executor.py:135-175` 的实际取值路径吻合。
4. **R4 接口时间窗与不可全覆盖认知** — **fail**：结论层面正确（承认不能全覆盖 + 保留 D10 兜底），但 UM 按窗拉取缺窗口收敛与截断检测两条规则（B1a）；表内权重/时间窗数字本 Reviewer 离线无法核验，单独标 contested（O7），该 contested 本身不阻塞。
5. **R5 & O1–O5** — **fail**：O1/O2/O3/O4 均已落实且经代码核实（`resolve_attempt` 存在、`_is_money_name` 查找顺序有效、`_CACHE_MAX_AGE_PRICE` 数值一致）；O5 的 colspan 只覆盖历史表，遗漏持仓表 `17 → 18` 及其 self-check 硬断言（O5-残留）。
6. **拆包准备就绪度** — **fail**：先后依赖清晰（后端先、前端抄冻名），但 `close_log` 字段语义（B1b/O11）与 UM 查询形状（B1a）未决前，契约不能冻结，两包不应开工。
7. **Handoff 与回执规范** — **pass**：产物为 dispatch 指定的唯一 create-only 路径，含 Bookkeeper 追加区标记；控制台回执按 `AGENTS.md` §7 review 版输出，结论明确为 REWORK。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/21-plan-review-r2.handoff.md`
  2. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md`
  3. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/20-plan-review.handoff.md`
- 执行：Bookkeeper 核验本交接件，将 B1a、B1b 交回 Planner（Grok 4.6 / xAI）修订 `10-design.md` §2.2 / §4.1 / D11；同时把 O5-残留、O6-新、O7–O11 写进后续实现 dispatch 的 Acceptance Checks。
- 关卡：`10-design.md` 修订后由 Human 决定是否再走一次跨 provider 只读计划评审；取得 ACCEPT 且 Human 批准后，方可拆后端（`claude_glm`）/ 前端（`kimi`）实现包。
- 不能假设的事实：
  - 本次是**计划评审**，按 `AGENTS.md` §8 **不触碰 `rework_count`**；`status.json` 现记 `rework_count=0`，本轮不应改变。
  - 本 Reviewer **未运行任何测试**、**未访问 live DB**、**未联网核验币安文档**；文中所有代码引用为静态阅读所得，行号对应 `1f7612e`。
  - §2.2 的权重与时间窗数字未经本 Reviewer 独立核验（O7）；其中「UM 无 `orderId` 参数」是 B1a 的前提，若该前提不成立，B1a 的修法应改为直接按 `orderId` 查询。
  - B1a 与 B1b 属**同一根因**（部分和冒充完整）的两个站点，不是两个独立缺陷；上文站点穷举清单即 `AGENTS.md` §8「同根因刹车」要求的根因扫描结果，修复时须对照该清单确认无遗漏。
  - 本轮未授权任何下单、重启、部署、merge、push，也未授权回补脚本对 live 库执行。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

**一句话结论：这版改得很好，上一轮的五条基本都补上了，但还差一条得再改一次。改的量是两句话，不是推倒重来。**

**先说改好了的。** 你要的历史回补写进去了，而且写得比我预期的谨慎：单独一个脚本、要你亲口授权才跑、不挂在下单和平仓流程上、每秒最多一次请求、一撞上币安限流就立刻停下来存断点、跑到一半断了能接着跑、已经补过的跳过不重复打。回补时用的是「当时那一分钟的 BNB 收盘价」而不是今天的价——这条很关键，用今天的价会把历史成本改写掉。上一轮我提的另外四条（折算价改用「成交额÷成交量」、禁用那个空字段、每笔至多查一次不重试、把新字段纳入防抹零检查）也都逐字落实了。我还专门去核对了它引用的函数名和常量，这次全部对得上——上一轮那种「路径根本不存在」的问题没有再出现。

**还差的这一条，是同一个老毛病换了个地方。** 这个阶段前后两轮，我挑出来的问题其实是同一个根：**一笔由好几部分加起来的钱，其中某几部分缺失时，还是照样输出一个看着完整的数**。所以这次我按规矩做了一遍穷举，把这个毛病在整个设计里可能出现的六个格子全列了出来，四个已经堵上了，剩两个没堵：

第一个在合约腿。币安的合约接口不支持按订单号查手续费，只能按时间段把那一段时间的成交全捞回来，再自己在本地挑出属于这笔订单的。设计写的是「捞七天」——但一笔订单的成交就发生在下单后几秒到几分钟里，捞七天没必要，而且捞回来的是这个币七天内**所有**订单的成交，量级完全不同。更要命的是设计没写「一次最多捞多少条、捞满了怎么办」。币安这类列表接口都有条数上限，一旦捞满被截断，本地挑出来的就只是这笔订单的一部分成交，加出来的手续费**偏小，但看不出来它偏小**。这正是我们两轮都在消灭的那个毛病。修法两句话：时间窗按成交时刻收窄到分钟级；捞回来的条数如果正好等于上限，这条腿判定为「不全」，不许拿可能缺斤少两的列表去求和。

第二个更小。新加的「不全」标记只管住了金额那一列，没管住旁边那行 BNB 数量。如果两条腿里一条查到了、一条没查到，金额会正确地显示「—」，但 BNB 数量那行还会照样显示查到的那半截，看起来像「钱不知道多少，但 BNB 确定扣了这么多」。补一句「标记为不全时这个数量也一并清空」就行。

**另外七条不拦路，但开工前得写进派工单。** 最值得说的两条：一是**持仓表的空表列数漏改了**——设计只提了历史表 16 改 17，但持仓表也加了一列，它的空表列数现在是 17、要改 18，而且前端自检脚本里有一条硬断言卡着这个数字，不改就直接跑红。二是**防抹零的静态检查扫不到回补脚本**——那个检查只扫两个目录，`scripts/` 不在里面，而回补脚本恰恰是往库里写价格的地方，写错成 0 也不会报警；把脚本路径加进那个名单，一行的事。剩下五条是：币安那几个接口的权重和时间窗数字我离线核不了（不影响安全，因为查不到就标不全，但「合约接口没有订单号参数」这条是整个方案的承重墙，动手前值得实际验一下）；回补脚本重跑时可能把注定失败的老单再全打一遍；回补要用的 K 线接口是第四个新增的外部接口，设计只数了三个，没说它挂在哪；查手续费要用的币种代号在两条腿上是不一样的（现货可能叫 SNXXBUSDT、合约叫 SNXXUSDT），别用错；新加的「不全」标记列，数据库默认值必须设成「1=不全」而不是「0=完整」，否则所有老记录会谎称自己完整。

**成本。** 这轮全程只读：没改代码、没动状态文件、没提交、没下单、没重启、没连外网、没查真实数据库。计划评审不算返工次数，你的返工预算还是满的。设计里那些实盘条数（282 条腿之类）作者自己标了「未核库」，我也没去查——那只影响回补要跑多久，不影响结论。

```text
[TASK_RESULT v2]
任务 ID: 21-plan-review-r2
执行结果: completed（完成）
结果摘要: r2 落实上轮 R1-R5 与 O1-O4，函数名/常量经代码核对无误。但同一根因（部分和冒充完整）尚有两个站点未覆盖：B1a 合约腿按时间窗拉成交缺窗口收敛与截断检测，可能对被截断列表求和且不标不全；B1b 不全标记未覆盖 fee_bnb_qty。已附该根因的站点穷举清单。另有 7 项非阻塞冻结项。
产物: [reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/21-plan-review-r2.handoff.md]
检查结果: [1 R1 历史回补方案: pass（六要素齐备且 fail-closed，附 O8/O9）, 2 R2 close_log 不全载体: fail（fee_bnb_qty 未纳入不全语义 + 迁移默认值方向未定）, 3 R3 折U均价与禁用 avg_price: pass（三点写死且与仓内既定算法一致）, 4 R4 时间窗与不可全覆盖: fail（UM 缺窗口收敛与截断检测；权重/窗口数字离线不可核验另标 contested）, 5 R5 与 O1-O5: fail（O1-O4 已落实并经代码核实；O5 漏持仓表 colspan 17→18 及 self-check 硬断言）, 6 拆包就绪度: fail（close_log 语义与 UM 查询形状未决前不可冻结契约）, 7 Handoff 与回执规范: pass]
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/21-plan-review-r2.handoff.md
修复要求: reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/21-plan-review-r2.handoff.md
阻塞项: [B1a UM 按时间窗拉成交缺窗口收敛与截断检测，可能对截断列表求和且不标不全（in-range）, B1b close_log/持仓的 fee_bnb_qty 未随 incomplete 置空（in-range）]
本地北京时间: 2026-08-20 00:26:53 CST
下一步模型: gemini-3.7-flash（Bookkeeper，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/21-plan-review-r2.handoff.md、reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md、reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/20-plan-review.handoff.md；执行：核验本交接件并把 B1a/B1b 交回 Planner（Grok 4.6 / xAI）修订 10-design.md 的 §2.2/§4.1/D11，把 O5-残留与 O6-新至 O11 写进后续实现 dispatch 的 Acceptance Checks；关卡：修订后由 Human 决定是否再走一次跨 provider 只读计划评审，ACCEPT 且 Human 批准后方可拆后端/前端实现包（计划评审不触碰 rework_count）
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- Bookkeeper: `gemini-3.7-flash`（provider `google`，窗口 `agy`）
- 核验时间（本地北京时间）：2026-08-20 00:36:15 CST
- 核对的 status revision：`4`（`phase=plan_review`、`current_task.state=dispatched`）
- source_sha256（`BOOKKEEPER_APPEND_ONLY` 标记前字节，UTF-8）：`9156801930f4d1932fae5bf93e96dcff17b487be6ab35065e1c747d676dea6df`
- 源边界复核：源区块收口于 Human Brief 闭合代码块（`...[/TASK_RESULT]\n\`\`\`\n\n`），标记独占一行。
- 核验结论：**通过核验，第二轮计划评审 REWORK（返工）结论采信**。
  1. **身份一致与只读合规**：`task_id` / `stage_id` / `base_sha` 与 `status.json` 逐字相同（`base_sha=1f7612e79065685f243feebaa900e9820f679bce`）；`delivery_sha=none`；Reviewer 未修改代码、既有文档或状态文件，除本 handoff 外零写入。
  2. **create-only 成立**：本 handoff 在预检时为 ABSENT，本次任务新建。
  3. **结构合规**：Human Brief 内 `[TASK_RESULT v2]` 结构齐全、与控制台回执一致；评审结论明确为 `REWORK（返工）`；问题记录与修复要求明确指向本交接件。
  4. **同根因刹车与阻塞项成立（in-range）**：
     - Reviewer 按 `AGENTS.md` §8 对「部分和冒充完整」缺陷家族完成 6 个站点穷举扫描；
     - **B1a**：UM 合约按 7 天大窗口拉成交返回该 symbol 全部订单成交，缺少以 `dispatched_at_us` 为起点的分钟级收敛；且缺少 `limit` 截断检测，当返回达到 limit 截断时对部分成交求和会导致隐蔽少算且不标不全；
     - **B1b**：`incomplete=1` 时，第二行/列展示的 `fee_bnb_qty` 未同步置 NULL，仍可能输出部分 BNB 数量造成歧义。
  5. **计数规则**：本轮为只读计划评审，根据 `AGENTS.md` §8 与 `agents/roles.md`，**`rework_count` 保持为 0，不消耗返工预算**。
- 可复现命令（核验脚本）：
  `python3 -c "import hashlib;raw=open('reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/21-plan-review-r2.handoff.md','rb').read();m=b'<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->';print(hashlib.sha256(raw.split(m)[0]).hexdigest())"`
- 后续状态：`status.json` 推进至 `revision=5`，`checkpoint=plan-review-r2-rework`，`current_task.state=verified`；将 B1a、B1b 与 O5-残留/O6-新至 O11 移交 Planner（Grok 4.6 / xAI）修订 `10-design.md`。

## Errata (append-only)

（暂无。）

