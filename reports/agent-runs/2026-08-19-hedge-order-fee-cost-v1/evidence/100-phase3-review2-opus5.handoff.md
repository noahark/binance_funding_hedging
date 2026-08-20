# Task Handoff: 100-phase3-review2-opus5

## Source Report (author-only; immutable after task end)

- task_id: `100-phase3-review2-opus5`
- role: `Reviewer`（阶段三 Review-2 终审，skill `agents/skills/reality-checker.md`）
- target model: Opus 5 / Anthropic（provider `anthropic`，窗口 `claude-review`）
- stage_id: `2026-08-19-hedge-order-fee-cost-v1`
- created_at: `2026-08-20 13:46:41 CST`
- base_sha: `06c00c07e0181c596292c2f163890456abed3d8d`
- delivery_sha: `3bc6acaec6e3bd2b837239d7a925007a29729db6`
- status_revision 核对: `23`（`phase=phase3_review2`、`checkpoint=phase3-review2-dispatched`、`current_task.state=dispatched`、`rework_count=0`）
- 评审结论: **ACCEPT（接受）** —— 但**发布前必须先执行下文 F1 的补救动作**，否则本次交付在当前生产数据上的实际效果为零。

### 隔离与只读范围

阶段三实现 Claude-GLM（`zhipu_glm`）、Review-1 Kimi（`moonshot`）、设计 Grok 4.6（`xai`）、Bookkeeper Gemini 3.7 Flash（`google`）、本 Reviewer Opus 5（`anthropic`）。Review-2 要求与交付区间内每一位实现与修复作者不同 provider——成立。

**披露**：本 Reviewer 是本 stage 三轮计划评审、阶段一 Review-1、阶段二 Review-2 的作者。本轮受审代码继续落实本 Reviewer 提出的多条要求，故下文对每条相关项均给出独立代码与运行证据。

只读执行。唯一写入是本文件（create-only；预检 ABSENT，本会话复核仍 ABSENT）。对生产库的全部访问均为 `file:…?mode=ro` 只读连接或 `sqlite3.Connection.backup()` 读取；聚合验证在 scratchpad 副本上进行。生产库 MD5 连测两次一致（`27725f2aa49c64733f14fc9421830a9f`），断点文件时间戳保持 `2026-08-20 12:39:46` 未被触碰。未 commit / merge / push、未下单、未重启服务、未部署、**未对币安发出任何请求**。

### 执行的验收命令（原始结果）

| 命令 | 结果 |
|---|---|
| `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_hedge_store.py backend/tests/test_hedge_api.py backend/tests/test_hedge_service.py backend/tests/test_backfill_leg_fees.py backend/tests/test_hedge_purity.py -q` | **232 passed**（24.20s），与 dispatch 预期数一致 |
| `node frontend/self-check.js` | **全部自检通过**，退出码 `0` |

前端在本交付区间**零改动**（`git diff --name-only` 无 `frontend/`）——阶段一冻结的三个键名与渲染逻辑直接对接真实聚合，无需任何适配。这是「契约先冻、后端先行」策略的直接兑现。

---

### 逐项核验（代码层面）

**1. 持仓真实聚合 — pass**

- `fee_rows` 仅在 `is_open` 分支收集（`store.py:2920`），且循环开头 `if _num(row["cumulative_base_qty"]) <= 0: continue`（`:2888`）已排除未成交腿——「只汇总 open 且有成交腿」两个条件都成立。
- 折 U 计算全部下沉到 `FF.usdt_fee_total`，均价由 `_leg_vwap` 严格取 `cumulative_quote_amt ÷ cumulative_base_qty`，docstring 显式写明「**严禁** `hedge_open_leg.avg_price`」，并对 `base <= 0 或 quote <= 0`（G5 哨兵）返回 `None`。D5 落实。
- `usdt_fee_total` 逐条枚举**六种**不全情形并一律 `return None, None, False`：四列全空（从未查询）、有量无价、有价无量（半截残留）、第三种资产、有资产名无量、本币不可定价。任一命中即整格 None + `incomplete=True`，**不输出半截金额也不输出半截 BNB 数量**——B1b 在真实聚合层再次落实。
- `_cycle_trading_fee_total` 与 `aggregate_positions` 对「有成交」的过滤分别用 SQL `CAST(...) > 0` 与 Python `_num(...) <= 0`，两者对 NULL 与 0 的行为一致，无口径分叉。

