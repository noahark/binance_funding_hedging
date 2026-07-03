# Review-1 (Task A) — Backend Snapshot Service

Stage: `2026-07-public-market-impl-v1`
Reviewer: `kimi-2.7` (reviewer_1, `code_reviewer`)
Subject: Task A backend snapshot service, commit range `H_intake..H_A`

## Fingerprint recomputation

```bash
git diff --binary 32f6f0f7e7a2406cc01e5364ef3557dbfcd2155c..a40b204658cfbe6df2cdeeee27ec5fc8f2bd4d72 -- . ':(exclude)reports/agent-runs/2026-07-public-market-impl-v1/status.json' | shasum -a 256
```

Result: `5148a4734c59cdd4c50e8388464a0b7867d772f8b61054c8eb82a173263d1e93`

Task-A `diff_fingerprint`: `a40b204658cfbe6df2cdeeee27ec5fc8f2bd4d72:5148a4734c59cdd4c50e8388464a0b7867d772f8b61054c8eb82a173263d1e93`

This matches the value recorded in `status.json.tasks.A.diff_fingerprint`.

## Boundary check

`git diff --name-only` over the Task-A range returns exactly 21 paths:

- 19 files under `backend/**`
- `reports/agent-runs/2026-07-public-market-impl-v1/20-implementation-backend.md`
- `reports/agent-runs/2026-07-public-market-impl-v1/60-test-output.txt`

No `frontend/**`, schema, contract doc, raw/normalized sample, or other out-of-scope path appears. Boundary is clean.

## Artifacts inspected

- `reports/agent-runs/2026-07-public-market-impl-v1/00-task.md`
- `reports/agent-runs/2026-07-public-market-impl-v1/10-design.md`
- `reports/agent-runs/2026-07-public-market-impl-v1/11-adr.md`
- `reports/agent-runs/2026-07-public-market-impl-v1/20-implementation-backend.md`
- `reports/agent-runs/2026-07-public-market-impl-v1/60-test-output.txt`
- `reports/agent-runs/2026-07-public-market-impl-v1/status.json`
- `backend/config.py`
- `backend/adapters/binance_public.py`
- `backend/domain/classify.py`
- `backend/domain/normalize.py`
- `backend/domain/snapshot.py`
- `backend/services/snapshot_service.py`
- `backend/app/server.py`
- `backend/tests/conftest.py`
- `backend/tests/test_classify.py`
- `backend/tests/test_normalize.py`
- `backend/tests/test_snapshot.py`
- `backend/tests/test_negative_schema.py`
- `backend/tests/smoke_server.py`
- `schemas/api/public-market/snapshot.schema.json`
- `docs/api/public-market-contract.md`
- `reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/public-market-snapshot.json`
- The raw Task-A diff itself (`git diff --binary ...`)

## Checkpoint verification

1. **Eligible filter**: `SnapshotService.build_snapshot` filters on `status == "TRADING"` and `contractType in ("PERPETUAL", "TRADIFI_PERPETUAL")`. `test_no_non_trading_or_non_perpetual_leakage` passes.
2. **asset_tag**: `asset_tag_for` maps `TRADIFI_PERPETUAL` → `BSTOCK` and `PERPETUAL` → `CRYPTO`, independent of `route_class`. The 6 curated symbols match the expected `(route_class, asset_tag, negative_funding_status)` tuples in `test_classification_matches_frozen_six`.
3. **route_class**: `classify_route` implements the three-case rule; `margin_public.source` is hardcoded `"unverified"` in `build_rows`.
4. **negative_funding_status priority**: `negative_funding_status` is an explicit ordered `if` sequence: `PERP_ONLY_EXCLUDED` → `DISABLED_PERP_ONLY`, then `BSTOCK` → `DISABLED_BSTOCK`, then `SPOT_ONLY_CANDIDATE` → `DISABLED_SPOT_ONLY`, otherwise `PRIVATE_BORROW_VALIDATION_REQUIRED`. MSTRUSDT/TSLAUSDT resolve to `DISABLED_PERP_ONLY`, confirmed by the frozen-six test.
5. **Decimal discipline**: `_abs_rate` uses `Decimal(str(rate_str))`; decimal output fields are copied straight from raw JSON strings. `grep -RnE '\bfloat\(' backend --include='*.py'` returns no matches anywhere in `backend`. Negative schema tests reject float `mark_price` and `last_funding_rate`.
6. **funding_history top-N**: `Config.top_n` defaults to `20`; `top_symbols_by_abs_rate` caps live `/fapi/v1/fundingRate` fetching to the top-N. Offline uses all frozen fixtures.
7. **summary == aggregation over rows**: `assemble_snapshot` builds summary via `_counts(rows, key)`. `test_summary_aggregates_from_rows` cross-checks against a fresh `Counter`.
8. **Three contract warnings**: `CONTRACT_WARNINGS` in `backend/domain/snapshot.py` are preserved verbatim and match the frozen normalized sample exactly.
9. **Validation gate**: `SnapshotService.get_snapshot` calls `jsonschema.validate` before returning; `server.py` catches validation/fetch exceptions and returns HTTP 503, never the invalid snapshot.
10. **Reproducible offline output**: `test_data_time_matches_frozen_sample` confirms `data_time == "2026-07-03T05:11:29Z"`; the 6 curated symbols align with the frozen sample.

