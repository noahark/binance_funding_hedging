# P2 — Market navigation layout shift Review-2 (Claude-GLM)

Identity:
- task_id: `P2-market-nav-layout-shift-review-2-claude-glm`
- target_role: `Reviewer` (Review-2)
- target_model: `claude_glm`
- provider: `zhipu_glm`
- target_window: `claude-glm-review`
- status_revision: `2`
- required_skill: `agents/skills/reality-checker.md`

Baseline source revision:
- `base_sha`: `2b1acc36cff97f7dc28e311920178e6b57156eae`

Delivery commit:
- `delivery_sha`: `8f4b891741b29194d35b213b5f7968ae9f501c61`

Goal:
- Perform an independent, read-only Review-2 requirement satisfaction, actual effects, operational risk, and release readiness review on the committed delivery range `2b1acc36cff97f7dc28e311920178e6b57156eae..8f4b891741b29194d35b213b5f7968ae9f501c61`.
- Review Focus:
  1. Inspect `git diff 2b1acc36cff97f7dc28e311920178e6b57156eae..8f4b891741b29194d35b213b5f7968ae9f501c61`.
  2. Verify that the layout shift defect (market table pushed down ~450px after scroll) is completely solved.
  3. Verify that synchronous cache rendering + universal re-alignment guard eliminate all positioning offsets.
  4. Verify zero regressions on existing navigation, filtering, or view switching.
  5. Verify zero backend, store, schema, database, or money/order side-effects.
  6. Execute `node frontend/self-check.js` and verify 185 tests pass cleanly.
- Output Handoff:
  - Create `reports/agent-runs/2026-08-29-market-nav-layout-shift-v1/evidence/P2-review-2-claude-glm.handoff.md` per Task Handoff Evidence Contract in `agents/roles.md`.

Allowed Files:
- `reports/agent-runs/2026-08-29-market-nav-layout-shift-v1/evidence/P2-review-2-claude-glm.handoff.md` (create only)
- Read-only on all other files. No source, test, schema, database, or git modifications.

Inputs:
- `AGENTS.md`
- this dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-29-market-nav-layout-shift-v1/status.json`
- `agents/roles.md` — Reviewer section and Task Handoff Evidence Contract section
- `agents/skills/reality-checker.md`
- `reports/agent-runs/2026-08-29-market-nav-layout-shift-v1/evidence/P1-market-nav-layout-shift-implementation.handoff.md`

Acceptance Checks:
- `pass`: Layout Shift defect completely resolved by synchronous pre-render and re-alignment guard.
- `pass`: Zero regressions across existing frontend views and self-check suite.
- `pass`: Zero backend/money/order side-effects.
- `pass`: `node frontend/self-check.js` executed and passed 100%.
- `pass`: Handoff file created at `evidence/P2-review-2-claude-glm.handoff.md`.

reply_to: agy
After emitting the normal console receipt, send that same receipt once to the reply_to window per HERDR.md, then stop.
