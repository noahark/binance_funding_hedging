# Design Discussion — Hedge Open Real API v1

This is a discussion artifact, not an approved `10-design.md` or ADR. It
separates facts already carried from round 1 from decisions that need the
user's explicit approval.

## User Decision Update — 2026-07-23 (Supersedes Earlier Open Questions)

- Include the real PAPI POST adapter in this milestone, but retain the separate
  human authorization for actual activation and the first live task.
- No product numeric caps: the operator controls amount, count, and margin
  allocation. Exchange filters, actual balance/account state, rate limits, the
  durable Start gate, and idempotent reconciliation remain mandatory.
- No numeric both-filled mismatch threshold: record actual legs and residual,
  but do not pause solely because their filled quantities differ. A single-leg,
  partial, timeout, or unknown outcome still pauses and reconciles; nothing
  automatically repairs or closes exposure.
- Immediate mode only. The smooth WebSocket gate is deferred to a separate next
  stage.
- Working rule: forward margin MARKET BUY uses `quoteOrderQty` in USDT; reverse
  spot SELL and both UM sides use base `quantity`. The supplied Binance corpus
  says generic spot MARKET supports `quantity` *or* `quoteOrderQty`, while the
  user reports a PAPI margin BUY constraint. This is therefore a mandatory
  endpoint/symbol research item; no runtime fallback is permitted.
- Spot and UM quantity/price/quote decimal rules must be independent,
  `Decimal` fixed-point values serialized per leg. The former `q_common` model
  cannot be used for forward opens.

## API Recon Intake — 2026-07-23

Raw evidence: `reports/api-samples/2026-07-hedge-open-real-api-v1/order-model-and-live-seams-recon.md`.

The report supports the forward USDT `quoteOrderQty` input, confirms UM MARKET
uses base `quantity`, confirms no PAPI testnet, and requires per-leg Decimal and
filter processing. `quoteOrderQtyMarketAllowed` must be true for the selected
spot symbol; false rejects a forward task without a silent fallback.

One correction is needed before architecture freeze. The API does not by itself
make forward legs *necessarily serial*; it makes the exact spot executed base
amount unavailable until the spot order fills. Therefore serial spot-fill → UM
quantity minimizes planned quantity difference but creates a deliberate
spot-only interval. Concurrent quote-buy + price-derived UM quantity reduces
that sequential interval but makes a quantity mismatch intentional. Neither
option permits auto-repair. The user must choose this tradeoff and confirm
whether the account is regular Portfolio Margin or PM-Pro.

## User Execution Decision Update — 2026-07-23

This update supersedes the quote-buy and serial alternatives above. The frontend
accepts a fixed base-asset quantity per attempt and an attempt count. For both
directions, calculate the effective spot/UM market filters, floor the input to
their decimal common grid `q_common`, then submit the two `quantity=q_common`
MARKET orders concurrently after persisting the attempt.

| Direction | Margin order | UM order |
| --- | --- | --- |
| forward | BUY MARKET `quantity=q_common`, `NO_SIDE_EFFECT` | SELL MARKET `quantity=q_common` |
| reverse | SELL MARKET `quantity=q_common`, `NO_SIDE_EFFECT` | BUY MARKET `quantity=q_common` |

`quoteOrderQty` remains an API capability evidenced by recon but is not in this
stage's execution contract. Spot and UM price/quantity decimal rules can still
differ: each request uses its own filters and Decimal serialization; the common
grid applies only to the base quantity. Immediate mode targets regular Portfolio
Margin as documented by the repository; PM-Pro is out of scope unless corrected
by the user.

## Carried Facts

1. The round-1 record transport has no real POST, but its forward order shape
   is intentionally obsolete: spot market BUY needs `quoteOrderQty`, not a
   pre-aligned base `quantity`.
2. Therefore a forward attempt cannot promise equal executed base quantities
   before sending both legs. A matched order *intent* is still possible, but
   actual fills need an explicit tolerance/reconciliation policy.
3. Reverse remains base-quantity on both legs and can be constructed on a
   common filter grid. It must sell only base already available after the
   separate borrow workflow; it must not auto-borrow.
4. The locked smooth-time policy is spot bookTicker + local-receive time,
   perp bookTicker + exchange `E`/`T`, cross-leg gap at most 200 ms, and
   NTP/Binance-server-time offset monitoring.
5. A non-filled, timeout, disconnect, or 5xx response is unknown until queried
   by the persisted client IDs. The system pauses on unresolved/single-leg
   exposure and never auto-trades a repair.

## Proposed Delivery Shape

### Control plane first

Persist global account limits and per-task limits before creating a task:

- `max_margin_fraction` / absolute USDT reserve policy;
- `max_task_notional_usdt`;
- `max_attempt_notional_usdt`;
- `max_open_attempts` and one active task per symbol/direction;
- a cumulative account-level notional cap for all running tasks;
- a mandatory explicit acknowledgement for a task's first live attempt.

