# Stage ADR

Status: **DRAFT for cross-model review.** Stage id
`2026-07-history-background-refresh-v1`. Updated 2026-07-12 from direct operator
refinement; recommended defaults remain subject to the recorded human gates.

Review scope: this current worktree version supersedes the earlier committed
drafts at `010ec85` and `efffe78`. Review the current three-file worktree diff;
the superseded decisions remain only as Git audit history and are not active
alternatives unless explicitly restated below.

## Context

The current cold snapshot performs serial top-20 settled-history calls and, when
enabled, private signed borrow work from the request-time build. The history
portion adds ~7.6s and the private path can raise the cold build to ~35s. The
existing backend per-symbol history cache and selected-symbol endpoint already
support click-through history loading, but snapshot assembly consumes only the
current top-N set. Therefore a click-loaded non-top-N history exists in backend
memory yet disappears from the main snapshot after browser refresh.

The operator clarified the product target: preload history for the rows the
homepage displays by default, not for a rank-based top-N or the full universe;
and treat a click on another row as one explicit refresh of that symbol's public
market/history plus actual account-specific borrow amount/rate. The click must
update canonical backend state and publish a full new snapshot, while returning
only the selected row for efficient drawer rendering. It creates no subscription,
watched set, priority retention, or separate interest-retention TTL and never
reads positions, balances, account valuation, or unrelated assets.

## Decision

Replace top-N prewarm with the meaningful-rate subset of the default view:

```text
route_class != PERP_ONLY_EXCLUDED
AND abs(daily_funding_rate) > 0.00030000
```

A serial background worker refreshes complete 30-day history for up to 10 of
those symbols every 30 seconds under the existing 1800s successful-result TTL.
For other eligible symbols, a selected-symbol row-snapshot endpoint submits one
command to the same worker. The worker refreshes public/history and selected-
asset signed borrow data, updates canonical stores, publishes a full immutable
state, and completes the request with only the updated row projection. Snapshot
assembly merges all valid eligible-symbol history entries regardless of default-
set membership. Main snapshot requests remain read-only. Scheduled private work
retains independent TTL/candidate semantics. No delta fetch, full-universe
prewarm, concurrency pool, watched set, priority ledger, or disk cache is added;
one row-snapshot endpoint/schema and targeted frontend patch are added.

## ADR List

- **ADR-1 Default-view meaningful-rate scope replaces top-N.** Prewarm the
  non-`PERP_ONLY_EXCLUDED` rows whose absolute `daily_funding_rate` is strictly
  greater than `0.00030000`. This matches the valid-rate subset of current
  frontend defaults. Null/invalid-rate rows may remain visible but are
  intentionally not prewarmed and retain click refresh. The predicate and null
  exception are tested at exact positive/negative/string boundaries.

- **ADR-2 Serial complete-window refresh.** Process at most 10 default-view
  symbols per 30-second tick in a stable deterministic cycle. Reuse the 1800s
  successful cache and fetch the complete bounded 30-day window on miss/expiry.
  Delta fetch and funding concurrency are deferred to v1.1 unless measured load
  later justifies them.

- **ADR-3 Click is one one-shot symbol refresh.** A click submits one bounded
  `RefreshSymbolCommand` to the existing worker, which wakes immediately,
  refreshes the selected symbol once, updates canonical stores, publishes a full
  state, and returns only the updated row projection/version. The command then
  disappears. No watched set, subscription, pin, retained priority, or separate
  interest-retention TTL exists. Successful source results receive only their
  normal cache TTL from the new fetch time. Only concurrent in-flight duplicates
  for the same symbol may be coalesced to protect signed endpoints. The frontend
  disables the clicked row for one second and ignores activation while its
  refresh remains in flight; this absorbs accidental double-clicks without a
  backend post-completion cooldown.

- **ADR-4 One worker owns domain caches and immutable publication.** Scheduled
  ticks and click commands are serialized through one worker. HTTP request
  threads submit/wait but never mutate domain caches or publish. The worker
  updates caches, builds/validates unpublished local state, replaces the full
  `PublishedState` reference once, then returns the selected row projection when
  applicable. Queue/condition synchronization is limited to command delivery and
  completion; no network call is protected by a request-visible cache lock. The
  legacy funding-history endpoint is a pure projection from published state and
  performs no upstream fetch or cache mutation.

