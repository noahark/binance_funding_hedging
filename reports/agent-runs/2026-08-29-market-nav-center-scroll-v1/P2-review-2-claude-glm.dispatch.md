# P2 — Market navigation viewport center scroll Review-2 (Claude-GLM)

Identity:
- task_id: `P2-market-nav-center-scroll-review-2-claude-glm`
- target_role: `Reviewer` (Review-2)
- target_model: `claude_glm`
- provider: `zhipu_glm`
- target_window: `claude-glm-review`
- status_revision: `2`
- required_skill: `agents/skills/reality-checker.md`

Baseline source revision:
- `base_sha`: `25cea9db770936e3e896fc71234b39f733f4ad65`

Delivery commit:
- `delivery_sha`: `69e5cfa5f0d6764fb20452035ce18b63fc043875`

Goal:
- Perform an independent, read-only Review-2 requirement satisfaction, actual effects, operational risk, and release readiness review on the committed delivery range `25cea9db770936e3e896fc71234b39f733f4ad65..69e5cfa5f0d6764fb20452035ce18b63fc043875`.
- Review Focus:
  1. Inspect `git diff 25cea9db770936e3e896fc71234b39f733f4ad65..69e5cfa5f0d6764fb20452035ce18b63fc043875`.
  2. Verify that the user's reported issue (target row stopping at the bottom instead of centering in the middle) is completely resolved by the mathematical rAF centering implementation.
  3. Verify that the change introduces zero regressions to existing navigation, filtering, or view-switch behaviors.
  4. Verify zero backend, database, store, schema, network API, or money/order side-effects.
  5. Execute `node frontend/self-check.js` and verify all 185 tests pass cleanly.
- Output Handoff:
  - Create `reports/agent-runs/2026-08-29-market-nav-center-scroll-v1/evidence/P2-review-2-claude-glm.handoff.md` per Task Handoff Evidence Contract in `agents/roles.md`.

Allowed Files:
- `reports/agent-runs/2026-08-29-market-nav-center-scroll-v1/evidence/P2-review-2-claude-glm.handoff.md` (create only)
- Read-only on all other files. No source, test, schema, database, or git modifications.

Inputs:
- `AGENTS.md`
- this dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-29-market-nav-center-scroll-v1/status.json`
- `agents/roles.md` — Reviewer section and Task Handoff Evidence Contract section
- `agents/skills/reality-checker.md`
- `reports/agent-runs/2026-08-29-market-nav-center-scroll-v1/evidence/P1-market-nav-center-scroll-implementation.handoff.md`

Acceptance Checks:
- `pass`: Viewport vertical center positioning requirement is faithfully met.
- `pass`: Zero regressions on existing features.
- `pass`: Zero backend/schema/money side effects.
- `pass`: `node frontend/self-check.js` executed and passed 100%.
- `pass`: Handoff file created at `evidence/P2-review-2-claude-glm.handoff.md`.

reply_to: agy
After emitting the normal console receipt, send that same receipt once to the reply_to window per HERDR.md, then stop.
