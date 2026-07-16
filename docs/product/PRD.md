# Binance Funding Hedging PRD

Status: as-built read-only snapshot plus future execution requirements, 2026-07-16

Last updated: 2026-07-16

## Product Summary

Build a manual Binance funding-rate hedging workstation for Portfolio Margin
accounts. The system scans eligible USDT-quoted perpetual and spot or margin
pairs, shows funding opportunities, estimates execution costs, and lets the
operator manually trigger smoothed market-order hedge execution.

The first product version is not an autonomous trading bot. It is an execution,
monitoring, accounting, and evidence system for manually controlled funding-rate
hedging.

Current as-built status: the repository has landed a read-only workstation
slice, not execution. The backend serves public market data plus optional
private signed GET enrichment for balances, positions, borrow validation,
borrow-cost references, and sort basis. A serial background refresh worker owns
a single immutable published state and all domain-cache writes; it also drives
paired public bookTicker quotes surfaced as additive per-row `opening_quotes`
and settled 7D/30D plus estimate-24h annualized funding fields. The frontend
renders the opportunity table — including opening-spread and annualized funding
columns — and the private read-only account panels; it has no order, open,
borrow, repay, or transfer ticket of any kind. On macOS the local server runs
under a launchd agent (`com.aoke.funding-hedging.server`) managed by
`scripts/service-control.py`. There is no implemented order, borrow, repay,
transfer, close, or automated execution surface yet.

## Background

The project starts from an older FMZ isolated-margin strategy. That strategy
proved the core funding hedge pattern:

- Positive funding: short perpetual futures and buy spot.
- Negative funding: long perpetual futures and borrow base asset to sell spot.
- Open and close thresholds reduce churn.
- Smooth execution, order reconciliation, funding-fee accounting, and abnormal
  leg detection are operationally important.

The new system keeps those product lessons but replaces the old FMZ and
isolated-margin assumptions with Binance Portfolio Margin, explicit API
adapters, a web UI, and a safer manual execution workflow.

## Goals

- Provide a clear funding-rate opportunity table for eligible USDT symbols.
- Classify each symbol by public route feasibility before private account
  integration.
- Let the operator manually create an execution plan by total notional and
  number of rounds.
- Execute smoothed hedges with market orders only after operator confirmation.
- Use live websocket depth after the operator clicks open, so the UI can show
  current spread and estimated slippage before and during execution.
- Track futures leg, spot or margin leg, borrow state, funding income, fees,
  borrow interest, and realized execution cost.
- Highlight leg mismatch and accounting anomalies without automatically closing
  positions.
- Show current holdings and leg reconciliation directly on the overview page.
- Record raw Binance request and response JSON during adapter discovery and
  early live testing.

## Non-Goals

- No automatic open based on funding thresholds.
- No automatic close based on funding thresholds.
- No automatic emergency close in v0.1.
- No automatic leg repair in v0.1.
- No multi-quote support beyond USDT in v0.1.
- No hedge-mode dual-side position support in v0.1.
- No withdrawal, transfer to external address, or custody automation.
- No backtesting engine in v0.1.

## Operating Assumptions

- Account mode: Binance Portfolio Margin.
- Futures market: USDⓈ-M perpetual futures.
- Position mode: one-way mode only.
- Quote asset: USDT only.
- Primary execution is manual and operator-confirmed.
- First live validation can use small real capital because Binance sandbox or
  paper behavior may miss account, borrow, and commission edge cases.
- API keys must not have withdrawal permission.
- Current as-built private access is optional, read-only, and disabled by
  default. When enabled, it uses signed GET requests through a backend whitelist.
  Private user data streams and all execution endpoints remain future work.

## Public Route Classification

Phase 1 classifies public market feasibility only. It does not prove that the
operator's account can borrow, trade, or hold a given asset.

For each USDT perpetual symbol:

1. Verify that a USDⓈ-M perpetual contract exists and is trading.
2. Join it against public spot exchange information.
3. Mark whether the spot symbol publicly indicates margin support.
4. Mark bStocks or other tokenized equity-like products separately from route
   class.
5. Preserve the data timestamp and raw sample file references.

Route class values:

- `MARGIN_SPOT_CANDIDATE`: has USDT perpetual, has USDT spot, and spot public
  data indicates margin support. Positive-funding hedge is structurally
  possible from public data. Negative-funding hedge still requires later private
  borrowability validation.
- `SPOT_ONLY_CANDIDATE`: has USDT perpetual and USDT spot, but public spot data
  does not indicate margin support. Positive-funding hedge can be observed as a
  normal spot route candidate. Negative-funding hedge is disabled.
- `PERP_ONLY_EXCLUDED`: has USDT perpetual but no corresponding USDT spot leg.
  It cannot form a contract-spot hedge and is excluded from executable
  candidates.

Asset tags are independent from route class:

- `CRYPTO`
- `BSTOCK`
- `UNKNOWN`

Each row must include `asset_tag_confidence` and `asset_tag_source`. bStocks are
positive-funding observation candidates only when a spot leg exists; negative
funding is disabled.

`negative_funding_status` priority:

1. `PERP_ONLY_EXCLUDED` maps to `DISABLED_PERP_ONLY`.
2. `asset_tag = BSTOCK` maps to `DISABLED_BSTOCK`.
3. `SPOT_ONLY_CANDIDATE` maps to `DISABLED_SPOT_ONLY`.
4. Remaining `MARGIN_SPOT_CANDIDATE` rows map to
   `PRIVATE_BORROW_VALIDATION_REQUIRED` until private account discovery proves
   borrowability.

## Hedge Modes

### Positive Funding

When the funding rate is positive, shorts receive funding and longs pay funding.

Execution:

- Futures leg: open short USDⓈ-M perpetual.
- Spot leg: buy spot or margin spot.
- Account route priority:
  1. Portfolio Margin / cross-margin spot buy when supported.
  2. Normal spot account buy when margin route is unavailable.

Supported assets:

- `MARGIN_SPOT_CANDIDATE`
- `SPOT_ONLY_CANDIDATE`
- bStock rows with a valid spot leg, marked as positive-funding only

### Negative Funding

When the funding rate is negative, longs receive funding and shorts pay funding.

Execution:

- Borrow base asset first.
- Spot/margin leg: sell borrowed base asset.
- Futures leg: open long USDⓈ-M perpetual.

Supported assets:

- Later private-account validated `MARGIN_SPOT_CANDIDATE` rows only.

If borrow fails, the execution plan is abandoned before opening the hedge. After
multiple borrow failures, the plan is marked failed and must not keep retrying
silently.

## Manual Execution Flow

1. Operator selects a symbol and hedge direction from the opportunity table.
2. Operator inputs:
   - Total target notional.
   - Number of execution rounds.
   - Maximum acceptable spread/slippage threshold.
   - Hard maximum slippage limit for timeout fallback execution.
3. System calculates per-round target base-asset quantity. Notional is used for
   display and exchange filter validation, but base quantity is the primary
   hedge alignment unit.
4. System loads exchange trading rules for all required legs.
5. If per-round notional is below any required minimum notional, the system
   replaces it with:

   ```text
   max(required_min_notional_values) * 1.02
   ```

   It then recalculates the execution round count.
6. System rounds quantity to the coarser required step size across both legs,
   then rechecks both legs against notional filters after rounding.
7. If the final remainder is below the minimum notional, merge it into the
   previous round.
8. Operator clicks open.
9. System starts websocket depth subscription for the selected futures leg and
   spot or margin leg.
10. UI shows live spread, estimated slippage, expected fee, and current execution
   plan.
11. Operator confirms execution.
12. System places market orders for each round.
13. For negative funding, borrowing must happen before the first market order.
14. System records every order, fill, commission, borrow, and API response.
15. UI updates position state and highlights mismatched legs.

## Execution Rules

- Market orders are the only real order type in v0.1.
- Websocket depth is used for display, spread estimation, and pre-trade
  visibility, not for limit-order placement.
- Execution is round-based.
- Each round should align futures and spot/margin legs by base-asset quantity.
  Notional is used for display and minimum-order checks.
- In future real execution, each round monitors the spread/slippage gate for up
  to 10 minutes. If the gate has not been met within 10 minutes, the executor
  automatically sends one market-order hedge round and then continues to the
  next round, unless the configured hard maximum slippage limit is exceeded.
