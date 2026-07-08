# Serial implementation prompt — 2026-07-ui-filter-balance-metal-v1

你是 `stage/2026-07-ui-filter-balance-metal-v1` 的 serial implementer。

Provider identity: `claude_glm` / `zhipu_glm`。  
角色: implementation author only。  
Bookkeeper: Codex/OpenAI 当前会话。  
Review-1 reviewer: fresh Kimi session (`moonshot_kimi`) after bookkeeper freezes the committed diff.

## 0. Hard Rules

Read and obey:

- `AGENTS.md`
- `agents/developer-discipline.md`
- `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/00-task.md`
- `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/10-design.md`
- `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/11-adr.md`
- `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/12-development-breakdown.md`
- `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/15-requirements-review.md`
- `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/16-design-review.md`
- `reports/api-samples/2026-07-ui-filter-balance-metal-v1/20260708T0928Z/normalized/metal-symbol-summary.json`

Do not commit. The bookkeeper will commit, compute the fingerprint, and dispatch review-1.

Do not modify:

- `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/status.json`
- `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/70-handoff.md`
- review files
- private signing, order, borrow, repay, transfer, or key-management code

Allowed product/report files:

- `backend/domain/normalize.py`
- `backend/domain/snapshot.py`
- `backend/tests/test_normalize.py`
- `backend/tests/test_snapshot.py`
- `backend/tests/test_private_account_v1.py`
- `backend/tests/fixtures/private-account-v1-design.json`
- `schemas/api/public-market/snapshot.schema.json`
- `docs/api/public-market-contract.md`
- `frontend/index.html`
- `frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json`
- `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/20-implementation.md`

If you need a file outside this list, stop and report the exact reason in `20-implementation.md`; do not expand scope silently.

Red lines:

- No placing orders.
- No borrow/repay/transfer calls.
- No private write endpoints.
- No credential logging or environment dumps.
- No float-based threshold logic for the low-rate filter.
- No `DISABLED_METAL`.
- bStock remains disabled for negative funding arbitrage.

## 1. Goal

Implement one serial diff that can be frozen by the bookkeeper and sent directly to review-1:

1. Frontend market table gets a default-on filter after `显示 PERP_ONLY_EXCLUDED`: `隐藏 |日费率| ≤ 0.03%`.
2. Private account balance cards change from inline suffix `【: ... USDT】` to separate amount + approximate USDT lines.
3. Backend/schema/docs/frontend add `asset_tag="METAL"` for `XAU/XAG/COPPER/XPT/XPD` and keep borrowability determined by private read-only API results.

## 2. Public Sample Evidence You Must Respect

Evidence path:

- `reports/api-samples/2026-07-ui-filter-balance-metal-v1/20260708T0928Z/raw/fapi-v1-exchangeInfo.json`
- `reports/api-samples/2026-07-ui-filter-balance-metal-v1/20260708T0928Z/raw/api-v3-exchangeInfo-metal-symbol-queries.json`
- `reports/api-samples/2026-07-ui-filter-balance-metal-v1/20260708T0928Z/normalized/metal-symbol-summary.json`

The summary shows current Binance public futures `exchangeInfo` contains:

- `XAUUSDT`, `baseAsset=XAU`, `contractType=TRADIFI_PERPETUAL`
- `XAGUSDT`, `baseAsset=XAG`, `contractType=TRADIFI_PERPETUAL`
- `XPTUSDT`, `baseAsset=XPT`, `contractType=TRADIFI_PERPETUAL`
- `XPDUSDT`, `baseAsset=XPD`, `contractType=TRADIFI_PERPETUAL`
- `COPPERUSDT`, `baseAsset=COPPER`, `contractType=TRADIFI_PERPETUAL`

Therefore `asset_tag_for()` must check metal `baseAsset` before the existing `TRADIFI_PERPETUAL -> BSTOCK` mapping. A metal future with `contractType=TRADIFI_PERPETUAL` is `METAL`, not `BSTOCK`.

