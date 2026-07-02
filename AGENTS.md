# AGENTS.md - AI Project Harness Rules

This file is the single startup document for agents working in this repository.
Read it before making changes, then read the active workflow and stage files.

## Project State

This is a new project. The current priority is to build a lightweight Harness for
requirements, design, implementation, review, fix, and evidence tracking before
the target product is implemented.

The first manual loop is not started yet.

## Authority Order

When documents conflict, use this order:

1. `AGENTS.md` - repository-level agent rules and safety gates.
2. `workflows/templates/*.yaml` - executable workflow contracts.
3. `schemas/*.schema.json` - machine-readable output contracts.
4. `agents/registry.yaml` - model, adapter, and skill routing.
5. `agents/skills/*.md` - role skill prompts and local overrides.
6. `agents/developer-discipline.md` - developer execution discipline for
   implementation and fix work.
7. `reports/agent-runs/<stage>/` - current stage facts and evidence.
8. `docs/*.md` - product, architecture, and design notes.

`agents/developer-discipline.md` is subordinate to the hard gates above. It
should guide developer behavior only when it does not conflict with this file,
workflow YAML, schemas, registry routing, or stage facts. Root `CLAUDE.md` is
kept only as a compatibility pointer for Claude Code.

## Canonical Paths

Drafts, model outputs, intermediate plans, reviews, and test logs must stay in:

```text
reports/agent-runs/<stage-id>/
```

Approved project documents must use these paths:

```text
docs/product/PRD.md
docs/architecture/ARCHITECTURE.md
docs/architecture/ADR/
docs/development/DEVELOPMENT_GUIDE.md
docs/planning/ROADMAP.md
docs/planning/DECISIONS.md
```

Do not write model drafts directly into canonical docs. Promote synthesized
content into `docs/` only after user approval.

## Roles

### Controller

Default controller: GLM5.2 through Claude Code, invoked through the local
`claude-glm` adapter.

The controller may:

- Read workflow YAML and stage files.
- Create and update `reports/agent-runs/<stage>/`.
- Dispatch work to implementation and review models.
- Collect raw artifacts and verify that required evidence exists.
- Update `status.json` and `70-handoff.md`.

The controller must not:

- Declare final acceptance.
- Hide, summarize, or rewrite implementation evidence before review.
- Feed reviewers only its own narrative summary.
- Record credentials, tokens, cookies, private keys, or full environment dumps.

### Designers

Before a milestone direction or requirement set is frozen, the controller must
run the registered direction panel for that round. The panel is declared in the
workflow/registry or in the approved stage intake before drafting starts.
When a registry panel key is derived from a stage id, replace hyphens with
underscores; for example, `2026-07-initial-direction` maps to
`2026_07_initial_direction`. The active panel key must be recorded in
`00-intake.md` or `status.json` before synthesis.

Each registered direction model writes one independent draft to:

```text
reports/agent-runs/<stage-id>/direction-drafts/<model-id>.md
```

If a registered model is unavailable or quota-exhausted, the stage must record
`direction-drafts/<model-id>.unavailable.md` with the reason. Drafts preserve
source model identity and must not be replaced by controller summaries.

The configured direction synthesizer, normally GPT/Codex, reads the raw draft
files and produces `06-direction-synthesis.md` for user review. The synthesizer
may be one of the panel models, but its synthesis is not a substitute for a
missing independent draft unless the user explicitly approves that shortcut.
Development does not begin until the user approves or edits the synthesis.

After user approval, the stage designer creates the next stage scope, file
boundaries, non-goals, acceptance criteria, and test strategy.

### Implementers

Implementers can be Kimi subagents, Claude-GLM, Grok, or another explicitly
registered model. Implementers may write code only within the active task scope
and file boundary.

### Reviewers

Review-1 is assigned to Grok Build with the `code_reviewer` skill. Review-2 is
the final gate and uses GPT/Codex first, then Claude only if GPT/Codex is
unavailable, quota-exhausted, or ineligible under the anti-self-review gate. If
Claude is also unavailable or quota-exhausted, the workflow stops with
`decision_models_exhausted`.

A stage's final reviewer must not be its designer or implementer. Reviewers are
read-only. They must inspect raw artifacts:

- Workflow YAML and `00-task.md`.
- `10-design.md`, `11-adr.md`, and `06-direction-synthesis.md` when present.
- The actual git diff or patch.
- Test output in `60-test-output.txt`.
- Implementation and fix reports.
- Relevant source files.

Self-review identity is checked at two granularities:

- `review-1` uses model-level isolation. Same provider with a different model is
  allowed when there is no shared session, prompt transcript, or tool state. This
  permits Grok Composer 2.5 implementation to be reviewed by Grok Build.
- `review-2` uses provider-level isolation for final decisioning. The final
  reviewer must not share the designer or implementer provider.

Provider identity means model vendor, not CLI wrapper. `claude_glm` is
`zhipu_glm`, not Anthropic, even though it is accessed through Claude Code.

