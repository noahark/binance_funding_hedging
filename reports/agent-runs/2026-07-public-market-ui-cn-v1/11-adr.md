# ADR: 2026-07-public-market-ui-cn-v1

> Note: `00-task.md` states this stage sets no `11-adr.md` (no new architecture
> decision). This minimal file exists only because `scripts/validate-stage.py`
> requires `11-adr.md` to be present at the pre-review/pre-accept gates. It
> records the "no new architecture decision" determination and the one process
> decision worth auditing; it adds no architecture.

## ADR-1: No new architecture decision this stage

- **Context**: this stage is a wording amendment (evidence-backed warning text) +
  frontend display/i18n polish. The snapshot shape, schema, server, and badge
  system are all stable from prior stages.
- **Decision**: no architecture change. Single-file frontend, stdlib HTTP server,
  existing badge/route system, and the frozen `public-market-snapshot/v1` schema
  are all reused as-is. Display format rules live in `10-design.md` (design
  detail), not here.
- **Rationale**: `00-task.md` Task/ADR section. A wording + i18n stage must not
  churn contract versions or introduce structural change; `schema_version` stays
  `public-market-snapshot/v1` and `rows` stays field-identical to `548ae0d`
  (proven by Task C, `60-test-output.txt` Section 5).

## ADR-2: `warnings[1]` text is contract semantics, amended in lockstep

- **Context**: the served `warnings[]` array is part of the contract surface.
  `warnings[1]` previously said the settled-vs-estimate meaning of
  `lastFundingRate` was unproven ("ambiguous"); the 2026-07-04 mid-period capture
  (`reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/`,
  `verify-funding-semantics.py` PASS) now proves it is the current-period
  real-time estimate.
- **Decision**: update `CONTRACT_WARNINGS[1]` in `backend/domain/snapshot.py`
  AND the matching contract-doc paragraph + Open Verification Items entry in
  `docs/api/public-market-contract.md` in lockstep, citing the evidence path.
  No schema field is added (this is wording, not a field).
- **Rationale**: the served warning and the frozen contract doc must not display
  a stale "ambiguous" claim next to evidence that resolves it. The amendment is
  purely textual; `rows` structure/values are unchanged (Task C field-identity
  check vs `548ae0d`).

## ADR-3: Rate percent formatting is string-shift only (display-layer decimal discipline)

- **Context**: the merged 「资金费率/结算时间」column renders the funding rate as a
  percent. `parseFloat(x)*100` / `Number(x)*100` produces float artifacts
  (`0.0001*100 = 0.010000000000000002`).
- **Decision**: `formatFundingRate` shifts the decimal by string manipulation
  (regex split sign/int/frac, first-2-frac digits into the integer part, pad,
  trim trailing zeros, normalize leading zeros, sign with `-0`→`0` collapse).
  `parseFloat`/`Number*100` is forbidden for the rate percent rendering.
- **Rationale**: hard constraint (decimal discipline at the display layer);
  keeps the rendered percent exact and auditable. `classForFundingRate`
  (CSS sign class, pre-existing from prior stages, not a percent formatter) and
  `formatPrice` (mark/index price thousands separator) are not rate-percent
  formatting and are out of this rule's scope.

## ADR-4: Task C rows baseline anchored at 548ae0d (bstock-alias-v1 accepted head)

- **Context**: Task C must assert rows are field-identical to "the prior accepted
  build"; a precise anchor is needed.
- **Decision**: anchor the baseline at `548ae0d` (the most recent product head
  accepted before this stage), rebuilt offline via a temporary git worktree over
  the same frozen raw.
- **Rationale**: `548ae0d` is the accepted product state this stage builds on;
  `6d8c0c4`/`b84a342`/`d3d6e7c` are intake/bookkeeping commits with no product
  code, so they share `548ae0d`'s rows. The worktree method lets the baseline run
  the actual `548ae0d` backend code (verified via
  `backend.domain.snapshot.__file__`) without disturbing the working tree.

本地北京时间: 2026-07-04 13:36 CST
下一步模型: review-1（cross-review）
