# 21 — Backend Task B1 Implementation Report

Stage `2026-07-borrow-task-ui-fake-v1` · Branch `stage/2026-07-borrow-task-ui-fake-v1`
Role: implementation author (claude_glm) · HEAD `8163e21`
Dispatch: `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/28-claude-glm-backend-b1.dispatch.md`

## 1. Contract implemented

The additive classic-margin minimum-borrow mapping chain, exactly as specified:

```text
allAssets[i].userMinBorrow (string, key assetName)
  → classic_ref.user_min_borrow_by_name[assetName]
  → rows[].borrow_validation.classic_margin.user_min_borrow
  → rows[].borrow_validation.classic_margin.user_min_borrow_value_usdt
```

`user_min_borrow` is the raw decimal string preserved verbatim; `user_min_borrow_value_usdt`
is a new 2dp `ROUND_HALF_UP` USDT valuation. No existing 8dp
`portfolio_account.max_borrowable_value_usdt` contract was changed, reused, or reduced.

## 2. Changed files (7 modified + 2 new)

```
 backend/domain/snapshot.py                         |  42 +++++
 backend/services/private_client.py                 |  12 +-
 backend/tests/fixtures/private-account-v1-design.json | 12 +-
 backend/tests/test_phase2_borrow_sort.py            |   7 +-
 backend/tests/test_private_account_v1.py            | 173 ++++++++++++++++
 backend/tests/test_private_client.py                |  29 +++-
 schemas/api/public-market/snapshot.schema.json      |  14 +-
 7 files changed, 277 insertions(+), 12 deletions(-)
```

