# P3 — Market borrow view button implementation

Identity:
- task_id: `P3-market-borrow-view-implementation`
- target_role: `Implementer`
- target_model: `kimi`
- provider: `moonshot`
- target_window: `kimi`
- status_revision: `3`
- required_skill: `agents/skills/senior-developer.md`

Goal:
- Implement the approved plan for adding the "查看借币" (View Borrow Task) button in the Market Table borrow column.
- Reference Authorities:
  1. Approved Plan: `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/market-borrow-view.plan.md`
  2. P2 Review Handoff & Observations: `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P2-market-borrow-view-plan-review.handoff.md`
- Key Implementation Requirements:
  1. UI Placement & Styling: Wrap the Confirm button and the conditional "查看借币" button in a `.borrow-op-actions` flex container inside `.borrow-op-inputs` (addressing Observation A). Disabled rows (`isBorrowOpDisabledRow`) continue to render `—`.
  2. Visibility Predicate: Render the button only when `task.asset === row.base_asset && (task.status === 'borrowing' || task.status === 'paused')`. Return null/empty if no active/paused task matches.
  3. Deterministic 1-to-N Selection: When multiple matching tasks exist, select `sortTasksNewestFirst(matches)[0]`.
  4. Deep Linking & Jump Flow:
     - Recover task tab: `setBorrowTab('tasks')`.
     - Sync filter: set `state.borrowTaskFilter` to the target task's status (e.g. `'paused'` if the task is paused).
     - Switch view: `setActiveView('borrow-tasks')`.
     - Locate card: find `.borrow-task-card[data-task-id="..."]` safely without malformed selector injection.
     - Smooth scroll: `cardEl.scrollIntoView({ behavior: 'smooth', block: 'center' })`.
     - Transient highlight: apply focus animation class (e.g. `.is-focused` for ~1.5s, respecting `prefers-reduced-motion`).
  5. Event Isolation: Explicitly call `e.stopPropagation()` in both `click` and `keydown` handlers on the "查看借币" button. Do NOT call `preventDefault()` on Enter/Space so keyboard activation works.
  6. Market Table Projection: Ensure market table buttons update when `state.borrowTasks` changes (addressing Observation B without redundant double rendering).
  7. Testing: Update `frontend/self-check.js` mock DOM and add test cases 1 through 8 as detailed in the plan §5, referencing `globalThis.__appHelpers` (addressing Observation C).
- Required Checks:
  - Run `node frontend/self-check.js` and confirm all tests pass with 0 errors.

Allowed Files:
- `frontend/index.html` (modify)
- `frontend/self-check.js` (modify)
- `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P3-market-borrow-view-implementation.handoff.md` (create, preflight `test ! -e` passed)
- No backend, API, store, executor, schema, database, configuration, or git state changes.

Inputs (read in startup order, then only these task materials):
- `AGENTS.md`
- this dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/status.json`
- `agents/roles.md` — Implementer section and Task Handoff Evidence Contract section
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/market-borrow-view.plan.md`
- `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P2-market-borrow-view-plan-review.handoff.md`
- `frontend/index.html`
- `frontend/self-check.js`

Current Verified Facts:
- `base_sha`: `7bb70a74e4e97a5c0b136bc6146167a360f0debb`
- P2 plan review returned `ACCEPT` with 4 non-blocking observations.
- This is a pure frontend implementation task with zero backend dependencies.

Acceptance Checks:
- `pass`: "查看借币" button renders dynamically in `.borrow-op-actions` only for rows with `borrowing` or `paused` borrow tasks.
- `pass`: Clicking or keyboard-triggering "查看借币" switches to borrow-tasks view, activates tasks tab, sets filter to task status, smoothly scrolls target card to center, and applies ~1.5s highlight animation.
- `pass`: Event propagation is stopped on the button, preventing the table row drawer from opening.
- `pass`: Table redraw preserves user inputs in the borrow operation inputs.
- `pass`: `node frontend/self-check.js` executes and passes 100% cleanly.
- `pass`: Handoff file created at `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P3-market-borrow-view-implementation.handoff.md` with `delivery_sha: pending`, source report, and Human brief.

Stop:
- Stop after implementation, running `node frontend/self-check.js`, creating the handoff file, and emitting the console receipt. Do not commit, merge, or launch reviewer sessions.

reply_to: agy
After emitting the normal console receipt, send that same receipt once to the reply_to window per HERDR.md, then stop.
