# P2 — Market navigation layout shift Review-1 (Grok)

Identity:
- task_id: `P2-market-nav-layout-shift-review-1-grok`
- target_role: `Reviewer` (Review-1)
- target_model: `grok`
- provider: `xai`
- target_window: `grok-review`
- status_revision: `2`
- required_skill: `agents/skills/code-reviewer.md`

Baseline source revision:
- `base_sha`: `2b1acc36cff97f7dc28e311920178e6b57156eae`

Delivery commit:
- `delivery_sha`: `8f4b891741b29194d35b213b5f7968ae9f501c61`

Goal:
- Perform an independent, read-only Review-1 code and test review on the committed delivery range `2b1acc36cff97f7dc28e311920178e6b57156eae..8f4b891741b29194d35b213b5f7968ae9f501c61`.
- Review Focus:
  1. Inspect `git diff 2b1acc36cff97f7dc28e311920178e6b57156eae..8f4b891741b29194d35b213b5f7968ae9f501c61`.
  2. Verify synchronous `renderPnlCurve()` execution in `setActiveView` before `loadPnlSeries()`.
  3. Verify that `renderPnlCurve` internal guard cleanly owns panel visibility (leaving market view automatically collapses panel via guard; entry immediately expands panel if points/error exist).
  4. Verify the Layout Shift guard in `renderPnlCurve` triggering `scrollIntoView({ behavior: 'auto', block: 'center' })` when `state.marketRowFocusSymbol` is active.
  5. Verify `frontend/self-check.js` 62e-1 and 62e-2 assertions and ambient teardown.
  6. Execute `node frontend/self-check.js` and verify 185 tests pass cleanly.
- Output Handoff:
  - Create `reports/agent-runs/2026-08-29-market-nav-layout-shift-v1/evidence/P2-review-1-grok.handoff.md` per Task Handoff Evidence Contract in `agents/roles.md`.

Allowed Files:
- `reports/agent-runs/2026-08-29-market-nav-layout-shift-v1/evidence/P2-review-1-grok.handoff.md` (create only)
- Read-only on all other files. No source, test, schema, database, or git modifications.

Inputs:
- `AGENTS.md`
- this dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-29-market-nav-layout-shift-v1/status.json`
- `agents/roles.md` — Reviewer section and Task Handoff Evidence Contract section
- `agents/skills/code-reviewer.md`
- `reports/agent-runs/2026-08-29-market-nav-layout-shift-v1/evidence/P1-market-nav-layout-shift-implementation.handoff.md`

Acceptance Checks:
- `pass`: Synchronous pre-render in `setActiveView` verified.
- `pass`: Single-owner guard in `renderPnlCurve` verified.
- `pass`: Layout Shift auto re-alignment guard verified.
- `pass`: `node frontend/self-check.js` executed and passed 100%.
- `pass`: Handoff file created at `evidence/P2-review-1-grok.handoff.md`.

reply_to: agy
After emitting the normal console receipt, send that same receipt once to the reply_to window per HERDR.md, then stop.
