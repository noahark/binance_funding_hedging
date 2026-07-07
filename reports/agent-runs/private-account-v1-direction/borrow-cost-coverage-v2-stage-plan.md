# Stage Plan：2026-07-borrow-cost-coverage-v2（最终 · 细化拆分版）

作者 / bookkeeper：Fable5（Claude Opus 4.8 会话，履行 stage operator 记账职责）
状态：STAGE-PLAN 定稿，含路由 + 防漂移拆分 + review 建议吸收
设计依据：`borrow-cost-coverage-v2-fix-plan-draft4.md`（含 GPT review P1-P3）
review 吸收：Opus 4.6 五点（本文件 §9 逐条裁定，含 1 条纠正）
证据链：Gate A（`borrow-cost-coverage-v2-gate-a-live.md`）+ Gate B（`endpoint-recon-kimi-borrow-rate-v2.md §9`，24 脱敏样本）

---

## 1. 阶段元数据与路由

```yaml
stage-id:    2026-07-borrow-cost-coverage-v2
complexity:  MEDIUM
mode:        serial                       # 单轨串行，非 parallel_development（理由见 §1.2）
delivery:    单一原子交付物 H（backend+schema+docs+frontend+tests 同批落）

routing:
  owner_implementer: claude_glm            # 唯一实现者，仅在 §3 file 边界内改
  review_1:          kimi
  review_2:          codex
  bookkeeper:        fable5                 # 独立记账 + 验收簿记，不实现
  breakdown_author:  fable5                 # 本 stage-plan 作者（设计参与，供 review-2 披露）
```

### 1.1 角色隔离与 prior-involvement 披露（记账官必录，供 review-2 评估独立性）

| 模型 | 本 stage 身份 | 历史参与（披露） | 资格判定 |
|---|---|---|---|
| claude_glm | implementer（owner） | 无 | 实现者，禁任何 review |
| kimi | review-1 | Gate B 端点摸排（证据采集，非 designer/implementer） | 可任 review-1 |
| codex | review-2 | 撰写 **已被取代**的 DRAFT-1..3 fix-plan 草稿 | 活动设计为 DRAFT-4/本 plan（Fable5 作），codex 非活动设计作者 → 可任 review-2；**prior-involvement 已披露**，请 review-2 自评独立性 |
| fable5 | bookkeeper + breakdown author + 验收簿记 | DRAFT-4 + 本 stage-plan（设计参与） | **不实现、不任 review-2**（reviewer≠designer 红线保持）；bookkeeper≠implementer 保持（fable5≠claude_glm，无 dual-hat） |

> 单一写者纪律：仅 bookkeeper 写 `status.json` / `70-handoff.md` / 证据 commit；implementer 不 commit、不碰 status.json。

### 1.2 为什么 serial 而非 parallel_development

parallel 模式（`docs/parallel-development-mode.md`）用于**双独立任务**并行 + 嵌入交叉预审。本阶段是**一个不可拆分的原子改动**：契约语义变更（`borrowability_not_probed`）必须让 backend / schema / docs / frontend / tests 同批落地。拆并行反而制造中间态不一致。故走标准 serial：单 owner 交付整块 diff → review-1 → review-2 → bookkeeper 落盘。

---

## 2. 前置门（均已完成，实现期不重跑）

| Gate | 结论 | 证据 |
|---|---|---|
| Gate A：候选数 > cap | ✅ 66 > 50，skipped=16 | `borrow-cost-coverage-v2-gate-a-live.md` |
| Gate B：next-hourly 失效 root-cause | ✅ 单次 assets 硬上限 20；发 50 → HTTP500 code=2 → `:319` 静默降级 | `endpoint-recon-kimi-borrow-rate-v2.md §9` |

锁定参数：`MAX_ASSETS_PER_CALL=20`、`BATCH_SIZE=15`、`5 批覆盖 66`、`~500 IP weight/快照`（1h TTL 下可忽略）。

---

## 3. 交付物 H · 逐文件防漂移拆分

> **防漂移总则（implementer 必读）**：只做本节列出的改动；不重构相邻代码、不改风格、不加未要求的抽象/配置/错误处理；每一行改动都要能追溯到下面某条。遇到本节未覆盖、又必须改的情况 → 停，写 `escalation` 交 bookkeeper，不得自行扩面。

### 3.A `backend/services/private_client.py` — next-hourly 分批（主修，先行）

**改 `fetch_cost_leg_chain(borrow_assets)` 内 tier① 段（当前 L304-320）**：

