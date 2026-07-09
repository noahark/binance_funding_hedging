# 70-handoff

## Current State

External-review round in progress. First review received
(`reviews/claude-opus4.8.md`, verdict REWORK). Based on that review plus GPT
discussion, the direction converged and the user made a decision
(`status.json.decision_log` DEC-2026-07-08-001):

- The model `bookkeeper` is NOT restored, and NOT replaced by a model recorder
  (`codex_stage_recorder` rejected). Mechanical anchoring is a deterministic
  script, not a model.
- Adopt the **human-operated independent task-branch trial mode** directly with
  **git worktree branches** (no serial single-worktree warm-up), so double-owner
  (GLM backend + Kimi frontend) stages reach review-1 with zero extra human
  involvement.
- The single unavoidable integration/serialization point is folded into the
  human's existing review-2 preparation via `scripts/prepare-review-2`.

The spec draft to review now is
`10-independent-task-branch-mode-draft.md` (DRAFT-1). It only specifies the
mode; it does NOT modify `AGENTS.md`, `workflows/`, `scripts/validate-stage.py`,
or `schemas/`. Framework changes are listed in its §10 for later, gated behind
this review.

All four external reviews are in (`reviews/codex-gpt5.md`, `glm52.md`,
`kimi-for-coding.md`, `claude-opus4.8.md`); all REWORK, none BLOCKED. Only
`codex-gpt5.md` reviewed the new worktree draft; `glm52.md`/`kimi-for-coding.md`
reviewed the OLD `00-context-and-proposal.md`, and their big three (Option A,
single-writer vacuum, review-1=Codex) are already resolved by the DRAFT-1
design.

The environment + review round is snapshotted in
`05-harness-environment-snapshot.md`, which also locks four trial-mode HARD
requirements (DEC-2026-07-08-002): D1 task branch does not write top-level
status.json (task-local evidence snapshot only); D2 record-checkpoint commit
scope limited to source/test + task-local evidence; D3 backend/frontend pathspec
frozen pre-dispatch; D4 first trial forbids schema/API contract/shared fixture
changes.

The spec is now revised to **DRAFT-2** (`10-independent-task-branch-mode-draft.md`),
incorporating D1–D4 plus codex-gpt5 F1–F9 and the cross-cutting items (R9
dispatch discipline, invalid-JSON ownership, embedded R1–R10 verbatim, validator
gates in flow, provider-derived cross-review, no new status enum, rebind hash
separated from canonical fingerprint, immutable-script guard, branch ancestry,
single-owner section). It still modifies no canonical Harness files; framework
changes are listed in DRAFT-2 §14.

## Files

- `status.json`
- `00-context-and-proposal.md`
- `05-harness-environment-snapshot.md`  <- decision baseline (DEC-...-002)
- `10-independent-task-branch-mode-draft.md`  <- DRAFT-2, primary review target now
- `review-prompt.md`
- `reviews/README.md`
- `reviews/claude-opus4.8.md`
- `reviews/codex-gpt5.md`
- `reviews/glm52.md`
- `reviews/kimi-for-coding.md`
- `20-documentation.md`
- `60-test-output.txt`

## Human Request Captured

The user wants to reconsider the model `bookkeeper` role. The desired direction
is:

- Requirements and execution documents are finalized first.
- Human dispatches GLM backend and Kimi frontend terminals.
- Implementers run through Harness/YAML instructions toward review-1.
- Human uses review-1 result to choose fix direction or dispatch review-2 to
  Codex/Claude.
- External reviewers should write their reviews under their own model names.

## DRAFT-2 rev c (current)

Four DRAFT-2 reviews are in (`reviews/{gemini3.1pro,codex-gpt5,kimi-for-coding,glm52}-draft2.md`);
all REWORK, none BLOCKED, strongly converging — findings are now precise
script-contract gaps. The spec is revised to **DRAFT-2 rev c**, folding the 8
consensus blocking gaps plus recommended items, and locking five decisions
(DEC-2026-07-08-003):

- A=checkpoint.json is a sidecar (never committed to task branch; ingested +
  committed on the integration branch by prepare-review-2) → resolves the
  self-reference; no global fingerprint-exclusion change.
- B=new independent flag `independent_task_branch_mode` (dispatch-ready gate
  re-implemented under it).
- C=keep canonical fingerprint unchanged (no --no-renames) but pin the exact
  `git -c diff.renames=true …` recompute invocation across all sites.
- D=validator reads task-local `evidence/<task>/30-review-1.md`.
- E=product task branches cannot set `allow_harness_change=true`.

rev c also adds: scope split (product_paths vs evidence dir), immutable-guard
trust boundary (recorder runs from a trusted checkout via git refs),
`git show base:` scope reads, cross-worktree ingest via explicit `--*-worktree`
paths, anti-stale-tip assertion, atomic `--no-commit --no-ff` merge,
worktree/cwd pinning, and §17 negative fail-closed fixtures ⑥–⑬.

## draft2c confirmation → rev c2

Confirmation round on rev c is in: `reviews/glm52-draft2c.md` = **ACCEPT** (F1–F12
+ all common items closed, A–E correct); `reviews/codex-gpt5-draft2c.md` = REWORK
on two pre-script execution-timing pins that overlap glm's P3 (R1/R2). Both folded
into **DRAFT-2 rev c2** (DEC-2026-07-08-004), no conceptual disagreement, no
BLOCKED:

- §9 reordered: validate the task worktree's uncommitted candidate → commit C_e →
  run tests against C_e (fixes the pre-commit `base..branch`-is-empty timing bug).
- §10-7 pinned: sequential `--no-ff` merges M1→M2 → ingest commit M3 (=merge_head)
  → assert rebind + full tests only after merge_head exists → atomic rollback via
  `git reset --hard T0`.
- §17 adds fixtures ⑭ (worktree-candidate/clean + test-on-C_e), ⑮ (merge/rollback),
  ⑯ (single-owner smoke); R3 noted as an accepted human-trust assumption.

**Round CLOSED — 2×ACCEPT on DRAFT-2 rev c2**: glm52 ACCEPT + codex-gpt5
re-confirmed ACCEPT on rev c2 (§9/§10-7 pins closed; relayed verbally by user
2026-07-08 20:54, no raw artifact yet). Spec is review-complete.

## Next Steps

1. (Optional paper trail) have codex drop a one-line `reviews/codex-gpt5-draft2c2.md`
   ACCEPT so the 2×ACCEPT has a raw artifact, per the Harness "model claims are
   not evidence" discipline. Not blocking.
2. Land the §14 framework changes on a stage branch
   (`stage/2026-07-independent-task-branch-mode`): AGENTS.md pointer,
   `stage-delivery.yaml` mode, validator, schemas, `_template/`, and the two
   scripts + their fixtures.
3. First real run = Harness-only enablement stage (§17): scripts + validator +
   the synthetic dry-run fixture proving positive ①–⑤ and fail-closed ⑥–⑯,
   THEN a real GLM/Kimi double-owner stage.

Note: this stage folder is still git-untracked (uncommitted). Consider committing
it to durably fix the snapshot + review chain.

本地北京时间: 2026-07-08 20:28:38 CST
下一步模型: codex（可选一行复确认）/ 或直接进 §14 落地
下一步任务: 可选让 codex 确认 rev c2 §9/§10-7 两处时序已闭合；或径直在 stage 分支落
§14 + 两脚本 + §17 dry-run fixture。
