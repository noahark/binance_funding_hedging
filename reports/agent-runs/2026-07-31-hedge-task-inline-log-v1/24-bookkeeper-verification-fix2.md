# 24：Bookkeeper 核验记录 —— fix-2（opus5，2026-07-31）

对 `claude_glm` 的 fix-2 交付（`23-fix2-result.md`）做独立核验。结论：**通过，予以封存**。

## 独立复跑（不是转述回执）

### 解析层零值归一 —— 在改动后的代码上实测

```
'0'             -> None ✓        '50000.12'     -> '50000.12'     ✓
'0.00000'       -> None ✓        '0.0000123'    -> '0.0000123'    ✓
'0.0'           -> None ✓        '120.70000000' -> '120.70000000' ✓
0               -> None ✓
'0E-8'          -> None ✓
'-0'            -> None ✓
'0.000000000'   -> None ✓
```

七种零写法全部归一为 `None`，三种非零值**逐字原样**返回，未被补零/截断/科学计数法改写。

### 【最易错处】成交额的零语义未被误伤

```
_quote_decimal('0')       -> '0'        ✓ 真实零保留
_quote_decimal('0.00000') -> '0.00000'  ✓ 真实零保留
```

`cumulative_quote_amt` 的 T1 契约（`NULL` = 未知 / `"0"` = 真实零成交）完好。这是本轮
packet 标为最容易改错的地方，实测确认未被波及。

### 其余

| 检查 | 结果 |
|---|---|
| 后端回归 | `1112 passed in 58.75s`（基线 1108 + 新增 4），与交付一致 |
| 前端自检 | `全部自检通过` |
| `store.py` / 前端 | **零改动**（`git diff --name-only` 无命中） |
| 改动量 | `service.py` +10、`live_hedge_executor.py` 净 +14、测试 +63 —— 符合预期量级 |

## 逐项核验

- **AC1 解析层**：判零由字面比对改为 `Decimal(str(raw)) == 0` 数值比较，覆盖全部零写法；
  非零走 `_quote_decimal` 原样透传。不可解析输入仍返回 `None`。
- **AC2 展示层**：`_resolve_avg_price` 取用库存值前做同样的数值判零，为零则退回本地
  计算（②）。attempts 与 entries 因共用该 helper，行为必然一致。
- **AC3 端到端**：`test_query_zero_avg_price_is_not_a_real_price` 覆盖「已受理未成交、
  `avgPrice="0.00000"`」→ 投影为 `None`。
- **AC4** 非零均价仍优先展示交易所值。
- **AC5** 见上，成交额零语义完好，既有 T1 用例全绿。
- **边界**：`live_hedge_executor.py` 仅 `_avg_price_decimal` 一处变更；未动
  `_quote_decimal`、`store.py`、migration、前端。

## 值得记下的一点

新代码的注释把**「为什么成交额的零要留、均价的零要丢」**这个区别写进了函数文档，并明确
写下 `Do not unify them`。

这正是本轮缺陷的根源类型——两个看起来相似、语义相反的零。把区别钉在代码里，比只在
stage 报告里记一笔更能防住将来的"顺手统一"。记录在案。

## 路由裁定：**重跑 review-1，再回 review-2**

实现者建议可直接回 review-2（窄发现），并声明从 Bookkeeper 判定。**Bookkeeper 判定需要
重跑 review-1**，理由：

1. 本轮改的是 `backend/services/live_hedge_executor.py` —— **实盘下单执行器**，
   且是本 stage 至此**首次触碰该文件**（前两轮 delivery 对它均为零改动）。
2. 改的是**资金字段的解析语义**，`AGENTS.md` §8 明列「review-2 阶段的修复若扩文件、
   改契约或增风险，须重过 review-1」。本轮扩了文件面、改了解析契约。
3. review-2 按职责不做代码级审查；让它单独为一处资金解析语义把关，覆盖不足。
4. 重跑 review-1 **不消耗** `rework_count`（评审轮不递增），成本仅为一轮时间，
   而 `rework_count` 已达 2/3、容错所剩无几，此时更应把问题拦在代码级。

## SHA 封存

- `base_sha`：`42de1aff364e7c979d2fbb5dc56f1dec65287cc7`（未变）
- `delivery_sha`：更新为本次 fix-2 提交（见 `status.json`），区间含首轮交付 +
  fix-1 + fix-2 的全部改动。

`rework_count` 保持 **2**（本次核验不递增；**上限 3，仅剩一次**）。
