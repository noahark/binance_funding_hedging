# P2 — Market navigation viewport center scroll Review-1 (Grok)

Identity:
- task_id: `P2-market-nav-center-scroll-review-1-grok`
- target_role: `Reviewer` (Review-1)
- target_model: `grok`
- provider: `xai`
- target_window: `grok-review`
- status_revision: `2`
- required_skill: `agents/skills/code-reviewer.md`

Baseline source revision:
- `base_sha`: `25cea9db770936e3e896fc71234b39f733f4ad65`

Delivery commit:
- `delivery_sha`: `69e5cfa5f0d6764fb20452035ce18b63fc043875`

Goal:
- Perform an independent, read-only Review-1 code and test review on the committed delivery range `25cea9db770936e3e896fc71234b39f733f4ad65..69e5cfa5f0d6764fb20452035ce18b63fc043875`.
- Review Focus:
  1. Inspect `git diff 25cea9db770936e3e896fc71234b39f733f4ad65..69e5cfa5f0d6764fb20452035ce18b63fc043875`.
  2. Verify `scrollElementToCenter(el)` math formula: `targetY = currentY + rect.top - window.innerHeight/2 + rect.height/2` with `Math.max(0, targetY)` clamp.
  3. Verify execution in `requestAnimationFrame` with `setTimeout(0)` fallback, and graceful headless fallback to `el.scrollIntoView({ behavior: 'smooth', block: 'center' })` when window/scrollTo is absent.
  4. Verify that `viewBorrowAssetInMarket` connects to `scrollElementToCenter(tr)` without breaking existing focus class lifecycle or filter unblocking logic.
  5. Verify that self-check 62e-1..4 properly cleans up ambient state and mock fixtures in `finally`.
  6. Execute `node frontend/self-check.js` and verify all 185 tests pass cleanly.
- Output Handoff:
  - Create `reports/agent-runs/2026-08-29-market-nav-center-scroll-v1/evidence/P2-review-1-grok.handoff.md` per Task Handoff Evidence Contract in `agents/roles.md`.

Allowed Files:
- `reports/agent-runs/2026-08-29-market-nav-center-scroll-v1/evidence/P2-review-1-grok.handoff.md` (create only)
- Read-only on all other files. No source, test, schema, database, or git modifications.

Inputs:
- `AGENTS.md`
- this dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-29-market-nav-center-scroll-v1/status.json`
- `agents/roles.md` — Reviewer section and Task Handoff Evidence Contract section
- `agents/skills/code-reviewer.md`
- `reports/agent-runs/2026-08-29-market-nav-center-scroll-v1/evidence/P1-market-nav-center-scroll-implementation.handoff.md`

Acceptance Checks:
- `pass`: Math centering formula and rAF timing are correct.
- `pass`: `viewBorrowAssetInMarket` integration is verified.
- `pass`: Node/headless fallback is intact.
- `pass`: `node frontend/self-check.js` executed and passed 100%.
- `pass`: Handoff file created at `evidence/P2-review-1-grok.handoff.md`.

reply_to: agy
After emitting the normal console receipt, send that same receipt once to the reply_to window per HERDR.md, then stop.
