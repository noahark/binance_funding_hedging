# Task — Hedge Open Fake UI v1

## Goal

Deliver a pure front-end fake prototype of the hedge OPEN surface so the user
can shape and iterate the interaction, task page, and private-account position
display before any backend order code exists. No real funds, no order path, no
backend change, no real websocket.

## Deliverables

- **T1 Market table columns** (`frontend/index.html`):
  - Rename estimate columns `正向开单` → `正向开单率`, `反向开单` → `反向开单率`
    (name only; existing 60s-snapshot rate semantics unchanged).
  - Add two operation columns `正向开单` / `反向开单` immediately after the
    `借币` column. Each column cell has: two inputs (single-open base amount,
    success count N) + two buttons (平滑开单 / 立即开单).
  - Both direction columns are always clickable. Highlight the recommended
    direction's buttons by the row's current funding sign (positive → forward,
    negative → reverse). This is a visual recommendation, not a lockout.
  - On click: fake pre-open balance check — forward needs USDT (amount × N
    notional), reverse needs cross-margin sellable quota. Insufficient → modal
    dialog (`反向开单现货余额不足` / `正向开单 USDT 余额不足`). Sufficient →
    create a mock open task and reflect it on the 开单任务 page.

- **T2 开单任务 page** (new left-nav entry, vertical card list):
  - Each task card shows: coin, direction (正/反), mode (平滑/立即), single
    amount, target N, success count, fail count (x/3), status (运行/暂停/完成/
    敞口告警), simulated spot & perp book prices with the 正向开单率/反向开单率
    combo, and (smooth mode) current basis rate vs the 0.05% threshold.
  - Buttons per card: 暂停 / 启动 / 删除 / 成交1次 (advance exactly one fill by
    the single-open amount) / 立即成交所有 (run the remaining count, one async
    hedged fill per 1 second, until N reached).

- **T3 Private-account fake position table** (aggregate by coin, all fields):
  - open basis rate (locked-basis average across fills), position quantity,
    spot avg price, perp avg price, price unrealized PnL (spot leg + perp leg),
    accrued funding, reverse borrow interest, net PnL.
  - Driven by mock task fills accumulating each leg's total filled quantity and
    total notional; avg price = total notional / total quantity per leg.

## Fake behavior contract

- Book prices are pure fake data with periodic drift; the forward/reverse open
  rate is computed from them each tick.
- Smooth task: auto-advances one fill when the simulated basis rate >= 0.05%
  (or on manual 成交1次). Immediate task / 立即成交所有: one fill per 1s.
- Cumulative > 3 fill failures in a plan → terminate the plan, set status
  敞口告警/暂停, no re-send. (Fake may inject occasional failures to exercise it.)
- All task and position state persists in localStorage across reloads.

## Explicit non-goals (deferred to stage 2/3)

- Real order placement, real Binance requests, credentials.
- Real websocket book subscription and real basis gating.
- Durable SQLite tasks, backend executor, dry-run/live switch.
- Close/repay/transfer surface.

## Test strategy

- Extend the existing `frontend/` self-check harness with deterministic checks
  for: column rename + new operation columns present and ordered after 借币;
  recommended-direction highlight by funding sign; fake balance-check modal
  paths; task creation/lifecycle (暂停/启动/删除/成交1次/立即成交所有); >3-fail
  termination; position aggregation math (avg price, basis rate, net PnL);
  localStorage persistence round-trip.
- No backend tests are added or changed in this stage.

## Owner

- Single owner: Kimi (front-end domain). Backend/Claude-GLM not involved.
