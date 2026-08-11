Identity: task_id=reverse-position-drift-review-1; target_role=Reviewer; target_model=claude_glm; provider=zhipu_glm; status_revision=4; required_skill=agents/skills/code-reviewer.md

Goal

Perform a fresh, independent, cross-provider review-1 of the HIGH_RISK reverse-position drift delivery. The implementation author is Codex/OpenAI; reviewer identity is fresh `claude_glm`/Zhipu. Inspect the fixed committed range `7194876e61c037d238d0e3d621a094d7dd3a6e43..f1d929178a346026bccab8fe98d4cfa69761d8a0`, never moving HEAD or substituting a later bookkeeping commit. Review correctness, account-field semantics, Decimal/sign/finite handling, aggregation, forward regression, schema/API/docs consistency, tests, and seams. Return explicit ACCEPT or REWORK with AGENTS.md scope classification for every finding; do not implement.

Allowed Files

- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-review-1.handoff.md` — create-only reviewer handoff; Bookkeeper preflight command `test ! -e reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-review-1.handoff.md` returned exit 0 / `HANDOFF_PATH_ABSENT`; authority is the Task Handoff Evidence Contract.

Inputs

- `AGENTS.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/status.json`
- `agents/roles.md` (Reviewer section and Task Handoff Evidence Contract only)
- `agents/skills/code-reviewer.md`
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-implement.handoff.md`
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-plan-review.handoff.md`
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/10-plan.md`
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/reverse-position-drift-implement.dispatch.md`
- `backend/domain/snapshot.py`
- `backend/hedge_open_tasks/domain.py`
- `schemas/api/public-market/snapshot.schema.json`
- `backend/tests/test_private_account_v1.py`
- `backend/tests/test_positions_merge.py`
- `backend/tests/test_hedge_api.py`
- `docs/api/public-market-contract.md`

Acceptance Checks

- Verify `status.json` records base SHA `7194876e61c037d238d0e3d621a094d7dd3a6e43`, delivery SHA `f1d929178a346026bccab8fe98d4cfa69761d8a0`, revision 4, this task id, and `dispatched`; stop on any mismatch.
- Inspect raw `git diff 7194876e61c037d238d0e3d621a094d7dd3a6e43..f1d929178a346026bccab8fe98d4cfa69761d8a0`; treat stage control commits as context and the seven implementation files as the reviewed delivery. Confirm no hidden product behavior outside the approved scope.
- Verify `crossMarginLocked -> cross_margin_locked` is additive/optional, missing maps to null, schema version and frozen samples remain compatible, and totals/valuation/refresh/transport are unchanged.
- Verify reverse rows are grouped once by the existing resolved base-asset identity; only active local reverse rows participate; closed/no-task rows do not consume debt; all valid spot quantities aggregate before one account-level verdict is copied to the group.
- Verify B/F/L/local quantities require non-negative finite Decimal values, missing/blank/text/NaN/Infinity/negative inputs cause no exception or partial arithmetic, and `A=max(B-F-L,0)` neither uses float nor silently substitutes total wallet, ordinary spot, or interest.
- Verify interest is excluded; the existing `Decimal("0.01")` tolerance is reused; exactly 1% shortage is false and strictly greater is true; the documented false-negative effect matches code.
- Verify the forward branch remains behaviorally identical, including account-readability handling and strict held comparison, and reverse changes cannot alter positions API keys or frontend consumption.
- Verify the three test files cover the accepted matrix and independently run `python3 -m pytest backend/tests/test_private_account_v1.py backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py`; also run `git diff 7194876e61c037d238d0e3d621a094d7dd3a6e43..f1d929178a346026bccab8fe98d4cfa69761d8a0 --check`. Do not start services or call local/live APIs.
- Verify `docs/api/public-market-contract.md` is the appropriate live authority and accurately states locked, reverse formula, interest exclusion, tolerance boundary, invalid-data semantics, and that `drift=false` is not reconciliation proof.
- Apply Scenario Admission to reviewer-introduced hypotheticals. Classify each finding as `in-range`, `pre-existing-independent`, or `pre-existing-release-critical` with required evidence. Return ACCEPT when all blocking in-range checks pass; REWORK requires concrete findings and executable repair requirements.
- Create the deterministic handoff with immutable source report, exact fixed SHAs, commands/results, Required Reading, compliant Human Brief, explicit `评审结论`, `问题记录`, and `修复要求`; remain read-only except for that one create-only file.

Stop

Stop after the fixed-range read-only review, required tests/checks, deterministic handoff creation, and compliant `TASK_RESULT v2`. Do not edit delivery/control files, status, prior evidence, plan, dispatches, docs, or source; do not implement, commit, start/relay another model, merge, push, deploy, control services, access credentials, call live/local APIs, or perform any account action.
