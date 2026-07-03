# Review 3 (post-commit reopening, by gpt)

> Triggered by the user pasting a new gpt review of the committed stage
> (`c53664e`). The stage was at `stage_accepted_waiting_user`. This review
> was run against the **live capture** (`reports/api-samples/public-market/
> 20260702T163929Z/`), not the test fixtures — which is why review-2 (codex,
> fixture-scoped) did not surface these. The controller independently
> reproduced every finding against raw artifacts before reopening.

## Reviewer (informal, user-supplied)

- Provider: openai (gpt) — user-pasted, not controller-dispatched.
- Scope: live public capture + committed source.
- Collected by: controller (`claude_glm` / `zhipu_glm`).

## Controller-Independent Reproduction (model claims are not evidence)

All five findings reproduced against raw artifacts. Counts match the gpt
review exactly.

### P1 — bStocks / tokenized-equity perps missed (CONFIRMED)

- `backend/domain/symbols.py:57` rejects any `contractType != "PERPETUAL"`.
- Real `fapi_exchange_info.json` has **118 `TRADIFI_PERPETUAL` + USDT**
  symbols; the 8 curated bStocks (TSLAUSDT/AAPLUSDT/NVDAUSDT/GOOGLUSDT/
  AMZNUSDT/MSFTUSDT/METAUSDT/COINUSDT) are all `TRADIFI_PERPETUAL`+`TRADING`.
- Live candidate table: `asset_tag = {CRYPTO: 653}`, **BSTOCK = 0**; all 8
  curated bStocks ABSENT.
- PRD violation: PRD:86/106/116/140 require bStocks marked
  `asset_tag=BSTOCK`; **AC-04 fails on real data.**
- Test blind spot: `backend/tests/fixtures/fapi_exchange_info.json` types
  TSLAUSDT as `PERPETUAL`; **0 `TRADIFI_PERPETUAL` in fixtures** → the bStock
  join path is never exercised → why review-2 missed it.

### P1 — non-TRADING contracts pollute the candidate table (CONFIRMED)

- `symbols.py` filters `quoteAsset==USDT` on the futures side but **never
  `status=="TRADING"`** (line 79 only captures `status`, does not gate on it).
  The spot side does filter `status=="TRADING"` (line 43) — asymmetric.
- Real capture: **124 of 653 `PERPETUAL`+USDT are non-TRADING** (122
  `SETTLING` + 2 `PENDING_TRADING`). OMGUSDT = `PERPETUAL`+`SETTLING` and is
  in the candidate table with `perp_status=SETTLING`.
- Live candidate table: **124/653 rows have `perp_status != TRADING`** —
  exactly the gpt-reported count.

### P2 — fake-ui loads the 6-row fixture, not the 653-row live capture (CONFIRMED)

- `prototypes/fake-ui/index.html:207`:
  `DATA_URL = "../../backend/tests/fixtures/candidate-classification.json"`.
- Blocks the Phase-1 goal "a clear view of the real market."

### P2 — manual-open symbol dropdown resets on render (CONFIRMED)

- `renderManual()` (line 383) rewrites `manualSymbol` `innerHTML` on every
  call **without preserving the selected value** (cf. line 303, which does
  preserve `selectedSymbol`). `manualSymbol` `change` (line 415) re-fires
  `renderManual` → user selection is discarded.

### P3 — UI copy rewritten to English (CONFIRMED)

- Old workstation (d8e12dd, 1495 lines) was Chinese: title
  "Binance 统一保证金资金费率对冲"; nav 总览持仓 / 费率行情 / 手动开仓 /
  收益归因; Chinese headings/badges.
- Current (439 lines) is English: Market Overview / Funding Opportunities /
  Manual Open Preview. Not a compute bug; violates the user's product-
  acceptance preference.

## Verdict

- **verdict: REWORK** (reopens the committed stage; rework_count 2 → 3, the
  LAST allowed rework).
- next_action: `fix`.
- diff_fingerprint reviewed: post-commit `base(c8...)..c53664e` impl scope
  `46ea7835…` (unchanged from review-2 r2 ACCEPT — the new findings are about
  real-data behavior the prior fixture-scoped review did not exercise, not
  about a code regression).

## Required Fixes (fix #3 — comprehensive, single round)

1. `backend/domain/symbols.py`: accept `{PERPETUAL, TRADIFI_PERPETUAL}` as
   perpetual-type contracts; add `status == "TRADING"` filter on the futures
   side (mirror the spot-side gate).
2. Fixtures + tests: type the bStock fixture as `TRADIFI_PERPETUAL`; add a
   non-TRADING (`SETTLING`) perp fixture; add tests that **FAIL on current
   code** — bStock tagged + present; non-TRADING perp excluded.
3. `prototypes/fake-ui/index.html`: bind to the real live capture (default),
   preserve the manual-symbol selection across renders, restore Chinese
   workstation copy/style (ref `git show d8e12dd:prototypes/fake-ui/index.html`),
   keep Phase-1 read-only + simulation-only (hard constraint: no real order /
   borrow / repay / transfer / signed path).
4. Controller will regenerate
   `reports/api-samples/public-market/20260702T163929Z/candidate-classification.{json,csv}`
   from the fixed code (the committed sample currently shows the buggy
   BSTOCK=0 / 124-non-TRADING output).

## Hard Constraints (unchanged, must hold after fix #3)

Only public endpoints; no api-key/signed/private/websocket/order/borrow/
repay/transfer code path; all amounts Decimal serialized as strings;
`negative_funding_status` priority `PERP_ONLY > BSTOCK > SPOT_ONLY >
PRIVATE_BORROW_VALIDATION_REQUIRED` unchanged; file boundary = `symbols.py`,
fixtures, `test_*.py`, `fake-ui/index.html` (+ controller-regenerated sample).

## Routing

- Fix dispatched to the original implementer `grok-composer-2.5-fast` (xai,
  skill `minimal_change_engineer`) with this reproduction + required fixes.
- After fix: controller re-runs pinned toolchain, regenerates the live sample,
  re-verifies counts (BSTOCK>0, 0 non-TRADING among emitted rows), recomputes
  the fingerprint, and re-dispatches review (provider-isolated, mandated to
  verify against the REAL capture this time).
- rework_count budget: this is fix #3 of 3. If it does not converge →
  `human_gate` (allowed stop reason); the controller will not force an ACCEPT.
