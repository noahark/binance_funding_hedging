# 20 — Implementation (backend, Task A)

Stage: `2026-07-public-market-impl-v1`
Owner: Claude-GLM (`claude_glm`, model `glm-5.2[1m]`), role `senior_developer`.
Scope: `backend/**` plus this file. Boundary: strictly `backend/**` only; no
touch to `frontend/**`, schemas, the contract doc, or raw samples.

This is the controller (Claude-GLM) implementing Task A itself. The same model
as the stage controller also authored backend code; that is recorded in
`status.json` under `evidence_policy.controller_and_backend_implementer_same_model`
and disclosed for review-2 routing.

## File manifest (committed in H_A)

```
backend/__init__.py
backend/config.py
backend/adapters/__init__.py
backend/adapters/binance_public.py
backend/app/__init__.py
backend/app/server.py
backend/domain/__init__.py
backend/domain/classify.py
backend/domain/normalize.py
backend/domain/snapshot.py
backend/services/__init__.py
backend/services/snapshot_service.py
backend/tests/__init__.py
backend/tests/conftest.py
backend/tests/smoke_server.py
backend/tests/test_classify.py
backend/tests/test_negative_schema.py
backend/tests/test_normalize.py
backend/tests/test_snapshot.py
```

19 source files. `__pycache__/` is gitignored at the repo root and is not
committed. (A historical `c53664e Implement public-market discovery` was reset
by `11d5504 Reset public market stage to contract-first`; its compiled `.pyc`
remnants linger on disk under `backend/**/__pycache__/` but are gitignored,
reference deleted sources, and are neither committed nor used. This Task A
implementation is independent of that reset code — see "Independence" below.)

## Architecture

Layered, single direction of dependency (`adapters → domain → services → app`):

- `adapters/binance_public.py` — `BinancePublicClient`. Public, read-only
  endpoints only. `fetch_raw()` returns the four raw payloads
  (futures exchangeInfo, premiumIndex, spot exchangeInfo, and — in live mode —
  funding history for selected symbols). Offline mode reads the frozen
  raw-sample directory. Maintains `request_log` (per-endpoint counts).
- `domain/normalize.py` — pure helpers: `filter_of`, `asset_tag_for`,
  `iso_from_ms` (integer-division ms→seconds, no float).
- `domain/classify.py` — pure functions: `classify_route`,
  `negative_funding_status` (explicit ordered priority).
- `domain/snapshot.py` — `top_symbols_by_abs_rate`, `build_rows`,
  `assemble_snapshot`. `SCHEMA_VERSION` and `CONTRACT_WARNINGS` live here.
- `services/snapshot_service.py` — `SnapshotService`: pipeline orchestration +
  in-memory TTL cache + jsonschema validation (raises → caller maps to 503).
- `app/server.py` — stdlib `http.server.ThreadingHTTPServer` handler:
  `/api/public-market/snapshot` (JSON, schema-validated; 503 on validation
  failure) and same-origin static hosting of `frontend/` at `/`.

No FastAPI/uvicorn (ADR-1). Dependencies: standard library + `jsonschema`.

## Data flow

`fetch_raw` → filter `status=="TRADING"` and `contractType in {PERPETUAL,
TRADIFI_PERPETUAL}` → `build_rows` (normalize + classify + funding history) →
`assemble_snapshot` (summary aggregated FROM rows) → jsonschema-validate →
serve (or 503 on validation failure). Validation gate is on every served
snapshot, so an invalid snapshot is never returned.

## Behavior-rule implementation (checkpoint-by-checkpoint vs 00-task.md)

- **Eligible filter**: `SnapshotService.build_snapshot` keeps only
  `status=="TRADING"` and `contractType in ELIGIBLE_CONTRACT_TYPES`
  (`PERPETUAL`, `TRADIFI_PERPETUAL`). Covered by
  `test_no_non_trading_or_non_perpetual_leakage`.
- **asset_tag**: `asset_tag_for(contract_type)` → TRADIFI_PERPETUAL=BSTOCK,
  PERPETUAL=CRYPTO. Independent of route_class. MSTR/TSLA confirmed
  `BSTOCK`+`PERP_ONLY_EXCLUDED` in `test_classification_matches_frozen_six`.
