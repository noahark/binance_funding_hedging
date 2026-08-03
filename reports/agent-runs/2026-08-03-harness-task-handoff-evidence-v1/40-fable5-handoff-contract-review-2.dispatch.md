Identity: task_id: harness-handoff-contract-review-2-fable5-v1; target_role: Reviewer; target_model: fable5; provider: anthropic; status_revision: 6; required_skill: agents/skills/reality-checker.md

## Goal

Independently perform review-2 for the complete Harness task-handoff evidence
delivery in the fixed committed range
`ed802bc64d5d1476a19b19aa58d773229b24bfa4..14e4592839c40ab499d8e4cdef7861492368aaff`.
The implementation and repair author is Zhipu GLM; Human explicitly selected
Fable5's separate Anthropic provider quota for this final review, which satisfies
the review-2 isolation requirement. Review the approved requirement, the actual
effect, evidence, operational risks and readiness; do not rely only on review-1.
This is an `ACCEPT` / `REWORK` gate, not merge, deployment, live activation or
final Human acceptance.

## Allowed Files

- `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-review-2-fable5-v1.handoff.md`

This is the sole create-only write. Bookkeeper preflight ran
`test ! -e reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-review-2-fable5-v1.handoff.md`
and passed before this dispatch. Create it only after completing the review; if it
already exists, stop `blocked` and do not overwrite or append it. Do not edit any
delivery file, existing evidence, `status.json`, `PROJECT_STATE.md`, dispatch,
Git state or model routing. Do not commit.

## Inputs

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/40-fable5-handoff-contract-review-2.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/status.json`
6. `agents/roles.md` (Shared Rules, Task Handoff Evidence Contract, Reviewer, Bookkeeper)
7. `agents/skills/reality-checker.md`
8. `docs/planning/harness-task-handoff-evidence-design-2026-08-03.md` (R4 approved design)
9. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-review-1-deepseek-v1.handoff.md`
10. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-repair-glm-r2.handoff.md`

## Acceptance Checks

1. The actual, complete delivery produces the intended task-to-task handoff:
   each contract-bound task has one deterministic handoff, a complete immutable
   Source Report plus Human Brief, and concrete next-reader paths, action and gate;
   it eliminates normal-path Human copying without claiming terminal transcript
   capture or adding a blackboard or stage-wide summary.
2. The operational boundary is safe and practical: Human still starts terminals;
   Bookkeeper remains the only normal state writer; reviewers retain a fresh,
   create-only, no-commit exception; normal verification and malformed/missing
   source paths fail closed without a parallel evidence authority.
3. The SHA lifecycle supports real operation: the author source stays immutable,
   Bookkeeper records source SHA-256 and the committed delivery SHA, reviewers use
   the fixed range, and archive / errata rules do not silently rewrite evidence.
4. Review the complete fixed range and primary evidence independently of
   review-1. Classify every finding under `AGENTS.md` §8, distinguish out-of-range
   observations from in-range blockers, and identify any remaining release or
   operational risk in plain Chinese.
5. Return an explicit `ACCEPT` only if there is no in-range blocker. Otherwise
   return `REWORK` with repository paths containing executable repair requirements.
   The reviewer handoff must contain its complete Source Report, Human Brief /
   console receipt source, formal review closure, evidence paths and deterministic
   next-reader path.

## Stop

Stop after the read-only review, the newly created review handoff and a complete
console `TASK_RESULT v2` derived from its Human Brief, including the required
review closure. Do not update `status.json`, prepare a fix dispatch, start a
model, merge, push, deploy or run live operations. The handoff is Bookkeeper's
formal input; the console receipt is for the Human to read without copying its
normal-path text to Bookkeeper.
