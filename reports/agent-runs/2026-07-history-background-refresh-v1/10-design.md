# Stage Design

Status: **DRAFT for cross-model review.** Stage id
`2026-07-history-background-refresh-v1`.

Review scope: this current worktree version supersedes the earlier committed
drafts at `010ec85` and `efffe78`. Review the current three-file worktree diff;
the superseded text is not an active alternative design.

## Summary

Replace the historical absolute-rate top-20 prewarm with a backend selector for
the meaningful-rate subset of the frontend's default homepage: route is not
`PERP_ONLY_EXCLUDED` and `abs(daily_funding_rate) > 0.00030000` (strictly above
0.03%). A serial background worker keeps settled funding history warm for that
default-visible set. A click on any other eligible row submits one one-shot
symbol refresh to the same worker: refresh the selected symbol's public fields,
30-day history, actual max-borrowable amount, and actual borrow rate; update the
canonical stores; publish a complete new snapshot; then return only that updated
row projection to the caller. The click creates no watched set, subscription,
pin, retained priority, or separate interest-retention TTL; refreshed data uses
only its normal source-cache TTL from the new fetch time.
Null/invalid-rate rows may remain visible under current frontend semantics but
are intentionally outside scheduled prewarm and retain the one-shot click path.

The full snapshot endpoint never rebuilds or deep-fetches. The background worker
is the only cache mutator and snapshot publisher: scheduled ticks and one-shot
click commands are serialized through it. It assembles and validates a complete
immutable `PublishedState` in local variables and publishes it by one reference
replacement. The full snapshot remains the canonical all-row state; the click
endpoint returns a single-row projection from the newly published version so the
frontend patches only that row and drawer. Existing 60s full-snapshot polling
remains the eventual full-table reconciliation path.

## Scope And Non-Goals

In scope:

- default-homepage history selection parity with the current frontend;
- serial background history prewarm for that selected set;
- selected-symbol on-demand history fetch backed by the backend cache;
- one-shot selected-symbol public + signed-borrow refresh serialized through the
  existing background worker;
- snapshot assembly from all valid cached history, including click-loaded rows;
- pure published-state reads for the full-snapshot and legacy-history endpoints;
- independent background private refresh using existing endpoint caches/TTLs;
- explicit worker start/stop lifecycle and default-on emergency kill switch;
- a selected-symbol row-snapshot response and targeted frontend row/drawer patch.

Non-goals for v1:

- full-universe prewarm;
- funding-history delta fetch/merge;
- history-fetch concurrency or a connection pool;
- a generic job scheduler/cache framework;
- a watched/interested-symbol set, click priority retention, or separate
  interest-retention TTL;
- disk persistence or a cold-start readiness gate;
- full-snapshot download or full-table rerender after every click;
- balances, positions, account valuation, or unrelated-asset private reads in a
  selected-symbol refresh;
- removal of the existing full snapshot or funding-history endpoint.

## Existing Seams

- `SnapshotService` is a single long-lived service object.
- `_funding_history_cache` already stores successful per-symbol 30-day results
  for 1800 seconds; failures are not cached.
- `get_funding_history(symbol)` already validates eligibility, fetches a cache
  miss through the backend, and returns data for the drawer; the new row-snapshot
  refresh supersedes it for the frontend click flow. In the target design the
  compatibility endpoint becomes a pure projection from `PublishedState`: it
  performs no upstream fetch and no cache write, preserving the single-worker
  ownership invariant.
- `build_rows()` fills history for every symbol present in the supplied
  `funding_history_by_sym`; the missing step is to supply all valid cached
  entries, not only entries reached through the current top-N loop.
- Frontend defaults are `showPerpOnly=false` and `hideLowDailyRate=true`, with a
  pure decimal/string boundary of `abs(daily_funding_rate) <= 0.00030000` hidden.
- The frontend already polls `/api/public-market/snapshot` every 60 seconds.

## Design Decisions

- **D1. Default-view prewarm selector replaces top-N.** Build history candidates
  from base rows using exactly:
  `row.route_class != "PERP_ONLY_EXCLUDED"` and
  `abs(Decimal(row.daily_funding_rate)) > Decimal("0.00030000")`.
  Null/invalid rates are intentionally not prewarmed even though the current
  frontend threshold helper leaves those rows visible. They retain click refresh.
  Selection uses `daily_funding_rate`, not `lastFundingRate`. Parity for valid
  rate strings and the intentional null exception are frozen by shared boundary
  test vectors; v1 does not add a wire flag solely to share this rule.

