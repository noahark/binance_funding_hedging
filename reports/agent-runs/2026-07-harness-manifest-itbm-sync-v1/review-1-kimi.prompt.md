<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status:        pending
target_model:  kimi / kimi-code/kimi-for-coding
adapter_cmd:   kimi --model kimi-code/kimi-for-coding -p "$(cat reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/review-1-kimi.prompt.md)"
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/30-review-1.md
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable，设计期定稿后不得修改） ===== -->
You are review-1 for Harness stage `2026-07-harness-manifest-itbm-sync-v1`.

Read-only requirement:

- Do not modify files.
- Do not run destructive commands.
- Review only raw artifacts and the committed diff range recorded in
  `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/status.json`.

Required context:

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `docs/independent-task-branch-mode.md`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/00-task.md`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/10-design.md`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/11-adr.md`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/20-implementation.md`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/60-test-output.txt`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/status.json`
- `harness-manifest.yaml`

Review scope:

- The implementer is Claude-GLM (`zhipu_glm` provider identity).
- You are Kimi (`moonshot_kimi` provider identity), so review-1 provider
  isolation is satisfied if you use a fresh session.
- Confirm `harness-manifest.yaml` now includes these specific sync assets:
  - `docs/independent-task-branch-mode.md`
  - `scripts/_itbm.py`
  - `scripts/record-checkpoint`
  - `scripts/prepare-review-2`
  - `scripts/tests/itbm_dry_run.py`
- Confirm the implementation did not add broad `scripts/` ownership and did not
  modify protected Harness behavior files outside the task scope.
- Confirm the recorded tests are sufficient for this manifest-only stage.

Diff instructions:

1. Read `base_sha`, `head_sha`, and `diff_fingerprint` from
   `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/status.json`.
2. Inspect:
   `git diff --binary <base_sha>..<head_sha> -- . ":(exclude)reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/status.json"`
3. Do not review a moving `HEAD` diff as the gate diff.

Return format:

- Start with concise findings, ordered by severity.
- End with one strict JSON object matching `schemas/review-verdict.schema.json`.
- For `ACCEPT`, use `"next_action": "continue"`.
- For `REWORK`, include `fix_start_prompt`.
- `reviewer_prior_involvement` must be `"none"`.

The final JSON must include:

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-harness-manifest-itbm-sync-v1",
  "role": "first_reviewer",
  "model": "kimi-code/kimi-for-coding",
  "verdict": "ACCEPT | REWORK | BLOCKED",
  "diff_fingerprint": "<copy from status.json>",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [],
  "next_action": "continue | fix | human_gate"
}
```
