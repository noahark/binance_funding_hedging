# Design

## Approach

This is a metadata-only Harness sync repair. The implementation should modify
only `harness-manifest.yaml` by adding explicit `harness_owned` entries for the
independent task-branch mode document and deterministic scripts introduced by
the accepted enablement stage.

The stage uses the single-owner recorder trial path:

1. GLM edits the manifest and stage implementation evidence.
2. GLM runs deterministic tests.
3. GLM runs `scripts/record-checkpoint --single-owner` on the stage branch.
4. GLM preserves the recorder output and updates `status.json` with the
   committed review range.
5. GLM runs the pre-review validator and self-dispatches Kimi review-1.
6. On review-1 ACCEPT, GLM records review evidence and leaves the stage ready
   for review-2.

## Boundary

The only delivery file is `harness-manifest.yaml`. The stage evidence directory
may be updated as required by the Harness.

## Test Strategy

- Run the independent task-branch dry-run fixture:
  `python3 scripts/tests/itbm_dry_run.py`
- Compile the touched script dependencies:
  `python3 -m py_compile scripts/validate-stage.py scripts/_itbm.py`
- Run the stage validator before review-1:
  `python3 scripts/validate-stage.py 2026-07-harness-manifest-itbm-sync-v1 --phase pre-review`

## Review Focus

- Verify the manifest entries are neither missing nor overly broad.
- Verify the stage did not change protected Harness behavior files.
- Verify review-1 uses the status-recorded `base_sha..head_sha` range and
  schema-valid JSON.

## Known Limitation In Current Recorder

`scripts/record-checkpoint --single-owner` currently commits the candidate and
prints a fingerprint, but does not write top-level `status.json`. The dispatch
packet compensates by requiring GLM to preserve recorder output and update
`status.json` in a separate evidence step.

本地北京时间: 2026-07-09 09:32:23 CST
下一步模型: claude_glm
下一步任务: implement manifest sync and run single-owner recorder
