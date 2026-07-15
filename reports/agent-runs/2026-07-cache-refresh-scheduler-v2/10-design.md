# Stage Design: Three-Cadence Cache Refresh Scheduler

## Summary

The live worker keeps one serial write authority and one immutable
`PublishedState`. It evaluates three logical cadence groups. The groups share
publication but not freshness gates: a cache entry in one source never makes a
different source fresh.

The design freezes scheduled endpoint membership below. Manual click refresh,
fallback-only endpoints, and discovery-only endpoints are recorded separately so
no endpoint silently changes cadence.

## Frozen Endpoint Matrix

### Group A: 60-second fast sources

These sources feed current opportunity ranking or the private account panel and
are evaluated independently every approximately 60 seconds.

| Endpoint | Shape | Cache key | Purpose | Condition |
|---|---|---|---|---|
| `GET /fapi/v1/premiumIndex` | one full-market response | global source | current estimated funding rate, mark/index prices, next funding time, candidate ranking | always in live mode |
| `GET /api/v3/ticker/price` | one full-spot-market response | global source | USDT valuation price map | only when private account enrichment is enabled and usable |
| `GET /papi/v1/balance` | one whole-account response | global source | unified balances | private channel only |
| `GET /papi/v1/um/positionRisk` | one whole-account response | global source | UM positions | private channel only |
| `GET /api/v3/account?omitZeroBalances=true` | one whole-account response | exact global source + fixed params | spot balances | private channel only |

Group A is not subject to the 10-symbol budget.

### Group B: fixed 30-minute shared/unified sources

These are queried as one fixed timer group every 1800 seconds. They are not
subject to the symbol cursor or 10-symbol budget.

| Endpoint | Shape | Cache key | Purpose | Condition |
|---|---|---|---|---|
| `GET /fapi/v1/exchangeInfo` | full futures market | global source | contract eligibility, type, precision, filters | always in live mode |
| `GET /api/v3/exchangeInfo` | full spot market | global source | spot-leg matching and precision | always in live mode |
| `GET /fapi/v1/fundingInfo` | adjusted-symbol list | global source | non-default funding interval | always; current best-effort 8h fallback remains unchanged |
| `GET /sapi/v1/margin/allPairs` | all classic-margin pairs | global source | margin pair reference | private channel only |
| `GET /sapi/v1/margin/allAssets` | all classic-margin assets | global source | asset borrowability reference | private channel only |
| `GET /sapi/v1/margin/crossMarginData` | all rate tiers | global source | VIP/reference borrow-rate fallback table | private channel only |
| `GET /sapi/v1/account/info` | whole-account metadata | global source | VIP level and account switches | private channel only |

Group B updates its source timestamps only on the existing successful return
path. This stage does not add new failure or empty-response policy.

#### Slow-private transport TTL contract

The effective transport-cache TTL for the slow private sources in Groups B and
C is 1800 seconds. The implementation changes the current
`private_channel_ttl_seconds` default from 3600 to 1800; any runtime override
used by these scheduled keys must remain `<= 1800`. The independent 60-second
account TTL remains `private_channel_fast_ttl_seconds=60`.

The transport entry is timestamped no later than its corresponding successful
business-cache update. A Group B or Group C business timestamp advances only
after a successful source result. At business age `>=1800s`, the corresponding
transport entry must therefore also be expired and the scheduled call must
perform real upstream I/O. A still-valid older transport entry must never be
treated as a successful 30-minute refresh or advance `updated_monotonic`.

### Group C: 30-second sweep, at most 10 homepage symbols

The worker takes the next at-most-10 symbols from the homepage history candidate
set every 30 seconds. `10 symbols` means 10 logical work units, not a hard cap of
10 HTTP calls.

The homepage candidate predicate remains:

```text
route_class != PERP_ONLY_EXCLUDED
AND abs(daily_funding_rate) > 0.00030000
```

For every selected symbol, the three component freshness checks are independent.

| Endpoint | Query shape | Business cache key | Due rule | Eligibility |
|---|---|---|---|---|
| `GET /fapi/v1/fundingRate?symbol=...&startTime=...&endTime=...&limit=1000` | one request per symbol | `symbol` | missing or age `>= 1800s` | every selected homepage candidate |
| `GET /sapi/v1/margin/next-hourly-interest-rate?assets=...&isIsolated=false` | one batched request for due assets from the selected symbols, respecting the existing per-call asset cap | unpack response to one cache entry per `base_asset` | missing or age `>= 1800s` | selected row has negative funding, `MARGIN_SPOT_CANDIDATE`, and `asset_tag in {CRYPTO, METAL}` |
| `GET /papi/v1/margin/maxBorrowable?asset=...` | one request per due unique base asset | `base_asset` | missing or age `>= 1800s` | same private borrow-candidate predicate |

The combined scheduled-borrow predicate is frozen as:

```text
daily_funding_rate < -0.00030000
AND route_class == MARGIN_SPOT_CANDIDATE
AND asset_tag in {CRYPTO, METAL}
AND the read-only private channel is usable
```

