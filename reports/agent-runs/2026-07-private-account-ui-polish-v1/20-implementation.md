# Implementation Report: Private Account UI Polish V1

Stage: `2026-07-private-account-ui-polish-v1`
Implementer: Kimi
Design: ACCEPT by Fable5 (2026-07-07)

## Summary

Implemented Task A (additive v0.4 contract/backend) and Task B (frontend display
polish) per `10-design.md` and `11-adr.md`. All backend tests, frontend self-check,
and schema validation pass.

## Changed files

- `backend/domain/snapshot.py`
  - Added `_usdt_value_optional()` returning `Optional[Decimal]` for row-level
    valuation (missing/bad amount or price → `None` + warning; valid zero →
    `Decimal(0)`).
  - Kept existing `_usdt_value()` unchanged for top-level `total_value_usdt`
    (missing price counted as 0, preserving anti-double-count).
  - `assemble_private_account()` now emits `value_usdt` on every
    `balances_unified[]` and `balances_spot[]` row.
- `schemas/api/public-market/snapshot.schema.json`
  - Added optional nullable `value_usdt` to `balances_unified` and
    `balances_spot` item properties; `um_positions` unchanged.
- `docs/api/public-market-contract.md`
  - Appended v0.4 additive amendment describing the new per-balance fields and
    their semantics.
- `frontend/index.html`
  - Moved `#private-panel` before the market table in DOM order.
  - Replaced `badgeForNegativeFundingStatus(ns)` with row-aware function
    `badgeForNegativeFundingStatus(row)` implementing structural-priority +
    borrow-validation label derivation.
  - Added borrow-rate subline in the net-yield column for rows with
    `borrow_rate_source != null`, with VIP0 fallback marked "参考".
  - Added `折算: <value_usdt> USDT` line to unified/spot balance cards,
    with `-` fallback and privacy masking.
- `frontend/self-check.js`
  - Added assertions for DOM order, borrow-rate subline, VIP0 reference badge,
    row-aware negative-funding labels, value_usdt display/privacy/null fallback.
  - Updated assertion 16 to the new Chinese-first negative-funding format.
- `frontend/fixture/public-market-snapshot.json`
  - Added representative `private_account` block with `value_usdt` samples
    (including a `null` row) for schema/manual testing.
- `backend/tests/fixtures/private-account-v1-design.json`
  - Added `value_usdt` placeholders to private account balance rows and states.
- `backend/tests/test_private_account_v1.py`
  - Extended anti-double-count test to assert row `value_usdt`.
  - Added tests for null on missing price, `"0.00000000"` on valid zero,
    stablecoin pricing, and `um_positions` having no `value_usdt`.
- `reports/api-samples/2026-07-private-account-ui-polish-v1/20260706T172648Z/`
  - `api-v3-ticker-price.json` (raw public no-key sample) +
    `evidence-index.md` with provenance from v0.3 sample.

## Key implementation points

### Row-level valuation vs total valuation

The critical design requirement was that `value_usdt` must distinguish "missing
price" (`null`) from "priced zero" (`"0.00000000"`). The existing `_usdt_value`
returns `Decimal(0)` for both cases, so a new `_usdt_value_optional` was added:

- Returns `None` when asset/amount is missing or unparseable, or when price is
  missing/bad, appending a warning each time.
- Returns `Decimal(0)` for a valid zero amount or a computation that yields zero.
- Stablecoins (`USDT`, `USDC`) price at 1.

Top-level `total_value_usdt` continues to use `_usdt_value`, so missing-price
assets are counted as 0 and the anti-double-count rule is unchanged.

### Frontend negative-funding labels

`badgeForNegativeFundingStatus(row)` now checks structural priorities first:

1. `DISABLED_PERP_ONLY` → `仅合约: 无现货腿`
2. `DISABLED_BSTOCK` → `bStock: 负费率不可借`
3. `DISABLED_SPOT_ONLY` → `仅现货: 无杠杆借币`
4. `PRIVATE_BORROW_VALIDATION_REQUIRED` is then resolved against
   `row.borrow_validation`:
   - `verified=true, pair_listed=true, asset_borrowable=true` → `已验证可借`
   - `verified=true, pair_listed=false` → `杠杆交易对未列出`
   - `verified=true, asset_borrowable=false` → `资产不可借`
   - `verified=false, error='not_probed_this_round'` → `未探测(限速预算)`
   - otherwise → `需私有验证`

### Borrow-rate subline

Only rows with `borrow_rate_source != null` show the subline. The account rate
is preferred; if absent, the VIP0 reference rate is shown with a `参考` badge;
if both are absent, `-` is shown.

## Verification

```bash
python3 -m pytest backend/tests/test_private_account_v1.py -q   # 51 passed
python3 -m pytest backend/tests/test_snapshot.py -q             # 19 passed
python3 -m pytest backend/tests -q                              # 157 passed
node frontend/self-check.js                                     # 39 assertions passed
python3 -c "jsonschema.validate(fixture, schema)"               # OK
```

Raw output is captured in `60-test-output.txt`.

## Evidence

- Raw public sample: `reports/api-samples/2026-07-private-account-ui-polish-v1/20260706T172648Z/`
- Test output: `reports/agent-runs/2026-07-private-account-ui-polish-v1/60-test-output.txt`

