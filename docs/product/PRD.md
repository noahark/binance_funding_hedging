# Binance Funding Hedging PRD

Status: current product baseline and approved immediate-open direction

Last updated: 2026-07-23

## 1. Product Summary

This product is a locally operated workstation for manually controlled Binance
funding-rate hedging on a regular Portfolio Margin account. It discovers
USDT-quoted opportunities, shows account and route information, records
operator-directed borrow and hedge tasks, and is evolving toward a narrowly
gated real immediate hedge-open path.

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
- Durable SQLite immediate hedge-open task skeleton, API, frontend, task/log
  views, global Start control, and a one-second scheduler using record/dry-run
  transport. It does not submit real hedge market orders.
- A local Python standard-library HTTP server, vanilla-JS frontend, and
  launchd-based local service management on macOS.

### 2.2 Not implemented yet

- Real PAPI margin and USDⓈ-M market-order execution for hedge opening.
- Real order preflight, `orderId` reconciliation, fill accounting, and the
  immediate-open contract described in section 6.
- Smooth/WebSocket-gated execution.
- Manual close, repay, transfer, full holdings reconciliation, or complete
  funding/fee/interest accounting.
- User-data-stream persistence and any automatic risk response.

Implementing a real adapter does not authorize enabling it, turning on the
durable Start gate, or placing the first real hedge task. Those are explicit
human actions.

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

This section is the current approved product direction. It describes the next
real-API stage; it does not claim that real hedge POSTs already exist.

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

1. A task schedules one concurrent pair every second until it issues `target_n`
   planned attempts or is paused.
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
5. Explicit human authorization before the first real hedge task.

Manual-close implementation is future product work, not a prerequisite for
this immediate-open stage or its first human-authorized real task.

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
and public quote/depth sources. Optional private enrichment uses a backend
signed-GET allowlist. Raw samples stay under `reports/api-samples/` with
credentials redacted.

### 8.2 Immediate-open implementation requirements

The real adapter must use independently researched PAPI margin and UM order and
query endpoints, request signing, bounded `recvWindow`, returned rate-limit
headers, and Decimal-safe serialization. Market-filter behavior must handle
per-constraint `MARKET_LOT_SIZE`/`LOT_SIZE` fallback and zero-disabled fields.
Ambiguous execution uses query/reconciliation, never blind POST retry.

No PAPI testnet is assumed. Tests use fake/record transports; any real response
sample or live order is separately authorized evidence.

### 8.3 Later streams and accounting

Portfolio Margin user streams, spot/UM depth streams, complete funding-income
ledger, commissions, BNB discount, rebates, borrow interest, and holdings
reconciliation are future work. They are not current capabilities.

## 9. UI Requirements

### 9.1 Current UI

- Opportunity table with public route classification, funding data, opening
  quote references, and raw-evidence context.
- Private account panels when optional signed-read-only enrichment is enabled.
- Borrow task and log views backed by SQLite.
- Immediate hedge-open task, log, settings/status, and position views backed by
  SQLite. The present executor is dry-run/record transport; smooth-open is
  visibly unavailable for this stage.

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
- Persistence: local SQLite for borrow and hedge-open task domains.
- Runtime: local macOS service management through launchd scripts.

### 10.2 Future evolution

Async IO, a typed frontend framework, richer event storage, websocket handling,
and broad accounting are options to evaluate when their stages are approved;
they are not committed migrations.

## 11. Acceptance and Roadmap

### 11.1 Accepted baseline

Public discovery, optional private read-only enrichment, live-gated borrowing,
and the dry-run immediate hedge-open skeleton are accepted repository state.

### 11.2 Active real immediate-open stage

Acceptance requires the section-6 contract: Decimal/filter handling,
durable-before-send attempts, concurrent fixed-quantity POST construction,
orderId/client-ID reconciliation, one-second scheduling, configurable
consecutive-failure pause, audited cumulative averages, no automatic repair,
and tests proving zero real POST by default.

Code review acceptance does not authorize enabling live execution, turning on
Start, accessing credentials, or placing a first real task.

### 11.3 Later stages

- Smooth/WebSocket basis-aware execution.
- Manual close, repay/transfer workflows, and complete position reconciliation.
- User data streams and complete funding/fee/borrow-interest accounting.
- Additional account modes/routes only with fresh evidence and explicit scope.

## 12. Open Facts And Deferred Decisions

- Real account permissions, filters, symbols, and regional restrictions require
  read-only or explicitly authorized live evidence.
- PM-Pro support is not claimed.
- Future response to residual exposure is deliberately deferred; immediate mode
  records it without special action.
- Smooth-mode conditions, depth-stream ownership, and close/repay semantics
  require separate design stages.
