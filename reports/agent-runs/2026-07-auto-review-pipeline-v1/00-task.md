# Stage Task: 2026-07-auto-review-pipeline-v1

## Authority And Frozen Input

This is a Harness-only delivery stage governed by `AGENTS.md` and
`workflows/templates/stage-delivery.yaml`.

The authoritative requirements source is:

`reports/agent-runs/2026-07-auto-review-pipeline-design-review/40-operator-decision-table.md`

Its D1–D12, P1–P13, rework numbers, vocabulary, and non-goals are frozen. This
task may refine implementation mechanics but may not reopen those operator
decisions.

## Goal

Add a deterministic, stage-opt-in auto-review pipeline that can run the bounded
middle of a Harness delivery—implementation dispatch, blocking checks,
embedded cross-check, seal, review-1, and bounded fix loops—while preserving:

- the existing committed-range `diff_fingerprint` formula;
- provider/session isolation;
- raw evidence and strict verdict validation;
- a single stage rework ledger;
- human-started review-2 and human-authorized merge;
- the existing human-dispatch workflow as the default and fallback path.

The result must be default-off, fail-closed, testable without live model calls,
and ready for two later pilot stages. This bootstrap stage must not use the new
pipeline to implement or review itself.

## Delivery Outputs

1. Top-level Harness policy and workflow amendments for an explicit
   `auto_review_pipeline/v1` mode.
2. A human-readable `docs/auto-review-pipeline.md` contract, including the
   two-pilot protocol and P11 metrics: Grok schema-valid rate, escalation-shape
   validation, and runner RECEIPT completeness.
3. Deterministic runner and seal tooling with one canonical fingerprint
   implementation path.
4. Machine-readable authorization and runner receipt schemas.
5. Validator/status/template support for authorization, budgets, review units,
   evidence, mode transitions, and escalation.
6. Deterministic tests for auto mode and regression tests proving manual mode
   remains unchanged.
7. Harness manifest updates so every new Harness-owned asset is synced.

## File Boundaries

### Allowed Harness Contract Files

- `AGENTS.md`
- `harness-manifest.yaml`
- `workflows/templates/stage-delivery.yaml`
- `agents/registry.yaml`
- `agents/developer-discipline.md`
- `agents/skills/code-reviewer.md` only if required by the frozen verdict
  boundary
- `agents/skills/minimal-change-engineer.md` only if required by bounded fix
  routing
- `docs/model-adapters.md`
- `docs/parallel-development-mode.md`
- new `docs/auto-review-pipeline.md`
- `reports/agent-runs/README.md`
- `reports/agent-runs/_template/status.json`
- `reports/agent-runs/_template/70-handoff.md`

### Allowed Harness Schemas And Scripts

- new `schemas/auto-review-authorization.schema.json`
- new `schemas/runner-receipt.schema.json`
- `scripts/validate-stage.py`
- new `scripts/harness_stage_lib.py`
- new `scripts/stage-seal.py`
- new `scripts/auto-review-runner.py`
- new `scripts/tests/test_harness_stage_lib.py`
- new `scripts/tests/test_stage_seal.py`
- new `scripts/tests/test_auto_review_runner.py`
- new `scripts/tests/test_validate_stage_auto_review.py`

The development breakdown may remove optional files from this allowlist. Adding
another implementation path requires a recorded design amendment before
dispatch.

### Stage Evidence Files

- `reports/agent-runs/2026-07-auto-review-pipeline-v1/**`

### Read-Only Inputs

- `schemas/review-verdict.schema.json`
- `reports/agent-runs/2026-07-auto-review-pipeline-design-review/**`
- `reports/follow-ups/2026-07-auto-review-pipeline-*.md`
- historical accepted Harness stage evidence used only as regression examples

### Forbidden Or Out Of Scope

- `backend/**`
- `frontend/**`
- `schemas/api/**`
- product PRD, product roadmap, funding semantics, runtime services, and public
  API contracts
- any `reports/agent-runs/<other-stage-id>/**` mutation
- `schemas/review-verdict.schema.json` structural changes in v1
- any new `diff_fingerprint` or worktree-fingerprint field/protocol
- live order, borrow, repay, transfer, deployment, credentials, or external
  product side effects

## Required Control Contract

### Opt-In And Authorization

- Missing or disabled auto-review configuration means current human dispatch.
- Auto mode requires a schema-valid, human-approved authorization artifact for
  the exact stage, branch, allowed adapters, paths, budgets, topology, and
  frozen rework limits.
- Changing authorization-relevant fields stops the runner and requires a new
  human authorization artifact.

### Runner Authority

- The runner is deterministic and non-LLM.
- It is the only automatic adapter invoker and mechanical writer.
- Models cannot select the next adapter, shell command, state transition,
  commit range, or authoritative evidence path.
