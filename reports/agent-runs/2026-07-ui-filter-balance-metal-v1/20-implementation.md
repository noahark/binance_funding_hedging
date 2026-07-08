# Implementation Report — 2026-07-ui-filter-balance-metal-v1

- Implementer identity: `claude_glm / zhipu_glm`
- Role: serial implementation author only (no commit)
- Branch: `stage/2026-07-ui-filter-balance-metal-v1`
- Starting HEAD: `f2b20ed00aecd2e710e393cfb4c61d6b518d3578` (`bookkeeper(…): 派发 serial implementation`)
- All changes below are uncommitted on top of that HEAD, per the completion contract; the bookkeeper inspects `git diff`, commits, computes the fingerprint, and dispatches review-1.

## Files Changed

9 files, all within the prompt's allowed-product-files list (`git diff --stat HEAD`):

```
 backend/domain/normalize.py                    |  26 ++++-
 backend/domain/snapshot.py                     |  16 +--
 backend/tests/test_normalize.py                |  33 ++++++
 backend/tests/test_snapshot.py                 | 120 ++++++++++++++++++++-
 docs/api/public-market-contract.md             |  82 ++++++++++++++-
 frontend/fixture/public-market-snapshot.json   |  48 ++++++++-
 frontend/index.html                            |  71 +++++++++++--
 frontend/self-check.js                         | 140 +++++++++++++++++++++----
 schemas/api/public-market/snapshot.schema.json |   1 +
 9 files changed, 492 insertions(+), 45 deletions(-)
```

No file outside the allowed list was touched. `backend/tests/test_private_account_v1.py` and `backend/tests/fixtures/private-account-v1-design.json` were left unchanged: the balance-value assertions needed by R2 self-check are applied at runtime inside `frontend/self-check.js` (deep-copy fixtures set `value_usdt`), so the shared design fixture's default six-row semantics are preserved (no baseline churn, per prompt §8).

## Implementation Summary by Requirement

### R1 — low-daily-rate filter (frontend, no float)

- `frontend/index.html` adds a default-ON checkbox immediately after `filter-show-perp-only`:
  `<input id="filter-hide-low-daily-rate" type="checkbox" checked /> 隐藏 |日费率| ≤ 0.03%`
- `els.filterHideLowDailyRate` binding; `state.filters.hideLowDailyRate = true`; a `change` listener updates state and re-renders (table + summary).
- New helper `absDailyRateAtOrBelowThreshold(rateStr)` exposed via `globalThis.__appHelpers`. The threshold comparison is **pure string/BigInt**: it parses `(-?)(\d+)(\.(\d+))?`, scales the absolute value and the threshold `0.00030000` (= `30000 × 10^(scale-8)` at `scale = max(fracLen, 8)`) into `BigInt`, and compares. **No `Number()` / `parseFloat()` touches the threshold comparison** (avoids float boundary drift).
- Semantics: `null`/`undefined`/`''`/invalid → `false` (never hidden by this filter); `0.00030000` and `-0.00030000` → `true` (boundary inclusive); `0.00030001` and `-0.00030001` → `false`.
- Applied in `filteredRows()` after the existing route/PERP filters: `if (state.filters.hideLowDailyRate && absDailyRateAtOrBelowThreshold(row.daily_funding_rate)) return false;`

### R2 — balance card three-line layout (frontend)

- Removed the old inline `【: ... USDT】` suffix (`inlineUsdtSuffix`).
- New helpers `formatBalanceAmount(value)` and `approximateUsdtLine(valueUsdt)`:
  - `formatBalanceAmount`: privacy-hidden → `****`; otherwise delegates to `formatPrice` (thousands separators on the integer part only, raw fractional string preserved exactly — no rounding, no trailing-zero trim); invalid/missing → `—`.
  - `approximateUsdtLine`: hidden → `≈ **** USDT`; `null`/invalid → `≈ — USDT`; valid → `≈ ${formatUsdt2(value)} USDT` (so `0.00000000` → `≈ 0.00 USDT`).
- Unified balance card now renders asset / `<div class="amount">` / `<div class="amount value-usdt">≈ … USDT</div>` (three lines). Spot card renders `free` as the amount line, a separate `<div class="amount locked">冻结: …</div>` line, and its own `≈ … USDT` line.

### R3 — METAL asset tag (backend + schema + docs + frontend)

