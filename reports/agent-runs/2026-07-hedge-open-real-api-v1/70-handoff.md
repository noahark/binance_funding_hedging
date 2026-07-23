# Handoff — Hedge Open Real API v1

## Recovery Header

- Active phase: `testing / R4 implementation verified; formal Review-1 preparation`.
- Stage branch: `stage/2026-07-hedge-open-real-api-v1`, created from local main
  `28c550d87c1ca90983d5bde9c7102d42cffecd4e`; current HEAD is
  backend R4 delivery is `d90f2f18acec7fe6286f2ae3fc8e187580bf0793` and frontend
  delivery is `d873699d4c06f8dec343c9a6dcfa5fecc22d74b5`.
  Stage evidence commits exist; implementation is complete pending formal review.
- Classification: `MILESTONE`; default direction panel is mandatory. Independent
  raw drafts are received from Claude Opus 4.8, GLM-5.2, Kimi K3, and GPT-5
  Codex. Grok has an explicit unavailable record because the operator reported
  no quota. The panel is complete and synthesis may begin.
- Harness/main sync exception: user-selected Kimi K3 routing was committed on
  local main `5659f79` and merged into this stage as `53831d2`, because the
  pending mandatory panel must use K3. The Harness protocol suite passed
  52/52 and `validate-stage.py --phase checkpoint` passed after the merge.
- Read next: `status.json`, `06-direction-synthesis.md`,
  `04-user-execution-policy.md`, and raw `direction-drafts/` only if auditing
  the synthesis.
- Carried evidence: previous round's
  `reports/agent-runs/2026-07-hedge-open-live-v1/{80-user-acceptance.md,design-inputs.md,10-design.md,11-adr.md}`.
- New raw API recon received:
  `reports/api-samples/2026-07-hedge-open-real-api-v1/order-model-and-live-seams-recon.md`.
  It validates PAPI margin quantity/quote capability, UM quantity-only,
  per-leg decimal/filter behavior, and no PAPI testnet. The user selects the
  fixed-quantity route, so quoteOrderQty is not used this stage.
- Safety: no credential access, Binance network call, real POST, push, global
  Start activation, or first live task is authorized. Do not infer authorization
  from `APP_HEDGE_EXECUTOR=live` being implemented in a future diff.
- Latest user policy: each running task card is an independent asynchronous
  worker and sends one concurrent pair each second; multiple cards may submit in
  the same second. Accepted orders are tracked by `orderId` to terminal state;
  actual amounts are accumulated for weighted averages but do not gate cadence;
  three confirmed consecutive failed pairs pause, with that threshold
  configurable. See `04-user-execution-policy.md` and
  `05-cadence-resolution.md`.

## User-Frozen Scope

- Include the real PAPI POST adapter; actual activation and first live task are
  still a separate human authorization after implementation/review.
- No product numeric risk caps and no numeric both-filled mismatch threshold;
  the operator controls amount, count, and margin allocation.
- Actual fills/residuals and previous unresolved attempts do not block the
  one-second immediate schedule. `orderId` orders are queried to terminal state;
  ambiguous no-response cases are queried by client ID, never blindly resent.
  Three confirmed consecutive failed pairs pause by default; no automatic repair
  or close occurs.
- Immediate only; smooth WebSocket mode is a separate next stage. Each future
  smooth task will independently monitor its price spread through WebSocket and
  trigger only on its own configured spread-rate condition.
- Working rule is forward margin MARKET BUY with `quoteOrderQty`; reverse spot
  sell and both UM sides use `quantity`. **Superseded:** user selects concurrent
  fixed base `quantity=q_common` for every immediate hedge leg; quoteOrderQty is
  not used in this stage. Regular Portfolio Margin is the account assumption;
  PM-Pro is out of scope.
- Kimi direction routing is now `kimi_k3` / `kimi-k3`. The already stored
  `direction-drafts/kimi27.md` remains immutable under its historical filename;
  the human operator confirmed it was in fact executed by K3, so it is the
  valid K3 panel result and does not require rerun.

## Next Action

The user-approved design remains frozen in `00-task.md`, `10-design.md`,
`11-adr.md`, and `05-cadence-resolution.md`. Backend and frontend delivery are
already committed, and R4 is verified. Do not rerun implementation.

The next procedural gate is formal Review-1. First obtain the human operator's
real R9 receipt data for the completed Task A/Task B dispatches and append it
to their existing packets without changing their prompt bodies. Then set the
stage to `review_1`, run the clean `pre-review` validator, and have the human
operator execute the prepared Kimi backend and Claude-GLM frontend review
packets. Real activation and the first live task remain separate human actions.

## Implementation intake and R4 status

- Task A / Claude-GLM and Task B / Kimi raw implementation reports are received
  at `20-implementation-backend.md` and `20-implementation-frontend.md`.
- The bounded backend fix is received in `40-fix-backend-r4.md`. R4-1 adds the
  durable additive `attempts` projection required by the frontend timeline;
  R4-2 starts one worker per eligible task so a slow card does not block a
  sibling card's same-tick submission.
- Bookkeeper reproduced `.venv/bin/python -m pytest backend/tests -q` with
  **862 passed in 43.58s**, `node frontend/self-check.js` with all checks
  passing, and `git diff --check` passing. See `14-r4-verification.md`.
- Formal Review-1 packets are prepared but not yet human-dispatched:
  `30-review-1-backend-opus46.dispatch.md` (Claude Opus 4.6 reviews backend;
  the prior Kimi packet remains unused after the operator reported quota
  exhaustion, see `15-kimi-review-1-unavailable.md`) and
  `30-review-1-frontend.dispatch.md` (Claude-GLM reviews frontend).
- Before the clean `pre-review` validator can pass, the human operator must
  append real R9 dispatch receipts to the already completed Task A and Task B
  implementation packets. Their raw reports do not expose the executed adapter
  commands or provider-native session IDs; the bookkeeper must not invent them.
  Real activation and the first live task remain separate human actions.
- The human operator has now supplied the Task A Claude-GLM runner Session ID
  `694ea9e3-20e9-4f42-800e-940f9530a9bb` and Task B Kimi Session ID
  `session_135dcaae-ea96-456c-960e-00762ebc1fe8`; both are recorded in
  `status.json.session_receipts` with source `operator`.
- `20-implementation.md` is only an index required by the stage template. It
  points reviewers to the unedited Task A, Task B, and R4 raw reports and is
  not a substitute for those reports.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/70-handoff.md
本地北京时间: 2026-07-23 23:59:59 CST
下一步模型: human operator
下一步任务: record completed implementation dispatch receipts, then execute the two prepared formal Review-1 packets