- Model-produced commands are never executed.

### Review Snapshot And Evidence

- Embedded cross-check occurs before seal when required or selected.
- Blocking checks run once before embedded cross-check and again after its
  evidence is written, immediately before seal.
- Blocking checks must depend only on frozen code/test/config pathspecs and
  must not read `reports/agent-runs/<stage-id>/` evidence as test input.
- The exact observed `git diff --binary` patch is saved and compared
  byte-for-byte with the same base/pathspec after seal; no comparison hash is
  recorded as a fingerprint.
- Seal uses the existing fingerprint implementation and a committed clean
  snapshot.
- Status binding and verdict recording use later mechanical evidence commits
  without rebinding the reviewed snapshot.

### Review Units And Isolation

- Serial delivery uses task review units; all required units must ACCEPT.
- A non-empty post-task code-scope integration diff becomes another required
  integration unit.
- Parallel delivery integrates isolated task worktrees and uses one tip review
  unit.
- A review-1 provider must differ from every implementation/fix author provider
  in the reviewed unit.
- Grok is auto-mode review-1 only; manual stages retain existing routing.
- Tip-once Grok failure escalates to a human; no automatic high-end fallback.

### Bounded Retry And Cost

- `max_rework_per_stage = 3` remains one stage ledger.
- All automatic code-changing retries combined may consume at most 2.
- One blocking-test retry is allowed and consumes that budget.
- Invalid JSON gets at most two attempts per model; attempts consume call budget
  but not rework budget.
- Every model invocation attempt consumes call-count budget once adapter
  execution begins.
- Wall-clock budget covers one uninterrupted authorized runner session; resume
  after a human stop requires renewed authorization.

### Human Fallback And Final Gates

- Runner preflight/control failures produce evidence, switch to a pending human
  path, and stop. They do not silently continue.
- Human dispatch resumes only after an explicit human action recorded in
  status/evidence.
- Review-2 remains human-started.
- Review-2 ACCEPT remains `stage_accepted_waiting_user`, not merge authority.

## Acceptance Criteria

1. **Default compatibility:** absent/false auto configuration preserves current
   DRAFT-2 workflow, validator behavior, review routing, and human dispatch.
2. **No self-host:** this stage records and uses auto mode as disabled.
3. **Authorization:** invalid, missing, expired, wrong-stage, wrong-branch, or
   incomplete authorization fails before any model invocation or commit.
4. **Runner-only control:** all automatic transitions and adapter calls come
   from frozen workflow/registry mappings, never from model text.
5. **Exclusive worktree:** auto mode refuses a shared, wrong-branch, or dirty
   integration worktree outside the explicitly allowed phase.
6. **Cross-check semantics:** required attempts always produce raw output or a
   recorded unavailable/skip artifact; advisory absence remains fail-open.
7. **Seen-diff bind:** captured and sealed code-scope patches compare
   byte-for-byte; mismatch fails closed; no new fingerprint field exists.
8. **Fingerprint compatibility:** old and new tooling compute byte-identical
   existing `diff_fingerprint` values for the same committed range.
9. **Seal protocol:** snapshot, status binding, validation, clean-tree checks,
   and crash recovery are deterministic and auditable.
10. **Review-unit completeness:** review-2 cannot start until every required
    unit has schema-valid ACCEPT bound to that unit's fingerprint.
11. **Provider isolation:** ineligible review candidates are rejected from the
    full author-provider set of the review unit.
12. **Fallback:** serial unit fallback occurs only when eligible; parallel tip
    Grok failure escalates without automatic GPT/Claude substitution.
13. **Verdict parsing:** raw output is preserved; exactly one final
    schema-valid verdict object is accepted and stored unaltered.
14. **Verdict-record commit:** review evidence is committed without changing
    the reviewed snapshot fingerprint.
15. **Multi-owner REWORK:** v1 never permits concurrent writes to one stage
    worktree; domain fixes are serialized and followed by unified checks/seal.
16. **Single ledger:** blocking fixes, review-1 fixes, and review-2 fixes share
    `max_rework=3`; automatic code-changing charges cannot exceed 2.
17. **Cost bounds:** model-call caps, per-adapter timeouts, and the shared
    rework/automatic-code-change ledgers fail closed with an `80-*.md`
    escalation artifact. There is no total runner-session wall-clock budget;
    long-running stages may continue for hours while those bounded controls
    remain satisfied.
18. **Mode transitions:** only documented auto→pending-human→human and
    human→auto-with-new-authorization transitions are valid.
19. **Threat boundary:** code/reports/model output are untrusted data; receipts
    contain command references, never expanded aliases, environment dumps,
    tokens, or credentials.
20. **Status compatibility:** top-level Harness statuses remain unchanged;
    unknown auto substates or transitions fail closed.
