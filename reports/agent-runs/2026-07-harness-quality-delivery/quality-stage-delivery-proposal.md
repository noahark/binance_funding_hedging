# Quality Stage Delivery Proposal

Created at: 2026-07-03 16:08:27 CST
Status: Draft for external model review
Audience: Fable5 / Claude, GPT/Codex, GLM5.2, Kimi, project owner

## Purpose

This document proposes replacing the informal "loop" framing with a
quality-driven stage delivery process.

The goal is not to make agents run continuously. The goal is to produce
long-term maintainable delivery code with clear scope, bounded model authority,
raw evidence, reproducible reviews, and explicit human checkpoints.

Automation is useful only when it strengthens delivery quality. If automation
reduces evidence quality, skips human judgment, or encourages model drift, the
stage should stop and ask for human direction.

## Why Move Away From "Loop"

The word "loop" suggests that the main objective is to keep execution moving.
That is not the desired behavior for this project.

The desired behavior is:

- Each stage starts from a user-approved direction.
- Each stage has explicit development boundaries.
- Each implementation task has a specific owner and reviewer.
- Evidence is committed before review.
- Reviewers inspect raw artifacts, not controller summaries.
- A stage stops after acceptance and waits for the user to approve the next
  direction.

The workflow should therefore be described as stage delivery with quality gates,
not as a continuous loop.

## Proposed Stage Model

Each new development phase should be treated as a delivery stage:

```text
user direction discussion
  -> multi-model direction drafts when needed
  -> GPT/Codex synthesis for user approval
  -> Fable5 development detail breakdown
  -> bounded implementation by assigned models
  -> task-level cross review
  -> integration evidence and tests
  -> final review gate
  -> stop for user acceptance and next direction
```

The stage may contain multiple implementation tasks, but it should have one
clear acceptance boundary.

## Human Direction Gate

At the start of each meaningful stage, the project owner defines the direction,
quality bar, and non-goals.

For milestone or high-risk work, multiple models should independently discuss
the direction before implementation starts. The controller or GPT/Codex then
synthesizes the raw drafts into one proposed direction document for user review.

Development must not begin until the user approves or edits the synthesized
direction.

For small, mechanical, or already-covered tasks, the user may explicitly approve
skipping the multi-model direction panel.

## Fable5 Detail Breakdown Gate

After the user approves the direction, Fable5 should produce a development
detail breakdown before implementation begins.

This role is not an implementer. Its job is to narrow ambiguity and reduce
model drift.

The breakdown should define:

- Stage objective and non-goals.
- Backend and frontend ownership.
- File and directory boundaries.
- API contracts or data contracts.
- Required fixtures, samples, and schema files.
- Test commands and minimum evidence.
- Risk points and review focus.
- Explicit "do not touch" areas.
- Required checkpoint files.

The output should become part of the stage evidence, normally as
`10-design.md`, `11-adr.md`, or a dedicated detail-breakdown section inside the
stage design artifacts.

## Implementation Ownership

The default implementation split should be:

- Claude-GLM: backend, API contract, data normalization, deterministic tests,
  adapters, and service logic.
- Kimi: frontend UI, page state, API integration, visual behavior, and user
  interaction.

Backend work should expose a clear contract before frontend integration starts.
Frontend work should consume that contract instead of guessing backend fields.

If the stage requires both backend and frontend work, the controller should
split it into bounded tasks:

```text
backend contract / backend implementation
frontend UI / frontend integration
integration verification
```

Each task should produce its own implementation report and test evidence, but
the stage should have one final acceptance gate.

## Controller Role

Claude-GLM may act as the controller because its large context window is useful
for reading Harness rules, stage evidence, and handoff files.

The controller may:

- Prepare stage directories.
- Dispatch prompts to implementation and review models.
- Collect raw artifacts.
- Run validation scripts.
- Update `status.json` and `70-handoff.md`.
- Create local evidence commits before review.

The controller must not:

- Declare final acceptance.
- Hide raw evidence behind summaries.
- Review its own implementation in the same session.
- Treat unavailable local tools as proof that a model is globally unavailable
  without checking the configured adapter path.

## Task-Level Cross Review

Before final review, implementation tasks should be cross-reviewed.

Suggested default:

- Claude-GLM backend implementation -> Kimi review-1.
- Kimi frontend implementation -> fresh read-only Claude-GLM review-1.

The reviewing session must be fresh and read-only. It must not share the
implementer's session transcript, tool state, or hidden assumptions.

Review-1 checks:

- Scope compliance.
- Contract compatibility.
- Obvious correctness issues.
- Missing tests or weak evidence.
- Frontend/backend mismatch.
- Whether the work is ready for final review.

Review-1 cannot accept the whole stage. It can only say whether the task-level
work is ready to proceed, needs rework, or is blocked.

## Final Review Gate

Review-2 is the stage-level final review.

It should inspect the complete stage evidence:

- Workflow and task files.
- Design and ADR.
- Implementation reports.
- Fix reports.
- Raw diffs.
- Test output.
- API/data samples when relevant.
- Task-level review verdicts.
- `status.json` and `70-handoff.md`.

Default final review routing:

- GPT/Codex first, if eligible.
- Claude/Fable5 only if GPT/Codex is quota-exhausted, unavailable, auth-failed,
  or ineligible under anti-self-review.

If GPT/Codex designed the stage, it should not be the final reviewer for that
stage. In that case, Claude/Fable5 should be the final reviewer.

