# Design

## Overview

This stage converts 5 accepted-review P2 hardening findings into small,
testable Harness fixes. The design is deliberately narrow: no new state
machine values, no new fingerprint scheme, and no product-facing changes.

## D1: `--evidence-out` Error Handling

Current behavior writes the evidence file after a successful validation run but
does not catch `OSError`. The fix should wrap directory creation and file write
in a small `try/except OSError` block, then raise or print a `ValidationError`
with the target path and system error.

Expected result: failed evidence writing returns a controlled validation failure
message and non-zero exit.

## D2: `--dry-run` Mode Guard

`--dry-run` is documented as single-owner only. The parser currently accepts it
for all modes. The fix should reject `--dry-run` before entering double-owner
logic when `--single-owner` is false.

Expected result: `record-checkpoint <stage> --dry-run` without `--single-owner`
exits with a clear `ItbmError`.

## D3: Rename Detection Pinning

`scripts/_itbm.py` already pins `-c diff.renames=true`; `validate-stage.py`
should do the same in its `git diff --binary` invocation. This removes
dependence on user-level `.gitconfig`.

Expected result: both canonical fingerprint call paths use identical rename
detection policy.

## D4: `review_1.actual_model`

`review_2.actual_model` exists because planned model and executed model can
differ. Review-1 can also have adapter alias or model substitution. Add
`actual_model` to the review-1 template/status shape and, where appropriate,
document it as optional until a review is completed.

Expected result: new stages have a first-class place to record review-1 actual
model evidence.

## D5: Fix Return Gate

The workflow should tell the operator whether a fix after REWORK returns to
review-1 or review-2. This can be represented as explicit transition guidance,
fields, or branch labels in `workflows/templates/stage-delivery.yaml`, as long
as the rule is machine-readable enough for future validators or dispatch logic.

Expected result: review-1 REWORK after fix returns to review-1 redispatch;
review-2 REWORK after fix returns to review-2 redispatch. A fix must not skip
the originating gate.

## Testing Strategy

- Extend `scripts/tests/itbm_dry_run.py` for the `--dry-run` guard.
- Extend `scripts/tests/test_validate_stage.py` for `--evidence-out`, rename
  config pinning, template field, and workflow guidance where practical.
- Preserve all prior Harness regression commands.

本地北京时间: 2026-07-09 21:10:45 CST
下一步模型: claude_glm
下一步任务: implement design D1-D5 and record test evidence
