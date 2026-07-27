# Replacement Development Breakdown — Sequential Pair Loop + Opening-Log Page

Author role: replacement development-breakdown author (Claude Fable 5,
anthropic). Design-only. No product code, `status.json`, `70-handoff.md`, PRD,
or source file was modified in producing this document.

Inputs read: `15-immediate-loop-and-open-log-amendment.md` (the user-approved
amendment, top authority for cadence/error-handling/log scope);
`50-review-2.md` (REWORK verdict, findings + required fixes 1–8);
`52-review-2-rework-backend.dispatch.md` / `53-review-2-rework-frontend.dispatch.md`
(superseded packets — format reference only); `12-development-breakdown.md`;
`status.json`; `backend/app/server.py` (hedge route table, lines 72–105,
563–565); `backend/hedge_open_tasks/service.py` (doc projections 79–197,
`get_logs` 408–426).

**Supersession scope.** This breakdown replaces only:

- the one-pair-per-second cadence contract (12-breakdown §3.6 "One-second
  scheduling", §4.4, and every cadence restatement in earlier files);
- packets `52`/`53`, which are **superseded before human execution and must not
  be run** (already so recorded in `status.json.model_routing`).

Everything else in `12-development-breakdown.md` remains in force unchanged:
file boundaries, signer reuse, purity guard, Decimal discipline, additive
route/schema rules, non-goals, live-gate stack, durable-before-send, and the
no-quoteOrderQty order-parameter model. All Review-2 required fixes 1–8 remain
required except where their cadence wording is replaced by the amendment
(Review-2 §必须修复 item 5's "不会阻塞下一秒开单" becomes "does not block
another task or the recovery of legacy pending legs" — the next pair of the
*same* task is now intentionally gated by the current pair's final outcome).

---

## 1. Authority stack for this rework round

1. `15-immediate-loop-and-open-log-amendment.md` — execution loop, error
   matrix, opening-log page (user-approved 2026-07-24).
2. `50-review-2.md` required fixes 1–8 — all still binding except superseded
   cadence wording. Fix 8 (main-sync SHA evidence) is **bookkeeper-only** and
   is not part of either implementation packet.
3. The surviving frozen contract (PRD §6, 12-breakdown §1.1/§3.4) — unchanged
   where not replaced above.

Nothing here authorizes real Binance access, live mode, Start, or a first live
order. No WebSocket/smooth code belongs in this delivery.

## 2. Replacement execution contract (restated, binding)

Per running immediate task, one worker owns exactly one active attempt:

```text
while task is running and scheduled_attempt_count < target_n:
    obtain complete fresh preflight facts
    atomically reserve exactly one durable attempt and increment its count
    concurrently submit the spot and perpetual legs
    persist returned order IDs; query ambiguous responses by client ID
    query both legs until each has a final exchange outcome
    persist actual fills and a task-local event log
    decide task-local next state, then begin the next loop iteration only if allowed
```

- `target_n` = planned order-pair **attempts**, not successes. Reserving an
  attempt consumes one count even if one or both submissions later fail. No
  retry/replacement may create attempt `target_n + 1`.
- Spot and perpetual POSTs of the current pair are concurrent; "sequential"
  applies only between pair 1, pair 2, … of the same task.
- The next pair of the same task never starts while that task has an unresolved
  pair. Other tasks continue independently.
- A returned `orderId` = accepted; poll to a final exchange outcome (`FILLED`,
  `REJECTED`, `EXPIRED`, `CANCELED`), retaining partial fills. Timeout / 5xx /
  no authoritative business result ≠ "no order": query by pre-persisted client
  order ID, never resend that leg.

### 2.1 Binding interpretations (pinned here so implementers do not re-decide)

- **I-1 Single entry path.** Scheduler worker, manual `fill-once`, and any
  other dispatch entry share one per-task serialization plus the same atomic
  `scheduled_attempt_count < target_n` reservation transaction. In live mode
  `fill-once` means "request one counted attempt through the task's own worker
  path" — it can never run a second concurrent pair for the same task or
  bypass the reservation. The live `fill-all` synchronous-bulk prohibition
  (12-breakdown §3.8) stands; under the sequential model `fill-all` may at
  most arm the task.
- **I-2 Counter semantics.** Both legs accepted → accepted pair → reset the
  consecutive-failure counter. A pair with a known final non-fatal failure
  (including `single_leg` whose failed leg's error is non-fatal) → counted
  attempt + increment the counter (amendment matrix rows 3–4: "the configured
  failure rule decides"). A fatal error (matrix rows 1–2) stops the task
  immediately without waiting for the threshold. An unresolved (querying) pair
  touches no counter until resolved. No fill-equality, residual, or value cap.
- **I-3 `interval_seconds` demoted.** The pair-N+1 gate is the pair-N final
  outcome, not a timer. The `interval_seconds` settings field stays in the
  wire doc (additive discipline: no field removed); Task A records its
  residual meaning (e.g., worker/poll pacing baseline) in the fix report. It
  must never allow pair N+1 before pair N is final, and must never gate
  another task.
- **I-4 Task status vocabulary gains additive `stopped`.** `stopped` = fatal
  stop (amendment matrix rows 1–2): final for that task; the operator corrects
  the cause and creates a **new** task. `paused` remains for the
  consecutive-failure threshold and manual pause. Task doc gains a nullable
  `stop_reason` alongside the existing `pause_reason`. Frontend renders the
  two states distinctly.
- **I-5 429/Retry-After.** A process-wide technical delay of new exchange
  writes for the stated wait (shared account/IP limit). It is recorded, but it
  never marks any task failed/paused/completed and never changes another
  task's business state.
- **I-6 Reconciliation is never abandoned.** A task with an unresolved pair
  stays in its query/reconciliation state and is not eligible for its next
  pair. Polling of already-persisted non-terminal legs continues even when
  Start is off, the task is done/paused/stopped, or no task is eligible
  (Review-2 fix 5). Reconciliation is bounded/rate-aware and never blocks
  another task's dispatch.
- **I-7 Preflight failure taxonomy.** Before reservation only. A preflight
  fact matching a fatal matrix row (insufficient balance/margin/available
  quantity; symbol unavailable; invalid account/position mode; filter or
  min-notional violation; other known configuration rejection) → stop the task
  with that reason + a durable log entry; no attempt. An incomplete or failed
  preflight *read* (missing price/filters/rate-limit facts, transport error) →
  fail-closed: no attempt, no POST, no exchange-failure count, no simulated
  executor call; write a log entry and let the still-running task retry its
  loop after pacing. Neither case may consume an attempt count.

## 3. Task A — Backend rework (owner: Claude-GLM / glm-5.2[1m])

### 3.1 File boundary (unchanged from packet 52)

Allowed: `backend/hedge_open_tasks/{domain.py,executor.py,scheduler.py,service.py,store.py}`;
`backend/services/{hedge_open_live_client.py,hedge_preflight_provider.py,live_hedge_executor.py}`;
`backend/app/server.py` (minimal wiring only); directly related
`backend/tests/test_hedge_*.py`, `backend/tests/test_live_hedge_executor.py`;
plus the raw report `40-fix-review-2-backend.md`.

Forbidden: `frontend/**`, `backend/services/binance_signing.py`,
`backend/borrow_tasks/**`, `docs/**`, `reports/api-samples/**`, `status.json`,
`70-handoff.md`, `50-review-2.md`, `15-immediate-loop-and-open-log-amendment.md`,
env/credential files, any real network configuration.

### 3.2 Requirements (A-1 … A-9)

- **A-1 Attempt cap (Review-2 fix 1 + amendment item 1).** `target_n` is the
  planned-attempt hard cap. Task selection and the pre-send transaction both
  check `scheduled_attempt_count < target_n` atomically; every entry point
  shares it (I-1). Failed/single-leg outcomes are never replaced.
- **A-2 Fresh-preflight-first (fix 2).** Complete fresh preflight, then one
  transaction persists the immutable attempt with that preflight's exact
  `q_common`, position mode, filters/account/balance/price/rate snapshot, both
  deterministic client IDs, and sanitized wire shapes — then POST. Preflight
  failure follows I-7 (zero attempt / POST / simulation / failure count).
- **A-3 Fail-closed preflight completeness (fix 3).** Require every approved
  factual field: account + symbol tradable status, `dualSidePosition` literal
  `false`, price, directional balance, `NOTIONAL` **or** `MIN_NOTIONAL`,
  per-constraint `MARKET_LOT_SIZE`→`LOT_SIZE` fallback, current order
  rate-limit facts. Any missing/malformed fact blocks before reservation.
  Preserve only sanitized rate headers; never secrets.
- **A-4 Wire/metadata separation (fix 4).** `endpoint` and every internal
  field leave the signed body; executor→client tests assert the exact signed
  keys for both legs.
- **A-5 Sequential per-task loop + independent reconciliation (fix 5 +
  amendment items 1–3).** Implement §2 exactly: per-task worker, terminal
  polling gates only that task's next pair, reconciliation per I-6.
  Classification: only an explicit order-absent business code confirms
  non-acceptance; auth/signature/timestamp/permission/5xx/timeout stay
  unknown-and-querying; `CANCELED`/`EXPIRED`/`REJECTED`/`FILLED` all terminal
  with partial fills retained.
- **A-6 Fill accounting (fix 6).** Persist end-to-end actual cumulative
  base/quote, weighted average, fees when available, partial fills, and
  two-leg residual; `aggregate_positions` includes any leg with positive
  actual fill regardless of literal status.
- **A-7 Error matrix (amendment §Error handling).** Implement the six matrix
  rows with I-4/I-5/I-7 semantics. Every recorded error carries a
  machine-readable category/code when Binance provides one plus a safe Chinese
  display reason. Never log API keys, signatures, or secret-bearing headers.
- **A-8 Opening-log entries projection (amendment §Opening log page).**
  Extend `GET /api/hedge-open-logs` additively with the frozen `entries`
  contract of §5. Same route, same `cursor`/`limit` params, same `next_cursor`
  mechanism; `logs`/`attempts` arrays stay unchanged. Entries include
  attempts in every state **and** task events (fatal stop, threshold pause,
  pre-`orderId` errors, 429 delay), newest-first.
- **A-9 Two-worker independence proof (amendment acceptance item 6).**
  Deterministic fake-transport regression: two running tasks proceed
  independently (task B's pair submits while task A's pair is mid-query), and
  neither task starts its own pair 2 before its pair 1 is final.

### 3.3 Required deterministic regressions (fake transports only)

Each must first reproduce the old defect, then pass:

1. `target_n=1`: success / confirmed-failed / single-leg / concurrent
   fill-once+scheduler each yield at most one attempt row and one POST pair.
2. Fresh filters changing the common grid → persisted attempt and actual wire
   both use the fresh `q_common`.
3. Any missing preflight fact → zero attempt, zero POST, zero failure count,
   zero simulated-executor call; fatal preflight facts stop the task with
   reason + log entry.
4. executor→client signed bodies contain exactly the approved keys, no
   `endpoint`.
5. Reconciliation continues with Start off / task done / none eligible, and
   never blocks another task's dispatch; 400 auth-ambiguity stays unknown;
   explicit absent code confirms failure; `CANCELED` with partial fill is
   terminal and retains the fill.
6. Cumulative quote/partial/fee/residual reach the projections; aggregation
   includes positive-fill non-`FILLED` legs.
7. Matrix rows: fatal → `stopped`+`stop_reason`; non-fatal → counter;
   threshold reached → `paused`; both-accepted resets; 429 delays writes
   process-wide without changing any task's business state.
8. The §5 `entries` projection: pagination, newest-first, `—`-able nullable
   fields, pre-`orderId` error entries, task-event entries.
9. A-9 two-task independence + per-task sequentiality.

### 3.4 Self-test commands (unchanged)

```text
.venv/bin/python -m pytest backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py backend/tests/test_hedge_open_live_client.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_executor.py backend/tests/test_hedge_purity.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
git diff --check
```

## 4. Task B — Frontend rework (owner: Claude Sonnet 5)

### 4.1 File boundary (unchanged from packet 53)

Allowed: `frontend/index.html`, `frontend/self-check.js`,
`40-fix-review-2-frontend.md`. Forbidden: everything else. A missing/renamed
backend field is escalated to the bookkeeper, never invented.

### 4.2 Requirements (B-1 … B-4)

- **B-1 Semantics rework (Review-2 fix 7, updated by amendment).**
  `target_n` renders as 计划尝试次数 (planned attempts), never "成功开单次数".
  Failure counts, pause/stop reasons, button states, and thresholds come only
  from the backend task doc (`failure_pause_threshold`,
  `consecutive_submission_failures`, `status`, `pause_reason`, `stop_reason`);
  delete the hardcoded `/3`, the legacy `>3` termination inference, and any
  disable logic that contradicts the server.
- **B-2 State display.** Render `stopped` (致命错误，任务已终止，需修正后新建任务)
  and `paused` (连续失败暂停/手动暂停) distinctly. A `single_leg` outcome shows
  单腿成交警示 + the fact that the task continues scheduling **unless** the
  backend status says paused/stopped — never a false "任务已暂停". A querying
  pair shows 查询中/等待终态.
- **B-3 开单日志 page (amendment §Opening log page).** A dedicated 开单日志
  tab beside 开单任务, following the borrow-log page's newest-first, 刷新,
  加载更多 interaction, reading the §5 `entries` array of the same-origin
  `GET /api/hedge-open-logs`. Every row renders the amendment's field list;
  unavailable fields render `—`. No browser signing, no Binance direct
  request, no new write endpoint. Chinese-first UI; Decimal strings verbatim.
  The in-task compact attempt timeline may stay, but the log page is the
  authoritative place an operator sees failures.
- **B-4 Self-check.** Extend `frontend/self-check.js` mocks/assertions to
  cover: planned-attempt labels, `stopped`/`paused`/`single_leg`/querying
  rendering, custom threshold display, the 开单日志 tab (pagination, `—`
  fallbacks, pre-`orderId` error rows, task-event rows). Not static-text-only.

### 4.3 Self-test commands (unchanged)

```text
node frontend/self-check.js
.venv/bin/python -m pytest backend/tests -q
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
git diff --check
```

## 5. Frozen additive contract (owned by A, consumed by B)

Route table unchanged. `GET /api/hedge-open-logs?cursor=&limit=` response gains
one additive array; existing `logs`, `attempts`, `next_cursor` are untouched:

```json
{
  "entries": [
    {
      "entry_id": "…",
      "entry_type": "attempt | task_event",
      "task_id": "…", "coin": "BTC", "direction": "forward",
      "attempt_seq": 3,
      "created_ts": "…Z", "submitted_ts": null, "final_ts": null,
      "q_common": "0.003", "planned_quote_amount": null,
      "spot": {"side": "BUY", "client_order_id": "…", "order_id": null,
               "status": null, "cumulative_base_qty": "0",
               "cumulative_quote_amt": "0", "avg_price": null,
               "fee_amount": null, "fee_asset": null},
      "perp": {"side": "SELL", "client_order_id": "…", "order_id": null,
               "status": null, "cumulative_base_qty": "0",
               "cumulative_quote_amt": "0", "avg_price": null},
      "residual": "0",
      "overall_result": "querying | both_accepted | filled | single_leg | confirmed_failed | task_stopped | task_paused",
      "error_category": null, "error_code": null, "error_reason_zh": null,
      "next_action": "continue_next_attempt | waiting_query | paused | stopped | completed"
    }
  ]
}
```

- `entry_type=task_event` rows (fatal stop, threshold pause, 429 delay,
  pre-reservation preflight events) carry `null` attempt/leg fields; the UI
  renders `—`.
- Decimals are strings; timestamps ISO-8601 UTC; every nullable field must be
  `—`-renderable.
- `task_to_doc` additions: `status` may now be `stopped`; new nullable
  `stop_reason`. All previously frozen fields keep their names.
- Field names above are frozen. A change here is a bookkeeper escalation,
  never a local fix on either side.

## 6. Acceptance mapping

| Amendment requirement (15 §Replacement delivery) | Where |
| --- | --- |
| 1. one active pair per task, atomic count reservation, no bypass | A-1, I-1, tests 1/9 |
| 2. concurrent two-leg POST within a pair, client-ID reconciliation before classification | A-2/A-5, test 5 |
| 3. final-outcome polling gates only that task's next pair | A-5, I-6, test 9 |
| 4. error matrix incl. no-`orderId` durable log entry and fatal stop | A-7, I-4/I-5/I-7, tests 3/7/8 |
| 5. fill/fee/residual persistence + paginated opening-log API and UI | A-6/A-8, B-3, tests 6/8 |
| 6. deterministic two-worker independence proof | A-9, test 9 |

Review-2 fixes 1–7 map to A-1…A-6 and B-1/B-2; fix 8 stays bookkeeper-only.

## 7. Sequencing and bookkeeper notes

1. Bookkeeper records this breakdown + packets `54`/`55` in `status.json`
   (model routing unchanged: backend Claude-GLM, frontend Claude Sonnet 5),
   runs the checkpoint/dispatch-ready validation, and commits.
2. Human operator executes `54` and `55` in fresh write-capable sessions; the
   two tasks may run in parallel against §5 (frozen here); implementers stop
   for the bookkeeper without committing.
3. Bookkeeper reconciles both diffs (R4-style), reruns integration evidence,
   fixes the Review-2 P2 main-sync SHA (fix 8) itself, recomputes the
   committed fingerprint, and re-enters the required committed review gates
   (`rework_count` is 2 of 3).
4. Live mode, Start, and a first real order remain separately human-authorized
   and are out of scope for every packet.

---

当前 Session ID: 94305f00-bde4-4d80-a69e-091eddffcbe7
Session ID 来源: runtime_env (harness scratchpad path; navigation only)
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/16-replacement-development-breakdown.md
本地北京时间: 2026-07-24 14:55:04 CST
下一步模型: bookkeeper
下一步任务: record this breakdown and packets 54/55 in status.json, run checkpoint/dispatch-ready validation, then hand both packets to the human operator