- `backend/domain/normalize.py`: added `REAL_METAL_BASE_ASSETS = {"XAU", "XAG", "COPPER", "XPT", "XPD"}`; `asset_tag_for(contract_type, base_asset="")` checks the metal `baseAsset` (case-insensitive) BEFORE the `TRADIFI_PERPETUAL -> BSTOCK` mapping → returns `("METAL", "base_asset_metal_symbol", "HIGH")`. The default `base_asset=""` preserves the single-argument contract for existing callers/tests.
- `backend/domain/snapshot.py`: `build_rows()` passes `obj.get("baseAsset", "")` into `asset_tag_for`. `select_borrow_candidates()` candidate predicate widened from `asset_tag == "CRYPTO"` to `asset_tag in ("CRYPTO", "METAL")`; docstring updated to `{CRYPTO, METAL}`. Every other condition/behavior (negative daily rate, `MARGIN_SPOT_CANDIDATE`, de-dupe by `base_asset`, abs-daily-DESC/symbol-ASC sort, uncapped rate probe, capped borrowability probe, `borrowability_not_probed`) is unchanged.
- `schemas/api/public-market/snapshot.schema.json`: `asset_tag.enum` gains `METAL` → `["CRYPTO", "BSTOCK", "METAL", "UNKNOWN"]`. No `DISABLED_METAL` added to `negative_funding_status`.
- `docs/api/public-market-contract.md`: enum list gains `METAL`; new "METAL Asset Tag + UI Amendments (v0.5)" section documents priority-over-BSTOCK, `base_asset_metal_symbol`, evidence path, no-`DISABLED_METAL`, probe-range widening to `{CRYPTO, METAL}`, R1 (no-float filter) and R2 (three-line card) semantics; inline priority-chain note clarifies `METAL` is not a structural disable.
- `frontend/index.html`: `<option value="METAL">METAL(金属)</option>` added to the asset-tag filter; `badgeForAssetTag("METAL")` → `METAL(金属)` with the neutral badge class (`''`, not bStock `accent` / not `danger`).
- `frontend/fixture/public-market-snapshot.json`: added an evidenced `XAUUSDT` row (`asset_tag=METAL`, `base_asset_metal_symbol`, `contract_type=TRADIFI_PERPETUAL`, no spot leg → `PERP_ONLY_EXCLUDED` / `DISABLED_PERP_ONLY`, `ui_flags=[MARGIN_PUBLIC_UNVERIFIED, PERP_ONLY_NO_SPOT_LEG]` — no `TRADIFI_BSTOCK`); summary counts updated to `total_rows=7`, `PERP_ONLY_EXCLUDED=3`, `asset_tag_counts +METAL:1`, `DISABLED_PERP_ONLY=3`. Fixture validated against the schema and count self-consistency.

## METAL Semantics (exact notes)

- A metal `baseAsset ∈ {XAU, XAG, COPPER, XPT, XPD}` is checked BEFORE the `TRADIFI_PERPETUAL -> BSTOCK` mapping, so a metal that ships as `contractType=TRADIFI_PERPETUAL` (all five do — evidence `reports/api-samples/2026-07-ui-filter-balance-metal-v1/20260708T0928Z/normalized/metal-symbol-summary.json`) is tagged `METAL`, never `BSTOCK`.
- There is **no `DISABLED_METAL`**. `METAL` is a product tag, not a borrow prohibition; a `METAL` candidate row falls through the unchanged `negative_funding_status` priority chain to `PRIVATE_BORROW_VALIDATION_REQUIRED` (verified: `negative_funding_status("MARGIN_SPOT_CANDIDATE", "METAL") == "PRIVATE_BORROW_VALIDATION_REQUIRED"`, no `classify.py` change needed).
- An eligible `METAL` row (`MARGIN_SPOT_CANDIDATE` + negative daily rate) now enters `rate_probe_assets` / `borrowability_probe_assets`; its borrowability and borrow cost come from the private read-only borrow-validation interface (the tag never implies borrowability). The runtime probe loop in `backend/services/snapshot_service.py` consumes the candidate set directly with no `asset_tag` re-filter, so the single predicate widening closes the loop.
- In the current public sample none of the five metals has a public exact or B-suffix spot leg, so they resolve `PERP_ONLY_EXCLUDED` / `DISABLED_PERP_ONLY`. bStock remains disabled for negative-funding arbitrage (`BSTOCK` still excluded from borrow candidates).

## Tests Run

### `python3 -m pytest backend/tests -q`

```
........................................................................ [ 41%]
........................................................................ [ 83%]
.............................                                            [100%]
173 passed in 4.20s
```

New backend tests added: `test_normalize.py` (+4: metal baseAsset on PERPETUAL, metal priority over TRADIFI/BSTOCK, case-insensitive, single-arg callers still work); `test_snapshot.py` (+5: metal no-spot-leg → PERP_ONLY_EXCLUDED/DISABLED_PERP_ONLY, metal margin-spot candidate enters borrow candidates, bStock stays excluded, METAL+CRYPTO compose deduped/sorted, METAL snapshot row validates schema). Existing bStock tests (`TSLA/AAPL` alias, DISABLED_BSTOCK) are unchanged and still pass.

### `node frontend/self-check.js`

45 `[PASS]` assertion lines, ending `全部自检通过` (exit 0). New/rewritten assertion groups for this stage:

