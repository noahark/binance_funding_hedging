# Review: codex-gpt5 (DRAFT-2 rev c)

## Verdict

REWORK

## Summary

rev c has closed the main contract gaps from my DRAFT-2 review: checkpoint self-reference is solved by a sidecar lifecycle, product/evidence scope is split, review-1 ingest now uses explicit worktree paths with provenance hashes, anti-stale-tip is specified, `allow_harness_change` is closed for product task branches, and §14 now names the higher-authority workflow/template/validator/schema changes. It is close enough to implement, but not quite safe to start writing the two scripts until two remaining execution-order seams are pinned down.

## Findings

### Resolved From My Previous Review

- Previous Critical scope finding is resolved in rev c §3/§6/§9-3: `product_paths` drives product intersection/rebind, while `evidence/<task-id>/` is separately task-owned metadata.
- Previous Critical checkpoint self-reference finding is resolved in rev c §6/§9-6/§10-1: `checkpoint.json` is an uncommitted task-worktree sidecar and is only committed by `prepare-review-2` on the integration branch.
- Previous High review-1 ingest finding is mostly resolved in rev c §10-1/§10-7/§13: explicit `--backend-worktree` / `--frontend-worktree`, path verification, sha256 provenance, and integration-branch commit are now specified.
- Previous High anti-stale-tip finding is resolved in rev c §10-2 and fixture §17-⑧.
- Previous High `allow_harness_change=true` finding is resolved by decision E and rev c §1/§9-2/§17.
- Previous Medium/High workflow-contract finding is resolved at spec level by rev c §14-2, which adds `workflows/templates/stage-delivery.yaml` and an optional `independent_task_branch_mode`.
- Previous Medium test/cwd finding is mostly resolved by rev c §9-4/§10/§14-3.

### High: `record-checkpoint` still specifies guard/scope checks against branch commits, but implementer changes are uncommitted worktree changes

rev c §8 Phase 2 says GLM/Kimi implement in their own worktrees and do not touch git. rev c §9 then runs `record-checkpoint` from a trusted checkout with `--task-worktree <path>`. However §9-2/§9-3 define the immutable guard and scope checks using `git diff <base_sha>..<task-branch>`, and §9-5 later creates the first task commit C_e.

Before C_e exists, `base_sha..<task-branch>` can be empty even though the task worktree contains uncommitted product changes, untracked files, or forbidden edits. A literal implementation either misses the actual implementation files during guard/scope validation, or has to invent an unstated "worktree candidate diff" layer. This is especially important for protected paths: the trusted script will not run the task worktree's modified `scripts/`, but it still must fail closed if the task worktree contains modified `scripts/**`, `schemas/**`, `AGENTS.md`, or other protected files before committing C_e.

This affects rev c §9-2, §9-3, §9-5 and the current validator assumptions in `scripts/validate-stage.py:124-176` / `scripts/validate-stage.py:817-846`, which operate from the current git root and committed refs unless explicitly extended.

Required fix: define the exact candidate set that `record-checkpoint` validates and commits. It should include the task worktree's tracked, staged, unstaged, and untracked changes, plus any already-committed task-branch delta if retries allow it. The guard/scope rules must run on that combined candidate set before C_e is created:

- any protected Harness path in the task worktree or branch delta -> BLOCKED;
- any path outside `product_paths` plus the generated `evidence/<task-id>/` set -> BLOCKED;
- commit C_e using an explicit pathspec from that validated set only;
- after commit, assert the task worktree is clean except for allowed sidecars produced after C_e, such as `checkpoint.json` and later review-1 artifacts.

### High: §10-7's rebind/integration sequence references `merge_head` before the merge commit exists, and the status commit boundary is not explicit

rev c §6 defines `<task>_integration_product_rebind_hash = sha256(PRODUCT_DIFF(base, merge_head))`, where `PRODUCT_DIFF(base, head)` is a committed-range diff. But rev c §10-7 says `prepare-review-2` should run `git merge --no-commit --no-ff`, perform the rebind assertion, run full tests, abort/reset on failure, and only then "正式 commit merge + ingest" on success. At the rebind point, there is no `merge_head` commit yet.

The draft therefore mixes two different objects: a pre-commit merged index/worktree and a post-commit `merge_head`. A script writer could implement either one and get different bytes for the rebind check, especially if test output, ingested review artifacts, or later status writes are staged between the assertion and the final commit.

There is also a related clean-gate boundary: rev c §10-8 writes top-level `status.json` after the merge/ingest commit, while `scripts/validate-stage.py:124-130` requires a clean worktree before pre-review. The draft should state whether the reviewed integration `head_sha` is the merge+ingest evidence commit and `status.json` is committed in a later status-only commit, or whether another two-step pattern is used. This matters because AGENTS.md:247-254 requires review prompts to use the recorded `base_sha..head_sha`, not a moving `HEAD`.

Required fix: make the integration commit lifecycle explicit. One workable contract:

- after `git merge --no-commit --no-ff`, compute a pre-commit product rebind check against the merged index/worktree with a separately named command, not `PRODUCT_DIFF(base, merge_head)`;
- copy/verify review-1 artifacts and full test output into the integration worktree;
- create a single integration evidence commit `M_e` containing merged product files plus ingested evidence/test output, but not fingerprint-bearing `status.json`;
- recompute canonical `integration_diff_fingerprint` and product rebind hashes against committed `base..M_e`;
- write and commit top-level `status.json` in a separate status-only commit, recording `head_sha=M_e`;
- run `validate-stage.py --phase pre-review` from the integration worktree and ensure it recomputes against the recorded `head_sha`, not current `HEAD`.

An alternative is a temporary merge commit followed by reset on failed assertions, but the spec must choose one. The current wording is still ambiguous enough to produce non-identical `prepare-review-2` implementations.

### Medium: `review-1.attempts.json` should be required even for zero invalid attempts

rev c §10-1 requires `prepare-review-2` to ingest `review-1.attempts.json`, and §10-3 / §11 say it enforces `invalid_json_attempts <= 2`. But §11 describes the human writing the file when review returns invalid JSON. A clean first-pass review could therefore have no attempts file unless the dispatch prompt or validator requires a zero-count sidecar.

Required fix: state that every review-1 dispatch must leave `evidence/<task-id>/review-1.attempts.json`, with an empty or zero-valued `invalid_json_attempts` map when no invalid attempts occurred. Add this to §11, §13, §14 schema/template changes, and fixture coverage.

## Required Changes

1. Update rev c §9 to define `record-checkpoint`'s pre-commit candidate diff over the task worktree, including staged/unstaged/untracked files, and require guard/scope checks on that candidate set before C_e.
2. Update rev c §10-7/§10-8 to define the exact integration commit sequence, including whether rebind is checked against a pre-commit index/worktree object or a committed `M_e`, and how the status-only commit records `head_sha`.
3. Require `review-1.attempts.json` to exist for every task even when all review attempts were valid JSON.

## Open Questions

1. For §10-7, do you prefer pre-commit index/worktree rebind followed by a committed `M_e` recheck, or a temporary merge commit that is reset on failure? I recommend pre-commit check plus committed `M_e` recheck because it preserves the no-bad-commit invariant.
2. Should `record-checkpoint` fail if the task worktree has any dirty file after C_e and `checkpoint.json`, or should it allow a narrow set of post-checkpoint sidecars? I recommend the narrow explicit allowlist.

## Footer

本地北京时间: 2026-07-08 20:33:19 CST
下一步模型: human
下一步任务: Patch DRAFT-2 rev c for the two remaining script-order contracts, then proceed to the Harness-only enablement stage after confirmation.