- **D2. Serial rolling history prewarm.** The worker processes up to 10 selected
  symbols every 30 seconds, in deterministic symbol order, and uses the existing
  successful-result TTL. It fetches a complete bounded 30-day window on expiry
  or miss. No delta merge and no concurrency in v1. Candidate membership is
  recomputed from the latest base rows; a cycle uses a stable list so membership
  changes cannot corrupt an index into a mutating collection.

- **D3. Click = one-shot refresh command, not retained interest.** A click on an
  eligible symbol submits one `RefreshSymbolCommand(symbol)` to the existing
  worker and waits within a bounded timeout. The worker wakes immediately (it
  does not wait for the next 30s tick), performs the selected-symbol refresh once,
  updates canonical caches, assembles/publishes a new full `PublishedState`, and
  completes the command with the updated row projection and published version.
  The command is then discarded. Repeated later clicks are independent commands;
  there is no watched set, pin, promotion, priority ledger, or separate
  interest-retention TTL. Successful source results receive only their normal
  history/private cache TTL from this refresh time.
  Concurrent commands for the same symbol may be coalesced only while the first
  is in flight to prevent duplicate signed calls; this is bounded request
  deduplication, not retained interest. The frontend immediately places the
  clicked row in a one-second non-clickable state and ignores activation while
  its refresh remains in flight. This UI debounce absorbs accidental mouse
  double-clicks without creating a backend cooldown: a deliberate click after
  completion remains a new one-shot refresh.

  The public portion is narrow and explicit: add a per-symbol premium-index
  adapter and reuse the latest worker-owned exchange/spot/funding-interval base
  metadata; fetch the selected symbol's complete 30-day funding history. A click
  must not invoke full-universe `fetch_raw()` solely to refresh one row. Global
  base data continues to refresh on the fixed 60s scheduled cadence.

- **D4. Snapshot assembly consumes all valid backend history cache entries.** At
  assembly time, start from offline fixture history when applicable and merge a
  shallow point-in-time copy of every unexpired successful backend history entry
  whose symbol remains an eligible current USDT perpetual/TRADIFI row, regardless
  of whether it belongs to the default prewarm set. `build_rows()` then
  calculates 7D/30D fields
  for default-prewarmed and click-loaded rows alike. A background failure or TTL
  expiry does not erase history from an already published immutable snapshot;
  the next successful publication determines the new view.

- **D5. Single worker owns cache mutation and immutable publication.** Scheduled
  work and `RefreshSymbolCommand` work run serially on the same worker. HTTP
  request threads submit/wait for commands but do not mutate domain caches or
  `PublishedState`. Network fetch, cache replacement, assembly, and schema
  validation occur in worker-owned unpublished state; a
  complete state bundles `snapshot`, `data_time_ms`, `generated_at`, and
  `version`, then replaces `self._published_state` once. Requests see a complete
  old or new state and never rebuild it. Because the worker is the sole domain-
  cache writer, snapshot assembly can copy/read cache state without a broad
  business lock or concurrent-dict producer ambiguity. Standard queue/condition
  synchronization is confined to command delivery and completion; no HTTP call
  runs while holding a request-visible cache/publication lock. The legacy
  funding-history endpoint reads/projects history from `PublishedState` only and
  never calls `_fetch_history_for`, mutates cache, or becomes a second producer.

- **D6. Scheduled private refresh is independent; click private scope is narrow.**
  Private signed work never runs from `get_snapshot()`. Scheduled classic
  reference, cost leg, account panels, and borrowability retain their existing
  1h/60s TTLs, batching, and caps and are not forced into the history cursor. A
  selected-symbol command may bypass the normal cache age once for only the
  selected base asset's actual rate and max-borrowable reads. Implement this as
  exact-key one-shot TTL bypass for that asset's `maxBorrowable` entry and actual-
  rate entry/batch only; do not clear the private cache. Reuse cached classic,
  VIP/account-tier, and other shared reference data when valid. It must not fetch
  unified balances, spot balances, positions, account valuation, or unrelated
  assets. All signed traffic stays inside the single HMAC exit, GET-only
  whitelist, sanitized audit, and bounded error/degrade path. A private failure
  retains the last successful borrow fields (or existing unknown/unverified
  representation) and does not erase successful public/history refresh results.
  When a click publishes the new complete state, it reuses the last published
  `private_account` block and every non-selected row's borrow fields; it must not
  re-enter account-panel assembly methods merely because their 60s transport TTL
  expired.

