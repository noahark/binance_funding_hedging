# Phase E Task 1 Final Follow-up — Bookkeeper Single Value

## Identity

- task_id: `phase-e-bookkeeper-single-value`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `6`
- required_skill: `agents/skills/minimal-change-engineer.md`
- supersedes: `14-bookkeeper-single-authority-glm.dispatch.md`

## Goal

Apply the Human's final terminology and single-source decision with the smallest
change. v2 keeps the established v1 name `Bookkeeper`. Its current identity is
one atomic stage-level value at `status.json.bookkeeper`.

1. In `AGENTS.md`, replace active `Stage Recorder` terminology with
   `Bookkeeper`.
2. Make `下一步模型` read the model id from `status.json.bookkeeper`, not from
   dispatch `result_recipient`.
3. Remove the `result_recipient` dispatch rule and example entirely.
4. Update the exact `status.json` field list to include `bookkeeper`.
5. Use this readable example:
   `Codex（Bookkeeper，经 human_operator 转交）`.
6. In `agents/roles.md`, rename the active `Stage Recorder` role and references
   to `Bookkeeper`.
7. Add this stage-level scalar to the minimal status shape:

```json
"bookkeeper": "codex"
```

8. Define the value as one canonical model id. Do not store a duplicate provider
   beside it. Provider identity, when needed elsewhere, comes from the single
   model/provider mapping in `agents/roles.md`.
9. State that Human assigns the Bookkeeper at stage intake and Bookkeeper
   records that decision. A mid-stage handover requires a new Human decision
   and status revision, but changes only this one value; for example:
   `"bookkeeper": "opus5"`.
10. Remove `result_recipient` from the minimal dispatch Identity. A task result
    returns to the single `status.json.bookkeeper`; dispatch does not duplicate
    that identity.
11. Preserve the Chinese handoff labels, timestamp command, compact-output
    rules, model routing, SHA/context rules, and slimmed `reality-checker.md`.

The current stage status already records:

```json
"bookkeeper": "codex"
```

Do not add `provider`, `stage_recorder`, a compatibility alias, or a second
Bookkeeper identity field.

## Allowed Files

- `AGENTS.md`
- `agents/roles.md`
- `reports/agent-runs/2026-07-harness-v2-phase-e/status.json`, but only
  `current_task.state: dispatched -> reported` after checks pass

Do not modify any other file. Preserve the existing uncommitted
`agents/skills/reality-checker.md` change.

## Inputs

Read only:

1. `AGENTS.md`;
2. this dispatch;
3. `reports/agent-runs/ACTIVE.json`;
4. `PROJECT_STATE.md`;
5. `reports/agent-runs/2026-07-harness-v2-phase-e/status.json`;
6. the current `Stage Recorder` section of `agents/roles.md`;
7. `agents/developer-discipline.md`;
8. `agents/skills/minimal-change-engineer.md`;
9. `reports/agent-runs/2026-07-harness-v2-phase-e/22-explicit-result-recipient-glm-result.md`.

## Acceptance Checks

- `status.json.bookkeeper` remains the scalar string `codex`.
- `AGENTS.md` and `agents/roles.md` use `Bookkeeper`, not `Stage Recorder`.
- `AGENTS.md` sources `下一步模型` only from `status.json.bookkeeper`.
- Active Harness documents contain no `result_recipient` or
  `stage_recorder` identity path.
- The minimal status shape contains scalar `bookkeeper`; it contains no
  Bookkeeper provider field.
- The minimal dispatch Identity contains no result-recipient field.
- Chinese handoff lines remain mandatory and `[/TASK_RESULT]` remains the final
  non-whitespace output.
- The substantive follow-up diff changes only `AGENTS.md` and
  `agents/roles.md`; status may contain only the permitted state transition.
- Run:
  - `git diff --check`
  - `rg -n "Bookkeeper|status\\.json\\.bookkeeper|Codex.*Bookkeeper|本地北京时间:|下一步模型:|下一步任务:" AGENTS.md agents/roles.md`
  - `! rg -n "Stage Recorder|stage_recorder|result_recipient" AGENTS.md agents/roles.md`
- No commit, push, main change, legacy deletion, cross-model dispatch, service,
  credential, or live action occurs.

## Stop

After checks pass, change only this task's state to `reported` if desired.
Return one concise `[TASK_RESULT v2]` with no more than eight grouped checks and
end exactly in this style:

```text
本地北京时间: <YYYY-MM-DD HH:MM:SS CST from local date>
下一步模型: Codex（Bookkeeper，经 human_operator 转交）
下一步任务: 将本次 raw TASK_RESULT 交给 Codex 核实并提交固定版本，然后由 Codex 准备 Grok 4.5 review-1（初审）派发包
[/TASK_RESULT]
```

Stop at `[/TASK_RESULT]`. Do not start Codex, Grok, or any other model.
