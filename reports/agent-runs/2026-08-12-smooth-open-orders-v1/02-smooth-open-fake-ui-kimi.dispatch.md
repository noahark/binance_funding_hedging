Identity:
- task_id: smooth-open-fake-ui-kimi
- target_role: Implementer
- target_model: kimi
- provider: moonshot
- status_revision: 2
- required_skill: agents/skills/senior-developer.md

Goal

Create a frontend-only, visibly fake preview of the frozen smooth-open design so
the Human can judge layout, wording, and information density before any backend
or WebSocket integration. Add the signed slippage-threshold input immediately
after each disabled "平滑开单" button, and add one fake running smooth-open task
card under the task page's "执行中" filter. The preview must be unmistakably
non-executing and must not enable, send, or simulate a real smooth task request.

Allowed Files

- frontend/index.html
- frontend/self-check.js
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-fake-ui-kimi-self-check.txt
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-fake-ui-kimi.handoff.md (create-only; preflight `test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-fake-ui-kimi.handoff.md` returned 0 before dispatch)

Inputs

- AGENTS.md
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/02-smooth-open-fake-ui-kimi.dispatch.md
- reports/agent-runs/ACTIVE.json
- PROJECT_STATE.md
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json
- agents/roles.md (Implementer section and Task Handoff Evidence Contract)
- agents/developer-discipline.md
- agents/skills/senior-developer.md
- docs/planning/smooth-open-orders-v1.md (especially D4-D13, §7, §8.4, and Human 2026-08-13 in §12)
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/01-advisory-design-reviews.md
- frontend/index.html
- frontend/self-check.js

Acceptance Checks

- pass: each forward/reverse market operation cell renders, in this order,
  disabled `平滑开单`, a compact signed-decimal text input with default visible
  value `0.05`, a `%` suffix, then the unchanged `立即开单`; this task does not
  remove the smooth disabled state or add a smooth create request.
- pass: the task view's `running` filter renders exactly one separate fake smooth
  card without inserting it into `state.hedgeTasks`, counters, task navigation,
  logs, or any backend response; other filters do not render the fake card.
- pass: the fake card is visibly labelled `样式预览（不执行）`, represents a
  running forward smooth task, and shows threshold, current round/target,
  remaining wait, spot/perp connection labels, both forward and reverse opening
  rates, the participating bid/ask prices and quantities, both 80% coverage
  readings, and the current wait reason in the product's existing visual style.
- pass: fake card controls are display-only and disabled; it may show
  `成交1次` for layout but never `立即成交所有`, never carries a real task id or
  actionable `data-hedge-action`, and never triggers GET/POST or timer work.
- pass: no backend, schema, API contract, dependency, service, credential, live
  gate, order, borrow, transfer, or production data is changed or contacted.
- pass: `frontend/self-check.js` gains focused regression assertions for input
  order/default/percent, fake-card running-filter isolation, explicit fake label,
  disabled/non-actionable controls, no fill-all, and the still-disabled smooth
  create path; existing assertions remain green.
- pass: `node --check frontend/self-check.js` and
  `node frontend/self-check.js` pass; raw output is saved to the allowed evidence
  file; `git diff --check` passes.
- pass: create the deterministic handoff required by the Task Handoff Evidence
  Contract, mark only this task `reported` in status revision 2, and make one
  delivery commit containing only Allowed Files; do not push.

Stop

Stop after the fake frontend preview, focused self-checks, raw evidence, handoff,
reported status, and one local delivery commit. Do not enable smooth creation,
invent backend data, start a server, use a browser against the live service,
modify the real immediate-order behavior, install dependencies, push, prepare
the CCXT task, or start/review another model.
