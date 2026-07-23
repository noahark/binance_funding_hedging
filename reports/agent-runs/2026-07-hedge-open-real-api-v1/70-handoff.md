# Handoff — Hedge Open Real API v1

## Recovery Header

- Active phase: `planned / direction-panel evidence collection`.
- Stage branch: `stage/2026-07-hedge-open-real-api-v1`, created from local main
  `28c550d87c1ca90983d5bde9c7102d42cffecd4e`; current HEAD is
  `e57ff47`. Stage evidence commits exist; no implementation has started.
- Classification: `MILESTONE`; default direction panel is mandatory. Independent
  raw drafts are received from Claude Opus 4.8, GLM-5.2, and Kimi K3. Codex and
  Grok evidence (or explicit unavailable records) remain before synthesis.
- Harness/main sync exception: user-selected Kimi K3 routing was committed on
  local main `5659f79` and merged into this stage as `53831d2`, because the
  pending mandatory panel must use K3. The Harness protocol suite passed
  52/52 and `validate-stage.py --phase checkpoint` passed after the merge.
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
- Kimi direction routing is now `kimi_k3` / `kimi-k3`. The already stored
  `direction-drafts/kimi27.md` remains immutable under its historical filename;
  the human operator confirmed it was in fact executed by K3, so it is the
  valid K3 panel result and does not require rerun.

## Next Action

The human operator obtains independent `codex` and `grok-build` direction
drafts (or explicit unavailable records) using `direction-panel-dispatch.md`.
The bookkeeper will then synthesize all raw drafts for user approval.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/70-handoff.md
本地北京时间: 2026-07-23 16:45:40 CST
下一步模型: human operator
下一步任务: obtain the remaining Codex and Grok direction-panel evidence
