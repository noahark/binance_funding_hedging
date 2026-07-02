# Agent Run Blackboard

Each workflow stage gets one directory:

```text
reports/agent-runs/<stage-id>/
  00-task.md
  10-design.md
  20-implementation.md
  30-review-1.md
  40-fix-report.md
  50-review-2.md
  60-test-output.txt
  70-handoff.md
  status.json
```

Use `_template/` when creating a new stage.

## Ownership

| File | Owner | Purpose |
|---|---|---|
| `00-task.md` | Designer | Scope, non-goals, acceptance criteria, file boundaries |
| `10-design.md` | Designer | Architecture, task split, risks, test strategy |
| `20-implementation.md` | Implementer | Changed files, decisions, tests, remaining work |
| `30-review-1.md` | Reviewer | First review findings and strict JSON verdict |
| `40-fix-report.md` | Implementer | Fix mapping and retest evidence |
| `50-review-2.md` | Final reviewer | Final raw-artifact review and strict JSON verdict |
| `60-test-output.txt` | Controller | Raw or scrubbed command output |
| `70-handoff.md` | Controller | Current facts, artifact index, next action |
| `status.json` | Controller | Machine-readable stage status |

Reviewers must not edit implementation reports. Implementers must not edit
review files. Only the controller updates `status.json`.

## Status Values

Allowed values:

```text
planned
designing
implementing
testing
review_1
fixing
review_2
accepted
blocked
paused
```

## Evidence Rules

- Store enough output to reproduce the conclusion.
- Scrub credentials and tokens before committing reports.
- Mark stale or skipped tests explicitly.
- A stage is not accepted until `status.json`, `70-handoff.md`, test output, and
  schema-valid review verdicts agree.