**2. 关仓全腿聚合 — pass**

`insert_close_log` 在调用方**未显式传**三个手续费键时，才用 `_cycle_trading_fee_total(cycle_id)` 现算 open + close 全部有成交腿；显式传参则原样落库（测试覆盖 round-trip）。全腿完整 → 写真实值 + `incomplete=0`；任一不全 → NULL/NULL/`1`。`close_log` 仍无 UPDATE 路径，回补不改写旧行（断点 1 保持）。

**3. 实时写入 commit-first — pass（核心红线成立）**

三处接线全部位于 store 写入成功之后：

| 站点 | 位置 | commit 保证 |
|---|---|---|
| 一（inline 主终态） | `service.py:3876` `resolve_attempt` 的 `try/except` 之 `else` 分支 | `resolve_attempt` 内部 `with self._lock, self._conn`，返回即已提交 |
| 二（drain 终态） | `service.py:2856` `resolve_leg_from_query` + `_persist_leg_raw` 之后，`if terminal and exchange_status == FILLED` | 同上 |
| 三（inline 暂停类终态） | `service.py:3875` 另一 `resolve_attempt` 调用点的 `else` 分支 | 同上 |

三处都挂在 `else`（即写入**未**抛异常）上——写失败时走既有 `_record_state_write_failure`，根本不会触发手续费拉取。顺序正确，无「事务内发网络请求」。

`_fetch_leg_fees_after_terminal` 的幂等与单次保证：跳过非 FILLED / 无 `order_id` / 四列任一非空的腿；`update_leg_fees` 的 `WHERE 四列 IS NULL` 再兜一层原子守卫。站点二传 `only_leg_id` 精确限定单腿。

**失败不改终态有直接测试**：`test_realtime_fee_hook_failure_never_touches_terminal_state` 注入 `Exception("transport down")` 后断言 `exchange_status == FILLED and terminal == 1`。另有 no-transport no-op、每腿单次+已写跳过、两腿 symbol 分别解析共五个用例。

**4. UM 零宽窗修正 — pass**

`um_query_window` 的 `end <= start` 分支由 `return None` 改为 `end = start + UM_FALLBACK_WINDOW_US`（向**未来**方向扩 10 分钟）。方向正确：市价单成交发生在 `dispatched_at_us` 之后毫秒级，必然落在 `[dispatched, dispatched+10min]` 内；窗内多余成交由本地 `orderId` 过滤兜底。倒置窗（`end < start`）同样走该回退。两个时间戳皆缺仍返回 `None`（不构造无根据的窗）。

修正的必要性由实盘数据直接证实：见 F1。

**5. 传输层与纯度 — pass**

`build_realtime_transport` 以 duck-typed `client` 装配，`fee_fetcher` 仍不 import 服务层（纯度契约保持）。`_realtime_fee_transport` 在 `_client` 缺失或 `credentials_present` 为假时返回 `None` → 整个钩子 no-op，**disabled/测试环境绝不为凑传输层发请求**。BNB 冻价复用预检 provider 的 `_read_est_price`（D4 链：进程内 `price_map` ≤300s → 公开现价一次 → None），未在本包重写第二套取价实现；provider 不可用时返回恒 `None` 的读取器（数量仍记、价格空、该腿标不全）。

---

### 实盘效果核验（本轮核心，Review-2 独有）

代码正确不等于效果达成。本 Reviewer 对生产库做只读取证，并在 scratchpad 副本上实跑 `aggregate_positions`：

```
币种              手续费折U      BNB数量   不全
1000CATUSDT           —            —     True
INJUSDT               —            —     True
JSTUSDT               —            —     True
SHELLUSDT             —            —     True
SNXUSDT               —            —     True
STOUSDT               —            —     True
THEUSDT               —            —     True
TSTUSDT               —            —     True
TUTUSDT               —            —     True
WLDUSDT               —            —     True
XVGUSDT               —            —     True

合计 11 行，其中出数字 0 行、显示「—」11 行
```

**当前生产数据下，本次交付的页面效果与上线前完全相同。** 根因见 F1。

#### 🔴 F1 · 回补断点残留使阶段三的零宽窗修复对存量 UM 腿不生效 · 非代码缺陷 · **发布前必须处理**

**事实链（全部实测）**

