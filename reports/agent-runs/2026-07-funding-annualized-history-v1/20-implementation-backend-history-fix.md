# Task C Implementation Report — Selected-Symbol Settled-History Endpoint

Stage: `2026-07-funding-annualized-history-v1`
Branch: `stage/2026-07-funding-annualized-history-v1` (HEAD `5a5b9f6`; Task A/B
already committed; Task C changes are uncommitted — the bookkeeper owns commits).
Executor: Claude-GLM (`glm-5.2` via Claude Code).

## Summary

Task C adds the same-origin, public read-only endpoint
`GET /api/public-market/funding-history?symbol=<eligible-USDT-perpetual>`. It
resolves the symbol against the current snapshot's eligible rows, derives the
settled-window end from that snapshot's `data_time`, and reuses the existing
per-symbol 30-minute successful-result cache plus the Task A settled-history
helpers. The browser never calls Binance; no private channel, credential,
database, full-universe prefetch, or wire-version change is introduced. Backend
tests, schema validation, `git diff --check`, an offline HTTP smoke, and a
no-credential live-public smoke all pass.

## Endpoint Contract

Route (added to the stdlib server, same-origin static host):

```text
GET /api/public-market/funding-history?symbol=<symbol>
```

Success payload validates against the new
`schemas/api/public-market/funding-history.schema.json`
(`public-market-funding-history/v1`):

```json
{
  "schema_version": "public-market-funding-history/v1",
  "symbol": "SKLUSDT",
  "data_time": "2026-07-10T12:34:56Z",
  "history_status": "available",
  "funding_history": [
    {"funding_time": 1783689600000, "funding_rate": "-0.00010000"}
  ],
  "annualized_funding_7d": "-1.64235296",
  "annualized_funding_30d": "-0.30751323"
}
```

`funding_history` is newest-first and windowed to the inclusive 30 days ending
at the snapshot `data_time`. `annualized_funding_7d`/`annualized_funding_30d`
reuse the Task A settled-only Decimal calendar-window formula (`sum * 365/N`),
and are `null` for an empty window. The endpoint does **not** return the
current-period 24h estimate — the selected snapshot row stays authoritative for
that.

Error surface (JSON `{"error": ...}`):

| HTTP | `error` | Meaning |
| --- | --- | --- |
| 400 | `invalid_symbol` | `symbol` missing or malformed. |
| 404 | `symbol_not_found` | Well-formed symbol is not an eligible current snapshot row. |
| 502 | `funding_history_unavailable` | Snapshot unavailable, or the public upstream settled-history call failed. Failure is NOT cached. |

A successful empty window is **HTTP 200** with `history_status: "empty"` and IS
cached (distinct from an upstream 502 failure).

## Design Decisions

- **Symbol validation first.** `symbol` must match `^[A-Z0-9]{1,40}$` (Binance
  USDⓈ-M perpetual style, e.g. `BTCUSDT`, `1000SATSUSDT`). Missing/empty/
  lower-case/space-injected/overlong values return 400 *before* the snapshot is
  consulted (no upstream call). The server's `parse_qs` drops blank values, so
  `?symbol=` is treated as missing → 400.
- **Eligibility = current snapshot rows.** A well-formed symbol not present in
  `snapshot["rows"]` returns 404 with no upstream call. This covers non-existent
  symbols and symbols filtered out of the snapshot (non-TRADING, non-USDT,
  non-perpetual).
- **Window end reused from the snapshot.** `build_snapshot` now records
  `self._data_time_ms` (the premium-index time it already computes); the endpoint
  passes it to `_fetch_history_for`. The 60-second snapshot cache and this value
  stay in lockstep: a cache hit keeps the last-build boundary, which matches the
  cached snapshot the endpoint validated the symbol against. No ISO→ms parsing
  and no float touch the time path.
- **Cache reuse, not a new cache.** The endpoint calls the existing
  `_fetch_history_for(symbol, t_end_ms)`, so it shares the Task A per-symbol
  1,800-second successful-result cache. A successful top-N preload and a later
  endpoint request for the same symbol hit the same entry; the 60-second
  whole-snapshot cache is untouched.
- **No full-universe prefetch.** A non-top-N eligible symbol (not preloaded by
  `build_snapshot`) is fetched on demand through the same bounded cache —
  asserted by `test_non_topn_symbol_served_on_demand`. The endpoint never polls
  the full universe.
- **Failure vs empty is explicit.** `_fetch_history_for` returns `None` on a
  transport/HTTP/parse failure (not cached, retries next call) → 502; it returns
  `[]` on a successful empty window (cached) → 200 `empty`. A snapshot that
  itself cannot be built/fetched is also mapped to 502 (the endpoint cannot
  resolve eligibility or a window boundary).
- **No 24h on this endpoint.** The payload omits `annualized_funding_24h`; the
  drawer's selected row carries the current-period estimate. Asserted in tests.
- **Pure helper extraction (the only `domain` change).** `settle_history_view(
  raw_entries, t_end_ms)` composes the existing `_build_funding_history` +
  `compute_annualized_funding_window` and adds the `available`/`empty` status
  split — no new arithmetic, no duplication.

## Changed Files (all within the Task C boundary)

- `backend/app/server.py` — `do_GET` routes
  `/api/public-market/funding-history` to a new `_handle_funding_history`; reads
  only the `symbol` query param via `parse_qs`; writes the `(status, payload)`
  from the service as JSON (with `Cache-Control: no-store` on 200). The snapshot
  route, static host, and all existing semantics are unchanged.