- **ADR-5 Independent scheduled private refresh plus narrow click refresh.**
  Scheduled classic reference, cost leg, account panels, and per-asset borrow
  work retain existing 1h/60s TTLs, batching, and caps and stay outside the
  history cursor. A click command may force one selected-base-asset actual-rate
  and max-borrowable refresh through exact selected-asset cache-key TTL bypass,
  reusing valid global/account-tier references and never clearing the whole
  private cache. Complete click publication reuses the last published account
  panel and every non-selected row's borrow fields. It must never fetch balances,
  positions, account valuation, or unrelated assets.
  Single HMAC exit, GET-only whitelist, sanitized audit, bounded timeout, and
  last-good degradation remain mandatory.

- **ADR-6 Explicit default-on lifecycle and fixed cadence.** `SnapshotService`
  construction has no thread side effect. Server startup starts one worker, which
  immediately produces a base publication before the 30s loop; shutdown stops
  it. Base public refresh is due at 60s, each 30s tick processes <=10 default-set
  histories and publishes, and normal private calls rely on existing TTLs. Click
  commands wake the same worker between ticks. Offline mode and an emergency
  kill switch prevent start; no implicit test-runner detection is used. Before
  the immediate first base publication, snapshot/symbol reads return brief 503.
  Symbol-command wait is configurable, default 30s, and timeout preserves the
  last published state.

- **ADR-7 Fast degraded cold start.** Before a first successful background
  history sweep, requests may return a base snapshot with empty/null deep fields.
  Existing 60s frontend polling displays later publications. Strict completeness
  of the first cold-process response would require blocking startup prewarm or
  persistent disk cache and is deferred pending explicit operator choice.

- **ADR-8 Full snapshot is canonical; click response is one-row projection.** Add
  `public-market-symbol-snapshot/v1` at a selected-symbol refresh/read route. The
  worker always publishes a complete canonical snapshot, but this endpoint
  returns only metadata/warnings and the selected row from that same version —
  never the full rows array. The response exposes `published_version`. Frontend
  applies a one-second row click guard and patches only that row and drawer.
  Existing <=60s full polling reconciles global ordering/summary; the existing
  funding-history endpoint remains compatible as a read-only projection.

## Alternatives Considered

- **Absolute-rate top-N prewarm:** rejected because rank is not the user's
  homepage visibility rule; it can spend requests on hidden rows and omit visible
  rows.
- **Full-universe prewarm:** rejected because it adds public request pressure for
  data normally not viewed.
- **Delta fetch in v1:** deferred because merge, inclusive-boundary dedupe,
  failure retention, empty-success freshness, and TTL interaction add complexity
  without being necessary to move work off the request path.
- **Strict startup prewarm gate:** deferred because it moves delay from the first
  request to service readiness and contradicts the minimal fast-degradation goal.
- **Disk-persistent history cache:** deferred because process-restart persistence
  is not required to fix browser-refresh loss and would add storage lifecycle and
  corruption/migration concerns.
- **New frontend timer/task:** rejected because the 60s poller already exists.
- **Return the full snapshot after every click:** rejected because it transfers
  and rerenders unrelated rows; the click returns only the selected row projected
  from the newly published canonical state.
- **Clicked-symbol watched/priority set:** rejected because a click expresses one
  refresh request, not a subscription. No retained click state is needed.
- **Click refresh of balances/positions/account valuation:** rejected as
  unrelated to the selected symbol and unnecessarily expensive/private.
- **Click-time full-universe public refresh:** rejected because a selected-row
  command uses a per-symbol public adapter plus current base metadata; global
  base refresh remains scheduled at 60s.
- **Backend cooldown after click:** rejected because each later deliberate click
  is a new refresh. Accidental duplication is handled by a one-second frontend
  guard plus in-flight backend coalescing.
- **One cursor for history and borrow:** rejected because history is symbol-
  scoped, borrowability is asset-scoped, and classic/cost-leg calls have global
  or endpoint-defined batch semantics.