| 时间 | 事件 | 证据 |
|---|---|---|
| `11:57:40` | 阶段二交付 `831e255`，其 `um_query_window` 对零宽窗 `return None` | `git show -s --date=iso` |
| `12:17:52` | 阶段二双评审收口 `06c00c0` | 同上 |
| `12:39:46` | **live 回补执行**（Human 授权），用的是含零宽窗缺陷的阶段二代码 | `data/backfill-leg-fees-progress.json` 文件时间戳 |
| `13:30:49` | 阶段三交付 `3bc6aca`，修复零宽窗 | `git show -s --date=iso` |

回补结果（读断点文件与生产库，只读）：

- 写入成功 **137** 条；判定失败 **132** 条，游标推至 **286**
- 失败原因分布：`um_window_unbuildable` **131** 条、`no_trades` **1** 条
- **132 条失败腿的 `endpoint` 100% 为 `/papi/v1/um/order`**（按 id 反查生产库分组统计）

阶段二评审时本 Reviewer 已实测「缺 `dispatched_at_us` 的腿为 0 条」，故 `um_window_unbuildable` 的唯一可能来源就是 `end <= start` 零宽窗——而 inline `resolve_attempt` 用同一个 `now_us` 同时落 `dispatched_at_us` 与 `last_query_at_us`，合约腿的窗**必然**零宽。这正是阶段三所修的缺陷，实盘数据 131/132 的集中度是它的直接证据。

**为什么修复对它们不生效**：`BackfillEngine.run()` 以 `list_legs_missing_fees(after_id=cursor, exclude_ids=[…failed])` 选腿。当前断点为 `cursor=286` + `failed` 含这 131 个 id——**游标与失败集合双重阻挡**，用阶段三新代码重跑也会把它们全部跳过。设计 §4.3 的「已尝试失败的腿重跑不再打」在此正确地生效了，但它保护的是「注定取不到的腿」，而这 131 条是「被有缺陷的代码误判为取不到」。

**为什么导致 11 行全「—」**：每个未平仓周期都含 UM 腿；UM 腿四列全空 → `usdt_fee_total` 命中「四列全空 = 从未查询」→ 按 D11「任一参与腿缺构成量 → incomplete」→ 整行 None/None/True。现货与杠杆腿 136 条虽已成功写入（136 条 BNB 手续费均带冻价、1 条 USDT），但被同周期的 UM 腿拖成不全——**这是 D10/D11 的正确行为，不是新缺陷**。

**建议的补救动作（须 Human 授权，属动生产数据 + 打币安）**

1. 备份 `data/backfill-leg-fees-progress.json`，然后重置它（删除该文件，或把 `cursor` 置 0、`failed` 清空）。该文件在 `.gitignore` 内，是纯本地断点。
2. 先小批量验证修复是否真的生效：`python3 scripts/backfill-leg-fees.py --limit 5`，确认返回的 UM 腿不再是 `um_window_unbuildable`。
3. 确认后全量重跑。**重跑对已写入的 137 条腿是安全的**——`update_leg_fees` 的 `WHERE 四列 IS NULL` 与候选查询的「四列全空」条件会双重排除它们，不会改写历史真值。
4. 预计新增签名 GET 约 **132** 次，按 1 次/秒节流约 **2.2 分钟**。
5. 重跑后再看页面：能出数字的行数取决于币安 UM `userTrades` 对 9–14 天前成交的可回溯性（仍是未确认前提，见 F3）。

**分类说明**：零宽窗缺陷由阶段二交付 `831e255` 引入，早于本轮 `base_sha`；阶段三**已在受审区间内修复它**。故本条不是阶段三的 in-range 缺陷，也不构成对阶段三的 `REWORK`——需要的是一次运维动作，不是代码返工。但它决定本次交付是否产生任何实际效果，因此列为**发布前必须处理的具名事项**上交 Human 决定。

#### 🟡 F2 · 手续费钩子的日志写失败无兜底，可能把异常带回订单结算路径 · in-range · 不阻塞

`_fetch_leg_fees_after_terminal` 的每腿处理有 `try/except Exception`，但 **`except` 分支内部调用 `self._store.append_log(...)` 本身没有保护**；同时三个调用点均为裸调用（站点一/三是 `try/except/else` 的 `else` 分支，站点二在 drain 的 `for` 循环内），**外层没有 try**。

若 `append_log` 抛出（`store.py:2603-2612` 为 `with self._lock, self._conn` + INSERT，在磁盘满、SQLite 锁超时或库损坏时会抛），异常将穿过 `_fetch_leg_fees_after_terminal` 传播到调用点：站点一/三会传给结算调用者；站点二会中断 drain 的 `for` 循环，使**同轮其余腿的 reconcile 被跳过**（它们可能仍处于非终态）。

