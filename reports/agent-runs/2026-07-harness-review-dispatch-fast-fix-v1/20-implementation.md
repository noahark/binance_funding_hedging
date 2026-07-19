# Implementation Report — Task H1 (Fable5 clean-room)

## Result

**PASS.** Clean-room implementation from committed baseline `2eae7bd`
(branch `stage/2026-07-harness-review-dispatch-fast-fix-v1`). No Grok source
was recovered, reused, or patched. All frozen requirements are implemented; no
requirement had to be weakened, so no BLOCKER is raised. Stopping here for the
Codex bookkeeper; formal Review-1 was not launched and no other model or
adapter was invoked.

## Changed Files (all inside Allowed Files)

- `scripts/review_artifacts.py` — **new** shared stdlib-only protocol-v1
  module + human-invoked capture CLI.
- `scripts/tests/test_review_artifacts.py` — **new** focused fixture suite
  (86 tests, includes optional `jsonschema` oracle which runs locally on
  jsonschema 4.25.1).
- `scripts/validate-stage.py` — protocol-v1 gate, phase timing, pair binding,
  identity/fingerprint cross-checks, human-operator dispatch-ready rules,
  conditional embedded review.
- `scripts/validate-all-stages.py` — user-authorized integration: the
  aggregate sweep now calls the protocol gate with ACTIVE.json evidence.
- `AGENTS.md` — actor-neutral dispatch authority, protocol-v1 hard gate,
  embedded-review opt-in, footer exemption for protocol-v1 review stdout.
- `docs/parallel-development-mode.md` — v0.5: single dispatch authority,
  embedded review opt-in, R9/R10 rewritten without model-side self-launch,
  protocol-v1 artifact names, per-round PASS|BLOCKER result.
- `workflows/templates/stage-delivery.yaml` — actor-neutral guards, protocol
  default, protocol-aware Review-1/2 writes and output contracts with an
  explicit legacy branch, opt-in embedded checkpoint node.
- `docs/model-adapters.md` — actor-neutral dispatch rule plus the
  "Review Output Capture (Protocol v1)" runbook (producer exit captured
  separately; pipefail required for any pipeline example).
- `harness-manifest.yaml` — registers `scripts/review_artifacts.py`,
  `scripts/validate-all-stages.py`, and
  `scripts/tests/test_review_artifacts.py` under `harness_owned`.
- `reports/agent-runs/_template/status.json` — protocol v1 default-on,
  `parallel_mode.embedded_review` default-off, `raw_output_path`/
  `verdict_path` fields on review records.
- This stage's `20-implementation-fable5.md` (this file) and appended
  `60-test-output.txt`.

Not touched, per role boundary: `status.json`, `70-handoff.md`,
`reports/agent-runs/ACTIVE.json`, product/backend/frontend/API/sample files,
completed-stage artifacts, `schemas/review-verdict.schema.json` (no
clarification was needed; verdict meaning unchanged). Nothing was committed or
pushed.

## Key Design Decisions

1. **Canonical verdict bytes** = `json.dumps(obj, ensure_ascii=False,
   sort_keys=True, separators=(",", ":"))` in UTF-8, no surrounding bytes, no
   terminal newline. Deterministic regardless of raw key order; any byte
   difference fails (R4 fixed).
2. **Atomic no-clobber publication** uses temp file + flush + fsync +
   `os.link` — the hard link itself is the atomic no-clobber step, so there is
   no check-then-replace window (R7 fixed); temp file is always cleaned.
3. **Active-stage evidence** is `reports/agent-runs/ACTIVE.json` (explicit,
   no date heuristic). Missing protocol fails closed at dispatch-ready
   always, and at pre-review/pre-accept for the active stage; cold historical
   stages without the field stay legacy (R1 fixed). A malformed ACTIVE.json
   itself fails closed.
4. **Fingerprint semantics**: the verdict file is authoritative; the status
   review record's `model`/`verdict`/`diff_fingerprint` are derived cache and
   must equal the parsed verdict. Task pairs are additionally bound to the
   committed task fingerprint. The serial/top-level review-vs-status
   fingerprint equality stays in `validate_acceptance`, preserving RC4
   authorized-exception semantics unchanged.
5. **Review-1 isolation granularity**: task pairs isolate against that task's
   own implementer/fix author (cross-review pairs review each other by
   design); serial Review-1 and Review-2 isolate against all stage
   implementer/fix identities. Isolation uses the normalized status reviewer
   provider (`PROVIDER_IDENTITIES`), and the verdict `model` must equal the
   status-recorded reviewer model, closing the alias evasion (R5 fixed).
