# Fix-4 Bookkeeper Intake Audit — Two Residual P1 Gates

## Disposition

Claude-GLM's fix-4 delivery respected its source/test file boundary and its
reported fake-only commands are internally consistent. Independent bookkeeper
verification passed the four-file targeted backend suite (`143 passed`), the
frontend self-check, and `py_compile`.

F1 is closed. F2 and F3 each retain one contract-breaking residual, so fix-4
is not ready for an evidence commit or a new review fingerprint. These are
intake corrections within formal review-1 rework round 1; `rework_count` stays
`1`.

## Closed Finding

### F1 — closed

The three stale static statements claiming no real borrow / all results disabled
are gone. The page retains the accurate browser boundary (no scheduling,
simulation, signing or Binance request), preserves the runtime
`execution_disabled` result label, and projects live/disabled plus Start/Stop
state through the execution badge. The self-check retains its existing guards
and adds narrow stale-copy assertions.

## Residual Findings

### BK-R1-FIX4-001 (P1) — create can POST while the current interval is unknown

Frozen sources require the UI to show and confirm the **current global
interval before create** (`00-task.md` scope and AC #12, design D9, breakdown
section 6). The new preview renders the real interval only when
`state.borrowSchedulerSettings` is already populated. Otherwise it explicitly
shows `当前全局间隔未加载`, while `createBorrowTask()` still calls
`POST /api/borrow-tasks` without checking scheduler-settings availability.
Startup calls `loadSchedulerSettings()` asynchronously without awaiting it, so
an immediate click or a GET failure can create an immediately runnable task
without the required interval confirmation.

Required closure: fail closed before POST unless a valid loaded
`interval_seconds` is available, render the actual interval before submission,
and add a self-check proving settings-unavailable means zero task POST. Do not
add a timer, browser scheduler, signing, or external fetch.

### BK-R1-FIX4-002 (P1) — startup recovered-orphan lifecycle count regressed to zero

Frozen D7 / ADR-006 requires startup to report recovered orphan blockers.
Fix-4 transitions each pending attempt to `resolved/unknown` inside
`BorrowTaskStore.__init__`. The existing
`count_pending_orphan_attempts()` still counts only `outcome='pending'`, and
`server.run()` calls it after construction. A real temporary-SQLite
reproduction produced:

```text
before_restart_pending_count= 1
after_restart_recovered_orphan_count= 0
after_restart_reason= crash_orphan_responseless
after_restart_outcome= resolved
after_restart_task_blocked= True
```

The orphan remains correctly blocked and scheduled, but lifecycle evidence now
reports zero. Required closure: make the sanitized count represent current
orphan-blocked tasks across the pending-to-response-less-unknown transition and
across a second restart, then return to zero after successful reconciliation.
The count must remain non-secret and must not weaken reconciliation or add any
write retry.

## Independent Verification

```text
python3 -m pytest backend/tests/test_borrow_store.py backend/tests/test_borrow_scheduler.py backend/tests/test_borrow_api.py backend/tests/test_live_borrow_executor.py -q
143 passed in 17.93s

node frontend/self-check.js
全部自检通过

python3 -m py_compile backend/services/binance_signing.py backend/services/portfolio_margin_borrow_client.py backend/services/live_borrow_executor.py backend/services/private_client.py backend/borrow_tasks/*.py backend/app/server.py backend/config.py
exit 0
```

No network or credential source was used. No implementation file was modified
by the bookkeeper.

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.bookkeeper-audit.md
本地北京时间: 2026-07-21 12:54:57 CST
下一步模型: human operator → Claude-GLM / glm-5.2[1m]
下一步任务: execute task-C-bookkeeper-fix-5.prompt.md, close BK-R1-FIX4-001/002, append fake-only evidence, and stop for bookkeeper intake

---

## Fix-5 Intake Addendum — One Stale-Interval Residual

Fix-5 closes the store lifecycle-count residual and correctly blocks the initial
unloaded-settings path. Independent verification passed the five-file targeted
suite (`158 passed`), all 97 frontend self-check items, and `py_compile`.

One narrow P1 remains in BK-R1-FIX4-001. `loadSchedulerSettings()` assigns the
new document on success, but its `catch` branch only displays an error and does
not invalidate `state.borrowSchedulerSettings`. Therefore this sequence remains
possible:

```text
successful GET -> cached interval_seconds="5"
later GET -> HTTP 503
state.borrowSchedulerSettings -> still "5"
currentIntervalSeconds() -> "5"
createBorrowTask() -> POST allowed
```

The fix-5 self-check clears settings manually before simulating 503, so it does
not cover the loaded-to-failed transition. The fix-5 prompt required every
settings-load failure to fail closed with zero task POST, and frozen AC #12
requires confirmation of the current interval. A known failed refresh cannot
continue authorizing creation from a stale cached value.

Required micro closure: invalidate scheduler settings in the GET failure path;
change item 66b to start with a successfully loaded interval, then return 503
without calling the clear seam, and prove zero task POST plus an unloaded/error
preview. Preserve the one-shot GET, existing guards, and all fix-4/fix-5 backend
behavior. This remains formal review-1 rework round 1; `rework_count` stays 1.

