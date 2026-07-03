# Task B dispatch — Kimi frontend market table

You are Kimi (`kimi-2.7`), acting as the **frontend owner** for
`stage_id=2026-07-public-market-impl-v1`, skill `minimal_change_engineer`,
mode write-code. The backend public-market contract is already frozen and
dual-reviewed ACCEPT in the prior stage; you build the frontend against that
frozen contract only.

## Read first

- `AGENTS.md`
- `agents/developer-discipline.md`
- `reports/agent-runs/2026-07-public-market-impl-v1/fable5-detail-breakdown.md` (§4 Task B is your spec)
- `reports/agent-runs/2026-07-public-market-impl-v1/00-task.md` (file boundaries)
- `docs/api/public-market-contract.md` (frozen contract — higher authority than any summary)
- `schemas/api/public-market/snapshot.schema.json` (frozen schema)
- `reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/public-market-snapshot.json` (frozen normalized sample — your fixture source)
- `docs/product/PRD.md`
- `prototypes/fake-ui/index.html` (read-only visual baseline for the Chinese workstation style)

## Goal

Build a build-tool-free static frontend (`frontend/`) — pure HTML/CSS/JS, no
bundler/framework/npm — that displays the public-market snapshot in the agreed
Chinese workstation visual style. The backend (Task A, built in parallel) will
statically host `frontend/` at `/` on `127.0.0.1` and serve
`GET /api/public-market/snapshot` on the same origin.

## Data source (only two allowed)

1. `fetch('/api/public-market/snapshot')` — relative same-origin path via the
   backend static host. **The formal local page must load real data from this
   endpoint.** No direct Binance calls.
2. A fixture mode: a byte-level copy of the frozen normalized sample at
   `frontend/fixture/public-market-snapshot.json`. Do not hand-edit it. Fixture
   mode is for offline tests / no-backend self-checks only; it must not be the
   default data source for the formal page.

## Required display

Market table with, per row: `symbol`, `asset_tag`, `route_class`,
`futures.last_funding_rate`, `futures.next_funding_time` (converted to Beijing
time for display), `futures.mark_price`, `futures.index_price`,
`negative_funding_status`, and `ui_flags`.

UI-copy rules (review-1 will check these against the contract warnings):

- The `last_funding_rate` column/header and tooltip must read "最近更新的资金费率"
  (most recently updated funding rate). **Never** label it "已结算" (settled) or
  "预测" (estimate/predicted) — the settled-vs-estimate semantics are unproven
  (a contract warning).
- `warnings[]` must be rendered in a visible region of the page; do not swallow
  them.
- BSTOCK rows must be visibly tagged. `PERP_ONLY_EXCLUDED` rows may be filtered
  out by default (with a toggle to show them).

## Allowed interactions (this stage)

Market-table display, filter/search, manual refresh button, warning display, and
BSTOCK / route_class / negative_funding_status status tags only.

## Forbidden this stage

- Do NOT implement: open-position ticket, planning calculator, order flow,
  account status, position status, or any trading-intent button. Do not stub
  them either.
- Do NOT call Binance directly.
- Do NOT invent classification, route, or conversion logic beyond display
  formatting (e.g. ms→Beijing-time is fine; deriving route_class is not).
- Do NOT use WebSocket, order-book/depth, or auto-refresh polling.
- Do NOT edit anything outside `frontend/**` (no `backend/**`, no schema, no
  contract doc, no `docs/`, no `agents/`, no `workflows/`, no `scripts/`). A
  boundary crossing is REWORK regardless of code quality.
- If a required UI field is absent from the contract, mark the task BLOCKED and
  request a contract update; do not work around it.

## Git / commit rule (important)

Write `frontend/**` and your report
`reports/agent-runs/2026-07-public-market-impl-v1/20-implementation-frontend.md`
into the worktree. **Do NOT run `git commit` / `git add`.** The controller
commits Task B in a fixed order so each task's review fingerprint stays clean
(see `70-handoff.md` Commit-order strategy). Leave your files in the working
tree for the controller to commit.

## Test self-check (write into 20-implementation-frontend.md)

A replayable self-check list, including: all 6 fixture rows render; `warnings`
visible; BSTOCK tag shown; `next_funding_time` converted to Beijing time
correctly; PERP_ONLY_EXCLUDED filterable; fixture mode and live-endpoint mode
both documented. The controller's Task C will do the live same-origin
integration check separately.

## Output

- `frontend/**` (static page + `frontend/fixture/public-market-snapshot.json`)
- `reports/agent-runs/2026-07-public-market-impl-v1/20-implementation-frontend.md`

End your work with the standard footer:

```text
本地北京时间: <local date output> CST
下一步模型: Claude-GLM (controller)
下一步任务: Controller commits Task B, then integration verification (Task C).
```