Current spot exact and B-suffix alias probes for those metal symbols return invalid-symbol responses in the raw spot query file. That means current sample route may be `PERP_ONLY_EXCLUDED`, but the product decision is still: `METAL` is not a borrow prohibition. If a future metal row later has a `MARGIN_SPOT_CANDIDATE` route and negative daily rate, it must enter private borrow validation.

## 3. Backend Changes

### 3.1 `backend/domain/normalize.py`

Add:

```python
REAL_METAL_BASE_ASSETS = {"XAU", "XAG", "COPPER", "XPT", "XPD"}
```

Change `asset_tag_for` signature:

```python
def asset_tag_for(contract_type: str, base_asset: str = "") -> tuple:
```

Rules, in order:

1. If `base_asset.upper()` is in `REAL_METAL_BASE_ASSETS`, return:
   ```python
   ("METAL", "base_asset_metal_symbol", "HIGH")
   ```
2. Else `TRADIFI_PERPETUAL` stays:
   ```python
   ("BSTOCK", "futures_contractType_tradifi_perpetual", "HIGH")
   ```
3. Else `PERPETUAL` stays:
   ```python
   ("CRYPTO", "futures_contractType_perpetual", "HIGH")
   ```
4. Else `UNKNOWN` unchanged.

Keep the default parameter so existing single-argument tests and callers continue to work.

### 3.2 `backend/domain/snapshot.py`

In `build_rows()`, pass `obj.get("baseAsset", "")` into `asset_tag_for(contract_type, base_asset)`.

In `select_borrow_candidates()`:

- Change the candidate asset-tag condition from only `CRYPTO` to `CRYPTO` or `METAL`.
- Keep every other condition and behavior unchanged:
  - `daily_funding_rate` exists;
  - `route_class == "MARGIN_SPOT_CANDIDATE"`;
  - `Decimal(str(daily_funding_rate)) < 0`;
  - de-dupe by `base_asset`;
  - sort by absolute daily funding desc and symbol asc;
  - rate probe full set uncapped;
  - borrowability probe capped by `max_calls`;
  - unprobed assets use existing `borrowability_not_probed`.

Update the function docstring to say `asset_tag in {CRYPTO, METAL}`.

Do not change `negative_funding_status()` unless tests expose a real need. The intended result is:

```python
negative_funding_status("MARGIN_SPOT_CANDIDATE", "METAL") == "PRIVATE_BORROW_VALIDATION_REQUIRED"
```

## 4. Schema And Contract Docs

### 4.1 `schemas/api/public-market/snapshot.schema.json`

Add `METAL` to `rows[].asset_tag.enum`.

Do not add `DISABLED_METAL` to `negative_funding_status`.

### 4.2 `docs/api/public-market-contract.md`

Update:

- `asset_tag` enum list includes `METAL`.
- Asset-tag semantics describe:
  - `METAL` is selected by `baseAsset in XAU/XAG/COPPER/XPT/XPD`;
  - it is checked before `TRADIFI_PERPETUAL -> BSTOCK`;
  - `asset_tag_source = base_asset_metal_symbol`;
  - current public sample evidence path is `reports/api-samples/2026-07-ui-filter-balance-metal-v1/20260708T0928Z/`.
- `negative_funding_status` priority remains exactly:
  1. `PERP_ONLY_EXCLUDED` -> `DISABLED_PERP_ONLY`
  2. `asset_tag = BSTOCK` -> `DISABLED_BSTOCK`
  3. `SPOT_ONLY_CANDIDATE` -> `DISABLED_SPOT_ONLY`
  4. `MARGIN_SPOT_CANDIDATE` -> `PRIVATE_BORROW_VALIDATION_REQUIRED`
- Add explicit note: `METAL` is not a structural disable reason. Borrowability/cost for an eligible metal row is determined by private read-only borrow validation results.
- Update the borrow-validation candidate paragraph so it no longer says candidates are only `asset_tag=CRYPTO`; it should say `asset_tag in {CRYPTO, METAL}`. bStock remains excluded.

## 5. Frontend Changes

### 5.1 Low daily-rate filter

In `frontend/index.html`:

1. Add a new checkbox control immediately after `filter-show-perp-only`:

```html
<input id="filter-hide-low-daily-rate" type="checkbox" checked />
隐藏 |日费率| ≤ 0.03%
```

