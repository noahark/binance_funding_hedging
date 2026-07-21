# Stage Task — Real Borrow Boundary C

## Stage ID

`2026-07-real-borrow-boundary-c-v1`

## Goal

Connect the accepted durable borrow-task backend to a narrowly allowlisted,
real Binance Portfolio Margin borrow executor while preserving the existing
frontend task workflow. A confirmed task may create real debt only when the
process is explicitly configured for live execution and the global execution
switch is enabled.

The completed product must persist intent before dispatch, count a success only
after durably recording a valid exchange `tranId`, stop duplicate attempts on
an unknown result, reconcile ambiguous attempts through the verified loan
record API, obey exchange rate-limit cooldowns, quarantine pre-C tasks, and
offer a fast global stop for new attempts.

## User-Frozen Product Decisions

- The existing market-row amount and successful-count inputs remain the main
  task definition.
- Clicking Confirm creates and authorizes the task; there is no new draft/arm
  workflow.
- Ordinary risk limits are controlled by the user's account principal,
  `amount_per_attempt`, and `success_target`.
- The application does not add a USDT-equivalent cap, asset allowlist, or
  `maxBorrowable` preflight in this stage.
- The backend is authoritative; the browser never signs, schedules, retries,
  or contacts Binance directly.
- Execution starts serially: at most one Binance borrow POST may be in flight
  from this process at a time.
- The scheduler never replays missed ticks. The minimum interval is an
  exchange-capacity constraint derived from verified request weight and IP
  budget; the frozen floor is two seconds and the default remains five.

## Scope

### Backend

- Add a separate, exact-path Portfolio Margin write/reconciliation client.
- Refactor signature construction into one shared signing primitive without
  weakening the existing GET-only `PrivateClient` whitelist.
- Add a production `LiveBorrowExecutor` implementing the existing
  `BorrowExecutor` port.
- Enforce one execution owner for each borrow-task SQLite database with a
  non-blocking sidecar advisory lock; non-owner processes remain available for
  read and task-mutation APIs but never start a scheduler.
- Wire `disabled` and `live` executor selection into process configuration and
  server startup; default remains disabled.
- Add a durable global execution switch and read-only execution-status
  projection.
- Quarantine tasks created before the Boundary C schema/migration so enabling
  live mode cannot execute old disabled-stage tasks silently.
- Map every transport and exchange response into the frozen result categories.
- Reconcile pending/unknown attempts with the loan-record endpoint and never
  repeat an ambiguous attempt automatically.
- Preserve sanitized audit evidence without keys, signatures, signed queries,
  headers containing credentials, or full private response bodies.

### Minimal frontend integration

- Replace stale “execution disabled/no real borrow” copy.
- Display backend execution mode/global-stop state.
- Show amount × count = maximum target quantity and current interval before
  creating an immediately runnable task.
- Add a global stop/start control backed by the server.
- Refresh active task/execution state fast enough for supervised use, without
  turning the browser into an execution clock.

### Contract evidence

- The refreshed official public POST, loan-record GET, capacity, and error-code
  contract is archived under
  `reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/`.
  Its `evidence-index.md` is the implementation authority for verified facts
  and named fail-closed defaults.
- No authenticated sample or live POST is collected by development tests.

## Non-Goals

- Repay, transfer, spot sale, futures hedge/order, automatic close, or any
  other Binance write endpoint.
- Automatic trade execution after borrowing.
- Browser-side credentials, signing, retry loops, or task authority.
- A new general-purpose Binance write client.
- `maxBorrowable` as a synchronous precondition for each attempt.
- App-level principal accounting, asset allowlists, USDT exposure conversion,
  or additional numeric risk caps.
- Parallel/concurrent borrow POSTs.
- A live load/stress/frequency test.
- A CI test or Harness gate that creates real debt.
- Changes to the public-market snapshot schema or existing read-only account
  semantics except the minimal signer refactor required to preserve one HMAC
  implementation.

## File Boundaries

Allowed product/source files:

- `backend/borrow_tasks/**`
- `backend/services/binance_signing.py` (new shared signing primitive)
- `backend/services/portfolio_margin_borrow_client.py` (new exact-path PM
  borrow/history transport)
- `backend/services/live_borrow_executor.py` (new typed live executor)
- `backend/services/private_client.py` (signer refactor only; remains GET-only)
- `backend/app/server.py`
- `backend/config.py`
- `backend/tests/test_borrow_*.py`
- `backend/tests/test_private_client.py`
- `backend/tests/test_binance_signing.py`
- `backend/tests/test_portfolio_margin_borrow_client.py`
- `backend/tests/test_live_borrow_executor.py`
- `backend/tests/test_config.py`
- `backend/tests/test_service_health.py` or `backend/tests/conftest.py` only if
  required for server wiring tests
- `schemas/api/borrow-tasks/**`
- `frontend/index.html`
- `frontend/self-check.js`
- `.env.example`
- `scripts/run-server.sh`
- `scripts/tests/test_service_control.py` only if credential/redaction startup
  behavior changes
- `docs/architecture/ARCHITECTURE.md`
- `docs/development/DEVELOPMENT_GUIDE.md`
- `docs/product/PRD.md` only for an accurate built-state update after acceptance
- `reports/api-samples/2026-07-real-borrow-boundary-c-v1/**` for public,
  non-secret contract evidence
- this stage directory for reports and evidence

