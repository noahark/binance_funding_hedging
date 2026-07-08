# External Review Prompt — DRAFT-2 round

You are reviewing **DRAFT-2 (rev b)** of a proposed Harness trial mode for this
repository: the human-operated **independent task-branch (worktree) delivery
mode**. This reviews the revised spec, not the original proposal.

## Output file naming (READ FIRST — avoids collisions)

Write exactly one file to:

```text
reports/agent-runs/2026-07-harness-flow-optimization-v1/reviews/<model-id>-draft2.md
```

Use the **`-draft2`** suffix, NOT `-round2`. The `-round2` suffix is already
taken and semantically mixed in this directory (`glm52-round2.md` reviewed
DRAFT-1; `kimi-for-coding-round2.md` reviewed DRAFT-2), so `-draft2` is the
unambiguous name for this round. Do not overwrite any existing file. Examples:

```text
claude-opus4.8-draft2.md
codex-gpt5-draft2.md
glm52-draft2.md
kimi-for-coding-draft2.md
grok-build-draft2.md
gemini3.1pro-draft2.md
deepseek-v4-draft2.md
```

## Decision baseline (settled — review implementation, not direction)

The following are user-decided trial-mode HARD requirements. Do **not** argue to
reverse them or re-open the direction. You **may and should** flag any place
where the spec's wording contradicts them, leaves a landing gap, or creates a
fail-closed risk.

- Direction adopted: worktree independent task branches; deterministic script
  recorder (not a model); review-1 stays cross-provider GLM↔Kimi; review-2 stays
  human-dispatched Codex→Claude.
- **D1** task branch does not write top-level `status.json` (task-local evidence
  snapshot only); integration `status.json` is written solely by
  `prepare-review-2`. *(Constrains double-owner task branches only; the
  single-owner exception is DRAFT-2 §7.)*
- **D2** `record-checkpoint` commit scope = source/test + task-local evidence dir
  only.
- **D3** backend/frontend pathspec is frozen **pre-dispatch** in the
  integration/base `status.json.tasks[].allowed_scope` (implementers and CLI
  cannot change it).
- **D4** the first trial forbids schema / API contract / shared fixture changes
  (forbidden shared paths are hard gates).

## Read

Primary:
- `reports/agent-runs/2026-07-harness-flow-optimization-v1/10-independent-task-branch-mode-draft.md` (DRAFT-2 rev b — primary target)
- `reports/agent-runs/2026-07-harness-flow-optimization-v1/05-harness-environment-snapshot.md` (locked decision baseline)

Canonical Harness (for precise findings):
- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `agents/registry.yaml`
- `docs/parallel-development-mode.md`
- `docs/model-adapters.md`
- `docs/harness-design.md`
- `scripts/validate-stage.py`
- `schemas/review-verdict.schema.json`

Prior reviews (context only — do not re-review these):
- `reviews/{claude-opus4.8,claude-opus4.6,codex-gpt5,glm52,kimi-for-coding}.md` — round 1 (old proposal / DRAFT-1).
- `reviews/glm52-round2.md` — targeted **DRAFT-1**; D1–D4 resolved several of its findings, some contract points may still apply.
- `reviews/kimi-for-coding-round2.md` — targeted **DRAFT-2**; its F1/F2/F3/F5 are folded into DRAFT-2 rev b — verify they are actually resolved, do not just re-raise them.

## Task

Review whether DRAFT-2 rev b is safe and complete enough to land its §14
framework changes and run the §17 Harness-only enablement stage. Focus on
implementation-contract correctness, not the settled direction.

## Review focus

- **§9 `record-checkpoint` contract**: immutable-script guard coverage (can an
  implementer still tamper with the recorder or its policy inputs?), commit-scope
  enforcement (D2), branch-ancestry / no-sibling-merge / no-stale-tip checks.
- **§10 `prepare-review-2` contract**: product-only changed-file intersection,
  merge determinism, the rebind assertion, single top-level `status.json`
  ownership, `human_decision` handling.
- **§6 fingerprint & rebind model**: the intentional divergence — canonical
  `task_diff_fingerprint`/`integration_diff_fingerprint` follow existing
  `compute_diff_fingerprint()` (**no** `--no-renames`, whole committed task diff
  incl. `evidence/`, excl. top status.json), while the non-binding
  `product_rebind_hash` uses `--no-renames` over `allowed_scope` product paths
  only. Is this divergence safe on product renames, or should canonical also add
  `--no-renames`? Does it cover rename/move/delete/generated/binary edges?
- **§13 review-1 commit semantics**: review-1 artifacts are produced after
  `task_head` is frozen and are committed by `prepare-review-2` on the
  integration branch, not the task branch. Is this airtight against fingerprint
  drift?
- **§11 human dispatch discipline**: R9 receipt + raw-output + the
  `invalid_json_attempts` accounting location (`evidence/<task-id>/review-1.attempts.json`).
- **§14 framework-change list**: completeness and fail-closed risk — unknown
  status values, validator required-file mapping, **git worktree ↔ cwd execution
  context** for the scripts and validator (does the validator resolve repo
  root / stage / evidence paths correctly inside a worktree?).
- **§17 trial plan**: are the positive assertions ①–⑤ plus the failure-mode
  fixtures ⑥–⑪ (intersection, rebind-mismatch, stale-tip, early-delete,
  shared-file, forbidden-path) a sufficient gate before a real double-owner
  stage?
- Any new mode-specific failure mode DRAFT-2 misses.

## Required review format

```markdown
# Review: <model-id> (DRAFT-2)

## Verdict

ACCEPT | REWORK | BLOCKED

(There is no CONDITIONAL ACCEPT. Use REWORK for "accept once required changes
are made" and list them under Required Changes. This matches
schemas/review-verdict.schema.json.)

## Summary

One short paragraph.

## Findings

By severity, with concrete refs (e.g. DRAFT-2 §9, validate-stage.py:NNN,
AGENTS.md Hard Gate).

## Required Changes

Changes required before landing §14 framework changes / running the §17
enablement stage.

## Open Questions

Decisions still needing human approval.

## Footer

本地北京时间: <timestamp from local `date`>
下一步模型: <model-or-human>
下一步任务: <specific next task>
```

## Constraints

Do not modify product code, canonical Harness files, or the spec in place. Do not
re-open the settled direction or the intent of D1–D4 (flagging wording
contradictions, landing gaps, or fail-closed risks around them is welcome). Write
only your review file under `reviews/<model-id>-draft2.md`.

本地北京时间: 2026-07-08 19:30:01 CST
下一步模型: external reviewer
下一步任务: Write DRAFT-2 review to `reviews/<model-id>-draft2.md`.
