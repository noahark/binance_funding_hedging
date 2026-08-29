# P2 — Borrow card to market navigation plan review

Identity:
- task_id: `P2-borrow-card-market-nav-plan-review`
- target_role: `Reviewer`
- target_model: `opus5`
- provider: `anthropic`
- target_window: `claude`
- status_revision: `2`
- required_skill: `agents/skills/software-architect.md`

Goal:
- Perform the independent, cross-provider, read-only pre-implementation review required for this borrowing-related `HIGH_RISK` task.
- Decide whether the fixed P1 plan is minimal, internally consistent, implementable against the verified frontend seams, and sufficient to satisfy every dispatch acceptance check without backend, borrowing, order, position, money, or live side effects.
- Return a formal `ACCEPT` or `REWORK` verdict to Bookkeeper (`gemini-3.7-flash`, window `agy`). Do not implement the plan.

Fixed Review Target:
- Plan: `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/borrow-card-market-nav.plan.md`
- Expected SHA-256: `cc87b1e2d8669a93aae3d3a415ed3dd83464780b52cd570ae866b2935e405791`
- Baseline source revision: `341aef6aeab417b3d2e83bd6f5ec1bed90b048b0`
- Verify the plan hash before review. A mismatch makes this packet stale and must return `REWORK`; do not review a moving artifact.

Allowed Files:
- `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P2-borrow-card-market-nav-plan-review.handoff.md` (create only after preflight `test ! -e` passes)
- All other repository files are read-only. Do not change source, tests, plans, dispatches, state, schemas, evidence owned by P1, configuration, or live systems.

Required Reading:
- `AGENTS.md`
- this dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/status.json`
- `agents/roles.md` — Reviewer section and Task Handoff Evidence Contract section
- `agents/skills/software-architect.md`
- `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P1-borrow-card-market-nav-plan.handoff.md`
- fixed plan artifact above
- `frontend/index.html` — only the seams named by the plan
- `frontend/self-check.js` — only the existing self-check seams named by the plan

Review Checks:
1. Confirm exact header placement and DOM/CSS contract for a compact `行情 ↗` button, including graceful no-match behavior and accessibility.
2. Confirm matching is strictly `row.base_asset === task.asset`, deterministically resolves a symbol from the current snapshot, and does not invent aliases or network fallback.
3. Confirm the already-visible branch checks `displayRows()` before mutation and preserves every filter state and DOM control without an unnecessary table redraw.
4. Confirm the hidden branch releases and synchronizes every currently proven hiding condition: search, asset tag, route class, `showPerpOnly`, low daily rate, and low net yield; verify `showPerpOnly=true` closes the `PERP_ONLY_EXCLUDED` visibility gap while `preferOpenable` and `showHl` remain untouched.
5. Confirm the fixed order of view switching, at-most-one redraw, safe row lookup with `CSS.escape`, smooth centered scrolling, and a deterministic 1.5-second focus lifecycle that survives redraws, handles repeated clicks, and has reduced-motion feedback.
6. Confirm click and keydown propagation isolation preserves native keyboard activation and cannot trigger a borrow POST, market fetch, row drawer, order, position, or other side effect.
7. Confirm the proposed `frontend/self-check.js` cases exercise real handlers and DOM/state synchronization, cover the PERP-only guarantee and no-match fail-closed behavior, and run with the existing zero-dependency harness.
8. Confirm implementation scope remains only `frontend/index.html`, `frontend/self-check.js`, and the later implementer handoff; reject speculative abstractions or any backend/schema/store/API work.

Verdict Rules:
- `ACCEPT` only if the fixed plan satisfies all checks and can be implemented without an unresolved acceptance oracle.
- `REWORK` must identify concrete blocking findings, point to the affected plan section/source evidence, and give executable, bounded repair requirements. Plan review does not increment `rework_count`.
- A reviewer-introduced hypothetical may block only when it passes `AGENTS.md` §1 Scenario Admission; otherwise keep it out of the verdict or retain one observation with a concrete reopen trigger where permitted.
- Do not treat the borrowing domain label alone as evidence of a source-side borrowing or money mutation: review the actual planned effect and fail closed on any proven route to one.

Required Handoff:
- Create `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P2-borrow-card-market-nav-plan-review.handoff.md` using the deterministic Task Handoff Evidence Contract.
- Record `delivery_sha: none` because this is a read-only review.
- Include the plan path and verified SHA-256, review evidence and commands, explicit verdict, findings/repair paths, and the exact console receipt in Human Brief before exactly one `BOOKKEEPER_APPEND_ONLY` marker.
- `下一步模型` is the current Bookkeeper: `gemini-3.7-flash（Bookkeeper，agy 窗口）`.
- `下一步任务` must direct that Bookkeeper to verify this handoff and either advance after `ACCEPT` or prepare a bounded Planner correction after `REWORK`.

Expected Console Result:
- Emit one compliant `[TASK_RESULT v2]` block, including:
  - `评审结论: ACCEPT（接受） | REWORK（返工）`
  - `问题记录: <path | none>`
  - `修复要求: <path | none>`
  - the three required Chinese handoff lines.
- After console output, send the exact same receipt once to `agy` using `HERDR.md`; do not wait for, read, or poll the reply.

Stop:
- Stop immediately after writing the P2 handoff, emitting the console receipt, and sending that same receipt once to `agy`. Do not implement, edit P1 artifacts, update `status.json`, commit, merge, deploy, or start another model session.

reply_to: agy
