Identity: task_id=herdr-approved-handoff-plan, target_role=Planner, target_model=codex, provider=openai, status_revision=1, required_skill=agents/skills/task-planner.md

Goal
Plan the smallest Harness change that implements the Human-requested Herdr communication policy. The requested direction is: (1) narrow AGENTS.md §3.2 so its absolute prohibition retains only the ban on acting as or impersonating another independent workflow model session; (2) after Human directly asks for it, allow a model to use Herdr to copy the visible next-task content into a named, already-running terminal; and (3) remove the statement that the task-result next-step fields do not authorize the current model to contact or dispatch the next formal role. Herdr is only a Human-directed copy/paste aid: do not add an approval ID, content hash, repository receipt, audit log, or new durable approval workflow. Resolve the exact wording and boundaries that preserve Human choice of the target and content while preventing autonomous session creation, task-state transition, or response approval. Do not modify the Harness or run Herdr commands.

Allowed Files
- docs/planning/herdr-approved-handoff-2026-08-12.plan.md

Inputs
1. AGENTS.md
2. reports/agent-runs/ACTIVE.json
3. PROJECT_STATE.md
4. reports/agent-runs/2026-08-12-herdr-approved-handoff-v1/status.json
5. agents/roles.md (Planner, Shared Rules, Task Handoff Evidence Contract, and Bookkeeper sections)
6. agents/skills/task-planner.md
7. https://herdr.dev/zh-cn/docs/cli-reference/

Acceptance Checks
1. pass/fail: The plan names every active authority that must change, with no duplicated detailed contract.
2. pass/fail: The plan distinguishes a Human-directed copy/paste into an already-running terminal from starting a session, formal dispatch, task-state transition, and approval of a target model request.
3. pass/fail: The plan introduces no approval ID, content hash, repository receipt, audit log, or other persistent approval record for the Herdr copy/paste action.
4. pass/fail: The plan keeps current-session subagent delegation unaffected and explains the formal-review isolation effect.
5. pass/fail: The plan supplies exact implementation file boundaries, validation commands, and a cross-provider plan-review request; no implementation is performed.

Stop
Write only the planning artifact, return the required TASK_RESULT v2, and stop. Do not edit AGENTS.md, agents/roles.md, status.json, or PROJECT_STATE.md; do not start, call, relay to, or prompt a Herdr terminal; do not create an implementation or review dispatch.
