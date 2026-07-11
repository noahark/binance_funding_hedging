# PASTE BODY: Task C Selected-Symbol Settled-History Endpoint

You are the executor in an existing interactive Claude-GLM session. Perform
this bounded backend task in the repository. Do not start another model
terminal, do not return a `-p` launch command, and do not delegate the task.
Do not commit; the bookkeeper owns commits and stage state.

Before editing, read `AGENTS.md` and:

- `reports/agent-runs/2026-07-funding-annualized-history-v1/00-task.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/10-design.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/11-adr.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/12-development-breakdown.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/13-review-feedback-fix.md`

Task A and Task B are already committed. This is Task C only: add the
same-origin public `GET /api/public-market/funding-history?symbol=...` endpoint
described in the fix design.

Required behavior:

1. Validate the query symbol. Return JSON HTTP 400 `invalid_symbol` when it is
   missing or malformed, and HTTP 404 `symbol_not_found` when it is not an
   eligible symbol in the current snapshot.
2. Use the current snapshot's time boundary and reuse the existing successful
   1,800-second per-symbol funding-history cache. Do not fetch all symbols, use
   request-time browser values, persist data, or add a private/client-side
   Binance route.
3. Return a schema-valid HTTP 200 payload with
   `schema_version: public-market-funding-history/v1`, `symbol`, `data_time`,
   `history_status` (`available` or `empty`), newest-first `funding_history`,
   and settled-only `annualized_funding_7d` / `annualized_funding_30d`.
4. An upstream transport/HTTP/parse failure returns JSON HTTP 502
   `funding_history_unavailable`. Do not cache failures. A successful empty
   list is HTTP 200 with `history_status: empty` and is cacheable.
5. Preserve the existing snapshot endpoint, its top-N preload, its 60-second
   cache, `public-market-snapshot/v1`, sort behavior, private-channel behavior,
   and all existing public data semantics.

You may edit only Task C files listed in `00-task.md`:

- `backend/app/server.py`
- `backend/services/snapshot_service.py`
- `backend/domain/snapshot.py` only to extract/reuse pure settled-history logic
- `backend/tests/test_funding_history.py`
- `backend/tests/test_funding_history_endpoint.py` (new)
- `backend/tests/smoke_server.py`
- `schemas/api/public-market/funding-history.schema.json` (new)
- `reports/agent-runs/2026-07-funding-annualized-history-v1/20-implementation-backend-history-fix.md`

Do not edit frontend files, canonical docs, `status.json`, `70-handoff.md`,
review artifacts, Harness files, frozen samples, `.env*`, or any private/trading
code.

Tests required before reporting:

```bash
python3 -m pytest backend/tests -q
python3 -m json.tool schemas/api/public-market/funding-history.schema.json >/dev/null
git diff --check
```

Also run a no-credential live-public smoke check only after tests pass, using a
new unused local port and `ENV_FILE=/dev/null`, `APP_OFFLINE=false`, and
`BINANCE_PRIVATE_CHANNEL_ENABLED=false`. Verify HTTP 200 for a valid selected
symbol and no private credentials in output. Record only the Task C
implementation report with changed files, test output, endpoint status cases,
live-smoke result, and any blocker. End it with the required local timestamp
footer.
