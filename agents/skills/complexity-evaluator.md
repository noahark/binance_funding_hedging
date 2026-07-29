---
local_skill_id: complexity_evaluator
source: local
agency_ref: null
adapted_for: ai_project_harness
---

# Complexity Evaluator Skill

## Authority

`AGENTS.md`, current `status.json`, the valid dispatch, and user decisions
override this skill.

## Mission

Classify the next work item only far enough to choose the v2 review path. Do not
create speculative coordination or revive the retired direction-panel route.

## Classification

- `LOW_RISK`: documentation or mechanical work with no business, money, live,
  credential, contract, or destructive effect.
- `HIGH_RISK`: orders, positions, borrowing, repayment, transfer, money/PnL or
  accounting meaning, live gates, risk limits, credentials, controlling
  contracts, destructive actions, or an unclear test oracle.

## Routing

- `LOW_RISK`: one independent final review is allowed when the dispatch records
  the reason.
- `HIGH_RISK`: require review-1 and review-2.

## Required Output

- Classification: `LOW_RISK` or `HIGH_RISK`.
- Reasoning in 3-7 bullets.
- Required human authorization.
- Required review path.
