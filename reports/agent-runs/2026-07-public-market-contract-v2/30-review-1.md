# Review-1 Recheck: Public Market Contract V2 — Clean Subject

Role: `reviewer_1`, provider=`kimi`, model=`kimi-2.7`, skill=`code_reviewer`, mode=read-only/plan.

Review date: 2026-07-03. Recheck verdict at: 2026-07-03T11:45:51Z.

> **Dispatch evidence (controller note):** This clean-subject recheck was
> dispatched via
> `reports/agent-runs/2026-07-public-market-contract-v2/review-1-kimi-recheck.prompt.md`.
> Kimi also emitted a matching stdout JSON verdict captured in
> `reports/agent-runs/2026-07-public-market-contract-v2/review-1-kimi-recheck.raw-output.txt`
> (`verdict=ACCEPT`, `diff_fingerprint=a25e431…53484d21…`). The controller
> independently recomputed the fingerprint (`53484d21…`) and schema-validated
> both JSON verdicts (0 errors each) because controller and implementer share
> provider (`claude_glm`); reviewer identity is `moonshot_kimi`, distinct from
> both.

## Overall Conclusion

This is a lightweight review-1 recheck of the **clean contract-stage subject** after review-2 found that the prior frozen range bound out-of-scope Harness governance changes into the review subject. The contract semantics have not changed; the only substantive change is the repaired evidence boundary.

I verified the clean subject directly:

- `base_sha`: `2e6b5a0eaa0cd4dbbc94cc2bab9b142a7aaa3130`
- `head_sha`: `a25e4316019197fd3e09bd6827b8aa7c4e2ce36f`
- Recomputed fingerprint:
  `a25e4316019197fd3e09bd6827b8aa7c4e2ce36f:53484d21b25373e524ae6abfd8c05883b4cd2c471ccc45f0e98aef51691b41bf`
  — matches `status.json`.
- `scripts/validate-stage.py 2026-07-public-market-contract-v2 --phase pre-review`: PASSED.
- Normalized snapshot re-validates against `schemas/api/public-market/snapshot.schema.json`: PASS (6 rows, `source_sample_id=20260703T051738Z`).
- `git diff --binary <base>..<head>` contains only contract-stage paths allowed by `00-task.md`; no out-of-scope Harness governance files are in the diff.
- The contract content files (`docs/api/public-market-contract.md`, `api-field-matrix.md`, `api-sample-index.md`, `60-test-output.txt`, raw samples, normalized snapshot, generator) are byte-identical to the prior accepted review subject (`d73eb10`). `20-implementation.md` differs only by updating the "Files changed" section and evidence-integrity note to describe the clean base; no contract conclusion changed.

No P0/P1 findings. The one P3 finding from the prior review-1 (negative schema tests not replayable from a committed script) remains non-blocking and is unchanged in severity.

Verdict: **ACCEPT**.

## Harness-Approved Equivalence Decision

Per the standard Harness `diff_fingerprint` protocol, a review verdict is bound to a specific `base_sha..head_sha` range. The prior Kimi review-1 ACCEPT (`d73eb10:de0c199b…`) covered a subject that included undisclosed out-of-scope Harness paths. The repaired clean subject (`a25e431:53484d…`) excludes those paths. This recheck establishes that:

1. The clean subject is a **normal committed tree** on both ends (not a worktree fingerprint).
2. The standard Harness fingerprint formula is unchanged.
3. All contract-stage delivery content is identical to the previously reviewed subject.
4. The only meaningful change is the removal of out-of-scope Harness governance paths from the review diff.

Therefore, the prior review-1 ACCEPT conclusion is **equivalent and reapplicable** to the clean subject `a25e431:53484d…`, and this recheck records an explicit Harness-approved equivalence decision to that effect. No new REWORK is required.

## Findings

No P0 or P1 findings.

### P3 (residual, non-blocking): Negative schema tests are not replayable from a committed script

