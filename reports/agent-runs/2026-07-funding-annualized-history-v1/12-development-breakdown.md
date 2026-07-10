# Development Breakdown: 2026-07-funding-annualized-history-v1

## Ownership And Sequence

| Task | Owner | Provider identity | Dependency | Review-1 |
| --- | --- | --- | --- | --- |
| A: backend contract and settled history | Claude-GLM (`glm-5.2`) | `zhipu_glm` | none | fresh Kimi session (`moonshot_kimi`) |
| B: table and history drawer | Kimi (`kimi-code/kimi-for-coding`) | `moonshot_kimi` | Task A committed wire/schema/fixture | fresh Claude-GLM session (`zhipu_glm`) |

This is a serial split, not a parallel-development stage. Codex/GPT is the
package designer and bookkeeper only; it is excluded from implementation and
fix authorship. Because Codex/GPT authored this design, review-2's primary
reviewer is an unrelated Anthropic Claude session (`claude-fable-5`, then
`opus4.8` on quota exhaustion) after a runner-level availability check.
Codex/GPT is only the documented strong-reviewer fallback if that reviewer is
unavailable or ineligible.

## Task A: Backend Contract And Settled-History Enrichment

Owner: Claude-GLM.

1. Extend the public adapter so `fetch_funding_rate` accepts bounded window
   inputs and sends `symbol`, `startTime`, `endTime`, and `limit=1000` through
   safe query construction.
2. Add a dedicated successful-result 30-minute cache in the snapshot service;
   keep the existing 60-second whole-snapshot cache intact. Restrict live deep
   fetches to `top_symbols_by_abs_rate(..., Config.top_n)`.
3. On an individual history error, append
   `funding_history_unavailable:<symbol>` and return that row with empty
   history and null settled annualization. Do not turn it into a snapshot 503.
4. Add pure Decimal helpers and row fields for D2. Filter the returned history
   to the inclusive 30-day window, serialize it newest first, and quantize all
   non-null annualized results to eight fixed decimal places.
5. Add the three fields to the row schema's `required` array as
   decimal-string-or-null values. Add one negative schema assertion per field;
   do not add count fields, change `schema_version`, or alter sorting.
6. Capture and retain authentic public multi-week raw evidence in this stage's
   API-sample path. Add deterministic vectors under
   `backend/tests/fixtures/funding-history/` and focused coverage in the new
   `backend/tests/test_funding_history.py` for boundary, mixed interval,
   negative, empty, cache, top-N, degraded-fetch, ordering, and missing-field
   schema cases. Update `test_config.py` and `test_snapshot.py` where the new
   configuration or required output fields affect existing coverage.
7. Run the backend test suite and record only the task report; do not commit or
   modify stage status/handoff/review records.

Allowed files are exactly the Task A list in `00-task.md`.

## Task B: Table Columns And Drawer UX

Owner: Kimi. Start only after the bookkeeper has committed Task A and confirmed
the three field names/schema are unchanged.

1. Update the frontend fixture and required-row validation for the three
   annualized fields.
2. Add 24h/7D/30D annualized columns after the daily-rate column. Reuse the
   existing percentage formatter and sign classes; add labels/tooltips that
   distinguish estimate-derived 24h from settled 7D/30D.
3. Add a single responsive right-side drawer and backdrop. Row activation must
   support click, `Enter`, and `Space`; close must support the close control,
   backdrop, and Escape.
4. Render the selected symbol, identical formatted header values, and
   newest-first `funding_history` rows using `Asia/Shanghai`. Empty history
   uses the design's neutral empty state. The drawer must survive refresh only
   while the selected symbol remains.
5. Keep all data access inside the existing backend snapshot fetch; do not add
   browser calls to Binance, privacy masking for public funding values, nested
   cards, or unrelated layout changes.
6. Extend `frontend/self-check.js` for new fields, display/null behavior, and
   drawer interaction. Record only the task report; do not commit or modify
   stage status/handoff/review records.

Allowed files are exactly the Task B list in `00-task.md`.

## Shared Contract And Do-Not-Touch Rules

- Fields: `annualized_funding_24h`, `annualized_funding_7d`,
  `annualized_funding_30d`, each a decimal string or `null`.
- History: settled only, 30-day inclusive window, newest-first on the wire.
- 24h estimate semantics must never be relabeled as settled history.
- Do not modify canonical docs, route/version, sort basis, borrow/net-yield
  semantics, private channel, execution surfaces, Harness files, accepted
  stage artifacts, or frozen contract-v2 sample files.

## Bookkeeper Integration Check

After each bounded task, the bookkeeper must verify the changed-file boundary,
commit the task on `stage/2026-07-funding-annualized-history-v1`, and preserve
the relevant test report. After Task B, it anchors the combined stage range,
runs `scripts/validate-stage.py 2026-07-funding-annualized-history-v1 --phase pre-review`,
and prepares the two formal cross-review packets from raw artifacts.

```text
本地北京时间: 2026-07-10 13:13:36 CST
下一步模型: human
下一步任务: 批准后先将 Task A 的 PASTE BODY 交给 Claude-GLM；Task B 必须等待 Task A 的固定契约提交。
```
