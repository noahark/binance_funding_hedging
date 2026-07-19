# Stage Task

## Goal

Remove contradictory model-to-model dispatch rules, make committed task review
the single default cross-review round, and guarantee that review evidence and
strict verdict JSON are captured mechanically before a stage can advance.

## Non-Goals

- No changes to `backend/**`, `frontend/**`, Binance behavior, credentials,
  product APIs, or borrow execution Boundary C.
- No autonomous pipeline that selects models or advances stage state.
- No rewrite of historical stage evidence.
- No weakening of committed-state fingerprints, provider isolation, human
  acceptance, or Review-2.
- No deletion of optional embedded review; it becomes explicit opt-in instead
  of the default path.

## Allowed Files

- `AGENTS.md`
- `docs/parallel-development-mode.md`
- `workflows/templates/stage-delivery.yaml`
- `docs/model-adapters.md`
- `scripts/validate-stage.py`
- one new deterministic review-output capture helper under `scripts/`
- focused tests/fixtures for the validator and capture helper under `scripts/`
- `reports/agent-runs/_template/**`
- `schemas/review-verdict.schema.json` only if clarification is necessary;
  avoid changing verdict meaning
- this stage's evidence directory

## Forbidden Files

- `backend/**`
- `frontend/**`
- `schemas/api/**`
- `reports/api-samples/**`
- prior completed stage artifacts
- secrets, shell profiles, credentials, and model transcript stores

## Acceptance Criteria

1. All external implementation/review/fix dispatches have
   `executor: human_operator`; an implementer/reviewer is forbidden from
   launching any other model terminal.
2. `validate-stage.py --phase dispatch-ready` rejects external review dispatch
   metadata using `executor:self`.
3. Parallel development defaults to exactly one cross-provider task Review-1
   after the bookkeeper commits the fixed task range. Embedded review is opt-in.
4. A human-invoked, single-dispatch capture helper preserves exact raw stdout,
   writes a separate strict verdict JSON atomically, and never selects a model,
   advances status, or launches a second dispatch.
5. Missing/empty output, fenced JSON, invalid schema, wrong fingerprint, or
   extra non-whitespace JSON content fails before phase advancement.
6. Review prompts default to JSON-only output. Navigation/footer metadata uses
   schema-approved fields; it is not placed outside the verdict object.
7. New protocol enforcement is opt-in/versioned for new stages; historical
   accepted stages continue validating without mutation.
8. Positive and negative fixtures cover the six reported failure modes.
9. Harness docs, workflow YAML, templates, validator, helper, and tests describe
   one consistent flow.

## Human Gates

- The user chooses the independent plan reviewer.
- After plan review, the user chooses a different implementation model.
- No merge or push occurs until Codex verifies the bounded diff and tests and
  the user-approved fast-fix route is satisfied.

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/00-task.md
本地北京时间: 2026-07-19 22:12:37 CST
下一步模型: user-selected independent plan reviewer
下一步任务: 审查问题归因、单次 Review-1 默认策略及 strict verdict 分离方案
