# Handoff — Hedge Open Real API v1

## Recovery Header

- Active phase: `planned / detailed design complete; development breakdown pending`.
- Stage branch: `stage/2026-07-hedge-open-real-api-v1`, created from local main
  `28c550d87c1ca90983d5bde9c7102d42cffecd4e`; current HEAD is
  `62c4cac`. Stage evidence commits exist; no implementation has started.
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
- Latest user policy: send one concurrent pair each second; accepted orders are
  tracked by `orderId` to terminal state; actual amounts are accumulated for
  weighted averages but do not gate cadence; three confirmed consecutive failed
  pairs pause, with that threshold configurable. See `04-user-execution-policy.md`.

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

The user approved `06-direction-synthesis.md`, removal of the stale Manual
Close Design Gate, and the canonical PRD restructuring. `00-task.md`,
`10-design.md`, and `11-adr.md` now freeze the detailed stage design. Claude
Opus 4.8's raw `12-development-breakdown.md` was received and recommends
parallel backend (Claude-GLM) / frontend (Kimi) work with embedded pre-review
opted out. One human product decision remains before implementation dispatch:
whether one-second dispatch applies to every running task independently or is
globally serialized across all running tasks. Real activation and the first live
task remain separate human actions.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/70-handoff.md
本地北京时间: 2026-07-23 20:05:26 CST
下一步模型: human
下一步任务: choose per-task versus globally serialized one-second dispatch
