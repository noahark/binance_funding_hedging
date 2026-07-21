# Stage Design — Real Borrow Boundary C

## Summary

Boundary C keeps the accepted A+B task domain and replaces only the executor
edge with an explicitly enabled live adapter. The implementation remains a
local modular monolith:

```text
existing browser task UI
        │ same-origin task/execution APIs
        ▼
BorrowTaskService ── durable global switch
        │
        ├─ persist pending attempt
        ├─ call BorrowExecutor with no store lock
        │      └─ LiveBorrowExecutor
        │             └─ narrow PortfolioMarginBorrowClient
        │                    └─ shared signing primitive
        └─ resolve typed result into SQLite
                    └─ unknown/pending → loan-record reconciliation
```

The browser never sees credentials or signed values. The existing task amount,
count, interval, progress, and log contracts remain authoritative. New UI work
is intentionally small: execution status/stop, a pre-submit target summary, and
faster read polling while the borrow view is open.

## Verified Public Contract And Fail-Closed Unknowns

The official public capture and closure matrix are archived at
`reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/`.
It verifies:

- signed `POST /papi/v1/marginLoan`, form-body parameters `asset`, `amount`,
  `timestamp`, optional `recvWindow`, IP weight 100, and success `tranId`;
- signed `GET /papi/v1/margin/marginLoan`, IP weight 10, GET `txId` equal to
  POST `tranId`, and row fields `txId`, `asset`, `principal`, `timestamp`, and
  `status`;
- Portfolio Margin IP capacity of 6000 weight/minute; and
- the three frozen definite-rejection codes and the documented rate/unknown
  error classes used below.

The current public pages do not guarantee a `Retry-After` representation or a
loan-record propagation SLA. Those remain explicit unknowns governed by the
local fallback and bounded-reconciliation policy. The complete POST parameter
table contains no idempotency key, so the design relies on write-ahead intent
and fail-closed reconciliation rather than server-side deduplication.

## Design Decisions

### D1 — Preserve the A+B task contract

`POST /api/borrow-tasks` continues to accept:

```json
{
  "asset": "HOME",
  "amount_per_attempt": "1.25",
  "success_target": 3
}
```

It creates a `borrowing` task. When live mode and the global switch are enabled,
the task becomes scheduler-eligible immediately. The Confirm interaction is the
task-level authorization; no second arm state is added.

Money remains decimal strings/`Decimal`. `amount_per_attempt × success_target`
is the maximum target quantity for that task, not a promise that every attempt
will succeed and not a USDT risk calculation.

The scheduler interval has an exchange-capacity floor, distinct from an
application exposure cap:

```text
min_interval_seconds = ceil(60 / (0.5 × ip_budget_per_min / post_weight))
```

Half the documented IP budget is reserved for reads and reconciliation. The
archived values are 6000 weight/minute and weight 100 per POST, so the frozen
minimum is two seconds; the default remains five seconds. The formula remains
the authority if a later committed public-contract amendment changes either
input.

### D2 — Two independent execution gates

1. Process capability: `APP_BORROW_EXECUTOR=live` selects the live executor.
   Default is `disabled`; unknown values fail startup.
2. Durable operational switch: stored execution state allows global Start/Stop
   without editing credentials or changing every task.

Both must permit execution. Global Stop prevents selection of new attempts but
does not claim to cancel a request already sent.

Frozen new same-origin contract:

```text
GET  /api/borrow-execution/status
POST /api/borrow-execution/start
POST /api/borrow-execution/stop
```

Start and Stop accept no body, are idempotent, and return HTTP 200 with the same
document as GET. Stop has no optimistic-concurrency version that could prevent
a safety action. The schema is
`schemas/api/borrow-tasks/execution-status.schema.json`, has
`schema_version = "borrow-execution/v1"`, and rejects additional properties.

Status response:

```json
{
  "schema_version": "borrow-execution/v1",
  "mode": "live",
  "execution_enabled": true,
  "can_execute": true,
  "block_reason": null,
  "in_flight_attempt_id": null,
  "global_cooldown_until": null,
  "live_authorized_task_count": 0,
  "updated_at": "2026-07-20T11:30:00.000000Z"
}
```

`mode` is process configuration; `execution_enabled` is durable operator state;
`execution_enabled` defaults false on fresh and migrated databases.
`can_execute = mode==live AND execution_enabled AND credentials_present AND
is_execution_owner`; the transient cooldown is deliberately not folded into
this stable capability flag. `block_reason` is one of
`executor_disabled`, `globally_stopped`, `borrow_credentials_missing`,
`not_execution_owner`, `rate_limited`, or `invalid_configuration`, never an
environment value. `in_flight_attempt_id` is transient process memory;
`unresolved_attempt_id` remains the durable per-task blocker. Missing live
credentials do not kill the snapshot/UI service: they produce
`can_execute=false`, `borrow_credentials_missing`, a distinct sanitized
lifecycle event, and zero signed borrow traffic. An invalid executor enum still
fails at configuration load.

