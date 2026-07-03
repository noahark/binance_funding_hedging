# Review-1 (Task A) — Backend bStock Alias Amendment

Stage: `2026-07-public-market-bstock-alias-v1`
Reviewer: `kimi-2.7` (reviewer_1, `code_reviewer`)
Subject: Task A contract amendment + backend bStock alias repair, commit range `H_intake..H_A` = `d240e43..1f94c84`

## Fingerprint recomputation

```bash
git diff --binary d240e43e75034a6718ede79bc295d39e77cd860e..1f94c842a67ac75b170f796b17cb08172457b5d7 -- . ':(exclude)reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json' | shasum -a 256
```

Result: `fe6d0bd9d16ea2e75c54b59ed9469f206c5e733dc4d159ba35c959d63ad4c815`

Task-A `diff_fingerprint`: `1f94c842a67ac75b170f796b17cb08172457b5d7:fe6d0bd9d16ea2e75c54b59ed9469f206c5e733dc4d159ba35c959d63ad4c815`

This **matches** the value recorded in `status.json.tasks.A.diff_fingerprint`.

## Boundary check

`git diff --name-only d240e43e75034a6718ede79bc295d39e77cd860e..1f94c842a67ac75b170f796b17cb08172457b5d7` returns 14 paths:

- `schemas/api/public-market/snapshot.schema.json`
- `docs/api/public-market-contract.md`
- `backend/domain/normalize.py`
- `backend/domain/snapshot.py`
- `backend/tests/conftest.py`
- `backend/tests/fixtures/bstock-alias-raw/api-v3-exchangeInfo.json`
- `backend/tests/fixtures/bstock-alias-raw/fapi-v1-exchangeInfo.json`
- `backend/tests/fixtures/bstock-alias-raw/fapi-v1-fundingRate-TSLAUSDT-limit5.json`
- `backend/tests/fixtures/bstock-alias-raw/fapi-v1-premiumIndex.json`
- `backend/tests/test_negative_schema.py`
- `backend/tests/test_normalize.py`
- `backend/tests/test_snapshot.py`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/20-implementation-backend.md`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/60-test-output.txt`

All paths are inside the Task A scope. The only path not explicitly enumerated in the review dispatch is `backend/tests/conftest.py`, which is under `backend/tests/**` and therefore in scope. No `frontend/**`, `backend/domain/classify.py`, `backend/config.py`, `reports/api-samples/**`, or any other forbidden path appears. Boundary is clean.

## Artifacts inspected

- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/00-task.md`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/10-design.md`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/11-adr.md`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/20-implementation-backend.md`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/60-test-output.txt`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json`
- `backend/domain/normalize.py`
- `backend/domain/snapshot.py`
- `backend/domain/classify.py` (verified unchanged)
- `backend/tests/conftest.py`
- `backend/tests/test_normalize.py`
- `backend/tests/test_snapshot.py`
- `backend/tests/test_negative_schema.py`
- `backend/tests/test_classify.py` (verified unchanged)
- `backend/tests/fixtures/bstock-alias-raw/*.json`
- `schemas/api/public-market/snapshot.schema.json`
- `docs/api/public-market-contract.md`
- The raw Task-A diff itself (`git diff --binary d240e43..1f94c84`)

## Checkpoint verification

1. **`backend/domain/normalize.py:resolve_spot_leg`** — Three branches are implemented exactly as required:
   - `base_asset + quote_asset` exact match → `("exact_symbol")`.
   - Only when `contract_type == "TRADIFI_PERPETUAL"`, alias `base_asset + "B" + quote_asset` → `("bstock_b_suffix_alias")`.
   - Otherwise `(None, None)`.
   Exact is checked first, so even a TRADIFI symbol with an exact spot leg uses `exact_symbol` (covered by `test_resolve_spot_leg_exact_beats_alias_for_tradifi`). Normal `PERPETUAL` never falls back to the B-suffix alias (covered by `test_resolve_spot_leg_alias_not_triggered_for_perpetual`).

2. **`backend/domain/snapshot.py:build_rows`** — Replaced the old `spot = spot_by_sym.get(sym)` with `spot, match_type = resolve_spot_leg(...)`. `spot.match_type` is filled into the row. `classify_route` and `negative_funding_status` calls are unchanged. `CONTRACT_WARNINGS[2]` now states the alias rule, contains `TRADIFI_PERPETUAL`, and explicitly says the bStock collateral ratio is dynamic/unknown and not hard-coded.

3. **`backend/domain/classify.py` unchanged** — `git diff d240e43..1f94c84 -- backend/domain/classify.py` is empty. The priority sequence `PERP_ONLY_EXCLUDED → BSTOCK → SPOT_ONLY_CANDIDATE → MARGIN_SPOT_CANDIDATE` is intact.

4. **Schema** — `spot.match_type` is declared as a nullable enum `["exact_symbol", "bstock_b_suffix_alias", null]` and is **not** in the `spot.required` list. The frozen curated sample (which has no `match_type`) therefore remains schema-valid.

5. **Semantic闭环** — A TRADIFI futures symbol (e.g. `TSLAUSDT`) with a B-suffix spot/margin leg (`TSLABUSDT`) now resolves to `MARGIN_SPOT_CANDIDATE` and `positive_funding_enabled=true`. Because `asset_tag=BSTOCK` takes priority over the candidate route in `negative_funding_status`, the row resolves to `DISABLED_BSTOCK`. This is achieved entirely by the existing classifier plus the alias join; no `classify.py` change is needed. `test_bstock_alias_classification`, `test_bstock_negative_rate_still_disabled`, and `test_bstock_no_spot_match_type_null` cover the three cases.

