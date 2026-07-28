# Stage Intake And Complexity — Hedge Order Truth And Error Fidelity v1

## User Discussion Summary

Continues directly from accepted `2026-07-hedge-open-live-hardening-v1` (merged
to LOCAL `main` at `c8b6bbe`, bookkeeping closed at `ecc3841`, not pushed). That
stage removed the P0 that blocked every order, and the 2026-07-27 live
acceptance run proved it: a real order reached Binance and the perp leg filled.

The same run exposed the next layer. Three of this stage's four items are cases
of the system **discarding or fabricating information it already had access
to**, so this is a data-truth stage, not a feature stage.

The user opened this stage on 2026-07-28 from the standing proposal
`reports/agent-runs/_proposals/2026-07-27-hedge-order-truth-and-error-fidelity.md`,
and chose Codex for Review-1 (see §Reviewer Routing).

## Primary Evidence — The Live Records Themselves

Read from the production database `data/hedge-open-tasks.sqlite3` by the
bookkeeper at intake, 2026-07-28. Full capture:
`01-live-record-evidence.md`.

```text
leg   order_id    exchange_status  cum_base  cum_quote  error_code  error_category
perp  888412130   FILLED           10000     0          (null)      (null)
spot  (null)      REJECTED         0         0          51169       (null)
```

That single pair of rows demonstrates three of the four defects directly:

- **T1** — a leg that genuinely filled 10000 NOMUSDT recorded a cumulative quote
  amount of `0`.
- **T2** — a real rejection carrying code `51169` was classified as nothing at
  all; `error_category` is NULL.
- **T3** — there is no column anywhere on the row holding what Binance actually
  said. Diagnosing `51169` required asking Binance support because our own
  records could not answer it.

The task row for that same attempt carries a fourth, previously unrecorded
defect — see T5.

## Scope — Four Proposed Items Plus One Found At Intake

### T1 (P0 for accounting) — Fill figures are wrong because Binance removed the fields

Binance removed `cumBase` / `cumQuote` / `avgPrice` from `POST /papi/v1/um/order`
and `/papi/v1/cm/order` responses, announced 2026-07-13, **effective
2026-07-14** (official Portfolio Margin changelog, verified 2026-07-27). Our
first real fill was 2026-07-27.

Verified code path (bookkeeper, at intake):

- `backend/services/live_hedge_executor.py:242-248` and `:338-344` read
  `cummulativeQuoteQty` and fall back to `cumQuote`. For a UM leg both are now
  absent, so `_decimal_str(None)` returns the default `"0"`. `avgPrice` is
  handled slightly better — `avg_price` becomes `None`, not `0`.
- `backend/hedge_open_tasks/store.py:660-668` then treats `"0"` as *absent* and
  tries the `filled_qty * avg_price` fallback; `avg_price` is `None`, so it
  lands in the final `else` and stores `Decimal(0)`.

So for every UM fill, `cumulative_quote_amt` is `0` — not merely imprecise. The
position table's average price and unrealised PnL derive from that column.

The margin (spot) endpoint still returns `cummulativeQuoteQty`, so the two legs
now need different sources. That asymmetry must be explicit in the design, not
incidental.

Also unresolved: **when** the authoritative read happens. Today a leg goes
`TERMINAL_RECORDED` straight off the POST and is never queried again — the
observed fill has `last_query_at_us == dispatched_at_us`.

### T2 (P1) — The error-code table is blind to an entire product line

Binance uses **positive** codes on margin endpoints and **negative** on UM/CM,
deliberately. Verified at intake: `FATAL_EXCHANGE_CODES`,
`AUTH_AMBIGUOUS_EXCHANGE_CODES` and `INSUFFICIENT_FUNDS_CODES`
(`backend/hedge_open_tasks/domain.py:306-353`) contain only negative literals,
so **no margin-leg error can match any of them**. Observed: `51169` fell through
to the "unlisted 4xx → known non-fatal rejection (counter)" default, leaving
`error_category` NULL.

The fix must be structural — the next unlisted margin code must not be silently
swallowed either — not a one-line addition of `51169`.

### T3 (P1) — Persist the exchange's own words and the full order record

**The user's explicit requirement**, stated 2026-07-27:

> 记得增加存储下单原始返回订单信息，以及查询订单详情的全量信息

Two things must be persisted:

1. **The raw order-placement response** — the complete body Binance returned to
   our POST, success or failure, including `code` and `msg`. Verified at intake:
   `_business_msg()` (`live_hedge_executor.py:77`) extracts the message for
   classification and then discards it; `hedge_open_leg` has `error_code` and
   `error_category` but no message or payload column; `hedge_open_log` records
   only request params, never the response.
