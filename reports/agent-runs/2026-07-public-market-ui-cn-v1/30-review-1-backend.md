# Review-1 Report — Task A: lastFundingRate warning semantic amendment

- **Stage**: `2026-07-public-market-ui-cn-v1`
- **Reviewer**: Kimi (`kimi-2.7`), `code_reviewer` skill
- **Task reviewed**: A — `CONTRACT_WARNINGS[1]` wording amendment + contract doc + tests
- **Implementer**: Claude-GLM (`glm-5.2[1m]`)
- **Review type**: cross-review (read-only; product files not modified)

## Recomputed diff fingerprint

```bash
git diff --binary b84a34235aa5b37bb0ce83f23ac35e4e5e686899..dba4c12ce61745ef393142af2255a3fc519bf4eb -- . ':(exclude)reports/agent-runs/2026-07-public-market-ui-cn-v1/status.json' | shasum -a 256
```

Result:

```text
8afc3dcf42da591bb171f6622937455315d78e1f2167cb672c4cad96a7d38318
```

Task-A `diff_fingerprint`:

```text
dba4c12ce61745ef393142af2255a3fc519bf4eb:8afc3dcf42da591bb171f6622937455315d78e1f2167cb672c4cad96a7d38318
```

Matches the value recorded in `status.json.tasks.A.diff_fingerprint`.

## Scope verification

`git show --name-only --format= dba4c12` returns exactly the four expected files:

- `backend/domain/snapshot.py`
- `backend/tests/test_snapshot.py`
- `docs/api/public-market-contract.md`
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/20-implementation-backend.md`

No frontend, schemas, classify/normalize, services, adapters, agents/workflows/scripts, or api-samples files are touched by `dba4c12`.

## Checkpoint findings

### 1. `snapshot.py`: single string change only

`git diff d3d6e7c..dba4c12 -- backend/domain/snapshot.py` is exactly one `-`/`+` line pair at `CONTRACT_WARNINGS[1]`.

`build_rows`, `assemble_snapshot`, all other constants and functions are byte-identical to the base.

### 2. `warnings[1]` wording matches `00-task.md:51-57`

Actual string in `backend/domain/snapshot.py:19`:

> "premiumIndex.lastFundingRate is the real-time estimate for the CURRENT funding period and is charged at nextFundingTime; it drifts until settlement (mid-period divergence from settled history evidenced under reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/). Settled history comes from /fapi/v1/fundingRate; do not present the estimate as a settled value."

This matches the required English wording in `00-task.md` verbatim, including the evidence path.

### 3. Rows / API payload otherwise frozen

Confirmed by the single-line `snapshot.py` diff and by the Task C field-identity replay in `60-test-output.txt` Section 5: rows are field-identical to the accepted `548ae0d` baseline (647 == 647); only `warnings[1]` differs. Independently recomputed: the `d3d6e7c..dba4c12` diff contains no change to `build_rows` or `assemble_snapshot`.

### 4. Contract doc in lockstep

`git diff d3d6e7c..dba4c12 -- docs/api/public-market-contract.md` touches only:

- The `lastFundingRate` funding-semantics paragraph (now states real-time estimate for the CURRENT period, drift, evidence path, and settled-history source).
- The Open Verification Items entry, which moves from `PARTIALLY RESOLVED` to `RESOLVED (2026-07-04, stage 2026-07-public-market-ui-cn-v1)` and cites the same evidence path and `verify-funding-semantics.py` PASS.

All other contract-doc content is unchanged.

### 5. Forbidden files untouched this stage

```bash
git diff b84a342..dba4c12 -- backend/domain/classify.py backend/domain/normalize.py backend/services backend/adapters schemas/
```

Output is empty. No boundary crossing.

### 6. Tests: assertion-only, no logic change

`backend/tests/test_snapshot.py` adds two assertions inside the existing `test_three_contract_warnings_preserved`:

- `"real-time estimate" in w1`
- `"2026-07-public-market-ui-cn-v1/20260704T044945Z" in w1`

All other test logic is unchanged.

Test run:

```bash
.venv/bin/python -m pytest backend/tests -q
```

Result: `54 passed in 0.67s`.

### 7. No live HTTP / decimal discipline

```bash
grep -RnE '\bfloat\(' backend/domain backend/services
```

No matches (exit 1). Decimal discipline is preserved.

## Evidence verification

Evidence directory exists:
`reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/`

- `evidence-index.md` records sha256 of raw captures and states the capture proves mid-period divergence.
- `verify-funding-semantics.py` was re-run offline:

```text
BTCUSDT   lastFundingRate=   0.00010000 | settled=   0.00010000 @ 07-04 00:00 UTC | next=07-04 08:00 UTC | equal=True
ETHUSDT   lastFundingRate=   0.00008538 | settled=   0.00009748 @ 07-04 00:00 UTC | next=07-04 08:00 UTC | equal=False
SOLUSDT   lastFundingRate=   0.00006761 | settled=   0.00007283 @ 07-04 00:00 UTC | next=07-04 08:00 UTC | equal=False
TSLAUSDT  lastFundingRate=   0.00000000 | settled=   0.00000000 @ 07-04 00:00 UTC | next=07-04 08:00 UTC | equal=True
PASS: 2/4 symbols diverge mid-period (ETHUSDT, SOLUSDT); lastFundingRate is NOT a settled-history echo -> in-period real-time estimate, charged at nextFundingTime.
EXIT 0
```

Evidence path cited in code and contract doc matches the actual directory.

## Reviewer prior-involvement disclosure

- `reviewer_prior_involvement`: `none`
- Notes: I (Kimi, `kimi-2.7`) am the Task B implementer in this same stage, but I had no involvement in Task A's direction synthesis, development breakdown, design, implementation, or fix authorship. Task A was implemented by Claude-GLM (`glm-5.2[1m]`).

## Residual risks (carry forward)

The lastFundingRate evidence capture is a single mid-period snapshot proving divergence and 15-minute drift. It is read-only intake evidence and was not re-fetched during this stage. This is acceptable for a wording amendment stage and is recorded as a non-blocking residual.

## Conclusion

All Task A checkpoints pass. The change is a single constant-string amendment in `CONTRACT_WARNINGS[1]`, with matching contract-doc and test updates. No forbidden files were touched, rows are unchanged, tests pass, and the diff fingerprint matches the recorded value.

本地北京时间: 2026-07-04 13:51:57 CST
下一步模型: controller → review-1 Task B (fresh read-only Claude-GLM) → review-2 (Codex/GPT)
下一步任务: 将本 review-1 报告与 JSON verdict 提交 controller，进入 Task B review-1。

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-public-market-ui-cn-v1",
  "role": "first_reviewer",
  "model": "kimi-2.7",
  "verdict": "ACCEPT",
  "diff_fingerprint": "dba4c12ce61745ef393142af2255a3fc519bf4eb:8afc3dcf42da591bb171f6622937455315d78e1f2167cb672c4cad96a7d38318",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "I (Kimi, kimi-2.7) am the Task B implementer in this same stage, but I had no involvement in Task A's direction synthesis, development breakdown, design, implementation, or fix authorship. Task A was implemented by Claude-GLM (glm-5.2[1m]).",
  "reviewed_artifacts": [
    "reports/agent-runs/2026-07-public-market-ui-cn-v1/00-task.md",
    "reports/agent-runs/2026-07-public-market-ui-cn-v1/10-design.md",
    "reports/agent-runs/2026-07-public-market-ui-cn-v1/11-adr.md",
    "reports/agent-runs/2026-07-public-market-ui-cn-v1/20-implementation-backend.md",
    "reports/agent-runs/2026-07-public-market-ui-cn-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-public-market-ui-cn-v1/status.json",
    "backend/domain/snapshot.py",
    "backend/tests/test_snapshot.py",
    "docs/api/public-market-contract.md",
    "reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/evidence-index.md",
    "reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/verify-funding-semantics.py",
    "reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/verify-output.txt"
  ],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [
    "The lastFundingRate evidence capture is a single mid-period snapshot proving divergence plus 15-minute drift; it is read-only intake evidence and was not re-fetched this stage."
  ],
  "next_action": "continue"
}
```
