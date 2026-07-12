# Stage ADR

Status: **DRAFT for cross-model review.** Stage id
`2026-07-history-background-refresh-v1`. Reconstructed 2026-07-12 from the
2026-07-11 discussion; recommended defaults shown, three decisions still open
for the operator.

## Context

First-load cold build is dominated by the request-time serial deep-history loop:
~7.6s for 20 sequential `fundingRate` calls (no connection reuse), and ~35s once
private borrow validation is enabled (up to 50 serial signed calls). The backend
history cache works but only accelerates re-fetch; it does not persist display,
and non-top-N rows are `null` in the snapshot, so a browser refresh drops the
7D/30D and drawer values. Binance offers no multi-symbol batch for
`/fapi/v1/fundingRate`. The fix is to move deep work off the request path into a
background refresh that warms a hot cache and rebuilds the snapshot.

## Decision

Add a daemon thread to `SnapshotService` that periodically runs a pure
`refresh_once()`: walk the borrow-candidate/visible set in rolling batches
(default 10 symbols / 30s), incrementally fetch only new settlements, warm both
the funding-history cache and the private borrow block, and rebuild the snapshot
under a single lock. Request handlers read the hot cache. Frontend re-pulls the
snapshot every ~60s. Enabled by default; not started in offline/test contexts.

## ADR list (recommended defaults)

- **ADR-1 Prewarm scope = candidate/visible set**, not all ~660 symbols (reuse
  `select_borrow_candidates`). Full-universe every sweep breaches the request
  budget; the original funding stage ADR-2 rejected it and that reasoning stands.
- **ADR-2 Rolling batch, no concurrency in v1** — 10 symbols / 30s cursor sweep.
  Simplest, self-throttling, hides latency in the background. **Connection reuse
  + small concurrency (5–10) is the highest-impact speedup** (20 calls 7.6s →
  ~1–2s) but is deferred to **v1.1** to keep the v1 review surface small.
  *(Open decision: operator may pull concurrency into v1.)*
- **ADR-3 Single `threading.Lock`** over `_cache`, `_funding_history_cache`, and
  the cursor. Eliminates the read/write race introduced by the background writer.
- **ADR-4 (supersedes original draft ADR-4) Background refresh covers BOTH
  funding history and private borrow** (per operator). Borrow validation is the
  larger cost, so the payoff is larger. Constraint: the background borrow refresh
  must reuse the existing **single signed exit**, must not fan out HMAC traffic,
  must never log expanded credentials, and must stay within the signed-endpoint
  rate budget. *(Open decision: confirm borrow-in-background, or keep borrow in
  request path for v1 and add it in v1.1.)*
- **ADR-5 Freshness contract** — `get_snapshot()` keeps its 60s lazy-rebuild
  fallback as the correctness floor; the background thread only lowers latency.
  Timestamps reflect real build time.
- **ADR-6 Enabled by default; testability/offline non-start guard.** Per
  operator, no product opt-in gate. The daemon does not start under
  `config.offline` or in tests, preserving deterministic byte-identical output
  there. *(Open decision: keep an emergency kill-switch config, default on, or
  no config toggle at all.)*
- **ADR-7 Incremental (delta) fetch in v1** — when cached, fetch only settlements
  newer than the last cached `funding_time`. Near-zero risk, removes most repeat
  traffic; included in v1.

## Alternatives Considered

- **Concurrency + connection pool in the request path** (no background thread):
  faster cold build but still on the request path and still re-does work each
  cold build; rejected as the v1 core (kept as v1.1 accelerator).
- **Full-universe prewarm**: rejected — request/signed budget (Binance
  500/5min/IP shared window for `fundingRate`/`fundingInfo`; signed borrow limits).
- **asyncio rewrite**: rejected — server is already `ThreadingHTTPServer`; a
  daemon thread avoids a new runtime model and dependency.
- **Product opt-in (default off)**: rejected by operator; replaced by a
  testability/offline non-start guard (ADR-6).

## Tradeoffs

- Tradeoff: background writer vs lockless caches.
  - Benefit: first load fast; refresh keeps data; latency hidden.
  - Cost: must add a lock and prove no race (main review risk).
- Tradeoff: borrow in background (ADR-4).
  - Benefit: removes the largest (~35s) first-load cost.
  - Cost: signed HMAC calls off the request path; single-exit + credential +
    rate-budget discipline must be re-proven.

## Edge Cases Or Constraints

- Per-symbol failure must not poison cache or 503 the snapshot (reuse existing
  degrade).
- Delta fetch boundary must not double-count or skip a settlement at
  `funding_time == last cached`.
- Offline/test: daemon must not start; output byte-identical to today.
- Cursor must wrap correctly when the candidate set changes size between ticks.

## Links To Prior Direction

- Requirements seed: `reports/follow-ups/2026-07-funding-annualized-history-drawer.md`
  (on branch `docs/2026-07-10-session-artifacts`), §5.3 fetch policy.
- Delivered predecessor: stage `2026-07-funding-annualized-history-v1` (accepted;
  its ADR-2 rejected full-universe polling — ADR-1/ADR-2 here are consistent).
- Source discussion: Claude Code session `07e45576` (2026-07-11).

## Reviewer Notes

- The daemon loop is deliberately a thin shell over a pure `refresh_once()` so
  tests never sleep or hit the network — do not read the loop as untestable.
- Enabling by default (ADR-6) is an operator decision against the usual
  additive/default-off Harness convention; please weigh the test-determinism and
  rollback implications and recommend whether an emergency kill-switch is
  warranted.
- ADR-4 intentionally moves signed borrow work into the background; verify the
  single-exit contract and credential handling are preserved, not just the
  history path.
