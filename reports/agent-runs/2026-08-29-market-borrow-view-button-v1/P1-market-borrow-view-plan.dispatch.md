# P1 — Market borrow view button plan

Identity:
- task_id: `P1-market-borrow-view-plan`
- target_role: `Planner`
- target_model: `gpt-5.6-sol`
- provider: `openai`
- status_revision: `1`
- required_skill: `agents/skills/task-planner.md`

Goal:
- Produce the minimal, robust implementation plan and breakdown for adding a "查看借币" (View Borrow Task) button in the Market Table's "借币" column.
- Product Requirements & UX:
  1. Placement: Next to (on the right of) the existing "确认" (Confirm) button in the Market Table's borrow operation cell (`renderBorrowOpCell`).
  2. Visibility / Matching Condition: Only render and display this button if there is at least one active borrow task in `state.borrowTasks` for the row's `base_asset` whose `status` is currently `'borrowing'` (执行中) or `'paused'` (暂停中). If there are no borrow tasks for that asset, or if all tasks for that asset are `'completed'` or `'deleted'`, do not show the button.
  3. Action & Deep Linking Flow:
     - On clicking the button, navigate to the "借币任务" (Borrow Tasks) view (`setActiveView('borrow-tasks')`).
     - Tab/Filter handling: Check the target task's status. If the target task is `paused`, ensure the borrow view filter is switched (e.g. `state.borrowTaskFilter = 'paused'` or `'all'`) so that the task card DOM element is actually rendered by `renderBorrowTasks()`.
     - Element finding & Scrolling: Locate the target card DOM element (`.borrow-task-card[data-task-id="..."]`) and smoothly scroll it into view (`scrollIntoView({ behavior: 'smooth', block: 'center' })`).
     - Visual Feedback: Apply a transient highlight pulse/focus animation class (e.g., lasting ~1.5s) to the target card so the user immediately recognizes the focused task.
     - Event Isolation: Explicitly stop event propagation (`e.stopPropagation()`) for both click and keydown on the button to avoid accidentally triggering the market table row's drawer open event.
  4. Multi-task Handling (1-to-N): Define deterministic behavior if multiple matching tasks exist for the same asset (e.g., target the latest created task by `created_at` / `id`).
  5. Minimal Change & Safety: This is a pure frontend enhancement in `frontend/index.html` reading existing `state.borrowTasks` memory cache. No backend API, schema, or store changes.
  6. Testing Strategy: Detail additions/updates to `frontend/self-check.js` covering rendering conditions (show on borrowing/paused, hidden on no-task/completed/deleted), click-to-jump event behavior, filter switching, and event bubbling isolation.
  7. Plan Artifact: Write the complete plan to `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/market-borrow-view.plan.md`.
  8. Plan-Review Dispatch: Prepare the read-only pre-implementation plan-review dispatch packet for `opus5` (`anthropic`, window label `claude`) at `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/P2-market-borrow-view-plan-review.dispatch.md`.
  9. Task Handoff: Create `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P1-market-borrow-view-plan.handoff.md` per Task Handoff Evidence Contract in `agents/roles.md`.
  10. Do not implement code changes in P1.

Allowed Files:
- `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/market-borrow-view.plan.md` (create)
- `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/P2-market-borrow-view-plan-review.dispatch.md` (create)
- `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P1-market-borrow-view-plan.handoff.md` (create, preflight `test ! -e` passed)
- No source, test, schema, state, database, production, or live configuration changes.

Inputs:
- `AGENTS.md`
- `HERDR.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/status.json`
- `agents/roles.md` — Planner section, Reviewer section, and Task Handoff Evidence Contract section
- `agents/skills/task-planner.md`
- `frontend/index.html` — market table rendering, `renderBorrowOpCell`, `attachRowHandlers`, `setActiveView`, `renderBorrowTasks`, `renderBorrowTaskCard`
- `frontend/self-check.js` — existing market table and borrow tasks assertions

Current verified facts:
- `base_sha`: `7bb70a74e4e97a5c0b136bc6146167a360f0debb`.
- Human explicitly assigned the workflow: Bookkeeper (`gemini-3.7-flash` / `agy`), Design / Planning (`gpt-5.6-sol` / `codex`), Plan Review (`opus5` / `claude`), Development (`kimi` / `kimi`), Concurrent Review 1 & Review 2 (`grok` / `grok-review` & `claude-glm` / `claude-glm-review`).
- `state.borrowTasks` is already loaded on startup and refreshed on entering borrow view and after task mutations.
- `renderBorrowOpCell` generates HTML for each row; `attachRowHandlers` binds events to elements in that cell.

Acceptance Checks:
- `pass`: Plan defines the exact DOM structure, CSS styling, and button visibility predicate matching `task.asset === row.base_asset && (task.status === 'borrowing' || task.status === 'paused')`.
- `pass`: Plan details the jump mechanism: view transition (`setActiveView('borrow-tasks')`), filter synchronization (ensuring paused tasks are rendered), DOM element selection, `scrollIntoView`, and visual highlight animation.
- `pass`: Plan defines multi-task resolution (latest task) and event isolation (`e.stopPropagation()`).
- `pass`: Plan specifies concrete test cases in `frontend/self-check.js`.
- `pass`: Plan keeps scope minimal with zero backend changes.
- `pass`: Prepared `P2-market-borrow-view-plan-review.dispatch.md` is read-only, targets `opus5` (`anthropic`, window `claude`), cites fixed plan artifact, and specifies return to Bookkeeper (`gemini-3.7-flash` / `agy`).
- `pass`: Handoff file created at `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P1-market-borrow-view-plan.handoff.md` with complete source report, human brief, and `BOOKKEEPER_APPEND_ONLY` marker.

Stop:
- Stop after creating the plan, P2 dispatch, and P1 handoff file, then emit console receipt. Do not implement code or launch P2 directly.

reply_to: agy
After emitting the normal console receipt, send that same receipt once to the reply_to window per this file, then stop.
