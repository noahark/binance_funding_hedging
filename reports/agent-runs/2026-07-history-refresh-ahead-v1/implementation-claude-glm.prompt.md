# Claude-GLM Implementation Dispatch

You are the implementation author for LOW stage
`2026-07-history-refresh-ahead-v1` on branch
`stage/2026-07-history-refresh-ahead-v1`.

Read completely before editing:

- `AGENTS.md`
- `agents/developer-discipline.md`
- `reports/agent-runs/2026-07-history-refresh-ahead-v1/00-task.md`
- `reports/agent-runs/2026-07-history-refresh-ahead-v1/10-design.md`
- `reports/agent-runs/2026-07-history-refresh-ahead-v1/11-adr.md`
- `reports/agent-runs/2026-07-history-refresh-ahead-v1/status.json`
- relevant code/tests in the allowed boundary below

## Required Change

Implement only the history refresh-ahead contract:

- default history refresh-due age is 1500 seconds;
- history publication expiry remains the configured 1800-second default;
- derive refresh-due as `max(0, funding_history_cache_ttl_seconds - 300)` so
  environment overrides preserve the separation;
- use that refresh threshold in `_history_is_fresh()` and the cache-reuse guard
  in `_fetch_history_for()`;
- keep `_all_valid_history()` on the full configured publication TTL;
- do not change the inherited pre-fetch success timestamp behavior.

## Allowed Writes

- `backend/services/snapshot_service.py`
- `backend/tests/test_background_worker.py`
- `reports/agent-runs/2026-07-history-refresh-ahead-v1/20-implementation.md`

Everything else is forbidden, including `backend/config.py`, private client,
frontend, schemas, canonical docs, Harness files, status/handoff/review/test
evidence files, and git commits.

## Required Deterministic Evidence

Tests must prove:

1. 1499 seconds reuses cached history without a public history call.
2. 1500 seconds on cursor selection performs a real public history call.
3. `_all_valid_history()` continues publishing the old successful entry through
   1799 seconds even if early refresh is pending or fails.
4. Successful early refresh keeps history present after the original entry
   crosses 1800 seconds.
5. Borrow-rate and max-borrowable do not become due at 1500 seconds; private call
   counts do not increase.
6. The existing coverage re-entry test remains unchanged and passes.

Run exactly:

```text
python3 -m pytest backend/tests/test_background_worker.py -q
python3 -m pytest backend/tests -q
python3 -m py_compile backend/services/snapshot_service.py backend/tests/test_background_worker.py
git diff --check
git status --short
```

Update `20-implementation.md` with assumptions, exact changed files, test output,
and explicit confirmation that no forbidden behavior changed. Do not commit.

End your report with:

```text
本地北京时间: <from local date command> CST
下一步模型: codex_bookkeeper
下一步任务: 核验最小 diff、测试结果和文件边界
```
