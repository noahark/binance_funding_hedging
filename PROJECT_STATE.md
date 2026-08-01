# Project State

Cross-stage state, read at startup. Keep under 8 KB. Git history is not a runtime
check.

## Live Risks

- `[OPEN][RUNTIME-UNVERIFIED]` The Start gate may still be live and no close
  function exists. No agent may create orders, touch credentials, control the
  service, or write the live task DB; an authorized read-only check must precede
  any live action.
- `[OPEN][VERIFIED-INCIDENT]` **BK-T3-002 — the live task DB was written during
  development (2026-08-01 23:45:48).** `data/hedge-open-tasks.sqlite3` went from
  `interval_us = 1000000` to `500000` while stage
  `2026-07-31-hedge-task-lifecycle-v1` Task 3 was being implemented, breaking
  both the packet's read-only rule for `data/` and the line above. **The
  implementer's attribution — "the running service applied the migration" — is
  disproved**: PID 57852 started 19:33:42 and ran 4h36m without restart,
  `server.py` builds the store once at startup (`:763`) with no reload, and the
  migration code did not exist until ~4 hours after that start. The writer was
  some run of the new migration pointed at the real path; `version` /
  `updated_at_us` are unchanged, matching that SQL's signature exactly. **Impact
  is benign** — only the cadence setting changed, to the correct value; no task,
  attempt, leg or order data was touched, and no order was placed. Kept open
  because the rule was breached and the attribution was initially wrong, not
  because the data is at risk. Full evidence: that stage's `27-` §3.
- `[OPEN][UNREVIEWED-LIVE-PATH]` The bStock spot-alias fix (`3dc6756`, merged
  2026-08-01) changes **which instrument a real spot order is placed on**: with a
  resolved `spot_symbol` the spot leg goes to the bStock pair (TSLAUSDT futures
  -> TSLABUSDT spot). It is `HIGH_RISK` by §8 (orders) and passed **no plan
  review, no review-1 and no review-2**. Merged on explicit Human authorisation;
  Human declined an operational restriction. Ordinary symbols are unaffected
  (absent `spot_symbol` the path still uses `coin`) and no bStock task exists
  today, so blast radius is currently nil — **the first bStock task created will
  exercise unreviewed live order behaviour.** The earlier
  `2026-07-public-market-bstock-alias-v1` stage covered the public-market alias
  only, not the order path.

## Merged Position Table — Known Limitations (Task 1, merged 2026-08-01)

Three accepted limitations shipped with the backend-merged position table. All
three are the same class: **the display asserting something it does not know.**
None costs money directly; each can mislead an operating decision.

- `[OPEN][ACCEPTED]` **A — single-leg marker under-reports.** The flag is
  `spot_qty > 0 and perp_qty == 0`, so it only catches a perp leg that is
  entirely absent; an aggregated partial imbalance (spot 2.0 / perp 1.0) reads as
  "no exposure". Spec required consuming the backend `pair_outcome` /
  `leg_exposure` verdict. **Do not treat that marker as the authoritative
  exposure judgement.** Complete history is the per-attempt inline log.
- `[OPEN][ACCEPTED]` **B — spot balance and drift read the wrong pool.** Both
  read the classic spot account (`/api/v3/account`) while the hedge's spot leg is
  a margin order into the unified account. The `drift` flag (manual-reduction
  detection) is therefore **permanently inert**. Do not read the spot-balance
  column as "this hedge's spot holding", and do not read an absent drift marker
  as "records agree".