The server—not the browser—calculates and enforces each value from fresh
read-only preflight data. The browser only displays the effective limits and
the rejection reason.

### Order-intent model

Use a requested quote notional as the common user-facing input. At dispatch:

| Direction | Spot intent | Perp intent | Critical preflight |
| --- | --- | --- | --- |
| forward | MARKET BUY `quoteOrderQty=Q` | MARKET SELL `quantity=q_perp` derived conservatively from Q and a fresh price | free USDT, spot min notional, perp market filters, position mode, rate limit |
| reverse | MARKET SELL `quantity=q_common` | MARKET BUY `quantity=q_common` | free base, both market filters, position mode, rate limit |

For forward, `q_perp` must be derived from a documented price-side rule and
slippage buffer, then floored to the perp market step. The safe question is not
whether the legs can be exactly equal before execution—they cannot—but whether
the possible residual exposure is bounded by a user-approved USDT/base tolerance
and is observable before the next attempt.

### Execution state machine

1. Persist an `attempt` with both deterministic client IDs and its immutable
   preflight snapshot **before either POST**.
2. Submit legs concurrently only after all gates pass.
3. Reconcile by client ID, trades, and position risk after every ambiguous or
   non-filled response; never resend that client ID.
4. Classify results as `balanced`, `partial_or_unresolved`, or
   `mismatch_exposure`. The latter two pause the task and global execution
   dispatch; they never repair automatically.
5. Record actual filled base/quote amounts, fees where supplied, and the
   difference from the intended hedge. This replaces the round-1
   `both_mismatched -> null` information loss.

### Live activation is an independent control, not a startup default

Real POST must require all of:

1. `APP_HEDGE_EXECUTOR=live` at process start;
2. durable global Start gate ON;
3. fresh preflight within a short approved TTL;
4. limits pass using server-side values;
5. explicit task-level acknowledgement; and
6. a human-approved first-live-run procedure.

The design should specify fail-closed behaviour for stale preflight, websocket
disconnection, clock offset beyond bound, exchange filter changes, HTTP 429/418,
and restart recovery.

## Mandatory Prior-Round Repairs

- F-003: apply `MARKET_LOT_SIZE` and `LOT_SIZE` fallback per constraint, and
  normalize zero-valued filter strings as disabled.
- F-004: persist and enforce the rate-limit snapshot; stop dispatch on 429/418.
- F-005: make durable attempt persistence truly happen before send.
- F-006: remove fill-all spinning and re-audit every manual action against the
  Start gate in live mode.
- Replace the `both_mismatched_contract_gap` with a reviewable representation
  that shows both actual legs and the residual exposure without claiming a
  leg is absent.

## Decisions Required From The User

1. Is this one delivery stage allowed to contain live POST code, with actual
   activation still held for a later human action; or should the stage end at
   production-parity dry run and put the POST adapter in a separately reviewed
   activation stage?
2. What are the initial hard limits: maximum percentage of available margin,
   maximum USDT per attempt, maximum USDT per task, maximum attempts per task,
   and maximum aggregate running notional? These must be numbers, not UI hints.
3. For forward fills, what residual tolerance is acceptable before automatic
   pause: base-asset quantity, USDT notional, or both? If neither is approved,
   every non-identical execution should pause.
4. Should immediate and smooth modes ship together? Smooth adds the locked
   websocket clock gate and operational monitoring; immediate can share the
   order/risk core but has a smaller failure surface.

## Recommended Direction

Build the full production-parity control plane and corrected order model in
this milestone, but gate the real POST adapter behind a separately approved
activation task. This creates a testable dry-run that uses genuine read-only
preflight and live websocket data without silently converting a software merge
into trading authorization. Once its tests and review are accepted, the narrow
activation task can introduce the POST transport and first-live-run checklist.

This recommendation does not change the user's goal of using the real API; it
separates read-only/live-market truth from irreversible order placement so the
risk parameters and reconciliation semantics are proven first.

## Later User Policy Supersession — 2026-07-23

This document preserves the earlier discussion chronology. Its earlier
recommendations to pause on partial/unresolved results, block the next attempt,
apply numeric caps, or defer the real POST adapter are superseded where they
conflict with the latest user policy recorded in
`04-user-execution-policy.md` and `status.json.scope_decisions`:

- immediate mode sends one fixed-`q_common` concurrent pair every second;
- returned `orderId` values are persisted and queried to terminal status;
- actual fills are accumulated for weighted average accounting, not used as a
  current hedge-equality or cadence gate; and
- a configurable consecutive confirmed-failure threshold defaults to three and
  pauses future opening once reached.

Historical analysis remains useful for filters, endpoint facts, and the need to
query ambiguous responses by client ID without blindly retransmitting a POST.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/01-design-discussion.md
本地北京时间: 2026-07-23 19:00:05 CST
下一步模型: bookkeeper
下一步任务: synthesize the complete panel and latest user policy
