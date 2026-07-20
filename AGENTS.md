# AGENTS.md - AI Project Harness Rules

This file is the single startup document for agents working in this repository.
Read it before making changes, then read the active workflow and stage files.

## Session Bootstrap

To resume an existing session, locate the active stage in one hop, then stop:

1. Read `reports/agent-runs/ACTIVE.json`. It names the active stage, or carries
   `active: null` when no stage is in flight.
2. If a stage is active, read that stage's `70-handoff.md` recovery header (the
   `## Recovery Header` block at the top) and `status.json`. That is enough to
   resume the common case.
3. Read the workflow YAML section only for the phase you are about to act on or
   gate; you need not read the whole workflow just to resume.

## Startup Read Budget

A new terminal session reads only, in this order:

1. `AGENTS.md`;
2. the active workflow section needed for the next action;
3. the active stage located through `reports/agent-runs/ACTIVE.json`: its
   `status.json`, the `70-handoff.md` recovery header, and named
   `status.current_inputs` needed for that action.

Do not recursively scan `reports/agent-runs/` or read any `history/` directory
at startup. Historical artifacts are cold audit evidence and are read only
when an exact review, audit, or finding reference names them.

## Project State

Product as built: the repository currently contains a read-only Binance funding
snapshot workstation. The backend serves a normalized public-market snapshot
with optional private signed GET enrichment for account balances, positions,
borrow validation, borrow cost, and sort basis. The frontend consumes that
backend contract and exposes the opportunity table and private read-only
account panels.

No order, borrow, repay, transfer, close, or other trading execution surface is
implemented. Manual execution, accounting, reconciliation, and live order flows
remain future product stages.

Harness as built: multiple manual delivery stages have run, with evidence under
`reports/agent-runs/`. The Harness contract is currently held at the DRAFT-2
decision baseline
(`reports/agent-runs/2026-07-harness-flow-optimization-v1/05-harness-environment-snapshot.md`,
see DEC-2026-07-10-002).

Known open gaps: API naming still uses the historical
`/api/public-market/snapshot` route and `public-market-snapshot/v1` wire version,
borrowability semantics still distinguish borrow evidence outside the generic
`verified` flag, and manual execution is not yet implemented.

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
- Prepare dispatch packets, prompts, routing metadata, and handoff text for
  implementation, review, and fix models.
- Collect raw artifacts and verify that required evidence exists.
- Update `status.json` and `70-handoff.md`.
- Create local evidence commits before formal review gates.

The bookkeeper must not:

- Execute model-dispatch commands or invoke implementation/review/fix model
  terminals.
- Declare final acceptance.
- Hide, summarize, or rewrite implementation evidence before review.
- Feed reviewers only its own narrative summary.
- Record credentials, tokens, cookies, private keys, or full environment dumps.

Dispatch authority is actor-neutral: no model session — bookkeeper,
implementer, reviewer, designer, or any other — may execute model-dispatch
commands or invoke another model terminal or adapter. Model sessions prepare
model-facing dispatch artifacts only; a session that reaches an external
dispatch stops and returns the prepared packet path. The human operator
executes dispatch by copying the prepared prompt or command into the selected
model terminal, captures the producer exit status, and records the resulting
raw output or receipt under the stage evidence path. Every external
implementation, optional embedded pre-review, review-1, review-2, and fix
dispatch records `executor: human_operator`. A model claim that it launched
another model is never dispatch evidence.

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
breakdown author is Claude provider, using Fable5 first and Opus4.8 after
Fable5 quota exhaustion, unless the registry or user selects another model. The
breakdown must record owner split, allowed files, forbidden files, API/data
contracts, test evidence, risk points, and review focus. This is design
involvement for review-2 disclosure purposes.

### Implementers

Implementers are domain-routed by default: Claude-GLM owns backend, API
contract, schema, normalization, external-sample, and data-semantics work; Kimi
owns frontend, UI, client integration, and frontend test work. Codex/GPT is not
an implementation or fix author in this Harness.