- `[OPEN][ACCEPTED]` **F4 — "exchange has no position" is claimed without
  checking.** When the account cannot be read (`SnapshotNotReady`, or
  `verified: false` from any failed signed read — an expired key, a changed IP
  allowlist, a Binance error), every local row still reports
  `match_status = no_um` and the UI prints 交易所无仓 with a liquidation hint.
  Verified: it does this even when the account block actually contains that UM
  position. **Telltale: if the 账户数据未就绪 banner is on screen, the row's
  match state is not trustworthy.** **Task 2 must fix this** (contract, display
  and three failing-capable tests specified in the stage's `46-` §3.3); if Task 2
  ships without it, the limitation returns to Human for a fresh decision.

Also true of the merged table, by design rather than defect: an average marked
均价不完整 covers only the priced share of the fills and is **not** the full cost
basis; `match_status` is a new API key, so frontend and backend must ship
together.

`[OPEN][RELEASE-GATE-SKIPPED]` review-2's ACCEPT was conditional on a full
read-only smoke run against the final delivery `ef53a02`, covering the
account-not-ready path, unified-account spot matching, snapshot staleness and
zero trading side effects. **Human authorised the merge without executing it.**
The checklist survives in the stage as `49-preflight-smoke-checklist.md` and can
still be run against `main`.

## Open Follow-ups

- `[OPEN][RESIDUAL]` `resolve_leg_from_query` writes `avg_price` / `quote_amt`
  without `COALESCE`, so a later query returning `None` overwrites a value already
  known. Unreachable today (Binance's order-detail GET returns quote and avgPrice
  together); becomes reachable if that changes. Introduced with the avg_price
  column (stage `2026-07-31-hedge-task-inline-log-v1`), following the existing
  `quote_amt` pattern. review-2 ruled it non-blocking for merge.
- `[OPEN][RESIDUAL]` Perp average price can still read blank. Fixed in stage
  `2026-07-31-hedge-task-inline-log-v1` (delivery `d85a2d3`): `hedge_open_leg`
  now has an `avg_price` column, both write paths persist the exchange's own
  `avgPrice`, and all three leg projections prefer it over the local
  `quote / base` division. What remains is upstream — Binance dropped
  quote/avgPrice from the UM POST result (2026-07-14), so a perp leg's figures
  only arrive via the order-detail GET; until that GET lands, the column is
  legitimately unknown and renders as an em-dash rather than a fabricated zero.
- `[OPEN][DEFERRED]` Task-card deadlock, the six-reasons auto-delete and the
  re-query cadence are now Task 2 / Task 3 of the active stage (see Next
  Priority). Verified findings and anchors: that stage's `01-` `10-` `12-`;
  earlier plan-review rounds in archive `2026-07-31-hedge-task-inline-log-v1`
  files `04-` `05-` `06-`. F10's COOKIEUSDT diagnosis is stale.
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

- Active stage: `2026-07-31-hedge-task-lifecycle-v1`. **Task 1 (merged position
  table) is merged to local `main` 2026-08-01 (merge `d597fef`, delivery
  `ef53a02`); not pushed.** Serial chain continues: **Task 2**
  (`hedge-task-lifecycle-v1` — deadlock fix + five reasons auto-delete +
  `rate_limited` backoff + the `COALESCE` guard), then **Task 3**
  (`hedge-leg-requery-cadence-v1` — 1s -> 100ms). Task 2 rebases on `ef53a02`
  and **must also fix F4** (above). `rework_count` resets for each new
  deliverable. Decisions D1-D16 live in the stage's `02-` `03-` `04-` and
  `46-` §3.
- Carried into Task 3 as a named input: `scheduler.py:51-56` derives its wake
  slice from `interval_us`, so dropping to 100ms raises the scheduler thread's
  wake rate about fivefold (floored at 5ms, no exchange traffic since live
  `tick()` returns immediately).
- Idle, not closed: `2026-07-hedge-fast-fix-v1` (`awaiting_findings`, no current task).
- Main line: live testing of the immediate-hedge scenario. The inline log is now
  merged but has had **no runtime verification** (review-2, 2026-07-31).

## Last Completed

- stage: `2026-07-31-hedge-task-inline-log-v1`
- archive_ref: `archive/2026-07-31-hedge-task-inline-log-v1` (delivery `e9ba135`)
- recorded_completed_at: `2026-07-31`

## Update Rule

Record live incidents at once; remove resolved items. Over budget: evict resolved
first, then oldest, keeping a git reference.