The final reviewer must return a strict schema-valid verdict. A valid `REWORK`
verdict must include a ready-to-send fix prompt.

## Evidence and Commit Discipline

Review gates require committed evidence.

Before review-1 or review-2:

- Stage artifacts must be written.
- Tests or command checks must be recorded.
- A local evidence commit must exist.
- `base_sha`, `head_sha`, and `diff_fingerprint` must be recorded.
- `scripts/validate-stage.py <stage-id> --phase pre-review` must pass.

Local evidence commits do not imply user approval to push, merge, deploy, or
mark the stage accepted.

The standard fingerprint remains:

```text
head_sha + ":" + sha256(git diff --binary <base_sha>..<head_sha> -- . ":(exclude)reports/agent-runs/<stage-id>/status.json")
```

No worktree fingerprint or alternate fingerprint protocol should be introduced.

## Output Footer Requirement

Every model-facing report, handoff, review, and significant controller response
should end with a short operational footer:

```text
本地北京时间: YYYY-MM-DD HH:MM:SS CST
下一步模型: <model-or-human>
下一步任务: <specific next task>
```

This footer is not a substitute for `status.json`, but it makes human handoff
and cross-model routing easier to audit.

For strict JSON review verdicts, the timestamp and next action should either be
inside schema-approved fields or placed before the final JSON block. The final
JSON block must remain the last parseable contract when the schema requires it.

## Stop Conditions

A stage should stop only when one of these conditions is true:

- Final review accepts the stage, then the project waits for user acceptance and
  the next direction.
- Both final decision models are unavailable or quota-exhausted.
- All eligible development or fix models are unavailable or quota-exhausted.
- Human escalation is required because of product ambiguity, missing evidence,
  repeated invalid verdicts, rework limit, or non-automatable risk.

The stage should not continue merely because another model can produce more
text. More model output is useful only if it resolves a concrete blocker.

## Proposed Harness Renaming

Consider renaming the workflow template from a loop-oriented name to a
stage-delivery name.

Candidate names:

- `quality-stage.yaml`
- `delivery-stage.yaml`
- `stage-delivery.yaml`

This is a naming and framing change. It does not require changing the evidence
model, registry, or review schema by itself.

## Open Questions For Fable5 Review

1. Should Fable5 always do development detail breakdown, or only for
   `HIGH`/`MILESTONE` stages?
2. Should task-level review-1 be represented as one stage-level `30-review-1.md`
   or as multiple task-specific review files?
3. Should frontend/backend task ownership be encoded in `status.json` as
   first-class task records?
4. How should the Harness prevent a controller from skipping Kimi or
   Claude-GLM cross-review when both are available?
5. Should the timestamp/next-model footer be added to all stage templates, or
   only to handoff and model reports?
6. What minimum runner automation is needed before this becomes reliable enough
   for repeated use across projects?

## Fable5 Review Absorption

Reviewed at: 2026-07-03 18:31:05 CST
Reviewer: Claude/Fable5
Disposition: Adopted with hardening

Accepted changes:

- Replace informal loop framing with `stage-delivery` / quality gates.
- Keep Fable5 development detail breakdown as a default gate for `MEDIUM`,
  `HIGH`, and `MILESTONE` stages; allow `LOW` stages to skip it when user
  approved or covered by existing synthesis.
- Treat development breakdown as design involvement. It must be disclosed if
  the same provider later performs review-2.
- Preserve the hard ban on implementation/fix author self-review. A provider
  that wrote delivery code or fix code is never eligible for final review of
  that code.
- Relax designer-provider isolation from a hard ban into a strong-reviewer
  disclosure override for Codex/GPT and Claude/Fable5.
- Allow the override only after an unrelated decision model fails a runner-level
  check, with fallback reason and evidence file recorded in `status.json`.
- Add `reviewer_prior_involvement` to the strict review verdict schema.
- Require validator checks for implementation-provider conflicts,
  design-conflict disclosure, fallback reason, and evidence file existence.
- Split task-level review-1 artifacts as `30-review-1-<task-id>.md` for
  multi-task stages and record task metadata in `status.json.tasks`.
- Add a per-model invalid verdict JSON limit of 2 attempts before treating that
  model as unavailable for the gate.
- Add the operational footer to handoffs and model reports, with timestamps
  sourced from the local `date` command.
- Rename the workflow contract to `stage-delivery.yaml`.

Not adopted as a default now:

- Adding Gemini as an active third review-2 fallback. The registry now keeps it
  as a future candidate if disclosure overrides become too frequent or the user
  explicitly approves a third decision model.

Implementation notes:

- Template repository updated and pushed at
  `3de53ee481d23aeeb5fa199d05a3269e518359e9`.
- Current project synchronized from the template repository after the push.
- `schemas/api/public-market/snapshot.schema.json` was restored after a sync
  script issue exposed that broad directory deletion can remove project-owned
  schema files.
- The sync script now uses an explicit `removed_harness_owned` manifest section
  for obsolete Harness files instead of deleting whole target directories.

## Recommended Next Step

Use the updated `stage-delivery.yaml` Harness for new stages. For the active
public-market contract stage, decide whether to re-run review-2 under the new
strong-reviewer disclosure override or keep the existing terminal
`decision_models_exhausted` record as historical evidence.

本地北京时间: 2026-07-03 18:31:05 CST
下一步模型: Human / Codex / Claude-Fable5
下一步任务: Decide whether the active contract stage should re-enter review-2 using the new disclosure override, or remain stopped with the recorded decision-model exhaustion.