Forbidden or out-of-scope files/areas:

- `backend/domain/**` and public snapshot schemas
- order, repay, transfer, sell, hedge, or close endpoints
- Harness/workflow/validator changes
- unrelated historical stages
- `.env`, key files, credential stores, cookies, signed queries, or private raw
  account payloads

## Acceptance Criteria

1. Runtime defaults to disabled. A missing/invalid live configuration or
   missing dedicated borrow credentials fails closed without sending a request.
   An invalid executor mode fails startup; live mode with missing credentials
   keeps the read-only product available but reports
   `borrow_credentials_missing` and emits zero signed borrow traffic.
2. The existing `PrivateClient` remains exact-path GET-only. One shared module
   contains signature construction; the new client has its own exact method and
   path allowlist containing only the verified borrow POST and loan-record GET.
   Signing and sending consume the same serialized payload bytes; both live
   modules live under `backend/services/` and are injected through the existing
   executor seam, while `backend/borrow_tasks/**` remains network/signing-free.
3. Before any network I/O, one pending-insert transaction re-checks execution
   ownership, task status, `live_authorized`, durable global Start, cooldown,
   `unresolved_attempt_id IS NULL`, and
   `success_count < success_target`. It inserts pending, advances the cursor,
   and sets `unresolved_attempt_id` atomically. A failed check creates no
   attempt row and no POST. No DB lock/transaction is held during I/O.
4. A 2xx response counts as success only when its JSON contains a valid
   `tranId`, which is persisted in the same resolution transaction that bumps
   `success_count`.
5. `known_rejection` is limited to the stage-archived codes `-51006`, `-51014`,
   and `-51061`. An unlisted 4xx becomes `unknown`; HTTP 400 with business code
   `-1003`, 429, and 418 become `rate_limited`;
   2xx without a valid normalized `tranId`, timeout, connection loss,
   malformed success, and possibly accepted 5xx become `unknown`.
6. Executor bugs/exceptions cannot kill the scheduler or leave the task
   eligible. Containment exists around executor dispatch and at the scheduler
   loop; the attempt remains/resolves unknown and the task is blocked.
7. An unresolved task never sends another borrow POST. Reconciliation uses the
   verified loan-record contract at `+5s/+15s/+60s/+300s/+900s`; a unique,
   contract-valid match may resolve success, while no match, multiple matches,
   cross-task ambiguity, or exhaustion remains blocked. No HTTP force-clear or
   retry-anyway route exists.
8. Pre-C tasks cannot execute merely because the process changes to live mode.
   They require a post-migration explicit Start action.
9. Global Stop is checked atomically in the conditional pending insert and
   prevents every POST not yet dispatched. It does not rewrite or discard an
   in-flight attempt. Stop blocks new debt but not safe reconciliation GETs;
   an exchange rate-limit cooldown blocks all signed borrow-client traffic.
10. Pause/delete during I/O prevents later attempts. Every dispatched result is
    recorded. A success increments the durable count: `borrowing` stays
    borrowing below target and completes at target; `paused` stays paused below
    target and completes at target; `deleted` always stays deleted; `completed`
    stays completed. Eligibility and Start both reject a task whose count has
    already reached its target, guaranteeing zero extra POSTs.
11. Existing amount/count/edit/interval/task/log API behavior remains compatible.
    Minimal new execution-status/start/stop contracts are schema-validated.
12. The UI clearly says whether real execution is available/enabled/stopped,
    exposes the global cooldown and each task's blocked/reconciling condition,
    confirms target total and interval before create, and displays progress
    without controlling dispatch.
13. Fake/recording transport tests cover success, known rejection, 429/418 and
    `-1003`, timeout, connection loss, 5xx, malformed JSON, large-integer
    `tranId`, Decimal matching, restart-orphan recovery, idempotent migration,
    stop/pause/delete races, paused-at-target completion, Start-at-target,
    cooldown catch-up prevention, exception containment, one-shot POST, and
    credential redaction. Existing HMAC, urlopen, borrow-package import, UI
    timer, and UI fetch-method guards receive exact-file/route amendments only,
    never wildcard or directory exemptions.
14. No automated test, review command, or model action performs a live Binance
    write. Full backend regression and frontend self-check pass.
15. Exactly one process owns execution for a database. Ownership uses
    `fcntl.flock(LOCK_EX | LOCK_NB)` on `<borrow_db_path>.lock`, acquired before
    any scheduler starts and held for process lifetime. A second process starts
    no scheduler, dispatches nothing even if tick is forced, remains available
    for read/mutation APIs, and reports `not_execution_owner`.

## Human Gates

- The human operator supplies a separate write-capable API key locally and is
  responsible for Binance-side permissions and IP restrictions.
- The operator, not any model, enables live process mode/global execution.
- The first live task is created by the human only after review; the stage does
  not prescribe or guess its asset, amount, count, or interval.
- Borrow-only scope creates naked debt and does not automatically hedge or repay.

## Designer

- Model/provider: Codex/GPT
- Role: stage designer and bookkeeper; excluded from implementation/fix
- Date: 2026-07-20

当前 Session ID: unavailable (runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/00-task.md
本地北京时间: 2026-07-20 23:13:18 CST
下一步模型: human operator → claude-fable-5 (opus4.8 only after verified quota exhaustion)
下一步任务: run development-breakdown.prompt.md to produce canonical 12-development-breakdown.md; no implementation yet
