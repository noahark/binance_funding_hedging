# Phase E Closeout Plan

## Durable Decisions

The accepted Harness v2 behavior already lives in its active authorities:

- `AGENTS.md` owns startup, safety, flow, review rules, result protocol, stage
  completion, and Human boundaries;
- `agents/roles.md` owns detailed role duties, model/provider routing, state
  shape, task-state vocabulary, and dispatch shape;
- `PROJECT_STATE.md` owns cross-stage risks and follow-ups.

No additional product or architecture document needs promotion during closeout.

## Non-Blocking Follow-up Migration

Migrate the three review-2 wording observations as one compact Harness follow-up:

- keep future dispatch packets to the six-section active shape rather than
  copying historical Task 3 headings;
- if the superseded v1 branch document is touched again, remove its stale
  approved/pending impression;
- when Startup routing is next edited, keep role-to-skill navigation from
  becoming a second detailed routing authority.

These observations do not reopen Task 3 and do not block Phase E acceptance.

## Archive And Removal

1. Commit this acceptance and closeout plan.
2. Create annotated tag `archive/2026-07-harness-v2-phase-e` at that commit.
3. Verify the tag contains this stage directory and accepted review evidence.
4. Update `PROJECT_STATE.md`, clear `ACTIVE.json`, and remove this completed
   stage directory from the normal worktree.
5. Commit the closure, verify clean state, then fast-forward `main`.

The archive tag is the recovery path after stage-directory removal.
