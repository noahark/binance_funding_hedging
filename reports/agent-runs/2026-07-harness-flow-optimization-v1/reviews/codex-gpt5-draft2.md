# Review: codex-gpt5 (DRAFT-2)

## Verdict

REWORK

## Summary

DRAFT-2 rev b is directionally sound and resolves several first-round blockers: no worktree fingerprint, no model recorder, task-local snapshots for double-owner branches, cross-provider review-1, and a separate non-binding product rebind hash. It is not yet safe to land §14 or run the §17 enablement stage because the script contracts still leave load-bearing ambiguity around scope checks, fingerprint-bearing checkpoint files, review-1 artifact ingestion, stale task tips, and workflow/validator integration.

## Findings

### Critical: `record-checkpoint` still blocks its own task-local evidence unless product and metadata scopes are split

DRAFT-2 §1 D3 freezes `status.json.tasks[].allowed_scope` as the pre-dispatch product pathspec source, and §6 now correctly says `evidence/<task-id>/` is metadata and not part of the product rebind hash. But §9 step 3 still says changed files must all be inside frozen `allowed_scope`, while §9 step 5 requires `record-checkpoint` to commit `evidence/<task-id>/` files such as `60-test-output.txt`, implementation reports, and embedded-review files.

For a first trial with `backend/**` and `frontend/**`, the generated evidence paths are outside both product scopes. A literal implementation fails every checkpoint; a permissive implementation has to invent an unstated exception. This means Kimi round-2 F1 is only partially resolved.

Required fix: define separate machine fields and checks:

- `tasks[].allowed_scope.product_paths`: only product/source/test paths used for product intersection and product rebind.
- `tasks[].allowed_scope.evidence_paths` or fixed `evidence/<task-id>/` metadata ownership: exact recorder/reviewer artifact paths allowed outside product scope.
- `record-checkpoint` validates product changed files against product paths and metadata changed files against the fixed evidence set; any other `reports/**` path remains BLOCKED.
- `prepare-review-2` excludes metadata from product intersection/rebind but validates required metadata independently.

### Critical: `checkpoint.json` creates a self-referential fingerprint or an uncommitted sidecar, but the draft does not choose

DRAFT-2 §6 puts `checkpoint.json` in task-local evidence and says it contains `base_sha`, `head_sha`, `task_diff_fingerprint`, `allowed_scope`, and `product_rebind_hash`. The same section says canonical `task_diff_fingerprint` covers all committed task-branch changes, including `evidence/<task-id>/`, excluding only top-level `status.json`. AGENTS.md explains that `status.json` is excluded because recording the fingerprint inside the hashed diff would be self-referential, and `scripts/validate-stage.py::compute_diff_fingerprint()` currently excludes only `reports/agent-runs/<stage>/status.json`.

If `checkpoint.json` is committed in `task_head`, its `task_diff_fingerprint` field changes the bytes being fingerprinted, creating the same self-reference problem that top-level `status.json` avoids. If `checkpoint.json` is written after the commit, as §9 steps 5-6 imply, then `prepare-review-2` cannot reliably read it from `--backend-branch` / `--frontend-branch`, and the checkpoint evidence is not committed before formal review.

Required fix: make the checkpoint lifecycle explicit and non-self-referential. Preferred: freeze `task_head_sha` before writing fingerprint-bearing sidecars; keep fingerprint-bearing `checkpoint.json` outside the reviewed task diff and have `prepare-review-2` copy/commit it on the integration branch after verifying it against `task_head_sha`. Alternative: split into a committed `checkpoint-input.json` without fingerprint fields and a generated `checkpoint.json` sidecar. Do not extend canonical fingerprint exclusions casually; that would be a framework-wide protocol change.

### High: review-1 artifacts are uncommitted by design, but `prepare-review-2` has no specified input path or provenance check

DRAFT-2 §13 says review-1 artifacts are produced after `task_head_sha` is frozen, must not be committed back to the task branch, remain as uncommitted files under `evidence/<task-id>/`, and are later committed by `prepare-review-2` on the integration branch. However §10 defines `prepare-review-2` only with branch arguments and says it reads each branch's `evidence/<task-id>/checkpoint.json` / review-1 verdict. A Git branch cannot expose uncommitted files in another worktree.

This is a deterministic-runner gap, not a model-policy issue. Without a specified mechanism, `prepare-review-2` may read stale/missing local files, depend on an implicit current working directory, or silently lose review-1 raw evidence if a worktree is removed.

Required fix: define review-1 artifact ingestion precisely. For example, `prepare-review-2` should take explicit `--backend-worktree` and `--frontend-worktree` paths, verify each path is a git worktree attached to the expected branch and tip, copy only the expected review-1 files plus attempts sidecar, record sha256/provenance for each copied artifact, and commit them on the integration branch. If auto-discovery via `git worktree list --porcelain` is allowed, that must be specified and covered by dry-run fixtures.

### High: §10 lacks the anti-stale-tip assertion that §17 expects

DRAFT-2 §17 includes a stale-tip fixture: after `record-checkpoint`, if a task branch moves, `prepare-review-2` must reject it. But §10 only requires merge-base equality and accepted review-1 verdicts. It does not require the current branch tip to equal `checkpoint.head_sha`, nor does it require the review-1 verdict fingerprint to equal the recomputed fingerprint for that exact head.

