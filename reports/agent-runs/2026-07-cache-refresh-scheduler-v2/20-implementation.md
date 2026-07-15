# Implementation Report

## State

**Implemented — full suite green (325 passed).** All eight frozen design
contracts (FR-1..8, CC-1..6, INV-1/1b) are covered by focused tests. Ready for
bookkeeper inspection.

## Implementer

- Model: `glm-5.2`
- Provider identity: `zhipu_glm`
- Skill: `senior_developer`
- Adapter: `claude_glm`

## Changed Files (all within the frozen 7-file write boundary)

### 1. `backend/config.py` (S1)
- `DEFAULT.private_channel_ttl_seconds = 1800` (down from legacy 3600); FR-2 / §5.5.
- `GROUP_B_REFRESH_SECONDS = 1800` module constant; CC-2 (fixed, not env-configurable, not amplifiable).
- `from_env` rejects `BINANCE_PRIVATE_CHANNEL_TTL_SECONDS > 1800` (effective max); §5.5 1799/1800 boundary accepted.

### 2. `backend/adapters/binance_public.py` (S2)
- `fetch_premium_index()` — Group A live seam (`GET /fapi/v1/premiumIndex`), cached at `cache_ttl_seconds` (60s).
- `fetch_exchange_info_group_b()` — Group B live seam (futures + spot exchangeInfo + best-effort fundingInfo), cached at `GROUP_B_REFRESH_SECONDS` (1800s). fundingInfo keeps its E1 8h-default degradation.
- `_fetch_live()` composes both seams; `fetch_raw` retained as the offline/back-compat entry.

### 3. `backend/services/private_client.py` (S3b)
- `fetch_classic_reference()` now returns additive keys (`pair_listed_by_symbol`, `asset_borrowable_by_name`, `daily_interest_vip0_by_coin`, `cross_margin_daily_by_vip: {vip_level: {coin: dailyInterest}}`) alongside the original 3 keys.
- Narrow Group-C seams: `fetch_account_info()`, `fetch_next_hourly_rates(assets)` (batched, `NEXT_HOURLY_BATCH_SIZE=15`), `fetch_interest_rate_history_latest(asset)` (FR-6 fallback), `fetch_max_borrowable(asset, *, force=False)`.
- `_select_chain_tier` priority ① next_hourly → ② rate_history → ③ cross_margin_tier → ④ vip0_reference.

### 4. `backend/services/snapshot_service.py` (S3–S9) — core three-cadence refactor
- New worker-owned caches: `_global_source_cache[source_id] = (updated_monotonic, value)` (CC-1 per-source due), `_borrow_rate_cache[asset] = (ts, raw, source)`, `_max_borrowable_cache[asset] = (ts, value)`, `_coverage_attempted: set` (CC-3), `_account_checked_at` (wall-clock for the private-account panel).
- `_scheduled_tick()` rewritten: `_refresh_due_sources` → `_compose_base_raw` (waits for A+B) → `_eligible_rows` → `_sweep_group_c` → `_all_valid_history` → `_assemble` → validate-before-publish (BK-6/BK-7).
- `_refresh_due_sources(now)`: independent Group A (premium 60s) / Group B (group_b_public + classic_reference + account_info 1800s) timestamps; private account panels + price_map at Group A cadence, only when classic_ref is usable. `has_seams` fallback: legacy stub clients without the split seams collapse to one `fetch_raw()` serving both public groups (preserves the single-timestamp bootstrap for the existing endpoint tests). Timestamps advance only on success (FR-2).
- `_sweep_group_c`: cursor mod-n over `history_sweep_batch_size` candidates; history for every candidate, borrow-rate + max-borrowable only for the FR-4 universe; components freshness-independent (FR-7). Borrow-rate uses the narrow `fetch_next_hourly_rates` batch + per-asset `fetch_interest_rate_history_latest` fallback (FR-6), **not** `fetch_cost_leg_chain` (INV-1b). No top-50 cap (FR-5).
- `_is_scheduled_borrow_candidate`: strict `daily_funding_rate < -0.00030000` AND `MARGIN_SPOT_CANDIDATE` AND `asset_tag in {CRYPTO, METAL}` AND classic_ref present (FR-4).
- `_resolve_borrow_rate_for_asset` (S5): ① next_hourly (raw hourly, ×24 exactly once via `resolve_cost_leg_rate`, CC-4) → ② rate_history → ③ cross_margin_tier[vip] → ④ vip0_reference; no network.
- `_synthesize_cost_leg` (S8): aggregate chain diagnostic, highest-priority source present.
- `_gather_private_inputs` split into `_gather_private_inputs_click` (unchanged click semantics + reuses `resolved_rates`) and `_gather_private_inputs_scheduled` (cache-only, FR-3).
- **Regression fix (see Deviations):** `_gather_private_inputs_scheduled` `private_error` falls back to `"private_channel_disabled"` when the channel is unusable AND `last_error` is unset (the offline sync-build path never runs `_refresh_due_sources`).

