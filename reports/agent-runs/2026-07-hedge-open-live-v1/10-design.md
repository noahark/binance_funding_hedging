# Design — Hedge Open Live v1 (Round 1: immediate open, dry-run record transport)

Scope: real, durable, gated backend open executor for **immediate mode only**
(1 fill/sec, no websocket), default **dry-run record transport**. Grounded in
`design-inputs.md` (DI-1..DI-4) and the two recon reports under
`reports/api-samples/2026-07-hedge-open-live-v1/`. Reuses the accepted stage-1
contracts (Task/Fill fields, `deleted` status, position aggregation) and the
existing `borrow_tasks` module shape.

## 1. Architecture
New backend module `backend/hedge_open_tasks/` mirroring `backend/borrow_tasks/`:
`domain.py` (pure logic), `store.py` (durable SQLite), `executor.py`
(disabled default + gated live, record transport), `service.py` (orchestration,
scheduler thread, global Start, preflight), plus API handlers wired into the
existing server. Frontend wires the stage-1 UI to the new API.

## 2. Data model (SQLite)
### 2.1 `hedge_open_tasks` (task rows)
Stage-1 Task fields carried forward verbatim: `id`, `coin`(symbol), `direction`
(`forward`|`reverse`), `mode`(`immediate` this round; `smooth` reserved),
`single_amount`(base), `target_n`, `success_count`, `fail_count`,
`status`(`running`|`paused`|`done`|`exposure_alert`|`deleted`), `created_at`,
`updated_at`. Add: `q_common`(rounded base qty actually used), `leg_exposure`
(nullable JSON), `position_side_mode`(`BOTH`|`hedge`, snapshot at create).

### 2.2 `hedge_open_fills` (per fill, both legs)
`id`, `task_id`, `ts`, `attempt_id`, and per leg (`spot`,`perp`):
`client_order_id`, `order_id`(nullable until known), `status`,
`filled_qty`, `avg_price`, `raw_ref`(pointer to the record-transport log row).
Positions aggregate from here (stage-1 math: avg = Σnotional/Σqty per leg).

### 2.3 settings / logs
Global settings row (executor mode snapshot, Start gate, interval fixed 1s this
round) + append-only log rows, shaped like `borrow_tasks`.

## 3. Direction mapping (DI-4, locked)
| direction | spot leg (`/papi/v1/margin/order`) | perp leg (`/papi/v1/um/order`) |
|---|---|---|
| forward (funding>0) | `BUY` MARKET `quantity=q_common` `sideEffectType=NO_SIDE_EFFECT` | `SELL` MARKET `quantity=q_common` `positionSide=BOTH`(one-way)/`SHORT`(hedge) |
| reverse (funding<0) | `SELL` MARKET `quantity=q_common` `sideEffectType=NO_SIDE_EFFECT` | `BUY` MARKET `quantity=q_common` `positionSide=BOTH`/`LONG` |
Both legs `newOrderRespType=RESULT`, unique `newClientOrderId` derived from one
`attempt_id`. No `reduceOnly` on opens. Never `MARGIN_BUY`/`AUTO_REPAY`. Reverse
does NOT auto-borrow.

## 4. Quantity common-grid rounding (DI-4, correctness-critical)
Per symbol, read public exchangeInfo (spot `api.binance.com/api/v3/exchangeInfo`,
perp `fapi.binance.com/fapi/v1/exchangeInfo`); pick the effective market qty step
per leg (`MARKET_LOT_SIZE` if enabled else `LOT_SIZE`). Compute a **common grid**
= decimal `lcm(step_spot, step_perp)`; `q_common = floor(single_amount /
grid)*grid` using decimal fixed-point. Reject the attempt if `q_common` < any
leg min, > any leg max, or fails either leg's minNotional (est. at a conservative
price). **Both legs send the same `q_common`** — never round per leg. Filters are
read per attempt / cached with refresh, never hardcoded.

## 5. Preflight (read-only; any failure blocks Start)
On global Start and before each task's first attempt:
1. exchangeInfo (both markets) → compute grid/`q_common`, min/max/notional.
2. `GET /papi/v1/um/positionSide/dual` → one-way/hedge; snapshot to task.
3. Balance `GET /papi/v1/balance`: forward needs USDT `crossMarginFree` ≥
   est. `q_common × N × price`; reverse needs base `crossMarginFree ≥ q_common ×
   N`. `maxBorrowable` is verification only, never treated as sellable.
