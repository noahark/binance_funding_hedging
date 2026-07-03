# Stage Intake And Complexity

Stage ID: `2026-07-public-market-discovery`

## User Discussion Summary

Implement the first real development loop: Phase 1 public market discovery,
candidate classification, and funding-opportunity UI prototype, exactly as
captured in the approved direction synthesis
(`reports/agent-runs/2026-07-initial-direction/06-direction-synthesis.md`,
section 10 deliverables) and the promoted PRD
(`docs/product/PRD.md`: Phase 1 scope, Public Route Classification, and Phase 1
Acceptance Criteria). The direction panel and `promote-approved-docs` steps are
already complete upstream for this task; this stage is the bounded
implementation itself.

Goal: make the real public Binance market visible (USDⓈ-M perpetuals, current
and historical funding rates, spot availability, public margin-support
indicators, bStock detection) and produce a deterministic route-classified
candidate table plus a simulation-only manual-open preview — with no API key
and no private/signed/order path.

## Classification

- Complexity: `MEDIUM`
- Direction panel required: `false`
- Existing synthesis covers this work: `true`
- User approved lightweight route: `false` (not needed; existing synthesis covers)
- Lightweight skip allowed: `true` (existing_synthesis_covers_task satisfies the skip condition)

## Rationale

- Approved synthesis section 10 names this exact stage
  (`2026-07-public-market-discovery`) with an explicit deliverable list;
  section 7 fixes the technical spine (Python, Decimal, thin public adapters,
  pure classifier/planner, file-persisted samples, pytest).
- Synthesis was already promoted to `docs/product/PRD.md` (commit `ef6afc5`),
  so `direction-drafts`, `direction-synthesis`, and `promote-approved-docs`
  are done upstream and are not repeated.
- This matches MEDIUM (bounded implementation inside an approved direction).
  It is not HIGH: no new domain math, no new data model, no external-integration
  uncertainty — public endpoint semantics and `negative_funding_status` priority
  are already fixed in the PRD.
- No new product/domain/credential/deploy human gate in this stage; those were
  decided in the direction round.

## Human Gates

- None new for this stage (direction already user-approved). The PRD-level
  constraints (public-only endpoints, Decimal for all amounts/rates, serialized
  as strings, `negative_funding_status` priority
  PERP_ONLY > BSTOCK > SPOT_ONLY > PRIVATE_BORROW_VALIDATION_REQUIRED,
  `premiumIndex.lastFundingRate` semantics evidence) are execution constraints,
  not new approvals.
- Checkpoint confirmation requested after stage-design, before implementation.

## Routing Decision

- Next node: `stage-design`
- Designer assignment: `claude` (Anthropic, `software_architect` skill). Codex is
  deliberately kept available to serve as review-2 primary reviewer, preserving
  provider-level isolation against an Anthropic designer. Review-1 stays Grok
  Build (`grok-build`).

## Evaluator

- Provider: `claude_glm` (provider identity: `zhipu_glm`)
- Model: `glm-5.2[1m]`
- Skill: `complexity_evaluator`