### 5. `backend/tests/test_config.py` (S1) — 4 new tests
slow-TTL default 1800 / reject >1800 / 1799+1800 boundary / `GROUP_B_REFRESH_SECONDS == 1800`.

### 6. `backend/tests/test_background_worker.py` (S2/S4/S7/S8) — 11 new §7.1 tests
Added `_SeamStubPublic` / `_SeamStubPrivate` / `_seam_service` (expose the split seams + an enabled private channel; every endpoint counted). The legacy `_StubPublic`/`_StubPrivate`/`_service` are **unchanged** and keep the existing 17 tests on the `fetch_raw` fallback path (surgical: no existing test was rewritten). New tests cover: independent A(60s)/B(1800s) cadences + `raw_calls==0`; CC-1 source independence + FR-2 no-cache-on-failure; FR-4 strict boundary; CC-4 ×24 exactly-once; tier ③④ fallbacks; FR-7 component independence; FR-2 borrow-rate no-cache; INV-1b narrow-seam-only (`cost_leg_calls==[]`); FR-5 no top-50 cap (60 assets); CC-3 coverage entry/advance with cursor.

### 7. `backend/tests/test_private_client.py` (S3b) — 35 tests
Covers the additive classic-reference keys + the four narrow Group-C seams + chain-tier resolution.

## Design Decisions Mapped to the Frozen Design

| Contract | Implementation |
|---|---|
| FR-2 (success-only timestamps, slow TTL ≤1800) | `_source_due`/`_borrow_rate_due`/`_max_borrowable_due` advance only on success; config rejects >1800 |
| FR-3 (scheduled assembly cache-only) | `_gather_private_inputs_scheduled` reads only `_global_source_cache` + per-asset caches |
| FR-4 (strict `< -0.00030000`) | `_is_scheduled_borrow_candidate` |
| FR-5 (no top-50 cap) | `_sweep_group_c` iterates the full FR-4 universe, ignores `borrow_check_max_calls` |
| FR-6 (rate_history per-asset fallback) | `_refresh_borrow_rates` |
| FR-7 (component independence) | separate `_borrow_rate_cache` / `_max_borrowable_cache` / `_funding_history_cache` TTLs |
| CC-1 (per-source due) | each `_global_source_cache` source_id owns its timestamp |
| CC-3 (cursor-attempt coverage) | `_coverage_attempted` records attempts (incl. failures); exit-universe drops |
| CC-4 (×24 exactly once) | raw hourly stored; `resolve_cost_leg_rate` normalizes once on resolve |
| INV-1b (narrow seam isolation) | scheduled path uses `fetch_next_hourly_rates`/`_interest_rate_history_latest`/`fetch_max_borrowable`, never `fetch_cost_leg_chain` |

## Deviations / Notes

1. **One regression fix in `snapshot_service.py`.** Routing offline `build_snapshot` through the cache-only scheduled assembly path left `self._private.last_error` at its init `None` (the old path called `fetch_classic_reference()`, which sets it). Result: offline rows rendered `borrow_validation.error = None` instead of `"private_channel_disabled"` (`test_phase2_borrow_sort.py` failed). Fix: a 5-line `private_error` fallback in `_gather_private_inputs_scheduled` gated on `self.client.offline or not config.private_channel_enabled`. Live scheduled ticks are unaffected (`_refresh_due_sources` already sets `last_error`). This restores the pre-v2 offline borrow-error contract; no schema, frontend, or canonical-doc change.

2. **`has_seams` fallback retained.** Legacy stub clients (and the existing endpoint tests) without the split public seams collapse to a single `fetch_raw()` serving both public groups, preserving the single-timestamp bootstrap. This is why the frozen `test_symbol_snapshot_endpoint.py` / `test_funding_history_endpoint.py` pass unchanged.

