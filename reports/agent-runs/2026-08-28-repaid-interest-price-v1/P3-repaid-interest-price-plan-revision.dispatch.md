# P3 — Repaid interest price plan revision

Identity:
- task_id: `P3-repaid-interest-price-plan-revision`
- target_role: `Planner`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `7`
- required_skill: `agents/skills/task-planner.md`

Goal:
- Revise the existing plan after the verified P2 `REWORK`. Preserve its smallest
  usable engineering skeleton, but resolve F1-F4 and name O1-O3. Do not implement.
- Human-fixed terminal rule: a partial repayment never freezes interest cost.
  While an asset has any outstanding borrowing/debt position, every related
  historical interest row remains an open estimate converted at the current
  price. Only a repayment event for which the asset debt is verifiably zero may
  freeze prior interest at that full-repayment event price. A later re-borrow
  starts a new open interval. Exchange capitalization of interest is not proof
  of terminal repayment.
- Human-selected F2 path A: immediately after a successful repayment response,
  attempt to capture the in-memory snapshot spot bid. The whole observation must
  be exception-isolated: `SnapshotNotReady` or any other exception becomes a
  missing price and can never skip or delay recording the repayment terminal
  result. Describe it accurately as capture-time snapshot bid, not a true Binance
  repayment exchange rate. Missing prices remain fail-closed and recover through
  the idempotent historical-kline backfill path.
- Prepare a separate P4 read-only re-review dispatch for `opus5`/Anthropic. The
  revised plan must pass that plan-review gate before implementation is prepared.

Allowed Files:
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md` (modify)
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/P4-repaid-interest-price-plan-rereview.dispatch.md` (create)
- No source, test, schema, state, project-state, database, production, commit, or
  other documentation changes.

Inputs:
- `AGENTS.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/status.json`
- `agents/roles.md` — Planner section; Reviewer section only for P4 routing
- `agents/skills/task-planner.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/P1-repaid-interest-price-plan.dispatch.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P2-repaid-interest-price-plan-review.handoff.md`
- `backend/app/server.py` — margin repayment, PnL series, and position paths
- `backend/margin_repay/store.py`
- `backend/services/hedge_open_live_client.py` — repayment response contract
- `backend/services/snapshot_service.py` — snapshot readiness/error behavior
- `backend/domain/snapshot.py` — quote freshness and debt/balance fields
- `backend/ledger_flow/domain.py`
- `backend/ledger_flow/service.py`
- `backend/ledger_flow/store.py`
- `backend/tests/test_ledger_flow_domain.py`
- `backend/tests/test_ledger_flow_service.py`
- `backend/tests/test_margin_repay.py`
- `docs/api/public-market-contract.md`

Acceptance Checks:
- `pass`: F1 is corrected: the plan calls the SNX/INJ behavior capitalization,
  not settlement, and no longer treats any `succeeded`, `amount="0"`, missing
  `repaid_amount`, or partial repayment as proof of full repayment.
- `pass`: The plan defines one exact, auditable source and stored evidence for
  "debt verifiably zero" for future events and a fail-closed rule when that
  evidence is unavailable. It handles partial repayment, repeated borrow/full-
  repay/re-borrow intervals, `unknown`/`failed`, identical timestamps, and
  historical rows including STORJ without inventing a close-order relationship.
- `pass`: Until a verified-zero terminal exists, all related interest rows use
  current price dynamically; at the verified full-repayment event they switch
  once to its stored price and remain stable. Tests explicitly prove partial
  repayment does not switch, full repayment switches once, and re-borrowed rows
  are open again.
- `pass`: F2 path A is made executable: all snapshot access/parsing is inside a
  best-effort exception boundary, repayment `store.resolve` remains guaranteed,
  price failure yields `succeeded` plus NULL price, and an executable test makes
  snapshot access raise while asserting the terminal status still persists.
- `pass`: F3/F4 are resolved: the read shape actually exposes the fallback time
  field (or one derived settlement field), and source naming distinguishes
  capture-time snapshot bid from historical 1m K-line evidence. No source is
  described more strongly than the code can prove.
- `pass`: Schema, matching/index authority, both PnL consumers, migration,
  idempotent NULL-only backfill, rollback, and fail-closed behavior are updated
  consistently. The plan names how a future NULL capture is recovered without
  retrying or compromising the repayment request.
- `pass`: O1-O3 are named: local repayment records do not cover exchange-side
  manual/automatic repayments; production backfill includes container/database
  access and pre-write SQLite backup; any one unpriced asset globally hides net
  profit. Scope expansion is rejected unless backed by current evidence.
- `pass`: The P4 packet is read-only, targets `opus5`/Anthropic with at most one
  reviewer skill, reviews all P2 findings and Human decisions, reserves the exact
  create-only handoff path
  `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P4-repaid-interest-price-plan-rereview.handoff.md`,
  and returns to Bookkeeper `gpt-5.6-sol`/`codex`.

Stop:
- Stop after revising the plan and creating the P4 re-review packet. Do not edit
  `status.json` or `PROJECT_STATE.md`, implement, commit, send another terminal,
  access credentials, write production data, deploy, or restart services. Return
  a compliant `[TASK_RESULT v2]` and wait for Human/Bookkeeper verification.
