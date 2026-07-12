# Development Breakdown — Serial-Only v1 Slimming

Status: **FROZEN FOR HUMAN DISPATCH**

Author: Codex/OpenAI, acting as operator-assigned bookkeeper and amendment
designer. Prior round-3 reviewer involvement is disclosed. Codex must not
implement or fix delivery code. Opus 4.8 is reserved for review-2 and receives
no breakdown/design task in this amendment.

## Topology And Ownership

- One serial implementation task: `T4-serial-v1-slimming`.
- Implementer: Claude-GLM / GLM-5.2 (`zhipu_glm`).
- Review-1: fresh read-only Kimi (`moonshot_kimi`).
- Review-2: human-started Opus 4.8 (`anthropic`), reserved from this amendment's
  design/breakdown/implementation.
- Bookkeeper: Codex/OpenAI; prepares packets and evidence commits only.
- Human operator executes every model dispatch.
- This human-authorized amendment does not increment or reset the historical
  `rework_count=3`.

## Exact Writable Set

Contract and startup policy:

```text
AGENTS.md
workflows/templates/stage-delivery.yaml
agents/registry.yaml
docs/auto-review-pipeline.md
docs/model-adapters.md
docs/parallel-development-mode.md
reports/agent-runs/README.md
reports/agent-runs/_template/status.json
reports/agent-runs/_template/70-handoff.md
schemas/auto-review-authorization.schema.json
schemas/runner-receipt.schema.json
```

Runtime and deterministic tests:

```text
scripts/auto-review-runner.py
scripts/harness_stage_lib.py
scripts/validate-stage.py
scripts/tests/test_auto_review_runner.py
scripts/tests/test_harness_stage_lib.py
scripts/tests/test_validate_stage_auto_review.py
```

Append-only evidence:

```text
reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md
reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
```

## Read-Only / Forbidden

Read-only Harness inputs:

```text
scripts/stage-seal.py
scripts/tests/test_stage_seal.py
harness-manifest.yaml
schemas/review-verdict.schema.json
reports/agent-runs/2026-07-auto-review-pipeline-v1/status.json
reports/agent-runs/2026-07-auto-review-pipeline-v1/70-handoff.md
reports/agent-runs/2026-07-auto-review-pipeline-v1/history/**
all task/review/verdict/decision/design/breakdown artifacts
```

Forbidden product paths:

```text
backend/**
frontend/**
schemas/api/**
docs/product/**
docs/api/**
```

No additional file may be touched without an appended blocker and a new
bookkeeper decision. Do not modify `docs/harness-design.md`; its phrase
"improves wall-clock time" refers to elapsed performance, not the removed
authorization budget.

## Work Package A — Contract Slimming

1. Add AGENTS startup read-budget rule: history is cold; no recursive startup
   scan; read status/handoff/current_inputs first.
2. Make auto v1 serial-only across AGENTS/workflow/registry/docs/templates.
3. Remove automatic parallel task/tip/integration promises and parallel-tip
   fallback semantics; retain legacy manual `parallel_mode` and mutex.
4. Reduce authorization schema to the exact field list in design §Authorization.
5. Keep fixed policies in workflow/runtime rather than repeating them per auth.
6. Update receipt timeout wording to adapter-specific timeout.
7. Update stage README/templates with history and active-context conventions.

## Work Package B — Runtime Alignment

1. Remove total-session wall-clock fields, methods, imports, calls, and tests.
2. Remove auth/runtime handling for deleted fields.
3. Make review units task-only and remove topology branches.
4. Keep Grok primary and serial Kimi/GLM fallback as fixed workflow policy.
5. Load registry `timeout_seconds` and command-specific timeout overrides.
6. Resolve timeout per adapter/command immediately before invocation.
7. Keep test-only invoker injection deterministic without weakening production
   registry authority.
8. Update validator and status-template budget shape.
9. Fix the duplicate shadowed FX6 test name and stale runner-lock docstring as
   adjacent P3 hygiene.

## Test Matrix

Authorization:

- slim valid auth passes schema and handwritten validation;
- each removed field independently fails as unknown;
- missing retained field fails;
- stage/branch/task/path/approval/expiry binding remains;
- stale parallel topology field fails.

Serial runtime:

- full real-seal happy path reaches `completed_review_1`;
- long fake-clock advance does not stop the run;
- no parallel/tip/integration runtime branch remains;
- invalid Grok output retries twice, then eligible serial fallback;
- provider isolation remains.

Timeout:

- GLM implementation receives registry 3000 seconds;
- Grok optional review receives command override 900 seconds;
- Kimi/other calls receive their registry timeout;
- a timed-out invocation consumes one call, records receipt, and stops using
  existing failure routing;
- model output cannot alter timeout.

Regression:

- expiry before calls/commits;
- shell-safe paths;
- lock loser zero-write;
- resume fail-closed;
- crash recovery and seal suite unchanged;
- verdict byte fidelity;
- rework/auto-change atomic accounting;
- manual mode and legacy parallel mode unchanged;
- fingerprint unchanged.

## Required Commands

```text
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
python3 -m py_compile scripts/validate-stage.py scripts/harness_stage_lib.py scripts/stage-seal.py scripts/auto-review-runner.py
scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint
git diff --check
grep -rn "formal-1" scripts harness-manifest.yaml     # expect exit 1
git diff --name-only 54ce1c8..HEAD | rg '^(backend|frontend|schemas/api|docs/product|docs/api)/'  # expect exit 1
rg -n 'wall_clock_seconds|run_started_at|run_deadline_at|_check_wall_clock|_init_wall_clock' AGENTS.md workflows agents docs schemas scripts reports/agent-runs/_template
rg -n 'auto.*parallel|parallel.*auto|kind.*(tip|integration)|scope\.topology|review_1_provider|allowed_adapters|auto_high_end_dispatch_allowed' AGENTS.md workflows agents docs schemas scripts reports/agent-runs/_template
```

Residue scans may match explicit migration/history statements. Every match must
be classified in the implementation report; no normative live requirement or
runtime field may remain.

## Review-1 Focus

- docs/workflow/schema/runtime tell the same serial-only story;
- no safety cap was accidentally removed with redundant auth fields;
- registry timeout is actually used, not merely documented;
- old authorization fields fail closed;
- history policy does not hide evidence from explicit review/audit requests;
- only writable files changed;
- no test expectation was weakened without a replacement proving the new
  operator-approved behavior.

本地北京时间: 2026-07-12 10:59:45 CST
下一步模型: Claude-GLM / GLM-5.2（human-dispatched implementation）
下一步任务: 执行 task-serial-v1-slimming-claude-glm.prompt.md，返回 20/60 append 证据，不 commit