- 把「一次 comma-joined 全部 borrow_assets」改为「按 `BATCH_SIZE=15` 切片，逐批 `_cached_get`，成功结果 `.update()` 进一个 `merged_next_hourly` dict」。
- **部分失败语义（吸收 Opus 4.6 §1）**：某批抛 `PrivateEndpointError` → **仅跳过该批**，已合并的批次保留；**不 abort、不清空、不整体降级**。失败批的资产因不在 `merged_next_hourly` 而自然拿不到利率（下游 resolve 返回 None → `rate_unavailable`）。
- **修静默吞异常（DRAFT-4 §3.5）**：失败批不得静默。至少记录 `f"next_hourly_batch_failed:{code}:{n_assets}"` 到 `self.last_error`（或既有 warning 通道），使 tier① 失效可观测。
- 合并完成后，把 `merged_next_hourly` 传入 `_select_chain_tier`（**合并在 tier 选择之前**，DRAFT-4 §3.5）。
- `BATCH_SIZE`：优先读 `config.next_hourly_asset_batch_size`（§3.E 新增，默认 15）；若不引入配置则用模块常量 `NEXT_HOURLY_BATCH_SIZE = 15` 并注释指向 Gate B 证据。

**缓存纪律（吸收+纠正 Opus 4.6 §3）**：

- **保持逐批 `_cached_get` 缓存**（cache key 已含 `assets` 参数，L191）——成功批各自缓存 1h，失败批不写缓存 → 下一张快照（≤60s 后）自动只重试失败批。
- **禁止**把 `merged_next_hourly` 整表作为单一缓存项。整表缓存会让「部分批失败」的残缺结果被缓存 1h，破坏 60s 自愈。
- 同一快照周期内不会重复调用：`get_snapshot` 已有 60s 快照级缓存（`snapshot_service.py:81`），`fetch_cost_leg_chain` 每次 build 只跑一次。无需额外去重。

**不改**：`_select_chain_tier` 逻辑、tier②/③/④、`fetch_max_borrowable`、`_signed_get`、`_cached_get` 签名与缓存结构。

### 3.B `backend/domain/snapshot.py` — 候选集拆分 + coverage 重定义

**改 `select_borrow_candidates(rows, max_calls)`（当前返回 `probed_assets/truncated_assets/coverage`）**，改为返回：

```python
{
  "rate_probe_assets": [...],            # 全量负费率 MARGIN_SPOT_CANDIDATE+CRYPTO，去重，abs rate DESC 排序，不受 cap
  "borrowability_probe_assets": [...],   # 同池，取前 max_calls 个（保持现有 top-N 语义）
  "borrowability_unprobed_assets": set(),# rate_probe - borrowability_probe
  "coverage": {                          # 语义改为 borrowability 覆盖
    "probed": len(borrowability_probe_assets),
    "skipped": len(borrowability_unprobed_assets),
    "reason": "rate_limit_budget" if skipped else None,
  },
}
```

- 排序/去重/候选口径（`daily_funding_rate<0 ∧ route_class==MARGIN_SPOT_CANDIDATE ∧ asset_tag==CRYPTO`）**保持不变**。
- 可选：`rate_probe_assets` 受 `config.borrow_rate_max_assets`（§3.E，默认 0=不限）上限。

**`resolve_cost_leg_rate` 不改**——它对 `daily_by_asset` 中不存在的 key 已返回 None（L395-397），这正是根因 B / 失败批资产的正确落点（Opus 4.6 §2 的断言对象）。

### 3.C `backend/domain/snapshot.py` — `assemble_borrow_validation` 契约变更

**签名**：`truncated: bool` → `borrowability_truncated: bool`（新名，不复用旧名）。

**三态行为**（替换当前 L713-730 的 `if truncated:` 早返回）：

| 情形 | verified | classic_margin | daily_interest_account | portfolio_account | error | checked_at |
|---|---|---|---|---|---|---|
| `classic_ref is None` | False | 全 null | null | 全 null | 原 error | None |
| `borrowability_truncated=True` | **False** | 按 classic_ref 正常填 | **保留传入值** | **max_borrowable/borrow_limit=null** | **`borrowability_not_probed`** | **保留 checked_at** |
| 正常 | True | 正常填 | 传入值 | portfolio 值 | None | checked_at |

铁律：`borrowability_truncated=True` **不得**清空 `daily_interest_account`，只清 `portfolio_account`。

### 3.D `backend/services/snapshot_service.py` — 装配接线