**为什么不阻塞**：核心承诺「不影响成交终态」由 commit-first 结构性保证，异常发生时终态早已提交，**成交数据不会丢，也不会产生资金错误或敞口**；后果限于 worker 异常与本轮 drain 中断。触发需 DB 层故障，本 Reviewer 无该故障的实例证据，按 `AGENTS.md` §8 新假设场景证据门不足以据此阻塞。仓内存在 `_record_state_write_failure` 这一既有机制，说明「store 写会失败」是项目已承认的前提，故该路径值得收紧。

**建议**：在三个调用点或 `_fetch_leg_fees_after_terminal` 方法体最外层加一层 `try/except Exception: pass`（配合既有失败记录机制），使「不影响订单链路」从「几乎不会」变为「结构上不可能」。现有测试 `test_realtime_fee_hook_failure_never_touches_terminal_state` 覆盖的是 transport 抛异常，未覆盖 `append_log` 抛异常，建议补一条同形态用例。

#### 🟡 F3 · 「币安 UM `userTrades` 可回溯多久」仍未确认 · 沿用自阶段二 · 不阻塞

三轮计划评审与阶段二 Review-2 均把它列为待实测前提，至今未验证。F1 的重跑正是顺带验证它的最佳时机：若小批量重跑后 UM 腿仍大面积失败且原因不再是 `um_window_unbuildable` 而是 `no_trades`，即说明历史回溯受限；反之则说明可回溯。**建议把这次重跑的失败原因分布记入 `PROJECT_STATE.md`**，终结这个悬了四轮的未知项。

#### 💭 F4 · 实时路径无节流 · 设计既定 · 观察

回补路径有 1 次/秒节流，实时路径没有（站点一一次调用最多发 2 次 GET，两条腿各一次）。设计 §4.1 已核算「平滑 `target_n=20` 最坏 40 次」并有断言把守，属既定接受范围。但叠加 `PROJECT_STATE.md` Operating Limits（每任务约 4 req/s、建议并发不超过约 5 个任务）与 2026-08-18 的借币 IP 418 记录，建议在首次实盘开单验证时打开任务日志页观察 `leg_fee_fetch` 事件，确认未出现 429/418。

---

### 结论与发布就绪判断

阶段三代码**完整实现了 `10-design` D5/D7/D10/D11 与 §4.1/§5.1/§5.2 的全部口径**：持仓与关仓两处聚合的不全语义严密（六种不全情形逐条枚举、金额与 BNB 数量同命运）、实时写入三处接线全部 commit-first 且失败不改终态（有直接测试）、UM 零宽窗修正方向正确、传输层保持纯度契约且无凭证时 no-op。232 项测试与前端自检全绿，前端零改动即对接成功。**代码层面无阻塞缺陷。**

但按 reality-checker 的「实际交付效果」与「发布就绪」标准，必须明确：**在执行 F1 的补救动作之前，本次交付在当前生产数据上的页面效果为零（11 行全「—」）**。这不是代码缺陷，而是一次用有缺陷的旧代码执行的回补留下的断点残留。本 Reviewer 给出 `ACCEPT` 而非 `REWORK`，是因为需要的是运维动作而非代码返工——把它退回实现者不会改变任何代码，且动生产数据仍须 Human 授权。

**ACCEPT 的边界**：接受的是阶段三代码。不构成合并、部署、实盘开单或重跑回补的授权。清理断点并重跑回补属动生产数据 + 打币安，须 Human 单独授权（`AGENTS.md` §3）。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/100-phase3-review2-opus5.handoff.md`
  2. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/90-phase3-review1-kimi.handoff.md`
  3. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/80-phase3-aggregate-realtime-glm.handoff.md`
  4. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md`