- **D7. Explicit lifecycle, cadence, and bootstrap.** Constructing
  `SnapshotService` starts no thread. Server startup explicitly starts the
  worker, which performs an immediate no-sleep base refresh/publication before
  entering the 30s loop; shutdown stops it. Until that first base publication,
  snapshot and symbol-refresh reads return a brief 503; the worker never waits
  for deep-history completeness before publishing base rows. Base public data
  refreshes when age reaches 60s; every 30s tick
  processes the next <=10 missing/expired default-set histories, invokes normal
  private assembly through existing TTLs, merges all valid caches, and publishes
  after that tick. Offline and kill-switch-disabled modes start no worker.
  Requests never wait for a complete history sweep; disk persistence and strict
  first-response deep-history completeness are deferred.
  A symbol command waits at most configurable
  `symbol_refresh_timeout_seconds` (default 30s); timeout returns an explicit
  refresh-unavailable response and leaves the last published state unchanged.

- **D8. Row-snapshot endpoint and targeted frontend patch.** Add a versioned
  selected-symbol refresh/read endpoint (recommended route:
  `GET /api/public-market/symbol-snapshot?symbol=...`) returning only metadata,
  warnings, and the selected row projected from the newly published canonical
  snapshot. It never returns the full rows array. The frontend replaces that
  symbol in its in-memory snapshot, patches only the corresponding DOM row and
  drawer, applies a one-second non-clickable row guard, and does not fetch/rerender
  the full table for the click. Visibility
  changes for that row are applied locally; global ordering/summary reconciliation
  may wait for the existing <=60s full-snapshot poll and must be documented. The
  response contract uses `public-market-symbol-snapshot/v1`, includes an explicit
  `published_version`, and has a dedicated schema. The existing funding-history
  endpoint remains compatible as a read-only projection from published state.

## Selected-Refresh Failure Matrix

Every published object remains schema-complete. "No partial PublishedState"
means no half-assembled object is exposed; it does not discard successful source
updates when another source can fall back to last-good data.

| Public | History | Selected borrow | Publish/result |
|---|---|---|---|
| success | success | success | Publish all refreshed selected-row fields. |
| success | success | failure | Publish new public/history with last-good or existing unknown borrow fields and warning. |
| success | failure | success | Publish new public/borrow with last-good or empty history fields and warning. |
| failure | success | success | Reuse last-good public base; publish new history/borrow if symbol remains eligible. |
| failure with no eligible last-good row | any | any | Do not replace state; return refresh unavailable. |
| all selected sources fail | failure | failure | Do not replace state; return last published row plus failure metadata or explicit unavailable per endpoint schema. |

## Data Flow

Default prewarm:

```text
background base rows
  -> apply default-view selector
  -> fetch expired/missing history for next <=10 symbols
  -> copy all valid backend history entries
  -> assemble + validate immutable PublishedState
  -> publish once
```

Non-default click:

```text
GET symbol-snapshot?symbol=X
  -> validate X against current published eligible rows
  -> submit one RefreshSymbolCommand(X); wake worker; bounded wait
  -> worker refreshes X public fields + 30D history
  -> worker refreshes X base-asset actual rate/max-borrowable via signed GET
  -> no balances/positions/account valuation/unrelated assets
  -> worker updates canonical stores, assembles/validates/publishes full state
  -> endpoint returns only X row + metadata/version/warnings
  -> frontend patches X row + drawer only; row is non-clickable for first 1s
```

## Task Breakdown

- **Task A (backend-dominant, owner `claude_glm`):** default-view selector,
  explicit worker lifecycle/cadence, serial history prewarm, one-shot command
  queue/completion, selected public + narrow signed-borrow refresh, canonical
  stores, all-valid-cache assembly, immutable publication, row-snapshot endpoint
  and schema, configuration, raw sample evidence, and backend tests.
- **Task B is light frontend integration within the backend-dominant bounded
  task:** switch drawer click to the row-snapshot endpoint and patch only the
  selected row/drawer; preserve existing 60s poller. Per Harness dominance rules,
  the whole bounded task may remain with `claude_glm`; the development breakdown
  must record the exact frontend file/test boundary.

## Test Strategy

- Selector parity vectors:
  - `0.00029999`, `0.00030000`, `-0.00030000`: not prewarmed;
  - `0.00030001`, `-0.00030001`: prewarmed when route is not excluded;
  - any high rate with `PERP_ONLY_EXCLUDED`: not prewarmed;
  - null/invalid daily rate: visible under current frontend default but
    intentionally not prewarmed; click path remains available.