- `backend/services/snapshot_service.py` — `get_funding_history(symbol) ->
  (status, payload)`; `_load_funding_history_schema()` (lazy, resolves the schema
  beside `config.schema_path`, no Config change); `build_snapshot` records
  `self._data_time_ms`; `__init__` initializes `_data_time_ms`/`_funding_history_schema`;
  module-level `_SYMBOL_RE` and `FUNDING_HISTORY_SCHEMA_VERSION`.
- `backend/domain/snapshot.py` — new pure `settle_history_view` (extract/reuse of
  existing settled-history logic; the only domain edit).
- `schemas/api/public-market/funding-history.schema.json` (new) — the v1 success
  contract (self-contained `$defs.decimal_string`).
- `backend/tests/test_funding_history_endpoint.py` (new) — 17 tests.
- `backend/tests/test_funding_history.py` — one `settle_history_view` test +
  import (additive).
- `backend/tests/smoke_server.py` — exercises the endpoint (200/schema, 400, 404)
  in the offline HTTP smoke.

`backend/config.py` is **not** modified: the funding-history schema path is
derived from `config.schema_path.parent`, so no new Config field is needed.

## Frozen Behaviors (Task C must not disturb)

- The snapshot endpoint, its top-N preload, its 60-second cache,
  `public-market-snapshot/v1`, sort behavior, private-channel behavior, and all
  existing public data semantics are untouched. The new route is the only
  `do_GET` addition; no existing route or handler changed.

## Endpoint Status Matrix (asserted by `test_funding_history_endpoint.py`)

| Case | Result |
| --- | --- |
| missing / empty / lower-case / special-char / overlong symbol | 400 `invalid_symbol`, no upstream call |
| well-formed symbol not in snapshot | 404 `symbol_not_found`, no upstream call |
| eligible symbol, records present | 200 `available`, schema-valid, newest-first, no 24h |
| eligible symbol, successful empty window | 200 `empty`, null 7D/30D, schema-valid |
| upstream `URLError` | 502 `funding_history_unavailable`; failure not cached (retries) |
| snapshot itself unavailable | 502 `funding_history_unavailable` |
| repeat success (incl. empty) within 1800s TTL | one upstream `fundingRate` call |
| non-top-N eligible symbol | served on demand via the bounded cache |
| window end / request params | `start=t_end-30d`, `end=t_end`, `limit=1000`, from snapshot `data_time` |

## Test Output

```
python3 -m pytest backend/tests -q                               -> 244 passed in 5.90s
python3 -m json.tool schemas/api/public-market/funding-history.schema.json >/dev/null -> OK
git diff --check                                                 -> clean
```

`test_funding_history_endpoint.py` (17 tests) covers: invalid-symbol parametrized
400; 404 unknown symbol; 200 available (schema-valid, newest-first, no 24h);
200 empty (null annualization); 502 upstream failure + not-cached retry; 502
snapshot-unavailable; success and empty-success cache reuse; `data_time` sourced
from the snapshot; exact request window/limit; and non-top-N on-demand serving.
`test_funding_history.py` gains one `settle_history_view` available/empty test.

## Smoke Results

Offline HTTP smoke (idle port 8799, `Config(offline=True)`, exercises the real
stdlib server + service + schema end-to-end):

```
GET /api/public-market/funding-history?symbol=ZKPUSDT -> 200, schema-valid,
  history_status=empty, rows=0, data_time=2026-07-03T05:11:29Z
GET /api/public-market/funding-history (no symbol)   -> 400
GET /api/public-market/funding-history?symbol=NOPEUSDT -> 404 {"error": "symbol_not_found"}
OFFLINE SMOKE OK
```

(`smoke_server.py` itself hard-codes port 8787, which was occupied in this
environment; the equivalent offline smoke above uses an idle port to exercise the
identical server/service/schema path. The script's added assertions are
unchanged.)

No-credential live-public smoke (idle port 8801, `ENV_FILE=/dev/null
APP_OFFLINE=false BINANCE_PRIVATE_CHANNEL_ENABLED=false`):

```
eligible symbol: SKLUSDT
funding-history HTTP status: 200
schema_version: public-market-funding-history/v1
history_status: available  rows: 179
annualized_funding_7d: -1.64235296
annualized_funding_30d: -0.30751323
credential leak terms in body: []
LIVE SMOKE OK
```

The live response carried 179 authentic settled records (a 1h-cadence symbol) and
real negative annualization; the body contained none of `api_key`, `apisecret`,
`binance_api`, `x-mbx-apikey`, `cookie`, etc., and no 24h estimate. (A benign
`BrokenPipeError` appeared in the server log on the `_handle_snapshot` path — the
smoke client's readiness-poll disconnected mid-response before the final
successful snapshot/endpoint round-trip; it is not an endpoint defect.)

## Blockers / Deviations

- No outstanding blockers. All required commands pass; both smokes pass.
- Minor environment note only: the default smoke port 8787 was occupied, so the
  offline smoke was run on an idle port with identical coverage (no code change).

## Next

Hand to the bookkeeper to commit Task C on the stage branch, record its fixed
range in `status.json`, and freeze the `public-market-funding-history/v1`
endpoint + schema for Task D (Kimi frontend drawer history loading). Task D must
not begin until Task C's committed endpoint contract is confirmed; it must call
this same-origin endpoint, not a browser fetch to Binance.

```text
本地北京时间: 2026-07-10 20:42:48 CST
下一步模型: bookkeeper
下一步任务: 在 stage 分支提交 Task C 并固定 funding-history/v1 端点契约与 schema，供 Task D (Kimi 前端) 消费。
```
