# Review: codex-gpt5

## Verdict

REWORK

## Summary

The revised independent task-branch mode is directionally sound and resolves the
largest failures from the first proposal: no worktree fingerprint, no model
recorder, review-1 remains cross-provider, and review-2 gets a committed
integration fingerprint. The remaining issues are now concrete implementation
contract gaps, not conceptual blockers. The main problems are that both task
branches intentionally modify shared Harness metadata while §7/§9 require
changed-file intersection to be empty, the draft uses task-specific report/test
filenames that the current validator cannot accept, and the rebind proof needs a
more precise product-diff versus evidence/metadata-diff split. Fix those before
landing scripts or validator changes.

## Findings

### F1 — Critical: changed-file intersection will fail by design because both task branches write `status.json`

Section §6 says each task branch writes branch-scoped `status.json`, and §7 says
`prepare-review-2` must reject any changed-file intersection before merging. That
means a normal successful backend task and frontend task will both touch:

- `reports/agent-runs/<stage-id>/status.json`
- likely `70-handoff.md` or shared dispatch/status evidence, depending on the
  final templates

So the "changed-file intersection empty" gate would reject the happy path before
integration. The draft later says the integration branch status is regenerated
and "takes ownership", but it does not exempt branch-scoped Harness metadata from
the intersection check or define how those files are merged/ignored.

Required fix: split intersection checks into at least two sets:

- `product_changed_files`: must be disjoint and is the hard R1 gate.
- `stage_metadata_files`: may overlap only for explicitly enumerated generated
  files, and `prepare-review-2` must discard/regenerate integration-owned
  versions deterministically.

Alternatively, do not let task branches write top-level `status.json`; write
task-local status snapshots such as `task-status/backend.json` and
`task-status/frontend.json`, then let `prepare-review-2` produce the only
top-level integration `status.json`.

### F2 — Critical: current validator required-file checks do not match task-specific filenames

The draft makes task branches produce `20-implementation-<task>.md` and
`60-test-output-<task>.txt`, then runs `validate-stage.py --phase pre-review` on
that task branch. Current `scripts/validate-stage.py` requires fixed files:

- `20-implementation.md`
- `60-test-output.txt`
- `70-handoff.md`

and for MEDIUM/HIGH/MILESTONE, `12-development-breakdown.md`.

Unless the validator is changed before trial, each task branch will fail
pre-review even if the task-specific evidence is complete. Section §10 mentions
validator/schema updates, but does not explicitly list required-file mapping or
task-level evidence naming as a fail-closed change.

Required fix: §10 must require `validate-stage.py` task mode to accept
task-specific evidence paths from `status.json.tasks[]`, or `record-checkpoint`
must also create canonical per-branch aliases (`20-implementation.md`,
`60-test-output.txt`) in each task branch.

### F3 — High: rebind proof is underspecified for evidence/metadata versus product code

Section §6 says:

```text
sha256(integration_diff ∩ backend_paths) == backend task diff hash
```

and similarly for frontend. This is the right idea, but the contract does not
define:

- the exact pathspecs used for backend/frontend rebind;
- whether evidence files under `reports/agent-runs/<stage-id>/` are included in
  task diff hashes;
- whether `status.json` is excluded using the same canonical exclusion as
  `compute_diff_fingerprint`;
- how binary files, renames, generated files, deleted files, and path moves are
  normalized;
- whether "task diff hash" is the full task fingerprint hash or a separate
  product-path hash.

Using the full task fingerprint hash for rebind will not work once integration
regenerates top-level status/evidence. The rebind proof should compare
path-restricted product diffs derived from committed states, while the canonical
task and integration fingerprints remain the binding review anchors.

Required fix: introduce explicit non-binding rebind hashes, for example:

```text
backend_product_rebind_hash =
  sha256(git diff --binary <base>..<backend_head> -- <backend_pathspecs>)

integration_backend_product_rebind_hash =
  sha256(git diff --binary <base>..<integration_head> -- <backend_pathspecs>)
```

Then compare those two. Keep `task_diff_fingerprint` and
`integration_diff_fingerprint` as the canonical gate fingerprints.

### F4 — High: `record-checkpoint` trust boundary needs an immutable-script guard

The draft allows GLM/Kimi terminals to run `record-checkpoint` as their R10
tail. That is acceptable only if the task cannot modify the script or its
policy inputs before running it. Otherwise an implementer can alter
`scripts/record-checkpoint`, `scripts/validate-stage.py`, registry routing,
allowed scopes, or task metadata and then run a compromised recorder.

Required fix: `record-checkpoint` must fail if Harness control files changed in
the task branch unless the task explicitly permits Harness changes. At minimum,
guard these paths:

- `AGENTS.md`
- `workflows/**`
- `agents/registry.yaml`
- `docs/model-adapters.md`
- `docs/parallel-development-mode.md`
- `scripts/record-checkpoint`
- `scripts/prepare-review-2`
- `scripts/validate-stage.py`
- `schemas/**`

The allowed scope must come from frozen stage metadata committed at base, not
from caller-provided CLI arguments alone.

### F5 — High: task branches need a precise ancestry and no-upstream-merge rule

The draft requires both task branches to have the same merge-base as recorded
`base_sha`. Good, but not sufficient. A task branch can merge unrelated commits,
merge the integration branch, or include a merge commit while still having a
merge-base equal to base. That makes rebind and review-1 provenance harder to
audit.

