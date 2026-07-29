# Phase E Task 2 — Result Contract Authority Deduplication

This packet supersedes
`62-phase-e-task2-cn-protocol-correction-glm.dispatch.md`. Do not execute the
superseded packet.

## Identity

- task_id: `phase-e-task2-result-authority-dedup`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `12`
- required_skill: `agents/skills/minimal-change-engineer.md`

## Goal

Finish the approved Task 2 by removing duplicate definitions of the formal
task-result contract.

`AGENTS.md` must be the only active file that defines:

- the complete formal-result structure;
- visible result-field labels;
- canonical route values and their meaning;
- required review closure fields;
- the final output marker rule.

Do not translate copied result fields in roles or skills. Remove those copied
field instructions and replace them with a short reference to the sole
authority in `AGENTS.md`.

This is a pre-review correction, not a formal `REWORK`; keep `rework_count` at
`0`.

## Allowed Files

Modify only:

```text
AGENTS.md
agents/roles.md
agents/skills/code-reviewer.md
agents/skills/reality-checker.md
agents/skills/security-reviewer.md
reports/agent-runs/2026-07-harness-v2-phase-e/status.json
```

Preserve every other uncommitted Task 2 modification and deletion exactly as
found. Do not restore, repeat, or expand the v1 retirement.

## Inputs

Read only:

1. `AGENTS.md`;
2. this dispatch;
3. `reports/agent-runs/ACTIVE.json`;
4. `PROJECT_STATE.md`;
5. current Phase E `status.json`;
6. the `Reviewer` and `Bookkeeper` sections of `agents/roles.md`;
7. `agents/developer-discipline.md`;
8. `agents/skills/minimal-change-engineer.md`;
9. the three allowed review skills;
10. `reports/agent-runs/2026-07-harness-v2-phase-e/61-phase-e-task2-bookkeeper-verification.md`.

Do not read the superseded packet as an instruction source. Do not scan
business source, unrelated stages, credentials, runtime data, or historical
evidence.

## Required Corrections

1. Keep the complete Chinese result protocol only in `AGENTS.md`.
2. Within `AGENTS.md` itself, change the explanatory uses of the retired
   English field labels so the authority is internally consistent:
   - describe completed review state through the Chinese result label;
   - describe passing review through the Chinese review label;
   - make the compact-output condition use the Chinese result label.
3. In `agents/roles.md`, replace the detailed Reviewer output-field bullets
   with one short rule: the Reviewer must use the Task Result Protocol and
   review closure defined in `AGENTS.md`. Keep role duties, read-only behavior,
   provider isolation, and Human-to-Bookkeeper transfer. Do not list any result
   field label there.
4. In each allowed review skill:
   - keep task-specific review method, evidence requirements, read-only
     behavior, and fail-closed behavior;
   - replace result-field and output-template instructions with one short
     reference to the Task Result Protocol and review closure in `AGENTS.md`;
   - do not list English or Chinese result-field labels;
   - do not copy the outer marker or complete result template.
5. The skill may say that missing evidence is non-accepting, but the canonical
   result values and their definitions remain owned by `AGENTS.md`.
6. Do not translate internal JSON keys, dispatch Identity keys, SHA fields, or
   historical raw results.

## Acceptance Checks

Run:

```text
git diff --check
python3 -m json.tool reports/agent-runs/ACTIVE.json
python3 -m json.tool reports/agent-runs/2026-07-harness-v2-phase-e/status.json
rg -n "任务 ID:|执行结果:|结果摘要:|产物:|检查结果:|阻塞项:|评审结论:|问题记录:|修复要求:" AGENTS.md
! rg -n "任务 ID:|执行结果:|结果摘要:|产物:|检查结果:|阻塞项:|评审结论:|问题记录:|修复要求:" agents/roles.md agents/skills/code-reviewer.md agents/skills/reality-checker.md agents/skills/security-reviewer.md
! rg -n "outcome:|verdict:|findings_path|fix_requirements_path" AGENTS.md agents/roles.md agents/skills/code-reviewer.md agents/skills/reality-checker.md agents/skills/security-reviewer.md
rg -n "Task Result Protocol.*AGENTS.md|AGENTS.md.*Task Result Protocol" agents/roles.md agents/skills/code-reviewer.md agents/skills/reality-checker.md agents/skills/security-reviewer.md
```

Also verify:

- only `AGENTS.md` contains the full formal-result structure;
- roles contain responsibility, routing, and isolation, not result schema;
- skills contain review technique, not result schema;
- the exact Task 2 deletion set remains deleted;
- no other path changes;
- `status.json.bookkeeper` remains scalar `codex`;
- `rework_count` remains `0`;
- `status.json` changes only this task from `dispatched` to `reported`;
- no commit, push, main update, model launch, service action, credential access,
  or live action occurs.

## Stop

Return one concise result through the sole Task Result Protocol in `AGENTS.md`.
The task identifier is `phase-e-task2-result-authority-dedup`. Tell the Human
that the raw result goes to Codex Bookkeeper, which will verify the complete
Task 2 diff, fix `delivery_sha`, and prepare Grok 4.5 review-1.
