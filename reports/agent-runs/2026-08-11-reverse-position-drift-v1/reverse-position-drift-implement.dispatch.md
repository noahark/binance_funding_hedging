Identity: task_id=reverse-position-drift-implement; target_role=Implementer; target_model=codex; provider=openai; status_revision=3; required_skill=agents/skills/senior-developer.md

Goal

Implement the accepted minimal backend-only fix for reverse-position drift. Human explicitly selected a fresh Codex Implementer for this fast fix. Add the existing raw unified-account `crossMarginLocked` field to the published private-account projection, then make reverse drift compare the account-asset aggregate of active local reverse spot quantity with `A=max(B-F-L,0)`, where B is borrow principal, F is unified free, L is unified locked, and interest is excluded. Preserve forward drift behavior exactly. This changes display/validation meaning only: do not touch orders, borrowing, repayment, transfer, preflight, gates, credentials, service control, deployment, live APIs, or runtime data. Commit only the dispatch-approved delivery after tests; create the deterministic handoff with `delivery_sha: pending`; move only this task's status state from `dispatched` to `reported`.

Allowed Files

- `backend/domain/snapshot.py`
- `backend/hedge_open_tasks/domain.py`
- `schemas/api/public-market/snapshot.schema.json`
- `backend/tests/test_private_account_v1.py`
- `backend/tests/test_positions_merge.py`
- `backend/tests/test_hedge_api.py`
- `docs/api/public-market-contract.md`
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-implement.handoff.md` — create-only task handoff; Bookkeeper preflight command `test ! -e reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-implement.handoff.md` returned exit 0 / `HANDOFF_PATH_ABSENT`; authority is the Task Handoff Evidence Contract.
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/status.json` — may change only `current_task.state` from `dispatched` to `reported` after the handoff and delivery are ready.

Inputs

- `AGENTS.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/status.json`
- `agents/roles.md` (Implementer section and Task Handoff Evidence Contract only)
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-plan-review.handoff.md`
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/10-plan.md`
- `backend/domain/snapshot.py` (private-account unified projection only)
- `backend/hedge_open_tasks/domain.py` (position merge/drift seams only)
- `schemas/api/public-market/snapshot.schema.json` (`private_account.balances_unified` only)
- `backend/tests/test_private_account_v1.py` (unified projection/schema tests only)
- `backend/tests/test_positions_merge.py`
- `backend/tests/test_hedge_api.py` (positions contract tests only)
- `docs/api/public-market-contract.md` (unified-balance and hedge-position drift sections only)

Acceptance Checks

- Modify no product, test, schema, or live-doc file outside the seven named delivery files; the handoff and the single allowed status state transition are control artifacts, not expanded product scope.
- Map raw `crossMarginLocked` to additive `cross_margin_locked` on every assembled unified row; absent upstream input becomes `None`; do not change valuation, totals, warnings, ordering, refresh, or transport behavior.
- Declare optional `cross_margin_locked` in the existing snapshot schema as decimal string or null without changing schema version or breaking frozen older samples.
- For each resolved base asset, aggregate all active local `direction=reverse` rows with valid non-negative finite Decimal `spot_qty`; exclude closed and `no_task` rows; consume account-level borrowed/free/locked once; compute `A=max(B-F-L,0)` and apply one verdict back to the group.
- Reject missing, blank, unparsable, non-finite, or negative B/F/L/spot inputs without exceptions or partial arithmetic; the affected reverse group stays `drift=false`, meaning no provable alert rather than proven consistency. Do not use `totalWalletBalance`, ordinary spot balance, or interest as a substitute.
- Exclude `crossMarginInterest` and local `borrow_interest` from the quantity formula. Reuse `_EXPOSURE_IMBALANCE_TOLERANCE = Decimal("0.01")`; exactly 1% shortage is not drift and strictly more than 1% is drift. Do not add another tolerance constant or use float.
- Preserve the existing forward branch behaviorally unchanged: regular spot free+locked plus unified total balance, current account-readability handling, and strict `held < recorded_spot`; reverse fields and tolerance must not affect it.
- Add the accepted test matrix across the three named test files: JST borrowed-and-sold, borrowed-unsold, locked/pending, partial fill, 1% boundary, interest growth, same-asset multiple reverse rows, forward regression, missing/blank/text/NaN/Infinity/negative fields, account unreadable, snapshot/schema projection, and positions API key/wire behavior.
- Run `python3 -m pytest backend/tests/test_private_account_v1.py backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py` and `git diff --check`; both must pass. Do not start a service or call any local/live API.
- Update only the relevant live API contract sections with the additive locked field, reverse account-asset formula, interest exclusion, 1% boundary/false-negative effect, invalid-data behavior, and the fact that `drift=false` is not proof of reconciliation.
- Create `reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-implement.handoff.md` before the delivery commit, following the Task Handoff Evidence Contract with `delivery_sha: pending`, exact changed paths, commands/results, Required Reading for the Next Task, and a compliant Human Brief. Commit all approved delivery/control files in one non-amended commit, then change only `current_task.state` to `reported` as part of that commit.

Stop

Stop after the bounded implementation, required tests, deterministic handoff, one delivery commit, the allowed `reported` state transition, and the compliant `TASK_RESULT v2`. Do not implement outside scope, edit prior plan/review artifacts, start or relay a reviewer, review your own delivery, change `delivery_sha` or routing, merge, push, deploy, restart/control services, access credentials, call live/local APIs, or perform any account action.
