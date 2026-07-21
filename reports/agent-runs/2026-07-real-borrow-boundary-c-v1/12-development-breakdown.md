# Canonical Development Breakdown — Real Borrow Boundary C

Stage: `2026-07-real-borrow-boundary-c-v1`

Status: **registered HIGH-stage canonical breakdown.** This supersedes
`12-development-breakdown.draft.md` (historical, non-authoritative). It records
decisions already frozen by the Opus 4.8 round-2 adjudication
(`design-review-round-2.opus.raw-output.md`, verdict
`PASS_TO_DESIGN_AMENDMENT`) and the amended `00-task.md` / `10-design.md` /
`11-adr.md`; it does not re-open any of them. Where the draft left five open
items, all five are now closed (see §0). This document is written to let the
bookkeeper mechanically prepare a single implementation dispatch with no
remaining architectural choice.

Authority order used to resolve any conflict, per the breakdown prompt:
`AGENTS.md` → workflow/registry → round-2 §3/§5 → amended task/design/ADR →
public contract evidence. The draft is not authority.

Evidence gate: `CLOSED_WITH_FAIL_CLOSED_DEFAULTS` at
`reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/evidence-index.md`.
The §8 public-evidence preconditions are satisfied and remain binding.
Implementation remains **unauthorized** until the bookkeeper prepares its
human-operated dispatch.

---

## 0. Draft open items — all closed

| Draft open item | Frozen decision | Source |
| --- | --- | --- |
| 1. Execution-control route names + schema body | Unified prefix `GET /api/borrow-execution/status`, `POST /api/borrow-execution/start`, `POST /api/borrow-execution/stop`; body = `borrow-execution/v1`, `additionalProperties:false` | round-2 §3.2 |
| 2. Credential names + startup-fail vs blocked | `BINANCE_BORROW_API_KEY` / `BINANCE_BORROW_API_SECRET`; live+missing creds → service starts, `can_execute=false`, `block_reason="borrow_credentials_missing"`, zero signed traffic; invalid mode still hard-fails at config load | round-2 §3.3 |
| 3. Missing/invalid `Retry-After` fallback | 60s fallback; valid values clamped to `[60s, 300s]`; 418 → 300s + manual re-arm | round-2 §3.4 |
| 4. Bounded reconciliation read timing | `+5s / +15s / +60s / +300s / +900s`, then terminal `reconciliation_exhausted` | round-2 §3.5 |
| 5. Normal restart: resume vs re-arm | Resume post-C authorization/status/counts/global switch; orphan pending attempts stay blocked and enter reconciliation; startup reports recovery counts | ADR-006 / D7 |

No open architectural item remains. If the implementer finds a genuine
conflict, they must stop with `ESCALATED` and not renegotiate requirements.

---

## 1. Single Task C — ownership and routing

- **Task id (machine, must match `status.json.tasks[0].id`):** `C`
- **Task name (descriptive):** `boundary-c-live-borrow`
- **Shape:** one serial, backend-dominant implementation task. Parallel mode and
  embedded review are **off**. Not split; the frontend change is light display
  integration with no separable second workload.
- **Implementation owner:** `claude_glm` / `glm-5.2[1m]`, skill
  `senior_developer`, under the registry backend-dominant routing
  (`agents/registry.yaml` `mixed_stage_policy`: backend/API/schema/normalization
  is the large majority; frontend is light integration → whole task to
  `claude_glm`).
- **Review-1:** fresh `kimi` session (cross-provider from `claude_glm`, per
  `review_1_selection_rules`). Read-only/plan session, raw artifacts only.
- **Review-2:** Codex/GPT only if eligible under strong-reviewer prior-design
  disclosure; otherwise an eligible unrelated final reviewer via the documented
  fallback. Codex is **excluded from implementation and fix authorship**.
- **Codex/GPT must not implement or fix code** in this stage.
- This breakdown is design involvement for review-2 disclosure purposes.

### Dependencies before coding

1. Registered breakdown (this file) exists. ✅ (this document)
2. Evidence gate closed under
   `reports/api-samples/2026-07-real-borrow-boundary-c-v1/`. ✅
   (`CLOSED_WITH_FAIL_CLOSED_DEFAULTS`)
3. Stage branch `stage/2026-07-real-borrow-boundary-c-v1` checked out; no
   unrelated `_proposals` content added to the stage.
4. Design/ADR/task match the evidence or are amended and re-reviewed. ✅
   (round-2 applied).

---

## 2. File boundaries

### Allowed product/source files

Exact live module names are **frozen**:

- `backend/services/binance_signing.py` — single shared HMAC/signature
  primitive (new).