## Independent test rerun

```bash
.venv/bin/python -m pytest backend/tests -q
```

Result: `39 passed in 0.61s`

```bash
.venv/bin/python backend/tests/smoke_server.py
```

Result:

```
GET /api/public-market/snapshot -> HTTP 200, schema-valid
  rows=688 warnings=3 total_rows=688
  data_time=2026-07-03T05:11:29Z generated_at=2026-07-03T05:17:38Z source_sample_id=20260703T051738Z
GET / -> HTTP 200, frontend index.html bytes=27982
GET /fixture/public-market-snapshot.json -> HTTP 200, bytes=8900
SMOKE OK
```

## Findings

No P0/P1/P2/P3 findings. Task A meets the acceptance criteria and behavior rules.

## Residual risks (carry forward)

- The live HTTP path is not exercised this stage; all tests and the smoke run offline against frozen fixtures. Live request counts and rate-limit headroom are design figures, not measured.
- The server smoke is single-process (background thread + same-process `urllib`) because the Harness sandbox blocks cross-process loopback TCP. It exercises the real handler and socket.

## Disclosure

I am the Task B (frontend) implementer for this stage, but I had no involvement in Task A's direction synthesis, development breakdown, or design, and I did not write or fix any Task A code. The cross-review pool assigned Task A review-1 to Kimi because Task A's implementer is `claude_glm`.

本地北京时间: 2026-07-03 21:52:29 CST
下一步模型: controller (dispatch Task A to review-2 / integrate Task C)
下一步任务: Record review-1 acceptance and proceed to stage-level review-2.

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-public-market-impl-v1",
  "role": "first_reviewer",
  "model": "kimi-2.7",
  "verdict": "ACCEPT",
  "diff_fingerprint": "a40b204658cfbe6df2cdeeee27ec5fc8f2bd4d72:5148a4734c59cdd4c50e8388464a0b7867d772f8b61054c8eb82a173263d1e93",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "I am the Task B (frontend) implementer for this stage, but I had no involvement in Task A's direction synthesis, development breakdown, or design, and I did not write or fix any Task A code. Cross-review pool assigned Task A review-1 to Kimi because the implementer is claude_glm.",
  "reviewed_artifacts": [
    "reports/agent-runs/2026-07-public-market-impl-v1/00-task.md",
    "reports/agent-runs/2026-07-public-market-impl-v1/10-design.md",
    "reports/agent-runs/2026-07-public-market-impl-v1/11-adr.md",
    "reports/agent-runs/2026-07-public-market-impl-v1/20-implementation-backend.md",
    "reports/agent-runs/2026-07-public-market-impl-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-public-market-impl-v1/status.json",
    "backend/config.py",
    "backend/adapters/binance_public.py",
    "backend/domain/classify.py",
    "backend/domain/normalize.py",
    "backend/domain/snapshot.py",
    "backend/services/snapshot_service.py",
    "backend/app/server.py",
    "backend/tests/conftest.py",
    "backend/tests/test_classify.py",
    "backend/tests/test_normalize.py",
    "backend/tests/test_snapshot.py",
    "backend/tests/test_negative_schema.py",
    "backend/tests/smoke_server.py",
    "schemas/api/public-market/snapshot.schema.json",
    "docs/api/public-market-contract.md",
    "reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/public-market-snapshot.json",
    "git diff --binary 32f6f0f7e7a2406cc01e5364ef3557dbfcd2155c..a40b204658cfbe6df2cdeeee27ec5fc8f2bd4d72 -- . ':(exclude)reports/agent-runs/2026-07-public-market-impl-v1/status.json'"
  ],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [
    "The live HTTP path is not exercised this stage; all tests and the smoke run offline against frozen fixtures. Live request counts and rate-limit headroom are design figures from public docs + top-N design, not measured.",
    "The server smoke is single-process (background thread + same-process urllib) because the Harness sandbox blocks cross-process loopback TCP. It exercises the real handler and socket."
  ],
  "next_action": "continue"
}
```
