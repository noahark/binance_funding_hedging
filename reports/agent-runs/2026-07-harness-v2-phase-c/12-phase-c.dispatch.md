# Phase C Dispatch

## Identity

- task_id: `harness-v2-phase-c`
- target_role: `Planner` with disclosed Stage Recorder duty
- target_model: `codex`
- provider: `openai`
- status_revision: `1`
- required_skill: none

The user explicitly started Phase C. Codex authored the Harness documents and
may maintain this low-risk meta-stage state, but cannot review its own delivery.
An independent provider must perform the Phase C review.

## Goal

Make the Harness v2 runtime path internally coherent before rehearsal:

1. fix the two non-blocking Phase B review suggestions;
2. dogfood the minimal v2 `ACTIVE.json`, `status.json`, and dispatch structure;
3. remove legacy workflow/schema authority from files that the new startup path
   can still read;
4. leave the unreachable v1 workflow engine frozen until Phase D proves it can
   be deleted as one unit.

## Allowed Files

```text
AGENTS.md
PROJECT_STATE.md
agents/roles.md
agents/developer-discipline.md
agents/skills/code-reviewer.md
agents/skills/complexity-evaluator.md
agents/skills/minimal-change-engineer.md
agents/skills/product-strategist.md
agents/skills/reality-checker.md
agents/skills/security-reviewer.md
agents/skills/senior-developer.md
agents/skills/software-architect.md
agents/skills/task-planner.md
agents/skills/test-strategist.md
reports/agent-runs/ACTIVE.json
reports/agent-runs/2026-07-harness-v2-phase-c/**
```

Do not modify business source, tests, live data, credentials, the main worktree,
or the active v1 `2026-07-hedge-order-truth-v1` stage.

## Required Changes

- In `PROJECT_STATE.md`, replace the now-empty `ACTIVE.json` evidence pointer
  with a reference pinned to the historical design baseline or remove it when
  the surviving evidence is sufficient.
- In `AGENTS.md`, replace startup wording `disclose` with `read` or `load`.
- Remove `docs/model-adapters.md` from the v2 startup file table; model launch
  instructions belong in the human-delivered packet, not Human's default read.
- Make reachable discipline/skill override headers subordinate to
  `AGENTS.md`, the valid dispatch, and current `status.json`, not legacy
  workflow YAML, registry, or schemas.
- Make review skill output instructions use `[TASK_RESULT v2]`,
  `ACCEPT | REWORK`, `findings_path`, and `fix_requirements_path` instead of the
  v1 verdict schema and `fix_start_prompt`.
- Add the copyable minimal status and dispatch field structure to the Stage
  Recorder section of `agents/roles.md`; do not create another template file.

## Deferred Legacy Cluster

Do not delete these in Phase C:

```text
workflows/templates/stage-delivery.yaml
agents/registry.yaml
schemas/review-verdict.schema.json
scripts/validate-stage.py
scripts/tests/test_validate_stage_dispatch_protocol.py
docs/parallel-development-mode.md
docs/harness-design.md
docs/model-adapters.md
harness-manifest.yaml
```

They remain available to the active v1 stage on main and are not referenced by
the v2 startup path. Delete them only after Phase D rehearsal and final
dependency verification.

## Acceptance Checks

- `ACTIVE.json` is a one-field pointer to this stage.
- `status.json` has exactly the twelve DRAFT-3.2 top-level fields.
- `AGENTS.md` remains within 120–180 lines and has ten chapters.
- `PROJECT_STATE.md` remains at or below roughly 2 KB.
- New startup and named role/skill paths contain no operative dependency on
  workflow YAML, registry routing, the v1 verdict schema, `70-handoff.md`, or
  Session ID footer rules.
- Review skills remain read-only and return the v2 verdict fields.
- No business source or main-worktree file changes.
- `git diff --check` passes.

## Stop

After deterministic checks, commit a fixed Phase C delivery on
`codex/harness-v2-rebuild`, prepare an independent review request, and stop for
the human operator. Do not push, merge main, enter Phase D, or delete the legacy
cluster.
