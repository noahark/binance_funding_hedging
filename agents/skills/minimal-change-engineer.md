---
local_skill_id: minimal_change_engineer
source: local
agency_ref: null
adapted_for: ai_project_harness
---

# Minimal Change Engineer Skill

## Authority

`AGENTS.md`, workflow YAML, review findings, and schema files override this
skill.

## Mission

Fix review findings with the smallest traceable code or document change that
satisfies the stage acceptance criteria.

## Rules

- Touch only files required by the finding or its tests.
- Do not refactor adjacent code unless the finding cannot be fixed otherwise.
- Preserve user and other agent changes.
- Add or update tests when the finding is behavioral.
- Record every finding-to-fix mapping in `40-fix-report.md`.
- Do not mark completion until tests and reports are updated.

## Required Output

- Findings addressed.
- Files changed.
- Rationale for each change.
- Tests run and where full output is stored.
- Remaining blockers or residual risk.
