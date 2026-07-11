# Stage ADR: Auto Review Pipeline v1

Status: **PROPOSED FOR DEVELOPMENT BREAKDOWN**
Date: 2026-07-11
Stage: `2026-07-auto-review-pipeline-v1`

## Context

The current DRAFT-2 Harness deliberately requires human execution of every
model dispatch and an independent bookkeeper for evidence commits/status. That
contract is auditable but creates repeated human relay work between
implementation, seal, review-1, and fixes.

The operator froze a target in `40-operator-decision-table.md`: automate the
bounded middle using cheap implementation/review models and deterministic
scripts, while retaining high-end/human attention for review-2 and merge.

The design must resolve several tensions:

- automation needs authority to invoke adapters and commit evidence;
- no model may gain self-review or state-machine authority;
- advisory cross-check happens before a committed snapshot;
- the only formal fingerprint remains committed-range based;
- serial and parallel stages need different review-1 granularity;
- retry/cost controls must share one stage ledger;
- current manual stages must remain valid without migration.

## Decision 1 — Add A Versioned, Default-Off Mode

`auto_review_pipeline/v1` is an optional nested status contract. Missing or
disabled configuration preserves current human dispatch. Enabling it requires a
committed, schema-valid human authorization artifact.

This bootstrap stage does not use auto mode.

### Alternatives Considered

- **Big-bang replace human dispatch:** rejected because it removes the proven
  fallback before pilots and repeats the failure pattern that caused the prior
  Harness rollback.
- **Infer enablement from task prompts or model capabilities:** rejected because
  authorization would be ambiguous and model-controlled.

### Tradeoff

- Benefit: safe trial and rollback boundary.
- Cost: workflow/validator must support two explicit modes temporarily.

## Decision 2 — Runner Inherits Mechanical Bookkeeper Authority Only

A deterministic, non-LLM runner is the only automatic dispatcher and
mechanical writer. It may invoke registry adapters, run tests, seal, update
mechanical status fields, commit evidence, and apply fixed transitions.

It may not invent requirements, broaden paths, select unregistered models,
interpret arbitrary model prose as control flow, invoke high-end models in the
automatic loop, or declare final acceptance.

Narrative handoff is generated from deterministic templates. Optional model
narrative, if later allowed, is an appendix and never authoritative.

### Alternatives Considered

- **Implementer calls reviewer directly:** rejected because the code author
  controls prompt/environment and can creep into self-acceptance.
- **Use a cheap LLM as bookkeeper/orchestrator:** rejected because state
  transitions and commits would remain probabilistic.
- **Keep human as every-hop dispatcher:** retained as fallback, but rejected as
  the auto mode target because it does not solve operator friction.

### Tradeoff

- Benefit: auditable, testable control plane.
- Cost: runner becomes privileged and needs strict allowlists/security tests.

## Decision 3 — Keep One Fingerprint And Use Patch Equality For Bind

The existing `diff_fingerprint` formula is unchanged. Embedded cross-check
records the exact observed `git diff --binary` bytes for a frozen base/pathspec.
After snapshot commit, the same diff is regenerated and compared byte-for-byte.

The frozen blocking command set runs both before cross-check and after its
evidence lands, immediately before seal. Those commands may consume only frozen
code/test/config inputs, never stage evidence. Byte equality would make the
first result code-equivalent, but v1 retains the explicit second pass from the
frozen §D main path as defense in depth.

The comparison is not stored as a fingerprint/hash in status or verdicts.

### Alternatives Considered

- **Add worktree fingerprint:** rejected by current Hard Gates and creates a
  competing review identity.
- **Seal before cross-check and commit evidence later:** rejected because
  advisory evidence would not be part of the frozen review inputs.
- **Trust that worktree did not change:** rejected because it is not evidence.
- **Omit the second blocking pass because bind proves code equality:** rejected
  because it leaves the frozen main-path step out of the runner/test state
  machine and depends on an implicit evidence-independence assumption.

### Tradeoff

- Benefit: proves cross-check saw the code later reviewed without changing the
  formal fingerprint protocol.
- Cost: exact pathspec/diff-byte reproducibility must be carefully tested.

## Decision 4 — Seal Uses Snapshot Then Binding Commit

Seal creates `H_snapshot`, computes its fingerprint, then creates `H_bind` with
status/receipt/handoff fields. Formal review targets the recorded snapshot, not
moving HEAD. Verdicts later use a separate verdict-record commit.

### Alternatives Considered

- **Write status/head before commit:** impossible because head is not yet known.
- **Amend snapshot after writing status:** rejected because amendment changes
  head and recreates the self-reference problem.
- **Leave status dirty:** rejected by the formal clean-worktree gate.

### Tradeoff

- Benefit: deterministic committed state with no circular hash.
- Cost: more mechanical commits and explicit crash recovery states.

## Decision 5 — Review Units Follow Delivery Topology

