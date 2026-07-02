# 06 Direction Synthesis: Initial Public Market Phase

Status: draft for user review
Stage ID: 2026-07-initial-direction
Synthesizer: Codex
Inputs:

- `direction-drafts/deepseek.md`
- `direction-drafts/fable5.md`
- `direction-drafts/gemini3.1pro.md`
- `direction-drafts/glm52.md`
- `direction-drafts/grok-build.md`
- `direction-drafts/kimi27.md`
- User decisions after draft review

This document is the synthesized direction for the next project stage. It is not
yet a canonical PRD update. After user approval, selected items should be
promoted into `docs/product/PRD.md`, `docs/architecture/ARCHITECTURE.md`, and
`docs/development/DEVELOPMENT_GUIDE.md`.

## 1. User Decisions To Apply

The following decisions override raw model draft suggestions:

1. Phase 1 must not use API keys, private account endpoints, private account
   websocket streams, Portfolio Margin signed endpoints, or user data streams.
   It should focus on public market understanding first.
2. Phase 1 should build the public-market list: USDⓈ-M perpetual symbols,
   current and historical funding rates, spot availability, public margin
   support indicators, bStocks detection/marking, and opportunity ranking.
3. Future real execution should use this rule: within each execution round,
   monitor the spread/slippage gate for up to 10 minutes. If the gate has not
   been met after 10 minutes, automatically execute one hedge round with market
   orders and continue to the next round. Future implementation should still
   enforce a configurable hard maximum slippage limit; if that hard limit is
   exceeded, pause and alert instead of sending market orders. This is a future
   execution rule, not a Phase 1 real-trading requirement.
4. Spot-leg feasibility must be classified into exactly three route classes:
   margin plus spot, spot only, and perp only. Margin support implies spot
   support; spot support does not imply margin support.
5. Manual close is important but should only be marked as a future design gate
   for now. Detailed manual close design should happen when the project reaches
   real manual-open development.

## 2. Final Phase 1 Direction

Phase 1 should be renamed and scoped as:

`Phase 1: Public Market Discovery + Candidate Classification + Funding Opportunity UI`

The goal is to make the real public market visible before any private account
integration. The system should answer:

- Which USDT perpetual symbols exist and are trading?
- What are their current funding rates and next funding times?
- Which symbols have a corresponding spot market?
- Which spot symbols publicly indicate margin support?
- Which symbols appear to be bStocks or tokenized equity-like products?
- Which positive-funding opportunities are structurally possible from public
  data alone?
- Which negative-funding opportunities are impossible, deferred, or require
  later private borrowability validation?

Phase 1 should not answer:

- Whether the user's account can actually borrow a specific asset.
- Whether the user's Portfolio Margin account has enough balance or margin.
- Whether the user's API key has required permissions.
- Whether a private order, loan, repayment, or user stream behaves as expected.

Those are Phase 2 or later private discovery questions.

## 3. Route Classification

Public route classification should be based on futures and spot public
exchange information.

### 3.1 Route Classes

`MARGIN_SPOT_CANDIDATE`

- The symbol has a USDT perpetual contract.
- The symbol has a corresponding USDT spot market.
- The spot market publicly indicates margin support.
- Positive funding can be shown as a candidate route: short perpetual + buy
  margin/spot leg.
- Negative funding remains `PRIVATE_BORROW_VALIDATION_REQUIRED` until a later
  private-account discovery phase verifies borrowability and PM behavior.

`SPOT_ONLY_CANDIDATE`

- The symbol has a USDT perpetual contract.
- The symbol has a corresponding USDT spot market.
- The spot market does not publicly indicate margin support.
- Positive funding can be shown as a normal spot fallback candidate.
- Negative funding is disabled because there is no public margin borrow route.

`PERP_ONLY_EXCLUDED`

- The symbol has a USDT perpetual contract.
- The symbol has no corresponding USDT spot market.
- It cannot form a contract-spot hedge and should be filtered out of executable
  candidates, while optionally remaining visible in diagnostics.

### 3.2 Asset Tags

Route class and asset type should be separate fields:

- `route_class`: `MARGIN_SPOT_CANDIDATE`, `SPOT_ONLY_CANDIDATE`, or
  `PERP_ONLY_EXCLUDED`.
- `asset_tag`: `CRYPTO`, `BSTOCK`, or `UNKNOWN`.
- `asset_tag_confidence`: `HIGH`, `MEDIUM`, or `LOW`.
- `asset_tag_source`: exchangeInfo fields, curated local list, symbol/name
  heuristic, or manual override.

This avoids mixing two different concepts:

- Route class answers whether a spot leg can be constructed.
- Asset tag answers whether special product restrictions apply.

