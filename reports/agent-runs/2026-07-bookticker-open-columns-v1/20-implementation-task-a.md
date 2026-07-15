# Task A Implementation Report — Claude-GLM

Stage: `2026-07-bookticker-open-columns-v1`
Branch: `stage/2026-07-bookticker-open-columns-v1` (HEAD `fea9fdc`, the stage base
SHA; not committed)

## Implementer

- Adapter: `claude_glm`
- Provider identity: `zhipu_glm` (not Anthropic)
- Model: `glm-5.2`
- Skill: `senior_developer`
- Role: Task A implementer (backend / API / schema / domain / tests / human-readable
  contract sync). Per identity, not review-1 for this Task A and not review-2 for
  this stage.

## Exact Changed Files

All writes are within the Task A allowed set (no commit; no branch / git-history
change).

Source:

- `backend/adapters/binance_public.py` — added `_normalize_book_ticker(rows)`
  (string-only price discipline, non-empty-list shape) and
  `BinancePublicClient.fetch_book_ticker_pair()` (live-only paired full bookTicker,
  separate request-log keys, atomic raise on empty map / one-side failure).
- `backend/domain/snapshot.py` — added `compute_opening_spread_pct(bid, ask)`,
  `_opening_price(raw)`, and `build_opening_quotes(spot_quote, futures_quote, *,
  usable, updated_at)` (the `fresh | incomplete | stale | unavailable` truth table,
  per-direction spread independence). Decimal-only; strict
  `(bid − ask)/ask × 100`; quantize `0.01` `ROUND_HALF_UP` on the final result only;
  `-0.00 → 0.00`.
- `backend/services/snapshot_service.py` — added the `book_ticker_pair` Group A
  refresh block in `_refresh_due_sources` (capability-checked, atomic completion-
  time cache write, `urllib.error.URLError | OSError | ValueError` degraded to
  last-good), the `_attach_opening_quotes(rows)` projection (monotonic age →
  usable/stale recomputed every assembly), and its call in `_assemble`.

Schema:

- `schemas/api/public-market/snapshot.schema.json` — added the optional additive
  `opening_quotes` row property (closed object, 8 required nested fields,
  `status` enum `[fresh, incomplete, stale, unavailable]`, prices/spreads as
  `decimal_string | null`). `symbol-snapshot.schema.json` is unchanged and inherits
  via the shared row `$ref`.

Tests:

- `backend/tests/test_book_ticker.py` (new) — adapter seam (URLs, request log,
  offline None, number-price rejection, empty-map raise, one-side-failure raise),
  pure spread formula (BTC vector + oracle parity, `1.005` HALF_UP carry, negative
  zero, invalid/zero operands), `build_opening_quotes` truth table (unavailable /
  stale / fresh / forward-only / reverse-only / zero-price / no-spot-leg), and the
  row join via `_attach_opening_quotes` (exact crypto, bStock alias
  `TSLAUSDT → TSLABUSDT`, perp-only no-spot-leg, never-succeeded).
- `backend/tests/test_background_worker.py` — added the `fetch_book_ticker_pair`
  seam to `_SeamStubPublic` (`fail_book_ticker` / `book_pair`) and threaded it
  through `_seam_service`; added pair-cache tests (cold success, 60s Group A
  cadence, atomic one-side failure not cached, CC-1 failure does not suppress
  premium/group_b, private-disabled still fetches, `119s` usable / `120s` stale
  projection without manufacturing a fetch failure, and the legacy no-seam
  `_StubPublic` → `unavailable` with no `AttributeError`).
- `backend/tests/test_negative_schema.py` — added `opening_quotes` legacy-
  compatibility (omitted + full + unavailable-all-null all valid), nested unknown-
  property rejection, number price/spread rejection, invalid-status rejection, and
  missing-required rejection.
