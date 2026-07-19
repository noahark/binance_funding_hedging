# Direction Synthesis — Real Borrow Execution v1

## Synthesizer

- Provider: Codex / GPT
- Skill: `product_strategist` (`agents/skills/product-strategist.md`)
- This is a proposed direction for user approval, not authority to create a Binance loan or start delivery code.

## Inputs

- `direction-drafts/codex.md`
- `direction-drafts/claude.md`
- `direction-drafts/glm52.md`
- `direction-drafts/kimi27.md`
- `direction-drafts/grok-build.md`
- Product authority: `docs/product/PRD.md`, `docs/architecture/ARCHITECTURE.md`

## Problem Statement

The accepted fake task UI creates browser-memory records only. The user now wants real borrowing: tasks that persist, retry a fixed amount toward a successful-borrow target, and remain manageable from the existing UI.

This is the repository’s first external write surface and first automated debt-creation loop. The current architecture intentionally permits only whitelisted signed GET requests, and the product baseline marks borrowing as future execution work. A safe change must not weaken the read-only snapshot contract, let the browser sign requests, retry an ambiguous outcome, or create unbounded naked-borrow risk.

## Target User And Workflow

The target user is the single local operator of this `127.0.0.1` workstation and Portfolio Margin account.

1. The operator creates a task with the existing asset, single-attempt amount and target confirmed-success count.
2. The backend validates and persists it as draft/paused, then presents a maximum-debt/risk summary before it can be armed.
3. The backend—not the browser—owns scheduling, attempts, success counts, stop conditions and crash recovery.
4. A task can dispatch only when a separate process-level execution gate is enabled, the task is explicitly armed/running, the kill switch is clear and all server-side caps pass.
5. The UI renders server state: confirmed progress, next eligible time, latest result, block reason and kill-switch state. Pause/delete prevent future work but reconcile an already-dispatched attempt.

## Final Proposed Direction

### Three safety boundaries

Do not make the fake confirmation button live in one jump. Deliver in explicit boundaries:

| Boundary | Deliverable | Binance borrow POST |
| --- | --- | --- |
| A — durable task core | task/attempt ledger, decimal global round-robin scheduler, PaperExecutor, server task API, UI migration, task/log tabs, confirmation UI, kill switch, deterministic tests | No |
| B — verified contract | official-document plus permitted read-only evidence for the selected PM loan/history APIs; mock/recording adapter conformance | No |
| C — live adapter | narrow write adapter, reconciliation, live-enable runbook and a manually supervised first attempt | Yes, only after separate explicit human approval |

Approve A+B for this stage. C is a distinct later execution stage: even a “small discovery POST” creates real debt and must not enter code, tests or sample collection by implication.

### Durable server authority

Use a durable local task store (recommended: stdlib `sqlite3` with transactional/WAL behavior; exact schema belongs to stage design). Persist:

- immutable task definition: task id, PM account/mode, asset, decimal-string amount, success target, creation/version/arming timestamps;
- global scheduler setting: a positive decimal interval in seconds (default `5`), stored as an integer duration rather than a binary float; it has no product-defined minimum interval;
- task state: desired and observed state, success count, attempt count, latest result, paused/terminal reason and soft-delete marker;
- write-ahead attempt ledger: locally generated attempt id/sequence, scheduled/dispatch/finish timestamps, requested amount, redacted result, exchange reference where available, observed effective gap, and state-transition audit.

Use decimal strings/`Decimal` for money on the server. Browser JS numbers and the current classic-reference `userMinBorrow` display are guidance only, never live borrowing authority.

### State, success and retry

Keep user-facing task words where they fit: `borrowing`, `paused`, `deleted`, `completed`. Surface server-owned `pending_confirmation`, `reconciling` and `blocked` as status reasons/substates.

- The global dispatcher selects one runnable task on each interval tick in stable round-robin order. With A/B/C and a 3-second global interval, dispatches are A at 0s, B at 3s, C at 6s, then A at 9s. Paused, deleted, completed and unknown-outcome-blocked tasks are skipped.
- No `maxBorrowable` preflight gates a dispatch. Its result can be stale by the time a task sends a request; the borrow endpoint is the authoritative availability decision.
- All known exchange rejects, including no inventory and account-limit/business rejects, are recorded as the latest result and return to the round-robin queue. There is no product-defined consecutive-failure or total-attempt ceiling.
- A 429/418 response is different: the exchange-provided `Retry-After` produces a global scheduler cooldown. This is protocol compliance, not a configured product frequency limit.
- A timeout, connection loss after dispatch, malformed response or possibly-accepted 5xx is an **unknown outcome**. Stop new attempts for that task and reconcile against verified exchange history/account evidence; never issue another borrow just because a response is missing.
- A known successful response containing `tranId` is persisted and counts immediately toward the task target. Loan-history reconciliation is mandatory for unknown outcomes and periodic audit, not a synchronous GET after every normal success.
- Completion occurs at the target successful-response count. A task is not slowed by a balance refresh after a known `tranId` success.

### Authorization, controls and lifecycle

Borrow execution is default-off and needs both a process-level local execution flag (separate from read-only private access) and a task-level confirmation showing asset, amount, target, maximum debt and current global dispatch interval.

The backend enforces a kill switch, positive/finite decimal input validation, task-level at-most-one unresolved attempt, asset/account validation and exchange-mandated 429/418 backoff. Different tasks may have requests in flight concurrently when a very short global interval is chosen; the scheduler records actual dispatch/completion times so observed throughput is analyzable rather than assumed. Edits are versioned and apply only between attempts; raising potential debt requires new confirmation. Delete is a soft delete and retains audit history.