For bStocks:

- Positive funding may be displayed as an observation/candidate only if a spot
  leg exists.
- Negative funding must be disabled.
- bStock rows should clearly show that their real tradability and account
  eligibility are not validated in Phase 1.

## 4. Public Data Sources

Phase 1 should use public endpoints only. No API key should be required.

Required public endpoint families:

- `GET /fapi/v1/exchangeInfo`
  - USDⓈ-M symbol list, status, contract type, filters, quantity rules, and
    minimum notional data.
- `GET /fapi/v1/premiumIndex`
  - Current funding rate, mark price, index price, and next funding time.
- `GET /fapi/v1/fundingRate`
  - Historical funding samples for selected symbols or ranked candidates.
- `GET /api/v3/exchangeInfo`
  - Spot symbol list, status, filters, and public margin-support indicators
    such as `isMarginTradingAllowed` or permission-related fields when present.
- `GET /fapi/v1/depth`
  - Optional public futures depth snapshots for top candidates.
- `GET /api/v3/depth`
  - Optional public spot depth snapshots for top candidates.

Do not include in Phase 1:

- `POST /papi/v1/listenKey`
- `wss://fstream.binance.com/pm/ws/<listenKey>`
- `GET /papi/v1/account`
- `GET /papi/v1/um/account`
- `GET /papi/v1/um/positionRisk`
- `GET /papi/v1/um/income`
- `GET /papi/v1/margin/maxBorrowable`
- `POST /papi/v1/um/order`
- `POST /papi/v1/margin/order`
- `POST /api/v3/order`
- `POST /papi/v1/marginLoan`
- `POST /papi/v1/repayLoan`
- Any borrow, repay, order, transfer, fee-burn toggle, or signed account route.

## 5. Output Artifacts

Phase 1 should produce concrete files that can be reviewed without trusting
model claims.

Recommended artifact layout:

```text
reports/api-samples/public-market/
  <timestamp>/
    fapi_exchange_info.json
    fapi_premium_index.json
    fapi_funding_rate_<symbol>.json
    spot_exchange_info.json
    fapi_depth_<symbol>.json
    spot_depth_<symbol>.json
    sample-index.json

reports/agent-runs/2026-07-public-market-discovery/
  00-task.md
  10-design.md
  20-implementation.md
  60-test-output.txt
  70-handoff.md
```

`2026-07-initial-direction` is the direction-freeze stage. The implementation
stage proposed by this synthesis must use a new stage-id, such as
`2026-07-public-market-discovery`, so status files, diff fingerprints, tests,
and review evidence do not mix with the direction-stage blackboard.

Candidate classification output should be saved as machine-readable data:

```text
reports/api-samples/public-market/<timestamp>/candidate-classification.json
reports/api-samples/public-market/<timestamp>/candidate-classification.csv
```

Each row should include at least:

- `symbol`
- `base_asset`
- `quote_asset`
- `perp_status`
- `spot_status`
- `route_class`
- `asset_tag`
- `asset_tag_confidence`
- `asset_tag_source`
- `positive_funding_candidate`
- `negative_funding_status`
- `current_funding_rate`
- `next_funding_time`
- `funding_history_summary`
- `futures_min_notional`
- `spot_min_notional`
- `effective_min_notional`
- `futures_step_size`
- `spot_step_size`
- `data_timestamp`
- `source_files`
- `exclusion_reason`

Suggested `negative_funding_status` values:

- `DISABLED_PERP_ONLY`
- `DISABLED_BSTOCK`
- `DISABLED_SPOT_ONLY`
- `PRIVATE_BORROW_VALIDATION_REQUIRED`

Classification priority must be deterministic:

1. `PERP_ONLY_EXCLUDED` always maps to `DISABLED_PERP_ONLY`.
2. `asset_tag = BSTOCK` maps to `DISABLED_BSTOCK` when negative funding is
   considered, even if the route class is `MARGIN_SPOT_CANDIDATE`.
3. `SPOT_ONLY_CANDIDATE` maps to `DISABLED_SPOT_ONLY`.
4. Remaining `MARGIN_SPOT_CANDIDATE` rows map to
   `PRIVATE_BORROW_VALIDATION_REQUIRED` until private borrowability discovery
   proves otherwise.

## 6. UI Direction

Phase 1 UI should show real public market structure, not private positions.

Recommended screens:

1. Market Overview
   - total USDT perpetual symbols
   - count by route class
   - count by asset tag
   - count of positive funding candidates
   - count of rows requiring later private borrow validation
   - data freshness timestamp

