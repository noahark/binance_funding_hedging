# P1 — Market navigation layout shift fix implementation

Identity:
- task_id: `P1-market-nav-layout-shift-implementation`
- target_role: `Implementer`
- target_model: `kimi`
- provider: `moonshot`
- target_window: `kimi`
- status_revision: `1`
- required_skill: `agents/skills/senior-developer.md`

Baseline source revision:
- `base_sha`: `2b1acc35ec0db7ecf8b548bdfb13e01869e5d4cb`

Goal:
- Fix the market navigation layout shift in `frontend/index.html` where clicking "行情 ↗" from a Borrow Task Card results in the viewport stopping ~450px too high (target row pushed down) due to `#pnl-curve-panel` expanding asynchronously after scrolling.

Problem Analysis & Root Cause (Independently verified by Claude/opus5):
1. `#pnl-curve-panel` (height ~450px) sits directly above `#market-board` in `#market-view`.
2. When leaving `market` view, `setActiveView` explicitly collapsed `els.pnlCurvePanel.style.display = 'none'`.
3. When returning to `market` view via `viewBorrowAssetInMarket`, `setActiveView('market')` only called async `loadPnlSeries()` without synchronous pre-rendering (unlike `flow-log` and `borrow-tasks`).
4. `scrollIntoView` executed while the PNL panel height was 0.
5. 100-200ms later, `loadPnlSeries()` network request finished and called `renderPnlCurve()`, expanding the ~450px panel and pushing the entire market table down by 450px.

Implementation Requirements:
1. Synchronous Pre-render in `setActiveView` (`frontend/index.html` ~line 8075):
   ```javascript
   if (isMarket) {
     renderPnlCurve();
     loadPnlSeries();
   }
   ```
   (Call `renderPnlCurve()` unconditionally when `isMarket` is true, allowing it to evaluate its internal state guards).
2. Remove unneeded collapse on leave:
   Remove `else if (els.pnlCurvePanel) els.pnlCurvePanel.style.display = 'none';` in `setActiveView`, because `#market-view` parent container already manages view visibility.
3. Universal Layout Shift Re-alignment Guard in `renderPnlCurve` (`frontend/index.html` ~line 9236):
   When `renderPnlCurve()` renders or unhides the panel, check if a row navigation is currently active:
   ```javascript
   if (state.marketRowFocusSymbol) {
     const tr = marketRowElForSymbol(state.marketRowFocusSymbol);
     if (tr && typeof tr.scrollIntoView === 'function') {
       tr.scrollIntoView({ behavior: 'auto', block: 'center' });
     }
   }
   ```
   This guarantees that even on cold loads or any subsequent asynchronous panel updates, the target row is instantaneously re-centered.
4. Keep `viewBorrowAssetInMarket`'s standard `tr.scrollIntoView({ behavior: 'smooth', block: 'center' })`.

Tests & Compatibility (`frontend/self-check.js`):
- Add test assertions verifying:
  1. Switching to market view calls `renderPnlCurve()` synchronously.
  2. `renderPnlCurve()` re-aligns the focused row if `state.marketRowFocusSymbol` is active.
- Execute `node frontend/self-check.js` and verify 100% pass (0 failures).

Output Handoff:
- Create `reports/agent-runs/2026-08-29-market-nav-layout-shift-v1/evidence/P1-market-nav-layout-shift-implementation.handoff.md` with `delivery_sha: pending`.

Allowed Files:
- `frontend/index.html` (modify)
- `frontend/self-check.js` (modify)
- `reports/agent-runs/2026-08-29-market-nav-layout-shift-v1/evidence/P1-market-nav-layout-shift-implementation.handoff.md` (create, preflight `test ! -e` passed)
- No backend, API, store, executor, schema, database, configuration, or git state changes.

Inputs:
- `AGENTS.md`
- this dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-29-market-nav-layout-shift-v1/status.json`
- `agents/roles.md` — Implementer section and Task Handoff Evidence Contract section
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `frontend/index.html`
- `frontend/self-check.js`

Acceptance Checks:
- `pass`: `setActiveView('market')` invokes `renderPnlCurve()` synchronously before `loadPnlSeries()`.
- `pass`: Unneeded `pnlCurvePanel.style.display = 'none'` on leaving market view is removed.
- `pass`: `renderPnlCurve()` contains layout shift guard re-aligning `state.marketRowFocusSymbol` with `behavior: 'auto'`.
- `pass`: `node frontend/self-check.js` passes 100% with 0 failures.
- `pass`: Deterministic handoff created at `evidence/P1-market-nav-layout-shift-implementation.handoff.md`.

reply_to: agy
After emitting the normal console receipt, send that same receipt once to the reply_to window per HERDR.md, then stop.
