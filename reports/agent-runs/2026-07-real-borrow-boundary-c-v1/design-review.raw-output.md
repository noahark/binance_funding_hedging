# Design Review Raw Output — Boundary C Real Borrowing

## Capture metadata

| Field | Value |
| --- | --- |
| Stage | `2026-07-real-borrow-boundary-c-v1` |
| Role | independent read-only design review (not formal Review-1/Review-2) |
| Prompt | `design-review.prompt.md` |
| Model name | **Grok 4.5** |
| Provider | xAI |
| Adapter / runtime | Grok Build CLI |
| Provider-native Session ID | unavailable (Grok Build CLI does not expose a provider-native session ID in this runtime) |
| Session ID source | unavailable |
| Executor | human_operator (operator dispatched the prepared prompt into Grok) |
| Captured at (local) | 2026-07-20 21:16:51 CST |
| Product code edited | no |
| Live Binance / credentials | none |

This file is the stage-local raw capture of the design-review response originally
returned in the Grok session. Bookkeeper amendments and canonical
`12-development-breakdown.md` remain subsequent steps.

---

# Boundary C Design Review

Read-only review of design artifacts and current A+B source (`borrow_tasks/*`,
`private_client.py`, `config.py`, `server.py` borrow wiring, frontend borrow
copy). No product/stage files edited during the review itself; no network,
credentials, or adapter dispatch.

---

## 1. Verdict: REWORK

Architecture direction is sound and aligned with user decisions (existing
Confirm entry, no app-level caps, borrow-only, serial backend-dominant task).
It is **not** implementation-ready until several correctness freezes are written
into the design/ADR/breakdown. Current A+B store/service behavior contradicts
stated Boundary C invariants in ways that would create real debt races if
implemented as “extend existing resolve path.”

---

## 2. Blocking findings

### P0-1 — Eligibility is not DB-authoritative during pending (duplicate-debt landmine)

**Evidence:** `BorrowTaskStore.insert_pending_attempt` writes a pending attempt
and advances the cursor, but **does not** set
`borrow_task.unresolved_attempt_id`. Eligibility is
`status=borrowing AND unresolved_attempt_id IS NULL`. The marker is set only on
`RESULT_UNKNOWN` resolution or store-open orphan recovery.

**Design claim (D6):** every pending/unknown attempt makes the task ineligible.

**Gap:** During live I/O, ineligibility depends on the service `tick` lock
remaining held for the full network RTT. That is true today, but:

- it is not the durable ledger invariant the design claims;
- any future “release lock during I/O” change (or a missed lock) enables a
  second POST while the first is still pending;
- pause/delete can run under the store lock while `tick` holds only the service
  lock.

**Required freeze:** In the **same transaction** as pending insert:

1. re-check `status == borrowing`, `live_authorized == true`, global execution
   enabled, and `unresolved_attempt_id IS NULL`;
2. set `unresolved_attempt_id = attempt_id` (or equivalent durable block);
3. if gates fail, **do not** insert/dispatch (no network).

Clear the marker only on terminal resolution that is not `unknown` (success /
known_rejection / rate_limited / execution_disabled as applicable). Keep
`unknown` blocked until recon uniquely succeeds.

### P0-2 — Pause/delete/stop race window before POST is underspecified

**Evidence:** `tick` holds `self._lock` and calls
`list_eligible` → `insert_pending` → `execute` → `resolve`. HTTP `post_pause` /
`post_delete` use the store only and **do not** take the service lock. Between
list and insert (and after insert, before POST), the operator can pause/delete/
stop while dispatch still proceeds.

**Design claim (D8 / AC9–10):** pause/delete/stop prevent later attempts;
already-dispatched results are still recorded.

**Gap:** “Already dispatched” must mean **after the HTTP request has left the
process**, not merely “scheduler selected the task.” Without gate re-check
inside the pending-insert transaction, a paused/stopped task can still POST.

**Required freeze:**

- Global Stop, live authorization, and status must be revalidated inside the
  pending-insert transaction.
- If revalidation fails: no attempt row (or only a non-network cancelled local
  event—prefer no row), no POST.
- After the POST bytes are sent: never suppress resolution; pause/delete/stop
  only block subsequent POSTs.

### P0-3 — Success resolution can resurrect `deleted` → `completed`

**Evidence:** `resolve_attempt` on success does:

```text
if success_count >= success_target: new_status = completed
UPDATE ... status = new_status
```

It starts from current status but **overwrites** to `completed` even when current
status is `deleted` (or `paused`).

**Design claim (D8 / AC10):** `deleted` is terminal and must not become
`completed` if an in-flight attempt succeeds.

