# Review: claude-opus4.6

> Reviewer identity disclosure: this review is written by **Claude Opus 4.6**
> (Anthropic provider). Claude is a review-2 decision model and the configured
> direction synthesis fallback; Anthropic provider is also the home of Fable5
> and Opus4.8, which wrote the prior REWORK review (`reviews/claude-opus4.8.md`).
> This review is **not** an implementation or fix author for any reviewed
> artifact. I have no direction synthesis, breakdown, or design authorship in
> this stage. `reviewer_prior_involvement: none`.

## Verdict

CONDITIONAL ACCEPT

## Summary

DRAFT-1 is a major improvement over the original `00-context-and-proposal.md`.
It absorbs the three critical findings from `claude-opus4.8.md` (F1 Option A →
committed-state scripts, F2 single-writer reassigned to deterministic scripts,
F4 review-1 stays cross-provider), and correctly rejects `codex_stage_recorder`
in favour of two deterministic scripts (`record-checkpoint`,
`prepare-review-2`) that never call models. The two-level fingerprint model
(task fingerprint for review-1, integration fingerprint for review-2) with a
mechanical rebind assertion is sound in principle and is the right design for
worktree-branched parallel delivery. However, the draft has several
specification gaps that would cause ambiguity or silent failure during
implementation. None are architectural; all are tightenable within the existing
design. I mark CONDITIONAL ACCEPT rather than REWORK because the direction is
now correct and the gaps are enumerable fixes, not structural redesign.

## Findings

### F1 — HIGH: `record-checkpoint` scope verification lacks a machine-readable scope source (§7.1 step 3)

**Evidence.** §7 says `record-checkpoint` must "校验 changed files 落在该 task
的 allowed scope 内（越界 → BLOCKED）." But the script's contract does not
specify **where** the allowed scope comes from. Candidates:
- `status.json.tasks[].scope` (exists in `parallel-development-mode.md` §5
  `embedded_reviews.<id>.scope`);
- A new `status.json.tasks[].allowed_files` field;
- A CLI `--scope` argument.

Without a canonical source, the script either hardcodes paths (brittle) or
skips the check (unsafe). The dispatch-ready validator
(`validate-stage.py:532-633`) already reads `tasks[].r10_checklist` which
contains `task_prompt_path` and `diff_patch_path` but not an explicit
`allowed_scope` glob.

**Impact.** If scope verification is not deterministic and machine-readable, R6
("实现终端提交 git 或改 status.json 即该 task 定性 REWORK") loses its
enforcement mechanism, and a task branch could contain out-of-scope changes that
the script does not catch.

**Recommendation.** Add `allowed_scope: ["backend/**"]` (glob list) to
`status.json.tasks[]` and use it as the authoritative input to
`record-checkpoint --task`. The validator's `dispatch-ready` phase should check
that scope lists are present and pairwise disjoint. Add `--scope` as a
redundant CLI argument that must match `status.json` (defense-in-depth).

### F2 — HIGH: rebind assertion (§6) is under-specified for merge commits and binary diffs

**Evidence.** §6 states:
> `sha256(integration_diff ∩ backend_paths) == backend task diff hash`

This assertion requires:
1. **Path-filtered diff extraction**: `git diff --binary <base>..<merge-head> -- backend/**`
   must produce the same bytes as `git diff --binary <base>..<backend-head> -- .`.
   This is true for a clean octopus/recursive merge with no conflict markers,
   but the draft does not specify **which merge strategy** is required or what
   happens if git inserts merge metadata (e.g., `.gitattributes` merge markers).

2. **Binary diff stability**: `git diff --binary` output includes index lines
   with abbreviated SHAs that may differ between the two computations (one from
   the task branch range, one from the integration branch range filtered by
   path). In practice, `git diff --binary <base>..<head> -- <paths>` computes
   the diff between the two trees, so the index lines should match. But this
   depends on the merge commit's tree being the bitwise union of the two task
   trees — which is only guaranteed if changed-file sets are truly disjoint
   **and** the merge strategy is recursive/ort with no rename detection across
   task boundaries.

**Impact.** If the rebind assertion fails spuriously (false negative), every
integration attempt BLOCKs, creating a workflow deadlock. If it passes
incorrectly (false positive), the guarantee of "no smuggled changes" is void.