- Background unit tests: stable batch order, max 10/tick, cursor/cycle behavior
  when membership changes, complete 30-day fetch on miss/expiry, no delta path,
  per-symbol failure without cache poisoning, selected-set size observation, and
  `ceil(N/10)*30s` sweep-time comparison against the 1800s TTL.
- One-shot click tests: command creates no retained interest/priority TTL; worker
  refreshes selected public/history and only selected-asset signed borrow data;
  balances/positions/account valuation/unrelated assets are never called;
  published full state and returned row share the same version/data; subsequent
  full snapshot contains the row result until normal cache expiry/replacement.
- Repeated-click tests: two activations inside one second produce one frontend
  request; activation while drawer refresh is in flight is ignored; a deliberate
  click after completion produces a new command; concurrent backend duplicates
  coalesce by selected symbol/base asset.
- Public/private scope tests: click uses the per-symbol public adapter and never
  full `fetch_raw`; exact selected-asset private keys bypass TTL once while shared
  references stay cached; complete publication reuses prior `private_account` and
  never calls account-panel balance/position methods.
- Legacy endpoint tests: funding-history compatibility reads published state only
  and performs zero network/cache writes.
- Failure-matrix tests cover each table row above and prove no half-assembled
  object is published.
- Endpoint/contract tests: response contains one row and no full `rows` array;
  invalid/ineligible symbols degrade consistently; timeout/failure retains last
  published state; raw public and sanitized signed evidence grounds the contract.
- Request-path tests: `get_snapshot()` triggers no network or rebuild; the
  selected-symbol endpoint triggers only its bounded command and never directly
  mutates caches; signed-call audit contains only allowed borrow endpoints for the
  selected asset and never account-panel endpoints.
- Publication tests: readers see a complete old or new version; click cache
  replacement never mutates an already published state; refresh failure keeps
  the last published state.
- Lifecycle tests: construction alone starts no thread; explicit start is
  idempotent; stop terminates promptly; offline and kill-switch-disabled modes
  do not start.
- Private tests: signed calls remain single-exit/GET-only, stay off full-snapshot
  and legacy-history handlers, honor existing TTL/caps, and degrade without
  blocking publication. The symbol endpoint only submits/waits for its worker
  command; signed calls execute in the worker.
- Frontend tests: targeted row/drawer patch, one-second click guard, in-flight
  guard, stale-response identity checks, and no click-time full-table render.
- Regression: existing backend suite and `node frontend/self-check.js`; expected
  production frontend change is bounded to `frontend/index.html`.

## Risks And Review Focus

- **Cold-start expectation:** minimal v1 guarantees a fast degraded first
  response and eventual default-view completeness, not strict cold-first-response
  completeness. Reviewer must flag any text or test that claims otherwise.
- **Selector drift:** backend/frontend copies of the default rule can diverge;
  exact valid-rate boundary vectors and the intentional null exception are
  mandatory until a future contract centralizes it.
- **Command latency/failure:** a selected refresh intentionally waits on multiple
  public and signed reads. The endpoint needs a bounded timeout, visible loading
  state, per-source last-good fallback, and no partial PublishedState publication.
- **Targeted frontend reconciliation:** a refreshed borrow/net-yield value can
  change global ordering or summary. v1 patches the row/drawer immediately and
  relies on the <=60s full poll for global reconciliation; reviewer must confirm
  that bounded temporary ordering staleness is acceptable.
- **Request pressure:** the default selector has no artificial top-N cap, so
  tests/metrics must record selected-set size and confirm the 10/30s cadence fits
  the public endpoint budget under observed market distributions.
- **Private isolation:** private work remains a separate background concern and
  must not leak back into snapshot/history request handlers.
- **Compatibility drift:** the old funding-history endpoint must remain a pure
  published-state projection; any on-demand fetch there would violate the single-
  worker ownership contract.

## Raw Artifact Requirements For Review

- `00-intake.md`
- `10-design.md`
- `11-adr.md`
- git diff or patch
- source: `backend/services/snapshot_service.py`, `backend/app/server.py`,
  `backend/config.py`, `backend/domain/snapshot.py`,
  `backend/services/private_client.py`, public adapter, frontend default filter
  and selected-history poller
- new row-snapshot schema and raw public/sanitized signed samples required for
  the contract amendment