- If the hard maximum slippage limit is exceeded, the executor pauses and
  alerts the operator instead of submitting orders.
- If either leg in a round is rejected, unresolved, partially unconfirmed, or
  otherwise non-`FILLED` after the configured confirmation path, stop all
  remaining rounds and wait for human handling.
- Partial fills, rejected orders, borrow failures, or missing responses must
  mark the execution as degraded or failed.
- No automatic close is allowed in v0.1.
- No automatic repair order is allowed in v0.1.
- A stale or missing API response must not be interpreted as proof that a leg no
  longer exists.

## Position Monitoring

The system maintains a holdings table that compares:

- Futures position direction and notional.
- Spot or margin balance direction and notional.
- Borrowed base asset and interest.
- Expected hedge direction.
- Quantity difference.
- Notional difference.
- Last data timestamp for each leg.

If legs do not match, the UI must highlight the symbol and state the mismatch
type. The first version only alerts; it does not automatically repair or close.

Mismatch examples:

- Futures leg exists, spot leg missing.
- Spot/margin leg exists, futures leg missing.
- Direction mismatch.
- Quantity difference exceeds configured tolerance.
- Borrow exists without matching futures long.
- API data stale on one side.

## Fee and Profit Accounting

The system tracks gross and net economics per symbol and for the whole account.

Required values:

- Funding income by symbol.
- Funding fee income and expense ledger by event time.
- Cumulative funding income.
- Futures commission.
- Spot or margin commission.
- Commission asset.
- BNB discount effect when commission is charged in BNB.
- Rebate-adjusted fee.
- Borrow interest.
- Estimated slippage cost.
- Net result.

Funding fee ledger rows must preserve:

- Funding income or expense time.
- Symbol.
- Futures position direction at settlement time.
- Funding rate used for the event when available.
- Position notional at settlement time.
- Signed funding amount.
- Income type.
- Binance transaction or income ID when available.
- Raw source payload reference.

Default rebate settings:

- Spot rebate: 40%.
- Futures rebate: 40%.

Accounting formula:

```text
rebate_adjusted_fee = actual_fee_after_bnb_discount * 0.6
net_funding_result = funding_income
  - futures_rebate_adjusted_fee
  - spot_or_margin_rebate_adjusted_fee
  - borrow_interest
  - estimated_slippage_cost
```

Capital occupation and additional safety-buffer cost are excluded from v0.1
accounting.

## Interface Discovery

Before full adapter encapsulation, the project should run staged
request/response discovery and save raw JSON samples. Discovery is split into:

1. Public market discovery with no API key. Completed for the current snapshot.
2. Private account discovery with read-only API key access. Completed for the
   current optional snapshot enrichment.
3. Real execution discovery before any live order path is enabled. Future.

The local Binance documentation mirror `llms-full.txt` is the first reference
for this stage. The adapter discovery report must record the exact local file
timestamp or fallback source used for each endpoint family.

### Initial Public Market Discovery

The completed initial public discovery stage used public endpoints only:

- `GET /fapi/v1/exchangeInfo`: USDⓈ-M perpetual symbols, status, filters,
  quantity rules, and minimum notional data.
- `GET /fapi/v1/premiumIndex`: mark price, index price, funding-rate field, and
  next funding time.
- `GET /fapi/v1/fundingRate`: funding-rate history for ranked symbols or sample
  candidates.
- `GET /api/v3/exchangeInfo`: spot symbol status, filters, and public
  margin-support indicators such as `isMarginTradingAllowed` or
  permission-related fields when present.
- `GET /fapi/v1/depth` and `GET /api/v3/depth`: optional public depth snapshots
  for top candidates.

That initial public discovery baseline did not use:

- API keys.
- Signed endpoints.
- Portfolio Margin account endpoints.
- User data streams or listen keys.
- Any order, borrow, repay, transfer, or fee-burn toggle endpoint.

The public market discovery report must explicitly document the semantics used
for `premiumIndex.lastFundingRate` and `nextFundingTime`. The UI must not label
stale or previous-period data as a current actionable funding signal without
evidence from samples or local docs.

### Binance Interface Baseline