Reviewer output must end with a strict JSON verdict matching
`schemas/review-verdict.schema.json`. If the JSON is missing or invalid, the
review attempt is non-accepting and must route to retry, fallback, fix, or one
of the allowed terminal stop reasons.

## Hard Gates

- Git is required. No git repository means no diff fingerprint and no review.
- Diff fingerprint is defined as
  `head_sha + ":" + sha256(git diff --binary <base_sha>..HEAD)`.
- Model claims are not evidence. Evidence is raw diff, test output, artifacts,
  schema-valid verdicts, and committed or uncommitted repository state.
- Final reviewer must not be the stage designer.
- Reviewer must not be the implementer of the reviewed task.
- Reviewer input must be raw artifacts and file paths, not only controller
  summaries.
- Invalid verdict JSON fails closed as non-accepting evidence. It cannot pass a
  gate and must route to retry, fallback, fix, or an allowed terminal stop
  reason.
- Failing tests do not enter final review unless the task is explicitly to
  document or triage the failure.
- Each stage has a finite rework limit. Default: 3.
- Product meaning, domain assumptions, external side effects, destructive data
  actions, credentials, public deployment, and risk limit changes require human
  approval.
- Codex review nodes use `codex exec` in read-only mode with a custom prompt
  when strict JSON verdict output is required. Do not rely on `codex review`
  for schema-constrained verdicts.
- Review-2 fallback from GPT/Codex to Claude is allowed only for quota,
  authentication, service availability, or anti-self-review ineligibility. Do
  not ask Claude for a second opinion after a valid GPT/Codex verdict.
- Review-1 uses the configured Grok Build model. If the adapter cannot access that
  model, fail closed instead of silently using another Grok model.

## Standard Loop

The intended loop is:

1. After user requirement discussion, classify the work as `LOW`, `MEDIUM`,
   `HIGH`, or `MILESTONE`.
2. Collect independent direction drafts from the registered direction panel for
   the current round when a milestone direction or requirement set is being
   frozen. Each available panel member must produce a raw draft, or the run must
   record an explicit unavailable/quota note for that model.
3. Have the configured direction synthesizer, normally GPT/Codex, synthesize the
   raw drafts into a final direction and requirements document for user review.
4. Wait for user approval before development starts.
5. Design stage scope and acceptance criteria.
6. Split implementation tasks.
7. Implement the bounded task.
8. Run deterministic tests, lint, type checks, or replay checks.
9. Review raw artifacts.
10. Fix if review returns `REWORK`.
11. Repeat until accepted, then stop and wait for the user to start the next
   multi-model direction round.

Lightweight bugfixes or mechanical follow-up tasks may skip the direction panel
when the user explicitly approves that shortcut or an existing synthesis already
covers the task.

Complexity routing:

- `LOW`: skip direction panel only when covered by an existing synthesis or user
  approval; otherwise ask the user to confirm the lightweight route.
- `MEDIUM`: skip direction panel when covered by an existing synthesis or user
  approval; proceed to stage design.
- `HIGH`: run direction panel by default, unless the user explicitly narrows the
  task and accepts a lightweight route.
- `MILESTONE`: always run the registered direction panel and configured
  synthesis.

## Terminal Stop Reasons

The workflow may stop only for these terminal reasons:

1. Both decision models, GPT/Codex and Claude, are quota-exhausted or otherwise
   unavailable, so no decision or final review can continue.
2. All development models are quota-exhausted or otherwise unavailable, so no
   implementation or fix task can continue.
3. The stage task passes review, then the workflow stops and waits for the user
   to start the next multi-model direction round.
4. Human escalation is required because the workflow hit a non-automatable
   product decision, missing evidence that models cannot collect, repeated
   invalid verdict output, or the rework limit.

Other failures, including invalid JSON, failed tests, missing artifacts, or a
single model failure, are routed to retry, fix, fallback, or evidence collection
inside the active workflow before escalating to one of these terminal reasons.

The first manual loop is intentionally deferred.

## Checkpoint Requirements

Before reporting completion, switching stage, compacting context, or asking
another model to continue, update:

- `status.json`
- `70-handoff.md`
- The active role report, such as `20-implementation.md`, `30-review-1.md`, or
  `50-review-2.md`
- `60-test-output.txt` when tests or command checks were run

The checkpoint must include current branch, HEAD if available, git status,
changed files, test status, open findings, blockers, and next action.

## Local Command Notes

- Codex prompt execution uses `codex exec`.
- Codex free-form review may use `codex review`, but schema-bound Harness
  review nodes use read-only `codex exec` with the review prompt.
- `codex -p` is a profile flag, not a prompt flag.
- `claude-glm` is a local shell alias/function. Invoke through an adapter and do
  not record its expanded environment.
- YAML files describe intent and routing. Command details belong in adapters or
  runner code, not arbitrary shell snippets embedded in tasks.
