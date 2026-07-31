# 19：review-1（重跑）verdict —— **ACCEPT**（grok / xai，2026-07-31 18:40:55 CST）

受审区间：`42de1aff364e7c979d2fbb5dc56f1dec65287cc7 .. d85a2d3c1953d635dee59c8a1ccfccdbc40ba73b`
（含首轮交付 + 本轮修复）。评审者声明未读工作树、未移动 `HEAD`，并核对了 status
revision 14 一致。

`评审结论: ACCEPT（接受）`，`阻塞项: none`，**无 in-range 发现**。`rework_count` 保持 1。

隔离披露（评审者原样给出）：review-1 重跑与本 stage 计划评审 r1-r3、首轮 review-1 同为
grok / xai；跨 provider 相对实现/修复作者成立；本会话未参与实现或修复。

## 六项判断（全部成立）

| Goal | 结论 | 要点 |
|---|---|---|
| 1 `avg_price` 语义变更 | 安全 | 三级优先级正确；历史行走②与修复前一致；**无串腿**——库存值只来自本腿，spot/perp 分别解包（`store.py:1113-1118`），无对侧腿交叉 |
| 2 写路径 | 安全 | migration 幂等（沿用 ALTER guard）；两处写入均正确；**确认没有第三条写路径**——`UPDATE hedge_open_leg` 仅三处，`mark_leg_querying`（`store.py:1193`）只动状态与时间戳，本就不应写均价；7 元组解包已全部同步 |
| 3 r6 拆分裁定 | **独立确认站得住** | 「r6 原意是不得用未知成交额做除法，防凭空造价，不是『有 quote 才允许有均价』；交易所 avgPrice 不是除出来的」——不认为原意被曲解 |
| 4 既有资金契约 | 完好 | quote 的 NULL 契约未动（即使 avg 在场也不推导，r4 注释仍在）；r4 旧推导未恢复；`backend/services/` 零 diff |
| 5 Part A | 正确无遗留 | 列头与 `hedgeLogTimeCell` 均已改；产品代码无残留；未新增成交时间戳 |
| 6 边界 | 未超出 | 6 文件均在 Allowed Files；未碰状态机/调度/结算/计数器/暂停删除/worker/`aggregate_positions`/下单/凭据/live 闸门 |

评审者另指出的结构亮点：三处投影抽公共 helper，比「三处手写同一优先级」更强，两流同价
由调用同一函数保证。

## 两条非阻塞观察

### O1 —— `resolve_leg_from_query` 对 `avg_price` / `quote_amt` 无 `COALESCE`

评审者：后续 query 若带回 `None` 会覆盖先前值；与既有 quote 写入模式一致，**非本轮新增
缺陷**；live 成交路径通常一次补齐后即 terminal。定性为残余、不阻塞。

**Bookkeeper 独立核实 —— 结论同为不阻塞，但有一处定性需精确化：**

- 触发需要两步：① 某次 query 拿到 `avg` 但 `quote` 为 `None`（否则合约腿达终态、不再
  查——`leg_is_terminal_fill` 要求 perp 的 quote 已知）；② 下一次 query 返回**确定**
  verdict 但 `avg` 为 `None`（inconclusive 时 `_reconcile_own_legs` 是 `continue`，
  根本不写库）。
- 条件 ① 正是「交易所返回均价却不返回成交额」这一组合。本 stage 早前已查证：币安
  2026-07-14 移除的是 **UM 的 POST RESULT** 字段，**订单详情 GET 仍同时返回二者**
  （`live_hedge_executor.py:67-74` 的具名规则）。故 ① **在当前交易所行为下不可达**。
- **精确化**：`avg_price` 这一列的写入是**本轮新增**的，它沿用了既有 `quote_amt` 的
  无 `COALESCE` 模式。因此更准确的表述是「本轮引入、沿用既有模式、当前不可达」，
  而非「非本轮引入」。这个差别不改变处置（不阻塞），但记录在案以免日后误判来源。
- 若币安将来也从订单详情 GET 移除成交额，① 即变为可达，届时应改为
  `COALESCE(?, avg_price)` 或等价的「不用未知覆盖已知」策略。**已作为观察项移交 review-2。**

### O2 —— `PROJECT_STATE.md` 的 `[OPEN][MONEY-ACCURACY]` 描述已过时

评审者指出该条目仍写「无 `avg_price` 列、权威值被丢」，而本交付已修。

**已处置**：Bookkeeper 已将其改写为 `[OPEN][RESIDUAL]`，记录「列与两条写路径已落地，
残余部分在上游——合约腿的数据只能靠订单详情 GET 补回，未补到时该列合法未知、渲染为
破折号而非伪造的零」。

## Bookkeeper 核验

**已封存。** 回执携带完整正文、逐项依据与发现清单（本轮无 in-range 项），符合
`AGENTS.md` §7。

抽查评审者的关键事实判断：

- 「没有第三条写路径」→ 复核 `UPDATE hedge_open_leg` 的出现位置，确为三处，
  `mark_leg_querying` 只动 dispatch/order_id/时间戳，属实。
- 「无串腿」→ 复核 `store.py:1113-1118` 的 spot/perp 分别解包与
  `service.py:1226` 的单腿传参，属实。

`rework_count` 保持 **1**。`ACCEPT` 不等于合并授权（`AGENTS.md` §9）。

## 下一步

review-2（`codex` / openai，`reality-checker`）复审，锚定同一区间
`42de1aff..d85a2d3c`。dispatch 见 `20-review-2-rerun.dispatch.md`。
