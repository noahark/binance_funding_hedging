# Harness Design

## Purpose

The Harness coordinates long-running project development through explicit
stage-delivery files, role skills, evidence capture, and review gates.

It is designed to prevent three failure modes:

1. A stage operator claiming completion without raw evidence.
2. Reviewers judging a bookkeeper's summary instead of the real diff and tests.
3. A model reviewing its own design or implementation.

## Current Scope

This repository currently implements only the document-level Harness contract:

- `AGENTS.md`
- `agents/registry.yaml`
- `docs/model-adapters.md`
- `docs/parallel-development-mode.md`
- `workflows/templates/stage-delivery.yaml`
- `schemas/review-verdict.schema.json`
- `reports/agent-runs/README.md`
- `reports/agent-runs/_template/`

Multiple bounded delivery stages have completed in this repository. The
Harness contract is currently held at the DRAFT-2 decision baseline
(`reports/agent-runs/2026-07-harness-flow-optimization-v1/05-harness-environment-snapshot.md`).

## Architecture

```text
workflow YAML
  -> abstract orchestrator state machine
    -> single bookkeeper / stage operator execution session
    -> evaluates complexity after user requirement discussion
    -> collects independent direction drafts
    -> asks GPT/Codex to synthesize the direction for user review
    -> waits for user approval before development
    -> creates stage blackboard
    -> dispatches designer / breakdown author / implementer / reviewer
    -> collects raw evidence
    -> validates strict JSON verdicts
    -> updates status and handoff
```

The orchestrator is not a model. It is the workflow contract. The bookkeeper is
the only stage state writer and evidence committer, but it is not an acceptance
authority.

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
bookkeeper first classifies the requested work:

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

The bookkeeper may index the files but must not replace the source drafts with
its own summary. Development starts only after user approval of the synthesis.
Lightweight bugfixes or mechanical follow-up tasks may skip this panel when the
user explicitly approves the shortcut or an existing synthesis covers the task.

Implementation uses Claude-GLM and Kimi as the default delivery-code owners.
Codex is not an implementation or fix author. Claude-GLM owns backend,
API-contract, schema, normalization, external-sample, and data-semantics work.
Kimi owns frontend, UI, client integration, and frontend test work.

For mixed stages, route by dominant workload. If backend work is the large
majority and frontend work is light integration or display wiring, dispatch the
whole bounded task to Claude-GLM. If frontend work is the large majority and
backend work is light endpoint or schema glue, dispatch the whole bounded task
to Kimi. If both backend and frontend work are substantial and separable, split
implementation by domain owner.

Grok implementation is optional and only used when the user explicitly enables
it for a stage; when enabled it uses Composer 2.5:

```text
grok --model grok-composer-2.5-fast
```

The generic actor pool does not override a stage-specific routing decision. If
`status.json.model_routing.excluded_for_core_work` excludes a model for the
active stage, the bookkeeper must not dispatch implementation or fix work to
that model unless the user explicitly re-enables it.

Review routing is fixed:

1. `review-1`: cross-review with `code_reviewer`.
   - If implementer is `claude_glm`, review-1 uses Kimi.
   - If implementer is Kimi, review-1 uses Claude-GLM.
   - Otherwise choose the first available reviewer from the cross-review pool
     that does not share provider identity with the implementer.
2. `review-2`: GPT/Codex with `reality_checker`.
3. If GPT/Codex is quota-exhausted, unavailable, auth-failed, or the
   strong-reviewer disclosure override is required, use Claude.
4. If Claude is also unavailable or quota-exhausted, stop with
   `decision_models_exhausted`.

Do not ask Claude for a second opinion after a valid GPT/Codex review-2 verdict.
Fallback or strong-reviewer override is only for availability, quota, auth,
timeout, repeated invalid verdict JSON, or design-conflict eligibility.

Grok remains available for direction drafts or explicit experiments, but it is
not a required review gate.

## Orchestrator And Bookkeeper

The orchestrator is the contract made of `AGENTS.md`, workflow YAML, schemas,
and the active stage files. It has no session identity and cannot write code or
accept a stage.

The bookkeeper, also called the stage operator, is the single local execution
session that writes `status.json`, creates committed evidence, runs validators,
and prepares model-facing dispatch packets. The default should be independent
from the implementation terminals. GLM5.2 through Claude Code may still be
assigned as bookkeeper when the user chooses it, but that is an explicit stage
assignment, not the framework default.

Dispatch execution is human-operated. Codex/GPT and Claude provider sessions
may write implementation, review, and fix prompts, command templates, routing
metadata, and handoff text, but they must not invoke other model CLIs or model
terminals. The human operator copies the prepared dispatch into the selected
model terminal and records the resulting raw output or receipt under the stage
evidence path.

Bookkeeper responsibilities:

- Select the next stage from workflow state.
- Coordinate direction draft collection and GPT/Codex synthesis.
- Build prompts from templates and raw artifact paths.
- Prepare eligible-model dispatch packets from adapter rules.
- Validate output contracts.
- Update stage status.
- Stop on blockers or invalid machine-readable outputs.
- Commit bounded evidence locally before formal review gates.

Bookkeeper restrictions:

- No final acceptance.
- No reviewer prompt based only on bookkeeper summary.
- No credential or environment leakage into reports.
- No silent skip of tests, review, or schema validation.

If a bookkeeper must also implement part of a stage, the overlap must be
recorded in `status.json` and `70-handoff.md`, and review-2 must evaluate the
dual-hat risk. This should be exceptional; the preferred pattern is a neutral
bookkeeper plus separate implementation terminals.

## Parallel Development Mode

`docs/parallel-development-mode.md` defines the adopted trial mode for stages
with separable backend/frontend or similarly independent tasks. It is optional
and stage-scoped.

The intended pattern is:

1. The designer/breakdown author writes task prompts, file boundaries,
   prewritten cross-review prompts, and R10 dispatch tails before coding starts.
2. GLM/Claude-GLM and Kimi, or other assigned implementers, develop in separate
   terminals without touching git or `status.json`.
3. Each implementation terminal immediately executes its own `next_dispatch`
   when marked `executor: self`, launching a fresh read-only opposite-model
   embedded pre-review through the adapter command written in the prompt.
4. Local pre-review/fix loops are capped at two rounds. They are checkpoints,
   not formal review-1 verdicts, because they happen before committed evidence.
5. The bookkeeper re-generates each task diff, reconciles it with the
   implementer-produced diff, creates H_A/H_B evidence commits in order, then
   prepares the formal review-1 dispatch packet against committed fingerprints
   for human execution.

This mode improves wall-clock time without changing the evidence model:
committed-state fingerprints, validator checks, formal review-1, and review-2
remain mandatory.

## Stage Branch Mode

New delivery stages use a dedicated branch, normally `stage/<stage-id>`, created
by the bookkeeper at H_intake before stage-design or implementation evidence is
committed.

The branch keeps product work, review evidence, Harness sync commits, and
discarded stages from polluting the same moving `main` history. Stage
`base_sha`, `head_sha`, task fingerprints, and review prompts are anchored to
commits on the stage branch.

Default behavior:

1. Harness/template sync commits land on `main`.
2. Stage design, implementation, review evidence, fixes, and terminal
   bookkeeping commits land on the stage branch.
3. `review-2 ACCEPT` enters `stage_accepted_waiting_user` and stops. It does
   not merge to `main`.
4. Merge or fast-forward back to `main` happens only after explicit user
   acceptance.
5. The stage branch remains pure by default. Do not merge `main` into it unless
   the stage needs new Harness behavior from `main`.
6. If `main` is merged into a stage branch by exception, record the reason,
   rerun tests and validator, recompute fingerprints, and re-enter or
   mechanically rebind review gates as the changed diff requires.
7. Rebase is forbidden because it rewrites evidence commit identities.
8. Failed or abandoned stage branches are retained as evidence and are not
   merged to `main`.

The executable branch gate lives in `scripts/validate-stage.py`. It is enabled
only when `status.json.stage_branch.name` is non-empty, so historical stages and
legacy blackboards are not retroactively invalidated.

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
Adapters own the command details. `docs/model-adapters.md` is the local command
runbook and must be checked before marking a model unavailable.

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

- Codex default Harness model: `gpt-5.5` with high reasoning effort, as
  configured locally by the adapter/profile.
- Codex schema-bound review: `codex exec -C <repo> -m gpt-5.5 -s read-only --output-schema schemas/review-verdict.schema.json - < <prompt-file>`
- Codex free-form review: `codex exec review --base <base> - < <prompt-file>`
- Codex `-p` means profile, not prompt.
- Claude Code print mode uses `claude -p "<prompt>"`.
- Claude review uses `claude-fable-5` by default, then `opus4.8` if Fable5
  quota is exhausted.
