# 23-fix2-result：2026-07-31-hedge-task-inline-log-v1-fix-2（已完成）

> 实现者 claude_glm，2026-07-31。修复基线 `delivery_sha = d85a2d3`（fix-1 封存）。
> **结论：R2-Rerun-F1 已修复（解析层 + 展示层纵深防御），自测全过。**

## 问题（R2-Rerun-F1，已核实）

`_avg_price_decimal`（`live_hedge_executor.py:93`）判零条件是 `raw in (None, "", "0", 0)`，
**只认字面 `"0"`**。币安 USDⓈ-M「查询订单」对「已受理但未成交」订单实际返回
`avgPrice="0.00000"`——它与 `"0"` 不相等，于是漏网，被落库并在日志表显示为均价 `0.00000`。
用户会读成「成交价是零」，事实是「还没成交」。违反本 stage 钱的展示硬约束。

Bookkeeper 实测（`22-fix2.dispatch.md`）：
```
'0'        -> None       ✓
'0.00000'  -> '0.00000'  ✗   ← 币安实际返回格式
'0.0'      -> '0.0'      ✗
```

## 两层修复

**第一层（解析层，主修复）**——`_avg_price_decimal`：判零改为**数值判零**。
```python
if raw is None or isinstance(raw, bool):
    return None
try:
    value = Decimal(str(raw))
except (InvalidOperation, ValueError, TypeError):
    return None
if value == 0:          # Decimal 按值比较：Decimal("0.00000")==0、Decimal("0E-8")==0 都命中
    return None
return _quote_decimal(raw)   # 非零值逐字透传，不做格式化改动
```
`Decimal` 按值比较，一次性覆盖 `"0"`/`"0.00000"`/`"0.0"`/`"0E-8"`/`"-0"`/`0` 等所有零的写法；
非零值仍走 `_quote_decimal`（与原行为一致，无格式化改动）。

**第二层（展示层，纵深防御）**——`_resolve_avg_price`（`service.py:205`）：取用库存值前再做
同样的数值判零——库存值为零时视为未知，退回本地计算（②），不展示 `0`。护住：① 已落库的
脏数据（解析层修好也不会自动消失）；② 未来若出现别的写入路径；③ 业务上均价不可能为零。

## 硬约束遵守

1. **未动 `_quote_decimal`**：成交额的 `"0"` 是**真实零成交**（合法值），与均价零含义不同。
   `_quote_decimal("0")` 仍返回 `"0"`、`_quote_decimal("0.00000")` 仍返回 `"0.00000"`；
   `cumulative_quote_amt` 的「NULL=未知 / "0"=真实零」T1 契约完好（既有 T1 用例全绿）。
   —— `git diff` 证明 `live_hedge_executor.py` 仅 `_avg_price_decimal` 一个函数变更。
2. **非零值表示不变**：`"50000.12"` 进、`"50000.12"` 出（仍走 `_quote_decimal`，无补零/截断/
   科学计数法）。
3. **未碰**：状态机/调度/结算/计数器/暂停删除/worker/aggregate_positions/下单行为；
   `store.py`、migration、前端均零改动。

## 改动文件（全部在 Allowed Files 内）

```
 backend/services/live_hedge_executor.py | 23 +++-   # 仅 _avg_price_decimal（数值判零）
 backend/hedge_open_tasks/service.py     | 10 ++     # 仅 _resolve_avg_price（零值防御）
 backend/tests/test_live_hedge_executor.py | 36 ++++  # AC1/AC3/AC4/AC5
 backend/tests/test_hedge_service.py     | 27 ++      # AC2（两流零值防御）
```
`_quote_decimal`、`store.py`、前端零改动（`git diff d85a2d3 -- store.py frontend/` 为空）。

## 原始测试输出

```
$ python3 -m pytest backend/tests -q
........................................................................ [ 97%]
................................                                        [100%]
1112 passed in 58.63s     # 基线 1108 + 新增 4（解析层零值、quote 零保留、端到端、展示层防御）

$ node frontend/self-check.js | tail -1
全部自检通过
```

新增用例：`test_avg_price_decimal_drops_any_numeric_zero_keeps_nonzero_verbatim`、
`test_quote_decimal_real_zero_is_preserved_not_dropped`、
`test_query_zero_avg_price_is_not_a_real_price`、
`test_resolve_avg_price_zero_stored_falls_back_to_local_both_streams`。
**无既有用例转红**（没有任何测试断言过 `_avg_price_decimal("0.00000")` 的旧错误行为）。

## 验收逐项

| AC | 结果 | 证据 |
|---|---|---|
| 1 解析层零值归一（"0"/"0.00000"/"0.0"/0/"0E-8"/"-0"→None；非零逐字） | pass | test_avg_price_decimal_drops_any_numeric_zero… |
| 2 展示层零值防御（库存零→退回本地；两流一致） | pass | test_resolve_avg_price_zero_stored_falls_back_to_local_both_streams |
| 3 端到端（avgPrice="0.00000"→投影 None，页面上不出现 0） | pass | test_query_zero_avg_price_is_not_a_real_price |
| 4 真实均价不受影响（非零 avgPrice 仍优先） | pass | 同上对照分支 + AC2 非零分支 |
| 5 成交额零语义未波及（_quote_decimal("0")=="0"、T1 契约完好） | pass | test_quote_decimal_real_zero_is_preserved_not_dropped + 既有 T1 用例 |
| 6 回归（pytest 1112 + self-check 全过） | pass | 原始输出见上 |
| 7 改动量（两函数各几行 + 测试） | pass | service +10、live_executor 净 +14、测试 +63 |

## 下一步

按 §8，本轮改了 `live_hedge_executor.py`（services 层，写路径相关）+ 展示层契约（均价零
不展示），属 review-2 阶段修复；上次 review-1 复审已 ACCEPT。本轮发现是 review-2 复审的
窄发现（单函数语义 + 展示层防御，未扩文件/未改契约外行为）。交 Bookkeeper（opus5）核验后
路由：窄发现可直接回 review-2；若 Bookkeeper 判定改了均价展示契约需重过 review-1，则从其
判定。未合并、未推送、未启动评审终端。
