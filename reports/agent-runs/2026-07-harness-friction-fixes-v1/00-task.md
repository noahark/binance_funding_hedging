# Stage Task

## Objective

Repair the Harness friction exposed by the first real single-owner run so future
Harness-only stages do not repeatedly hit the same review-gate and evidence
capture problems.

## Scope

Prioritize fixes that materially reduce stage execution friction:

1. Prevent validator designer-overlap false positives before review-2 reviewer
   selection.
2. Fix single-owner dispatch/checkpoint ordering so validator evidence is inside
   the reviewed range, or so the reviewed range is explicitly recomputed after
   validator evidence lands.
3. Improve `record-checkpoint --single-owner` so it writes or prepares
   top-level `status.json` review metadata instead of forcing manual
   transcription.
4. Add validator evidence-output support or an equivalent pattern that avoids
   `validate-stage.py --phase pre-review | tee <repo-file>` dirtying the
   worktree during the clean-worktree check.
5. Document and validate the delivery-anchored `head_sha` convention and
   validator-log fixed-point property.
6. Tighten model dispatch/status templates so actual model fallback
   (`claude-opus-4-8` after Fable5 quota/unavailability) is recorded cleanly.
7. Improve review-output hygiene where feasible without inventing new adapter
   infrastructure.
8. Ensure generated `fix_start_prompt.next_action` reflects the true next step
   after a REWORK, especially review-1 redispatch before review-2.

## Allowed Files

The development breakdown must narrow this list, but likely allowed paths are:

- `scripts/validate-stage.py`
- `scripts/record-checkpoint`
- `scripts/_itbm.py`
- `scripts/tests/**`
- `reports/agent-runs/_template/**`
- `workflows/templates/stage-delivery.yaml`
- `docs/independent-task-branch-mode.md`
- `docs/model-adapters.md`
- `reports/agent-runs/README.md`
- `AGENTS.md` only if a hard gate or authority-level clarification is required
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/**`

## Forbidden Files

- `backend/**`
- `frontend/**`
- Product docs under `docs/product/**`, unless only referenced as context
- API samples under `reports/api-samples/**`
- Credential, token, cookie, private key, or full environment dumps

## Acceptance Criteria

- `reports/agent-runs/_template/status.json` no longer causes unselected Codex
  review-2 preference to be treated as selected reviewer identity.
- `scripts/validate-stage.py` no longer fails pre-review solely because an
  unselected review-2 preferred provider overlaps with the designer.
- Single-owner flow has a documented and tested path where validator evidence
  is included in, or safely reconciled with, the reviewed range.
- `record-checkpoint --single-owner` behavior and documentation match: either
  it writes/prepares top-level `status.json` metadata, or docs/templates stop
  claiming it does.
- Validator evidence capture has a supported command pattern that does not
  dirty the worktree before the clean-worktree check.
- Delivery-anchored `head_sha` and validator fixed-point semantics are
  explicitly documented for reviewers and stage operators.
- Tests cover the fixed failure modes, including at least:
  - unselected `review_2.primary_provider` / preferred provider does not trip
    designer-overlap checks before review-2 selection;
  - selected review-2 reviewer still enforces provider isolation and disclosure;
  - single-owner checkpoint/status metadata path;
  - validator evidence-output or clean-worktree-safe capture.
- Existing `python3 scripts/tests/itbm_dry_run.py` still passes.
- `python3 -m py_compile scripts/validate-stage.py scripts/_itbm.py` passes.
- `scripts/validate-stage.py 2026-07-harness-friction-fixes-v1 --phase pre-review`
  passes before review-1 dispatch.

## Non-Goals

- Do not change product runtime behavior.
- Do not replace the whole Harness state machine.
- Do not add a second fingerprint protocol.
- Do not change provider identity rules: `claude_glm` remains `zhipu_glm`,
  not Anthropic.

本地北京时间: 2026-07-09 13:42:58 CST
下一步模型: claude
下一步任务: create development breakdown with owner split, file boundaries, tests, and review focus
