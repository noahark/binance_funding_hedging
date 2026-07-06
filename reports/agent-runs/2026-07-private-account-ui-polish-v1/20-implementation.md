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