The following endpoint families define the broader interface map. Read-only
private GET endpoints have landed only where the API contract and backend
whitelist allow them. Trading, borrowing, repayment, transfer, and websocket
execution paths remain future stages unless explicitly stated otherwise.

Portfolio Margin REST:

- Base URL: `https://papi.binance.com`.
- Signed endpoints require `X-MBX-APIKEY`, `timestamp`, `recvWindow`, and
  request signature.
- Default `recvWindow` should stay at or below 5000 ms unless a later design
  explicitly justifies a different value.
- Portfolio Margin request limits observed in the local docs:
  - IP request limit: 6000 per minute.
  - Order limit: 1200 per minute.
  - Adapter code must record returned rate-limit headers.
- HTTP `503` with unknown execution state must not be treated as a plain failed
  order. The executor must first confirm via user data stream or order query to
  avoid duplicate market orders.

Portfolio Margin account and UM futures:

- `GET /papi/v1/account`: account information.
- `GET /papi/v1/balance`: account balance.
- `GET /papi/v1/um/account` and `GET /papi/v2/um/account`: UM account detail.
  V2 is preferred for active symbols because it returns symbols with positions
  or open orders and has better performance.
- `GET /papi/v1/um/positionRisk`: UM position risk and liquidation fields.
- `GET /papi/v1/um/positionSide/dual`: confirm one-way mode before trading.
- `GET /papi/v1/um/accountConfig`: UM account configuration.
- `GET /papi/v1/um/symbolConfig`: UM symbol configuration.
- `GET /papi/v1/um/commissionRate`: UM user commission rate.
- `GET /papi/v1/um/feeBurn`: BNB fee-burn status for UM futures.
- `POST /papi/v1/um/order`: UM market order.
- `GET /papi/v1/um/order`: UM order query.
- `GET /papi/v1/um/income`: UM income history for funding fee ledger.
- `GET /papi/v1/um/income/asyn` and `GET /papi/v1/um/income/asyn/id`: bulk UM
  income history download path for reconciliation.

Portfolio Margin margin leg:

- `POST /papi/v1/margin/order`: margin account market order.
- `GET /papi/v1/margin/order`: margin order query.
- `GET /papi/v1/margin/myTrades`: margin trade list for commission and fill
  reconciliation.
- `GET /papi/v1/margin/maxBorrowable`: max borrowable amount.
- `POST /papi/v1/marginLoan`: borrow asset before negative-funding hedge.
- `GET /papi/v1/margin/marginLoan`: margin loan records.
- `POST /papi/v1/repayLoan`: repay margin loan.
- `GET /papi/v1/margin/repayLoan`: margin repay records.
- `GET /papi/v1/margin/marginInterestHistory`: borrow interest history.
- `POST /papi/v1/margin/repay-debt`: margin debt repayment endpoint to sample
  but not use automatically in v0.1.

Spot fallback leg:

- `GET /api/v3/exchangeInfo`: spot symbol status and filters.
- `POST /api/v3/order`: spot market order when Portfolio Margin margin route is
  unavailable.
- `GET /api/v3/order`: spot order query.
- `GET /api/v3/depth`: spot order book snapshot for websocket book bootstrap.

Futures market data and trading rules:

- `GET /fapi/v1/exchangeInfo`: USDⓈ-M futures symbol status and filters.
- `GET /fapi/v1/premiumIndex`: current mark price, index price, funding rate,
  and next funding time.
- `GET /fapi/v1/fundingRate`: funding-rate history.
- `GET /fapi/v1/depth`: futures order book snapshot when building local books.

Websocket streams:

- Portfolio Margin user data stream:
  - `POST /papi/v1/listenKey`: create listen key.
  - `PUT /papi/v1/listenKey`: keep alive.
  - `DELETE /papi/v1/listenKey`: close.
  - `wss://fstream.binance.com/pm/ws/<listenKey>`: account stream.
- User data events that must be sampled:
  - `ACCOUNT_UPDATE` for balance, position, and funding-fee related changes.
  - `ORDER_TRADE_UPDATE` for UM futures fills and order state.
  - `executionReport` for margin order fills.
  - `liabilityChange` for margin liabilities.
  - `RISK_LEVEL_CHANGE` as an alert source only.
