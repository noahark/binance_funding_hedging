# Design

## Problem

The first single-owner Harness run completed successfully but exposed friction
that will recur unless the Harness itself is updated. The most expensive
problems were not delivery bugs; they were tool/template mismatches:

- Review-1 initially REWORKed because the dispatch prompt anchored the review
  fingerprint before validator evidence was committed.
- `review_2.primary_provider=codex` in the template was interpreted as an
  already-selected final reviewer, causing false designer-overlap failure.
- Validator logs and review evidence commits created repeated questions about
  fixed-point fingerprints and delivery-anchored `head_sha`.
- Single-owner `record-checkpoint` printed the fingerprint but left manual
  top-level `status.json` transcription to the model.

## Design Direction

Implement targeted Harness fixes rather than broad process churn:

1. **Separate preferred reviewer from selected reviewer.**
   Template and validator behavior should not treat a pending preference as
   actual reviewer identity. Provider isolation must still be strict once a
   reviewer is selected.

2. **Make single-owner checkpoint deterministic.**
   `record-checkpoint --single-owner` should either write/prep the status
   fields it claims to own or stop claiming that behavior. The preferred design
   is to have the script update top-level review metadata in a predictable,
   tested way.

3. **Make validator evidence capture clean-worktree-safe.**
   Add a supported pattern, likely `--evidence-out <path>`, so the validator can
   check a clean tree and then write the evidence file after validation.

4. **Document two accepted evidence conventions.**
   Reviewers need explicit context for:
   - delivery-anchored `head_sha` with later auxiliary review/handoff commits;
   - validator fixed-point behavior where a committed log cannot contain the
     exact fingerprint of the commit that contains itself.

5. **Repair generated/dispatch metadata.**
   Dispatch packets and templates should set next actions to the immediate next
   state and record actual fallback model execution without compromising
   provider isolation.

## Expected Implementation Shape

The detailed breakdown should decide whether this is one GLM-owned task or
split into tool/doc sub-tasks. The likely dominant work is Python/Harness logic,
so Claude-GLM is the likely implementer. Kimi review-1 should cross-review the
GLM implementation.

## Test Strategy

- Unit or fixture tests for `validate-stage.py` identity handling.
- Dry-run fixture updates for single-owner checkpoint behavior.
- Regression tests for `itbm_dry_run.py`.
- Manual validator runs against this stage before review.

## Risks

- Over-broad validator relaxation could weaken anti-self-review gates.
- Updating `record-checkpoint` to mutate `status.json` must avoid
  self-referential fingerprints and must preserve the single canonical
  fingerprint protocol.
- `--evidence-out` must not mask real dirty-worktree failures.

本地北京时间: 2026-07-09 13:42:58 CST
下一步模型: claude
下一步任务: write `12-development-breakdown.md`
