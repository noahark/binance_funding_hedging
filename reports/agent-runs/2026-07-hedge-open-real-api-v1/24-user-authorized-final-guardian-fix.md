# User authorization — final guardian-scanner fix

## Decision

On 2026-07-25, after the bookkeeper explained H-1 in plain language, the user
approved one additional narrowly bounded backend repair:

> 目前其他的子线程单独运行和查询的业务做好了吧。那就再做一次针对这个守护进城的fix派发。上下文和需求描述清晰一点

The user keeps the amendment-21 requirement: no long-lived global guardian for
live hedge opening. This authorization raises the stage's otherwise exhausted
three-rework limit for **one and only one** correction of H-1. It does not
authorize a new product feature, a broader refactor, WebSocket/smooth opening,
credentials, real Binance traffic, live activation, Start, or any order.

## Fixed business meaning

- A task card still owns its own bounded worker: preflight -> reserve -> submit
  the two legs concurrently -> query only its own legs -> settle -> optional
  next pair.
- The correction must preserve that local-worker behavior and its existing
  regression coverage.
- In live-capable mode, application startup may perform one recovery handoff
  for durable pending work and then return. Manual Start/recover may launch
  only its named task. A periodic scheduler/tick must not repeatedly discover
  all hedge-open tasks or start workers for them.
- Dry-run behavior is not being redesigned by this authorization.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/24-user-authorized-final-guardian-fix.md
本地北京时间: 2026-07-25 18:48:57 CST
下一步模型: human
下一步任务: run the prepared packet 63 in a fresh write-capable Claude-GLM session
