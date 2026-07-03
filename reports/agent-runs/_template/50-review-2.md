# Review 2

## Reviewer

- Model:
- Skill:
- Adapter:

## Reviewed Artifacts

- `docs/product/PRD.md`
- user-approved direction synthesis, when present
- workflow YAML
- `00-task.md`
- `10-design.md`
- `11-adr.md`
- `06-direction-synthesis.md` when present
- git diff or patch
- `20-implementation.md`
- `40-fix-report.md`
- `60-test-output.txt`
- `30-review-1.md`
- relevant source files

## Prior Involvement Disclosure

- `reviewer_prior_involvement`: `none` / `direction_synthesis` / `breakdown` / `design`
- If not `none`, disclose the prior work here and review the stage design and
  breakdown as evidence under review. Use the user-approved synthesis, PRD, and
  product documents as the higher authority.
- If this is a strong-reviewer design-conflict override, cite the recorded
  unrelated-reviewer unavailable evidence file and fallback reason.
- If this reviewer/provider wrote any implementation or fix code for this stage,
  stop: final review is not allowed.

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
