# Direction Panel Dispatch — Real Borrow Execution v1

## Operator Instructions

This is direction work only. Send the model-specific prompt below to the named model manually, exactly preserving the returned raw response at its output path. Do not ask any model to implement code, modify source files, execute a Binance borrow request, invoke private write endpoints, use credentials, or write synthetic credentials.

If a registered model is unavailable or quota-exhausted, create its named `.unavailable.md` file with the failure reason and the normal execution footer instead. Do not replace its draft with a bookkeeper summary.

Every response must end with the repository execution footer. Session IDs must be verified from the model runner or recorded as unavailable with the reason.

## Common Context For Every Panel Member

You are an independent product-and-architecture direction-panel member for `2026-07-real-borrow-execution-v1` in `/Users/ark/Desktop/ai code/funding_hedging`.

Use the repository-local `product_strategist` skill. Read `agents/skills/product-strategist.md` in full before drafting, then read `AGENTS.md`; the `direction-drafts` and `direction-synthesis` workflow sections in `workflows/templates/stage-delivery.yaml`; the current-stage `00-intake.md`; the finished fake-stage intake `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/00-intake.md`; and only the source files/documents you need to understand current backend/frontend architecture.

The user has explicitly asked to move from the already-accepted front-end fake task UI into real borrow business. The existing fake semantics are: asset + per-attempt borrow quantity + target successful-borrow count; while borrowing, attempt every interval; a failed attempt waits for the next interval; stop after the target number of successful attempts; UI can start, pause, delete, edit and filter tasks. The former UI-only task had no backend or side effects. Two prior P3 UI issues are explicitly deferred, not to be re-opened.

This is a financial external-side-effect milestone. Do not write code or trigger real/simulated private borrowing. Produce a concise but concrete independent direction recommendation that covers:

1. A safe, user-visible definition of “real borrow task”, including what a successful request means and what the system must persist/audit.
2. The recommended authorization and confirmation model for an autonomous retrying request that creates debt: default state, enablement, kill switch, per-task/global caps, valid assets/amounts, retry interval, maximum attempts/failure policy, and pause/delete race behavior.
3. Correctness: request idempotency/duplicate prevention across network timeouts and restart, state transitions, reconciliation with exchange borrow/history/account data, and how to deal with unknown outcomes.
4. Security/operations: credentials and permission scope, logging/redaction, local-only versus service process, crash recovery, concurrency, rate limits, alerting/observability, and test strategy that never touches a live account.
5. API/frontend contract and rollout plan that can preserve the current fake UI while connecting it safely to backend task state.
6. Explicit non-goals and the human decisions that must be frozen before coding.

State your assumptions, alternatives, and recommended phased delivery. Cite exact repository paths/observations where useful. Treat user-approved product documents as higher authority than other design artifacts. Use these headings so every required `product_strategist` output is explicit: `Problem Statement`, `Target User And Workflow`, `Scope`, `Non-goals`, `Domain Assumptions Requiring Confirmation`, `Acceptance Criteria`, and `Open Questions And Human Gates`. End with the required footer.

## Claude

- Model / provider: `claude` / Anthropic
- Raw output path: `reports/agent-runs/2026-07-real-borrow-execution-v1/direction-drafts/claude.md`
- Additional lens: focus on risk-controlled product behavior, state machines, adverse/unknown exchange outcomes, and the minimal human decisions that make an unattended borrowing loop acceptable.

## Claude-GLM

- Model / provider: `glm-5.2[1m]` / zhipu_glm (via Claude-GLM adapter)
- Raw output path: `reports/agent-runs/2026-07-real-borrow-execution-v1/direction-drafts/glm52.md`
- Additional lens: focus on the existing backend’s technical architecture, Binance private API semantics to verify, durable scheduler/reconciliation design, idempotency limits of exchange APIs, and deterministic tests/fixtures.

## Kimi

- Model / provider: `kimi-2.7` / Kimi
- Raw output path: `reports/agent-runs/2026-07-real-borrow-execution-v1/direction-drafts/kimi27.md`
- Additional lens: focus on the current frontend fake UI’s migration to backend-owned state, user comprehension of debt/risk and task statuses, confirmation/error/recovery UX, and frontend test boundaries.

## Grok Build

- Model / provider: `grok-build` / Grok
- Raw output path: `reports/agent-runs/2026-07-real-borrow-execution-v1/direction-drafts/grok-build.md`
- Additional lens: independently challenge the proposed autonomous borrowing concept, identify failure modes or unsafe assumptions likely to be missed, and recommend conservative constraints and a rollout sequence.

当前 Session ID: unavailable (prepared by Codex; current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/01-direction-panel-dispatch.md
本地北京时间: 2026-07-19 02:16:55 CST
下一步模型: human operator
下一步任务: 将对应分段派发给四个注册方向模型并保存原始输出
