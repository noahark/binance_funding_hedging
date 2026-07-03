# Review-2: Public Market Contract V2

Reviewer: Codex/GPT
Role: final reviewer / reality checker
Mode: strong-reviewer disclosure override
Reviewed at: 2026-07-03 18:47:33 CST

## Prior Involvement Disclosure

`reviewer_prior_involvement`: `design`

Codex/GPT previously participated as stage designer / direction synthesizer.
This review is allowed only because the user approved the 2026-07-03
strong-reviewer disclosure override and the unrelated decision reviewer
Claude/Fable5 failed runner-level review-2 dispatch. Evidence:

- `reports/agent-runs/2026-07-public-market-contract-v2/review-2-claude-dispatch-failure.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/review-2-claude-dispatch.raw-output.txt`

Codex/GPT did not implement or fix any delivery code for this reviewed stage.
This review treats `docs/product/PRD.md` and
`reports/agent-runs/2026-07-initial-direction/06-direction-synthesis.md` as
higher authority than the stage design files.

## Reviewed Artifacts

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `schemas/review-verdict.schema.json`
- `docs/product/PRD.md`
- `reports/agent-runs/2026-07-initial-direction/06-direction-synthesis.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/00-task.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/10-design.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/11-adr.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/20-implementation.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/30-review-1.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/40-fix-report.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/60-test-output.txt`
- `reports/agent-runs/2026-07-public-market-contract-v2/70-handoff.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/status.json`
- `reports/agent-runs/2026-07-public-market-contract-v2/api-field-matrix.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/api-sample-index.md`
- `docs/api/public-market-contract.md`
- `schemas/api/public-market/snapshot.schema.json`
- `reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/*.json`
- `reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/build-normalized-sample.py`
- `reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/public-market-snapshot.json`
- Frozen diff:
  `git diff --binary 2bb47ad13065827ed1ee91d5d0e231cd312fdc0a..d73eb10187f34696aec4aea8f596c0d3578a1dcf -- . ":(exclude)reports/agent-runs/2026-07-public-market-contract-v2/status.json"`

## Verification Performed

- Recomputed frozen diff hash:
  `de0c199bd7b9121ec2539c6a891f3167043bc1f4412704c3276fe6171b3fdd46`.
- Revalidated normalized sample against
  `schemas/api/public-market/snapshot.schema.json`: `PASS`.
- Re-ran `build-normalized-sample.py "2026-07-03T05:17:38Z"` and revalidated:
  `PASS`, 6 rows, `source_sample_id=20260703T051738Z`.
- Checked the frozen diff file list against `00-task.md` allowed paths.

## Findings

### P1: Review subject includes out-of-scope Harness changes that are not disclosed in stage evidence

Evidence:

- `00-task.md` lines 20-25 limit the contract discovery task to
  `docs/api/public-market-contract.md`, `schemas/api/public-market/*.schema.json`,
  the active stage directory, and
  `reports/api-samples/public-market-contract-v2/**`.
- The frozen review diff `2bb47ad..d73eb10` includes out-of-scope Harness files:
  `.harness-version`, `AGENTS.md`, `agents/registry.yaml`,
  `docs/harness-design.md`, `docs/model-adapters.md`,
  `harness-manifest.yaml`, `reports/agent-runs/README.md`,
  `scripts/validate-stage.py`, and
  `workflows/templates/feature-loop.yaml`.
- `20-implementation.md` lines 65-83 list changed files relative to the review
  base, but do not disclose these Harness changes.
- `status.json` lines 45-64 likewise omits those Harness files from
  `changed_files`.

Impact:

The final reviewer cannot cleanly accept this as a bounded public-market
contract stage. The product contract evidence is mostly sound, but the recorded
diff fingerprint binds unrelated Harness governance changes into the same
review subject while the implementation report and status claim a narrower
changed-file set. Accepting this would weaken the Harness rule that final review
is based on the actual raw diff, not controller summaries or partial file lists.

Recommendation:

Create a clean contract-stage review subject or explicitly repair the evidence
boundary. Preferred fix: create a committed base/head pair whose standard
Harness diff contains only the allowed contract-stage paths plus explicit
review/fix evidence, then update `base_sha`, `head_sha`, `diff_fingerprint`,
`status.changed_files`, `20-implementation.md`, and `70-handoff.md`. If a clean
pair is impossible, expand the stage scope and reports to explicitly include
the Harness governance files and explain why the contract stage is also
accepting them; this is less preferred because it broadens the stage beyond the
user-approved contract task.

## Non-Blocking Observations

- The public-market contract itself is directionally consistent with the PRD and
  initial synthesis: no private endpoints, no keys, clear route classes,
  `lastFundingRate` ambiguity preserved, and bStock tagging separated from
  route class.
- Kimi review-1 accepted with a non-blocking P3 that negative schema tests are
  recorded in `60-test-output.txt` but not replayable from a committed negative
  test script. This remains useful to fix later, but is not the reason for this
  `REWORK`.
- `10-design.md` still contains old review-2 wording that says Codex is
  ineligible if Claude is unavailable. The newer `AGENTS.md`,
  `stage-delivery.yaml`, and `status.json` override it through the documented
  disclosure path. Clean-up is advisable when repairing the evidence boundary.

## Fix Start Prompt

The strict JSON verdict below contains the ready-to-send fix prompt.

## Operational Footer

本地北京时间: 2026-07-03 18:47:33 CST
下一步模型: Claude-GLM
下一步任务: Fix the contract stage evidence boundary so review-2 can verify a clean committed subject, then re-run pre-review validation.