2. Add DOM binding in `els`.
3. Add `state.filters.hideLowDailyRate = true`.
4. Add a listener for the checkbox that updates state and rerenders table/summary.
5. Add helper exposed through `globalThis.__appHelpers`:

```js
absDailyRateAtOrBelowThreshold(rateStr)
```

Behavior:

- `null`, `undefined`, `''`, invalid decimal -> `false`.
- Valid decimal string -> compare absolute value to `0.00030000`.
- Inclusive boundary: `0.00030000` and `-0.00030000` return `true`.
- `0.00030001` and `-0.00030001` return `false`.
- Do not use `Number()` or `parseFloat()` for this threshold comparison. Use string parsing/comparison or an integer scaled representation.

6. Apply in `filteredRows()` after existing route/PERP filters:

```js
if (state.filters.hideLowDailyRate && absDailyRateAtOrBelowThreshold(row.daily_funding_rate)) return false;
```

`daily_funding_rate == null` must not be hidden by this filter.

Default-on behavior means existing self-check default 6-row baseline would drop to 5 because `CUSDT.daily_funding_rate == "0.00030000"`. Do not break existing baseline assertions. Use a dedicated deep-copy fixture scenario in self-check for the low-rate filter boundary.

### 5.2 Asset tag UI

In `frontend/index.html`:

- Add `<option value="METAL">METAL(金属)</option>` to asset-tag filter.
- `badgeForAssetTag("METAL")` renders `METAL(金属)` with a non-danger class. Do not use the bStock accent/danger style.
- Existing `CRYPTO/BSTOCK/UNKNOWN` display stays unchanged.

### 5.3 Balance card display

Replace the old `inlineUsdtSuffix(value_usdt)` behavior.

Add helpers:

```js
function formatBalanceAmount(value) { ... }
function approximateUsdtLine(valueUsdt) { ... }
```

Rules:

- `formatBalanceAmount`:
  - privacy hidden -> `****` via existing masking flow or helper branch;
  - no numeric rounding;
  - preserve the fractional substring exactly;
  - add thousands separators only to the integer part;
  - invalid/missing -> existing display fallback (`—`) unless privacy hidden.
- `approximateUsdtLine`:
  - privacy hidden -> `≈ **** USDT`;
  - `value_usdt == null` or invalid -> `≈ — USDT`;
  - valid -> `≈ ${formatUsdt2(value_usdt)} USDT`;
  - `0.00000000` -> `≈ 0.00 USDT`.

Render:

Unified balance card:

```html
<div class="asset">USDT</div>
<div class="amount">100.0861659</div>
<div class="amount value-usdt">≈ 100.09 USDT</div>
```

Spot balance card:

```html
<div class="asset">USDT</div>
<div class="amount">100.0861659</div>
<div class="amount locked">冻结: 0</div>
<div class="amount value-usdt">≈ 100.09 USDT</div>
```

Spot main amount line is `free`; `locked` remains separate. Remove old `【: ...】` from rendered balance cards and tests.

## 6. Frontend Self-Check

Update `frontend/self-check.js`.

Required:

1. Mock new DOM id `filter-hide-low-daily-rate`.
2. Keep the default design fixture baseline at 6 rows. If necessary, after initial render set the new filter off for the legacy baseline section, or make the baseline explicit and then run a separate low-rate scenario. The design review preferred independent/deep-copy scenario; use that.
3. Add helper tests for `absDailyRateAtOrBelowThreshold`:
   - `0.00030000` -> true
   - `-0.00030000` -> true
   - `0.00030001` -> false
   - `-0.00030001` -> false
   - `null` -> false
   - `''` -> false
   - invalid -> false
4. Add UI behavior test:
   - with `hideLowDailyRate=true`, boundary rows `0.00030000` and `-0.00030000` are hidden;
   - `0.00030001` remains visible;
   - toggling checkbox off restores hidden rows.
5. Update balance tests:
   - old `【: ...】` must not appear;
   - visible state includes separate `≈ 123.45 USDT` / `≈ 67.89 USDT` style lines;
   - hidden state includes `≈ **** USDT`;
   - null value shows `≈ — USDT`;
   - zero value shows `≈ 0.00 USDT`;
   - thousands formatting only touches integer part, fractional string preserved.
