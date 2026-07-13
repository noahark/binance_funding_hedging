# Stage Intake And Complexity

Status: **DRAFT for cross-model review** — updated 2026-07-12 after operator
scope refinement. Not yet an approved delivery stage.

Review scope: this current worktree version supersedes the earlier committed
drafts at `010ec85` and `efffe78`. Review the current three-file worktree diff;
the superseded text remains only in Git history as audit evidence and is not an
active alternative design.

Stage id: `2026-07-history-background-refresh-v1`

## User Discussion Summary

On first page load the snapshot cold build blocks for several seconds. Measured
(backend module, no HTTP-layer cache):

- `fetch_raw()` base calls ≈ **2583ms**.
- Single `fundingRate` history call ≈ **250–470ms** (new TLS connection each
  time; `urllib`, no connection reuse).
- **20 sequential `fundingRate` calls ≈ 7618ms** (~381ms each) — the historical
  top-N loop dominates the ~10s cold build at `top_n=20`.
- With the private borrow channel enabled, cold build reaches **~35s** (up to
  50 serial signed borrow checks, `BINANCE_BORROW_CHECK_MAX_CALLS=50`).

The existing per-symbol backend history cache (1800s) already works, and the
selected-symbol endpoint already fetches a non-preloaded symbol on click and
caches the successful result in the backend. The remaining product defect is
that snapshot assembly only consumes the current top-N history set: a history
loaded by a click is merged into frontend memory but is not automatically
included in later snapshots, so a browser refresh loses the displayed values.

## Refined Operator Intent

The product goal is not full-universe prewarming. It is:

1. Keep the default homepage opportunity set warm so its rows can show settled
   7D/30D history without click-time fetching.
2. Define that set as the meaningful-rate subset of the existing frontend
   defaults, replacing historical absolute-rate top-N selection:
   - exclude `route_class == PERP_ONLY_EXCLUDED`;
   - exclude `abs(daily_funding_rate) <= 0.00030000` (0.03%);
   - therefore prewarm rows where route is not excluded and absolute daily rate
     is strictly greater than 0.03%; null/invalid-rate rows may remain visible in
     the frontend but are intentionally not prewarmed and retain click refresh.
3. Treat a row click as one explicit, one-shot symbol refresh. The refresh reads
   the selected symbol's current public market fields, complete 30-day settled
   history, actual account-specific borrow amount, and actual account-specific
   borrow rate; writes successful results into the same backend stores used by
   scheduled refresh; publishes a new canonical snapshot; and returns only that
   symbol's updated row snapshot for the drawer. A click does not subscribe,
   promote, pin, or extend background priority for the symbol.
4. Keep request pressure bounded: do not prewarm the full universe, do not add
   funding-history concurrency in v1, and do not add incremental/delta merging
   in v1.
5. Keep scheduled private borrow refresh on its own endpoint TTL/candidate
   cadence, but allow the explicit selected-symbol refresh command to force one
   bounded read-only signed refresh for that symbol's base asset. It must not
   fetch balances, positions, account valuation, or unrelated assets.
6. Keep the full snapshot endpoint as the canonical all-row data source. The
   frontend continues to filter the full snapshot locally. The click endpoint
   returns only the refreshed row projection, so the frontend patches that row
   and drawer instead of downloading or rendering the full table on every click.

The recommended cold-start contract is fast degradation rather than request
blocking: before the first background sweep finishes, the initial snapshot may
contain empty/null deep history; subsequent existing 60s frontend polling shows
the warmed values. A strict guarantee that the first cold-process response
already contains every default-row history would require either a startup
prewarm gate or persistent disk cache and is outside the minimal v1 unless the
operator explicitly chooses it.

## Classification

- Complexity: `MEDIUM`
- Direction panel required: `false`
- Existing synthesis covers this work: `true` (operator refinement + this
  intake/design/ADR packet)
- User approved lightweight route: `true`
- Lightweight skip allowed: `true`

## Rationale

- Bounded backend change on existing seams: replace top-N history selection
  with a default-view selector, make snapshot assembly consume all valid backend
  history-cache entries, add explicit background lifecycle/publication, and move
  private work off full-snapshot and legacy-history request handlers.
- No new dependency, database, generic scheduler, concurrency pool, watched-set,
  or priority-retention system is required. One selected-symbol row-snapshot
  endpoint/schema and light targeted frontend patching are required.
- Delta fetch is deferred; v1 keeps the existing complete 30-day fetch and
  1800s successful-result TTL.

## Human Gates

- Gate: operator confirms the recorded cold-start default: brief 503 only before
  the worker's immediate base publication, never waiting for deep-history sweep.
- Gate: operator confirms an emergency background-refresh kill switch remains
  available with background refresh enabled by default.
- Gate: user acceptance required before merge to main (Harness default).

## Operator Decisions Recorded 2026-07-12

- A click is a one-shot refresh only; there is no interested/watched set,
  separate interest-retention TTL, or retained priority. Successfully refreshed
  data receives only its normal source-cache TTL from the new fetch time.
- The one-shot refresh includes actual max-borrowable and actual borrow-rate
  reads for the selected base asset through the existing signed GET-only exit.
- It excludes balances, positions, account valuation, and unrelated assets.
- The backend publishes the complete canonical snapshot, but the click response
  returns only the selected symbol's updated row snapshot for targeted frontend
  rendering.
- The frontend disables the clicked row for one second immediately after the
  click to absorb accidental mouse double-clicks. While the refresh remains in
  flight it also ignores duplicate activation; after completion, a later
  deliberate click is a new one-shot refresh.

## Routing Decision

- Next node: `development-breakdown`
- Implementation remains paused pending operator resolution of the two human
  gates, stage intake bookkeeping, and the required MEDIUM development breakdown.

## Bookkeeper

- Provider/model/session: to be assigned; original reconstruction authored by
  Claude Opus 4.8 (`claude-opus-4-8`), then refined by Codex from direct operator
  guidance.
- Independent from implementers: `true` (target: independent local session)
- If not independent, disclosure: n/a at draft stage.

## Parallel Mode

- Uses `docs/parallel-development-mode.md`: `false` (backend-dominant bounded
  task with light frontend production integration)
- R10 dispatch tail required: `false`
- R4 diff reconciliation required: `false`

## Evaluator

- Provider: (to assign)
- Model: (to assign)
- Skill: complexity_evaluator
