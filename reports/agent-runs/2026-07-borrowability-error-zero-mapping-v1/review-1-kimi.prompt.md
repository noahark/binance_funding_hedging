# Review-1 Prompt — Kimi — 2026-07-borrowability-error-zero-mapping-v1

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
- implementation report: `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/20-implementation.md`

Hard rules:

- Read-only review. Do not modify files, do not run formatters, do not create commits, do not call external APIs, and do not use private credentials.
- Review raw artifacts and the actual committed diff. Do not rely only on bookkeeper summaries.
- Use the exact committed range and fingerprint below. Do not review a moving `HEAD` range.
- Findings should be concrete bugs, contract drift, missing evidence, unsafe behavior, or meaningful test gaps.
- If verdict is `REWORK`, include a complete `fix_start_prompt` in the final JSON.
- Your final output must end with one strict JSON object matching `schemas/review-verdict.schema.json`. Do not wrap the JSON in a code fence.

Committed review range:

```text
base_sha=41c6ba542e040cb3d1e82c046d9a9406bd11860d
head_sha=ea631bf1dbf23662db37f491d92cb3f10685d720
diff_fingerprint=ea631bf1dbf23662db37f491d92cb3f10685d720:31efea285e557d074f8f49d30146b07a285e3ecdb1a19d776b170479983251aa
```

Use this diff command:

```text
git diff --binary 41c6ba542e040cb3d1e82c046d9a9406bd11860d..ea631bf1dbf23662db37f491d92cb3f10685d720 -- . ':(exclude)reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/status.json'
```

Required artifacts to inspect:

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/00-task.md`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/10-design.md`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/11-adr.md`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/12-development-breakdown.md`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/20-implementation.md`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/60-test-output.txt`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/status.json`（含 `scope_amendments` SCOPE-001/002）
- `reports/follow-ups/2026-07-borrowability-51061-zero-mapping.md`（根因 + 实盘 SPELLUSDT 证据）
- `schemas/review-verdict.schema.json`

Relevant product files:

- `backend/services/private_client.py`
- `backend/domain/snapshot.py`
- `backend/services/snapshot_service.py`
- `backend/tests/test_private_client.py`
- `backend/tests/test_private_account_v1.py`
- `backend/tests/test_phase2_borrow_sort.py`
- `backend/tests/fixtures/private-account-v1-design.json`
- `schemas/api/public-market/snapshot.schema.json`
- `docs/api/public-market-contract.md`
- `frontend/index.html`
- `frontend/self-check.js`

Acceptance criteria to verify:

1. 51061 类业务错误 → `portfolio_account.max_borrowable="0"` + `error_code="51061"`；`borrow_limit=null`（400 body 无 borrowLimit）。
2. **分类分界 = Binance code 的正负号**：正数业务码（非零集，如 59999）→ `None` + `last_error` 前缀 `max_borrowable_business_error:`（distinct discovery log）；**负数系统/鉴权码 -1003/-2014/-2015 与无 code 网络/5xx → `max_borrowable_failed:`**。核对 `test_private_client.py:238`（-2015）**未被改动**且仍断言 `max_borrowable_failed`。
3. 截断未探测 → `max_borrowable=null` + `borrow_validation.error="borrowability_not_probed"`（保持不变）。
4. `verified` 语义**未变**（仍不看 max_borrowable）；SPELLUSDT 类借光行仍可 `verified=true`，但 badge 不再是绿色「已验证可借」。
5. 前端 badge：`verified=true` 且 `max_borrowable="0"` → 非 success 的 `warn`「可借 0(已借完)」（title 含 error_code）；其余分支不变。
6. 前端 net-yield 列：`max_borrowable != null` 时展示「可借: <值> (≈ … USDT)」子行，`"0"` 带「已借完」；`null` 不展示子行。
7. `max_borrowable_value_usdt` 后端折算：8dp 串，口径与 balance `value_usdt` 完全一致（`_quantize_rate`；stable 按 1；缺价/null → null；"0"→"0.00000000"）；**全程无 float**（无 `Number()`/`parseFloat()` 进入折算/金额比较；前端仅 `formatUsdt2`）。
8. schema/contract additive：`portfolio_account` +`error_code` +`max_borrowable_value_usdt`（均加入 `required`）；所有含 portfolio_account 的 fixture/断言形状同步（含 `test_phase2_borrow_sort.py:230` 五字段、`:222` 未动）。
9. `BORROW_ZERO_BUSINESS_CODES` 仅含 `51061`，不臆测枚举；权限类/第四态为 out-of-scope。
10. residual R1：`snapshot_service.py:132/:182` 注释补正 `{CRYPTO, METAL}`（仅注释）。
11. 未改私有签名/白名单/下单/借还划转/密钥管理；11 个改动文件全部在冻结允许列表内（含 SCOPE-001/002 追加的两测试文件）。
12. Evidence tests pass：
    - `python3 -m pytest backend/tests -q` => `190 passed`
    - `node frontend/self-check.js` => `全部自检通过`（含「借币三态」）
    - `git diff --check` => PASS

Review output guidance:

- Lead with findings if any. Include file and line when possible.
- If there are no blocking findings, say so briefly and return `ACCEPT`.
- If you return `REWORK`, your JSON must include `fix_start_prompt` with:
  - stage id and diff fingerprint under review;
  - this raw review output path: `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/review-1-kimi.raw-output.md`;
  - ordered findings with severity, file/line evidence, impact, and recommendation;
  - required fixes; allowed fix files and forbidden paths;
  - exact tests to run: `python3 -m pytest backend/tests -q`, `node frontend/self-check.js`, `python3 scripts/validate-stage.py 2026-07-borrowability-error-zero-mapping-v1 --phase pre-review`;
  - expected `40-fix-report.md` mapping from findings to fixes.

Final JSON requirements:

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-borrowability-error-zero-mapping-v1",
  "role": "first_reviewer",
  "model": "kimi-code/kimi-for-coding",
  "verdict": "ACCEPT|REWORK|BLOCKED",
  "diff_fingerprint": "ea631bf1dbf23662db37f491d92cb3f10685d720:31efea285e557d074f8f49d30146b07a285e3ecdb1a19d776b170479983251aa",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": ["..."],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [],
  "next_action": "continue|fix|human_escalation_required"
}
```

本地北京时间: 2026-07-09 06:54:10 CST
下一步模型: kimi
下一步任务: review-1 read-only inspection and schema-valid verdict JSON.
