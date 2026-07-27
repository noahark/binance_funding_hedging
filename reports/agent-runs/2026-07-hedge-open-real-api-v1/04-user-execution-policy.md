# User Execution Policy Update — Hedge Open Real API v1

## User Decisions Recorded 2026-07-23

These choices supersede earlier design suggestions that paused or blocked the
one-second immediate schedule based on actual fill quantities or on an
unresolved earlier attempt.

1. **Requested quantity is the execution alignment only.** Every leg must send
   the same valid `q_common` quantity for that attempt. The system does not use
   later actual filled quantities or notional values as a hedge-equality gate.
   Small quantity/value differences are normal for this type of market hedge;
   they are recorded but receive no special treatment in this stage.
2. **Cadence is one new concurrent hedge pair per second.** Ongoing order-status
   tracking does not block the next scheduled pair. The schedule remains subject
   to the existing executor/Start gate, valid filters, account/venue rejection,
   and exchange rate-limit handling; these are not a fill-equality check.
3. **Acceptance and tracking are separate.** A leg that returns an `orderId` is
   an accepted order. Persist the `orderId`, then query that order until Binance
   returns a final state. A missing response or timeout is not automatically a
   confirmed failure: first query using the persisted client order ID so that a
   possibly accepted order is never duplicated.
4. **Failure pause.** A confirmed failed pair increments a consecutive failure
   counter. The default `consecutive_failure_pause_threshold` is **3** and is a
   configurable variable, so it may later be changed to 1 or 2. Reaching the
   configured threshold pauses further scheduled opening. A successful accepted
   pair resets the consecutive failure counter. This is a failure guard, not an
   amount, count, margin, residual, or slippage cap.
5. **Order accounting.** Preserve each leg's returned/queryable actual base
   quantity and quote amount. Per-leg cumulative quantity and cumulative quote
   amount calculate the weighted average price:

   ```text
   average_price = cumulative_quote_amount / cumulative_base_quantity
   ```

   The quantities and values are for audit, display, and later refinement, not
   a current dispatch gate.

## Clarifying Implementation Interpretation

- A known exchange terminal rejection/cancel/expiry, or a pair in which an
  order is confirmed absent after client-ID lookup, is a confirmed failure.
- A transport timeout/ambiguous response stays `unknown` and is repeatedly
  queried rather than being retried or immediately counted as a failure.
- A returned `orderId` is not the same as a completed fill. The system keeps
  polling the order state; a market order normally completes quickly, but no
  automatic cancel, replacement, repair, or close is permitted here.
- This stage borrows only the legacy strategy's `orderId`-then-query and
  weighted-average accounting idea from `币安套费率策略，逐仓杠杆.js`. It explicitly
  excludes that script's sequential leg flow, timeout cancel/replacement, and
  automatic borrow/repay behavior.

## Consequence For Earlier Draft Advice

Earlier panel recommendations to pause immediately on partial fill, one-leg
fill, amount residual, or an unresolved previous attempt are not the selected
immediate-mode scheduling policy. The selected guard is confirmed consecutive
submission failure at the configurable threshold. The final design must still
make unknown transport results observable and queryable to avoid duplicate
orders.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/04-user-execution-policy.md
本地北京时间: 2026-07-23 19:00:05 CST
下一步模型: bookkeeper
下一步任务: synthesize completed panel evidence and present remaining canonical-document decisions