For mixed tasks, route by dominant workload. If backend work is the large
majority and frontend work is light integration or display wiring, the whole
bounded task may be dispatched to Claude-GLM. If frontend work is the large
majority and backend work is light endpoint or schema glue, the whole bounded
task may be dispatched to Kimi. If backend and frontend work are both
substantial and separable, split implementation by domain owner. Grok or another
explicitly registered model may write code only when the user or stage
explicitly enables it. Implementers may write code only within the active task
scope and file boundary.

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
breakdown author. Codex/GPT and Claude provider may perform final review despite
prior design involvement only through the strong-reviewer disclosure override
defined below; Claude uses Fable5 first and Opus4.8 after Fable5 quota
exhaustion under the same Anthropic provider identity. Reviewers are read-only.
They must inspect raw artifacts:

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
  is available after a runner-level check, Codex/GPT or Claude provider may
  review with a recorded design-involvement disclosure. Claude uses Fable5 first
  and Opus4.8 after Fable5 quota exhaustion under the same Anthropic provider
  identity.

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

Reviewer output is a strict JSON verdict matching
`schemas/review-verdict.schema.json`. Under
`review_artifact_protocol: raw-plus-strict-json/v1` (the default for new
stages) the review stdout is exactly one JSON object with no Markdown, fences,
narrative, or footer; the operator captures it to the stage
`*.raw-output.md` file and publishes the canonical `*.verdict.json` with the
capture-only helper `scripts/review_artifacts.py capture`. The verdict file is
the gate authority; matching status fields are derived cache. On legacy
(pre-protocol) stages the verdict JSON ends the review narrative instead. If
the JSON is missing or invalid, the review attempt is non-accepting and must
route to retry, fallback, fix, or one of the allowed terminal stop reasons;
retries use new `-retry-N` attempt paths.

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
- New delivery stages use a stage branch named `stage/<stage-id>` unless the
  stage intake records an explicit user-approved exception. The bookkeeper
  creates the branch at H_intake, and all stage commits before user acceptance
  stay on that branch.
- `review-2 ACCEPT` moves the stage only to `stage_accepted_waiting_user`; it
  does not authorize merging the stage branch to `main`. Merge or fast-forward
  back to `main` requires explicit user acceptance after review.
- `base_sha`, `head_sha`, and `diff_fingerprint` are anchored to commits on
  the active stage branch. Review prompts must use the status-recorded
  `<base_sha>..<head_sha>` range, never a moving `HEAD`.
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
- `review_artifact_protocol: raw-plus-strict-json/v1` is default-on in the
  stage template and mandatory for active/new stages at dispatch-ready,
  pre-review, and pre-accept; missing or unknown values fail closed. The
  active stage is identified by `reports/agent-runs/ACTIVE.json`, never by a
  date heuristic. Cold historical stages without the field keep legacy
  validation and are not rewritten. Under v1 each formal review gates on a
  stage-local raw/verdict pair (`30-review-1[-<task-id>][-retry-N].*` and
  `50-review-2[-retry-N].*`): the raw file decodes as exactly one JSON object,
  the verdict file is its deterministic canonical serialization with no
  surrounding bytes or trailing newline, both decode to the same object, and
  the verdict is cross-checked against stage/task status for `stage_id`, role,
  model, fingerprint, and normalized reviewer provider isolation. Phase
  timing: `pre-review` with status `review_1` does not require the Review-1
  result pair; `pre-review` with status `review_2` requires every task/serial
  Review-1 pair; `pre-accept` additionally requires the Review-2 pair.
- Before entering implementation for a parallel development stage, run
  `scripts/validate-stage.py <stage-id> --phase dispatch-ready` and preserve the
  output in the stage evidence. For every parallel stage this gate checks the
  R10 checklist, task prompt paths, cross-review routing, and the
  human-operator dispatch fields before any implementer starts coding. The
  embedded pre-review prompt, round-cap, and failure escalation branch checks
  apply only when `parallel_mode.embedded_review.enabled == true`.
- Unknown status values, unknown fingerprint protocols, or bookkeeper/model-invented
  state machine transitions fail closed and route to `human_escalation_required`
  unless the Harness schema, docs, and validator are updated first.
- Final reviewer should differ from the stage designer, direction synthesizer,
  or breakdown author. Codex/GPT and Claude provider may use the documented
  strong-reviewer disclosure override when no unrelated decision model is
  available; Claude uses Fable5 first and Opus4.8 after Fable5 quota exhaustion.
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
- Model dispatch preparation must use `docs/model-adapters.md` and
  `agents/registry.yaml`. No model session may execute model dispatch or invoke
  another model terminal/adapter; the human operator executes prepared dispatch
  packets in the target model terminal and every external dispatch records
  `executor: human_operator`. A bookkeeper or implementation session lacking a
  built-in tool for a model is not sufficient to mark that model unavailable;
  the runner-level adapter check must fail.
