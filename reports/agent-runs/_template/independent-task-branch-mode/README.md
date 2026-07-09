# Independent task-branch mode — stage template

Skeleton for a double-owner stage run under the human-operated independent
task-branch trial mode. Spec: `docs/independent-task-branch-mode.md`
(pointer) → the full contract lives in DRAFT-2 rev c2 at
`reports/agent-runs/2026-07-harness-flow-optimization-v1/10-independent-task-branch-mode-draft.md`.

## Layout

```text
status.json                       # frozen pre-dispatch: base_sha + tasks[].allowed_scope (committed at base on the integration branch)
70-handoff.md
evidence/<task-id>/
  20-implementation.md            # committed into C_e by record-checkpoint
  60-test-output.txt              # written by record-checkpoint (uncommitted sidecar, ingested by prepare-review-2)
  checkpoint.json                 # uncommitted sidecar (never committed to the task branch)
  30-review-1.md                  # review-1 narrative (uncommitted; ingested on the integration branch)
  review-1.verdict.json           # {"verdict": "ACCEPT", "diff_fingerprint": "<task_diff_fingerprint>"}
  review-1.attempts.json          # {"invalid_json_attempts": {...}}
```

## Branch topology (git ref constraint)

- Integration branch: `stage/<stage-id>` (holds the single top-level status.json).
- Task branches: `task/<stage-id>/<owner>` — a SEPARATE `task/` namespace, NOT
  nested under `stage/<id>` (git cannot hold both `stage/<id>` and
  `stage/<id>/x`).

## Drive it

```bash
# each task worktree, from the integration/trusted checkout:
scripts/record-checkpoint <stage-id> --task backend --branch task/<stage-id>/backend-glm \
  --task-worktree ../wt-backend --base-sha <base>
# after both review-1 ACCEPT:
scripts/prepare-review-2 <stage-id> --base-sha <base> --integration-branch stage/<stage-id> \
  --backend-worktree ../wt-backend --frontend-worktree ../wt-frontend \
  --human-decision proceed_to_review_2 --rationale "..."
scripts/validate-stage.py <stage-id> --phase pre-review
```

Verify the mechanism end to end with `python3 scripts/tests/itbm_dry_run.py`.
