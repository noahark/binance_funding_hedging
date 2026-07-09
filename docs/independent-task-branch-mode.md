# Independent Task-Branch Mode

Status: **TRIAL** (enablement landed 2026-07-08). This is an optional execution
variant of `workflows/templates/stage-delivery.yaml` for double-owner stages
(GLM backend + Kimi frontend) where the two product task scopes are disjoint. It
lets both tasks reach review-1 with zero extra human involvement, folding the one
unavoidable integration/serialization point into the human's review-2
preparation.

The full, reviewed contract is DRAFT-2 rev c2:
`reports/agent-runs/2026-07-harness-flow-optimization-v1/10-independent-task-branch-mode-draft.md`
(reviewed to 2×ACCEPT; see that stage's `status.json.decision_log`
DEC-2026-07-08-001..004).

## What it is

- **Recorder** `scripts/record-checkpoint` — deterministic script (no model),
  runs from a trusted checkout, anchors one task branch to review-1 (commit C_e,
  canonical fingerprint, product rebind hash, task-local evidence). It is NOT a
  model bookkeeper and its output is independently recomputable from git.
- **Integrator** `scripts/prepare-review-2` — deterministic script, ingests the
  two task worktrees' uncommitted checkpoint + review-1 evidence, enforces
  anti-stale-tip, merges the disjoint branches atomically, proves the rebind,
  reruns full tests, and writes the single top-level `status.json` for review-2.
- Both share `scripts/_itbm.py` (the pinned canonical fingerprint invocation,
  decision C).

## Invariants preserved

Committed-state review gates, the single canonical diff fingerprint (no worktree
fingerprint), no new status enum values, cross-provider review-1 (GLM↔Kimi),
human-executed review-2 dispatch (Codex→Claude). Running the scripts / git /
pytest / `validate-stage.py` is not model dispatch.

## Verify

```bash
python3 scripts/tests/itbm_dry_run.py   # 13 assertions: positive path + fail-closed gates
```

Template: `reports/agent-runs/_template/independent-task-branch-mode/`.
Schema: `schemas/independent-task-branch-mode.schema.json`.
