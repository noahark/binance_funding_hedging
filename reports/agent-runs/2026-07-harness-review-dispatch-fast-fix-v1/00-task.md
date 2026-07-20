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
- `docs/harness-design.md`
- `docs/parallel-development-mode.md`
- `workflows/templates/stage-delivery.yaml`
- `docs/model-adapters.md`
- `harness-manifest.yaml`
- `scripts/validate-stage.py`
- `scripts/validate-all-stages.py`
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
15. `docs/harness-design.md` no longer directs an implementation model to launch
    another model or records `executor: self`; it states that embedded review is
    default-off, explicit opt-in only, and human-operator executed.
16. Every bare `30-review-1.md` or `50-review-2.md` reference in the workflow is
    explicitly identified as legacy-only or is replaced by a protocol-aware
    raw/verdict reference, without weakening legacy compatibility.
17. The AGENTS dispatch-ready rule states that embedded-review prompt and
    escalation checks apply only when
    `parallel_mode.embedded_review.enabled == true`.
18. The Fable5 implementation report names its actual canonical path,
    `20-implementation.md`, while preserving the report's authorship and audit
    history.
19. `ACTIVE.json` fails closed not only on invalid JSON but also when the JSON
    root or `active` member has an invalid shape. Only `active: null` or an
    object with a non-empty string `stage_id` is accepted; focused tests cover
    scalar, list, missing-key, missing-stage-id, non-string, and blank values.

## Human Gates

- The user chooses the independent plan reviewer.
- After plan review, the user chooses a different implementation model.
- On 2026-07-19 the user authorized `scripts/validate-all-stages.py` as a
  necessary Task H1 integration path and replaced the abandoned Grok attempt
  with Fable5 implementation from the committed baseline.
- On 2026-07-20 the user explicitly authorized the five non-blocking Kimi
  follow-ups above as an in-stage H1 continuation and requested commit and push.
  The implementation remains assigned to Fable5; the changed implementation
  fingerprint must receive a fresh protocol-valid Review-1 and Review-2 before
  user acceptance or merge.
- User-authorized stage evidence checkpoints may be committed and pushed to the
  stage branch. No implementation merge to `main` occurs until Codex verifies
  the bounded diff and tests, both review gates accept the updated fingerprint,
  and the user explicitly accepts the stage.

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/00-task.md
本地北京时间: 2026-07-20 11:01:36 CST
下一步模型: human operator → Fable5 / Anthropic
下一步任务: 人工执行 34-implementation-followup-fable5.prompt.md，完成五项用户授权补充修复
