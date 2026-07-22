# Design — Hedge Open Fake UI v1

Single-owner front-end stage. All work lives in `frontend/index.html` (inline
`<script>`, DOM, CSS) and `frontend/self-check.js`. No backend, no network, no
real websocket. State persists in `localStorage`. The existing self-check
harness already mocks `localStorage`, `setInterval`/`clearInterval`, and
`fetch`, and runs via `node frontend/self-check.js`.

## 1. Market table columns (T1)

### 1.1 Rename estimate columns
- `<th>正向开单</th>` → `<th>正向开单率</th>`, `<th>反向开单</th>` →
  `<th>反向开单率</th>` (thead near index.html:999-1000). Keep both `title`
  tooltips and the underlying `renderOpeningQuotesCell(row, direction)` logic
  and 60s-snapshot semantics unchanged — this is a name-only change.

### 1.2 New operation columns
- Add two `<th>` after `<th>借币</th>` (index.html:1010), in order:
  `正向开单` then `反向开单`.
- Each row renders an operation cell per direction, styled after the existing
  borrow input controls (`.control`, `.btn compact`). Cell contents:
  - input `单次开单币量` (base coin, `inputmode="decimal"`, placeholder e.g.
    `如 0.01`)
  - input `成功开单次数` (integer, `inputmode="numeric"`, placeholder `如 5`)
  - button `平滑开单` and button `立即开单`
- **Recommended-direction highlight**: for a row, if `funding_rate > 0` the
  forward cell's buttons get a `primary`/highlight class; if `funding_rate < 0`
  the reverse cell's buttons are highlighted. Both cells stay fully clickable
  (no `disabled`). Zero/null funding → neither highlighted.

### 1.3 Pre-open fake balance check
- On `平滑开单`/`立即开单` click, read + validate the two inputs (amount > 0,
  N integer >= 1). Invalid → inline field error, no task created.
- Fake balance model (localStorage `hedge_fake_account`, seeded on first use):
  - `usdt_free` (e.g. seed `10000`), and per-coin `reverse_quota` (e.g. seed
    `{ default: 5 }` base-coin units, overridable).
  - Forward needs `amount × N × ref_price` USDT; reverse needs
    `amount × N` base-coin sellable quota. Insufficient → modal dialog with
    direction-specific copy: `正向开单 USDT 余额不足` / `反向开单现货余额不足`,
    showing required vs available. No task created.
  - Sufficient → reserve the amount from the fake account and create the task.

## 2. 开单任务 page (T2)

### 2.1 Navigation
- Add a left-nav button `nav-hedge-tasks` (after `nav-borrow-tasks`,
  index.html:878-885) with a `nav-count` badge `hedge-task-count`.
- Add a `<section class="panel" id="hedge-task-view" style="display:none;">`
  parallel to `borrow-task-view`. Wire nav switching in the existing nav
  handler so exactly one panel is visible at a time.

### 2.2 Task card (vertical list `hedge-task-list`)
Each card (styled after `.borrow-task-list` cards) shows:
- Header: coin, direction badge (`正向`/`反向`), mode badge (`平滑`/`立即`).
- Progress: `已成功 s / N`, `失败 f / 3`, status badge
  (`运行`/`暂停`/`完成`/`敞口告警`).
- Live book block (mock, drifting): spot bid1/ask1, perp bid1/ask1, and the
  `正向开单率` / `反向开单率` combo computed from the current mock book.
- Smooth mode only: `当前基差率 X% (阈值 0.05%)` with a met/unmet indicator.
- Buttons: `暂停` / `启动` / `删除` / `成交1次` / `立即成交所有`.
  - `成交1次`: advance exactly one fill by `single_amount` immediately (async
    both legs), regardless of basis/mode.
  - `立即成交所有`: run the remaining `N − success_count` fills, one async
    hedged fill per 1 second, until N reached or the task pauses/terminates.

## 3. Private-account fake position table (T3)
- Add a position table into `private-panel` (index.html:913), aggregated by
  coin across all task fills. Columns (all shown first, tune later):
  `币种 | 方向 | 持仓数量 | 现货均价 | 合约均价 | 开单价差率 | 价格未实现盈亏 |
  累计资金费 | 借币利息 | 净盈亏`.
