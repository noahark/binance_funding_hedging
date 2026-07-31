# 16-fix-result：2026-07-31-hedge-task-inline-log-v1-fix-1（revision 13，已完成）

> 实现者 claude_glm，2026-07-31。base_sha `42de1aff`，修复基线 `b14f55ce`。
> **结论：Part A（R2-F1）+ Part B（均价落库）均完成，自测全过。**
>
> 历史：首轮（revision 12）实现者按 AC11/Stop 停下，回报 Part B 两处 packet 缺口（漏
> reconcile 写路径、未裁定 r6 守卫与 entries 流）。Bookkeeper 核实全部属实，dispatch 由
> 六处增补为九处并追加 r6 裁定（revision 13，commit `dee594f`）。本轮按修订后清单完成。
> 这是 packet 缺陷而非实现缺陷，**不额外递增 rework_count**（仍为 1）。

## Part A —— R2-F1「成交时间列在说谎」：✅ 已修复

- 列头「成交时间」→ **「尝试时间」**；`frontend/index.html` 与 `backend/` 全量搜索该字样 = 0。
- 去掉 `hedgeLogTimeCell` 的 `order_id` 门控：`attempt.ts` 有值即展示北京时间，无值才 `—`；
  四状态每行第 3 列均显示尝试时间（self-check 新断言，重点覆盖无 order_id 的行）。

## Part B —— 均价改用交易所返回值：✅ 已完成（九处加性改动）

**根因**（已核实）：执行器 `_avg_price_decimal`（`live_hedge_executor.py:93-97`）早已把交易所
`avgPrice` 解析出来，reconcile 路径 `classify_query_response`→`_query_figures`（`:137`）也取；
但 `hedge_open_leg` 表无 `avg_price` 列，`resolve_leg_from_query`（事后 GET 补数据的正路）签名
也无该参数——**取到了、没存**。合约腿均价正是靠这条 reconcile 路径补回来的（币安 2026-07-14
从 UM POST 移除 quote/avgPrice）。

**九处改动（全部加性，仅多记一列观测值）**：

| # | 文件:位置 | 改动 |
|---|---|---|
| 1 | `store.py:387` | migration：`leg_additions` 加 `("avg_price", "TEXT")`，沿用既有 ALTER guard，幂等 |
| 2 | `store.py:815` `_leg_final_fields` | 返回值加 `avg_price`（第 7 元），取自 `leg_outcome.get("avg_price")` 原样透传 |
| 3 | `store.py:1104-1142` `resolve_attempt` | 解包第 7 元 + `UPDATE … avg_price = ?` |
| 4 | `store.py:1561` `resolve_leg_from_query` | **【增补·最关键】** 签名加 `avg_price` kw + `UPDATE … avg_price = ?`（合约腿补均价的正路） |
| 5 | `service.py:1202` reconcile 调用点 | **【增补】** 传 `avg_price=verdict.avg_price`（verdict 即 LegDispatch，已带该字段） |
| 6 | `store.py:271` `_row_to_leg` | 加 `"avg_price": row["avg_price"]` |
| 7 | `service.py:205` `_resolve_avg_price` + `_leg_to_doc` | 三级优先级 ① 库存交易所值 → ② 本地 quote/base → ③ None（抽公共 helper） |
| 8 | `service.py:288/314` `_entry_spot_leg`/`_entry_perp_leg` | **【增补】** 复用同一 `_resolve_avg_price`——两流必然同优先级，同一笔钱两处同价 |
| 9 | 测试 | 三级优先级（两流）、reconcile 落库、migration 幂等、r6 守卫拆分 |

**均价优先级公共 helper**：#7/#8 三处投影共用 `_resolve_avg_price(leg, local_avg)`，从结构上
保证 attempts 与 entries 两流展示同一价格（dispatch AC：两流不一致比单流错误更严重）。

### r6 守卫拆分（按 Bookkeeper 裁定，非删除）

