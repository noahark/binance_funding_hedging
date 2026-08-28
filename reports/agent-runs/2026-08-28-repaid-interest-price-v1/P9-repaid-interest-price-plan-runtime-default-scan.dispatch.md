# P9 — Repaid interest price plan runtime-default scan

Identity:
- task_id: `P9-repaid-interest-price-plan-runtime-default-scan`
- target_role: `Planner`
- target_model: `opus5`
- provider: `anthropic`
- status_revision: `15`
- required_skill: `agents/skills/task-planner.md`

Goal:
- Repair P8 F1 and satisfy the AGENTS.md same-root brake with one bounded,
  exhaustive scan of the reviewed plan. Do not implement or redesign.
- Copy the reviewer-named root verbatim into the plan scan record:
  `F1 in-range — 60/120 秒把代码默认值写成未经核实的运行时常量`.
- Enumerate every active or historical statement in the plan that could turn a
  code/config default, configurable threshold, or unverified deployment value
  into a runtime guarantee. Fix the active `60/120` wording and give an
  applicable/not-applicable reason for every other site. Keep the scan concise.

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
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P8-repaid-interest-price-plan-contract-rereview.handoff.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/P7-repaid-interest-price-plan-contract-repair.dispatch.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/P8-repaid-interest-price-plan-contract-rereview.dispatch.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`
- `backend/config.py`
- `backend/services/snapshot_service.py`
- `backend/domain/snapshot.py`
- `backend/app/server.py`

Acceptance Checks:
- `pass`: The active contract states that `Config` has a **code default**
  `cache_ttl_seconds=60`, so only when deployment configuration does not
  override it is the default `fresh` threshold `<120` seconds; the actual
  runtime threshold is always `< 2 * configured cache_ttl_seconds`, and this
  plan has not verified any deployment's configured value.
- `pass`: Any API-documentation instruction forbids presenting default
  `60/120` as an unconditional runtime guarantee while preserving the
  parameterized `fresh` contract, possible lag, and non-execution-rate meaning.
- `pass`: A concise same-root scan lists every plan occurrence or semantic site
  involving configurable/default/runtime numeric claims. Each is classified as
  fixed, already parameterized, historical-only, independently evidenced, or
  not applicable, with a reason; no site is silently omitted.
- `pass`: The scan covers at minimum the active `cache_ttl_seconds` formula and
  default parenthetical, the superseded P5 `fresh` wording, historical timeout
  references, stored event timestamps, and deterministic ordering/time-unit
  conversions, explaining why non-configuration facts are outside this root.
- `pass`: No architecture, schema, algorithm, bounded implementation files,
  test mechanism, STORJ exceptional path, fail-closed behavior, source-field
  contract, A9 Human convention, or root A/B scan topology changes. P6-passed
  R1-R3/R5/R7-R9 and P8-passed source/zero-string fixes remain intact.
- `pass`: The plan records P9 as a same-root exhaustive scan and states that
  Bookkeeper must seal a new fixed commit and obtain another independent plan
  review `ACCEPT` before preparing implementation.

Stop:
- Stop after modifying only the plan. Do not create the next review packet,
  edit `status.json` or `PROJECT_STATE.md`, implement, commit, send another
  terminal, access credentials, write production data, deploy, restart, or
  perform the exceptional STORJ correction. Return a compliant
  `[TASK_RESULT v2]` and wait for Human/Bookkeeper verification.
