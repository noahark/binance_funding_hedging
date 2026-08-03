Identity: task_id: harness-handoff-contract-implementation-glm-v1; target_role: Implementer; target_model: claude_glm; provider: zhipu_glm; status_revision: 1; required_skill: agents/skills/senior-developer.md

## Goal

Implement the approved R4 task-handoff evidence contract exactly as described in
`docs/planning/harness-task-handoff-evidence-design-2026-08-03.md`. This is a
HIGH_RISK Harness contract change; the independent DeepSeek plan review is ACCEPT
and Human has authorized this bounded implementation on the current stage branch.

## Allowed Files

- `AGENTS.md`
- `agents/roles.md`
- `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/status.json`

Do not modify any other file. You may change only your own `current_task.state`
from `dispatched` to `reported` in the allowed `status.json`, after the delivery
commit succeeds. Commit only the three allowed files in one delivery commit.

## Inputs

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/10-claude-glm-handoff-contract-implementation.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/status.json`
6. `agents/roles.md` (Implementer, Reviewer, Bookkeeper, Shared Rules)
7. `agents/developer-discipline.md`
8. `agents/skills/senior-developer.md`
9. `docs/planning/harness-task-handoff-evidence-design-2026-08-03.md` (R4)
10. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/01-deepseek-r4-plan-review.raw.md`

## Acceptance Checks

1. Preserve the existing `TASK_RESULT v2` field set and final closing marker.
   For new approved stages, use the existing `产物` field to list the deterministic
   handoff path. Require `下一步任务` to state `读取：<paths|none>；执行：<action>；
   关卡：<gate>` without vague routing text.
2. Put the detailed, single active handoff-contract authority in `agents/roles.md`:
   deterministic path; Source Report; Required Reading sub-section before the
   append marker; Human Brief as the source for console display; create-only
   reviewer exception; Bookkeeper same-file verification; SHA-256 source boundary;
   errata; blocked/failed/REWORK/rejection and `SOURCE_REPORT_MISSING`; archive
   finality; multiple inputs read in written order; REWORK reads repair-requirement
   paths.
3. Rewrite, rather than duplicate, the normal Reviewer/Bookkeeper rule that Human
   transfers raw `TASK_RESULT`: in the normal path the handoff is the only formal
   verification input. Retain Human-transferred console text solely for the
   non-advancing `SOURCE_REPORT_MISSING` fallback.
4. Keep the reviewer isolated from delivery code, existing evidence, status,
   commits and model routing. Its sole write exception is creation after review of
   the exact dispatch-specified handoff path, which preflight `test ! -e <path>`
   recorded in Allowed Files as absent; an existing path fails.
5. Keep Bookkeeper as the only normal state writer. It preflights the path in the
   dispatch, verifies existence/newness, identity, SHA, receipt structure, evidence
   paths and next-step consistency; it appends its verification to the same handoff,
   does not create a parallel record, and does not alter `delivery_sha`.
6. Do not add `status.json` fields/states, blackboards, global/stage summary files,
   terminal transcript capture, product changes, or external side effects.
7. Run and report: `git diff --check`; inspect the complete diff for the acceptance
   checks above; and run `python3 -m json.tool` on the stage `status.json`.

## Stop

Stop after the one delivery commit, self-tests and a complete console `TASK_RESULT v2`.
Set only your own task state to `reported`; do not set `verified`, prepare a review
dispatch, modify any stage evidence, start a reviewer, merge, push, deploy or run
live operations. The Human operator transfers the raw result to the stage Bookkeeper.
