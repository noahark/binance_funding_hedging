# Phase D Rehearsal — UPSTREAM Wording Cleanup

## Identity

- task_id: `phase-d-upstream-wording-cleanup`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `1`
- required_skill: `agents/skills/minimal-change-engineer.md`

## Goal

Perform the first low-risk, reversible Harness v2 rehearsal task. Remove the
two stale v1 operational statements from `agents/skills/UPSTREAM.md` without
changing its provenance purpose:

1. reviewer output must end with schema-valid JSON;
2. local skill ownership is defined by `agents/registry.yaml`.

Replace them with the minimum accurate v2 wording: this file records provenance
only, while runtime behavior and task output follow `AGENTS.md`, the valid
dispatch, current `status.json`, and `TASK_RESULT v2`.

## Allowed Files

- `agents/skills/UPSTREAM.md`
- `reports/agent-runs/2026-07-harness-v2-phase-d/status.json`, but only
  `current_task.state: dispatched -> reported` after all checks pass

Do not modify any other file. Do not delete the frozen v1 cluster in this task.

## Inputs

Read only:

1. `AGENTS.md`;
2. this dispatch;
3. `reports/agent-runs/ACTIVE.json`;
4. `PROJECT_STATE.md`;
5. `reports/agent-runs/2026-07-harness-v2-phase-d/status.json`;
6. the `Implementer` section of `agents/roles.md`;
7. `agents/developer-discipline.md`;
8. `agents/skills/minimal-change-engineer.md`;
9. `agents/skills/UPSTREAM.md`.

Do not scan completed stages, `history/`, workflow YAML, registry, schemas, or
business source files.

## Acceptance Checks

- `agents/skills/UPSTREAM.md` no longer names `agents/registry.yaml` or
  `schema-valid JSON`.
- Repository URL, pinned commit, MIT license, and vendored refresh warning
  remain intact.
- New wording points to the v2 authority chain and `TASK_RESULT v2`.
- The substantive diff changes only `agents/skills/UPSTREAM.md`.
- In the `TASK_RESULT` summary, report the files actually read, whether any
  context compaction occurred, and these two byte counts:
  - startup: `AGENTS.md + ACTIVE.json + PROJECT_STATE.md + status.json`;
  - loaded task: startup plus this dispatch, the required role/discipline/skill,
    and `agents/skills/UPSTREAM.md`.
- Run:
  - `git diff --check`
  - `rg -n "registry\\.yaml|schema-valid JSON|TASK_RESULT v2|provenance" agents/skills/UPSTREAM.md`
- No commit, push, main update, business-code change, service action, live
  action, credential access, or cross-model dispatch occurs.

## Stop

After the checks pass, optionally change only this task's state from
`dispatched` to `reported`, return the complete `[TASK_RESULT v2]` block to the
human operator, and stop. Do not commit and do not start a reviewer. The Stage
Recorder will verify the diff, preserve the raw result, and prepare review-1.
