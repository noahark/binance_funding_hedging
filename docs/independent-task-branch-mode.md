# Independent Task-Branch Mode

Status: **TRIAL** (enablement landed 2026-07-08). This is an optional execution
variant of `workflows/templates/stage-delivery.yaml` for double-owner stages
(GLM backend + Kimi frontend) where the two product task scopes are disjoint. It
lets both tasks reach review-1 with zero extra human involvement, folding the one
unavoidable integration/serialization point into the human's review-2
preparation.

The full, reviewed contract is DRAFT-2 rev c2:
`reports/agent-runs/2026-07-harness-flow-optimization-v1/10-independent-task-branch-mode-draft.md`
(reviewed to 2×ACCEPT; see that stage's `status.json.decision_log`
DEC-2026-07-08-001..004).

## What it is

- **Recorder** `scripts/record-checkpoint` — deterministic script (no model),
  runs from a trusted checkout, anchors one task branch to review-1 (commit C_e,
  canonical fingerprint, product rebind hash, task-local evidence). It is NOT a
  model bookkeeper and its output is independently recomputable from git.
- **Integrator** `scripts/prepare-review-2` — deterministic script, ingests the
  two task worktrees' uncommitted checkpoint + review-1 evidence, enforces
  anti-stale-tip, merges the disjoint branches atomically, proves the rebind,
  reruns full tests, and writes the single top-level `status.json` for review-2.
- Both share `scripts/_itbm.py` (the pinned canonical fingerprint invocation,
  decision C).

## Single-owner recorder

`record-checkpoint --single-owner` is the single-implementer variant (one
worktree on the integration branch, no task split). In addition to committing
the delivery changes and printing the fingerprint, it now writes the top-level
`status.json` review metadata (`base_sha`, `head_sha`, `diff_fingerprint`,
`changed_files`) and makes a status-only commit. Because `status.json` is
excluded from the canonical fingerprint, that metadata commit does not change
the recorded `diff_fingerprint` and introduces no self-referential fingerprint.

Flags:

- `--single-owner` writes the metadata and makes the status-only commit.
- `--single-owner --dry-run` performs **no repository mutation**: it does not
  `git add`, does not `git commit`, does not write `status.json`, and leaves
  `HEAD`, the index, and the worktree unchanged. It reads the current branch tip
  and prints the status fields computed over the already-committed state, so it
  is a side-effect-free preview. (It therefore does not reflect uncommitted
  pending changes, which the non-dry-run path would commit first.)

### Evidence ordering for single-owner pre-review (evidence-before-anchor)

The first single-owner run hit review-1 friction because the validator evidence
(`61-validate-pre-review.txt`) was committed *after* `head_sha` was anchored, so
the reviewed `base_sha..head_sha` range did not contain it. The supported
ordering is one of:

1. **Evidence-before-anchor (preferred).** Commit all implementation and report
   evidence so the worktree is clean, then capture the validator output with the
   clean-worktree-safe flag and commit it *before* anchoring `head_sha`:

   ```bash
   # clean worktree -> validator passes -> writes evidence without tee-dirtying
   python3 scripts/validate-stage.py <stage-id> --phase pre-review \
     --evidence-out reports/agent-runs/<stage-id>/61-validate-pre-review.txt
   git add -A && git commit -m "validator pre-review evidence"
   # NOW anchor head_sha at a tip that includes the validator evidence
   python3 scripts/record-checkpoint <stage-id> --single-owner \
     --branch stage/<stage-id> --task-worktree <repo> --base-sha <base-sha>
   ```

   `record-checkpoint --single-owner` re-anchors `head_sha` at the current branch
   tip, so re-running it after the evidence commit moves the recorded
   `base_sha..head_sha` range to include the validator evidence.

2. **Reconcile-after (equivalent).** Anchor `head_sha` first, capture the
   validator evidence, commit it, then recompute `head_sha` / `diff_fingerprint`
   (re-run `record-checkpoint --single-owner`, or recompute by hand) so the
   reviewed range includes the evidence commit.

Either way the goal of F2 is: `61-validate-pre-review.txt` must be inside, or
safely reconciled with, the recorded `base_sha..head_sha` range that review-1
inspects.

## Evidence Conventions

Reviewers and stage operators should treat two evidence semantics as accepted
conventions, not as defects:

- **Delivery-anchored `head_sha`.** `head_sha` points at the delivery commit
  that review inspects. Later auxiliary commits — the status-only metadata
  commit from `record-checkpoint --single-owner`, a `70-handoff.md` update, or a
  re-anchoring commit — do **not** move `head_sha` unless the stage explicitly
  re-anchors and re-validates. Review prompts must use the
  `<base_sha>..<head_sha>` range recorded in `status.json`, never a moving
  `HEAD`, because unrelated Harness commits may land after the delivery commit.
  If the branch tip drifts past `head_sha` and the drift should be reviewed,
  re-anchor `head_sha` to the new tip and rerun
  `validate-stage.py --phase pre-review` before dispatch.

- **Validator fixed-point property.** A validator log committed into the
  repository cannot contain the fingerprint of the commit that contains itself
  (self-reference is impossible). Therefore a committed
  `61-validate-pre-review.txt` records the fingerprint of the head *as it was
  before the log was included* — a pre-inclusion snapshot. The authoritative
  final fingerprint always lives in `status.json.diff_fingerprint`. Treat the
  log fingerprint as "validation passed at this prior head", and treat
  `status.json` as the source of truth for the reviewed range.

These conventions are why `--evidence-out` exists (F4): it lets the validator
check a clean worktree and write the evidence file *after* passing, so evidence
capture no longer dirties the worktree before the clean-worktree check.

## Invariants preserved

Committed-state review gates, the single canonical diff fingerprint (no worktree
fingerprint), no new status enum values, cross-provider review-1 (GLM↔Kimi),
human-executed review-2 dispatch (Codex→Claude). Running the scripts / git /
pytest / `validate-stage.py` is not model dispatch.

## Verify

```bash
python3 scripts/tests/itbm_dry_run.py   # 17 assertions: positive path + fail-closed gates + single-owner status write + dry-run no-mutation
```

Template: `reports/agent-runs/_template/independent-task-branch-mode/`.
Schema: `schemas/independent-task-branch-mode.schema.json`.