### D3 — Separate write client, shared signer

The current `PrivateClient` is intentionally GET-only and currently contains
the repository's single HMAC construction. Boundary C must not add a second
ad-hoc signature implementation or make `PrivateClient` generally writable.

Create `backend/services/binance_signing.py` as the single signature primitive,
`backend/services/portfolio_margin_borrow_client.py` as the exact-path
transport, and `backend/services/live_borrow_executor.py` as the typed executor.
The executor is injected through `BorrowTaskService(executor=...)`;
`backend/borrow_tasks/**` imports no service/network/signing module. The
existing GET-only client and the new borrow client call the signer while
retaining independent method/path allowlists:

- read client: its current GET allowlist only;
- borrow client: only the verified Portfolio Margin borrow POST and loan-record
  GET;
- hardcoded `https://papi.binance.com`; no caller-supplied URL/path/method;
- dedicated `BINANCE_BORROW_API_KEY` and `BINANCE_BORROW_API_SECRET` variables;
- no retries inside the POST transport.

One serialization function produces the payload string used for both signing
and sending. The borrow POST uses the archived
`application/x-www-form-urlencoded` body form and never splits a parameter
between query and body. The new client has its own gate-before-signing negative
test. The existing static guards may add only the exact new filenames;
wildcard, prefix, or directory-wide exemptions are forbidden.

The live executor receives structured transport results, never raw urllib/HTTP
objects.

### D4 — Single-owner serial write dispatch

The initial live implementation stays synchronous at the executor boundary and
uses the existing service tick lock. In addition, exactly one process may own
execution for a SQLite database. Before any scheduler thread exists, the
service takes `fcntl.flock(LOCK_EX | LOCK_NB)` on the sidecar file
`<borrow_db_path>.lock` and holds it for process lifetime. A non-owner process
starts normally, serves read and task-mutation APIs, starts no scheduler,
dispatches nothing even when tick is forced, and reports
`block_reason="not_execution_owner"`. Kernel lock release supplies crash
recovery; no lease, heartbeat, expiry, or database-file locking is added.

The existing same-port bind failure blocks the common accidental second
process, but it is incidental: different `APP_BIND_PORT` values can still share
one `APP_BORROW_DB_PATH`, so port binding is not the debt-safety mechanism.

Missed ticks are never replayed. After a skipped, blocked, cooled-down, or slow
interval, `_last_tick_mono` advances to `now`, not by one accumulated interval.
A 60-second cooldown at a five-second interval must produce at most one dispatch
in the next three seconds, never a burst of historical ticks. The attempt log
records actual times and latency.

No asynchronous/concurrent POST worker is added. Reconciliation GETs are also
serialized by the service so they cannot race a duplicate borrow for the same
task.

### D5 — Result classification is fail closed

| Observation | Typed result | Scheduler effect |
| --- | --- | --- |
| 2xx JSON with valid non-empty `tranId` | `success` | persist id, increment count, complete at target |
| business code `-51006`, `-51014`, or `-51061` | `known_rejection` | record; task remains in rotation |
| HTTP 400 with business code `-1003`, or HTTP 429 | `rate_limited` | record; global cooldown |
| HTTP 418 | `rate_limited` | 300s global cooldown, then wait for manual global Start |
| timeout/connection loss after dispatch | `unknown` | block task; reconcile |
| malformed/empty 2xx | `unknown` | block task; reconcile |
| 5xx unless official evidence proves definite rejection | `unknown` | block task; reconcile |
| unexpected executor exception | `unknown` or unresolved pending | block task; scheduler stays alive |

No automatic POST retry occurs inside the transport. Known rejection retries
only through a later ordinary scheduler turn. Unknown never retries as a POST.
The public evidence freezes the known-rejection allowlist to `-51006`,
`-51014`, and `-51061`; every unlisted 4xx is `unknown`.
`tranId` is normalized through one arbitrary-precision-safe string path and is
never parsed through float. Missing, invalid, non-numeric, or non-positive
`Retry-After` becomes 60 seconds; a valid value is clamped to `[60, 300]`
seconds. The 418 branch applies a 300-second minimum local cooldown, never
auto-resumes, and must be re-armed by global Start; the archived two-minute to
three-day ban range means expiry of the local cooldown is not evidence that an
exchange ban has ended. The borrow POST has its own test-overridable module
constant of 10 seconds; it does not reuse the snapshot read timeout and is not
environment-configurable.

`_dispatch_one` contains executor exceptions after pending insert and maps them
to unknown/unresolved without re-raising. `BorrowScheduler._loop` has a
last-resort guard so a store/projection exception cannot silently terminate the
scheduler thread.

