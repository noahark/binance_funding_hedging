# Stage Task

## Goal

Eliminate the normal-success funding-history publication gap by making only the
history component refresh-due 300 seconds before its existing publication
expiry. With the default 1800-second history cache TTL, refresh work begins at
1500 seconds while cached history remains publishable until 1800 seconds.

## Required Behavior

1. `_history_is_fresh()` treats a history entry as refresh-fresh only until the
   effective refresh threshold `max(0, publication_ttl - 300)`.
2. `_fetch_history_for()` uses the same refresh threshold for its cache reuse
   guard, so a cursor-selected entry aged 1500 seconds performs real public
   history I/O instead of returning the old cache entry.
3. `_all_valid_history()` continues to publish successful cached history until
   the configured `funding_history_cache_ttl_seconds` (default 1800 seconds).
4. Failed early refreshes do not overwrite the cache; the prior entry remains
   publishable until the existing hard expiry and is retried on later cursor
   visits under existing failure behavior.
5. At most 10 symbols are examined per scheduled tick, unchanged.

## Frozen Non-Goals

- Do not change `Config.funding_history_cache_ttl_seconds` or its environment
  override/default tests.
- Do not change borrow-rate or max-borrowable due thresholds.
- Do not change Group B cadence or private transport TTLs.
- Do not change coverage ledger or the `-0.00030000` exit/re-entry behavior.
- Do not fix the inherited pre-fetch timestamp P3.
- Do not change frontend files, API/schema contracts, manual refresh semantics,
  candidate selection, cursor size, or trading behavior.

## File Boundary

Implementation may edit only:

- `backend/services/snapshot_service.py`
- `backend/tests/test_background_worker.py`
- `reports/agent-runs/2026-07-history-refresh-ahead-v1/20-implementation.md`

All other product, test, canonical-doc, Harness, status, handoff, review, and
evidence files are forbidden to the implementer.

## Acceptance Criteria

- At age 1499 seconds, selected cached history is reused without upstream I/O.
- At age 1500 seconds, a cursor-selected history entry performs real upstream
  history I/O and refreshes its cache on success.
- History remains present in the publication overlay from 1500 through 1799
  seconds while an early refresh is pending or fails.
- A successful early refresh prevents a normal-path empty history window when
  the original entry crosses 1800 seconds.
- At age 1500, eligible borrow-rate and max-borrowable entries remain fresh and
  produce no additional private calls.
- Existing HOME threshold re-entry test remains unchanged and passing.
- Focused background-worker tests and the full backend test suite pass.

本地北京时间: 2026-07-15 10:44:33 CST
下一步模型: claude_glm
下一步任务: 在三文件边界内实现历史 1500 refresh-due / 1800 publish-expiry
