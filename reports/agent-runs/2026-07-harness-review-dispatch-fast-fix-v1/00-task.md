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
- `harness-manifest.yaml`
- `scripts/validate-stage.py`
- one new shared deterministic review-artifact helper/CLI under `scripts/`
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
4. A human-invoked capture helper consumes one already-captured raw response,
   writes a separate strict verdict JSON atomically, and never selects a model,
   imports or invokes an adapter, advances status, commits, retries, or launches
   another process. Adapter execution and exit-code capture remain visibly human
   operations.
5. Protocol-v1 task Review-1 uses
   `30-review-1-<task-id>.raw-output.md` and
   `30-review-1-<task-id>.verdict.json`; serial Review-1 omits the task suffix;
   Review-2 uses `50-review-2.raw-output.md` and
   `50-review-2.verdict.json`. Retry attempts use a `-retry-N` suffix and status
   points to the selected attempt. Bare narrative `30-review-1.md` and
   `50-review-2.md` are non-authoritative compatibility artifacts under v1.
6. Missing/empty output, fenced JSON, narrative outside JSON, raw/verdict object
   mismatch, invalid schema, wrong fingerprint, wrong role/model, or
   same-provider review fails before phase advancement. Verdict files are the
   authority; matching status fields are derived and cross-checked.
7. Review prompts under protocol v1 emit exactly one JSON object. They are
   exempt from the Markdown footer rule; navigation and Session ID data live in
   the operator capture receipt and `status.json.session_receipts`, never in
   `reviewer_prior_involvement_notes` or outside the verdict JSON.
8. `review_artifact_protocol: raw-plus-strict-json/v1` is default-on in the
   stage template and mandatory for active/new stages at dispatch-ready,
   pre-review, and pre-accept. Cold historical stages without the field retain
   legacy validation without mutation. This introducing stage uses v1 itself.
9. When `pre-review` is run for `status == review_2`, all required task/serial
   Review-1 raw+verdict pairs must already pass. Pre-accept additionally
   requires the stage Review-2 pair. The top-level serial Review-1 path is not
   omitted.
10. Parallel mode keeps mandatory bookkeeper scope/diff reconciliation and
    committed task fingerprints even when embedded review is off. The explicit
    opt-in is `parallel_mode.embedded_review.enabled: true`; only then are its
    dispatch, patch, raw output, verdict, round, and reason fields required.
11. Runtime validation remains Python-standard-library-only. One shared module
    implements the schema-v1 checks used by both helper and validator; fixtures
    exercise every constraint and compare with `jsonschema` when that optional
    package is available.
12. The new helper and its focused tests are registered in
    `harness-manifest.yaml` so Harness sync cannot omit the producer required by
    the validator.
13. Positive and negative fixtures cover the six reported failures plus
    raw/verdict mismatch, missing protocol on a live stage, conditional embedded
    review, serial Review-1, phase timing, and failed overwrite/partial-write.
14. Harness docs, workflow YAML, templates, validator, helper, and tests describe
    one consistent flow.

## Human Gates

- The user chooses the independent plan reviewer.
- After plan review, the user chooses a different implementation model.
- No merge or push occurs until Codex verifies the bounded diff and tests and
  the user-approved fast-fix route is satisfied.

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/00-task.md
本地北京时间: 2026-07-19 22:50:53 CST
下一步模型: user-selected non-Codex implementation model
下一步任务: 按 13-plan-review-synthesis-and-amendment.md 实现 Task H1