**Required freeze:** On success, always increment `success_count` and audit the
attempt; set `status=completed` **only if** current status is still `borrowing`
(or an explicit live-runnable set that excludes `deleted`/`paused`). Never
transition `deleted` → anything. Optionally leave `paused` as `paused` while
still recording success count (design already implies this).

### P0-4 — Executor exception can kill the scheduler thread

**Evidence:** `BorrowTaskService._dispatch_one` calls
`self._executor.execute(...)` with **no** try/except. An unexpected exception
leaves the attempt pending (good after restart recovery) but can kill the
scheduler thread (bad for AC6).

**Required freeze:** Any exception after pending insert maps to `unknown` (or
leaves pending + sets unresolved), never re-raises out of `tick`. Scheduler
remains alive. Tests must inject raising executors.

### P1-1 — Shared signer vs existing single-HMAC security test

**Evidence:** `backend/tests/test_private_client.py` asserts product
HMAC/signature surface exists **only** in `private_client.py`. Design correctly
adds `binance_signing.py` and forbids a second ad-hoc signer.

**Required freeze:** Update the security test contract: HMAC construction is
allowed **only** in `backend/services/binance_signing.py`; `PrivateClient` and
the borrow client must call it; `PrivateClient` remains GET-only exact-path;
borrow client exact-allowlists only verified POST + loan-record GET. Fail closed
if either client constructs HMAC inline.

### P1-2 — No HTTP “force clear unresolved” / “retry anyway”

**Evidence:** `clear_unresolved` exists as a Python test seam. Design correctly
rejects unsafe retry.

**Required freeze:** Boundary C must not expose any HTTP/API that clears
`unresolved_attempt_id` without a unique recon success. Recon success is the
only production clear path for unknown/pending. Test seam stays non-HTTP.

### P1-3 — Open items 1–5 are not frozen (implementation blockers)

The draft breakdown’s five open items are still open. Implementation must not
invent them. Exact freezes are in §4 below.

### P1-4 — `known_rejection` definition is not exchange-grounded yet

Design classifies “explicit exchange/business rejection **proving no loan**” as
retriable. Without archived official error semantics, implementers may treat 4xx
bodies as safe known failures when some statuses are ambiguous.

**Required freeze (after public docs archive):** default fail-closed mapping:

- only documented, non-ambiguous client/business rejections → `known_rejection`;
- any ambiguous body/status → `unknown`;
- 429/418 → `rate_limited`;
- 2xx without valid `tranId` → `unknown`;
- 5xx → `unknown` unless official evidence proves definite non-acceptance
  (currently treat as unknown).

### P2 (blocking for freeze quality, not architecture) — Official contract evidence not captured

`reports/api-samples/2026-07-real-borrow-boundary-c-v1/` is missing. Candidate
endpoints from recon (`POST /papi/v1/marginLoan`,
`GET /papi/v1/margin/marginLoan`, `tranId`/`txId`) are **not** implementation
freezes until public docs are archived and design assumptions re-checked.

---

## 3. Non-blocking findings

### P3-1 — Status projection for blocked/reconciling tasks

Surface `unresolved_attempt_id` / latest `unknown` clearly in task list and logs
(A+B already has fields). Optional UI label “对账中/已阻断” helps supervision;
not a new state machine.

### P3-2 — Used-weight observability

Recon recommended logging numeric used-weight counters. Design D10 already
allows sanitized counters when present—keep optional, not a preflight gate.

### P3-3 — Interval vs recon latency warning

No product minimum interval (correct per A+B). UI confirmation should keep
showing the interval; optional soft warning if interval is aggressive is product
sugar, not required.

### P3-4 — Startup vs blocked for missing live credentials

Prefer process start with `can_execute=false` over hard crash when
`APP_BORROW_EXECUTOR=live` but borrow keys missing—still fail closed for POSTs.
Invalid enum values should still fail startup (existing pattern).

### P3-5 — Components are appropriately lean

`LiveBorrowExecutor` + narrow PM client + shared signer + durable global switch
+ recon is the right minimal set. No draft/arm, no maxBorrowable preflight, no
concurrent workers—keep it that way.

---

## 4. Open-item decisions

### 1) Execution-control routes and schema body

**Decision: Confirm the draft routes and freeze the body.**

```text
GET  /api/borrow-execution-status
POST /api/borrow-execution/start
POST /api/borrow-execution/stop
```

Schema: `schemas/api/borrow-tasks/execution-status.schema.json`
`schema_version`: `borrow-execution/v1`

Success body (freeze):

```json
{
  "schema_version": "borrow-execution/v1",
  "mode": "disabled|live",
  "execution_enabled": true,
  "can_execute": true,
  "block_reason": null,
  "in_flight_attempt_id": null,
  "updated_at": "2026-07-20T11:30:00.000000Z"
}
```

