# Project State

Cross-stage state, read at startup. Keep under 8 KB. Git history is not a runtime
check.

## Live Risks

- `[OPEN][RUNTIME-UNVERIFIED]` The Start gate may still be live and no close
  function exists. No agent may create orders, touch credentials, control the
  service, or write the live task DB; an authorized read-only check must precede
  any live action.

## Open Follow-ups

- `[OPEN][MONEY-ACCURACY]` Displayed fill average price is computed locally as
  `cumulative_quote_amt / cumulative_base_qty` (`service.py:224`), not the
  exchange's own figure. `live_hedge_executor.py:116` already parses Binance
  `avgPrice`, but `hedge_open_leg` has no `avg_price` column (`store.py:85-99`),
  so the authoritative value is discarded. Human 2026-07-31: use the returned
  figure instead — it is more precise. Needs a schema + write-path change, so it
  is out of scope for the read-only inline-log stage. Consequence today: perp avg
  is often blank because Binance dropped quote/avgPrice from the UM POST result
  (2026-07-14) and the backfill GET may not land.
- `[OPEN][MONEY-VISIBILITY]` `aggregate_positions` (`store.py:1934-1951`) excludes
  `deleted` tasks, so a deleted task's already-filled legs vanish from
  `GET /api/hedge-open-positions` while the account exposure remains. Pre-existing
  (manual delete triggers it today); it becomes routine if auto-pause ever turns
  into auto-delete. Found by plan review r2 (grok), verified. Blocks that change.
  Detail: stage `2026-07-31-hedge-task-inline-log-v1` file `06-`.
- `[OPEN][DEFERRED]` Task-card restart deadlock, moved out of the inline-log stage
  by Human 2026-07-31; needs its own stage. Covers F10, the Human-approved
  "six auto-pause reasons -> auto-delete" change, quota-exhausted closeout, and the
  three re-arm entries (`post_start` / `fill-once` / `fill-all`). Two plan-review
  rounds of verified findings are preserved in stage
  `2026-07-31-hedge-task-inline-log-v1` files `04-`, `05-`, `06-` — read those
  before re-deriving anything. F10's COOKIEUSDT diagnosis is stale.

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
- `[OPEN][HARNESS-HYGIENE]` ~39 completed stage dirs in `reports/agent-runs/`, vs §9.5.
- `[OPEN][HARNESS-DEFERRED]` v2 findings: batch A merged; batch B + R3/R4 wait for a
  real problem (Human 2026-07-31). G1/G14 OPEN by decision. Detail: archive `22-`.

## Next Priority

- Active stage: `2026-07-31-hedge-task-inline-log-v1` (task-card inline log + F10 restart
  deadlock; HIGH_RISK, bookkeeper opus5). No live orders.
- Idle, not closed: `2026-07-hedge-fast-fix-v1` (`awaiting_findings`, no current task).
- Main line: live testing of the immediate-hedge scenario.

## Last Completed

- stage: `2026-07-harness-v2-trial-hardening-v1`
- archive_ref: `archive/2026-07-harness-v2-trial-hardening-v1`
- recorded_completed_at: `2026-07-31`

## Update Rule

Record live incidents at once; remove resolved items. Over budget: evict resolved
first, then oldest, keeping a git reference.
