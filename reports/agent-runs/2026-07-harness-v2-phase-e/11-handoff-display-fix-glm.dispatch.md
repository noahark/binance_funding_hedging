# Phase E Task 1 Follow-up — Human-Readable Handoff Display

## Identity

- task_id: `phase-e-handoff-display-polish`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `2`
- required_skill: `agents/skills/minimal-change-engineer.md`

## Goal

Apply Human feedback before the current delivery is committed. Keep the three
handoff fields inside `TASK_RESULT v2`, but make their values as direct and
useful as the retired v1 display.

In `AGENTS.md`:

1. Require the three handoff fields for every formal task rather than saying a
   task merely "may" include them.
2. Require `completed_at_cst` to use the exact format
   `YYYY-MM-DD HH:MM:SS CST`, produced by:
   `date '+%Y-%m-%d %H:%M:%S CST'`.
3. Require `suggested_next_actor` to use a human-readable role/model flow, not
   an internal identifier such as `stage_recorder`. It may name a planned next
   model only when that route is already determined by current status, dispatch,
   roles, or Human decision. This is still informational and does not authorize
   model launch.
4. Require `suggested_next_action` to state the concrete next gate and task in
   plain Chinese. Do not use vague text such as "设置 next" or "准备独立审查".
5. Apply the compact-output rule to every low-risk task with
   `outcome: completed`, not only review `ACCEPT`: summary targets at most 300
   Chinese characters and checks are normally at most eight grouped,
   non-duplicative PASS/FAIL items. Required high-risk or `REWORK` evidence may
   exceed the target.
6. Include a human-readable example equivalent to:

```text
completed_at_cst: 2026-07-30 00:28:20 CST
suggested_next_actor: Stage Recorder（阶段记录器）→ Human 启动 Grok 4.5（初审）
suggested_next_action: 核实本次结果并提交固定版本，然后准备 Grok 4.5 初审任务包
```

Do not change the accepted routing or the slimmed reality-checker content.

## Allowed Files

- `AGENTS.md`
- `reports/agent-runs/2026-07-harness-v2-phase-e/status.json`, but only
  `current_task.state: dispatched -> reported` after all checks pass

Do not modify any other file. Preserve the existing uncommitted changes in
`agents/roles.md` and `agents/skills/reality-checker.md`.

## Inputs

Read only:

1. `AGENTS.md`;
2. this dispatch;
3. `reports/agent-runs/ACTIVE.json`;
4. `PROJECT_STATE.md`;
5. `reports/agent-runs/2026-07-harness-v2-phase-e/status.json`;
6. the `Implementer` section of `agents/roles.md`;
7. `agents/developer-discipline.md`;
8. `agents/skills/minimal-change-engineer.md`;
9. `reports/agent-runs/2026-07-harness-v2-phase-e/20-contract-skill-slimming-glm-result.md`.

## Acceptance Checks

- The three handoff fields are required for formal tasks and remain inside the
  single result block.
- Timestamp format and exact local `date` command are specified.
- Actor and action values are plain-language, concrete, and may show an already
  decided next model without granting dispatch authority.
- Compact-output rules cover low-risk completed implementation and review tasks.
- `[/TASK_RESULT]` remains the final non-whitespace output.
- The substantive follow-up diff changes only `AGENTS.md`; status may contain
  only the permitted task-state transition.
- Run:
  - `git diff --check`
  - `rg -n "YYYY-MM-DD HH:MM:SS CST|Stage Recorder.*Grok 4\\.5|outcome: completed|300 Chinese|at most eight" AGENTS.md`
- No commit, push, main change, legacy deletion, cross-model dispatch, service,
  credential, or live action occurs.

## Stop

After checks pass, change only this task's state to `reported` if desired.
Return one concise `[TASK_RESULT v2]` with no more than eight grouped checks and
demonstrate this exact handoff style:

```text
completed_at_cst: <YYYY-MM-DD HH:MM:SS CST from local date>
suggested_next_actor: Stage Recorder（阶段记录器）→ Human 启动 Grok 4.5（初审）
suggested_next_action: 核实本次修正并提交固定版本，然后准备 Grok 4.5 初审任务包
[/TASK_RESULT]
```

Stop at `[/TASK_RESULT]`. Do not start Grok or any other model.