- **severity**: P3
- **title**: Negative schema tests are not replayable from a committed script
- **file**: `reports/agent-runs/2026-07-public-market-contract-v2/60-test-output.txt`
- **line**: 31
- **evidence**: Section 4 lists ten tampered cases and their rejection results, but the script or commands used to create the tampered samples and validate them are not committed. `build-normalized-sample.py` only emits the positive sample.
- **impact**: Minor reproducibility gap; not a correctness issue because the schema constraints are real.
- **recommendation**: Commit a small Python script under `reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/` that applies the ten documented mutations and asserts each is rejected by `jsonschema.Draft202012Validator`.

## Historical Notes Preserved

- Historical Grok review-1 dispatch failure: see `status.json.review_1.prior_dispatch_failures` and `reports/agent-runs/2026-07-public-market-contract-v2/review-1-grok-timeout.raw-output.txt`.
- Prior Kimi review-1 REWORK/ACCEPT cycle and the `20-implementation.md` fingerprint fix: see earlier sections of `30-review-1.md` and `40-fix-report.md`.
- Review-2 evidence-boundary repair and clean subject rebuild: see `50-review-2.md` and `40-fix-report.md`.

{"schema_version": 1, "stage_id": "2026-07-public-market-contract-v2", "role": "first_reviewer", "model": "kimi-2.7", "verdict": "ACCEPT", "diff_fingerprint": "a25e4316019197fd3e09bd6827b8aa7c4e2ce36f:53484d21b25373e524ae6abfd8c05883b4cd2c471ccc45f0e98aef51691b41bf", "reviewer_prior_involvement": "none", "reviewer_prior_involvement_notes": "Kimi did not participate in direction synthesis, design, implementation, or fix authorship for this stage. This recheck is an independent cross-review of the clean contract-stage subject.", "reviewed_artifacts": ["reports/agent-runs/2026-07-public-market-contract-v2/status.json", "reports/agent-runs/2026-07-public-market-contract-v2/70-handoff.md", "reports/agent-runs/2026-07-public-market-contract-v2/20-implementation.md", "reports/agent-runs/2026-07-public-market-contract-v2/40-fix-report.md", "reports/agent-runs/2026-07-public-market-contract-v2/api-field-matrix.md", "reports/agent-runs/2026-07-public-market-contract-v2/api-sample-index.md", "reports/agent-runs/2026-07-public-market-contract-v2/60-test-output.txt", "docs/api/public-market-contract.md", "schemas/api/public-market/snapshot.schema.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/public-market-snapshot.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/build-normalized-sample.py", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/fapi-v1-exchangeInfo.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/fapi-v1-premiumIndex.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/fapi-v1-fundingRate-BTCUSDT-limit10.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/api-v3-exchangeInfo-curated-BTCETHXVG.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/api-v3-exchangeInfo-full-summary.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/sapi-v1-margin-allPairs-nokey.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/sapi-v1-margin-isolated-allPairs-nokey.json"], "findings": [{"severity": "P3", "title": "Negative schema tests are not replayable from a committed script", "file": "reports/agent-runs/2026-07-public-market-contract-v2/60-test-output.txt", "line": 31, "evidence": "Section 4 lists ten tampered cases and their rejection results, but the script or commands used to create the tampered samples and validate them are not committed. build-normalized-sample.py only emits the positive sample.", "impact": "Minor reproducibility gap; not a correctness issue because the schema constraints are real.", "recommendation": "Commit a small Python script under reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/ that applies the ten documented mutations and asserts each is rejected by jsonschema.Draft202012Validator."}], "required_fixes": [], "next_action": "continue", "residual_risks": ["premiumIndex.lastFundingRate settled-vs-estimate semantics remain ambiguous until a settle-time sample is captured in a later phase.", "MARGIN_SPOT_CANDIDATE classification uses only the public spot isMarginTradingAllowed signal; actual account borrowability requires private validation in Phase 2.", "Harness-approved equivalence decision: the prior review-1 ACCEPT conclusion for d73eb10:de0c199b is reapplicable to the clean subject a25e431:53484d because the clean subject excludes only out-of-scope Harness governance paths and all contract-stage delivery content is identical. No new REWORK is required."]}
