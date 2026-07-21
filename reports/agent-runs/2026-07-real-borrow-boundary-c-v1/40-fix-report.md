# Task C — Review-1 REWORK Fix 4 Report (F1 / F2 / F3)

- Stage: `2026-07-real-borrow-boundary-c-v1`
- Executor: `claude_glm` / provider identity `zhipu_glm` / `glm-5.2[1m]` — the
  original Task C implementer, single executor session.
- Audited diff fingerprint:
  `61ce536dfba6ddd347586cf324209acdfdc6afd9:449b46378a324fa3c8bdd9ec9425b1e59b7509cb55e6c129d8991322dcb1a984`
- Source review (findings + evidence):
  `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/30-review-1.md`
- Real fake-only verification outputs (append-only):
  `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt`
  (section **Fix-4 REWORK (F1/F2/F3) — Claude-GLM / glm-5.2[1m] real fake-only
  outputs**).

## Contract compliance (self-attested, executor session only)

- Single executor; no other model session or adapter command was called,
  launched, or dispatched. No `ESCALATED`.
- No real / authenticated / production-reachable Binance request; all transport
  exercise used injected fake / recording transport + dummy credentials.
- No `.env` / key file / cookie / credential store / expanded alias environment
  read.
- No second POST, no hidden retry, no retry-anyway / force-clear route added;
  no exact-path / HMAC / urlopen / AST / UI guard weakened.
- No commit / push / merge, no model dispatch.
- File boundaries respected. **The four bookkeeping files `status.json`,
  `70-handoff.md`, `30-review-1.bookkeeper-intake.md`, `ACTIVE.json` were
  modified externally (operator/bookkeeper, ~2026-07-21 12:22–12:24 CST, the
  `review-1 freshness bookkeeping correction`) — NOT by this executor.** This
  executor did not read those modifications as task evidence and did not touch
  those files; they are flagged here only so the bookkeeper is aware. This
  report does not claim review or acceptance.

## Source / test files changed (fix-4 scope only)

| File | Role |
| --- | --- |
| `frontend/index.html` | F1 copy rewrites (942/953/2548); F2 op-cell preview, `renderBorrowPreview`, input binding, startup settings load |
| `frontend/self-check.js` | F1 assertions (item 63); F2 assertions (item 62 + new 62b); `getElementById` mock `preview` |
| `backend/borrow_tasks/domain.py` | F3 `REASON_CRASH_ORPHAN_RESPONSELESS` constant |
| `backend/borrow_tasks/store.py` | F3 startup orphan→response-less-unknown intake; `resolve_reconciliation_success` finalizes formerly-pending row |
| `backend/tests/test_borrow_store.py` | F3 store tests (4) |
| `backend/tests/test_borrow_scheduler.py` | F3 scheduler test (1) |

> The optional P3 polish (remove unused `raw_body` field; `.env.example` doc
> lines) was **not** done — it is non-gating and outside the three required
> findings; left for a later pass to keep this correction surgical.

---

## F1 (P1) — stale「不发起真实借币」copy contradicts live execution status

### Root cause
Three static strings had no JS rewrite and asserted the disabled-stage invariant
(「本阶段不发起真实借币（执行未启用）」/「所有尝试结果均为『执行未启用』」).
With a live + started execution badge on the same screen the static text was
self-contradictory and contradicted `execution-status`.

### Changes
- `frontend/index.html:942` (subtitle) — rewritten to defer mode/enabled to the
  execution badge; keeps「任务与日志由后端 SQLite 持久化并调度」.
- `frontend/index.html:953` (banner) — removed the stale claim; keeps「任务与
  日志持久化在后端（SQLite），刷新或重启不丢失」and the still-true browser
  statements, now「浏览器不调度、不模拟、不签名、不请求 Binance」(added
  「不签名」).
- `frontend/index.html:2548` (task-card note template) — rewritten to defer to
  the execution badge; keeps「任务持久化在后端」.
- The runtime result-category label `execution_disabled: '执行未启用'`
  (`BORROW_RESULT_LABELS`, ~2195) is **untouched**, so the task card still shows
  「执行未启用」for `execution_disabled` attempts via `borrowResultBadge` (item
  65 still passes).
- `frontend/self-check.js` (item 63) — added assertions (no guard loosened):
  - `html` must NOT contain「不发起真实借币」or「所有尝试结果均为「执行未启用」」.
  - `html` MUST still contain「不签名」and「不请求 Binance」.
  - the existing `html.includes('执行未启用')` guard is retained (now guards the
    result-category label) and the「前端演示/浏览器内存」negative guard is retained.

### Tests / result
`node frontend/self-check.js` → `全部自检通过` (exit 0). Items 62 / 63 / 65 still
pass; new F1 assertions pass.

---

## F2 (P1) — create path lacks pre-submit target-total and current-interval confirmation

### Root cause
The market-row op cell had only the amount input, count input and confirm button;
`createBorrowTask` POSTed after shape validation without ever showing
amount×count target total or the current global interval on the create path
(interval was only shown in the borrow-tasks settings row).

### Changes
- `frontend/index.html` op cell (~1709) — added a `<div class="borrow-op-preview"
  id="borrow-preview-{symbol}">` (a div — does not change the 2-input / 1-button
  counts asserted by item 62).
- New `renderBorrowPreview(symbol)` — projects asset, single amount, success
  count, `amount×count` target total (via the existing BigInt `multiplyDecimalString`,
  no float) and the current global interval from the already-loaded
  `state.borrowSchedulerSettings` (unloaded → honestly marked). Display-only; no
  new task state machine, no browser scheduling/signing.
