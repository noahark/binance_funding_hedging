# Stage Task

## Stage ID

`2026-07-funding-annualized-history-v1`

## Goal

Extend the read-only public-market snapshot and existing frontend so operators
can compare estimated 24h funding annualization with 7D/30D annualization from
settled funding records, then inspect a selected row's near-30-day settled
history in a right-side drawer.

The delivery must preserve the distinction between the current-period estimate
and settled funding: 24h is estimate-derived; 7D and 30D are settled-only.

## Non-Goals

- No order, borrow, repay, transfer, close, or other execution surface.
- No private API, credential, account, borrow-cost, or `net_daily_yield`
  behavior change.
- No route rename or wire-version bump; retain
  `GET /api/public-market/snapshot` and `public-market-snapshot/v1`.
- No global sort-basis change, full-universe deep-history polling, websocket,
  chart, or frontend-to-Binance request.
- No full-universe prefetch for the Drawer follow-up. A selected symbol may use
  only the same-origin backend endpoint defined in
  `13-review-feedback-fix.md`.
- No canonical-document promotion in the implementation tasks. Promotion is
  considered only after review and explicit user approval.
- No Harness, workflow, registry, adapter, or unrelated cleanup changes.

## File Boundaries

Task A, backend contract and settled-history enrichment, may modify:

- `backend/adapters/binance_public.py`
- `backend/config.py`
- `backend/domain/snapshot.py`
- `backend/services/snapshot_service.py`
- `backend/tests/test_config.py`
- `backend/tests/test_snapshot.py`
- `backend/tests/test_funding_history.py` (new)
- `backend/tests/fixtures/funding-history/**` (new deterministic vectors)
- `schemas/api/public-market/snapshot.schema.json`
- `reports/api-samples/2026-07-funding-annualized-history-v1/**`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/20-implementation-backend.md`

Task B, frontend presentation and drawer UX, may modify:

- `frontend/index.html`
- `frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/20-implementation-frontend.md`

Task C, selected-symbol settled-history endpoint, may modify:

- `backend/app/server.py`
- `backend/services/snapshot_service.py`
- `backend/domain/snapshot.py` only if a pure existing-history helper must be
  extracted rather than duplicated
- `backend/tests/test_funding_history.py`
- `backend/tests/test_funding_history_endpoint.py` (new)
- `backend/tests/smoke_server.py`
- `schemas/api/public-market/funding-history.schema.json` (new)
- `reports/agent-runs/2026-07-funding-annualized-history-v1/20-implementation-backend-history-fix.md`

Task D, history drawer refinement, may modify:

- `frontend/index.html`
- `frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/20-implementation-frontend-history-fix.md`

Forbidden or out-of-scope for both tasks:

- `AGENTS.md`, `workflows/**`, `agents/**`, Harness scripts, and stage-template
  files.
- `docs/api/public-market-contract.md` and all other canonical docs.
- Existing frozen sample directories and accepted-stage artifacts.
- Private-channel code, trading/borrow/transfer code, route/version changes,
  credentials, `.env*`, and unrelated frontend/backend files.
- `status.json`, `70-handoff.md`, review artifacts, and stage commits. The
  bookkeeper owns those records and commits.

## Acceptance Criteria

1. The schema declares additive decimal-or-null fields
   `annualized_funding_24h`, `annualized_funding_7d`, and
   `annualized_funding_30d` without adding them to the row schema's `required`
   array. Frozen v0.1 snapshots lacking the fields remain schema-valid, while
   every current `SnapshotService` output row must emit all three keys.
2. 24h equals `daily_funding_rate * 365`. 7D and 30D equal the Decimal sum of
   settled records inside their calendar windows times `365 / N`, quantized to
   eight fixed decimal places. No production float path or interval-derived
   7D/30D formula is allowed.
3. Live history retrieval is bounded to the current `Config.top_n` symbols,
   requests a 30-day window with `limit=1000`, has a dedicated 30-minute cache,
   and cannot make one failed symbol fail the whole snapshot.
4. A raw public deep-history sample is recorded under this stage's
   `reports/api-samples/` path. It must ground the contract change; synthetic
   vectors supplement rather than replace it.
5. The table displays all three annualized values with existing sign/color
   conventions and accurate estimate-versus-settled labels. Null values render
   as `-`.
6. Row selection opens one accessible right-side drawer containing the selected
   symbol, the same values, and newest-first settled history. Backdrop, close
   control, and Escape close it; refresh retains the drawer only while its
   symbol remains in the snapshot.
7. Backend tests, frontend self-check, schema validation, and `git diff --check`
   pass before formal review.
8. `GET /api/public-market/funding-history?symbol=<eligible-USDT-perpetual>` is
   a same-origin, public read-only endpoint. It reuses the per-symbol 30-minute
   successful-result cache and the snapshot's time boundary; it never causes a
   full-universe prefetch or a browser-to-Binance request. Its success response
   distinguishes an empty settled window from upstream failure; invalid symbols
   and unavailable upstream history use deterministic 4xx/5xx responses.
9. Opening a drawer for a row with no preloaded history requests that endpoint
   once, renders a loading state, and replaces the drawer's settled history and
   7D/30D values on success. An empty successful response says there are no
   records; an unavailable response says the history request failed and offers
   retry. It must not claim that an unrequested non-top-N symbol has no history.
10. The default table no longer displays a `route_class` column. The field and
    existing route filter remain available, while `negative_funding_status`
    stays visible as the operator-facing negative-funding decision state.
11. The right Drawer is at least 620px wide on desktop (or full viewport width
    on a narrower device); its three annualized cards do not wrap their labels.

## Human Gates

- Human approval of this package is required before implementation dispatch.
- The review-feedback fix package also requires explicit human dispatch
  approval. Task C must commit before Task D is sent to Kimi.
- User acceptance remains required after review-2 before merge or canonical-doc
  promotion.

## Designer

- Model: Codex/GPT current session
- Skill: `task_planner`
- Date: 2026-07-10

```text
本地北京时间: 2026-07-10 13:13:36 CST
下一步模型: human
下一步任务: 确认任务边界、冻结的 wire 字段与串行派发顺序。
```
