# P5 — Repaid interest price plan simplification

Identity:
- task_id: `P5-repaid-interest-price-plan-simplification`
- target_role: `Planner`
- target_model: `opus5`
- provider: `anthropic`
- status_revision: `11`
- required_skill: `agents/skills/task-planner.md`

Goal:
- Replace the P3 overbuilt debt-zero evidence design with the smallest plan that
  implements Human's final product rule. Do not implement.
- Human-final normal-path rule: while there is no local terminal event, all
  asset-denominated accumulated interest uses the current cached spot price
  dynamically. The only terminal event recognized by normal code is a local
  asset-card repayment submitted with the exact stored intent `amount="0"`
  (repay all) that returns the existing strict `status="succeeded"`. At that
  event, all earlier interest rows for the asset switch once to the captured
  in-memory spot bid and remain fixed. A nonzero partial repayment and every
  `pending`/`unknown`/`failed` record never freeze interest. A later re-borrow
  creates new interest rows after the prior terminal and those rows are open
  again until the next `0 + succeeded` event.
- `0 + succeeded` is an explicit Human product terminal convention, not a claim
  that the stored response proves post-repayment exchange debt is zero. Do not
  add any live balance GET or debt-evidence inference to strengthen it.
- Human-final exceptional-history rule: STORJ and similar pre-feature anomalies
  are archived by a separately authorized, backed-up, auditable direct database
  correction. The normal program must not contain a generic historical debt-zero
  inference, K-line backfill/recovery engine, cross-database coverage heuristic,
  or fallback solely for those exceptional rows. This planning task does not
  authorize the later production write.
- Same-root brake — the revised plan must copy and exhaustively scan both named
  root-cause families rather than patching only F5-F7:
  1. `根因 A：把"没有观测到"或"可以推断"当作"已被证明"。`
  2. `根因 B：在"钱已出去、终态未落库"这条缝隙上追加观测动作。`
  Enumerate every plan decision that relies on absence/inference and every action
  between repayment dispatch return and `store.resolve`, including already-fixed
  and deleted sites; give a not-applicable reason for all other reviewed sites.
- Prepare a separate P6 read-only final plan-review dispatch for
  `gpt-5.6-sol`/OpenAI. No implementation may start before P6 `ACCEPT`.

Allowed Files:
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md` (modify)
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/P6-repaid-interest-price-plan-final-review.dispatch.md` (create)
- No source, test, schema, state, project-state, database, production, commit, or
  other documentation changes.

Inputs:
- `AGENTS.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/status.json`
- `agents/roles.md` — Planner section; Reviewer section only for P6 routing
- `agents/skills/task-planner.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/P1-repaid-interest-price-plan.dispatch.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/P3-repaid-interest-price-plan-revision.dispatch.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P2-repaid-interest-price-plan-review.handoff.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P4-repaid-interest-price-plan-rereview.handoff.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`
- `backend/app/server.py` — margin repayment, PnL series, and position paths
- `backend/margin_repay/store.py`
- `backend/services/snapshot_service.py` — in-memory snapshot error behavior
- `backend/domain/snapshot.py` — spot quote shape
- `backend/ledger_flow/domain.py`
- `backend/ledger_flow/service.py`
- `backend/ledger_flow/store.py`
- `backend/tests/test_ledger_flow_domain.py`
- `backend/tests/test_ledger_flow_service.py`
- `backend/tests/test_margin_repay.py`
- `docs/api/public-market-contract.md`

Acceptance Checks:
- `pass`: The plan deletes all three `repay_after_*` columns, the signed balance
  GET, debt-zero observation, a/b/c inference, `coverage_for_window` backfill
  gate, cross-database historical inference, `--assume-debt-zero`, and generic
  historical/future K-line recovery script from product implementation scope.
- `pass`: The sole terminal predicate is exact `amount == "0" AND
  status == "succeeded"`, explicitly documented as Human convention rather than
  exchange proof. Nonzero partial and all non-success states remain dynamic;
  repeated repay-all/re-borrow intervals and identical timestamps are deterministic.
- `pass`: Between successful repayment dispatch return and `store.resolve`, the
  exhaustive action list contains only best-effort in-memory cached-price read
  and local parsing. It contains no network request, retry, sleep, cross-database
  read, or second business observation; all exceptions yield NULL price and
  `resolve` executes exactly once outside the exception boundary.
- `pass`: The stored schema is minimal: `repay_price_usdt TEXT` and
  `repay_price_source TEXT` only. The source is accurately named
  `snapshot_spot_bid_at_capture`; missing terminal price remains fail-closed and
  is not silently replaced by current/accrual/K-line price.
- `pass`: One shared domain conversion/matching authority serves both PnL curve
  and position view. It maps each interest row to the first later `0 + succeeded`
  terminal by `(settlement_ms, client_request_id)`; unmatched rows use current
  price, matched rows use stored price, and post-terminal re-borrow rows remain open.
- `pass`: Exceptional STORJ handling is explicitly outside normal code and
  scripts. The plan gives only a later operational checklist—separate Human
  authorization, database backup, independently selected historical price,
  direct row update with a distinct manual source, read-back verification, and
  audit evidence—and states that deploy/review does not authorize that write.
- `pass`: Tests are reduced to the smallest sufficient money/PnL guards: partial
  stays dynamic; `0 + succeeded` switches once and stays fixed; re-borrow reopens;
  cached-price exception still persists `succeeded` with NULL and fail-closed;
  terminal ordering/tie-break; two consumers agree; additive migration is
  idempotent. No test scaffolding exists solely for deleted inference machinery.
- `pass`: The plan contains an exhaustive same-root scan table for root A and
  root B, accounts for every P2/P4 site including deleted F5-F7 machinery, and
  the P6 packet is read-only, targets `gpt-5.6-sol`/OpenAI with one reviewer skill,
  reserves exact create-only handoff
  `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P6-repaid-interest-price-plan-final-review.handoff.md`,
  and returns to Bookkeeper `gpt-5.6-sol`/`codex`.

Stop:
- Stop after simplifying the plan and creating the P6 final plan-review packet.
  Do not edit `status.json` or `PROJECT_STATE.md`, implement, commit, send another
  terminal, access credentials, write production data, deploy, restart services,
  or perform the exceptional STORJ database correction. Return a compliant
  `[TASK_RESULT v2]` and wait for Human/Bookkeeper verification.