- New `renderBorrowPreviews()` — refreshes all rendered rows after
  `loadSchedulerSettings`.
- `attachRowHandlers` — renders the preview once per bound row (runs in the
  self-check mock too) and binds `input` events (real DOM) to refresh on typing.
- `init` — `loadSchedulerSettings()` on startup so the global interval is
  available in the market view (failure is retried on borrow-view entry).
- `__appHelpers` — exposes `renderBorrowPreview` for the self-check.

### Tests / result
- `frontend/self-check.js` item 62 — extended to assert each op cell contains
  `id="borrow-preview-{sym}"` (no input/button guard changed).
- New item 62b — loads settings (`MOCK_SETTINGS_DEFAULT`, interval `5`), types
  `12.5` × `3`, calls `renderBorrowPreview('AUSDT')` and asserts the preview
  contains asset `A`, `12.5`, `成功 3 次`, `目标总量`, `37.5` (BigInt, no float),
  `当前全局间隔` / `5 秒`; asserts the preview contacts/signs no Binance; and
  that partial input (count empty) drops back to the hint (no half total). Mock
  `getElementById` regex extended with `preview`.
- `node frontend/self-check.js` → `全部自检通过` (exit 0). No new timer (the
  settings load is one-shot GET, already on the fetch-method whitelist) and no
  timer/fetch-method guard was loosened.

---

## F3 (P1) — crash-orphaned pending attempt never enters bounded reconciliation

### Root cause
`list_due_reconciliations` requires `outcome='resolved' AND result_category='unknown'
AND reconcile_next_at_us IS NOT NULL`. A crash orphan (an attempt whose
`insert_pending_attempt` committed but whose `resolve_attempt` never ran because the
process died) stays `outcome='pending'` with `reconcile_next_at_us=NULL`, so it is
never returned by `list_due_reconciliations` and never reconciled. Startup recovery
only re-marked the task blocked. The existing test only asserted `blocked`.

### Changes (`backend/borrow_tasks/store.py`, `domain.py`)
- Startup recovery (`__init__`, after the existing marker recovery) — idempotently
  transitions every `outcome='pending'` attempt into the bounded reconciliation
  schedule as a response-less unknown:
  `outcome='resolved'`, `result_category='unknown'`,
  `reason='crash_orphan_responseless'`, `finished_at_us = COALESCE(NULL, now)`
  (recovery clock), `reconcile_step=0`,
  `reconcile_next_at_us = recovery_now + RECONCILE_DELAYS_SECONDS[0]·1e6`.
  Idempotent: only `outcome='pending'` rows are touched, so a second startup finds
  none and re-schedules nothing. The task's `unresolved_attempt_id` marker (set
  pre-crash by `insert_pending_attempt` and reconfirmed above) keeps it blocked
  until reconciliation resolves it.
- `resolve_reconciliation_success` — also finalizes the attempt row
  (`outcome='resolved'`, `finished_at_us = COALESCE(finished_at_us, now_us)`) so a
  formerly-pending orphan is not left dangling after reconciliation proves success.
  `result_category` stays `'unknown'` (audit distinguishes history-inferred success
  via `reason='reconciled_unique_txid_match'`); the task's `latest_result_category`
  becomes `'success'` as before.
- `domain.py` — `REASON_CRASH_ORPHAN_RESPONSELESS = "crash_orphan_responseless"`.
- No second POST, no force-clear, no retry-anyway: the orphan is recovered into the
  existing `_reconcile_pass`, which still requires a unique CONFIRMED match passing
  `attribution_is_unique` to credit success; no-match / multiple-candidate /
  cross-task ambiguity / five-reads-exhausted all stay blocked.

### Tests / result
- `backend/tests/test_borrow_store.py` (4 new):
  1. `test_restart_orphan_pending_enters_reconciliation_schedule` — after restart
     the orphan is `resolved/unknown/crash_orphan_responseless`, step 0,
     `reconcile_next_at_us = finished + 5s`, listed due at/after that time, still
     blocked + ineligible.
  2. `test_restart_orphan_reconciliation_success_finalizes_and_counts` — unique
     match credits success, marker cleared, row finalized (`outcome`,
     `finished_at_us` kept, `tran_id` + `reason` recorded).
  3. `test_restart_orphan_no_match_exhausts_stays_blocked` — five no-match reads →
     terminal exhaustion, still blocked + ineligible.
  4. `test_restart_orphan_recovery_is_idempotent` — second startup does not reset
     the schedule; exactly one attempt row.
- `backend/tests/test_borrow_scheduler.py` (1 new):
  `test_restart_orphan_reconciles_via_tick_with_no_second_post` — a crash orphan is
  recovered at startup and a later `tick` proves a unique match via the
  loan-record GET (`reconcile_calls == 1`) with **zero** `executor.execute`
  (`exe.calls == []`) — the unresolved marker blocks eligibility so the orphan
  never re-enters dispatch.
- Existing fail-closed test `test_restart_fail_closed_blocks_pending_attempt` still
  passes (marker survives, ineligible).

## Verification summary (real fake-only)

| Command | Result |
| --- | --- |
| `pytest test_borrow_store test_borrow_scheduler test_borrow_api test_live_borrow_executor -q` | **143 passed** |
| `pytest test_binance_signing test_portfolio_margin_borrow_client test_live_borrow_executor test_borrow_store test_borrow_scheduler test_borrow_api test_config test_private_client test_private_account_v1 test_service_health -q` | **330 passed** |
| `pytest backend/tests -q` | **629 passed** |
| `node frontend/self-check.js` | `全部自检通过` (exit 0) |
| `python3 -m py_compile …` | exit 0 |
| `git diff --check` | clean (exit 0) |

