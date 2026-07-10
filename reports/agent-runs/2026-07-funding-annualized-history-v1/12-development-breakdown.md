# Development Breakdown: 2026-07-funding-annualized-history-v1

## Ownership And Sequence

| Task | Owner | Provider identity | Dependency | Review-1 |
| --- | --- | --- | --- | --- |
| A: backend contract and settled history | Claude-GLM (`glm-5.2`) | `zhipu_glm` | none | fresh Kimi session (`moonshot_kimi`) |
| B: table and history drawer | Kimi (`kimi-code/kimi-for-coding`) | `moonshot_kimi` | Task A committed wire/schema/fixture | fresh Claude-GLM session (`zhipu_glm`) |
| C: selected-symbol history endpoint | Claude-GLM (`glm-5.2`) | `zhipu_glm` | Task B committed | fresh Kimi session (`moonshot_kimi`) |
| D: Drawer history loading and table refinement | Kimi (`kimi-code/kimi-for-coding`) | `moonshot_kimi` | Task C committed endpoint/schema | fresh Claude-GLM session (`zhipu_glm`) |

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
5. Add the three fields as optional decimal-string-or-null row-schema
   properties. Preserve frozen v0.1 schema validation, and assert instead that
   every current service output row emits all three keys. Do not add count
   fields, change `schema_version`, or alter sorting.
6. Capture and retain authentic public multi-week raw evidence in this stage's
   API-sample path. Add deterministic vectors under
   `backend/tests/fixtures/funding-history/` and focused coverage in the new
   `backend/tests/test_funding_history.py` for boundary, mixed interval,
   negative, empty, cache, top-N, degraded-fetch, ordering, legacy optional-
   schema, and current-output-presence cases. Update `test_config.py` and
   `test_snapshot.py` where the new configuration or output fields affect
   existing coverage. Do not modify frozen samples or legacy hand-authored rows
   solely to satisfy this additive change.
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
  `annualized_funding_30d`, each an optional decimal string or `null` in the
  schema and always present in current service output.
- History: settled only, 30-day inclusive window, newest-first on the wire.
- 24h estimate semantics must never be relabeled as settled history.
- Do not modify canonical docs, route/version, sort basis, borrow/net-yield
  semantics, private channel, execution surfaces, Harness files, accepted
  stage artifacts, or frozen contract-v2 sample files.

## Task C: Selected-Symbol History Endpoint

Owner: Claude-GLM. This review-feedback task is a backend/API-contract change,
not a Kimi task.

1. Add `GET /api/public-market/funding-history?symbol=...` to the stdlib server
   and a schema-valid success response defined in `13-review-feedback-fix.md`.
2. Resolve the requested symbol against the current snapshot's eligible rows;
   take the request window end from that snapshot's `data_time`, then reuse the
   existing successful per-symbol 30-minute cache and settled-history helpers.
   Do not use request-time browser values, a full-universe prefetch, a database,
   or private channel code.
3. Return deterministic HTTP 400 (missing/malformed), 404 (not eligible), and
   502 (`funding_history_unavailable`) responses. A successful no-record window
   is HTTP 200 with `history_status: "empty"`; it is not an error and is cached
   as a successful result.
4. Add focused service, route, schema, cache reuse, and error-path tests. Keep
   existing snapshot top-N enrichment and its 60-second cache semantics intact.
5. Run `python3 -m pytest backend/tests -q`, schema JSON checks, and
   `git diff --check`; write only the Task C implementation report.

Allowed files are exactly the Task C list in `00-task.md`.

## Task D: Drawer History Loading And Table Refinement

Owner: Kimi. Start only after Task C is committed and the bookkeeper records
the endpoint/schema path and fixed range in the Task D dispatch body.

1. Remove only the default route-class table column. Keep the route filter and
   route field in client validation/payload; retain the visible negative-funding
   status column. Update `colspan` and self-check indexes accordingly.
2. Change the Drawer desktop width to 620px with a full-width narrow-viewport
   fallback; keep the three annualized card labels on one line.
3. For a selected row with no preloaded history, call the same-origin endpoint,
   render loading, merge a success response into the selected row/table, render
   `empty` as no records, and render HTTP 502 as a retryable load failure.
   Ignore a response that arrives after selection has changed. Never call
   Binance from the browser.
4. Extend the self-check for request URL, loading/success/empty/failure/retry
   states, stale-response isolation, removed route column, retained filter and
   status column, 12-column blocked state, and Drawer width/card labels.
5. Run `node frontend/self-check.js` and `git diff --check`; write only the
   Task D implementation report.

Allowed files are exactly the Task D list in `00-task.md`.

## Bookkeeper Integration Check

After each bounded task, the bookkeeper must verify the changed-file boundary,
commit the task on `stage/2026-07-funding-annualized-history-v1`, and preserve
the relevant test report. The review-feedback amendment adds serial Task C then
Task D, so formal review is prepared only after Task D is committed and the
combined stage range is re-anchored.

```text
本地北京时间: 2026-07-10 13:13:36 CST
下一步模型: human
下一步任务: 批准后先将 Task A 的 PASTE BODY 交给 Claude-GLM；Task B 必须等待 Task A 的固定契约提交。
```
