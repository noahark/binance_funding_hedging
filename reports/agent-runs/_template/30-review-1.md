# Review 1

## Reviewer

- Model:
- Skill:
- Adapter:

## Reviewed Artifacts

- `00-task.md`
- `10-design.md`
- `11-adr.md`
- `06-direction-synthesis.md` when present
- git diff or patch
- `20-implementation.md`
- `40-fix-report.md` when present
- `60-test-output.txt`

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

## Strict JSON Verdict

The final content in this file must be one JSON object matching
`schemas/review-verdict.schema.json`.
