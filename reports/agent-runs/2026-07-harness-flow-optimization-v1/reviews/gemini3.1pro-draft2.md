# Review: gemini3.1pro (round 2, DRAFT-2)

## Verdict

REWORK

## Summary

DRAFT-2 correctly establishes the independent task-branch topology and integrates the non-negotiable trial-mode requirements (D1-D4). The separation of the product rebind hash from canonical fingerprints is structurally sound. However, there remain critical implementation-level contract gaps in §9 and §10—specifically a circular dependency regarding how `checkpoint.json` is committed without invalidating the fingerprint it contains, and a missing anti-stale-tip check in `prepare-review-2` that could allow unreviewed code to be merged.

## Findings

### 1. CRITICAL: Circular Dependency in `record-checkpoint` Fingerprint Calculation (§9 & §6)
**Evidence:** §9 step 6 states `record-checkpoint` calculates `task_diff_fingerprint` and writes it to `evidence/<task-id>/checkpoint.json`. However, §6 defines the canonical diff fingerprint formula as excluding only `<top status.json>`. It does not exclude `evidence/<task-id>/checkpoint.json`.
**Impact:** If `checkpoint.json` is committed in the task branch, committing it changes the git tree and invalidates the very fingerprint recorded inside it. If it is left uncommitted, it violates the `require_clean_worktree` check required for the pre-review phase.
**Resolution:** The canonical fingerprint formula in §6 must be updated to also exclude task-local checkpoint files, or `record-checkpoint` must use a strict two-phase commit where the fingerprint is anchored to the commit *before* `checkpoint.json` is committed.

### 2. HIGH: `prepare-review-2` Lacks an Anti-Stale-Tip Guard (§10)
**Evidence:** §10 step 1 reads both branches' `checkpoint.json` and verifies that the `review_1.verdict` is `ACCEPT`. It does not explicitly mandate that the current tip of the task branch mathematically matches the fingerprint that was accepted.
**Impact:** After a successful review-1, an implementer could `git commit --amend` their task branch to inject unauthorized changes. `prepare-review-2` would read the `ACCEPT` verdict from the (unamended or tampered) `checkpoint.json`, recompute the `product_rebind_hash` from the *new* tip, and successfully integrate unreviewed code.
**Resolution:** §10 must explicitly require `prepare-review-2` to recompute the `task_diff_fingerprint` from the current task branch tip and assert that it strictly equals the `diff_fingerprint` recorded in the `ACCEPT` verdict.

### 3. MEDIUM: Incomplete Framework-Change List for `stage-delivery.yaml` (§14)
**Evidence:** §14 lists necessary updates for `AGENTS.md`, `validate-stage.py`, and `schemas/`, but completely omits changes to `workflows/templates/stage-delivery.yaml`.
**Impact:** The workflow YAML currently enforces transitions based on a model bookkeeper (e.g., routing failures from `embedded-cross-review-checkpoint` to `bookkeeper-decision`). Without updating the YAML to reflect the new task-branch-checkpoint and script-driven integration states, the actual execution path will diverge from the canonical YAML definition.
**Resolution:** Add `workflows/templates/stage-delivery.yaml` to the §14 framework-change list, explicitly defining the new stage topologies and transition rules for when there is no model bookkeeper.

### 4. MEDIUM: Trial Plan Lacks Negative Failure-Mode Fixtures (§17)
**Evidence:** §17 step 3 defines a synthetic dry-run fixture that proves the happy path assertions (metadata doesn't intersect, fingerprints recompute, rebind hashes match). It does not mandate fixtures that prove the hard gates actually fail-closed.
**Impact:** We risk deploying a harness mode where the validators fail to block invalid states (e.g., product path intersection, stale tips, unauthorized immutable file modifications).
**Resolution:** Expand the §17 dry-run fixtures to explicitly include negative tests: a shared-file modification fixture (must fail R1), a stale-tip fixture (must block integration), and a script-tampering fixture (must fail the immutable-script guard).

## Required Changes

1. Fix the circular dependency in §9/§6 by either excluding `evidence/<task-id>/checkpoint.json` from the canonical diff fingerprint, or specifying a precise two-commit sequence for `record-checkpoint` where the canonical `head_sha` precedes the checkpoint metadata commit.
2. Add an anti-stale-tip assertion to §10 `prepare-review-2` to strictly compare the current task branch's recomputed fingerprint against the accepted fingerprint.
3. Update §14 to include mandatory changes to `workflows/templates/stage-delivery.yaml` (task-branch transitions, branch name template support).
4. Update §17 to require negative failure-mode fixtures before a live run.

## Open Questions

1. Should the canonical `diff_fingerprint` algorithm globally ignore all `.json` files inside `reports/agent-runs/<stage>/evidence/`, or should we stick to the two-commit sequence for `record-checkpoint` to keep the diff formula as simple as possible?
2. Does `validate-stage.py` require updates to its `require_clean_worktree` logic if we adopt the two-commit sequence?

## Footer

本地北京时间: 2026-07-08 19:50:17 CST
下一步模型: human
下一步任务: Resolve the circular dependency regarding `checkpoint.json` and add the anti-stale-tip guard to DRAFT-2 before finalizing the script contracts.
