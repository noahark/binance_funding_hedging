# Fix Report — Review-2 Rework, Frontend (Task B, packet 55)

Executor role: bounded frontend rework implementer (Claude Sonnet 5, anthropic).
Scope: `frontend/index.html`, `frontend/self-check.js` only. No backend, docs,
`status.json`, `70-handoff.md`, credential, or environment file was read or
modified. No Binance connection, no real POST, no commit, no dispatch.

Authority read in full, in order, before writing any code:
`15-immediate-loop-and-open-log-amendment.md` (user-approved amendment — top
authority for cadence/error-matrix/opening-log wording), `16-replacement-
development-breakdown.md` (§4 Task B requirements B-1..B-4, §5 frozen `entries`
contract), `50-review-2.md` (original REWORK verdict, finding 6 / required fix
7, and the raw JSON verdict), `04-user-execution-policy.md`. Packet
`53-review-2-rework-frontend.dispatch.md` was **not** read or executed (already
superseded); its supersession is only referenced via packet 55's receipt.

## What the previous round got wrong (finding → fix map)

| Review-2 / amendment source | Problem | Fix in this round |
| --- | --- | --- |
| 50-review-2.md finding 6 (P1) + required fix 7 | `target_n` labeled "成功开单次数" (successful-order count) | Every label (market-table input, empty-state copy, task card) now reads "计划尝试次数" (planned attempts). Error copy updated to match. |
| 50-review-2.md finding 6 | Hardcoded `/3` and a client-side `fail_count > 3` → "计划终止" (`isHedgeTaskTerminated`) that could disagree with the server | `isHedgeTaskTerminated` deleted entirely (definition + `__appHelpers` export). Button matrix (`pauseDisabled`/`startDisabled`/`deleteDisabled`/`fillDisabled`) now derives only from `task.status`, `pause_reason`, `stop_reason` as returned by the backend task doc. |
| 50-review-2.md finding 6 | `leg_exposure` truthy alone rendered "任务已暂停，等待人工处理" regardless of real status, while the backend keeps scheduling | Exposure note now branches on `task.status`: `running`/anything else → "任务仍继续调度下一组，系统不自动对冲、不自动平仓"; only `paused`/`stopped` → "任务当前处于「X」，暂不再补发". Never shows the old false-pause sentence. |
| 15-amendment I-4 (additive `stopped`) | No distinct rendering existed for a fatal terminal stop vs. a threshold/manual pause | Added `stopped` to `HEDGE_TASK_STATUS_LABELS`/`HEDGE_TASK_STATUS_BADGE` ("已终止", danger badge) and a new `stopReasonLine` that renders `task.stop_reason` verbatim with "需人工修正原因后新建任务". `paused` keeps its existing `pause_reason` line. Button matrix: `stopped` behaves like a terminal state (start/fill disabled, delete still allowed for soft-delete), matching `done`/`deleted`. |
| 15-amendment §Opening log page / 16-breakdown §5 | No dedicated log page existed; the only per-attempt view was the compact in-task timeline, which review-2 flagged as an insufficient failure-visibility surface | Added a new **开单日志** tab beside **开单任务** (`hedge-tab-tasks` / `hedge-tab-logs`, mirroring the borrow-log tab pattern exactly: same CSS classes, same panel-swap logic, same newest-first / 刷新 / 加载更多 interaction). Reads `GET /api/hedge-open-logs?limit=50[&cursor=...]` and renders the frozen `entries[]` array from §5. The existing compact "尝试时间线" view is unchanged and stays under the 开单任务 tab, per the amendment's "may remain as a compact view" allowance. |

## B-1..B-4 requirement coverage

- **B-1 (semantics)** — `target_n` → "计划尝试次数" everywhere; failure counts /
  pause-stop reasons / button states / thresholds now read only from
  `failure_pause_threshold`, `consecutive_submission_failures`, `status`,
  `pause_reason`, `stop_reason`. No hardcoded `/3` or `>3` remains anywhere in
  either file (verified by grep after edits).
