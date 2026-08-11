Identity: task_id=reverse-position-drift-plan; target_role=Planner; target_model=codex; provider=openai; status_revision=1; required_skill=agents/skills/task-planner.md

Goal

Produce the smallest implementation-ready plan for the observed reverse-position drift defect: after a reverse open borrows and sells the base asset, unified-account spot free balance can be zero while the borrow principal remains positive, and the position table incorrectly marks the local record as inconsistent. Keep this delivery display/validation-only: no order, borrow, repay, transfer, gate, credential, deployment, service-control, or live-account action. Treat the task as HIGH_RISK because it changes position and borrowing meaning. Prepare an independent cross-provider plan-review dispatch for Kimi; do not implement.

Allowed Files

- reports/agent-runs/2026-08-11-reverse-position-drift-v1/10-plan.md
- reports/agent-runs/2026-08-11-reverse-position-drift-v1/reverse-position-drift-plan-review.dispatch.md

Inputs

- AGENTS.md
- reports/agent-runs/ACTIVE.json
- PROJECT_STATE.md
- reports/agent-runs/2026-08-11-reverse-position-drift-v1/status.json
- agents/roles.md (Planner section only)
- agents/skills/task-planner.md
- backend/services/private_client.py
- backend/services/snapshot_service.py
- backend/domain/snapshot.py
- backend/hedge_open_tasks/domain.py
- backend/app/server.py
- schemas/api/public-market/snapshot.schema.json
- backend/tests/test_private_account_v1.py
- backend/tests/test_positions_merge.py
- backend/tests/test_hedge_api.py
- frontend/index.html (read only the snapshot ingestion and position drift display seams)
- docs/api/public-market-contract.md (read only the private-account unified-balance and hedge-position field sections)

Acceptance Checks

- The plan traces the current raw `crossMarginBorrowed` / `crossMarginFree` / `crossMarginLocked` path through snapshot assembly, position merging, API output, and the unchanged frontend drift consumer, with concrete code anchors.
- The release boundary is backend-only unless current evidence proves a frontend change is required; it explicitly excludes order execution, borrowing, repayment, transfer, preflight, gates, credentials, deployment, service control, and live API calls.
- The plan defines one authoritative reverse actual-spot-exposure formula. Borrow interest is excluded from opening-position quantity comparison. It must distinguish “borrowed and sold” from “borrowed but still free or locked”; if current account fields cannot prove that distinction, the plan stops with the exact missing evidence instead of guessing.
- Forward positions retain their current spot-balance comparison unchanged.
- The plan specifies account-level aggregation for multiple local reverse rows sharing one base asset, missing/invalid-field fail-closed behavior, sign handling, quantity precision/tolerance, and why each rule matches the current domain representation.
- The executable test matrix includes at least: JST-style borrowed-and-sold (`free=0`, `locked=0`), borrowed-but-unsold, locked/pending sell, partial quantity, interest growth, multiple same-asset rows, forward regression, and missing/invalid upstream fields.
- The plan names the minimal production, schema, test, and live-doc files that implementation may modify; it adds no abstraction, dependency, compatibility layer, new endpoint, state, or recovery workflow.
- `reverse-position-drift-plan-review.dispatch.md` targets a fresh Kimi read-only plan review, records provider `moonshot`, uses zero or one existing reviewer skill, and requires an explicit ACCEPT/REWORK verdict against this HIGH_RISK plan before any implementation dispatch.

Stop

Stop after writing the plan and plan-review dispatch. Do not modify product code, tests, schemas, canonical docs, ACTIVE.json, PROJECT_STATE.md, or status.json. Do not run live services or APIs, commit, implement, review your own plan, or start/relay the next formal workflow terminal.