- Review-2 fallback or strong-reviewer override is allowed only for quota,
  authentication, service availability, timeout, repeated invalid verdict JSON,
  or design-conflict ineligibility of the preferred unrelated reviewer. Do not
  ask Claude for a second opinion after a valid GPT/Codex verdict.
- Review-1 uses the configured cross-review pool. Grok is not a default review
  gate and must not be substituted into review-1 unless the user explicitly
  enables it for the stage.
- Stages using `docs/parallel-development-mode.md` must follow that document's
  R1-R10 rules. The default parallel flow is: implementation reports and
  self-tests, bookkeeper R4 scope/diff reconciliation, committed task
  ranges/fingerprints, one fresh cross-provider formal Review-1 per committed
  task fingerprint, then Review-2. Embedded pre-review is an explicit opt-in
  (`parallel_mode.embedded_review.enabled: true` plus a non-empty reason); it
  never replaces formal Review-1, and its dispatches are executed by the human
  operator like every other external dispatch. R4 diff reconciliation before
  H_A/H_B evidence commits stays mandatory even when embedded review is off.
  R10 checklist data belongs in `status.json` task metadata or dispatch RECEIPT
  metadata, not inside immutable PROMPT BODY text.
- Harness/template sync lands on `main` only and must not be mixed into an
  active stage branch unless that stage needs the new Harness behavior. If
  `main` is merged into a stage branch by exception, record the reason, rerun
  tests and validator, recompute fingerprints, and re-enter or mechanically
  rebind review gates as the changed diff requires. Rebase is forbidden.
- Pre-accept authorized exceptions (RC4): a review whose `diff_fingerprint`
  legitimately trails `status.diff_fingerprint` may be downgraded to
  PASS-with-exception ONLY by a compliant `status.authorized_exceptions[]`
  record. The admissible `assertion_id` whitelist is source-enumerated in
  `scripts/validate-stage.py` (`AUTHORIZED_EXCEPTION_ASSERTION_IDS`); stage
  data may REFERENCE an exception class but cannot DEFINE one. Each record
  requires `authorizer == "user"` (literal), a non-empty `reason`, a parseable
  ISO-8601 `at`, `applies_to_fingerprint == status.diff_fingerprint` (the waiver
  is pinned to one diff and auto-expires the next time the fingerprint changes),
  and a repo-relative git-tracked `evidence_file` sealed by `evidence_sha256`
  (the sha256 of its committed blob): the validator reads the committed content,
  rejects absolute/outside/untracked paths and any digest mismatch. v1 admits
  only class-1 `review_fingerprint_trails_status`; class-2 (waiving
  `verdict == ACCEPT`) is NOT admitted. Anti-self-grant is two layers, not a
  proof: the literal + pin + committed+sealed evidence make a forged waiver
  non-silent (it must be committed into reviewed history and surfaced in the
  banner), but code cannot prove the evidence text came from a human — the
  final guarantee is mandatory human verification of the evidence verbatim
  before release (the banner is the trigger), a workflow obligation the
  validator cannot mechanically enforce. Release is never silent: on PASS the
  validator prints
  `PASS (N authorized exceptions applied: <id>@<scope>, …)`.
- Authorized exceptions can NEVER waive the negative list, even with a record
  present: (1) `status.diff_fingerprint` recomputes consistently, (2) clean
  worktree, (3) reviewer identity separation, (4) an exception record's own
  `evidence_file` being a committed, digest-sealed repo-relative file, (5) an
  exception record's own structural integrity (fields, authorizer,
  `assertion_id`, fingerprint pin, `reason`, `at`). The exemption mechanism
  cannot exempt itself; any malformed record fails closed and invalidates every
  exception.

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
5. Bookkeeper creates and records `stage/<stage-id>` at H_intake before stage
   commits begin.
6. Design stage scope and acceptance criteria.
7. Run development detail breakdown for `MEDIUM`, `HIGH`, or `MILESTONE`
   stages.
