# Direction Panel Dispatch — Hedge Open Real API v1

Human operator: run this packet once in each registered direction-panel model
(`codex`, `claude`, `glm52`, `kimi_k3`, `grok-build`). Replace `<model-id>` with
the actual model identifier. The model must not launch or relay to another
model. Preserve each raw response unchanged at:

`reports/agent-runs/2026-07-hedge-open-real-api-v1/direction-drafts/<model-id>.md`

## Evidence Already Received

- `claude-opus-4-8.md` is accepted as the `claude` panel draft.
- `glm52.md` is accepted as the `glm52` panel draft.
- `kimi27.md` keeps its historical filename, but the human operator confirmed it
  was executed by **K3** before the routing rename. It is therefore accepted as
  the `kimi_k3` panel draft; do not rerun Kimi merely to rename the artifact.

The remaining independent drafts are `codex` and `grok-build` (or a respective
explicit unavailable record).

## Task

Provide an independent Chinese product/architecture direction draft for the
real Portfolio Margin immediate hedge-open milestone. You are read-only: do not
edit source, access credentials, send orders, start services, or make a Binance
private request. Read these raw inputs:

- `reports/agent-runs/2026-07-hedge-open-real-api-v1/{00-intake.md,01-design-discussion.md,02-api-recon-intake.md}`;
- `reports/api-samples/2026-07-hedge-open-real-api-v1/order-model-and-live-seams-recon.md`;
- `reports/agent-runs/2026-07-hedge-open-live-v1/{design-inputs.md,10-design.md,11-adr.md,80-user-acceptance.md}`;
- `docs/product/PRD.md`, `docs/architecture/ARCHITECTURE.md`, and `AGENTS.md`.

## Frozen Inputs

- Regular Portfolio Margin, immediate mode only; smooth WebSocket mode is next
  stage.
- Frontend inputs fixed base quantity per attempt and attempt count.
- For either direction, floor that quantity onto the common Decimal grid valid
  for both spot MARKET and UM MARKET filters, yielding `q_common`.
- Submit both legs concurrently after the durable attempt is persisted:
  forward = margin BUY MARKET `quantity=q_common`, `NO_SIDE_EFFECT` + UM SELL
  MARKET `quantity=q_common`; reverse = margin SELL `quantity=q_common`,
  `NO_SIDE_EFFECT` + UM BUY MARKET `quantity=q_common`.
- No product numeric amount/count/margin cap. Binance filters, available
  balance/account status, rate limits, `APP_HEDGE_EXECUTOR=live`, durable Start
  gate, and first-live-task human authorization remain mandatory.
- Both filled does not receive an executed-quantity equality check. Single-leg,
  partial, timeout, or unknown result pauses and reconciles; no auto-borrow,
  auto-repay, auto-close, or auto-repair.
- Resolve F-003 through F-006 before the live executor.

## Draft Requirements

Propose a bounded stage design: precise preflight/read-only inputs, Decimal and
filter behavior, durable attempt/state transitions, concurrent dispatch and
reconciliation, real-POST gate proof, API/UI contract, tests, file/task split,
and residual risks. Identify any frozen assumption that is unsafe or internally
inconsistent, but do not replace it silently. Distinguish facts from design
choices. End with the mandatory footer below.

当前 Session ID: report your provider-native ID, or unavailable with reason
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/direction-drafts/<model-id>.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: archive this raw direction draft; do not implement code