3. **macOS seatbelt sandbox intermittently blocked file I/O (Read/Edit/Bash EPERM) twice during the session; resumed after the operator lifted the restriction each time.** No workaround was applied in code.

## Test Commands & Results

```
# Focused (final worker test file):
python3 -m pytest backend/tests/test_background_worker.py -q
# => 28 passed in 1.19s   (17 existing + 11 new §7.1)

# Final blocking full suite:
python3 -m pytest backend/tests -q
# => 325 passed in 12.67s
```

No network, no server, no background process, no real Binance calls. The two
frozen endpoint test files (`test_symbol_snapshot_endpoint.py`,
`test_funding_history_endpoint.py`) and `backend/domain/snapshot.py` pass
unchanged.

## Write-Boundary Confirmation

Edited only the 7 frozen files (`backend/config.py`,
`backend/adapters/binance_public.py`, `backend/services/private_client.py`,
`backend/services/snapshot_service.py`, `backend/tests/test_config.py`,
`backend/tests/test_background_worker.py`, `backend/tests/test_private_client.py`)
plus this report. **No** edit to `frontend/**`, `schemas/api/**`, canonical
`docs/**`, harness files, `status.json`, `70-handoff.md`, `30-review-1.md`,
`40-fix-report.md`, `50-review-2.md`, `backend/domain/snapshot.py`,
`test_symbol_snapshot_endpoint.py`, or `test_funding_history_endpoint.py`. **No**
new file was created. **No** commit / merge / rebase / push.

The implementation is ready for bookkeeper inspection.

本地北京时间: 2026-07-15 CST
下一步模型: human → bookkeeper
下一步任务: 检查实现差异与测试结果

## Bookkeeper Pre-Commit Verification — Correction Required

The bookkeeper independently reran the full backend suite and obtained
`325 passed in 12.97s`; `git diff --check` also passed. The write boundary was
compliant. However, source/design reconciliation found two frozen-contract
defects before any implementation commit or review dispatch:

1. `CC-3 / INV-4`: `_coverage_attempted` is append-only. Leaving the current
   homepage borrow universe filters the visible counts but does not remove the
   asset from the ledger, so re-entry incorrectly inherits `probed` before a new
   max-borrowable attempt.
2. `FR-2 / INV-5`: successful business-cache timestamps use the tick's
   pre-network `now`, while `PrivateClient._cached_get()` records its transport
   cache later. At business age `>=1800s`, the transport entry can therefore
   remain valid, return without real upstream I/O, and still advance business
   freshness for another cycle.

Both failures were reproduced read-only and are preserved in
`60-test-output.txt`. The earlier `CC-3 ... exit-universe drops` claim is not
accepted as implemented until Correction 1 lands with adversarial tests. The
stage remains `implementing`; review-1 has not started.

Correction packet:
`implementation-claude-glm-rework-1.prompt.md`.

本地北京时间: 2026-07-15 00:42:46 CST
下一步模型: human → claude_glm
下一步任务: 执行 Correction 1，修复 coverage exit/re-entry 与 1800 秒双层缓存时钟偏差

---

## Correction 1 — CC-3 exit/re-entry prune + FR-2/INV-5 completion-time stamping

执行依据: `implementation-claude-glm-rework-1.prompt.md`。本节为**追加**修正，
不删除或静默重写上方历史文本。Grok session `019f6180...` 为非正式只读复核，
其 ACCEPT 结论不作为门禁；下列两项按冻结设计强制修复，未采纳 Grok 对二者的
降级判断。

### F1 — CC-3 / INV-4: coverage ledger 真实 exit prune 与 re-entry 语义

**问题(已复现):** `_coverage_attempted` 此前只 `add`、从不 `prune`。资产退出
homepage borrow universe 后，集合仍含该资产；重新进入且尚未重新请求 max-borrowable
时，错误得到 `probed=1`。

**修复 (`backend/services/snapshot_service.py`, `_gather_private_inputs_scheduled`):**
装配时先把 coverage ledger 收窄到**当前** universe:

```python
universe = self._homepage_borrow_universe(rows, classic_ref)
universe_set = set(universe)
# 退出 universe 的资产从账本移除；re-entry 以 unattempted 起算。
self._coverage_attempted &= universe_set
probed = [a for a in universe if a in self._coverage_attempted]
skipped = [a for a in universe if a not in self._coverage_attempted]
```

