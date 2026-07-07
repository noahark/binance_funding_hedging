# H 实现说明 — stage `2026-07-borrow-cost-coverage-v2`

- owner: claude_glm（glm-5.2 实现会话）
- base_sha（stage 建点）: `5bdfc4b3dc6843a8e52aeb86896c735500ed137a`
- diff 测量基准: 工作树 vs HEAD（`1ecd825`，bookkeeper 预生成 prompt 后）；bookkeeper 做 R4 对账时会以 head_sha 重算。
- 交付物: H（backend + frontend + docs + tests 单批），改动只留工作树，**未 commit、未碰 status.json**。
- reviewer diff: `H.diff.patch`（692 行，`git diff -- backend frontend docs schemas`）。

## 1. 改动文件清单 ↔ task-H §3 映射

| 文件 | §3 | 改动摘要 |
|---|---|---|
| `backend/services/private_client.py` | §3.A | 顶部加 `NEXT_HOURLY_BATCH_SIZE = 15`；`fetch_cost_leg_chain` tier① 由「单次 comma-joined 全量」改为「按 15 分批、逐批 `_cached_get`、`.update()` 合并进 `merged_next_hourly`」；部分批失败仅 `continue`+记 `last_error=next_hourly_batch_failed:{reason}:{n}`（不静默、不清空、不降级）；合并表传入 `_select_chain_tier`（合并在 tier 选择之前）。 |
| `backend/domain/snapshot.py` | §3.B | `select_borrow_candidates` 返回改为 `rate_probe_assets`（全量、不受 cap）/ `borrowability_probe_assets`（受 cap）/ `borrowability_unprobed_assets`（set）/ `coverage`（语义改 borrowability：probed=borrowability 数）。候选口径/去重/排序（abs DESC, symbol ASC）完全不变；rate_probe 默认不限。 |
| `backend/domain/snapshot.py` | §3.C | `assemble_borrow_validation` 关键字参数 `truncated` → **`borrowability_truncated`**；新分支 `verified=False` + classic_margin 按 classic_ref 正常填 + **`daily_interest_account` 保留** + `portfolio_account` 额度清空（`source` 保留）+ **`checked_at` 保留** + `error="borrowability_not_probed"`。`pair_listed/asset_borrowable/daily_vip0` 解析前置，被新分支与正常分支共用。`classic_ref is None` 分支不变。 |
| `backend/domain/snapshot.py` | §3.D（文案落点） | `assemble_snapshot` 的 `coverage.skipped>0` top-level warning 文案改为 `「{N} asset(s) borrowability not probed (rate still covered) — 部分资产可借额度未探测（利率仍覆盖）」`。文案唯一定义点在 domain `assemble_snapshot`（snapshot_service 经 summary 传入），故编辑落此文件，归属 §3.D。 |
| `backend/services/snapshot_service.py` | §3.D | 取三集合；`cost_leg = fetch_cost_leg_chain(rate_probe_assets)`；maxBorrowable 循环只遍历 `borrowability_probe_assets`；行装配利率门由 `base in probed_assets and base not in truncated_assets` 改为 **`base in rate_probe_assets`**（利率解析只依赖 rate set，与 borrowability 解耦）；`assemble_borrow_validation(..., borrowability_truncated=base in borrowability_unprobed_assets)`。sort_basis / sort_rows / 60s 快照缓存 / private_account 装配未改。 |
| `frontend/index.html` | §3.F | `not_probed_this_round` 分支**之前**插入 `borrowability_not_probed` → `<span class="badge muted">有利率·可借性未探测</span>`。其它徽章分支/利率子行/布局/样式未改。 |
| `frontend/self-check.js` | §4.5 | 第 34 项「五文案」→「六文案」：新增 FUSDT 第六态（`borrowability_not_probed` + `daily_interest_account=0.00010000` + `borrow_rate_source=next_hourly` + `negative_funding_status=PRIVATE_BORROW_VALIDATION_REQUIRED`），断言徽章「有利率·可借性未探测」(`badge muted`) **且**净收益列展示「日借币: +0.01%」；**保留** DUSDT `not_probed_this_round` 旧用例（回归）。 |
| `docs/api/public-market-contract.md` | §3.G | `coverage`/warnings 段重述为 borrowability 覆盖 + 两预算解耦；新增 `error` 枚举 `borrowability_not_probed`（可借额度未探测但 `daily_interest_account`/`net_daily_yield` 仍填，仅 portfolio 额度 null，checked_at 保留）；warning 文案同 §3.D；**保留** `not_probed_this_round`（legacy）说明。 |

