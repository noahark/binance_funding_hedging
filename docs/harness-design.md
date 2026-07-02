# Harness Design

## Purpose

The Harness coordinates long-running funding hedging development through
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
    -> creates stage blackboard
    -> dispatches designer / implementer / reviewer
    -> collects raw evidence
    -> validates strict JSON verdicts
    -> updates status and handoff
```

The controller is an orchestrator, not an acceptance authority.

## Controller

The default controller is GLM5.2 accessed through Claude Code using the local
`claude-glm` adapter. The reason for using it as controller is the large context
window, which is useful for reading workflow files, stage reports, and historical
handoffs.

Controller responsibilities:

- Select the next stage from workflow state.
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
- Treat command failure, timeout, missing JSON, or invalid schema as `BLOCKED`.

Known command semantics:

- Codex non-interactive development: `codex -C <repo> exec "<prompt>"`
- Codex review: `codex -C <repo> review --base <base> "<prompt>"`
- Codex `-p` means profile, not prompt.
- Claude Code print mode uses `claude -p "<prompt>"`.
- Local `claude-glm` must be invoked without recording its expanded auth
  environment.

## Evidence Model

Every review receives raw artifacts:

- `00-task.md`
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

- `final_reviewer` must differ from `designer`.
- `reviewer` must differ from `implementer`.
- If a rotation selects an ineligible model, the controller must choose the next
  eligible model or mark the stage `BLOCKED`.

## Verdict Contract

Reviewer output must end with one JSON object matching
`schemas/review-verdict.schema.json`.

Allowed verdicts:

- `ACCEPT`
- `REWORK`
- `BLOCKED`

Invalid or missing JSON is treated as `BLOCKED`.

## Testing Priority

Funding hedging correctness must be anchored in deterministic tests and replay
fixtures. Review is a second layer, not the oracle.

The first real product stage should prioritize:

- funding rate parsing
- fee and slippage assumptions
- position sizing
- hedge ratio calculations
- PnL accounting
- exchange API fixtures
- replay or backtest baselines
- risk and liquidation constraints

Without these checks, the loop becomes model-reviewing-model and cannot prove
financial correctness.

## Deferred Work

Not implemented yet:

- A runner.
- Automatic model invocation.
- Manual first loop execution.
- Git commits for bootstrap.
- Product PRD and technical stack decisions.