- **route_class**: `classify_route(contract_type, spot_symbol,
  spot_margin_allowed)` — spot+margin → MARGIN_SPOT_CANDIDATE; spot no-margin
  → SPOT_ONLY_CANDIDATE; no spot → PERP_ONLY_EXCLUDED. `margin_public.source`
  is always `"unverified"`.
- **negative_funding_status priority**: explicit ordered sequence in
  `negative_funding_status` — PERP_ONLY → DISABLED_PERP_ONLY, then BSTOCK →
  DISABLED_BSTOCK, then SPOT_ONLY → DISABLED_SPOT_ONLY, then default →
  PRIVATE_BORROW_VALIDATION_REQUIRED. Order is not interchangeable. MSTR/TSLA
  are PERP_ONLY+BSTOCK → resolve to DISABLED_PERP_ONLY (priority 1 wins over 2).
- **Decimal discipline**: ranking uses `Decimal`; every decimal field is
  serialized as a string straight from raw JSON. `float()` audit: none in
  backend source (see Section 2 of `60-test-output.txt`).
- **funding_history**: top-N by `|last_funding_rate|` bounds LIVE
  `/fapi/v1/fundingRate` volume. Offline uses every frozen fixture already on
  disk (no HTTP). See "funding_history / top-N" below.
- **summary == aggregation over rows**: `_counts` aggregates FROM rows;
  `test_summary_aggregates_from_rows` asserts equality with a fresh
  `collections.Counter` over rows.
- **Cache TTL**: in-memory `(monotonic, snapshot)` cache, default 60s.
- **Offline**: `Config(offline=True)` reads the frozen raw-sample directory;
  tests/CI are always offline.
- **Three contract warnings**: `CONTRACT_WARNINGS` carried verbatim into every
  snapshot; `test_three_contract_warnings_preserved` checks the three markers.

## Decimal discipline

`_abs_rate` uses `Decimal(str(rate_str))`. `iso_from_ms` uses `int(ms)//1000`.
`build_rows` copies raw JSON strings directly into decimal fields. No `float()`
anywhere in backend source (audit in `60-test-output.txt` Section 2). Negative
schema tests `test_reject_float_mark_price` and `test_reject_float_funding_rate`
confirm the schema itself rejects floats.

## funding_history / top-N

- **Live**: `top_symbols_by_abs_rate(futures_symbols, premium_by_sym, top_n=20)`
  selects the 20 symbols with largest `|lastFundingRate|`; the service fetches
  `/fapi/v1/fundingRate?symbol=…` only for those symbols not already in the raw
  bundle. Other symbols get `funding_history: []`.
- **Offline**: every frozen funding fixture already on disk is used (no HTTP
  cost); only `BTCUSDT` has a frozen fixture (10 entries) in the current
  sample, asserted by `test_only_fixture_symbols_have_funding_history` and
  `test_btcusdt_top_symbol_has_funding_history`.
- **Request count (design, not measured this stage)**: per cache refresh,
  live mode issues 3 fixed calls (futures exchangeInfo, premiumIndex, spot
  exchangeInfo) + top-N(=20) fundingRate calls = **23 HTTP GETs**. Weight
  budget per Binance public docs: futures exchangeInfo≈1, premiumIndex≈1,
  each fundingRate≈1 (futures IP limit 2400 weight/min); spot exchangeInfo≈20
  (spot IP limit 6000 weight/min). At the default 60s TTL that is ≈23
  calls/min, i.e. well under 1% of either weight ceiling — ample headroom.
  These figures are derived from public docs and the top-N design; the live
  HTTP path itself is not exercised this stage (see "Known limitations").
  Default N=20 is design-confirmed (ADR-2) and is not changed.

## summary aggregation

`assemble_snapshot` builds `summary` via `_counts(rows, key)` for
`route_class`, `asset_tag`, `negative_funding_status`, plus `total_rows =
len(rows)`. Counts are computed FROM rows, never independently.
`test_summary_aggregates_from_rows` cross-checks against a fresh Counter.

## Offline mode

`Config.offline=True` + `offline_raw_dir` (defaults to the frozen raw-sample
directory, `FROZEN_SOURCE_SAMPLE_ID="20260703T051738Z"`,
`FROZEN_GENERATED_AT="2026-07-03T05:17:38Z"`). `BinancePublicClient.fetch_raw`
parses the frozen files; funding history is read via the funding-rate fixture
regex. `generated_at`/`source_sample_id` in offline mode are pinned to the
frozen values so output is reproducible. `test_get_snapshot_is_schema_valid_and_cached`
asserts the offline service makes zero HTTP requests (`request_log()=={}`).

