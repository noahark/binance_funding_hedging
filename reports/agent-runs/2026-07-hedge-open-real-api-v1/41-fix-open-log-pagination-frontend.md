# Fix Report — Opening-Log Pagination Compatibility, Frontend (packet 57)

Executor role: bounded frontend compatibility-fix implementer (Claude Sonnet 5,
anthropic). Scope: `frontend/index.html`, `frontend/self-check.js` only. No
credential was read, no Binance connection was made, no real POST was sent, no
live/Start was enabled, no commit was made, and `backend/**`, `docs/**`,
`status.json`, `70-handoff.md`, PRD/design/ADR, and packets 54/55/56 were not
opened or modified.

Authority read in full, in order, before writing any code:
`17-opening-log-pagination-compatibility.md` (top authority for this task —
the frozen additive `entries_limit`/`entries_cursor`/`entries_next_cursor`
seam), `18-replacement-r4-diff-reconciliation.md` (bookkeeper's R4 finding: the
prior implementation's reuse of the legacy `cursor`/`limit`/`next_cursor` for
`entries` could re-surface the newest `task_event` on every subsequent page),
then the current `frontend/index.html` / `frontend/self-check.js` as they
stood after packet 55.

This is a bounded interface repair, not a new product decision: it does not
change order quantities, cadence, risk policy, or any Binance request shape.

## What changed and why

The previous round (packet 55) implemented the 开单日志 tab against the
originally-frozen §5 contract, which reused the same `cursor`/`limit` request
params and `next_cursor` response field that the legacy `logs`/`attempts`
pagination already used. R4 found this unsafe because `entries` merges two
different persistence sequences (`hedge_open_log(ts_us, id)` and
`hedge_open_attempt(created_at_us, id)`) that cannot share one two-part legacy
cursor without risking duplicate pages. `17-opening-log-pagination-
compatibility.md` froze the fix as a small additive seam that leaves the old
pagination completely alone and gives `entries` its own request/response
names.

### 1. `frontend/index.html` — `loadHedgeLogs`

- First page: `GET /api/hedge-open-logs?entries_limit=50` (was `?limit=50`).
- Load more: `GET /api/hedge-open-logs?entries_limit=50&entries_cursor=<...>`
  (was `?limit=50&cursor=<...>`), where `<...>` is the **previous response's**
  `entries_next_cursor` — never the legacy `next_cursor` field.
- Next-page state is now read from `doc.entries_next_cursor`. If that field is
  missing or not a string, the frontend safely treats it as "no more pages"
  (`state.hedgeLogs.nextCursor = null`) and never falls back to
  `doc.next_cursor`, per rule 5 of the compatibility doc.
- `HEDGE_LOG_PAGE_LIMIT` (=50) and the `hedgeApi()` call plumbing are
  unchanged; only the query-param names and the response-field read changed.
- The task-local compact attempt timeline (`loadHedgeAttempts`, fixed
  `?limit=100`, no cursor) was not touched — verified unchanged by grep before
  and after editing.
- Borrow log pagination (`/api/borrow-logs?...`) and every hedge task action
  route were not touched.
- No new browser signing, no new write endpoint, no Binance URL was
  introduced; the route table and method (`GET`) are exactly as before.

### 2. `frontend/self-check.js`

- Fetch mock: the existing split between the attempt-timeline literal URL
  (`?limit=100` → `hedgeLogsGetResponse`) and everything else on the
  `/api/hedge-open-logs` prefix (→ `hedgeLogPageResponses` queue) needed no
  structural change — it was already URL-literal-based, and the new
  `entries_limit=`/`entries_cursor=` request strings never match the
  `?limit=100` literal, so they correctly fall through to the paginated queue.
  Comments were updated to name the new params.
- `HEDGE_LOG_PAGE_1` / `HEDGE_LOG_PAGE_2` fixtures now carry `entries_next_cursor`
  as the real pagination field, plus a **decoy** legacy `next_cursor` with a
  deliberately different value (`'legacy-cursor-should-be-ignored'` /
  `'legacy-cursor-should-also-be-ignored'`) — this makes the pagination test
  fail loudly if the frontend ever reads the wrong field.
- Test 88 (tab structure/first load) now asserts the exact URL
  `/api/hedge-open-logs?entries_limit=50`.
- Test 90 (rewritten) asserts:
  - the load-more request is exactly
    `/api/hedge-open-logs?entries_limit=50&entries_cursor=entries-cursor-page-2`
    (the real `entries_next_cursor` value, not the decoy legacy cursor);
  - after merging both pages, every `entry_id` across the combined list is
    unique (`new Set(entryIds).size === entryIds.length`) — a direct
    regression check for the R4-found duplicate-`task_event` bug;
  - newest-first ordering is preserved across the merge;
  - explicit refresh re-requests exactly `/api/hedge-open-logs?entries_limit=50`
    (no `entries_cursor`) and resets to page 1.
