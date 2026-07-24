# Immediate Task Loop And Open-Log Amendment

## User-approved change — 2026-07-24

This amendment replaces only the immediate-mode timing rules in `00-task.md`,
`04-user-execution-policy.md`, `05-cadence-resolution.md`, `10-design.md`,
`11-adr.md`, and the Review-2 repair packets `52`/`53`. Those earlier files
remain unchanged as historical evidence. The user has explicitly approved this
replacement rule:

> Every task card is its own asynchronous process. Its opening **count** is
> sequential: one group is submitted, queried to a final outcome, and only then
> may that same task begin its next group. Within one group, spot and perpetual
> market orders are submitted concurrently. A task-local error must not stop
> another task, because another task may be operating independently (including
> a future close task).

This is not an authorization for real Binance access, live mode, Start, or a
first live order.

## Immediate-mode execution contract

For each running immediate task, one background worker owns exactly one active
attempt. Other task workers continue independently.

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

Definitions:

- `target_n` means the number of planned order-pair attempts, not the number of
  successful pairs. Reserving an attempt consumes one count even if one or both
  order submissions later fail. No retry or replacement may create attempt
  `target_n + 1`.
- Fresh preflight failure occurs before reservation. It creates no order attempt,
  no POST, and no exchange-failure count.
- A returned `orderId` means that leg was accepted. The worker must query it
  until a final exchange outcome: `FILLED`, `REJECTED`, `EXPIRED`, or
  `CANCELED`. A final non-filled order is still a handled final outcome; it must
  retain any partial fill.
- A timeout, connection failure, 5xx, or a response with no authoritative
  business result is **not** treated as no order. The worker queries by its
  pre-persisted client order ID and does not resend that leg.
- The next pair of the same task never starts while this task has an unresolved
  pair. This replaces the earlier one-new-pair-per-second rule.
- The spot and perpetual POST operations of the current pair are independent
  asynchronous operations started together. “Sequential” applies only between
  pair 1, pair 2, and so on within the same task.

## Error handling and task isolation

All recorded errors must include a machine-readable category/code when Binance
provides one, plus a safe Chinese display reason. Never log API keys, signatures,
or raw secret-bearing headers.

| Result after client-ID reconciliation | Current task action | Other tasks |
| --- | --- | --- |
| Insufficient balance, margin, or available quantity | Stop this task with a clear reason; do not start another pair. | Continue normally. |
| Symbol unavailable, account/position mode invalid, filter/min-notional error, or other known configuration rejection | Stop this task with the exchange reason; operator must correct it before a new task. | Continue normally. |
| Known non-fatal pair rejection | Record the completed attempt; apply the configurable consecutive-failure rule, then continue only when the task remains running and has counts left. | Continue normally. |
| One leg accepted and the other reaches a final error | Record a `single_leg` result and both leg facts. No automatic repair, cancel, close, or replacement. A fatal error stops this task; otherwise the configured failure rule decides whether it may take its next counted attempt. | Continue normally. |
| Timeout, 5xx, signature/auth/permission ambiguity, or no authoritative order response | Keep this task in its query/reconciliation state and do not start its next pair or resend a write. | Continue normally. |
| Exchange 429 / Retry-After | Record the event and delay new opening requests for the stated exchange wait. This is not a business stop of other tasks. | They retain their task state; their future exchange writes must still obey the same external account/IP limit. |

The last row is a technical constraint rather than a product-level global stop:
Binance can impose a shared account/IP order limit, so software cannot force a
second task's request through a stated `Retry-After`. It must not mark other
tasks failed, paused, or completed. Future close work may receive priority, but
that priority executor is outside this stage.

The existing configurable failure threshold remains. It applies only after a
pair has a known final, non-fatal failure. A direct fatal error such as
insufficient balance stops the affected task immediately; it does not wait for
three failures. A successful accepted pair resets the consecutive-failure
counter. No fill equality, residual, or value cap is introduced.

## Opening log page

Add a dedicated **开单日志** tab beside **开单任务**, following the existing
borrow-log page's newest-first, refresh, and load-more interaction. Reuse the
same-origin read-only `GET /api/hedge-open-logs` family with an additive,
cursor-paginated entry projection; do not add browser signing, a Binance direct
request, or a new unsafe write endpoint.

Each log row must show, with unavailable fields rendered as `—`:

- event time (created, submitted, and final/last-updated time as available);
- task ID, coin/symbol, direction, and attempt sequence;
- planned `q_common`, estimated/planned amount when available, and actual spot
  and perpetual base/quote amounts;
- each leg's side, `orderId`, client order ID, exchange status, cumulative
  quantity, average price, and available fee;
- overall result: querying, both accepted, filled, single-leg, confirmed
  failure, task stopped, or task paused;
- safe failure category/code and Chinese reason; and
- the task-local next action: continue next counted attempt, waiting for query,
  paused, stopped, or completed.

The log is durable audit data. It records both successes and failures, including
an error that occurred before either `orderId` was returned. The current
in-task attempt timeline may remain as a compact view, but it must not be the
only place an operator can see failures.

## Future smooth-opening common pattern

Smooth opening is still a later stage; no WebSocket code belongs in this
delivery. Its approved architectural pattern is now fixed:

1. each smooth task independently maintains current spot/perpetual price and
   order-book state from WebSocket data;
2. that task's sequential attempt loop waits for its own spread-rate, depth,
   and slippage condition;
3. it then uses the same concurrent-two-leg submission and per-pair terminal
   query flow above; and
4. it returns to waiting for its own next condition before the next counted
   attempt. Other smooth/immediate tasks remain independent.

## Replacement delivery and acceptance requirements

The previously prepared packets `52-review-2-rework-backend.dispatch.md` and
`53-review-2-rework-frontend.dispatch.md` are **superseded before human
execution**. They describe the discarded one-second cadence and must not be
run. A new breakdown and replacement packets must cover:

1. one active pair per task, atomic count reservation, and no parallel
   fill-once/scheduler bypass;
2. concurrent spot/perpetual POST only within that pair, with client-ID
   reconciliation before any error classification;
3. final-outcome polling that gates only that task's next pair, never another
   task's business state;
4. the error-classification matrix above, including a no-`orderId` durable log
   entry and task-local fatal stop;
5. actual fill/fee/residual persistence and the new paginated opening-log API
   and UI; and
6. deterministic fake-transport tests proving two task workers can proceed
   independently while neither worker starts its own pair 2 before pair 1 is
   final.

All existing Review-2 P0/P1 repair requirements remain required unless this
amendment expressly replaces their cadence wording. No automatic repair,
cancel, close, borrow, repay, transfer, or real network test is added.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/15-immediate-loop-and-open-log-amendment.md
本地北京时间: 2026-07-24 14:22:47 CST
下一步模型: bookkeeper
下一步任务: record the user-approved amendment, invalidate obsolete fix packets, then prepare a replacement breakdown and dispatch packets
