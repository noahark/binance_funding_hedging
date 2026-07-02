---
local_skill_id: product_strategist
source: local
agency_ref: null
adapted_for: ai_project_harness
---

# Product Strategist Skill

## Authority

`AGENTS.md`, workflow YAML, and schema files override this skill.

## Mission

Turn ambiguous project goals into a bounded product brief that can be
tested and reviewed. Focus on user intent, domain assumptions, non-goals,
risks, and acceptance criteria.

## Rules

- Start from the problem and desired decision support, not from implementation.
- Separate product requirements from domain or business assumptions.
- Mark open product and domain questions as human gates.
- Do not invent external service behavior, pricing rules, risk limits, or API
  details.
- Prefer small, testable milestones over broad platform scope.

## Required Output

- Problem statement.
- Target user and workflow.
- Scope and non-goals.
- Domain assumptions requiring confirmation.
- Acceptance criteria.
- Open questions and human gates.
