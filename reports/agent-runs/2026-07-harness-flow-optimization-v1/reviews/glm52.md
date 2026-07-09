# Review: glm52

> Reviewer identity disclosure: this review is written by **GLM-5.2**
> (`zhipu_glm`, the `claude_glm` adapter). GLM is one of the two implementer
> models whose autonomy this proposal *expands* (running through review-1
> evidence preparation). Findings about implementer self-authority over
> evidence/commits are therefore not abstract to me — please weight them as a
> mildly self-interested party flagging where its own role gains power, and
> apply the normal "reviewer may equal designer is allowed, but independence of
> the *gate* still matters" scrutiny.

## Verdict

REWORK

## Summary

The direction is sound and mostly already true: the human already owns dispatch
execution (`AGENTS.md` Roles; `model_dispatch_execution_requires_human`), and
collapsing the bookkeeper's *decision/orchestration* authority into the human
operator is safe and desirable. But the proposal as written reopens the single
most important invariant it claims to preserve — *reproducible, anchored
evidence before formal review* — by recommending "Option A" (uncommitted
worktree diff + loose `git-head.txt`/`git-status.txt`) as the frozen-evidence
mechanism. That mechanism is not merely weaker than the current committed-state
fingerprint; it is **structurally incompatible** with the current validator and
directly violates three hard gates. It also removes the bookkeeper's mechanical
single-writer duties (status.json, local evidence commit, fingerprint) without
reassigning them, which would repeat the v0.3 dual-hat failure already recorded
in `parallel-development-mode.md` §8-5. Adopt the human-dispatch direction, but
drop Option A, keep committed-state fingerprints, and explicitly reassign the
mechanical writer role before any trial.

## Findings

### P0 — Frozen-evidence "Option A" contradicts canonical rules and the proposal's own invariant

The proposal recommends (§Key Design Changes #7, §Candidate Evidence Command
Shape): *Option A — no candidate commit, use `git diff --binary > candidate.diff`
+ sha256 + `git rev-parse HEAD` + `git status --short`*, and explicitly
recommends "begin with Option A."

This violates, concretely:

- `workflows/templates/stage-delivery.yaml:29` `require_committed_state_before_review: true`.
- `workflows/templates/stage-delivery.yaml:32` `forbid_worktree_fingerprint: true`.
- `AGENTS.md` Hard Gates: "Review gates require a committed repository state";
  "Diff fingerprint is defined as a single committed-state scheme … Do not
  invent alternate fingerprint fields or **worktree fingerprint protocols**."
- `scripts/validate-stage.py:831` `require_clean_worktree(...)` runs for
  `pre-review`/`pre-accept`.
- `scripts/validate-stage.py:681-684` rejects `worktree_fingerprint` and
  `commit_state == "uncommitted_working_tree"`.
- `scripts/validate-stage.py:667-668` requires `head_sha != base_sha` before
  review.

The contradiction is airtight and structural, not stylistic:

- `require_clean_worktree` demands a clean tree at pre-review. But the proposed
  command `git diff --binary > candidate.diff` (no range) captures *unstaged
  working-tree* changes. A clean tree ⇒ empty diff; a dirty tree ⇒ the validator
  fails. The two requirements cannot both hold. Option A is literally
  un-runnable against the current gate.
- `git rev-parse HEAD` is a moving symbolic ref. After the implementer emits the
  packet and before review-1 runs, any commit (Harness sync on `main`, another
  task, a status commit) moves HEAD, so `git-head.txt` no longer describes the
  base the diff was computed against. The committed-state `base_sha..head_sha`
  protocol is immune to this; the proposed packet is not.
- A loose `.diff` + `.sha256` does not bind the diff to the repository. A
  reviewer can confirm the file was not corrupted, but **cannot recompute it
  from the repo** (the tree has moved). Tamper-evidence degrades from
  "independently reproducible from commits" to "the author didn't garble the
  file."

Most damning: the proposal states its own invariant — *"Formal review-1 must
not review a moving worktree"* (§Frozen Evidence) — and then recommends the one
mechanism that produces a moving-worktree snapshot. Intent and mechanism
contradict.