### D6 — Reconciliation proves success, not failure-by-absence

The conditional pending-insert transaction re-checks execution ownership,
`status=borrowing`, `live_authorized=1`, the durable global switch, cooldown,
`unresolved_attempt_id IS NULL`, and
`success_count < success_target`. In one transaction it inserts pending,
advances the cursor, and assigns `unresolved_attempt_id`; a failed predicate
creates no row and no POST. The marker clears only on a terminal non-unknown
resolution. Every pending/unknown attempt is therefore durable and ineligible
before network I/O.

Reconciliation queries the verified loan-record endpoint at five bounded
delays measured from becoming unresolved:

```text
+5s → +15s → +60s → +300s → +900s
```

After the fifth read it enters visible terminal
`reconciliation_exhausted`; the task remains blocked and no second POST is
authorized. Global operator Stop blocks POSTs but not safe history reads. A
rate-limit cooldown blocks every signed borrow-client call, including history
GETs. Matching rules are:

- when a known `tranId` exists, query/match by its documented transaction key;
- for a response-less unknown, query by the archived `startTime`/`endTime`
  contract over a bounded, dispatch-anchored window and require exact asset
  plus `Decimal(principal) == Decimal(requested_amount)`;
- only one unique `CONFIRMED`, contract-valid record resolves the attempt as
  success; `PENDING` and `FAILED` never prove success;
- no match, delayed visibility, multiple candidates, or cross-task ambiguity
  leaves the task blocked;
- account balance deltas are corroboration only and cannot uniquely attribute
  a loan.

The archived GET contract explicitly maps response-row `txId` to POST
`tranId`. On reconciliation-proven success, persist the matched `txId` in
`tran_id` and use
`reason="reconciled_unique_txid_match"`. History and response paths share the
same identifier/Decimal normalizers. No HTTP force-clear or “retry anyway”
action exists. The public contract supplies no propagation SLA; the five-read
sequence is therefore a conservative local policy, and absence at any point is
never proof of failure.

### D7 — Pre-C task quarantine

The existing database can contain `borrowing` tasks whose attempts were safely
disabled. Use `PRAGMA user_version` as an idempotent schema gate and add
`live_authorized INTEGER NOT NULL DEFAULT 0`. On the one-time migration:

- add an internal live-authorization marker/version;
- mark all pre-C tasks as not live-authorized;
- transition any pre-C `borrowing` task to `paused` once, preserving counts and
  logs;
- a later per-task explicit Start marks it live-authorized and makes it
  eligible only while `success_count < success_target`.

New tasks created after the C migration are live-authorized by their Confirm
action. The exact eligibility predicate is
`status='borrowing' AND unresolved_attempt_id IS NULL AND live_authorized=1 AND
success_count < success_target`. A Start at or above target returns the task as
`completed` instead of making it borrowing. Normal process restart preserves
post-C authorization, status, global switch, and counts; startup reports the
number of live-authorized tasks and recovered orphan blockers. Any orphaned
pending attempt blocks its task before scheduling resumes.

### D8 — Pause/delete/edit races

An attempt snapshots the asset and requested amount before dispatch. Stop,
pause, or delete that lands before the atomic conditional insert prevents the
attempt row and POST. Once request bytes leave the process, resolution is never
suppressed. Resolve-time success follows this matrix:

| Status at resolution | Count effect | Status effect |
| --- | --- | --- |
| `borrowing`, remains below target | +1 | remains `borrowing` |
| `borrowing`, reaches target | +1 | `completed` |
| `paused`, remains below target | +1 | remains `paused` |
| `paused`, reaches target | +1 | `completed` |
| `deleted` | +1 | always remains `deleted` |
| `completed` | +1 | remains `completed` |

For every result:

- the already-dispatched result is always resolved and audited;
- pause/delete prevents every later attempt;
- edit affects only later attempts;
- non-success categories do not change task status;
- Start at target normalizes/returns `completed` and never permits another POST;
- an unknown in-flight result retains its reconciliation marker even when the
  task is paused/deleted.

### D9 — Minimal frontend amendment

The current page structure and task APIs remain recognizable. Add only:

- an execution badge (`disabled`, `live enabled`, `globally stopped`, or
  sanitized configuration block);
- global Start/Stop control;
- the nullable global cooldown and each task's derived
  blocked/reconciling/exhausted condition;
- before-create confirmation text containing asset, amount, count, computed
  maximum target quantity, and current global interval;
- active-view polling of execution status/tasks at a modest UI cadence such as
  two seconds; this is display refresh only;
- removal of A+B text claiming all attempts are disabled.

Logs remain explicitly refreshable/paginated; implementation may refresh their
first page after a task mutation or while the log tab is active, but the browser
does not schedule attempts.