Serial stages use per-task review units. Every required task unit must ACCEPT;
a non-empty post-task code integration diff creates another required unit.

Parallel stages use isolated task worktrees, deterministic integration, and one
tip review unit. Review-1 eligibility uses the complete author-provider set of
that unit, including fix authors.

### Alternatives Considered

- **Always per-task:** rejected for parallel integration because no gate sees
  combined behavior.
- **Always tip-once:** rejected for serial delivery because early task rework
  repeatedly drags later work into the loop and defeats serial convergence.
- **Let runner infer topology from git history:** rejected; topology and units
  must be frozen in stage metadata.

### Tradeoff

- Benefit: review granularity matches integration risk.
- Cost: validator/status completeness becomes more structured.

## Decision 6 — Grok Is Auto Review-1, With Scope-Aware Fallback

Auto mode uses `grok-build` in plan/read-only mode. Serial unit fallback may use
Kimi/GLM only when candidate provider identity is absent from that unit's
author set. A parallel GLM+Kimi tip has no eligible cross-pool fallback; Grok
failure escalates for human routing. GPT/Claude are never auto-substituted.

### Alternatives Considered

- **Grok as global manual and auto default:** rejected until pilots demonstrate
  stable verdict behavior.
- **Always fallback to Kimi/GLM:** rejected because both commonly authored a
  parallel tip.
- **Auto fallback to GPT/Claude:** rejected by high-end cost policy and human
  attention goals.

### Tradeoff

- Benefit: independent combined-diff gate with bounded cost.
- Cost: Grok outage stops parallel auto flow rather than silently degrading.

## Decision 7 — Preserve Verdict Schema; Route Multi-Owner Fixes In Runner

`review-verdict.schema.json` remains unchanged. Runner preserves the full
`fix_start_prompt`, assigns findings by required file path and frozen ownership,
adds a deterministic owner header, and serializes v1 multi-owner fixes.

Ambiguous/missing paths, shared-contract changes, or boundary conflicts
escalate. Runner never assigns by natural-language guess.

### Alternatives Considered

- **Change schema to per-owner prompts:** rejected for v1 to minimize contract
  and historical verdict migration.
- **Send one unrestricted prompt to both owners:** rejected because it invites
  overlapping writes and scope drift.
- **Concurrent fixes in the integration worktree:** rejected due race and
  unprovable artifact ordering.

### Tradeoff

- Benefit: no verdict schema migration and deterministic ownership.
- Cost: some otherwise-fixable findings escalate; multi-domain fixes take
  longer because writes are serial.

## Decision 8 — One Rework Ledger, Plus Independent Call/Clock Budgets

The stage retains `max_rework_per_stage=3`. All automatic code-changing retries
combined consume at most 2, preserving at least one review-2 repair opportunity.

Each stage authorization also freezes positive model-call and wall-clock
budgets. Invalid JSON retries consume calls but not rework. A blocking-test fix
consumes rework.

### Alternatives Considered

- **Separate auto and human rework ledgers:** rejected because total stage cost
  could nearly double and contradict the current single cap.
- **Allow auto to consume all 3:** rejected because review-2 would have no
  repair room.
- **Only round cap, no call/time bounds:** rejected because retries/timeouts can
  be expensive without changing rework count.

### Tradeoff

- Benefit: predictable maximum automatic work and review-2 reserve.
- Cost: some stages escalate despite an otherwise repairable finding.

## Decision 9 — Human Fallback Is A Stop, Not An Automatic Continuation

Recoverable auto preflight/fallback failures move runner substate to
`awaiting_human`, set top-level `paused`, write evidence, and stop. Cap,
timeout, budget, unroutable fix, and tip-once Grok failure use the frozen
top-level `human_escalation_required` terminal route plus `80-*.md`. An operator
may select human dispatch or issue a superseding auto authorization where the
terminal semantics permit. No failed runner process automatically launches a
manual-mode model.

### Alternatives Considered

- **Immediately continue through human adapter commands:** rejected because no
  human actually authorized/resumed that action.
- **Remain in auto mode with unlimited retries:** rejected on cost and audit
  grounds.

### Tradeoff

- Benefit: explicit authority and reliable incident evidence.
- Cost: operator intervention is still required on exceptional paths.

## Decision 10 — Model Artifacts Are Untrusted Data

Only workflow/registry/status/authorization mappings drive control. Raw model
output is preserved; the runner accepts only one final schema-valid verdict
object and maps its enum to fixed transitions. Model-produced commands and
next-hop instructions are never executed.

Receipts record adapter references, not expanded commands/environment. Secret
exposure in output escalates rather than being silently rewritten.

### Alternatives Considered

- **Let implementer report select next dispatch:** rejected as prompt-injection
  and permission-creep surface.
- **Redact/rewrite raw evidence automatically:** rejected because it destroys
  evidence integrity; sensitive exposure requires controlled escalation.

### Tradeoff

