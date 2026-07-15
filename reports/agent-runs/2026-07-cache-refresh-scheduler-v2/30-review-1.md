# Review 1

## Dispatch State

- State: `prepared_waiting_human_execution`
- Reviewer: Kimi `kimi-code/kimi-for-coding`
- Provider identity: `moonshot_kimi`
- Reviewer prior involvement: `none`
- Prompt: `review-1-kimi.prompt.md`
- Stage base SHA: `8aac137a46d228f2d68b2036a15575eda0e235a3`
- Reviewed head SHA: `60c91f7b32ab0f0a51f719a094915adfbec87c83`
- Diff fingerprint:
  `60c91f7b32ab0f0a51f719a094915adfbec87c83:f970f6be1afa92b55b3ef79f1135753647fa9d8693b5e83fa80aa6a27bdfbfb0`
- Formal verdict: pending; this dispatch metadata is not a verdict.
- Pre-review validator: `PASS` (clean worktree; evidence in `60-test-output.txt`)

## Reviewer

- Model: `kimi-code/kimi-for-coding` (pending human execution)
- Skill: `code_reviewer`
- Adapter: `kimi`

## Reviewed Artifacts

- workflow YAML
- `00-task.md`
- `10-design.md`
- `11-adr.md`
- `06-direction-synthesis.md` when present
- git diff or patch
- `20-implementation.md`
- `40-fix-report.md` when present
- `60-test-output.txt`
- relevant source files

## Task Binding

- Task id: `task`
- Task owner / implementer: `claude_glm` / `zhipu_glm`
- Reviewed base_sha: `8aac137a46d228f2d68b2036a15575eda0e235a3`
- Reviewed head_sha: `60c91f7b32ab0f0a51f719a094915adfbec87c83`
- Reviewed diff_fingerprint:
  `60c91f7b32ab0f0a51f719a094915adfbec87c83:f970f6be1afa92b55b3ef79f1135753647fa9d8693b5e83fa80aa6a27bdfbfb0`

For multi-task stages, prefer task-specific files named
`30-review-1-<task-id>.md` and record the task verdict in `status.json.tasks`.

## Findings

List findings ordered by severity.

## Fix Start Prompt

Required when the verdict is `REWORK`; omit only for `ACCEPT` or non-fixable
`BLOCKED`.

Write a ready-to-send prompt for the fix implementer. It must include:

- stage id and reviewed diff fingerprint
- raw review file path and raw verdict JSON path
- ordered findings with severity, file/line evidence, impact, and recommendation
- required fixes from the verdict
- allowed file boundaries for the fix
- forbidden paths and side effects
- exact test/lint/typecheck commands to run after the fix
- required `40-fix-report.md` finding-to-fix mapping

The strict JSON verdict below must repeat the same prompt in `fix_start_prompt`
when `verdict` is `REWORK`.

## Operational Footer

本地北京时间: 2026-07-15 08:07:32 CST
下一步模型: human → kimi
下一步任务: 执行 review-1-kimi.prompt.md 并返回完整原始输出

## Strict JSON Verdict

The final content in this file must be one JSON object matching
`schemas/review-verdict.schema.json` and include
`reviewer_prior_involvement`.
