# Stage Design

Status: **DRAFT for cross-model review.** Stage id
`2026-07-history-background-refresh-v1`.

## Summary

Add an optional background refresh loop to `SnapshotService` so deep per-symbol
work (funding history **and** private borrow validation) runs **off the request
path**. A daemon thread periodically calls a pure `refresh_once()` that walks the
visible/borrow-candidate set in **rolling batches** (default 10 symbols every
30s), assembles a new immutable published state, and swaps it in by one atomic
reference replacement. Request handlers only read the published state, so first
load no longer waits on a cold build, and a
browser refresh no longer loses history (the values live in the snapshot, not
frontend memory). Frontend adds a ~60s `setInterval` to re-pull the snapshot.

## Assumptions

- Existing seams are reused, not rewritten:
  - `backend/services/snapshot_service.py:50` `SnapshotService` is a single
    long-lived object → natural home for a daemon thread.
  - `backend/app/server.py:104` already uses `ThreadingHTTPServer` → adding one
    `threading.Thread(daemon=True)` is idiomatic; no asyncio/new dependency.
  - Two caches already exist: snapshot (`config.cache_ttl_seconds`, 60s) and
    per-symbol history (`snapshot_service.py:67` `_funding_history_cache`,
    `config.funding_history_cache_ttl_seconds=1800`).
  - Per-symbol failure degrade already exists (`_fetch_history_for`,
    `snapshot_service.py:292`; returns None, does not cache failures).
  - Candidate set is already encapsulated: `select_borrow_candidates`
    (`backend/domain/snapshot.py:471`) and top-N (`domain/snapshot.py:43`).
- Binance `/fapi/v1/fundingRate` is per-symbol only (no batch); settled records
  are immutable once past.

## Design Decisions

- D1. **Background daemon + pure `refresh_once()`.** A daemon thread loops with a
  sleep, but the unit of work is a pure `refresh_once(now)` that fetches the next
  batch, warms enrichment data, and assembles a new `PublishedState` in local
  variables (published only on full success). Tests call
  `refresh_once()` directly; the loop/sleep is a thin shell so tests stay
  deterministic and offline.
- D2. **Rolling batch, cursor-based.** Each tick refreshes the next `N`
  (default 10) symbols of the candidate set, cycling a cursor. A ~50–56 symbol
  set completes a full sweep in ~5 ticks ≈ 2.5 min — comfortably inside the
  1800s history TTL and the ≥1h settlement cadence.
- D3. **Incremental (delta) fetch in v1.** When history is already cached for a
  symbol, fetch only new settlements (`startTime = last cached funding_time`),
  not the full 30-day window. Near-zero risk, removes most repeat traffic.
- D4. **History AND borrow both refreshed in background** (per user). The loop
  warms funding history and the private borrow-validation block for the
  candidate set, so first load and refresh both read warm results. This
  **supersedes the original draft ADR-4** (which kept borrow in the request
  path). See ADR for the signed-call discipline this requires.
- D5. **Single-writer immutable publication (no business-level cache lock).** The
  background refresh worker is the *only* writer of the enrichment store and the
  published state. It performs all network fetch, merge, snapshot assembly, and
  schema validation in local (unpublished) variables, then publishes the finished
  result with one reference replacement `self._published_state = next_state`.
  `snapshot`, `data_time_ms`, `generated_at`, and `version` are bundled into a
  single `PublishedState` that is never mutated in place. A request thread reads
  the published reference and therefore sees either the complete old version or
  the complete new one — never fields mixed across versions. No `threading.Lock`
  is added to the request read path; HTTP, assembly, validation, and JSON
  serialization never run inside any publish critical section. The rolling cursor
  is private to the single worker (no lock). Schema is loaded at startup (not
  lazily) so request and worker threads never race on initialization.
  `PrivateClient` is called only by the worker; if a second caller is ever added,
  its concurrency is designed then, not pre-covered by a global lock now.
