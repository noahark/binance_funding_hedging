# AGENTS.md - Funding Hedging Harness Rules

This file is the single startup document for agents working in this repository.
Read it before making changes, then read the active workflow and stage files.

## Project State

This is a new project. The current priority is to build a lightweight Harness for
requirements, design, implementation, review, fix, and evidence tracking before
the funding hedging product is implemented.

The first manual loop is not started yet.

## Authority Order

When documents conflict, use this order:

1. `AGENTS.md` - repository-level agent rules and safety gates.
2. `workflows/templates/*.yaml` - executable workflow contracts.
3. `schemas/*.schema.json` - machine-readable output contracts.
4. `agents/registry.yaml` - model, adapter, and skill routing.
5. `reports/agent-runs/<stage>/` - current stage facts and evidence.
6. `docs/*.md` - product, architecture, and design notes.
7. Imported or historical documents such as `Agent.md`, `CLAUDE.md`, and
   `多模型子代理编排与审查指南.md`.

Historical documents are references only. Do not copy old repository names,
servers, branch rules, secrets, or production incidents into the active Harness.

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

Codex and Claude rotate as stage designers. A designer creates the next stage
scope, file boundaries, non-goals, acceptance criteria, and test strategy.

### Implementers

Implementers can be Kimi subagents, Claude-GLM, Grok, or another explicitly
registered model. Implementers may write code only within the active task scope
and file boundary.

### Reviewers

Codex and Claude rotate as final reviewers. Reviewers are read-only. They must
inspect raw artifacts:

- Workflow YAML and `00-task.md`.
- The actual git diff or patch.
- Test output in `60-test-output.txt`.
- Implementation and fix reports.
- Relevant source files.

Reviewer output must end with a strict JSON verdict matching
`schemas/review-verdict.schema.json`. If the JSON is missing or invalid, the
stage is `BLOCKED`.

## Hard Gates

- Git is required. No git repository means no diff fingerprint and no review.
- Model claims are not evidence. Evidence is raw diff, test output, artifacts,
  schema-valid verdicts, and committed or uncommitted repository state.
- Final reviewer must not be the stage designer.
- Reviewer must not be the implementer of the reviewed task.
- Reviewer input must be raw artifacts and file paths, not only controller
  summaries.
- Invalid verdict JSON fails closed to `BLOCKED`.
- Failing tests do not enter final review unless the task is explicitly to
  document or triage the failure.
- Each stage has a finite rework limit. Default: 3.
- Product meaning, financial assumptions, destructive data actions, credentials,
  real trading, and public deployment require human approval.

## Standard Loop

The intended loop is:

1. Design stage scope and acceptance criteria.
2. Split implementation tasks.
3. Implement the bounded task.
4. Run deterministic tests, lint, type checks, or replay checks.
5. Review raw artifacts.
6. Fix if review returns `REWORK`.
7. Repeat until `ACCEPT`, `BLOCKED`, or rework limit is reached.
8. Use a different eligible designer for the next stage.

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

- Codex prompt execution uses `codex exec` or `codex review`.
- `codex -p` is a profile flag, not a prompt flag.
- `claude-glm` is a local shell alias/function. Invoke through an adapter and do
  not record its expanded environment.
- YAML files describe intent and routing. Command details belong in adapters or
  runner code, not arbitrary shell snippets embedded in tasks.
