# Stage Design Review Fix Record

Status: **FABLE5 ACCEPT-with-edits — ALL RECORD PATCHES APPLIED**
Date: 2026-07-11
Source review: `13-stage-design-review-fable5.md`
Reviewed design commit: `c38c5a8e682d79b4cd1e663f3c164278365f777a`

This record documents design-text corrections only. No Harness implementation,
model dispatch, product code, or frozen operator decision changed.

## F1 — Post-Cross-Check Blocking Gate

Disposition: **applied by restoring the explicit second blocking pass**.

Updated `00-task.md`, `10-design.md`, and `11-adr.md` now require:

1. blocking checks before embedded cross-check;
2. embedded cross-check or its skip/unavailable evidence;
3. the identical frozen blocking command set again immediately before seal;
4. blocking inputs limited to frozen code/test/config paths and excluding
   `reports/agent-runs/<stage-id>/` evidence;
5. test coverage proving evidence writes do not alter blocking semantics and a
   second-pass failure blocks seal.

This chooses the frozen 40-table §D main-path reading rather than relying only
on byte-equality equivalence. Seen-diff bind remains mandatory and unchanged.

## F2 — P11 Pilot Metrics

Disposition: **applied**.

The design now requires `docs/auto-review-pipeline.md` to specify a pilot
metrics artifact containing:

- Grok attempts, schema-valid attempts, invalid attempts, and validity rate;
- final schema-valid verdict path/fingerprint;
- escalation paths and shape-validation results;
- expected/valid/missing RECEIPTs and completeness rate;
- budget/rework use and final pilot state.

Both pilots require at least one final schema-valid Grok verdict and 100%
RECEIPT completeness. Every produced escalation must validate, and at least one
pilot must execute a controlled safe escalation drill. The measured Grok rate
is retained for the later operator default-flip decision; this stage does not
invent a promotion threshold.

## N1 — Complexity Evaluator Authority Source

Disposition: **corrected**.

`00-intake.md` and `status.json` now attribute the default Claude-GLM evaluator
to the `stage-delivery.yaml` workflow rotation, not `agents/registry.yaml`.

## N2 — Authorization Expiry

Disposition: **defined and promoted to acceptance/test coverage**.

`expires_at` is required and nullable:

- `null`: no independent authorization-expiry instant;
- ISO8601 value: runner checks it before every model call and commit;
- either form remains bounded by call-count, wall-clock, rework, and operator
  stop controls.

The development breakdown must retain schema and runner tests for both forms.

## Verification Required Before Commit

- status JSON parse
- checkpoint validator
- stage-design `git diff --check`
- D1–D12/P1–P13 traceability
- negative product-path and locked-vocabulary scans
- explicit scans for post-cross-check blocking, P11 metrics, workflow rotation,
  and nullable `expires_at`

本地北京时间: 2026-07-11 12:26:36 CST
下一步模型: Claude Fable 5（development breakdown author）
下一步任务: 依据已修补的 00-task/10-design/11-adr 起草 12-development-breakdown.md；不得实施或执行模型 dispatch。
