# Stage Intake And Complexity — Boundary C

## User Discussion Summary

The accepted and merged stage `2026-07-real-borrow-execution-v1` delivered
durable borrow tasks A+B: SQLite persistence, backend scheduling, task/log APIs,
the existing frontend entry, and a disabled runtime executor. It intentionally
made no Binance write request.

The user now authorizes a new Boundary C development stage whose product goal
is to connect that existing task system to real Binance Portfolio Margin
borrowing. The user will control ordinary exposure through account principal,
the per-attempt asset amount, and the requested successful-attempt count. The
stage must not invent an additional product-level USDT cap, asset allowlist, or
`maxBorrowable` preflight unless later requested by the user or required by
verified exchange rules.

The existing frontend is the primary product entry. Its current Confirm action
creates a `borrowing` task immediately; for Boundary C that action is treated as
the task-level authorization to begin real attempts when the process live gate
and global execution switch are both enabled.

This stage creation authorizes design, implementation with fake/recording
transports, and review. It does **not** authorize a model, test, script, or
bookkeeper to send a live Binance request. The human operator enables live mode
and creates/starts the first exact task after implementation and review.

## Classification

- Complexity: `HIGH`
- Direction panel required: `false`
- Existing synthesis covers this work: `true`
- User approved lightweight route: `true`
- Lightweight skip allowed: `true`

## Rationale

- This is the repository's first production debt-creating adapter, so signing,
  unknown-outcome recovery, migration of old tasks, and operational shutdown
  are high-risk correctness concerns.
- The direction panel and synthesis already exist in
  `2026-07-real-borrow-execution-v1`; that synthesis explicitly defined
  Boundary C. The user's 2026-07-20 instruction narrows the implementation to a
  backend-dominant live integration using the accepted frontend.
- A fresh direction panel would repeat an already approved product direction
  and add Harness cost without changing the bounded task.

## Human Gates

- Credentials are supplied only through local runtime environment variables;
  they never enter source, stage artifacts, prompts, fixtures, logs, or command
  output.
- No automated test, review, capture, or model action may send
  `POST /papi/v1/marginLoan`.
- Enabling the process live mode and the durable global execution switch is a
  human operator action.
- The first exact real task remains a human UI/API action after implementation
  review. Its asset, amount, count, interval, and resulting maximum target
  quantity must be visible before confirmation.
- Borrow, reconcile, and status reads are in scope. Repay, transfer, spot sell,
  hedge/order placement, and automatic close are not authorized.

## Routing Decision

- Next node: `stage-design`, followed by independent design review and the
  registered HIGH-stage development breakdown.

## Direction Source

- Existing synthesis:
  `reports/agent-runs/2026-07-real-borrow-execution-v1/06-direction-synthesis.md`
- Prior endpoint/capacity recon:
  `reports/agent-runs/2026-07-real-borrow-execution-v1/03-grok-borrow-api-capacity-recon.md`
- User amendment: existing frontend remains the entry; ordinary exposure is
  user-controlled through principal, amount, and count; backend connects the
  real borrow path.

## Bookkeeper

- Provider/model/session: Codex/GPT; provider-native Session ID unavailable in
  this runtime.
- Independent from implementers: `true`
- Codex is stage designer/bookkeeper only and is excluded from implementation
  and fix authorship.

## Parallel Mode

- Uses `docs/parallel-development-mode.md`: `false`
- Embedded review enabled: `false`
- R10 dispatch tail required: `false`
- R4 diff reconciliation required: `false`
- Reason: this is one backend-dominant bounded task with only small frontend
  status/copy integration. Serial delivery is simpler and avoids coordination
  overhead.

## Evaluator

- Provider: Codex
- Model: GPT
- Skill/role: complexity evaluation by bookkeeper

当前 Session ID: unavailable (runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/00-intake.md
本地北京时间: 2026-07-20 19:27:29 CST
下一步模型: independent design reviewer selected by human operator
下一步任务: review the Boundary C task, design, ADR, and draft development breakdown without implementation or live calls
