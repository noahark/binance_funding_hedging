# P4 — Review-1 (Grok) for Market borrow view button

Identity:
- task_id: `P4-market-borrow-view-review-1-grok`
- target_role: `Reviewer` (Review-1)
- target_model: `grok`
- provider: `xai`
- target_window: `grok-review`
- status_revision: `4`
- required_skill: `agents/skills/code-reviewer.md`

Goal:
- Perform formal, independent Review-1 of the fixed delivery commit `89ab96d70c1a04ee120ff6ee6f2b22d6ab58420a` against base `7bb70a74e4e97a5c0b136bc6146167a360f0debb`.
- Inspect code quality, CSS styles/animations, DOM seams, contract compliance, event isolation, error boundaries, input preservation during redraws, and self-check coverage in `frontend/index.html` and `frontend/self-check.js`.
- Execute `node frontend/self-check.js` independently and verify all test cases pass.
- Return an explicit `ACCEPT（接受）` or `REWORK（返工）` verdict.

Fixed Delivery Target:
- Base SHA: `7bb70a74e4e97a5c0b136bc6146167a360f0debb`
- Delivery SHA: `89ab96d70c1a04ee120ff6ee6f2b22d6ab58420a`
- Reviewed diff: `git diff 7bb70a74e4e97a5c0b136bc6146167a360f0debb..89ab96d70c1a04ee120ff6ee6f2b22d6ab58420a`

Allowed Files:
- Create only: `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P4-review-1-grok.handoff.md`.
- Read-only otherwise. Do not modify source, tests, plan, schema, database, configuration, `status.json`, or git history.

Inputs (read in startup order, then only these task materials):
- `AGENTS.md`
- this dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/status.json`
- `agents/roles.md` — Reviewer section and Task Handoff Evidence Contract section
- `agents/skills/code-reviewer.md`
- `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/market-borrow-view.plan.md`
- `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P3-market-borrow-view-implementation.handoff.md`
- `frontend/index.html`
- `frontend/self-check.js`

Acceptance Checks:
- `pass`: Inspect `git diff 7bb70a7..89ab96d` and verify that "查看借币" button renders strictly when `task.asset === row.base_asset && (task.status === 'borrowing' || task.status === 'paused')`, and is hidden otherwise.
- `pass`: Button layout `.borrow-op-actions` is cleanly placed inside `.borrow-op-inputs` without breaking grid layout or input styling.
- `pass`: Jump flow deterministically selects newest task, resets tab to tasks, syncs filter to task status, switches view, safely queries DOM, smooth scrolls to center, and applies ~1.5s highlight with reduced-motion static outline fallback.
- `pass`: Click and keydown handlers on the button call `e.stopPropagation()` without `preventDefault()`, preventing table drawer opening and preserving keyboard Enter/Space activation.
- `pass`: Market table projection updates on task list/mutation changes while preserving user input values.
- `pass`: `node frontend/self-check.js` passes 100% cleanly (176 PASS, 0 FAIL).
- `pass`: Create handoff at `evidence/P4-review-1-grok.handoff.md` with complete source report, Human brief, and `BOOKKEEPER_APPEND_ONLY` marker.

Stop:
- Stop after review, creating the handoff file, and emitting the console receipt. Do not commit, merge, or deploy.

reply_to: agy
After emitting the normal console receipt, send that same receipt once to the reply_to window per HERDR.md, then stop.
