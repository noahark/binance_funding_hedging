# P7 — Repaid interest price plan contract repair

Identity:
- task_id: `P7-repaid-interest-price-plan-contract-repair`
- target_role: `Planner`
- target_model: `opus5`
- provider: `anthropic`
- status_revision: `13`
- required_skill: `agents/skills/task-planner.md`

Goal:
- Apply the single bounded F1 repair from P6 `REWORK` to the fixed P5 plan.
  Do not redesign the accepted architecture and do not implement.
- Preserve Human's fixed product rule and every accepted P6 result
  R1-R3/R5/R7-R9. This task only makes the price-source control contract
  internally consistent and corrects one zero-string description.

Allowed Files:
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md` (modify)
- No review packet, source, test, schema, state, project-state, evidence,
  database, production, commit, or other documentation changes.

Inputs:
- `AGENTS.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/status.json`
- `agents/roles.md` — Planner section only
- `agents/skills/task-planner.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P6-repaid-interest-price-plan-final-review.handoff.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/P6-repaid-interest-price-plan-final-review.dispatch.md`
- `backend/services/snapshot_service.py`
- `backend/domain/snapshot.py`
- `backend/app/server.py`
- `docs/api/public-market-contract.md`

Acceptance Checks:
- `pass`: Every statement that says `fresh` has no time meaning is replaced
  with the source-provable contract: the quote cache age is
  `< 2 * cache_ttl_seconds` and all four prices are valid; it may still lag the
  actual repayment event and is not an exchange repayment execution rate.
- `pass`: `repay_price_source` has one consistent TEXT-field contract. The
  normal automatic write path writes only `snapshot_spot_bid_at_capture` or
  NULL; a separately Human-authorized historical correction may write the
  auditable distinct value `manual_correction`. The plan explicitly forbids a
  database CHECK or closed enum that would reject that manual value.
- `pass`: The zero-string wording states that the normal API rejects `"0.0"`,
  `"0.00"`, and `"00"`; if an anomalous legacy database row contains such a
  value, the pure matcher treats it as non-terminal. The exact terminal
  predicate and T9 conclusion remain unchanged.
- `pass`: The repair is limited to the three F1 wording sites and any directly
  duplicated control wording needed for internal consistency. No schema,
  algorithm, file boundary, test mechanism, operational step, fallback, or
  same-root scan topology changes.
- `pass`: R1-R3/R5/R7-R9 remain satisfied, including A9 as a Human normative
  terminal rather than proof, the one-action repayment gap, fail-closed
  behavior, the shared conversion authority, and STORJ outside normal code.
- `pass`: The plan records this as the bounded P7 contract repair and states
  that Bookkeeper will seal a new fixed commit and prepare a new independent
  plan rereview before any implementation dispatch.

Stop:
- Stop after modifying only the plan. Do not create the next review packet,
  edit `status.json` or `PROJECT_STATE.md`, implement, commit, send another
  terminal, access credentials, write production data, deploy, restart, or
  perform the exceptional STORJ database correction. Return a compliant
  `[TASK_RESULT v2]` and wait for Human/Bookkeeper verification.
