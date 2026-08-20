# Task Handoff: 20-plan-review

## Source Report (author-only; immutable after task end)

- task_id: `20-plan-review`
- role: `Reviewer`（HIGH_RISK 跨 provider 只读计划评审）
- target model: Opus 5 / Anthropic（provider `anthropic`，窗口 `claude`）
- stage_id: `2026-08-19-hedge-order-fee-cost-v1`
- created_at: `2026-08-19 23:15:32 CST`
- base_sha: `b09b1993ae50f6af8b56615655cfb1966b8c60a6`
- delivery_sha: `none`（计划评审无交付提交；受审对象是文档 `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md`，工作树 HEAD 与 `status.json.base_sha` 一致）
- status_revision 核对: `1`（与 dispatch 声明一致）
- 评审结论: **REWORK（返工）**

### 隔离与只读范围

设计作者 Grok 4.6（`xai`）、Bookkeeper Gemini 3.7 Flash（`google`）、本 Reviewer Opus 5（`anthropic`），三方跨 provider 隔离成立；本 Reviewer 未参与本 stage 设计。

本次为**纯只读**：未修改任何代码、测试、既有文档、`status.json`、`PROJECT_STATE.md`、`ACTIVE.json`；未 commit / merge / push；未下单、未重启服务、未部署；未访问真实凭据；未读取或查询 live DB（`data/*.sqlite3`）。唯一写入是本文件（dispatch Allowed Files 的 create-only 授权，Bookkeeper 预检 `test ! -e` 记为 ABSENT，本会话开始时复核仍 ABSENT）。

### 已核实的设计事实（设计陈述 → 代码证据，全部成立）

| 设计陈述 | 证据 | 结论 |
|---|---|---|
| §2.2 轮询回写把手续费写死 `None` | `backend/hedge_open_tasks/service.py:2810-2811`（`fee_amount=None, fee_asset=None`） | 成立 |
| §2.2 `hedge_open_leg` 已有 `fee_amount`/`fee_asset` | `backend/hedge_open_tasks/store.py:100-101` | 成立 |
| D1/D2 加列不删列可行 | `backend/hedge_open_tasks/store.py:478-488` 既有幂等 `ALTER TABLE … ADD COLUMN` 模式（`avg_price` 即按此加入） | 成立，机械改动 |
| §2.2 `hedge_open_fill` 是死表 | `PROJECT_STATE.md` Open Follow-ups「2026-08-14 核验 0 行、生产代码零调用」；`store.py:2662` 非零行只落审计告警 | 成立（独立记录交叉确认） |
| §2.3 `price_map` 来自公开全表 ticker | `backend/adapters/binance_public.py:278-293`（`GET /api/v3/ticker/price` 全表，每次快照一次） | 成立 |
| D4 第一档「进程内 price_map」可达 | `backend/services/snapshot_service.py:1217-1229` `get_cached_source`（只读、不触发刷新）；`backend/app/server.py:1748-1753` 已注入；`backend/hedge_open_tasks/service.py:674-686` service 已持有该 reader | 成立，**零新接线** |
| D4 取价顺序有既有先例 | `backend/services/hedge_preflight_provider.py:463-489`（`price_map` → 公开单 symbol `ticker/price` → None），上限常量 `:54 _CACHE_MAX_AGE_PRICE = 5*60` | 成立，建议直接复用该形状 |
| §4 白名单加三条 GET 是机械改动 | `backend/services/hedge_open_live_client.py:83-114` `ALLOWLIST` 表 + `:243-246` `_require_whitelisted`；既有测试 `backend/tests/test_hedge_open_live_client.py:259-275` | 成立 |
| §4「不得因手续费拉不到卡住终态」在传输层已有底 | `backend/services/hedge_open_live_client.py:249-279`：一次性传输、无重试、`timeout` 有界、超时/连接错返回 typed 响应而非抛出 | 成立（fail-closed 结构已具备，仍需在实现 dispatch 写死调用时序，见 O2） |
| §5.1 插列位置存在 | `frontend/index.html:7180-7181`「开单价差率」「累计资金费」相邻 | 成立 |
| §7 两包契约可机械冻结 | `backend/tests/test_hedge_api.py:64-94` `_POSITION_KEYS` 与真实 HTTP 响应键集相等；`backend/tests/test_frontend_field_binding.py:203-220` 前端引用 ⊆ `_POSITION_KEYS`、merge 层新字段必须同步 | 成立，**前端无法猜键**（持仓表侧） |

