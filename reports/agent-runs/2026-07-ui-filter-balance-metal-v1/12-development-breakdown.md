# 12-development-breakdown：草稿

> 仅在用户确认 `00-task.md` 与 `10-design.md` 后生效。

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
- `schemas/api/public-market/snapshot.schema.json`
- `docs/api/public-market-contract.md`
- `frontend/index.html`
- `frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json`

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
2. Balance card UI:
   - Replace inline suffix with standalone approximate USDT line.
   - Preserve hidden mode behavior.
   - Update self-check cases for display, null, zero, hidden.
3. METAL tag:
   - Add `REAL_METAL_BASE_ASSETS`.
   - Pass baseAsset into `asset_tag_for`.
   - Update schema enum, docs, frontend select/badge, fixtures, backend tests.

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
- bStock behavior must remain unchanged.

本地北京时间: 2026-07-08 02:23:15 CST
下一步模型: human
下一步任务: 确认后生成实现任务书。