{
  "schema_version": 1,
  "stage_id": "2026-07-public-market-contract-v2",
  "role": "final_reviewer",
  "model": "gpt5.5",
  "verdict": "REWORK",
  "diff_fingerprint": "d73eb10187f34696aec4aea8f596c0d3578a1dcf:de0c199bd7b9121ec2539c6a891f3167043bc1f4412704c3276fe6171b3fdd46",
  "reviewer_prior_involvement": "design",
  "reviewer_prior_involvement_notes": "Codex/GPT previously participated as stage designer / direction synthesizer. User approved strong-reviewer disclosure override after Claude/Fable5 failed runner-level review-2 dispatch; evidence is in reports/agent-runs/2026-07-public-market-contract-v2/review-2-claude-dispatch-failure.md.",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml",
    "schemas/review-verdict.schema.json",
    "docs/product/PRD.md",
    "reports/agent-runs/2026-07-initial-direction/06-direction-synthesis.md",
    "reports/agent-runs/2026-07-public-market-contract-v2/00-task.md",
    "reports/agent-runs/2026-07-public-market-contract-v2/10-design.md",
    "reports/agent-runs/2026-07-public-market-contract-v2/11-adr.md",
    "reports/agent-runs/2026-07-public-market-contract-v2/20-implementation.md",
    "reports/agent-runs/2026-07-public-market-contract-v2/30-review-1.md",
    "reports/agent-runs/2026-07-public-market-contract-v2/40-fix-report.md",
    "reports/agent-runs/2026-07-public-market-contract-v2/60-test-output.txt",
    "reports/agent-runs/2026-07-public-market-contract-v2/70-handoff.md",
    "reports/agent-runs/2026-07-public-market-contract-v2/status.json",
    "reports/agent-runs/2026-07-public-market-contract-v2/api-field-matrix.md",
    "reports/agent-runs/2026-07-public-market-contract-v2/api-sample-index.md",
    "docs/api/public-market-contract.md",
    "schemas/api/public-market/snapshot.schema.json",
    "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/*.json",
    "reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/build-normalized-sample.py",
    "reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/public-market-snapshot.json",
    "git diff --binary 2bb47ad13065827ed1ee91d5d0e231cd312fdc0a..d73eb10187f34696aec4aea8f596c0d3578a1dcf -- . ':(exclude)reports/agent-runs/2026-07-public-market-contract-v2/status.json'"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "Review subject includes out-of-scope Harness changes that are not disclosed in stage evidence",
      "file": "reports/agent-runs/2026-07-public-market-contract-v2/20-implementation.md",
      "line": 65,
      "evidence": "00-task.md lines 20-25 restrict the task to contract docs/schema, the active stage directory, and reports/api-samples/public-market-contract-v2/**. The frozen diff 2bb47ad..d73eb10 also includes .harness-version, AGENTS.md, agents/registry.yaml, docs/harness-design.md, docs/model-adapters.md, harness-manifest.yaml, reports/agent-runs/README.md, scripts/validate-stage.py, and workflows/templates/feature-loop.yaml. 20-implementation.md lines 65-83 and status.json lines 45-64 do not disclose those Harness files.",
      "impact": "Final review cannot accept this as a bounded public-market contract stage because the diff fingerprint binds unrelated Harness governance changes into the reviewed subject while the implementation report and status claim a narrower changed-file set.",
      "recommendation": "Create a clean committed review subject whose standard Harness diff contains only allowed contract-stage paths plus explicit review/fix evidence, or explicitly expand the stage scope and evidence reports to include the Harness governance changes. Prefer the clean subject."
    }
  ],
  "required_fixes": [
    "Repair the contract stage evidence boundary so the recorded base_sha/head_sha/diff_fingerprint and changed_files agree with the actual raw diff and the task file boundaries."
  ],
  "residual_risks": [
    "lastFundingRate settled-vs-estimate remains intentionally ambiguous until a later settle-time sample.",
    "MARGIN_SPOT_CANDIDATE private borrowability remains out of Phase 1.",
    "Negative schema tests are recorded in 60-test-output.txt but not yet packaged as a committed replay script."
  ],
  "fix_start_prompt": "You are Claude-GLM acting as controller/fix implementer for stage_id=2026-07-public-market-contract-v2. Review-2 returned REWORK on diff_fingerprint d73eb10187f34696aec4aea8f596c0d3578a1dcf:de0c199bd7b9121ec2539c6a891f3167043bc1f4412704c3276fe6171b3fdd46. Read raw review file reports/agent-runs/2026-07-public-market-contract-v2/50-review-2.md, status.json, 70-handoff.md, 00-task.md, 20-implementation.md, and the frozen diff command: git diff --binary 2bb47ad13065827ed1ee91d5d0e231cd312fdc0a..d73eb10187f34696aec4aea8f596c0d3578a1dcf -- . ':(exclude)reports/agent-runs/2026-07-public-market-contract-v2/status.json'. Required fix: repair the evidence boundary. Preferred approach: create or identify a clean committed base/head pair whose standard Harness diff contains only the allowed contract-stage paths from 00-task.md plus explicit review/fix evidence; update base_sha, head_sha, diff_fingerprint, status.changed_files, 20-implementation.md, and 70-handoff.md accordingly. If you cannot create a clean pair, stop and route to human_escalation_required rather than inventing a second fingerprint protocol. Do not change Binance contract semantics unless evidence requires it. Do not use API keys, signed endpoints, private endpoints, orders, borrow, repay, transfer, or frontend Binance calls. After repair, run schema validation for reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/public-market-snapshot.json, recompute the standard diff hash, run scripts/validate-stage.py 2026-07-public-market-contract-v2 --phase pre-review, write reports/agent-runs/2026-07-public-market-contract-v2/40-fix-report.md with finding-to-fix mapping, update status.json and 70-handoff.md, and stop for review-2 recheck.",
  "next_action": "fix"
}