- `backend/services/portfolio_margin_borrow_client.py` — exact-path PM
  borrow POST + loan-record GET transport (new).
- `backend/services/live_borrow_executor.py` — typed live executor
  implementing the existing `BorrowExecutor` port (new).
- `backend/services/private_client.py` — signer **refactor only**; stays
  exact-path GET-only. Must not become generally writable.
- `backend/borrow_tasks/**` — domain/store/service/scheduler edits for the
  durable global switch, migration, eligibility predicate, resolve matrix,
  reconciliation, ownership-lock acquisition, status projection. **Stays
  network/signing-free**; the executor is *injected* through
  `BorrowTaskService(executor=...)`, never imported.
- `backend/app/server.py` — executor selection, dependency injection,
  ownership-lock acquisition/start ordering, three new route handlers,
  `_is_borrow_path` extension, blocked-credentials lifecycle event.
- `backend/config.py` — remove the `live` reject branch (keep invalid-enum
  hard-fail); add two credential fields.
- `schemas/api/borrow-tasks/**` — new `execution-status.schema.json`; reuse
  existing `error.schema.json`.
- `frontend/index.html`, `frontend/self-check.js` — minimal execution UI and the
  two exact self-check guard amendments.
- `.env.example`, `scripts/run-server.sh` — new env names (documentation only).
- Tests (see §5): `backend/tests/test_borrow_*.py`,
  `backend/tests/test_private_client.py`, `backend/tests/test_binance_signing.py`,
  `backend/tests/test_portfolio_margin_borrow_client.py`,
  `backend/tests/test_live_borrow_executor.py`, `backend/tests/test_config.py`,
  and `backend/tests/conftest.py` / `test_service_health.py` /
  `scripts/tests/test_service_control.py` **only if** server wiring / credential
  redaction startup behavior requires it.
- Docs after acceptance only:
  `docs/architecture/ARCHITECTURE.md`, `docs/development/DEVELOPMENT_GUIDE.md`,
  `docs/product/PRD.md` (accurate built-state update).
- Stage report artifacts:
  `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation.md`,
  `.../60-test-output.txt`.

### Forbidden / do-not-touch

- `backend/domain/**` and public snapshot schemas.
- Any order / repay / transfer / sell / hedge / close endpoint or client.
- A general-purpose signed request client accepting arbitrary method/path/URL.
- `maxBorrowable` preflight, app-level USDT caps, asset allowlists, principal
  accounting, concurrent/async POST workers, browser scheduling, draft/arm
  lifecycle.
- Harness/workflow/validator changes; unrelated historical stages.
- `.env`, key files, credential stores, cookies, signed queries, private raw
  account payloads.
- No git commit, push, review dispatch, `status.json` update, or acceptance
  declaration **by the implementer**.

---

## 3. API and data contracts (frozen)

### 3.1 Existing task contracts — unchanged

`POST/GET /api/borrow-tasks`, `/api/borrow-tasks/{id}/{start,pause,delete,edit}`,
`/api/borrow-logs`, `/api/borrow-scheduler-settings` keep their accepted
`borrow-tasks/v1` behavior. Existing clients must keep working. Money stays
decimal strings / `Decimal`; never parse amounts or ids through float.

### 3.2 New execution-control routes (unified prefix)

```text
GET  /api/borrow-execution/status
POST /api/borrow-execution/start
POST /api/borrow-execution/stop
```

- `_is_borrow_path` (`server.py`) gains exactly **one** prefix entry
  (`/api/borrow-execution` + `/api/borrow-execution/`), matching the existing
  `/api/borrow-tasks` prefix-dispatch style.
- `start` / `stop` take **no body**, are **idempotent**, and return HTTP 200
  with the identical document returned by `status`.
- **No optimistic-concurrency `version`** on `stop` (or `start`): a safety Stop
  must never fail a concurrency check.
- Errors reuse `schemas/api/borrow-tasks/error.schema.json`.

### 3.3 Status document — `borrow-execution/v1`

Schema `schemas/api/borrow-tasks/execution-status.schema.json`,
`schema_version = "borrow-execution/v1"`, `additionalProperties: false`:

```json
{
  "schema_version": "borrow-execution/v1",
  "mode": "disabled|live",
  "execution_enabled": true,
  "can_execute": true,
  "block_reason": null,
  "in_flight_attempt_id": null,
  "global_cooldown_until": null,
  "live_authorized_task_count": 0,
  "updated_at": "2026-07-20T11:30:00.000000Z"
}
```

- `mode` = process configuration (`APP_BORROW_EXECUTOR`).
- `execution_enabled` = durable operator switch; **defaults `false` on both
  fresh and migrated databases**.
