# Binance Funding Hedging PRD

Status: current product baseline, reflecting delivered live functionality

Last updated: 2026-08-08

This document evolves with delivered stages; where it and the code disagree,
the code and `PROJECT_STATE.md` are authoritative.

## 1. Product Summary

This product is a locally operated workstation for manually controlled Binance
funding-rate hedging on a regular Portfolio Margin account. It discovers
USDT-quoted opportunities, shows account and route information, records
operator-directed borrow and hedge tasks, and runs a narrowly gated real
immediate hedge-open and manual-close path that has been live-verified.

It is not an autonomous trading bot. The operator chooses the symbol,
direction, base-asset amount, number of attempts, allocated margin, and when to
arm execution. The system records outcomes and does not automatically repair,
close, borrow, repay, or transfer assets as a response to an order outcome.

## 2. Current Product State

### 2.1 Implemented and usable today

- Public market discovery for USDT perpetual/spot pairs, including route class,
  asset tag, funding information, filter data, opening quote references, and
  raw-sample references.
- Optional signed read-only account enrichment for Portfolio Margin balances,
  positions, borrow validation, borrow-cost references, and sort basis.
- Durable SQLite borrow tasks, task/log UI, global Start control, and an
  optional gated live Portfolio Margin borrow executor
  (`POST /papi/v1/marginLoan` when `APP_BORROW_EXECUTOR=live`).
- Durable SQLite immediate hedge-open tasks with cycles and merged positions:
  API, frontend, task/log/position views, global Start control, a one-second
  scheduler, and a gated live executor that submits real PAPI margin and
  USDⓈ-M market orders (stage `2026-08-06-hedge-order-close-validation`; the
  record/dry-run transport is removed from production and lives only in
  `backend/tests/fakes.py`).
- Manual close tasks, live-verified (a real SNXXUSDT position was fully
  closed on 2026-08-07; see `PROJECT_STATE.md`).
- Asset transfer between the unified and regular-spot accounts via
  `POST /api/asset-transfer`, live-verified with three real transfers
  (`data/asset-transfer.sqlite3`).
- A dual-column flow log backed by local SQLite ledgers: borrow interest and
  UM income (funding fee, commission, realized PnL, transfer) are pulled from
  Binance and recorded (`data/ledger-flow.sqlite3`).
- A local Python standard-library HTTP server and vanilla-JS frontend.
  Service management was launchd-based, but launchd has been broken since
  2026-08-03 (TCC authorization failure); the service actually runs as a
  manually started foreground process via `scripts/run-server.sh` (see
  `PROJECT_STATE.md` Live Risks).

### 2.2 Not implemented yet

- Smooth/WebSocket-gated execution.
- Repay workflows and full holdings reconciliation.
- User-data-stream persistence and any automatic risk response.
- 1000x multiplier-contract leg-quantity conversion (the six multiplier
  symbols are currently fail-closed at task creation; the conversion touches
  the real order-quantity path and awaits explicit human authorization — see
  `PROJECT_STATE.md` Open Follow-ups).

Implementing a real adapter never authorized enabling it. Live execution has
since been explicitly human-authorized and is the standing operating premise
(the Start gate is kept ON; see `PROJECT_STATE.md` Live Risks); gate changes,
credentials, and first use of any new live path remain explicit human actions.

## 3. Product Goals

- Show a clear funding-rate opportunity table for eligible USDT symbols.
- Distinguish public route feasibility from account-specific tradeability and
  borrowability.
- Let the operator create fixed-quantity immediate hedge-open tasks.
- Preserve exchange filters, account state, requests, order identifiers,
  outcomes, and accumulated execution data for audit and later improvement.
- Surface mismatches and unknown results without automatic intervention.
- Keep trading credentials and signed requests entirely in the backend.

## 4. Non-Goals

- No automatic opening based on funding-rate thresholds.
- No automatic close, emergency close, leg repair, cancel-and-replace, borrow,
  repay, or transfer caused by execution outcomes.
- No multi-quote support beyond USDT, PM-Pro claim, or hedge-mode dual-side
  support in the current immediate-open stage.
- No backtesting engine, external custody operation, or withdrawal permission.
- No smooth execution in the immediate-open stage.

## 5. Operating Assumptions

- Account mode: regular Binance Portfolio Margin.
- Futures market: USDⓈ-M perpetual futures.
- Position mode: one-way; UM orders use `positionSide=BOTH`. The system never
  changes position mode. A non-one-way account fails preflight.
- Quote asset: USDT. API keys must not allow withdrawals.
- Primary execution is manual and operator-confirmed.
- Binance permissions, regional availability, filters, and response semantics
  require live read-only or explicitly authorized live evidence; documentation
  alone is not sufficient proof.

## 6. Approved Immediate Hedge-Open Contract