The frontend self-check must be narrowed exactly twice: allow the one selected
borrow-view polling delay in the timer whitelist, and allow POST only for the
two `/api/borrow-execution/{start,stop}` routes in the fetch-method whitelist.
No general POST or timer exemption is allowed.

### D10 — Sanitized observability

Persist/log only:

- logical endpoint name, method, HTTP status, Binance business code, sanitized
  reason category, latency, `Retry-After`, used-weight numeric counters when
  present, and transaction id;
- never API key/secret, signature, full query, authorization headers, raw
  private response bodies, or full environment dumps.

Lifecycle logs state `borrow_executor=disabled|live` and
`borrow_execution_enabled=true|false` without credential details.

## Task Breakdown

### Contract evidence and design confirmation

- Consume the closed public evidence at the stage API-sample path.
- Preserve every `CLOSED_WITH_FAIL_CLOSED_DEFAULTS` distinction; do not promote
  an undocumented header, propagation SLA, precision rule, or limit family to
  a verified fact.

### Single backend-dominant implementation task

- Implement signer refactor, live client/executor, configuration/wiring,
  durable global switch, migration quarantine, reconciliation, schemas, tests,
  and the small frontend integration.
- Default owner: Claude-GLM under the repository's backend-dominant routing.
- Codex/GPT must not implement or fix code.

### Review

- Review-1: fresh Kimi session, cross-provider from Claude-GLM.
- Review-2: Codex only if it did not author/fix code; disclose prior stage-design
  involvement as required by the strong-reviewer rule or use an eligible
  unrelated final reviewer.

## Test Strategy

### Unit tests

- Exact method/path allowlists and shared signer canonicalization.
- Single-owner lock acquisition, non-owner status, absent scheduler, and forced
  tick no-dispatch behavior.
- Credential absence, redaction, and fail-closed configuration.
- Success/rejection/`-1003`/429/418/manual-rearm/unknown classification.
- Decimal amount preservation and `tranId` validation.
- Global execution start/stop state.
- Legacy-task migration and restart orphan blocking.
- Reconciliation unique/no/multiple match behavior.
- Reconciliation cross-task ambiguity and exhausted terminal behavior.
- Pause/delete/edit during an injected blocking executor call, including
  paused-at-target completion, deleted-terminal success, and Start at target.
- Executor and scheduler-loop exception containment; no missed-tick catch-up.

### Integration tests

- Recording transport verifies exact host/path/method/parameter names with
  dummy credentials and no network.
- HTTP handlers validate all old and new response schemas.
- End-to-end fake live task: create → pending → fake POST success → progress →
  completion.
- Unknown path: create → fake timeout → blocked → fake history match → success.
- Global stop and rate-limit cooldown prevent later dispatches.
- Recording transport proves exactly one POST for each error/response class.
- Existing A+B SQLite database fixture migrates without live eligibility.

### Regression

- Full backend pytest suite.
- Frontend self-check.
- Static proof that no tests resolve Binance production hosts; exact five-guard
  signer/urlopen/AST/timer/fetch-method enforcement with dual assertions.
- Secret-pattern/redaction checks.
- `git diff --check` and Python compilation.

### Manual checks

- Local UI with recording transport only: execution badge, confirmation
  summary, global stop, task progress, blocked state, and log rendering.
- No real credential or Binance POST in implementation/review evidence.

## Risks

- Ambiguous network results can create duplicate debt if treated as failure.
- Enabling live mode against an old database can unintentionally run stale tasks.
- A signer refactor can weaken the read-only client's deny-by-default property.
- A low configured interval can consume documented request weight quickly.
- Two processes can share a database on different ports; the sidecar ownership
  lock, not incidental same-port bind failure, is the execution authority.
- The interval is not a throughput promise; sub-floor cadence would risk a
  shared-IP ban affecting the read-only product, so the evidence-derived floor
  is a correctness constraint.
- Pause/delete cannot recall a request already accepted by Binance.
- Borrow-only scope creates naked debt; no hedge or repay automation exists.
- The local same-origin control surface assumes the server remains bound to
  loopback; public binding is out of scope and unsafe for this control model.

## Raw Artifact Requirements For Review

- `00-intake.md`
- `00-task.md`
- `10-design.md`
- `11-adr.md`
- `12-development-breakdown.draft.md`
- prior approved synthesis and capacity recon
- official public contract evidence once captured
- actual committed diff and deterministic test output after implementation

当前 Session ID: unavailable (runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/10-design.md
本地北京时间: 2026-07-20 23:13:18 CST
下一步模型: human operator → claude-fable-5 (opus4.8 only after verified quota exhaustion)
下一步任务: run development-breakdown.prompt.md to produce canonical 12-development-breakdown.md; no implementation yet
