# P8 — Repaid interest price plan contract rereview

Identity:
- task_id: `P8-repaid-interest-price-plan-contract-rereview`
- target_role: `Reviewer / Plan Review (pre-implementation)`
- target_model: `gpt-5.6-sol`
- provider: `openai`
- status_revision: `14`
- required_skill: `agents/skills/software-architect.md`

Goal:
- Independently rereview the bounded P7 repair of P6 F1. Confirm the three
  control-text corrections are complete and that accepted P6 results
  R1-R3/R5/R7-R9 did not regress. Do not redesign the plan or review
  implementation; no implementation exists yet.
- This is a narrow rereview, but an explicit `ACCEPT` is still required before
  Bookkeeper may prepare the `claude_glm` implementation dispatch.

Allowed Files:
- Reviewer is read-only except for creating exactly one handoff at the
  preflight-absent path:
  `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P8-repaid-interest-price-plan-contract-rereview.handoff.md`
- Preflight command:
  `test ! -e reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P8-repaid-interest-price-plan-contract-rereview.handoff.md`
  returned success before dispatch. The path is create-only under the Task
  Handoff Evidence Contract in `agents/roles.md`.
- No edits to the plan, status, project state, source, tests, schema, database,
  production, commits, or any other file. No deployment or terminal send.

Inputs:
- `AGENTS.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/status.json`
- `agents/roles.md` — Reviewer section and Task Handoff Evidence Contract only
- `agents/skills/software-architect.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/P8-repaid-interest-price-plan-contract-rereview.dispatch.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P6-repaid-interest-price-plan-final-review.handoff.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/P7-repaid-interest-price-plan-contract-repair.dispatch.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`
- `backend/config.py`
- `backend/services/snapshot_service.py`
- `backend/domain/snapshot.py`
- `backend/app/server.py`
- `docs/api/public-market-contract.md`

Acceptance Checks:
- `pass`: Git verifies the fixed range
  `db680957151e17ad9703e1889bcf6571d4ecd812..34ad78db1929716d5860067821b6b349500ac6e7`
  and that it changes only
  `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`
  by the bounded P7 contract repair. Review that committed range, not moving
  `HEAD` or an uncommitted worktree.
- `pass`: The active `fresh` contract says the cache age is
  `< 2 * configured cache_ttl_seconds` and all four normalized prices are
  non-NULL; it may lag the repayment event and is not an exchange execution
  rate. Independently check whether the plan's `60`/`120` wording is clearly a
  code default rather than an unproved runtime constant.
- `pass`: `repay_price_source` has one consistent storage/writer contract:
  free nullable TEXT with no database CHECK or closed-enum enforcement; the
  normal automatic writer emits `snapshot_spot_bid_at_capture` or NULL, while
  the separately authorized historical correction uses the distinguishable
  auditable value `manual_correction`. Decide whether any wording allowing
  future manual labels weakens the two current documented source meanings.
- `pass`: Normal API rejection of `"0.0"`, `"0.00"`, and `"00"` is separated
  from matcher behavior for anomalous legacy rows; the exact terminal predicate
  and T9 conclusion remain unchanged.
- `pass`: The two historical quotations of the old phrase `fresh 无时效含义`
  are unambiguously labeled as the superseded P5 mistake and cannot be read as
  an active contract.
- `pass`: No schema, algorithm, bounded implementation files, tests, STORJ
  exceptional path, fail-closed rule, one-action repayment gap, shared domain
  authority, A9 Human convention, or same-root scan topology regressed from the
  P6-passed R1-R3/R5/R7-R9 design.
- `pass`: Findings follow AGENTS.md scope classification and scenario-admission
  rules. A `REWORK` must identify a concrete plan-stage ambiguity that cannot
  be left to the implementation/code reviews; otherwise return `ACCEPT` and
  state that the plan may proceed to implementation-dispatch preparation.

Stop:
- Create the single handoff, return a compliant `[TASK_RESULT v2]` with an
  explicit `ACCEPT` or `REWORK`, send that same receipt once to `reply_to`, and
  stop. Do not implement, commit, update stage state, deploy, access production,
  or perform the exceptional STORJ database correction.

reply_to: codex
After emitting the normal console receipt, send that same receipt once to the
reply_to window per `HERDR.md`, then stop.