This is the borrow-eligible subset of the homepage candidate set. A row whose
absolute daily funding rate is `<=0.00030000` is outside the homepage set and
receives no scheduled history, borrow-rate, or max-borrowable work. Its existing
manual selected-row refresh remains unchanged.

The historical global `borrow_check_max_calls` top-50 truncation does not apply
to scheduled Group C borrow-rate or max-borrowable work. The at-most-10-symbol
cursor is the scheduling pressure boundary. Across successive cursor cycles,
every current homepage borrow candidate may receive max-borrowable validation.

Duplicate base assets in a selected batch are queried once. A fresh history entry
does not suppress due borrow data; a fresh borrow-rate entry does not suppress due
history or max-borrowable data.

The existing approximately 94-candidate set requires about 10 ticks, so the
normal successful-path refresh age is approximately 30-35 minutes: 1800 seconds
until due, plus up to one approximately five-minute full sweep before the symbol
is examined. There is no separate 25-minute operation.

### Homepage borrow coverage semantics

The existing wire shape `coverage = {probed, skipped, reason}` is preserved, but
its counting universe is the de-duplicated `base_asset` set satisfying the
combined homepage scheduled-borrow predicate above:

- `probed` counts current-universe assets for which the worker has completed at
  least one scheduled max-borrowable attempt since the asset entered the current
  homepage universe. An endpoint failure is still an attempt and remains
  represented by the existing per-row/private error path; it does not create or
  advance a successful business-cache timestamp.
- `skipped` counts current-universe assets not yet attempted because the
  at-most-10-symbol cursor has not reached them. `reason` is
  `rate_limit_budget` exactly when `skipped > 0`, otherwise `null`.
- Assets outside the current homepage borrow universe, including negative rows
  with absolute daily funding rate `<=0.00030000`, are not counted as skipped and
  do not receive `borrowability_not_probed` merely because they are outside the
  scheduled product scope.
- Leaving the homepage universe removes an asset from these counts and stops
  scheduled borrow refresh. Re-entry makes a missing or expired component due
  when the cursor next examines the symbol.

Coverage is therefore cursor-attempt coverage, not a claim that every attempted
endpoint succeeded or that every cached value is currently fresh. This keeps
failure reporting separate and avoids reviving the removed top-50 semantics.

## Explicit Non-Normal Paths

The following endpoints are not members of the three normal scheduled groups:

- `GET /sapi/v1/margin/interestRateHistory?asset=...` remains a fallback-only
  cost-leg source. It may run only for a selected, due homepage borrow asset whose
  `next-hourly-interest-rate` request failed or returned no usable value. A
  successful fallback is stored per `base_asset` with its source. It does not
  add another logical symbol slot and is not expanded into homepage-wide normal
  polling.
- `GET /fapi/v1/premiumIndex?symbol=...`, the selected-symbol history request,
  forced single-asset `next-hourly-interest-rate`, `interestRateHistory`, and
  `maxBorrowable` remain part of the existing manual row-click command and do not
  consume scheduled symbol slots.
- `GET /papi/v1/margin/marginInterestHistory` and
  `GET /papi/v1/portfolio/interest-history` remain discovery-only and are not
  called by normal snapshot assembly.

## Cache Structure

Use the smallest source-aware business-cache shape required by this stage:

```text
SourceCacheEntry = (updated_monotonic, value)
BorrowRateCacheEntry = (updated_monotonic, value, source)

global_source_cache[source_id] = SourceCacheEntry
funding_history_cache[symbol] = SourceCacheEntry
borrow_rate_cache[base_asset] = BorrowRateCacheEntry
max_borrowable_cache[base_asset] = SourceCacheEntry
```

The exact implementation may preserve existing specialized dictionaries instead
of introducing one generic class, provided every logical source has an explicit
timestamp and Group C can test each component independently.

`PrivateClient._cache` remains the transport cache with the slow scheduled
private TTL contract above. The new per-base-asset borrow-rate business cache
must not use the comma-joined batch string as its freshness identity. A
successful batch is unpacked into individual asset values, sources, and
timestamps before snapshot assembly.

The wire response remains unchanged. Source timestamps are internal scheduling
metadata and are not added to the public schema in this stage.

## Scheduling And Publication

1. Cold start fetches Groups A and B, then publishes as soon as the existing
   validation permits; Group C warms incrementally.
2. The serial worker remains the only domain-cache writer.
3. On each wake, it evaluates Group A and Group B due times independently, then
   examines at most 10 Group C symbols when the 30-second sweep is due. The
   cursor advances for every examined symbol even when all three components are
   fresh and no request is issued.
4. Scheduled network updates and snapshot assembly are separate phases. Group B
   refresh owns the fixed shared/reference endpoints. Group C refresh owns only
   the selected symbols' due history and due per-asset borrow components.
