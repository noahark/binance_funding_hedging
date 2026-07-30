# Project State

Cross-stage state, read at startup. Keep under 2 KB. Git history is not a runtime
check.

## Live Risks

- `[OPEN][RUNTIME-UNVERIFIED]` The Start gate may still be live and no close
  function exists. No agent may create orders, touch credentials, control the
  service, or write the live task DB; an authorized read-only check must precede
  any live action.

## Open Follow-ups

- `[OPEN][DEFERRED]` Three discarded-failure sites, by decision: `service.py:1141`
  (inconclusive query, needs log-rate design), `:1632` (dry-run, no order),
  `live_hedge_executor.py:690-702` (`_error_leg` drops the send reason; needs a
  `LegDispatch` change). Plus: should these events reach the `entries` timeline?
  Human decides. Audit: `archive/2026-07-unknown-not-zero-v1` file `71-`.
- `[OPEN][RESIDUAL]` `_rate_limit_stamp_pending` is in-process: a restart between a
  failed stamp and settlement costs one failure count (task pauses one early,
  fail-closed). Durable fix = a new column.
- `[OPEN][RESIDUAL]` The money-zero tripwire is a speed bump, not a proof: five
  evasions + `fee_amount` outside the money names. DEC-2026-07-30-001.
- `[OPEN][DEFERRED]` Five order-truth items + five hardening P3s: `stage_followups`
  in `git show 3113a5d:` and `git show 7180f61:`.
- `[OPEN][HARNESS-HYGIENE]` ~39 completed stage dirs still in `reports/agent-runs/`,
  against AGENTS.md §9.5.
- `[HUMAN-OWNED]` The 19 v2 findings belong to approved stage
  `2026-07-harness-v2-trial-hardening-v1`, now in independent plan review;
  implementation waits for that ACCEPT plus Human re-authorization. No other
  model may plan from `harness-v2-trial-findings-2026-07-30.md`.

## Next Priority

Main line: live testing of the immediate-hedge scenario.

## Last Completed

- stage: `2026-07-unknown-not-zero-v1`
- archive_ref: `archive/2026-07-unknown-not-zero-v1`
- recorded_completed_at: `2026-07-30`

## Update Rule

Record live incidents at once; remove resolved items. Over budget: evict resolved
first, then oldest, keeping a git reference.
