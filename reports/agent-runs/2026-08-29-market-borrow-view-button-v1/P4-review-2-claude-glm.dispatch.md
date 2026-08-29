# P4 — Review-2 (Claude-GLM) for Market borrow view button

Identity:
- task_id: `P4-market-borrow-view-review-2-claude-glm`
- target_role: `Reviewer` (Review-2)
- target_model: `claude_glm`
- provider: `zhipu_glm`
- target_window: `claude-glm-review`
- status_revision: `4`
- required_skill: `agents/skills/reality-checker.md`

Goal:
- Perform formal, independent Review-2 of the fixed delivery commit `89ab96d70c1a04ee120ff6ee6f2b22d6ab58420a` against base `7bb70a74e4e97a5c0b136bc6146167a360f0debb`.
- Evaluate requirement satisfaction, actual operational UX, end-to-end reality check, absence of regressions, boundary cases (e.g. paused task filtering, reduced-motion), and release readiness.
- Execute `node frontend/self-check.js` independently and verify all test cases pass.
- Return an explicit `ACCEPT（接受）` or `REWORK（返工）` verdict.

Fixed Delivery Target:
- Base SHA: `7bb70a74e4e97a5c0b136bc6146167a360f0debb`
- Delivery SHA: `89ab96d70c1a04ee120ff6ee6f2b22d6ab58420a`
- Reviewed diff: `git diff 7bb70a74e4e97a5c0b136bc6146167a360f0debb..89ab96d70c1a04ee120ff6ee6f2b22d6ab58420a`

Allowed Files:
- Create only: `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P4-review-2-claude-glm.handoff.md`.
- Read-only otherwise. Do not modify source, tests, plan, schema, database, configuration, `status.json`, or git history.

Inputs (read in startup order, then only these task materials):
- `AGENTS.md`
- this dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/status.json`
- `agents/roles.md` — Reviewer section and Task Handoff Evidence Contract section
- `agents/skills/reality-checker.md`
- `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/market-borrow-view.plan.md`
- `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P3-market-borrow-view-implementation.handoff.md`
- `frontend/index.html`
- `frontend/self-check.js`

Acceptance Checks:
- `pass`: Reality check on requirement: User can visually see "查看借币" on relevant rows and one-click jump/scroll to the exact borrow task card with highlight feedback.
- `pass`: Deep linking robustness: When jumping to a paused task, the filter properly reflects `paused` so the card is rendered and found in DOM.
- `pass`: Event isolation reality: Clicking "查看借币" never triggers row selection/drawer open.
- `pass`: Input preservation: Ongoing typing in borrow quantity/attempt inputs is preserved during table redraws.
- `pass`: Zero backend/schema/database/money risk.
- `pass`: `node frontend/self-check.js` passes 100% cleanly (176 PASS, 0 FAIL).
- `pass`: Create handoff at `evidence/P4-review-2-claude-glm.handoff.md` with complete source report, Human brief, and `BOOKKEEPER_APPEND_ONLY` marker.

Stop:
- Stop after review, creating the handoff file, and emitting the console receipt. Do not commit, merge, or deploy.

reply_to: agy
After emitting the normal console receipt, send that same receipt once to the reply_to window per HERDR.md, then stop.