- `can_execute = (mode == "live") AND execution_enabled AND credentials_present
  AND is_execution_owner`. The transient cooldown is **deliberately excluded**
  so the badge does not flicker enabled/disabled during ordinary 429 handling
  (round-2 §3.8).
- `global_cooldown_until` — nullable ISO string; **must be exposed** so a
  supervising operator can explain why enabled execution is idle.
- `in_flight_attempt_id` — **transient, in-memory**; absent after restart (that
  is correct). Set immediately before `executor.execute`, cleared in every
  resolve path including the exception branch.
- `unresolved_attempt_id` — **durable** per-task blocker (not in this document;
  it is the store column); set inside the pending-insert transaction, cleared
  only on a terminal non-`unknown` resolution.
- `block_reason` is a sanitized enum, **never** an environment value:
  `executor_disabled`, `globally_stopped`, `borrow_credentials_missing`,
  `not_execution_owner`, `rate_limited`, `invalid_configuration`.
- Kimi F9 (derive in-flight from pending ledger rows) is **rejected**: after a
  crash a pending row is an orphan, not an in-flight request; reporting it as
  in-flight would tell the operator a request is running when none is.

### 3.4 Credentials and mode

```text
APP_BORROW_EXECUTOR = disabled | live      (default: disabled)
BINANCE_BORROW_API_KEY
BINANCE_BORROW_API_SECRET
```

- `APP_BORROW_EXECUTOR` not in `{disabled, live}` → `ValueError` at config load,
  before any bind (preserves the existing invalid-enum hard-fail semantics; the
  A+B branch at `backend/config.py` that rejects any non-`disabled` value is the
  code being narrowed — remove the reject-`live` part, keep the invalid-enum
  raise).
- `live` + missing/empty key or secret → process starts; `mode="live"`,
  `can_execute=false`, `block_reason="borrow_credentials_missing"`, zero signed
  borrow-client traffic. `_emit_lifecycle` emits a distinct startup event with
  `borrow_executor=live` and `borrow_execution_blocked=borrow_credentials_missing`;
  the frontend badge renders the blocked state unmissably.
- `disabled` + credentials present → normal start; credentials never read,
  never logged.

---

## 4. Wiring, migration, transaction boundaries

### 4.1 Config wiring (`backend/config.py`)

- **Remove** the branch that raises for `borrow_executor == "live"` (the A+B
  guard that permits only `disabled`). **Keep** the invalid-enum hard-fail for
  any value outside `{disabled, live}`.
- Add two credential fields (`BINANCE_BORROW_API_KEY`,
  `BINANCE_BORROW_API_SECRET`) read via the existing env helpers. They are never
  logged and never appear in any lifecycle/status payload.

### 4.2 Server wiring (`backend/app/server.py`)

- In `run(...)`, select the executor from config:
  `disabled → DisabledBorrowExecutor()`; `live → LiveBorrowExecutor(...)` built
  over `PortfolioMarginBorrowClient(...)` over `binance_signing`. Inject through
  `BorrowTaskService(str(config.borrow_db_path), executor=...)`.
- **Ownership-lock ordering:** acquire the sidecar `flock` before the scheduler
  thread can exist — inside `BorrowTaskService.__init__` or immediately before
  `.start()` — and **before** `borrow_service.start()`. The existing construct →
  bind → `start()` ordering is preserved; the lock acquisition is added on the
  service side so a non-owner still constructs and serves read/mutation APIs but
  never starts a scheduler.
- Add the three `/api/borrow-execution/*` handlers and extend `_is_borrow_path`
  with the single new prefix.
- Live+missing-credentials emits the distinct blocked lifecycle event (§3.4).

### 4.3 Ownership lock (`backend/borrow_tasks/**`, service side)

- `fcntl.flock(LOCK_EX | LOCK_NB)` on the sidecar file `<borrow_db_path>.lock`
  (never the DB file itself — SQLite owns its own DB-file locking).
- Non-blocking; held for **process lifetime**; never re-acquired per tick;
  released only on `close()` / process exit, never while the scheduler runs.
- Owner: scheduler runs normally.
- Non-owner: starts, serves every read and task-mutation API, starts **no**
  scheduler, dispatches nothing even if a tick is forced,
  `can_execute=false`, `block_reason="not_execution_owner"`; its durable
  mutations are honored by the owner.
- Crash recovery is free: the kernel releases the lock on process death; the
  next process acquires it. Orphaned pending attempts already block their tasks
  through `unresolved_attempt_id`; ownership adds nothing to that path.