4. `GET /papi/v1/rateLimit/order` → persisted throttle (see §8).
Insufficient balance → the same modal contract as stage 1 (direction-specific
copy), no task Start.

## 6. Immediate open engine (this round)
- Fixed 1s interval scheduler (durable, one thread like `borrow_tasks`).
- Each tick, for a running task with `success_count < target_n`: build one
  attempt (`attempt_id`, two client ids), submit **both legs concurrently**
  (asyncio), then run the confirmation state machine (§7). One successful
  balanced fill → `success_count++`. Reaching N → `done`.
- **Dry-run record transport (default):** the executor records the fully-formed
  signed-request params (no secrets), filter versions, preflight snapshot, and
  client ids to the log/fills tables, and returns a simulated non-committal
  outcome. It performs **no network POST**. Live path (§9) is the only place a
  real POST can happen.

## 7. Single-leg exposure state machine (DI-4, locked policy)
Do not trust the POST return alone. Per attempt:
1. Submit both legs with unique client ids (persist attempt before send).
2. Any timeout/5xx/disconnect/non-`FILLED` → "unknown"; do NOT resend the same
   client id; query `margin/order`+`um/order`, then `margin/myTrades`+
   `um/userTrades`, and `um/positionRisk` to establish real filled qty/price.
3. Both legs `FILLED` at aligned qty → success fill recorded.
4. One leg `FILLED` + other `REJECTED`/`EXPIRED`/zero/partial/unknown →
   **single-leg exposure**: set `leg_exposure`, status `exposure_alert`, pause;
   record both legs' actual qtys/orders/trades/positionRisk. **No auto-hedge, no
   auto-close** (that is a new trade authorization).
5. Cumulative `fail_count > 3` → terminate the plan, pause, no re-send.
(In dry-run, outcomes come from the record transport's simulated result; the
state machine and persistence are exercised identically so the live round reuses
them unchanged.)

## 8. Rate limiting
Both POSTs are weight 1 → one hedge attempt = 2 order events. A persisted
throttle honors `GET /papi/v1/rateLimit/order` (tightest limit wins). On 429/418:
stop queuing, keep unsent tasks, do not retry to accelerate.

## 9. Safety gate (Boundary C posture, DI-2)
- Executor is `DisabledHedgeExecutor` unless `APP_HEDGE_EXECUTOR=live`.
- Even when live, a **durable global Start gate** must be ON, and the first real
  task is a human action. Read-only preflight must pass first.
- A test proves: with `APP_HEDGE_EXECUTOR` unset OR Start gate off, no real POST
  is reachable (record transport only).
- No credentials in source/artifacts/logs; record transport logs param shapes,
  never secrets/signatures.

## 10. API contract (freeze here for FE/BE parallel)
Parallels `borrow_tasks`; exact paths/JSON to be finalized in breakdown, shape:
- `POST /api/hedge-open-tasks` (create: coin, direction, mode=immediate,
  single_amount, target_n) → task JSON.
- `GET /api/hedge-open-tasks` (list, filter by status incl. deleted).
- `POST /api/hedge-open-tasks/<id>/{pause|start|delete|fill-once|fill-all}`.
- `GET /api/hedge-open-settings` / execution badge (executor mode + Start gate).
- `GET /api/hedge-open-logs` (paginated).
- `GET /api/hedge-open-positions` (aggregated from fills).
Task/Fill JSON field names = stage-1 frozen names + §2 additions.

## 11. Frontend wiring
Swap the stage-1 fake engine calls for these API calls; keep all UI (columns,
cards, filters, `deleted`, positions). 立即开单 → real create. 平滑开单 → present
but disabled with a "下一轮" hint. Execution badge shows dry-run vs live + Start
gate state. Preflight insufficient-balance uses the real result with the stage-1
modal copy.

## 12. Test strategy
Per `00-task.md` §Test strategy. Hard rule: **no test performs a real Binance
request**; the live executor is never exercised against the network in CI —
only the record transport and the disabled/gated paths are tested. A real
order-response sample is added only after a later human-authorized real order.
