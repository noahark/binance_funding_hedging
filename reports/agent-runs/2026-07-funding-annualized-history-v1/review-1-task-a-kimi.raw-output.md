# Review-1 Raw Output: Task A Backend Contract And Settled History

Reviewer: fresh Kimi read-only session (`kimi-code/kimi-for-coding`)
Stage: `2026-07-funding-annualized-history-v1`
Review range: `0206f8bf7236e807b4cd69d7beed02eb41e8ec60..2e27efcbed960206b43c25054bf6105224942439`
Diff fingerprint: `2e27efcbed960206b43c25054bf6105224942439:85c780708fe546a32f6ef2120841c0176aab313adf81f6d82da82e48fdfdddfb`

## Preflight

`scripts/validate-stage.py 2026-07-funding-annualized-history-v1 --phase pre-review` passed with status `review_1`.

## Verified Commands

- `python3 -m pytest backend/tests/test_funding_history.py backend/tests/test_config.py -q` -> 44 passed
- `python3 -m pytest backend/tests -q` -> 244 passed
- `python3 -m json.tool schemas/api/public-market/snapshot.schema.json >/dev/null` -> OK
- `git diff --check 0206f8bf..2e27efc -- . ':(exclude)reports/agent-runs/2026-07-funding-annualized-history-v1/status.json'` -> clean
- `git diff --binary 0206f8bf..2e27efc -- . ':(exclude)reports/agent-runs/2026-07-funding-annualized-history-v1/status.json' | sha256sum` -> `85c780708fe546a32f6ef2120841c0176aab313adf81f6d82da82e48fdfdddfb`

## Findings

- **P0**: None.
- **P1**: None.
- **P2** `backend/services/snapshot_service.py:288,301` — The dedicated funding-history cache is keyed only by `symbol`, not by `(symbol, start_ms, end_ms)`. Within the 1,800-second TTL, a later snapshot whose `t_end_ms` has advanced reuses entries fetched for an earlier 30-day window, so the newest settled records can be omitted and slightly stale records included until the cache expires. This does not violate the stated Task A requirement but is a residual window-drift risk.
- **P3** `backend/services/snapshot_service.py:114` — `data_time_ms = max((p.get('time', 0) for p in raw['premium_index']), default=0)` can produce `0` if `premium_index` is empty or lacks `time`, leading to a negative `startTime` in the deep-history request. The likely outcome is a degraded row (not a snapshot failure), but the edge case is not explicitly guarded.

## Required Fixes

None for Task A. The P2/P3 items are acceptable residual risks for this bounded stage.

```text
本地北京时间: 2026-07-10 23:09:55 CST
下一步模型: bookkeeper / review-2 dispatcher
下一步任务: 将 Task A review-1 ACCEPT 证据录入 status.json，并准备后续 review-1 Task B/C/D 与 review-2 派发。
```

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-funding-annualized-history-v1",
  "role": "first_reviewer",
  "model": "kimi-code/kimi-for-coding",
  "verdict": "ACCEPT",
  "diff_fingerprint": "2e27efcbed960206b43c25054bf6105224942439:85c780708fe546a32f6ef2120841c0176aab313adf81f6d82da82e48fdfdddfb",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/00-task.md",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/10-design.md",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/11-adr.md",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/20-implementation-backend.md",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/60-test-output.txt",
    "reports/api-samples/2026-07-funding-annualized-history-v1/20260710T061419Z/capture.md",
    "reports/api-samples/2026-07-funding-annualized-history-v1/20260710T061419Z/raw/fapi-v1-fundingRate-BTCUSDT-limit1000.json",
    "backend/adapters/binance_public.py",
    "backend/config.py",
    "backend/domain/snapshot.py",
    "backend/services/snapshot_service.py",
    "backend/tests/test_funding_history.py",
    "backend/tests/test_config.py",
    "schemas/api/public-market/snapshot.schema.json"
  ],
  "findings": [
    {
      "severity": "P2",
      "title": "Funding-history cache key omits window bounds",
      "file": "backend/services/snapshot_service.py",
      "line": 288,
      "evidence": "cached = self._funding_history_cache.get(symbol) and self._funding_history_cache[symbol] = (now, entries) key only by symbol, not by (symbol, start_ms, end_ms).",
      "impact": "Within the 1,800-second TTL a later snapshot with a different t_end_ms reuses entries fetched for an earlier 30-day window; newest settled records may be omitted and stale records included until expiry.",
      "recommendation": "Key the cache by (symbol, start_ms, end_ms) or document the accepted window-drift tolerance in the design/ADR."
    },
    {
      "severity": "P3",
      "title": "Defensive edge case: data_time_ms=0 yields negative startTime",
      "file": "backend/services/snapshot_service.py",
      "line": 114,
      "evidence": "data_time_ms = max((p.get('time', 0) for p in raw['premium_index']), default=0). If premium_index is empty or lacks time, start_ms becomes -30*86_400_000.",
      "impact": "Low: public inputs are required for a valid snapshot; Binance will likely reject the negative startTime and degrade the row rather than fail the snapshot.",
      "recommendation": "Guard history fetch when data_time_ms <= 0 by degrading to empty history/null annualization, consistent with other degradation paths."
    }
  ],
  "required_fixes": [],
  "residual_risks": [
    "Within the 1,800-second funding-history cache TTL, window drift can occur because the cache key is symbol-only.",
    "Empty or time-less premium_index input is not explicitly guarded before computing the deep-history window."
  ],
  "next_action": "continue"
}
```