6. **Embedded review** requires `parallel_mode.embedded_review.enabled: true`
   plus non-empty `reason`; each enabled round requires dispatch, patch, raw
   output, integer `round`, and a non-formal `result: PASS|BLOCKER` (distinct
   from the formal verdict schema; R6 fixed). Legacy recorded entries are
   still artifact-validated without the new requirements, keeping history
   green.

## Requirement-to-Code Mapping

Prompt criteria 1–12 → implementation and proof:

1. Human-only external dispatch: `AGENTS.md` (dispatch authority paragraph +
   Hard Gates), `docs/parallel-development-mode.md` v0.5 (Phase 2, R9, R10),
   `workflows/templates/stage-delivery.yaml` (guards + implementation/
   review/embedded nodes), `docs/model-adapters.md` General Rules;
   `scripts/validate-stage.py` `validate_dispatch_ready` rejects executor
   `self` and requires `human_operator`. Tests:
   `TestDispatchReady.test_executor_self_rejected` /
   `test_executor_other_value_rejected` /
   `test_manual_user_handoff_false_rejected`;
   `TestHarnessTextContracts.test_no_surviving_self_dispatch_tokens`.
2. Embedded default-off + mandatory R4/Review-1:
   `validate_parallel_mode` (embedded conditional; r4 flag still required),
   AGENTS Hard-Gates parallel bullet, parallel-mode v0.5 Phase 2/3/4. Tests:
   `TestEmbeddedReviewConditional.test_default_off_requires_no_embedded_entries`,
   dispatch-ready default packet test.
3. Protocol default-on/live-mandatory/cold-legacy via ACTIVE.json:
   `validate_review_artifact_protocol` + `active_stage_id`;
   `_template/status.json`; this stage's status already carries v1. Tests:
   `TestProtocolResolutionAndPhaseTiming.test_missing_protocol_*`,
   `test_unknown_protocol_fails_closed_every_phase`,
   `test_active_stage_id_reads_pointer`,
   `test_malformed_active_pointer_fails_closed`.
4. Phase timing without deadlock: `require_review_1 = pre-accept or
   (pre-review and status==review_2)`; `pre-review+review_1` requires no
   pair. Tests: `test_pre_review_status_review_1_requires_no_pair`,
   `test_pre_review_status_review_2_requires_serial_pair`,
   `test_pre_accept_requires_review_2_pair`,
   `test_pre_accept_with_both_pairs_passes` (R2 fixed).
5. Raw/verdict same object + exact canonical bytes:
   `review_artifacts.load_and_parse_pair` / `canonical_verdict_bytes`.
   Tests: `TestCanonicalPairBinding` (trailing newline, leading whitespace,
   pretty-print, unsorted keys, object mismatch, fenced raw).
6. Stage containment + frozen names + positive `-retry-N`:
   `resolve_stage_local_artifact` / `match_protocol_filename`; raw and
   verdict must select the same attempt. Tests: `TestArtifactNames` (13
   cases incl. absolute/traversal/foreign-stage/subdir/narrative names,
   retry-0 and retry-01 rejected), `test_attempt_mismatch_rejected`,
   `test_retry_pair_selected_by_status_passes`.
7. Identity binding: `_protocol_pair_errors` cross-checks verdict
   `stage_id`, role (`first_reviewer` vs `final_reviewer|reality_checker`),
   model equality, recorded fingerprint, normalized provider isolation.
   Tests: `test_verdict_stage_id_mismatch_rejected`,
   `test_wrong_role_rejected`, `test_model_mismatch_rejected`,
   `test_missing_reviewer_provider_rejected`,
   `test_provider_alias_self_review_rejected` (fable5↔claude alias),
   `test_fingerprint_cache_mismatch_rejected`,
   `test_task_pair_fingerprint_must_match_task`.
8. Embedded rounds need dispatch/patch/raw/round/reason + non-formal
   PASS|BLOCKER: `validate_parallel_mode`. Tests:
   `test_enabled_requires_reason`, `test_enabled_requires_entries_at_pre_review`,
   `test_enabled_complete_round_passes`,
   `test_enabled_round_missing_result_fails`,
   `test_enabled_round_formal_verdict_value_rejected` (ACCEPT rejected as a
   round result), `test_legacy_recorded_entries_without_opt_in_still_validated`.
