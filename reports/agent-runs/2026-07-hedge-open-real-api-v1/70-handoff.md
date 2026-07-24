# Handoff — Hedge Open Real API v1

## Recovery Header

- Active phase: `design_amendment / user replaced the immediate cadence and added opening logs`.
- Stage branch: `stage/2026-07-hedge-open-real-api-v1`, created from local main
  `28c550d87c1ca90983d5bde9c7102d42cffecd4e`; current HEAD is
  backend R4 delivery is `d90f2f18acec7fe6286f2ae3fc8e187580bf0793` and frontend
  delivery was corrected at `820dd1ec88f0d2727bb0bd3cd06bc28d6c4afc55`; the
  reviewed stage head was rebound to `01d3a4712c89efab79772ce2e5ee2ba415e1e43c`
  after a main-only Harness compatibility merge.
  Stage evidence commits exist; implementation and task-level Review-1 are complete.
  The rebound final Review-2 was executed against its fixed range and returned
  `REWORK`; its raw verdict is `50-review-2.md`.
- Classification: `MILESTONE`; the mandatory direction panel is complete. The
  user approved a bounded design amendment at
  `15-immediate-loop-and-open-log-amendment.md`; replacement task breakdown is
  now required before any repair implementation dispatch.
- Harness/main sync exception: user-selected Kimi K3 routing was committed on
  local main `5659f79` and merged into this stage as `53831d2`, because the
  pending mandatory panel must use K3. The Harness protocol suite passed
  52/52 and `validate-stage.py --phase checkpoint` passed after the merge.
- Read next: `status.json`, `15-immediate-loop-and-open-log-amendment.md`,
  `50-review-2.md`, and the two task-level Review-1 reports.
- Carried evidence: previous round's
  `reports/agent-runs/2026-07-hedge-open-live-v1/{80-user-acceptance.md,design-inputs.md,10-design.md,11-adr.md}`.
- New raw API recon received:
  `reports/api-samples/2026-07-hedge-open-real-api-v1/order-model-and-live-seams-recon.md`.
  It validates PAPI margin quantity/quote capability, UM quantity-only,
  per-leg decimal/filter behavior, and no PAPI testnet. The user selects the
  fixed-quantity route, so quoteOrderQty is not used this stage.
- Safety: no credential access, Binance network call, real POST, push, global
  Start activation, or first live task is authorized. Review-2 found that a
  task configured for one planned group could keep creating additional groups
  after a `single_leg` result. Do not enable `APP_HEDGE_EXECUTOR=live`, Start,
  or a first live task until the bounded repair passes renewed review.
- Latest user policy: each task card is an independent asynchronous worker, but
  its count is sequential. It submits exactly one concurrent spot/perpetual
  pair, queries that pair to a final result, and only then may submit its next
  counted pair. Business errors stop only the affected task when classified as
  fatal; an opening-log page records all outcomes. See
  `15-immediate-loop-and-open-log-amendment.md`.

## User-Frozen Scope

- Include the real PAPI POST adapter; actual activation and first live task are
  still a separate human authorization after implementation/review.
- No product numeric risk caps and no numeric both-filled mismatch threshold;
  the operator controls amount, count, and margin allocation.
- An unresolved attempt blocks only its own task's next pair. `orderId` orders
  are queried to terminal state; ambiguous no-response cases are queried by
  client ID, never blindly resent. Three confirmed consecutive non-fatal
  failures pause by default, while a classified fatal error (such as insufficient
  balance) stops its own task immediately. No automatic repair or close occurs.
- Immediate only; smooth WebSocket mode is a separate next stage. Each future
  smooth task will independently monitor its price spread through WebSocket and
  trigger only on its own configured spread-rate condition.
- Working rule is concurrent fixed base `quantity=q_common` for every immediate
  hedge leg; `quoteOrderQty` is not used in this stage. Regular Portfolio Margin
  is the account assumption; PM-Pro is out of scope.
- Kimi direction routing is now `kimi_k3` / `kimi-k3`. The already stored
  `direction-drafts/kimi27.md` remains immutable under its historical filename;
  the human operator confirmed it was in fact executed by K3, so it is the
  valid K3 panel result and does not require rerun.

## Next Action

The final review at `50-review-2.md` remains schema-valid `REWORK`. Its P0
attempt-cap fix is still mandatory, but the user has replaced the timing model:
one task now owns one active pair at a time, while the two legs of that pair
remain concurrent. The same amendment adds a durable, paginated opening-log
page and task-local fatal-error stops. It does not authorize any real order.

`52-review-2-rework-backend.dispatch.md` and
`53-review-2-rework-frontend.dispatch.md` are preserved as immutable evidence
but are superseded before execution. Do not give either to a model. The next
bookkeeper work is a replacement development breakdown that maps the unchanged
Review-2 findings plus `15-immediate-loop-and-open-log-amendment.md` to new
backend/frontend boundaries, test evidence, and provider-isolated review
routing. Only then may replacement dispatch packets be prepared.

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
- Frontend Review-1 initially returned **REWORK** because `single_leg` and a
  null `pair_outcome` were not shown in plain Chinese and the self-check did not
  cover their real backend values. Sonnet 5 completed the bounded correction in
  `40-fix-frontend-r1.md`, committed as `820dd1e`; the new task fingerprint is
  `820dd1e:cd44c9a921e4f6bb21697c1a4c3ab776dc860b2791dd38b887cb5b7dc7f44c6b`.
- The re-review in `45-review-1-frontend-rfix.md` is **ACCEPT**: `single_leg`
  now shows 「单腿成交」+ warning, `pair_outcome:null` shows 「查询中」+ info, and
  the self-check covers both states. This is a front-end wording/test repair
  only; it changes no trading, backend, API, credential, or risk rule.
- The raw backend review identifies itself as Opus 4.6. The user-reported
  Sonnet 5 session back-filled dispatch metadata and performed a limited
  spot-check; it did not author a separate review verdict.
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
本地北京时间: 2026-07-24 14:24:42 CST
下一步模型: bookkeeper
下一步任务: prepare the replacement development breakdown; do not dispatch 52 or 53 and do not activate live trading