- 候选集：`probe = select_borrow_candidates(...)` 取三集合。
- 利率链路：`cost_leg = fetch_cost_leg_chain(probe["rate_probe_assets"])`。
- 可借性：`fetch_max_borrowable` 循环只遍历 `probe["borrowability_probe_assets"]`。
- 行装配（改当前 L194-212）：
  ```python
  if base in rate_probe_assets and cost_leg:
      rate = resolve_cost_leg_rate(base, cost_leg)
      if rate is not None:
          daily_borrow_rate = rate
          borrow_rate_source = cost_leg.get("chain_hit_source")
  row["borrow_validation"] = assemble_borrow_validation(
      ..., daily_interest_account=daily_borrow_rate,
      borrowability_truncated=(base in borrowability_unprobed_assets),
  )
  ```
- `borrow_validation_summary.coverage` 沿用 §3.B 新 coverage；`coverage.skipped>0` 的 top-level warning 文案改为「部分资产可借额度未探测（利率仍覆盖）」。
- **不改**：sort_basis 逻辑（`net_daily_yield` 排序自动纳入新获利率的行，属期望行为）。

### 3.E `backend/config.py` — 可选配置（若引入）

```text
next_hourly_asset_batch_size  默认 15   env BINANCE_NEXT_HOURLY_ASSET_BATCH_SIZE
borrow_rate_max_assets        默认 0    env BINANCE_BORROW_RATE_MAX_ASSETS（0=不限）
```

不引入则用常量，二选一，**不要两套并存**。

### 3.F `frontend/index.html` — 徽章第六态

在 `not_probed_this_round` 分支（L906）**之前**插入：

```javascript
if (bv && bv.verified === false && bv.error === 'borrowability_not_probed') {
  return `<span class="badge muted" title="PRIVATE_BORROW_VALIDATION_REQUIRED">有利率·可借性未探测</span>`;
}
```

利率子行（L1093-1104）**不改**（`borrow_rate_source!=null` 已能渲染利率）。**不改**其他徽章分支。

### 3.G `docs/api/public-market-contract.md` — 契约语义（§coverage/warnings，L447-454）

- 新增 `error` 枚举 `borrowability_not_probed`：可借额度未探测，但 `daily_interest_account`/`net_daily_yield` **仍填充**。
- `coverage` 语义改为 borrowability 覆盖；warning 文案同 §3.D。
- 保留 `not_probed_this_round` 说明（legacy 态，仍可能出现）。

### 3.H `schemas/api/public-market/snapshot.schema.json` — additive

仅当 `error` 是受约束枚举时，additive 加入 `borrowability_not_probed`；不改字段形状。加则补兼容测试。

---

## 4. 测试清单（防漂移：测试名 + 断言逐条写死）

### 4.1 新增 — 阻塞回归：截断不清空利率（本阶段最重要）
`test_borrowability_truncated_keeps_rate`：`borrow_check_max_calls=2`，4 个负费率候选，next-hourly fixture 覆盖全部 4，maxBorrowable 只探前 2。断言第 3/4 资产：
`borrow_rate_source=="next_hourly"` ∧ `classic_margin.daily_interest_account` 非空 ∧ `net_daily_yield` 非空 ∧ `portfolio_account.max_borrowable is None` ∧ `error=="borrowability_not_probed"`。

### 4.2 新增 — next-hourly 子集缺失（吸收 Opus 4.6 §2）
`test_next_hourly_subset_miss_no_fabrication`：next-hourly fixture **只返回 3/4** 资产。断言缺失资产 `borrow_rate_source is None` ∧ `daily_interest_account is None`（不伪造、不落 rate_history）。

### 4.3 新增 — 分批合并 / 部分批失败（吸收 Opus 4.6 §1）
- `test_batch_merge_covers_all`：>20 资产分批，断言合并后全部命中、`chain_hit_source=="next_hourly"`。
- `test_partial_batch_failure_partial_merge`：某批抛错，断言成功批资产有利率、失败批资产 rate=None、**不整体降级 tier②**、`last_error` 含 `next_hourly_batch_failed`。

### 4.4 修改 — 现有测试（必须改，非保留）
- `test_private_account_v1.py:227 test_borrow_validation_truncated_state`：改用 `borrowability_truncated=True`，断言 `daily_interest_account` **保留**、`error=="borrowability_not_probed"`、`portfolio_account.max_borrowable is None`。
- L855-859 / L869-892 coverage & warning 断言：按 §3.D 新文案 + 新 coverage 语义更新。

