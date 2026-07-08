# Review-1 Prompt — Kimi — 2026-07-ui-filter-balance-metal-v1

You are the fresh review-1 reviewer for this Harness stage.

Reviewer identity:

- provider: `kimi`
- model: `kimi-code/kimi-for-coding`
- provider_identity: `moonshot_kimi`
- role: `first_reviewer`
- reviewer_prior_involvement: `none`

Implementer identity:

- provider: `claude_glm`
- provider_identity: `zhipu_glm`
- implementation report: `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/20-implementation.md`

Hard rules:

- Read-only review. Do not modify files, do not run formatters, do not create commits, do not call external APIs, and do not use private credentials.
- Review raw artifacts and the actual committed diff. Do not rely only on bookkeeper summaries.
- Use the exact committed range and fingerprint below. Do not review a moving `HEAD` range.
- Findings should be concrete bugs, contract drift, missing evidence, unsafe behavior, or meaningful test gaps.
- If verdict is `REWORK`, include a complete `fix_start_prompt` in the final JSON.
- Your final output must end with one strict JSON object matching `schemas/review-verdict.schema.json`. Do not wrap the JSON in a code fence.

Committed review range:

```text
base_sha=3d3c66e64446d1285a96b4a0e0843e912e4c540e
head_sha=2e966904a6adb576adee8f979738ef664f80058c
diff_fingerprint=2e966904a6adb576adee8f979738ef664f80058c:83956ebe014a34fc8ee85cfb04bb701fac76e488e106fac746a1a542762222a1
```

Use this diff command:

```text
git diff --binary 3d3c66e64446d1285a96b4a0e0843e912e4c540e..2e966904a6adb576adee8f979738ef664f80058c -- . ':(exclude)reports/agent-runs/2026-07-ui-filter-balance-metal-v1/status.json'
```

Required artifacts to inspect:

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/00-task.md`
- `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/10-design.md`
- `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/11-adr.md`
- `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/12-development-breakdown.md`
- `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/15-requirements-review.md`
- `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/16-design-review.md`
- `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/20-implementation.md`
- `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/60-test-output.txt`
- `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/status.json`
- `reports/api-samples/2026-07-ui-filter-balance-metal-v1/20260708T0928Z/normalized/metal-symbol-summary.json`
- `schemas/review-verdict.schema.json`

Relevant product files:

- `backend/domain/normalize.py`
- `backend/domain/snapshot.py`
- `backend/tests/test_normalize.py`
- `backend/tests/test_snapshot.py`
- `schemas/api/public-market/snapshot.schema.json`
- `docs/api/public-market-contract.md`
- `frontend/index.html`
- `frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json`

Acceptance criteria to verify:

1. Default UI hides rows with parseable `abs(daily_funding_rate) <= 0.00030000`; null/invalid rates are not hidden by this filter.
2. Low-rate threshold comparison does not use float/Number/parseFloat in the threshold logic.
3. The new checkbox is after `显示 PERP_ONLY_EXCLUDED`, defaults checked, composes with existing filters, and can restore hidden rows.
4. Balance cards render separate asset, amount, and approximate USDT lines; privacy mode masks both amount and estimated value.
5. Quantity display adds thousands separators only to the integer part and preserves the fractional string.
6. `value_usdt == null` shows `≈ — USDT`; zero value shows `≈ 0.00 USDT`.
7. `asset_tag="METAL"` covers `XAU/XAG/COPPER/XPT/XPD` by `base_asset`, with `asset_tag_source="base_asset_metal_symbol"`, and has priority over `TRADIFI_PERPETUAL -> BSTOCK`.
8. Schema, docs, backend, frontend filter/badge, fixture, and tests are synchronized for `METAL`.
9. No `DISABLED_METAL` exists. `METAL` is not a structural borrow prohibition.
10. Eligible `METAL` + negative funding + `MARGIN_SPOT_CANDIDATE` rows enter existing private read-only borrow validation candidate selection; bStock remains excluded.
11. No private signing, order, borrow, repay, transfer, or key-management behavior changed.
12. Evidence tests pass:
    - `python3 -m pytest backend/tests -q` => `173 passed`
    - `node frontend/self-check.js` => `全部自检通过`
    - `git diff --check` => PASS

Review output guidance:

- Lead with findings if any. Include file and line when possible.
- If there are no blocking findings, say so briefly and return `ACCEPT`.
- If you return `REWORK`, your JSON must include `fix_start_prompt` with:
  - stage id and diff fingerprint under review;
  - this raw review output path: `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/review-1-kimi.raw-output.md`;
  - ordered findings with severity, file/line evidence, impact, and recommendation;
  - required fixes;
  - allowed fix files and forbidden paths;
  - exact tests to run: `python3 -m pytest backend/tests -q`, `node frontend/self-check.js`, `python3 scripts/validate-stage.py 2026-07-ui-filter-balance-metal-v1 --phase pre-review`;
  - expected `40-fix-report.md` mapping from findings to fixes.

Final JSON requirements:

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-ui-filter-balance-metal-v1",
  "role": "first_reviewer",
  "model": "kimi-code/kimi-for-coding",
  "verdict": "ACCEPT|REWORK|BLOCKED",
  "diff_fingerprint": "2e966904a6adb576adee8f979738ef664f80058c:83956ebe014a34fc8ee85cfb04bb701fac76e488e106fac746a1a542762222a1",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": ["..."],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [],
  "next_action": "continue|fix|human_escalation_required"
}
```

本地北京时间: 2026-07-08 10:56:41 CST
下一步模型: kimi
下一步任务: review-1 read-only inspection and schema-valid verdict JSON.