**Recommendation.**
- Specify the merge strategy explicitly: `git merge --strategy=ort
  --no-rename-across-task-boundaries` or simply `git merge --no-edit
  <task-branch>` with a post-merge tree assertion.
- Define the rebind check as a **tree-level** assertion rather than a diff-byte
  assertion: for each task's scope paths, assert `git diff --stat
  <base>..<integration-head> -- <scope-paths>` exactly equals `git diff --stat
  <base>..<task-head> -- .`, then compare the sha256 of the path-filtered
  binary diffs. Document that if these diverge, the merge introduced
  renames or content changes outside the recorded scope.
- Alternatively, use tree object comparison:
  `git diff-tree <task-head>:<scope-path> <integration-head>:<scope-path>`
  must be empty. This is more robust than diff-byte comparison.

### F3 — HIGH: `record-checkpoint` test re-run does not specify test isolation (§7.1 step 2)

**Evidence.** §7 says the script "复跑该 task 的测试命令 →
`60-test-output-<task>.txt`." But:
- The script runs in a `git worktree` directory that contains **only** this
  task's changes. Depending on the project's test infrastructure, tests may
  import shared modules from `main`, use fixtures from the other task's scope,
  or depend on build artifacts that don't exist in the worktree.
- The draft does not specify whether the test command is taken from
  `status.json.tasks[].test_command`, from the r10_checklist
  `self_tests_command`, or from a CLI argument.

**Impact.** Tests that pass in the full repo may fail in the worktree (false
negative) or tests that fail in the full repo may pass in the isolated worktree
(false positive), both undermining evidence quality.

**Recommendation.** Specify:
1. The test command source: `status.json.tasks[].test_command` or
   `r10_checklist.self_tests_command` (prefer the latter since it already exists
   in the dispatch-ready contract).
2. The working directory: the task's worktree root.
3. Expected behavior: if the task's tests depend on shared infrastructure from
   `main`, the worktree should be set up with `git worktree add --track` from
   the stage branch base, ensuring shared code is present. Document this as a
   precondition.

### F4 — MEDIUM: `prepare-review-2` does not specify status.json conflict resolution mechanics (§7.2 step 7)

**Evidence.** §6 states: "集成分支的 status.json 由 `prepare-review-2` 独写并
**取得所有权**（merge 冲突以脚本写入的集成版为准）." But the script contract
does not specify the **mechanics**:
- Does the script `git merge --no-commit` both task branches, then overwrite
  `status.json` with a freshly computed integration version before
  `git commit`?
- Or does it `git merge` with `-X ours` for `status.json` and then patch the
  file?
- What about `70-handoff.md` and other stage-level files that may conflict?

**Impact.** If merge conflicts extend beyond `status.json` (e.g., both tasks
modify `60-test-output.txt` — which the draft implies they produce separately
as `60-test-output-<task>.txt`), the script's behavior is undefined.

**Recommendation.** Specify:
1. `prepare-review-2` merges each task branch with `--no-commit`.
2. For `status.json`, the script ignores both task-branch versions and writes a
   fresh integration status computed from the two task branch metadata.
3. For `60-test-output.txt`, the script runs its own full test suite (step 6)
   and writes the result fresh.
4. For any other conflict: the script ABORTs and writes BLOCKED. Changed-file
   disjointness (step 3) should prevent this, but the spec should have an
   explicit fallback.

### F5 — MEDIUM: §10 待改点 omits `stage-delivery.yaml` changes for the new branch topology

**Evidence.** §10 lists changes needed in `AGENTS.md`, `validate-stage.py`,
`schemas/`, and two new scripts. But `stage-delivery.yaml` also needs updates:

1. **`guards.stage_branch_name_template`** (line 24): Currently
   `"stage/{{stage_id}}"`. The new topology has `stage/<id>/backend-glm` and
   `stage/<id>/frontend-kimi`. The validator's
   `validate_stage_branch()` (line 462-512) checks `current branch ==
   status.json.stage_branch.name`; task branches won't match unless the
   template is extended or the validator accepts task-branch name patterns.

2. **New stage `task-branch-checkpoint`**: The workflow YAML has no stage
   between `implementation` and `review-1` for the per-task checkpoint that
   `record-checkpoint` performs. Either a new stage must be added, or the
   existing `test` + `review-1` preflight must be extended to handle per-task
   checkpoints.

3. **`embedded-cross-review-checkpoint` transitions** (line 483-498): Currently
   route failures to `bookkeeper-decision`. In the new mode, there is no model
   bookkeeper; failures should route to `human_escalation_required` or to the
   script's BLOCKED state.

**Impact.** Without YAML changes, the workflow contract and the actual execution
path diverge, which violates the authority order (`AGENTS.md` > workflow YAML >
everything else). A stage operator following the YAML literally would not find
the task-branch-checkpoint step.

**Recommendation.** Add `stage-delivery.yaml` to §10's change list with
specific items:
- Extend or parameterize `stage_branch_name_template` for task branches.
- Add an optional `task-branch-checkpoint` stage (or annotate that
  `record-checkpoint` is a sub-step of the existing `test` stage).
- Update `embedded-cross-review-checkpoint` transitions for the
  no-model-bookkeeper case.

### F6 — MEDIUM: §9 R1 "changed-file 交集为空" needs to cover status.json, test output, and evidence files (§9, R1)

**Evidence.** R1 states: "changed-file 交集为空；共享文件/schema/API
contract/fixture/全局配置一旦同时被改，禁止机械集成." But the disjointness check
must also handle:
- `status.json`: both task branches have their own version written by
  `record-checkpoint`. This is explicitly handled by §6 ("merge 冲突以脚本写入
  的集成版为准"), but R1 as stated would flag it as a disjointness violation.
- `60-test-output-<task>.txt`: if tasks write to different files, no conflict;
  but if either task creates `60-test-output.txt` (the canonical name), it
  conflicts.
- Evidence files in `reports/agent-runs/<stage>/`: both tasks write
  `20-implementation-<task>.md`, etc., which should not count as scope overlap.

**Impact.** An overly strict disjointness check would BLOCK every integration
because `status.json` is always modified by both branches. An overly loose
check would miss real conflicts.

**Recommendation.** R1's disjointness check should explicitly exclude from the
intersection calculation:
1. `reports/agent-runs/<stage>/status.json` (owned by scripts, not tasks)
2. `reports/agent-runs/<stage>/*.md` and `*.txt` evidence files (namespaced by
   task suffix)
3. Any path listed in a `script_owned_files` field

The check applies only to **product source files and shared configuration
files**, not to Harness evidence artifacts.

### F7 — MEDIUM: `human_decision` block (§8) lacks a validator enforcement path

**Evidence.** §8 defines the `human_decision` block that `prepare-review-2`
writes into `status.json`. §10 item 3 notes that a `human_decision` schema is
needed. But §10 item 2 (validator changes) says:
> "校验 `human_decision` 块存在于 review_2 前"

This is listed as a validator change but is not present in the current
`validate-stage.py`. The validator's `validate_common()` (line 636-686)
checks status, fingerprints, and worktree cleanliness, but has no
`human_decision` check. There is no `PRE_REVIEW_2_STATUSES` gate that
distinguishes review-1 → review-2 transitions from other transitions.

**Impact.** Without the validator check, a `prepare-review-2` invocation
without the `--human-decision` flag would produce an integration status.json
missing the `human_decision` block, and the validator would not catch it.
Review-2 would proceed without auditable human authorization.

**Recommendation.** Add to §10 item 2 an explicit validator requirement:
```python
if status == "review_2":
    human_decision = status_doc.get("human_decision", {})
    if not isinstance(human_decision, dict) or not human_decision.get("decision"):
        errors.append("review_2 requires human_decision block")
```
And specify that `prepare-review-2` must refuse to proceed without
`--human-decision` and `--rationale` CLI arguments (already partially present
in §7.2's CLI signature).

### F8 — MEDIUM: §7.2 step 9 reviewer disclosure note is imprecise about script-runner identity

**Evidence.** §7.2 step 9 says:
> "若 reviewer 曾任 recorder-脚本触发者不构成代码作者自审，但仍按现行披露规则处理"

This is correct in principle (running a deterministic script does not create
implementation authorship), but the phrasing "按现行披露规则处理" is vague. The
current `AGENTS.md` disclosure rules distinguish between:
- Implementation/fix authorship (hard ban on review-2)
- Design involvement (strong-reviewer override with disclosure)
- Bookkeeper involvement (must disclose in status.json)

The person who runs `prepare-review-2` is not a code author (the script is
deterministic), but they **are** the entity that produced the integration commit
and computed the integration fingerprint. This is analogous to the bookkeeper's
role, not the implementer's role.

**Impact.** Without clarity, a future review-2 might incorrectly flag the
script-runner as a code author and refuse to proceed, or incorrectly skip
disclosure.

**Recommendation.** Add a sentence to §9 or §7.2: "Running `record-checkpoint`
or `prepare-review-2` does not create implementation or fix authorship, does not
create design involvement, and does not require `reviewer_prior_involvement`
disclosure by the review-2 reviewer. The script runner is analogous to a CI
system: they produce committed state from deterministic operations, not from
judgment."

### F9 — LOW: §5 Phase 3 "单 task 机械锚定" timing relative to embedded pre-review is ambiguous

**Evidence.** §5 Phase 2 includes "执行预写对侧 fresh read-only 预审(R10)"
followed by "只在自己 scope 内修(封顶2轮)". Phase 3 is then "单 task 机械锚定
[scripts/record-checkpoint]". The question is: does `record-checkpoint` run
**after** embedded pre-review completes (including any fix rounds), or can it
run in parallel with the other task's pre-review?

The answer should be: `record-checkpoint` runs after the task's own embedded
pre-review cycle is complete (including fixes), because it needs the final code
state. But this is not explicitly stated.

**Impact.** Low — the dependency is implicit from the data flow (the script
commits the final state, which must include pre-review fixes). But for a
specification document, implicit is risky.

**Recommendation.** Add to Phase 3: "Runs after Phase 2 completes for this
task (including any fix rounds). The two tasks' Phase 3 may run in parallel
with each other."

### F10 — LOW: §12 trial plan does not specify the fallback merge strategy for a failed trial

**Evidence.** §12 item 5 says: "任一红线破 → 回退串行 bookkeeper 模式并重开本提案
为 DRAFT." But it does not specify what happens to the task branches and
integration branch if the trial fails mid-stream. Options:
- Abandon both task branches, return to `stage/<id>`, and restart
  implementation in serial mode on that branch.
- Cherry-pick successful task work from one branch into serial mode.
- Abandon the stage entirely.

**Impact.** Low — the user can decide at failure time. But specifying the
default simplifies the human operator's decision under stress.

**Recommendation.** Add: "On trial failure, both task branches are abandoned
(not merged). If reusable implementation work exists on one branch, it may be
cherry-picked to `stage/<id>` under serial mode at the human operator's
discretion. The stage branch `stage/<id>` remains the single branch for
serial mode."

## Required Changes

**Blocking (must fix before trial):**

1. **(F1)** Add `allowed_scope` to `status.json.tasks[]` and specify it as the
   authoritative input to `record-checkpoint` scope verification. Add pairwise
   disjointness check to `dispatch-ready` validator phase.

2. **(F2)** Specify the merge strategy in `prepare-review-2` (recommend
   `--no-commit` + tree-level assertion). Document the rebind assertion at the
   tree-object level or specify the exact `git diff` commands that produce
   byte-identical output. Add a worked example showing the exact commands.

3. **(F5)** Add `stage-delivery.yaml` to §10's change list with specific items
   for task-branch name templates, task-branch-checkpoint stage, and
   embedded-checkpoint transition updates.

4. **(F6)** Specify that R1's disjointness check excludes Harness-owned files
   (`status.json`, evidence artifacts) and applies only to product source files
   and shared configuration.

**Non-blocking (should fix, may land alongside or after trial):**

5. **(F3)** Specify the test command source and worktree isolation requirements
   for `record-checkpoint`.

6. **(F4)** Specify `prepare-review-2` merge conflict resolution mechanics for
   `status.json` and evidence files.

7. **(F7)** Add the `human_decision` validator check specification to §10.

8. **(F8)** Clarify script-runner identity vis-à-vis reviewer disclosure rules.

9. **(F9)** Clarify `record-checkpoint` timing relative to embedded pre-review.

10. **(F10)** Specify fallback merge strategy for trial failure.

## Open Questions

1. **Rebind assertion granularity**: Should the rebind check use diff-byte
   comparison (simpler but fragile with merge metadata), tree-object comparison
   (robust but requires additional git plumbing commands), or both (belt and
   suspenders)? The choice affects `prepare-review-2` implementation complexity.

2. **Worktree lifecycle**: Who cleans up worktrees after trial completion? Does
   `prepare-review-2` remove the task worktrees after successful integration, or
   does the human operator do it? This affects disk usage on long-running
   stages.

3. **Scope definition language**: Are scopes defined as git pathspecs (e.g.,
   `backend/**`), as regular expressions, or as explicit file lists? Pathspecs
   are simplest and integrate with `git diff -- <paths>`, but may not cover
   edge cases like generated files or build artifacts.

4. **Task-branch naming convention**: §4 shows
   `stage/<id>/backend-glm` and `stage/<id>/frontend-kimi`. Are these
   conventions fixed, or can the task prompt specify custom branch names? If
   fixed, the validator can enforce the pattern; if variable, the branch name
   must be recorded in `status.json.tasks[].branch`.

## Recommended Trial Plan

1. **Pre-trial changes (land on `main` via a separate LOW stage):**
   - Add `tasks[].allowed_scope` field to status.json convention and update
     `validate-stage.py` dispatch-ready phase to check pairwise disjointness.
   - Add `stage_branch.name` pattern support in `validate_stage_branch()` to
     accept `stage/<id>/<task>` names when the stage is in task-branch mode.
   - Implement `scripts/record-checkpoint` and `scripts/prepare-review-2` as
     shell scripts (Bash or Python, dependency-free, consistent with
     `validate-stage.py`'s philosophy).
   - Add `human_decision` block validation to `validate-stage.py` for
     `status == "review_2"`.
   - Add a trial-mode pointer in `AGENTS.md` (minimal, reversible).

2. **Select trial stage:**
   - One MEDIUM stage with strictly disjoint backend (GLM) + frontend (Kimi).
   - No shared schema files, no API contract changes during implementation.
   - Both tasks have existing test suites that can run in isolation.

3. **Execute:**
   - Phase 0: Design freeze with dual task prompts, embedded pre-review
     prompts, and R10 dispatch tails.
   - Phase 1: Human creates two `git worktree add` directories and dispatches.
   - Phase 2: GLM and Kimi implement in parallel, each running embedded
     pre-review via R10.
   - Phase 3: Human runs `record-checkpoint` for each task branch.
   - Phase 4: Human dispatches cross-review-1 (GLM→Kimi, Kimi→GLM).
   - Phase 5: Human runs `prepare-review-2` with `--human-decision
     proceed_to_review_2`.
   - Phase 6: Human dispatches review-2 to Codex/Claude.

4. **Success criteria:**
   - `validate-stage.py --phase dispatch-ready` passes before implementation.
   - `validate-stage.py --phase pre-review` passes for each task branch before
     review-1.
   - `record-checkpoint` scope verification catches (or correctly allows) all
     changed files.
   - `prepare-review-2` rebind assertion passes (integration diff == union of
     task diffs).
   - `validate-stage.py --phase pre-review` passes for integration branch
     before review-2.
   - review-1 can independently recompute task fingerprint from task branch.
   - review-2 can independently recompute integration fingerprint from
     integration branch.
   - `human_decision` block is present and schema-valid before review-2.
   - No task branch modified files outside its allowed scope.
   - Human intervention count: dispatch (2 commands) + `record-checkpoint` (2)
     + review-1 dispatch (2) + `prepare-review-2` (1) + review-2 dispatch (1)
     = 8 commands total, comparable to serial mode.

5. **Failure criteria / rollback:**
   - Any red line from §9 is broken → abandon both task branches, return to
     serial mode on `stage/<id>`, restart from Phase 1.
   - `prepare-review-2` rebind assertion fails → investigate whether the
     disjointness assumption was violated or whether the diff-byte comparison is
     unreliable. If the latter, switch to tree-object comparison before
     retrying.
   - Revert all `AGENTS.md` / validator / script changes on `main` if the trial
     reveals an architectural flaw (not just an implementation bug).

## Footer

本地北京时间: 2026-07-08 18:59:20 CST
下一步模型: human
下一步任务: 汇总本评审（claude-opus4.6）与已有评审（claude-opus4.8 REWORK、
glm52 REWORK、kimi-for-coding REWORK）的共识与分歧；根据 F1-F4 必改项修订
10-independent-task-branch-mode-draft.md 为 DRAFT-2；然后决定是否进入
§10 落地变更（validator/schema/scripts）。
