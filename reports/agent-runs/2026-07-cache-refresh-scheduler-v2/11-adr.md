# Stage ADR: Source-Aware Three-Cadence Refresh

## Context

The current live worker refreshes four public base inputs together under one
approximately 60-second timestamp, sweeps at most 10 history symbols every 30
seconds under a 1800-second history TTL, and relies on private transport-cache
TTLs for borrow and account inputs. A fresh history tuple says nothing about the
freshness of borrow-rate or max-borrowable data.

The operator wants low request pressure and approximately 30-minute homepage
freshness, with a distinct fixed 30-minute refresh for shared/unified sources.

## Decision

Adopt three explicit scheduled endpoint groups:

1. 60-second dynamic all-market/account sources;
2. fixed 1800-second shared/unified sources;
3. a 30-second at-most-10-symbol homepage sweep whose history, borrow-rate, and
   max-borrowable components each refresh only when missing or age `>=1800s`.

Represent batch borrow-rate freshness per base asset at the business-cache layer.
Preserve current public schemas and the serial single-writer publication model.

Freeze the following implementation contracts after independent cross-check and
operator approval:

- change the slow private transport TTL default from 3600 to 1800 seconds and
  require its effective scheduled value to remain `<=1800`; successful business
  timestamps advance only after a successful source result;
- separate scheduled source updates from cache-only snapshot assembly, with
  Group B owning fixed references and Group C owning only selected due
  components;
- define the scheduled borrow universe as homepage rows with
  `daily_funding_rate < -0.00030000`, `MARGIN_SPOT_CANDIDATE`, and
  `asset_tag in {CRYPTO, METAL}`;
- remove the global top-50 max-borrowable truncation from scheduled Group C and
  define coverage only over the current homepage borrow universe;
- call `interestRateHistory` only as a selected-asset fallback after unusable or
  failed next-hourly data, never as a normal homepage-wide poll.

## Alternatives Considered

- Force-refresh every selected component whenever the cursor reaches a symbol.
  - Rejected because the operator prefers lower backend pressure and accepts
    approximately 30-minute freshness.
- Start refresh at 25 minutes to enforce a strict 30-minute maximum age.
  - Rejected by the operator. There is no refresh-ahead boundary; normal age may
    reach approximately 30-35 minutes because of cursor latency.
- Keep borrow-rate freshness keyed by the comma-joined request batch.
  - Rejected because batch membership changes and cannot represent the freshness
    of one asset.
- Retain the 3600-second slow private transport TTL under 1800-second business
  scheduling.
  - Rejected because a scheduled due call could return a still-valid transport
    entry without real upstream I/O and falsely advance business freshness.
- Keep the current scheduled `fetch_cost_leg_chain` and rely on transport-cache
  hits to separate cadence groups.
  - Rejected because it mixes Group B, Group C, and fallback endpoints, applies
    next-hourly to the all-row rate pool, and makes request pressure depend on
    changing batch-cache keys rather than the 10-symbol cursor.
- Retain the global max-borrowable top-50 or continue scheduled borrow work for
  negative rows outside the homepage rate threshold.
  - Rejected by the operator. Assets with absolute daily funding rate
    `<=0.00030000` are not homepage opportunities and do not warrant scheduled
    borrow checks; every homepage borrow candidate may instead be covered over
    successive cursor cycles.
- Add generalized last-good, response completeness, and empty-overwrite guards.
  - Deferred by explicit operator decision; endpoint-specific correctness work
    can address those cases separately.

## Tradeoffs

- Tradeoff: per-source timestamps add internal cache state.
  - Benefit: one cached component cannot incorrectly suppress another component's
    refresh.
  - Cost: more scheduling tests and source-merging logic.
- Tradeoff: no refresh-ahead window.
  - Benefit: simpler pressure-controlled behavior matching operator intent.
  - Cost: effective refresh age includes up to one symbol-sweep cycle.
- Tradeoff: no new failure/empty-response semantics.
  - Benefit: keeps this stage bounded to normal scheduling behavior.
  - Cost: abnormal upstream responses remain governed by existing behavior.
- Tradeoff: slow private transport TTL decreases from 3600 to 1800 seconds.
  - Benefit: Group B/C business due checks correspond to real 30-minute upstream
    refreshes.
  - Cost: slow shared private reference endpoints may be requested twice per
    hour instead of once per hour.
- Tradeoff: scheduled borrow coverage is homepage-only and no longer top-50.
  - Benefit: the 10-symbol cursor becomes the single pressure boundary and all
    meaningful homepage borrow candidates can eventually receive validation.
  - Cost: low-rate negative rows outside the homepage threshold receive no
    scheduled borrow refresh and remain manual-refresh-only.
- Tradeoff: fetch/update and assembly become distinct phases.
  - Benefit: cadence ownership and request bounds are explicit and testable.
  - Cost: the service must retain Group B source state and per-asset rate/source
    state instead of relying on one snapshot-wide cost-leg call.

## Edge Cases Or Constraints

- Private endpoints run only when the explicitly enabled read-only private
  channel is usable.
- `10 symbols` is a logical work-unit cap, not an HTTP-call cap.
- Duplicate base assets are deduplicated before private calls.
- The Group C cursor examines at most 10 homepage symbols and advances even when
  every component is fresh; it does not scan until it accumulates 10 due calls.
- Coverage counts only current homepage borrow candidates. Out-of-scope
  low-rate rows are not skipped; not-yet-attempted in-scope assets are skipped
  until reached by the cursor, while request failures stay in existing error
  paths and never advance successful business timestamps.
- Fallback/manual/discovery-only endpoints must not silently enter a normal
  cadence group.
- Current rate ranking remains approximately 60 seconds fresh; it must not move
  into the 30-minute shared group.

## Links To Prior Direction

- Prior background worker stage:
  `reports/agent-runs/2026-07-history-background-refresh-v1/`
- Current source contract: `docs/api/public-market-contract.md`

## Reviewer Notes

Review this ADR against the exact endpoint matrix in `10-design.md`. In
particular, challenge whether any endpoint is misclassified between 60 seconds,
fixed 30 minutes, and the 30-second symbol sweep, and whether an existing
fallback/manual endpoint has been accidentally omitted.
