# Plan Review Synthesis And Normative Amendment

## Disposition

The four reviews converge on the same result: Decisions 1–3 are accepted, but
the following details are mandatory before implementation. This amendment is
the authoritative resolution of the plan-review findings; implementation does
not need another plan-review round.

Raw evidence and provenance are indexed in `09-plan-review-index.md`.

## Frozen Contract

### 1. Dispatch authority

- The rule is actor-neutral: no model session may invoke another model or model
  adapter. It stops and returns the prepared packet path.
- Every external implementation, review, fix, or optional embedded-review
  dispatch is executed by the human operator and records
  `executor: human_operator`.
- Remove or rewrite all surviving `executor:self`, implementing-terminal child
  adapter, R10 self-launch, and `manual_user_handoff_allowed: false` semantics
  across AGENTS, parallel-mode, workflow, adapters, template, and validator.
- A model claim that it launched another model is never dispatch evidence.

### 2. Review topology

- Default parallel flow is implementer report/self-tests → bookkeeper R4-style
  scope and diff reconciliation → committed task ranges/fingerprints → one
  fresh cross-provider formal Review-1 for each task → Review-2.
- Embedded review is optional and never replaces formal Review-1. Its exact
  opt-in is `parallel_mode.embedded_review.enabled: true` plus a non-empty
  reason. When false/absent in legacy data, no embedded artifacts are required;
  when true, dispatch, patch, raw output, verdict, round, and receipt fields are
  mandatory and external execution still belongs to the human.

### 3. Protocol activation and compatibility

- Canonical value: `review_artifact_protocol: raw-plus-strict-json/v1`.
- `_template/status.json` and this stage contain it. Active/new stages must have
  the exact value at dispatch-ready, pre-review, and pre-accept; missing or
  unknown values fail closed.
- Cold historical stages without it keep the legacy path so existing evidence
  is not rewritten. `validate-all-stages.py` must remain green.

### 4. Artifact names and authority

- Task Review-1: `30-review-1-<task-id>.raw-output.md` and
  `30-review-1-<task-id>.verdict.json`.
- Serial Review-1: `30-review-1.raw-output.md` and
  `30-review-1.verdict.json`.
- Review-2: `50-review-2.raw-output.md` and `50-review-2.verdict.json`.
- Retries add `-retry-N` before the artifact suffix; status points to the
  selected attempt. Generic narrative files may remain for history but are not
  gate authority under v1.
- The strict verdict file is authoritative. Corresponding status values are
  derived cache and must match the parsed file, never replace it.

### 5. Raw/verdict mechanical binding

- Raw is the exact captured stdout from one human-launched adapter and must
  decode as one JSON object with only surrounding JSON transport whitespace.
- Verdict is deterministic canonical serialization of that object, with no
  fence, prose, leading/trailing bytes, or terminal newline.
- The gate parses both and requires decoded-object equality before applying
  schema, status, role, model, fingerprint, and provider-isolation checks.
- This cannot cryptographically prove which provider produced bytes. Provider
  and Session ID remain an explicit human receipt/audit obligation.

### 6. Capture helper boundary

- Implement one shared, standard-library-only module/CLI at
  `scripts/review_artifacts.py`, reused by `validate-stage.py`.
- The helper consumes an already-captured raw file, an output verdict path, the
  schema path, and operator-supplied receipt metadata. It does not accept model
  selection or adapter commands; import adapter registries; spawn subprocesses;
  edit stage state; commit; retry; or advance workflow.
- The human captures the adapter exit status before invoking the helper. A
  non-zero producer exit fails the attempt. One-shot output capture is
  preferred; interactive sessions require explicit exact transcript export.
- Any received raw bytes remain as attempt evidence. The helper refuses output
  overwrite, writes verdict via temporary file + flush/fsync + atomic rename
  only after full success, and never damages an earlier valid verdict. Retries
  use new attempt paths.
- Shell examples must enable `pipefail` when a pipeline is shown and separately
  expose both producer and helper exit results; no example may hide failure in
  the left side of a pipe.

### 7. Schema and footer

- Runtime validation remains dependency-free. The shared module exhaustively
  enforces schema v1 (types, required keys, `additionalProperties`, constants,
  enums, minimums, finding structure, and conditional `fix_start_prompt`).
- A fixture corpus covers every constraint. When `jsonschema` is installed, a
  test compares the standard-library result with the canonical schema; it is a
  test oracle, not a runtime dependency.
- Protocol-v1 review stdout is exactly one JSON object and is exempt from the
  normal Markdown output footer. Navigation, timestamps, producer exit status,
  and Session ID source live in the operator capture receipt and
  `status.json.session_receipts`. `reviewer_prior_involvement_notes` retains
  only its disclosure meaning. No schema change is presently required.

### 8. Gate timing

- Dispatch-ready rejects external `executor:self`, validates owner/reviewer
  cross-provider routing and paths, and conditionally validates embedded-review
  fields only when enabled.
- Pre-review while entering/running `review_2` requires every task Review-1 pair
  for parallel stages or the top-level serial Review-1 pair to pass all protocol
  checks.
- Pre-accept repeats Review-1 checks and additionally requires Review-2 raw and
  verdict to pass. Missing evidence cannot be deferred past its transition.

### 9. Distribution and tests

- Add `harness-manifest.yaml` to implementation scope and register the helper
  and focused tests under `harness_owned`.
- Tests must cover all six incidents, raw/verdict mismatch, missing protocol on
  live stages, unknown protocol, default embedded-off pass, enabled-incomplete
  embedded fail, serial and parallel names, phase timing, wrong identity and
  fingerprint, producer failure, and atomic no-overwrite behavior.

## Scope Decision

The change remains one MEDIUM Harness-only task. No product, backend, frontend,
API, sample, credential, or completed-stage evidence file is in scope. Codex is
bookkeeper/designer and remains excluded from implementation. The user chooses
the implementation model.

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/13-plan-review-synthesis-and-amendment.md
本地北京时间: 2026-07-19 22:50:53 CST
下一步模型: user-selected implementation model
下一步任务: 严格按本修订实施单一 Harness 任务，不改产品代码
