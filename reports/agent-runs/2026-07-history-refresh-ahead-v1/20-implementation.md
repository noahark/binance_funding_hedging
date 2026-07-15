# Implementation Report

## State

**Implemented — full suite green (335 passed).** The history refresh-ahead
contract is implemented within the frozen three-file boundary. Ready for
bookkeeper inspection.

## Implementer

- Model: `glm-5.2`
- Provider identity: `zhipu_glm`
- Skill: `senior_developer`
- Adapter: `claude_glm`

## Assumptions

1. The refresh-ahead headroom is a fixed `300` seconds (module constant), not a
   new environment variable — `10-design.md` permits "a small module constant or
   a small private helper" and forbids a new env var or scheduler abstraction.
2. `funding_history_cache_ttl_seconds` (default 1800) remains the single source
   of truth for both thresholds; the refresh threshold is derived from it as
   `max(0, ttl - 300)`, so any environment override preserves the 300s
   separation automatically.
3. The inherited pre-fetch success-timestamp behavior (the P3 from the prior
   stage) is left untouched per the frozen non-goals; refresh writes still stamp
   `time.monotonic()` at the existing point in `_fetch_history_for`.

## Changed Files (exact, within the frozen three-file boundary)

### 1. `backend/services/snapshot_service.py`

- Added module constant `HISTORY_REFRESH_AHEAD_SECONDS = 300` next to the
  existing schema-version constants.
- Added private helper `_history_refresh_ttl(self) -> int` returning
  `max(0, self.config.funding_history_cache_ttl_seconds - HISTORY_REFRESH_AHEAD_SECONDS)`.
- `_history_is_fresh()` now compares `now - cached[0]` against
  `self._history_refresh_ttl()` (refresh-fresh at 1500s) instead of the full TTL.
- `_fetch_history_for()` cache-reuse guard now uses `ttl = self._history_refresh_ttl()`
  so a cursor visit at 1500s performs real upstream I/O instead of returning the
  old cache entry. The cache write on success is unchanged.

### 2. `backend/tests/test_background_worker.py`

- Five new deterministic boundary tests under a new
  "History refresh-ahead" section, using monkeypatched `time.monotonic`.

### 3. `reports/agent-runs/2026-07-history-refresh-ahead-v1/20-implementation.md`

- This report.

## Behavior

```text
history_refresh_due_age  = max(0, funding_history_cache_ttl_seconds - 300)   # 1500 default
history_publish_expiry   = funding_history_cache_ttl_seconds                # 1800 default
```

- `_history_is_fresh()` and the `_fetch_history_for()` reuse guard use the
  refresh threshold (1500).
- `_all_valid_history()` still publishes on the full publication TTL (1800).
- `_sweep_group_c` `component_ttl` still drives borrow-rate / max-borrowable on
  the full TTL (1800).

## What Was NOT Changed (forbidden-behavior confirmation)

- `Config.funding_history_cache_ttl_seconds` and its env-override/default tests:
  untouched.
- Borrow-rate and max-borrowable due thresholds (`component_ttl` in
  `_sweep_group_c`, `_borrow_rate_due`, `_max_borrowable_due`): untouched; they
  keep the 1800s cadence.
- Group B cadence and private transport TTLs: untouched.
- Coverage ledger and the `-0.00030000` exit/re-entry behavior: untouched; the
  existing `test_coverage_reentry_starts_unattempted` runs unchanged.
- Inherited pre-fetch success timestamp (P3): not repaired here.
- Frontend, API/schema contracts, manual refresh semantics, candidate selection,
  cursor size (≤10/tick), and trading behavior: untouched.
- No new environment variable and no generalized scheduler abstraction.

## Deterministic Evidence

The five new tests prove each required behavior (00-task acceptance criteria /
prompt evidence list):

1. `test_history_1499_reuses_cache_without_public_call` — at 1499s a cursor
   visit reuses the cached entry; `history_calls` does not increase.
2. `test_history_1500_performs_real_public_call` — at 1500s a cursor-selected
   entry performs a real public history call (`history_calls + 1`) and the cache
   is re-stamped to 1500.
3. `test_all_valid_history_publishes_old_entry_through_1799` — `_all_valid_history()`
   keeps publishing the old successful entry at 1500 and 1799 (even though an
   early refresh is due / would fail, since failure is not cached) and drops it
   at 1800.
4. `test_successful_early_refresh_keeps_history_present_after_1800` — a
   successful early refresh at 1500 keeps history present at 1801 (no
   normal-success empty window).
5. `test_borrow_components_not_due_at_1500` — at 1500s history is due
   (`history_calls + 1`) but borrow-rate (`next_hourly_calls`) and max-borrowable
   (`max_borrowable_calls`) counts are unchanged.
6. The existing coverage re-entry test (`test_coverage_reentry_starts_unattempted`)
   is unchanged and passes.

## Test Commands & Results

```text
python3 -m pytest backend/tests/test_background_worker.py -q
# => 37 passed in 1.90s   (32 existing + 5 new)

python3 -m pytest backend/tests -q
# => 335 passed in 13.83s

python3 -m py_compile backend/services/snapshot_service.py backend/tests/test_background_worker.py
# => PYCOMPILE OK

git diff --check
# => clean (no whitespace errors)
```

## Write-Boundary Confirmation

Edited only the three frozen files (`backend/services/snapshot_service.py`,
`backend/tests/test_background_worker.py`, this report). `git status --short`
shows exactly those two source/report files and nothing else. **No** edit to
`backend/config.py`, private client, frontend, schemas, canonical docs, Harness
files, status/handoff/review/test-evidence files. **No** new file created.
**No** commit / merge / rebase / push.

本地北京时间: 2026-07-15 12:09:06 CST
下一步模型: codex_bookkeeper
下一步任务: 核验最小 diff、测试结果和文件边界
