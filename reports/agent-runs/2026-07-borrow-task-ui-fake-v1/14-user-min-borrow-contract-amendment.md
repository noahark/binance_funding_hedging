# Contract Amendment — Classic Margin `user_min_borrow`

## Requested Outcome

Expose Binance classic-margin `allAssets[i].userMinBorrow` as the additive row field `rows[].borrow_validation.classic_margin.user_min_borrow`, then use it only as the empty amount input's placeholder in the fee-market operation column.

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
```

Lookup gates exactly match `asset_borrowable`:

- classic reference unavailable: `user_min_borrow = null`;
- `pair_listed` false or absent: `user_min_borrow = null`;
- otherwise: `user_min_borrow_by_name[base_asset]`, preserving the raw decimal string or `null` when the key/field is missing;
- the borrowability-truncated branch retains this classic-reference field, just as it retains `asset_borrowable` and interest fields.

The schema adds required `user_min_borrow: decimal-string | null` to `classic_margin`. This is additive in product meaning but requires schema/fixture updates because the current schema forbids undeclared properties.

## UI Rule

The fee-market operation amount input remains empty. Its fixed `placeholder="如 1000"` becomes:

- `最小借币量 <user_min_borrow>` when a string is present, including `"0"`;
- `最小借币量 —` when unavailable.

The field is guidance only: it does not set the input value, auto-create a task, alter validation, modify a task-list edit input, or imply that the amount is currently borrowable.

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/14-user-min-borrow-contract-amendment.md
本地北京时间: 2026-07-18 21:53:57 CST
下一步模型: Claude
下一步任务: 将 contract amendment 纳入 development breakdown，并分派后端/前端任务
