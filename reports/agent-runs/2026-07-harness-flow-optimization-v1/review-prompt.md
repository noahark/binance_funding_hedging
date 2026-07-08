# External Review Prompt

You are reviewing a proposed Harness workflow change for this repository.

Read:

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `agents/registry.yaml`
- `docs/model-adapters.md`
- `docs/harness-design.md`
- `docs/parallel-development-mode.md`
- `reports/agent-runs/2026-07-harness-flow-optimization-v1/00-context-and-proposal.md`

Task:

Review whether the project should remove the model `bookkeeper` role and move
to a human-operated dispatch flow where GLM/Kimi implementer terminals execute
through implementation, embedded pre-review, scoped fixes, frozen evidence, and
formal review-1. Human then decides fix direction or dispatches review-2 to
Codex/Claude.

Output path:

```text
reports/agent-runs/2026-07-harness-flow-optimization-v1/reviews/<model-id>.md
```

Use your own model/provider name as `<model-id>`, for example:

```text
claude-fable5.md
claude-opus4.8.md
glm52.md
kimi-for-coding.md
grok-build.md
gemini3.1pro.md
deepseek-v4.md
```

Required review format:

```markdown
# Review: <model-id>

## Verdict

ACCEPT | REWORK | BLOCKED

## Summary

One short paragraph.

## Findings

List findings by severity. Include concrete file/rule references when possible.

## Required Changes

List changes required before adopting the proposal.

## Open Questions

List decisions that still need human approval.

## Recommended Trial Plan

Describe how to test this on one stage safely.

## Footer

本地北京时间: <timestamp if available>
下一步模型: <model-or-human>
下一步任务: <specific next task>
```

Review focus:

- Safety of removing the model bookkeeper.
- Whether human-operated dispatch is sufficiently auditable.
- Whether GLM/Kimi can safely run through review-1 preparation.
- Whether implementer-generated frozen evidence is acceptable if review-1
  audits it first.
- Required schema, validator, and workflow changes.
- Failure modes around self-review, stale diffs, missing evidence, invalid JSON,
  and human decision gates.

Do not modify product code. Do not rewrite the proposal in place. Write only
your review file under `reviews/<model-id>.md`.

本地北京时间: 2026-07-08 16:38:03 CST
下一步模型: external reviewer
下一步任务: Write review output to `reviews/<model-id>.md`.