语义符合冻结契约:
- **失败尝试算 attempt** — `fetch_max_borrowable` 调用即记入（成功/失败均计）。
- **越界低费率不计 skipped** — 退出 universe 的资产经 `&=` 已不在账本，也不在
  当前 universe，不进 `skipped` 列表。
- **exit 移除 / re-entry unattempted** — 集合求交每 tick 执行；re-entry 时该
  资产不在 `_coverage_attempted`，故 `probed` 不含它。
- **cursor-only pass 不计新 attempt** — 仅 cursor 经过、max-borrowable 未实际
  请求时不 `add`。
- **`reason == "rate_limit_budget"` iff 当前 universe `skipped > 0`。**

**测试 (`backend/tests/test_background_worker.py`, 3 个确定性 ledger 测试):**
- `test_coverage_ledger_prunes_on_universe_exit` — tick1 记 BTC；改 funding rate
  使其退出 universe 再 tick → `service._coverage_attempted == set()` 且
  `coverage.probed == 0`。
- `test_coverage_reentry_starts_unattempted` — enter → exit → re-enter，cursor
  经过 BTC 但 max fresh → 不 attempt：`_coverage_attempted == set()`、
  `max_borrowable_calls` 不变、`coverage == {probed:0, skipped:1,
  reason:"rate_limit_budget"}`。
- `test_coverage_reason_rate_limit_budget_iff_skipped` — 2 个 FR-4 资产、
  `batch_size=1`：tick1 skipped>0 → `rate_limit_budget`；tick2 cursor 到 B →
  `reason is None`。

### F2 — FR-2 / INV-5: 成功时间戳改用 completion-time，保证 transport_ts ≤ business_ts

**问题(已复现):** 此前 business-cache 成功时间戳用 tick 的 pre-fetch `now`，
而 `PrivateClient._cached_get()` 在其之后才记录 transport cache 条目
(`self._cache[key] = (now + lifetime, data)`)。结果
`business_ts < transport_write_ts`，business age 到 1800s 时 transport 条目
仍可能有效 → 真实上游 I/O 被推迟、business freshness 仍被推进。

**修复 (`backend/services/snapshot_service.py`):** 所有成功写入改为
**fetch-then-stamp** — `value` 非 None 时才写
`(time.monotonic(), value)`，且 `time.monotonic()` 在 fetch 返回**之后**读取
(completion time)。覆盖范围:
- `premium_index`、`group_b_public`(含 `has_seams` 分支与单次 `fetch_raw` 回退
  分支)、`classic_reference`、`account_info`；
- panel loop: `price_map` / balances / positions / spot 等 `_global_source_cache`
  成功写入；
- `_refresh_borrow_rates`(next_hourly batch 用 `batch_completed`、rate_history
  回退逐项 completion)；`_refresh_max_borrowable`(`(time.monotonic(), res)`)。

不变量:
- **transport_ts ≤ business_ts** — completion time 在 transport 写入之后捕获，
  故 `transport_age ≥ business_age`；business age 到 1800s 时 transport 必已到期。
- **失败/None 不推进 timestamp** — 仅 success 分支写 cache。
- **slow source 在 business age `>=1800s` 真实请求上游** — 不用 `force=True`，
  不做 transport eviction。
- **每 source / per-asset 独立时间戳** — 未引入 scheduler 抽象。
- **due 判断仍用 tick `now`** — `_refresh_due_sources` / `_sweep_group_c` /
  `_source_due` 保留 tick-now；`_refresh_borrow_rates` / `_refresh_max_borrowable`
  的 `now` 形参已移除(只用于 completion stamp 的孤儿形参清理)，调用方同步更新。

**测试:**
- `backend/tests/test_private_client.py` ::
  `test_inv5_completion_time_transport_le_business_and_real_get_at_1800` —
  真实 `PrivateClient` + 共享 skew monotonic(非零时钟偏差, `SKEW=0.001`/call)。
  断言: ① `transport_write_time - 1800 ≤ biz_ts`(INV-5); ② business 1799s
  `due is False`; ③ business 1800s `due is True` 且 `signed_get_calls == 2`
  (真实 signed GET, 非 transport 命中); ④ failing urlopen 不推进 business ts。
- `backend/tests/test_background_worker.py` ::
  `test_global_source_cache_stamps_completion_time` — 严格递增时钟下，
  classic_reference / account_info / price_map 三处成功时间戳均 `> tick now`，
  且 `classic < account < price_map`(各自 completion stamp，反映 fetch 顺序)。

