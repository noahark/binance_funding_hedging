# Stage Intake And Complexity — Hedge Open Fake UI v1

## User Discussion Summary

The user is starting the real hedge open/close execution surface, split into
three sequential stages: (1) this front-end fake UI prototype, (2) the live
backend open executor, (3) the close stage. This stage is only the front-end
fake prototype so the interaction, task page, and private-account position
display can be shaped and iterated before any backend order code is written.

Product intent for the open surface (locked during the 2026-07-22 requirement
discussion):

- Direction follows funding sign: positive funding → forward open (buy spot +
  short perp, no borrow); negative funding → reverse open (borrow-sell spot +
  long perp, needs cross-margin sellable quota).
- Smooth open only fires a leg when the spot/perp basis meets a threshold
  (>= 0.05%) with the two order-book streams time-aligned (abs delay <= 200ms).
  Immediate open skips the book gate and fires one leg every 1 second.
- Basis convention (locked, symmetric): the selling leg fills at the
  counterparty best; forward basis = perp bid1 − spot ask1; reverse basis =
  spot bid1 − perp ask1; over the reference price, >= 0.05% opens.
- Each fill is a market order on both legs, fired simultaneously/asynchronously.
  A single-leg fill with the other leg failing (leg risk) records the exposure,
  alerts, and pauses the task — no auto-hedge, no rollback.
- A cumulative >3 order failures in a plan terminates that plan and only pauses
  the task; no re-send.
- Quantity input unit is base-coin amount.

## This Stage Scope (front-end fake, pure client)

1. Market table column rework: rename existing `正向开单` / `反向开单`
   estimate columns to `正向开单率` / `反向开单率`; add two operation columns
   `正向开单` / `反向开单` after the `借币` column, each with two inputs
   (single-open base amount / success count N) and two buttons (平滑开单 /
   立即开单). Both columns clickable; the recommended-direction button is
   highlighted by current funding sign. Pre-open fake balance check (forward:
   USDT; reverse: cross-margin quota) pops an insufficient-balance dialog.
2. New left-nav `开单任务` page: vertical card list; each card shows
   direction/mode/single-amount/target-N/success+fail(x/3)/status, simulated
   spot+perp book prices with the forward/reverse open-rate combo, and the
   smooth-mode current basis vs the 0.05% threshold. Buttons: 暂停 / 启动 /
   删除 / 成交1次 (advance one fill) / 立即成交所有 (run remaining, 1 fill/s).
3. Private-account fake position table (aggregate by coin, all fields first):
   open basis rate (locked-basis average), position quantity, spot avg price,
   perp avg price, price unrealized PnL (both legs), accrued funding, reverse
   borrow interest, net PnL. Driven by mock task fills accumulating each leg's
   total filled quantity and notional.

All book prices are pure fake data with periodic drift (user decision); no real
websocket, no real order, no backend change. State persists in localStorage.

## Classification

- Complexity: `MEDIUM`
- Direction panel required: `false`
- Existing synthesis covers this work: `n/a (front-end fake prototype, no
  product-direction freeze; interaction is user-specified in this discussion)`
- User approved lightweight route: `true`
- Lightweight skip allowed: `true`

## Rationale

- This is a pure front-end mock prototype with no real funds, no order path, no
  backend surface, and no external side effects. The interaction is fully
  specified by the user in the 2026-07-22 discussion.
- A direction panel would repeat an already user-specified UI direction and add
  Harness cost without changing the bounded task. The user explicitly authorized
  the lightweight route.
- The live backend open executor (stage 2) and close (stage 3) will carry the
  real risk and will run their own design/review discipline.

## Human Gates

- No real Binance request, no order placement, no credential access, no backend
  code, no real websocket subscription in this stage.
- Real order execution, live websocket basis gating, and durable SQLite tasks
  are explicitly deferred to `stage/2026-07-hedge-open-live-v1`.

## Routing Decision

- Next node: `stage-design` (this file set) → development breakdown →
  single-owner front-end implementation dispatch to Kimi → cross review-1
  (Claude-GLM) → review-2 (GPT/Codex first; unavailable this round → Claude
  strong-reviewer fallback with disclosure).

## Bookkeeper

- Provider/model: Claude / Opus 4.8 (via Claude Code), provider identity
  `anthropic`.
- Independent from implementer (Kimi): `true`.
- Dual-hat disclosure: the bookkeeper also authors the development breakdown
  (design involvement). It is NOT an implementer or fix author. Review-2 must
  treat this as design-involvement for isolation purposes.

## Parallel Mode

- Uses `docs/parallel-development-mode.md`: `false`.
- Reason: one single-owner front-end task (Kimi domain). Serial delivery is
  simpler; there is no second disjoint implementation task to parallelize.
- The implementation dispatch prompt still carries the `[HARNESS-EXECUTOR-
  CONTRACT v1]` anti-relay preamble and the R10 dispatch tail (self-test
  commands, exact artifact paths, stop-for-bookkeeper).

## Evaluator

- Provider: Claude, Model: Opus 4.8, role: complexity evaluation by bookkeeper.

当前 Session ID: unavailable (Claude Code runtime does not expose a provider-native Session ID to the model)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-fake-ui-v1/00-intake.md
本地北京时间: 2026-07-22 18:51:35 CST
下一步模型: bookkeeper (self) — stage design + development breakdown
下一步任务: write 00-task.md, 10-design.md, 11-adr.md, 12-development-breakdown.md, then prepare the Kimi implementation dispatch packet
