# Stage ADR — Boundary C Live Borrowing

## Context

A+B already provides a durable task ledger, round-robin scheduler, typed
executor port, status/log API, and frontend controls. It deliberately rejects a
live executor. Boundary C is the smallest product change that converts the
executor edge into a real Portfolio Margin debt-creating path.

The dominant correctness problem is not ordinary exchange rejection. It is an
ambiguous result after the request may have reached Binance: blindly retrying
can double the debt. The second migration problem is that old tasks marked
`borrowing` were created when execution was disabled and must not silently
become live.

## ADR-001: Existing Confirm is the task authorization

### Decision

Keep the existing create-and-run interaction. The pre-submit UI must display
asset, amount, successful count, target total, and interval. No second draft/arm
state is introduced.

### Alternatives Considered

- New draft → confirm → arm lifecycle.
  - Rejected because the user explicitly wants to keep the completed frontend
    entry and directly connect the backend; it adds state and clicks without
    improving unknown-result correctness.

### Tradeoff

- Benefit: preserves the accepted workflow and keeps C small.
- Cost: an accidental Confirm can create debt quickly, so execution mode must be
  unmistakable and the target summary must appear before the request.

## ADR-002: User-managed exposure, server-enforced correctness

### Decision

Do not add app-level USDT caps, principal accounting, asset allowlists, or a
`maxBorrowable` preflight. The user controls ordinary exposure through Binance
account principal plus task amount/count. The server still enforces decimal
validation, serial dispatch, global stop, exchange cooldown, and duplicate-debt
prevention.

The scheduler interval has an exchange-capacity floor rather than an exposure
cap. It reserves half the verified IP budget for reads/reconciliation using
`ceil(60 / (0.5 × ip_budget_per_min / post_weight))`; the archived 6000/min
budget and weight-100 POST freeze the floor at two seconds, while the existing
default remains five. This avoids
a borrow cadence that can IP-ban the unrelated read-only product.

### Alternatives Considered

- Hard per-attempt/per-task/global USDT caps.
  - Deferred by the user's selected risk model.
- Synchronous `maxBorrowable` before every POST.
  - Rejected because it is stale immediately, consumes request weight, and does
    not solve ambiguity after dispatch.

### Tradeoff

- Benefit: no false precision or duplicated risk configuration.
- Cost: the backend cannot prove the user's external principal limit and can
  create the full task target if the account permits it.

## ADR-003: Separate write client with one signer primitive

### Decision

Extract signature creation into one shared module. Preserve the existing
read-only client's GET whitelist. Add a separate client with only the verified
borrow POST and loan-record GET and dedicated borrow credentials.

### Alternatives Considered

- Add POST support to `PrivateClient`.
  - Rejected because it breaks the read-only security boundary.
- Duplicate signing code in the live adapter.
  - Rejected because it creates two cryptographic exits and weakens existing
    grep-level security checks.
- General-purpose signed request client accepting arbitrary method/path.
  - Rejected because deny-by-default exact allowlisting is safer and sufficient.

## ADR-004: Persist intent, then classify; never retry unknown

### Decision

In one conditional transaction before I/O, re-check execution ownership, task
status, live authorization, global Start, cooldown, no unresolved attempt, and
count below target; then insert pending and set `unresolved_attempt_id`. A valid
normalized `tranId` response counts immediately. Only evidence-enumerated
rejections may retry on a later scheduler turn. Unlisted 4xx, timeout,
connection loss, malformed success, and potentially accepted 5xx become
unknown and block only that task until loan-record reconciliation proves a
unique success. The A+B resolve path that can overwrite a deleted task is a
required Boundary C fix, not optional polish.

The archived public evidence freezes `known_rejection` to `-51006`, `-51014`,
and `-51061`; all other 4xx responses are unknown except rate-limit handling.
Missing/invalid `Retry-After` uses 60 seconds and valid values clamp to
`[60, 300]` seconds. HTTP 418 uses a 300-second minimum local cooldown and
requires a manual global Start afterward; it never auto-resumes, and local
expiry does not assert that Binance's documented possible multi-day ban has
ended. HTTP 400 business code `-1003` is rate limiting. The borrow POST uses its
own 10-second test-overridable module constant and never retries inside
transport.

Absence of a history record is not proof of failure and never authorizes an
automatic second POST.

### Alternatives Considered

- Retry every transport error.
  - Rejected due to duplicate debt.
- Query history synchronously after every known success.
  - Rejected as unnecessary request weight/latency; the durable response id is
    the normal fast-path authority.
- Use balance delta as success proof.
  - Rejected because other clients, manual activity, interest, and repayment can
    change the same balance.

## ADR-005: Serial initial implementation

### Decision

Allow at most one borrow POST in flight for the database's execution owner.
Missed ticks are discarded rather than replayed: after any slow, blocked, or
cooled-down interval the monotonic anchor resets to `now`. Reconciliation GETs
remain serialized with dispatch.

This tightens the prior direction synthesis, which allowed different tasks to
be concurrently in flight at short intervals. Boundary C intentionally rejects
that concurrency for the first debt-creating adapter.

### Alternatives Considered

- Async/multi-task concurrent writes.
  - Deferred. It adds process-wide rate coordination and more ambiguous overlap
    without being required by the current UI.

## ADR-006: Separate one-time legacy quarantine from ordinary restart

### Decision

