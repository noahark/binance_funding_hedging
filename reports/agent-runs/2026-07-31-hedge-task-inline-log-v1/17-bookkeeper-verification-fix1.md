# 17：Bookkeeper 核验记录 —— fix-1（opus5，2026-07-31）

对 `claude_glm` 的修复交付（`16-fix-result.md`）做独立核验。结论：**通过，予以封存**。

## 独立复跑的证据

| 检查 | Bookkeeper 实测结果 |
|---|---|
| 后端回归 | `1108 passed in 58.23s`（基线 1104 + 新增 4），与交付一致 |
| 前端自检 | `全部自检通过` |
| `live_hedge_executor.py` 未改 | `git diff --name-only backend/services/` 为空 —— AC8 成立 |
| 「成交时间」残留 | `frontend/index.html` 中 0 处 |
| 改动范围 | 6 个文件全在 Allowed Files 内 |

## 逐项核验

### Part A（R2-F1）

- 列头已改为「尝试时间」（`index.html:4238`）。
- `hedgeLogTimeCell`（`:4277`）已去掉 `order_id` 门控，只判 `attempt.ts` 是否有值——
  与裁定一致。
- self-check 新断言覆盖四状态每行均显示时间。

### Part B（九处，逐处核对 diff）

| # | 改动 | 核验 |
|---|---|---|
| 1 | migration 加 `("avg_price", "TEXT")` | 在 `leg_additions` 内，沿用既有 guard 模式 |
| 2 | `_leg_final_fields` 返回 avg_price | 签名由 6 元组扩为 7 元组，取 `leg_outcome.get("avg_price")` 原样透传 |
| 3 | `resolve_attempt` UPDATE | 解包 `spot_avg`/`perp_avg`，UPDATE 加 `avg_price = ?` |
| 4 | **`resolve_leg_from_query`** | 签名加 `avg_price: str \| None = None`，UPDATE 加该列 —— **首轮缺口已补，合约腿补均价的正路打通** |
| 5 | reconcile 调用点 | 传 `avg_price=verdict.avg_price` |
| 6 | `_row_to_leg` | 加 `"avg_price": row["avg_price"]` |
| 7-8 | 三处腿投影 | **抽出公共 helper `_resolve_avg_price`（`service.py:205`），`_leg_to_doc` / `_entry_spot_leg` / `_entry_perp_leg` 三处共用** —— 比 packet 要求的「用相同优先级」更强：结构上保证两流必然同价，不依赖人工对齐 |
| 9 | 测试 | 见下 |

### r6 守卫拆分（按 Bookkeeper 裁定）

- 反造假内核保住：`_NullQuoteExecutor` 的 avg 改为 `None`，原用例继续断言
  「NULL quote + 无 avg → 两流均 `None`」。
- 新语义用例：`test_null_quote_with_exchange_avg_projects_on_both_streams`，断言两流
  均展示 `"50000"` 且 `a["spot"]["avg_price"] == e["spot"]["avg_price"]`。
- `cumulative_quote_amt is None` 的断言未被改动 —— quote 的 NULL 契约完好。

### 新增测试（4 条，全部命中要害）

- `test_avg_price_priority_three_levels_both_streams`：三级优先级 × 三处投影全覆盖
  （库存 `99999` 优先 / 退回本地 `50000` / 无键退回 / 全无则 `None`）。
- `test_resolve_leg_from_query_persists_avg_price`：断言 `"50123.45"` 经 reconcile
  落库并投影 —— **这条直接验证了首轮缺口对应的核心场景**。
- `test_avg_price_migration_idempotent_and_preserves_existing_rows`：跨重开幂等、
  既有行逐字保留。
- 新语义两流一致用例（见上）。

## 值得记下的一点

实现者把三处投影抽成公共 helper，而不是在三处各写一遍相同逻辑。packet 只要求
「必须用完全相同的三级优先级」，它给出的是**结构上不可能不一致**的做法。两流同价从
「靠人工对齐」变成「靠调用同一函数」——这是比要求更好的解法，记录在案。

## SHA 封存

- `base_sha`：`42de1aff364e7c979d2fbb5dc56f1dec65287cc7`（未变）
- `delivery_sha`：更新为本次修复提交（见 `status.json`）。原交付 `b14f55ce` 已被取代，
  评审区间为 `base_sha..新 delivery_sha`，含首轮交付与本轮修复的全部改动。

## 下一步（路由）

本轮扩了 schema + 写路径，按 `AGENTS.md` §8**必须重跑 review-1**（`grok` / xai），
通过后再回 review-2（`codex` / openai）。不走「窄发现直接回 review-2」的快路径。

`rework_count` 保持 **1**。
