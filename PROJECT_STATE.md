# Project State

Startup reads this cross-stage state. Keep it under 2 KB. Git history is not a
runtime check.

## Live Risks

- `[CLOSED][HUMAN-REPORTED 2026-07-30]` The naked `SHORT 10000 NOMUSDT`
  (`orderId 888412130`) was hedged by a manual spot buy. Human-reported, not
  agent-verified.
- `[OPEN][RUNTIME-UNVERIFIED]` The Start gate may still be live and no close
  function exists. No agent may create orders, touch credentials, control the
  service, or write the live task database; an authorized read-only check must
  precede any live action. Evidence: `git show 7180f61:.../ACTIVE.json`.

## Open Follow-ups

- `[OPEN][ACCEPTED-LIMITATION]` Human accepted order-truth after review-1
  `REWORK` without review-2. A deferred-query single-leg fill with NULL quote
  stores exposure price as zero. Observe first.
  Evidence: archived `43-review-1-r7.md` and `61-validate-pre-accept-final.txt`.
- `[OPEN][DEFERRED]` Six order-truth items remain: two collateral-cap items,
  inconclusive-query evidence, brake documentation, contradictory zero
  notional, and one flaky oversized-body test. See `stage_followups` in
  `git show 3113a5d:reports/agent-runs/2026-07-hedge-order-truth-v1/status.json`.
- `[OPEN][LEGACY-P3]` Five hardening follow-ups remain in `stage_followups` at
  `git show 7180f61:reports/agent-runs/2026-07-hedge-open-live-hardening-v1/status.json`.
- `[OPEN][HARNESS-WORDING]` Next Harness edit: keep packets to the six-section
  shape, drop the superseded v1 branch document's stale approved/pending
  impression, keep Startup skill navigation from becoming a second routing
  authority.
- `[OPEN][HARNESS-HYGIENE]` 39 completed stage directories remain in
  `reports/agent-runs/`, against AGENTS.md §9.5. Removal is a separate cleanup.

## Last Completed

- stage: `2026-07-harness-v2-phase-e`
- archive_ref: `archive/2026-07-harness-v2-phase-e`
- recorded_completed_at: `2026-07-30`

## Update Rule

Record live incidents immediately; remove resolved or migrated items.
