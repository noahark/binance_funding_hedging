# User Decisions And Contract Amendment — A+B Dispatch Freeze

This amendment is the later, more specific authority for the named parts of
`12-development-breakdown.md`. It records the user's confirmation before
implementation dispatch and does not broaden Boundary C authorization.

## 1. Create Means Start Immediately

The user confirms that confirming a market-row borrow task creates it in
`borrowing` state and makes it eligible for the backend scheduler immediately.
There is no required navigation to the task page and no second Start click.

The frontend only submits `POST /api/borrow-tasks` and renders the returned
backend state. The SQLite task service and its scheduler are the sole task and
execution authorities.

For A+B, the ordinary backend executor remains `DisabledBorrowExecutor`.
Each scheduled backend attempt therefore persists the sanitized result
`execution_disabled`; it never contacts Binance and is not a browser
simulation. The UI must label this honestly as “执行未启用”.

This confirms the creation rule in `12-development-breakdown.md` §3.3–§3.4
and supersedes the earlier general “draft/paused” A+B proposal in
`06-direction-synthesis.md` §Freeze #2. The process-level live-execution gate
and task confirmation remain mandatory Boundary C work.

## 2. Future-C Concurrency Is Not Frozen As Synchronous

The A+B disabled executor may return synchronously because it does no I/O.
That implementation convenience must not freeze a future live adapter into a
synchronous, scheduler-blocking execution model.

In A+B, the store must still persist the attempt before invoking the executor,
keep all SQLite transactions short, and resolve the attempt afterward. It must
not hold a store lock or transaction while calling the executor. Boundary C
will separately decide and review the execution/concurrency mechanism; it must
preserve the per-task at-most-one-unresolved invariant and may allow different
tasks to be in flight under short intervals.

This narrows `12-development-breakdown.md` §3.8: the word “synchronously” is
an A+B implementation detail, not an adapter contract or a C-stage commitment.

## 3. Newest-First Log Order

“借币日志” means most recently completed attempt first. A pending/unresolved
attempt is ordered by its `dispatched_at`; if that is unavailable, by
`scheduled_at`. The stable sort is therefore:

```text
ORDER BY COALESCE(finished_at, dispatched_at, scheduled_at) DESC, id DESC
```

The opaque cursor must encode the complete sort boundary (effective timestamp
and id), not only `id`. This supersedes `12-development-breakdown.md` §3.6’s
`id DESC` refinement and restores the completion-oriented intention of
`10-design.md`.

## Scope Reminder

Nothing here authorizes a Binance request, signed client, credential access,
live executor, `maxBorrowable` preflight, frequency cap, or live stress test.

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/13-user-decisions-and-contract-amendment.md
本地北京时间: 2026-07-19 16:30:21 CST
下一步模型: Claude-GLM 与 Kimi（在 dispatch-ready 通过后）
下一步任务: 按冻结 A+B 契约并行实现后端持久化任务与前端 API 接入