- Spot market streams:
  - Base URL `wss://stream.binance.com:9443` or `wss://stream.binance.com:443`.
  - Subscribe to `<symbol>@depth` only after the operator starts manual open.
  - Maintain local order book by combining websocket depth updates with
    `GET /api/v3/depth` snapshots.
- USDⓈ-M futures market streams:
  - Use `wss://fstream.binance.com/ws` or `/stream`.
  - Subscribe to `<symbol>@depth` or `<symbol>@depth@100ms` only for the active
    manual-open symbol.

Trading-rule normalization:

- Spot rules must parse `LOT_SIZE`, `MARKET_LOT_SIZE`, `MIN_NOTIONAL`, and
  `NOTIONAL` from `/api/v3/exchangeInfo`.
- USDⓈ-M futures rules must parse `LOT_SIZE`, `MARKET_LOT_SIZE`, and
  `MIN_NOTIONAL` from `/fapi/v1/exchangeInfo`.
- Market order minimum notional must use the stricter minimum across all
  required legs and apply the 2% uplift defined in the manual execution flow.
- Quantity rounding must obey `stepSize`; rounded quantities must be rechecked
  against notional filters before order submission.

The adapter layer must be built from observed JSON, not only from assumed docs.
Every sampled response should be stored under `reports/api-samples/` with
timestamped filenames and redacted credentials.

## UI Requirements

The current read-only UI exposes public market discovery and private account
review screens:

- Market overview: total USDT perpetual symbols, route-class counts, asset-tag
  counts, positive-funding candidate count, rows requiring later private borrow
  validation, and data freshness timestamp.
- Funding opportunities: sortable funding table with current funding field,
  next funding time, recent funding history summary when available, route class,
  asset tag, positive/negative support status, effective minimum notional, and
  depth sample availability.
- Candidate detail: futures rules, spot rules, route classification reasoning,
  bStock detection reasoning, funding history, and raw sample file references.
- Opening-spread display: per-row `opening_quotes` show about-60s public
  bookTicker reference forward/reverse opening spreads
  (`forward_spread_pct`, `reverse_spread_pct`; percentage points, 2 decimals)
  with `fresh` / `incomplete` / `stale` / `unavailable` status. This is a public
  reference quote, not an execution surface — the frontend exposes no order,
  open, borrow, or transfer action.

Execution UI remains future work. Later execution stages should expose these
operational screens:

- Overview holdings: account status, funding summary, current risk flags,
  holdings table, leg reconciliation, and mismatch highlights.
- Opportunity table: all eligible symbols, classification, funding rate,
  account route, borrowability, minimum notional, next funding time.
- Manual open: manual open plan with total notional, rounds, corrected
  per-round amount, expected route, borrow precheck, live spread, and market
  order confirmation.
- Profit and fees: funding income, commission, BNB discount, rebate-adjusted
  fee, borrow interest, estimated slippage, net result, and all funding fee
  ledger rows with income or expense time.

## Risk Controls

- API key must not allow withdrawals.
- Per-order maximum notional must be configurable.
- Per-symbol maximum notional must be configurable.
- Total strategy notional must be configurable.
- UI must show whether the symbol is margin-routed or spot-routed.
- UI must show whether a symbol supports negative funding hedge.
- Borrow failure must stop the execution before opening the hedge.
- Leg mismatch must be highlighted and preserved for human decisioning.
- No auto-close logic is allowed without a later explicit PRD revision.

## Manual Close Design Gate

Manual close is required before real manual-open trading ships, but detailed
manual close behavior is deferred until the real manual-open stage. That later
design must define user inputs, round planning, leg order sequencing, borrow
repayment handling for negative-funding positions, ledger updates, and
acceptance tests. No automatic close is allowed in v0.1.

## Technology Direction

As-built (current read-only workstation):

- Backend: Python standard library only (`http.server`, no web framework, no
  `asyncio`); a serial background refresh thread owns the single immutable
  published state and all domain-cache writes. Runtime dependency surface is
  `jsonschema` only.
- Frontend: same-origin static HTML/CSS/vanilla-JS workstation with a
  `node frontend/self-check.js` contract self-check; no build step.
- Persistence: none yet; the snapshot is rebuilt in memory from public HTTP or
  frozen offline fixtures.
