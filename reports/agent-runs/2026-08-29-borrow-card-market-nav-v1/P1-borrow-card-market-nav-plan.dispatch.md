# P1 — Borrow card to market navigation plan

Identity:
- task_id: `P1-borrow-card-market-nav-plan`
- target_role: `Planner`
- target_model: `gpt-5.6-sol`
- provider: `openai`
- target_window: `codex`
- status_revision: `1`
- required_skill: `agents/skills/task-planner.md`

Goal:
- Produce the minimal, robust implementation plan and breakdown for adding a "行情 ↗" (Navigate to Market Row) button on each Borrow Task Card.
- Product Requirements & UX:
  1. Placement & UI: Positioned in the top-right corner of the Borrow Task Card header (`.borrow-task-head`), styled as a lightweight compact button (`btn compact`).
  2. Asset Matching: Map `task.asset` (e.g. `BTC`, `ETH`, `INJ`) to the corresponding market row in `state.snapshot.rows` where `row.base_asset === task.asset`. If no matching row exists in snapshot, handle gracefully (e.g. disabled or hidden).
  3. Action & Deep Linking Flow:
     - Switch view: `setActiveView('market')`.
     - Filter & Visibility Handling ("智能按需放开 + 保底 100% 可见"):
       - Check if the target row is already visible under current filters (`displayRows().some(r => r.symbol === targetSymbol)`).
       - If already visible: preserve user's current search text, category dropdowns, and checkbox filters as-is without resetting.
       - If currently hidden/filtered out: auto-adjust blocking filters (clear search text `state.filters.search = ''`, reset `assetTag`/`routeClass` to `''`, uncheck `hideLowDailyRate` and `hideLowNetYield`), synchronize DOM control values (`els.searchInput.value = ''`, `els.filterHideLowDailyRate.checked = false`, `els.filterHideLowNetYield.checked = false`, etc.), and call `renderTable()` to ensure the target row is rendered.
     - Element Lookup & Scrolling: Locate target row (`tr = els.tableBody.querySelector('tr[data-symbol="..."]')`) and smoothly scroll it into center (`tr.scrollIntoView({ behavior: 'smooth', block: 'center' })`).
     - Visual Feedback: Apply transient focus animation class (e.g. `.market-row-focus` for ~1.5s, with static outline fallback under `prefers-reduced-motion: reduce`).
     - Event Isolation: Call `e.stopPropagation()` in click and keydown handlers on the button.
  4. Minimal Change & Zero Backend: Pure frontend enhancement in `frontend/index.html` and `frontend/self-check.js`. No backend API, store, schema, or database changes.
  5. Testing Strategy: Detail additions/updates to `frontend/self-check.js` covering button rendering, asset matching, already-visible navigation (filters preserved), hidden-row navigation (filters auto-unblocked & DOM inputs synced), scrolling/focus lifecycle, and event isolation.
  6. Plan Artifact: Write the complete plan to `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/borrow-card-market-nav.plan.md`.
  7. Plan-Review Dispatch: Prepare the read-only pre-implementation plan-review dispatch packet for `opus5` (`anthropic`, window `claude`) at `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/P2-borrow-card-market-nav-plan-review.dispatch.md`.
  8. Task Handoff: Create `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P1-borrow-card-market-nav-plan.handoff.md` per Task Handoff Evidence Contract in `agents/roles.md`.
  9. Do not implement code changes in P1.

Allowed Files:
- `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/borrow-card-market-nav.plan.md` (create)
- `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/P2-borrow-card-market-nav-plan-review.dispatch.md` (create)
- `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P1-borrow-card-market-nav-plan.handoff.md` (create, preflight `test ! -e` passed)
- No source, test, schema, state, database, production, or live configuration changes.

Inputs:
- `AGENTS.md`
- `HERDR.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/status.json`
- `agents/roles.md` — Planner section, Reviewer section, and Task Handoff Evidence Contract section
- `agents/skills/task-planner.md`
- `frontend/index.html` — borrow task cards rendering, `renderBorrowTaskCard`, `displayRows`, `filteredRows`, `renderTable`, `setActiveView`
- `frontend/self-check.js`

Current verified facts:
- `base_sha`: `341aef6aeab417b3d2e83bd6f5ec1bed90b048b0`.
- Workflow: Bookkeeper (`gemini-3.7-flash` / `agy`), Design / Planning (`gpt-5.6-sol` / `codex`), Plan Review (`opus5` / `claude`), Development (`kimi` / `kimi`), Concurrent Review 1 & Review 2 (`grok` / `grok-review` & `claude-glm` / `claude-glm-review`).

Acceptance Checks:
- `pass`: Plan defines the exact DOM structure, CSS styling, and placement for "行情 ↗" in `.borrow-task-head`.
- `pass`: Plan defines asset-to-symbol resolution (`row.base_asset === task.asset`).
- `pass`: Plan details the intelligent filter unblocking algorithm (preserve if visible, unblock & sync DOM controls if hidden).
- `pass`: Plan details the deep-linking navigation flow: view switch, DOM lookup, `scrollIntoView`, and 1.5s highlight animation with reduced-motion fallback.
- `pass`: Plan specifies concrete test cases in `frontend/self-check.js`.
- `pass`: Scope is pure frontend with zero backend modifications.
- `pass`: Prepared `P2-borrow-card-market-nav-plan-review.dispatch.md` is read-only, targets `opus5` (`anthropic`, window `claude`), cites fixed plan artifact, and specifies return to Bookkeeper (`gemini-3.7-flash` / `agy`).
- `pass`: Handoff file created at `evidence/P1-borrow-card-market-nav-plan.handoff.md` with complete source report, Human brief, and `BOOKKEEPER_APPEND_ONLY` marker.

Stop:
- Stop after creating the plan, P2 dispatch, and P1 handoff file, then emit console receipt. Do not implement code or launch P2 directly.

reply_to: agy
After emitting the normal console receipt, send that same receipt once to the reply_to window per HERDR.md, then stop.
