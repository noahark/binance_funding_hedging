# Task — Hedge Open Live v1 (Round 1: immediate open, dry-run)

## Goal
Replace the stage-1 fake open engine with a **real, durable, gated** backend
open executor for **immediate mode only** (1 fill/sec, no websocket), running as
**dry-run record transport** by default. Real order placement stays behind an
explicit `APP_HEDGE_EXECUTOR=live` gate + global Start + human-created first task.
Smooth mode (websocket basis gate + clock calibration) is the next round.

## Deliverables

### Backend — new `hedge_open_tasks` module (modeled on `borrow_tasks`)
- **domain**: pure logic — direction mapping, quantity common-grid rounding,
  preflight rules, single-leg-exposure classification, failure-threshold,
  status transitions. No I/O.
- **store**: durable SQLite — tasks table (stage-1 Task fields incl. `deleted`)
  + fills table (per fill: both legs' clientOrderId/orderId/filled qty/price/
  status). Settings + logs like `borrow_tasks`.
- **executor**: `DisabledHedgeExecutor` (default) and a live executor gated by
  `APP_HEDGE_EXECUTOR=live`. Dry-run = **record transport**: log the would-send
  signed request params (no secrets), filter versions, preflight snapshot, and
  client ids; **no network POST**.
- **service**: orchestration — global Start gate, read-only preflight, the
  immediate scheduler (1 fill/sec), concurrent dual-leg submit, single-leg
  exposure detection + alert + pause, `>3`-fail termination.
- **API**: hedge-open tasks CRUD + settings + logs (shape parallels the borrow
  task/API surface; reuse conventions).

### Frontend — wire stage-1 UI to the real backend
- Open columns' 立即开单 → create a real hedge-open task via API. 平滑开单 stays
  present but disabled/"下一轮" this round.
- 开单任务 page → real task state/fills from the API (keep cards, filters,
  `deleted` soft-delete, 暂停/启动/删除/成交1次/立即成交所有).
- Private-account positions → aggregate from real fills.
- Balance-check pre-open → real preflight result (forward USDT / reverse
  crossMarginFree).

## Non-goals (explicit)
- **No websocket, no smooth-open basis gate** (next round).
- No repay/transfer/close (stage 3).
- No real order by default: dry-run record transport; `APP_HEDGE_EXECUTOR=live`
  + global Start + first real task are human-only actions after review.
- No position-mode switch, no auto-borrow/auto-repay, no auto-hedge/auto-close
  on single-leg exposure.
- Do not fabricate a real order-response sample; the executor uses the official
  response schema and record transport until a later authorized real order.

## Test strategy
- Backend: deterministic unit tests for domain (direction map, common-grid
  rounding incl. mismatched steps, preflight accept/reject, single-leg
  classification, `>3`-fail termination, status incl. `deleted`), store
  (persistence round-trip, fills aggregation), and the dry-run record transport
  (asserts no network POST; asserts recorded param shape). No real Binance call
  in any test.
- Frontend: extend `frontend/self-check.js` for the real-API wiring (task
  create/lifecycle against a mocked API, positions from fills, disabled
  平滑开单).
- Safety: a test proving the live path is unreachable unless
  `APP_HEDGE_EXECUTOR=live` AND the global Start gate is on.

## Owner split
- Backend (`hedge_open_tasks` module + API + tests): **Claude-GLM**.
- Frontend (real-API wiring + self-check): **Kimi**.
- Parallel-mode candidate — decide at breakdown after interfaces (API shapes,
  Task/Fill JSON) are frozen in design.
