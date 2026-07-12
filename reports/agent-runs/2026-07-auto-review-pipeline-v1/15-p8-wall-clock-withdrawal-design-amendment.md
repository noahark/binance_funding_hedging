# Design Amendment — Remove Total Runner-Session Wall Clock

## Authority And Scope

Authority: the human operator decision recorded in
`54-p8-wall-clock-withdrawal-operator-decision.md`. It supersedes the
wall-clock portion of frozen P8 while preserving every unrelated D/P decision.

Complexity remains **HIGH** because this is a machine-readable Harness contract
amendment spanning documentation, schema, runner behavior, and deterministic
tests. The operator has already selected the direction, so no new direction
panel is required. Development breakdown remains mandatory.

## Intended Contract

The runner has no total-session elapsed-time deadline. Remove:

- authorization `budgets.wall_clock_seconds`;
- status/runtime `run_started_at` and `run_deadline_at`;
- `_init_wall_clock`, `_check_wall_clock`, and calls whose only purpose is the
  total-session deadline;
- timeout/escalation tests and documentation for aggregate elapsed time.

Preserve:

- `budgets.max_model_calls` and immediate charging before adapter start;
- registered per-adapter timeout behavior for each individual invocation;
- `max_stage_rework=3`, `max_auto_code_changes<=2`, and invalid-JSON attempt cap;
- required nullable `expires_at`, checked before every model call and commit
  when non-null;
- operator stop, authorization supersession, mode transitions, provider
  isolation, receipt evidence, seal/fingerprint, review-2, and merge gates.

The v1 authorization schema is corrected in place. Auto mode is default-off,
has not completed either pilot, has not been accepted, and is not on `main`;
there is no supported installed authorization contract to migrate. Because the
schema uses `additionalProperties: false`, a stale artifact carrying
`wall_clock_seconds` must fail validation rather than be silently normalized.

## Preliminary Delivery Boundary

Expected implementation files, subject to Opus breakdown narrowing:

```text
docs/auto-review-pipeline.md
docs/harness-design.md
schemas/auto-review-authorization.schema.json
scripts/auto-review-runner.py
scripts/harness_stage_lib.py
scripts/tests/test_auto_review_runner.py
scripts/tests/test_harness_stage_lib.py
```

Stage evidence append-only/output files:

```text
reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md
reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
```

Design/bookkeeper files are handled before implementation and are not part of
the implementer writable set. Historical reviews, verdicts, prompts, the
frozen 40-table, status, and handoff are read-only to the implementer.

The breakdown must check whether workflow, registry, validator, authorization
examples, manifest, or templates contain semantic (not merely lexical)
dependencies before freezing the final writable set. It must not add files
without identifying the exact dependency.

## Acceptance Delta

1. Authorization schema requires `max_model_calls` but neither requires nor
   permits `wall_clock_seconds`.
2. Runner does not derive, persist, resume, or enforce a total-session deadline.
3. A deterministic multi-hour fake-clock advance alone never stops a healthy
   run or prevents seal/review completion.
4. Individual adapter timeout still stops the affected call and records the
   existing failure evidence/call charge.
5. A non-null `expires_at` still fails closed before every call and commit;
   `null` remains valid.
6. Call/rework/automatic-change caps and all prior FX1–FX7 protections remain.
7. Manual-mode behavior and bootstrap default-off behavior remain unchanged.
8. No second clock/deadline field or compatibility protocol is introduced.
9. No product/backend/frontend/API path changes.
10. Documentation, schema, runner, tests, and examples contain no normative
    claim that a total wall-clock budget is required.

## Required Tests

- Update schema positive/negative fixtures to omit `wall_clock_seconds` and
  reject a stale authorization that includes it.
- Replace aggregate wall-clock tests with a long-duration fake-clock test that
  completes successfully when call/rework/adapter-timeout/expiry limits pass.
- Retain tests proving adapter timeouts consume calls and stop safely.
- Retain expiry tests across model calls and every seal commit.
- Run the full deterministic suite, Python compilation, checkpoint validator,
  `git diff --check`, formal-1 scan, forbidden product-path scan, and a global
  normative-reference scan for removed clock fields.

## Review Focus

- Removal is complete across schema, runner, docs, examples, and tests.
- Per-adapter timeout was not accidentally removed with total-session timing.
- `expires_at` semantics remain distinct and intact.
- No test was weakened merely to make an obsolete expectation disappear;
  replacement tests prove the new operator-approved behavior.
- Round-3 P1 is disposed by superseding/removing its requirement, not by
  claiming the old implementation satisfied the old contract.

本地北京时间: 2026-07-12 10:26:57 CST
下一步模型: Claude Opus 4.8（development breakdown author；human dispatch）
下一步任务: 将本设计收窄为 implementer packet 所需的精确 writable set、删除清单、测试矩阵和反漂移规则