- 执行：Bookkeeper 核验本交接件并记录阶段三 Review-2 `ACCEPT`（双评审闭环）；把 **F1 作为发布前必办事项**向 Human 交底（含四步补救动作与安全性说明），F2 列为收口前的健壮性修复候选，F3 列为重跑时顺带验证并回写 `PROJECT_STATE.md` 的项，F4 列为首次实盘开单时的观察项。
- 关卡：Human 授权清理断点并重跑回补 → 小批量 5 条验证零宽窗修复生效 → 全量重跑 → 页面复核。此后再决定合并与实盘开单验证。
- 不能假设的事实：
  - 本轮 `ACCEPT` **不构成**合并、部署、实盘开单或重跑回补的授权。
  - **不要因为页面仍是 11 行「—」而判定阶段三失败**——代码已验证正确，原因是 F1 的断点残留，补救动作明确。
  - 重跑回补**不会改写**已成功写入的 137 条腿（`update_leg_fees` 的 `WHERE 四列 IS NULL` 与候选查询双重排除），这一点已通过代码核验，可安全执行。
  - 「币安 UM `userTrades` 可回溯多久」仍未确认（F3）；重跑后仍可能有一部分 UM 腿失败，届时失败原因会从 `um_window_unbuildable` 变为 `no_trades`，两者含义不同，不要混为一谈。
  - 本 Reviewer **未对币安发出任何请求**、未写生产库（MD5 连测两次一致 `27725f2aa49c64733f14fc9421830a9f`）、未触碰断点文件（时间戳仍为 `12:39:46`）；聚合验证在 scratchpad 副本上进行。
  - 工作树中 `80-phase3-aggregate-realtime-glm.handoff.md` 与 `status.json` 的未提交改动**非本 Reviewer 所为**。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

**一句话结论：代码是对的，测试全绿，但你现在打开页面看到的还是 11 行横杠 —— 不是代码没做好，是中午那次回补留下的记录把修复挡住了。要跑一个补救动作才能看到数字。**

**先说代码。** 这一步做完了三件事：持仓表真的去算手续费了、平仓时把开+平全部腿的手续费冻进历史记录、下单成交后自动去币安拉手续费写库。最关键的安全线守住了 —— 拉手续费这个动作**一定发生在订单状态存盘之后**，三个接入点我逐个确认过位置，而且有一条测试专门注入故障来验证「拉取失败时订单仍然是已成交、已终态」。指定的两条命令都过了：232 项测试全绿、前端自检全过。前端这次**一行都没改** —— 阶段一冻好的字段名直接对上了真实数据，这是当初坚持「先冻契约再拆包」的回报。

**现在说问题。** 我在只读副本上把真实数据跑了一遍聚合，结果是：**11 行全是横杠，一行数字都没有**。

查下来是这么回事：

- 中午 **11:57** 交付了阶段二的回补脚本，那版代码里合约腿的时间窗有个缺陷；
- 你在 **12:39** 授权跑了回补；
- 结果 **137 条成功、132 条失败**，而失败的 **132 条全是合约腿**，原因清一色是「时间窗构造不出来」；
- 下午 **13:30** 交付的阶段三**正好修了这个缺陷**。

也就是说，回补是用有毛病的那版代码跑的，把 132 条合约腿全判成了「查不到」。而脚本有个保护机制：**已经失败过的腿，重跑不再打**（这本来是好设计，省得对着注定查不到的老单一遍遍发请求）。所以现在即使代码修好了，重跑也会把这 132 条直接跳过。

而每个持仓周期都有合约腿。现货那边 136 条其实都成功了（BNB 手续费，价格也冻好了），但只要同一个周期里有一条腿缺数，整行就按规矩显示横杠 —— **这是我们前三轮反复要求的「宁可不显示也不能显示半截数」，它正在正确工作**。

**补救动作（要你授权，因为要动数据库和发请求）：**

1. 把 `data/backfill-leg-fees-progress.json` 这个断点文件备份一下然后删掉（它是纯本地文件，不在版本库里）；
2. 先小批量试 5 条：`python3 scripts/backfill-leg-fees.py --limit 5`，看合约腿是不是不再报「时间窗构造不出来」；
3. 确认有效再全量重跑，大约 **132 次请求、2 分多钟**；
4. **重跑绝对不会改坏已经补好的那 137 条** —— 脚本有两道「只写空列」的守卫，我核过代码。

重跑之后能出几行数字，还取决于一个到现在都没验证过的事：币安的合约成交记录到底能往回查多久。这些单子最老的是 14 天前的。**这次重跑正好能把这个问题一次问清楚** —— 如果还失败，失败原因会从「时间窗构造不出来」变成「查不到成交」，两者含义完全不同。建议把结果记下来，这个悬了四轮的未知项该结掉了。