- **ADR context (§2.4, record only):** the existing same-port bind failure
  blocks the common "ran the command twice" accident because socket bind
  precedes `borrow_service.start()`. That protection is **real but incidental** —
  `APP_BIND_PORT` and `APP_BORROW_DB_PATH` are independently configurable, so a
  different port + same DB yields two live schedulers. A non-owner also opens the
  store (running benign orphan-marker recovery) before bind fails, so "a second
  process touches the DB" is already true today. Debt safety rests on the
  sidecar lock, not on port binding.

### 4.4 Migration — idempotent authorization boundary

- `PRAGMA user_version` is the idempotent schema gate. Add
  `live_authorized INTEGER NOT NULL DEFAULT 0`.
- One-time on the C migration: mark all pre-C tasks not live-authorized;
  transition any pre-C `borrowing` task to `paused` **once**, preserving counts
  and logs.
- A later per-task explicit Start marks a migrated task live-authorized and
  eligible **only while `success_count < success_target`**.
- New post-C tasks are live-authorized by their Confirm action.
- Normal restart preserves post-C authorization, status, counts, and the durable
  global switch; startup reports live-authorized and recovered-orphan counts. No
  blanket re-arm.

### 4.5 Pending-insert transaction (the single correctness core)

In **one** conditional transaction, before any network I/O, re-check **all** of:

```text
is_execution_owner
status = 'borrowing'
live_authorized = 1
durable global switch (execution_enabled) = on
NOT in global cooldown
unresolved_attempt_id IS NULL
success_count < success_target
```

Then, atomically: insert the pending attempt, advance the cursor, and set
`unresolved_attempt_id`. **A failed predicate creates no attempt row and no
POST.** No DB lock or transaction is held during network I/O. The marker clears
only on a terminal non-`unknown` resolution.

### 4.6 Eligibility predicate (frozen, count gate included)

```sql
status = 'borrowing' AND unresolved_attempt_id IS NULL
  AND live_authorized = 1 AND success_count < success_target
```

The current `list_eligible_tasks` filters only
`status = ? AND unresolved_attempt_id IS NULL`; it must gain
`live_authorized = 1` and `success_count < success_target`. This closes the
extra-POST path proven in round-2 §2.1/§2.2.

---

## 5. Result classification and reconciliation (frozen)

### 5.1 Classification — deny by default

| Observation | Typed result | Scheduler effect |
| --- | --- | --- |
| 2xx JSON with valid non-empty `tranId` | `success` | persist id, increment count, complete at target |
| business code `-51006`, `-51014`, `-51061` | `known_rejection` | record; task stays in rotation |
| HTTP 400 with business code `-1003`, or HTTP 429 | `rate_limited` | record; global cooldown |
| HTTP 418 | `rate_limited` | 300s global cooldown, then wait for manual global Start |
| timeout / connection loss after dispatch | `unknown` | block task; reconcile |
| malformed / empty 2xx | `unknown` | block task; reconcile |
| 5xx unless evidence proves definite rejection | `unknown` | block task; reconcile |
| unexpected executor exception | `unknown` / unresolved pending | block task; scheduler stays alive |

- `known_rejection` allowlist is **exactly** `-51006`, `-51014`, `-51061`; every
  **unlisted 4xx → `unknown`**. The three codes are archived and frozen; the
  set is not empty and is not an implementer choice.
- **`-1003` → `rate_limited`** under HTTP 400 body *or* 429, consistent with the
  existing read client. The business code is verified; its exact PAPI HTTP
  representation is not guaranteed, so handle both status paths.
- No automatic POST retry inside transport (**one-shot**). `known_rejection`
  retries only through a later ordinary scheduler turn. `unknown` **never**
  retries as a POST.
- `tranId` normalized through one arbitrary-precision-safe **string** path; never
  parsed via float; positive integer expected.
- **Retry-After:** missing / unparseable / non-numeric / non-positive → **60s**;
  a valid value clamped to **[60s, 300s]** (lower 60s because the PM budget is a
  per-minute window; upper 300s so one malformed header cannot silently freeze
  the product for the supervised operator).
- **418:** 300s minimum local cooldown, **no auto-resume**; `block_reason` stays
  `rate_limited` until the operator calls `start` again. Local expiry is **not**
  proof the documented 2-min-to-3-day ban has ended.
- **Borrow POST timeout:** its own module-level constant **10s**,
  test-overridable, **not** env-configurable, and explicitly **not**
  `config.request_timeout`.
