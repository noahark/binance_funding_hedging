# Stage Task

## Stage ID

`2026-07-history-background-refresh-v1`

## Goal

Move expensive funding-history and private borrow enrichment off the full-
snapshot request path while preserving a single canonical backend snapshot.
Keep the meaningful-rate subset of the default homepage warm in serial rolling
batches. A user click performs one selected-symbol refresh of public market
fields, 30-day settled history, actual selected-asset borrow rate, and actual
selected-asset max-borrowable; the worker publishes a complete new state and the
endpoint returns only that row projection for targeted frontend rendering.

## Non-Goals

- No order, borrow, repay, transfer, close, or other trading execution.
- No full-universe history prewarm.
- No history-fetch concurrency, connection pool, asyncio rewrite, delta merge,
  generic scheduler, disk cache, watched-symbol set, interest TTL, or priority
  ledger.
- No click-time balance, position, account valuation, unrelated-asset, or full-
  universe public refresh.
- No full-snapshot response or full-table rerender after every row click.
- No removal of the existing full-snapshot or funding-history compatibility
  endpoints.
- No Harness, workflow, registry, canonical product-document, deployment, or
  credential-management changes in this stage.

## File Boundaries

Allowed production files, subject to development-breakdown narrowing:

- `backend/services/snapshot_service.py`
- `backend/services/private_client.py`
- `backend/adapters/binance_public.py`
- `backend/app/server.py`
- `backend/config.py`
- `backend/domain/snapshot.py` only if pure row assembly/extraction needs a
  narrowly scoped helper
- `schemas/api/public-market/symbol-snapshot.schema.json`
- `frontend/index.html`

Allowed tests and evidence:

- `backend/tests/`
- `frontend/self-check.js`
- `reports/api-samples/2026-07-history-background-refresh-v1/`
- `reports/agent-runs/2026-07-history-background-refresh-v1/`

Forbidden or out of scope:

- trading execution surfaces or mutating Binance endpoints
- credential values, expanded aliases/environments, signatures, headers, full
  signed queries, balances, positions, or account valuation evidence
- `AGENTS.md`, `workflows/`, `agents/registry.yaml`, and Harness scripts/schemas
- canonical `docs/` promotion before user approval
- unrelated frontend layout, styling, filtering, and account-panel behavior

## Acceptance Criteria

- `GET /api/public-market/snapshot` performs zero upstream fetches and returns a
  complete old or new published state.
- Worker startup is explicit; construction alone starts no thread; offline and
  kill-switch-disabled modes do not start it.
- Before the immediate first base publication, snapshot/symbol reads briefly
  return 503; no request waits for deep-history sweep.
- Base public data refreshes at 60s; every 30s tick processes at most 10 missing/
  expired histories from the valid-rate default-view subset and publishes.
- Null/invalid-rate rows may remain visible but are intentionally not prewarmed.
- A symbol click submits one bounded worker command; it creates no watched set,
  priority state, or separate interest TTL.
- The selected public refresh does not invoke full `fetch_raw()`.
- Selected-asset max-borrowable and actual-rate reads use exact-key one-shot TTL
  bypass through the existing single HMAC GET-only exit.
- Click publication reuses the last published account panel and non-selected-row
  borrow fields; balances, positions, valuation, and unrelated assets are never
  fetched by the click path.
- The worker is the only domain-cache writer and only full-state publisher.
- The legacy funding-history endpoint is a pure published-state projection with
  zero upstream/cache writes.
- `public-market-symbol-snapshot/v1` returns one row, warnings/metadata, and an
  explicit published version; it never returns the full rows array.
- Full snapshot and selected row response are provably from the same published
  version.
- Frontend patches only the selected row/drawer, disables that row for one second
  after click, ignores activation while the command is in flight, and does not
  click-time rerender the full table.
- Global ordering/summary may reconcile on the existing full poll within 60s.
- Partial-source failure follows the design truth table and never exposes a half-
  assembled state or erases last-good data unnecessarily.
- Selected refresh timeout defaults to 30s and preserves last published state.
- Raw public samples and sanitized signed-call evidence ground the new contract.
- Existing backend tests and `node frontend/self-check.js` pass with the new
  deterministic lifecycle/command cases.

## Human Gates

- Approved design default: brief 503 only before immediate base publication;
  never block for complete deep-history prewarm.
- Approved design default: emergency background kill switch remains present and
  background refresh is enabled by default; offline forces non-start.
- Credentials remain operator-provided and are never recorded in artifacts.
- Merge to `main` requires explicit user acceptance after review-2 ACCEPT.

## Designer

- Provider/model: OpenAI Codex / GPT-5
- Skill: `software_architect` (`read_write_docs`)
- Prior involvement: design author and later user-authorized bookkeeper; not an
  implementation, fix, or formal-review author
- Date: 2026-07-12

本地北京时间: 2026-07-12 23:06:34 CST
下一步模型: Claude Fable5
下一步任务: 使用 task_planner 产出 12-development-breakdown.md