6. Add asset tag UI assertion for `METAL(金属)`.

Existing self-check numbers may change. Keep the script readable; do not make a fragile wall of string checks where a helper check would be clearer.

## 7. Backend Tests

Update or add tests:

### `backend/tests/test_normalize.py`

- `asset_tag_for("PERPETUAL", "XAU") == ("METAL", "base_asset_metal_symbol", "HIGH")`
- `asset_tag_for("TRADIFI_PERPETUAL", "COPPER") == ("METAL", "base_asset_metal_symbol", "HIGH")`
- Existing single-argument tests still pass.

### `backend/tests/test_snapshot.py`

Add focused tests that do not require live API:

- A synthetic `XAUUSDT` or `COPPERUSDT` futures row with `baseAsset` metal returns `asset_tag=METAL`.
- If the row has no spot leg, `route_class=PERP_ONLY_EXCLUDED` and `negative_funding_status=DISABLED_PERP_ONLY`.
- A synthetic metal row with exact spot leg and negative `daily_funding_rate` is included in `select_borrow_candidates()` output.
- bStock remains excluded from `select_borrow_candidates()`.

Do not loosen existing bStock tests. They should still prove `TSLA/AAPL` bStock behavior remains disabled.

### `backend/tests/test_private_account_v1.py`

Only edit if necessary for fixture/schema/self-check compatibility. Do not rewrite unrelated private-account tests.

## 8. Fixtures

### `backend/tests/fixtures/private-account-v1-design.json`

Only change if self-check needs explicit METAL or balance fixture values. Preserve the default six-row semantics unless you deliberately isolate the low-rate test in a deep-copy scenario.

If you add a METAL row to the default fixture, update:

- `summary.total_rows`
- `route_counts`
- `asset_tag_counts`
- `negative_funding_status_counts`

But prefer avoiding default baseline churn unless necessary.

### `frontend/fixture/public-market-snapshot.json`

Add/update a METAL sample for UI/schema fixture consistency if low risk. Keep summary counts accurate. This fixture is not the Node self-check source; do not rely on it for self-check behavior.

## 9. Tests To Run Before Reporting Done

Run:

```text
python3 -m pytest backend/tests -q
node frontend/self-check.js
```

Also run targeted grep/audit:

```text
rg -n "DISABLED_METAL|METAL\\(贵金属\\)|base_asset_precious|【:" backend frontend docs schemas reports/agent-runs/2026-07-ui-filter-balance-metal-v1/20-implementation.md
rg -n "parseFloat\\(|Number\\(" frontend/index.html
```

The second command may show existing `Number()` uses for price/time/style; that is okay. You must explicitly confirm no `Number()`/`parseFloat()` is used in the low-rate threshold helper.

## 10. Required Report

Write `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/20-implementation.md`.

Include:

- implementer identity: `claude_glm / zhipu_glm`;
- branch and starting HEAD;
- files changed;
- short implementation summary by requirement R1/R2/R3;
- exact notes on METAL semantics:
  - baseAsset metal has priority over TRADIFI/BSTOCK mapping;
  - no `DISABLED_METAL`;
  - eligible METAL rows enter borrow validation and use interface results;
- tests run with exact PASS/FAIL output;
- grep/audit results;
- any deviations from allowed files;
- residual risk, if any.

Footer:

```text
本地北京时间: <from date command>
下一步模型: bookkeeper/codex
下一步任务: 冻结实现 diff，计算 fingerprint，进入 review-1（Kimi）。
```

## 11. Completion Contract

When done, leave the worktree with your implementation changes and `20-implementation.md` uncommitted. Do not change `status.json` or `70-handoff.md`. The bookkeeper will:

1. inspect `git diff`;
2. rerun tests as needed;
3. commit implementation;
4. compute the standard Harness fingerprint;
5. run `scripts/validate-stage.py 2026-07-ui-filter-balance-metal-v1 --phase pre-review`;
6. dispatch review-1 to Kimi.

If you cannot complete safely, write the blocker into `20-implementation.md` and stop.