Impact: a task branch can receive an extra commit after review-1 ACCEPT. `prepare-review-2` may merge the new tip and prove rebind for the new tip, while review-1 actually approved the old tip.

Required fix: before merge, for every task:

- `git rev-parse <task-branch>` equals `checkpoint.head_sha`.
- `checkpoint.base_sha` equals the frozen stage base.
- recomputed `task_diff_fingerprint(base_sha, checkpoint.head_sha)` equals `checkpoint.task_diff_fingerprint`.
- schema-valid `review_1.diff_fingerprint` equals that same fingerprint.
- any mismatch is BLOCKED, with evidence written before exit.

### High: `allow_harness_change=true` weakens the immutable-script guard for exactly the files that define the guard

DRAFT-2 §9 lets `record-checkpoint` pass protected Harness changes when frozen metadata sets `allow_harness_change=true`. §17 says the enablement stage itself is conventional serial and does not use `record-checkpoint`, which is fine. But it also leaves a path for product tasks to set `allow_harness_change=true` and then modify `scripts/**`, `schemas/**`, workflow files, registry, or AGENTS.md inside an independent task branch.

That exception undermines the trust boundary unless it is made much narrower. The first real trial already forbids schema/API/shared fixture changes; it should also forbid Harness control-file changes in independent task branches.

Required fix: for this trial mode, set `allow_harness_change=true` only for a dedicated serial Harness enablement stage, not for double-owner product task branches. If a later stage truly needs Harness changes, route it through single-owner or serial mode with explicit human approval and review-2 disclosure, not through the independent worktree task-branch path.

### Medium/High: §14 omits `workflows/templates/stage-delivery.yaml`, but the workflow template is a higher-authority executable contract

AGENTS.md authority order puts `workflows/templates/*.yaml` above stage reports and docs. The current `stage-delivery.yaml` still defines the bookkeeper as the single writer for stage state/evidence commits/dispatch packets, requires committed artifacts before review-1/review-2, and assumes top-level required files. DRAFT-2 changes the writer topology to recorder/integrator scripts, task-local evidence, per-task review-1 artifacts, and independent worktree branches.

§14 lists AGENTS.md, `validate-stage.py`, schemas, and the two new scripts, but does not list workflow template changes. Leaving the workflow unchanged creates a direct conflict with the proposed mode, and lower-authority DRAFT text cannot override it.

Required fix: add `workflows/templates/stage-delivery.yaml` to §14 with an explicit optional mode, such as `independent_task_branch_mode`, including task-branch topology, recorder/integrator script gates, task-local evidence paths, review-1 artifact ingestion, and integration pre-review gates.

### Medium: test command source and worktree execution context remain too loose for a deterministic recorder

DRAFT-2 §9 says `record-checkpoint` reruns the task tests, and §14 notes worktree/cwd risks, but the script contract does not define where the test command comes from, what cwd it uses, or how it resolves stage/evidence paths inside a git worktree. `docs/parallel-development-mode.md` R10 requires exact self-test commands and real artifact paths before implementation starts; `validate-stage.py` currently resolves the repo root and stage directory from the current worktree.

Required fix: §9/§14 should require `record-checkpoint` to read the test command from frozen `status.json.tasks[].test_command` or `tasks[].r10_checklist`, run it from the task worktree root, write output only to the task evidence path in that same worktree, and fail closed when the command is missing or tries to write outside the allowed evidence path. Add dry-run coverage for running the scripts from non-primary worktree cwd.

## Required Changes

1. Split product scope from evidence/metadata scope and update §3/§6/§9/§10/§14/schema/dry-run fixtures accordingly.
2. Resolve the `checkpoint.json` fingerprint self-reference by defining a sidecar or split-file lifecycle that never includes a fingerprint-bearing file in the diff it fingerprints.
3. Specify exactly how `prepare-review-2` locates, verifies, copies, hashes, and commits uncommitted review-1 artifacts and `review-1.attempts.json`.
4. Add the anti-stale-tip assertion to §10 and make fixture ⑧ test that exact assertion.
5. Close the `allow_harness_change=true` bypass for double-owner product task branches; keep Harness changes in the serial enablement path.
6. Add `workflows/templates/stage-delivery.yaml` to §14 and define the optional independent task-branch mode in the higher-authority workflow contract.
7. Specify task test command source, worktree cwd, evidence-path resolution, and validator cwd behavior before implementing `record-checkpoint`.

## Open Questions

1. Should fingerprint-bearing task checkpoint metadata be an integration-branch-only sidecar, or should the Harness extend the canonical exclusion list beyond top-level `status.json`? I recommend the sidecar approach to avoid changing the global fingerprint protocol.
2. Should `prepare-review-2` require explicit worktree paths, or may it discover worktrees from branch names? I recommend explicit paths plus verification.
3. Should any double-owner product stage ever permit `allow_harness_change=true`? I recommend no for the first trial.
4. Should canonical `compute_diff_fingerprint()` add `--no-renames`? I recommend leaving canonical unchanged for this trial and proving product rebind behavior with rename/move/delete fixtures, because canonical fingerprint changes affect the whole Harness.

## Footer

本地北京时间: 2026-07-08 19:51:02 CST
下一步模型: human
下一步任务: Revise DRAFT-2 rev b to close the script-contract gaps above, then re-run DRAFT-2 review before landing §14 enablement changes.
