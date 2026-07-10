# Review-Feedback Fix: On-Demand History And Drawer Refinement

## Status

Planned package only. No Task C or Task D code has been dispatched, changed, or
committed. This amendment is inside the active funding-history stage and must
complete before formal review.

## User Findings And Decisions

| Finding | Cause | Fixed decision |
| --- | --- | --- |
| Drawer history appears absent for selected TST/RE rows | Live snapshot preloads only the top 20 symbols by `abs(lastFundingRate)`; these rows were not queried | Add a selected-symbol same-origin backend history endpoint with existing cache reuse. |
| Empty Drawer copy is ambiguous | The UI treats unrequested, true-empty, and fetch-failed histories as the same empty array | Display loading, true empty, and retryable upstream failure as different states. |
| Route column and negative-status column look redundant | One is structural classification; the other is the operational negative-funding state derived partly from it | Remove only the default route-class table column; retain API field and filter. |
| Drawer is too narrow for three annualized cards | Desktop width is 420px | Set desktop width to 620px, full width on narrower viewports, and prohibit card-label wrapping. |

## Contract

### Existing Snapshot Contract

`GET /api/public-market/snapshot` remains unchanged. It may continue to contain
preloaded settled history for top-N rows. No current snapshot field changes,
wire-version bump, sort change, private-channel behavior change, or full-market
history polling are allowed.

### New Same-Origin History Contract

```text
GET /api/public-market/funding-history?symbol=<symbol>
```

The accepted success payload is:

```json
{
  "schema_version": "public-market-funding-history/v1",
  "symbol": "TSTUSDT",
  "data_time": "2026-07-10T12:00:00Z",
  "history_status": "available",
  "funding_history": [
    {"funding_time": 1783689600000, "funding_rate": "-0.00010000"}
  ],
  "annualized_funding_7d": "-0.00521429",
  "annualized_funding_30d": "-0.00121667"
}
```

`history_status` is `available` or `empty`. It is `empty` only when Binance
successfully returned no in-window settled records. `funding_history` is always
newest first. The 7D/30D values use the existing settled-only Decimal calendar
formula; they are `null` for an empty window. The endpoint does not return or
recompute the current-period 24h estimate.

Error responses are JSON with an `error` field:

| HTTP | Error | Meaning |
| --- | --- | --- |
| 400 | `invalid_symbol` | Missing or malformed query parameter. |
| 404 | `symbol_not_found` | Well-formed symbol is not an eligible current snapshot row. |
| 502 | `funding_history_unavailable` | Public upstream retrieval failed; frontend must offer retry. |

## Cache And Data Rules

- The endpoint is backend-only and public read-only. The browser never calls
  Binance.
- It calls `SnapshotService.get_snapshot()` first, validates the symbol against
  that snapshot's eligible rows, and derives its window end from that snapshot
  time.
- It reuses the existing successful per-symbol, in-memory 1,800-second cache.
  Successful empty arrays are cacheable; failure results are never cached.
- The existing 60-second snapshot cache and current top-N preload remain. No
  database, full-universe prefetch, websocket, pagination, private endpoint,
  credential, or trading surface is added.

## Implementation Sequence

1. Human authorizes Task C and pastes
   `task-history-endpoint-claude-glm.prompt.md` into Claude-GLM.
2. Bookkeeper validates file scope, test evidence, and commits Task C on the
   stage branch. It records Task C's fixed range in `status.json`.
3. Human then pastes `task-drawer-history-refinement-kimi.prompt.md` into Kimi.
   Kimi must use the Task C committed endpoint contract, not invent a browser
   fetch to Binance.
4. Bookkeeper commits Task D, recomputes the combined range/fingerprint, and
   only then prepares the formal cross-reviews.

## Acceptance

- Non-top-N selected TST/RE-style rows can load their settled history without
  a global poll.
- A true empty 30-day window, an upstream failure, and an unrequested initial
  row are visibly distinct.
- The route filter remains, route data remains in the API, and the table no
  longer displays a route-class column.
- The wider Drawer shows all three annualized card labels without wrapping.
- Backend tests, frontend self-check, endpoint schema validation, `git diff
  --check`, and a local live-public smoke check pass before formal review.

```text
本地北京时间: 2026-07-10 20:17:06 CST
下一步模型: human
下一步任务: 先授权并派发 Task C 给 Claude-GLM；Task D 的 Kimi PASTE BODY 必须等待 Task C 提交。
```