- **Cooldown scope:** a rate-limit cooldown blocks **all** signed borrow-client
  traffic **including reconciliation GETs** (the IP budget is shared and the
  exchange asked for backoff). Operator **Stop** blocks only POSTs;
  reconciliation GETs continue (Stop means "create no new debt", and the operator
  needs the truth about attempts already in flight).

### 5.2 Exception containment (both layers required)

- `_dispatch_one` contains executor exceptions **after** pending insert, maps
  them to `unknown` / unresolved without re-raising.
- `BorrowScheduler._loop` has a last-resort guard so a store/projection
  exception cannot silently terminate the scheduler thread.

### 5.3 Reconciliation — proves success, never failure-by-absence

Delays measured from the moment the attempt became unresolved:

```text
+5s → +15s → +60s → +300s → +900s     (5 reads, ~21 min; weight 10×5=50)
```

then stop automatically and enter terminal, **visible** `reconciliation_exhausted`
— task stays blocked, authorizes nothing, **never** a second POST. No read
earlier than 5s (propagation latency is unarchived; an early empty read is
indistinguishable from real absence).

Matching:

- when a `tranId` is known → unique `txId` match on the documented key;
- response-less unknown → query the archived `startTime`/`endTime` window
  (dispatch-anchored, bounded, page size ≤ 100) requiring exact `asset` and
  `Decimal(principal) == Decimal(requested_amount)`;
- only **one unique `CONFIRMED`** contract-valid record resolves success;
  `PENDING` / `FAILED` / empty never prove success;
- zero match, delayed visibility, multiple candidates, or cross-task ambiguity →
  **stay blocked**;
- account balance deltas are corroboration only, never authority.
- On reconciliation-proven success, persist the matched id into the attempt's
  `tran_id` and set `reason="reconciled_unique_txid_match"` so audit
  distinguishes response-proven from history-inferred success.
- **No HTTP force-clear or "retry anyway" route exists.** The only operator exit
  from an exhausted/blocked task is delete.
- Record field names are **verified**: `txId`, `asset`, `principal`,
  `timestamp`, `status` (with `status ∈ {PENDING, CONFIRMED, FAILED}`). Match on
  those exact fields; do not invent loose amount matching. What remains
  undocumented is only the propagation SLA (§8); the dispatch-anchored window
  width is a local conservative policy, not a Binance guarantee, so keep it
  bounded (the archived selection contract already caps a window at 30 days and
  page size ≤ 100 — do not exceed the dispatch-anchored bound the policy sets).

### 5.4 Resolve matrix (verbatim) + zero-extra-POST guarantee

| Status when result resolves | `success_count` | Status transition |
| --- | --- | --- |
| `borrowing`, count < target | +1 | stays `borrowing` |
| `borrowing`, count reaches target | +1 | → `completed` |
| `paused`, count < target | +1 | stays `paused` |
| `paused`, count reaches target | +1 | → `completed` |
| `deleted` | +1 | **stays `deleted`, always** |
| `completed` | +1 | stays `completed` |

- Auto-completion is permitted from `borrowing` **and** `paused` (round-2 §2.1
  overturns round-1 Opus/Grok/GLM; adopts Kimi F7). Suppressing `paused →
  completed` would leave a task at `count == target` in `paused`; a later Start
  moves it to `borrowing`, it becomes eligible, and the next tick sends a real
  borrow POST beyond the requested count. That path must not exist.
- Non-success categories never change status. `unknown` sets/retains the
  reconciliation marker regardless of status, including on `paused`/`deleted`.
- Every dispatched attempt is always resolved and audited; controls only prevent
  the *next* POST. Once request bytes leave the process, resolution is never
  suppressed.
- **Zero-extra-POST — both required (belt and braces):**
  1. eligibility predicate includes `success_count < success_target` (§4.6);
  2. `post_start` refuses to move a task to `borrowing` when
     `success_count >= success_target`, returning the task as `completed`
     (idempotent; no error path for the ordinary case).

  With the transition rule alone, a legacy row already at target could still be
  Started; with the predicate alone, a Started at-target task would sit
  eligible-looking forever. Freeze both.

---

## 6. Frontend integration (minimal) and the two self-check guards

`frontend/index.html` — add only:

- an execution badge: `disabled` / `live enabled` / `globally stopped` /
  sanitized configuration-block (`borrow_credentials_missing`);
- a global Start/Stop control backed by the server;
- the nullable `global_cooldown_until` and each task's **derived**
  blocked / reconciling / `reconciliation_exhausted` condition;
- pre-create confirmation text: asset, amount, count, computed
  `amount × count` maximum target quantity, and current global interval;
- active-view polling of execution-status/tasks at a modest UI cadence (e.g.
  2s) — **display refresh only**; the browser never schedules attempts;
