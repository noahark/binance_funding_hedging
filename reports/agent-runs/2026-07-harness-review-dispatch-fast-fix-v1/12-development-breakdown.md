# Development Breakdown

## Status

Draft pending independent plan review. No implementation model is assigned.

## Single Harness Task

Owner: user-selected model after plan review.

Allowed paths are defined in `00-task.md`. Product code is forbidden.

### Required Deliverables

- Consistent authority text across AGENTS/workflow/parallel-mode/adapters.
- Protocol-v1 template fields and new-stage-only enforcement.
- Capture-only helper with atomic raw/verdict handling.
- Validator changes for human dispatch, optional embedded review, output files,
  schema/fingerprint/identity, and legacy compatibility.
- Positive/negative fixtures listed in
  `05-root-cause-and-fix-plan.md#required-test-matrix`.
- `20-implementation.md` and `60-test-output.txt`.

### Forbidden Implementation Choices

- No automatic model selection or chained dispatch.
- No model adapter invocation from implementation/reviewer prompts.
- No in-place modification of raw reviewer stdout.
- No mandatory migration of completed stage status files.
- No change to product code or API schemas.

### Review Focus

- Authority order is consistent.
- Default review count is actually reduced to one task cross-review.
- Capture helper cannot replace a valid prior verdict on failure.
- Strict verdict is whole-file JSON and raw provenance remains verifiable.
- Legacy completed stages still pass.

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/12-development-breakdown.md
本地北京时间: 2026-07-19 22:12:37 CST
下一步模型: user-selected independent plan reviewer
下一步任务: 审查后由用户指定不同模型实施该单任务