未核实项（证据边界）：设计 §1 引用的实盘库计数（`hedge_open_leg` 282 / `FILLED` 269 / 原始回包 417 / 11 个未平仓周期）为 Planner 自述，dispatch 明令禁止访问 live DB，本 Reviewer 未验证。这些数字只用于论证动机，不承载设计正确性，不构成阻塞。重开触发：若 Bookkeeper 或 Human 需要以这些数字作为验收基线，须由有授权的角色另行只读取数。

---

### 阻塞发现（必须本轮修，均为 in-range）

#### P1 — 历史仓位冻结的手续费合计会出现「部分和冒充完整」，且永久不可纠正 · in-range · 阻塞

**事实。** 设计 §5.1 给持仓表配了不全标记（建议键 `trading_fee_incomplete`），§5.2 给 `close_log` **没有任何等价字段**，只说「已关闭、没有腿手续费的历史行保持空 → 页面「—」」。而 D10 的原则是「缺任何构成折 U 的数 → 该格「—」，部分和标不全，不当 0」。两处口径不一致，`close_log` 侧缺少表达「不全」的载体。

**为什么必然发生，而不是假设。** 设计自己陈述：现存未平仓周期的腿手续费全空（§1、D8），且 D9 明确不回补历史。本功能上线后，这些周期一旦平仓，其 **open 腿手续费为 NULL、close 腿手续费为真值**——这是每一个存量周期关闭时的确定路径，不是小概率分支。按 §5.2 现有文字，`trading_fee_usdt` 会冻进一个**只含平仓腿**的合计数，页面上与「开+平完整成本」不可区分。

**为什么不能留作观察。** `backend/hedge_open_tasks/store.py:2443-2470` `insert_close_log` 是一次性 INSERT，无更新路径；`backend/hedge_open_tasks/service.py:2701-2724` `_finalize_close_task` 写失败被 `except: pass` 吞掉（周期已关是主事实）。一旦冻错，D9 又禁止回补，这个数字永远无法纠正。属账务含义（HIGH_RISK），须在拆包前拍死。

**修复要求（Planner 拍板，二选一并写进 10-design.md §5.2）。**
（a）`close_log` 增加与持仓表同义的不全标记列（如 `trading_fee_incomplete`），任一参与腿缺必需构成量即置真，前端按 §5.1 同一规则渲染「—」或「不全」；或
（b）明确「任一参与腿（开+平）缺手续费构成量 → `trading_fee_usdt` 整体写 NULL」，即用 NULL 承载「不全」，并在设计里写死「不得写入部分和」。
无论选哪个，须同时写死：`insert_close_log` 之前所有参与腿的手续费必须已落库，否则按不全处理（不得因写入时序造成的缺失被当成「本来就没有手续费」）。

#### P2 — 非 BNB 手续费的折 U 价格来源写成「该腿 avg_price」，对现货腿基本取不到值 · in-range · 阻塞

**事实。** 设计 §5.1 折 U 公式第三项写「Σ(非 USDT 的 `fee_other_qty` × 该腿 avg_price)」，D5 写「本币用该腿已有成交均价折 U」。但代码里 `hedge_open_leg.avg_price` 只装交易所回包的 `avgPrice` 原话：`backend/services/live_hedge_executor.py:135-175` `_post_figures` / `_query_figures` 对两腿都取 `body.get("avgPrice")`，而现货（`/api/v3/order`、`/papi/v1/margin/order`）回包不带 `avgPrice`，只带 `cummulativeQuoteQty`；`:109-132` `_avg_price_decimal` 还会把任何数值零判为未知 → `None`。

**实际影响。** 非 BNB 手续费最常见的形态正是**现货 BUY 以 base 币收取手续费**（BNB 抵扣关闭或 BNB 余额耗尽时）。按设计字面实现，这一路的 `avg_price` 恒为 NULL → 按 D10 整格「—」→ 该功能在它最该出数的场景上永远出不了数。这不是精度问题，是「设计的数永远不出现」。

**仓内已有权威推导。** `backend/hedge_open_tasks/store.py:2532-2562` `_cycle_leg_basis_locked` 是本仓既定的成交均价口径：`Σcumulative_quote_amt / Σcumulative_base_qty`，且只让已知 notional 参与分母（未知不拖价）。历史仓位的现货/合约均价列走的就是它。

