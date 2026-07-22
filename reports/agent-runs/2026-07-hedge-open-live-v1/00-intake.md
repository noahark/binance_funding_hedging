# Stage Intake And Complexity — Hedge Open Live v1

## User Discussion Summary

Stage 2 of the hedge open/close program: the **live backend open executor**. It
takes the interaction, task page, and position display shaped and accepted in
stage 1 (`2026-07-hedge-open-fake-ui-v1`, front-end fake, merged to local main
`1aee0fe`) and replaces the mock engine with a real, durable, gated execution
path. The close surface remains stage 3.

The product direction is already frozen by the 2026-07-22 three-stage discussion
and the stage-1 contracts, and must be carried forward unchanged:

- Direction by funding sign: positive → forward (buy spot + short perp, no
  borrow); negative → reverse (borrow-sell spot + long perp, needs cross-margin
  sellable quota; reverse does NOT auto-borrow — borrow stays in the existing
  borrow system).
- Basis convention (ADR-2, locked): forward = (perp_bid1 − spot_ask1)/mid;
  reverse = (spot_bid1 − perp_ask1)/mid; a fill opens when the applicable basis
  >= 0.05%.
- Smooth open fires a leg only when basis >= 0.05% AND the spot/perp books are
  time-aligned (abs delay <= 200ms); immediate open fires one leg every 1s.
- Both legs are market orders, fired concurrently/asynchronously. A single-leg
  fill with the other leg failing records the exposure, alerts, and pauses the
  task — no auto-hedge, no rollback. A cumulative > 3 fill failures terminates
  the plan and only pauses the task; no re-send.
- Quantity unit is base coin. Task/Fill fields and `Task.status` (including the
  stage-1 follow-up value `"deleted"`, ADR-5) are carried forward.

## This Stage Scope

- Backend `hedge_open_tasks` module (domain/store/service/executor + durable
  SQLite), modeled on the existing `borrow_tasks` module.
- Real order placement on Binance Portfolio Margin (papi): spot leg + USDⓈ-M
  perp leg, market, concurrent. Exact endpoints/params/filters to be grounded in
  real public API samples (see Recon below).
- Smooth mode: backend subscribes Binance public order-book streams (spot +
  perp), computes basis, gates on >= 0.05% and <= 200ms cross-stream skew.
  Immediate mode: one fill per 1s, no stream gate.
- Single-leg exposure detection → record + alert + pause. `> 3` cumulative
  failures → terminate + pause.
- Safety gate modeled on Boundary C: disabled/dry-run executor by default;
  `APP_HEDGE_EXECUTOR=live` required for any real order; durable tasks; a global
  Start gate; read-only preflight before any real action.
- Frontend: replace the stage-1 fake engine with real API calls (open columns →
  real tasks; task page → real task state + real book; positions → real fills).

## Classification

- Complexity: `HIGH`
- Direction panel required: `false`
- Lightweight route user approved: `true` (user chose "HIGH + 轻量路线" on
  2026-07-22)
- Lightweight skip allowed: `true`

## Rationale

- The macro direction is not an open question: what to build (spot+perp hedge
  open) and how (basis口径, market dual-leg, single-leg policy, failure
  threshold, Boundary-C-style safety gate) are already frozen by the user's
  three-stage discussion and the accepted stage-1 contracts. A fresh direction
  panel would repeat an already frozen direction and add Harness cost.
- The real risk is implementation correctness and safety, which is covered by
  stage design review, review-1/review-2, dry-run/live gating, and real API
  sample grounding — not by a direction panel. This mirrors the Boundary C
  lightweight judgment for a real-execution stage.

## Human Gates

- Real funds. No real Binance order, no production websocket subscription for
  execution, no credential access, and no push are authorized by this intake.
- Enabling `APP_HEDGE_EXECUTOR=live`, the global Start gate, and creating the
  first real hedge task remain explicit human operator actions AFTER
  implementation and review, exactly as in Boundary C.
- Contract changes to order endpoints, filters, or stream formats must be
  grounded in real public API samples landed under `reports/api-samples/`
  (Hard Gate). Synthetic fixtures may supplement but never replace fact evidence.

## Routing Decision

- Next node: **API/websocket fact recon** (`api-recon-websocket.prompt.md`,
  user-delegated to an external model) → stage design → development breakdown →
  task split (backend Claude-GLM + frontend Kimi; parallel mode candidate) →
  review-1 → review-2.

## Direction Source

- 2026-07-22 three-stage requirement discussion (open/close split; direction,
  basis, single-leg, failure threshold, market dual-leg).
- Stage 1 accepted contracts: `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/`
  `{10-design.md,11-adr.md,00-task.md}`.
- Boundary C safety model: `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/`.

## Bookkeeper

- Provider/model: Claude / Opus 4.8 (via Claude Code), `anthropic`.
- Independent from implementers: `true`. If the bookkeeper also authors the
  development breakdown, that design involvement is disclosed for review-2.

## Open Items Before Design

1. Recon returns real spot + USDⓈ-M perp order-book stream facts (this file's
   companion prompt).
2. Order endpoints (papi spot margin market + UM perp market), params, and
   exchange filters (stepSize/minNotional) still need real samples.
3. First-round scope (smooth+immediate together vs immediate-first) to be
   confirmed at design time.

当前 Session ID: unavailable (Claude Code runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-v1/00-intake.md
本地北京时间: 2026-07-22 21:40:33 CST
下一步模型: user-delegated recon model (websocket facts), then bookkeeper stage design
下一步任务: run api-recon-websocket.prompt.md to ground Binance spot + USDⓈ-M perp order-book stream facts, then design the live open executor
