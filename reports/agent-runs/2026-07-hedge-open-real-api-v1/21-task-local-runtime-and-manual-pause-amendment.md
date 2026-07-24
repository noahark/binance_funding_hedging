# Task-local runtime and manual-pause amendment

## User-approved change — 2026-07-24

This amendment narrows the runtime shape for immediate hedge opening. It is a
local scheduling/error-policy change only: it adds no Binance endpoint, wire
parameter, credential use, WebSocket behavior, or real-order authorization.
No public API sample is applicable because the amended facts are local process
ownership and user-selected pause policy, not external API capability.

The user explicitly selected:

> Do not add a long-lived global guardian/coordinator thread for short opening
> windows. When a task receives 429 or insufficient-balance-type failure,
> pause only that task's subprocess and wait for manual recovery; do not link
> other task subprocesses.

This amendment supersedes only the conflicting runtime/error clauses in
`15-immediate-loop-and-open-log-amendment.md`, `16-replacement-development-
breakdown.md`, and the unexecuted packet
`61-review-1-backend-r2-rework.dispatch.md`. Those files remain immutable
historical evidence. Packet 62 is the only executable repair packet.

## Binding runtime contract

There is no newly introduced permanent global coordinator/guardian for hedge
opening. A task has a bounded-lifetime local worker only while it is actively
running or reconciling its own one active pair:

```text
manual Start/recover for task T
    -> create or durably claim exactly one local worker for T
    -> T worker: preflight -> reserve pair N -> concurrent two-leg submit
                 -> query only T's two legs to terminal -> one atomic settlement
                 -> pair N+1 only when T remains running
    -> done / paused / stopped -> T worker exits
```

No runtime component may scan and synchronously query all tasks before another
task can dispatch. A one-time startup/manual recovery invocation may find a
durably pending task and launch only that task's bounded recovery worker; it
must return after the handoff and must not become a permanent scanner.

Per-task worker ownership is durable: an atomic store-level claim/attempt guard
must prevent two triggers (manual action, startup recovery, or concurrent
request) from owning or sending the same task/pair. A process restart resumes
by querying saved client order IDs only; it must never resend an existing write.

## Manual-pause and isolation contract

| Confirmed outcome after client-ID reconciliation | Current task | Other tasks |
| --- | --- | --- |
| 429 / Retry-After | Persist `paused` with a rate-limit reason and audit event; worker exits; no automatic wait/retry; manual recovery is required. It does not consume the consecutive-failure counter. | No local state, error count, pause, stop, or scheduling linkage. They may continue their own writes. |
| Insufficient balance, margin, or available quantity | Persist `paused` with the precise safe reason and audit event; worker exits; manual recovery is required. It does not wait for the consecutive-failure threshold. | No local state, error count, pause, stop, or scheduling linkage. |
| Other fatal configuration fact (symbol/mode/filter/min-notional) | Keep the existing task-local `stopped` behavior unless a future user decision changes it. | No linkage. |
| Known non-fatal final pair failure | Settle this pair once; apply only this task's configurable consecutive-failure count and pause it when its threshold is reached. | No linkage. |
| Timeout/5xx/ambiguous response | This task continues only its own client-ID reconciliation; it cannot start pair N+1 or resend pair N. | No linkage. |

Binance may still independently reject another task because its account/IP
limit is external to this application. “No linkage” means this application does
not globally pause, stop, count failures for, or delay another task after a
task-local 429. It cannot guarantee that an external exchange will accept every
other request.

The durable pair settlement remains the only place that updates a task's
consecutive-failure counter. A leg response must not separately increment the
counter; both legs are first reconciled and the pair is settled exactly once.

## Required implementation evidence

The replacement repair must prove deterministically, without Binance access:

1. a blocked query for task A does not prevent task B from reserving/submitting
   its own pair;
2. two simultaneous triggers cannot create two workers or two reservations for
   the same task/pair;
3. a confirmed 429 pauses only task A, exits A's local worker, does not change
   A's consecutive-failure count, and leaves B dispatchable;
4. a confirmed insufficient-balance/margin/available-quantity response pauses
   only task A and leaves B dispatchable; and
5. after restart/recovery, a pending pair is queried by its saved client order
   IDs and is never resent.

The reverse-direction missing-price preflight P1 from Review-1 remains required
unchanged: an unreadable/invalid `est_price` must fail closed for both
directions before reservation or POST.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/21-task-local-runtime-and-manual-pause-amendment.md
本地北京时间: 2026-07-24 23:15:34 CST
下一步模型: bookkeeper
下一步任务: prepare the superseding bounded backend repair packet 62 and validate dispatch readiness
