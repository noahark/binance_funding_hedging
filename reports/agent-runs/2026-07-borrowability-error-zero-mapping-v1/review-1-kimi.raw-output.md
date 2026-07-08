# Review-1 Raw Output — Kimi — 2026-07-borrowability-error-zero-mapping-v1

Reviewer: `kimi` / `kimi-code/kimi-for-coding` (`moonshot_kimi`)
Role: `first_reviewer`
Prior involvement: `none`

Review range: `41c6ba542e040cb3d1e82c046d9a9406bd11860d..ea631bf1dbf23662db37f491d92cb3f10685d720`
Diff fingerprint: `ea631bf1dbf23662db37f491d92cb3f10685d720:31efea285e557d074f8f49d30146b07a285e3ecdb1a19d776b170479983251aa` (verified by recomputing `git diff --binary <base>..<head> -- . ':(exclude)reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/status.json' | sha256sum`).

## Artifacts inspected

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/00-task.md`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/10-design.md`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/11-adr.md`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/12-development-breakdown.md`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/20-implementation.md`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/60-test-output.txt`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/status.json`
- `reports/follow-ups/2026-07-borrowability-51061-zero-mapping.md`
- `schemas/review-verdict.schema.json`
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

## Findings

No blocking findings. The implementation matches the frozen design, ADR, and acceptance criteria.

### Acceptance criteria verification

1. **51061 → `max_borrowable="0"` + `error_code="51061"`**: confirmed in `backend/services/private_client.py:267-271` and covered by `test_private_client.py:265-274`. The 400 body has no `borrowLimit`, so `borrow_limit=None`.
2. **Classification boundary = Binance code sign**: positive codes (e.g. 59999) → `None` + `last_error` prefix `max_borrowable_business_error:` (`private_client.py:272-277`, `test_private_client.py:277-283`); negative system/auth codes (-1003/-2014/-2015) and no-code network/5xx → `max_borrowable_failed:` (`private_client.py:278-280`). `test_private_client.py:236-238` (-2015) is unchanged and still asserts `max_borrowable_failed`.
3. **Truncation not probed unchanged**: `assemble_borrow_validation` truncated branch still returns `max_borrowable=None` with `error="borrowability_not_probed"` (`snapshot.py:767-790`).
4. **`verified` semantics unchanged**: verified branch still returns `verified=True` independently of `max_borrowable` (`snapshot.py:792-810`); test `test_private_account_v1.py:1235-1253` asserts `verified=True` with `max_borrowable="0"`.
5. **Frontend badge**: `badgeForNegativeFundingStatus` checks `pa.max_borrowable === '0'` before the green success branch and renders a `warn` badge "可借 0(已借完)" with `error_code` in the title (`frontend/index.html:924-928`).
6. **Frontend net-yield subline**: only shown when `pa.max_borrowable != null`; uses `formatUsdt2(pa.max_borrowable_value_usdt)`; "0" adds a compact "已借完" tag (`frontend/index.html:1165-1171`).
7. **`max_borrowable_value_usdt` conversion**: `_max_borrowable_value_usdt` in `snapshot.py:489-513` uses `Decimal` throughout, stable assets at 1, missing price/null/blank → `None`, zero → `"0.00000000"` via `_quantize_rate`. No `Number()`/`parseFloat()` is introduced in the conversion path; frontend only uses `formatUsdt2`.
8. **Schema/contract additive**: `portfolio_account.required` now includes `error_code` and `max_borrowable_value_usdt` (`snapshot.schema.json:368`); all fixtures and strict key assertions (`test_phase2_borrow_sort.py:230`, `private-account-v1-design.json`) are synchronized. `test_phase2_borrow_sort.py:222` top-level `set(bv)` is unchanged.
9. **`BORROW_ZERO_BUSINESS_CODES` only `{51061}`**: `private_client.py:94`.
10. **Residual R1 comments corrected**: `snapshot_service.py:132` and `:182` now say `{CRYPTO, METAL}`.
11. **Scope/file boundary**: the 11 changed files listed in `20-implementation.md` are all within the frozen allowed list; no private signing/whitelist/order/borrow-repay/transfer/key-management code was touched.
12. **Evidence tests pass**: `60-test-output.txt` records `190 passed` for `python3 -m pytest backend/tests -q`, `node frontend/self-check.js` passes (including "借币三态"), and `git diff --check` is clean.

## Residual risks

- `BORROW_ZERO_BUSINESS_CODES` intentionally contains only the confirmed code `51061`; other positive business codes surface via the distinct `max_borrowable_business_error:` log and are treated as unknown (`null`). This is the agreed design posture (no enumeration without raw samples).
- `max_borrowable_value_usdt` depends on the same `{asset}USDT` price map as balance valuation; missing price → `null` and no ≈USDT subline, which is handled gracefully by the frontend.

本地北京时间: 2026-07-09 07:02:44 CST
下一步模型: bookkeeper（anthropic） / review-2（codex/openai）
下一步任务: ACCEPT verdict — bookkeeper 落档 30-review-1.md 并派发 review-2。

{"schema_version":1,"stage_id":"2026-07-borrowability-error-zero-mapping-v1","role":"first_reviewer","model":"kimi-code/kimi-for-coding","verdict":"ACCEPT","diff_fingerprint":"ea631bf1dbf23662db37f491d92cb3f10685d720:31efea285e557d074f8f49d30146b07a285e3ecdb1a19d776b170479983251aa","reviewer_prior_involvement":"none","reviewed_artifacts":["AGENTS.md","workflows/templates/stage-delivery.yaml","reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/00-task.md","reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/10-design.md","reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/11-adr.md","reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/12-development-breakdown.md","reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/20-implementation.md","reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/60-test-output.txt","reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/status.json","reports/follow-ups/2026-07-borrowability-51061-zero-mapping.md","schemas/review-verdict.schema.json","backend/services/private_client.py","backend/domain/snapshot.py","backend/services/snapshot_service.py","backend/tests/test_private_client.py","backend/tests/test_private_account_v1.py","backend/tests/test_phase2_borrow_sort.py","backend/tests/fixtures/private-account-v1-design.json","schemas/api/public-market/snapshot.schema.json","docs/api/public-market-contract.md","frontend/index.html","frontend/self-check.js"],"findings":[],"required_fixes":[],"residual_risks":["BORROW_ZERO_BUSINESS_CODES intentionally only contains confirmed code 51061; other positive business codes are logged to max_borrowable_business_error: discovery channel and treated as unknown (null) until a raw sample confirms them.","max_borrowable_value_usdt depends on the same {asset}USDT price map as balance valuation; missing price yields null and the frontend hides the ≈USDT segment."],"next_action":"continue"}
