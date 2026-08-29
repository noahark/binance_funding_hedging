# P4 — Borrow card to market navigation Review-1 (Grok)

Identity:
- task_id: `P4-borrow-card-market-nav-review-1-grok`
- target_role: `Reviewer` (Review-1)
- target_model: `grok`
- provider: `xai`
- target_window: `grok-review`
- status_revision: `4`
- required_skill: `agents/skills/code-reviewer.md`

Baseline source revision:
- `base_sha`: `341aef6aeab417b3d2e83bd6f5ec1bed90b048b0`

Delivery commit:
- `delivery_sha`: `1de91864ab2446f51668b0c356d17da1a6575de6`

Goal:
- Perform an independent, read-only Review-1 code and test review on the committed delivery range `341aef6aeab417b3d2e83bd6f5ec1bed90b048b0..1de91864ab2446f51668b0c356d17da1a6575de6`.
- Review Focus:
  1. Inspect `git diff 341aef6aeab417b3d2e83bd6f5ec1bed90b048b0..1de91864ab2446f51668b0c356d17da1a6575de6`.
  2. Verify UI & Styling: "行情 ↗" button in `.borrow-task-head .borrow-market-nav` (`margin-left: auto`), disabled fallback when unmatchable.
  3. Verify Matching & Unblocking Logic: `row.base_asset === task.asset`. Already-visible path preserves all filters and DOM inputs without redraw. Hidden path unblocks 6 filters (`search=''`, `assetTag=''`, `routeClass=''`, `showPerpOnly=true`, `hideLowDailyRate=false`, `hideLowNetYield=false`), syncs DOM controls, and calls `renderTable()`.
  4. Verify View Switch & Highlight: `setActiveView('market')`, safe DOM lookup `tr.selectable[data-symbol="${CSS.escape(symbol)}"]`, smooth center scroll, 1.5s focus pulse animation with `prefers-reduced-motion: reduce` static outline fallback, focus preserved across snapshot redraws.
  5. Verify Event Isolation: `e.stopPropagation()` on click/keydown without `preventDefault()`.
  6. Execute `node frontend/self-check.js` and verify all 184 tests pass cleanly.
- Output Handoff:
  - Create `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P4-review-1-grok.handoff.md` per Task Handoff Evidence Contract in `agents/roles.md`.

Allowed Files:
- `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P4-review-1-grok.handoff.md` (create only)
- Read-only on all other files. No source, test, schema, database, or git modifications.

Inputs:
- `AGENTS.md`
- this dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/status.json`
- `agents/roles.md` — Reviewer section and Task Handoff Evidence Contract section
- `agents/skills/code-reviewer.md`
- `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/borrow-card-market-nav.plan.md`
- `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P3-borrow-card-market-nav-implementation.handoff.md`

Acceptance Checks:
- `pass`: Button placement, disabled fallback, and styling meet plan.
- `pass`: Unblocking logic covers all 6 hiding filters and syncs DOM controls.
- `pass`: Deep linking, safe selector, smooth center scrolling, and 1.5s pulse focus are verified.
- `pass`: Event isolation is complete.
- `pass`: `node frontend/self-check.js` executed and passed 100%.
- `pass`: Handoff file created at `evidence/P4-review-1-grok.handoff.md`.

reply_to: agy
After emitting the normal console receipt, send that same receipt once to the reply_to window per HERDR.md, then stop.
