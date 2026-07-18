# 31 — Review-1 (Backend Task B1) — Kimi

Stage `2026-07-borrow-task-ui-fake-v1` · Task `backend-minimum-borrow-contract-b1`
Reviewer: Kimi (`kimi-code/kimi-for-coding`, provider `moonshot_kimi`) · read-only, fresh session
Dispatch: `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/36-kimi-review-1-backend-b1-rebound.dispatch.md`

Reviewed committed range (from dispatch, cross-checked against `status.json` task B1):

```text
base_sha: 8163e2128a450116660a92b449fa4d2b97b3448c
head_sha: 623d059b52723d9ee412519db054a2a25cedf504
diff_fingerprint: 623d059b52723d9ee412519db054a2a25cedf504:d613e05020e5885d8171d26a5d165ced8b1193530ef301ff1622ab35bad028d0
```

Identity note: B1 implementer is `claude_glm` (provider `zhipu_glm`); this reviewer is
provider `moonshot_kimi` — provider-level cross-review isolation for the reviewed code
holds. This reviewer implemented the stage's frontend tasks F2/F3, which are outside
this B1 review scope and are reviewed separately by Claude-GLM; this reviewer had no
part in B1 design, breakdown, or code.

## 1. Independent verification performed

All checks below were executed by this reviewer against the committed repository state,
not taken from the implementation report:

- Branch `stage/2026-07-borrow-task-ui-fake-v1`, worktree clean; range
  `8163e21..623d059` resolves to exactly one commit `623d059 feat(backend): expose
  minimum borrow guidance` (bookkeeper evidence commit of the B1 delivery).
- Fingerprint independently recomputed per the Harness scheme
  (`head_sha + ":" + sha256(git diff --binary <base>..<head> -- . ":(exclude)<stage>/status.json")`):
  result is byte-identical to the dispatch value above.
- Full range diff read line by line: `backend/services/private_client.py`,
  `backend/domain/snapshot.py`, `schemas/api/public-market/snapshot.schema.json`,
  `backend/tests/test_private_client.py`, `backend/tests/test_private_account_v1.py`,
  `backend/tests/test_phase2_borrow_sort.py`,
  `backend/tests/fixtures/private-account-v1-design.json`, plus the landed evidence
  files (`21-implementation-backend.md`, `61-test-output-backend.txt`) and the new raw
  sample. 10 files, 480 insertions, 12 deletions — all inside the B1 allowed-file
  boundary from `00-task.md` and `status.json.model_routing`; no forbidden path touched.
- Raw sample byte-identity independently re-run:
  `shasum -a 256` of `reports/api-samples/2026-07-private-account-v1/20260705T232800Z/sapi-v1-margin-allAssets.json`
  and `reports/api-samples/2026-07-borrow-task-ui-fake-v1/sapi-v1-margin-allAssets.json`
  both yield `80e67eb96fa82afb7165021faf5111e82339c33d28bcc9bf064f343a40e46a52`.
  Sample facts re-verified: 409/409 records carry `userMinBorrow`, every value is the
  factual string `"0"`, first record is `{assetName: "BTC", isBorrowable: true,
  userMinBorrow: "0"}` — the implementer did not fabricate a non-zero raw value;
  synthetic non-zero inputs exist only inside `backend/tests/`.
- Test suite independently re-run: `python3 -m pytest backend/tests -q` →
  **394 passed in 12.16s** (matches the 394-passed claim in `61-test-output-backend.txt`).
- `git diff --check 8163e21..623d059` → clean (no whitespace errors).

## 2. Contract conformance (vs `14-user-min-borrow-contract-amendment.md` and breakdown §2)

Mapping chain `allAssets[i].userMinBorrow → classic_ref.user_min_borrow_by_name[assetName]
→ classic_margin.user_min_borrow / user_min_borrow_value_usdt` verified end to end:

- **Raw-string preservation.** `private_client.py:269-275` builds
  `user_min_borrow_by_name` as `{x.get("assetName"): x.get("userMinBorrow")}` — pure
  passthrough, no bool/float/Decimal coercion; a record missing the field maps to
  `None`. Test `test_classic_reference_user_min_borrow_preserves_nonzero_raw` pins
  verbatim preservation of `"0.001"`/`"0.0005"` and the missing-field `None` mapping.
- **Gating identical to `asset_borrowable`.** In `assemble_borrow_validation`
  (`snapshot.py:1064-1130`): `classic_ref is None` branch emits both fields `null`;
  `pair_listed` falsy (false or absent) forces `user_min_borrow = None` via the same
  `if pair_listed:` gate as `asset_borrowable`; otherwise the raw string is projected
  by `base_asset`. The `borrowability_truncated` branch retains both new fields exactly
  as it retains `asset_borrowable`/interest fields, while only `portfolio_account`
  amounts stay cleared — covered by `test_assemble_user_min_borrow_truncated_branch_retained`.
- **Two-decimal valuation.** New `_user_min_borrow_value_usdt` (`snapshot.py:803-833`)
  mirrors `_max_borrowable_value_usdt` routing (`_STABLE_USD_ASSETS` priced at 1,
  `<ASSET>USDT` lookup, `None` on null/blank/invalid amount or missing/invalid price,
  no warnings) and quantizes with `Decimal("0.01")` + `ROUND_HALF_UP`, `format(…, "f")`
  (no scientific notation). Raw `"0"` yields `"0.00"` (valid zero, not null); negative
  zero is normalized via `if value == 0: value = Decimal(0)`, consistent with
  `_quantize_rate`. Tests pin `1.005 → "1.01"`, `55.555 → "55.56"`, `"0" → "0.00"`,
  and `re.fullmatch(r"-?\d+\.\d{2}", v)` exactly-two-decimals on every non-null value.
