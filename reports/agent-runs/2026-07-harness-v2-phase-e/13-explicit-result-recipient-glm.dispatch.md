# Phase E Task 1 Follow-up — Explicit Result Recipient

## Identity

- task_id: `phase-e-explicit-result-recipient`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `4`
- required_skill: `agents/skills/minimal-change-engineer.md`
- result_recipient: `codex / Stage Recorder / openai`

## Goal

Remove the remaining ambiguity in the Human-readable handoff without adding a
new file or a new state system.

1. In `AGENTS.md`, change the handoff rule from optional to mandatory: every
   formal `[TASK_RESULT v2]` must contain the three Chinese handoff lines.
2. Define `下一步模型` as the concrete `result_recipient` named by the active
   dispatch. For this stage it must display:
   `Codex（Stage Recorder，经 human_operator 转交）`.
3. Keep the next planned reviewer in `下一步任务`, rather than replacing the
   immediate result recipient. The immediate recipient and later reviewer are
   different steps.
4. In the Stage Recorder section of `agents/roles.md`, add
   `result_recipient` to the dispatch Identity shape. Define it as:
   `<model> / <role> / <provider>`.
5. State that Stage Recorder must fill this field with the actual assigned
   result-handling session before Human launches the target terminal. A generic
   role name is insufficient when a concrete model has been assigned.
6. Preserve the three Chinese labels, exact local timestamp command, compact
   output rules, routing rules, and slimmed `reality-checker.md`.

Required ending for this task:

```text
本地北京时间: <YYYY-MM-DD HH:MM:SS CST from local date>
下一步模型: Codex（Stage Recorder，经 human_operator 转交）
下一步任务: 将本次 raw TASK_RESULT 交给 Codex 核实并提交固定版本，然后由 Codex 准备 Grok 4.5 review-1（初审）派发包
[/TASK_RESULT]
```

These lines are informational. GLM must not start Codex, Grok, or any other
model.

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
6. the `Stage Recorder` section of `agents/roles.md`;
7. `agents/developer-discipline.md`;
8. `agents/skills/minimal-change-engineer.md`;
9. `reports/agent-runs/2026-07-harness-v2-phase-e/21-handoff-display-cn-glm-result.md`.

## Acceptance Checks

- `AGENTS.md` says every formal result block must contain the three Chinese
  handoff lines; it no longer says a task merely “may include” them.
- `下一步模型` is sourced from dispatch `result_recipient`.
- The example names `Codex（Stage Recorder，经 human_operator 转交）`.
- `agents/roles.md` includes `result_recipient` in the minimal dispatch
  Identity and defines its three components.
- Immediate result recipient remains distinct from the planned later reviewer.
- The substantive follow-up diff changes only `AGENTS.md` and
  `agents/roles.md`; status may contain only the permitted state transition.
- Run:
  - `git diff --check`
  - `rg -n "must contain|result_recipient|Codex.*Stage Recorder|本地北京时间:|下一步模型:|下一步任务:" AGENTS.md agents/roles.md`
  - `! rg -n "A task may include these informational handoff" AGENTS.md`
- No commit, push, main change, legacy deletion, cross-model dispatch, service,
  credential, or live action occurs.

## Stop

After checks pass, change only this task's state to `reported` if desired.
Return one concise `[TASK_RESULT v2]` with no more than eight grouped checks and
the required ending above. Stop at `[/TASK_RESULT]`.
