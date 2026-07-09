# Review: claude-opus4.8

## Verdict

REWORK

## Summary

The direction is sound and much less radical than it looks: "human-operated
dispatch" is already the current rule (Codex/GPT and Claude sessions prepare
packets, the human executes model dispatch), and the "bookkeeper" the proposal
wants to delete is really the *single non-implementer writer* that commits
evidence, writes `status.json`, computes fingerprints, and runs the validator —
work that is load-bearing and cannot simply disappear. What actually changes,
and where the risk is, are two things the proposal under-specifies: (1) the
"frozen evidence" scheme (Option A, working-tree `git diff` + sha256-of-diff +
`git status`) directly contradicts the committed-state Hard Gate, the single
diff_fingerprint scheme, and three concrete checks in `scripts/validate-stage.py`;
and (2) letting the implementer *generate* the review-1 evidence removes the
independent recompute that currently makes "model claims are not evidence" true.
Adopt the human-dispatch renaming, but keep committed-state fingerprints +
validator recompute + R4 reconciliation + non-implementer test re-run, define a
recorded human-decision artifact, update the validator status vocabulary, and
trial on exactly one low-blast-radius stage before touching canonical rules.

## Findings

### F1 — CRITICAL: "Option A" frozen evidence violates the committed-state Hard Gate and cannot pass the current validator

The "Candidate Evidence Command Shape" and Option A ("no candidate commit, use
diff hash + git HEAD/status") use `git diff --binary > review-1-candidate.diff`
against a dirty working tree plus `git status --short`, and a
`sha256(review-1-candidate.diff)` as the anchor. This collides head-on with:

- `AGENTS.md` Hard Gates: "Review gates require a committed repository state";
  "Diff fingerprint is defined as a single committed-state scheme:
  `head_sha + ":" + sha256(git diff --binary <base_sha>..<head_sha> ...)`";
  "Do not invent alternate fingerprint fields or worktree fingerprint
  protocols."
- `scripts/validate-stage.py`: `require_clean_worktree()` runs for `pre-review`
  and `pre-accept` and will FAIL on the dirty tree Option A produces;
  `worktree_fingerprint` is an explicit rejected field; `commit_state ==
  "uncommitted_working_tree"` is rejected.
- A sha256 of a working-tree diff file is a *second, different* fingerprint
  (different base range, includes `status.json`, binary diff of uncommitted
  state) — exactly the "alternate fingerprint protocol" the Hard Gate bans.

Option A is not adoptable. Use Option B: the non-implementer writer makes a local
candidate commit on the stage branch (`head_sha`), and the "frozen evidence
packet" becomes a convenience *bundle derived from committed state*, not a
replacement anchor. The `.diff` should be `git diff --binary <base_sha>..<head_sha>`
and its hash is redundant to the canonical `diff_fingerprint`, not a new gate.

### F2 — HIGH: The commit / single-writer authority is dropped, not reassigned

Today the bookkeeper is the single writer for git commits, `status.json`,
`base_sha`/`head_sha`/`diff_fingerprint`; implementers are *forbidden* to commit
(parallel-mode R6). The proposal removes the model bookkeeper and has implementers
"generate frozen evidence," but never names who now commits and writes
`status.json`. Two bad outcomes if left unspecified:

- Implementer commits + writes status → breaks the single-writer invariant and
  R6, and recreates the exact dual-hat degradation that
  `docs/parallel-development-mode.md` §8 finding #1 was written to fix (implementer
  swallows stage-flow discipline).
- Human hand-commits and hand-computes fingerprints → large new manual error
  surface; humans should not compute `diff_fingerprint` by hand.

Key point the proposal misses: **running `git commit`, `pytest`, and
`validate-stage.py` is not "model dispatch execution."** The only thing forbidden
to Codex/Claude sessions is *invoking another model terminal*. So a
non-implementer Codex/Claude session can legally remain the single writer/committer
while the human executes model dispatch. That means the bookkeeper's *function*
must survive under a new name; only its *name* and its (already-absent) dispatch
authority are being removed.

### F3 — HIGH: Implementer-generated evidence is "model claims" unless independently recomputed

"Model claims are not evidence" (Hard Gate). A diff/hash/test-output the
implementer writes into files in its own working tree is a model claim wearing a
filename. review-1 "verifying evidence completeness first" only checks *presence*
of six files — it does not prove the diff matches reality or that
`60-test-output.txt` came from the reviewed state. The current system's real
protection is that a *non-implementer* commits and the validator *recomputes*
`diff_fingerprint` from git, and (parallel-mode R4) the bookkeeper regenerates and
reconciles each task diff and re-runs tests. The proposal silently drops R4
reconciliation and the non-implementer test re-run — that is a regression.
Implementer-authored *narrative* (`20-implementation.md`) is fine; the *diff and
test output must be regenerated/verified against committed state by a
non-implementer actor.*

### F4 — MEDIUM: Making review-1 "usually Codex" is a regression against the two-layer model

The proposed role table sets `formal_review_1` = "Usually Codex." Current design
keeps review-1 as the cheap cross-provider catch between implementers
(`claude_glm ↔ kimi`) and reserves Codex→Claude as the review-2 *decision* gate.
Defaulting review-1 to Codex (a) collapses the two layers, (b) burns the scarce
decision-model provider on the first pass, and (c) risks provider-identity
overlap bookkeeping at review-2. Keep review-1 cross-provider from the implementer
pool; escalate to Codex/Claude only when the human explicitly asks.

### F5 — MEDIUM: New status vocabulary fails closed in the validator