`test_null_notional_projects_null_on_attempts_and_entries` 的夹具 `_NullQuoteExecutor` 原带
`avg_price="50000"` + NULL quote。按裁定拆成两支：

- **保反造假内核**：`_NullQuoteExecutor` 改为 `avg_price=None`（NULL quote + 无 avg）→ 两流
  `avg_price` 均为 `None`（review-1 r6「不得用未知成交额做除法」原意，由该用例继续守卫）。
- **新语义**：新增 `_NullQuoteWithAvgExecutor`（NULL quote + 有交易所 avg）+ 用例
  `test_null_quote_with_exchange_avg_projects_on_both_streams` → 两流展示 `"50000"`、值相同；
  `cumulative_quote_amt is None` 断言**一律保留不动**（quote NULL 契约不变）。

> 这是 `avg_price` 字段的资金语义契约变更（「由 quote/base 算出」→「交易所值优先，否则算，
> 都没有则 null」），Bookkeeper 已向 Human 说明并记入 `status.json.blockers`。

## 硬约束遵守

1. **只存交易所原话，不推导**：未用 `filled_qty×avg_price` 反推 `cumulative_quote_amt`；
   `cumulative_quote_amt` 的 NULL 契约不变（`test_resolve_attempt_persists_null_quote…` 与
   `test_leg_final_fields_t1_null_contract` 均仍过）。
2. **未改 `_avg_price_decimal`**：`git diff backend/services/` 为空（AC8）。
3. **既有数据不倒退**：migration 后既有行 `avg_price` 为 NULL → 走 ② 本地计算（单测
   `test_avg_price_priority_three_levels_both_streams` 的 ② 分支 + migration 用例跨重开逐字不变）。
4. **不扩别处**：未碰状态机/调度/结算/计数器/暂停删除/worker/aggregate_positions/下单行为；
   legacy `hedge_open_fill` 表与 `aggregate_positions` 路径未动。

## 改动文件（全部在 Allowed Files 内）

```
 backend/hedge_open_tasks/service.py | 55 +++++-----  # _resolve_avg_price + _leg_to_doc/_entry_*_leg + reconcile 传参
 backend/hedge_open_tasks/store.py   | 29 +++++----    # migration/_leg_final_fields/resolve_attempt/resolve_leg_from_query/_row_to_leg
 backend/tests/test_hedge_service.py | 89 +++++++++++   # r6 拆分 + 三级优先级两流单测
 backend/tests/test_hedge_store.py   | 74 +++++++++++   # reconcile 落库 + migration 幂等
 frontend/index.html                 | 14 +++---        # Part A
 frontend/self-check.js              | 21 ++++++-        # Part A
 6 files changed, 238 insertions(+), 44 deletions(-)
```

后端改动 ~84 行（service 55 + store 29），略超 dispatch 原估「二三十行」——因 revision 13 由六
处扩为九处（增补 reconcile 写路径 + entries 两流 + 公共 helper），属同比例增长，非理解偏差。
`live_hedge_executor.py` 零改动（AC8）。

## 原始测试输出

```
$ python3 -m pytest backend/tests -q
........................................................................ [ 97%]
............................                                             [100%]
1108 passed in 57.95s        # 基线 1104 + 新增 4（r6 拆分净 +1、优先级、reconcile、migration）

$ node frontend/self-check.js | tail -1
全部自检通过
```

新增用例：`test_null_quote_with_exchange_avg_projects_on_both_streams`、
`test_avg_price_priority_three_levels_both_streams`、
`test_resolve_leg_from_query_persists_avg_price`、
`test_avg_price_migration_idempotent_and_preserves_existing_rows`；r6 守卫原位拆分。
**唯一改动的既有用例**是 r6 那条（按裁定拆分，dispatch 明确授权）；其余既有用例无一转红。

## 下一步

按 §8，本轮扩了 schema + 写路径，修复完成后**须重跑 review-1**（code-reviewer），再回 review-2
（reality-checker）。未合并、未推送、未启动评审终端。交 Bookkeeper（opus5）封存。
