Identity: task_id: harness-handoff-contract-repair-glm-r1; target_role: Implementer; target_model: claude_glm; provider: zhipu_glm; status_revision: 2; required_skill: agents/skills/minimal-change-engineer.md

## Goal

Repair only BK-001 and BK-002 from
`reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/21-bookkeeper-verification-rework-r1.md`.
The root cause is that the new handoff contract is not routed into every subject
task's required inputs and has no defined same-file evidence path for a present
but malformed handoff. Do not redesign the R4-approved contract or expand scope.

## Allowed Files

- `AGENTS.md`
- `agents/roles.md`
- `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/status.json`
- `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-repair-glm-r1.handoff.md`

Do not modify any other file. You may change only your own `current_task.state`
from `dispatched` to `reported` in the allowed `status.json`, after the repair
delivery commit succeeds. The handoff path above is your sole create-only
evidence write: Bookkeeper preflight ran
`test ! -e reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-repair-glm-r1.handoff.md`
and passed before this dispatch. It must be newly created for this task; if it
exists, stop `blocked` and do not overwrite or append it. Commit only these four allowed files in one repair
delivery commit.

## Inputs

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/22-claude-glm-handoff-contract-repair-r1.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/status.json`
6. `agents/roles.md` (Implementer, Reviewer, Bookkeeper, Shared Rules, Task Handoff Evidence Contract)
7. `agents/developer-discipline.md`
8. `agents/skills/minimal-change-engineer.md`
9. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/21-bookkeeper-verification-rework-r1.md`
10. `docs/planning/harness-task-handoff-evidence-design-2026-08-03.md` (R4)

## Acceptance Checks

1. For every new-stage task subject to the contract, Bookkeeper's prepared
   dispatch must name the Task Handoff Evidence Contract as a required `Inputs`
   reading and must state in `Allowed Files` the deterministic handoff path, its
   create-only authority, and the successful preflight `test ! -e <path>` result.
   Use scoped pointers from relevant role sections where needed; do not duplicate
   detailed field definitions outside the contract.
2. Define a fail-closed, same-file path for an existing but malformed handoff:
   no author bytes are edited; Bookkeeper appends an explicit rejection verification
   at EOF with `source_sha256: unavailable`, the malformed precondition, reproducible
   check, and reported/blocker state. A normal source SHA-256 is calculated only
   when the append marker exists. A missing file remains the only
   `SOURCE_REPORT_MISSING` case.
3. Preserve all R4 behavior, existing `TASK_RESULT v2` field shape and closing
   marker, status schema/state vocabulary, Bookkeeper single status writer, review
   isolation, Human terminal-start gate, fixed delivery SHA, archive finality and
   no blackboard/stage summary/transcript capture.
4. Run and report: `git diff --check`; inspect the complete repair diff against
   BK-001/BK-002; and run `python3 -m json.tool` on the stage `status.json`.

## Stop

Stop after one repair delivery commit, the newly created handoff, self-tests and
a complete console `TASK_RESULT v2` derived from that handoff's Human Brief.
Set only your own repair task state to `reported`; do not set `verified`, prepare
review dispatches, edit other stage evidence, start a reviewer, merge, push,
deploy or run live operations. The handoff is the Bookkeeper's formal input;
the console receipt is for the Human to read, and the Human starts the prepared
Bookkeeper terminal without copying normal-path receipt text.