None of the proposed states (`design_freeze`, `dispatch_packet_prepared`,
`human_dispatched_to_implementers`, `implementer_run`, `embedded_pre_review`,
`scoped_fix_loop`, `frozen_evidence_prepared`, `formal_review_1`,
`awaiting_human_decision_after_review_1`, `fix_assigned`, `review_2_dispatched`,
`final_review_2`) except `stage_accepted_waiting_user` are in
`ALLOWED_STATUSES`. Hard Gate: unknown status values "fail closed and route to
`human_escalation_required` unless the Harness schema, docs, and validator are
updated first." Worse, `formal_review_1` is not in `PRE_REVIEW_STATUSES`, so the
fingerprint-required and clean-worktree gating keyed on `review_1`/`review_2`
would silently not fire. The validator must be patched (either map new states
onto existing gate classes, or extend `ALLOWED_STATUSES` + `PRE_REVIEW_STATUSES`)
*before* any trial run.

### F6 — MEDIUM: The human decision gate has no required artifact — the least-logged step is the most consequential

`awaiting_human_decision_after_review_1 → fix | review_2` is the branch that
decides the stage, yet no artifact is defined for it. Every other transition
today produces `status.json` + verdict JSON + handoff. Without a recorded
`human_decision` block (decided_by, decision, rationale, reviewed_fingerprint,
timestamp), the claim "human-operated dispatch is auditable" is false precisely
at the decision point. Add the block and a validator check that a
`human_decision` exists before review-2 or a fix is dispatched.

### F7 — LOW/MEDIUM: The 6-file "minimum evidence" is narrower than the required review artifact set

The list omits `00-task.md`, `10-design.md`, `11-adr.md`,
`12-development-breakdown.md`, `06-direction-synthesis.md`, `40-fix-report.md`,
and prior review files — all of which reviewers are *required* to read
(`reviewer_uses_raw_artifacts`). If the frozen packet becomes the review-1 input,
review-1 loses its ability to check contract drift and scope. State explicitly
that frozen evidence *augments* the standard artifact set; it never replaces it.

### F8 — LOW: `git-status.txt` contradicts a committed model

Under Option B (committed) `git status --short` is empty and adds nothing;
recording it as evidence implies the uncommitted Option A. Drop it as an anchor
input — `require_clean_worktree()` already enforces cleanliness at the gate.

## Required Changes

Mandatory before adoption (blocking):

1. Replace Option A with Option B. Frozen evidence is a bundle *derived from a
   committed stage-branch state*; keep the single canonical `diff_fingerprint`;
   do not add a diff-file sha256 as a gate anchor. (F1)
2. Name the surviving single writer/committer explicitly and keep it a
   *non-implementer* session; state that git/test/validator execution is not
   "model dispatch" and remains allowed for that session while the human executes
   model-terminal dispatch. (F2)
3. Preserve, do not drop: R4 diff reconciliation, non-implementer test re-run,
   and validator fingerprint recompute against committed state. (F3)
4. Patch `scripts/validate-stage.py` (statuses + pre-review/pre-accept gate
   classes) and update `AGENTS.md`/YAML/schema *before* the trial, so no run
   depends on unknown states. (F5)
5. Add a required, validated `human_decision` artifact for the
   post-review-1 branch. (F6)
6. Keep review-1 as cross-provider from the implementer pool; do not default it
   to Codex. (F4)
7. Clarify that frozen evidence augments — never replaces — the required review
   artifact set. (F7)

Recommended (non-blocking):

- Drop `git-status.txt` as an anchor input. (F8)
- Reframe the proposal's headline: this is mostly *renaming* the bookkeeper to a
  human-operated `stage_operator` + non-implementer `writer`, not deleting its
  function. That framing prevents the accidental loss of the commit authority.

## Open Questions

1. After removal, is the single committer/`status.json` writer a Codex/Claude
   *dispatch_author* session (allowed to run git/tests/validator), or is the
   human expected to run those commands? This must be decided before trial. (F2)
2. If the opposite pre-review model is unavailable, who produces the embedded
   pre-review evidence? The implementer must NOT self-fill; confirm the
   escalation path. (failure mode)
3. Does the user accept keeping review-1 cross-provider (GLM/Kimi) rather than
   Codex-by-default? (F4)
4. This is a HIGH harness change; is the user approving a lightweight route
   (no direction panel) for the rule change itself?

## Recommended Trial Plan

1. Land the validator + docs changes first, on `main`, behind the existing
   status-vocabulary so nothing runs on unknown states (F5). Keep `AGENTS.md`
   rule edits minimal and reversible.
2. Pick one LOW/MEDIUM parallel stage with clean, non-overlapping
   backend/frontend scope and cheap rollback to serial bookkeeper mode.
3. Run it on a dedicated `stage/<id>` branch (existing stage-branch mechanism) so
   any red-line breach never corrupts `main` rules.
4. Use Option B end to end: implementer produces narrative + runs self-tests →
   non-implementer writer commits candidate, re-runs tests, R4-reconciles, computes
   `diff_fingerprint`, runs `validate-stage.py --phase pre-review` → cross-provider
   review-1 against committed fingerprint → record `human_decision` → human
   dispatches review-2 (Codex, then Claude).
5. Success criteria: `validate-stage.py` passes at every gate with the new
   statuses; every transition (including the human decision) has a recorded
   artifact; review-2 can independently recompute the reviewed fingerprint from
   git. Any red-line breach → revert to serial bookkeeper mode and re-open this
   proposal as DRAFT.

## Footer

本地北京时间: 2026-07-08 16:44:03 CST
下一步模型: human
下一步任务: 汇总各外部评审（本文件 REWORK）结论；先落地 F1/F2/F5 阻塞项
（Option B + 单一写者归属 + validator 状态词表），再择一个低风险 parallel
stage 试运行。
