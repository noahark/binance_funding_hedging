# Design

## Context

The Group C cursor examines at most 10 homepage symbols every 30 seconds. Three
component checks occur in that loop: public funding history for every candidate,
and borrow-rate/max-borrowable only for eligible private borrow candidates.

Today history refresh and publication use the same configured TTL. When an entry
reaches 1800 seconds it stops being published immediately, but it may wait for
the cursor before being refreshed. The resulting normal-success gap was observed
on ANIME and HOME.

## Decision

Separate only the history component's refresh-fresh threshold from its existing
publication expiry:

```text
history_refresh_due_age = max(0, funding_history_cache_ttl_seconds - 300)
history_publish_expiry  = funding_history_cache_ttl_seconds
```

Use the refresh threshold in both `_history_is_fresh()` and the cache-reuse
guard inside `_fetch_history_for()`. Keep `_all_valid_history()` unchanged on
the full publication TTL.

The implementation may use a small module constant or a small private helper;
it must not introduce a new environment variable or generalized scheduler
abstraction.

## Invariants

- A 1500-second cursor visit reaches the upstream public funding-history seam.
- The old entry remains publishable until 1800 seconds if the early refresh
  fails or has not yet been attempted.
- Successful refresh writes continue using the inherited timestamp behavior;
  the unrelated P3 is not repaired here.
- Borrow-rate and max-borrowable continue using the existing 1800-second
  component TTL.
- Cursor candidate order, batch size, and per-tick pressure remain unchanged.

## Tests

Use deterministic monotonic time and counting stubs. Pin the 1499/1500 boundary,
the separate 1800 publication boundary, continuous normal-success publication,
and zero extra private component calls at 1500 seconds.

本地北京时间: 2026-07-15 10:44:33 CST
下一步模型: claude_glm
下一步任务: 实现最小双门槛并用确定性边界测试证明作用面
