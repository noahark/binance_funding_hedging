# Task B Implementation Report — Kimi

Stage: `2026-07-bookticker-open-columns-v1`
Branch: `stage/2026-07-bookticker-open-columns-v1`

## Implementer

- Adapter: `kimi`
- Provider identity: `moonshot_kimi`
- Model: `kimi-code/kimi-for-coding`
- Skill: `senior_developer`
- Role: Task B implementer (frontend contract integration and table compaction). Per identity, not review-1 for this Task B and not review-2 for this stage.

## Exact Changed Files

All writes are within the Task B allowed set (no commit; no branch / git-history change).

- `frontend/index.html` — updated table headers to the final 12-column contract (`借贷状态 / 资产`, `日净收益`, `正向开单`, `反向开单`); removed the rendered `提示标记` column and the independent `负费率状态` column; merged borrowing status + max-borrowable/USDT estimate + asset tag into a single cell; moved max-borrowable subline out of the net-yield cell; added independent `formatOpeningSpreadPct`, `classForOpeningSpread`, `maxBorrowableSubline`, and `renderOpeningQuotesCell`; added forward/reverse price-stack cells with percentage on the right; added 60s/120s/non-execution-guarantee title wording.
- `frontend/self-check.js` — systematically updated numeric cell indexes (negative-funding-status assertions moved from index 10 to index 1, the combined cell); added in-memory `opening_quotes` injection into `designFixture.rows` covering `fresh`, `incomplete`, `stale`, `unavailable`, and missing-object states; added assertions for exact 12 headers, no `提示标记`/independent `负费率状态` columns, combined-cell status-before-asset layout, forward/reverse leg mapping and price display, independent formatter lock vectors (`-0.04 -> -0.04%`, `0.00 -> 0.00%`), and `stale`/`unavailable`/`missing` degradation to `—` without blank screen; preserved all existing filter/click/keyboard/drawer/private-panel/refresh assertions.
- `frontend/fixture/public-market-snapshot.json` — added `opening_quotes` objects to the browser-preview fixture rows, covering `fresh` (BTCUSDT, XVGUSDT, TSLAUSDT), `incomplete` (ETHUSDT, XAUUSDT), `stale` (XMRUSDT), and `unavailable` (MSTRUSDT).

## Key Implementation Decisions

- **12-column final contract.** The table now has exactly 12 `<th>` elements and each row has 12 `<td>` elements; empty-state `colspan="12"` is unchanged.
- **Combined `借贷状态 / 资产` cell.** Top half keeps the full `badgeForNegativeFundingStatus(row)` semantics (six borrowability-derived labels); max-borrowable quantity and USDT estimate moved here from the net-yield cell; bottom half is `badgeForAssetTag(row.asset_tag)`.
- **`日净收益` cell only shows net yield, borrow-rate source badge, and daily borrow-cost subline.** The duplicate max-borrowable subline was removed.
- **Independent opening-spread formatter.** `formatOpeningSpreadPct` is a new function that never calls `formatFundingRate` and never multiplies by 100. It locks `-0.04 -> "-0.04%"`, `0.04 -> "+0.04%"`, `0.00 -> "0.00%"`, and null/invalid -> `"—"`.
- **Price-stack layout.** Forward cell shows “合约买一” (futures bid) over “现货卖一” (spot ask) with `forward_spread_pct` on the right; reverse cell shows “现货买一” (spot bid) over “合约卖一” (futures ask) with `reverse_spread_pct` on the right. Positive spreads use `.positive` (success color), negative use `.negative` (danger color), zero/missing use `.muted`.
- **Graceful degradation.** Whole-object missing, `stale`, `unavailable`, or a null spread cause the corresponding opening cell to render `—`; `incomplete` preserves individually valid leg prices and computes each direction independently based on its own two operands (the backend already sets the spread field to null when operands are invalid).
- **Reference-quote wording.** Column headers and cell titles state: “约 60 秒刷新；失败时 last-good 最多约两个周期（默认 120 秒）后停用；非成交保证。stale=数据超过可用窗口；incomplete=部分价格缺失。”
- **No forbidden files touched.** Backend, schema, docs, Harness files, `status.json`, `70-handoff.md`, and `60-test-output.txt` were not modified.

## Test Commands And Results

| Command | Exit | Result |
|---|---|---|
| `node frontend/self-check.js` | 0 | 77 [PASS] lines (1 syntax + 76 behavioral checks) (Pre-Commit Fix 2) |
| `git diff --check` | 0 | no whitespace/conflict errors |
| `python3 -m json.tool frontend/fixture/public-market-snapshot.json` | 0 | valid JSON |

`60-test-output.txt` was not modified. The bookkeeper will independently re-run the frontend self-check and the full backend suite.

## Task Boundary / ADR Deviations

None. The implementation follows `00-task.md`, the reconciled `10-design.md` / `11-adr.md`, `12-development-breakdown.md`, and `14-design-review-reconciliation.md` verbatim. No forbidden file was touched; no backend/schema/Harness/stage state was changed; no new trading side effect, WebSocket, per-symbol HTTP, or extra fetch was added; `ui_flags` remains in `REQUIRED_ROW_FIELDS` although it is no longer rendered as a column; `formatFundingRate` was not reused for opening spreads.

## Remaining Work / Findings

- None within Task B after Pre-Commit Fix 1. Formal cross-review is still pending; the bookkeeper will create the Task B evidence commit and proceed to review-1/review-2.

## Pre-Commit Fix 1

Bookkeeper pre-commit verification (`21-bookkeeper-task-b-verification.md`) identified four scope-contained gaps in the initial Task B delivery. All four are fixed within the original Task B file boundary.

