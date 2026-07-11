# Stage Intake: 2026-07-funding-annualized-history-v1

## User Discussion Summary

The operator requested a read-only funding-history enrichment for the existing
opportunity table:

- Display 24h, 7D, and 30D annualized funding rates.
- Derive 24h from the existing estimated daily funding rate; derive 7D and 30D
  solely from settled `/fapi/v1/fundingRate` records.
- Open a right-side drawer from a table row with the selected symbol, the same
  three annualized values, and its near-30-day settled history.
- Keep the current route, wire version, sort basis, private channel behavior,
  and all trading/borrow/transfer execution surfaces out of scope.

Requirements source: `reports/follow-ups/2026-07-funding-annualized-history-drawer.md`.
It captures the operator discussion and supplies the math, API, rate-budget,
and UX constraints for this stage.

## Classification

- Complexity: `MEDIUM`
- Direction panel required: `false`
- Existing synthesis covers this work: `false`
- User approved lightweight route: `true`
- Lightweight skip allowed: `true`

## Rationale

- The operator has already frozen the product intent and the core financial
  semantics in the follow-up requirements; a new milestone direction panel
  would duplicate that decision.
- The stage changes a public snapshot contract, Decimal value-path math,
  bounded public-data retrieval, schema validation, and a substantive frontend
  interaction. It therefore requires recorded design and a development
  breakdown before implementation.
- Backend and frontend work are both substantial but can be serially split on
  a frozen additive wire contract. Serial ownership avoids the extra
  coordination and embedded-review machinery of parallel mode.

## Human Gates

- This package is ready for operator review, not implementation dispatch. The
  human operator must approve the intake/design package before either task is
  sent to an implementer.
- Canonical contract documentation promotion and merging to `main` remain
  separate user gates after review-2. This package does not authorize either.
- A live public raw sample is mandatory before any frozen public contract
  amendment can be accepted. Synthetic fixtures may add test coverage but
  cannot replace that evidence.

## Routing Decision

- Next node: `human_review_stage_package`
- On approval: `stage-design` is complete; dispatch Task A to Claude-GLM, then
  dispatch Task B to Kimi after Task A's committed wire contract is available.

## Bookkeeper

- Provider/model/session: Codex/GPT current session (`openai`)
- Independent from implementers: `true`
- If not independent, disclosure: not applicable; Codex/GPT is not an
  implementation or fix author for this stage.

## Parallel Mode

- Uses `docs/parallel-development-mode.md`: `false`
- R10 dispatch tail required: `false`
- R4 diff reconciliation required: `false`
- Reason: this is a serial two-owner delivery. The backend task freezes and
  tests the additive wire contract before the frontend task consumes it.

## Evaluator

- Provider: `codex`
- Model: current Codex/GPT session
- Skill: `complexity_evaluator`

```text
本地北京时间: 2026-07-10 13:13:36 CST
下一步模型: human
下一步任务: 审阅本 stage 包并确认是否允许按 Task A 后 Task B 的顺序派发。
```