2. **The full order-detail query response** — the complete body from the
   order-detail read, which under T1 becomes the authoritative source of fill
   amounts.

Storage shape (new columns vs a raw-payload table vs `hedge_open_log` entries),
retention, and whether raw bodies need redaction are design questions, not
prejudged here.

### T4 (P2) — Determine the real cause of `51169`, then fix the preflight

`51169` = `MARGIN_TRADE_COEFF_INSUFFICIENT`. Per Binance support, COEFF is the
collateral/haircut coefficient — the check is on *discounted effective margin*,
not nominal balance. Our preflight gate compares `crossMarginFree` against
`q*N*price` (`domain.py:794`), and Binance support explicitly would not confirm
that is the field Binance validates.

Established:

- **Ruled out**: NOMUSDT not being margin-tradable — public `exchangeInfo` shows
  `isMarginTradingAllowed: true`, identical to BTCUSDT.
- **Ruled out as a remedy**: a test-order endpoint. PAPI has **no**
  `/papi/v1/margin/order/test` or `/papi/v1/um/order/test`. Do not design around
  one.
- **Unproven**: that the concurrent UM fill consumed the margin the spot leg
  needed. Binance support called it likely, but had already answered "not
  documented" on the balance-field question, so this is inference.

**T4 is gated on a separate human authorization.** Its required first step is one
real margin BUY on NOMUSDT with no concurrent UM order. Success ⇒ concurrency
contention is real. Same `51169` ⇒ it is the coefficient or wallet placement. The
order only buys, so it creates no new naked exposure — but it spends real money
and is not covered by opening this stage. If the user declines or defers, T1–T3
ship and T4 defers with the preflight untouched. Fixing the preflight against an
unproven cause is how the current gate got written.

### T5 (P1) — The live exposure record is timestamped 1970 (found at intake)

**Not in the proposal.** The bookkeeper found this while grounding the intake
against the production database, and verified the cause in the code.

The NOMUSDT card's `leg_exposure` — the only durable record that a naked position
exists — reads
`{"leg": "perp", "qty": "10000", "price": null, "ts": "1970-01-01T00:00:00.000000Z"}`.

- `backend/hedge_open_tasks/service.py:1688`, in the **live** dispatch path
  (`_dispatch_to_outcome`), calls `D.build_leg_exposure(spot_leg, perp_leg, 0)`
  with a hardcoded literal `0`.
- `build_leg_exposure` (`domain.py:882-910`) renders it via `us_to_iso(ts_us)`,
  producing the Unix epoch.
- `backend/hedge_open_tasks/executor.py:342`, the dry-run / record-transport
  path, passes the real `ctx.ts_us` — which is why no offline test catches this.

Two reasons it belongs in this stage rather than a follow-up: it is the same
defect class as T1 and T2 (a fabricated value standing in for information the
system had), and it is currently corrupting the record of a real outstanding
position. The fix is expected to be small; the regression lock matters more than
the fix.

`leg_exposure.price = null` on the same document is a *downstream* symptom of T1,
not a separate defect. The design must confirm that T1's fix restores it rather
than patching the exposure document separately.

Evidence: `01-live-record-evidence.md` §NEW FINDING.

## Non-Goals

- Close / unwind functionality (that is the third stage of the hedge programme).
  The outstanding naked short is therefore **not** resolved by this stage.
- Smooth mode (`@bookTicker` gating).
- Re-litigating `single_leg_exposure` being ADVISORY — settled, see below.
- Surfacing the newly persisted raw payloads or exchange messages in the UI. T2
  restores a meaningful `error_category`, which the card already consumes;
  displaying the exchange's verbatim message is a separate follow-up.
- Redesigning the preflight before T4's discriminator has run.
- Any live activation, and any change to the currently open Start gate.
- 1000x-prefix symbol normalisation (separate recorded follow-up).

## Settled At Intake — `single_leg_exposure` Stays ADVISORY

The 2026-07-27 run produced a real naked short (10000 NOMUSDT) and the task still
settled to `done`. That is correct per the frozen design: `single_leg_exposure`
is advisory, recorded but never a gate (`domain.py:90-99`, verified at intake).

Asked on 2026-07-28 whether a naked position actually occurring changes that, the
user decided: **keep it advisory — a single-leg outcome does not pause the
task.** T2 therefore does not need to distinguish "retryable" from "must halt"
for the sake of exposure control. Recorded in the proposal and in
`status.scope.T2.exposure_semantics_settled`.

## Runtime State At Intake — LIVE SURFACE IS OPEN

