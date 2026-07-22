# ADR — Hedge Open Live v1 (Round 1)

Decisions are grounded in `design-inputs.md` (DI-1..DI-4) and the recon reports
under `reports/api-samples/2026-07-hedge-open-live-v1/`. Each carries into the
live round unchanged.

## ADR-1: Reuse the `borrow_tasks` module shape
`hedge_open_tasks` = domain/store/service/executor + durable SQLite + one
scheduler thread + a disabled/gated executor, mirroring the accepted
`borrow_tasks` module. **Why:** proven durable-task + safety-gate pattern in this
repo; lowest-risk path for a real-funds surface. **Consequence:** review can lean
on the existing module's conventions; new logic is the hedge-specific parts.

## ADR-2: Dual-leg market, base-coin `quantity`, common-grid rounding
Both legs are `MARKET` with `quantity=q_common` in **base coin** (not
`quoteOrderQty`). `q_common` is floored onto the decimal `lcm` of the two legs'
effective market steps; both legs send the SAME `q_common`. **Why (DI-4):** per-leg
independent rounding produces unequal legs = manufactured directional exposure.
**Consequence:** reject an attempt whose `q_common` violates either leg's
min/max/minNotional rather than send mismatched legs.

## ADR-3: `NO_SIDE_EFFECT` both directions; reverse never auto-borrows
Spot leg always `sideEffectType=NO_SIDE_EFFECT`. papi enumerates only
`NO_SIDE_EFFECT`/`MARGIN_BUY`/`AUTO_REPAY` (no `AUTO_BORROW_REPAY`). **Why:**
reverse must sell only already-borrowed base (borrow stays in the existing borrow
system); forward buys with available USDT. **Consequence:** reverse preflight
requires `crossMarginFree(base) >= q_common × N`; `maxBorrowable` is verification
only, never treated as sellable. `positionSide` from `/um/positionSide/dual`
(one-way BOTH / hedge LONG|SHORT); mode is never changed in-flow.

## ADR-4: Single-leg exposure — detect, alert, pause; never auto-remediate
Never trust the POST return alone: on any non-`FILLED`/timeout/5xx, reconcile via
order/trades/positionRisk queries by unique client id (never resend same id). One
leg filled + the other not = `exposure_alert` + `leg_exposure` + pause, recording
both legs' real state. **No auto-hedge, no auto-close** (a new trade
authorization). Cumulative `>3` failures terminate the plan and pause. **Why
(DI-4 + locked policy):** leg risk is the top real-funds hazard; auto-remediation
is out of scope and itself risky. **Consequence:** the UI must render
`exposure_alert`/terminated states (already in stage 1).

## ADR-5: Dry-run record transport by default; live behind hard gates
Default executor is disabled; real POST is reachable only when
`APP_HEDGE_EXECUTOR=live` AND a durable global Start gate is ON AND read-only
preflight passed; the first real task is a human action. Dry-run = record
transport (log would-send signed params without secrets, filter versions,
preflight snapshot, client ids; no network POST). **Why (DI-2 + DI-4):** papi has
no testnet; this mirrors Boundary C and keeps CI/tests off the network.
**Consequence:** a test asserts the live path is unreachable without both gates;
the real order-response sample is deferred to a later human-authorized order and
is never fabricated.

## ADR-6: Round split — immediate now, smooth (websocket) next
Round 1 implements immediate mode only (1 fill/sec, no websocket). The smooth
gate (`|E_perp − t_spot_local| ≤ 200ms` with perp exchange `E`, spot local
receive time, NTP/serverTime clock calibration + offset monitoring — DI-1
DECISION LOCKED / option B) is the next round. **Why:** get the real order +
safety + single-leg + dry-run loop proven first; the websocket basis gate is a
separable, heavier concern. **Consequence:** `mode="smooth"` and the DI-1 gate
are reserved in the data model and UI now, implemented next round.

## ADR-7: Carry stage-1 Task/Fill contracts, incl. `deleted`
Task/Fill field names and `Task.status` (five states incl. the stage-1 follow-up
`deleted`) are carried forward verbatim so the fake→live swap is a
data-source change, not a contract change. **Consequence:** the frontend keeps
its cards/filters/soft-delete/positions; only the data source becomes the real
API.