5. The scheduled assembly phase reads persistent Group A/B source state and
   per-symbol/per-asset business caches. It must not call the current all-row
   `fetch_cost_leg_chain(rate_probe_assets)` path, rebuild a global top-50
   max-borrowable probe, or otherwise initiate hidden network work.
6. Borrow-rate resolution is per asset: use a current per-asset next-hourly
   value first, the selected-asset `interestRateHistory` fallback when invoked,
   then the current Group B VIP/reference table. Row `borrow_rate_source`
   records the source actually used. The unchanged top-level
   `chain_hit_tier`/`chain_hit_source` remains a compatibility diagnostic for
   the highest-priority source used by at least one current borrow row; it does
   not assert that every row used the same source.
7. All successful due-source updates are assembled into the same canonical
   snapshot and schema-validated before atomic publication.
8. Manual click commands remain serialized through the existing command queue
   and keep their existing force-refresh and deadline semantics.

## Scope Decisions Frozen By The Operator

- No 25-minute refresh-ahead window.
- No new failure-path last-good retention guarantee.
- No new empty/partial-success overwrite protection.
- No endpoint response completeness matching in this stage.
- Normal Group C refresh is driven by missing/age-`>=1800s` component state.
- Group B is a fixed 1800-second global timer and is independent of Group C.
- Slow scheduled private transport TTL is 1800 seconds and may not exceed the
  corresponding business TTL.
- Scheduled borrow work is homepage-only, uses the strict
  `daily_funding_rate < -0.00030000` combined predicate, and has no global
  top-50 truncation.
- Fetch/update phases are separate from cache-only snapshot assembly.

## Implementation Boundaries

Expected code seams:

- split the current `fetch_raw()` inputs so Group A and Group B are not forced to
  share one 60-second timestamp;
- extend the current history sweep into a component-aware symbol sweep;
- introduce per-base-asset borrow-rate business cache timestamps;
- split scheduled Group B reference refresh and Group C due-asset refresh from
  cache-only assembly; do not retain the all-row scheduled cost-leg call;
- make scheduled max-borrowable selection follow the selected Group C symbols
  and remove the global instantaneous top-50 cap from this scheduled path;
- redefine borrow coverage over the current homepage borrow universe while
  preserving the existing wire object shape;
- preserve the full snapshot wire contract and click refresh path.

## Test Strategy

### Unit tests

- Group A and Group B become due independently at 60 and 1800 seconds.
- Group B calls do not consume Group C symbol slots.
- Slow private transport data is reused at 1799 seconds and performs real
  upstream I/O at 1800 seconds; a runtime slow TTL above 1800 is rejected.
- A selected symbol with fresh history and expired borrow rate refreshes only the
  borrow-rate component.
- A selected symbol with missing max-borrowable and fresh other components calls
  only `maxBorrowable`.
- Batch rate results update timestamps per asset rather than per batch string.
- Duplicate base assets are queried once.
- Positive-funding and non-margin selected symbols do not trigger borrow calls.
- A negative row at or below absolute daily rate `0.00030000` does not enter the
  scheduled borrow universe or coverage counts; crossing above the threshold
  makes it eligible on a later cursor examination.
- More than 50 homepage borrow candidates can all receive max-borrowable work
  across successive cursor cycles; no global top-50 truncation remains.
- Scheduled assembly performs no all-row cost-leg or max-borrowable network
  calls, and `interestRateHistory` runs only after selected-asset next-hourly
  failure or absence.
- Coverage increments by current-universe cursor attempts, excludes out-of-scope
  low-rate assets, and does not treat endpoint failure as a successful cache
  timestamp.

### Integration tests

- Cold-start Groups A/B plus incremental Group C publication remain schema-valid.
- Existing full snapshot and manual row-click endpoints retain their contracts.
- Existing frontend fixtures/self-checks remain unchanged.

### Manual checks

- Observe request audit counts over at least one 60-second window and one
  simulated/shortened 1800-second window in deterministic tests.
- Confirm no credentials, full signed queries, or account payloads enter logs.

## Risks

- Splitting `fetch_raw()` incorrectly could combine source payloads from
  inconsistent generations; schema validation protects shape but not product
  freshness semantics.
- Batch membership changes must not become the business-cache identity for
  borrow-rate freshness.
- A 3600-second runtime transport override would recreate false 30-minute
  refreshes; configuration validation must keep slow scheduled transport TTL at
  or below 1800 seconds.
- Leaving the existing all-row `fetch_cost_leg_chain` inside scheduled assembly
  would bypass the 10-symbol pressure model even if transport caching hides some
  calls.
- The symbol cursor must keep making progress when most selected components are
  fresh and therefore issue no requests.
- With failures and successful empty responses explicitly out of scope, this
  stage guarantees only the normal successful refresh path requested by the
  operator.

## Raw Artifact Requirements For Later Review

- `00-task.md`
- `10-design.md`
- `11-adr.md`
- git diff or patch
- implementation report
- deterministic test output
- relevant source files
