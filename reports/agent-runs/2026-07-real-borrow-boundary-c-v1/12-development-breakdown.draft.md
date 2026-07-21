# Draft Development Breakdown — Boundary C

Status: **bookkeeper/designer draft for independent review**. This is not yet
the registered HIGH-stage `12-development-breakdown.md`. After design review,
the registered breakdown author must adopt or amend it before implementation.

## Proposed Breakdown Author And Routing

- Registered author: Claude provider, Fable5 first and Opus4.8 after quota
  exhaustion, unless the user selects another model.
- Implementation owner: Claude-GLM (`claude_glm`) because this is a
  backend-dominant task and the frontend change is light integration.
- Review-1: fresh Kimi session.
- Review-2: Codex/GPT if eligible under the documented prior-design disclosure;
  otherwise use the workflow fallback.
- Codex is excluded from implementation and fix authorship.
- Parallel mode: disabled; one serial implementation task.

## Proposed Task C — Narrow Live Borrow Delivery

### Purpose

Implement the complete bounded Boundary C slice: verified contract evidence,
shared signer refactor, narrow live client/executor, runtime gates, migration,
reconciliation, schemas/tests, and minimal frontend live-status integration.

### Owner

- Provider/model: `claude_glm` / registered GLM backend model
- Skill: `senior_developer`

### Dependencies

Before coding:

1. Independent design review is resolved.
2. Registered `12-development-breakdown.md` exists.
3. Official public endpoint evidence exists under
   `reports/api-samples/2026-07-real-borrow-boundary-c-v1/`.
4. Exact endpoint/method/parameter/response/rate-limit assumptions in
   `10-design.md` either match the evidence or are amended and re-reviewed.
5. Stage branch remains checked out and no unrelated `_proposals` content is
   added to the stage.

### Allowed Files

- All paths listed as allowed in `00-task.md`.
- Implementation report:
  `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation.md`
- Test evidence:
  `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt`

### Forbidden Files And Behavior

- All forbidden areas from `00-task.md`.
- No live Binance DNS/network access in tests or implementation verification.
- No use of real credentials, `.env`, shell key stores, or private payloads.
- No arbitrary signed method/path/URL API.
- No `maxBorrowable` preflight, risk caps, asset allowlist, concurrent POST,
  order, hedge, sell, transfer, repay, or close.
- No Harness/workflow changes.
- No git commit, push, review dispatch, status update, or acceptance declaration
  by the implementer.

## Frozen Contracts To Implement

### Existing task routes

Do not rename or reinterpret the accepted `borrow-tasks/v1` task/list/log/edit/
interval contracts. Existing clients must continue to work.

### New execution-control routes

Proposed paths, subject to design review:

```text
GET  /api/borrow-execution-status
POST /api/borrow-execution/start
POST /api/borrow-execution/stop
```

New versioned schema:

```text
schemas/api/borrow-tasks/execution-status.schema.json
schema_version = borrow-execution/v1
```

The registered breakdown must freeze exact success and error bodies before
implementation begins.

### Dedicated credentials

```text
BINANCE_BORROW_API_KEY
BINANCE_BORROW_API_SECRET
APP_BORROW_EXECUTOR=disabled|live
```

Actual names may be amended during review, but read-only and write credentials
must remain logically separate and all names must be covered by startup-log
redaction tests.

### Result contract

Use only existing result categories:

```text
success | known_rejection | rate_limited | unknown | execution_disabled
```

Do not add provider-specific result strings to public APIs. Preserve sanitized
business code/reason/HTTP status/transaction id fields.

## Proposed Implementation Sequence

1. Capture official public contract evidence and add a short evidence index.
2. Add signer module and refactor `PrivateClient` with existing regression tests
   still enforcing GET-only exact allowlisting.
3. Add recording-transport Portfolio Margin client and exhaustive no-network
   transport tests.
