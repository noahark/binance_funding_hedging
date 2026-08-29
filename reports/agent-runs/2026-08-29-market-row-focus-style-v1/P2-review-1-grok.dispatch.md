# P2 — Market row focus styling Review-1 (Grok)

Identity:
- task_id: `P2-market-row-focus-style-review-1-grok`
- target_role: `Reviewer` (Review-1)
- target_model: `grok`
- provider: `xai`
- target_window: `grok-review`
- status_revision: `2`
- required_skill: `agents/skills/code-reviewer.md`

Baseline source revision:
- `base_sha`: `2417b92219d442e2085a17e70f9734ab753809b0`

Delivery commit:
- `delivery_sha`: `e449c9d7e9d25371c43bf2a3ffa1cf7857bfbaf5`

Goal:
- Perform an independent, read-only Review-1 code and test review on the committed delivery range `2417b92219d442e2085a17e70f9734ab753809b0..e449c9d7e9d25371c43bf2a3ffa1cf7857bfbaf5`.
- Review Focus:
  1. Inspect `git diff 2417b92219d442e2085a17e70f9734ab753809b0..e449c9d7e9d25371c43bf2a3ffa1cf7857bfbaf5`.
  2. Verify that `market-row-focus-pulse` keyframe was split into `-bg`, `-left`, and `-right`.
  3. Verify that `td` receives only `-bg` (without box-shadow/inset), `td:first-child` receives `inset 4px 0 0 var(--brand)`, and `td:last-child` receives `inset -4px 0 0 var(--brand)`.
  4. Verify reduced motion support in media query.
  5. Verify that `frontend/self-check.js` 62d-8 assertions and regression guards match.
  6. Execute `node frontend/self-check.js` and verify 185 tests pass cleanly.
- Output Handoff:
  - Create `reports/agent-runs/2026-08-29-market-row-focus-style-v1/evidence/P2-review-1-grok.handoff.md` per Task Handoff Evidence Contract in `agents/roles.md`.

Allowed Files:
- `reports/agent-runs/2026-08-29-market-row-focus-style-v1/evidence/P2-review-1-grok.handoff.md` (create only)
- Read-only on all other files. No source, test, schema, database, or git modifications.

Inputs:
- `AGENTS.md`
- this dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-29-market-row-focus-style-v1/status.json`
- `agents/roles.md` — Reviewer section and Task Handoff Evidence Contract section
- `agents/skills/code-reviewer.md`
- `reports/agent-runs/2026-08-29-market-row-focus-style-v1/evidence/P1-market-row-focus-style-implementation.handoff.md`

Acceptance Checks:
- `pass`: CSS keyframe split and `:first-child`/`:last-child` rules verified.
- `pass`: Internal `td` elements have zero inner vertical divider stripes.
- `pass`: Reduced motion rules verified.
- `pass`: `node frontend/self-check.js` executed and passed 100%.
- `pass`: Handoff file created at `evidence/P2-review-1-grok.handoff.md`.

reply_to: agy
After emitting the normal console receipt, send that same receipt once to the reply_to window per HERDR.md, then stop.