6. **Tests** — `backend/tests/fixtures/bstock-alias-raw/**` files all carry a top-level `_synthetic` marker and are explicitly marked as offline/synthetic (not live, not frozen evidence). `test_normalize.py` adds 5 `resolve_spot_leg` tests. `test_snapshot.py` adds 6 bStock alias tests. `test_negative_schema.py` adds rejection of invalid `match_type` plus validation that `null` is valid. `test_classify.py` is unchanged, providing regression protection for the priority sequence.

7. **Decimal/float discipline** — `grep -RnE '\bfloat\(' backend --include='*.py'` returns no matches (exit code 1 = clean). Decimal fields remain strings.

8. **`margin_public.source` unchanged** — Still `"unverified"` and `public_cross_margin_pair` is still `null` in every row. No collateral ratio is hard-coded.

9. **JSON schema validity of synthetic fixture output** — `test_bstock_alias_snapshot_validates` passes, and the Task C integration script (`task-c-integration-check.py`) reports `[PASS] assembled snapshot is schema-valid (match_type included)`. `json_schema_valid = true`.

## Independent test rerun

```bash
.venv/bin/python -m pytest backend/tests -q
```

Result:

```text
....................................................                     [100%]
52 passed in 0.82s
```

```bash
.venv/bin/python -m pytest backend/tests/test_normalize.py backend/tests/test_snapshot.py backend/tests/test_negative_schema.py -q
```

Result:

```text
...........................................                              [100%]
43 passed in 0.63s
```

`scripts/validate-stage.py 2026-07-public-market-bstock-alias-v1 --phase pre-review` was run. It failed because of two untracked review-prompt files (`review-1-backend-kimi-prompt.md`, `review-1-frontend-glm-prompt.md`) created by the controller before dispatch. These are workflow artifacts, not product code, and do not affect Task A review evidence.

## Findings

No P0/P1/P2/P3 findings. Task A meets the acceptance criteria and behavior rules.

## Residual risks (carry forward)

- The bStock alias rule is verified only against the synthetic offline fixture. No live Binance bStock spot/margin payload is captured in this stage.
- The alias logic assumes the quote asset is always `USDT` (the `build_rows` caller passes `"USDT"`). If the project later supports non-USDT bStocks, the alias construction must be revisited.
- The live HTTP path is unchanged and not exercised this stage; all verification is offline.

## Disclosure

I am the Task B (frontend) implementer for this stage, but I had no involvement in Task A's direction synthesis, development breakdown, or design, and I did not write or fix any Task A code. The cross-review pool assigned Task A review-1 to Kimi because Task A's implementer is `claude_glm`.

本地北京时间: 2026-07-04 00:00:28 CST
下一步模型: controller (dispatch Task A to review-2)
下一步任务: Record review-1 ACCEPT and proceed to stage-level review-2.

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-public-market-bstock-alias-v1",
  "role": "first_reviewer",
  "model": "kimi-2.7",
  "verdict": "ACCEPT",
  "diff_fingerprint": "1f94c842a67ac75b170f796b17cb08172457b5d7:fe6d0bd9d16ea2e75c54b59ed9469f206c5e733dc4d159ba35c959d63ad4c815",
  "fingerprint_matches_status": true,
  "json_schema_valid": true,
  "reviewer_prior_involvement": "task_b_frontend_implementer",
  "reviewer_prior_involvement_notes": "我是本阶段 Task B（前端）实现者；未参与 Task A 的 direction/breakdown/design，未写任何 Task A 代码。跨审查池因 Task A 实现者是 claude_glm 而把 review-1 分配给 Kimi。",
  "reviewed_artifacts": [
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/00-task.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/10-design.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/11-adr.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/20-implementation-backend.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json",
    "backend/domain/normalize.py",
    "backend/domain/snapshot.py",
    "backend/domain/classify.py",
    "backend/tests/conftest.py",
    "backend/tests/test_normalize.py",
    "backend/tests/test_snapshot.py",
    "backend/tests/test_negative_schema.py",
    "backend/tests/test_classify.py",
    "backend/tests/fixtures/bstock-alias-raw/api-v3-exchangeInfo.json",
    "backend/tests/fixtures/bstock-alias-raw/fapi-v1-exchangeInfo.json",
    "backend/tests/fixtures/bstock-alias-raw/fapi-v1-fundingRate-TSLAUSDT-limit5.json",
    "backend/tests/fixtures/bstock-alias-raw/fapi-v1-premiumIndex.json",
    "schemas/api/public-market/snapshot.schema.json",
    "docs/api/public-market-contract.md",
    "git diff --binary d240e43e75034a6718ede79bc295d39e77cd860e..1f94c842a67ac75b170f796b17cb08172457b5d7 -- . ':(exclude)reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json'"
  ],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [
    "The bStock alias rule is verified only against the synthetic offline fixture. No live Binance bStock spot/margin payload is captured in this stage.",
    "The alias logic assumes the quote asset is always USDT (build_rows passes 'USDT' to resolve_spot_leg). Non-USDT bStocks would require revisiting the alias construction.",
    "The live HTTP path is unchanged and not exercised this stage; all verification is offline."
  ],
  "next_action": "continue"
}
```
