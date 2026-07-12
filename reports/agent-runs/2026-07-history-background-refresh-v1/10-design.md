# Stage Design

Status: **DRAFT for cross-model review.** Stage id
`2026-07-history-background-refresh-v1`.

## Summary

Add an optional background refresh loop to `SnapshotService` so deep per-symbol
work (funding history **and** private borrow validation) runs **off the request
path**. A daemon thread periodically calls a pure `refresh_once()` that walks the
visible/borrow-candidate set in **rolling batches** (default 10 symbols every
30s), warms the existing caches, and rebuilds the snapshot. Request handlers keep
reading from the hot cache, so first load no longer waits on a cold build, and a
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
  batch, warms caches, and rebuilds the snapshot into `self._cache`. Tests call
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
- D5. **Thread-safe cache writes.** Guard `_cache`, `_funding_history_cache`, and
  the batch cursor with a single `threading.Lock`; the current caches are lockless
  dicts and `check→fetch→set` is not atomic once a background writer exists.
- D6. **Enabled by default, with a testability/offline non-start guard.** No
  product opt-in gate (per user). The daemon does **not** start under
  `config.offline` or in test contexts, so the existing deterministic tests are
  unaffected. Whether to keep an emergency kill-switch config (default on) is an
  open ADR decision.
- D7. **Freshness contract preserved.** `get_snapshot()`
  (`snapshot_service.py:100`) keeps its 60s lazy-rebuild fallback; the background
  thread only lowers latency and must never be the sole freshness source.
  `data_time`/`generated_at` reflect real build time.

## Task Breakdown

- Task A (backend, owner claude_glm): daemon shell + `refresh_once()` +
  cursor batch + delta fetch + lock + config flags + freshness handling; borrow
  block warmed via existing single-exit signed path (no HMAC fan-out).
- Task B (frontend, owner kimi): ~60s `setInterval` snapshot re-pull; drawer/row
  values render from snapshot (no reliance on click-only memory state).

## Test Strategy

- Unit tests: `refresh_once()` called directly — cursor advance/wrap, delta
  fetch boundary (only new `funding_time` pulled), degrade on per-symbol failure
  (no cache poisoning), lock-held concurrent read/write small test.
- Integration tests: snapshot served from warm cache without a cold build;
  offline mode does not start the daemon; borrow block warmed without duplicate
  signed exits.
- Replay/backtest checks: existing funding-history fixtures still pass; byte
  identity of product output when the daemon is not started (offline/test).
- Manual checks: first load latency before/after; refresh keeps 7D/30D + drawer
  populated for candidate rows.

## Risks

- R1. **Thread safety** (primary): background writer + request reader on lockless
  dicts. Mitigation D5 (single lock). This is the main review focus.
- R2. **Signed private-call discipline** (D4): background borrow refresh sends
  HMAC-signed requests. Must keep the single-exit contract, never log expanded
  credentials, and stay within the signed-endpoint rate budget.
- R3. **Freshness staleness**: a background sweep may lag one interval; D7 keeps
  lazy rebuild as the correctness floor.
- R4. **Test determinism**: a real-network daemon would make tests flaky;
  D1 (pure `refresh_once`) + D6 (no start offline/test) mitigate.

## Raw Artifact Requirements For Review

- `00-intake.md`
- `10-design.md`
- `11-adr.md`
- git diff or patch
- implementation report
- test output
- source: `backend/services/snapshot_service.py`, `backend/app/server.py`,
  `backend/config.py`, `backend/domain/snapshot.py`, frontend snapshot poller
