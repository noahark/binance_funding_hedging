# Review-1: Harness Hardening Follow-ups

## Reviewer Identity

- Implementer: `claude_glm` / `glm-5.2`, provider identity `zhipu_glm`.
- Reviewer: `kimi` / `kimi-code/kimi-for-coding`, provider identity `moonshot_kimi`.
- Provider isolation: satisfied; reviewer provider differs from implementer provider.
- `reviewer_prior_involvement`: `none`.

## Reviewed Range

- `base_sha`: `ddcf0e11a2ece33bdb9863512504fcc404867e4f`
- `head_sha`: `6eb87a0fdb8ee550115013a1faccd678ed51282d`
- `diff_fingerprint`: `6eb87a0fdb8ee550115013a1faccd678ed51282d:3ce700761aad68d0084a22ff742edf1ee0e2194716625bfa563a8927eb821638`
- Verified fingerprint locally: matched byte-for-byte.

## Reviewed Artifacts

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `docs/model-adapters.md`
- `reports/agent-runs/README.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/00-task.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/10-design.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/11-adr.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/20-implementation.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/21-bookkeeper-inspection.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/60-test-output.txt`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/61-validate-pre-review.txt`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/62-validate-pre-review-final.txt`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/status.json`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/70-handoff.md`
- `reports/agent-runs/_template/status.json`
- `schemas/review-verdict.schema.json`
- `git diff --binary ddcf0e11a2ece33bdb9863512504fcc404867e4f..6eb87a0fdb8ee550115013a1faccd678ed51282d -- . :(exclude)reports/agent-runs/2026-07-harness-hardening-followups-v1/status.json`

## Findings

No P0/P1/P2 findings. All five acceptance criteria are implemented and covered by tests.

### AC1 — `--evidence-out` write failure handling

- Location: `scripts/validate-stage.py` near line 969.
- Change: `evidence_path.parent.mkdir(...)` and `evidence_path.write_text(output)` are wrapped in `try/except OSError`.
- On failure the script prints `EVIDENCE WRITE FAILED: could not write <path>: <OSError>` to `stderr` and returns non-zero, without a Python traceback.
- Test coverage: `scripts/tests/test_validate_stage.py::test_evidence_out_write_failure_clean_error` passes.

### AC2 — `record-checkpoint --dry-run` requires `--single-owner`

- Location: `scripts/record-checkpoint` near line 168.
- Change: early guard raises `ItbmError` when `args.dry_run and not args.single_owner`, before any double-owner git mutation.
- Error message clearly says `--dry-run is single-owner only` and explains how to fix the invocation.
- Test coverage: `scripts/tests/itbm_dry_run.py::test_dry_run_requires_single_owner` passes, and asserts no repository mutation occurs.

### AC3 — `compute_diff_fingerprint` pins `diff.renames=true`

- Location: `scripts/validate-stage.py` in `compute_diff_fingerprint`.
- Change: `git -c diff.renames=true diff --binary ...` is now used, matching `scripts/_itbm.py::canonical_fingerprint`.
- Test coverage: `scripts/tests/test_validate_stage.py::test_fingerprint_pins_renames_true` passes under a hostile `diff.renames=false` repo config.

### AC4 — `review_1.actual_model` support

- Location: `reports/agent-runs/_template/status.json`.
- Change: both top-level `review_1` and `tasks[].review_1` blocks now include `"actual_model": null`, mirroring `review_2.actual_model`.
- Workflow guidance: `workflows/templates/stage-delivery.yaml` review-1 preflight now instructs recording the actual executed model in `status.json.review_1.actual_model` when it differs from the anticipated model.
- Test coverage: `scripts/tests/test_validate_stage.py::test_template_review_1_actual_model` passes.

### AC5 — Fix return gate encoded in workflow

- Location: `workflows/templates/stage-delivery.yaml` under the `fix` stage.
- Change:
  ```yaml
  return_gate:
    rule: "a fix must not skip the originating review gate"
    after_fix_from_review_1: review-1
    after_fix_from_review_2: review-2
  ```
- This supplements the existing F8 policy text with machine-readable transition fields.
- Test coverage: `scripts/tests/test_validate_stage.py::test_workflow_fix_return_gate` passes.

## Scope Check

All changed files fall within the allowed file list from `00-task.md`:

- `scripts/validate-stage.py`
- `scripts/record-checkpoint`
- `scripts/tests/itbm_dry_run.py`
- `scripts/tests/test_validate_stage.py`
- `reports/agent-runs/_template/status.json`
- `workflows/templates/stage-delivery.yaml`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/*` (stage evidence)

No forbidden paths were modified: no `backend/**`, `frontend/**`, `docs/product/**`, `docs/architecture/**`, `reports/api-samples/**`, `AGENTS.md`, `agents/registry.yaml`, `schemas/**`, or old stage artifacts.

## Test Verification Run by Reviewer

```bash
python3 scripts/tests/itbm_dry_run.py              # 19/19 assertions passed
python3 -m py_compile scripts/validate-stage.py scripts/_itbm.py scripts/record-checkpoint  # OK
python3 scripts/tests/test_validate_stage.py       # 19/19 assertions passed
python3 scripts/validate-stage.py 2026-07-harness-hardening-followups-v1 --phase pre-review --evidence-out /tmp/review1-pre-review-evidence.txt  # PASSED
python3 scripts/validate-stage.py 2026-07-harness-hardening-followups-v1 --phase checkpoint  # PASSED
git diff --check                                    # clean
```

All commands exited successfully.

## Residual Risks

- AC5 is workflow-level guidance; `validate-stage.py` does not yet enforce `return_gate` at runtime. This is consistent with the design intent ("machine-readable enough for future validators or dispatch logic") and does not regress existing behavior.
- AC4 only updates the template; pre-existing stage `status.json` files are intentionally left to their respective bookkeepers.

## Verdict

`ACCEPT`. The stage is ready for review-2.

本地北京时间: 2026-07-09 21:50:46 CST
下一步模型: review-2 (codex primary, claude fallback if needed)
下一步任务: prepare and dispatch review-2 prompt for the accepted range

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-harness-hardening-followups-v1",
  "role": "first_reviewer",
  "model": "kimi-code/kimi-for-coding",
  "verdict": "ACCEPT",
  "diff_fingerprint": "6eb87a0fdb8ee550115013a1faccd678ed51282d:3ce700761aad68d0084a22ff742edf1ee0e2194716625bfa563a8927eb821638",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml",
    "docs/model-adapters.md",
    "reports/agent-runs/README.md",
    "reports/agent-runs/2026-07-harness-hardening-followups-v1/00-task.md",
    "reports/agent-runs/2026-07-harness-hardening-followups-v1/10-design.md",
    "reports/agent-runs/2026-07-harness-hardening-followups-v1/11-adr.md",
    "reports/agent-runs/2026-07-harness-hardening-followups-v1/20-implementation.md",
    "reports/agent-runs/2026-07-harness-hardening-followups-v1/21-bookkeeper-inspection.md",
    "reports/agent-runs/2026-07-harness-hardening-followups-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-harness-hardening-followups-v1/61-validate-pre-review.txt",
    "reports/agent-runs/2026-07-harness-hardening-followups-v1/62-validate-pre-review-final.txt",
    "reports/agent-runs/2026-07-harness-hardening-followups-v1/status.json",
    "reports/agent-runs/_template/status.json",
    "schemas/review-verdict.schema.json",
    "git diff --binary ddcf0e11a2ece33bdb9863512504fcc404867e4f..6eb87a0fdb8ee550115013a1faccd678ed51282d -- . :(exclude)reports/agent-runs/2026-07-harness-hardening-followups-v1/status.json"
  ],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [
    "AC5 return_gate is machine-readable workflow guidance but not yet runtime-enforced by validate-stage.py; this matches the stage design intent.",
    "AC4 only updates the status.json template; legacy stage status.json files are not backfilled."
  ],
  "next_action": "continue"
}
```
