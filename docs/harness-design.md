# Harness Design

## Purpose

The Harness coordinates long-running project development through
explicit workflow files, role skills, evidence capture, and review gates.

It is designed to prevent three failure modes:

1. A controller model claiming completion without raw evidence.
2. Reviewers judging a controller's summary instead of the real diff and tests.
3. A model reviewing its own design or implementation.

## Current Scope

This repository currently implements only the document-level Harness contract:

- `AGENTS.md`
- `agents/registry.yaml`
- `workflows/templates/feature-loop.yaml`
- `schemas/review-verdict.schema.json`
- `reports/agent-runs/README.md`
- `reports/agent-runs/_template/`

The first manual loop is intentionally not started.

## Architecture

```text
workflow YAML
  -> GLM5.2 controller through Claude Code
    -> evaluates complexity after user requirement discussion
    -> collects independent direction drafts
    -> asks GPT/Codex to synthesize the direction for user review
    -> waits for user approval before development
    -> creates stage blackboard
    -> dispatches designer / implementer / reviewer
    -> collects raw evidence
    -> validates strict JSON verdicts
    -> updates status and handoff
```

The controller is an orchestrator, not an acceptance authority.

## Documentation Paths

The Harness separates drafts from approved documents:

- Drafts, model outputs, reviews, and test logs: `reports/agent-runs/<stage-id>/`
- Approved PRD: `docs/product/PRD.md`
- Approved architecture: `docs/architecture/ARCHITECTURE.md`
- Approved ADRs: `docs/architecture/ADR/`
- Approved development guide: `docs/development/DEVELOPMENT_GUIDE.md`
- Approved roadmap: `docs/planning/ROADMAP.md`
- Approved decision log: `docs/planning/DECISIONS.md`

No model should write raw drafts directly into canonical docs. The workflow
promotes synthesized and user-approved decisions into `docs/`.

## Sync Ownership

`harness-manifest.yaml` is the source of truth for template synchronization:

- `harness_owned`: copied on first install and later updates.
- `install_only`: copied on first install only, then owned by the target project.
- `project_owned_after_install`: never overwritten by Harness updates.
- `generated_or_runtime`: created by scripts or workflow runs, not copied back
  into the template repository.

The update path is intentionally one-way:

```text
ai_project_harness -> target project
```

Project-specific PRDs, architecture decisions, roadmaps, and business documents
must not be synced back into this template repository.

## Skill Registry

`agents/registry.yaml` keeps stable local skill IDs. Each skill has one explicit
source:

- `agency_agents` for vendored upstream role files in `agents/skills/`.
- `local` for project-owned roles with no clean upstream match.

Vendored agency skills are pinned to a specific upstream commit, keep the MIT
license notice, remove upstream Identity & Memory sections, and add project
Harness overrides. Skill prompts are lower authority than `AGENTS.md`, workflow
YAML, and schemas.

Current local skills:

- `product_strategist`
- `minimal_change_engineer`
- `test_strategist`

Developer implementation and fix work also reads
`agents/developer-discipline.md` as subordinate execution discipline: think
before coding, keep changes simple, edit surgically, and verify against explicit
success criteria. It does not override Harness hard gates or review contracts.
Root `CLAUDE.md` remains only as a compatibility pointer for Claude Code.

Current agency-backed skills:

- `software_architect`
- `task_planner`
- `senior_developer`
- `code_reviewer`
- `reality_checker`
- `security_reviewer`

## Model Routing

Direction and requirement freeze happens before milestone development. The
controller first classifies the requested work:

- `LOW`: mechanical changes such as logging fields, copy changes, or test-only
  edits.
- `MEDIUM`: bounded implementation inside an approved direction.
- `HIGH`: core logic, domain math, data model, external integration, or
  unclear oracle.
- `MILESTONE`: new phase or requirement/architecture freeze.

`LOW` and `MEDIUM` tasks can skip the five-model direction panel when the user
approves that route or an existing synthesis covers the task. `HIGH` runs the
panel by default unless the user explicitly narrows the scope. `MILESTONE`
always runs the panel.

For direction-panel tasks:

1. GPT/Codex writes its own direction draft.
2. Claude writes its own direction draft.
3. GLM5.2 writes its own direction draft.
4. Kimi 2.7 writes its own direction draft.
5. Grok Build writes its own direction draft.
6. GPT/Codex reads all five raw drafts, synthesizes the final direction, and
   formats it for user review.

The controller may index the files but must not replace the source drafts with
its own summary. Development starts only after user approval of the synthesis.
Lightweight bugfixes or mechanical follow-up tasks may skip this panel when the
user explicitly approves the shortcut or an existing synthesis covers the task.

Implementation can use multiple registered implementers, but Grok implementation
uses Composer 2.5:

```text
grok --model grok-composer-2.5-fast
```

Review routing is fixed:

1. `review-1`: Grok Build with `code_reviewer`.
2. `review-2`: GPT/Codex with `reality_checker`.
3. If GPT/Codex is quota-exhausted, unavailable, auth-failed, or ineligible
   under anti-self-review, use Claude.
4. If Claude is also unavailable or quota-exhausted, stop with
   `decision_models_exhausted`.

