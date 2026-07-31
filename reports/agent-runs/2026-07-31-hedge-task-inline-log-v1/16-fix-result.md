# 16-fix-result：2026-07-31-hedge-task-inline-log-v1-fix-1

> 实现者 claude_glm，2026-07-31。base_sha `42de1aff`，修复基线 delivery_sha `b14f55ce`。
> **结论：Part A（R2-F1）已完成并自测通过；Part B（均价落库）阻塞，需 Bookkeeper/Human 裁定。**

## Part A —— R2-F1「成交时间列在说谎」：✅ 已修复

按 dispatch 钉死的三步：
1. 列头「成交时间」→ **「尝试时间」**；`frontend/index.html` 与 `backend/` 全量搜索「成交时间」
   字样 = 0（仅 `self-check.js` 的「断言其不存在」测试合法命中）。
2. **去掉 `hedgeLogTimeCell` 的 `order_id` 门控**：改为 `attempt.ts` 有值即展示北京时间
   （`hedgeLogEntryTimeText`），无值才 `—`。四种状态每一行都显示该次尝试时间。
3. 同步更新 `index.html` 注释与 `self-check.js` 断言（新增「每行第 3 列为北京时间」断言，
   重点覆盖无 `order_id` 的进行中/确认失败行——旧门控会把它们抹成 `—`）。

**改动**：`frontend/index.html`（表头、`hedgeLogTimeCell`、注释）、`frontend/self-check.js`
（注释 + Part A 断言）。`git diff --stat`：前端共 +25/−9，未碰后端。

**验证**：`node frontend/self-check.js` → 全部自检通过（含两个内嵌日志用例与新增 Part A 断言）。

## Part B —— 均价改用交易所返回值：⛔ 阻塞（两个 dispatch 未覆盖的缺口）

按 dispatch AC11（「既有用例转红→停下回报」）与 Stop（「超出边界即为 blocker，停下回报」），
Part B 我**未动后端**。核实到两处必须由 Bookkeeper/Human 裁定的问题：

### 缺口 1：改动 #5 会破坏 review-1 r6 的资金回归守卫

- **根因**：`_leg_to_doc` 均价优先级改为 ① 库存 `avg_price` → ② 本地 `quote/base` → ③ `None`
  后，`test_null_notional_projects_null_on_attempts_and_entries`（`test_hedge_service.py:474`，
  review-1 r6 P1 回归守卫）的 attempts 路径断言会转红。
- **机制**：该用例的 `_NullQuoteExecutor`（:435）刻意构造「`cumulative_quote` 缺失但
  `avg_price="50000"`」的腿。Part B 落库后，`_leg_final_fields` 取 `leg_outcome["avg_price"]`
  存 `"50000"`，`_leg_to_doc` 走 ① → 展示 `"50000"`；而 r6 断言 `leg["avg_price"] is None`
  （:488）→ **失败**。
- **为何不能自行改**：r6 是防「均价造假」的资金回归守卫（NULL notional → NULL avg）。Part B
  的语义是「展示交易所**原话** avgPrice（非推导）」——与 r6 的反造假精神不冲突，但与该用例
  **字面断言**冲突。更新该守卫属资金含义契约变更，dispatch AC11 明令「停下回报」。
- **附带的 attempts/entries 不一致**：dispatch 只改 `_leg_to_doc`（attempts 流，内嵌表消费），
  不改 `_entry_spot_leg`/`_entry_perp_leg`（entries 流，日志页）。同一腿在两流会展示不同均价
  （attempts 显示库存 avg、entries 显示本地算）——review 易抓。
- **建议**（供 Bookkeeper 裁定）：
  - a) 把 r6 用例拆成「NULL quote + NULL avg → None」（保 r6 反造假核心）与「NULL quote +
    在场 avg → 显示 avg」（Part B 新行为）两条；**且**一并改 `_entry_*_leg` 使两流一致；或
  - b) 收窄 #5：仅当本地算不可得（quote NULL）**且**库存 avg 在场才用库存值，否则维持本地算
    （这样 r6 的 `avg_price="50000"`+NULL quote 会显示 "50000"，仍需改 r6 断言，但 entries
    流可不动）。两条都改 r6，需 Human 认可。

### 缺口 2：dispatch 漏点 reconcile 写入路径 `resolve_leg_from_query`

- **根因**：`_leg_final_fields` 仅 `resolve_attempt`（同步派发解析，:1105/1108）调用；但腿的另一
  条落库路径 `resolve_leg_from_query`（`store.py:1561`，事后 GET 补成交的正路）也
  `UPDATE hedge_open_leg` 写 `cumulative_quote_amt`/`cumulative_base_qty`，**无 `avg_price`**，
  且其签名无 `avg_price` 参数、调用方（reconcile worker）也未传。
- **后果**：dispatch 改动 #3 只点了 `resolve_attempt`。一条经 reconcile 解析的 perp 腿（正是
  「quote NULL、靠 GET 补 avg」的场景）**不会落库 avg_price** → Part B 对其所述 bug 不生效，
  且与 resolve_attempt 路径行为不一致。
- **为何不能自行补**：补这处需改 `resolve_leg_from_query` 签名 + UPDATE + reconcile 调用方传参，
  属写路径**范围扩大**，超出 dispatch 的六处钉死改动，Stop 明令「停下回报」。

### Part B 我已核实、不重复调查的事实（与 dispatch 一致）

- `_avg_price_decimal`（`live_hedge_executor.py:93-97`）已把 `"0"`/缺失映射为 `None`——**不得改**
  （硬约束 #2），落库的是 `None`。
- record transport 的 `_simulate_leg` 对 FILLED 腿产出 `avg_price=str(price)`，且
  `cumulative_quote = filled_qty*price`，故本地算 `quote/base == price == 库存值`——这是为何
  绝大多数既有 record-transport 用例（如 `avg_price == "1"`）在 #5 下仍成立；**唯一转红的是
  r6 的 `_NullQuoteExecutor`**（缺口 1）。
- `cumulative_quote_amt` 的 NULL 契约（`_leg_final_fields` docstring，review-1 r4 移除推导）——
  **不得动**（硬约束 #1）。

## 改动文件

```
 frontend/index.html    | 13 +++++--------   # Part A：表头「尝试时间」+ hedgeLogTimeCell 去门控 + 注释
 frontend/self-check.js | 21 +++++++++++++++++- # Part A：注释 + 「每行显示尝试时间」断言
```

后端零改动（Part B 未实施）。

## 验证

```
$ node frontend/self-check.js | tail -2
[PASS] 任务卡内嵌日志 AC1/AC2/AC3/AC4/AC6/AC7/AC9：…（含 Part A 尝试时间断言）
[PASS] 任务卡内嵌日志 AC5/AC7：…
全部自检通过

$ grep -rn "成交时间" frontend/index.html backend/   # = 0（仅 self-check 断言合法命中）
```

`pytest backend/tests` 未重跑——本轮未改后端，基线 `b14f55ce` 的 1104 passed 仍有效。

## 下一步（交 Bookkeeper opus5）

Part A 已可封存。Part B 需 dispatch 增补两处后重派：
1. 裁定缺口 1 的 r6 守卫处置（a 或 b），并明确是否一并改 entries 流（`_entry_*_leg`）。
2. 增补缺口 2：`resolve_leg_from_query` 加 `avg_price`（签名 + UPDATE + reconcile 调用方传参）。
按 §8，Part B 修复完成后仍须重跑 review-1 再回 review-2（已记入 status.json.blockers）。
