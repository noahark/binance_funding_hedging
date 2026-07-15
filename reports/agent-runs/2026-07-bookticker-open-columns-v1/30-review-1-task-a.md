# Task A Formal Review-1 Narrative

Reviewed the committed Task A backend/API/schema/domain diff for stage `2026-07-bookticker-open-columns-v1` (Claude-GLM implementation, Kimi cross-review).

**Diff fingerprint verified:**
`01fca8cda4e3ce37ab2b976f1ca060ed9da109a0:a8ad71a421cbf1122ec8bedf123646fcb3606b85fdc2651917519524d33222de`

**Mandatory focus checks:**

1. **Spot/futures full bookTicker requests & normalization** — `fetch_book_ticker_pair()` calls `GET /api/v3/ticker/bookTicker` and `GET /fapi/v1/ticker/bookTicker` with no parameters; request log bumps separate real-endpoint keys; `_normalize_book_ticker()` keeps prices as JSON strings only, rejects number-typed prices without `str()` coercion, and raises on non-list/empty payload. ✓
2. **Pair atomic commit** — The adapter raises on empty normalized map or one-side failure; the service only writes the cache when `pair is not None`; failure does not advance the timestamp or partially replace the map. ✓
3. **60s due / <120s usable / ≥120s stale** — `_source_due(..., ttl_a)` drives refresh; `_attach_opening_quotes()` recomputes `usable = (now - success_ts) < 2 * ttl` every assembly, so the 120s boundary is a projection, not a fetch-failure side effect. The test `test_usability_cutoff_119_usable_120_stale` verifies this without manufacturing a failure. ✓
4. **Alias-aware join** — `_attach_opening_quotes()` joins futures by `row.futures.symbol` and spot by resolved `row.spot.symbol`; bStock alias `TSLAUSDT -> TSLABUSDT` is covered by `test_join_bstock_alias_uses_resolved_spot_symbol`; `None` spot leg yields `incomplete` without substitute. ✓
5. **Forward/reverse Decimal formulas** — `compute_opening_spread_pct` uses strict `(bid - ask) / ask * 100`, final-only `ROUND_HALF_UP` quantize to `0.01`, `-0.00 -> 0.00`, and returns `None` for invalid/zero/negative operands. BTC vector `-0.04`/`0.04` and `1.005` HALF_UP carry are tested. ✓
6. **`opening_quotes` additive optional schema** — `snapshot.schema.json` adds `opening_quotes` outside the row `required` list, with closed object and 8 required nested fields; `test_negative_schema.py` confirms legacy omission is valid, number prices/spreads are rejected, unknown nested properties are rejected, and invalid statuses are rejected. ✓
7. **Selected-symbol click** — `_handle_refresh_command()` calls `_assemble()` which reads the same `book_ticker_pair` cache; `test_click_performs_no_book_ticker_http` asserts no additional bookTicker HTTP, and `test_click_projects_canonical_row_opening_quotes` asserts the projected row equals the full-snapshot row. ✓
8. **Private disabled / legacy stub compatibility** — `fetch_book_ticker_pair` is capability-checked with `hasattr`; legacy `_StubPublic` without the seam publishes `unavailable` without `AttributeError`; bookTicker runs with private channel disabled; no credentials, order, borrow, or trading side effects were added. ✓
9. **Tests truly fail on regression** — New `test_book_ticker.py` and extensions to worker/schema/click tests assert exact semantics (vectors, age boundaries, atomic failure, capability check, schema rejection), not just sample strings. Independent rerun: 142 focused backend tests pass; full `backend/tests` 375 pass; `py_compile` and `git diff --check` pass. ✓

**Findings:** None.

**Verdict:** ACCEPT.

```text
当前 Session ID: session_675fb858-c888-48d4-8d94-567f70fc91ae
Session ID 来源: transcript_path (cross-checked state.json.workDir=/Users/ark/Desktop/ai code/funding_hedging and lastPrompt="review-1-task-a-kimi.prompt.md")
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/30-review-1-task-a.md
本地北京时间: 2026-07-15 21:38:58 CST
下一步模型: codex_bookkeeper
下一步任务: 校验 Task A review-1 JSON、Session/provider isolation 与 fingerprint，并与 Task B review-1 一并门禁
```

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-bookticker-open-columns-v1",
  "role": "first_reviewer",
  "model": "kimi-code/kimi-for-coding",
  "verdict": "ACCEPT",
  "diff_fingerprint": "01fca8cda4e3ce37ab2b976f1ca060ed9da109a0:a8ad71a421cbf1122ec8bedf123646fcb3606b85fdc2651917519524d33222de",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml",
    "agents/skills/code-reviewer.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/00-task.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/10-design.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/11-adr.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/14-design-review-reconciliation.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-a.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/review-1-preflight.txt",
    "schemas/review-verdict.schema.json",
    "schemas/api/public-market/snapshot.schema.json",
    "backend/adapters/binance_public.py",
    "backend/domain/snapshot.py",
    "backend/services/snapshot_service.py",
    "backend/tests/test_book_ticker.py",
    "backend/tests/test_background_worker.py",
    "backend/tests/test_negative_schema.py",
    "backend/tests/test_symbol_snapshot_endpoint.py",
    "docs/api/public-market-contract.md",
    "docs/architecture/ARCHITECTURE.md",
    "docs/development/DEVELOPMENT_GUIDE.md"
  ],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [
    "Cross-market REST time skew remains inherent: the two bookTicker responses are not exchange-time atomic. The UI title and contract docs already disclose this as a reference quote, not an execution guarantee."
  ],
  "next_action": "continue"
}
```
