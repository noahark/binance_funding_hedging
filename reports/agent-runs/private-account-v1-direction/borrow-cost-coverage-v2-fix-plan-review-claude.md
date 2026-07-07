# Borrow Cost Coverage v2 Fix Plan — Review

模型：Claude (Opus 4.8)
任务：只读 review `borrow-cost-coverage-v2-fix-plan.md`，不修改业务代码，不提交 git
裁决：**REWORK**
关联证据（已逐一核对）：

- `reports/agent-runs/private-account-v1-direction/borrow-cost-coverage-v2-fix-plan.md`（被评审对象）
- `reports/agent-runs/private-account-v1-direction/endpoint-recon-kimi-borrow-rate-v2.md`
- `backend/services/private_client.py`（`fetch_cost_leg_chain` L268、`_select_chain_tier` L409、`fetch_max_borrowable` L233）
- `backend/services/snapshot_service.py`（probe 集构造 L135、cost_leg L142、行装配 L189-212）
- `backend/domain/snapshot.py`（`select_borrow_candidates` L333、`resolve_cost_leg_rate` L385）
- `backend/config.py`（`borrow_check_max_calls` 默认 50，L45）

---

## 0. 裁决摘要

方案技术方向（next-hourly 作利率主源、maxBorrowable 与利率分离、bStock 保护）正确，但 **§1 根因诊断与代码实际行为不符**，导致 immediate fix 部分错配：把已实现的当待修、把真正的硬骨头 under-scope、把最简修复漏掉。**不能 ACCEPT，需 REWORK。**

---

## 1. 核心问题：根因诊断错误

方案 §1 归因：

> fallback `interestRateHistory` 只查 `borrow_assets[0]`，结果只有 OPG 拿到利率，其他 null。

代码实际行为不是 per-asset fallback。`_select_chain_tier`（`private_client.py:409`）是**快照级单 tier 选择**：

```python
if any(v for v in next_hourly.values()):        # 只要有任意命中
    return {... "daily_by_asset": dict(next_hourly) ...}   # 整张 next_hourly 表全返回
if any(v for v in rate_history.values()):        # 仅当 next_hourly 完全为空才轮到
    ...
```

推论：

- **只要 next-hourly 返回任意资产（Kimi 实测 8/9 命中），tier① 赢家通吃，`rate_history` 根本不被读取。** 所以"只查第一个资产"这条路径在 next-hourly 正常的稳态下是死代码，改它对主症状零帮助。
- Kimi 报告 §5.1 本身是对的——它明确加了前提"**当 tier① 因网络/限频失败时**"才退到 tier②。fix plan 丢了这个条件，把 transient 降级路径误当稳态主因。

---

## 2. `-` 的真实来源（方案漏诊）

`snapshot_service.py` 中负费率行显示 `-` 的实际路径有两条，均非方案所述：

**(A) 截断 —— 最可能的"大量 `-`"来源。** `snapshot_service.py:135` `select_borrow_candidates(rows, borrow_check_max_calls)`，默认 cap=50（`config.py:45`）。超出者进 `truncated_assets`；行循环 `:195`：

```python
if base in probed_assets and base not in truncated_assets and cost_leg:
    rate = resolve_cost_leg_rate(...)
```

截断资产既无利率也无可借性，直接 `-` / `not_probed_this_round`。若负费率候选 > 50，这就是大面积 `-` 的直接原因，**与数据源无关**。

**(B) next-hourly 返回子集。** 送进去但响应缺失的资产（TSLAB 或任何 next-hourly 不覆盖的币）为 null；因 tier① 赢家通吃，这些缺失资产**永不回退**到 rate_history。

---

## 3. 由根因错误导致的方案错配

1. **2.1「Immediate Fix：next-hourly 批量填充所有命中资产」基本已实现。** `resolve_cost_leg_rate`（`snapshot.py:385`）已对每个 probed 非截断资产做 `next_hourly × 24` 并写 `borrow_rate_source="next_hourly"`。方案把已完成项列为待修。