Unlike the previous stage, the user chose **not** to close the live surface
before implementation. Verified by the bookkeeper at 2026-07-28 07:26 CST:

- Backend service PID 96409 is **running** in live mode (up 9h31m).
- `hedge_open_settings.start_gate = 1`, `version = 4` — the durable Start gate is
  **OPEN**.
- `hedge_open_task` is empty, so nothing is dispatching; but creating a card and
  pressing Start would place real orders.
- A real naked SHORT 10000 NOMUSDT (`orderId 888412130`) from the 2026-07-27 run
  is still outstanding. No close function exists.

The user was offered closing the gate and stopping the service and chose to leave
both as they are; the risk is theirs and is not a defect. **Consequence for this
stage: no implementer, reviewer or designer may create a task card, press Start,
place an order, touch credentials, or write to `hedge_open_settings`.** The one
exception is T4's discriminator, which the user must authorize separately and
which the human operator executes.

## Classification

- Complexity: `MEDIUM`
- Direction panel required: `false`
- Existing synthesis covers this work: `true`
- Lightweight skip allowed: `true`

Rationale:

- All four items are defect repairs and persistence inside the direction already
  frozen and approved for `2026-07-hedge-open-real-api-v1`
  (`06-direction-synthesis.md` of that stage). No new product direction.
- T3 adds a storage surface and T1 changes where authoritative fill figures come
  from, which touches an accepted contract's data flow, so it is not `LOW`: it
  needs a development breakdown and both review gates.
- The user opened the stage on 2026-07-28 from the standing proposal without
  requesting a direction panel; the MEDIUM route permits the skip on existing
  synthesis coverage alone.

## Reviewer Routing — User Decision 2026-07-28

The user chose **Codex for Review-1**. Codex is not in the registered Review-1
cross-review pool (`agents/registry.yaml` `review_1_cross_review_pool: [kimi,
claude_glm]`), so this is an explicit stage-level enablement, recorded in
`15-user-authorized-codex-review-1.md` — the same treatment Grok required last
stage.

That choice has a forced consequence, presented to the user before they decided:
AGENTS.md allows only two decision models at the final gate (Codex, Claude), and
the design-involvement override that would let Claude review its own stage's
design is available only when the other decision model is *unavailable*. Codex is
available. So with Codex at Review-1, the final gate is either Codex again or
Claude-with-no-design-involvement.

**The user chose: Claude designs, Codex walks both gates.**

- Designer + breakdown author: `claude` (Fable5, Opus4.8 on quota exhaustion)
- Implementer: `claude_glm` (`glm-5.2[1m]`) — backend-only stage
- Review-1: `codex`
- Review-2: `codex`

Compliance check (bookkeeper): every hard gate holds. Review-1 and Review-2 are
both provider-isolated from the implementer (`codex` ≠ `zhipu_glm`). Review-2 has
no design involvement, so no strong-reviewer disclosure override is needed and
none is claimed. AGENTS.md and `scripts/validate-stage.py` place no constraint on
Review-1 and Review-2 sharing an identity.

**Disclosed cost, accepted by the user:** the final gate is not an independent
second pair of eyes. Codex will have already formed and published a verdict on
the same diff at Review-1, so Review-2 largely re-confirms its own reading rather
than challenging it. The mitigation available to this stage is that Review-1 and
Review-2 must run in **two distinct fresh read-only sessions** with no shared
transcript, and Review-2's packet must direct it at `00-task.md`'s acceptance
criteria as the top authority — which is exactly the authority-order point that
caught the previous stage's blocking finding.

Reviewer pool as of 2026-07-28: `codex`, `claude_glm`, `claude`, `grok`
available; `kimi` quota not recovered.

## Carried Follow-Ups From The Previous Stage

Five P3 items carry forward in
`reports/agent-runs/2026-07-hedge-open-live-hardening-v1/status.json.stage_followups`.
None is in scope here by default. One is thematically identical to this stage's
subject and the design may fold it in if it is cheap:

- `p3-preflight-snapshot-key-contract-untested` — no test asserts that
  `compute_preflight` emits the `spot_min_qty` / `spot_max_qty` / `perp_min_qty`
  / `perp_max_qty` keys `_leg_qty_filters` reads. If the names drift, the suite
  stays green while the offline validator silently stops checking step/min/max.
  That is the same silent-downgrade shape as T1 and T2.

The other four (`p3-api-samples-backslash-prose`, `p3-confirm-negative-matrix`,
`p3-409-dialog-title-unfrozen`, `p3-selfcheck-dialog-body-includes`) stay
deferred; folding them in would widen a data-truth diff with unrelated cosmetics.
