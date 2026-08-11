Identity: task_id=reverse-position-drift-plan-review; target_role=Reviewer; target_model=kimi; provider=moonshot; status_revision=2; required_skill=none

Goal

Perform a fresh, independent, cross-provider, read-only plan review of the HIGH_RISK reverse-position drift fix before any implementation dispatch. Decide whether `10-plan.md` is the smallest implementation-ready plan supported by the current code and account-field evidence. Verify in particular that its authoritative reverse actual-spot-exposure formula distinguishes borrowed-and-sold from borrowed-but-still-free-or-locked, excludes interest, aggregates multiple local reverse rows at account-asset level, preserves forward behavior, and fails closed without fabricating consistency or inconsistency. Return an explicit ACCEPT or REWORK verdict to the Planner/Bookkeeper path; do not implement.

- stage_id: `2026-08-11-reverse-position-drift-v1`
- current_task.id: `reverse-position-drift-plan-review`
- current_task.state: `dispatched`
- status revision: `2`
- target model/provider: fresh Kimi / moonshot

Stop immediately if the active stage, task, state, status revision, target model/provider, or repository revision recorded by Bookkeeper differs. This prepared packet does not authorize its own start; Human starts it only after Bookkeeper verification and routing.

Allowed Files

- Create only: `reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-plan-review.handoff.md`

Inputs

- `AGENTS.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/status.json`
- `agents/roles.md` (Reviewer section and the Task Handoff Evidence Contract only)
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/10-plan.md`
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/reverse-position-drift-plan.dispatch.md`
- `backend/services/private_client.py` (unified-balance fetch only)
- `backend/services/snapshot_service.py` (private-account refresh/assembly seams only)
- `backend/domain/snapshot.py` (private-account unified-balance projection only)
- `backend/hedge_open_tasks/domain.py` (position merge/drift only)
- `backend/app/server.py` (`GET /api/hedge-open-positions` composition/output only)
- `schemas/api/public-market/snapshot.schema.json` (`private_account.balances_unified` only)
- `backend/tests/test_private_account_v1.py` (unified-balance projection/schema tests only)
- `backend/tests/test_positions_merge.py`
- `backend/tests/test_hedge_api.py` (positions contract tests only)
- `frontend/index.html` (snapshot ingestion and position drift display seams only)
- `docs/api/public-market-contract.md` (private-account unified-balance and hedge-position field sections only)

Acceptance Checks

- Trace all three raw fields `crossMarginBorrowed` / `crossMarginFree` / `crossMarginLocked` from the existing raw `/papi/v1/balance` response through the proposed snapshot projection, pure position merge, unchanged server output, and unchanged frontend `p.drift` consumer. Identify any unsupported hop or claim.
- Decide whether the repository evidence supports `A=max(B-F-L,0)` as “borrowed and sold” while keeping `crossMarginInterest` / `borrow_interest` out of opening quantity. If it does not, return REWORK naming the exact missing evidence; do not substitute `totalWalletBalance`, ordinary spot holdings, or a hypothetical field.
- Verify the 1% Decimal comparison reuses the existing domain tolerance, states its boundary and false-negative effect, introduces no float/sign error, and cannot turn missing/invalid/negative/non-finite input into a numeric zero.
- Verify multiple active local reverse rows resolving to one base asset are summed once before comparing with the account-level actual exposure; no-task/closed rows are not consumed and account borrow is not allocated or double-counted by cycle.
- Verify the forward path remains behaviorally identical, including its current account readability handling and strict `held < recorded_spot` comparison.
- Verify the proposed production change is limited to `backend/domain/snapshot.py` and `backend/hedge_open_tasks/domain.py`; the schema, three named tests, and live API document are sufficient; private client, refresh service, server, and frontend remain unchanged.
- Verify the executable matrix covers borrowed-and-sold, borrowed-unsold, locked/pending, partial, tolerance boundary, interest growth, same-asset multiple rows, forward regression, missing/invalid fields, and API wire behavior.
- Apply `AGENTS.md` Scenario Admission to any reviewer-introduced hypothetical. This plan review does not increment `rework_count`.
- The handoff source report must state one explicit `评审结论: ACCEPT（接受）` or `评审结论: REWORK（返工）`. REWORK must include concrete findings and executable plan-repair requirements in the same handoff file; ambiguous or missing closure is non-accepting.
- Create the deterministic handoff at `reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-plan-review.handoff.md` following the Task Handoff Evidence Contract. Do not edit it after ending the task.
- Return a compliant `[TASK_RESULT v2]` whose `产物` lists that handoff path and whose final three review lines are `评审结论`, `问题记录`, and `修复要求` with explicit values.
- As a Reviewer, remain read-only except for the one create-only handoff file. Do not modify plan, code, tests, schema, docs, state, dispatches, ACTIVE.json, or PROJECT_STATE.md.

Stop

Stop after the read-only plan review, deterministic handoff creation, and explicit verdict. Do not implement, edit the plan, run live services/APIs, commit, change status, start/relay another formal workflow terminal, merge, deploy, or perform any account action.