2. **2.2「bounded per-asset fallback，缺失资产 source=rate_history」隐含一次架构重构，方案未点명。** 当前是"快照级单 tier、整表返回"；要让同一快照内 A 用 next_hourly、B 用 rate_history，必须把 `_select_chain_tier` / `cost_leg` 从"单 tier 表"改为 **per-asset tier 合成**。方案测试用例 2（"缺失资产 → source==rate_history"）在现有 all-or-nothing 模型下**无法通过**。这是本次真正的硬骨头，却被写成一句轻描淡写的 fallback 调整，严重 under-scope。

3. **truncation 被错误归入「2.3 maxBorrowable rotating queue」。** 截断的是 `probed_assets` 这个**共享集合**，同时喂给 next-hourly 输入与 maxBorrowable 循环。仅算作 maxBorrowable 覆盖率问题是误判。

---

## 4. 方案漏掉的最简修复（应作为 immediate fix 核心）

next-hourly 是**一次 comma-joined 调用，权重固定 200，与资产数无关**（`private_client.py:312`）；真正贵的是 maxBorrowable（5/asset）。故 `borrow_check_max_calls=50` 这个 cap 由 maxBorrowable 成本驱动，却**连累了 next-hourly 的输入集**。

**建议：解耦两个预算。** 把全部负费率候选（不 cap 或更大 cap）喂给 next-hourly 拿利率，只对 maxBorrowable 保留探测预算。这样"大量 `-` 日借币利率"能以近乎零额外成本立刻消失，**无需 rotating queue、无需碰 rate_history**。这是最小改动、最高收益路径，方案因误诊而错过。

**需实测确认的开放项（阻塞项，不可默认）：** next-hourly 单次调用 `assets` 参数是否有资产数量上限？Kimi 仅验到 9 个。若一次能覆盖全部候选，解耦成立；若有上限，需分批多次调用。上手前必须补一个只读探测确认。

---

## 5. 次要但需修正

- **§6.1 验收「不再大面积显示 -」缺可量化门槛**，且未区分"截断导致"vs"数据源导致"——按当前诊断，仅改数据源可能症状照旧。建议改为："负费率候选中 next-hourly 覆盖的资产 100% 有利率；未覆盖者按 (B) 明确标注原因"。
- **测试用例 1 基本是现有行为回归**，非新覆盖；真正需新写的是"截断解耦"与"per-asset tier 合成"两类用例，方案均缺。
- **bStock 保护（§2.1 / 测试 4）表达清晰且正确**，无需改动。
- 阶段拆分把 rotating queue 单独后置——方向正确，保留。

---

## 6. 必须修正项（must-fix）

1. **重写 §1 根因**：以代码为准——`_select_chain_tier` 是快照级单 tier；稳态下 rate_history 不参与；主症状来自 (A) `borrow_check_max_calls` 截断 与 (B) next-hourly 子集覆盖，而非"fallback 只查第一个资产"。
2. **新增 immediate fix：解耦 rate-probe 输入集与 maxBorrowable 预算**，让 next-hourly 覆盖全部候选；上手前先补 next-hourly 资产数上限的只读实测。
3. **若保留 2.2 的 per-asset fallback**，须显式声明这是把 cost_leg 从"单 tier 表"重构为"per-asset tier 合成"，并据此重写测试 2；否则该测试不可能通过。
4. **验收标准量化**，并区分截断原因 vs 数据源原因。

---

## 7. 复核指引（给下一位 reviewer / GPT）

关键交叉验证点，可直接对照代码复核本报告结论：

- `private_client.py:424` —— 确认 tier① 命中即整表返回、rate_history 仅在 next_hourly 全空时参与。
- `snapshot_service.py:195` —— 确认截断资产不解析利率。
- `snapshot.py:349,369-372` —— 确认 cap 来自 `borrow_check_max_calls`，共享给 next-hourly 与 maxBorrowable。
- `private_client.py:312` —— 确认 next-hourly 为单次 comma-joined 调用（权重与资产数无关）。

---

本地北京时间: 2026-07-07 20:40 CST
下一步模型: GPT/Codex（用户将据此再核对）
下一步任务: 依 must-fix 修订 fix plan，或就根因诊断给出反驳证据