2. Funding Opportunities
   - sortable funding table
   - current funding rate
   - next funding time
   - 3-day or recent funding history summary when available
   - route class
   - asset tag
   - positive/negative support status
   - effective minimum notional
   - depth availability if sampled

3. Candidate Detail
   - futures rule summary
   - spot rule summary
   - route classification explanation
   - bStock detection explanation
   - funding history
   - raw sample file references

4. Manual Open Preview
   - simulation only
   - no API key
   - no real orders
   - lets the operator input total notional and rounds
   - shows minimum-notional correction and effective per-round values
   - previews planning with base-asset quantity alignment, then validates
     notional filters after step-size rounding
   - shows the future execution rule: wait up to 10 minutes per round, then
     automatically execute that round if the spread gate has not been met,
     subject to a configurable hard slippage limit
   - clearly labels this as a future execution preview

The current fake UI can be reused, but Phase 1 should avoid implying that real
account holdings, actual fees, account borrowability, or private position
matching are already known.

## 7. Technical Direction

The six model drafts agree on the technical spine. Phase 1 should adopt these
parts:

- Use Python for public data collection, classification, and deterministic
  tests.
- Use `Decimal` for all quantities, rates, notionals, and fee-related math.
- Keep public API adapters thin: request, parse, save raw JSON, normalize.
- Keep classifier and planner logic pure and independently testable.
- Use base-asset quantity alignment for planning previews. Notional is used for
  display and filter validation; it is not the primary hedge alignment unit.
- Persist public samples as files before introducing database complexity.
- Do not introduce signed private adapters until a later stage.
- Do not implement any executable order, borrow, repay, transfer, or private
  user stream path in Phase 1.

Suggested module responsibilities for the first implementation stage:

```text
backend/
  domain/
    symbols.py
    funding.py
    classification.py
    trading_rules.py
    planning.py
  adapters/
    binance_public.py
  services/
    public_market_discovery.py
  tests/
    test_classification.py
    test_trading_rules.py
    test_planning.py
```

Exact paths can be finalized in `10-design.md`; this synthesis only fixes the
responsibilities.

## 8. Decisions From Model Drafts

### 8.1 Accepted For Promotion

- Evidence must come from files, raw samples, tests, screenshots, or review
  verdicts, not from model assertions.
- Phase 1 should be zero-trading-risk.
- `Decimal` is mandatory for trading-related calculations.
- Route classification and trading-rule normalization should be pure functions
  with fixture tests.
- Public samples should be reusable as replay fixtures.
- bStocks should be tagged and visible but not treated as fully executable.
- Negative funding should not be treated as executable without private
  borrowability validation.
- Future execution must have an explicit state machine.
- Future 503 handling must be fail-closed and idempotent.
- Future execution must stop all remaining rounds when either leg reaches a
  non-`FILLED` terminal state or remains unresolved after the configured
  confirmation path.
- Manual close should be a required future design gate before real manual open.

### 8.2 Deferred

- Private account discovery.
- Portfolio Margin borrow/repay behavior.
- User data stream and listenKey behavior.
- Real BNB fee-burn status.
- Actual commission and rebate reconciliation.
- Actual position reconciliation.
- Real order execution.
- Real manual close execution.
- SQLite schema.
- React migration decision.
- Multi-symbol active execution.

### 8.3 Not Adopted As Written

- The claim that `/papi/v1/marginLoan` and `/papi/v1/repayLoan` are absent from
  the local Binance docs is not adopted. Local `llms-full.txt` contains those
  PAPI endpoints in the Portfolio Margin trade section. However, the broader
  warning is valid: PM borrow semantics and account-specific permissions must
  still be validated in a later private discovery stage before any negative
  funding execution is enabled.
- Suggestions to use private API key discovery in Phase 1 are not adopted.
- Suggestions to implement websocket order-book execution behavior in Phase 1
  are not adopted.
- Suggestions to design full manual close now are not adopted; only a future
  gate marker should be added.

## 9. PRD Updates Recommended After Approval

If the user approves this synthesis, promote these changes into
`docs/product/PRD.md`:

1. Rename or redefine Phase 1 as public market discovery, candidate
   classification, funding opportunity list, and simulation UI.
2. Split interface discovery into:
   - public market discovery with no API key
   - later private account discovery with API key
   - later real execution discovery
3. Add the three route classes:
   - `MARGIN_SPOT_CANDIDATE`
   - `SPOT_ONLY_CANDIDATE`
   - `PERP_ONLY_EXCLUDED`
4. Add separate `asset_tag` values for `CRYPTO`, `BSTOCK`, and `UNKNOWN`.
5. Clarify that public margin support is only a candidate signal. Actual
   borrowability and user-account eligibility require later private discovery.