- Local service: macOS launchd agent `com.aoke.funding-hedging.server` managed
  by `scripts/service-control.py`; `scripts/run-server.sh` is the plist entry
  point.

Future direction (preferred architecture for the execution stages):

- Backend: Python with `asyncio` for strategy state, Binance adapters,
  websocket subscriptions, Decimal calculations, and execution orchestration.
- Frontend: TypeScript and React for the operator workstation.
- Persistence: local database to be decided after adapter discovery; SQLite is a
  likely first candidate for raw events, fills, and position snapshots.

Rationale:

- Python fits strategy logic, Decimal accounting, async IO, and later replay or
  analysis work.
- TypeScript/React fits dense operational UI, forms, tables, and real-time
  status updates.
- Trading credentials remain in the backend.

## Initial Public Discovery Acceptance Criteria

- Public Binance discovery uses no API key and produces raw JSON samples under
  `reports/api-samples/public-market/<timestamp>/`.
- Candidate classification can be regenerated from public samples.
- The table separates `MARGIN_SPOT_CANDIDATE`, `SPOT_ONLY_CANDIDATE`, and
  `PERP_ONLY_EXCLUDED`.
- bStocks or potential bStocks are tagged with source and confidence.
- Positive and negative funding statuses are explicit and follow the configured
  priority order.
- Funding-rate field semantics for `premiumIndex.lastFundingRate` and
  `nextFundingTime` are documented from samples or local docs.
- Planning preview aligns by base quantity, rounds by step size, and rechecks
  notional filters after rounding.
- UI prototype shows public market discovery screens with realistic public
  sample data and exposes no order, open, borrow, or execution action.
- Tests cover classification, trading-rule parsing, funding-field
  normalization, minimum-notional selection, and planning preview.
- No API credentials were added for that baseline.
- No private account endpoints or user data streams were used for that
  baseline.
- No signed endpoint was used for that baseline.
- No order, borrow, repay, transfer, or fee-burn endpoint was implemented.
- No real trading code was introduced.
- No automatic open or close was introduced.

## Private And Execution Expansion Acceptance Criteria

The current implementation has completed the read-only private snapshot subset:
account blocks, balances, positions, borrow validation, borrow-cost references,
and sort basis. The remaining criteria in this section describe future private
depth, execution, accounting, and reconciliation work.

- Private Binance API discovery commands or scripts collect raw JSON samples
  with explicit user approval and API keys that do not allow withdrawals.
- Discovery covers PAPI account, UM account, UM position risk, UM order query,
  UM income, PAPI margin order query, margin borrow/repay records, margin
  interest history, account route permissions, and borrowability.
- Portfolio Margin user data stream can receive and persist sample
  `ACCOUNT_UPDATE`, `ORDER_TRADE_UPDATE`, `executionReport`, and liability or
  risk events when available.
- Private discovery validates whether public `MARGIN_SPOT_CANDIDATE` rows are
  actually borrowable and tradeable for the operator's account.
- Trading-rule normalizer extracts minimum notional and quantity rules from
  public and private samples.
- Execution planner calculates corrected per-round base quantity with 2% uplift
  and notional rechecks.
- Accounting model can calculate rebate-adjusted fees from sample fill data.
- Funding fee ledger can display every funding income and expense row with event
  time and signed amount.
- Order-state handling treats HTTP 503 unknown execution state as unresolved
  until confirmed by order query or user data stream.

## Phase 3 Acceptance Criteria

- Backend can subscribe to selected spot and futures depth streams after manual
  operator action.
- UI can display live spread and execution plan for one selected symbol.
- Small-capital live test can place a manually confirmed positive-funding hedge.
- Every request and response is recorded.
- Holdings table detects and highlights leg mismatch without auto-closing.

## Open Questions

- Exact response fields and account permission behavior must be confirmed during
  interface discovery because Binance docs and account availability can differ by
  region, user level, and account type.
- bStocks availability, trading route, and account eligibility must be verified
  on the actual Binance account.
- Tolerance thresholds for leg mismatch need to be defined after seeing real
  fills and precision behavior.
- Whether normal spot fallback should transfer balances into Portfolio Margin
  later is deferred.
