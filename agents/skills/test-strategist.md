---
local_skill_id: test_strategist
source: local
agency_ref: null
adapted_for: ai_project_harness
---

# Test Strategist Skill

## Authority

`AGENTS.md`, workflow YAML, and product acceptance criteria override this skill.

## Mission

Define deterministic evidence for domain correctness. Tests are the
primary oracle; model review is only a secondary quality gate.

## Rules

- Prefer deterministic unit tests and replay fixtures over live external calls.
- Cover domain calculations, parsing, persistence, permissions, external
  integration contracts, and risk-limit behavior.
- Record exact commands, exit codes, git state, and output location.
- Mark skipped or stale tests explicitly.
- Do not claim domain correctness from model review alone.
- Any unconfirmed domain assumption becomes a human gate.

## Required Output

- Test matrix.
- Fixtures or replay data needed.
- Commands to run.
- Pass/fail criteria.
- Known gaps and human gates.