9. Capture helper boundary: `scripts/review_artifacts.py` — stdlib-only, no
   subprocess import, consumes an existing raw file, requires
   `--producer-exit-status` (non-zero fails, raw retained), schema sanity
   check, refuses overwrite, atomic no-clobber publish. Tests:
   `TestCaptureCLI` (7 cases) + `TestAtomicNoClobber` (3 cases incl.
   collision without damage and failed publish leaving no partial file) +
   `TestHarnessTextContracts.test_capture_helper_never_dispatches`.
10. Workflow Review-1/2 protocol-v1 pairs + JSON-only stdout, footer only in
    legacy branch: `stage-delivery.yaml` review-1/review-2 `writes` +
    `output_contract` protocol/legacy branches, session_receipts rules,
    `artifacts.review_artifact_protocol_v1` block.
11. Fixture corpus + optional `jsonschema` oracle: `schema_corpus()` covers
    every schema-v1 constraint (all required keys, types, enums, consts,
    minLength/minItems, additionalProperties at both levels, finding fields,
    line null/minimum, conditional `fix_start_prompt`);
    `TestJsonschemaOracle.test_parity` compares stdlib vs
    `Draft202012Validator` on the canonical schema file (ran, not skipped).
    All `21-bookkeeper-reconciliation.md` R1–R7 negative cases have direct
    fixtures (mapping above).
12. Manifest distribution: `harness-manifest.yaml` now ships the helper, the
    aggregate validator, and the focused tests. Test:
    `TestHarnessTextContracts.test_manifest_registers_helper_and_tests`.

`00-task.md` acceptance criteria 1–14 are covered by the same mapping
(1→#1, 2→#1, 3→#2, 4→#9, 5→#6, 6→#5/#7, 7→#10 + AGENTS footer exemption,
8→#3, 9→#4, 10→#2/#8, 11→#11, 12→#12, 13→#11 corpus + negative fixtures,
14→ docs/workflow/validator/helper/tests describe the single flow above).

## Test Evidence

Appended to `60-test-output.txt`
(`=== Fable5 clean reimplementation evidence 2026-07-20 07:05:13 CST ===`):

- `python3 scripts/tests/test_review_artifacts.py` — **Ran 86 tests … OK**
  (includes live `jsonschema` parity, all phase-timing, live-vs-cold
  protocol, canonical-byte, containment/name, identity, conditional
  embedded, and atomic collision fixtures).
- `python3 -m py_compile scripts/review_artifacts.py scripts/validate-stage.py
  scripts/validate-all-stages.py` — PASS.
- `python3 scripts/validate-stage.py 2026-07-harness-review-dispatch-fast-fix-v1
  --phase checkpoint` — PASSED; `--phase dispatch-ready` — PASSED (protocol
  v1 present on this stage).
- `python3 scripts/validate-all-stages.py --repo-root .` — 18 green,
  1 green_with_exception, 9 red over 28 stages: identical verdict counts to
  the pre-change committed baseline. Baseline compare shows **zero drift on
  all 27 historical stages**; the single ERRDRIFT is this in-flight stage
  swapping legacy narrative-file errors for protocol-pair errors (9 → 9),
  the intended migration for the protocol-introducing stage.
- `python3 scripts/test-validate-all-stages-compare.py --help` — OK; full
  sentinel run 11/11 passed.
- `git diff --check` — PASS. YAML/JSON parse of edited config files — PASS.
- Residual-token sweep: no `executor: self` / `executor:self` /
  `manual_user_handoff_allowed: false` semantics survive in AGENTS,
  parallel-mode, adapters, workflow, template, or validator; the only
  `manual_user_handoff_allowed` hit is the validator line that rejects it.

## Residual Notes For The Bookkeeper

- The `-retry-N` grammar requires N ≥ 1 without leading zeros.
- Review-2 verdict `role` accepts `final_reviewer` or `reality_checker`
  (both appear in historical evidence and the schema enum); Review-1 requires
  `first_reviewer`.
- The all-stages compare exits 1 solely because of this stage's expected
  ERRDRIFT; record it in the migration judgment when creating the evidence
  commit.
- Next step per the dispatch receipt: Codex bookkeeper reconciliation; no
  reviewer was invoked by this session.

当前 Session ID: 81560638-a8c5-456b-ad9a-68714587b413
Session ID 来源: runtime_env (CLAUDE_CODE_SESSION_ID)
原始输出路径: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/20-implementation-fable5.md
本地北京时间: 2026-07-20 07:05:57 CST
下一步模型: human_operator → Codex bookkeeper
下一步任务: 按 23-implementation-fable5.prompt.md 收尾要求进行 bookkeeper 对账（R4）；不派发 Review-1