Untracked (this dispatch's permitted new artifacts):

- `reports/api-samples/2026-07-borrow-task-ui-fake-v1/sapi-v1-margin-allAssets.json` — byte-for-byte copy of the source sample.
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/61-test-output-backend.txt` — captured command output.

### 2.1 `backend/services/private_client.py`

`fetch_classic_reference` now builds, alongside `asset_borrowable_by_name`:

```python
"user_min_borrow_by_name": {
    x.get("assetName"): x.get("userMinBorrow") for x in all_assets
},
```

A record missing `userMinBorrow` maps to `None` (`.get` default); the raw string is
otherwise carried through unchanged. Docstring lists the new key.

### 2.2 `backend/domain/snapshot.py`

New `_user_min_borrow_value_usdt(asset, user_min_borrow, price_map)` (after
`_max_borrowable_value_usdt`). Same amount/price routing as the maximum-borrow
valuation (stable USD assets `{"USDT","USDC"}` priced at 1; `<ASSET>USDT` price
lookup; `None` on null/blank/invalid amount or missing/invalid price; raw `"0" →
"0.00"`), but quantized with `Decimal` + `ROUND_HALF_UP` to exactly two decimals:

```python
return format(value.quantize(Decimal("0.01"), ROUND_HALF_UP), "f")
```

It deliberately does NOT call the 8dp `_quantize_rate` path and emits no warnings.

`assemble_borrow_validation` — all three return branches (`classic_ref is None`,
`borrowability_truncated`, normal) now emit both `user_min_borrow` and
`user_min_borrow_value_usdt` inside `classic_margin`. Gating mirrors `asset_borrowable`
exactly:

```python
if pair_listed:
    ...
    user_min_borrow = classic_ref.get("user_min_borrow_by_name", {}).get(base)
else:
    ...
    user_min_borrow = None
user_min_borrow_value_usdt = _user_min_borrow_value_usdt(base, user_min_borrow, price_map or {})
```

`.get("user_min_borrow_by_name", {})` means an absent key (existing fixtures/tests)
degrades to `None` (schema-valid). The truncated branch keeps both fields (rate is
covered) and clears only the `portfolio_account` amounts, unchanged from before.

### 2.3 `schemas/api/public-market/snapshot.schema.json`

`classic_margin` `required` extended to
`["pair_listed","asset_borrowable","daily_interest_vip0","daily_interest_account",
"user_min_borrow","user_min_borrow_value_usdt","source"]`. Both new properties are
`anyOf: [{$ref #/$defs/decimal_string}, {type:null}]`. `additionalProperties` stays
`false`.

### 2.4 `backend/tests/fixtures/private-account-v1-design.json`

All six `classic_margin` blocks updated. Rows with `pair_listed: true` (AUSDT/BUSDT/
CUSDT/DUSDT) get placeholder `"user_min_borrow": "<AMOUNT>",
"user_min_borrow_value_usdt": "<AMOUNT>"`; rows with `pair_listed: null` (EUSDT/FUSDT)
get `null, null`. This design fixture is read only by the redaction scan
(`test_redaction_scan_design_fixture`), never by schema validation — the `<AMOUNT>`
placeholders are consistent with every other account-context value in this fixture.

### 2.5 Raw sample copy

`reports/api-samples/2026-07-borrow-task-ui-fake-v1/sapi-v1-margin-allAssets.json` is a
byte-for-byte copy of `reports/api-samples/2026-07-private-account-v1/20260705T232800Z/
sapi-v1-margin-allAssets.json` (409 records, every `userMinBorrow` is the factual `"0"`).
The source was not altered and no nonzero raw sample was invented — synthetic nonzero
inputs appear only in tests.

### 2.6 Tests

- `backend/tests/test_private_account_v1.py` — import extended to also import
  `_user_min_borrow_value_usdt`; 12 new focused tests
  (`test_user_min_borrow_value_usdt_*`, `test_assemble_user_min_borrow_*`,
  `test_assemble_max_borrowable_value_usdt_keeps_eight_decimals`,
  `test_user_min_borrow_schema_accepts_decimal_string_or_null`,
  `test_user_min_borrow_schema_rejects_missing_field_and_extra_property`).
- `backend/tests/test_private_client.py` — `test_classic_reference_maps_raw_fields`
  updated for the new key (`{"BTC":"0","FOO":None}`); new
  `test_classic_reference_user_min_borrow_preserves_nonzero_raw` proves nonzero raw
  values (`"0.001"`, `"0.0005"`) are preserved verbatim.
- `backend/tests/test_phase2_borrow_sort.py` — edited under the dispatch's explicit
  allowance (§22: "only if its exact-field assertions require this contract update"):
  `test_offline_full_snapshot_validates_v02_schema` `classic_margin` set assertion grew
  from 5 to 7 fields plus two offline-null assertions.

Coverage spans map construction / raw preservation, all null/pair gates (classic_ref
absent, pair not listed, pair listed, map-missing-key), truncated retention,
stable/nonstable pricing, missing/invalid input, raw zero, exact two-decimal +
half-up (`1.005 → "1.01"`, `55.555 → "55.56"`), strict schema failures (missing field
and extra property via `pytest.raises(jsonschema.ValidationError)`), and the unchanged
eight-decimal maximum-borrow behavior.

## 3. Test results

Full backend suite, run exactly as dispatched:

```
python3 -m pytest backend/tests -q      → 394 passed in 16.26s   exit=0
git diff --check                         → (no output)            exit=0
```

Baseline before this task was 381 passing; +13 new tests, 0 failures, 0 skipped.

Complete command output is captured in `61-test-output-backend.txt`.

## 4. SHA-256 — byte-identical sample copy

```
shasum -a 256 \
  reports/api-samples/2026-07-private-account-v1/20260705T232800Z/sapi-v1-margin-allAssets.json \
  reports/api-samples/2026-07-borrow-task-ui-fake-v1/sapi-v1-margin-allAssets.json

80e67eb96fa82afb7165021faf5111e82339c33d28bcc9bf064f343a40e46a52  reports/api-samples/2026-07-private-account-v1/20260705T232800Z/sapi-v1-margin-allAssets.json
80e67eb96fa82afb7165021faf5111e82339c33d28bcc9bf064f343a40e46a52  reports/api-samples/2026-07-borrow-task-ui-fake-v1/sapi-v1-margin-allAssets.json
```

Explicit equality statement: the two SHA-256 digests are identical
(`80e67eb96fa82afb7165021faf5111e82339c33d28bcc9bf064f343a40e46a52`), confirming the
stage-local sample is a byte-for-byte copy of the source sample and was not altered.

## 5. Deviations / blockers

- No implementation deviation. The contract was implemented exactly as specified; no
  endpoints, signed writes, borrow/repay execution, retry schedulers, persistence, or
  external side effects were added.
- `test_phase2_borrow_sort.py` was edited strictly within the dispatch's conditional
  allowance — only the exact-field assertion that the contract update forced.
- No commit was made; the worktree is left intact for the bookkeeper's evidence commit
  and the later Kimi dependency handoff.
- Per `status.json`, the standing blocker — "Kimi frontend Task F2 remains blocked
  until B1 is committed on the stage branch with `python3 -m pytest backend/tests -q`
  green and a byte-identical stage-local raw sample" — is now satisfiable: tests are
  green (394 passed) and the stage-local sample is byte-identical. The block lifts once
  the bookkeeper commits this evidence; B1 itself has no open blocker.

```text
当前 Session ID: unavailable (the executing model cannot observe its own provider-native session ID through the harness; to be recorded by the operator/runner into status.json.session_receipts)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/21-implementation-backend.md
本地北京时间: 2026-07-18 22:32:26 CST
下一步模型: bookkeeper (human/operator), then Kimi
下一步任务: bookkeeper 提交 B1 实现证据到 stage 分支（7 源/测试/schema/fixture 文件 + 21-implementation-backend.md + 61-test-output-backend.txt + 逐字节复制的 allAssets 样本），解除 Kimi 前端 Task F2 的借币下限依赖阻塞；Kimi 随后跨模型审查后端 B1 并继续 F2
```