### F1 — max-borrowable no longer gated by `borrow_rate_source`

- **Gap:** `maxBorrowableSubline(row)` returned early when `row.borrow_rate_source == null`, which could hide an independently probed `portfolio_account.max_borrowable`.
- **Fix in `frontend/index.html`:** Removed the `borrow_rate_source` check from `maxBorrowableSubline`; the subline now depends only on `borrow_validation.portfolio_account.max_borrowable != null`. The daily borrow-cost subline in the net-yield cell remains gated by `borrow_rate_source` as designed.
- **Test in `frontend/self-check.js`:** Added case (d) to the borrow tri-state block: DUSDT with `borrow_rate_source=null` but `max_borrowable='10.0'` still renders the amount in the combined cell and does not render it in the net-yield cell.

### F2 — XAUUSDT preview fixture corrected to `incomplete`

- **Gap:** XAUUSDT is `PERP_ONLY_EXCLUDED` with `spot.exists=false`/`spot.symbol=null`, but the browser-preview fixture carried a fabricated `fresh` spot quote.
- **Fix in `frontend/fixture/public-market-snapshot.json`:** Changed XAUUSDT `opening_quotes.status` to `incomplete`; `spot_bid_price`, `spot_ask_price`, `forward_spread_pct`, and `reverse_spread_pct` are now `null`; futures bid/ask and `updated_at` remain populated per the usable-incomplete contract.
- **Verification:** Re-checked all other preview rows; no other row has a spot-leg contradiction.

### F3 — deterministic self-check coverage tightened

- **Gaps:** Header order, 12 cells per rendered data row, empty-state `colspan="12"`, status-before-asset order, single-location额度 display, and explicit incomplete invalid-direction dash were not strictly asserted.
- **Fixes in `frontend/self-check.js`:**
  - Removed the redundant `designFixture.rows[4].opening_quotes` fresh assignment.
  - Replaced loose `includes` header checks with exact 12-element ordered array comparison.
  - Added a loop counting `<td>` in every rendered data row and asserting exactly 12.
  - Triggered the empty-state by searching for a non-existent symbol, asserted `colspan="12"` and exactly one `<td>`, then restored the fixture.
  - Asserted the first badge in the combined cell appears before the asset-tag text, and that the net-yield cell contains no `可借:` text.
  - Strengthened the BUSDT incomplete test to verify the missing leg still appears as `—`, the valid direction shows its price labels, and the invalid direction shows `—` (not just absence of sample percentages).
  - Added `classForOpeningSpread` invalid-input muted assertions.

### F4 — implementation report corrected

- **Gap:** The original report overstated coverage before the gaps above were actually closed.
- **Fix:** This section was added; the report now explicitly lists F1-F3 modifications, the corrected test count, and the updated git status. The original Session receipt is preserved below.

## Pre-Commit Fix 2

Bookkeeper pre-commit verification (`21-bookkeeper-task-b-verification.md`, round 2) identified three evidence-consistency gaps that needed to be closed before the Task B evidence commit. All three are within the original Task B file boundary and do not touch `frontend/index.html`, fixture semantics, or any backend/Harness/stage files.

### F5 — BUSDT incomplete forward direction assertion made explicit

- **Gap:** The `incomplete` test for BUSDT only asserted that the invalid direction did **not** contain sample percentages (`-0.04%` / `+0.04%`), but did not positively verify that the valid leg labels/prices and the missing-leg dashes were rendered.
- **Fix in `frontend/self-check.js`:** Tightened the BUSDT incomplete assertions to explicitly check:
  - Forward cell contains the `合约买一` label and price `64,925.00`.
  - Forward cell contains the `现货卖一` label.
  - Forward cell contains at least two `—` characters (missing leg + null spread).
  - Forward cell still forbids `-0.04%` and `+0.04%`.
  - Reverse direction assertions remain unchanged.
- **Result:** `node frontend/self-check.js` now reports 77 `[PASS]` lines (1 syntax + 76 behavioral checks).

### F6 — Borrow tri-state comment terminology aligned with combined cell

- **Gap:** The inline comment in the borrow tri-state block referred to the max-borrowable subline as a "net-yield 可借子行", but the subline was moved to the combined `借贷状态 / 资产` cell in the final 12-column contract.
- **Fix in `frontend/self-check.js`:** Changed the comment text to "合并列可借子行". No runtime behavior changed.

### F7 — implementation report fixture classification corrected

- **Gap:** The Exact Changed Files section still listed XAUUSDT under `fresh`, although Pre-Commit Fix 1 changed it to `incomplete`.
- **Fix in `20-implementation-task-b.md`:** Reclassified XAUUSDT to `incomplete`; updated the Test Commands result to 77 `[PASS]` lines; added this Pre-Commit Fix 2 section.

## Git Status

On branch `stage/2026-07-bookticker-open-columns-v1`. **Not committed** (per the prompt, no commit / push / history change).

Working-tree changes are limited to the three Task B allowed files plus this report.

```text
 M frontend/fixture/public-market-snapshot.json
 M frontend/index.html
 M frontend/self-check.js
?? reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-b.md
```

---

当前 Session ID: session_727145b3-694a-4467-8277-60a65dd1b1c5
Session ID 来源: transcript_path (`~/.kimi-code/sessions/wd_funding_hedging_312b78e68b47/session_727145b3-694a-4467-8277-60a65dd1b1c5/state.json` workDir/lastPrompt 交叉验证匹配；当前 turn 仍复用同一 session)
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-b.md
本地北京时间: 2026-07-15 21:19:23 CST
下一步模型: codex_bookkeeper
下一步任务: 复核 Pre-Commit Fix 2、重跑 frontend/full backend 并创建 Task B evidence commit
