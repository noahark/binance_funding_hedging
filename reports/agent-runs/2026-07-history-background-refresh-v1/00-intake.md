# Stage Intake And Complexity

Status: **DRAFT for cross-model review** — reconstructed 2026-07-12 from the
2026-07-11 design discussion (Claude Code session `07e45576`). The original
draft was never committed (untracked, lost). Not yet an approved delivery stage.

Stage id: `2026-07-history-background-refresh-v1`

## User Discussion Summary

On first page load the snapshot cold build blocks for several seconds. Measured
(backend module, no HTTP-layer cache):

- `fetch_raw()` base calls ≈ **2583ms**.
- Single `fundingRate` history call ≈ **250–470ms** (new TLS connection each
  time; `urllib`, no connection reuse).
- **20 sequential `fundingRate` calls ≈ 7618ms** (~381ms each) — the top-N deep
  history loop is the dominant cost of the ~10s cold build at `top_n=20`.
- With the private borrow channel enabled, cold build reaches **~35s** (up to
  50 serial signed borrow checks, `BINANCE_BORROW_CHECK_MAX_CALLS=50`).

Two more findings:

1. The backend per-symbol history cache (1800s) **works** (474ms → 17ms on
   re-fetch), but it is an acceleration cache, not display persistence. The
   7D/30D and drawer values merged on row click are **frontend memory state**
   and are lost on refresh; non-top-N rows are `null` in the snapshot itself.
2. Binance `/fapi/v1/fundingRate` is **per-symbol only** — no multi-symbol batch
   endpoint exists, so throughput can only improve via concurrency, connection
   reuse, or incremental fetch, not a batch API.

**User intent for this stage:** move the deep-history work (both funding history
AND private borrow) **off the request path** into a background refresh that
keeps a hot cache warm, so first load is fast and refresh does not lose data.
Rolling batch cadence **30s / 10 symbols**. Background refresh **enabled by
default** (user declined a product opt-in gate); a test/offline non-start guard
is still required for deterministic tests.

## Classification

- Complexity: `MEDIUM`
- Direction panel required: `false`
- Existing synthesis covers this work: `true` (this note + 2026-07-11 discussion)
- User approved lightweight route: `true`
- Lightweight skip allowed: `true`

## Rationale

- Reason: bounded backend change on existing seams (`SnapshotService`,
  `ThreadingHTTPServer`, two existing caches, `select_borrow_candidates`,
  per-symbol degrade). Estimated ~100–200 backend lines + a small frontend
  timer. No new external dependency, no new endpoint contract, no schema wire
  change required for v1.

## Human Gates

- Gate: operator confirms the 3 ADR decisions still open (borrow-in-background
  scope, emergency kill-switch, concurrency in v1 vs v1.1) before implementation.
- Gate: user acceptance required before merge to main (Harness default).

## Routing Decision

- Next node: `stage-design`

## Bookkeeper

- Provider/model/session: to be assigned; draft prepared by Claude Opus 4.8
  (`claude-opus-4-8`) as reconstruction author, not as independent bookkeeper.
- Independent from implementers: `true` (target: independent local session)
- If not independent, disclosure: n/a at draft stage.

## Parallel Mode

- Uses `docs/parallel-development-mode.md`: `false` (backend-dominant; light
  frontend timer)
- R10 dispatch tail required: `false`
- R4 diff reconciliation required: `false`

## Evaluator

- Provider: (to assign)
- Model: (to assign)
- Skill: complexity_evaluator
