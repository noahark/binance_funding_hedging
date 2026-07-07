# Borrow Cost Coverage v2 Fix Plan DRAFT-2 — Review

模型：Claude (Opus 4.8)
任务：只读 review `borrow-cost-coverage-v2-fix-plan-draft2.md`，不修改业务代码，不提交 git
裁决：**ACCEPT（有条件）** —— 方向已正确，但有 1 个阻塞级落地陷阱 + 1 个未证实前提必须先补
关联证据（已逐一核对）：

- `reports/agent-runs/private-account-v1-direction/borrow-cost-coverage-v2-fix-plan-draft2.md`（被评审对象）
- `reports/agent-runs/private-account-v1-direction/borrow-cost-coverage-v2-fix-plan-review-claude.md`（DRAFT-1 REWORK）
- `reports/agent-runs/private-account-v1-direction/endpoint-recon-kimi-borrow-rate-v2.md`（Kimi 主报告，本轮亦重读）
- `backend/domain/snapshot.py`（`assemble_borrow_validation` L666、`select_borrow_candidates` L333、`resolve_cost_leg_rate` L385）
- `backend/services/snapshot_service.py`（行装配 L189-212）
- `backend/services/private_client.py`（`_select_chain_tier` L409、`fetch_cost_leg_chain` L268）

---

## 0. 裁决摘要

DRAFT-2 正确吸收了 DRAFT-1 的 4 条 must-fix：根因重写（§1/§2）、解耦 rate-probe 与 maxBorrowable 预算（§3）、显式 defer per-asset tier synthesis（§4.1）、量化验收（§8）。方向现在成立。

但仍有两点必须在动手前补入，条件 1 若不补，fix 上线后主症状会照旧：

1. **阻塞级**：解耦会在 `assemble_borrow_validation` 的 `truncated` 分支被二次截断，rate 仍被清空——DRAFT-2 的编辑地图漏了这个函数。
2. **前提未证**：根因 A（截断）本身缺实盘证据，需设为显式决策门。

其余为非阻塞改进。

---

## 1. 必修 1（阻塞级）：解耦在 `assemble_borrow_validation` 里被二次截断

DRAFT-2 §3.1 伪代码只在行循环算 `daily_borrow_rate` 并传下去，§6 称"行装配时利率解析不再依赖 truncated_assets"。但真正决定输出的是 `assemble_borrow_validation`（`snapshot.py:713`）：

```python
if truncated:                       # 当前由 snapshot_service.py:211 传入 base in truncated_assets
    return {
        "verified": False,
        "classic_margin": {... "daily_interest_account": None ...},   # ← rate 在此被清掉
        "error": "not_probed_this_round",
    }
```

后果：解耦后若 `truncated` 仍来自"borrowability 未探测"集合，则任何不在 maxBorrowable 预算内的资产都会进此分支，`daily_interest_account` 被强制置 None、`verified=False`——恰好抹掉解耦本要保住的利率。§3.1 在行循环算对了 rate，但此函数短路覆盖它。

**因此 DRAFT-2 编辑地图（§6）漏了最关键的一处**：`assemble_borrow_validation` 的 `truncated` 分支必须重构：

- "可借性未探测"不得 null 掉 `daily_interest_account`；
- 不得仅因可借性未探测就 `verified=False`；
- 需重新定义"rate 有、borrowability 无"时的 `verified` / `error` 三态语义。此契约 §5 的状态表暗示了，但 §3.1 伪代码与 §6 边界都没落到这个函数。

**回归守卫已具备**：DRAFT-2 测试 1（"第 3/4 资产 maxBorrowable 未探测但仍有 daily_interest_account 和 borrow_rate_source=next_hourly"）若写成穿过 `assemble_borrow_validation` 的集成断言，正好抓这个陷阱。但 §6 仍须明确点명"改 `assemble_borrow_validation` 截断分支"，否则实现者面对测试 1 失败不知改哪。

---

## 2. 必修 2：根因 A（截断）前提未被证实，须设为决策门

DRAFT-2（及 Claude DRAFT-1 review）都把根因 A（`borrow_check_max_calls=50` 截断）当作"大量 `-`"最可能来源，但**尚无证据证明实盘负费率 `MARGIN_SPOT_CANDIDATE + CRYPTO` 候选真的 > 50**。

若实盘候选 ≤ 50，则根因 A 未触发，真实主因为根因 B（next-hourly 子集缺失）或 next-hourly transient 失败——此时 immediate fix（解耦）上线后 UI 不会有任何变化。

§3.2 只读探测会记录"请求 asset 数量"，证据会浮现——但 DRAFT-2 未将其做成**显式决策门**。须补：

```text
if 候选数 <= borrow_check_max_calls:
    根因 A 未触发 → immediate fix 无法解释主症状 → 转向根因 B（per-asset-cost-leg-v1）
```

防止"改完发现没效果"。

---

## 3. 次要（非阻塞）

- **§3.2 分批合并层级**：若 next-hourly 有单次上限需分批，合并必须发生在 `fetch_cost_leg_chain` 内部的 `next_hourly` 原始 dict 上、在 `_select_chain_tier` 之前（tier 命中判断 `any()` 依赖它），而非 §3.2 所写"合并 daily_by_asset"（那是 tier 选择后的产物）。否则会按批做 tier 选择、source 不一致。
- **§4.2 保留的快照级 fallback**：解耦后 `fetch_cost_leg_chain` 接收更大的 `rate_probe_assets`，`interestRateHistory(borrow_assets[0])` 的 `[0]` 会变成更大集合的头部；crossMarginData tier③/④ 返回全表，覆盖不受影响。行为一致，无需改动，确认无误。
- bStock 保护（§5 / 测试 3）、§4.1 defer per-asset synthesis、§9 阶段拆分、§7 回归命令均 OK。

---

## 4. 必须修正项（must-fix）

1. **（阻塞）** §6 编辑地图补上 `assemble_borrow_validation` 截断分支重构：可借性未探测不得清空 `daily_interest_account`、不得单凭此置 `verified=False`；明确 rate 有/borrowability 无 时的三态语义。
2. **（阻塞）** §3.2 补显式决策门：候选数 ≤ `borrow_check_max_calls` 时判定根因 A 未触发、转根因 B，避免 immediate fix 无效。
3. **（非阻塞）** §3.2 明确分批合并发生在 `_select_chain_tier` 之前的 `next_hourly` dict 层。

修正 1、2 后即可进入实现；3 可在实现说明中落实。

---

## 5. 复核指引（给下一位 reviewer / GPT）

- `snapshot.py:713-730` —— 确认 `truncated=True` 分支当前会 null 掉 `daily_interest_account` 且 `verified=False`（必修 1 的依据）。
- `snapshot_service.py:211` —— 确认 `truncated` 参数当前由 borrow 截断集喂入。
- `snapshot.py:333-357` —— 确认候选集与 cap 来源；实盘候选数需对照 50 验证根因 A（必修 2）。
- `private_client.py:424` —— 确认分批合并须在 tier 选择前。

---

本地北京时间: 2026-07-07 20:52 CST
下一步模型: GPT/Codex（用户将据此再核对）
下一步任务: 依 must-fix 1/2 修订 DRAFT-2，或就根因 A 实盘候选数给出证据