### 4.5 前端 self-check（吸收 Opus 4.6 §4）
第 34 项「五文案」扩为「六文案」：新增 `borrowability_not_probed` 用例 → 断言徽章「有利率·可借性未探测」(`badge muted`) **且**利率子行仍显示「日借币: X.XX%」；**同时保留** `not_probed_this_round` 旧用例断言不被遮盖（回归）。fixture 补一行携带利率但可借性未探测。

### 4.6 回归命令
```text
python3 -m pytest backend/tests -q
node frontend/self-check.js
```

---

## 5. 验收标准（bookkeeper 落盘前逐条核）

1. tier① 分批后真正命中：实盘/smoke `chain_hit_source=next_hourly`（不再 rate_history）。
2. next-hourly 覆盖资产 100% 有 `daily_interest_account`+`net_daily_yield`。
3. `borrow_check_max_calls` 只限 maxBorrowable，不限利率覆盖。
4. `borrowability_not_probed`（有利率·未探测）与 `borrow_rate_source=null`（无利率）在数据+UI 均可区分。
5. next-hourly 未返回/失败批资产不伪造利率。
6. 前端第六态行自洽；`self-check.js` 通过（含旧态回归）。
7. `docs/...contract.md` 契约同步；schema 如动为 additive+兼容测试。
8. 部分批失败时部分合并、60s 自愈成立（失败批未被整表缓存）。
9. bStock 负费率借币仍禁用。
10. 全部测试通过（§4）；live smoke 只读，不触发交易/借还/划转；保留 Kimi Gate B 样本为证据。

---

## 6. Serial 交付流程（替代 parallel R10；吸收 Opus 4.6 §5 的结论）

**结论（bookkeeper 定）**：本阶段 serial，**不运行** `validate-stage.py --phase dispatch-ready`（该门为 parallel 专用，serial 下会因缺 parallel 结构假阳性）。改用下述轻量 handoff checklist，由 bookkeeper 手工核验。

owner=claude_glm 收尾必做（写死路径）：

```text
1. 自测：python3 -m pytest backend/tests -q && node frontend/self-check.js  → 全绿
2. diff：git diff -- backend/ frontend/ docs/ schemas/ > reports/agent-runs/2026-07-borrow-cost-coverage-v2/H.diff.patch
3. 实现说明：reports/agent-runs/2026-07-borrow-cost-coverage-v2/H.impl-note.md
   （含：改了哪些文件、Gate 证据引用、§8 输出统计）
4. 报告 PASS 并停，等 bookkeeper 串行落盘 + 派 review-1(kimi)。
5. BLOCKER 分支：仅 scope 内 fix；任何超出 §3 file 边界或新契约面 → 停，交 bookkeeper 升级，禁自行扩面。
6. 禁止：口头报告等待用户而不落 impl-note / diff。
```

实现报告 §8 建议统计：
```text
rate_probe_assets_count / borrowability_probe_assets_count / borrowability_unprobed_assets_count
next_hourly_returned_assets_count / batches_attempted / batches_failed
rows_with_rate_count / rows_with_rate_but_borrowability_unprobed_count / chain_hit_source
```

---

## 7. 交 bookkeeper（我）的开阶段动作清单

1. 建 stage_branch（stage-branch-mode，先于任何实现）。
2. 建 `reports/agent-runs/2026-07-borrow-cost-coverage-v2/`，引入本 plan + DRAFT-4 + 两份 Gate 证据为 stage facts。
3. 生成 owner 任务书 `task-H-claude-glm.prompt.md`（PROMPT BODY = §3 拆分 + §4 测试 + §6 收尾段，写死真实路径）。
4. 落 `status.json`（含 §1 routing + prior-involvement 披露 + serial handoff checklist；**不塞** parallel r10_checklist）。
5. 派 owner=claude_glm 实现 → review-1 kimi → review-2 codex → 我做验收簿记（不宣布 final acceptance，交用户）。

---

## 8. Bookkeeper 备注（Fable5）

- 我（Fable5）参与了 DRAFT-4 + 本 breakdown，属**设计参与**——已在 §1.1 披露，且**不兼 review-2**，reviewer≠designer 红线保持。
- 我不写实现代码；仅记账、派发、核验证据、验收簿记。final acceptance 归 review-2 + 用户，不归我。
- Opus 4.6 §3 的「整表缓存」建议**未采纳**（§3.A 已记纠正理由），此为设计决策，请 review-2 一并复核该决策是否成立。

---

本地北京时间: 2026-07-07 22:55 CST
下一步模型: bookkeeper（Fable5，即本会话）→ 建分支 + 生成 task-H 任务书
下一步任务: 执行 §7 开阶段动作，派 claude_glm 进实现
