# Review 1

## Reviewer

- Model:
- Skill:
- Adapter:

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

- Task id:
- Task owner / implementer:
- Reviewed base_sha:
- Reviewed head_sha:
- Reviewed diff_fingerprint:

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

本地北京时间:
下一步模型:
下一步任务:

## Strict JSON Verdict

The final content in this file must be one JSON object matching
`schemas/review-verdict.schema.json` and include
`reviewer_prior_involvement`.
