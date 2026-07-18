# Claude-GLM Implementation Dispatch — Task B1 Minimum-Borrow Contract

You are the implementation author for backend Task B1. Work in `/Users/ark/Desktop/ai code/funding_hedging` on branch `stage/2026-07-borrow-task-ui-fake-v1`.

Before editing, read these raw artifacts and inspect the named source/test anchors yourself:

- `AGENTS.md`
- `agents/developer-discipline.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/00-task.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/10-design.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/11-adr.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/12-development-breakdown.md` (§2 is authoritative task detail)
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/14-user-min-borrow-contract-amendment.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/status.json`

You may change only:

- `backend/services/private_client.py`
- `backend/domain/snapshot.py`
- `backend/tests/test_private_client.py`
- `backend/tests/test_private_account_v1.py`
- `backend/tests/test_phase2_borrow_sort.py` only if its exact-field assertions require this contract update
- `backend/tests/fixtures/private-account-v1-design.json`
- `schemas/api/public-market/snapshot.schema.json`
- `reports/api-samples/2026-07-borrow-task-ui-fake-v1/sapi-v1-margin-allAssets.json`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/21-implementation-backend.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/61-test-output-backend.txt`

Do not modify frontend files, `status.json`, `70-handoff.md`, any canonical documentation, workflow/agent files, or files outside that list. Do not commit.

Implement exactly this additive contract:

```text
allAssets[i].userMinBorrow (string, key assetName)
  → classic_ref.user_min_borrow_by_name[assetName]
  → rows[].borrow_validation.classic_margin.user_min_borrow
  → rows[].borrow_validation.classic_margin.user_min_borrow_value_usdt
```

Requirements:

1. In `fetch_classic_reference`, preserve `userMinBorrow` as the raw decimal string in a map keyed by `assetName`; a missing field/key produces `null` at assembly.
2. In every `assemble_borrow_validation` branch, gate both new classic-margin fields exactly as `asset_borrowable`: classic reference absent or pair not listed means both null; the borrowability-truncated branch preserves them when classic reference/pair evidence exists.
3. Preserve `user_min_borrow` verbatim. Calculate `user_min_borrow_value_usdt` only for a valid Decimal raw amount, with the same USDT/USDC stablecoin-at-one and `<ASSET>USDT` price lookup rules used by the existing maximum-borrow valuation. A missing or invalid price/amount gives null and emits no new warning.
4. The new value is a decimal string quantized with `Decimal` and `ROUND_HALF_UP` to exactly two digits after the decimal point (`"0" → "0.00"`; include a half-up case such as `1.005 → "1.01"`). Do not change, reuse as output, or reduce the existing eight-decimal `portfolio_account.max_borrowable_value_usdt` contract.
5. Update `classic_margin` schema required properties and design fixture for both fields (`decimal_string | null`). Copy `reports/api-samples/2026-07-private-account-v1/20260705T232800Z/sapi-v1-margin-allAssets.json` byte-for-byte to the permitted current-stage sample path. Do not alter it or invent a nonzero raw sample.
6. Add focused test coverage for map construction/raw preservation, all null/pair gates, truncated behavior, stable/nonstable pricing, missing/invalid input, raw zero, exact two-decimal + half-up behavior, strict schema failures, and unchanged eight-decimal maximum-borrow behavior. Synthetic nonzero inputs belong only in tests.

Run exactly:

```bash
python3 -m pytest backend/tests -q
git diff --check
shasum -a 256 reports/api-samples/2026-07-private-account-v1/20260705T232800Z/sapi-v1-margin-allAssets.json reports/api-samples/2026-07-borrow-task-ui-fake-v1/sapi-v1-margin-allAssets.json
```

Put complete command output in `61-test-output-backend.txt`. Write `21-implementation-backend.md` with changed files, decisions, test results, both SHA-256 values and explicit equality statement, deviations/blockers if any, and the mandatory footer. Leave the worktree intact for the bookkeeper's evidence commit and later Kimi dependency handoff.

当前 Session ID: unavailable (to be recorded by Claude-GLM/operator after execution)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/28-claude-glm-backend-b1.dispatch.md
本地北京时间: 2026-07-18 22:13:37 CST
下一步模型: Claude-GLM
下一步任务: 实现 Task B1、运行后端测试并留下原始报告与日志