- **B-2 (state display)** — `stopped` vs `paused` rendered distinctly (see
  table above); `single_leg` shows the advisory note plus "任务仍继续调度"
  unless the real status is `paused`/`stopped`; querying groups show "查询中"
  in both the compact timeline (`pair_outcome === null`) and the new log page
  (`overall_result: 'querying'` → "查询中", `next_action: 'waiting_query'` →
  "等待查询终态").
- **B-3 (开单日志 page)** — New tab, same-origin read-only fetch only
  (`GET /api/hedge-open-logs`), no browser signing, no Binance URL, no new
  write endpoint. Each row renders (all fields degrade to `—` when absent):
  event times (created/submitted/final), task ID, coin, direction, attempt
  seq, planned `q_common` + `planned_quote_amount`, both legs' `side` /
  `order_id` / `client_order_id` / exchange `status` / cumulative base+quote /
  `avg_price` / fee, `residual`, `overall_result` (mapped to the 7 Chinese
  states from §5), `error_category`/`error_code`/`error_reason_zh`, and
  `next_action` (mapped to the 5 Chinese states from §5). Decimal fields are
  passed through `hedgeText()` verbatim (no `Number()`/`hedgeNum()` round-trip)
  so amounts never re-serialize through JS floats. `task_event` rows render
  with all attempt/leg fields as `—`, per §5.
- **B-4 (self-check)** — Extended, not static-text-only:
  - Rewrote the old exposure/terminated test into a 3-task scenario (running
    +leg_exposure, paused+leg_exposure, stopped+stop_reason) asserting the
    exact continue-vs-halt wording and the full button matrix per status,
    including a check that `paused` does **not** disable fill-once/fill-all
    (matches `backend/hedge_open_tasks/service.py::_require_fillable`, which
    only blocks `deleted`/`done` — the first draft of this test wrongly
    asserted disablement and was corrected against that backend read).
  - Changed the "custom threshold" task-card test to use `failure_pause_threshold=5`
    (non-default) and assert the old default `3` is absent, proving the value
    isn't hardcoded.
  - Five new opening-log-page tests: tab structure/position + first-page load
    (`?limit=50`), field-for-field rendering incl. missing-leg and
    all-`null` `task_event` degradation, a no-`orderId` confirmed-failure row
    with two-page cursor pagination + load-more + explicit refresh, an
    empty/503-error degradation test, and a dedicated `querying` rendering
    test.

## Commands run (this session, verbatim)

