# Stage Task

## Objective

Update `harness-manifest.yaml` so future Harness sync operations include the
independent task-branch mode assets that are already part of this repository.

## Required Change

Add these Harness-owned paths to `harness-manifest.yaml` if they are not already
covered explicitly:

- `docs/independent-task-branch-mode.md`
- `scripts/_itbm.py`
- `scripts/record-checkpoint`
- `scripts/prepare-review-2`
- `scripts/tests/itbm_dry_run.py`

Do not add broad `scripts/` ownership; this repository intentionally lists
script assets explicitly.

## Allowed Files

- `harness-manifest.yaml`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/**`

## Forbidden Files

- Product implementation files under `backend/**` and `frontend/**`
- Harness behavior files: `AGENTS.md`, `workflows/**`, `scripts/**`,
  `schemas/**`, `agents/**`, `docs/model-adapters.md`,
  `docs/parallel-development-mode.md`
- Any credential, environment, or private sample file

## Non-Goals

- Do not modify `record-checkpoint`, `prepare-review-2`, validator behavior, or
  schemas in this stage.
- Do not change product docs or product behavior.
- Do not merge the stage branch to `main`.

## Acceptance Criteria

- `harness-manifest.yaml` contains the missing independent task-branch mode
  assets under `harness_owned`.
- Existing broad entries remain unchanged, especially `schemas/` and
  `reports/agent-runs/_template/`.
- `python3 scripts/tests/itbm_dry_run.py` passes.
- `python3 -m py_compile scripts/validate-stage.py scripts/_itbm.py` passes.
- `scripts/validate-stage.py 2026-07-harness-manifest-itbm-sync-v1 --phase pre-review`
  passes before review-1 dispatch.
- Kimi review-1 returns schema-valid JSON for the recorded diff fingerprint.

本地北京时间: 2026-07-09 09:32:23 CST
下一步模型: claude_glm
下一步任务: implement manifest sync and self-run single-owner checkpoint plus review-1