- **One broad cache/rebuild lock:** rejected because it adds request-path
  maintenance burden and can transmit network latency to readers. Immutable
  publication plus whole-entry history-cache replacement keeps the v1 protocol
  narrow.

## Tradeoffs

- **Default-view scope:** low request pressure and direct product alignment, but
  selected-set size varies with the market and has no fixed top-N ceiling.
- **One-shot click refresh:** selected public/history/borrow fields become current
  and persist in canonical cache/snapshots under normal TTL, but the symbol is not
  kept warm after expiry unless it qualifies for scheduled default prewarm or is
  clicked again.
- **One-row response:** avoids full snapshot transfer/rerender on click, but
  global ordering/summary may remain stale in the browser until the <=60s poll.
- **Complete 30-day fetch:** simple replacement semantics and existing tested
  behavior, at the cost of refetching unchanged settled records on TTL expiry.
- **Fast degraded cold start:** request latency stays bounded, but the first cold
  page may be temporarily incomplete until background publication and frontend
  polling.
- **Duplicated default predicate:** avoids a wire change, but backend/frontend
  parity must be protected by exact boundary tests.

## Edge Cases And Acceptance Constraints

- `abs(daily_funding_rate) == 0.00030000` is excluded; comparison is strict.
- Positive and negative thresholds behave symmetrically using decimal semantics.
- `PERP_ONLY_EXCLUDED` is excluded regardless of rate magnitude.
- Null/invalid daily rates do not enter background prewarm.
- Null/invalid daily rates may remain visible in the frontend and use click
  refresh; this is an intentional exception to exact set parity.
- Candidate membership changes do not skip/corrupt a mutable cursor cycle.
- Per-symbol failure does not poison cache or delete an already published value.
- Click-loaded cache success appears in the next published snapshot without a
  second publisher; the click response row and canonical full snapshot share the
  same published version.
- Selected-symbol response contains exactly one row projection and no full rows
  array; frontend click does not download or rerender the full table.
- Click signed calls are limited to selected-asset actual rate/max-borrowable and
  valid shared reference prerequisites; balances, positions, valuation, and
  unrelated assets are absent from the audit.
- Click creates no watched set, retained priority, pin, or separate interest TTL;
  refreshed values receive only normal source-cache TTL.
- Two frontend activations within one second produce one command; activation
  while the command is in flight is ignored; a later completed-state click may
  refresh again.
- Click public refresh never invokes full `fetch_raw`; click private refresh
  bypasses only selected-asset rate/max-borrowable keys and reuses valid shared
  references plus the last published account panel.
- Legacy funding-history reads published state only and performs no fetch/write.
- Selected-refresh partial failure follows the truth table in `10-design.md`:
  successful sources may publish with last-good fallbacks, but no half-assembled
  state is exposed and no eligible last-good row means no replacement.
- Cache expiry follows the existing 1800s successful-result contract; failures
  remain uncached.
- Readers never observe fields from different `PublishedState` versions.
- Private signed calls never originate from full-snapshot or legacy-history
  handlers; the symbol endpoint only submits/waits while its worker executes the
  selected-asset signed calls.
- Offline and kill-switch-disabled service construction starts no thread.

## Human Decisions Still Required

1. Confirm the recorded default of brief 503 before the worker's immediate base
   publication; it never waits for deep-history completeness.
2. Confirm the emergency kill switch remains present, default product behavior
   enabled (recommended).

## Links And Reviewer Notes

- Existing frontend predicate: `frontend/index.html` default
  `showPerpOnly=false`, `hideLowDailyRate=true`, threshold helper at ~1188–1214.
- Existing history cache/click path:
  `backend/services/snapshot_service.py` `_fetch_history_for` and
  `get_funding_history`.
- Delivered predecessor: `2026-07-funding-annualized-history-v1`.
- Reviewer should focus on selector parity, all-valid-cache snapshot merge,
  single-worker command semantics, selected-only signed scope, row-only response
  contract, canonical full-state/row-version identity, cold-start accuracy, and
  avoidance of watched-set or account-panel scope creep.
- Harness intake remains incomplete: `status.json`, `70-handoff.md`, `00-task.md`,
  evaluator/bookkeeper identity, and the MEDIUM `12-development-breakdown.md`
  must be supplied before implementation.