- removal of the A+B copy claiming all attempts are disabled / no real borrow.

Logs stay explicitly refreshable/paginated. No browser scheduling, no direct
Binance access, no new task state machine.

`frontend/self-check.js` — **exactly two** guard amendments, each narrowing, no
wildcard/prefix/directory exemption:

| Guard | Current location | Exact amendment |
| --- | --- | --- |
| interval whitelist | `self-check.js:3013-3016` (permits `delay === 60000` and `delay === 1000` only) | add exactly the one borrow-view poll delay (2000) |
| fetch-method whitelist | `self-check.js:3000-3011` (final branch `else if (c.method !== 'GET') throw '只读路由非法方法'`) | allow POST **only** for `/api/borrow-execution/start` and `/api/borrow-execution/stop` |

Both guards must remain red for anything else. `/api/borrow-execution/status`
stays GET; `/api/borrow-execution/{start,stop}` are the only new POST routes.
Naming only the timer guard (as the synthesis originally did) would leave the
method guard red and tempt a wholesale loosening — both are load-bearing.

---

## 7. Static guards — five, dual-assertion, exact filename only

| Guard | Location | Exact amendment |
| --- | --- | --- |
| single HMAC exit | `test_private_client.py:77-87` | allow exactly `binance_signing.py`; assert **neither** client constructs HMAC inline |
| urlopen confinement | `test_private_client.py:90-102` | allow exactly the one new borrow-client filename (`portfolio_margin_borrow_client.py`) |
| borrow-package AST purity | `test_borrow_executor.py` (executor seam / zero-network proof) | **unchanged** — must keep failing if a live/network/signing module lands in `backend/borrow_tasks/` |
| self-check interval whitelist | `self-check.js:3013-3016` | add exactly the borrow-view poll delay |
| self-check fetch-method whitelist | `self-check.js:3000-3011` | add exactly the two `/api/borrow-execution/{start,stop}` POST routes |

- Each amendment must add a **dual assertion** so the guard is narrowed, never
  merely widened.
- The AST-purity guard is why the borrow client lives under
  `backend/services/`, not `backend/borrow_tasks/` (Kimi's
  `backend/borrow_tasks/pm_borrow_client.py` suggestion is rejected — it
  contradicts this same guard).
- The new borrow client needs its **own** gate-fires-before-signing negative
  test; it does not inherit `test_private_client.py`'s.
- Signing and sending must consume **one** serialized payload string produced by
  **one** function; the borrow POST uses the archived
  `application/x-www-form-urlencoded` body and never splits a parameter between
  query and body.

---

## 8. Evidence — satisfied preconditions and the residual fail-closed unknowns

The evidence gate is `CLOSED_WITH_FAIL_CLOSED_DEFAULTS`. The public capture
under `.../20260720T150836Z/` and its `raw/*.md` slices **satisfy** the hard
preconditions for implementation; only a short list of facts the public pages do
not guarantee remain fail-closed. Do not describe the satisfied facts as open,
and do not promote the residual defaults to Binance guarantees.

### 8.1 Satisfied preconditions (verified — not blockers, not inferences)

| Fact | Verified value | Design consequence |
| --- | --- | --- |
| POST endpoint / method / host | `POST https://papi.binance.com/papi/v1/marginLoan`, signed | exact allowlist entry; base URL hardcoded, never caller-supplied |
| POST params / security / encoding | `asset`, `amount`, `timestamp`, optional `recvWindow` (≤ 60000ms) in `application/x-www-form-urlencoded` body; HMAC-SHA256 over `totalParams`, signature last | **satisfied precondition** — signer/serialization is fully specified; sign the exact bytes sent |
| POST request weight | **100** | cadence formula uses 100; the floor is fixed, not conditional |
| PM IP budget per minute | **6000/min** (verified, by IP) | half-budget formula → floor; a verified fact, not an inference |
| Cadence floor | **2s frozen** (default stays 5s) | frozen constant; recompute only if a committed evidence amendment changes weight 100 or budget 6000 |
| `tranId` type/magnitude | int64 | normalize as arbitrary-precision integer → stringify; never float |
| loan-record endpoint / weight | `GET /papi/v1/margin/marginLoan`, signed, weight **10** | second exact allowlist entry |
| loan-record params / pagination / depth | `asset`, `timestamp`; selection `txId` or `startTime`/`endTime`; `current`, `size` ≤ 100; 30-day window, `archived` for > 6 months | bounded dispatch-anchored windows; `txId` precedence when present |
| loan-record row fields | `txId`, `asset`, `principal` (decimal string), `timestamp`, `status ∈ {PENDING, CONFIRMED, FAILED}` | exact-field matching; only a unique `CONFIRMED` proves success |
| `txId == tranId` correspondence | verified (GET `txId` is POST `tranId`) | unique-ID fast path is authoritative |
| known-rejection codes | `-51006`, `-51014`, `-51061` | the **only** `known_rejection` set; every other 4xx → `unknown` (frozen, not empty, not an implementer choice) |
| `-1003` classification | `TOO_MANY_REQUESTS` is verified; exact PAPI HTTP representation is not guaranteed | handle an HTTP 400 body code or HTTP 429 as `rate_limited` |
| 5xx / `-1006` / `-1007` | official guidance: execution status may be unknown | classify as `unknown`; reconcile; never retry the POST |
| 418 semantics / ban range | verified: rate-ban after 429, duration 2 min–3 days | 300s minimum local cooldown + manual re-arm; local expiry is not proof the ban ended |
| idempotency key | not documented in the complete public parameter table | assume no server-side idempotency; write-ahead intent + fail-closed reconciliation is the whole defence |

