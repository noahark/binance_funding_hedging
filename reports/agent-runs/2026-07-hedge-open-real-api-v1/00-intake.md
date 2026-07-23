# Stage Intake And Complexity — Hedge Open Real API v1

## User Discussion Summary

Continue from accepted `2026-07-hedge-open-live-v1` (round 1: durable
immediate-open skeleton and dry-run record transport). The user asks to start
the real-API stage design and discuss details. The requested outcome is a
manually controlled hedge-open flow whose risk is bounded by margin, per-order
amount, and order count.

Prior accepted inputs that carry forward:

- Forward: buy spot/margin spot and sell USDⓈ-M perpetual; reverse: sell
  previously borrowed base and buy USDⓈ-M perpetual.
- User decision update: all immediate hedge legs use base `quantity=q_common`.
  Spot MARKET BUY and SELL as well as both UM sides accept this fixed base-asset
  input; the two legs are submitted concurrently. `quoteOrderQty` is not used
  in this stage.
- Smooth mode uses spot `@bookTicker` stamped with local receive time and perp
  `@bookTicker` exchange `E`/`T`, with `|E_perp - t_spot_local| <= 200 ms` and
  clock-offset monitoring.
- No automatic close, auto-hedge, auto-borrow, or auto-repair is in scope.

No real order, credential access, Binance network access, push, or live Start
activation is authorized by this design intake.

## User Decisions Recorded 2026-07-23

This section supersedes the earlier open questions below.

- This milestone includes the real PAPI order adapter. Actual activation and
  the first live order remain a separate human action after implementation and
  review; writing a gated adapter is not authorization to trade now.
- The product imposes no numeric ceiling for margin fraction, order amount,
  task notional, attempt count, or aggregate running notional. The operator
  controls risk through entered order amount, number of attempts, and allocated
  margin.
- There is no numeric forward-fill mismatch tolerance. If both legs are filled,
  record their actual amounts and residual; do not pause merely because the
  amounts differ. Single-leg, partial, timeout, or unknown outcomes still pause
  for reconciliation and never trigger automatic repair.
- Smooth mode is a separate next stage; this milestone implements immediate
  mode only.
- Working rule: forward spot MARKET BUY sends `quoteOrderQty` as total USDT;
  **Superseded by the later user decision:** both forward legs send the same
  fixed base `quantity=q_common` concurrently. Frontend inputs are per-attempt
  base quantity plus attempt count; quote-order-quantity is out of this stage.

## Classification

- Complexity: `MILESTONE`
- Direction panel required: `true`
- Existing synthesis covers this work: `false`
- User approved lightweight route: `false`
- Lightweight skip allowed: `false`

## Rationale

- This is the first stage that may introduce a signed trade POST and real-fund
  risk controls.
- It combines a corrected cross-market order model, persistent safety state,
  read-only private preflight, and a live websocket timing gate.
- Amount, count, margin-reserve, partial-fill, and first-live-run semantics are
  product decisions rather than implementation defaults.

## Human Gates

- Approve the risk-control values and their scope (account, task, attempt).
- Decide whether live POST is delivered in this stage or remains a separately
  approved activation stage after production-parity dry run.
- Approve the first-live-run procedure; this cannot be inferred from a config
  flag.
- Approve the direction synthesis before implementation.

## Routing Decision

- Next node: `direction-drafts`, after this design discussion fixes the human
  decision packet.

## Bookkeeper

- Provider/model/session: Codex / GPT-5 Codex / provider-native ID unavailable
  (this runtime does not expose one).
- Independent from implementers: `true`
- If not independent, disclosure: n/a

## Parallel Mode

- Uses `docs/parallel-development-mode.md`: `false` at intake; decided only
  after the approved design and development breakdown.
- R10 dispatch tail required: `false`
- R4 diff reconciliation required: `false`

## Evaluator

- Provider: Codex bookkeeper (provisional classification; no implementation
  dispatch executed)
- Model: GPT-5 Codex
- Skill: complexity_evaluator equivalent workflow assessment

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/00-intake.md
本地北京时间: 2026-07-23 13:58:49 CST
下一步模型: human-operated recon model
下一步任务: run the prepared PAPI order-model recon prompt and preserve its raw evidence