6. Add the future execution rule:
   - each round monitors spread/slippage for up to 10 minutes
   - if the threshold is not reached within 10 minutes, the executor
     automatically executes one market-order hedge round and continues to the
     next round
   - forced execution is subject to a configurable hard maximum slippage limit;
     if exceeded, the executor pauses and alerts instead of submitting orders
   - this rule does not apply to Phase 1 because Phase 1 has no real orders
7. Add the future execution safety rule:
   - if either leg in a round is rejected, unresolved, partially unconfirmed, or
     otherwise non-`FILLED` after the configured confirmation path, stop all
     remaining rounds and wait for human handling
   - do not automatically repair missing legs or close the mismatch
8. Add the planning-preview rule:
   - align hedge size by base-asset quantity
   - round to the coarser required step size across both legs
   - validate both legs against their notional filters after rounding
   - use notional for display and minimum-order checks, not as the primary
     alignment unit
9. Add a Phase 1 validation requirement for `premiumIndex.lastFundingRate`:
   - sampled files and local docs must explain whether the displayed field is
     the current applicable funding signal, a recently updated rate, or another
     documented value
   - the normalizer must record the chosen field semantics so the UI does not
     mislabel stale or previous funding data
10. Add a manual-close marker:
   - manual close must be designed before real manual-open trading ships
   - detailed manual close flow is deferred until that stage
11. Replace any Phase 1 acceptance criteria that imply private account samples
   with public-only samples.
12. Keep private PAPI endpoints in later sections, but mark them as out of
   scope for Phase 1.
13. Fix the current dangling wording in Interface Discovery:
    `save raw JSON samples for:` should be rewritten as a complete sentence or
    followed by an explicit list.

## 10. First Implementation Stage Proposal

After this synthesis is approved, the next development stage should be:

`Stage 1: Public Market Discovery And Opportunity Prototype`

Recommended stage-id:

`2026-07-public-market-discovery`

Recommended deliverables:

1. Public Binance discovery script.
2. Public sample capture under `reports/api-samples/public-market/<timestamp>/`.
3. Symbol joiner and route classifier.
4. Funding opportunity ranking output.
5. Trading-rule normalizer for futures and spot filters.
6. Unit tests for classification, rule parsing, minimum-notional selection, and
   planning preview. Planning preview tests must use base-asset quantity
   alignment, step-size rounding, and post-rounding notional rechecks.
7. UI update that shows public market opportunity data and clearly marks the
   simulation-only manual-open preview.
8. Funding-rate field semantics note, including evidence for how
   `premiumIndex.lastFundingRate` and `nextFundingTime` are normalized and
   displayed.
9. `60-test-output.txt` with the exact validation commands and output.
10. `70-handoff.md` listing produced samples, known gaps, and Phase 2 entry
   conditions.

Acceptance should require:

- Public samples exist and are referenced by index.
- Candidate classification can be regenerated from those samples.
- The table separates `MARGIN_SPOT_CANDIDATE`, `SPOT_ONLY_CANDIDATE`, and
  `PERP_ONLY_EXCLUDED`.
- bStocks or potential bStocks are tagged with source and confidence.
- Positive and negative funding statuses are explicit.
- `negative_funding_status` follows the priority order:
  `PERP_ONLY > BSTOCK > SPOT_ONLY > PRIVATE_BORROW_VALIDATION_REQUIRED`.
- Funding-rate semantics are backed by sampled files or local docs, and the UI
  labels the chosen funding fields accurately.
- Planning preview aligns by base quantity and has deterministic tests for
  step-size rounding and notional rechecks.
- Tests pass.
- No signed endpoint, API key, private websocket, order, borrow, repay, or
  transfer code path exists in the diff.

## 11. Open Questions For User Later

These should not block Phase 1:

1. When private discovery begins, should it start with read-only API key access
   only, or include account-level listenKey/user stream sampling?
2. Should real v0.1 execution support `SPOT_ONLY_CANDIDATE` rows, or should
   first real trading require `MARGIN_SPOT_CANDIDATE` only?
3. For negative funding, should borrow be pre-borrowed for the whole plan or
   handled per round? This cannot be decided safely until PM borrow behavior is
   validated.
4. What hard notional caps should Phase 3 small-funds testing use?
5. What exact manual-close behavior is required before real manual open ships?

## 12. Summary

The six-model panel agrees that the project should not rush into private
account integration or execution. The user decision further narrows Phase 1:
build a public-market understanding layer first.

The next approved work should therefore create a real public funding-rate and
route-classification dashboard backed by public Binance samples. This gives the
project a factual market map before it touches API keys, private account state,
borrowability, or real orders.
