# Task — Hedge Open Real API v1

## Objective

Replace the immediate hedge-open dry-run executor with a default-off real PAPI
path for the approved fixed-quantity, one-pair-per-second contract. Preserve
all read-only, borrow-task, and dry-run behavior outside this hedge-open scope.

## Frozen Requirements

- Regular Portfolio Margin, USDT, USDⓈ-M perpetual, one-way `positionSide=BOTH`.
- Both legs use Decimal-filtered `q_common` and are submitted concurrently.
- Forward: PAPI margin BUY + UM SELL; reverse: PAPI margin SELL + UM BUY; every
  margin leg uses `NO_SIDE_EFFECT`; no `quoteOrderQty`.
- Create one pair each second until `target_n` attempts are issued or the task
  pauses. Earlier fills, residuals, partial status, or pending queries do not
  block the next pair.
- Persist one immutable attempt and two client IDs before either POST. Query a
  timeout/ambiguous response by client ID; never blindly resend it.
- A returned `orderId` starts terminal-state polling. Persist actual amounts,
  fees, and per-leg cumulative weighted averages.
- Confirmed pair submission failure increments a configurable task-snapshotted
  threshold (default 3). Reaching it pauses future opening.
- No product amount/count/margin/residual/slippage caps; no automatic repair,
  cancel/replace, close, borrow, repay, transfer, or smooth/WebSocket mode.
- Real execution requires `APP_HEDGE_EXECUTOR=live`, global Start, fresh factual
  preflight, and separate human first-live authorization. No real order is
  authorized during implementation or tests.

## Deliverables

1. Real read-only preflight and Decimal filter/rate-limit/account validation.
2. Durable attempt/leg/order state and restart-safe client-ID reconciliation.
3. Default-off signed PAPI margin/UM POST/query adapter with exact allowlist.
4. Scheduler/service one-second dispatch and configurable failure pause.
5. API/UI state for attempts, orders, averages, failure count, and residual.
6. Fake/record transport and deterministic tests with no credentials or real
   private requests.

## Non-Goals

Smooth mode, user streams, PM-Pro, normal-spot fallback, automatic borrowing,
manual close, repay, transfer, full accounting, and real-order validation.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/00-task.md
本地北京时间: 2026-07-23 19:44:12 CST
下一步模型: Claude Opus 4.8
下一步任务: produce the required development breakdown from this frozen task
