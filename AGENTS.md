# AGENTS.md - AI Project Harness Rules

This file is the single startup document for agents working in this repository.
Read it before making changes, then read the active workflow and stage files.

## Project State

This is a new project. The current priority is to build a lightweight Harness for
requirements, design, implementation, review, fix, and evidence tracking before
the target product is implemented.

The first manual stage delivery run is not started yet.

## Authority Order

When documents conflict, use this order:

1. `AGENTS.md` - repository-level agent rules and safety gates.
2. `workflows/templates/*.yaml` - executable workflow contracts.
3. `docs/parallel-development-mode.md` - optional parallel implementation and
   embedded cross-review mode contract.
4. `schemas/*.schema.json` - machine-readable output contracts.
5. `agents/registry.yaml` - model, adapter, and skill routing.
6. `docs/model-adapters.md` - local CLI adapter commands and availability
   checks.
7. `agents/skills/*.md` - role skill prompts and local overrides.
8. `agents/developer-discipline.md` - developer execution discipline for
   implementation and fix work.
9. `reports/agent-runs/<stage>/` - current stage facts and evidence.
10. `docs/*.md` - product, architecture, and design notes.

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

### Orchestrator And Bookkeeper

The orchestrator is an abstract workflow concept: `AGENTS.md`, workflow YAML,
schemas, and active stage files define the state machine. It is not a specific
model, terminal, or transcript.

The bookkeeper, also called the stage operator, is the single write authority
for stage state, evidence commits, review dispatch, and handoff files. The
default bookkeeper should be an independent local execution session rather than
one of the implementation terminals. GLM5.2 through Claude Code
(`claude-glm`) may be assigned as bookkeeper only when the stage explicitly
records that assignment. If the same session must act as both implementer and
bookkeeper, disclose it in `status.json` and `70-handoff.md`; review-2 must
evaluate that dual-hat risk.

The bookkeeper may:

- Read workflow YAML and stage files.
- Create and update `reports/agent-runs/<stage>/`.
- Dispatch work to implementation and review models.
- Collect raw artifacts and verify that required evidence exists.
- Update `status.json` and `70-handoff.md`.
- Create local evidence commits before formal review gates.

The bookkeeper must not:

- Declare final acceptance.
- Hide, summarize, or rewrite implementation evidence before review.
- Feed reviewers only its own narrative summary.
- Record credentials, tokens, cookies, private keys, or full environment dumps.

### Designers

Before a milestone direction or requirement set is frozen, the bookkeeper must
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
source model identity and must not be replaced by bookkeeper summaries.

The configured direction synthesizer, normally GPT/Codex, reads the raw draft
files and produces `06-direction-synthesis.md` for user review. The synthesizer
may be one of the panel models, but its synthesis is not a substitute for a
missing independent draft unless the user explicitly approves that shortcut.
Development does not begin until the user approves or edits the synthesis.

After user approval, the stage designer creates the next stage scope, file
boundaries, non-goals, acceptance criteria, and test strategy.

For `MEDIUM`, `HIGH`, and `MILESTONE` stages, a development breakdown author
then narrows implementation boundaries before coding starts. The default
breakdown author is Claude/Fable5 unless the registry or user selects another
model. The breakdown must record owner split, allowed files, forbidden files,
API/data contracts, test evidence, risk points, and review focus. This is design
involvement for review-2 disclosure purposes.

### Implementers

Implementers can be Kimi subagents, Claude-GLM, Grok, or another explicitly
registered model. Implementers may write code only within the active task scope
and file boundary.

The generic workflow actor pool is only an eligibility list. Stage-specific
owner and exclusion rules in `status.json.model_routing` must be applied before
dispatch. A model excluded from current-stage core work must not receive
implementation or fix tasks unless the user explicitly re-enables it.

### Reviewers

Review-1 uses a cross-review pool with the `code_reviewer` skill. If the
implementer is `claude_glm`, review-1 uses Kimi. If the implementer is Kimi,
review-1 uses Claude-GLM. For any other implementer, the bookkeeper chooses the
first available reviewer from the registered cross-review pool that does not
share provider identity with the implementer. Review-2 is the final gate and
uses GPT/Codex first, then Claude when GPT/Codex is unavailable,
quota-exhausted, or when the workflow's strong-reviewer override is required.
If both decision models are unavailable and no override path is valid, the
workflow stops with `decision_models_exhausted`.

