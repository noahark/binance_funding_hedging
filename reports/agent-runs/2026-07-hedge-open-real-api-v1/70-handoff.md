# Handoff — Hedge Open Real API v1

## Recovery Header

- Active phase: `fixing / R4 reconciliation found bounded backend rework`.
- Stage branch: `stage/2026-07-hedge-open-real-api-v1`, created from local main
  `28c550d87c1ca90983d5bde9c7102d42cffecd4e`; current HEAD is
  last bookkeeper checkpoint HEAD was `133d286684713f3245d28249e7f9da62ff2d4b1f`.
  Stage evidence commits exist; no implementation has started.
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

The user approved `06-direction-synthesis.md`, removal of the stale Manual
Close Design Gate, and the canonical PRD restructuring. `00-task.md`,
`10-design.md`, `11-adr.md`, and `05-cadence-resolution.md` now freeze the
detailed stage design. The user selected per-task independent asynchronous
one-second cadence; the prior breakdown open item is resolved without editing
its raw artifact. Claude Opus 4.8's raw `12-development-breakdown.md` recommends
parallel backend (Claude-GLM) / frontend (Kimi) work with embedded pre-review
opted out. The bookkeeper has prepared immutable task packets
`task-A-claude-glm.prompt.md` and `task-B-kimi.prompt.md`; run the dispatch-ready
validator before the human operator runs them concurrently. Real activation and
the first live task remain separate human actions.

## Implementation intake and R4 status

- Task A / Claude-GLM and Task B / Kimi raw implementation reports are received
  at `20-implementation-backend.md` and `20-implementation-frontend.md`.
- Bookkeeper reproduced `.venv/bin/python -m pytest backend/tests -q` with
  **856 passed in 43.12s**, and `node frontend/self-check.js` with all checks
  passing. The source file boundaries and `git diff --check` also passed.
- Do not commit or formally review the current implementation diff yet.
  `13-r4-diff-reconciliation.md` records two P1 integration gaps: no durable
  attempt projection reaches the frontend timeline, and task-card cadence is
  still serialized while live calls wait. The bounded backend fix packet is
  `backend-r4-fix.prompt.md`; only the human operator may execute it.
- Task B is compatible with the required additive `attempts` response and has
  no requested fix. Real activation and the first live task remain separate
  human actions.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/70-handoff.md
本地北京时间: 2026-07-23 22:32:36 CST
下一步模型: human operator
下一步任务: execute the bounded Claude-GLM R4 backend fix packet and preserve 40-fix-backend-r4.md
