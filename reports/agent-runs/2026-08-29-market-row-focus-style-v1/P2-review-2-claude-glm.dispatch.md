# P2 — Market row focus styling Review-2 (Claude-GLM)

Identity:
- task_id: `P2-market-row-focus-style-review-2-claude-glm`
- target_role: `Reviewer` (Review-2)
- target_model: `claude_glm`
- provider: `zhipu_glm`
- target_window: `claude-glm-review`
- status_revision: `2`
- required_skill: `agents/skills/reality-checker.md`

Baseline source revision:
- `base_sha`: `2417b92219d442e2085a17e70f9734ab753809b0`

Delivery commit:
- `delivery_sha`: `e449c9d7e9d25371c43bf2a3ffa1cf7857bfbaf5`

Goal:
- Perform an independent, read-only Review-2 requirement satisfaction, actual visual effects, operational risk, and release readiness review on the committed delivery range `2417b92219d442e2085a17e70f9734ab753809b0..e449c9d7e9d25371c43bf2a3ffa1cf7857bfbaf5`.
- Review Focus:
  1. Inspect `git diff 2417b92219d442e2085a17e70f9734ab753809b0..e449c9d7e9d25371c43bf2a3ffa1cf7857bfbaf5`.
  2. Verify that the user's styling feedback ("改成只做该横列左右两边的竖边框高亮") is faithfully satisfied.
  3. Verify zero regressions on table rendering, row selection, navigation, or animations.
  4. Verify zero backend, schema, database, or money/order side-effects.
  5. Execute `node frontend/self-check.js` and verify 185 tests pass cleanly.
- Output Handoff:
  - Create `reports/agent-runs/2026-08-29-market-row-focus-style-v1/evidence/P2-review-2-claude-glm.handoff.md` per Task Handoff Evidence Contract in `agents/roles.md`.

Allowed Files:
- `reports/agent-runs/2026-08-29-market-row-focus-style-v1/evidence/P2-review-2-claude-glm.handoff.md` (create only)
- Read-only on all other files. No source, test, schema, database, or git modifications.

Inputs:
- `AGENTS.md`
- this dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-29-market-row-focus-style-v1/status.json`
- `agents/roles.md` — Reviewer section and Task Handoff Evidence Contract section
- `agents/skills/reality-checker.md`
- `reports/agent-runs/2026-08-29-market-row-focus-style-v1/evidence/P1-market-row-focus-style-implementation.handoff.md`

Acceptance Checks:
- `pass`: Visual requirement faithfully met with left/right borders and clean internal cells.
- `pass`: Zero regressions on existing features.
- `pass`: Zero backend/money/order side-effects.
- `pass`: `node frontend/self-check.js` executed and passed 100%.
- `pass`: Handoff file created at `evidence/P2-review-2-claude-glm.handoff.md`.

reply_to: agy
After emitting the normal console receipt, send that same receipt once to the reply_to window per HERDR.md, then stop.