- Review-1 uses the Kimi / Claude-GLM cross-review pool.
- Claude-GLM development owns backend/API/contract/schema/data-semantics work.
- Grok development uses `grok-composer-2.5-fast` only when explicitly
  workflow-enabled by the user.
- Kimi development owns frontend/UI/client-integration work and uses
  `kimi --model kimi-code/kimi-for-coding -p "<prompt>"` unless a stage
  explicitly pins another model.
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

The bookkeeper may provide an index of paths, but must not replace raw artifacts
with a narrative summary.

Contract amendments have an additional evidence rule: if a stage changes a
previously frozen API or data contract, it must attach raw public samples under
`reports/api-samples/<stage>/`. Synthetic fixtures may supplement coverage, but
they cannot be the only fact basis for the amendment.

## Anti-Self-Review

For a given stage:

- `review_1` uses provider-level cross-review isolation: it must not share
  provider identity, session state, prompt transcript, or tool state with the
  implementer.
- `review_2` uses provider-level isolation from every implementation and fix
  author. A model provider that wrote delivery code or fix code for the stage is
  unconditionally ineligible for final review.
- `review_2` should use a reviewer that differs from the designer, direction
  synthesizer, and development breakdown author. This is a preference, not a
  hard terminal blocker for Codex/GPT and Claude provider. Claude uses Fable5
  first and Opus4.8 after Fable5 quota exhaustion.
- Codex/GPT and Claude provider may use a strong-reviewer disclosure override
  after an unrelated decision model fails a runner-level check. The stage must
  record `reviewer_prior_involvement`, `fallback_reason`, and an existing
  evidence file for the unavailable unrelated model.
- In an override review, the prompt must use the user-approved synthesis, PRD,
  and product docs as the top-level requirements. Stage design and breakdown
  artifacts are evidence under review, not the highest authority.
- Provider identity means model vendor, not CLI wrapper. `claude_glm` is
  `zhipu_glm`, not Anthropic, even though it is accessed through Claude Code.
- `review_1` may equal the designer; `review_2` is the actual final gate.
- If a rotation selects an implementation/fix author as final reviewer, the
  bookkeeper must choose another reviewer. There is no override. If all
  decision models are unavailable and no valid design-conflict override applies,
  stop with `decision_models_exhausted`.

## Development Breakdown

For `MEDIUM`, `HIGH`, and `MILESTONE` stages, add a development detail
breakdown before implementation starts. The default breakdown author is
Claude provider, using Fable5 first and Opus4.8 after Fable5 quota exhaustion,
unless the registry or user selects another model. The breakdown author narrows
ambiguity and reduces implementation drift; it does not write delivery code in
that role.

The breakdown records file boundaries, API/data contracts, owner split,
required evidence, tests, risk points, and explicit non-goals. Because this is
design involvement, a breakdown author who later performs final review must use
the strong-reviewer disclosure override.

`LOW` tasks may skip this step when covered by an existing synthesis or
explicitly approved by the user.

## Diff Fingerprint

The Harness fingerprint for a review candidate is:

```text
head_sha + ":" + sha256(git diff --binary <base_sha>..<head_sha> -- . ":(exclude)reports/agent-runs/<stage-id>/status.json")
```

Reviewer verdict JSON must echo this value. If code changes after review, the
verdict is stale.

## Authorized Exceptions (RC4)

Pre-accept allows a review whose `diff_fingerprint` legitimately trails
`status.diff_fingerprint` to be downgraded to PASS-with-exception, but only
through a compliant `status.authorized_exceptions[]` record. This repairs the
RC4 false-red without weakening the content seal: the diff fingerprint formula
above is unchanged.

The admissible `assertion_id` whitelist is source-enumerated in
`scripts/validate-stage.py` (`AUTHORIZED_EXCEPTION_ASSERTION_IDS`); stage data
references an exception class but cannot define one. Adding a class requires a
template-repo code change plus strong review. v1 admits only class-1
`review_fingerprint_trails_status`; class-2 (waiving `verdict == ACCEPT`) is
not admitted because that is the heaviest weakening of the terminal gate.

