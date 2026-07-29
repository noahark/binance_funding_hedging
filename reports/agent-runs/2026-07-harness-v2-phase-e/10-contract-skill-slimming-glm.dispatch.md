# Phase E Task 1 — Contract And Reality-Checker Slimming

## Identity

- task_id: `phase-e-contract-skill-slimming`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `1`
- required_skill: `agents/skills/minimal-change-engineer.md`

## Goal

Apply the smallest evidence-based Harness v2 corrections found in the accepted
Phase D rehearsal. Preserve the `msitarzewski/agency-agents` skill mechanism and
provenance while making default final review concise and project-neutral.

Make these bounded changes:

1. In `AGENTS.md`, keep `TASK_RESULT v2` as the single closing block and require
   these human-readable handoff fields inside it:
   - `completed_at_cst`, obtained from a local `date` command;
   - `suggested_next_actor`;
   - `suggested_next_action`.
   They are informational only and never authorize dispatch. `[/TASK_RESULT]`
   is the final non-whitespace output.
2. Add compact-output rules: a low-risk `ACCEPT` summary targets at most 300
   Chinese characters, checks are short non-duplicative PASS/FAIL items
   (normally at most eight), and findings contain only actual issues.
   `REWORK` and high-risk evidence may exceed the target when required.
3. In `agents/roles.md`, record:
   - Kimi remains the preferred cross-provider review-1 for GLM when available;
   - Grok 4.5 is a Human-approved fallback when Kimi quota or service is
     unavailable, with the reason recorded;
   - Opus 5 is the default review-2 model;
   - Fable5 is used only when Human explicitly selects its separate paid quota;
   - routing hints in model output never replace Stage Recorder verification
     and Human terminal launch.
4. In the Stage Recorder section, require every SHA to come directly from
   `git rev-parse`; validate the written value against Git before commit. Define
   `base_sha` as the committed HEAD immediately before preparing the task
   packet, so it is direct and non-self-referential.
5. When a dispatch requests context size, require actual byte-count command
   output rather than model estimation.
6. Rewrite `agents/skills/reality-checker.md` in place as a concise,
   project-neutral review-2 skill. Preserve its metadata, `agency_ref`,
   `pinned_commit`, license reference, evidence-first purpose, read-only rule,
   and `ACCEPT | REWORK` closure. Remove unrelated Laravel, Playwright,
   screenshot, visual-design, generic website production template,
   personality, and simulated learning/memory content.

This task does not delete any skill file or any frozen v1 workflow component.

## Allowed Files

- `AGENTS.md`
- `agents/roles.md`
- `agents/skills/reality-checker.md`
- `reports/agent-runs/2026-07-harness-v2-phase-e/status.json`, but only
  `current_task.state: dispatched -> reported` after all checks pass

Do not modify any other file.

## Inputs

Read only:

1. `AGENTS.md`;
2. this dispatch;
3. `reports/agent-runs/ACTIVE.json`;
4. `PROJECT_STATE.md`;
5. `reports/agent-runs/2026-07-harness-v2-phase-e/status.json`;
6. the `Implementer` and `Stage Recorder` sections of `agents/roles.md`;
7. `agents/developer-discipline.md`;
8. `agents/skills/minimal-change-engineer.md`;
9. `agents/skills/reality-checker.md`;
10. exact Phase D findings from
    `git show archive/2026-07-harness-v2-phase-d:reports/agent-runs/2026-07-harness-v2-phase-d/41-phase-d-opus5-review-result.md`.

Do not scan unrelated stages, business source, runtime data, credentials, or
moving history.

## Acceptance Checks

- `AGENTS.md` contains the three in-block handoff fields, their
  non-authoritative meaning, compact ACCEPT rules, and final closing-marker
  rule.
- `agents/roles.md` contains the approved Kimi/Grok/Opus/Fable routing,
  command-derived SHA discipline, and command-derived context measurement.
- `reality-checker.md` retains agency provenance and license metadata.
- `reality-checker.md` is at most 80 lines and 4KB.
- `reality-checker.md` contains no Laravel, Playwright, screenshot, visual
  design, generic website template, or learning/memory instructions.
- The final-review skill remains evidence-first, read-only, fixed-diff based,
  risk aware, and fail-closed on missing required evidence.
- The substantive diff changes only the three Harness files above.
- Run and return the actual output of:
  - `git diff --check`
  - `wc -l -c AGENTS.md agents/roles.md agents/skills/reality-checker.md`
  - `rg -n "completed_at_cst|suggested_next_actor|suggested_next_action|git rev-parse|Grok 4\\.5|Opus 5|Fable5" AGENTS.md agents/roles.md`
  - `rg -ni "Laravel|Playwright|screenshot|visual design|learning|memory" agents/skills/reality-checker.md`
- No frozen v1 workflow, registry, schema, validator, business code, main, Git
  remote, service, credential, or live state is changed.

## Stop

After all checks pass, optionally change only this task's state from
`dispatched` to `reported`, return one concise `[TASK_RESULT v2]` block with the
three handoff fields inside it, and stop at `[/TASK_RESULT]`. Do not commit,
push, delete legacy files, or start another model. Stage Recorder will verify,
commit, and prepare independent review.