The implementer-authored `40-fix-report.md` also lacks the required six-line
execution footer. Fix-6 must append its micro-fix report and finish the report
with a footer sourced from the target runtime; existing evidence must not be
rewritten.

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.bookkeeper-audit.md
本地北京时间: 2026-07-21 13:34:51 CST
下一步模型: human operator → Claude-GLM / glm-5.2[1m]
下一步任务: execute task-C-bookkeeper-fix-6.prompt.md, invalidate stale scheduler settings on GET failure, add the loaded-to-503 zero-POST test, append the report footer, and stop for bookkeeper

---

## Micro Fix-6 Intake Closure — All Blocking Findings Closed

Micro fix-6 is accepted for evidence intake. The frontend GET-failure branch now
invalidates `state.borrowSchedulerSettings` before rendering; the rewritten
item 66b starts from a successfully loaded interval, performs a 503 refresh
without the clear seam, proves state becomes null, the preview becomes unloaded,
creation returns `ok=false`, and task POST delta remains zero. The implementer
report and dispatch both end with runtime-sourced six-line footers; Session ID
`358ab38a-1631-4cfa-869b-19ab824ff5b8` is explicitly sourced from the Claude
Code transcript path, while provider-native GLM identity remains unavailable.

Independent final fake-only verification:

```text
python3 -m pytest backend/tests -q
630 passed in 38.30s

node frontend/self-check.js
97 [PASS] items; 全部自检通过

python3 -m pytest scripts/tests -q
114 passed in 2.08s

python3 -m py_compile backend/services/binance_signing.py backend/services/portfolio_margin_borrow_client.py backend/services/live_borrow_executor.py backend/services/private_client.py backend/borrow_tasks/*.py backend/app/server.py backend/config.py
exit 0

git diff --check
clean
```

F1, F2, F3 and all bookkeeper residual P1 findings are closed. Optional reviewer
P3 items F4/F5 remain disclosed but are non-blocking. Formal `rework_count`
remains `1`. Product/fix evidence is ready for a local stage evidence commit and
new fingerprint; this audit does not claim review or acceptance.

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.bookkeeper-audit.md
本地北京时间: 2026-07-21 14:04:00 CST
下一步模型: bookkeeper
下一步任务: create the local fix evidence commit, compute the new standard fingerprint, then close the main-only verdict-extractor prerequisite before fresh Kimi review-1

---

## Fix-7 Intake Addendum — Product P1s Closed, One Mechanical Test Residual

Fix-7 is accepted for source-level intake on all three Review-2 P1 findings:

- the backend interval authority now rejects values below the frozen two-second
  capacity floor while preserving exact Decimal/microsecond handling;
- all 2xx responses are classified before business rejection codes, every 5xx
  remains unknown, and known rejection is restricted to the three archived
  codes on definite 4xx responses after rate-limit handling;
- `insert_pending_attempt(..., live_gates=True)` now rechecks
  `live_authorized == 1` inside the same transaction before inserting intent.

The targeted Fix-7 suite independently passes (`214 passed`). The implementer
also ran the wider signing/transport suite (`345 passed`), frontend self-check,
Harness tests (`128 passed`), py_compile, compare sentinel (`11/11`) and
`git diff --check`; those results are internally consistent with the changed
files and recorded raw output.

One mechanical residual remains:

### BK-R2-FIX7-001 — two zero-network fixtures still request a forbidden 1s interval

Independent execution of `backend/tests/test_borrow_executor.py` produced
exactly `2 failed, 5 passed`. Both failures occur before the tests' actual
zero-urllib/no-secret assertions because lines 130 and 161 still configure
`interval_seconds: "1"`, which Fix-7 now correctly rejects. This file was not
in the Review-2 fix prompt's allowed list, so the GLM executor correctly stopped
instead of widening scope.

The closure is deliberately mechanical and separately authorized in Micro
Fix-8: change both settings to `"2"`. The first scenario must also advance its
fake clock by `2_000_000` microseconds per iteration; otherwise it would run
only three of the five queued result categories while retaining the misleading
comment that every category was exercised. No product source change is needed.

The Fix-7 transcript-path Session ID
`db43835f-2fd3-49cf-b877-bb9841020efa` was independently verified from the
matching Claude Code JSONL metadata. The original dispatch receipt remained
`prepared`; the bookkeeper corrected it from verified transcript/report facts.

Formal `rework_count` remains `1`. No review gate, acceptance, merge,
deployment, credential access, live Binance request or live-borrow start is
authorized. After Micro Fix-8 is all green, bookkeeper will create a new
committed fingerprint and apply the user's narrow RC4 authorization to retain
the prior Kimi ACCEPT while routing directly to a correctly executed Review-2.

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.bookkeeper-audit.md
本地北京时间: 2026-07-21 22:55:21 CST
下一步模型: human operator → Claude-GLM / zhipu_glm / glm-5.2[1m]
下一步任务: execute task-C-review-2-fix-8.prompt.md, close BK-R2-FIX7-001, append fake-only evidence, and stop for bookkeeper intake
