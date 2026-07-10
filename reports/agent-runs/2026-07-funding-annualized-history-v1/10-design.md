# Stage Design: Funding Annualized History And Drawer

## Summary

The backend will enrich only the current top-N funding rows with a bounded
30-day settled-history window from `GET /fapi/v1/fundingRate`. It computes
three additive snapshot fields using `Decimal`, validates them through the
existing snapshot schema, and degrades each failed history fetch independently.
The frontend will render those values in the existing table and offer one
right-side drawer for the selected symbol's settled records.

Implementation is serial:

1. Claude-GLM lands and tests the backend/schema contract plus raw evidence.
2. Kimi consumes that committed contract for the table and drawer.

## Assumptions

- `premiumIndex.lastFundingRate` remains an estimate for the current period;
  `/fapi/v1/fundingRate` remains the sole source of settled records.
- `premium_index[*].time` is the snapshot time boundary supplied to the live
  history request and annualization windows. Tests must provide explicit times.
- The existing `Config.top_n` limit remains the per-refresh enrichment set.
- The existing 60-second snapshot cache stays unchanged. Deep settled history
  gets a separate 30-minute cache because settled records are immutable.

## Design Decisions

### D1. Additive wire contract, no version or sort change

Each `rows[]` object will require these additive fields in the snapshot schema:

| Field | Type | Meaning |
| --- | --- | --- |
| `annualized_funding_24h` | decimal string or `null` | Estimated daily rate times 365. |
| `annualized_funding_7d` | decimal string or `null` | Settled 7-day calendar-window sum times `365 / 7`. |
| `annualized_funding_30d` | decimal string or `null` | Settled 30-day calendar-window sum times `365 / 30`. |

No settlement-count fields ship in v1. The three fields are additive optional
schema properties so frozen v0.1 snapshots remain valid under the unchanged
wire version. The current `SnapshotService` output is nevertheless required to
supply all three keys as decimal strings or `null`; tests lock that runtime
guarantee. `schema_version`, route, `sort_basis`, `daily_funding_rate`, and
`net_daily_yield` retain their current semantics.

### D2. Calendar-window Decimal formulas

For `t_end = snapshot premium-index time in ms` and `N in {7, 30}`:

```text
t_start = t_end - N * 86_400_000
S_N = settled funding_history entries where t_start <= funding_time <= t_end
annualized_funding_Nd = quantize_8(sum(Decimal(funding_rate) for S_N) * 365 / N)
annualized_funding_24h = quantize_8(Decimal(daily_funding_rate) * 365)
```

`quantize_8` uses the repository's existing fixed-point Decimal discipline and
serializes ordinary eight-place decimal strings, never scientific notation.
For 7D/30D, an empty `S_N` yields `null`; there is no minimum-count floor and
no re-denomination by observed history span. This intentionally treats missing
calendar time as zero rather than inflating a new listing's rate. The formula
does not use `funding_interval_hours` and does not mix in the current estimate.

### D3. Settled-history request, cache, and degradation policy

For each selected top-N symbol, Task A changes the adapter request to:

```text
GET /fapi/v1/fundingRate?symbol=<symbol>&startTime=<t_end-30d>&endTime=<t_end>&limit=1000
```

The adapter must construct query parameters safely and the service must keep a
dedicated per-symbol successful-result cache through
`Config.funding_history_cache_ttl_seconds`, defaulting to 1,800 seconds and
configured through `APP_FUNDING_HISTORY_CACHE_TTL_SECONDS`. Cached records are
filtered to the inclusive 30-day window and serialized newest first. The
service must not make deep-history requests for non-top-N rows.

A transport, HTTP, or parse failure for one symbol adds a deterministic warning
`funding_history_unavailable:<symbol>`, leaves that row's history empty, and
sets its 7D/30D fields to `null`; it must not fail the public snapshot. Failed
requests are not cached. The main snapshot cache remains the only 60-second
cache and is not replaced by a full-universe history cache.

### D4. Drawer interaction and display semantics