Rules:

- `mode` = process config only;
- `execution_enabled` = durable global switch (default **false** on first C
  migration / empty store);
- `can_execute` = `mode==live AND execution_enabled AND credentials_present AND
  not_otherwise_blocked`;
- `block_reason` = sanitized enum/string only (`executor_disabled`,
  `globally_stopped`, `credentials_missing`, `invalid_configuration`, …)—never
  env values;
- `in_flight_attempt_id` = local attempt id if a POST is in flight, else null;
- start/stop return the same status document (200); start does not arm
  individual tasks;
- reuse existing borrow error schema for 4xx/405.

### 2) Credential names and missing-credential behavior

**Decision: Freeze names; fail closed without requiring process death.**

```text
BINANCE_BORROW_API_KEY
BINANCE_BORROW_API_SECRET
APP_BORROW_EXECUTOR=disabled|live   # default disabled; unknown → startup ValueError
```

- Read-only keys remain separate (`PrivateClient` env).
- `live` + missing borrow key/secret: process **may** start; `mode=live`,
  `can_execute=false`, `block_reason=credentials_missing`; **zero** signed
  borrow POSTs/GETs for write client until both present.
- Redaction tests must cover the new env names in startup logs.
- Do not log secrets, signatures, or full signed queries.

### 3) Missing/invalid `Retry-After` fallback

**Decision: Freeze 60 seconds global cooldown.**

- Parse `Retry-After` as non-negative seconds; accept integer or decimal string
  if present; clamp to a sane upper bound (e.g. 3600s) to avoid permanent
  accidental freeze from garbage.
- Missing, unparseable, or negative → **60s** global cooldown.
- Must not busy-loop; tests cover invalid header → exactly 60s.

### 4) Bounded reconciliation timing

**Decision: Freeze a small fixed backoff; never treat absence as failure; never
second POST.**

After an attempt becomes pending/unknown:

| Step | Delay after previous recon attempt (or after finish/dispatch for step 1) |
| --- | --- |
| 1 | 1s |
| 2 | 5s |
| 3 | 15s |
| 4 | 60s |
| 5 | 300s |

Then **stop automatic recon**; task remains blocked and visible. Operator may
delete the task. No “retry POST” action.

Matching rules (freeze intent):

- If local `tranId` known: query by documented `txId`/`tranId` key; unique valid
  record → success.
- If response-less unknown: bounded window around `dispatched_at` + exact asset
  + exact decimal amount; **only unique** contract-valid match → success.
- 0 matches or >1 matches → remain blocked.
- Balance/`crossMarginBorrowed` is corroboration only—never sole authority.
- Exact window width and query params are amended only after official public
  evidence archive (see Evidence gaps). Until then, implementers must not invent
  multi-hour windows or loose amount matching.

### 5) Process restart resume vs re-arm

**Decision: Resume post-C live-authorized tasks; do not pause-all on restart.**

- Post-C tasks marked live-authorized at Confirm: restart preserves
  `borrowing`/`paused`/`completed`/`deleted` and counts.
- Orphan pending / unresolved unknown: keep blocked; run recon; **never**
  auto-POST while unresolved.
- Pre-C tasks: one-time migration to `live_authorized=false` and pause any
  pre-C `borrowing` → `paused`; require explicit Start (which sets
  live-authorized).
- Process `APP_BORROW_EXECUTOR` and durable global switch still gate all POSTs
  after restart.
- Reject “pause every task on every restart” for this stage—it fights durable
  automation without improving unknown-outcome safety.

---

## 5. Required amendments

| File / section | Replacement intent |
| --- | --- |
| `10-design.md` D4–D6 | Specify atomic pending-insert transaction: gate re-check + set `unresolved_attempt_id` before any network; clear rules for marker lifecycle. |
| `10-design.md` D5 / scheduler | Wrap executor in exception containment; map to `unknown`/unresolved; scheduler never dies. |
| `10-design.md` D8 | Explicit status matrix: success must not overwrite `deleted`; pause/delete after POST still resolves attempt; pause/delete/stop **before** POST abort insert. |
| `10-design.md` D2 / contracts | Freeze execution-status schema body and start/stop behavior as in open-item 1. |
| `10-design.md` D3 + test strategy | Freeze single HMAC module location and updated security test assertion. |
| `10-design.md` D6 recon | Freeze backoff table (1/5/15/60/300s), unique-match-only success, no absence-as-failure, no force-clear API. |
| `11-adr.md` ADR-004/006 | Incorporate pending marker + restart resume decision; note A+B `resolve_attempt` completed-overwrite as a required fix, not optional polish. |
| `11-adr.md` edge cases | Add stop/pause between selection and POST; deleted terminal; Retry-After fallback 60s. |
| `12-development-breakdown.draft.md` → canonical `12-development-breakdown.md` | Resolve all five open items with the freezes above; add required tests for gate re-check, deleted-terminal success, exception containment, signer module grep, no-network host proof. |
| `00-task.md` AC (minor) | Align AC language with: unresolved set at pending insert; deleted never auto-completed. |
| Contract evidence | Before coding: populate `reports/api-samples/2026-07-real-borrow-boundary-c-v1/` with public official docs for POST + loan-record GET; amend design if params/IDs/weights contradict assumptions. |