8. Split implementation tasks.
9. For parallel development stages, validate dispatch completeness with
   `scripts/validate-stage.py <stage-id> --phase dispatch-ready` before
   launching implementers.
10. Implement the bounded task.
11. Run deterministic tests, lint, type checks, or replay checks.
12. For parallel development stages that explicitly opt in with
   `parallel_mode.embedded_review.enabled: true` and a recorded reason, run
   embedded cross-review checkpoints from `docs/parallel-development-mode.md`
   before the formal review gate; these checkpoints are off by default and
   never replace committed-state review-1.
13. Commit the bounded stage artifacts locally on the stage branch, compute the
   standard
   `diff_fingerprint`, run `scripts/validate-stage.py <stage-id> --phase
   pre-review`, then review raw artifacts.
14. If review returns `REWORK`, use the reviewer-provided `fix_start_prompt`
   to launch the fix task.
15. Repeat only within the bounded stage until `review-2 ACCEPT`, then stop at
   `stage_accepted_waiting_user`. Merge back to `main` only after explicit user
   acceptance.

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
3. The stage task passes review, enters `stage_accepted_waiting_user`, and then
   waits for explicit user acceptance before any merge to `main`.
4. Human escalation is required because the workflow hit a non-automatable
   product decision, missing evidence that models cannot collect, repeated
   invalid verdict output, or the rework limit.

Other failures, including invalid JSON, failed tests, missing artifacts, or a
single model failure, are routed to retry, fix, fallback, or evidence collection
inside the active workflow before escalating to one of these terminal reasons.

## Output Footer

Every model-facing report, handoff, review narrative, and significant
bookkeeper response should end with:

```text
当前 Session ID: <provider-native id | unavailable (reason)>
Session ID 来源: <runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable>
原始输出路径: <stage raw artifact path | unavailable (reason)>
本地北京时间: YYYY-MM-DD HH:MM:SS CST
下一步模型: <model-or-human>
下一步任务: <specific next task>
```

The timestamp must come from a local `date` command, not from model memory.
Session IDs must come from provider/runtime evidence and must never be guessed.
If the current model cannot see its provider-native ID, write `unavailable`
with the reason; the runner or human operator may add the verified ID to
`status.json.session_receipts`. Follow
`docs/model-adapters.md#session-id-capture-and-execution-receipts` for the
provider-specific lookup and verification order. A Session ID is navigation
metadata, not a credential, raw review artifact, provider identity, or a
cross-provider transcript locator. The raw output path and committed artifacts
remain the review evidence, while `status.json` remains the authoritative
machine-readable state. Review outputs under
`review_artifact_protocol: raw-plus-strict-json/v1` are exempt from this
footer: their stdout is exactly one JSON object, and navigation, timestamps,
producer exit status, and Session ID data live in the operator capture receipt
and `status.json.session_receipts` — never inside
`reviewer_prior_involvement_notes` or outside the verdict JSON. On legacy
(pre-protocol) stages, place the footer before the final JSON block so the
final JSON contract remains parseable.

## Checkpoint Requirements

Before reporting completion, switching stage, compacting context, or asking
another model to continue, update:

- `status.json`
- `70-handoff.md`
- The active role report, such as `20-implementation.md`, `30-review-1.md`, or
  `50-review-2.md`
- `60-test-output.txt` when tests or command checks were run
- `status.json.session_receipts` for completed model executions, including an
  explicit unavailable reason when no provider-native Session ID can be
  verified

The checkpoint must include current branch, `stage_branch` metadata, HEAD if
available, git status, changed files, test status, open findings, blockers, and
next action.

Checkpoints before review may be uncommitted. Review gates may not be
uncommitted.

## Local Command Notes

`docs/model-adapters.md` is the local command runbook. It records the currently
observed command forms for Codex, Claude, Claude-GLM, Grok, and Kimi, including
read-only review, write-capable development where applicable, and explicit
yolo/bypass modes.

Key reminders:

- Codex prompt execution uses `codex exec`.
- Codex free-form review may use `codex review`, but schema-bound Harness
  review nodes use read-only `codex exec` with the review prompt.
- `codex -p` is a profile flag, not a prompt flag.
- Claude review uses the configured Claude adapter model, currently
  `claude-fable-5`; if Fable5 quota is exhausted, the configured backup model is
  `opus4.8`, unless the registry or user changes it.
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
