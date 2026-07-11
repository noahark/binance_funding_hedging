# Review: Auto Review Pipeline Design Note (Codex)

Status: **PRE-STAGE REVIEW — REWORK**
Date: 2026-07-10
Reviewer: GPT/Codex
Reviewed document: `reports/follow-ups/2026-07-auto-review-pipeline-design-note.md`

This is an independent pre-stage design review, not a formal Harness review
gate: no committed delivery diff is under review, so no schema-bound verdict
JSON or `diff_fingerprint` applies. It does not authorize any change to
`AGENTS.md`, product code, or an active product stage.

## Verdict

**REWORK.** The direction is promising, but the proposed §4 sequence cannot
enter implementation as written. The repair below is suitable as input to a
dedicated Harness revision stage after user approval.

## Blocking Design Findings

### 1. Seal order is incompatible with the committed-state gate

The proposed sequence is `seal -> embedded pre-review -> Grok review-1`.
Embedded pre-review writes evidence files after the seal, making the worktree
dirty. `scripts/validate-stage.py --phase pre-review` rejects a dirty worktree.
Leaving those artifacts uncommitted prevents formal review; committing them
after the recorded snapshot leaves their relation to the reviewed fingerprint
undefined.

Required repair: run embedded pre-review before the review snapshot seal, then
rerun blocking checks and create one clean committed snapshot containing code,
tests, test logs, and pre-review evidence. Grok review-1 targets that snapshot.
Its output is committed afterwards as a verdict-record commit without rebinding
the reviewed `base_sha`, `head_sha`, or `diff_fingerprint`; the runner must
verify that the verdict itself cites the stable snapshot fingerprint.

### 2. The automation authority is underspecified

The current contract assigns stage state, evidence commits, and handoffs to a
single bookkeeper, while all model dispatches are human executed. A phrase such
as “models + orchestrating script” does not identify who has authority to
invoke adapters, write artifacts, change status, or commit.

Required repair: introduce a deterministic, non-LLM local pipeline runner as
the only automated dispatcher and mechanical writer. Implementer and reviewer
sessions may not invoke peer models directly, choose adapters, write
`status.json`, or commit. The runner must use immutable dispatch templates,
registry allowlists, per-call receipts, sanitized command references, and
atomic output capture.

### 3. Grok verdict validity is not mechanically proved

The current Grok command is an optional plan-mode review command; unlike the
Codex adapter, it has no output-schema flag. The current validator checks
status fields but does not parse a raw review artifact as JSON Schema evidence.

Required repair: the runner must capture raw stdout, require one parseable JSON
object, validate it against `schemas/review-verdict.schema.json`, persist the
unaltered output, and reject the attempt before any status transition if that
check fails. A claimed `json_schema_valid: true` is insufficient.

### 4. The proposal conflicts with the current parallel-mode contract

Current `docs/parallel-development-mode.md` defines pre-review as a pre-commit
checkpoint with bounded local BLOCKER fixes. The proposed auto pipeline calls it
post-seal and advisory by default. These are incompatible semantics, not a
cross-link detail.

Required repair: either replace that contract in the new mode or define two
explicitly mutually exclusive stage modes. The revision must specify one
authoritative validator path and one owner for dispatch; no stage may inherit
both pre-review contracts.

### 5. Isolation and worktree ownership need real enforcement

An autonomous runner cannot safely share a dirty worktree with another active
stage. “Read-only” prompt language or adapter plan mode is not enough to prove
reviewer isolation.

Required repair: run each auto-pipeline stage in an exclusive stage worktree;
review sessions use a fresh, runner-controlled read-only environment. The
runner must fail closed if exclusive worktree, receipt capture, secret-safe
logging, or read-only confinement is unavailable.

## Replacement Pipeline

1. The human freezes scope and explicitly authorizes an auto-run window,
   selected adapters, time/token budget, and rework cap. The runner owns an
   exclusive stage worktree.
2. GLM/Kimi implement inside their frozen file boundaries and run blocking
   checks.
3. For a two-owner/parallel stage, the runner performs the configured embedded
   cross-check before sealing. It records the immutable prompt, seen diff, and
   raw output. Its findings are advisory unless the replacement parallel-mode
   contract expressly says otherwise.
4. The runner reruns blocking checks, creates a clean review snapshot commit,
   writes the existing single fingerprint formula, and runs the existing
   validation gate.
5. In a fresh read-only session, Grok performs review-1 against the committed
   stage-tip snapshot. The runner schema-validates and records the verdict.
6. On `REWORK`, the runner dispatches only the verdict-provided fix prompt to
   the eligible implementer, then repeats from step 2. On `ACCEPT`, it records
   review-1 and stops for human-started review-2.
7. Review-2 and the explicit merge acceptance remain human gates.

No new status names are required: retain `implementing`, `testing`,
`review_1`, `fixing`, `review_2`, and `stage_accepted_waiting_user`. Add
versioned opt-in metadata rather than inventing a second state machine.

## Answers To §9

1. **Grok default review-1:** do not promote it to the global default now.
   Permit it only for opt-in canary stages after mechanical JSON validation and
   isolation exist; retain the current cross-pool default for manual stages.
2. **Mandatory embedded pre-review:** optional by default for single-task
   MEDIUM stages. Require a recorded attempt for parallel/two-owner or
   specifically high-contract-risk stages; its unavailability is recorded but
   does not replace or block formal review-1.
3. **Dual-implementer formal review:** review the combined stage tip once.
   Per-task reviews are embedded cross-checks only; formal review must inspect
   integration behavior and shared contracts.
4. **Human gates:** no manual acknowledgement of review-1 ACCEPT is needed,
   but there must be a prior auto-run authorization in addition to existing
   requirement/scope approvals, human escalation exits, review-2, and merge.
5. **Who invokes models:** only the deterministic local runner, never an
   implementer or reviewer session.
6. **Security/compliance:** automatic dispatch is not inherently prohibited by
   this repository, but it requires explicit operator opt-in. Retain human
   dispatch if the environment cannot provide isolated worktrees, allowlisted
   commands, receipt capture, secret-safe logging, and read-only review.
7. **Fingerprint:** retain the exact existing formula. Do not add a worktree
   fingerprint or any extension.
8. **Cap and escalation:** allow three fix cycles, hence one initial and at
   most three post-fix review-1 attempts. Retry invalid JSON at most twice per
   review attempt without charging rework. On cap, timeout, or repeated invalid
   JSON, write `80-auto-review-escalation.md` with fingerprint, round count,
   raw-output paths and hashes, sanitized adapter result, tests, and permitted
   next actions, then enter `human_escalation_required`.
9. **Vocabulary:** use `embedded cross-check` for advisory evidence, avoiding
   collision with the validator’s `pre-review` phase. Retain `review-1` for the
   formal gate and `review-2` for final review.
10. **Migration:** use a stage opt-in feature flag such as
    `auto_review_pipeline.enabled: true`, defaulting to false. Pilot it before
    changing any global default and never apply it implicitly to existing
    stages.

## Revision-Stage Boundary

Recommended complexity: **HIGH**. The future stage may change only Harness
contracts and their tests/documentation: `AGENTS.md`, workflow template,
registry, model-adapter documentation, parallel-mode contract, validator,
stage template, and deterministic runner/seal scripts. It must not modify
business code, public API contracts, or any active product-stage evidence.

本地北京时间: 2026-07-10 19:30:53 CST
下一步模型: Grok 4.5
下一步任务: 独立核对本审阅、设计说明与 Claude Fable 5 审阅，明确双任务 review-1 粒度和 seal/证据提交顺序。