This section is the approved product contract for immediate hedge-open. It is
implemented and live-verified: real hedge POSTs exist and have been exercised
under human authorization (stage `2026-08-06-hedge-order-close-validation`;
see `PROJECT_STATE.md`).

### 6.1 Operator input and limits

The operator supplies `single_amount` (fixed base-asset quantity per attempt)
and `target_n` (number of scheduled hedge-pair attempts).

There are no product-level maximum amount, maximum count, maximum allocated
margin, aggregate notional cap, residual tolerance, or slippage cap in this
stage. The operator controls exposure by amount, count, and allocated margin.
Valid filters, min/max quantities and notionals, account state, available
balance, rate limits, executor mode, and Start gate remain mandatory.

### 6.2 Quantity and direction

The backend parses both markets' effective filters with Decimal fixed-point
values. It floors the input to the common valid market-quantity grid,
`q_common`, then validates both individual legs. Display precision never
replaces exchange filters.

| Direction | Portfolio Margin margin leg | USDⓈ-M perpetual leg |
| --- | --- | --- |
| Positive funding | BUY MARKET `quantity=q_common`, `sideEffectType=NO_SIDE_EFFECT` | SELL MARKET `quantity=q_common` |
| Negative funding | SELL MARKET `quantity=q_common`, `sideEffectType=NO_SIDE_EFFECT` | BUY MARKET `quantity=q_common` |

`quoteOrderQty` is a valid Binance capability but is not part of this stage's
execution contract. The negative-funding route sells base asset already
available to the Portfolio Margin account; this stage does not automatically
borrow it.

### 6.3 Immediate scheduling and durable submission

1. Each running task owns an independent asynchronous scheduler and submits one
   concurrent pair every second until it issues `target_n` planned attempts or
   is paused. Several running tasks may each submit their own pair in the same
   second; there is no product-level global one-pair serialization.
2. Before each pair, current public/private preflight verifies market filters,
   account/position mode, available balance, and rate-limit eligibility.
3. Before any POST, SQLite persistently records the immutable attempt, both
   deterministic client order IDs, sanitized request shapes, and preflight
   snapshot.
4. It concurrently sends the two MARKET requests with the same `q_common`.

The next one-second pair is not blocked by a prior pair's fill quantity,
notional difference, partial state, residual, or ongoing status query. Binance
rate-limit responses and the durable Start/executor gates can still stop new
submissions.

### 6.4 Order acceptance, reconciliation, and pause policy

- A returned `orderId` proves that order was accepted; persist it and query it
  until Binance reports a terminal state.
- A missing response, timeout, or ambiguous 5xx is not a confirmed failure and
  is never blindly resent. Query the persisted client order ID first.
- A terminal rejection/cancel/expiry, or order confirmed absent after lookup,
  is a confirmed failed pair outcome.
- Two returned order IDs form an accepted pair and reset the consecutive failed
  pair count. Confirmed failed pairs increment it.
- `consecutive_failure_pause_threshold` is configurable with default 3.
  Reaching it pauses future scheduled attempts; it may later be changed to 1 or
  2 without introducing a notional or margin cap.
- No outcome triggers automatic repair, close, cancel/replace, borrow, repay,
  or transfer.

### 6.5 Recorded execution data

For each leg and task, persist order/client IDs, final state, actual base
quantity, cumulative quote amount, fee data when available, timestamps, and
signed residual. Per-leg weighted average price is:

```text
weighted_average_price = cumulative_quote_amount / cumulative_base_quantity
```

Small actual quantity/value differences between legs are normal. They are shown
and retained for audit, but receive no special action in this stage.

### 6.6 Real-execution gates

Real hedge POST requires:

1. `APP_HEDGE_EXECUTOR=live` in the configured backend path.
2. Durable global Start enabled.
3. A runnable task with passing factual preflight.
4. No browser or unsafe bulk/manual endpoint bypass.
5. Explicit human authorization before the first real hedge task (granted;
   live execution is now the standing operating premise — see
   `PROJECT_STATE.md`).

Manual close is delivered as its own task type with its own gate and has been
live-verified (see section 2.1).

## 7. Public Route Classification

Public route classification is feasibility evidence, not proof that the current
account can borrow or trade a symbol.

- `MARGIN_SPOT_CANDIDATE`: active USDT perpetual + active USDT spot + public
  margin indication. Positive funding is structurally feasible; negative
  funding still requires account-specific base availability/borrow validation.
- `SPOT_ONLY_CANDIDATE`: active perpetual + active USDT spot without public
  margin indication. Observation-only for the current PM immediate stage.
- `PERP_ONLY_EXCLUDED`: no active USDT spot leg; cannot form this hedge.

Asset tags are `CRYPTO`, `BSTOCK`, or `UNKNOWN`, with source and confidence.
BSTOCK and spot-only rows are excluded from the current negative-funding route.

## 8. Interface and Data Requirements

### 8.1 Current discovery

