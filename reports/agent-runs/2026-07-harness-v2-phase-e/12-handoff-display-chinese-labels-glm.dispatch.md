# Phase E Task 1 Follow-up — Chinese Handoff Labels

## Identity

- task_id: `phase-e-handoff-display-polish-cn`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `3`
- required_skill: `agents/skills/minimal-change-engineer.md`
- supersedes: `11-handoff-display-fix-glm.dispatch.md`

## Goal

Apply the Human's final display decision before the current delivery is
committed. Preserve one `[TASK_RESULT v2]` block, but use the retired v1-style
Chinese labels for its three closing handoff lines.

In `AGENTS.md`:

1. Require these exact labels inside every formal result block:
   `本地北京时间:`, `下一步模型:`, and `下一步任务:`.
2. Remove the proposed English handoff keys `completed_at_cst`,
   `suggested_next_actor`, and `suggested_next_action`; do not keep duplicate
   English aliases.
3. Require `本地北京时间` to use exact format
   `YYYY-MM-DD HH:MM:SS CST`, produced by:
   `date '+%Y-%m-%d %H:%M:%S CST'`.
4. Require `下一步模型` to use a readable role/model name and transfer note,
   such as `Stage Recorder（经 human_operator 转交）`, not an internal enum
   such as `stage_recorder`.
5. Require `下一步任务` to state the concrete evidence path, state transition,
   next gate, and already-decided target model when known. Do not use vague
   text such as “设置 next” or “准备独立审查”.
6. Keep these lines informational only. They never authorize the current model
   to start, call, relay to, or assign the next model.
7. Apply compact-output rules to every low-risk task with
   `outcome: completed`: summary targets at most 300 Chinese characters and
   checks are normally at most eight grouped, non-duplicative PASS/FAIL items.
   Required high-risk or `REWORK` evidence may exceed the target.
8. Require the exact presentation pattern:

```text
本地北京时间: 2026-07-30 00:28:20 CST
下一步模型: Stage Recorder（经 human_operator 转交）
下一步任务: 核实本次结果并提交固定版本，然后准备 Grok 4.5 review-1（初审）派发包
[/TASK_RESULT]
```

Do not change accepted model routing or the slimmed `reality-checker.md`.

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

- The three Chinese handoff labels are required inside the single result block.
- The three proposed English handoff labels no longer appear in `AGENTS.md`.
- Timestamp format and exact local `date` command are specified.
- Next model and task are readable, concrete, and non-authorizing.
- Compact-output rules cover low-risk completed implementation and review tasks.
- `[/TASK_RESULT]` remains the final non-whitespace output.
- The substantive follow-up diff changes only `AGENTS.md`; status may contain
  only the permitted task-state transition.
- Run:
  - `git diff --check`
  - `rg -n "本地北京时间:|下一步模型:|下一步任务:|YYYY-MM-DD HH:MM:SS CST|outcome: completed|300 Chinese|at most eight" AGENTS.md`
  - `! rg -n "completed_at_cst|suggested_next_actor|suggested_next_action" AGENTS.md`
- No commit, push, main change, legacy deletion, cross-model dispatch, service,
  credential, or live action occurs.

## Stop

After checks pass, change only this task's state to `reported` if desired.
Return one concise `[TASK_RESULT v2]` with no more than eight grouped checks and
end exactly in this style:

```text
本地北京时间: <YYYY-MM-DD HH:MM:SS CST from local date>
下一步模型: Stage Recorder（经 human_operator 转交）
下一步任务: 核实本次修正并提交固定版本，然后准备 Grok 4.5 review-1（初审）派发包
[/TASK_RESULT]
```

Stop at `[/TASK_RESULT]`. Do not start Grok or any other model.