No product-code change in this review.

---

## 6. Lean implementation assessment

**Yes — one serial backend-dominant task with embedded review off is
appropriate.**

Reasons:

- Work is ~90% backend correctness (signer, write client, gates, migration,
  recon, races) with a thin frontend status/copy/stop integration.
- Parallel split would force artificial client/UI boundary and R4/R10 overhead
  without reducing live-write risk.
- Routing to Claude-GLM for the whole bounded task matches AGENTS.md
  backend-dominant rule; Review-1 Kimi cross-provider; Codex excluded from
  implementation/fix.
- Components proposed are necessary for first live debt path; no draft/arm, no
  risk-cap subsystem, no concurrent POST worker—keep that lean scope.

Do **not** expand into repay/hedge, browser scheduling, or app-level USDT caps
under the guise of “safety.” Correctness freezes above are sufficient
server-side controls for the user’s chosen exposure model.

---

## 7. Evidence gaps

Must capture **public official** docs (no authenticated samples, no live POST)
under `reports/api-samples/2026-07-real-borrow-boundary-c-v1/` before
implementation freezes:

1. **`POST /papi/v1/marginLoan`**: exact path, security type, required params
   (`asset`, `amount`, `timestamp`, `recvWindow`, …), encoding, response shape
   and `tranId` (type/format), error body shape, documented IP weight (recon
   cites 100—**re-verify**), 429/418/`Retry-After` behavior.
2. **`GET /papi/v1/margin/marginLoan`**: exact path, params (`asset`, `txId` vs
   `tranId`, time range fields, pagination), response record fields for unique
   matching, weight (recon cites 10—**re-verify**).
3. **Identity mapping:** confirm `txId` query matches POST `tranId`.
4. **Idempotency:** whether any client order id / idempotency key exists
   (recon/design currently assume **none**—confirm).
5. **Business codes** that definitively mean “loan not created” vs ambiguous.
6. **Whether marginLoan counts toward the PM order rate limit** (still
   unverified in recon).
7. **Propagation expectations** for loan-record visibility after success
   (affects recon delays; no live measurement required for design freeze beyond
   conservative backoff).
8. **Base URL host** for papi write vs read (`https://papi.binance.com`
   hardcoded pattern)—confirm for both endpoints.

Until those are archived, treat recon links as **candidate** evidence only, not
frozen contract.

---

### Review Q-by-Q summary

| # | Question | Assessment |
| --- | --- | --- |
| 1 | Duplicate borrow after ambiguous result? | Intent correct; **P0** gaps on pending marker + pre-POST gate re-check. |
| 2 | Migration quarantine old A+B tasks? | Sound (live_authorized + pause pre-C); freeze Start = authorization. |
| 3 | Signer extraction vs GET-only? | Sound; freeze shared module + test rewrite. |
| 4 | Result classifications fail closed? | Sound skeleton; freeze known_rejection conservatively after docs. |
| 5 | Stop/pause/delete races? | Intent correct; **P0** fix deleted overwrite + pre-POST abort. |
| 6 | Loan-history matching strength? | Unique match only is correct; freeze backoff; evidence still missing. |
| 7 | Execution API + minimal FE enough? | Yes, if schema frozen and FE stays display-only. |
| 8 | Unnecessary complexity? | No; scope is appropriately minimal. |
| 9 | File boundaries + no-network tests? | Largely complete; add race/exception/signer/static-host proofs. |
| 10 | Five open items? | Frozen in §4. |

---

```text
当前 Session ID: unavailable (Grok Build CLI does not expose a provider-native session ID in this runtime)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/design-review.raw-output.md
本地北京时间: 2026-07-20 21:16:51 CST
下一步模型: bookkeeper / registered HIGH-stage development-breakdown author (Claude provider Fable5→Opus4.8)
下一步任务: amend 10-design.md / 11-adr.md with P0–P1 freezes; capture public API samples; produce canonical 12-development-breakdown.md; then human operator may dispatch implementation
```