Full real outputs are appended to `60-test-output.txt` (section cited above).

## Status / handoff

- New committed fingerprint: **pending bookkeeper commit** (the executor did not
  commit). A genuinely fresh reviewer session must re-run formal review-1 against
  the new committed fingerprint; this report claims no review and no acceptance.
- The four bookkeeping files (`status.json`, `70-handoff.md`,
  `30-review-1.bookkeeper-intake.md`, `ACTIVE.json`) carry an external
  operator/bookkeeper `review-1 freshness bookkeeping correction` that re-frames
  the formal rework count; it is not part of this fix-4 execution and is flagged
  for the bookkeeper only.
- Stopping for bookkeeper intake.

---

# Task C — Review-1 REWORK Fix 5 Report (BK-R1-FIX4-001 / BK-R1-FIX4-002 intake closure)

Run at 2026-07-21 13:25:42 CST by the original Task C implementer / fix-4 author
(claude_glm / zhipu_glm / glm-5.2[1m]), single executor session, continuing the
same registered Claude-GLM terminal. This round closes the two residual P1 gates
from the bookkeeper fix-4 intake (`40-fix-report.bookkeeper-audit.md`). Formal
review `rework_count` remains `1`; no new committed fingerprint was created.
Contract compliance identical to fix-4: no real/authenticated/production-
reachable Binance request (fake/recording transport + dummy credentials only);
no `.env` / key file / cookie / credential store / expanded alias environment
read; no second POST, no hidden retry, no retry-anyway / force-clear route added;
no exact-path / HMAC / urlopen / import / UI guard weakened; no commit/push/merge,
no model dispatch.

## BK-R1-FIX4-001 (P1) — create path POSTs before the loaded current interval is confirmed

