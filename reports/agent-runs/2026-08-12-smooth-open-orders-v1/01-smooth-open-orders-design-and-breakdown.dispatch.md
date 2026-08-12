Identity:
- task_id: smooth-open-orders-design-and-breakdown
- target_role: Planner
- target_model: codex
- provider: openai
- status_revision: 1
- required_skill: agents/skills/task-planner.md

Goal

Turn the Human request to develop \"平滑开单\" (smooth order entry) into the
smallest safe, testable product proposal. Use the current hedge-open flow and
the CCXT Pro WebSocket assessment as context. Define the release boundary,
non-goals, observable acceptance checks, data freshness/stop conditions, and
the precise Human product decisions that cannot be inferred. Decide whether a
read-only Binance WebSocket proof of concept is a necessary first deliverable.
No implementation, execution permission, deployment, or live API action is
granted by this task.

Allowed Files

- docs/planning/smooth-open-orders-v1.md
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/

Inputs

- AGENTS.md
- PROJECT_STATE.md
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json
- agents/roles.md (Planner section)
- agents/skills/task-planner.md
- docs/planning/hedge-open-position-cycle-v1.md
- docs/planning/open-spot-usdt-transfer-2026-08-08.review-request.md
- backend/hedge_open_tasks/service.py
- backend/services/hedge_open_live_client.py
- backend/adapters/binance_public.py
- https://github.com/ccxt/ccxt/wiki/ccxt.pro.manual

Acceptance Checks

- pass: the plan names the specific observed entry-flow seams and does not claim
  that CCXT Pro abstracts Binance portfolio-margin, borrowing, transfer, or
  two-leg execution semantics.
- pass: the proposal distinguishes public market-data subscriptions from private
  order events and from order/asset execution.
- pass: every proposed order-slicing, price, depth, timeout, stale-data, and
  partial-fill rule is either a Human decision point or has a concrete current
  evidence anchor; no numeric rule is invented.
- pass: the plan states an independently testable delivery sequence and marks
  any execution-affecting task as HIGH_RISK, requiring the prescribed plan
  review and two final reviews.
- pass: no network call, order, borrow, repayment, transfer, credential access,
  service control, or source-code change is made.

Stop

Write the planning artifact and return the task result. Do not create an
implementation dispatch, change status.json, or begin a proof of concept. If
the Human decisions needed for an executable scope are unresolved, make them
explicit and stop for the Bookkeeper/Human gate.