Required fix: define branch ancestry rules:

- `<base_sha>` must be an ancestor of each task `head_sha`.
- task branch history must not include commits whose first-parent path leaves
  the task branch base, unless explicitly approved;
- no merges from sibling task branches or `main` after task branch creation;
- all review-1 fingerprints use `<recorded_base_sha>..<task_head_sha>`, never a
  symbolic `HEAD`.

If merge commits are allowed, `prepare-review-2` must explicitly document how it
handles them.

### F6 — Medium: `human_decision` is placed too late for assign-fix branches

Section §8 says `prepare-review-2` writes `human_decision` after review-1 and
before review-2. But if the human chooses `assign_fix`, `prepare-review-2`
should not run, because no integration/review-2 preparation should happen.

Required fix: the human decision artifact should be a separate required stage
artifact or status block written before either:

- `assign_fix` dispatch, or
- `prepare-review-2 --human-decision proceed_to_review_2`.

`prepare-review-2` can verify and carry the `proceed_to_review_2` decision, but
it should not be the only way to create the decision record.

### F7 — Medium: review-1 output storage for two task branches is not specified enough

The draft says each track has review-1 and `prepare-review-2` checks both
review-1 verdicts are `ACCEPT`, but it does not define exact paths or status
shape. Existing validator logic expects review data in a small set of locations
and checks `review_1.diff_fingerprint` against top-level status.

Required fix: define task review-1 artifacts and status fields, for example:

```text
30-review-1-backend.md
30-review-1-frontend.md
review-1-backend.raw-output.md
review-1-frontend.raw-output.md
status.json.tasks[].review_1.verdict
status.json.tasks[].review_1.diff_fingerprint
```

Then update validator to verify each task review-1 fingerprint independently.

### F8 — Medium: single-owner path is mentioned but not specified

The draft is about double-owner worktree branches, but several lines mention
single-owner stages without defining whether `record-checkpoint` runs on
`stage/<id>` directly, whether review-1 remains cross-provider, or whether
`prepare-review-2` is skipped entirely.

Required fix: either move single-owner behavior out of this spec, or add a short
single-owner section:

- no task branch;
- `record-checkpoint` runs on `stage/<id>`;
- top-level fingerprint is the review-1 and review-2 candidate fingerprint
  until a fix changes it;
- `prepare-review-2` is not used.

### F9 — Low/Medium: task branch names under `stage/<id>/...` may be fine, but cleanup and uniqueness need a rule

Branch names like `stage/<stage-id>/backend-glm` are valid, but they accumulate
and can collide across retries. The draft should define cleanup/abandonment and
retry naming, for example:

- `stage/<stage-id>/backend-glm-r2` for a task branch rebuild after a failed
  trial;
- never force-delete task branches before review-2 acceptance;
- record abandoned branch names in `status.json` or handoff.

## Required Changes

Before adopting this draft or implementing the scripts:

1. Fix the changed-file intersection contract so generated Harness metadata
   does not make the happy path fail. Prefer task-local status snapshots plus a
   regenerated integration `status.json`.
2. Specify task-specific required-file handling in `validate-stage.py`, or make
   `record-checkpoint` create canonical per-branch aliases that current
   validation can accept.
3. Separate canonical review fingerprints from product-path rebind hashes, and
   define exact `git diff --binary` pathspecs for backend/frontend rebind.
4. Add immutable-script/policy guards to `record-checkpoint` and
   `prepare-review-2`.
5. Add branch ancestry/no-sibling-merge rules.
6. Move `human_decision` creation out of `prepare-review-2` so `assign_fix` and
   `escalate` decisions are also recorded.
7. Define exact review-1 artifact paths and `status.json.tasks[]` fields for
   two independent task verdicts.
8. Decide whether single-owner behavior belongs in this spec; if yes, specify
   it.

## Open Questions

1. Should task branches write top-level `status.json`, or should they write
   task-local status snapshots that integration consumes?
2. Should `record-checkpoint` be allowed to commit report/evidence files under
   `reports/agent-runs/<stage-id>/`, or only source/test files plus a task-local
   evidence directory?
3. What are the frozen backend/frontend pathspecs for the first trial stage?
   They must be known before dispatch, not inferred after implementation.
4. Is the first trial allowed to modify schema/API contract files? The draft's
   R1 says shared schema/API changes break mechanical integration, so a trial
   with shared contract edits should be excluded.

## Recommended Trial Plan

Proceed with the worktree-branch decision, but make the first implementation
stage a Harness-only enablement stage:

1. Implement `scripts/record-checkpoint` and `scripts/prepare-review-2` with no
   model calls.
2. Update `validate-stage.py` for task-branch metadata, task-specific review-1
   verdicts, task evidence paths, human decision checks, and integration rebind
   checks.
3. Add one synthetic dry-run fixture stage with two disjoint toy branches to
   prove:
   - shared metadata does not trip product-file intersection;
   - task fingerprints recompute;
   - product rebind hashes match;
   - integration fingerprint recomputes;
   - review-2 preflight blocks if any task review-1 is not `ACCEPT`.
4. Only then run a real GLM/Kimi double-owner stage.

## Footer

本地北京时间: 2026-07-08 18:56:51 CST
下一步模型: human
下一步任务: 修订 DRAFT-1 的 §6/§7/§8/§10，重点解决 metadata 交集、task-specific validator 文件、rebind hash 定义和 immutable-script guard。
