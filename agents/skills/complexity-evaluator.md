---
local_skill_id: complexity_evaluator
source: local
agency_ref: null
adapted_for: ai_project_harness
---

# Complexity Evaluator Skill

## Authority

`AGENTS.md`, workflow YAML, and user instructions override this skill.

## Mission

Classify the next work item so the Harness uses the right amount of model
coordination. The goal is to reserve five-model direction drafting for milestone
or high-risk requirement freezes, while allowing lightweight tasks to proceed
with a simpler path.

## Classification

- `LOW`: mechanical change, copy/text tweak, logging/metric rename, small config
  change, or test-only update.
- `MEDIUM`: bounded implementation within an already-approved direction, small
  API/UI behavior change, or limited bug fix with clear acceptance criteria.
- `HIGH`: core logic, risk controls, domain math, data model, external
  integration, cross-module behavior, or unclear test oracle.
- `MILESTONE`: new phase, product requirement freeze, architecture direction,
  strategy-level decision, or work that needs user co-review before development.

## Routing

- `LOW` and `MEDIUM`: skip five-model direction drafting when the user approves
  the lightweight route or an existing synthesis covers the work.
- `HIGH`: run five-model direction drafting unless the user explicitly narrows
  the task and accepts the risk.
- `MILESTONE`: always run five-model direction drafting and GPT/Codex synthesis
  before development.

## Required Output

- Classification: `LOW`, `MEDIUM`, `HIGH`, or `MILESTONE`.
- Reasoning in 3-7 bullets.
- Whether five-model direction drafting is required.
- Existing synthesis, if any, that covers the work.
- Required human gates.
- Recommended next workflow node.