**修复要求。** 在 10-design.md §5.1/D5 把「该腿 avg_price」改写为具体、与既有口径一致的表达：折 U 用该腿的 `cumulative_quote_amt / cumulative_base_qty`（两者任一缺失或为零 → 该腿不可定价 → 按 D10 整格「—」/不全），并说明 `avg_price` 列不作为此处价格来源及原因。

**同处建议（非阻塞，Planner 可一并写死）：** §4 的分组逻辑只区分「BNB / 其余一种 / 其余多种」，未要求校验「其余一种」是否就是该腿的 base 资产。若出现第三种资产，用该腿均价折算会静默给出错数。建议加一句硬条件：仅当 `fee_other_asset` ∈ {USDT, 该腿 base 资产} 时折算，否则按不全处理。这是零新结构的一次等值判断，正落在 D10 的口径内。

---

### 非阻塞发现与实现前必须冻结项

**O1 · 权重与调用次数评估不准（设计 §4）。** 设计写「权重大约 5/次，两腿各一次」。两处不准：
（i）三条端点权重不同源，不能用同一个 5 覆盖——`/papi/v1/margin/myTrades` 与 `/papi/v1/um/userTrades` 与现货 `/api/v3/myTrades` 的 IP 权重须按币安现行文档逐条落到实现 dispatch，本 Reviewer 离线无法取得权威现值，不臆断数字；
（ii）「两腿各一次」只对 immediate 单次任务成立。平滑任务每次成交都是一对新腿（`hedge_open_attempt` + 两条 `hedge_open_leg`），`target_n = 20` 即 40 条签名 GET。
影响面有现行记录支撑：`PROJECT_STATE.md` Operating Limits「最多约 5 个任务并发排空、每任务 4 req/s」与 Current Status 的 `[LIVE][2026-08-18] 借币 IP 418`（本机已吃过一次 418 封禁，交易所真正解封时间至今未知）。不阻塞设计成立，但实现 dispatch 必须写死：**每条腿至多一次、失败不重试、不进任何轮询循环**，并给出平滑任务的最坏调用量估算。

**O2 · 调用时序须写死在终态落库之后。** 设计 §4 的红线（拉不到不得卡住终态）方向正确，传输层也已有一次性 + 超时兜底（`hedge_open_live_client.py:249-279`）。但设计没写「在哪一步调用」。实现 dispatch 须写死：手续费 GET 发生在腿终态写入事务**提交之后**、独立于终态判定，任何异常只落日志不改腿状态。另须注意终态写入有**两个**站点，不能只接一个：`backend/hedge_open_tasks/store.py:1496-1520`（inline 派发回写）与 `backend/hedge_open_tasks/service.py:2803-2816`（drain 查询回写）。

**O3 · 新费用字段不在既有 money-zero tripwire 覆盖内。** `backend/tests/test_hedge_purity.py:222-227` 的 `_MONEY_NAMES = {price, avg_price, notional, quote, cumulative_quote_amt, cumulative_quote}`、`_MONEY_SUFFIXES = ("_notional","_avg_price","_quote")` 不匹配 `fee_bnb_price` / `trading_fee_usdt` / `fee_other_qty`。`PROJECT_STATE.md` 已把「`fee_amount` 在 money names 之外」记为该 tripwire 的既有逃逸口。把新字段名加进这两个既有集合是零新状态、零新契约、零新依赖的一次列表扩充，且正好守住 D10「未知不当 0」。建议列为后端包的验收项（不变量：新费用金额字段的缺值不得被 `_num(` / `_decimal_str(` / `or "0"` / `.get(…,"0")` 变成 0；误报形态：合法真零需带 `# money-zero-ok:` 标注）。

**O4 · BNB 冻价时点口径应在设计里明说。** D3 说「成本在付款当时已固定」，D4 实际实现的是「**写入时**取价」。drain 回写可能晚于成交若干轮，`price_map` 又有既有 5 分钟上限（`hedge_preflight_provider.py:54`）。对手续费量级而言这点偏差无实质影响，但口径应在文档里写成「写入时冻价，最大偏离受 price_map 上限约束」，并显式给出所采用的 max_age，避免日后被当成「成交瞬时价」对账。

**O5 · 前端两处机械同步点（前端包 dispatch 需点名）。**
（i）历史仓位空表 `colspan="16"`（`frontend/index.html:5719`）——当前正好 16 列，加一列必须同步改 17，否则空态排版错位；
（ii）`close_log` 侧没有 `_POSITION_KEYS` 这样的键契约：`backend/hedge_open_tasks/service.py:1064-1066` `get_close_logs` 直接返回 `list_close_logs()`（`SELECT *`），**列名即线上键名**。因此新列名必须在后端包里一次定死并写进前端 dispatch，不能靠前端推断。持仓表侧则有三重绑定测试兜底（`test_hedge_api.py:64-94` + `test_frontend_field_binding.py:203-220`），前端包应排在后端包之后，否则该绑定测试必红。

**O6 · dispatch Inputs 有三条路径在本仓不存在（packet 缺陷，非设计缺陷）。** `test -e` 实测：`backend/store.py`、`backend/services/hedge_open_live_service.py`、`backend/domain/positions.py` 三条 **MISSING**。实际对应物是 `backend/hedge_open_tasks/store.py`、`backend/hedge_open_tasks/service.py`、（持仓聚合在）`backend/hedge_open_tasks/store.py` 的 `aggregate_positions`（`:2615`）与 `backend/hedge_open_tasks/domain.py`。按 `AGENTS.md` §8，这属 pre-dispatch packet correction，**不计入 `rework_count`**；请 Bookkeeper 在下一份 dispatch 里更正，不要让实现者照失效路径找文件。

**O7 · 观察（不阻塞）。** 本 stage 的控制产物尚未提交：`reports/agent-runs/ACTIVE.json` 为已修改未提交，`20-plan-review.dispatch.md` 与 `status.json` 为未跟踪。计划评审不锚定 `base_sha..delivery_sha` 交付区间，故不影响本次结论；进入实现阶段前 Bookkeeper 需要一个已提交的基线。

---

### 逐项验收检查结果（对应 dispatch Acceptance Checks）

1. 已拍板口径 D1–D10 合规性 — **fail**：四列冻价结构、停写旧列不删列、不回补历史、不动净盈亏公式四项均成立且最小；但「持仓 open 腿 / 历史 open+close 腿」的边界在 `close_log` 侧不完备（P1），且 D10 的「不当 0」在 `close_log` 无载体。
2. 交易所数据语义与接口契约 — **contested**：端点选择与「`commission`/`commissionAsset` 是标量、按 `orderId` 分组求和」的语义，与本仓既有记录一致（`reports/agent-runs/2026-07-hedge-order-truth-v1/10-design.md:46-49` 早已把 `um/userTrades` 预声明为逐笔手续费来源）；被质疑的是「权重大约 5/次、两腿各一次」这一句（见 O1）。替代证据：`PROJECT_STATE.md` Operating Limits 与 `[LIVE][2026-08-18]` 418 记录；`backend/hedge_open_tasks/store.py:88-107`（腿即订单，平滑任务每次成交产生新腿）。本 Reviewer 离线无法取得币安现行权重权威值，故标 contested 而非 fail。
3. BNB 取价顺序与 fail-closed 保证 — **pass**：取价三档与既有 `_read_est_price` 形状一致且进程内源已接线可达（零新接线）；「拉取失败不得阻塞成交落库与 FILLED 终态」的红线方向正确，传输层已有一次性 + 超时兜底。附条件见 O2、O4。
4. 两包拆分可行性与契约冻结 — **fail**：持仓表侧键契约有三重绑定测试机械保障，前端确实无法猜键；但 `close_log` 侧的字段集在 P1 未决前不能冻结（是否新增不全标记会改变前端渲染契约），且 P2 未定前折 U 的输入项没写死。
5. 测试夹具与验收策略 — **contested**：六种离线夹具场景覆盖到位，方向正确；缺三项应补进验收——终态写入的**两个**站点都要有夹具（O2）、平滑任务多腿的调用次数上界断言（O1）、新费用字段纳入既有 money-zero tripwire（O3）。前端 `node frontend/self-check.js` 断言方向正确，须加历史表 `colspan` 同步项（O5）。
6. Handoff 与回执规范 — **pass**：产物为 dispatch 指定的唯一 create-only 路径，含 Bookkeeper 追加区标记；控制台回执按 `AGENTS.md` §7 review 版输出，结论明确为 REWORK。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/20-plan-review.handoff.md`
  2. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md`
  3. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/20-plan-review.dispatch.md`
- 执行：Bookkeeper 核验本交接件并把 REWORK 结论连同 P1、P2 交回 Planner（Grok 4.6 / xAI）修订 `10-design.md`；同时按 O6 更正下一份 dispatch 的 Inputs 路径，按 O1–O5 把各条冻结项写进后续实现 dispatch 的 Goal 与 Acceptance Checks。
- 关卡：`10-design.md` 修订后再走一次跨 provider 只读计划评审；取得 ACCEPT 且 Human 批准后，方可拆后端（`claude_glm`）/ 前端（`kimi`）实现包。
- 不能假设的事实：
  - 本次是**计划评审**，按 `AGENTS.md` §8 **不触碰 `rework_count`**；O6 的 packet 路径错误同样属 pre-dispatch packet correction，不计数。
  - 本 Reviewer **未访问 live DB**，设计 §1 的实盘计数未经核实，不得当作已验证基线。
  - 本 Reviewer **未运行任何测试**（只读计划评审，无交付代码可测）；文中所有代码引用均为静态阅读所得，行号对应工作树 HEAD `b09b199`，`store.py` / `service.py` 一经改动即会漂移。
  - `hedge_open_leg.avg_price` 不等于「成交均价」——现货腿一般为 NULL（见 P2）。
  - `close_log` 的列名即 API 线上键名（`SELECT *` 直出），无 `_POSITION_KEYS` 式守卫。
  - 本次评审未授权任何下单、重启、部署、merge、push，也未授权实盘验收。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

**一句话结论：计划不通过，要退回设计作者改两处，改完再评一次。这一轮不算返工次数，不消耗预算。**

**这个设计好在哪。** 大方向是对的，而且比预想的更省：手续费四列加在既有腿表上，用的是仓里已经跑熟的加列方式；BNB 取价那一步不用新接任何线，现成的账户快照价格表已经能被下单模块读到；三条新的只读查询加进白名单是机械活；「拉不到手续费绝不能卡住订单」这条红线方向正确，底层网络层本来就是一次性调用带超时，不会挂住。持仓表那边前端也猜不了字段名——仓里有三道测试互相咬住，后端不加、前端就用不了。

**两个必须改的地方。**

第一，历史仓位那一列会记错数，而且永远改不回来。现在库里那些还没平仓的仓位，手续费全是空的。功能上线后它们一旦平仓，系统会把「只有平仓那半边的手续费」冻成一个数写进历史，页面上看不出这是半截数——看着像完整成本，其实少了开仓那一半。设计里给持仓表留了「数据不全」的标记，却忘了给历史仓位留。历史那张表是一次性写死的，写完没有修改入口，设计本身又规定不回补历史，所以错一次就是永久错。要么加个「不全」标记，要么规定「缺一半就整个留空显示—」，两条选一条，得由设计作者拍板。

第二，非 BNB 手续费的折算价取错了地方。设计写「用该腿的成交均价」，但代码里那个「均价」字段现货腿基本是空的——币安现货回包根本不给这个字段。而「手续费用币本身扣」恰恰最常发生在现货买入那一腿。照现在写法实现，最该出数的场景永远显示「—」，功能等于白做。仓里另有一套现成的均价算法（成交额除以成交量，历史页现货均价列一直在用），改成引用它即可，是一句话的事。

**另外五条不拦路、但实现前要写死的。** 权重和调用次数估少了（平滑任务每成交一次就是两条新腿，20 次就是 40 次查询，不是「两腿各一次」；本机 8 月 18 号刚吃过一次币安 IP 封禁，解封时间至今未知，这块不能拍脑袋）；查手续费必须放在订单状态存盘之后，且订单终态有两个写入口，不能只接一个；仓里有个「钱不能凭空变成 0」的静态检查，新加的手续费字段名不在它的名单里，顺手加进去就能守住「缺数不当 0」；「冻价」实际是「写库那一刻的价」而不是「成交那一秒的价」，差几分钟，对手续费这个量级没实质影响，但口径要写明白；前端历史表有个写死的列数 16，加一列要同步改成 17。

**还有一条是派单包自己的笔误。** 派给我的输入清单里有三个文件路径在仓里不存在，我按实际结构找到了对应文件。请记账模型在下一份派单里更正，别让实现的人照着不存在的路径找。

**这一轮花了什么、没花什么。** 全程只读：没改一行代码、没动任何状态文件、没提交、没下单、没重启服务、没碰真实数据库。设计里引用的实盘条数（282 条腿、269 条成交等）我按派单禁令没去查库核对，那些数字只是动机说明，不影响结论。

```text
[TASK_RESULT v2]
任务 ID: 20-plan-review
执行结果: completed（完成）
结果摘要: 只读计划评审完成。设计主体成立（加列/取价/白名单/fail-closed 方向均经代码核实可行），但两处契约级缺陷须在拆包前修：P1 历史仓位冻结值会写入「只含平仓腿」的部分和且永久不可纠正；P2 非 BNB 折 U 取 leg.avg_price，现货腿该字段基本为 NULL，最常见场景永远出不了数。另有 5 项冻结条件与 1 项 dispatch 路径笔误。
产物: [reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/20-plan-review.handoff.md]
检查结果: [1 已拍板口径 D1–D10: fail（close_log 侧边界与 D10 载体缺失）, 2 交易所语义与接口契约: contested（端点与标量语义成立；权重/调用次数一句被质疑，离线无法取权威权重值）, 3 BNB 取价与 fail-closed: pass（取价三档可达且零新接线，红线方向正确）, 4 两包契约冻结: fail（close_log 字段集在 P1/P2 未决前不可冻结）, 5 测试夹具与验收: contested（六场景到位，缺两个终态站点/平滑调用上界/money-zero 名单三项）, 6 Handoff 与回执规范: pass]
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/20-plan-review.handoff.md
修复要求: reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/20-plan-review.handoff.md
阻塞项: [P1 close_log 缺不全载体，部分和冒充完整且不可回补（in-range）, P2 折 U 价格来源写为 leg.avg_price，现货腿恒 NULL（in-range）]
本地北京时间: 2026-08-19 23:15:32 CST
下一步模型: gemini-3.7-flash（Bookkeeper，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/20-plan-review.handoff.md、reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md、reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/20-plan-review.dispatch.md；执行：核验本交接件并把 REWORK 结论连同 P1/P2 交回 Planner（Grok 4.6 / xAI）修订 10-design.md，同时按 O6 更正下一份 dispatch 的 Inputs 路径；关卡：修订后再走一次跨 provider 只读计划评审，ACCEPT 且 Human 批准后方可拆后端/前端实现包（本轮为计划评审，不触碰 rework_count）
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- Bookkeeper: `gemini-3.7-flash`（provider `google`，窗口 `agy`）
- 核验时间（本地北京时间）：2026-08-19 23:22:15 CST
- 核对的 status revision：`1`（`phase=plan_review`、`current_task.state=dispatched`）
- source_sha256（`BOOKKEEPER_APPEND_ONLY` 标记前字节，UTF-8）：`d2f52ac8fecced155ce81b62e7bcb31805364d8b45745badd5482bd49c7eccc0`
- 源边界复核：源区块收口于 Human Brief 闭合代码块（`...[/TASK_RESULT]\n```\n\n`），标记独占一行。
- 核验结论：**通过核验，计划评审 REWORK（返工）结论采信**。
  1. **身份一致与只读合规**：`task_id` / `stage_id` / `base_sha` 与 `status.json` 逐字相同（`base_sha=b09b1993ae50f6af8b56615655cfb1966b8c60a6`）；`delivery_sha=none`（只读计划评审无交付 commit）；Reviewer 未修改代码、既有文档或状态文件，除本 handoff 外零写入。
  2. **create-only 成立**：本 handoff 在预检时为 ABSENT，本次任务新建。
  3. **结构合规**：Human Brief 内 `[TASK_RESULT v2]` 与控制台回执一致，闭合标记为末尾；评审结论明确为 `REWORK（返工）`；问题记录与修复要求明确指向本交接件。
  4. **阻塞项成立（in-range）**：
     - **P1**：`close_log` 缺失表达「不全」的载体，存量未平仓周期平仓时会导致「只有平仓腿手续费」的部分和冒充完整且永久无法纠正；
     - **P2**：非 BNB 折 U 价格源引用 `leg.avg_price`，而币安现货回包不带 `avgPrice` 导致其恒为 NULL，最常见场景无法出数。
  5. **计数规则**：本轮为只读计划评审，根据 `AGENTS.md` §8 与 `agents/roles.md`，**`rework_count` 保持 0，不消耗返工预算**。O6 所述 dispatch Inputs 路径笔误属 pre-dispatch packet correction，不计数。
- 可复现命令（核验脚本）：
  `python3 -c "import hashlib;raw=open('reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/20-plan-review.handoff.md','rb').read();m=b'<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->';print(hashlib.sha256(raw.split(m)[0]).hexdigest())"`
- 后续状态：`status.json` 推进至 `revision=2`，`checkpoint=plan-review-rework`，`current_task.state=verified`；将 P1、P2 及 O1–O6 移交 Planner（Grok 4.6 / xAI）修订 `10-design.md`。

## Errata (append-only)

（暂无。）

### 勘误 1 — Human 新事实导致评审发现降级与必改清单重组

- 日期: `2026-08-20 00:04:19 CST`
- 作者: Opus 5 / Anthropic（本 handoff 原作者，`20-plan-review` Reviewer）
- 触发: Human 于 `2026-08-20` 在评审后对话中给出两条新事实/新决定，本 Reviewer 据此复核并修订发现分级。
- **不改变的事实**：Source Report 与 Human Brief 一字未动（本勘误仅追加于 marker 之后；源区块 SHA-256 仍为 `d2f52ac8fecced155ce81b62e7bcb31805364d8b45745badd5482bd49c7eccc0`，可复算核对）。原 `评审结论: REWORK` **维持不变**，但成立理由发生变化，见下 R1。本轮仍为计划评审。

#### Human 提供的新事实

1. **（新需求）** Human 决定：上线时**回溯全部历史成交记录、补齐手续费字段**。这与设计 `10-design.md` D9「不回补历史成交」直接冲突。
2. **（口径澄清）** Human 确认：与 Planner 对话中拍板的折 U 价格口径，本来就是**手动算均价（成交额 ÷ 成交量）**，不是数据库 `avg_price` 列。

#### 发现分级修订

**P2 — 撤销阻塞，降为文本冻结项。** Human 已确认设计意图口径正确，本 Reviewer 原发现是对设计**文本**的读解，不是对口径的否定，予以撤回阻塞资格。保留的要求缩小为：`10-design.md` §5.1/D5 与后端实现 dispatch 必须把价格来源**写死为 `cumulative_quote_amt ÷ cumulative_base_qty`，并显式声明不得使用 `hedge_open_leg.avg_price` 列**。保留理由（非阻塞，仅防误实现）：该列真实存在且同名，合约腿有值、现货腿基本为 NULL（证据见 Source Report P2 的 `live_hedge_executor.py:135-175`），实现者照字面取用时，合约夹具仍会跑绿，缺陷要到现货腿上线后才暴露。

**P1 — 降级，依据更换，诉求缩小但不撤销。** 回补计划消除了原依据中「11 个存量周期在平仓时**必然**产生半截数」的必然性，该必然性是原发现的主要弹药，予以撤回。剩余诉求与回补是否执行无关，故不撤销：**只要存在任何一条腿的手续费未能取得，冻结进 `close_log` 的合计值就必须能表达「不全」**。新依据：回补不保证全覆盖（见下 R4 待确认事实），而回补后的部分缺失比回补前**更隐蔽**——多数腿已有值，页面上更难看出缺口，而 `insert_close_log` 仍是一次性写入、无更新路径（`store.py:2443-2470`）。载体成本为一个字段或一条「缺一即整体 NULL」的规则，与回补方案解耦。

#### 修订后的必改清单（供 Planner 重整理设计使用）

- **R1（新增，取代 P1 成为 `REWORK` 的首要理由）**：`10-design.md` D9「不回补历史成交」与 Human `2026-08-20` 决定直接矛盾，必须改写。改写须同时给出：回补范围（哪些腿、哪个时间起点）、回补的触发方式（一次性任务，不得挂在正常下单/平仓流程内）、控速与可中断续跑要求、以及回补失败或部分失败时的标记口径。**若不改 D9，实现者会照现行文档实现「不回补」，Human 的决定不会落地。**
- **R2（原 P1 降级后保留）**：`close_log` 冻结值需要「不全」载体（新增标记列，或明确「任一参与腿缺构成量 → 整体写 NULL」），二选一并写死。
- **R3（原 P2 降级后保留）**：折 U 价格来源按上文写死，并声明不得使用 `avg_price` 列。
- **R4（待确认事实，回补方案的前置条件）**：币安成交历史的**可回溯范围**必须在设计中给出结论——现货 `/api/v3/myTrades`、`/papi/v1/margin/myTrades`、`/papi/v1/um/userTrades` 三条按 `orderId` 查询时的时间窗、条数与历史保留限制。本 Reviewer 离线无权威值，不臆断。**该结论直接决定回补能否做到全覆盖，进而决定 R2 的载体是否必需**（若证实可全覆盖且回补成功，R2 仍需处理未来单笔取数失败的情形，但历史侧压力解除）。
- **R5（原 O1 量级升级）**：回补使签名 GET 的调用量从「每腿一次、平滑任务放大到数十次」升级到**历史全量数百次**（设计 §1 自述 `FILLED` 腿 269 条，未经本 Reviewer 核验）。现行记录 `PROJECT_STATE.md` Operating Limits 与 `[LIVE][2026-08-18] 借币 IP 418`（解封时间至今未知）使此项影响面显著上升。回补任务须独立控速，且不得与正常下单/平仓路径争用配额。
- 原 O2、O3、O4、O5、O6、O7 维持不变。

#### 计数与权限声明

本勘误**改变了检查结果的通过状态与阻塞项**，按 `agents/roles.md` Shared Rules 的勘误判据，它超出「不改变交付效果的编辑性更正」范围。本 Reviewer 不自行宣布其计数后果，提请 Bookkeeper 裁定，并说明理由：（a）本任务为计划评审，按 `AGENTS.md` §8「计划评审 verdict 返回 Planner，不触碰 `rework_count`」；（b）触发本次修订的是 **Human 需求细化与口径澄清**，§8 明确该情形不计入 `rework_count`。两条均指向不计数，但裁定权在 Bookkeeper，不在本 Reviewer。

本勘误未修改任何代码、测试、既有文档、`status.json`、`PROJECT_STATE.md`、`ACTIVE.json`；未提交、未 merge/push、未下单、未重启服务、未部署、未访问 live DB。

### 勘误 2 — 勘误 1 的时序定位与 `status.json` 不一致提示

- 日期: `2026-08-20 00:12:41 CST`
- 作者: Opus 5 / Anthropic（本 handoff 原作者，`20-plan-review` Reviewer）
- 原因: 勘误 1 追加时本 Reviewer 未先复读本文件，未察觉 Bookkeeper 已于 `2026-08-19 23:22:15 CST` 完成核验并将 `status.json` 推进至 `revision=2`。勘误 1 因此属 **post-verification erratum**，而非其行文所隐含的核验前追加。此处更正该时序定位。
- **不改变的事实**：勘误 1 的实质内容、修订后的必改清单（R1–R5）与分级判断均不变；Source Report、Human Brief、Bookkeeper Verification 三个区块一字未动，源区块 SHA-256 仍为 `d2f52ac8fecced155ce81b62e7bcb31805364d8b45745badd5482bd49c7eccc0`（追加只发生在文件末尾，可复算核对）。

#### 需要 Bookkeeper 处理的不一致

`status.json` `revision=2` 的 `blockers` 两条与勘误 1 修订后的结论已不一致，须由 Bookkeeper（唯一有权写 `status.json` 的角色）重新核验后更新：

| `status.json` `revision=2` 现有内容 | 勘误 1 修订后 |
|---|---|
| `P1: close_log 缺不全载体，部分和冒充完整且不可回补` | 降级：依据由「存量周期必然半截」换为「回补不保证全覆盖」，诉求缩小为 R2；不再以原形态阻塞 |
| `P2: 折 U 价格来源写为 leg.avg_price，现货腿恒 NULL` | **撤销阻塞**：Human 确认拍板口径本就是手动算均价；保留为非阻塞冻结项 R3 |

同时，Bookkeeper Verification 核验结论第 4 项「阻塞项成立（in-range）」所引依据已被 Human 新事实改变；该区块为 Bookkeeper 所有，本 Reviewer 不触碰，仅在此指出需复核。

`REWORK` 结论本身维持不变，但首要理由已变为 **R1：设计 D9「不回补历史成交」与 Human `2026-08-20` 回补决定直接矛盾**。计数后果的裁定权仍在 Bookkeeper，理由见勘误 1 末节（计划评审豁免 + Human 需求细化豁免，两条均指向不计数）。

本勘误未修改任何代码、测试、既有文档、`status.json`、`PROJECT_STATE.md`、`ACTIVE.json`；未提交、未 merge/push、未下单、未重启服务、未部署、未访问 live DB。

### Bookkeeper 勘误复核记录

- 日期: `2026-08-20 00:15:10 CST`
- Bookkeeper: `gemini-3.7-flash`（窗口 `agy`）
- 核验结论：采信勘误 1 与勘误 2。
  1. 本次修订由 Human 需求细化（拍板增加历史回补）与口径澄清触发，且本任务为计划评审，根据 `AGENTS.md` §8，**`rework_count` 保持为 0，不消耗返工预算**。
  2. `status.json` 更新至 `revision=3`，`checkpoint=plan-review-errata-verified`，`blockers` 修订为 R1 与 R2。
  3. 将修订后的必改清单 R1–R5 及交接件移交 Planner（Grok 4.6 / xAI）修订 `10-design.md`。

