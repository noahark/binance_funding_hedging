Identity: task_id: harness-handoff-contract-review-1-deepseek-v1; target_role: Reviewer; target_model: deepseek; provider: deepseek; status_revision: 5; required_skill: agents/skills/code-reviewer.md

## Goal

Independently perform review-1 for the complete Harness task-handoff evidence
delivery in the fixed committed range
`ed802bc64d5d1476a19b19aa58d773229b24bfa4..14e4592839c40ab499d8e4cdef7861492368aaff`.
The implementation/fix provider is Zhipu GLM; Human selected this DeepSeek review
after Kimi quota was unavailable, so it satisfies the required cross-provider
isolation. DeepSeek performed the R4 plan review; disclose that design involvement
in the review report, but it does not override the separate-provider requirement.
Review the actual contract, all relevant evidence and the fixed range, not the
summaries alone. If this review returns `ACCEPT`, Bookkeeper will prepare the
Human-selected Fable5 review-2 packet; do not prepare or start it yourself.

## Allowed Files

- `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-review-1-deepseek-v1.handoff.md`

This is the sole create-only write. Bookkeeper preflight ran
`test ! -e reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-review-1-deepseek-v1.handoff.md`
and passed before this dispatch. Create it only after completing the review; if it
already exists, stop `blocked` and do not overwrite or append it. Do not edit any
delivery file, existing evidence, `status.json`, `PROJECT_STATE.md`, dispatch,
Git state or model routing. Do not commit.

## Inputs

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/31-deepseek-handoff-contract-review-1.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/status.json`
6. `agents/roles.md` (Shared Rules, Task Handoff Evidence Contract, Reviewer, Bookkeeper)
7. `agents/skills/code-reviewer.md`
8. `docs/planning/harness-task-handoff-evidence-design-2026-08-03.md` (R4 approved design)
9. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-repair-glm-r2.handoff.md`
10. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/01-deepseek-r4-plan-review.raw.md`

## Acceptance Checks

1. The range implements the approved R4 design without changing the existing
   `TASK_RESULT v2` field set, closing marker, `status.json` schema/state values,
   Human terminal-start gate, fixed review boundary, or Bookkeeper single-writer
   authority.
2. The contract makes the repository handoff the single formal input: Source
   Report and Human Brief are immutable source payload, console output is derived
   and non-authoritative, the next task has concrete repository-relative reads,
   immediate action and gate, and no blackboard, stage-summary or transcript
   capture was introduced.
3. Reviewer isolation is still fail-closed: one fresh cross-provider session may
   create only its preflighted handoff, cannot commit or alter prior artifacts,
   and normal operation does not require Human to copy receipt text.
4. Bookkeeper paths are executable and fail closed: dispatch routes every
   contract-bound task to the detailed authority; create-only preflight is
   recorded; normal and malformed-existing handoffs have same-file verification
   paths; `SOURCE_REPORT_MISSING` is the sole non-advancing fallback; and the
   Delivery SHA lifecycle handles pre-commit `pending`, no delivery, known SHA,
   and reviewer ranges without rewriting source bytes.
5. Classify every finding under `AGENTS.md` §8. Return an explicit `ACCEPT` only
   if no in-range blocking issue remains; otherwise return `REWORK` with a
   repository path containing executable repair requirements. The reviewer handoff
   must contain the complete Source Report, Human Brief / console receipt source,
   formal review closure, evidence paths and the deterministic next-reader path.

## Stop

Stop after the read-only review, the newly created review handoff and a complete
console `TASK_RESULT v2` derived from its Human Brief, including the required
review closure. Do not update `status.json`, prepare a fix dispatch, start a
model, merge, push, deploy or run live operations. The handoff is Bookkeeper's
formal input; the console receipt is for the Human to read without copying its
normal-path text to Bookkeeper.
