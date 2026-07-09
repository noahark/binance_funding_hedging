# Confirmation Review Prompt — DRAFT-2 rev c (GLM + GPT)

You already reviewed DRAFT-2 (`reviews/glm52-draft2.md` / `reviews/codex-gpt5-draft2.md`,
both REWORK). This is a **confirmation round** on **DRAFT-2 rev c**, which folds
your findings plus five locked decisions. Your job: verify the contract gaps are
actually closed, and flag any remaining fail-closed risk BEFORE scripts are
written. Do not re-raise findings that rev c already resolves; do not re-open the
settled direction or decisions.

## Output file

```text
reports/agent-runs/2026-07-harness-flow-optimization-v1/reviews/<model-id>-draft2c.md
```

`<model-id>` = `glm52` or `codex-gpt5`. Use the `-draft2c` suffix. Do not
overwrite existing files.

## Locked decisions (DEC-2026-07-08-003 — do NOT re-litigate)

- **A** `checkpoint.json` is a sidecar: never committed to a task branch; it stays
  uncommitted in the task worktree and is ingested + committed on the integration
  branch by `prepare-review-2`. (Resolves the self-reference; no change to the
  canonical fingerprint exclusion set.)
- **B** new independent flag `independent_task_branch_mode.enabled` (NOT
  `parallel_mode.enabled`); the `--phase dispatch-ready` gate is re-implemented
  under it.
- **C** canonical fingerprint stays unchanged (no `--no-renames`), but all
  recompute sites use the pinned `git -c diff.renames=true …` invocation; the
  non-binding product rebind hash uses `--no-renames`.
- **D** validator task mode reads task-local `evidence/<task>/30-review-1.md`;
  the top-level `30-review-1.md` requirement is dropped for this mode.
- **E** product task branches cannot set `allow_harness_change=true`; Harness
  changes go only through a serial enablement stage.

## Read

- `reports/agent-runs/2026-07-harness-flow-optimization-v1/10-independent-task-branch-mode-draft.md` (DRAFT-2 **rev c** — primary target)
- `reports/agent-runs/2026-07-harness-flow-optimization-v1/05-harness-environment-snapshot.md` (baseline)
- your own prior review (`reviews/glm52-draft2.md` or `reviews/codex-gpt5-draft2.md`)
- `AGENTS.md`, `workflows/templates/stage-delivery.yaml`, `agents/registry.yaml`,
  `docs/parallel-development-mode.md`, `docs/model-adapters.md`, `docs/harness-design.md`,
  `scripts/validate-stage.py`, `schemas/review-verdict.schema.json`

## Verify these are closed (map to your prior findings)

Common (both):
1. **checkpoint sidecar lifecycle** (§6, §9-6, §10-1/§10-7): is the sidecar read
   cross-worktree and committed on integration without any self-reference or lost
   evidence? (codex Critical#2 / gemini#1 / glm F1)
2. **scope split** (§3, §6, §9-3): `product_paths` for intersection/rebind vs the
   auto-owned `evidence/<task-id>/` for commit — is the boundary now unambiguous,
   with everything else BLOCKED? (codex Critical#1 / kimi P1 / glm F3)
3. **anti-stale-tip** (§10-2): `git rev-parse <task-branch> == checkpoint.head_sha
   == review_1.diff_fingerprint` — airtight against post-review-1 amend/append?
   (all four)
4. **worktree ↔ cwd** (§9, §10, §14): recorder runs from the trusted checkout;
   validator/scripts cwd pinned to the right worktree root. (codex / glm F9)
5. **§14 completeness**: `stage-delivery.yaml` mode, `_template/`, new-flag
   dispatch-ready rewrite, pinned canonical invocation, script fixtures — any
   fail-closed gap left? (gemini#3 / codex / glm F10)

GLM-specific (verify your P1/P2 are closed):
- **immutable-guard trust boundary** (§9 opening + §9-2): recorder runs from a
  trusted checkout and operates on the task branch via git refs; it does NOT run
  the task worktree's own `scripts/` copy. Is the guard now un-bypassable from the
  worktree side? (glm F2)
- **allowed_scope read via `git show <base_sha>:…`** (§9-3), not the working-tree
  `status.json`. (glm F3)
- **`parallel_mode.enabled` ownership** resolved by decision B + §14. (glm F4)
- **review-1 artifact ingest step** now present in §10-1/§10-7. (glm F8)
- **partial-merge atomicity** (§10-7): `git merge --no-commit --no-ff` → assert →
  commit, else `merge --abort`. (glm F11)

GPT-specific (verify your Criticals/High are closed):
- checkpoint self-reference resolved by the sidecar choice (your OQ1 recommendation). 
- review-1 artifact ingestion now specified with explicit `--*-worktree` paths and
  provenance hashing (§10-1). (codex High#3)
- `allow_harness_change=true` closed for double-owner product branches (decision E). (codex High#4)
- test command source + worktree cwd pinned (§9-4, §14). (codex Medium)

## Required review format

```markdown
# Review: <model-id> (DRAFT-2 rev c)

## Verdict

ACCEPT | REWORK | BLOCKED
(No CONDITIONAL ACCEPT. Use REWORK for "accept once required changes are made".)

## Summary

One short paragraph: are the contract gaps closed enough to write the two scripts?

## Findings

Only NEW or STILL-OPEN issues, by severity, with concrete refs (DRAFT-2 rev c §N,
validate-stage.py:NNN). Note explicitly which of your prior findings are now
resolved.

## Required Changes

Blocking items (if any) before landing §14 and writing the scripts.

## Open Questions

## Footer

本地北京时间: <timestamp from local `date`>
下一步模型: <model-or-human>
下一步任务: <specific next task>
```

## Constraints

Do not modify product code, canonical Harness files, or the spec. Do not re-open
the settled direction or decisions A–E. Write only `reviews/<model-id>-draft2c.md`.

本地北京时间: 2026-07-08 20:28:38 CST
下一步模型: glm52 / codex-gpt5
下一步任务: Confirm DRAFT-2 rev c closes the contract gaps; write reviews/<model-id>-draft2c.md.
