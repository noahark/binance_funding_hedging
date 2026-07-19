# ADR — Durable Borrow Tasks A+B

## ADR-001: Isolated local borrow-task module

### Status

Accepted for A+B.

### Context

The snapshot service owns immutable read-only market state, while borrow tasks
need mutable state, local mutations, scheduling and later an external write
adapter. Adding that behavior to snapshot assembly or the existing GET-only
client would blur the repository's current security boundary.

### Decision

Create an isolated modular-monolith borrow-task service/store/scheduler and a
separate local HTTP route family. Keep `SnapshotService`, public snapshot
schemas and `PrivateClient` independent and unchanged in role.

### Consequences

The code adds modules and route tests, but future live execution can be
reviewed as a narrow adapter rather than reopening the snapshot boundary.

## ADR-002: SQLite attempt ledger, not browser memory or JSON rewrite

### Status

Accepted for A+B.

### Context

Tasks and logs must survive refresh/restart, support newest-first paging and
eventually preserve pre-dispatch intent. Browser memory loses all of these;
JSON rewrite has weak concurrent update and query behavior.

### Decision

Use Python stdlib `sqlite3` with short transactions and a local data path. Task
state and append-only attempt records are stored separately.

### Consequences

The first mutable local database needs migration/init/recovery tests. It avoids
introducing a runtime dependency or a separate service.

## ADR-003: Global decimal round-robin dispatch clock

### Status

Accepted for A+B.

### Context

The user wants one frequency setting shared by all tasks: with A/B/C and 3
seconds, dispatch A then B then C at successive 3-second ticks. The interval
must accept decimals such as 0.5 seconds and later support throughput analysis.

### Decision

Persist a positive `Decimal`-parsed interval normalized to integer microseconds
and a durable round-robin cursor. There is no product-defined minimum interval
or local frequency cap. The scheduler records requested and actual timing.

### Consequences

Requested cadence can exceed OS/executor capability; logs expose the effective
rate. In future C, exchange 429/418 `Retry-After` temporarily overrides the
clock as protocol compliance, not as a local cap.

## ADR-004: Direct borrow attempt; history only for unknown outcomes

### Status

Accepted as the future-C contract shape; no live call in A+B.

### Context

`maxBorrowable` can become stale between read and write. A normal successful
borrow response provides a transaction identifier, while a timeout/ambiguous
response must never be treated as safe to retry.

### Decision

Do not gate a future task attempt on `maxBorrowable`. Persist a known success
with `tranId` immediately; reserve exchange history reconciliation for unknown
outcomes and periodic audit. Keep an unresolved-attempt invariant per task.

### Consequences

The normal path avoids a preflight race and extra synchronous history query.
Future C must carefully map response/error semantics and implement its own
separate signed adapter.

## ADR-005: Borrow logs are first-class, redacted API data

### Status

Accepted for A+B.

### Context

The user wants to later infer effective frequency and exchange behavior from
every borrow attempt. A transient status message cannot support that analysis.

### Decision

Persist append-only, sanitized attempt metadata and expose it via a paginated
newest-first `借币日志` view. The UI retains only latest-result summaries in task
cards.

### Consequences

Storage grows with attempts and needs bounded page queries; the design keeps
full credentials, signatures, headers and raw private payloads out of the
ledger.

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/11-adr.md
本地北京时间: 2026-07-19 15:57:10 CST
下一步模型: Fable5
下一步任务: 基于批准设计拆分后端与前端实现任务、边界、测试和审阅重点