```
node frontend/self-check.js
→ 全部自检通过 (all blocks printed [PASS], including the 6 new/rewritten hedge blocks)
  Re-run again immediately before writing this report: still 全部自检通过.

.venv/bin/python -m pytest backend/tests -q
→ First two runs (before/after all frontend edits, backend untouched by this
  packet): 862 passed. A third run, taken just before finalizing this report,
  showed `1 failed, 861 passed` — `test_hedge_domain.py::
  test_preflight_step_unreadable_rejects` (`assert 'preflight_incomplete' ==
  'below_min_qty'`). `git status`/`git diff --stat -- backend` at that moment
  showed `backend/hedge_open_tasks/domain.py` and `backend/tests/
  test_hedge_domain.py` actively changing size between consecutive checks
  (116 → 132 → 189 inserted lines) with no action from this session. That is
  packet 54 (Task A, backend rework, different agent/session, disjoint file
  boundary) landing concurrently in the same shared working tree, per
  16-breakdown §7 ("the two tasks may run in parallel"). This packet never
  opened, read, or wrote any file under `backend/**`; the failing test and the
  file it exercises are both outside this packet's allowed-file list. This is
  reported for the bookkeeper's awareness, not fixed here.

.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
→ 55 passed in 0.89s / 0.96s (re-run)

git diff --check
→ no output (clean, no whitespace errors)
```

Per the dispatch's instruction not to write to `60-test-output.txt` (bookkeeper
owns that file to avoid a concurrent-write race with the parallel backend
task), raw output is summarized above rather than appended there.

## Changed files

- `frontend/index.html` (see `git diff --stat` below) — status
  label/badge map, exposure/stop-reason card copy, button matrix, removed
  `isHedgeTaskTerminated`, new 开单日志 tab markup/state/`els`/functions
  (`loadHedgeLogs`, `renderHedgeLogs`, `renderHedgeLogEntryCard`,
  `renderHedgeLogEntryLeg`, `setHedgeTab`, `HEDGE_LOG_*` label maps), new
  `__appHelpers` exports (`setHedgeTab`, `getHedgeTab`, `loadHedgeLogs`,
  `getHedgeLogs`), `resetHedgeStateForTest` extended.
- `frontend/self-check.js` (see `git diff --stat` below) — new DOM ids,
  `mockHedgeTask.stop_reason`, new `mockHedgeLogEntry` + three fixture
  constants + two page fixtures, fetch-mock split for `?limit=100` (attempt
  timeline, unchanged) vs. the new paginated log-page queue
  (`hedgeLogPageResponses`), rewritten exposure/terminated test, adjusted
  custom-threshold test, six new/extended test blocks for the log page.
- `reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-2-frontend.md`
  (this file).

```
$ git diff --stat -- frontend/index.html frontend/self-check.js
 frontend/index.html    | 226 ++++++++++++++++++++++++++----
 frontend/self-check.js | 374 +++++++++++++++++++++++++++++++++++++++++++++----
 2 files changed, 549 insertions(+), 51 deletions(-)
```

## Backend field dependency (not invented, escalate if it drifts)

The frozen §5 contract (16-breakdown) requires the backend (Task A, running in
parallel, owner glm) to additively ship: `GET /api/hedge-open-logs`'s new
`entries[]` array, and the task doc's `stop_reason` (nullable) plus `status`
gaining the literal value `"stopped"`. As of this session, neither exists yet
in `backend/hedge_open_tasks/store.py` / `service.py` (confirmed by grep before
starting: no `stop_reason`, no `entries` projection). This frontend round was
written strictly against the frozen §5 field names and I-4 status vocabulary,
not against the current backend state — per the breakdown's explicit sequencing
note that both tasks "may run in parallel against §5 (frozen here)". No field
name was invented or guessed beyond what §5/I-4 specify; the mock fixtures in
`self-check.js` reproduce §5 field-for-field. If Task A's actual shipped field
names or the `entries[]` shape end up diverging from §5, that is a bookkeeper
reconciliation item, not something this round should have silently patched
around.

## Known residual risks

- Everything in 50-review-2.md's own residual-risks list still applies
  unchanged (single-leg exposure remains possible up to the user-approved
  planned-attempt count; no automatic repair/cancel/close; real Binance field
  compatibility still needs authorized sanitized evidence). This round changes
  only how the frontend displays state the backend already owns.
- This frontend cannot verify the real shape of the backend's `entries[]`
  payload or the `stopped`/`stop_reason` fields end-to-end (backend rework is
  a separate, parallel packet not yet merged at the time this was written);
  `self-check.js` mocks are the only current proof this round has. Integration
  evidence against the actual merged backend is the bookkeeper's next step
  (per 16-breakdown §7).
- `HEDGE_TASK_STATUS_LABELS`/button matrix still recognizes the legacy
  `exposure_alert` status value (kept unchanged, not part of this round's
  required fixes) even though current backend `resolve_status_after_attempt`
  never produces it; left as dead-but-harmless code per the "surgical changes"
  instruction rather than removed without a request to do so.
- The pre-existing `HEDGE_PAIR_OUTCOME_BADGE.single_leg = 'warning'` CSS-class
  mismatch (the stylesheet only defines `.badge.warn`, not `.badge.warning`) in
  the untouched attempt-timeline code was **not** fixed — out of this round's
  bounded scope; new code added by this round consistently uses `'warn'`.

Stopping here per the dispatch contract: no commit, no review, no dispatch.
