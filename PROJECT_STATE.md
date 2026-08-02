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
  development** (2026-08-01 23:45:48). Root cause: Task 3's interval backfill
  rewrote a row on every store construction, outside the opt-in guard in
  DEC-2026-07-30-003; this was missed by the packet, reviews, and Bookkeeper.
  **Fixed 2026-08-02 (`9c6b3b2`, DEC-2026-08-02-002)**: the migration is deleted,
  cadence comes from the code constant, and a byte-level no-write regression
  covers store construction. Before service start verify
  `interval_us=500000 version=4` against the pre-merge snapshot; development
  and verification never use the real `data/` path. Evidence: archives `27-`,
  `39-` §1.2.

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
  **Re-decided 2026-08-02**: Task 2 was to fix it, Task 2 is deferred, and F4
  **stays accepted**. An exchange outage can trigger both
  `order_state_unknown` (pause and verify) and this false claim, so the table is
  least trustworthy when it matters most. **Operator rule: 「交易所无仓」本身
  永远不足以证明仓位没了 —— 去币安核实。横幅只覆盖三条路径中的两条，
  它不出现，什么也证明不了。**
  Opus5 identified a third path: `verified=true` can hide
  a missing UM-side read. A task bucket plus no matching UM is `no_um` only
  after a successful UM-granular read; the reported root cause is
  `backend/domain/snapshot.py` near `:1098` and `:1120`. This remains deferred.
- `[OPEN][RELEASE-GATE]` The read-only smoke run was never executed. Checklist:
  archive `49-`; it is a hard prerequisite for the next
  live activation. Its B-6 covers private-channel-off, but not F4's third path;
  add that case before the gate is used.

## Task 3 — Cadence + Absent Tolerance (merged 2026-08-02)

Delivery `d2ac353`. Re-query cadence **1s -> 500ms** plus a **10-try per-leg
retry budget** before a `404`/`-2013` is believed. Both reviews ACCEPT after
three review-1 rounds; `rework_count` 2/3. Runtime evidence is **zero**.

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
- F4 is fully specified and plan-reviewed, but **deliberately not implemented**;
  restart from this stage's archive closure record and the Opus5 report §9.
  It remains an accepted release/runtime limitation. Other queued work includes
  the task-card Chinese gap and the deferred lifecycle rework.
- Idle, not closed: `2026-07-hedge-fast-fix-v1` (`awaiting_findings`).
- Main line: live testing of the immediate-hedge scenario — still **no runtime
  verification** of the hedge-open path.

## Last Completed

- stage: `2026-07-31-hedge-task-lifecycle-v1`
- archive_ref: `archive/2026-07-31-hedge-task-lifecycle-v1` (Task 1 `ef53a02`,
  Task 3 `d2ac353`; Task 2 designed but not built, see
  `docs/planning/deferred-hedge-task-lifecycle.md`)
- recorded_completed_at: `2026-08-02`

- stage: `2026-08-02-hedge-f4-account-availability-v1`
- archive_ref: `archive/2026-08-02-hedge-f4-account-availability-v1`
  (closed before planner execution; F4 deliberately deferred; see `70-stage-closure.md`)
- recorded_completed_at: `2026-08-02`

## Update Rule

Record live incidents at once; remove resolved items. Over budget: evict resolved
first, then oldest, keeping a git reference.