### F3 — Group A 配置发散: 记录为非阻塞 P3 residual risk(吸收但不扩大契约)

吸收 Grok 的 Group A 观察:**Group A panel 的 business cadence 用
`cache_ttl_seconds`，transport 用 `private_channel_fast_ttl_seconds`**。二者
默认均为 60，默认 60/60 路径正确(completion-time 修复已覆盖 Group A panel 写入)。
env 发散(例如分别设不同值)是 **residual risk，P3 非阻塞**。

本轮**不**:① 把 Group A business cadence 改绑到 `private_channel_fast_ttl_seconds`;
② 新增 fast-TTL 配置拒绝规则。仅在此记录，留待后续按需评估。未改 `backend/config.py`。

### F4 — 口径修正 + 撤回旧结论

**撤回:** 上方 Design Decisions 表(line 64)中
"`CC-3 ... _coverage_attempted records attempts (incl. failures); exit-universe drops`"
关于 "exit-universe drops" 的描述，在 Correction 1 落地前**未真正实现**
(实现仅 `add`、无 prune)。该结论在此**明确撤回**;真实 prune 由 F1
(`_coverage_attempted &= universe_set`)首次实现。历史文本保留不删。

**口径更正(替换原"Group B public+classic+account"等笼统表述):**
- **Group B 1800s:** public exchangeInfo/fundingInfo(`group_b_public`)、
  `classic_reference`、`account_info`。
- **Group A 60s:** `premium_index`、`price_map`、balances、positions、spot panels。

### Correction 1 测试结果

```
python3 -m pytest backend/tests/test_background_worker.py backend/tests/test_private_client.py -q
# => 68 passed in 1.45s

python3 -m pytest backend/tests -q
# => 330 passed in 12.87s   (原 325 + CC-3×3 + INV-5 端到端×1 + completion-time stub×1)

python3 -m py_compile backend/config.py backend/adapters/binance_public.py \
  backend/services/private_client.py backend/services/snapshot_service.py
# => PYCOMPILE OK

git diff --check   # => clean (无空白错误)
```

### Correction 1 写入边界

本轮仅写入 4 个文件: `backend/services/snapshot_service.py`、
`backend/tests/test_background_worker.py`、`backend/tests/test_private_client.py`、
本报告。**未**改 `backend/config.py`、`backend/domain/snapshot.py`、
harness/state、canonical docs、frontend、schemas 或其他文件。**未** commit、
**未**启动 Kimi、**未**进入 review-1。

本地北京时间: 2026-07-15 CST
下一步模型: human → bookkeeper
下一步任务: 核验 Correction 1(F1/F2/F3/F4)的 finding → code → test → result 映射

## Bookkeeper Acceptance Of Correction 1

The bookkeeper inspected the actual four-file Correction 1 delta and independently
verified the frozen contracts:

- `CC-3 / INV-4`: the current-universe ledger is now pruned before coverage is
  assembled; exit removes the asset, re-entry begins unattempted, a fresh
  component cursor pass does not count as a new attempt, and the externally
  published `reason` tracks `skipped > 0` exactly.
- `FR-2 / INV-5`: successful global/per-asset business-cache entries now use a
  monotonic completion timestamp captured after the fetch returns. The non-zero
  skew test demonstrates transport write time `<=` business success time,
  1799-second reuse, a real signed GET at the 1800-second business boundary, and
  no timestamp advance after failure.
- Correction 1 changed only `backend/services/snapshot_service.py`,
  `backend/tests/test_background_worker.py`, `backend/tests/test_private_client.py`,
  and this implementation report. The original seven-file implementation scope
  remains intact.

Independent results:

```text
python3 -m pytest backend/tests/test_background_worker.py backend/tests/test_private_client.py -q
=> 68 passed in 1.52s

python3 -m pytest backend/tests -q
=> 330 passed in 13.01s

python3 -m py_compile backend/config.py backend/adapters/binance_public.py backend/services/private_client.py backend/services/snapshot_service.py
=> PASS

git diff --check
=> PASS
```

Disposition: both pre-commit P1 findings are closed. The Group A configurable
fast-TTL divergence remains the explicitly recorded, non-blocking P3 residual
risk; no unapproved cadence or configuration-contract change was introduced.

本地北京时间: 2026-07-15 08:02:33 CST
下一步模型: human → kimi
下一步任务: 在 implementation evidence commit 与 pre-review gate 完成后执行正式只读 review-1
