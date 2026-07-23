# Detailed Design — Hedge Open Real API v1

## Scope and Compatibility

The existing `backend/hedge_open_tasks/` record transport remains the safe
default. This stage adds a separate live executor and read-only preflight behind
`APP_HEDGE_EXECUTOR=live`; disabled and record modes remain zero-real-POST.
Public snapshot and borrow-task behavior are forbidden from change.

Existing hedge task routes remain the public surface and grow additively. Live
`fill-all` must not retain synchronous bulk dispatch: normal task scheduling
owns the one-second loop and every sending action passes the same gate.

## Preflight and Quantity

Each pair uses fresh public/private data for spot/UM filters and trade status,
directional PM balance, one-way position mode, PAPI order-rate availability,
and price references for factual min-notional validation. For each step/min/max
constraint, use enabled `MARKET_LOT_SIZE` first, then enabled `LOT_SIZE`; a zero
or missing value disables only that constraint.

Compute a Decimal common step, floor `single_amount` to `q_common`, validate
both legs, and serialize each as a fixed-point decimal string. No new slippage
buffer, notional cap, residual tolerance, or automatic quantity repair exists.

## Durable Attempt Model

Task state adds scheduled-attempt count, accepted-pair count,
`consecutive_submission_failures`, a task-snapshotted failure threshold, and
pause reason. Immutable attempt/leg records store sequence, `q_common`,
preflight fingerprints, both client IDs, request shapes, dispatch/query times,
`orderId`, exchange status, actual base/quote/fee fields, and terminal marker.

One SQLite transaction commits the attempt and both leg records before either
POST callable starts. A post-commit crash creates a query obligation; recovery
uses client IDs and never resends an original request.

## Dispatch and Reconciliation

```text
PREPARED -> DISPATCHING -> ACCEPTED_OR_QUERYING -> TERMINAL_RECORDED
                         \-> UNKNOWN_QUERYING
```

- Start both POSTs concurrently after `PREPARED` commits.
- `orderId` marks that leg accepted/querying; query it independently to terminal
  status.
- Timeout/missing/ambiguous responses are `UNKNOWN_QUERYING` until client-ID
  lookup proves accepted or absent.
- Both legs confirmed accepted reset the consecutive submission-failure counter.
  A pair only increments it when required lookup proves a leg never accepted.
- Terminal fill/residual/partial data is recorded and visible, but is not a
  scheduler gate. The next planned pair may dispatch after one second.
- Start, executor mode, task pause/done state, and exchange rate-limit cooldown
  still block sends.

## Live Adapter Boundary

A backend-only PAPI adapter owns canonical parameter bytes/signing, strict
host/method/path allowlist, bounded `recvWindow`, response/header classification,
and redacted logging. Only the live hedge executor calls write methods and it
must receive a service-produced gate/preflight context immediately before send.
Read-only query retries may be bounded; write POSTs never retry automatically.

## API, UI, and Tests

Task/list/log/position payloads grow additively with effective `q_common`,
threshold/failure counters, attempts/legs, client/order IDs, statuses,
cumulative base/quote totals, weighted averages, and residual. UI renders only
backend-authoritative data and exposes no Binance signing/scheduling.

Tests cover filter fallback, Decimal format, request shapes, durable-before-send,
concurrent calls, client-ID reconciliation/no-resend, one-second scheduling,
threshold pause, rate-limit cooldown, live bulk action prohibition, and default
zero real POST. Public snapshot, borrow tasks, disabled, and record transports
are regression boundaries.

## Boundaries and Risks

Likely backend scope is `backend/hedge_open_tasks/**`, a new narrowly scoped
PAPI hedge client under `backend/services/`, config/server wiring, and focused
`backend/tests/test_hedge_*`. Likely frontend scope is `frontend/index.html` and
`frontend/self-check.js`. Do not change raw samples, borrow behavior, public
snapshot routes/schemas, or approved PRD decisions.

The main risk is independent market-leg execution. The chosen policy records
outcomes and pauses only on confirmed submission failures; implementation must
not reintroduce automatic repair or a hidden residual threshold.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/10-design.md
本地北京时间: 2026-07-23 19:44:12 CST
下一步模型: Claude Opus 4.8
下一步任务: create an implementation task breakdown without changing the frozen contract
