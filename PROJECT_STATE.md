# Project State

Startup reads this cross-stage state. Keep it under 2 KB. Git history is not a
runtime check.

## Live Risks

- `[OPEN][RUNTIME-UNVERIFIED]` At `7180f61`, records say the service and Start
  gate may be live and a naked `SHORT 10000 NOMUSDT` (`orderId 888412130`) may
  remain while no close function exists. Current runtime/exchange state was not
  queried. Require an authorized read-only check before live action. No agent
  may create cards/orders, touch credentials, start/stop service, or write the
  live task database.
  Evidence: `git show 7180f61:reports/agent-runs/ACTIVE.json` and
  `reports/agent-runs/2026-07-hedge-order-truth-v1/01-live-record-evidence.md`.

## Open Follow-ups

- `[OPEN][ACCEPTED-LIMITATION]` Order-truth merged by explicit Human acceptance
  after review-1 `REWORK`; review-2 did not run. Confirmed P1: a deferred-query
  single-leg fill with NULL quote persists exposure price as zero, not NULL.
  Human chose observe-first handling.
  Evidence: `43-review-1-r7.md` and `61-validate-pre-accept-final.txt` under
  `reports/agent-runs/2026-07-hedge-order-truth-v1/`.
- `[OPEN][DEFERRED]` Six other order-truth follow-ups remain: two collateral-cap
  items, bounded inconclusive-query evidence, brake documentation,
  contradictory zero notional, and one flaky oversized-body test.
  Details: `git show 3113a5d:reports/agent-runs/2026-07-hedge-order-truth-v1/status.json`
  under `stage_followups`.
- `[OPEN][LEGACY-P3]` Five older non-blocking hardening follow-ups remain in
  `git show 7180f61:reports/agent-runs/2026-07-hedge-open-live-hardening-v1/status.json`
  under `stage_followups`.

## Last Completed

- stage: `2026-07-harness-v2-phase-d`
- archive_ref: `archive/2026-07-harness-v2-phase-d`
- recorded_completed_at: `2026-07-30`

## Update Rule

Record live incidents immediately; remove resolved or migrated items.
