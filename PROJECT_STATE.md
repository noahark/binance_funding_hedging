# Project State

Cross-stage state, read at startup. Keep under 8 KB. Git history is not a runtime
check.

## Live Risks

- `[OPEN][RUNTIME-UNVERIFIED]` The Start gate may still be live and no close
  function exists. No agent may create orders, touch credentials, control the
  service, or write the live task DB; an authorized read-only check must precede
  any live action.
- `[OPEN][UNREVIEWED-LIVE-PATH]` The bStock spot-alias fix (`3dc6756`, merged
  2026-08-01) changes **which instrument a real spot order is placed on**.
  `HIGH_RISK` by §8, passed **no review of any kind**; merged on explicit Human
  authorisation. Ordinary symbols unaffected and no bStock task exists today —
  **the first bStock task created will exercise unreviewed live order behaviour.**
- `[CLOSED][VERIFIED-INCIDENT]` **BK-T3-002 — the live task DB was written during
  development** (2026-08-01 23:45:48), changing **the cadence of a running live
  service** rather than data at rest. Value written was correct; no
  task/attempt/leg/order data touched. **Root cause, found after merge**: the
  Task 3 interval backfill rewrote a row **unconditionally on every store
  construction**, outside the opt-in guard DEC-2026-07-30-003 had added three days
  earlier for exactly this. It was never a stray run — any construction against
  the real DB rewrote it by design. Missed by the packet (never checked the
  decision log), three review-1 rounds, review-2 and the Bookkeeper.
  **Fixed 2026-08-02 (`9c6b3b2`, DEC-2026-08-02-002)**: the cadence now comes from
  the code constant, the migration is deleted, and a byte-level regression asserts
  that constructing a store never writes — the test that would have caught this.
  **Two operating rules stand:** ① verify `interval_us=500000 version=4` against
  snapshot `data/…bak-premerge-20260802-161143` before each service start;
  ② **development and verification runs never touch the real `data/` path.**
  Evidence: archive `27-` §3, `39-` §1.2.

## Merged Position Table — Accepted Limitations (Task 1, merged 2026-08-01)

All three are the same class: **the display asserting something it does not
know.** None costs money directly; each can mislead an operating decision.

- `[OPEN][ACCEPTED]` **A** — the single-leg marker only fires when the perp leg is
  entirely absent, so a partial imbalance (spot 2.0 / perp 1.0) reads as "no
  exposure". Not the authoritative exposure verdict; the per-attempt inline log is.
- `[OPEN][ACCEPTED]` **B** — spot balance and drift read the classic spot account
  while the hedge buys into the unified account, so the **drift flag is
  permanently inert**. An absent drift marker does not mean "records agree".
- `[OPEN][ACCEPTED]` **F4 — "exchange has no position" is claimed without
  checking.** Whenever the account cannot be read (`SnapshotNotReady`, or
  `verified: false` from an expired key / changed IP / Binance error), every row
  still reports `no_um` and prints 交易所无仓 with a liquidation hint — verified to
  do so even when the account block *does* contain that position.
  **Re-decided 2026-08-02**: Task 2 was to fix it, Task 2 is deferred, and Human
  authorised the Task 3 merge after seeing review-2's finding, so F4 **stays
  accepted**. That finding is why it must stay visible: **one exchange-side outage
  triggers both** `order_state_unknown` (task pauses, "go check the exchange")
  **and** F4's false 交易所无仓 — the moment you most need to verify is the moment
  the table is least trustworthy, and believing it can lead to rebuilding a task
  that already has a live leg. **Rule while accepted: when the 账户数据未就绪
  banner is on screen, verify on Binance, not in this table.** Fix is fully
  specified in the archive `46-` §3.3 and should be scheduled on its own.
- `[OPEN][RELEASE-GATE]` The read-only smoke run review-2 made its ACCEPT
  conditional on was **never executed** (Human authorised the merge without it).
  Checklist: archive `49-`. **Now a hard prerequisite for the next live
  activation** (review-2, 2026-08-02) — its account-not-ready item covers F4.

## Task 3 — Cadence + Absent Tolerance (merged 2026-08-02)

Delivery `d2ac353`. Re-query cadence **1s -> 500ms** (not the 100ms originally
asked — Human switched to match the legacy JS strategy) plus a **10-try per-leg
retry budget** before a `404`/`-2013` is believed. Both reviews ACCEPT after three
review-1 rounds; `rework_count` 2/3. Runtime evidence is **zero**; code evidence
is the strongest this project has produced.

