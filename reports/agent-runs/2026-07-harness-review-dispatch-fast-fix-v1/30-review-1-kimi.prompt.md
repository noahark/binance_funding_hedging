<!-- ===== DISPATCH RECEIPT =====
status: evidence_missing
target_model: kimi-code/kimi-for-coding / moonshot_kimi
executor: human_operator
adapter_cmd: kimi --model kimi-code/kimi-for-coding -p "$(cat reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/30-review-1-kimi.prompt.md)"
started_at:
completed_at: unavailable (operator did not provide exact completion time)
session_id: session_c18a8dee-303f-4973-8b0b-61f13d304b9a
session_id_source: operator
producer_exit_status: unavailable (not captured)
raw_output: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/30-review-1.raw-output.md
verdict_output: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/30-review-1.verdict.json
next_dispatch: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/30-review-1-kimi-retry-1.prompt.md (executor: human_operator)
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY (immutable after dispatch) ===== -->

You are the fresh, read-only formal Review-1 reviewer for stage
`2026-07-harness-review-dispatch-fast-fix-v1`. Use the repository
`code_reviewer` skill. Do not edit files, invoke another model, commit, or write
the verdict file yourself. The human operator captures your stdout.

Review exactly this committed range:

- base_sha: `8cf810d2335d5af08e2ff18181964e5e053e56b9`
- head_sha: `73752dbba16beaf41ff6fdfec3b3b84b1944306b`
- diff_fingerprint:
  `73752dbba16beaf41ff6fdfec3b3b84b1944306b:7cf1d8d251a5b628f735455b1c7f03b8977fa790efed6019d583b32719224619`

Implementation author: Fable5 / Anthropic. Your Moonshot provider identity is
independent. You previously performed a plan review in this stage, but did not
design, implement, or fix the reviewed code; disclose that fact in
`reviewer_prior_involvement_notes` while setting
`reviewer_prior_involvement` to `none` because the schema enum covers only
direction synthesis, breakdown, or design participation.

Read raw sources, not only the implementation narrative:

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `docs/parallel-development-mode.md`
- `docs/model-adapters.md`
- `harness-manifest.yaml`
- `reports/agent-runs/_template/status.json`
- `scripts/review_artifacts.py`
- `scripts/validate-stage.py`
- `scripts/validate-all-stages.py`
- `scripts/tests/test_review_artifacts.py`
- stage `00-task.md`, `13-plan-review-synthesis-and-amendment.md`,
  `21-bookkeeper-reconciliation.md`, `20-implementation.md`, and
  `60-test-output.txt`
- actual `git diff --binary 8cf810d..73752db -- .
  ':(exclude)reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/status.json'`

Independently rerun the focused tests, py_compile, checkpoint/dispatch-ready
validators, YAML/JSON parsing, diff fingerprint, and `git diff --check`. Audit
all acceptance criteria, especially:

1. active/new missing protocol versus cold historical legacy behavior;
2. Review-1/Review-2 phase timing without a preflight deadlock;
3. exact canonical raw/verdict binding, path containment, retry grammar,
   fingerprint/stage/model/provider isolation, and RC4 compatibility;
4. capture helper no-dispatch boundary and atomic no-clobber durability;
5. embedded review truly default-off while R4 and committed formal Review-1
   remain mandatory;
6. workflow/template/docs consistency, including whether generic
   `required_files` and fix-node legacy path references contradict the explicit
   protocol-v1 branches;
7. completeness and independence of the 86-test corpus and historical
   all-stage compatibility claims.

Your entire stdout must be exactly one JSON object matching
`schemas/review-verdict.schema.json`: no Markdown fence, heading, narrative, or
footer before or after it. Use:

- `schema_version`: 1
- `stage_id`: `2026-07-harness-review-dispatch-fast-fix-v1`
- `role`: `first_reviewer`
- `model`: `kimi-code/kimi-for-coding`
- the exact `diff_fingerprint` above
- verdict `ACCEPT`, `REWORK`, or `BLOCKED`
- `next_action`: `continue` only for ACCEPT; `fix` for REWORK

If verdict is REWORK, include a complete `fix_start_prompt` preserving exact
findings, paths, allowed boundaries, required tests, raw artifact paths, and
acceptance criteria. Do not soften a finding to fit the implementation report.
