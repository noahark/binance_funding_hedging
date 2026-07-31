# 14：review-2 verdict —— **REWORK**（codex / openai，2026-07-31 17:20:34 CST）

受审区间：`base_sha = 42de1aff364e7c979d2fbb5dc56f1dec65287cc7` ..
`delivery_sha = b14f55ce8c264635860bd5b54d61229b17bd9faa`。

`评审结论: REWORK（返工）`。阻塞项一条：**R2-F1**。

评审者独立性：`codex` / openai，未参与本 stage 任何设计、计划评审或实现，无需披露。

## R2-F1（in-range，阻塞）——「成交时间」列展示的不是成交时间

评审者判定：日志表的「成交时间」实际展示的是**尝试创建时间**，异步成交时会误导用户
判断资金何时成交；属本交付引入的范围内问题，需返工。

### Bookkeeper 核实：**成立，且比表述的更严重**

| 事实 | 证据 |
|---|---|
| 该列取的是 attempt 创建时间 | `attempt_to_doc` 的 `"ts": D.us_to_iso(attempt.get("created_at_us"))`（`service.py:270`）；前端 `hedgeLogTimeCell` 渲染 `attempt.ts` |
| `created_at_us` 是**下单前**预留那一刻 | attempt 行在 `prepare_attempt` 的预发送事务里写入（`store.py:754` 一带），早于两条腿 POST |
| **数据库里根本没有成交时间** | attempt 表只有 `created_at_us`（`store.py:79`），无 updated/settled 时间戳；leg 表只有 `dispatched_at_us`（发出）与 `last_query_at_us`（最后查询）（`store.py:97-98`）；交易所的 `transactTime` / `updateTime` **从未落库** |

因此「成交时间」这个列头在**数据层面就无法满足**——不是取错了字段，而是系统里没有这个
数据。实现者在 `09-delivery.md` 中已声明「`attempt` 投影里只有创建时间，没有成交时间，
故以创建时间为最接近代理」，并把它列为「Human 可推翻项」。但列头写「成交时间」本身是
一个**对用户的断言**，而该断言不成立：用户会据此判断"钱是这一刻出去的"。

这正落在本 stage 被定为 `HIGH_RISK` 的理由上——展示价格/数量/时间即展示账务信息。

**范围分类：`in-range`。** 该列由本次交付新增，列头文案是本次引入的断言。

### 前序评审为何漏判（记录，供后续参考）

- 实现者主动声明了口径，但用「最接近代理」的框架描述，未把「列名断言与数据不符」这一点
  提到台面。
- review-1（grok）判「时间门控 pass」——它审的是门控逻辑（至少一腿受理才显示）是否正确
  实现，未质疑列名与数据的语义匹配。
- **Bookkeeper 核验也漏判**：`10-` 的 AC 逐条核验只核了门控逻辑与倒序，未追问 `ts` 的
  语义。这是本次核验的一处实质遗漏，如实记录。

终审抓到它，正是 review-2「查实际效果而非代码」的价值所在。

## 第二条：合约均价缺失（发布级，不阻塞交付）

评审者：「现有功能能定位订单、数量和失败原因；但合约均价缺失时仍无法完整判断成本。
该均价问题早于本交付存在，且会阻塞发布前的人类风险决定。」`Goal4 发布就绪: fail`。

**范围分类：`pre-existing-release-critical`**（`AGENTS.md` §8）——早于 `base_sha` 存在、
不在本次交付文件内、涉及资金含义；**不机械阻塞交付，但阻塞合并/发布**，作为「合并前由
Human 决定」的具名事项上交。

已记入 `PROJECT_STATE.md` 的 `[OPEN][MONEY-ACCURACY]`。成因：币安 2026-07-14 从 UM 下单
返回移除 quote/avgPrice，靠事后 GET 补，补不到即为 `NULL`；且 `hedge_open_leg` 无
`avg_price` 列，交易所返回的权威 `avgPrice`（`live_hedge_executor.py:116` 已解析）被丢弃。

## ⚠️ 回执正文未随转交

`产物`、`问题记录`、`修复要求` 均写 `inline-full-text`，但 Human 转交的内容只有回执块与
两段摘要，**R2-F1 的完整发现正文与具体修复要求未收到**。

处置：R2-F1 的问题陈述在摘要中已足够明确、且 Bookkeeper 已独立核实到根因（数据层面
无成交时间），故据此推进修复，不再阻塞索要。修复方案由 Bookkeeper 依据核实结果定稿
（见 `15-fix.dispatch.md`），若 Human 补交正文中含不同的具体修复要求，将以追加勘误并入。

（流程记录：本 stage 五轮评审中有三轮出现「结论正文未随回执转交」。这是反复出现的转交
环节缺口，已在 `08-` 记录过一次，此处再记一次。）

## Bookkeeper 处置

- 封存本 verdict。`current_task.state` 保持 `reported`→ 退回修复，**不得写 `verified`**
  （`agents/roles.md` 拒收落盘规则）。
- **`rework_count` 由 0 递增为 1**（`AGENTS.md` §8：首次交付存在后，为修复缺陷的新实现
  任务递增一次，无论发现来自 review-1、review-2 还是 Bookkeeper 验证）。
- 修复路由：~~R2-F1 是窄的 review-2 发现，修复后直接回 review-2~~ —— **已被 Human 决定
  推翻，见下方勘误。**
- 合约均价（`pre-existing-release-critical`）作为**合并前的具名事项**上交 Human 决定。

## 勘误（2026-07-31，Human 决定后追加）

Human 决定把「均价改用交易所返回值」**并入本轮修复**，不另立 stage。

Bookkeeper 先前告知 Human「这不是小改动」，**该判断有误并已更正**：交易所的 `avgPrice`
执行器早已解析（`live_hedge_executor.py:93-97/116/137`）并已传到写库那一层（`:467/474`），
只是 `hedge_open_leg` 无该列而被丢弃。落库改动是六处加性修改，代码量确实很小——Human
的判断是对的。（中途一度以为该值存在 `hedge_open_fill` 表，查证后确认那条路径已废弃：
`insert_fill` 仅测试调用，实盘走 attempt/leg 表。）

代价不在代码量，而在流程与风险面，已向 Human 说明并获授权：

1. **碰 schema 与写路径**，超出本 stage 原有的「只动读路径」边界，该边界曾由计划评审
   批准、review-1 验证。Human 的决定构成 `AGENTS.md` §3 #1 所需的数据写入授权。
2. **修复路由改变**：按 §8「review-2 阶段的修复若扩文件、改契约或增风险，须重过
   review-1」，本轮修复完成后**必须重跑 review-1，然后才回 review-2**，不再适用窄发现
   的快路径。已记入 `status.json.blockers`。
3. `rework_count` 仍为 **1**：范围扩大不额外递增，仍是同一交付物的第一次修复轮。

修复 packet 见 `15-fix.dispatch.md`（Part A = R2-F1，Part B = 均价落库）。
