# P10 — Repaid interest price implementation

Identity:
- task_id: `P10-repaid-interest-price-implementation`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `16`
- required_skill: `agents/skills/senior-developer.md`

Goal:
- Implement the Human-approved plan fixed at
  `e37d45a29017c739118018cab9f250e74a1155e5` with the smallest sufficient
  change. Human explicitly waived the remaining plan-rereview loop and
  authorized development to start; this does not authorize deployment,
  production database writes, or the exceptional STORJ correction.
- Product rule: before a local terminal event, asset-denominated accumulated
  interest uses the current cached spot price dynamically. The only normal-code
  terminal event is exact stored `amount == "0"` plus strict
  `status == "succeeded"`; at that event, earlier interest uses the captured
  in-memory spot bid permanently. Partial/non-success records do not freeze;
  post-terminal re-borrowed interest is dynamic until the next terminal.
- Keep the implementation boring and local. Reuse current Decimal, SQLite,
  snapshot, fail-closed, and PnL paths. Do not add a debt-zero query, K-line
  backfill, historical inference, new script, dependency, abstraction layer,
  frontend change, retry, sleep, or second observation.

Allowed Files:
- `backend/margin_repay/store.py`
- `backend/app/server.py`
- `backend/ledger_flow/domain.py`
- `backend/ledger_flow/service.py`
- `backend/tests/test_ledger_flow_domain.py`
- `backend/tests/test_ledger_flow_service.py`
- `backend/tests/test_margin_repay.py`
- `docs/api/public-market-contract.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P10-repaid-interest-price-implementation.handoff.md` (create only)
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/status.json` only for the
  Implementer-authorized final transition of this task from `dispatched` to
  `reported`; no other field may change and that status-only change is not part
  of the delivery commit.
- No other file may change. In particular no frontend, script, schema file,
  project-state, stage packet, dependency, database, or production change.

Inputs:
- `AGENTS.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/status.json`
- `agents/roles.md` — Implementer section and Task Handoff Evidence Contract
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P6-repaid-interest-price-plan-final-review.handoff.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P8-repaid-interest-price-plan-contract-rereview.handoff.md`
- all eight implementation files listed under Allowed Files
- `backend/services/snapshot_service.py`
- `backend/domain/snapshot.py`
- `backend/services/hedge_open_live_client.py`

Acceptance Checks:
- `pass`: `margin_repay` has only two new nullable TEXT columns,
  `repay_price_usdt` and `repay_price_source`, added idempotently for old and
  new databases. `resolve()` accepts optional values, row documents expose
  them, and `list_records()` returns deterministic full records including
  `updated_at_us`. No CHECK/closed source enum is added.
- `pass`: After repayment dispatch returns, price capture runs only for exact
  `amount == "0"` and strict succeeded resolution. The entire in-memory
  snapshot read/parse is one best-effort exception boundary with no network,
  retry, sleep, cross-database read, or second observation; failure yields both
  price fields NULL. `store.resolve()` remains outside that boundary and is
  called exactly once regardless of capture outcome.
- `pass`: One pure domain authority implements terminal detection, settlement
  time (`update_time`, then `updated_at_us // 1000`), deterministic
  `(settlement_ms, client_request_id)` ordering, first terminal at or after each
  accrual, and Decimal conversion. Open rows use current price; matched rows use
  stored price; missing applicable price is fail-closed; USDT and true zero keep
  existing behavior.
- `pass`: Both the PnL curve and position view use that shared authority. They
  agree exactly for identical inputs, do not partially add an asset with any
  unpriced row, and leave `close_log`, the existing net-PnL formula, frontend
  wire shape, and coin-denominated interest totals unchanged.
- `pass`: Tests cover the plan's T1-T10: partial remains dynamic; terminal
  switches once and is stable; re-borrow reopens; capture exception still
  persists succeeded with NULL and one resolve; missing terminal price is
  fail-closed; ordering/tie-break and timestamp fallback; two-consumer equality;
  additive migration idempotence; exact zero-string matcher boundary; and
  non-terminal paths never call price capture.
- `pass`: API documentation states the Human terminal convention is not proof
  of exchange debt zero, documents dynamic-versus-fixed valuation, both new
  fields, automatic `snapshot_spot_bid_at_capture`, separately authorized
  `manual_correction`, fail-closed behavior, and parameterized freshness. It
  may mention the code default TTL but must not present default 120 seconds as
  an unconditional runtime guarantee.
- `pass`: Exact checks pass:
  `python -m pytest backend/tests/test_ledger_flow_domain.py backend/tests/test_ledger_flow_service.py backend/tests/test_margin_repay.py -q`;
  `python -m pytest backend/tests -q`;
  `node frontend/self-check.js`;
  `git diff --check`.
  If an unrelated pre-existing full-suite failure occurs, preserve raw output,
  prove it is outside this delivery, and do not modify unrelated files.
- `pass`: Create the deterministic handoff after preflight confirms it is
  absent, with `delivery_sha: pending`; then make exactly one delivery commit
  containing only the eight implementation files actually changed plus that
  handoff. After the commit, change only this task's status state to `reported`
  without committing that status change. Return the compliant receipt from the
  handoff and send it once to `reply_to`.

Stop:
- Stop after implementation, exact tests, one delivery commit, handoff, and the
  authorized `reported` transition. Do not review your own delivery, prepare a
  reviewer packet, change any other status field, push, merge, deploy, restart,
  access credentials or production, or perform the exceptional STORJ database
  correction.

reply_to: claude
After emitting the normal console receipt, send that same receipt once to the
reply_to window per `HERDR.md`, then stop.