21. **Deterministic tests:** unit/integration tests use fake adapters and local
    temporary git repositories; no test invokes a live model or network.
22. **Manual regression:** current checkpoint, dispatch-ready, pre-review, and
    pre-accept paths remain covered.
23. **Harness sync:** manifest/install/update ownership includes all new assets.
24. **Pilot gate:** documentation keeps default off and requires two accepted
    pilot stages before any future default-flip decision. Each pilot records
    Grok schema-valid attempts/rate, validates every generated escalation
    artifact against the frozen shape, and reports expected/valid RECEIPT counts
    and completeness rate. At least one controlled pilot path must exercise an
    escalation; both pilots require 100% RECEIPT completeness and at least one
    final schema-valid Grok verdict. No global Grok-rate promotion threshold is
    invented in v1; the future operator default-flip decision evaluates the
    recorded rate.
25. **Scope isolation:** the committed delivery diff contains no forbidden
    product/runtime paths.
26. **Mode mutex:** legacy `parallel_mode.enabled=true` and
    `auto_review_pipeline.enabled=true` cannot coexist. Auto mode expresses
    serial/parallel topology inside its own authorization/review-unit contract.
27. **Post-cross-check blocking:** every executed or unavailable/skipped
    embedded cross-check is followed by the frozen blocking command set before
    seal; evidence-only writes cannot affect command inputs, and any failure
    blocks seal.
28. **Authorization expiry:** `expires_at` is required and nullable; `null`
    means no authorization-expiry timestamp, while non-null ISO8601 values are
    enforced before every model call and commit. Call-count, per-adapter
    timeout, rework, automatic-code-change, operator-stop, and stage gates
    remain active for a null-expiry session.

## Operator-Approved Contract Amendment — 2026-07-12

The operator explicitly withdrew frozen decision P8's mandatory total
wall-clock budget after review-2 round 3 demonstrated that the requirement is
counterproductive for legitimate multi-hour work. The superseding authority is
`54-p8-wall-clock-withdrawal-operator-decision.md`; the bounded design is
`15-p8-wall-clock-withdrawal-design-amendment.md`.

This is a human-authorized contract amendment after
`human_escalation_required`, not a fourth rework charge. `rework_count` remains
3/3. The amendment removes `wall_clock_seconds`, `run_started_at`,
`run_deadline_at`, and total-session deadline enforcement. It preserves model
call caps, adapter-specific invocation timeouts, the shared rework ledger,
automatic code-change caps, nullable `expires_at`, explicit operator stop, and
all stage/review/merge gates. Because auto-review v1 is default-off, has not
piloted, and has not been accepted or merged, v1 is corrected in place without
introducing a legacy authorization variant.

## Required Test Evidence

The development breakdown must preserve exact commands. Minimum expected suite:

```text
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
python3 -m py_compile scripts/validate-stage.py scripts/harness_stage_lib.py scripts/stage-seal.py scripts/auto-review-runner.py
scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint
git diff --check <delivery-base>..<delivery-head>
```

Tests must cover positive and negative fixtures for authorization, transition
matrix, budgets, rework accounting, provider isolation, verdict parsing,
seen-diff binding, allowlisted paths, seal crash points, resume behavior,
escalation artifacts, nullable/expired authorization, post-cross-check blocking
with evidence-directory mutations, pilot metrics, and manual-mode regression.

## Bootstrap Stage Routing

- Implementation mode for this stage: current human-dispatch DRAFT-2 only.
- Provisional implementation owner: Claude-GLM (`zhipu_glm`), because the work
  is control-plane/Python/YAML/documentation with no frontend surface.
- Provisional review-1: fresh read-only Kimi (`moonshot_kimi`) per cross-pool
  isolation.
- Codex/GPT is excluded from implementation/fix authorship.
- Review-2 provider is an unresolved human gate: OpenAI and Anthropic both have
  prior direction/design involvement and must not be recorded as `none`.
- No implementation or model dispatch is authorized by this document; HIGH
  development breakdown and dispatch-ready evidence remain mandatory.

## Human Gates

- Approve any expansion beyond the listed Harness files.
- Approve any third decision-model enablement for this stage's review-2.
- Before review-2, choose an eligible independent reviewer or satisfy the
  strong-reviewer disclosure override with runner-level evidence.
- Explicitly accept after review-2 before merge to `main`.

## Designer

- Provider: `codex`
- Provider identity: `openai`
- Model/session: GPT-5/Codex
- Skill: `software_architect`
- Prior involvement: Codex design-review contributor and intake author
- Date: 2026-07-11

本地北京时间: 2026-07-11 11:54:00 CST
下一步模型: Claude Fable 5（development breakdown author）
下一步任务: 在不实施代码的前提下，把本任务拆成串行、文件边界互斥、可独立 review-1 的 Harness implementation packets。