Public discovery uses Binance spot and UM exchange information, funding data,
and public quote/depth sources. Optional private enrichment uses backend
deny-by-default allowlists that mix read-only signed GETs with a small set of
signed POST write paths (order, borrow, transfer) behind gated executors
(`backend/services/private_client.py`,
`backend/services/hedge_open_live_client.py`,
`backend/services/portfolio_margin_borrow_client.py`). Raw samples stay under
`reports/api-samples/` with credentials redacted.

### 8.2 Immediate-open implementation requirements

The real adapter must use independently researched PAPI margin and UM order and
query endpoints, request signing, bounded `recvWindow`, returned rate-limit
headers, and Decimal-safe serialization. Market-filter behavior must handle
per-constraint `MARKET_LOT_SIZE`/`LOT_SIZE` fallback and zero-disabled fields.
Ambiguous execution uses query/reconciliation, never blind POST retry.

No PAPI testnet is assumed. Tests use fake/record transports; any real response
sample or live order is separately authorized evidence.

### 8.3 Later streams and accounting

Borrow interest and UM income (funding fee, commission, realized PnL,
transfer) are already pulled into the local flow-log ledger
(`data/ledger-flow.sqlite3`); Portfolio Margin user streams, spot/UM depth
streams, BNB discount, rebates, and holdings reconciliation remain future
work and are not current capabilities.

## 9. UI Requirements

### 9.1 Current UI

- Opportunity table with public route classification, funding data, opening
  quote references, and raw-evidence context.
- Private account panels when optional signed-read-only enrichment is enabled.
- Borrow task and log views backed by SQLite.
- Immediate hedge-open task, log, settings/status, merged-position, and
  history-position (`history-view`) views backed by SQLite, with a live,
  human-gated executor; smooth-open is visibly unavailable.
- Flow-log view (`flow-log-view`): dual-column borrow-interest / UM-income
  ledger with refresh and coverage status.
- Asset-transfer UI: unified ⇄ regular-spot transfers with idempotency key,
  status lock on `unknown`, and manual-unlock wording.

### 9.2 Immediate-open additions

The real-open stage must show fixed base amount, planned attempt count,
effective `q_common`, task/Start/executor state, attempt timeline, per-leg
order IDs/statuses, cumulative quantities/weighted averages, confirmed failure
count/pause reason, and observed residual. The browser never signs, schedules,
or contacts Binance directly.

## 10. Architecture Direction

### 10.1 As built

- Backend: Python standard-library HTTP server, adapters/services, Decimal
  domain logic, and `jsonschema` validation where appropriate.
- Frontend: same-origin static HTML/CSS/vanilla JavaScript with contract
  self-checks and no build step.
- Persistence: local SQLite for the borrow, hedge-open, ledger-flow, and
  asset-transfer domains (`data/*.sqlite3`).
- Runtime: launchd-based service scripts exist, but launchd has been broken
  since 2026-08-03 (TCC authorization failure); the service actually runs as
  a manually started foreground process via `scripts/run-server.sh` (see
  `PROJECT_STATE.md` Live Risks).

### 10.2 Future evolution

Async IO, a typed frontend framework, richer event storage, websocket handling,
and broad accounting are options to evaluate when their stages are approved;
they are not committed migrations.

## 11. Acceptance and Roadmap

### 11.1 Accepted baseline

Public discovery, optional private read-only enrichment, live-gated borrowing,
live immediate hedge-open, manual close, asset transfer, and the flow-log
ledger are accepted repository state (delivery history in `PROJECT_STATE.md`).

### 11.2 Real immediate-open stage (delivered)

The section-6 contract is delivered and live-verified: Decimal/filter
handling, durable-before-send attempts, concurrent fixed-quantity POST
construction, orderId/client-ID reconciliation, one-second scheduling,
configurable consecutive-failure pause, audited cumulative averages, no
automatic repair, and tests proving zero real POST by default.

Code review acceptance never authorized live use; live execution has since
been explicitly human-authorized and is the standing operating premise (see
`PROJECT_STATE.md` Live Risks). Gate changes, credentials, and any new live
path remain explicit human actions.

### 11.3 Later stages

- Smooth/WebSocket basis-aware execution.
- Repay workflows and complete position reconciliation.
- 1000x multiplier-contract leg-quantity conversion (awaiting explicit human
  authorization — `PROJECT_STATE.md` Open Follow-ups).
- User data streams and broader accounting beyond the delivered flow-log
  ledger.
- Additional account modes/routes only with fresh evidence and explicit scope.

## 12. Open Facts And Deferred Decisions

- Real account permissions, filters, symbols, and regional restrictions require
  read-only or explicitly authorized live evidence.
- PM-Pro support is not claimed.
- Future response to residual exposure is deliberately deferred; immediate mode
  records it without special action.
- Smooth-mode conditions, depth-stream ownership, and close/repay semantics
  require separate design stages.
