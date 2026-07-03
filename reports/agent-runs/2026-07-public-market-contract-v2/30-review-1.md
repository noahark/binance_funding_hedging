# Review-1: Public Market Contract V2

Role: `reviewer_1`, provider=`kimi`, model=`kimi-2.7`, skill=`code_reviewer`, mode=read-only/plan.

Review date: 2026-07-03.

This is a re-review after a previous Kimi review-1 returned `REWORK` for one P1 finding.

## Overall Conclusion

The previous P1 finding has been fixed. `20-implementation.md` now correctly describes the committed-state fingerprint formula and points reviewers to the exact reproduce command in `status.json` and `70-handoff.md`; all stale `HEAD == base`, working-tree, and untracked-file language has been removed.

The updated committed subject range has been recomputed and matches the recorded `diff_fingerprint`:

```text
d73eb10187f34696aec4aea8f596c0d3578a1dcf:de0c199bd7b9121ec2539c6a891f3167043bc1f4412704c3276fe6171b3fdd46
```

`scripts/validate-stage.py 2026-07-public-market-contract-v2 --phase pre-review` passes. The normalized snapshot validates against `schemas/api/public-market/snapshot.schema.json`. The raw margin error bodies (`{"code":-2014,"msg":"API-key format invalid."}`) and the live no-key checks in `60-test-output.txt` support the conclusion that `/sapi/v1/margin/allPairs` and `/sapi/v1/margin/isolated/allPairs` require an API key. The field matrix maps every frontend-visible field to source endpoint, raw JSON path, observed type, nullability, semantics, and evidence. The BSTOCK rule (`contractType == "TRADIFI_PERPETUAL"` -> `asset_tag = "BSTOCK"`) is evidenced by 118 observed symbols, and the normalized sample demonstrates `asset_tag` is independent of `route_class` (e.g., `MSTRUSDT` and `TSLAUSDT` are `BSTOCK` + `PERP_ONLY_EXCLUDED`). The diff contains no backend implementation modules and no order/borrow/repay/transfer/websocket execution code.

No P0 or P1 finding remains. Verdict: **ACCEPT**.

## Findings

### P3: Negative schema tests are not replayable from a committed script

- **severity**: P3
- **title**: Negative schema tests are not replayable from a committed script
- **file**: `reports/agent-runs/2026-07-public-market-contract-v2/60-test-output.txt`
- **line**: 31
- **evidence**: Section 4 of `60-test-output.txt` lists ten tampered cases (`bad asset_tag enum`, `bad route_class enum`, `missing required futures.step_size`, `wrong schema_version const`, etc.) and their rejection results, but the script or commands used to create the tampered samples and validate them against the schema are not committed. `build-normalized-sample.py` only emits the positive sample.
- **impact**: Future reviewers must manually reconstruct the ten tampered inputs to reproduce the negative-test evidence. This is a minor reproducibility gap, not a correctness issue, because the schema constraints are real and the listed mutations are straightforward.
- **recommendation**: Commit a small Python script under `reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/` that reads the normalized sample, applies the ten documented mutations, and asserts each is rejected by `jsonschema.Draft202012Validator`. Record its invocation in `60-test-output.txt`.

## Historical Grok Dispatch Failure

Prior to this Kimi review-1, the controller attempted to dispatch Grok Build (`grok-build`) for review-1. The attempt failed with `model_unavailable`: the adapter preflight passed (`grok models` showed `grok-build` as default and the user was logged in), `scripts/validate-stage.py --phase pre-review` passed, but the dispatched `grok` process hung with 0 bytes of captured output beyond the 900-second timeout and no schema-valid verdict. Per `docs/model-adapters.md` and `agents/registry.yaml`, Grok is not a default Harness review gate; after user approval the stage was re-routed to the Kimi/Claude-GLM cross-review pool. The original timeout record is preserved in `status.json.review_1.prior_dispatch_failures` and the empty captured output is in `reports/agent-runs/2026-07-public-market-contract-v2/review-1-grok-timeout.raw-output.txt`.

## Previous REWORK and Fix

The first Kimi review-1 (fingerprint `1943e8b55c1cfdba018e8eae07428861e444e016:e0ae8c5cc404b0b0ebe45c8f637b6c30689337572a7248e9816181e34301311d`) returned `REWORK` with one P1 finding: `20-implementation.md` contained stale worktree-fingerprint semantics that contradicted the committed-state protocol. The fix was implemented in `20-implementation.md` and mapped in `40-fix-report.md`. This re-review confirms the fix and accepts the stage.

{"schema_version": 1, "stage_id": "2026-07-public-market-contract-v2", "role": "first_reviewer", "model": "kimi-2.7", "verdict": "ACCEPT", "diff_fingerprint": "d73eb10187f34696aec4aea8f596c0d3578a1dcf:de0c199bd7b9121ec2539c6a891f3167043bc1f4412704c3276fe6171b3fdd46", "reviewed_artifacts": ["AGENTS.md", "workflows/templates/feature-loop.yaml", "agents/registry.yaml", "docs/model-adapters.md", "reports/agent-runs/README.md", "schemas/review-verdict.schema.json", "reports/agent-runs/2026-07-public-market-contract-v2/status.json", "reports/agent-runs/2026-07-public-market-contract-v2/70-handoff.md", "reports/agent-runs/2026-07-public-market-contract-v2/00-task.md", "reports/agent-runs/2026-07-public-market-contract-v2/10-design.md", "reports/agent-runs/2026-07-public-market-contract-v2/11-adr.md", "reports/agent-runs/2026-07-public-market-contract-v2/20-implementation.md", "reports/agent-runs/2026-07-public-market-contract-v2/40-fix-report.md", "reports/agent-runs/2026-07-public-market-contract-v2/api-field-matrix.md", "reports/agent-runs/2026-07-public-market-contract-v2/api-sample-index.md", "reports/agent-runs/2026-07-public-market-contract-v2/60-test-output.txt", "docs/api/public-market-contract.md", "schemas/api/public-market/snapshot.schema.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/public-market-snapshot.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/build-normalized-sample.py", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/fapi-v1-exchangeInfo.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/fapi-v1-premiumIndex.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/fapi-v1-fundingRate-BTCUSDT-limit10.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/api-v3-exchangeInfo-curated-BTCETHXVG.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/api-v3-exchangeInfo-full-summary.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/sapi-v1-margin-allPairs-nokey.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/sapi-v1-margin-isolated-allPairs-nokey.json"], "findings": [{"severity": "P3", "title": "Negative schema tests are not replayable from a committed script", "file": "reports/agent-runs/2026-07-public-market-contract-v2/60-test-output.txt", "line": 31, "evidence": "60-test-output.txt section 4 lists ten tampered cases and their rejection results, but the script or commands used to create the tampered samples and validate them against the schema are not committed. build-normalized-sample.py only emits the positive sample.", "impact": "Future reviewers must manually reconstruct the ten tampered inputs to reproduce the negative-test evidence. This is a minor reproducibility gap, not a correctness issue, because the schema constraints are real and the listed mutations are straightforward.", "recommendation": "Commit a small Python script under reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/ that reads the normalized sample, applies the ten documented mutations, and asserts each is rejected by jsonschema Draft202012Validator. Record its invocation in 60-test-output.txt."}], "required_fixes": [], "next_action": "continue", "residual_risks": ["premiumIndex.lastFundingRate settled-vs-estimate semantics remain ambiguous until a settle-time sample is captured in a later phase.", "MARGIN_SPOT_CANDIDATE classification uses only the public spot isMarginTradingAllowed signal; actual account borrowability requires private validation in Phase 2."]}
