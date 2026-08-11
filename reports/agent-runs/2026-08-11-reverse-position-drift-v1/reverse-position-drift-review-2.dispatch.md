Identity: task_id=reverse-position-drift-review-2; target_role=Reviewer; target_model=opus5; provider=anthropic; status_revision=5; required_skill=agents/skills/reality-checker.md

Goal

Perform the final fresh, independent review-2 of the HIGH_RISK reverse-position drift delivery. Human explicitly selected Opus 5/Anthropic for this single final review and reported that frontend acceptance passed after the delivery; treat that as Human business-validation evidence, not as a substitute for technical or branch coverage. Judge the approved requirement, actual delivered effect, evidence quality, operational risk, documentation, remaining limitations, and release readiness against the fixed committed range `7194876e61c037d238d0e3d621a094d7dd3a6e43..f1d929178a346026bccab8fe98d4cfa69761d8a0`. Do not replace delivery SHA with later bookkeeping commits. Return explicit ACCEPT or REWORK; do not implement or authorize merge/deployment/live actions.

Allowed Files

- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-review-2.handoff.md` — create-only reviewer handoff; Bookkeeper preflight command `test ! -e reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-review-2.handoff.md` returned exit 0 / `HANDOFF_PATH_ABSENT`; authority is the Task Handoff Evidence Contract.

Inputs

- `AGENTS.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/status.json`
- `agents/roles.md` (Reviewer section and Task Handoff Evidence Contract only)
- `agents/skills/reality-checker.md`
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-review-1.handoff.md`
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-implement.handoff.md`
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-plan-review.handoff.md`
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/10-plan.md`
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/reverse-position-drift-implement.dispatch.md`
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/reverse-position-drift-review-1.dispatch.md`
- `backend/domain/snapshot.py`
- `backend/hedge_open_tasks/domain.py`
- `schemas/api/public-market/snapshot.schema.json`
- `backend/tests/test_private_account_v1.py`
- `backend/tests/test_positions_merge.py`
- `backend/tests/test_hedge_api.py`
- `docs/api/public-market-contract.md`

Acceptance Checks

- Verify status revision 5, task id/state, base SHA `7194876e61c037d238d0e3d621a094d7dd3a6e43`, delivery SHA `f1d929178a346026bccab8fe98d4cfa69761d8a0`, Opus 5/Anthropic routing, and clean fixed-range identity; stop on mismatch.
- Inspect raw `git diff 7194876e61c037d238d0e3d621a094d7dd3a6e43..f1d929178a346026bccab8fe98d4cfa69761d8a0`; separate stage control context from the seven-file delivery and judge the actual effect rather than summaries alone.
- Decide whether the delivery satisfies the Human-approved outcome: a reverse position whose borrowed base asset has been sold is no longer falsely marked inconsistent merely because unified free is zero, while borrowed-but-unsold, locked/pending, partial shortage, and strictly-over-1% shortage still alert when evidence is valid.
- Confirm forward behavior and positions API/frontend wire remain unchanged, and that this delivery cannot send orders, borrow, repay, transfer, change gates, mutate runtime data, access credentials, deploy, or control services.
- Evaluate the evidence stack: accepted cross-provider plan review, Bookkeeper-verified single delivery, accepted cross-provider review-1, three independent 224-test runs, fixed-range diff checks, schema/API contract tests, and Human-reported frontend acceptance. State explicitly what the Human validation proves and does not prove.
- Evaluate remaining behavior honestly: account-asset aggregation does not allocate debt to cycles; exactly/under 1% shortage can be hidden by the existing tolerance; invalid/unavailable data yields `drift=false`; therefore `drift=false` remains a weak “no proven alert” signal, never reconciliation proof.
- Verify `A=max(B-F-L,0)`, interest exclusion, non-negative finite Decimal validation, active-row aggregation, closed/no-task exclusion, and additive optional locked projection all match the documented live contract and the actual code/tests.
- Confirm the open `PROJECT_STATE.md` reverse automatic-close combination-margin risk is unrelated and remains unresolved; this display fix must not claim to make reverse closing safe or alter its temporary operating boundary.
- Independently run `python3 -m pytest backend/tests/test_private_account_v1.py backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py` and `git diff 7194876e61c037d238d0e3d621a094d7dd3a6e43..f1d929178a346026bccab8fe98d4cfa69761d8a0 --check`; do not start services or call local/live APIs.
- Apply Scenario Admission to reviewer-introduced hypotheticals. Classify every finding per AGENTS.md as `in-range`, `pre-existing-independent`, or `pre-existing-release-critical` with required evidence. ACCEPT requires all in-range release checks to pass; REWORK requires concrete findings and executable repair requirements.
- Create the deterministic handoff with immutable source report, exact fixed SHAs, commands/results, Human-validation interpretation, remaining risks/limits, release-readiness verdict, Required Reading, compliant Human Brief, and explicit `评审结论`, `问题记录`, and `修复要求`; remain read-only except for that one create-only file.

Stop

Stop after the fixed-range review-2, required tests/checks, deterministic handoff creation, and compliant `TASK_RESULT v2`. Do not edit delivery/control files, status, prior evidence, plan, dispatches, docs, or source; do not implement, commit, start/relay another model, merge, push, deploy, restart/control services, access credentials, call live/local APIs, or perform any account action. ACCEPT is review closure only and does not replace final Human acceptance or authorize merge/deployment/live operation.