**未改（设计决策，已落档）**：
- `backend/config.py`（§3.E）: 选择**模块常量** `NEXT_HOURLY_BATCH_SIZE=15`，**不引入** `next_hourly_asset_batch_size` / `borrow_rate_max_assets` 配置项（task-H §3.A/§3.E 二选一不并存；防漂移「不加未要求的配置」）。
- `schemas/api/public-market/snapshot.schema.json`（§3.H）: `borrow_validation.error` 为 `{"type":["string","null"]}` **无 enum 约束**（schema L385），故 additive 无对象，**不动** schema（不改字段形状）。

## 2. 测试输出摘要

```
$ python3 -m pytest backend/tests -q
164 passed in 4.33s          # 基线 160 → +4 新增（test_borrowability_truncated_keeps_rate /
                             # test_next_hourly_subset_miss_no_fabrication /
                             / test_batch_merge_covers_all / test_partial_batch_failure_partial_merge）
$ node frontend/self-check.js
全部自检通过                 # 第 34 项「六文案派生」PASS（含 FUSDT 第六态 + DUSDT 旧态回归）
```

**§4 测试逐条对应**：
- §4.1 `test_borrowability_truncated_keeps_rate`：max_calls=2 / 4 候选 / next-hourly 覆盖全 4 / maxBorrowable 探前 2。断言 unprobed(B,A)：`borrow_rate_source=="next_hourly"` ∧ `daily_interest_account=="0.00012000"` ∧ `net_daily_yield` 非空 ∧ `portfolio_account.max_borrowable is None` ∧ `error=="borrowability_not_probed"` ∧ `verified=False`；probed(D,C) 仍有额度 ∧ `verified=True`。
- §4.2 `test_next_hourly_subset_miss_no_fabrication`：next-hourly 仅返回 A/B/C。断言缺失 D：`borrow_rate_source is None` ∧ `daily_interest_account is None`（不伪造、不落 rate_history）；A/B/C 有利率。
- §4.3 `test_batch_merge_covers_all`：22 资产 → 2 批（15+7），每批 `len(batch)<=20`，合并后 22 全命中、`chain_hit_source=="next_hourly"`。
- §4.3 `test_partial_batch_failure_partial_merge`：30 资产 → 2 批，第 2 批 HTTP500。断言成功批 A0 有利率、失败批 A15/A29 `rate=None`、**`chain_hit_source=="next_hourly"`（不降级 tier②）**、`last_error` 含 `next_hourly_batch_failed`。
- §4.5（改）`test_borrow_validation_truncated_state`：`borrowability_truncated=True` → `daily_interest_account` **保留** ∧ `error=="borrowability_not_probed"` ∧ `portfolio_account.max_borrowable is None` ∧ `checked_at` 保留。
- §4.4（改）`test_truncation_appends_top_level_warning`：warning 文案断言更新为 `可借额度未探测` / `利率仍覆盖` / `2 asset`。
- §3.B 连代（改）`test_select_borrow_candidates_*`（caps/no_reason/only_neg/dedup）与 `_assemble_with_private`：键名 `probed_assets`→`rate_probe_assets`/`borrowability_probe_assets`，coverage 形状不变。
- §4.6 核对：`test_offline_snapshot_v03_fields_validate`（L855-859）在新契约下**自然通过**（offline fixture 无负费率 MARGIN_SPOT_CANDIDATE+CRYPTO 候选 → coverage.probed==0 不变；rows 断言不变），无需修改。

## 3. §5 验收自查表（对照 10-design §8 / stage-plan §5 十条）