- `backend/tests/test_symbol_snapshot_endpoint.py` — added the
  `fetch_book_ticker_pair` seam to `_StubPublic` and click-path tests (the click
  issues NO new bookTicker HTTP; the projected row `opening_quotes` equals the full-
  snapshot canonical row's).

Docs (sync of this implementation only — endpoints, cache, wire contract, verify):

- `docs/architecture/ARCHITECTURE.md` — Data Flow now shows the paired bookTicker
  Group A source → additive `opening_quotes`, with the 60s cadence / 120s
  usability / click-no-extra-I/O note.
- `docs/development/DEVELOPMENT_GUIDE.md` — added the opening-quotes targeted
  verification command.
- `docs/api/public-market-contract.md` — status bumped to v0.7; appended the
  "Opening Quotes Amendment (v0.7)" section (source, atomic pair cache, join,
  usability projection, field table, status truth table, click path, regression
  red lines).

`backend/tests/test_snapshot.py` was reviewed and needed no change (its offline
`_build_snapshot` path calls `build_rows` + `assemble_snapshot` directly; because
`opening_quotes` is optional and attached by the service, those offline snapshots
remain schema-valid — verified by the full suite).

## Key Implementation Decisions

- **Producer purity vs. "always emit complete object".** `build_rows` stays pure
  (no `opening_quotes`); the service attaches `opening_quotes` to every published
  row via `_assemble → _attach_opening_quotes`. The service is the producer, so
  "the current producer always emits a complete object" holds for the live/online
  path, while the offline `test_snapshot.py` direct-build path stays schema-valid
  because the field is optional.
- **Atomic pair cache.** Both endpoints + non-empty list shape + non-empty
  normalized map must succeed before the `book_ticker_pair` cache advances; the
  adapter raises on any partial/empty side, and the service keeps last-good (FR-2).
- **Usability is a projection, not a fetch side effect.** `usable = (now −
  success_ts) < 2 * cache_ttl_seconds` is recomputed every assembly from
  `time.monotonic()`, so a pair crossing 120s flips to `stale` without another
  fetch failure.
- **Status buckets.** `usable` (age `< 2*ttl`) + `updated_at` (None vs set)
  cleanly distinguish all four statuses inside `build_opening_quotes`; per-
  direction spread independence means one missing leg never blanks the other
  direction, and a valid price is preserved even when its direction is not.
- **Zero is missing liquidity.** `"0.00000000"` is not a computable zero: that
  price is `null` and only the direction it gates is blanked (`incomplete`).
- **No new bookTicker HTTP on click.** The click calls `_assemble` →
  `_attach_opening_quotes`, which reads the same cache the scheduled tick filled
  (D7), so the projected symbol-snapshot row reuses the canonical row's quotes.

## Test Commands And Results

| Command | Exit | Result |
|---|---|---|
| `pytest backend/tests/test_book_ticker.py backend/tests/test_snapshot.py backend/tests/test_background_worker.py backend/tests/test_symbol_snapshot_endpoint.py backend/tests/test_negative_schema.py -q` | 0 | 142 passed in ~6.4s |
| `pytest backend/tests -q` | 0 | 375 passed in ~16.1s |
| `python3 -m py_compile backend/adapters/binance_public.py backend/domain/snapshot.py backend/services/snapshot_service.py` | 0 | compiled clean |
| `git diff --check` | 0 | no whitespace/conflict errors |

`60-test-output.txt` was not modified. The bookkeeper independently re-runs and
stores the formal test evidence.

Deterministic coverage confirmed (prompt "Deterministic Tests" list): raw JSON
number price rejected (no `str()` coercion); one success then monotonic `119s`
usable / `120s` stale without a manufactured fetch failure; forward-only /
reverse-only / all-four / zero-or-missing-leg / never-success truth table;
non-list / empty list / normalized empty map / second-endpoint failure advance no
timestamp; legacy no-seam stub, private-disabled, bStock alias, click no-extra-I/O;
schema legacy compatibility and nested unknown/number rejection.

## Task Boundary / ADR Deviations

None. The implementation follows `00-task.md`, the reconciled `10-design.md` /
`11-adr.md`, `12-development-breakdown.md`, and `14-design-review-reconciliation.md`
verbatim. No forbidden file was touched; no history 1500s refresh-ahead / cursor /
≤10-per-tick / `-0.00030000` threshold / coverage ledger / borrow-max cadence /
private transport TTL / signed GET / whitelist / price-map gating was changed; no
new config/env, scheduler abstraction, per-symbol HTTP, WebSocket, or execution
side effect was added; wire version and `/api/public-market/snapshot` route are
unchanged; `ui_flags` / `asset_tag` / `negative_funding_status` are untouched.

## Remaining Work / Findings

- None within Task A. Task B (frontend opening-quotes rendering, independent
  formatter, not reusing `formatFundingRate`) is out of scope and blocked on the
  committed/frozen Task A contract; not started.

## Git Status

On branch `stage/2026-07-bookticker-open-columns-v1` at HEAD `fea9fdc` (the stage
base SHA). **Not committed** (per the prompt, no commit / push / history change).
Working-tree changes are limited to the Task A allowed files above plus this
report. Pre-existing uncommitted design / Harness / API-evidence changes in the
work tree belong to the user/bookkeeper and were left untouched.

Diffstat (allowed files, tracked):

```text
 backend/adapters/binance_public.py             |  60 +++++++++++
 backend/domain/snapshot.py                     | 111 ++++++++++++++++++-
 backend/services/snapshot_service.py           |  71 +++++++++++++
 backend/tests/test_background_worker.py        | 142 ++++++++++++++++++++++++-
 backend/tests/test_negative_schema.py          |  74 +++++++++++++
 backend/tests/test_symbol_snapshot_endpoint.py |  53 ++++++++-
 docs/api/public-market-contract.md             | 107 ++++++++++++++++++-
 docs/architecture/ARCHITECTURE.md              |   8 ++
 docs/development/DEVELOPMENT_GUIDE.md          |  10 ++
 schemas/api/public-market/snapshot.schema.json |  67 ++++++++++++
 10 files changed, 695 insertions(+), 8 deletions(-)
```

Untracked (allowed): `backend/tests/test_book_ticker.py` and this report
`20-implementation-task-a.md`.

---

当前 Session ID: aaba9bdc-5a62-4f9b-b820-d590c58c30a4
Session ID 来源: runtime_env (`CLAUDE_CODE_SESSION_ID`)
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-a.md
本地北京时间: 2026-07-15 18:04:47 CST
下一步模型: codex_bookkeeper
下一步任务: 核对 Task A diff/file boundary，独立重跑测试并创建 Task A evidence commit
