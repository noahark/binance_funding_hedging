# 12-development-breakdown：草稿

> 已按 Kimi/GLM 预实现 review 与用户裁定更新，可作为 serial implementation 输入。

## Owner split

- serial 单 owner 实现。
- review-1 使用 cross-review pool。
- review-2 使用 Codex/GPT，前提是实现作者不是 OpenAI provider。

## Allowed files

- `backend/domain/normalize.py`
- `backend/domain/snapshot.py`（仅必要接线）
- `backend/tests/test_normalize.py`
- `backend/tests/test_snapshot.py`
- `backend/tests/test_private_account_v1.py`
- `backend/tests/fixtures/private-account-v1-design.json`
- `schemas/api/public-market/snapshot.schema.json`
- `docs/api/public-market-contract.md`
- `frontend/index.html`
- `frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json`
- `reports/api-samples/2026-07-ui-filter-balance-metal-v1/`（仅只读采集真实公开金属样本时）

## Forbidden files

- `backend/services/private_client.py`
- 私有签名、API key、下单/借还/划转相关逻辑。
- unrelated reports/canonical docs。

## Implementation tasks

1. Frontend filter:
   - Add checkbox after `filter-show-perp-only`.
   - Add `state.filters.hideLowDailyRate=true`.
   - Add string-safe threshold helper.
   - Update `filteredRows()`, listeners, self-check.
   - Cover `0.00030000`, `-0.00030000`, `0.00030001` in an independent/deep-copy self-check scenario so the default 6-row baseline remains stable.
2. Balance card UI:
   - Replace inline suffix with standalone approximate USDT line.
   - Format only the integer part with thousands separators and preserve fractional strings exactly.
   - Show spot `free` on the main amount line; keep `locked` as a separate `冻结:` line.
   - Preserve hidden mode behavior.
   - Update self-check cases for display, null, zero, hidden.
3. METAL tag:
   - Add `REAL_METAL_BASE_ASSETS`.
   - Pass baseAsset into `asset_tag_for`, keeping the default parameter for backwards-compatible single-arg callers.
   - Update schema enum, docs, frontend select/badge, fixtures, backend tests.
   - Expand `select_borrow_candidates()` so `METAL` and `CRYPTO` negative `MARGIN_SPOT_CANDIDATE` rows enter borrow validation; do not add `DISABLED_METAL`.

## Test commands

```text
python3 -m pytest backend/tests -q
node frontend/self-check.js
```

## Review focus

- Low-rate filter must not use float for threshold logic.
- New filter must compose with `showPerpOnly`.
- Balance privacy masking must not leak amounts.
- Schema/docs/frontend/backend must all know `METAL`.
- `METAL` must not be treated as bStock-style disabled; borrowability and cost must come from existing private read-only interface results.
- `select_borrow_candidates()` must include eligible `METAL` rows while bStock remains excluded.
- bStock behavior must remain unchanged.

本地北京时间: 2026-07-08 09:28:44 CST
下一步模型: codex
下一步任务: 生成实现任务书并进入 serial implementation。