Do not ask Claude for a second opinion after a valid GPT/Codex review-2 verdict.
Fallback is only for availability, quota, auth, or anti-self-review eligibility.

Current local `grok models` output has been observed to expose both
`grok-build` and `grok-composer-2.5-fast`. The runner must check availability
before review-1 and fail closed if the configured model is unavailable.

## Controller

The default controller is GLM5.2 accessed through Claude Code using the local
`claude-glm` adapter. The reason for using it as controller is the large context
window, which is useful for reading workflow files, stage reports, and historical
handoffs.

Controller responsibilities:

- Select the next stage from workflow state.
- Coordinate direction draft collection and GPT/Codex synthesis.
- Build prompts from templates and raw artifact paths.
- Call eligible models through adapters.
- Validate output contracts.
- Update stage status.
- Stop on blockers or invalid machine-readable outputs.

Controller restrictions:

- No final acceptance.
- No reviewer prompt based only on controller summary.
- No credential or environment leakage into reports.
- No silent skip of tests, review, or schema validation.

## Terminal Stop Reasons

The workflow may stop only for these terminal reasons:

1. `decision_models_exhausted`: GPT/Codex and Claude are both unavailable or
   quota-exhausted for decision/final review.
2. `development_models_exhausted`: every development/fix model is unavailable
   or quota-exhausted.
3. `stage_accepted_waiting_user`: the current stage passes review and the
   workflow waits for the user to start the next multi-model direction round.
4. `human_escalation_required`: automation cannot proceed safely because of
   repeated review failure, max rework exhaustion, missing evidence, invalid
   verdict JSON after retry/fallback, or a product/domain human gate.

Other issues stay inside the active workflow as retry, fix, fallback, or evidence
collection work.

## Model Adapters

Workflow YAML must not directly interpolate shell commands for model execution.
Adapters own the command details.

Required adapter behaviors:

- Set working directory explicitly.
- Use read-only mode for reviewers.
- Capture stdout and stderr.
- Store raw transcripts outside committed reports unless summarized and
  scrubbed.
- Parse the required JSON verdict block.
- Treat command failure, timeout, missing JSON, or invalid schema as
  non-accepting evidence. Route to retry, fallback, fix, or one of the allowed
  terminal stop reasons.

Known command semantics:

- Codex non-interactive development: `codex -C <repo> exec "<prompt>"`
- Codex schema-bound review: `codex -C <repo> -s read-only exec "<prompt>"`
- Codex free-form review: `codex -C <repo> review --base <base> "<prompt>"`
- Codex `-p` means profile, not prompt.
- Claude Code print mode uses `claude -p "<prompt>"`.
- Local `claude-glm` must be invoked without recording its expanded auth
  environment.

## Evidence Model

Every review receives raw artifacts:

- `00-task.md`
- `10-design.md`
- `11-adr.md`
- `06-direction-synthesis.md` when present
- actual git diff or patch
- `20-implementation.md`
- `40-fix-report.md` when applicable
- `60-test-output.txt`
- relevant source files
- previous review files

The controller may provide an index of paths, but must not replace raw artifacts
with a narrative summary.

## Anti-Self-Review

For a given stage:

- `review_2` final reviewer must differ from `designer`.
- `review_1` uses model-level isolation: Grok Composer 2.5 implementation may be
  reviewed by Grok Build, provided there is no shared session or transcript.
- `review_2` uses provider-level isolation: the final reviewer must not share
  provider identity with the designer or implementer.
- Provider identity means model vendor, not CLI wrapper. `claude_glm` is
  `zhipu_glm`, not Anthropic, even though it is accessed through Claude Code.
- `review_1` may equal the designer; `review_2` is the actual final gate.
- If a rotation selects an ineligible final reviewer, the controller must choose
  the next eligible model. If both GPT/Codex and Claude are unavailable or
  ineligible, stop with `decision_models_exhausted`.

## Diff Fingerprint

The Harness fingerprint for a review candidate is:

```text
head_sha + ":" + sha256(git diff --binary <base_sha>..HEAD)
```

Reviewer verdict JSON must echo this value. If code changes after review, the
verdict is stale.

## Verdict Contract

Reviewer output must end with one JSON object matching
`schemas/review-verdict.schema.json`.

Allowed verdicts:

- `ACCEPT`
- `REWORK`
- `BLOCKED`

Invalid or missing JSON is treated as non-accepting evidence. It cannot pass a
gate and must route to retry, fallback, fix, or an allowed terminal stop reason.

## Testing Priority

Domain correctness must be anchored in deterministic tests, fixtures, and
replayable evidence. Review is a second layer, not the oracle.

The first real product stage should define the tests that prove the project's
critical behavior, such as:

- domain calculations and boundary cases
- parsing, normalization, and validation rules
- external service or API fixtures
- persistence and migration behavior
- permission, safety, and risk-limit constraints
- replay or regression baselines
- failure handling and recovery paths

Without these checks, the loop becomes model-reviewing-model and cannot prove
domain correctness.

## Deferred Work

Not implemented yet:

- A runner.
- Automatic model invocation.
- Manual first loop execution.
- Git commits for bootstrap.
- Product PRD and technical stack decisions.
