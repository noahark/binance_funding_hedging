# Handoff — Hedge Open Real API v1

## Recovery Header

- Active phase: `fixing / Review-1 accepted backend and returned a bounded frontend rework`.
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

Review-1 evidence is now received. Backend review is ACCEPT with two non-blocking
follow-up observations. The frontend rework is committed at `820dd1e` and its
self-check passed. The only next task is the narrow Claude-GLM re-review packet
`45-review-1-frontend-rfix.dispatch.md`, which checks the Chinese labels and
tests for "querying" and "single-leg" attempt states. Real activation and the
first live task remain separate human actions.

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
- Backend Review-1 at `30-review-1-backend.md` is **ACCEPT**. Its P2 items are
  future hardening only: reduce `recvWindow` from 60 seconds toward 5 seconds,
  and cap per-tick pending-order reconciliation for a much larger task count.
  Neither changes the current business contract.
- Frontend Review-1 at `30-review-1-frontend.md` is **REWORK**. The UI should
  show `single_leg` as Chinese "单腿成交" with a warning, and `pair_outcome:null`
  as "查询中" rather than a dash. Self-check fixtures must cover those two real
  states. No trading, backend, API, or risk-rule change is requested.
- Sonnet 5 completed the bounded correction in `40-fix-frontend-r1.md`, committed
  as `820dd1e`. Bookkeeper independently reran `node frontend/self-check.js`:
  all checks passed. The new task fingerprint is
  `820dd1e:cd44c9a921e4f6bb21697c1a4c3ab776dc860b2791dd38b887cb5b7dc7f44c6b`.
- The raw backend review identifies itself as Opus 4.6. The user-reported
  Sonnet 5 session back-filled dispatch metadata and performed a limited
  spot-check; it did not author a separate review verdict.
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
本地北京时间: 2026-07-24 11:51:36 CST
下一步模型: human operator
下一步任务: execute the narrow Claude-GLM frontend re-review packet and preserve 45-review-1-frontend-rfix.md