- D6. **Enabled by default, with a testability/offline non-start guard.** No
  product opt-in gate (per user). The daemon does **not** start under
  `config.offline` or in test contexts, so the existing deterministic tests are
  unaffected. Whether to keep an emergency kill-switch config (default on) is an
  open ADR decision.
- D7. **Request path read-only; publish-failure keeps last good.** `get_snapshot()`
  (`snapshot_service.py:100`) returns the currently published `PublishedState` and
  never rebuilds or deep-fetches. `get_funding_history()` degrades on a miss and
  lets the worker backfill — it is not a second cache writer. If a refresh round's
  fetch/merge/validation fails, nothing is published: the last successful
  `PublishedState` stays live and is still served, with staleness expressed via
  existing warning/log metadata (no new wire field in v1). `data_time` /
  `generated_at` / `version` inside each PublishedState reflect the build that
  produced it.

## Task Breakdown

- Task A (backend, owner claude_glm): daemon shell + `refresh_once()` +
  cursor batch + delta fetch + `PublishedState` + atomic reference publish +
  startup schema load + config flags + publish-failure/staleness handling; borrow
  block warmed via existing single-exit signed path (no HMAC fan-out).
- Task B (frontend, owner kimi): ~60s `setInterval` snapshot re-pull; drawer/row
  values render from snapshot (no reliance on click-only memory state).

## Test Strategy

- Unit tests: `refresh_once()` called directly — cursor advance/wrap, delta
  fetch boundary (only new `funding_time` pulled), degrade on per-symbol failure
  (no cache poisoning).
- Concurrency acceptance tests (single-writer immutable publication):
  - during concurrent reads, every response sees a **complete** old or new
    version — no `snapshot`/`data_time` mix across versions;
  - `get_snapshot()` and `get_funding_history()` trigger **no** deep network
    fetch and **no** cache/enrichment write;
  - when a refresh round fails, requests keep returning the **last successful**
    `PublishedState`;
  - a published object is **never** mutated in place by a later enrichment update
    (publish is reference replacement only).
- Integration tests: snapshot served from warm cache without a cold build;
  offline mode does not start the daemon; borrow block warmed without duplicate
  signed exits.
- Replay/backtest checks: existing funding-history fixtures still pass; byte
  identity of product output when the daemon is not started (offline/test).
- Manual checks: first load latency before/after; refresh keeps 7D/30D + drawer
  populated for candidate rows.

## Risks

- R1. **Concurrency correctness** (primary): correctness rests on single-writer
  + immutable `PublishedState` + one atomic reference publish (D5), not on a lock.
  Review focus shifts to proving no in-place mutation of a published object, no
  reader-side writes, and no fields mixed across versions. This relies on the
  current CPython single-reference-replacement semantics (see R5); a second writer
  or in-place mutation would break it.
- R2. **Signed private-call discipline** (D4): background borrow refresh sends
  HMAC-signed requests. Must keep the single-exit contract, never log expanded
  credentials, and stay within the signed-endpoint rate budget.
- R3. **Freshness staleness**: a background sweep may lag one interval; the
  correctness floor is D7 (always serve the last successful `PublishedState` +
  staleness metadata), not a request-path rebuild.
- R4. **Test determinism**: a real-network daemon would make tests flaky;
  D1 (pure `refresh_once`) + D6 (no start offline/test) mitigate.
- R5. **Runtime assumption**: v1 depends on the current CPython single-object
  reference-replacement semantics for lock-free publication. The 60s cadence is
  **not** the correctness basis — single-writer + immutable object + one reference
  publish is. Adding a second writer, mutating a published object in place, or
  moving to a runtime that does not satisfy this assumption requires re-evaluating
  the synchronization design.

## Raw Artifact Requirements For Review

- `00-intake.md`
- `10-design.md`
- `11-adr.md`
- git diff or patch
- implementation report
- test output
- source: `backend/services/snapshot_service.py`, `backend/app/server.py`,
  `backend/config.py`, `backend/domain/snapshot.py`, frontend snapshot poller
