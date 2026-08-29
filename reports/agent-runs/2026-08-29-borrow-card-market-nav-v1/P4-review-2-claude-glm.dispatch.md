# P4 — Borrow card to market navigation Review-2 (Claude-GLM)

Identity:
- task_id: `P4-borrow-card-market-nav-review-2-claude-glm`
- target_role: `Reviewer` (Review-2)
- target_model: `claude_glm`
- provider: `zhipu_glm`
- target_window: `claude-glm-review`
- status_revision: `4`
- required_skill: `agents/skills/reality-checker.md`

Baseline source revision:
- `base_sha`: `341aef6aeab417b3d2e83bd6f5ec1bed90b048b0`

Delivery commit:
- `delivery_sha`: `1de91864ab2446f51668b0c356d17da1a6575de6`

Goal:
- Perform an independent, read-only Review-2 requirements satisfaction, actual effects, operational risk, and release readiness review on the committed delivery range `341aef6aeab417b3d2e83bd6f5ec1bed90b048b0..1de91864ab2446f51668b0c356d17da1a6575de6`.
- Review Focus:
  1. Inspect `git diff 341aef6aeab417b3d2e83bd6f5ec1bed90b048b0..1de91864ab2446f51668b0c356d17da1a6575de6`.
  2. Verify that the user requirement is faithfully satisfied: borrow card top-right "行情 ↗" navigates directly to corresponding market table row.
  3. Verify that filter unblocking works reliably (preserving when visible; clearing search, unchecking low rate/yield, showPerpOnly=true when hidden) and DOM controls stay in sync.
  4. Verify zero backend, database, store, schema, network API, or money/order side-effects.
  5. Verify accessibility and reduced-motion fallback.
  6. Execute `node frontend/self-check.js` and verify all 184 tests pass cleanly.
- Output Handoff:
  - Create `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P4-review-2-claude-glm.handoff.md` per Task Handoff Evidence Contract in `agents/roles.md`.

Allowed Files:
- `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P4-review-2-claude-glm.handoff.md` (create only)
- Read-only on all other files. No source, test, schema, database, or git modifications.

Inputs:
- `AGENTS.md`
- this dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/status.json`
- `agents/roles.md` — Reviewer section and Task Handoff Evidence Contract section
- `agents/skills/reality-checker.md`
- `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/borrow-card-market-nav.plan.md`
- `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P3-borrow-card-market-nav-implementation.handoff.md`

Acceptance Checks:
- `pass`: User requirements for reverse market navigation are completely met.
- `pass`: Filter unblocking and DOM synchronization operate reliably with 0 regressions.
- `pass`: Zero backend/schema/money side effects.
- `pass`: `node frontend/self-check.js` executed and passed 100%.
- `pass`: Handoff file created at `evidence/P4-review-2-claude-glm.handoff.md`.

reply_to: agy
After emitting the normal console receipt, send that same receipt once to the reply_to window per HERDR.md, then stop.