**另外一个小隐患，不拦路。** 拉手续费失败时会写一条任务日志，但**写日志这个动作本身如果失败了（磁盘满、数据库锁住），没人接着**，异常会跑回订单结算流程里。好消息是订单数据那时已经存好了，不会丢钱也不会留敞口，最坏是 worker 报个错。修法是在外面再包一层保护，几行的事，建议收口前顺手做掉。

**边界：** 这轮通过的是代码，不等于可以合并、上线、开单。清断点重跑要你单独点头。**看到页面还是横杠时，别以为白干了** —— 代码是好的，差那一个动作。

```text
[TASK_RESULT v2]
任务 ID: 100-phase3-review2-opus5
执行结果: completed（完成）
结果摘要: 阶段三代码通过终审：三处实时写入均 commit-first、失败不改终态有直接测试、聚合六种不全情形严密、UM 零宽窗修正方向正确、前端零改动即对接。232 passed + self-check 全绿。但实测副本聚合显示 11 行全「—」——根因是 12:39 用含缺陷的阶段二代码跑的回补把 132 条合约腿全判失败并写入断点，阶段三修复被断点跳过。需清断点重跑（F1）。
产物: [reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/100-phase3-review2-opus5.handoff.md]
检查结果: [1 持仓真实聚合: pass（只汇总 open 且有成交腿、均价严格 quote/base 禁用 avg_price、六种不全情形逐条 None/None/True）, 2 关仓全腿聚合: pass（未传参时现算 open+close 全腿、全完整写 0、任一不全写 1、显式传参原样落库、close_log 仍无 UPDATE 路径）, 3 实时写入 commit-first: pass（三处均挂在 store 写成功的 else 分支、每腿至多 1 次、update_leg_fees 原子幂等再兜一层、注入异常测试断言终态不变）, 4 UM 零宽窗修正: pass（向未来扩 10 分钟方向正确、两戳皆缺仍返回 None）, 5 测试与自检: pass（232 passed、self-check 全绿、前端零改动）, 6 实盘效果: F1 记为发布前必办（副本实跑 11 行全「—」，132 条失败腿 100% 为 UM 路由，131 条 um_window_unbuildable，与零宽窗根因一致）, 7 健壮性: F2 记为 in-range 非阻塞（except 内 append_log 无兜底且调用点无外层 try，commit-first 已保证不丢成交数据）]
评审结论: ACCEPT（接受）
问题记录: reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/100-phase3-review2-opus5.handoff.md
修复要求: none（代码无需返工；F1 为运维动作、F2 为建议性健壮性收紧）
阻塞项: [none（但发布前必须先执行 F1 的清断点重跑，否则本次交付实际效果为零）]
本地北京时间: 2026-08-20 13:46:41 CST
下一步模型: gemini-3.7-flash（Bookkeeper，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/100-phase3-review2-opus5.handoff.md、reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/90-phase3-review1-kimi.handoff.md、reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/80-phase3-aggregate-realtime-glm.handoff.md；执行：核验并记录阶段三 Review-2 ACCEPT（双评审闭环），把 F1 四步补救动作作为发布前必办向 Human 交底，F2 列为收口前健壮性修复候选，F3 列为重跑时顺带验证并回写 PROJECT_STATE.md；关卡：Human 授权清断点→小批量 5 条验证→全量重跑→页面复核，此后再议合并与实盘开单；本轮 ACCEPT 不构成合并/部署/重跑授权
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- **verification_time**: 2026-08-20 13:50:35 CST
- **source_sha256**: `f474c478014812213e6126f2fe231164578523a8f375bd3e53332cbf0f5a4a37`
- **status_revision**: 23 -> 24
- **verdict**: `ACCEPT`
- **rework_count**: 0
- **isolation_check**: pass（implementer=`zhipu_glm`, review1=`moonshot`, review2=`anthropic`, strict 3-way provider isolation satisfied）
- **findings_summary**:
  - `F1` (发布前必办运维动作): 生产库重跑前需清空 `data/backfill-leg-fees-progress.json` 断点以释放被阶段二旧代码误判跳过的 131 条 UM 腿
  - `F2` (建议性非阻塞健壮性改进): `_fetch_leg_fees_after_terminal` 内 `append_log` 异常兜底防护
  - `F3` (实测取证): 重跑时记录币安 UM userTrades 历史窗口实际可回溯性至 `PROJECT_STATE.md`
  - `F4` (观察项): 首次实盘开单观察任务日志中的 `leg_fee_fetch` 事件
- **verification_status**: `verified`

## Errata (append-only)

（暂无。）