A reviewer must not be the implementer or fix author of the reviewed code. This
is a hard ban with no disclosure override. A stage's final reviewer should
preferably differ from its designer, direction synthesizer, or development
breakdown author. Codex/GPT and Claude/Fable5 may perform final review despite
prior design involvement only through the strong-reviewer disclosure override
defined below. Reviewers are read-only. They must inspect raw artifacts:

- Workflow YAML and `00-task.md`.
- `10-design.md`, `11-adr.md`, and `06-direction-synthesis.md` when present.
- The actual git diff or patch.
- Test output in `60-test-output.txt`.
- Implementation and fix reports.
- Relevant source files.

Self-review identity is checked at two granularities:

- `review-1` uses provider-level cross-review isolation. It must not share
  provider identity, session state, prompt transcript, or tool state with the
  implementer of the reviewed task.
- `review-2` uses provider-level isolation from all implementation and fix
  authors. The final reviewer must not share the provider identity of any model
  that wrote delivery code in the reviewed stage.
- `review-2` prefers provider-level isolation from the designer, direction
  synthesizer, and development breakdown author. If no unrelated decision model
  is available after a runner-level check, Codex/GPT or Claude/Fable5 may review
  with a recorded design-involvement disclosure.

Provider identity means model vendor, not CLI wrapper. `claude_glm` is
`zhipu_glm`, not Anthropic, even though it is accessed through Claude Code.

Strong-reviewer disclosure override:

- It applies only to prior direction synthesis, development breakdown, or stage
  design involvement. It never applies to implementation or fix authorship.
- It is allowed only after the unrelated decision model fails a runner-level
  availability check for quota, authentication, service, timeout, or repeated
  invalid verdict output. The failure evidence path must be recorded.
- The review verdict must include `reviewer_prior_involvement` and the stage
  status must record the fallback reason and evidence file.
- The review-2 prompt must treat the user's approved direction synthesis, PRD,
  and product documents as the top-level requirements. The design and breakdown
  artifacts are reviewed evidence, not the highest authority.
- `scripts/validate-stage.py` must fail acceptance if these disclosure fields or
  evidence paths are missing.

Reviewer output must end with a strict JSON verdict matching
`schemas/review-verdict.schema.json`. If the JSON is missing or invalid, the
review attempt is non-accepting and must route to retry, fallback, fix, or one
of the allowed terminal stop reasons.

If a reviewer returns `REWORK`, the verdict JSON must include
`fix_start_prompt`: a ready-to-send repair prompt for the fix implementer. The
prompt must preserve raw artifact paths, findings, required fixes, file
boundaries, exact test commands, and acceptance criteria. The bookkeeper may add
mechanical routing metadata, but must not hide or rewrite reviewer evidence when
dispatching the fix.

## Hard Gates

- Git is required. No git repository means no diff fingerprint and no review.
- Review gates require a committed repository state. The bookkeeper is
  authorized to create local stage commits before review; this does not imply
  user approval to push, merge, deploy, or mark the stage accepted.
- Diff fingerprint is defined as a single committed-state scheme:
  `head_sha + ":" + sha256(git diff --binary <base_sha>..<head_sha> -- . ":(exclude)reports/agent-runs/<stage-id>/status.json")`.
  `status.json` is excluded because it records the fingerprint and would
  otherwise be self-referential. Do not invent alternate fingerprint fields or
  worktree fingerprint protocols.
- Model claims are not evidence. Evidence is raw diff, test output, artifacts,
  schema-valid verdicts, and committed repository state. Uncommitted state is
  allowed only for in-progress checkpoints before a review gate.
- A contract amendment that modifies a previously frozen contract must carry
  raw public samples that ground the change, landed under
  `reports/api-samples/<stage>/`. Synthetic fixtures may supplement coverage
  but never replace fact evidence. A stage that amends a contract from
  synthetic fixtures alone must record the missing live sample as a follow-up
  and re-enter review when the live sample is added.
- Before dispatching `review-1`, dispatching `review-2`, or writing an accepted
  terminal state, run `scripts/validate-stage.py <stage-id> --phase <phase>` and
  preserve the output in the stage evidence.
- Unknown status values, unknown fingerprint protocols, or bookkeeper/model-invented
  state machine transitions fail closed and route to `human_escalation_required`
  unless the Harness schema, docs, and validator are updated first.