- **Eight-decimal contract untouched.** `_quantize_rate` and
  `_max_borrowable_value_usdt` are not modified; the new helper deliberately does not
  call the 8dp path. `test_assemble_max_borrowable_value_usdt_keeps_eight_decimals`
  asserts `"60.00000000"` alongside the new `"60.00"` in the same assembled block.
  Range diff confirms zero changes to the 8dp output path.
- **Strict schema.** `classic_margin.required` gains `user_min_borrow` and
  `user_min_borrow_value_usdt`; both are `anyOf [decimal_string, null]`;
  `additionalProperties: false` unchanged. Negative coverage proves missing-field and
  extra-property both fail `jsonschema.validate`; positive coverage proves
  decimal-string and null acceptance.
- **Fixture/sync updates.** All six `classic_margin` blocks in
  `private-account-v1-design.json` gained the two fields (listed rows → `"<AMOUNT>"`
  placeholders consistent with the fixture's redaction convention; `pair_listed: null`
  rows → `null, null`). `test_phase2_borrow_sort.py` exact-field assertion grew 5→7
  fields with two offline-null assertions — strictly within the breakdown's conditional
  allowance for that file.
- **No external/write-side effects.** Diff adds no endpoint, no signed write, no
  borrow/repay/transfer execution, no retry, no persistence, no new I/O surface;
  `fetch_classic_reference` keeps its existing three GETs and 1h TTL shape. Frontend
  files are untouched (F2/F3 presentation is correctly out of this scope).
- **Test adequacy.** 12+ focused new tests cover map construction, raw preservation
  (zero and non-zero), all null gates (classic_ref absent / pair not listed / map
  missing key), truncated retention, stable and non-stable price routing,
  missing/invalid inputs, exact 2dp + half-up rounding, strict-schema negatives, and
  the unchanged 8dp behavior. Independent rerun is green (394 passed).

## 3. Observations (non-blocking)

- `_user_min_borrow_value_usdt` shares the pre-existing theoretical exposure that
  `Decimal.quantize` under the default 28-digit context could raise on an
  astronomically large amount×price product; the existing 8dp `_quantize_rate` path
  has the same property, so this introduces no new risk class. Realistic Binance
  `userMinBorrow` values are far below that bound.
- `test_user_min_borrow_value_usdt_always_two_decimals` imports `re` inside the test
  body — cosmetic only.

Neither observation affects correctness, contract conformance, or schema validity; no
P0–P3 finding is opened.

## 4. Conclusion

B1 implements the frozen amendment exactly: raw-string preservation, gates identical
to `asset_borrowable` across all three assembly branches, 2dp `ROUND_HALF_UP`
valuation with the zero and failure modes specified, the 8dp maximum-borrow contract
byte-untouched, strict schema with negative coverage, a byte-identical raw public
sample (sha256-verified), adequate tests independently reproduced green, and no
external or write-side effects. Verdict: **ACCEPT**; B1 may proceed to review-2 as
part of the stage-level final gate.

```text
当前 Session ID: unavailable (this Kimi CLI session does not expose a provider-native session ID to the reviewer; operator/runner may record the verified ID into status.json.session_receipts)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/31-review-1-backend.md
本地北京时间: 2026-07-19 01:03:19 CST
下一步模型: bookkeeper（人类操作员记录本 verdict），随后 Claude-GLM 完成 F2+F3 rebound review-1，再准备 review-2
下一步任务: 将本 ACCEPT verdict 落入 status.json tasks[backend-minimum-borrow-contract-b1].review_1 与 review_1 汇总字段，推进剩余 rebound review-1 与 review-2 门
```

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-borrow-task-ui-fake-v1",
  "role": "first_reviewer",
  "model": "kimi-code/kimi-for-coding",
  "verdict": "ACCEPT",
  "diff_fingerprint": "623d059b52723d9ee412519db054a2a25cedf504:d613e05020e5885d8171d26a5d165ced8b1193530ef301ff1622ab35bad028d0",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "Reviewer (Kimi) implemented the stage's separate frontend tasks F2/F3, which are outside this B1 review scope and are cross-reviewed by Claude-GLM; reviewer had no role in B1 design, breakdown, implementation, or fix authorship. Provider isolation from the B1 implementer (zhipu_glm) holds.",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml",
    "schemas/review-verdict.schema.json",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/00-task.md",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/10-design.md",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/11-adr.md",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/14-user-min-borrow-contract-amendment.md",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/21-implementation-backend.md",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/61-test-output-backend.txt",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/status.json",
    "git diff 8163e2128a450116660a92b449fa4d2b97b3448c..623d059b52723d9ee412519db054a2a25cedf504",
    "backend/services/private_client.py",
    "backend/domain/snapshot.py",
    "schemas/api/public-market/snapshot.schema.json",
    "backend/tests/test_private_client.py",
    "backend/tests/test_private_account_v1.py",
    "backend/tests/test_phase2_borrow_sort.py",
    "backend/tests/fixtures/private-account-v1-design.json",
    "reports/api-samples/2026-07-borrow-task-ui-fake-v1/sapi-v1-margin-allAssets.json",
    "reports/api-samples/2026-07-private-account-v1/20260705T232800Z/sapi-v1-margin-allAssets.json"
  ],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [
    "_user_min_borrow_value_usdt shares the pre-existing theoretical Decimal.quantize context-precision exposure (28 digits) with the existing 8dp _quantize_rate path; no new risk class is introduced and realistic Binance userMinBorrow values are far below the bound.",
    "All 409 raw-sample userMinBorrow values are the factual \"0\"; non-zero behavior is covered only by synthetic in-test inputs, as the frozen amendment explicitly permits. A future live sample with a non-zero value may be added as stage follow-up evidence if one becomes available."
  ],
  "next_action": "continue"
}
```
