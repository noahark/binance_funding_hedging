# Design — Durable Borrow Tasks A+B

## Constraints And Chosen Shape

This is a single-user local workstation built with Python stdlib HTTP and
vanilla JavaScript. A modular-monolith borrow-task boundary is sufficient:
there is one process, one local SQLite file and no queue/service split. The
task domain must nevertheless be independent from snapshot assembly and the
future Binance adapter because scheduling/attempt invariants are materially
different from read-only market snapshots.

```text
frontend/index.html
  ↕ same-origin JSON
HTTP handler (borrow-task routes only)
  ↕
BorrowTaskService ── BorrowTaskStore (SQLite)
  ↕                         ↕
BorrowScheduler ───────── Attempt ledger
  ↕
BorrowExecutor port
  ├─ DisabledBorrowExecutor (ordinary A+B runtime)
  └─ PaperBorrowExecutor (tests only)

Future C only: separate BinanceBorrowAdapter
```

`SnapshotService`, the public-market schemas and `PrivateClient` remain
read-only and do not import the borrow-task modules.

## Domain Model

### Task

```text
id                    UUID/string identity
asset                 normalized asset symbol
amount_per_attempt    canonical decimal string
success_target        positive integer
success_count         non-negative integer
status                borrowing | paused | deleted | completed
version               monotonic optimistic-concurrency integer
latest_attempt_id     nullable
latest_result         nullable sanitized summary
created_at/updated_at ISO UTC timestamps
```

Task `deleted` is soft deletion. `completed` and `deleted` are terminal for
new schedule selection. `paused` is retained and can be restarted. A task with
an unresolved attempt is not eligible even if its visible desired status is
`borrowing`.

### Scheduler Settings

One durable record holds `interval_us`, `round_robin_cursor`,
`global_cooldown_until` and update/version timestamps. The UI accepts decimal
seconds and the backend parses it with `Decimal`, requiring only finite > 0,
then normalizes it to integer microseconds. There is no product-imposed lower
frequency bound. Actual dispatch/finish timestamps, not requested interval,
are the later frequency-analysis evidence.

On every due tick, choose the next eligible task after the cursor in stable
creation/id order; advance the cursor transactionally before dispatch. With
three eligible tasks and a 3-second interval: A → B → C → A. A tick with no
eligible task records no borrow attempt.

### Attempt And Log

An attempt is written before executor invocation:

```text
id, task_id, sequence, scheduled_at, dispatched_at, finished_at,
requested_amount, outcome, result_category, business_code, reason,
http_status, tran_id, latency_ms, effective_gap_us
```

Only a constrained result-category vocabulary and sanitized reason/code may
cross persistence/API boundaries. No request query, credential, signature,
header collection or full private response is stored.

The log endpoint reads attempts descending by `(finished_at, id)` using an
opaque cursor and bounded limit. It is an append-only audit view; task cards
read only the compact latest-result projection.

## A+B Executor Semantics

The executor interface returns a typed result rather than an HTTP object.

- `DisabledBorrowExecutor` returns `execution_disabled` without network I/O.
- `PaperBorrowExecutor` is injected by tests with scripted success, known
  rejection, rate-limit, unknown and error results.

For future C, the service—not the HTTP handler or browser—will map an actual
POST outcome. This stage models the following now so UI/storage contracts do
not need a rewrite:

| Result | A+B state effect |
| --- | --- |
| success with `tran_id` | increment success; complete at target |
| known rejection | save latest result; remain runnable |
| rate limited | save result; set global cooldown from executor result |
| unknown | mark task unresolved/blocked; no later task attempt for it |
| execution disabled | save result; do not fabricate a success |

The future C adapter must parse exchange `Retry-After`; it will be the source
of global cooldown. A+B does not call the exchange and therefore does not
invent one.

## HTTP Contract And Validation

Add a narrow local route dispatcher to `backend/app/server.py`. Its handlers
delegate to a service injected at server construction; they must not access the
database or executor directly.

Use JSON request/response helpers with explicit content type, bounded body
size, UTF-8 decode handling and deterministic JSON error shape. The server
remains localhost/same-origin. Existing GET snapshot/static behavior is
unchanged.

Define separate borrow-task JSON schemas under `schemas/api/borrow-tasks/` for
task, attempt-log page and scheduler settings. Do not add these fields to the
public snapshot schema.

## Frontend Design

The existing borrow page becomes an API client, not a task authority:

- market-row confirm creates a backend task;
- task actions call local mutation endpoints then refresh task state;
- a top settings control edits the global decimal interval;
- `借币任务` renders task filters/cards; `借币日志` renders newest-first log
  pages and a load-more action;
- latest-result summary is visible on each task card;
- no frontend task scheduler/timer, no Binance request and no secret surface.

The existing snapshot refresh timer may refresh market data as today; task
state is refreshed only through the task API under a separately designed,
bounded UI refresh policy. It is never the execution clock.

## Test Strategy

- Pure domain/store tests use `TemporaryDirectory`, SQLite and an injected
  monotonic/wall-clock pair.
- Scheduler tests advance a fake clock, assert A→B→C ordering and compare
  integer microsecond representation for fractional intervals.
- Executor tests assert zero `urllib`/Binance calls from A+B paths and cover
  each result category, cooldown, completion, restart and unresolved-attempt
  behavior.
- HTTP tests use the existing in-process server pattern; schema tests cover
  negative input and cursor pagination.
- Frontend `self-check.js` mocks every borrow-task API response and asserts
  tabs, latest result, filters, interval editing, newest-first logs and no
  direct Binance/task-timer side effect.

## Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| Fast requested intervals exceed process/network capability | log actual scheduling/dispatch times; never claim requested equals achieved |
| Restart leaves ambiguous work | durable unresolved marker; A+B paper tests; C later adds history reconciliation |
| Snapshot worker coupling delays task work | dedicated task scheduler; no snapshot imports |
| SQLite contention | single store transaction boundaries and short writes; no long network work inside a transaction |
| Sensitive execution evidence leaks | typed sanitized outcomes only; no C adapter or private payload in A+B |

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/10-design.md
本地北京时间: 2026-07-19 15:57:10 CST
下一步模型: Codex/GPT
下一步任务: 写入 ADR 并派发 Fable5 开发拆分