Each record requires `authorizer == "user"` (literal), a non-empty `reason`, a
parseable ISO-8601 `at`, a repo-relative git-tracked `evidence_file` sealed by
`evidence_sha256` (the sha256 of the committed blob), and
`applies_to_fingerprint == status.diff_fingerprint`. The validator reads the
COMMITTED content via `git show <HEAD>:<path>` — not the worktree — so an
untracked file, an absolute path, a `../` escape, or a post-seal content swap
cannot pose as evidence; it recomputes the blob's sha256 and rejects any
mismatch with `evidence_sha256`. (Deliberately not bound to `status.head_sha`:
post-head evidence is legal once it is tracked and digest-matched, which avoids
the head/post-head ordering deadlock.) The fingerprint pin makes the waiver
one-shot: any later fix changes `status.diff_fingerprint`, so the record
auto-expires and the gate re-redds until the waiver is re-authorized. This
prevents trading RC4's permanent false-red for a permanent false-green.

Anti-self-grant is two layers, not an impossibility claim. The literal
`authorizer == "user"`, the fingerprint pin, and the committed+digest-sealed
evidence together make a self-granted waiver NON-SILENT: forging one requires
committing fabricated authorization text into reviewed git history and surfacing
it in the PASS-with-exception banner — a visible, traceable trail across reviews
and to the operator. But code cannot PROVE the evidence text originated from a
human (any bytes a model can write, a model can write). The final guarantee is
mandatory human verification of the evidence verbatim before pre-accept release
of any exception (the banner is the trigger); human verification is a workflow
obligation (checklist + handoff), not something the validator can mechanically
enforce — consistent with the RC methodology, not dressed up as a mechanical
gate.

Release is never silent. On PASS the validator prints
`PASS (N authorized exceptions applied: <id>@<scope>, …)` and the pre-accept
evidence must contain that line.

The exemption mechanism cannot exempt itself. Authorized exceptions can never
waive the negative list, even with a record present:

1. `status.diff_fingerprint` recomputes consistently (the content seal itself).
2. Clean worktree.
3. Reviewer identity separation (no override).
4. An exception record's own `evidence_file` being committed and digest-sealed.
5. An exception record's own structural integrity (fields, authorizer,
   `assertion_id`, fingerprint pin, `reason`, `at`).

Any malformed record fails closed and invalidates every exception, so the
downgrade path cannot fire on a bad record.

For multi-task stages, `validate_task_coverage` adds chain-plus-prefix
coverage: the task chain must tile `base..head`, each review's
`diff_fingerprint` must match the recomputed prefix up to its
`covers_through_task`, and every task beyond the covered prefix needs its own
review record or a class-1 exception. Degenerate cases (no `tasks[]`, or a
single task) preserve the current single-fingerprint behavior exactly.

## Verdict Contract

Reviewer output must end with one JSON object matching
`schemas/review-verdict.schema.json`.

Allowed verdicts:

- `ACCEPT`
- `REWORK`
- `BLOCKED`

When the verdict is `REWORK`, the JSON must include `fix_start_prompt`. This is
a ready-to-send prompt for the fix implementer. It should carry raw review and
artifact paths, ordered findings, required fixes, file boundaries, forbidden
paths, exact verification commands, and the expected `40-fix-report.md`
finding-to-fix mapping. The bookkeeper may add routing metadata, but it should
not rewrite the evidence into a looser summary before dispatching the fix.

Invalid or missing JSON is treated as non-accepting evidence. It cannot pass a
gate and must route to retry, fallback, fix, or an allowed terminal stop reason.
The same model may emit invalid verdict JSON at most twice for one gate; after
two invalid attempts, treat that model as unavailable for the gate.

All verdict JSON objects must include `reviewer_prior_involvement` with one of:

- `none`
- `direction_synthesis`
- `breakdown`
- `design`

## Report Footer

Model-facing reports, handoffs, reviews, and significant bookkeeper responses
should end with:

```text
本地北京时间: YYYY-MM-DD HH:MM:SS CST
下一步模型: <model-or-human>
下一步任务: <specific next task>
```

The timestamp must come from a local `date` command. The footer helps human
handoff, but `status.json` remains authoritative.

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

Without these checks, the workflow becomes model-reviewing-model and cannot
prove domain correctness.

## Deferred Work

Not implemented yet:

- A runner.
- Automatic model invocation.
- Manual first stage delivery execution.
- Git commits for bootstrap.
- Product PRD and technical stack decisions.
