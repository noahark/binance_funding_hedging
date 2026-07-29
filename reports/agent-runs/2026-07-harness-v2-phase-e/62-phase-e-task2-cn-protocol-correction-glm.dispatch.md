# Phase E Task 2 — Chinese Protocol Pre-review Correction

## Identity

- task_id: `phase-e-task2-cn-protocol-correction`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `11`
- required_skill: `agents/skills/minimal-change-engineer.md`

## Goal

Finish the already approved Task 2 before formal review. The complete Chinese
template in `AGENTS.md` is correct, but several reachable instructions still
tell reviewers to emit the retired English field labels `outcome:`,
`verdict:`, `findings_path`, and `fix_requirements_path`.

Make one minimal wording correction so active instructions consistently use the
Chinese result labels while retaining the canonical route values
`completed`, `blocked`, `failed`, `ACCEPT`, and `REWORK`.

This is a pre-review packet correction, not a formal `REWORK`; keep
`rework_count` at `0`.

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

Do not scan business source, unrelated stages, credentials, runtime data, or
historical evidence.

## Required Corrections

1. In `AGENTS.md`, replace the two explanatory uses of English result-field
   labels:
   - explain a completed review using
     `执行结果: completed（完成）`;
   - explain a passing verdict using
     `评审结论: ACCEPT（接受）`;
   - make the compact-output condition use the Chinese `执行结果` label.
2. In `agents/roles.md`, make the Reviewer verdict instructions use
   `评审结论`, `问题记录`, and `修复要求`. Keep canonical `ACCEPT` and `REWORK`.
3. In each review skill, remove instructions to output the English labels
   `outcome:`, `verdict:`, `findings_path`, and `fix_requirements_path`.
   Refer to the complete Task Result Protocol in `AGENTS.md`; retain only the
   skill-specific fail-closed behavior and canonical route values.
4. Do not copy the complete Task Result template into a role or skill.
5. Do not translate internal JSON keys, dispatch Identity keys, SHA fields, or
   historical raw results.

## Acceptance Checks

Run:

```text
git diff --check
python3 -m json.tool reports/agent-runs/ACTIVE.json
python3 -m json.tool reports/agent-runs/2026-07-harness-v2-phase-e/status.json
rg -n "任务 ID:|执行结果:|结果摘要:|产物:|检查结果:|阻塞项:|评审结论:|问题记录:|修复要求:" AGENTS.md
! rg -n "(outcome|verdict|findings_path|fix_requirements_path):" AGENTS.md agents/roles.md agents/skills/code-reviewer.md agents/skills/reality-checker.md agents/skills/security-reviewer.md
rg -n "ACCEPT|REWORK|completed|blocked|failed" AGENTS.md agents/roles.md agents/skills/code-reviewer.md agents/skills/reality-checker.md agents/skills/security-reviewer.md
```

Also verify:

- the full output template still exists only in `AGENTS.md`;
- the exact Task 2 deletion set remains deleted;
- no other path changes;
- `status.json.bookkeeper` remains scalar `codex`;
- `rework_count` remains `0`;
- `status.json` changes only this task from `dispatched` to `reported`;
- no commit, push, main update, model launch, service action, credential access,
  or live action occurs.

## Stop

Return one concise result using the Chinese Task Result Protocol in
`AGENTS.md`. Use:

- `任务 ID: phase-e-task2-cn-protocol-correction`;
- `下一步模型: Codex（Bookkeeper，经 human_operator 转交）`;
- `下一步任务:` tell Codex to save the raw result, verify the complete Task 2
  diff, fix `delivery_sha`, and prepare Grok 4.5 review-1.

The standalone `[/TASK_RESULT]` marker must be the final non-whitespace line.