## Not done / next steps

- Bookkeeper to update `status.json`, compute diff fingerprint, and organize
  review-1 / review-2 (final reviewer Fable5).
- No merge to `main` until user acceptance after review.

本地北京时间: 2026-07-07 01:29:48 CST
下一步模型: Fable5 (bookkeeper + review-2)
下一步任务: 校验 checkpoint、计算 diff fingerprint、组织 review-1/review-2

---

# v1.1-ui-polish-2 Implementation Addendum

Stage: `2026-07-private-account-ui-polish-v1` round-2
Implementer: Kimi
Design: `10-design.md §v1.1-ui-polish-2 Design Addendum` + `11-adr.md ADR-7/8/9`,
ACCEPT by Fable5 (2026-07-07)

## Scope

Items 5–10 from the addendum, folded into the existing unmerged stage branch.
Round-1 value_usdt fields and items 1–4 were already on the branch and were not
reverted.

## Changed files

- `backend/domain/snapshot.py`
  - Added `_balance_sort_key()` helper using Decimal `(null-flag, -value, asset, idx)`.
  - `assemble_private_account()` now sorts `balances_unified` and `balances_spot`
    by `value_usdt` DESC, nulls last, `asset` ASC, input-order stable for same asset.
  - `sort_rows()` and market row ordering were **not** touched.
- `backend/tests/test_private_account_v1.py`
  - Added `test_assemble_private_account_sorts_balances_by_value_desc_nulls_last_asset_asc()`.
  - Added `test_assemble_private_account_sort_tiebreak_asset_asc_stable_same_asset()`.
- `backend/tests/test_snapshot.py`
  - Added `test_market_rows_order_regression()` to pin that market `rows` order is
    unchanged by the private-account balance sorting.
- `docs/api/public-market-contract.md`
  - Appended additive-only `Balance array display order` paragraph under the v0.4
    amendment; no schema/enum/schema_version change.
- `frontend/index.html`
  - Added `formatUsdt2()` decimal-string helper: 2-place ROUND_HALF_UP display.
  - Balance cards now render amounts inline with `【: 123.45 USDT】`; null/缺失 →
    `【: — USDT】`; zero `"0.00000000"` → `【: 0.00 USDT】`; privacy hidden masks both
    amount and suffix as `****`.
  - Removed「估值来源」overview card and dead `priceSource` variable.
  - Removed「估值时点」「检查时点」overview cards.
  - verified=true subtitle now reads `资产更新时间 <time>` (fallback to
    `pa.valuation.priced_at`, then `—`).
  - verified=false subtitle/body/help updated per the item-10 replacement table
    (`私有账户未读取`, key/IP/后端配置 help, no-ordering note).
  - Deleted `.sidebar-footer` block containing `公开行情 · 只读展示 · 不连接 Binance`.
  - Updated brand/topbar/data-note texts: `行情公开 · 账户私有只读`,
    `行情公开 · 账户需 key 私有只读`, `行情公开` / `账户只读` badges,
    data-note subtitle, `WARNING_CHINESE[0]`, `marginPublicNote`.
- `frontend/self-check.js`
  - Updated balance-card assertions for inline 2-place display, null/zero/privacy.
  - Added `formatUsdt2` ROUND_HALF_UP cases.
  - Added assertions that「估值来源/估值时点/检查时点」are no longer visible while
    `price_source` remains in payload.
  - Added assertion that page text no longer contains `不连接 Binance`.
  - Added assertion that verified=true subtitle contains `资产更新时间`.
  - Updated verified=false placeholder text checks to `私有账户未读取`.
  - Updated warning/margin-note text checks.

## Red-line compliance

1. Sorting only affects `assemble_private_account()` output arrays; `sort_rows()`,
   market `rows` order, `sort_basis`, and the frozen contract `Row order (frozen)`
   are unchanged. Regression test added.
2. No schema field/enum/`schema_version` change; only an additive contract note.
3. Backend time fields unchanged: `valuation.priced_at = checked_at`, top-level
   `checked_at` still emitted.
4. No order/borrow/repay/transfer/websocket/private-channel whitelist changes.
5. Frontend renders backend payload order; no client-side balance sorting or
   recomputation of `total_value_usdt`.

## Verification

```bash
python3 -m pytest backend/tests/test_private_account_v1.py -q   # 53 passed
python3 -m pytest backend/tests/test_snapshot.py -q             # 20 passed
python3 -m pytest backend/tests -q                              # 160 passed
node frontend/self-check.js                                     # 42 assertions passed
python3 -c "jsonschema.validate(fixture, schema)"               # OK
```

Raw output captured in `60-test-output.txt`.

## Evidence

- Test output: `reports/agent-runs/2026-07-private-account-ui-polish-v1/60-test-output.txt`
- Contract order note: `docs/api/public-market-contract.md §Balance array display order`

本地北京时间: 2026-07-07 16:46:48 CST
下一步模型: Fable5 (bookkeeper → 校验 diff/fingerprint → review-1/review-2)
下一步任务: 由 bookkeeper 复算 diff fingerprint、更新 status.json、派发 review-1/review-2
