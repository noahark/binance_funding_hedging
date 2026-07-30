# Project State

Startup reads this cross-stage state. Keep it under 2 KB. Git history is not a
runtime check.

## Live Risks

- `[OPEN][RUNTIME-UNVERIFIED]` At `7180f61`, records say the Start gate may be
  live and a naked `SHORT 10000 NOMUSDT` (`orderId 888412130`) may remain while
  no close function exists. This was not runtime-checked. Require an authorized
  read-only check before live action; no agent may create orders, touch
  credentials, control the service, or write the live task database.
  Evidence: `git show 7180f61:reports/agent-runs/ACTIVE.json` and archived
  `2026-07-hedge-order-truth-v1/01-live-record-evidence.md`.

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
- `[OPEN][HARNESS-WORDING]` On the next related Harness edit, keep new dispatch
  packets to the six-section shape, remove the superseded v1 branch document's
  stale approved/pending impression, and keep Startup skill navigation from
  becoming a second detailed routing authority.

## Last Completed

- stage: `2026-07-harness-v2-phase-e`
- archive_ref: `archive/2026-07-harness-v2-phase-e`
- recorded_completed_at: `2026-07-30`

## Update Rule

Record live incidents immediately; remove resolved or migrated items.