- Final reviewer should differ from the stage designer, direction synthesizer,
  or breakdown author. Codex/GPT and Claude/Fable5 may use the documented
  strong-reviewer disclosure override when no unrelated decision model is
  available.
- Reviewer must not be the implementer or fix author of the reviewed task. This
  has no override.
- Reviewer input must be raw artifacts and file paths, not only bookkeeper
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
- Model dispatch must use `docs/model-adapters.md` and `agents/registry.yaml`.
  A bookkeeper or implementation session lacking a built-in tool for a model is not sufficient to
  mark that model unavailable; the runner-level adapter check must fail.
- Review-2 fallback or strong-reviewer override is allowed only for quota,
  authentication, service availability, timeout, repeated invalid verdict JSON,
  or design-conflict ineligibility of the preferred unrelated reviewer. Do not
  ask Claude for a second opinion after a valid GPT/Codex verdict.
- Review-1 uses the configured cross-review pool. Grok is not a default review
  gate and must not be substituted into review-1 unless the user explicitly
  enables it for the stage.
- Stages using `docs/parallel-development-mode.md` must follow that document's
  R1-R10 rules. In particular, implementation task prompts must include the R10
  dispatch tail, `next_dispatch` entries marked `executor: self` must be
  executed or escalated before the implementer reports completion, and the
  bookkeeper must perform R4 diff reconciliation before creating H_A/H_B
  evidence commits.

## Standard Stage Delivery

The intended stage delivery flow is:

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
6. Run development detail breakdown for `MEDIUM`, `HIGH`, or `MILESTONE`
   stages.
7. Split implementation tasks.
8. Implement the bounded task.
9. Run deterministic tests, lint, type checks, or replay checks.
10. For parallel development stages, run embedded cross-review checkpoints from
   `docs/parallel-development-mode.md` before the formal review gate; these
   checkpoints do not replace committed-state review-1.
11. Commit the bounded stage artifacts locally, compute the standard
   `diff_fingerprint`, run `scripts/validate-stage.py <stage-id> --phase
   pre-review`, then review raw artifacts.
12. If review returns `REWORK`, use the reviewer-provided `fix_start_prompt`
   to launch the fix task.
13. Repeat only within the bounded stage until accepted, then stop and wait for
   the user to start the next multi-model direction round.

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

The first manual stage delivery run is intentionally deferred.

## Output Footer

Every model-facing report, handoff, review narrative, and significant
bookkeeper response should end with:

```text
本地北京时间: YYYY-MM-DD HH:MM:SS CST
下一步模型: <model-or-human>
下一步任务: <specific next task>
```

The timestamp must come from a local `date` command, not from model memory.
This footer is a human navigation aid; `status.json` remains the authoritative
machine-readable state. For strict JSON verdicts, place the footer before the
final JSON block or inside schema-approved fields so the final JSON contract
remains parseable.

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

Checkpoints before review may be uncommitted. Review gates may not be
uncommitted.

## Local Command Notes

`docs/model-adapters.md` is the local command runbook. It records the currently
observed command forms for Codex, Claude, Claude-GLM, Grok, and Kimi, including
read-only review, write-capable development, and explicit yolo/bypass modes.

Key reminders:

- Codex prompt execution uses `codex exec`.
- Codex free-form review may use `codex review`, but schema-bound Harness
  review nodes use read-only `codex exec` with the review prompt.
- `codex -p` is a profile flag, not a prompt flag.
- Claude review uses the configured Claude adapter model, currently
  `claude-fable-5`, unless the registry or user changes it.
- Review-1 uses Kimi and Claude-GLM as a cross-review pool. Grok development,
  when explicitly enabled, uses `grok-composer-2.5-fast`; Grok is not a default
  review gate.
- Kimi one-shot execution uses the explicit latest coding alias:
  `kimi --model kimi-code/kimi-for-coding -p "$(cat <prompt-file>)"`.
- Current Kimi CLI behavior rejects combining `--plan` or `-y` with `-p`; do
  not document or dispatch those combinations as one-shot prompt commands.
- `claude-glm` is a local shell alias/function. Invoke through an adapter and do
  not record its expanded environment.
- YAML files describe intent and routing. Command details belong in adapters or
  runner code, not arbitrary shell snippets embedded in tasks.