- **Finding:** `renderBorrowPreview` already wrote「当前全局间隔未加载」when
  `state.borrowSchedulerSettings` was absent, but `createBorrowTask()` still
  POSTed `/api/borrow-tasks` immediately. The startup `loadSchedulerSettings()`
  is a fire-and-forget (un-awaited) one-shot same-origin GET, so a user could
  confirm a task before the first GET completed or after it failed — creating an
  immediately-schedulable task without confirming the real current interval
  (violates AC #12/#13「创建前确认当前全局间隔」).
- **Root cause:** the preview's interval-availability predicate and the create
  gate used different logic; only the preview guarded on a loaded interval,
  while the create path validated amount/count but never the interval.
- **Changed files:**
  - `frontend/index.html`:
    - new `currentIntervalSeconds()` — single source of truth: returns the
      normalized interval string only when settings are loaded AND
      `interval_seconds` is a positive-decimal string, else `null`. Preview and
      create gate share this one predicate, so「shown interval」==「confirmed
      interval」.
    - `createBorrowTask()` fail-closes BEFORE amount/count validation:
      `if (currentIntervalSeconds() === null) return { ok:false, error:'当前全
      局调度间隔尚未加载…' }` — zero task POST when the interval is
      missing/failed.
    - `submitBorrowTask()` (op-cell entry) re-projects `renderBorrowPreview()`
      before POST, so asset / amount / count / BigInt target-total / real current
      interval match the input about to be submitted.
    - `renderBorrowPreview()` sources the interval from `currentIntervalSeconds()`
      (loaded → real seconds; unloaded → honest「未加载」label).
    - `__appHelpers.clearBorrowSchedulerSettings` test seam forces the unloaded
      state for the self-check.
  - `frontend/self-check.js`: new item 66b (negative + load-failure + positive).
- **Tests** (`frontend/self-check.js` item 66b):
  - negative (settings cleared): `createBorrowTask` returns `ok:false` whose
    error mentions「间隔」and the `/api/borrow-tasks` POST delta is 0; the
    `submitBorrowTask` entry first re-projects the preview (label contains
    「未加载」) then fail-closes with zero POST.
  - load-failure (settings GET → 503): after a failed reload the state stays
    unloaded, so create is still `ok:false` with zero POST.
  - positive (load interval=5): preview shows「当前全局间隔 5 秒」; create
    `ok:true` with exactly one `/api/borrow-tasks` POST.
  - the item restores the item-66 post-state, so items 67+ are unaffected.
- **Result:** 97 self-check items pass (incl. the new 66b); items 62/62b/63/64/
  65/66 are unchanged. No new timer, browser scheduling, signing, or Binance/
  foreign request added; the startup one-shot same-origin GET is retained; no
  existing fetch-method / timer / same-origin / BigInt / op-cell guard loosened.

## BK-R1-FIX4-002 (P1) — startup recovered-orphan count regressed 1 → 0

- **Finding:** fix-4 transitions a crash-orphaned `pending` attempt to
  `resolved/unknown/crash_orphan_responseless` at store construction, but
  `count_pending_orphan_attempts()` counted only `outcome='pending'`. So after
  restart the sanitized `recovered_orphan_blocker_count` (emitted by
  `server.run()` after store construction) dropped from 1 to 0 even though the
  task was still blocked — losing the D7/ADR-006 startup-recovery evidence.
  (Reproduced in the audit: `before_restart_pending_count=1`,
  `after_restart_recovered_orphan_count=0`, `after_restart_task_blocked=True`.)
- **Root cause:** the count measured a bare `outcome` scan instead of「tasks
  currently blocked by a crash orphan」, so the pending→recovered transition
  zeroed it while the blocker persisted.
- **Changed files:**
  - `backend/borrow_tasks/store.py` — `count_pending_orphan_attempts()` now
    counts tasks whose CURRENT `unresolved_attempt_id` marker points at an
    attempt that is either still `pending` (freshly dispatched, unresolved) OR
    recovered into a response-less unknown
    (`reason='crash_orphan_responseless'`). Counting by the task's current
    marker — not a bare outcome scan — keeps the count stable across the
    pending→response-less-unknown transition and across a second (idempotent)
    restart, returns to 0 only when reconciliation clears the marker, and does
    not re-count historical resolved-but-still-in-ledger orphans (their task
    marker was cleared). Only a sanitized integer is returned; no asset /
    amount / txId / credential / private response.
- **Tests** (`backend/tests/test_borrow_store.py` —
  `test_count_pending_orphan_attempts_covers_recovered_orphan_lifecycle`):
  - s1 inserts an orphan `pending` blocker → count 1; close.
  - s2 reopen (first recovery): count 1.
  - s3 reopen (second, idempotent): count 1.
  - advance the orphan attempt through its bounded schedule (5 reads): count
    still 1 (no-match exhaustion retains the marker).
  - create task B, insert a pending, `resolve_reconciliation_success(B)`: B is
    not counted, count still 1 (B's marker cleared; A still blocks).
  - s4 reopen, reconcile A to a unique match (success): A's marker cleared →
    count 0.
  - the pre-existing `test_count_pending_orphan_attempts_reports_crash_orphans`
    still passes (count 0 before, 1 after `insert_pending_attempt`).
- **Result:** the store suite (47 store tests), the scheduler/service/api/
  executor/service_health suites, and `backend/tests` (630) pass. `server.py`'s
  event field name (`recovered_orphan_blocker_count`) is unchanged; the
  +5/+15/+60/+300/+900s schedule, unique-match, cross-task attribution gate,
  418/re-arm, zero-second-POST, and no-force-clear / retry-anyway behaviors are
  unchanged.

## Source / test files changed (fix-5 scope only)

- `frontend/index.html` — BK-R1-FIX4-001.
- `frontend/self-check.js` — BK-R1-FIX4-001 self-check item 66b.
- `backend/borrow_tasks/store.py` — BK-R1-FIX4-002 count semantics.
- `backend/tests/test_borrow_store.py` — BK-R1-FIX4-002 lifecycle test.

Carried-over fix-4 working-tree changes (not re-touched this round):
`backend/borrow_tasks/domain.py`, `backend/tests/test_borrow_scheduler.py`, and
the fix-4 portions of `store.py` / `test_borrow_store.py` / `index.html` /
`self-check.js`. `backend/app/server.py` is unchanged.

## Verification summary (real fake-only, fix-5)

| Command | Result |
| --- | --- |
| `pytest test_borrow_store test_borrow_scheduler test_borrow_api test_live_borrow_executor test_service_health -q` | **158 passed** |
| `pytest test_binance_signing test_portfolio_margin_borrow_client test_live_borrow_executor test_borrow_store test_borrow_scheduler test_borrow_api test_config test_private_client test_private_account_v1 test_service_health -q` | **331 passed** |
| `pytest backend/tests -q` | **630 passed** |
| `node frontend/self-check.js` | `全部自检通过` (97 `[PASS]` items, exit 0) |
| `python3 -m py_compile …` | exit 0 |
| `git diff --check` | clean (exit 0) |

Full real outputs appended to `60-test-output.txt` (「Fix-5 intake closure」
section).

## Status / handoff

- New committed fingerprint: still **pending bookkeeper commit** (the executor
  did not commit). Formal `rework_count` remains `1`. This report claims no
  review and no acceptance; a genuinely fresh reviewer session must re-run
  formal review-1 against the new committed fingerprint.
- The externally-modified-not-by-this-executor bookkeeping files (`status.json`,
  `70-handoff.md`, `30-review-1.bookkeeper-intake.md`, `ACTIVE.json`,
  `task-C-bookkeeper-fix-4.dispatch.md`) remain flagged for the bookkeeper only.
- Stopping for bookkeeper intake of fix-5.

---

# Task C — Review-1 REWORK Micro Fix-6 Report (BK-R1-FIX5-001 stale loaded→503 interval)

Run at 2026-07-21 13:52:45 CST by the original Task C implementer / fix-4 / fix-5
author (claude_glm / zhipu_glm / glm-5.2[1m]), single executor session, continuing
the same registered Claude-GLM terminal. Closes the one narrow P1 residual from the
bookkeeper fix-5 intake (`40-fix-report.bookkeeper-audit.md` Fix-5 addendum). Formal
review `rework_count` remains `1`; no new committed fingerprint was created. Contract
compliance identical to fix-4/fix-5: no real/authenticated/production-reachable
Binance request (fake/recording transport + dummy credentials only); no `.env` / key
file / cookie / credential store / expanded alias environment read; no second POST,
no hidden retry, no retry-anyway / force-clear; no exact-path / HMAC / urlopen /
import / UI guard weakened; no commit/push/merge, no model dispatch.

## BK-R1-FIX5-001 (P1) — stale cached interval survives a failed settings refresh

- **Finding:** `loadSchedulerSettings()` assigned the new settings document on a
  successful GET, but its `catch` branch only displayed an error and left
  `state.borrowSchedulerSettings` untouched. So after「成功加载 interval=5，再刷新
  503」, `currentIntervalSeconds()` still returned `"5"` and `createBorrowTask()`
  POSTed — a known-failed refresh kept authorizing creation from a stale cached
  value, violating AC #12「当前间隔确认」and the fix-5 prompt's「加载失败零 POST」.
  The fix-5 self-check cleared settings manually before simulating 503, so it did
  not cover the loaded→failed transition.
- **Root cause:** the GET success path and the GET failure path were asymmetric —
  success overwrote the cache, but failure preserved it, so the「current interval」
  could reflect a stale value instead of the most recent GET outcome.
- **Changed files:**
  - `frontend/index.html` — `loadSchedulerSettings()` `catch` branch now sets
    `state.borrowSchedulerSettings = null` (invalidating the stale cache) before
    showing the error and before `renderSchedulerSettings()` / `renderBorrowPreviews()`
    re-render the unloaded state. One surgical line; no new timer, browser
    scheduling, signing, or Binance/foreign request; the startup one-shot same-origin
    GET is retained.
  - `frontend/self-check.js` — item 66b phase 4 rewritten.
- **Tests** (`frontend/self-check.js` item 66b phase 4, **no `clearBorrowSchedulerSettings`
  first**):
  - keep the successfully-loaded `interval=5` from the positive phase, then set the
    GET to 503 and call `loadSchedulerSettings()`;
  - assert `getBorrowSchedulerSettings() === null` (stale cache invalidated — this
    assertion fails without the code fix);
  - assert the preview re-renders to the「未加载」label;
  - assert `createBorrowTask` returns `ok:false` whose error mentions「间隔」and the
    `/api/borrow-tasks` POST delta is 0.
  - the initial-unloaded negative phase, the unloaded-`submit` phase, and the
    successful-load positive phase are preserved unchanged.
- **PUT-failure path intentionally unchanged:** `submitSchedulerInterval()`'s `catch`
  keeps the prior cached value, because a failed PUT means the server value did not
  change, so the prior cached value remains the legitimate current value. Only the
  GET failure path invalidates, because a failed GET can no longer confirm the
  current interval.
- **Result:** 97 self-check items pass (incl. the rewritten 66b); the full backend
  suite is re-run only for regression confirmation (no backend file touched this
  round): `test_borrow_store` 47 passed, `backend/tests` 630 passed, `py_compile`
  exit 0, `git diff --check` clean. All fix-4/fix-5 backend behavior and every
  fetch-method / timer / same-origin / BigInt / op-cell guard are preserved.

## Source / test files changed (micro fix-6 scope only)

- `frontend/index.html` — `loadSchedulerSettings()` GET-failure invalidation.
- `frontend/self-check.js` — item 66b phase 4 (loaded→503, no clear seam).

No backend file was modified. Existing evidence in this report and in
`60-test-output.txt` was not rewritten; this round only appends.

## Verification summary (real fake-only, micro fix-6)

| Command | Result |
| --- | --- |
| `node frontend/self-check.js` | `全部自检通过` (97 `[PASS]` items, exit 0) |
| `pytest backend/tests/test_borrow_store.py -q` | **47 passed** |
| `pytest backend/tests -q` | **630 passed** |
| `python3 -m py_compile backend/borrow_tasks/*.py backend/app/server.py backend/config.py` | exit 0 |
| `git diff --check` | clean (exit 0) |

Full real outputs appended to `60-test-output.txt` (「Micro fix-6」section).

## Status / handoff

- New committed fingerprint: still **pending bookkeeper commit** (the executor did
  not commit). Formal `rework_count` remains `1`. This report claims no review and
  no acceptance; a genuinely fresh reviewer session must re-run formal review-1
  against the new committed fingerprint.
- Stopping for bookkeeper intake of micro fix-6.

当前 Session ID: 358ab38a-1631-4cfa-869b-19ab824ff5b8 (Claude Code harness session id read from the transcript path; provider-native GLM session id is not separately exposed by this runtime)
Session ID 来源: transcript_path
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.md
本地北京时间: 2026-07-21 13:52:45 CST
下一步模型: bookkeeper
下一步任务: intake micro fix-6, independently rerun tests, and create a new committed fingerprint only if every gate closes

---

## Fix-7 (review-2 bounded repair — P1-1 / P1-2 / P1-3)

- Stage: `2026-07-real-borrow-boundary-c-v1`.
- Executor: `claude_glm` / provider identity `zhipu_glm` / `glm-5.2[1m]` — the
  original Task C implementer/fix author, single executor session, no
  model/adapter relay (HARNESS-EXECUTOR-CONTRACT v1).
- Reviewed fingerprint (the verdict this repair closes):
  `87c19273c3f488cf6d9ca80f8541704bb198cb81:29f0f587f3ef0dcc01261fa84047ff56fdbf717dcaa7cf20dddb13495229c162`
- Source review: `50-review-2.md` (its final JSON object is the raw verdict).
- Repair prompt: `task-C-review-2-fix-7.prompt.md`.
- Dispatch receipt: `task-C-review-2-fix-7.dispatch.md` (prepared by the human
  operator; this executor did NOT edit it — it is outside the allowed-files
  list). Anti-relay markers verified before editing
  (`fix_prompt_verbatim_prefix=PASS`, `anti_relay_marker=PASS`,
  `human_operator_dispatch=PASS` — recorded in `60-test-output.txt`).
- Real fake-only verification outputs (append-only): `60-test-output.txt`,
  section **Fix-7 (review-2 bounded repair) — real fake-only verification
  output**.

### Contract compliance (self-attested, executor session only)

- Single executor; no other model session or adapter command was called,
  launched, or dispatched. No `ESCALATED`.
- No real / authenticated / production-reachable Binance request; every
  transport exercise used injected fake/recording transport + dummy
  credentials.
- No `.env` / key file / cookie / credential store / signing-key material was
  read or logged.
- No second POST, no hidden retry, no retry-anyway / force-clear route added;
  the frozen endpoint, signer, credential, retry, reconciliation, and result
  contracts are unchanged.
- No commit / push / merge / deploy.
- The two nonblocking P3 observations (`raw_body` retained in memory; missing
  dedicated borrow variables in `.env.example`) were NOT addressed — they are
  explicitly out of scope for this bounded safety fix.
- File boundaries respected: the diff touches only the review-2 allowed-files
  list (table below). The raw review (`50-review-2.md`) was not rewritten or
  hidden. **One file-boundary conflict is documented below (command 3); it was
  NOT resolved by editing a forbidden file.**

### Source / test files changed (fix-7 scope only)

| File | Role |
| --- | --- |
| `backend/borrow_tasks/domain.py` | P1-1: `MIN_INTERVAL_SECONDS=Decimal("2")` constant + parser floor |
| `backend/services/live_borrow_executor.py` | P1-2: classify every 2xx first, every 5xx stays unknown, `known_rejection` only on a definite 4xx |
| `backend/borrow_tasks/store.py` | P1-3: recheck `live_authorized==1` inside the same atomic `insert_pending_attempt` transaction |
| `backend/tests/test_borrow_domain.py` | P1-1 regression: sub-floor reject + 2-second boundary accept |
| `backend/tests/test_borrow_scheduler.py` | P1-1 collateral (`"1"->"2"` + clock re-baseline) and P1-3 live-mode dispatch tests |
| `backend/tests/test_borrow_api.py` | P1-1 collateral (`"1"->"2"`) + new sub-floor `invalid_interval` static case |
| `backend/tests/test_borrow_store.py` | P1-1 collateral (`"0.5"->"2.5"`) + P1-3 `live_gates` block test |
| `backend/tests/test_live_borrow_executor.py` | P1-2 regression: 2xx/5xx with a known code -> unknown; 4xx known codes stay `known_rejection`; one-POST-only |
| `frontend/index.html` | P1-1 UI copy: drop the 0.5 example, state the >= 2 floor |
| `frontend/self-check.js` | P1-1 self-check: PUT `"2.5"` ok + PUT `"0.5"` -> 400 `invalid_interval` |
| `schemas/api/borrow-tasks/scheduler-settings.schema.json` | P1-1 output contract: `interval_us` minimum `1` -> `2000000` |

### Finding -> change -> test mapping

#### P1-1 — parser has no product minimum and accepts 0.5s (`domain.py:175`)

- **Root cause.** `parse_interval_seconds` capped only at one microsecond; it
  accepted `"0.5"`/`"1.999"`. `00-task.md:35-37` and
  `12-development-breakdown.md:514,545-553` freeze a 2-second shared-IP
  capacity floor (`ceil(60 / (0.5 * 6000 / 100)) = 2`); a sub-floor cadence
  risks a shared-IP 429/418 ban that would also take down the read-only
  snapshot channel.
- **Changes.**
  - `backend/borrow_tasks/domain.py:108-117` — added
    `MIN_INTERVAL_SECONDS = Decimal("2")` / `MIN_INTERVAL_US = 2_000_000` with
    a comment deriving the floor from the archived POST weight (100) and the
    6000/min shared per-IP budget reserving half for reads/reconciliation.
  - `backend/borrow_tasks/domain.py:186-216` — `parse_interval_seconds`
    docstring now states the 2-second floor; after the microsecond check it
    raises `invalid_interval` (`interval_seconds must be >= 2 (frozen shared-IP
    capacity floor)`) when `seconds < MIN_INTERVAL_SECONDS`. `1.999`/`0.5`/`1`
  fail; `2`/`2.0`/`2.5` succeed.
  - `frontend/index.html` — placeholder now `如 5（最小 2 秒）`; the local
    validation error message now `最小 2 秒` (the misleading `0.5` example is
    gone).
  - `frontend/self-check.js` — mock settings `2.5`/`2500000`; item 75 now PUTs
    `"2.5"` (ok) then PUTs `"0.5"` and asserts a 400 whose detail is exactly
    `interval_seconds must be >= 2 (frozen shared-IP capacity floor)`.
  - `schemas/api/borrow-tasks/scheduler-settings.schema.json` — `interval_us`
    minimum raised `1` -> `2000000` so the output contract matches the parser.
- **Tests.** `test_borrow_domain.py::test_parse_interval_floor_boundary`
  (2/2.0 accepted; 1.999/0.5 rejected as `invalid_interval`); the parametrized
  accept/reject lists were rebased accordingly.
  `test_borrow_api.py` gains an `invalid_interval_sub_floor` static-error case
  (`"0.5"` -> 400). `frontend/self-check.js` item 75 (above).
- **Collateral (unavoidable: `service.put_settings` routes through
  `parse_interval_seconds`).** Every scheduler/API/store test that seeded a
  sub-floor interval was rebased to the floor and its clock re-derived:
  `test_borrow_scheduler.py` (`"1"->"2"` everywhere + per-test clock
  re-baseline), `test_borrow_api.py` (`"1"->"2"` + clock), `test_borrow_store.py`
  (`"0.5"->"2.5"`). The default stays `5s`.

#### P1-2 — known-code classified before the 2xx branch (`live_borrow_executor.py:185`)

- **Root cause.** The known-code branch ran before the 2xx branch, so HTTP 200
  `{"code":-51006}` was returned as `known_rejection` (rotation-eligible)
  instead of `unknown` (blocks + reconciles). The same ordering could treat a
  5xx carrying a listed code as definitely rejected. Impact: after an
  ambiguous response the task returns to rotation and can issue a second
  borrow POST (`00-task.md:161-168`).
- **Change.** `backend/services/live_borrow_executor.py:160-238` —
  `classify_post_response` is reordered fail-closed:
  1. transport error / `http_status is None` -> `unknown`;
  2. `429` or `400`+`code=-1003` -> `rate_limited`;
  3. `418` -> `rate_limited` ban (300s, manual rearm);
  4. **every 2xx**: valid normalized `tranId` -> `success`, otherwise
     `unknown` (`malformed_2xx_no_tranid`) — including a 2xx whose body
     carries a known rejection code;
  5. **every 5xx** -> `unknown` (`possibly_accepted_5xx_{status}`) — even if
     the body carries a known code;
  6. **a definite 4xx whose code is in `{-51006,-51014,-51061}`** ->
     `known_rejection`;
  7. everything else -> `unknown`.
  The docstring (161-171) records this ordering and why it prevents an
  ambiguous 2xx/5xx from authorizing a second POST.
- **Tests.** `test_live_borrow_executor.py`:
  `test_classify_2xx_with_known_code_is_unknown` (parametrized over the three
  codes), `test_classify_5xx_with_known_code_is_unknown` (parametrized),
  `test_classify_4xx_with_known_code_remains_known_rejection` (parametrized —
  positive control preserved), and
  `test_executor_2xx_known_code_is_unknown_one_post_only` (end-to-end: a 200
  carrying `-51006` classifies `unknown`, the task blocks, and exactly one
  POST is issued).

#### P1-3 — `insert_pending_attempt` never checks `live_authorized` under `live_gates` (`store.py:583-607`)

- **Root cause.** `insert_pending_attempt` selected `live_authorized` but,
  when `live_gates=True`, never re-checked it inside the atomic transaction.
  A fake-only reproduction (`status=borrowing`, `live_authorized=0`,
  `execution_enabled=1`) created a pending attempt row, violating
  `00-task.md:155-160` and `12-development-breakdown.md:288-305,569-571`.
  Impact: a migrated/inconsistent/unauthorized persisted task could pass the
  final intent-before-send gate and reach a real POST.
- **Change.** `backend/borrow_tasks/store.py:596-603` — inside the
  `if live_gates:` block, as its FIRST statement and inside the same
  `with self._lock, self._conn:` transaction (before the settings lookup),
  recheck `if task["live_authorized"] != 1: return None`. A failed predicate
  creates zero attempt rows and zero POSTs. The docstring (571-581) records
  the durable live gates now including `live_authorized=1`.
- **Tests.** `test_borrow_store.py::test_insert_pending_live_gates_block_when_not_live_authorized`
  (a borrowing task with `live_authorized=0` + `live_gates=True` returns
  `None` and writes zero attempt rows). `test_borrow_scheduler.py`:
  `test_live_mode_unauthorized_task_dispatches_nothing` and
  `test_live_mode_authorized_task_dispatches_once` (end-to-end dispatch
  behavior at the scheduler seam).

### File-boundary conflict on command 3 (deferred — NOT resolved by editing a forbidden file)

Command 3 (`pytest backend/tests`) reports **2 failed / 648 passed**. Both
failures are in `backend/tests/test_borrow_executor.py`:

- `test_full_scenario_makes_zero_urllib_calls` (`test_borrow_executor.py:130`)
- `test_poisoned_env_secrets_never_leak` (`test_borrow_executor.py:161`)

Both die at `backend/borrow_tasks/domain.py:211` because they call
`svc.put_settings({"interval_seconds": "1"})`, and `"1"` is below the new
P1-1 floor.

**Analysis.**

1. This is the *direct, correct* consequence of P1-1. Review-2 explicitly
   requires `make 1.999/0.5 fail with invalid_interval`. These two tests use
   `"1"` (also sub-floor), so they now fail — exactly the behavior review-2
   mandates. The `"1"` is incidental scenery for the zero-network /
   no-credential-leak proofs (breakdown §3.9 / §5.1-9), not a sub-floor value
   the review asked to remove.
2. `test_borrow_executor.py` is NOT in the review-2 allowed-files list
   (`task-C-review-2-fix-7.prompt.md:25-38`). The review-2 Forbidden clause
   (`:40-41`) states "Every file not listed above". The original `00-task.md`
   allowed the wildcard `backend/tests/test_borrow_*.py`, but review-2
   deliberately narrowed the list to four named `test_borrow_*.py` files plus
   `test_live_borrow_executor.py` — and named, in the P1-1 finding
   (`:14`), exactly the files that "codify the invalid sub-floor value":
   `test_borrow_api.py:192-200`, `test_borrow_scheduler.py:155-167`,
   `index.html:964`, `self-check.js:3074-3103`. `test_borrow_executor.py` was
   not named.
3. This is a genuine inside-the-prompt contradiction: the narrowed
   allowed-files list omits the one additional test file P1-1 touches, while
   command 3 (`pytest backend/tests`) covers it.

**Decision.** This executor respected the explicit Forbidden clause and did
NOT edit `test_borrow_executor.py` (editing it would be a scope expansion,
which `:42` forbids). The diff stays entirely inside the allowed-files list.
The two failures are recorded truthfully in `60-test-output.txt`; they do not
touch any of the three P1 reproductions (commands 1 and 2 — the borrow-focused
and signing/transport suites — are fully green, including every new P1
regression test) and they do not weaken any safety property (they are the
correct rejection of a sub-floor value).

**Suggested mechanical follow-up for the bookkeeper/reviewer** (one line,
outside this executor's allowed scope): in `test_borrow_executor.py:130` and
`:161`, change `interval_seconds: "1"` to `"2"`. The zero-urllib /
no-credential-leak proofs are independent of the interval value, so this
restores command 3 to green without altering what those tests prove. If the
bookkeeper instead prefers to widen the review-2 allowed-files list and have
this executor apply the change, that is also acceptable — but it requires an
explicit scope decision from the reviewer/bookkeeper, not this executor.

### Verification summary (real fake-only, fix-7)

| Command | Result |
| --- | --- |
| `pytest test_borrow_domain test_live_borrow_executor test_borrow_store test_borrow_scheduler test_borrow_api` | **214 passed** (exit 0) |
| `pytest test_binance_signing test_portfolio_margin_borrow_client test_live_borrow_executor test_borrow_store test_borrow_scheduler test_borrow_api test_config test_private_client test_private_account_v1 test_service_health` | **345 passed** (exit 0) |
| `pytest backend/tests` | **2 failed / 648 passed** (exit 1) — see file-boundary note above |
| `node frontend/self-check.js` | `全部自检通过` (exit 0) |
| `pytest scripts/tests` | **128 passed** (exit 0) |
| `py_compile` signer/transport/live_executor/private_client/borrow_tasks/app/config | exit 0 |
| `scripts/test-validate-all-stages-compare.py --repo-root .` | 11/11 sentinel PASS (exit 0) |
| `git diff --check` | clean (exit 0) |

Full real outputs are appended to `60-test-output.txt` (Fix-7 section). No
backend or frontend file outside the allowed-files list was modified.

### Status / handoff

- All three P1 fail-closed corrections are implemented and their positive
  controls pass (commands 1 and 2). The frozen endpoint / signer / credential
  / retry / reconciliation / result contracts are unchanged; the non-catch-up
  scheduler, one-shot POST, unknown latch, cooldown/manual-rearm, migration,
  ownership, and read-only `PrivateClient` behavior are preserved.
- The single non-green item (command 3's two `test_borrow_executor.py`
  failures) is a documented file-boundary conflict, not a P1 defect, and is
  deferred to the bookkeeper/reviewer (mechanical one-line follow-up or an
  allowed-files widening).
- New committed fingerprint: still **pending bookkeeper commit** (this
  executor did not commit). Formal `rework_count` remains `1`. This report
  claims no review and no acceptance; a genuinely fresh reviewer session must
  re-run formal review against the new committed fingerprint.
- Stopping for bookkeeper intake of fix-7.

当前 Session ID: db43835f-2fd3-49cf-b877-bb9841020efa (Claude Code harness session id read from the transcript path `/Users/ark/.claude/projects/-Users-ark-Desktop-ai-code-funding-hedging/db43835f-2fd3-49cf-b877-bb9841020efa.jsonl`; provider-native GLM session id is not separately exposed by this runtime)
Session ID 来源: transcript_path
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.md
本地北京时间: 2026-07-21 22:41:33 CST
下一步模型: bookkeeper
下一步任务: intake fix-7, resolve the documented test_borrow_executor.py file-boundary conflict (apply the one-line `"1"->"2"` follow-up or widen the review-2 allowed-files list), independently rerun the eight verification commands, and create a new committed fingerprint only if every gate closes

---

## Micro Fix-8 — Explicit User-Authorized Direct Mechanical Test Repair

The user explicitly instructed Codex to make the previously isolated
`BK-R2-FIX7-001` fixture repair directly rather than dispatching the prepared
Claude-GLM Micro Fix-8 packet. This is a narrow re-enable of Codex for this
test-only change; it does not authorize Codex to self-review the stage.

Changed `backend/tests/test_borrow_executor.py` only:

- `test_full_scenario_makes_zero_urllib_calls`: scheduler fixture `"1"` to
  `"2"`, and fake-clock increments from `1_000_000` to `2_000_000` µs so all
  five queued executor categories remain exercised under the frozen 2-second
  floor.
- `test_poisoned_env_secrets_never_leak`: scheduler fixture `"1"` to `"2"`.

No product code, endpoint, signer, credentials, retry/reconciliation path,
frontend, schema or live transport behavior changed. This restores the tests'
original assertions rather than weakening them.

### Actual local fake-only verification

| Command | Result |
| --- | --- |
| `pytest backend/tests/test_borrow_executor.py` | **7 passed** |
| `pytest backend/tests` | **650 passed** |
| `node frontend/self-check.js` | all checks passed |
| `pytest scripts/tests` | **128 passed** |
| `py_compile` reviewed modules | exit 0 |
| `test-validate-all-stages-compare.py` | **11/11 passed** |
| `git diff --check` | clean |

The result is all-green code/test evidence. This report does not claim
Review-2 acceptance. Because Codex wrote this direct test repair, a later
formal Review-2 cannot use Codex; it must use a provider that did not author
implementation or fixes.

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.md
本地北京时间: 2026-07-21 23:10:25 CST
下一步模型: human operator or Anthropic final reviewer
下一步任务: bookkeeper commits the all-green direct repair and records the new fingerprint; do not mark Review-2 passed without an actual eligible review
