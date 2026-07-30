# Harness v2 Trial Hardening — Opus 5 Design

## Identity

- task_id: `harness-v2-trial-hardening-design-opus5`
- target_role: `Planner`
- target_model: `opus-5`
- provider: `anthropic`
- status_revision: `1`
- required_skill: `agents/skills/software-architect.md`

## Goal

Design the smallest implementable response to the nineteen Harness v2 trial
findings observed in the first live product stage. This is an independent
design task, not an implementation task.

The Human wants Opus 5 involved before any Harness file is modified. Challenge
the findings and candidate fixes rather than accepting the source document or
Codex's preliminary grouping by default.

Produce a Chinese-first design that:

- decides each `G1` through `G19` as accept, reframe, defer, reject, or already
  owned, with a short evidence-based reason;
- preserves `W1` through `W6`;
- defines one coherent first batch for result/verdict enforcement, high-risk
  plan review, repair-round semantics, contested acceptance checks, same-root
  brake, and review findings discovered outside the delivery range;
- defines a separate second batch for proven operational hygiene;
- treats `G11` as a separate destructive cleanup, not part of either delivery;
- explains whether any new executable file is necessary, its unique duty, why
  an existing authority cannot execute that duty, and how normative authority
  remains in `AGENTS.md`;
- gives exact future allowed-file boundaries, non-goals, tests, acceptance
  checks, migration/order constraints, and review focus for each batch;
- identifies the decisions Human must approve before implementation;
- states how the still-running product stage and any later findings are
  reconciled before code or contract edits start.

Pay particular attention to these design questions:

1. How can one small checker validate ordinary task results and review closure
   without recreating v1 schemas, YAML, or the monolithic validator?
2. Exactly when does `rework_count` increment after a delivered implementation,
   and which receipt/plan corrections remain excluded?
3. How can an implementer contest a faulty acceptance check with substitute
   evidence without silently passing a failed gate?
4. What happens after two repair rounds attributed to the same root cause?
5. How should review findings be classified when they predate the delivery:
   delivery-caused, pre-existing independent, or pre-existing release-critical?
6. How should immutable raw output, sealed evidence, drafts, and errata differ?
7. Which proposed fixes for `base_sha`, mid-flight revision changes, reading
   budgets, model launch documentation, and version markers would weaken v2 or
   restore duplicate authority?

## Allowed Files

You may create only:

- `reports/agent-runs/2026-07-harness-v2-trial-hardening-v1/20-opus5-design.md`

Do not modify `status.json`, `ACTIVE.json`, `PROJECT_STATE.md`, `AGENTS.md`,
`agents/**`, `scripts/**`, `docs/**`, product code, tests, or any other file.
Do not commit, merge, push, switch branches, start another model, access
credentials, operate a service, or perform a live action.

## Inputs

Read only:

1. `AGENTS.md`;
2. this dispatch;
3. `reports/agent-runs/ACTIVE.json`;
4. `PROJECT_STATE.md`;
5. this stage's `status.json`;
6. the `Planner`, `Reviewer`, and `Bookkeeper` sections of `agents/roles.md`;
7. `agents/skills/software-architect.md`;
8. the exact findings snapshot:
   `git show be789d6:docs/planning/harness-v2-trial-findings-2026-07-30.md`;
9. only the specific source lines or Git objects named as evidence by a finding
   when needed to verify or reject that finding.

Do not scan completed stages, unrelated product source, runtime data,
repository-external files, credentials, or moving history.

## Acceptance Checks

The design must:

1. cover all nineteen `G` findings and all six `W` preserve rules;
2. distinguish accepted problems from rejected or rewritten candidate fixes;
3. keep detailed rule authority in existing files and justify every new file;
4. avoid restoring v1 workflow YAML, registry, schema, adapter runbook, or
   monolithic validation;
5. specify two bounded, independently reviewable future delivery batches;
6. make the first batch's gate transitions and `rework_count` treatment
   unambiguous and resistant to task-renaming bypass;
7. give a three-way rule for pre-existing findings that preserves broad review
   sweeps without making scoped delivery hostage to unrelated debt;
8. preserve immutable raw evidence and define a bounded erratum path;
9. keep current product-stage files and state completely untouched;
10. end with a short plain-Chinese recommendation for Human, including choices
    that require Human approval.

## Stop

Write the design artifact, return the formal Task Result Protocol from
`AGENTS.md`, and stop for Codex Bookkeeper verification.

The dispatch `Identity` keys are input metadata, not result fields. Do not copy
them into the result block, invent visible result fields, rename Chinese labels,
or use any closing marker other than the standalone `[/TASK_RESULT]`.

Use `20-opus5-design.md` as the artifact path. The immediate next actor is Codex
Bookkeeper via Human transfer. Do not prepare an implementation packet or start
another model.