The table adds the three columns immediately after the current daily-rate
column. `24h` text and tooltip explicitly say it is estimate-derived; `7D` and
`30D` say they are settled-history annualizations. The existing funding sign
and color helpers are reused, and a null field renders `-`.

Each data row is selectable by click and keyboard (`Enter`/`Space`). One drawer
slides from the right and contains:

- a fixed header with symbol and the exact same formatted three values;
- an accessible close control;
- newest-first settlement time in `Asia/Shanghai` and funding rate rows;
- an empty state for both unavailable enrichment and no settled records.

Backdrop click, close control, and Escape close the drawer. Refresh preserves
the selected symbol and replaces its displayed data when the symbol remains;
it closes the drawer when that symbol disappears. The frontend never fetches
Binance directly.

### D5. Evidence and canonical-doc boundary

Task A captures at least one authentic multi-week public raw response under
`reports/api-samples/2026-07-funding-annualized-history-v1/`. It also adds
deterministic synthetic/mixed-interval vectors to tests as needed. The raw
sample is mandatory evidence for this frozen-contract amendment.

`docs/api/public-market-contract.md` remains unchanged during implementation:
its canonical promotion is a post-review, user-approved activity. The stage
handoff must call out the affected canonical path and the raw evidence used for
that future promotion.

## Task Breakdown

- Task A: Claude-GLM owns adapter request shape, history cache, Decimal
  calculations, snapshot/schema fields, samples, and backend tests.
- Task B: Kimi owns table columns, selection state, drawer markup/CSS/behavior,
  fixture updates, and frontend self-checks after Task A freezes the wire.
- Bookkeeper: commits each bounded task, anchors review evidence, and prepares
  cross-review packets. It does not write delivery code.

## Test Strategy

- Unit: `backend/tests/test_funding_history.py` with deterministic fixtures
  under `backend/tests/fixtures/funding-history/`: 24h, 7D, and 30D vectors;
  negative values; empty windows; inclusive boundaries; mixed 1h/4h intervals;
  fixed-point formatting; newest-first ordering; optional-schema acceptance for
  legacy rows; and always-present fields on current service output.
- Service/adapter: exact query parameters, top-N bound, deep-history TTL,
  per-symbol failure degradation, and no regression to existing snapshot cache.
- Configuration: `backend/tests/test_config.py` covers the new TTL default,
  environment override, and invalid integer rejection.
- Contract: JSON Schema validation for every produced row and offline build.
- Compatibility: `backend/tests/test_phase2_borrow_sort.py` continues to prove
  that the frozen v0.1 snapshot remains schema-valid; no frozen sample or
  legacy hand-authored row changes are needed.
- Frontend: fixture/self-check coverage for new required fields, column labels,
  null rendering, drawer open/close/Escape, list ordering, and refresh state.
- Final commands: `python3 -m pytest backend/tests -q`,
  `node frontend/self-check.js`, and `git diff --check`.

## Risks

- A symbol can have fewer than 30 calendar days of settlements. Calendar
  denominators prevent inflated annualization, but the UI must not present its
  settled result as the current-period estimate.
- The shared public endpoint has a 500/5min/IP budget. Top-N selection and the
  dedicated cache are mandatory, not optional performance improvements.
- A 1h instrument can produce far more records than an 8h instrument. The
  stage accepts the live-evidence constraint that current target windows fit
  `limit=1000`; pagination is an explicit follow-up if that ceases to be true.
- Schema optionality preserves legacy replay, while frontend work still relies
  on the current-service guarantee that every new output row contains the three
  fields.

## Raw Artifact Requirements For Review

- `00-intake.md`, `00-task.md`, `10-design.md`, `11-adr.md`, and
  `12-development-breakdown.md`
- task-specific implementation reports and test output
- raw public deep-history sample under `reports/api-samples/2026-07-funding-annualized-history-v1/`
- committed diff anchored by `status.json.base_sha..head_sha`
- relevant backend, schema, frontend, and test files

```text
本地北京时间: 2026-07-10 13:13:36 CST
下一步模型: human
下一步任务: 审核 D1-D5，特别是 Calendar denominator、30 分钟缓存和 canonical docs 延后晋升。
```
