# P1 — Market row focus styling optimization implementation

Identity:
- task_id: `P1-market-row-focus-style-implementation`
- target_role: `Implementer`
- target_model: `kimi`
- provider: `moonshot`
- target_window: `kimi`
- status_revision: `1`
- required_skill: `agents/skills/senior-developer.md`

Baseline source revision:
- `base_sha`: `2417b92736e4f3a76ef5ba138e68cfb7593da180`

Goal:
- Refine the `.market-row-focus` visual style in `frontend/index.html` so that instead of applying left inset shadows to every individual column cell (`td`), only the leftmost edge (`td:first-child`) and rightmost edge (`td:last-child`) have vertical highlight borders, while internal cells display a clean, cohesive background pulse without inner vertical stripes.

Problem Analysis:
- `tbody tr.market-row-focus > td` currently applied `market-row-focus-pulse` with `box-shadow: inset 3px 0 0 var(--brand)` to all cells, producing unwanted vertical dividing lines across every single column in the highlighted table row.

Implementation Requirements:
1. CSS Keyframes & Rules in `frontend/index.html` (~lines 1095-1105):
   ```css
   @keyframes market-row-focus-bg {
     0%, 70% { background: var(--brand-soft); }
     100% { background: transparent; }
   }
   @keyframes market-row-focus-left {
     0%, 70% { background: var(--brand-soft); box-shadow: inset 4px 0 0 var(--brand); }
     100% { background: transparent; box-shadow: none; }
   }
   @keyframes market-row-focus-right {
     0%, 70% { background: var(--brand-soft); box-shadow: inset -4px 0 0 var(--brand); }
     100% { background: transparent; box-shadow: none; }
   }
   tbody tr.market-row-focus > td {
     animation: market-row-focus-bg 1.5s ease-out;
   }
   tbody tr.market-row-focus > td:first-child {
     animation: market-row-focus-left 1.5s ease-out;
   }
   tbody tr.market-row-focus > td:last-child {
     animation: market-row-focus-right 1.5s ease-out;
   }
   ```
2. Reduced Motion Support in `frontend/index.html` (~lines 1255-1265):
   ```css
   @media (prefers-reduced-motion: reduce) {
     tbody tr.market-row-focus > td {
       animation: none;
       background: var(--brand-soft);
     }
     tbody tr.market-row-focus > td:first-child {
       box-shadow: inset 4px 0 0 var(--brand);
     }
     tbody tr.market-row-focus > td:last-child {
       box-shadow: inset -4px 0 0 var(--brand);
     }
     tbody tr.market-row-focus {
       outline: none;
     }
     ...
   }
   ```
3. Tests:
   - Execute `node frontend/self-check.js` and verify all tests pass 100% (185 passed, 0 failed).

Output Handoff:
- Create `reports/agent-runs/2026-08-29-market-row-focus-style-v1/evidence/P1-market-row-focus-style-implementation.handoff.md` with `delivery_sha: pending`.

Allowed Files:
- `frontend/index.html` (modify)
- `frontend/self-check.js` (modify if needed)
- `reports/agent-runs/2026-08-29-market-row-focus-style-v1/evidence/P1-market-row-focus-style-implementation.handoff.md` (create, preflight `test ! -e` passed)
- No backend, API, store, executor, schema, database, configuration, or git state changes.

Inputs:
- `AGENTS.md`
- this dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-29-market-row-focus-style-v1/status.json`
- `agents/roles.md` — Implementer section and Task Handoff Evidence Contract section
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `frontend/index.html`
- `frontend/self-check.js`

Acceptance Checks:
- `pass`: `market-row-focus` styling updated to apply left/right border shadows only to `td:first-child` and `td:last-child`.
- `pass`: Internal `td` cells receive only smooth background pulse without internal stripe artifacts.
- `pass`: `node frontend/self-check.js` passes 100% with 0 failures.
- `pass`: Deterministic handoff created at `evidence/P1-market-row-focus-style-implementation.handoff.md`.

reply_to: agy
After emitting the normal console receipt, send that same receipt once to the reply_to window per HERDR.md, then stop.