| # | 验收项 | 结果 | 证据 |
|---|---|---|---|
| 1 | tier① 分批后 `chain_hit_source=next_hourly`（不再永远 rate_history） | ✅ 代码+测试 | `test_batch_merge_covers_all` / `test_partial_batch_failure_partial_merge` 均断言 `next_hourly`；分批合并发生在 `_select_chain_tier` 之前 |
| 2 | next-hourly 覆盖资产 100% 有 daily_interest_account + net_daily_yield | ✅ 测试 | `test_batch_merge_covers_all`（22/22）；`test_borrowability_truncated_keeps_rate`（unprobed 也保留利率） |
| 3 | `borrow_check_max_calls` 只限 maxBorrowable，不限利率覆盖 | ✅ 代码 | snapshot_service：cost_leg 喂 `rate_probe_assets`，maxBorrowable 喂 `borrowability_probe_assets` |
| 4 | `borrowability_not_probed`（有利率·未探测）与 `borrow_rate_source=null`（无利率）数据+UI 可区分 | ✅ 测试+UI | §4.1（保留利率+error）/§4.2（无利率）；index.html 第六态徽章；self-check 六文案 |
| 5 | next-hourly 未返回/失败批资产不伪造利率 | ✅ 测试 | §4.2（D 缺失→None）；§4.3 partial（失败批→None） |
| 6 | 前端第六态行自洽；self-check 通过（含旧态回归） | ✅ | self-check 第 34 项六文案 PASS（FUSDT 第六态 + DUSDT not_probed_this_round 旧态） |
| 7 | contract.md 契约同步；schema additive | ✅ | contract.md §coverage/warnings 更新；schema error 无 enum → 不动（§3.H 决策） |
| 8 | 部分批失败部分合并；60s 自愈（失败批未被整表缓存） | ✅ 代码 | 逐批 `_cached_get`（key 含 assets 参数），失败批不写缓存；**无** merged 整表缓存项 |
| 9 | bStock 负费率借币仍禁用 | ✅ 未触碰 | 未改 classify/bStock 路径；候选口径 `asset_tag==CRYPTO` 不变 |
| 10 | 全部测试通过；live smoke 只读 | ✅ 测试 / ⏳ smoke | pytest 164 / self-check 全绿；live 只读 smoke 待 bookkeeper/用户在启用私有通道后跑（不在本实现会话） |

## 4. 统计（§6.3）

**测试覆盖（确定性）**：
- `test_borrowability_truncated_keeps_rate`：rate_probe_assets_count=4，borrowability_probe_assets_count=2，borrowability_unprobed_assets_count=2，rows_with_rate_but_borrowability_unprobed_count=2，chain_hit_source=`next_hourly`
- `test_batch_merge_covers_all`：batches_attempted=2（ceil(22/15)），batches_failed=0，next_hourly_returned_assets_count=22，rows_with_rate_count=22，chain_hit_source=`next_hourly`
- `test_partial_batch_failure_partial_merge`：batches_attempted=2，batches_failed=1，next_hourly_returned_assets_count=15（成功批），chain_hit_source=`next_hourly`（未降级 tier②）

**Gate A 实盘证据（`gate-a-live.md`，引用非重跑）**：
- negative_margin_spot_crypto_candidate_count=66，borrow_check_max_calls=50，would_truncate=True（skipped=16）
- 修复后预期：rate_probe_assets_count=66，borrowability_probe_assets_count=50，borrowability_unprobed_assets_count=16，batches_attempted=ceil(66/15)=5，chain_hit_source=`next_hourly`

**实盘 live 值（next_hourly_returned_assets_count / batches_failed / rows_with_rate_count）**：本实现会话为 offline（无私有通道），无法取实盘值；待 bookkeeper/用户在 `BINANCE_PRIVATE_CHANNEL_ENABLED=true` 下跑只读 smoke 落档（验收项 10）。

## 5. 缓存纪律（review-1 必查 §2）

- 逐批 `_cached_get` **保留**（cache key 含 `assets` 参数，private_client.py L191）。
- **未**把 `merged_next_hourly` 整表另存为单一缓存项（会缓存「部分批失败」残缺结果 1h，破坏 60s 自愈）。
- 失败批：`except PrivateEndpointError` 在 `_cached_get` 内部已 raise（不写缓存），外层 `continue` → 下一张快照（≤60s）只重试失败批。
- 同一快照周期不重复调用（`get_snapshot` 60s 快照级缓存），未加去重逻辑。

## 6. 防漂移核对

- 改动文件 7 个，全部在 task-H §3 允许集内（`git diff --stat` 见上）。
- Decimal 全程，零 float；key/secret 零片段（测试用 `"k"*64/"s"*64`）；fixture 用脱敏占位（`<AMOUNT>`）。
- bStock 禁用规则、`_select_chain_tier` 逻辑、tier②/③/④、`fetch_max_borrowable`、`_signed_get`/`_cached_get` 签名与缓存结构、白名单均未改。
- 未 commit、未碰 status.json。

## 7. next_dispatch

R10 步骤 4：机械触发 kimi 嵌入预审 review-1，落 `embedded-review-H-round1.raw-output.md`，按 verdict 分支处理。