- Benefit: prompt injection cannot directly control runner behavior.
- Cost: runner needs strict parsers and sensitive-output incident handling.

## Decision 11 — Bootstrap With Current Human Workflow

This stage sets auto mode disabled. Claude-GLM is the provisional single
implementation provider across serial Harness work packages; Kimi is the
provisional fresh review-1 provider. Development breakdown must freeze exact
packets before human dispatch.

Review-2 remains unresolved because OpenAI/Codex and Anthropic/Claude both
contributed content to the frozen design. The operator must either enable an
independent decision reviewer or satisfy a documented strong-reviewer override
path with truthful prior-involvement and required evidence.

### Alternatives Considered

- **Use new runner to build itself:** rejected as unaudited self-hosting.
- **Split implementation between GLM and Kimi:** rejected because there is no
  frontend domain and it complicates shared authority-file ownership.
- **Prefill Codex/Claude prior involvement as none:** rejected by both intake
  reviews and actual evidence.

### Tradeoff

- Benefit: implementation is reviewed under the last accepted Harness.
- Cost: this stage still incurs manual dispatch friction and needs a review-2
  routing decision later.

## Decision 12 — Pilot Readiness, Not Default Flip, Is The Stage Outcome

This stage delivers a default-off implementation and deterministic tests. It
does not flip defaults or retroactively enable existing stages. A docs-only
pilot and a small real pilot must each pass and reach their required acceptance
state before a future default-change decision can be opened.

Each pilot must publish machine-readable metrics for Grok schema-valid rate,
escalation-shape validation, and RECEIPT completeness. Both require at least one
final schema-valid Grok verdict and 100% receipt completeness; every produced
escalation must validate, and at least one pilot must execute a controlled safe
escalation drill. The schema-valid rate is evidence for the later operator
decision; v1 does not invent a global promotion threshold.

### Alternatives Considered

- **Flip default when implementation tests pass:** rejected because live runner,
  adapter, receipt, and escalation behavior require operational evidence.
- **Run a product pilot inside this Harness implementation stage:** rejected as
  prohibited product mixing and bootstrap self-use.

### Tradeoff

- Benefit: separates implementation correctness from operational confidence.
- Cost: at least two later stages are required before friction reduction is
  fully realized.

## Edge Cases And Constraints

- Evidence/status-only commits after a snapshot must never be treated as code
  integration units.
- An embedded cross-check unavailable artifact makes bind `N/A`; it does not
  create a fake PASS.
- A schema-valid verdict with wrong stage/unit fingerprint is invalid output.
- A model call that times out still consumes call budget.
- A fix author is added to the unit's author-provider set before re-review.
- If two tasks claim the same writable path in parallel topology, dispatch-ready
  must fail; no last-writer-wins behavior.
- Runner may not use `git add -A`; it stages the frozen allowlist and fails if
  other changes exist.
- Symlink/path traversal outside the authorized worktree fails closed.
- Unknown substate, transition, failure class, or authorization version routes
  to evidence-backed human escalation.
- Authorization `expires_at` is required but nullable: null means no separate
  expiry timestamp, while a non-null ISO8601 instant is enforced before every
  call/commit. Other budgets remain mandatory in both cases.
- Historical manual stages require no backfill.
- Legacy `parallel_mode.enabled` and auto-review enablement are mutually
  exclusive; auto parallel topology is represented only inside the new
  authorization/review-unit contract.

## Links To Prior Direction

- Frozen direction:
  `reports/agent-runs/2026-07-auto-review-pipeline-design-review/40-operator-decision-table.md`
- Codex design review:
  `reports/agent-runs/2026-07-auto-review-pipeline-design-review/30-review-codex.md`
- Fable divergence synthesis:
  `reports/agent-runs/2026-07-auto-review-pipeline-design-review/31-divergence-response-fable5.md`
- Decision-table patch merge:
  `reports/agent-runs/2026-07-auto-review-pipeline-design-review/43-decision-table-patch-merge.md`
- Intake reviews:
  `reports/agent-runs/2026-07-auto-review-pipeline-v1/01-intake-review-fable5.md`
  and `02-intake-review-grok.md`

## Reviewer Notes

- The two-commit seal is intentional and is not a second fingerprint protocol.
- `awaiting_human` is a nested runner substate, not a new top-level Harness
  status.
- New authorization/receipt schemas are additive Harness schemas; the frozen
  review-verdict schema remains untouched.
- Parallel initial task worktrees are supported, but v1 tip REWORK writes are
  deliberately serialized.
- Exact P8 numeric budgets are stage authorization data, not global defaults.
- This ADR author is OpenAI/Codex and therefore has design involvement; later
  review-2 status must record that fact truthfully.

本地北京时间: 2026-07-11 11:54:00 CST
下一步模型: Claude Fable 5（development breakdown author）
下一步任务: 把 ADR 决策转成最小实现任务、精确文件 owner、必跑命令和 review focus；不得写代码。
