# PASTE BODY: Task D Drawer History Loading And Table Refinement

You are the executor in an existing interactive Kimi session. Perform this
bounded frontend task in the repository. Do not start another model terminal,
do not return a `-p` launch command, and do not delegate the task. Do not
commit; the bookkeeper owns commits and stage state.

Do not start until the bookkeeper supplies the committed Task C range and
confirms that `GET /api/public-market/funding-history?symbol=...` plus
`schemas/api/public-market/funding-history.schema.json` exist. If that
dependency is absent, record it as a blocker and make no code change.

Before editing, read `AGENTS.md` and:

- `reports/agent-runs/2026-07-funding-annualized-history-v1/00-task.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/10-design.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/11-adr.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/12-development-breakdown.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/13-review-feedback-fix.md`

Implement Task D only:

1. Remove the default table's `route_class` column. Keep the route filter and
   route field in the snapshot/client validation. Keep the visible
   `negative_funding_status` column. Update all table column indexes and the
   blocked-state `colspan`.
2. Make the right Drawer `width: min(620px, 100vw)` on desktop/narrow viewports.
   Its annualized grid must use three non-overflowing tracks and labels such as
   `30D 已结算` must not wrap.
3. When a selected row already has `funding_history`, render it immediately.
   When it has none, show an accessible loading state and fetch the same-origin
   endpoint with `encodeURIComponent(row.symbol)`. Do not call Binance from the
   browser.
4. On HTTP 200, validate the response shape sufficiently for safe rendering,
   merge `funding_history`, `annualized_funding_7d`, and
   `annualized_funding_30d` into the selected row, refresh the table, and render
   the Drawer. `history_status: empty` is a genuine no-record message.
5. On HTTP 502 `funding_history_unavailable`, keep the Drawer open, show a
   distinct retryable failure state, and provide a retry control. Do not label
   it as “no settled history.” Ignore a response that arrives after the user has
   selected a different symbol or closed the Drawer.
6. Preserve row click/keyboard selection, Escape/backdrop/close behavior,
   refresh behavior, privacy behavior, existing 24h estimate wording, and all
   non-Drawer product UI.

You may modify only the Task D files listed in `00-task.md`:

- `frontend/index.html`
- `frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/20-implementation-frontend-history-fix.md`

Do not edit backend/schema/canonical docs, stage `status.json`/`70-handoff.md`,
review artifacts, Harness files, `.env*`, or private/trading code.

Extend `frontend/self-check.js` for: removed route column and retained route
filter/status column; revised column indexes and blocked `colspan`; Drawer
width/card label constraints; same-origin selected-symbol request; loading;
available history and table merge; true-empty; HTTP-502 retry; and stale
response isolation. Run:

```bash
node frontend/self-check.js
git diff --check
```

Write the Task D implementation report with changed files, test output, and
any blocker. End it with the required local timestamp footer.
