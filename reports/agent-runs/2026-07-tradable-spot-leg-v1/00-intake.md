# Intake — Tradable Spot Leg Status Gate

## User Request

> 下一阶段我们来修刚才说的现货没有排除不可用状态的问题吧

## Classification

- Complexity: `LOW`.
- Direction panel: skipped.
- Lightweight-route basis: the user explicitly requested this bounded fix, and the approved
  PRD already requires a spot leg that can structurally form a hedge. This stage clarifies and
  enforces that existing meaning; it does not introduce a new product direction.
- Parallel mode: disabled. The task is one backend/data-semantics change owned by Claude-GLM.

## Problem Statement

Binance spot `exchangeInfo` retains non-trading records. `AERGOUSDT`, `XMRUSDT`, and
`LITUSDT` currently have spot `status=BREAK`, zero spot book ticker prices, and active futures
quotes. The current resolver treats any exact symbol record as a usable spot leg, causing these
rows to become `SPOT_ONLY_CANDIDATE / DISABLED_SPOT_ONLY` instead of
`PERP_ONLY_EXCLUDED / DISABLED_PERP_ONLY`.

## Stage Boundary

- Backend normalization/classification semantics and backend tests.
- Clarifying edits to the approved PRD and public-market contract.
- Raw public samples under `reports/api-samples/2026-07-tradable-spot-leg-v1/`.
- No frontend or schema changes.
- No execution, trading, credential, or private-API behavior.

## Human Gates

- A human operator executes the prepared Claude-GLM implementation packet.
- Review and merge/push remain gated by the standard stage workflow.

---
当前 Session ID: 019f734a-dd82-7a11-8367-93fc1a5e954c
Session ID 来源: runtime_env
原始输出路径: reports/agent-runs/2026-07-tradable-spot-leg-v1/00-intake.md
本地北京时间: 2026-07-18 12:23:14 CST
下一步模型: codex（stage designer/bookkeeper）
下一步任务: 完成设计、真实样本与 Claude-GLM 派工包