- `[OPEN][OPERATING-LIMIT]` **Run at most ~5 tasks draining concurrently.** The
  worker queries *every* non-terminal leg each round, so two legs in flight is
  **4 req/s per task** against Binance's ~20/s weight budget. (An earlier
  Bookkeeper figure of "2/s, ~10 tasks" was a single-leg misreading.) Human's
  lever is symbol count; the durable fix is Task 2's `rate_limited` backoff.
  review-2 also advises a minimum-size first live order with the log page open.
- `[OPEN][ACCEPTED]` **F1-P1** — worker handoff can clear a re-entering worker's
  retry counters (leg regains its full budget, settlement ~5s late; no money
  error, no resend). Accepted because all three `ensure_worker` entries are manual
  clicks and the window is milliseconds. **Re-review the moment any non-manual
  path to `ensure_worker` appears.** Five elements: archive `32-` §7.3.
- `[OPEN][FOLLOW-UP]` Task-card pause reasons render **1 of 7** in Chinese — the
  frontend never reads the `pause_reason_zh` the backend already returns. The log
  timeline *is* wired (via `error_reason_zh`), so the frozen 51169 text and the
  new `order_state_unknown` guidance are reachable there, just not on the card.
  `pre-existing-independent` (`d873699`). Two-line frontend fix; should not wait
  for the deferred Task 2.
- `[OPEN][FOLLOW-UP]` `exposure_alert` is a **dead status** — nothing writes it,
  so the frontend badge can never appear. `pre-existing-independent` (`d90f2f1`).
- `[OPEN][FOLLOW-UP]` A deleted task's `order_state_unknown` settlement records
  `kind=task_paused` with text saying "task paused… resume manually" — it was
  neither paused nor is it resumable. Mild form of the family above.

## Open Follow-ups

- `[OPEN][RESIDUAL]` `resolve_leg_from_query` writes `avg_price` / `quote_amt`
  without `COALESCE`, so a later `None` overwrites a known value. Unreachable
  today. Was to ride Task 2.
- `[OPEN][RESIDUAL]` Perp average price can read blank — upstream: Binance dropped
  quote/avgPrice from the UM POST result (2026-07-14), so figures only arrive via
  the order-detail GET. Renders as an em-dash, not a fabricated zero.
- `[OPEN][DEFERRED]` Three discarded-failure sites, by decision: `service.py:1141`,
  `:1632`, `live_hedge_executor.py:690-702`. Should these reach the `entries`
  timeline? Human decides. Audit: `archive/2026-07-unknown-not-zero-v1` file `71-`.
- `[OPEN][RESIDUAL]` `_rate_limit_stamp_pending` is in-process: a restart mid-stamp
  costs one failure count (pauses one early, fail-closed). Fix = a new column.
- `[OPEN][RESIDUAL]` The money-zero tripwire is a speed bump, not a proof: five
  evasions + `fee_amount` outside the money names. DEC-2026-07-30-001.
- `[OPEN][HARNESS]` ~41 completed stage dirs in `reports/agent-runs/`, vs §9.5.
  v2 findings: batch A merged; batch B + R3/R4 wait for a real problem, G1/G14
  OPEN by decision (Human 2026-07-31). Detail: archive `22-`.

## Next Priority

- **No active stage.** `2026-07-31-hedge-task-lifecycle-v1` closed 2026-08-02:
  Task 1 (`ef53a02`) and Task 3 (`d2ac353`) merged and pushed, Task 2 designed but
  deliberately not built (DEC-2026-08-02-003).
- Highest-value next pieces, in order: **F4's fix** (fully specified, and the one
  limitation that can mislead an operating decision during an outage);
  **the task-card Chinese gap** (two-line frontend change); then the deferred
  lifecycle rework itself — read `docs/planning/deferred-hedge-task-lifecycle.md`
  first, it holds five problems the frozen design docs do not.
- Idle, not closed: `2026-07-hedge-fast-fix-v1` (`awaiting_findings`).
- Main line: live testing of the immediate-hedge scenario — still **no runtime
  verification** of the hedge-open path.

## Last Completed

- stage: `2026-07-31-hedge-task-lifecycle-v1`
- archive_ref: `archive/2026-07-31-hedge-task-lifecycle-v1` (Task 1 `ef53a02`,
  Task 3 `d2ac353`; Task 2 designed but not built, see
  `docs/planning/deferred-hedge-task-lifecycle.md`)
- recorded_completed_at: `2026-08-02`

## Update Rule

Record live incidents at once; remove resolved items. Over budget: evict resolved
first, then oldest, keeping a git reference.
