# P1 — Repaid interest price plan

Identity:
- task_id: `P1-repaid-interest-price-plan`
- target_role: `Planner`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `2`
- required_skill: `agents/skills/task-planner.md`

Goal:
- Produce the smallest implementable plan for fixing historical margin-interest
  USDT conversion. Human-approved product direction: interest that has a later
  successful repayment uses a price fixed at that repayment; interest without a
  matched successful repayment remains an open-loan estimate using the current
  price. The plan must resolve, rather than assume, the matching and price
  evidence needed to make this deterministic and auditable.
- Human explicitly rejected freezing every interest row at its accrual-time
  price. While borrowing remains unsettled, its USDT cost must move with the
  current price. A repayment is the terminal settlement event: the settled
  interest switches once to the repayment-time price and remains fixed after
  that. The one-time historical change at repayment is intended product
  behavior, not an instability to eliminate.
- Preserve fail-closed behavior: no reliable applicable price means net profit
  remains unavailable. Do not fabricate a close-order relationship for assets
  such as STORJ that have borrowing and repayment records but no hedge cycle.
- Prepare a separate pre-implementation plan-review dispatch for `opus5`
  (`anthropic`) after the plan artifact is complete. Do not implement.

Allowed Files:
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md` (create)
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/P2-repaid-interest-price-plan-review.dispatch.md` (create)
- No source, test, schema, state, project-state, documentation, database, or production changes.

Inputs:
- `AGENTS.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/status.json`
- `agents/roles.md` — read only the Planner section; use the Reviewer section only to prepare the plan-review routing
- `agents/skills/task-planner.md`
- `backend/app/server.py` — `_handle_pnl_series` and `_hedge_open_positions`
- `backend/ledger_flow/domain.py` — `build_pnl_series`
- `backend/ledger_flow/service.py` — `sum_interest_by_asset`
- `backend/ledger_flow/store.py` — interest row storage/query shape
- `backend/margin_repay/store.py`
- `backend/tests/test_ledger_flow_domain.py`
- `backend/tests/test_margin_repay.py`
- `frontend/self-check.js` — existing PnL incomplete/display checks only
- `docs/api/public-market-contract.md` — current ledger, repayment, and PnL contracts

Current verified evidence and fixed premises:
- Production `interest_rows` has one STORJ `ON_BORROW` row: principal `200`,
  interest `0.0130242`, accrued `2026-08-20 14:00:00 CST`.
- Production `margin_repay` has STORJ `amount=0`, `status=succeeded`,
  `update_time=2026-08-20 14:31:03.837 CST`.
- Production has no STORJ hedge task, hedge cycle, or close order. A design that
  requires a close order does not solve the observed defect.
- Current code converts every non-zero asset-denominated interest amount using
  the current public snapshot spot bid. It does not distinguish repaid from open
  borrowing; the PnL curve consumes all interest rows in its window.
- `margin_repay` currently stores no repayment-time price and has no direct
  foreign key to `interest_rows`.
- Anthropic Claude's informal consultation recommended accrual-time freezing;
  Human rejected that alternative on 2026-08-28. It is not an allowed default
  or fallback. The plan may cite its technical observations, but must implement
  the Human-approved open-dynamic / repaid-terminal model.
- Human selected Bookkeeper `gpt-5.6-sol`, label `codex`. Planned formal routing:
  pre-development plan review by `opus5`/Anthropic; implementation by
  `claude_glm`/Zhipu; final Review-1 by Grok 4.6/XAI and Review-2 by
  `opus5`/Anthropic against the same delivery SHA, prepared to run concurrently.

Acceptance Checks:
- `pass`: Plan states an exact deterministic rule mapping each interest row to
  a successful repayment or to the still-open bucket, including repeated and
  partial repayments; it does not silently equate `amount=0`, missing
  `repaid_amount`, or `unknown` with a fact not supported by the stored record.
- `pass`: Plan selects one authoritative repayment-time price definition and
  identifies how future successful repayments capture it and how existing rows,
  including STORJ, obtain auditable historical evidence. It names what happens
  when the price cannot be obtained.
- `pass`: Plan keeps historical converted costs stable after repayment and keeps
  open borrowing explicitly estimated from the current price. It explicitly
  treats the one-time change at repayment as the transition from estimate to
  terminal cost; both the positions view and PnL curve use one detailed authority
  rather than independent algorithms.
- `pass`: Plan names the minimal schema/data migration, backfill, idempotency,
  rollback, and production verification steps. No live write is authorized by
  this planning task.
- `pass`: Plan gives bounded source/test/documentation file lists and executable
  tests for matching, partial repayment, repeated loans, missing/unknown/failed
  repayment, missing price, historical stability, STORJ, and unchanged open-loan
  behavior. It rejects speculative abstractions.
- `pass`: Tests prove an unsettled interest row changes when current price
  changes, then switches exactly once to the matched repayment-time price and
  remains unchanged across later current-price changes.
- `pass`: The prepared plan-review dispatch is read-only, targets `opus5`
  (`anthropic`), uses at most one required reviewer skill, names the fixed plan
  artifact and raw evidence, and returns to Bookkeeper `gpt-5.6-sol` / `codex`.
- `pass`: No product source, test, schema, state, database, production, or live
  documentation is modified.

Stop:
- Stop after creating the plan artifact and the pre-implementation plan-review
  dispatch. Do not edit `status.json`, implement, commit, send another terminal,
  access credentials, write production data, deploy, or restart services.
