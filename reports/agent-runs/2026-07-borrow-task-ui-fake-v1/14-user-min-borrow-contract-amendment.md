# Contract Amendment — Classic Margin `user_min_borrow`

## Requested Outcome

Expose Binance classic-margin `allAssets[i].userMinBorrow` as the additive row field `rows[].borrow_validation.classic_margin.user_min_borrow`. Also expose its displayed USDT equivalent as `user_min_borrow_value_usdt`, stored as a two-decimal string. Use both only as guidance in the empty amount input's placeholder in the fee-market operation column.

## Raw Evidence

Existing public raw sample:

- `reports/api-samples/2026-07-private-account-v1/20260705T232800Z/sapi-v1-margin-allAssets.json`

Verified facts from that raw response:

- 409/409 asset records contain `userMinBorrow`.
- The sample's first record is `{assetName: "BTC", isBorrowable: true, userMinBorrow: "0"}`.
- All current captured values are `"0"`; this establishes the field path and string shape but does not provide a non-zero visual value.

Before implementation review, an unmodified raw copy of that public sample must be landed at `reports/api-samples/2026-07-borrow-task-ui-fake-v1/sapi-v1-margin-allAssets.json`. A synthetic test fixture with a non-zero value may supplement test coverage, but cannot replace that raw evidence.

## Contract

```text
allAssets[i].userMinBorrow (string, key assetName)
  → classic_ref.user_min_borrow_by_name[assetName]
  → rows[].borrow_validation.classic_margin.user_min_borrow
  → rows[].borrow_validation.classic_margin.user_min_borrow_value_usdt
```

Lookup gates exactly match `asset_borrowable`:

- classic reference unavailable: both fields are `null`;
- `pair_listed` false or absent: both fields are `null`;
- otherwise: `user_min_borrow` is `user_min_borrow_by_name[base_asset]`, preserving the raw decimal string or `null` when the key/field is missing;
- when that raw amount is a valid decimal, `user_min_borrow_value_usdt` uses the same stablecoin and `<ASSET>USDT` price-routing rules as the existing maximum-borrow valuation, then quantizes with `Decimal` and `ROUND_HALF_UP` to exactly **two** decimal places; missing/invalid price or amount yields `null`;
- the borrowability-truncated branch retains this classic-reference field, just as it retains `asset_borrowable` and interest fields.

`portfolio_account.max_borrowable_value_usdt` keeps its existing eight-decimal contract. The new minimum-borrow value must not reuse or alter that stored precision.

The schema adds required `user_min_borrow: decimal-string | null` and `user_min_borrow_value_usdt: decimal-string | null` to `classic_margin`. Tests must assert the new value has exactly two decimal places when non-null. This is additive in product meaning but requires schema/fixture updates because the current schema forbids undeclared properties.

## UI Rule

The fee-market operation amount input remains empty. Its fixed `placeholder="如 1000"` becomes:

- `最小借币量 <user_min_borrow> (≈ <user_min_borrow_value_usdt> USDT)` when both strings are present, including raw `"0"` and value `"0.00"`;
- `最小借币量 <user_min_borrow> (≈ — USDT)` when the raw string is present but its USDT value is unavailable;
- `最小借币量 —` when the raw minimum is unavailable.

The field is guidance only: it does not set the input value, auto-create a task, alter validation, modify a task-list edit input, or imply that the amount is currently borrowable.

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/14-user-min-borrow-contract-amendment.md
本地北京时间: 2026-07-18 22:01:37 CST
下一步模型: Claude
下一步任务: 将 contract amendment 纳入 development breakdown，并分派后端/前端任务