For context, the project already went the other way on purpose:
`parallel-development-mode.md` R4 explicitly records `git diff >
.diff.patch` only as a **non-binding pre-review snapshot** ("此文件是证据快照，
**不是**指纹，不得用于任何门禁绑定"). Option A promotes that snapshot into a
gate-binding artifact — a regression of discipline hard-won in v0.3/v0.4.

### P1 — Single-writer / commit / fingerprint duties removed but not reassigned

The bookkeeper is currently the **single writer** for `status.json`, local
evidence commits, and the binding `diff_fingerprint`
(`AGENTS.md` Roles §Orchestrator And Bookkeeper; `docs/harness-design.md`
"single writer"; `parallel-development-mode.md` R6). The proposal's role table
replaces the bookkeeper with `human_stage_operator` whose listed duties are
"chooses next action, copies prompts into model terminals, decides after
review-1, authorizes review-2 and merge." **None of the mechanical
single-writer duties are reassigned.** That leaves three bad options:

1. GLM/Kimi implementers commit + write status.json + compute the fingerprint →
   direct violation of R6 single-writer, and the fingerprint is self-authored
   by the code author (no independent anchoring). This is exactly the v0.3
   failure: `parallel-development-mode.md` §8-5 finding #1 records that
   "dual-hat (bookkeeper 兼 implementer-A) 实际退化为纯实现者" — when the
   implementer is also the writer, flow discipline collapses. The proposal
   re-institutes the configuration the project already rejected.
2. The human does it — fine, but then `human_stage_operator` must explicitly own
   "creates local evidence commit, computes `diff_fingerprint`, writes
   `status.json`, runs validator," and the role table / `AGENTS.md` must say so.
3. A thin "recorder" session does it — also fine, but then the bookkeeper isn't
   really removed, just renamed, which is the honest framing.

The proposal must pick one explicitly. My recommendation: the human (or a
recorder) owns the mechanical writes; GLM/Kimi implementers prepare source,
tests, and reports **up to but not including** the review commit, and must not
commit, write `status.json`, or compute the binding fingerprint. That preserves
the evidence model while still removing the model bookkeeper as
*decision-maker* — which is what the user actually asked for (see Open Questions).

### P1 — The evidence `git diff` command is ambiguous and frequently wrong

`git diff --binary` with no range/HEAD shows only **unstaged** changes
(working tree vs index). If the implementer staged everything (`git add -A`),
this is empty; if changes are partly staged, it shows a partial/incorrect diff.
For a binding artifact this is unacceptable. The only correct form is
`git diff --binary <base_sha>..<head_sha>` against two commits — which requires
the candidate commit Option A is trying to avoid. (See P0.)

### P1 — review-1 "usually Codex" contradicts registry/YAML routing and erodes gate independence

The role table sets `formal_review_1` owner to "Usually Codex, or user-selected
reviewer." But:

- `agents/registry.yaml:364-366` and `workflows/templates/stage-delivery.yaml:127-135`
  define `review_1_cross_review_pool: [kimi, claude_glm]`. **Codex is not in the
  pool**, and `review_1_selection_rules` (`registry.yaml:372-376`) route by
  implementer provider (`claude_glm → kimi`, `kimi → claude_glm`). Routing
  review-1 to Codex by default silently overrides canonical routing.
- Layered-gate independence: review-2 is "the actual final gate"
  (`docs/harness-design.md` Anti-Self-Review; `AGENTS.md` "do not seek second
  opinion after a valid GPT/Codex review-2 verdict"). If Codex performs
  review-1 *and* review-2, the two-gate independence collapses into one
  decision model passing twice. The validator does not forbid `review_2.provider
  == review_1.provider`, so this is not a hard violation, but it defeats the
  design intent and should be a stated, justified choice, not a default.

(Nota bene: `review_1_may_equal_designer: true`
(`stage-delivery.yaml:148,572`), so Codex doing review-1 after direction
synthesis needs *no* disclosure override — that specific sub-concern is not
valid. The valid concerns are the pool/routing mismatch and gate collapse.)

### P1 — Human-operated dispatch must inherit R9 receipt + raw-output + invalid-JSON discipline

Auditability of dispatch currently rests on `parallel-development-mode.md` R9/R10:
dispatch **files** with RECEIPT blocks + raw-output evidence, not chat-window
relay ("the prohibition is against unlogged chat-window relay,"
`parallel-development-mode.md:274-279`). The proposal's `human_stage_operator`
role says "copies prompts into model terminals" but does **not** bind the human
to the `.dispatch.md` / RECEIPT / raw-output discipline. Without that, the human
becomes an unaudited manual bridge — the precise failure mode R9 exists to
prevent.

Separately, invalid-verdict-JSON handling is currently bookkeeper-driven
(`registry.yaml` `invalid_json_verdict: retry_once_then_fallback...`,
`invalid_json_max_attempts_per_model: 2`; `review-verdict.schema.json` enforces
`next_action`; validator checks `invalid_json_attempts ≤ 2` at
`validate-stage.py:743-745`). If the human dispatches review-1 to Codex and
Codex returns invalid JSON twice, **who counts attempts and routes to
fallback?** The proposal is silent. The human dispatcher must own recording
`invalid_json_attempts` and following the fallback ladder, or this audit trail
breaks.

### P2 — Nearly all proposed new states are absent from the validator's allow-list

Proposed states (`dispatch_packet_prepared`, `human_dispatched_to_implementers`,
`embedded_pre_review`, `scoped_fix_loop`, `frozen_evidence_prepared`,
`awaiting_human_decision_after_review_1`, `fix_assigned`, `review_2_dispatched`)
are **none** of them in `ALLOWED_STATUSES` (`validate-stage.py:21-37`). Any
transition into them fails closed → `human_escalation_required` (`AGENTS.md`
Hard Gate on unknown status values). So the proposal is not trialable at all
without validator edits — consistent with the proposal's own "validator changes
required," but the scope is larger than implied: it is essentially the entire
state vocabulary.

Recommend minimizing churn: model the post-review-1 human pause as the existing
`paused` status plus a `70-handoff.md` note, rather than a new enum value. Most
of the proposed mid-states (`dispatch_packet_prepared`, `scoped_fix_loop`, etc.)
are process narration, not machine-enforceable gates; they belong in handoff
text, not `ALLOWED_STATUSES`.

### P2 — Parallel-mode interaction is unaddressed

`parallel-development-mode.md` §3 Phase 3, R4, R6 assign the bookkeeper:
re-generate and reconcile each task diff before committing (R4 落盘前对账),
**serially** create H_A/H_B evidence commits, compute task fingerprints, and
prepare the formal review-1 dispatch packet against committed fingerprints. The
proposal says nothing about how these transfer when the bookkeeper is gone. With
two implementers running in parallel and no single writer, R4 reconciliation and
serial commits become unowned, high-risk manual git surgery. This must be
specified before any parallel stage tries the new flow.

### P2 — "Opposite implementer model" is looser than the registry's provider rule

The role table defines `embedded_pre_reviewer` as "Opposite implementer model."
For single-domain tasks there is no "opposite implementer." The authoritative
rule is provider-based, not role-based
(`registry.yaml:372-376`; `parallel-development-mode.md:269-273`: reviewer derived
from implementer provider via review-1 selection rules, "not inferred from
'backend' or 'frontend' wording"). Keep the registry wording; "opposite
implementer" is misleading for single-model tasks.

### P2 — Commit-policy recommendation is inverted

The proposal recommends "begin with Option A, then add local candidate commits
only if review reproducibility is still weak." It should be the reverse: only
Option B (local candidate commit + committed-state fingerprint) is compatible
with current gates. Begin with committed-state evidence; *only* consider any
loose-snapshot path if a strictly stronger reproducibility story than
`base_sha..head_sha` exists — and none is proposed here.

### P3 — Evidence path collides with a required stage file; schema prose is stale

- The proposed packet lists `60-test-output.txt` as a frozen-evidence artifact,
  but `60-test-output.txt` is already a required stage file
  (`validate-stage.py:690`). Overloading it conflates the stage test log with
  the review-candidate evidence. Put review-candidate evidence under a distinct
  `evidence/` subpath (the proposal's `mkdir …/evidence` already implies this;
  make it explicit and drop `60-test-output.txt` from the candidate list).
- `schemas/review-verdict.schema.json:5,100` still says "controller" in prose.
  If the role is renamed, schema prose should be reconciled (cosmetic; the
  `role`/`next_action` enums themselves need no change for this proposal).

## Required Changes

1. **(P0) Drop Option A.** Mandate committed-state evidence: implementers prepare
   source/tests/reports but do **not** commit; `human_stage_operator` (or a
   recorder) creates the H_x candidate commit on the stage branch and computes
   the canonical
   `diff_fingerprint = head_sha + ":" + sha256(git diff --binary <base>..<head> -- . ":(exclude)reports/agent-runs/<stage>/status.json")`.
   review-1 audits by **recomputing** the fingerprint from `base_sha..head_sha`,
   not by hashing a loose `.diff`. Loose `git diff > .patch` + `git-status.txt`
   may be kept only as clearly **non-binding** supplementary snapshots
   (parallel-mode R4 semantics).
2. **(P1) Reassign single-writer duties explicitly.** In the role table and
   `AGENTS.md`, state that GLM/Kimi implementers must not commit, write
   `status.json`, or compute the binding fingerprint (inherit R6). The human
   (or recorder) owns those mechanical writes plus validator runs.
3. **(P1) Fix the evidence command** to commit-anchored ranges; remove
   `git diff` (no range) and remove loose `git-head.txt`/`git-status.txt` as
   *binding* artifacts.
4. **(P1) Decide review-1 ownership and reconcile routing.** Either keep the
   Kimi/`claude_glm` cross-review pool as the review-1 default and reserve
   Codex/Claude for review-2, or formally amend
   `registry.yaml#review_1_cross_review_pool`,
   `registry.yaml#review_1_selection_rules`, and
   `stage-delivery.yaml#rotation.review_1`. Do not silently default review-1 to
   Codex.
5. **(P1) Bind `human_stage_operator` to R9/R10 dispatch discipline**
   (dispatch files + RECEIPT + raw-output evidence) and to invalid-JSON attempt
   counting + the fallback ladder. Add validator checks for human-executed
   dispatch receipts where feasible.
6. **(P2) Minimize new status enum values.** Model the post-review-1 pause as
   `paused` + handoff. Add any genuinely new value to `ALLOWED_STATUSES` and to
   `PRE_REVIEW_STATUSES`/`PRE_ACCEPT_STATUSES` as appropriate, with explicit
   transitions in the YAML.
7. **(P2) Specify the parallel-mode interaction:** who performs R4 diff
   reconciliation and serial H_A/H_B commits when the bookkeeper is removed.

## Open Questions

1. **Which "bookkeeper" is being removed?** The bookkeeper has two jobs:
   (a) *orchestration decisions* (choose next action, route review, decide after
   review-1) and (b) *mechanical single-writer duties* (status.json, evidence
   commit, fingerprint, validator). The user's stated intent targets (a). The
   proposal's wording targets both. These should be decided separately —
   removing (a) is safe; removing (b) without reassignment is not. Human input
   required.
2. **Who is the mechanical single-writer** when the model bookkeeper is gone —
   the human for every stage, or an occasional thin recorder session? This
   changes the human's per-stage effort materially.
3. **Is review-1 intended to move to the decision models (Codex/Claude)** or
   stay in the Kimi/`claude_glm` cross-review pool? This affects both registry
   routing and the independence of the review-2 final gate.
4. **For parallel stages,** does the human accept the R4 reconciliation +
   serial-commit manual load, or does parallel mode retain a recorder while
   only serial stages go fully human-operated?

## Recommended Trial Plan

Run this on **one single-domain, non-parallel MEDIUM stage** before touching any
canonical doc/YAML/registry/schema/validator:

1. Keep the existing committed-state fingerprint protocol and the validator
   **unchanged**.
2. Human = single writer: creates the stage branch at H_intake, creates the H_x
   candidate commit, computes `diff_fingerprint`, writes `status.json`, runs
   `validate-stage.py --phase pre-review`.
3. GLM implements backend (or Kimi frontend) through implementation, embedded
   pre-review, and scoped fix, and **prepares** evidence files — but does not
   commit, does not touch `status.json`, does not compute the binding
   fingerprint.
4. Embedded pre-review by the cross-review pool member (registry selection
   rule); formal review-1 stays in the pool (Kimi for a GLM implementer).
5. Human dispatches review-1, then review-2 to Codex, filling R9 dispatch files
   + RECEIPT + raw-output evidence, and recording `invalid_json_attempts`.
6. Human decides fix direction vs review-2 dispatch from review-1 output.

**Success criteria** (all must hold):

- `validate-stage.py --phase pre-review` and `--phase pre-accept` pass
  **unmodified**.
- review-1 can independently recompute the fingerprint from `base_sha..head_sha`
  and it matches.
- The entire dispatch chain is reconstructable from dispatch files + RECEIPT
  blocks alone (no chat-window reliance).
- No single-writer violation (R6): implementers never committed or wrote
  `status.json`.
- Human effort comparable to or better than a baseline serial stage.

Run ≥2 such trials. Roll back to serial bookkeeper mode on **any** single-writer
or evidence-anchoring breach, and only then propose canonical
`AGENTS.md`/workflow/registry/schema/validator edits.

## Footer

本地北京时间: 2026-07-08 16:47:58 CST
下一步模型: claude / codex（其余外部评审）→ human
下一步任务: 收齐其余 model 评审后，由 human 综合「必改项」，按本 review 的 P0/P1 先修订 `00-context-and-proposal.md`（放弃 Option A、重新分配单一写者、厘清 review-1 归属），再决定是否进入单阶段试运行。
