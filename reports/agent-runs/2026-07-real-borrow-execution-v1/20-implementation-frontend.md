# Task B Implementation Report — Frontend Backend-Authority Migration

Stage: `2026-07-real-borrow-execution-v1`
Task: B (frontend), implementer Kimi (`kimi-code/kimi-for-coding`), skill
`senior_developer`. Prompt: `task-B-kimi.prompt.md`.

## Changed Files

- `frontend/index.html`
- `frontend/self-check.js`

No other file was touched. In particular: no backend/schema edits, no
`status.json` / `70-handoff.md`, no dispatch-file edits, no git commit.

## What Was Implemented

1. **Backend-authority migration.** `state.borrowTasks` is now only a render
   cache of the last `GET /api/borrow-tasks` response. All task truth comes
   from the same-origin API. The old in-memory fake authority
   (`borrowTaskIdSeq`, local status mutation, `parseBorrowAmount` float path,
   `formatTaskAmount`) is removed.
2. **Market-row create.** 确认 sends `POST /api/borrow-tasks` with frozen body
   `{"asset","amount_per_attempt","success_target"}` (asset from the row's
   `base_asset`; amount is the user-entered decimal string validated against
   `^[0-9]+(\.[0-9]+)?$` and sent verbatim — no float). The returned document
   (already `borrowing`, immediately scheduler-eligible) is displayed; no
   navigation and no second Start click.
3. **Task mutations.** start/pause/delete/edit call
   `POST /api/borrow-tasks/{id}/{start|pause|delete|edit}`. start/pause/delete
   send `{}`; edit sends `{"amount_per_attempt","success_target","version"}`
   (optimistic concurrency from the cached document). Every successful
   mutation patches the cache with the returned document, then refetches the
   list (frozen refresh policy b).
4. **Global interval editor.** Top of the borrow page: GET-renders
   `interval_seconds`, 确认 sends `PUT /api/borrow-scheduler-settings` with
   `{"interval_seconds": "<user string>"}`; 400 `invalid_interval` renders its
   `detail` locally; the old static "每 30 秒尝试一次" line now quotes the
   live interval from the settings document.
5. **Top-level tabs `借币任务 | 借币日志`.** Status filters live only inside
   the task tab. Log tab loads page 1 on activation and on an explicit 刷新
   action; older pages only via 加载更多 with `next_cursor`; 加载更多 hides
   when `next_cursor` is null. No log polling.
6. **Latest result + blocking state.** Every card shows the backend
   `latest_result` with frozen labels: `success→成功`,
   `known_rejection→已知拒绝`, `rate_limited→限频冷却`, `unknown→未知·待对账`,
   `execution_disabled→执行未启用`; null → `暂无执行记录`.
   `unresolved_attempt_id != null` shows the `待对账·暂停调度` badge, disables
   start/pause (task will not be scheduled), keeps delete available (operator
   escape hatch). All four lifecycle statuses and the accepted
   start/pause/delete button matrix and theme classes are preserved.
7. **Truthful copy.** The `前端演示/浏览器内存` disclaimers are replaced with
   persisted-task, execution-disabled wording: tasks and logs are persisted in
   backend SQLite; this stage performs no real borrowing; every scheduled
   attempt is `执行未启用`; the browser never schedules, simulates, or calls
   Binance.
8. **Refresh policy.** Task list refetches (a) on entering the borrow view,
   (b) after every successful mutation, (c) on the existing 60 s snapshot tick
   only while the borrow view is active. No new timer anywhere; the snapshot
   refresh is never a task execution clock.
9. **API errors.** Non-2xx responses surface the backend `detail` string
   locally: per-row for create, per-card for start/pause/delete/edit, next to
   the editor for interval, and as an in-view banner for list/log load
   failures (cached state is kept on load failure).

## API / Mock Contract

The frontend consumes only the frozen §3.1 routes:
`GET/POST /api/borrow-tasks`, `POST /api/borrow-tasks/{id}/{start,pause,delete,edit}`,
`GET /api/borrow-logs?limit=&cursor=`, `GET/PUT /api/borrow-scheduler-settings`.
No invented fields or client-side outcomes. `frontend/self-check.js` mocks
every response with documents copied field-for-field from the §3.3/§3.5/§3.6
example documents (`MOCK_TASK_HOME`, `MOCK_SETTINGS_DEFAULT`,
`MOCK_LOG_ENTRY_HOME` / pages), so Task B does not depend on Task A source.

## Test Summary

Commands run (output: `60-test-output-frontend.txt`):

```bash
node frontend/self-check.js   # 全部自检通过
git diff --check              # exit 0
```

Self-check coverage added per §5.2: tabs render/hide with filters only in the
task tab; task list renders from the mocked GET (全部 count includes
soft-deleted); create/start/pause/delete/edit issue exactly the frozen
route/method/body and re-render from the mocked response; mocked 400/409
renders `detail` locally without state corruption; interval editor round-trips
`"5"` → PUT `"0.5"` and shows mocked `invalid_interval`; all five latest-result
labels plus the unknown-block badge; log newest-first two-page cursor paging,
load-more visibility, explicit refresh reset; and a whole-run allowlist proof
that every fetch URL is one of the §3.1 same-origin paths or the pre-existing
snapshot routes (no `binance` substring, no absolute foreign origin), no new
`setInterval` beyond the 60000 ms snapshot timer and the 1000 ms countdown,
and localStorage holds only the privacy key. All pre-existing market/drawer
assertions remain green.

## Known Limitations

- Log "时间" column renders `finished_at || dispatched_at || scheduled_at`
  converted to Beijing time; pending attempts show `进行中` with their
  dispatch/schedule time. This is display-only; sort stays backend-side.
- Very large integer parts in amount/total display reuse the existing
  `toLocaleString` helper (same float-precision ceiling as the pre-existing
  balance formatting); fraction parts are rendered verbatim from the decimal
  string.
- `borrow_task` action errors and edit errors share the per-card
  `task-edit-error-<id>` container (one local error slot per card).
- 目标总量 is derived client-side via a BigInt decimal-string × integer
  helper (no float); it is display math only, never sent to the backend.

## R10 Disposition

- Self-tests PASS (see above). Reviewer snapshot generated:
  `embedded-review-B-round1.diff.patch`
  (`git diff --binary -- frontend/index.html frontend/self-check.js`).
- Embedded review: dispatched per the immutable
  `embedded-review-B.prompt.md`. Outcome and raw output:
  `embedded-review-B-round1.raw-output.md` (see R10 receipt below).
- No commit performed; stopping for the bookkeeper after the embedded-review
  disposition as instructed.

## R10 Receipt

```text
self_tests:            PASS (node frontend/self-check.js; git diff --check)
diff_patch:            embedded-review-B-round1.diff.patch
embedded_review_round: 1
reviewer:              claude_glm / glm-5.2 (fresh read-only session)
review_raw_output:     embedded-review-B-round1.raw-output.md
review_verdict:        PASS (checkpoint per R5; not a formal review-1 verdict)
rounds_used:           1 of 2
disposition:           PASS — implementation complete, no fix round needed;
                       stopping for the bookkeeper (no commit, per R6)
```

当前 Session ID: unavailable (Kimi CLI does not expose a provider-native session ID to the model)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/20-implementation-frontend.md
本地北京时间: 2026-07-19 18:18:21 CST
下一步模型: bookkeeper（人工操作员指定的独立记账会话）
下一步任务: 收 Task B 证据（20-implementation-frontend.md、60-test-output-frontend.txt、embedded-review-B-round1.{diff.patch,raw-output.md}），R4 diff 对账后串行落盘 H_B
