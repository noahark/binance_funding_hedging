# Handoff — Hedge Open Real API v1

## Recovery Header

- Active phase: `planned / design discussion before direction drafts`.
- Stage branch: `stage/2026-07-hedge-open-real-api-v1`, created from local main
  `28c550d87c1ca90983d5bde9c7102d42cffecd4e`; current HEAD is the same and no
  stage commit exists yet.
- Classification: `MILESTONE`; default direction panel is mandatory. No panel
  member has been dispatched because only the human operator may execute model
  dispatch. Recon is complete and `direction-panel-dispatch.md` is ready.
- Read next: `status.json`, `00-intake.md`, and `01-design-discussion.md`.
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
- Checkpoint: worktree has only the intended stage-intake artifacts
  (`reports/agent-runs/ACTIVE.json` plus this stage's `00-intake.md`,
  `01-design-discussion.md`, `02-api-recon-intake.md`,
  `api-recon-order-model-and-live-seams.prompt.md`,
  `direction-panel-dispatch.md`, `70-handoff.md`, and `status.json`,
  `60-test-output.txt`, plus the received raw recon); JSON and whitespace
  integrity checks passed. No product-code tests were run.

## User-Frozen Scope

- Include the real PAPI POST adapter; actual activation and first live task are
  still a separate human authorization after implementation/review.
- No product numeric risk caps and no numeric both-filled mismatch threshold;
  the operator controls amount, count, and margin allocation.
- Single-leg, partial, timeout, and unknown outcomes still pause and reconcile;
  nothing automatically repairs or closes exposure.
- Immediate only; smooth WebSocket mode is a separate next stage.
- Working rule is forward margin MARKET BUY with `quoteOrderQty`; reverse spot
  sell and both UM sides use `quantity`. **Superseded:** user selects concurrent
  fixed base `quantity=q_common` for every immediate hedge leg; quoteOrderQty is
  not used in this stage. Regular Portfolio Margin is the account assumption;
  PM-Pro is out of scope.

## Next Action

The human operator executes the prepared mandatory direction-panel packet once
for each default-panel member, saving independent raw drafts under
`direction-drafts/`. The bookkeeper then synthesizes those raw drafts for user
approval.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/70-handoff.md
本地北京时间: 2026-07-23 15:27:04 CST
下一步模型: human operator
下一步任务: execute the mandatory direction-panel packet for each registered panel member