- Aggregation (per coin):
  - `spot_avg = Σ spot_notional / Σ spot_qty`, `perp_avg = Σ perp_notional /
    Σ perp_qty` over that coin's fills.
  - `open_basis_rate` = quantity-weighted average of each fill's locked basis
    rate.
  - `position_qty` = Σ filled base qty (both legs equal by construction).
  - price unrealized PnL = spot leg mark-to-mock + perp leg mark-to-mock
    (hedged, near 0). accrued funding / reverse borrow interest = fake
    accumulators advancing on a slow tick. net PnL = price PnL + funding −
    interest.

## 4. Data contracts (frozen for stage 2 reuse)

### 4.1 localStorage keys
- `hedge_open_tasks`: `Task[]`
- `hedge_fake_account`: `{ usdt_free, reverse_quota: {<coin>|default: number} }`
- (positions are derived from tasks, not stored separately)

### 4.2 Task object
```
Task = {
  id: string,                 // uuid-ish
  coin: string,               // e.g. "BTCUSDT"
  direction: "forward"|"reverse",
  mode: "smooth"|"immediate",
  single_amount: number,      // base coin per fill
  target_n: number,           // success target
  success_count: number,
  fail_count: number,         // cumulative; >3 terminates
  status: "running"|"paused"|"done"|"exposure_alert",
  fills: Fill[],
  leg_exposure: null | { leg: "spot"|"perp", qty: number, price: number, ts: number },
  created_at: number, updated_at: number
}
Fill = { ts: number, spot_price: number, perp_price: number,
         qty: number, basis_rate: number }
```

### 4.3 Basis formula (ADR-2, locked)
- forward: `(perp_bid1 − spot_ask1) / mid(perp_bid1, spot_ask1)`
- reverse: `(spot_bid1 − perp_ask1) / mid(spot_bid1, perp_ask1)`
- open threshold: applicable basis `>= 0.0005` (0.05%).

## 5. Fake engine behavior
- A single mock-book drift tick (`setInterval`, e.g. 1000ms) perturbs each
  active coin's book and recomputes rates.
- Smooth task: on each tick, if `basis(direction) >= 0.05%` and
  `success_count < target_n`, advance one fill.
- Immediate task and `立即成交所有`: one fill per 1s regardless of basis.
- `成交1次`: one fill now.
- Each fill has an injectable fail probability (small, deterministic seed for
  self-check). On fail: `fail_count++`. Simulate a single-leg fill case that
  sets `leg_exposure`, status `exposure_alert`, and pauses. On cumulative
  `fail_count > 3`: terminate (status `paused`/`exposure_alert`, stop the loop,
  no re-send).
- On reaching `success_count == target_n`: status `done`, release loops.

## 6. Test strategy (self-check additions)
Add deterministic `[PASS]` assertions in `frontend/self-check.js`:
1. Estimate columns renamed to `正向开单率`/`反向开单率`; operation columns
   `正向开单`/`反向开单` exist and are ordered immediately after `借币`.
2. Recommended-direction highlight by funding sign (positive→forward,
   negative→reverse, zero→neither); both cells remain non-disabled.
3. Balance-check: forward USDT-insufficient and reverse quota-insufficient each
   yield the modal path and create no task; sufficient path creates a task.
4. Task lifecycle: create → 成交1次 advances success by 1 → 暂停/启动 toggles
   status → 立即成交所有 drives to N → 删除 removes.
5. `> 3` cumulative failures terminate the plan and pause; single-leg exposure
   sets `exposure_alert` + `leg_exposure`.
6. Position aggregation math: avg price = notional/qty per leg; open basis rate
   weighted average; net PnL = price PnL + funding − interest.
7. localStorage persistence round-trip for `hedge_open_tasks` and
   `hedge_fake_account`.
8. No new `fetch` call and no cross-origin request introduced (reuse the
   existing same-origin/timer guards).
