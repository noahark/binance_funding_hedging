# Codex Direction Draft — Real Borrow Execution v1

## Problem Statement

The accepted browser-only borrow-task UI must become a trustworthy local system that can create controlled real exchange borrowing work without confusing an attempted request with a completed loan, creating unbounded debt, or borrowing twice after an ambiguous network outcome.

## Target User And Workflow

The target user is the local operator of this funding-hedging workstation. They create a bounded borrow task from an approved market asset, review its maximum debt and execution policy, explicitly enable it, observe backend-reported progress and outcomes, and can pause or emergency-stop it before the next request. The system—not the browser—owns the durable execution state.

## Scope

The first real-execution scope is a backend-owned, persisted borrow task with a conservative exchange adapter, reconciliation, server API, and UI synchronization for one explicitly approved margin mode and asset allowlist.

## Recommendation

Treat this as a durable, backend-owned borrowing-workflow system rather than connecting the existing browser fake directly to a private exchange call. The first production-capable slice should support only the exact classic-margin mode, account, asset allowlist, retry cadence, and risk ceilings that the user explicitly approves. It should remain disabled until a distinct local execution enablement is present, and every run must be stoppable before the next attempt.

The task must be persisted before it is eligible to execute. A task should contain immutable creation metadata (task id, account/margin mode, asset, requested per-attempt amount, requested success target, creator timestamp, approval/version) plus mutable execution state (desired state, observed state, successful count, attempted count, last attempt/correlation id, last exchange outcome, next eligible time, terminal reason). The UI should render server state rather than independently simulating it.

## Key Safety Decisions To Freeze

1. Scope: verify whether the intended Binance operation is classic cross-margin borrow only, and whether `HOME` is the only initial asset. Do not abstract to isolated/cross modes before a verified API contract and user decision.
2. Confirmation: task creation may be a draft, but changing desired state to runnable needs an explicit, user-visible confirmation that shows cumulative maximum debt, asset, account and retry policy. Server-side execution must still require a separately configured local execution enablement / kill switch; no browser-only flag is sufficient.
3. Limits: require an asset allowlist, positive decimal validation, exchange `userMinBorrow` and precision constraints, per-attempt maximum, per-task cumulative maximum, global outstanding task maximum, concurrency limit of one for a task, and conservative rate limits. Stop a task on a validation breach or ambiguous outcome.
4. Retrying: only known non-executed failures are retryable. A timeout, response parse failure, connection loss after dispatch, or server 5xx must enter `outcome_unknown`, pause further borrow attempts and reconcile before any retry. Blind retry after an unknown outcome can borrow twice.
5. Success: count success only after a borrow-response identity is recorded and reconciliation verifies the intended amount/account state (or an exchange history record unambiguously matches the correlation/time window). An HTTP 2xx alone is not sufficient if subsequent persistence fails.
6. Lifecycle: separate desired state (`running`, `paused`, `deleted`) from execution state (`idle`, `attempting`, `retry_wait`, `reconciling`, `completed`, `blocked`, `failed`). Delete is a cancellation request: atomically disable scheduling, wait for an in-flight attempt to settle/reconcile, then soft-delete. Never delete audit history.

## Architecture And Rollout

Phase 0 should add no live write: define API/schema, database migrations, backend task engine with a fake/recording exchange adapter, deterministic clock, and UI migration to backend state. It must exercise restart, double-click, duplicate delivery, concurrent start/pause/delete, validation, and reconciliation tests.

Phase 1 can provide a locally enabled test/sandbox adapter if Binance semantics permit it, or a dry-run adapter that validates amount/limits without hitting a private borrow endpoint. This is not a substitute for an actual exchange integration but is required before production enablement.

Phase 2 adds the verified private borrow adapter behind configuration that is off by default. It needs minimum permission scope, no credentials in browser or repository, structured redacted audit logs, a durable task/attempt ledger, reconciliation polling/history queries, a process-wide execution lock, and a user-facing emergency stop. A one-task / one-asset / low bounded limit can be the initial live rollout.

The frontend should stop owning timers and task success counters. It should request task create/edit/start/pause/delete operations from the backend, render server-provided status and next-attempt/last-result data, and surface `outcome_unknown`, `blocked`, and safety-stop states distinctly from ordinary failed retry. The existing fake UI fields can remain, but edits must be versioned and only take effect between attempts.

## Security, Evidence And Tests

Credentials stay in the local runtime secret mechanism, never frontend JavaScript, reports, fixtures, exception messages or command transcripts. The exchange adapter should be the only code that signs requests. Every request should receive a locally generated attempt/correlation id saved before dispatch; if Binance has no idempotency key for borrow, reconciliation is the duplicate-prevention mechanism and unknown outcomes are fail-closed.

Tests must use recorded public contract samples and a controllable fake private adapter; no CI or Harness test may contain live credentials or create debt. Required tests include decimal/minimum validation, risk cap enforcement, transactional transitions, scheduler restart, unknown-outcome recovery, reconciliation matches/mismatches, lock/concurrency, API authorization, and UI state rendering. Browser tests should prove no direct secret/private-exchange access occurs from the UI.

## Non-goals

- Automatic repay, transfers, trading, hedging, order placement, profit/loss accounting, or portfolio risk optimization.
- Multiple exchanges, distributed workers, multi-user tenancy, and autonomous changes to risk limits.
- Treating deleted tasks as unaudited removal or treating a network timeout as safe to retry.

## Domain Assumptions Requiring Confirmation

- Binance exposes a private borrow operation and sufficient borrow/history or account evidence to reconcile an attempted request; the exact endpoint, parameters, response fields and rate limits must be verified against current official documentation before implementation.
- The workstation has a secure local credential-injection mechanism and a test/sandbox account may or may not be available; neither is assumed by this direction draft.
- Existing `userMinBorrow` data is suitable as client-facing validation guidance, but it does not on its own authorize a borrow or prove live availability.

## Acceptance Criteria

- No browser code signs or sends a private borrow request, and no test/fixture can create a live loan.
- A runnable task has durable identity, approved limits, lifecycle state, attempt ledger, redacted result, and restart-safe next action.
- The engine cannot issue concurrent attempts for one task and cannot retry an unknown-outcome attempt before reconciliation resolves it.
- Start/pause/delete and parameter edits are versioned, auditable, and safe around an in-flight attempt.
- The UI renders backend-owned state, including blocked, reconciliation and safety-stop outcomes, rather than faking success counts.
- All live execution remains off by default until the user-approved local enablement and explicit task confirmation are present.

## Open Questions And Human Gates

- Exact exchange account/margin mode and the initial asset allowlist.
- Whether user confirmation authorizes one task run, a session, or a durable schedule; the required local execution-enable mechanism and emergency-stop owner.
- Exact per-attempt, cumulative, concurrent-task and retry/unknown-outcome limits.
- Definition of success/reconciliation evidence acceptable for this exchange, and retention/audit expectations.
- Whether a real test account/sandbox is available; if not, production rollout must be separately approved after non-live adapter validation.

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/direction-drafts/codex.md
本地北京时间: 2026-07-19 02:16:55 CST
下一步模型: Claude、Claude-GLM、Kimi、Grok
下一步任务: 生成独立方向草案以供综合和用户审批
