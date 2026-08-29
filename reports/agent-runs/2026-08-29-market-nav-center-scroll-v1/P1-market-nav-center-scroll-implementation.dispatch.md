# P1 — Market navigation viewport center scroll implementation

Identity:
- task_id: `P1-market-nav-center-scroll-implementation`
- target_role: `Implementer`
- target_model: `kimi`
- provider: `moonshot`
- target_window: `kimi`
- status_revision: `1`
- required_skill: `agents/skills/senior-developer.md`

Baseline source revision:
- `base_sha`: `25cea9db770936e3e896fc71234b39f733f4ad65`

Goal:
- Adjust the reverse market navigation in `frontend/index.html` so that when clicking "行情 ↗" from a Borrow Task Card, the target table row is smoothly centered in the vertical middle of the viewport (rather than stopping at the bottom of the screen).

Problem Analysis & Root Causes:
1. `<tr>` (`display: table-row`) table box model: In modern browsers (Chrome/Safari), calling `tr.scrollIntoView({ behavior: 'smooth', block: 'center' })` on a table row inside a long table often fails to compute vertical center accurately and falls back to bottom-aligned positioning.
2. Layout Reflow Timing: Switching from `borrow-tasks` to `market` view unhides `marketView` (`display: ''`). If scrolling is calculated synchronously in the same JS turn, layout reflow may not be settled or may conflict with `setActiveView`'s `window.scrollTo(0,0)`.

Implementation Requirements:
1. Viewport Centering Helper: Implement a robust helper function (e.g. `scrollElementToCenter(el)`) in `frontend/index.html`:
   - Use `requestAnimationFrame` (or fallback `setTimeout`) to allow DOM layout reflow to settle.
   - Mathematically compute the exact viewport center position:
     `const rect = el.getBoundingClientRect();`
     `const currentY = window.pageYOffset || document.documentElement.scrollTop || 0;`
     `const targetY = currentY + rect.top - (window.innerHeight / 2) + (rect.height / 2);`
     `window.scrollTo({ top: Math.max(0, targetY), behavior: 'smooth' });`
   - Graceful fallback: If `getBoundingClientRect` or `window.scrollTo` is not available (e.g. in node/mock), fall back to `el.scrollIntoView({ behavior: 'smooth', block: 'center' })`.
2. Integration:
   - Call this centering helper in `viewBorrowAssetInMarket` when locating the target `tr`.
   - Optionally apply the same helper in `viewBorrowTask` for `.borrow-task-card` if appropriate for consistency.
3. Tests & Compatibility:
   - In `frontend/self-check.js`, ensure mock DOM (such as `requestAnimationFrame`, `window.scrollTo`, or `getBoundingClientRect`) supports this cleanly without breaking existing assertions.
   - Run `node frontend/self-check.js` and verify all tests pass 100% (0 failures).
4. Output Handoff:
   - Create `reports/agent-runs/2026-08-29-market-nav-center-scroll-v1/evidence/P1-market-nav-center-scroll-implementation.handoff.md` with `delivery_sha: pending`.

Allowed Files:
- `frontend/index.html` (modify)
- `frontend/self-check.js` (modify)
- `reports/agent-runs/2026-08-29-market-nav-center-scroll-v1/evidence/P1-market-nav-center-scroll-implementation.handoff.md` (create, preflight `test ! -e` passed)
- No backend, API, store, executor, schema, database, configuration, or git state changes.

Inputs:
- `AGENTS.md`
- this dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-29-market-nav-center-scroll-v1/status.json`
- `agents/roles.md` — Implementer section and Task Handoff Evidence Contract section
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `frontend/index.html`
- `frontend/self-check.js`

Acceptance Checks:
- `pass`: Viewport centering helper uses mathematical offset calculation (`rect.top - window.innerHeight / 2 + rect.height / 2`) in `requestAnimationFrame`.
- `pass`: Target `tr` in `viewBorrowAssetInMarket` uses this helper to center smoothly.
- `pass`: Fallback to `scrollIntoView` is preserved for headless/node environments.
- `pass`: `node frontend/self-check.js` executes and passes 100% with 0 failures.
- `pass`: Handoff file created at `evidence/P1-market-nav-center-scroll-implementation.handoff.md` with `delivery_sha: pending`.

reply_to: agy
After emitting the normal console receipt, send that same receipt once to the reply_to window per HERDR.md, then stop.