## Server & same-origin hosting

`app/server.py` exposes:
- `GET /api/public-market/snapshot` → 200 JSON (schema-validated) or 503 on
  validation failure.
- `GET /` and static → serves `frontend/index.html` and `frontend/**`
  same-origin, and `/fixture/public-market-snapshot.json` for offline UI.
- `build_server(config, service)` and `run(config=None)` for reuse in tests.

The production page fetches `/api/public-market/snapshot` same-origin (no
hardcoded external host); fixtures are for offline/test only.

## Test evidence

See `60-test-output.txt`:
- **Section 1 — pytest**: 39 passed, offline on frozen fixtures. Covers
  normalize/classify pure functions, schema positive + 11 negative mutations,
  service pipeline, summary aggregation, warnings preservation, decimal
  discipline, no leakage, top-N ranking/cap, and `get_snapshot` caching.
- **Section 2 — float() audit**: none in backend source.
- **Section 3 — server smoke**: real stdlib `http.server` over loopback,
  schema-validates `/api/public-market/snapshot`, serves `/`
  (index.html, 27982 bytes) and the fixture (8900 bytes).

## Contract-v2 alignment

- `schema_version = "public-market-snapshot/v1"` matches the frozen schema.
- The three contract warnings are preserved verbatim.
- Field names and shapes follow `schemas/api/public-market/snapshot.schema.json`
  (verified by jsonschema validation through `SnapshotService.get_snapshot`).
- Frozen-sample alignment: `data_time` matches the frozen normalized sample
  (`test_data_time_matches_frozen_sample`); the 6 curated symbols match
  expected `(route_class, asset_tag, negative_funding_status)` tuples
  (`test_classification_matches_frozen_six`).

## Independence from the reset c53664e implementation

Commit `c53664e Implement public-market discovery + candidate classification`
was reset by `11d5504 Reset public market stage to contract-first`. This Task A
implementation does not reuse that code: it is a fresh layered implementation
authored against the accepted `2026-07-public-market-contract-v2` contract and
the Fable5 detail breakdown. Stale `.pyc` of the deleted modules remain on
disk (gitignored) but are unused.

## Hard-constraints compliance

- No API key, signature, private account, user-data stream, order, borrow,
  repay, transfer, or websocket code. Adapters use public, unauthenticated GET
  endpoints only (`/fapi/v1/exchangeInfo`, `/fapi/v1/premiumIndex`,
  `/fapi/v1/fundingRate`, `/api/v3/exchangeInfo`).
- `schemas/**`, `docs/api/public-market-contract.md`, and raw samples are
  read-only and untouched.
- No planning-calculator UI, manual-open ticket, order button, account-status,
  or position-management logic.
- `funding_history` default top-N = 20 (unchanged).
- This report records what was implemented and does not declare final
  acceptance (controller never accepts; `can_accept_final: false`).

## Known limitations (stated honestly)

- **Live HTTP path not exercised this stage.** All tests and the smoke run are
  offline against frozen fixtures. Live request counts and rate-limit headroom
  above are design figures from public docs + the top-N design, not measured.
  The live branch is covered by the same code paths as offline (same
  `build_rows`/`assemble_snapshot`/validation), but the real
  `/fapi/v1/...` calls were not run here.
- **Server smoke is single-process.** The Harness sandbox blocks loopback TCP
  between separate processes, so `smoke_server.py` runs the real
  `http.server` in a background thread and connects via `urllib` from the same
  process (sandbox network disabled, local self-connect only). This exercises
  the actual handler and socket, just not cross-process. The smoke is committed
  and reproducible.

## Acceptance criteria self-check (Task A)

- offline tests pass — **yes**, 39 passed.
- served offline snapshot validates against the frozen schema with 0 errors —
  **yes**, `test_get_snapshot_is_schema_valid_and_cached` + smoke Section 3.
- warnings preserved — **yes**, 3 warnings, markers asserted.
- no `float()` on decimal paths — **yes**, audit clean + negative schema tests.
- `summary` matches `rows` aggregation — **yes**, dedicated test.

Task A is implementation-complete pending task-level review-1 (routed to Kimi
per `status.json`). Task-level `diff_fingerprint` is recorded in `status.json`
under `tasks.A` after the H_A commit.
