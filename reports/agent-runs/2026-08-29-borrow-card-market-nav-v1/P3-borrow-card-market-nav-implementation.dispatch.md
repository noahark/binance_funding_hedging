# P3 — Borrow card to market navigation implementation

Identity:
- task_id: `P3-borrow-card-market-nav-implementation`
- target_role: `Implementer`
- target_model: `kimi`
- provider: `moonshot`
- target_window: `kimi`
- status_revision: `3`
- required_skill: `agents/skills/senior-developer.md`

Goal:
- Implement the approved plan for adding the "行情 ↗" (Market Navigation) button on Borrow Task Cards.
- Reference Authorities:
  1. Approved Plan: `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/borrow-card-market-nav.plan.md`
  2. P2 Review Handoff & Observations: `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P2-borrow-card-market-nav-plan-review.handoff.md`
- Key Implementation Requirements:
  1. UI Placement & Styling: In `renderBorrowTaskCard`, place a `<button class="btn compact borrow-market-nav" type="button" data-task-nav-market="${asset}" ...>行情 ↗</button>` at the right side of `.borrow-task-head` (`margin-left: auto`). When snapshot has no match, render disabled with `aria-disabled="true"` and title explanation. Use scoped `.borrow-task-head .borrow-market-nav` styles without modifying base `.borrow-task-head` (Observation C).
  2. Deterministic Matching: `row.base_asset === task.asset` from `state.snapshot.rows` (first match).
  3. Action & Deep Linking Flow (`navBorrowTaskToMarket(asset)`):
     - Check `alreadyVisible = displayRows().some(r => r.symbol === targetSymbol)`.
     - If `alreadyVisible`: do NOT touch any `state.filters` or DOM controls; do NOT call `renderTable()`.
     - If hidden: unblock all 6 hiding filters and synchronize DOM controls:
       - `state.filters.search = ''` & `els.searchInput.value = ''`
       - `state.filters.assetTag = ''` & `els.filterAssetTag.value = ''`
       - `state.filters.routeClass = ''` & `els.filterRouteClass.value = ''`
       - `state.filters.showPerpOnly = true` & `els.filterShowPerpOnly.checked = true` (Note: true!)
       - `state.filters.hideLowDailyRate = false` & `els.filterHideLowDailyRate.checked = false`
       - `state.filters.hideLowNetYield = false` & `els.filterHideLowNetYield.checked = false`
       - Call `renderTable()` once.
     - Switch view: `setActiveView('market')`.
     - Query row safely: `els.tableBody.querySelector('tr.selectable[data-symbol="' + CSS.escape(symbol) + '"]')`.
     - Scroll: `tr.scrollIntoView({ behavior: 'smooth', block: 'center' })`.
     - Focus class & lifecycle: `state.marketRowFocusSymbol = symbol` + `.market-row-focus` pulse animation class (1.5s, with static outline under `prefers-reduced-motion: reduce`). Rerenders via `renderRowHtml` include the class if matching focus symbol. Single module timer clears focus after 1500ms.
     - Event isolation: `e.stopPropagation()` in click and keydown handlers without `preventDefault()`.
  4. Testing: Add self-check tests in `frontend/self-check.js` (including Observation A regression assertion and Observation D `globalThis.__appHelpers` usage).
- Required Checks:
  - Run `node frontend/self-check.js` and verify 100% PASS with 0 failures.

Allowed Files:
- `frontend/index.html` (modify)
- `frontend/self-check.js` (modify)
- `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P3-borrow-card-market-nav-implementation.handoff.md` (create, preflight `test ! -e` passed)
- No backend, API, store, executor, schema, database, configuration, or git state changes.

Inputs (read in startup order, then only these task materials):
- `AGENTS.md`
- this dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/status.json`
- `agents/roles.md` — Implementer section and Task Handoff Evidence Contract section
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/borrow-card-market-nav.plan.md`
- `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P2-borrow-card-market-nav-plan-review.handoff.md`
- `frontend/index.html`
- `frontend/self-check.js`

Acceptance Checks:
- `pass`: "行情 ↗" button renders on each borrow task card with disabled fallback for unmatchable assets.
- `pass`: When already visible, navigation preserves all current filters and DOM inputs without redraw.
- `pass`: When hidden, navigation unblocks all 6 hiding filters (including `showPerpOnly=true`), syncs DOM controls, and re-renders table.
- `pass`: View switches to market, scrolls smoothly to center, and applies ~1.5s highlight with reduced-motion fallback.
- `pass`: Event propagation is stopped on click/keydown.
- `pass`: `node frontend/self-check.js` executes and passes 100% cleanly.
- `pass`: Handoff file created at `evidence/P3-borrow-card-market-nav-implementation.handoff.md` with `delivery_sha: pending`.

Stop:
- Stop after implementation, running `node frontend/self-check.js`, creating the handoff file, and emitting the console receipt. Do not commit, merge, or launch reviewer sessions.

reply_to: agy
After emitting the normal console receipt, send that same receipt once to the reply_to window per HERDR.md, then stop.
