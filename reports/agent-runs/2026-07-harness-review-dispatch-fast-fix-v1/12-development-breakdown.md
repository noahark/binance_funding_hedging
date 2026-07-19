# Development Breakdown

## Status

Four independent plan reviews are complete. Their shared direction is accepted
with mandatory clarifications frozen in
`13-plan-review-synthesis-and-amendment.md`. No implementation model is assigned.

## Single Harness Task

Owner: user-selected model after plan review.

Allowed paths are defined in `00-task.md`. Product code is forbidden.

### Required Deliverables

- Consistent authority text across AGENTS/workflow/parallel-mode/adapters.
- Protocol-v1 template fields and live-stage enforcement with cold-history
  compatibility.
- `scripts/review_artifacts.py` as the shared dependency-free validator and
  human-invoked capture/normalization CLI. It consumes an existing raw file and
  never executes adapters or other subprocesses.
- Validator changes for human dispatch, optional embedded review, output files,
  raw/verdict equality, schema/fingerprint/identity, phase timing, serial/task
  naming, and legacy compatibility.
- `harness-manifest.yaml` registration for the helper and focused tests.
- Positive/negative fixtures listed in
  `05-root-cause-and-fix-plan.md#required-test-matrix`.
- `20-implementation.md` and `60-test-output.txt`.

### Forbidden Implementation Choices

- No automatic model selection or chained dispatch.
- No model adapter invocation from implementation/reviewer prompts.
- No in-place modification of raw reviewer stdout.
- No mandatory migration of completed stage status files.
- No use of `reviewer_prior_involvement_notes` for navigation metadata.
- No third-party dependency in validator/helper runtime paths.
- No change to product code or API schemas.

### Review Focus

- Authority order is consistent.
- Default review count is actually reduced to one task cross-review.
- Capture helper cannot replace a valid prior verdict on failure.
- Strict verdict is whole-file JSON and raw provenance remains verifiable.
- Legacy completed stages still pass.

### Frozen Implementation Sequence

1. Make dispatch authority actor-neutral in `AGENTS.md`; remove every surviving
   external model-side launch instruction from parallel docs, workflow, adapter
   guidance, templates, and validator. External dispatch is always
   `human_operator`.
2. Preserve bookkeeper diff reconciliation and committed H_A/H_B evidence while
   making `parallel_mode.embedded_review.enabled` default false. Validate the
   complete embedded artifact set only when explicitly enabled with a reason.
3. Add protocol v1 to `_template/status.json` and this stage. Freeze names:
   task Review-1 `30-review-1-<task-id>.*`, serial Review-1
   `30-review-1.*`, and Review-2 `50-review-2.*`, each as raw-output Markdown
   plus strict verdict JSON. Status holds the selected attempt paths.
4. Implement standard-library schema-v1 checking once in
   `scripts/review_artifacts.py`; reuse it from `validate-stage.py`. The helper
   reads an existing non-empty raw file, refuses overwrite, parses one JSON
   object with transport whitespace only, atomically writes canonical JSON with
   no trailing newline, and prints a receipt. Adapter exit status is captured by
   the human before helper invocation and recorded in `session_receipts`.
5. Make file verdicts authoritative. Parse raw and verdict, require decoded
   equality, then cross-check status, role, model, fingerprint, and provider
   isolation. At `pre-review`/`review_2`, require all Review-1 pairs; at
   pre-accept require Review-1 and Review-2 pairs.
6. Update protocol-v1 prompts so their stdout is exactly one JSON object; the
   normal report footer moves to operator receipt/session metadata for these
   strict outputs. Do not change verdict-schema meaning.
7. Register the helper/tests in `harness-manifest.yaml`; run focused positive and
   negative fixtures, optional parity against `jsonschema`, `py_compile`, YAML
   and JSON parsing, `git diff --check`, current-stage gates, and historical
   all-stage validation.

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/12-development-breakdown.md
本地北京时间: 2026-07-19 22:50:53 CST
下一步模型: user-selected non-Codex implementation model
下一步任务: 按冻结顺序实施单一 Harness 任务
