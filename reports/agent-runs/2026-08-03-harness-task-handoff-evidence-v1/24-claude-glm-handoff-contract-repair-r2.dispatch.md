Identity: task_id: harness-handoff-contract-repair-glm-r2; target_role: Implementer; target_model: claude_glm; provider: zhipu_glm; status_revision: 3; required_skill: agents/skills/minimal-change-engineer.md

## Goal

Repair only BK-003 and BK-004 recorded in
`reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-repair-glm-r1.handoff.md`.
Close the first-live-use gaps in the Task Handoff Evidence Contract: define how
an author-created, pre-commit handoff represents its delivery SHA, and require
next-task reads to be exact repository-relative paths. Do not redesign the
R4-approved contract or expand scope.

## Allowed Files

- `agents/roles.md`
- `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/status.json`
- `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-repair-glm-r2.handoff.md`

Do not modify any other file. You may change only your own `current_task.state`
from `dispatched` to `reported` in the allowed `status.json`, after the repair
delivery commit succeeds. The final path above is your sole create-only evidence
write: Bookkeeper preflight ran
`test ! -e reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-repair-glm-r2.handoff.md`
and passed before this dispatch. It must be newly created for this task; if it
exists, stop `blocked` and do not overwrite or append it. Commit only these three
allowed files in one repair delivery commit.

## Inputs

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/24-claude-glm-handoff-contract-repair-r2.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/status.json`
6. `agents/roles.md` (Shared Rules, Task Handoff Evidence Contract, Implementer, Reviewer, Bookkeeper)
7. `agents/developer-discipline.md`
8. `agents/skills/minimal-change-engineer.md`
9. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-repair-glm-r1.handoff.md`
10. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/22-claude-glm-handoff-contract-repair-r1.dispatch.md`

## Acceptance Checks

1. The detailed contract explicitly permits `delivery_sha: pending` only in an
   Implementer or fix author's handoff that is created before the one delivery
   commit containing it; `none` remains the no-delivery case, and a known SHA
   must be a direct `git rev-parse` value. Bookkeeper must verify `base_sha`,
   resolve the actual delivery SHA after the commit, write it to `status.json`
   and its same-file Verification block, and must not rewrite the author source
   payload. Review handoffs cite the already fixed reviewed delivery SHA.
2. The detailed contract requires every `Required Reading for the Next Task` and
   Human Brief `下一步任务` read item to be a concrete repository-relative path in
   written order. A self reference must use the full deterministic handoff path;
   do not use “本交接件”, bare filenames, “commit 的文件” or similar shorthand.
3. The new R2 handoff itself conforms to checks 1 and 2: it uses the permitted
   pre-commit delivery-SHA form, and its Source Report and Human Brief spell out
   the exact next-reader paths, immediate action and next gate.
4. Preserve BK-001/BK-002 and all R4 invariants: no change to `TASK_RESULT v2`
   fields or closing marker, status schema/state vocabulary, Bookkeeper single
   writer, reviewer isolation, Human terminal-start gate, delivery-review SHA,
   archive finality, or the no-blackboard/no-summary/no-transcript scope.
5. Run and report: `git diff --check`; inspect the complete repair diff against
   BK-003/BK-004; and run `python3 -m json.tool` on the stage `status.json`.

## Stop

Stop after one repair delivery commit, the newly created handoff, self-tests and
a complete console `TASK_RESULT v2` derived from that handoff's Human Brief.
Set only your own repair task state to `reported`; do not set `verified`, prepare
review dispatches, edit other stage evidence, start a reviewer, merge, push,
deploy or run live operations. The handoff is the Bookkeeper's formal input;
the console receipt is for the Human to read, and the Human starts the prepared
Bookkeeper terminal without copying normal-path receipt text.
