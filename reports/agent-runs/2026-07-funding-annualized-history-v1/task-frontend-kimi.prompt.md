# PASTE BODY: Task B Table Columns And History Drawer

You are the executor in an existing interactive Kimi session. Perform the work
in this repository. Do not start another model terminal, do not return a `-p`
launch command, and do not delegate the task. Do not commit; the bookkeeper
owns commits and stage state.

Before editing, read `AGENTS.md` and these artifacts:

- `reports/agent-runs/2026-07-funding-annualized-history-v1/00-task.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/10-design.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/11-adr.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/12-development-breakdown.md`

Task A is committed as `2e27efcbed960206b43c25054bf6105224942439` on this
stage branch. Its fixed wire contract is: decimal-string-or-null
`annualized_funding_24h`, `annualized_funding_7d`, and
`annualized_funding_30d`; `funding_history` is settled-only and newest first.
The schema keeps these fields optional for frozen-v0.1 compatibility, but every
current backend snapshot row emits all three fields. Treat them as present in
the frontend's current-service validation and fixture.

Implement Task B only:

1. Update the frontend fixture and client validation for the three fields.
2. Add 24h/7D/30D annualized columns immediately after daily funding. Reuse the
   existing percentage formatting and sign colors. Labels/tooltips must say
   24h is estimate-derived and 7D/30D are settled-history annualizations. Null
   values render `-`.
3. Make a table row selectable by click and `Enter`/`Space`. Open one right-side
   drawer with selected symbol, identical formatted values, and its settled
   history list in `Asia/Shanghai`. Newest records appear first.
4. Backdrop click, close control, and Escape close the drawer. A refresh keeps
   it open only while the selected symbol still exists and replaces its data.
5. Keep the frontend a backend-snapshot consumer. Do not call Binance from the
   browser, add trading actions, alter private-account panels, or hide public
   funding values with the privacy switch.

You may modify only the Task B files in `00-task.md`. Do not edit backend,
schema, canonical docs, stage `status.json`/`70-handoff.md`, review artifacts,
or Harness files.

Run:

```bash
node frontend/self-check.js
git diff --check
```

Write `20-implementation-frontend.md` with changed files, test output summary,
and any blocker. End your report with the required local timestamp footer. Do
not report completion until the specified checks pass or a specific blocker is
recorded.
