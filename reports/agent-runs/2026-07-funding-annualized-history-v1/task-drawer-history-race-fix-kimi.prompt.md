# PASTE BODY: Task D Drawer Response-Race Fix

You are the executor in the existing interactive Kimi session that implemented
Task D. Continue in the current stage worktree. Do not start another model
terminal, do not return a `-p` launch command, and do not delegate this task.
Do not commit; the bookkeeper owns commits and stage state.

Read `AGENTS.md`, the current Task D implementation report, and:

- `reports/agent-runs/2026-07-funding-annualized-history-v1/13-review-feedback-fix.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/task-drawer-history-refinement-kimi.prompt.md`

## Finding To Fix

`frontend/index.html` guards a history request immediately after
`await fetch(...)`, but it awaits `res.json()` afterwards without rechecking
whether that response is still active. If the user changes selection or closes
the Drawer while `res.json()` is pending, an old response can merge A's history
and 7D/30D values into the newly selected B row. The existing delayed-fetch
self-check does not cover this response-body race.

## Required Change

1. Add one small, readable active-request guard based on request id, selected
   symbol, and Drawer-open state. Apply it before every state mutation or render
   that follows an `await`, especially immediately after `await res.json()`.
2. Before merging a successful response, require all of:
   `schema_version === "public-market-funding-history/v1"`,
   `data.symbol === requested symbol`, `history_status` is `available` or
   `empty`, `funding_history` is an array, and both settled annualization keys
   exist. An invalid or mismatched response must render the existing retryable
   failure state; it must never merge into any row.
3. Extend `frontend/self-check.js` with a distinct response-body race:
   `fetch()` resolves while A remains selected, `res.json()` stays pending, the
   user selects B or closes the Drawer, then A's body resolves. Assert that the
   current selection, Drawer content, and B row are unchanged by A's response.
   Also cover the wrong-symbol response rejection.
4. Preserve every completed Task D behavior: same-origin only, loading,
   available/empty/502-retry states, route column removal, Drawer width, and
   all existing table/private UI behavior.

Allowed files only:

- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/20-implementation-frontend-history-fix.md`

Do not edit backend/schema/canonical docs, stage `status.json`/`70-handoff.md`,
review artifacts, Harness files, `.env*`, or private/trading code.

Run before reporting:

```bash
node frontend/self-check.js
git diff --check
```

Append a `Drawer response-race fix` section to the existing Task D report with
the changed files, exact test result, and the new race/mismatched-symbol
coverage. End the report with the required local timestamp footer.