```
[PASS] 余额卡片三行折算值与隐私遮蔽          (R2: no 【:, ≈ **** / ≈ 123.45 / ≈ 67.89)
[PASS] value_usdt null 显示占位              (R2: ≈ — USDT)
[PASS] value_usdt 合法零显示占位             (R2: ≈ 0.00 USDT)
[PASS] 余额数量整数千分位、小数原样保留       (R2: >1,234.56789000< / >123,456.07890000<)
[PASS] absDailyRateAtOrBelowThreshold 阈值边界（BigInt）   (R1: 7 boundary cases)
[PASS] 低日费率过滤 UI 行为（边界隐藏/超界保留/null 不过滤）(R1: deep-copy scenario)
[PASS] METAL 资产标签徽章与下拉选项          (R3: METAL(金属) neutral badge + <option>)
```

The legacy 6-row baseline is preserved by turning the new filter OFF for the legacy section (design fixture `CUSDT.daily_funding_rate == "0.00030000"` sits exactly on the boundary and would otherwise drop 6→5); the default-ON filter behavior is covered independently by the deep-copy scenario (prompt §6.2 / design-review option B).

## Grep / Audit Results

### Audit 1 — forbidden symbols / old suffix

```text
rg -n "DISABLED_METAL|METAL\(贵金属\)|base_asset_precious|【:" backend frontend docs schemas reports/agent-runs/2026-07-ui-filter-balance-metal-v1/20-implementation.md
```

All matches are **legitimate references to absence**, not implementations:

- `frontend/self-check.js:747,749,750` — the #35 assertion that the OLD `【:` format is gone (`if (privateBody2.includes('【:')) throw …`).
- `docs/api/public-market-contract.md:104,277,576` — explicit "there is **no** `DISABLED_METAL`" statements.
- `docs/api/public-market-contract.md:603` — R2 narrative "switch from the inline `【: … USDT】` suffix".

No `DISABLED_METAL` value, no `METAL(贵金属)`, no `base_asset_precious`, no live `【:` rendering exists. (`20-implementation.md` itself also matches — by design, since the audit command searches it and this report reproduces those terms in its own audit narrative; those are documentation, not code.)

### Audit 2 — float usage in `frontend/index.html`

```text
rg -n "parseFloat\(|Number\(" frontend/index.html
```

```
817:  const n = Number(str);                       // formatPrice: validity (NaN) gate only
820:  Number(intPart).toLocaleString('en-US');     // formatPrice: thousands-sep on INTEGER part only
846:  const n = Number(str);                       // formatUsdt2: validity (NaN) gate only
1023: // … no Number()/parseFloat() touches the threshold comparison …   (comment in helper)
1024: // … (comment in helper)
1084: const amt = Number(pos.position_amt);        // UM position direction badge (pre-existing, out of R1/R2/R3 scope)
```

Confirmed: no `Number()`/`parseFloat()` is used in the low-rate threshold helper. `absDailyRateAtOrBelowThreshold` (lines 1022–1039) is pure string/BigInt. The remaining `Number()` uses are display-only validity gates / integer thousands-separation in `formatPrice` and `formatUsdt2` (R2 amount/value formatting; the integer-only `toLocaleString` cannot lose fractional precision because the fractional substring is appended verbatim), plus one pre-existing position-amount read unrelated to this stage.

## Deviations From Allowed Files

One known item, disclosed because the file is **not** in the allowed list and was therefore left untouched:

- `backend/services/snapshot_service.py` has two now-stale comments referencing the old CRYPTO-only predicate:
  - `:132` — `# §1.5 borrow probe sets (neg funding + MARGIN_SPOT_CANDIDATE + CRYPTO, …`
  - `:182` — `# excluded upstream (asset_tag != CRYPTO); their portfolio_account amount …`
  - The **code** at `:185` iterates `borrowability_probe_assets` directly (the candidate set from `select_borrow_candidates`) with no `asset_tag` re-filter, so behavior is correct; only the comments are inaccurate (should read `{CRYPTO, METAL}`). Suggested follow-up for the bookkeeper/reviewer: update the two comments. No functional risk.

No other out-of-scope file was modified; no scope was expanded silently.

## Residual Risk

- **METAL spot-leg scenario is synthetic.** The public sample has no metal spot leg, so `PERP_ONLY_EXCLUDED` is the only evidenced runtime path; the `MARGIN_SPOT_CANDIDATE` metal → borrow-candidate path is exercised by constructed fixtures (`test_metal_margin_spot_candidate_enters_borrow_candidates`, `test_metal_and_crypto_compose_in_borrow_candidates`). It will only fire live if Binance later lists a metal spot/margin pair.
- **Frontend demo fixture `XAUUSDT` mark/index/last_funding_rate are illustrative** (the metal sample captured only `exchangeInfo` + spot-query, not `premiumIndex`); the METAL-relevant fields (`baseAsset=XAU`, `contractType=TRADIFI_PERPETUAL`, no spot leg → `PERP_ONLY_EXCLUDED`/`DISABLED_PERP_ONLY`, `asset_tag=METAL`) are evidenced. This fixture is not the Node self-check source.
- **`snapshot_service.py` comment drift** (above) — non-functional; tracked for a follow-up touch-up.

---

本地北京时间: 2026-07-08 10:45:49 CST
下一步模型: bookkeeper/codex
下一步任务: 冻结实现 diff，计算 fingerprint，进入 review-1（Kimi）。