4. Add `LiveBorrowExecutor` response mapping and exception containment.
5. Add store migration, legacy authorization marker, durable global switch,
   and execution-status projection.
6. Wire executor selection and global status/control handlers.
7. Add reconciliation state/query logic and restart recovery.
8. Fix pause/delete/edit in-flight semantics.
9. Add minimal frontend execution badge, confirmation summary, global stop, and
   active-view polling.
10. Run focused tests, full regression, self-check, static network/secret proofs,
    schema validation, and diff check.
11. Write the implementation report and stop for bookkeeper reconciliation.

## Evidence Commands To Freeze In The Registered Breakdown

The independent reviewer/registered author should confirm exact commands. The
minimum intended set is:

```text
python3 -m pytest backend/tests/test_borrow_domain.py \
  backend/tests/test_borrow_store.py \
  backend/tests/test_borrow_scheduler.py \
  backend/tests/test_borrow_executor.py \
  backend/tests/test_borrow_api.py \
  backend/tests/test_private_client.py \
  backend/tests/test_config.py -q
python3 -m pytest backend/tests -q
node frontend/self-check.js
python3 -m py_compile backend/services/binance_signing.py \
  backend/services/private_client.py backend/borrow_tasks/*.py \
  backend/app/server.py backend/config.py
git diff --check
```

Add a deterministic static/recording-transport proof that no test contacts a
production Binance host and that only the two verified method/path pairs are
reachable from the new client.

## Required Test Scenarios

- Configuration: default disabled, invalid mode, live without credentials,
  disabled with credentials, sanitized startup status.
- Signer: canonical payload, timestamp/recvWindow, dummy HMAC fixture, no secret
  in exception/log output.
- Client: exact allowlist, URL injection rejection, success, explicit business
  rejection, 429/418 with Retry-After, invalid Retry-After, 5xx, timeout,
  connection reset, malformed/empty response.
- Service/store: pending-before-call, no DB lock during I/O, exception
  containment, success count/completion, known-reject rotation, global cooldown,
  unknown blocking, migration quarantine, restart orphan, durable stop/start.
- Reconciliation: txId match, unique time-window match, no match, multiple
  matches, delayed match, deleted/paused task, no POST retry.
- Race: stop/pause/delete/edit while a blocking fake call is in flight; deleted
  remains deleted and the result is retained.
- Frontend: execution badge/control, pre-submit total/interval confirmation,
  old disabled copy removed, active-view polling is display-only, errors remain
  local and sanitized.
- Regression: all existing backend tests and frontend self-check.

## Review Focus

- Any path that can send a second POST after an ambiguous first result.
- Any path that makes pre-C tasks live without explicit Start.
- Whether a transport exception can terminate the scheduler thread.
- Whether signer extraction weakens the GET-only whitelist.
- Whether global Stop is checked atomically before pending insertion/dispatch.
- Whether pause/delete races lose or rewrite the in-flight result.
- Whether history matching can falsely attribute another/manual loan.
- Whether tests or docs expose credentials or contact production.
- Whether the small frontend changes have expanded into a second scheduler or
  unnecessary task-state redesign.

## Open Items For Independent Review

1. Confirm or amend the three proposed execution-control route names and exact
   schema body.
2. Confirm the dedicated credential names and whether service startup should
   fail or merely report blocked when live mode lacks credentials.
3. Freeze a conservative fallback cooldown for missing/invalid Retry-After.
4. Freeze bounded reconciliation read timing after reviewing current official
   endpoint weight and propagation expectations.
5. Decide whether normal process restart may resume post-C live-authorized
   tasks, or should pause them for re-arm. This draft proposes resume with
   orphan-attempt blocking.

当前 Session ID: unavailable (runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.draft.md
本地北京时间: 2026-07-20 19:27:29 CST
下一步模型: independent design reviewer / registered breakdown author
下一步任务: review the draft, resolve open items, then produce the canonical 12-development-breakdown.md
