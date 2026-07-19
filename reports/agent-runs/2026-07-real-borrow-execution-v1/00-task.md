# Task — Durable Borrow Tasks A+B (No Binance Write)

## Approved Scope

Implement the user-approved A+B slice of real borrow-task work on
`stage/2026-07-real-borrow-execution-v1`.

The slice replaces the accepted browser-memory fake task authority with a
backend-owned, durable local task system. It includes the global decimal
round-robin scheduler, durable attempt logs, task/log views and a test-only
paper execution seam. It deliberately sends **zero** Binance write requests.

The user-approved behavior is:

- Do not preflight `maxBorrowable`; the future borrow endpoint is the
  availability authority.
- One global frequency setting defaults to `5` seconds and accepts any positive
  decimal seconds, including `0.5`. It selects one runnable task each tick in
  stable round-robin order.
- Known result categories are persisted and shown as the task's latest result.
  In the future live adapter, known rejects remain in the rotation; a 429/418
  obeys Binance `Retry-After` globally; unknown outcomes block only their task
  for reconciliation.
- A future successful `tranId` response counts immediately once persisted;
  history is for unknown outcomes and audit, not the normal fast path.
- The task page gains a top-level `借币日志` tab with durable, newest-first,
  paginated attempt metadata.

## In Scope

### Backend — Claude-GLM ownership

- A small isolated borrow-task module: domain validation/state transitions,
  SQLite store, task service, scheduler and executor port.
- Local same-origin task and log APIs, plus scheduler-setting API, implemented
  in the stdlib HTTP server without changing snapshot endpoint semantics.
- Decimal-string money values and positive decimal interval parsing normalized
  to an integer duration; record scheduled, dispatch and completion timestamps
  so effective intervals are observable.
- `DisabledBorrowExecutor` for ordinary runtime and an injectable
  `PaperBorrowExecutor` for deterministic tests. Neither may sign or make a
  network request. A configuration value selecting a live executor must be
  rejected/not implemented in this stage.
- Append-only attempt metadata, newest-first cursor pagination, redacted
  result/error categories, durable task recovery and soft deletion.
- Backend tests for persistence/restart, round-robin, fractional interval
  representation, per-task unresolved-attempt invariant, result transitions,
  API validation/pagination and no-network/no-write behavior.

### Frontend — Kimi ownership

- Keep the approved market operation controls and task lifecycle presentation,
  but migrate task truth from `state.borrowTasks` to the new same-origin API.
- Add global interval edit/confirm at the borrow-task page top.
- Add `借币任务 | 借币日志` top-level view tabs. Task status filters remain in
  the task view; logs render newest-first pages with result/reason/timing data.
- Show the latest attempt result on every task card and API error messages
  locally. No browser timer may dispatch, simulate, sign or call Binance.
- Extend `frontend/self-check.js` with fetch mocks and UI contract assertions.

## Explicit Non-goals

- Any `POST`, `PUT`, `DELETE` or authenticated live request to Binance.
- A live signing client, API keys, credentials, a real borrow adapter, raw
  private account payloads, or a load/stress test against Binance.
- Repay, transfer, order, hedge, sell, close, WebSocket/user-data-stream or
  automatic trading behavior.
- Using `maxBorrowable` as a task preflight or polling it on the scheduler path.
- Repairing the two user-deferred P3 fake-UI findings.
- Changing `public-market-snapshot/v1` or its existing routes/schema.

## Proposed Local API Contract

```text
GET    /api/borrow-tasks
POST   /api/borrow-tasks
POST   /api/borrow-tasks/{id}/start
POST   /api/borrow-tasks/{id}/pause
POST   /api/borrow-tasks/{id}/delete
POST   /api/borrow-tasks/{id}/edit

GET    /api/borrow-logs?cursor=<opaque>&limit=<bounded>
GET    /api/borrow-scheduler-settings
PUT    /api/borrow-scheduler-settings
```

All local mutation endpoints accept/return explicit versioned JSON documents;
invalid/missing JSON, unsupported methods, non-positive/non-finite intervals,
unknown task IDs and invalid state transitions return deterministic 4xx JSON.
The detailed schema names/field shapes are designed before implementation and
must not reuse the public-market snapshot schema.

## Acceptance Criteria

1. Restarting the backend preserves tasks, scheduler setting, soft-deletion,
   attempt logs and latest-result state.
2. A global `3`-second setting dispatches A/B/C as A→B→C→A on a deterministic
   clock; a `0.5`-second setting is accepted and its actual timing is logged.
3. A scheduler tick never does a `maxBorrowable` request, a Binance request, or
   a browser-originated task action in A+B.
4. Each task has at most one unresolved attempt; other tasks can progress;
   unknown outcome stays blocked until a test executor resolves it.
5. Known paper result categories update task latest result and create exactly
   one sanitized log row. A successful paper `tranId` increments progress and
   completion stops later attempts.
6. Task view supports current filtering/start/pause/delete/edit semantics over
   backend state; log view is newest-first and paginated.
7. All existing backend tests and frontend self-check remain green; added tests
   prove zero Binance network/write activity and no credentials in logs/API.

## Human Gates

- Boundary C—the only slice allowed to add a Binance borrow POST—requires a
  separate stage, user approval and a new official/raw-contract review.
- Any live stress/frequency test, including `0.5` seconds, is Boundary C work
  and requires a separate explicit user authorization. A+B can only exercise
  the same cadence using the paper executor.

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/00-task.md
本地北京时间: 2026-07-19 15:57:10 CST
下一步模型: Codex/GPT
下一步任务: 完成 A+B 架构设计与 ADR，再派发 Fable5 开发拆分