### 8.2 Residual fail-closed unknowns (undocumented by the public pages)

Only these are genuinely undocumented and keep a fail-closed/default label:

| Undocumented fact | Consumer | Fail-closed default |
| --- | --- | --- |
| `Retry-After` presence / units / format | classification | not guaranteed by the page → treat a valid header as advisory; 60s fallback (clamp valid values to `[60s, 300s]`) covers every parse failure |
| loan-record propagation latency (post-POST SLA) | reconciliation | no published SLA → `+5/+15/+60/+300/+900s` is a labelled conservative local policy; an early empty read is never proof of failure |
| per-asset minimum amount / precision | rejection taxonomy | not published → no speculative client rounding; send validated `Decimal` text; any resulting exchange rejection lands in the unlisted-4xx bucket → `unknown` |
| whether these calls count against other limit families | capacity note | not fully specified → budget as shared IP weight and reserve the other half; does not affect correctness |

No hard implementation blocker remains: the POST parameter contract and the POST
weight are satisfied. `known_rejection` ships as the frozen three-code set (never
empty), and reconciliation ships with full-field matching (not `txId`-only),
because both contracts are archived.

### Interval floor (formula is authority)

```text
min_interval_seconds = ceil( 60 / (0.5 × ip_budget_per_min / post_weight) )
                     = ceil( 60 / (0.5 × 6000 / 100) ) = 2
```

Half the IP budget is reserved for reads/reconciliation. Frozen floor **2s**;
default stays **5s**. If the archive contradicts weight 100 or budget 6000, the
constant is **recomputed from the formula, not renegotiated**. The interval is
an exchange-capacity constraint (a sub-second borrow cadence risks an **IP** ban
that takes down the shared read-only snapshot channel), **not** a product
throughput promise and **not** a reintroduced risk cap.

---

## 9. Required tests (fake/recording only — no network, no real credentials)

Pre-C fixtures must be built **in-test via raw SQL** — no binary fixture.

Minimum required scenarios (round-2 §5.4):

1. **Two-owner ownership** — one process opens two `BorrowTaskService` on the
   same `db_path`; assert the second reports `not_execution_owner`, has no
   scheduler thread, and a forced tick dispatches nothing (`flock` is
   per-open-file-description, so two `open()` calls in one process reproduce
   this without subprocesses).
2. **Atomic gate abort** — each failed predicate (not owner / not borrowing /
   not live_authorized / globally stopped / in cooldown / unresolved present /
   count ≥ target) creates zero attempt rows and zero POST.
3. **Success-after-delete** — `deleted` stays `deleted`, count still +1, result
   audited.
4. **Paused-at-target completion** — `paused` reaching target → `completed`.
5. **Start-at-target refused** — `post_start` returns `completed`, no eligibility
   reopened, zero POST.
6. **No catch-up** — after a 60s cooldown at a 5s interval, ≤1 dispatch in the
   next 3s (`_last_tick_mono` advances to `now`, never by accumulated intervals).
7. **One-shot POST per error class** — recording transport asserts exactly one
   POST for each of 429 / 418 / timeout / connection reset / 5xx / malformed.
8. **Dual-layer exception containment** — an executor exception and a
   store/projection exception each keep the scheduler thread alive; the attempt
   resolves/stays `unknown`, the task is blocked.
9. **Idempotent migration** — `PRAGMA user_version` runs the pre-C quarantine
   exactly once; re-running is a no-op; pre-C `borrowing` → `paused`, counts/logs
   preserved, `live_authorized=0`.
