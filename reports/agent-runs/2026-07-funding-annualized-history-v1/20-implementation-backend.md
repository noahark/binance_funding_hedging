# Task A Implementation Report — Backend Contract And Settled-History Enrichment

Stage: `2026-07-funding-annualized-history-v1`
Branch: `stage/2026-07-funding-annualized-history-v1` (HEAD `0206f8b`, uncommitted
working-tree changes — the bookkeeper owns commits).
Executor: Claude-GLM (`glm-5.2` via Claude Code).

## Summary

Task A delivers the three additive annualized funding fields, the top-N bounded
deep settled-history enrichment, a dedicated per-symbol cache with per-symbol
failure degradation, and an authentic multi-week public raw sample that grounds
the contract change. Backend tests, schema validation, and `git diff --check`
pass.

## Contract Decision (Operator Direction — Read Before Review)

An earlier package revision specified the three fields as **required** on the
row schema. During implementation this collided with the existing invariant
locked by
`backend/tests/test_phase2_borrow_sort.py::test_frozen_v01_normalized_validates_under_v02_schema`
("the v0.1 frozen snapshot stays valid under the new schema because new fields
are all optional"). The operator directed (2026-07-10):

> Keep `public-market-snapshot/v1` additive / backward-compatible. Do **not**
> add the three annualized fields to the row schema `required`; keep them as
> decimal-or-null properties that may be absent. Do not modify the frozen v0.1
> sample or the `test_phase2_borrow_sort` compatibility assertion. The current
> backend snapshot must still always emit the three fields; assert service-output
> presence and computation semantics in `test_funding_history.py`. Revert any
> `null` backfills made to `test_negative_schema.py` / `test_private_account_v1.py`
> solely for `required`. Rationale: adding `required` without a wire-version bump
> breaks the existing v1 additive promise; constrain new snapshots with a
> service-output guarantee, not by rejecting old snapshots at the schema layer.

Implemented accordingly; the bookkeeper package correction records the same
decision. The three fields are **additive optional properties**
(`anyOf decimal_string | null`), **not** in `required`. Frozen v0.1 snapshots
(which lack them) stay valid; the live `build_rows` / `SnapshotService` pipeline
**always** emits all three keys on every current-snapshot row (asserted in
`test_funding_history.py`). This is a deliberate, operator-approved deviation
from the literal task text; it preserves the unchanged wire version and the v1
additive contract.

## Changed Files (all within the Task A boundary)

Source:

- `backend/adapters/binance_public.py` — `fetch_funding_rate` now takes
  `start_time_ms` / `end_time_ms` / `limit=1000` keyword arguments and builds the
  query via `urllib.parse.urlencode` (safe construction; the symbol is never
  string-interpolated raw). Raises on failure; the service owns degradation.
- `backend/config.py` — new `funding_history_cache_ttl_seconds` (default 1800),
  env `APP_FUNDING_HISTORY_CACHE_TTL_SECONDS` (alias
  `FUNDING_HEDGING_FUNDING_HISTORY_CACHE_TTL_SECONDS`), invalid integer rejected.
- `backend/domain/snapshot.py` — pure helpers
  `compute_annualized_funding_24h` (`daily_funding_rate * 365`, estimate-only)
  and `compute_annualized_funding_window` (settled-window sum * `365/N`,
  calendar denominator, empty window -> `null`); `_build_funding_history`
  (normalize raw entries to `{funding_time, funding_rate}`, filter to the
  inclusive 30-day window, serialize newest first); `build_rows` gained a
  `t_end_ms` keyword and emits the three annualized fields on every row.
- `backend/services/snapshot_service.py` — dedicated per-symbol
  successful-result cache (`_funding_history_cache`, TTL
  `Config.funding_history_cache_ttl_seconds`); live deep history restricted to
  `top_symbols_by_abs_rate(..., Config.top_n)`; `_fetch_history_for` requests
  `startTime=t_end-30d`, `endTime=t_end`, `limit=1000`, returns `None` (NOT
  cached) on failure so it retries next rebuild; per-symbol failure appends
  `funding_history_unavailable:<symbol>`, leaves that row empty/null, and never
  fails the snapshot. The 60-second whole-snapshot cache is untouched.
- `schemas/api/public-market/snapshot.schema.json` — three additive optional
  `decimal_string | null` properties added to `row.properties` (NOT to
  `required`). No `schema_version` / route / sort change.

Tests:

- `backend/tests/test_funding_history.py` (new) — 31 tests.
- `backend/tests/fixtures/funding-history/**` (new) — deterministic vectors:
  `seven-day-flat`, `boundaries`, `mixed-interval`, `negative-rates`,
  `out-of-window`.
- `backend/tests/test_config.py` — TTL default(1800)/override/invalid-reject.

Compatibility files: `backend/tests/test_negative_schema.py` and
`backend/tests/test_private_account_v1.py` have **zero net change**. They were
temporarily backfilled with three `null` fields while the schema was `required`,
and were reverted per the operator direction once the fields became optional
(verified absent from `git status`).

`backend/tests/test_snapshot.py` needed no change — `build_rows` already emits
the three fields, and they are optional.

## Frozen Behaviors (mapped to the task's five freeze points)

1. Decimal-only value paths, eight-place fixed-point strings. 24h is
   `daily_funding_rate * 365` and stays estimate-derived. — `compute_annualized_funding_24h`
   / `_quantize_rate`; no float on any value path.
2. 7D/30D use only settled `funding_history` entries in inclusive calendar windows
   ending at the snapshot premium-index time; sum the period rates and multiply by
   `365/N`; no average-interval / observed-span denominators / `lastFundingRate`;
   empty window -> `null`. — `compute_annualized_funding_window` + `_build_funding_history`.
3. Top-N only; `/fapi/v1/fundingRate` with `symbol`, `startTime=t_end-30d`,
   `endTime=t_end`, `limit=1000`; dedicated per-symbol successful-result cache via
   `Config.funding_history_cache_ttl_seconds` (default 1800, env
   `APP_FUNDING_HISTORY_CACHE_TTL_SECONDS`); the 60s whole-snapshot cache unchanged;
   history newest first. — `_fetch_history_for` + service top-N loop.
4. Individual history failure -> empty history, null 7D/30D, warning
   `funding_history_unavailable:<symbol>`, snapshot still succeeds; failed requests
   not cached. — service degrade path (asserted by two tests).
5. Authentic multi-week public raw response captured (see Raw Evidence); no
   synthetic fixture is claimed as raw evidence. — capture below + replay test.

## Test Output Summary

```
python3 -m pytest backend/tests -q        -> 226 passed in 5.12s
python3 -m json.tool schemas/api/public-market/snapshot.schema.json >/dev/null -> OK
git diff --check                          -> clean
```

`test_funding_history.py` coverage: 24h vectors (incl. null/empty/non-numeric/
neg-zero/no-scientific); 7D/30D vectors (flat, inclusive boundaries + 1ms-edge
exclusions, mixed 1h/4h spacing sum, negative sign preserved, empty window ->
null, `t_end` None -> null, unparseable-entry skip); `build_rows` field emission
+ newest-first + 30-day windowing + eight-place serialization + daily-null ->
24h-null + the always-present service-output guarantee; service exact request
params, top-N cap, cache hit within TTL, per-symbol failure degradation (no 503)
and failure-not-cached retry; additive schema (null accepted; absence still
valid); and replay of the authentic captured sample end-to-end.

`test_config.py`: TTL default 1800, env override (incl. legacy alias), invalid
integer rejection.

## Raw Evidence

```
reports/api-samples/2026-07-funding-annualized-history-v1/20260710T061419Z/
├── capture.md
└── raw/
    └── fapi-v1-fundingRate-BTCUSDT-limit1000.json
```

Captured live (no API key) on 2026-07-10 with the exact deep-history request the
service sends. **90** settled events, **29.67-day** span (multi-week; covers both
7D and 30D windows). First `fundingTime=1781078400011` (`-0.00003385`), last
`fundingTime=1783641600000` (`0.00009058`). Replay-validated by
`test_funding_history.py::test_real_btcusdt_sample_processes_through_pipeline`.

## Blockers / Deviations

- **Deviation (operator-approved, not a blocker):** three fields are additive
  optional on the schema, not `required`, per operator direction to preserve the
  v1 additive/backward-compatible contract. The live service-output guarantee
  (always present on current snapshots) replaces schema enforcement. Frozen v0.1
  snapshots remain valid.
- No outstanding blockers. All specified commands pass.

## Next

Hand to the bookkeeper to commit Task A on the stage branch, freeze the wire
field names/schema shape for Task B (Kimi frontend), and prepare the review-1
packet. Task B must not begin until Task A's committed contract is confirmed.

```text
本地北京时间: 2026-07-10 14:51:54 CST
下一步模型: bookkeeper
下一步任务: 提交 Task A 于 stage 分支并固定三字段 wire/schema 契约，供 Task B (Kimi 前端) 消费。
```