- New test 90b directly exercises compatibility rule 5: a page response with
  a **non-string** `entries_next_cursor` (`123`) plus a truthy legacy
  `next_cursor`, asserting load-more stays hidden, the internal cursor state
  is `null`, and `loadHedgeLogs(false)` refuses to fire a request (`{ ok:
  false }`) instead of silently falling back to the legacy cursor.
- Tests 91/92 (empty-state/503 degradation, `querying` rendering) had their
  fixture bodies' pagination field renamed from `next_cursor` to
  `entries_next_cursor` for accuracy; their assertions were otherwise
  unchanged since they don't exercise pagination.
- No assertion for the borrow log page, hedge task actions, or the attempt
  timeline's `?limit=100` request was changed; test 88/89/90/90b/91/92 all
  still separately confirm (via the unmodified attempt-timeline tests 85/86,
  re-run and still passing) that the `?limit=100` request shape is untouched.

## Commands run (this session, verbatim)

```
node frontend/self-check.js
→ 全部自检通过 — every block prints [PASS], including the rewritten/added
  opening-log-page blocks (88, 89, 90, 90b, 91, 92) and the unmodified
  attempt-timeline blocks (85, 86).

git diff --check
→ no output (clean; exit 0)
```

Per this packet's instructions, only the two commands above were required and
run; the backend/full-suite regressions (`pytest backend/tests`, `pytest
scripts/tests/test_validate_stage_dispatch_protocol.py`) belong to packet 56
(backend, disjoint file boundary) and the bookkeeper's post-56/57
reconciliation, not to this bounded frontend packet.

## Changed files

- `frontend/index.html` — `loadHedgeLogs()` request/response field rename
  (`entries_limit`/`entries_cursor`/`entries_next_cursor`), plus two comment
  updates describing the new seam. No other function, markup, or route was
  touched.
- `frontend/self-check.js` — fixture and mock-comment updates for the new
  field names, rewritten pagination test (90) with a duplicate-`entry_id`
  guard and decoy-legacy-cursor proof, new test 90b for the non-string/missing
  `entries_next_cursor` safe-degrade rule, and small fixture renames in tests
  91/92.
- `reports/agent-runs/2026-07-hedge-open-real-api-v1/41-fix-open-log-pagination-frontend.md`
  (this file).

```
$ git diff --stat -- frontend/index.html frontend/self-check.js
 frontend/index.html    | 231 ++++++++++++++++++++++++---
 frontend/self-check.js | 417 ++++++++++++++++++++++++++++++++++++++++++++++---
 2 files changed, 597 insertions(+), 51 deletions(-)
```

Note: these totals are cumulative against the last commit (`26bb7b4`) and
therefore include the still-uncommitted packet-55 frontend rework alongside
this packet's incremental pagination fix, per
`18-replacement-r4-diff-reconciliation.md` ("当前未提交实现保持原样，等待
56/57 修复完成后一起做最终对账、复跑、提交和重新 Review-1").

## Working-tree note (not authored by this session)

At the time of this run, `git status` also showed uncommitted changes under
`backend/hedge_open_tasks/**`, `backend/services/**`, `backend/tests/**`, a
new `backend/tests/test_hedge_review2_regressions.py`, and bookkeeper-owned
files (`60-test-output.txt`, `70-handoff.md`, `status.json`) actively growing
across repeated `git diff --stat` checks during this session. That is packet
56 (backend pagination repair, disjoint file boundary, different
agent/session) landing concurrently in the same shared working tree, per
17/18's explicit allowance ("两个修复可并行"). This session never opened, read,
or wrote any file under `backend/**`, `docs/**`, `status.json`, or
`70-handoff.md`.

## Known residual risks

- This fix is purely a request/response field rename on the frontend side; it
  cannot itself prove the backend's new `entries_next_cursor` cursor is stable
  and duplicate-free across real persistence-layer boundaries — that is
  packet 56's and the bookkeeper's integration-evidence responsibility.
- The frontend still cannot distinguish "backend has no `entries_next_cursor`
  field at all yet" from "backend correctly reports no more pages" — both
  degrade identically to `null`/no-load-more, per the frozen rule that missing
  is safe. This is the intended fail-safe behavior, not a gap, but it means a
  backend that never ships the field would look identical to one that has
  reached the last page; that is a backend-side observability concern, not a
  frontend defect.
- All residual risks already recorded in `40-fix-review-2-frontend.md` still
  apply unchanged (this packet only touches pagination plumbing, not any
  business/status/semantics logic from packet 55).

Stopping here per the dispatch contract: no commit, no review, no dispatch.

当前 Session ID: unavailable (this CLI harness does not expose a provider-native Session ID to the running agent)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/41-fix-open-log-pagination-frontend.md
本地北京时间: 2026-07-24 17:44:48 CST
下一步模型: bookkeeper
下一步任务: reconcile the frontend pagination change with packet 56 and run integration tests