10. **Reconciliation** — unique `CONFIRMED` match resolves success; zero /
    multiple / cross-task / exhausted stay blocked; `reconciliation_exhausted`
    is terminal, visible, authorizes no POST.
11. **Decimal amount matching** — `Decimal(principal) == Decimal(requested_amount)`
    exact; no float path.
12. **Large-integer `tranId`** — normalized as arbitrary-precision string, never
    float.
13. **Credential redaction** — both `BINANCE_BORROW_API_KEY` and
    `BINANCE_BORROW_API_SECRET` never appear in any lifecycle/status/log/exception
    output; `live`+missing → `borrow_credentials_missing`, zero signed traffic.
14. **Both self-check guards** — interval whitelist admits only
    `60000/1000/2000`; fetch-method whitelist admits POST only for the two
    `/api/borrow-execution/{start,stop}` routes; anything else is red.

Plus: exact method/path allowlists and shared signer canonicalization; the new
client's own gate-before-signing negative test; config default-disabled /
invalid-mode / live-without-creds / disabled-with-creds; global start/stop
durable state; restart orphan blocking; `-1003`/429/418/manual-rearm/unknown
classification; recording transport verifies exact host/path/method/parameter
names with dummy credentials and no network; all old + new response schemas
validate.

---

## 10. Deterministic test / verification commands

Run at implementation completion (fake/recording only; no live host):

```text
python3 -m pytest \
  backend/tests/test_borrow_domain.py \
  backend/tests/test_borrow_store.py \
  backend/tests/test_borrow_scheduler.py \
  backend/tests/test_borrow_executor.py \
  backend/tests/test_borrow_api.py \
  backend/tests/test_private_client.py \
  backend/tests/test_binance_signing.py \
  backend/tests/test_portfolio_margin_borrow_client.py \
  backend/tests/test_live_borrow_executor.py \
  backend/tests/test_config.py -q
python3 -m pytest backend/tests -q
node frontend/self-check.js
python3 -m py_compile \
  backend/services/binance_signing.py \
  backend/services/portfolio_margin_borrow_client.py \
  backend/services/live_borrow_executor.py \
  backend/services/private_client.py \
  backend/borrow_tasks/*.py \
  backend/app/server.py backend/config.py
git diff --check
```

The suite must include the static/recording proof that no test resolves a
Binance production host and that only the two verified method/path pairs are
reachable from the new client. No automated test, review command, or model
action performs a live Binance write.

---

## 11. Risk points and review focus

Risk points:

- Any path that can send a second POST after an ambiguous first result.
- Any path that makes a pre-C task live without an explicit post-migration Start.
- A transport exception terminating the scheduler thread.
- Signer extraction weakening the GET-only deny-by-default whitelist.
- Global Stop not checked atomically before pending insert / dispatch.
- Pause/delete/edit races losing or rewriting an in-flight result.
- History matching falsely attributing another task's or a manual loan.
- Two processes sharing a database on different ports (sidecar lock, not
  same-port bind, is the authority).
- Sub-floor cadence risking a shared-IP ban on the read-only product.
- Any test or doc exposing credentials or contacting production.
- Frontend changes expanding into a second scheduler or task-state redesign.

Review focus (review-1 Kimi, then review-2): the same list, plus verification
that the five static guards were narrowed (not widened) with dual assertions,
that `can_execute` excludes cooldown, that `global_cooldown_until` is exposed,
that the zero-extra-POST guarantee holds on both the predicate and `post_start`,
and that no app-level cap / allowlist / `maxBorrowable` was reintroduced as an
implementation convenience (raise such only as a product finding, never as code).

---

## 12. Stop conditions and artifacts to write back

- On implementation completion, the implementer writes
  `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation.md` and
  `.../60-test-output.txt`, then **stops for the bookkeeper**.
- The implementer does **not** commit, push, dispatch review, update
  `status.json`, or declare acceptance. The bookkeeper reconciles, records
  base/head SHA + diff fingerprint + test evidence path in `status.json`, and
  dispatches review-1 (fresh Kimi). Every cross-model next step is
  `executor:human_operator`.
- The first real borrow request is a human-operator action after code review;
  this stage does not prescribe or guess its asset, amount, count, or interval.
  Borrow-only scope creates naked debt and does not auto-hedge or repay.

---

当前 Session ID: unavailable (runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.md
本地北京时间: 2026-07-21 07:10:49 CST
下一步模型: bookkeeper (Codex/GPT)
下一步任务: record breakdown_author + session_receipts in status.json, prepare the single implementation dispatch for claude_glm (task id C); implementation remains unauthorized until dispatched