Require process live capability, execution ownership, and a durable global
execution switch. These two lifecycle cases are distinct:

1. **One-time pre-C quarantine.** A `PRAGMA user_version` migration adds
   `live_authorized INTEGER NOT NULL DEFAULT 0`, marks legacy tasks
   unauthorized, and pauses legacy `borrowing` tasks exactly once. A later
   per-task Start explicitly authorizes the migrated task.
2. **Ordinary restart after C.** Preserve post-C authorization, task status,
   counts, and the durable global switch. Pending/orphan/unknown attempts remain
   blocked and enter bounded reconciliation. Startup reports restored
   live-authorized and orphan-blocked counts; it does not require blanket
   re-arming.

New C tasks are live-authorized at Confirm. Eligibility always includes
`success_count < success_target`; Start at target returns `completed` without
reopening eligibility.

### Alternatives Considered

- Make every task auto-live immediately after deploying C.
  - Rejected because old disabled-stage tasks were never approved as real debt.
- Pause every task after every restart.
  - Not selected for this draft because it defeats durable task automation; the
    process/global gates and orphan recovery already fail closed. Reviewers
    should challenge this decision if a stronger re-arm policy is warranted.

## ADR-007: Minimal frontend change, backend authority

### Decision

Add execution status/global stop, pre-submit target summary, and display
polling. Do not add browser scheduling, direct Binance access, or a new task
state machine.

## ADR-008: One execution owner per borrow database

### Decision

Take a non-blocking `fcntl.flock(LOCK_EX | LOCK_NB)` on the sidecar
`<borrow_db_path>.lock` before any scheduler thread exists and hold it for
process lifetime. Do not lock the SQLite database file itself. The kernel
releases ownership on process death, so recovery needs no lease, heartbeat,
wall-clock expiry, or stale-owner repair.

A non-owner process starts and serves read and task-mutation APIs, but starts no
scheduler, dispatches nothing even if tick is forced, and reports
`can_execute=false` with `block_reason="not_execution_owner"`. Its durable
mutations are honored by the owner. Ownership release occurs only during
service close/process exit and never while the scheduler runs.

The existing server construction order already prevents a common same-port
second instance from starting its scheduler, because socket bind precedes
scheduler start. That protection is real but incidental: bind port and database
path are independently configurable, so two different ports can share one
database. A second process may also open the database and run benign orphan
marker recovery before bind failure. Debt safety therefore rests on the
sidecar lock, not port binding.

### Alternatives Considered

- SQLite boot token/lease.
  - Rejected because it adds heartbeat, timeout, wall-clock trust, and stale
    lease recovery; `flock` is released automatically on crash.
- Rely on port-bind exclusivity.
  - Rejected because different ports can share the same database.
- Lock the SQLite database file.
  - Rejected because SQLite owns its database locking protocol; the advisory
    ownership lock belongs on a sidecar.

## Edge Cases Or Constraints

- Global Stop cannot cancel a request already sent; it blocks selection of the
  next one. A Stop between selection and conditional pending insert prevents
  both the row and POST. Stop does not block safe reconciliation reads, while an
  exchange cooldown blocks all signed borrow-client traffic.
- Resolve success always increments the real count. Below target, `borrowing`
  stays borrowing and `paused` stays paused; at target, both become
  `completed`. `deleted` is terminal and never changes; `completed` remains
  completed. Allowing paused-at-target to remain paused would let a later Start
  create an extra POST, so Start and eligibility independently enforce count
  below target.
- Multiple matching loan-history records remain ambiguous.
- Only a unique `CONFIRMED` row can prove success; `PENDING`, `FAILED`, an empty
  result, or an ambiguous result stays unknown.
- Invalid/missing `Retry-After` uses 60 seconds; valid values clamp to
  `[60, 300]`. A 418 applies 300 seconds and requires manual re-arm.
- Bounded reconciliation reads occur at
  `+5s/+15s/+60s/+300s/+900s`; exhaustion becomes visible
  `reconciliation_exhausted` and never authorizes another POST.
- The local execution-control API is safe only on the existing loopback bind.
- This stage adds debt creation but no automatic repay or hedge.

## Links To Prior Direction

- `reports/agent-runs/2026-07-real-borrow-execution-v1/06-direction-synthesis.md`
- `reports/agent-runs/2026-07-real-borrow-execution-v1/03-grok-borrow-api-capacity-recon.md`
- `reports/agent-runs/2026-07-real-borrow-execution-v1/13-user-decisions-and-contract-amendment.md`
- `docs/product/PRD.md`
- `docs/architecture/ARCHITECTURE.md`
- `reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/evidence-index.md`

## Reviewer Notes

- The user has deliberately selected amount/count/principal control instead of
  application-level numeric caps. Do not reintroduce caps as an implementation
  convenience; raise them only as a product finding.
- “No automatic retry for unknown” is a hard correctness requirement, not an
  optional risk preference.
- No HTTP force-clear or retry-anyway action may clear an unknown result.
- Sharing a signer does not authorize the GET-only client to make POSTs.
- No live sample is required to review or test the code. The first real request
  is an operator action after code review.

当前 Session ID: unavailable (runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/11-adr.md
本地北京时间: 2026-07-20 23:13:18 CST
下一步模型: human operator → claude-fable-5 (opus4.8 only after verified quota exhaustion)
下一步任务: run development-breakdown.prompt.md to produce canonical 12-development-breakdown.md; no implementation yet