### Exchange and UI boundaries

Leave `public-market-snapshot/v1` and the existing GET-only `PrivateClient` contract intact. Create a separate narrow write adapter with explicit method/path allowlisting and a separately versioned same-origin task API. The frontend never sees credentials or signed parameters; it becomes a backend-state client rather than the task-state authority.

Keep the existing task page, filters, input layout, buttons and soft-delete behavior recognizable. Add a top-level `借币日志` tab alongside `借币任务`; task status filters stay in the task tab. The log tab is newest-first and paginated, showing timestamp, task/asset, sequence, requested amount, result category, sanitized reason/code, latency/effective gap and `tranId` where available. Replace fake progress with server progress and visibly distinguish execution-disabled, kill-switch, last-known failure, rate-limit cooldown and unknown-outcome reconciliation. The two user-deferred P3 UI issues remain out of scope.

### Security and tests

Verify the exact Portfolio Margin loan/history API semantics, decimal/step rules, response IDs, error codes, rate-limit headers and any idempotency support from official documentation plus permitted evidence before C. Do not trust model recollection; classic `userMinBorrow` is not proof of PM live availability.

Credentials remain local runtime secrets, with least privilege, no withdrawal permission and IP allowlisting. Keys, signatures, signed queries and full private payloads never enter source, logs, reports, prompts or fixtures. Test through fake/recording transports and a controllable clock only; no CI/Harness test may create a live loan.

## Accepted Ideas By Source

- **Codex:** backend-owned persistence; desired/execution state split; reconciled success; unknown outcomes fail closed; staged rollout and kill switch.
- **Claude:** write-ahead intent; task/attempt audit; serial dispatch; separate write client; retry classification; A/B/C progression; deletion reconciles, not erases.
- **GLM:** PM endpoint semantics must be evidenced; preserve GET-only adapter; independent task API; SQLite durability; live validation is a separate human gate.
- **Kimi:** preserve accepted UI while moving authority server-side; explicit risk confirmation and execution status; render paused reasons/unknown outcomes; deterministic frontend contract tests.
- **Grok:** treat automated borrow as tightly bounded debt assembly, not a hedge bot; require hard caps, runtime/attempt bounds, process-wide lock and no auto-resume after unknown outcome.

## Rejected Or Deferred Ideas

- Direct fake-button-to-Binance connection: rejected—no durable identity, cap enforcement, reconciliation or safe unknown-result behavior.
- Browser timer/direct private request: rejected—unsafe across refresh/restart and violates secret boundaries.
- Infinite retry until target: rejected—conflicts with the PRD’s no-silent-retry requirement.
- Real micro-borrow to collect a sample in this stage: deferred to C with separate live authorization.
- Borrow + sell/futures/repay/transfer or hedge bot: out of scope.
- Generalizing the GET-only private client into a general POST client: rejected.
- The two deferred UI P3 items: remain deferred by user direction.

## Requirements To Freeze

For A+B, the proposed freeze is:

1. Portfolio Margin only; classic reference fields cannot authorize live loans.
2. New tasks default to draft/paused; no borrow before process gate and task confirmation.
3. Server is the single authority; frontend has no direct Binance access or authoritative timer/success count.
4. Every attempt is persisted before dispatch. Each task has at most one unresolved attempt, while different tasks may be concurrently in flight under a short global interval; unknown outcomes never automatically retry.
5. A durable known-success response with `tranId` counts immediately; history is mandatory for unknown outcomes and periodic audit.
6. The global interval accepts any positive decimal second value, defaults to `5`, and round-robins runnable tasks. There is no backend product minimum or configured frequency cap; 429/418 must honor the exchange backoff.
7. Pause/delete are forward-looking and cannot erase an in-flight loan attempt.
8. Task API is independent/versioned; snapshot API stays unchanged.
9. A+B makes zero Binance borrow writes in code, tests and local development.
10. `借币日志` is durable, newest-first and paginated; it contains attempt/result metadata only, never credentials, signatures or full private payloads.

## Open Human Decisions

| Decision | Recommended default |
| --- | --- |
| Scope now | A+B now; C as a separately approved live-enable stage |
| Initial asset allowlist | `HOME` only; confirm or name another list |
| Retry interval | global default `5` seconds; task-page input accepts any positive decimal seconds and round-robins one runnable task per tick |
| Failure behavior | known failures remain in the rotation and expose their latest reason; unknown result blocks that task; 429/418 follows exchange `Retry-After` globally |
| Success | persisted successful response with `tranId` counts immediately; history is exceptional/periodic audit authority |
| Risk caps | set numeric per-attempt, per-task cumulative and global USDT-equivalent limits before C |
| Authorization lifetime | process flag + task confirmation + global kill switch; tasks pause after restart pending re-arm |
| Credentials | separate least-privilege write-capable key, no withdrawal, IP allowlist, local-only service |
| Naked-borrow risk | explicitly accept that this scope borrows but does not sell/hedge/repay |

## Next Step After User Approval

After explicit approval and any edits:

1. create `stage/2026-07-real-borrow-execution-v1` from `main` and commit stage evidence there;
2. promote only approved decisions into canonical product/architecture/ADR documents;
3. create the task/design and dispatch the required development breakdown;
4. implement and review only A+B;
5. stop after A+B acceptance. C needs a new explicit live-execution authorization and must not be inferred from approval of this synthesis.

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/06-direction-synthesis.md
本地北京时间: 2026-07-19 07:41:02 CST
下一步模型: human operator
下一步任务: 审批或编辑真实借币方向、阶段边界和人类决策；未批准前不得创建 stage branch 或开始实现
