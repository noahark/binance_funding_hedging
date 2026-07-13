# Handoff

This file is the stage's active handoff context. A new terminal session reads
it together with `status.json` and the active workflow to resume work; it does
not read `history/` at startup. Keep it current, and compact stale detail into
`history/` only after recording a full snapshot there.

## Recovery Header

Fixed, bounded resume block. A fresh session reads only this header plus
`status.json` to resume; keep every field filled and current.

- Active phase:
- Next action:
- Read-set: = status.current_inputs
- Open blockers:
- Do-not-read: reports/agent-runs/**/history/**, other stages

## Current State

- Stage:
- Status:
- Branch:
- HEAD:
- Git status:
- Bookkeeper:
- Parallel mode:
- Auto-review pipeline:
- Dispatch mode:
- Runner state:

## Artifact Index

- Intake:
- Task:
- Direction synthesis:
- Design:
- ADR:
- Implementation:
- Embedded review checkpoints:
- Auto-run authorization:
- Runner receipts:
- Embedded cross-check set:
- Escalation artifacts:
- Pilot metrics:
- Review 1:
- Fix report:
- Review 2:
- Test output:
- Status JSON:

## Open Findings

- None

## Blockers

- None

## Next Action

Describe the single next action.

本地北京时间:
下一步模型:
下一步任务:
