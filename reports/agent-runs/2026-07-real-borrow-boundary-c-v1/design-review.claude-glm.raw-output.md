# Design Review Raw Output — Boundary C Real Borrowing (claude-glm / GLM-5.2)

## Reviewer

| Field | Value |
| --- | --- |
| Stage | `2026-07-real-borrow-boundary-c-v1` |
| Role | independent read-only design review (**not** formal Review-1 / Review-2; no implementation exists) |
| Prompt | `design-review.prompt.md` |
| Provider | `zhipu_glm` (accessed via Claude Code; the `claude_glm` CLI). Per `AGENTS.md`, provider identity is the model vendor, not the CLI wrapper, so this is `zhipu_glm`, not Anthropic — even though it runs through Claude Code. |
| Model | `glm-5.2[1m]` |
| Provider-native Session ID | `unavailable` (runtime does not expose a provider-native Session ID; runner/human operator may add the verified ID to `status.json.session_receipts`) |
| Session ID source | `unavailable` |
| Executor | `human_operator` (operator dispatched the prepared prompt into this session) |
| Captured at (local) | 2026-07-20 21:21:23 CST |
| Product code edited | no |
| Live Binance request / credentials | none |
| Models / adapters dispatched | none |

This file is one independent design-review capture. A separate capture by a
different reviewer model exists at `design-review.raw-output.md`; the two are
independent evidence and may be cross-validated. Bookkeeper amendments and the
canonical `12-development-breakdown.md` remain subsequent steps.

Hard restrictions honored: no product/stage files edited, no model or adapter
dispatched, no credentials or `.env`/key files read, no authenticated request or
Binance POST sent, no endpoint fact taken from memory — unverified exchange
semantics are marked as evidence gaps.

Evidence actually read: `AGENTS.md`; `00-intake.md`, `00-task.md`, `10-design.md`,
`11-adr.md`, `12-development-breakdown.draft.md`;
`reports/agent-runs/2026-07-real-borrow-execution-v1/06-direction-synthesis.md`
and `03-grok-borrow-api-capacity-recon.md`; `workflows/templates/stage-delivery.yaml`
(stage-design + development-breakdown); `docs/parallel-development-mode.md`
(v0.5 R11–R12); current source `backend/borrow_tasks/**`,
`backend/services/private_client.py`, `backend/config.py`, `backend/app/server.py`,
borrow-task schemas, the borrow sections of `frontend/index.html`, and matching
tests. No recursive read of other stages or any `history/` directory.

---

# Boundary C Real Borrowing — Read-Only Design Review

Every claim below is grounded in the prompt's raw-artifact set plus source
actually read (file:line cited).

## 1. Verdict: REWORK

The design **direction and core correctness are right** (ADR-001…007, D4–D6
fail-closed reconciliation, separate write client, two gates, pre-C quarantine
all match the duplicate-debt threat model). REWORK is required because the
**draft breakdown does not freeze several implementation-critical boundaries**
and the **current A+B store/service code contradicts some stated Boundary C
invariants**. These are freeze/amend gaps in `12-development-breakdown.draft.md`,
`00-task.md`, `10-design.md`, and `11-adr.md`, plus required source fixes during
implementation — not a rejection of the design direction.

## 2. Blocking findings

### P1-1 — Live client/executor file boundary is unfrozen and conflicts with the borrow_tasks zero-network invariant

`backend/borrow_tasks/__init__.py` (docstring) declares the package imports no
`backend.services`/network, and `backend/tests/test_borrow_executor.py:86-102`
(`test_no_network_or_signing_imports_in_borrow_package`) AST-scans the whole
package for `urllib/http/socket/hmac/hashlib/ssl/requests`. A `LiveBorrowExecutor`
must delegate to a `PortfolioMarginBorrowClient` that performs a real `urllib`
POST. `00-task.md` File Boundaries lists `backend/services/binance_signing.py`
and `backend/services/private_client.py` but lists **no path for the live write
client or the live executor**; `10-design.md` D3 names the client only
descriptively. If an implementer places either inside `backend/borrow_tasks/`,
the AST proof breaks and the package purity claim becomes false.

**Required freeze:** signer + narrow write client + live executor live under
`backend/services/`; `borrow_tasks/` stays pure; `server.run` injects the
executor via the existing `BorrowTaskService(executor=…)` seam
(`service.py:104-120`). Concretely add to `00-task.md` File Boundaries:
`backend/services/portfolio_margin_borrow_client.py` (only
`POST /papi/v1/marginLoan` + `GET /papi/v1/margin/marginLoan`) and
`backend/services/live_borrow_executor.py` (implements `BorrowExecutor`).

### P1-2 — `resolve_attempt` overwrites the `deleted` terminal status on a live in-flight success (acceptance 10 / D8 not enforceable today)

`store.py:431-456` computes `new_status = task["status"]` then, on
success-at-target, sets `new_status = STATUS_COMPLETED` and writes it back
**without checking whether the task is already `deleted`** (or `paused`). In A+B
this is unreachable (`DisabledBorrowExecutor` is instantaneous, GIL does not
yield mid-`execute`). In Boundary C `execute` becomes a multi-second POST, and
`post_delete`/`post_pause` mutate the task through the **store lock** (a
different lock from `service._lock`, so they are not blocked by `tick`), so they
*can* fire during I/O. A success arriving after a delete would flip
`deleted → completed`. `test_borrow_store.py` has no coverage for
`resolve_attempt` after delete (it only tests `set_task_status("deleted")` at
line 269).

**Required freeze:** on `task.status == deleted`, never transition out of
`deleted`; `success_count` still increments on a real success (debt really
occurred) and the attempt row is always audited; the `unknown` reconciliation
marker is set regardless of paused/deleted. Add a `test_borrow_store` case:
resolve a success after delete and assert `status` stays `deleted`.

### P1-3 — Executor exception is not contained and can kill the scheduler thread (AC6 / D5 not enforceable today)

`service.py:297` calls `self._executor.execute(...)` with **no try/except**, and
the scheduler loop `scheduler.py:64-71` also has no try/except around
`self._tick()`. D5's last row and AC6 require that an unexpected executor
exception maps to `unknown`/unresolved and the **scheduler stays alive**. Today
an exception propagates out of `tick` → out of `_loop` → terminates the daemon
scheduler thread, which is not auto-restarted (`start()` is only called
explicitly at `server.py:430`). The attempt does stay pending (so restart orphan
recovery blocks the task — that part is fine), but the scheduler is dead.

**Required freeze:** wrap `execute` so any exception after pending insert maps
to `unknown` (or unresolved pending) and never re-raises out of `tick`; pin it
with a test that injects a raising executor and asserts the scheduler survives
and the task is blocked.

### P1-4 — Pending insert is not durably ineligible; pre-POST gate is underspecified (duplicate-debt landmine)

`store.py:326-375` (`insert_pending_attempt`) writes the pending attempt row and
advances the round-robin cursor, but **does not set
`borrow_task.unresolved_attempt_id`**. That marker is set only on `RESULT_UNKNOWN`
resolution (`store.py:457-462`) or at store-open orphan recovery
(`store.py:158-171`). Eligibility is `status=borrowing AND
unresolved_attempt_id IS NULL` (`store.py:225-234`). So during the live I/O
window (pending inserted, POST in flight, not yet resolved) the task is **still
durable-eligible**; non-duplication today relies entirely on the process-level
`service._lock` serializing `tick` (true in A+B, fragile as a design invariant)
and on no second process / no future "release lock during I/O" change.

Separately, `_dispatch_one` (`service.py:277-300`) checks only the rate-limit
cooldown; there is **no global execution-switch check**, no `live_authorized`
check, and no `status` re-check at dispatch time, because A+B has none of these.
A Stop/Pause/Delete that lands between selection and POST has no atomic gate to
abort the dispatch.

**Required freeze (single source of durability):** in the **same transaction**
as the pending insert, (a) re-check `status == borrowing`, `live_authorized`,
global execution enabled, and `unresolved_attempt_id IS NULL`; (b) set
`unresolved_attempt_id = attempt_id` so the task is durably ineligible for the
entire I/O window; (c) if any gate fails, do **not** insert and do **not** POST.
Clear the marker only on a terminal resolution that is not `unknown`. This
makes duplicate-debt prevention a ledger invariant rather than a lock-held
assumption, and it makes Global Stop/Pause/Delete-before-POST abort cleanly.
Once a POST's bytes have left the process, never suppress resolution — later
controls only block the *next* POST.

### P2-5 — The pre-C quarantine migration has no frozen schema

D7 says "add an internal live-authorization marker/version", "mark all pre-C
tasks as not live-authorized", "transition any pre-C `borrowing` task to
`paused` once". `store.py:26-74` (`_SCHEMA`) has no such column. The breakdown
must freeze: the exact column (e.g. `live_authorized INTEGER NOT NULL DEFAULT 0`),
the migration SQL with an **idempotency gate** (e.g. `PRAGMA user_version`, so
re-running cannot re-mark post-C tasks), the `create_task` default
(`live_authorized=1` for C tasks), the `post_start` behavior (explicit Start sets
`live_authorized=1`), and the `list_eligible_tasks` predicate change
(`AND live_authorized = 1`).

### P2-6 — The `known_rejection` business-code allowlist is not frozen

D5 maps "explicit exchange/business rejection proving no loan" to
`known_rejection`, but only `-51061` is evidenced (`03-grok-…recon.md` Class B).
Other 4xx (auth `-2014/-2015`, `-1100`, unknown codes) are undecided. The
fail-closed rule must be frozen: **only** codes officially documented as "no loan
created" enter the `known_rejection` allowlist; every other 4xx / unrecognized
code → `unknown` (block + reconcile). 2xx without a valid `tranId` → `unknown`;
5xx → `unknown` unless official evidence proves definite non-acceptance. The
concrete code set is evidence-gated (see §7).

### P2-7 — "POST transport must not retry" is not an explicit test

`private_client.py:177-179` retries 429 once after a 0.5 s sleep. The new borrow
client must never retry a POST (retry-after-ambiguity = duplicate debt).
ADR-003 says "no retries inside the POST transport", but the breakdown test list
("Client: … 429/418 with Retry-After") does not assert the one-shot property.
Add an explicit recording-transport test: on a 429 the client emits exactly one
POST and returns `rate_limited` with `Retry-After` for the service-level global
cooldown — never a second POST.

### P2-8 — `config.from_env` and `server.run` wiring changes are not called out in the breakdown

`config.py:174-186` currently `raise ValueError` for any
`APP_BORROW_EXECUTOR != "disabled"`; `Config` has no borrow-credential fields.
`server.py:419-430` (`run`) unconditionally constructs `BorrowTaskService(...)`
with the default disabled executor and ignores `config.borrow_executor`. Both
are in the allowed set, but breakdown steps 5–6 do not name the `from_env`
raise-removal, the new credential fields, or the `run` executor-selection branch.
Freeze them explicitly so the implementer does not treat the live path as
already wired.

## 3. Non-blocking findings

- **P3-9** `in_flight_attempt_id` (D2 status body) persistence is undefined.
  Recommend a transient in-memory field set before `execute` and cleared after
  `resolve`; on crash it is naturally absent and the orphan is handled by the
  existing pending/unknown marker (`store.py:158-171`). Avoid persisting it
  (removes crash-cleanup complexity).
- **P3-10** D6 says "when a known `tranId` exists, query/match by its documented
  transaction key" — but ADR-004/D5 make `tranId` an *immediate* success with no
  history block. Clarify that history is the authority only for `unknown`; a
  known `tranId` success may optionally audit history but never blocks on it.
- **P3-11** D6 "exact asset and amount match" does not name the loan-record
  field. Recon §5 shows records carry `principal` + `interest`; matching the
  *requested amount* should target `principal`. Field name is evidence-gated.
- **P3-12** The "no test contacts a production host" proof is unspecified. Reuse
  the existing monkeypatch pattern (`test_full_scenario_makes_zero_urllib_calls`,
  `test_borrow_executor.py:115`) plus a DNS-resolution assertion; freeze the
  concrete command in the breakdown evidence set.
- **P3-13** `06-direction-synthesis.md` permitted different tasks to be
  concurrently in flight under a short interval; Boundary C (D4 / ADR-005)
  tightens this to one POST in flight per process. Record this tightening
  explicitly in ADR-005 so a later reviewer does not read the synthesis and the
  stage as contradictory.
- **P3-14** Surface the blocked/reconciling state (existing
  `unresolved_attempt_id` + latest `unknown`) clearly in the task list/logs; an
  optional UI label is fine but not a new state machine.

## 4. Open-item decisions

1. **Execution-control routes + schema.** Adopt D2 as-is:
   `GET /api/borrow-execution-status`, `POST /api/borrow-execution/start`,
   `POST /api/borrow-execution/stop`; `schema_version = "borrow-execution/v1"`;
   status body per D2. `start`/`stop` return the updated status body (same shape
   as `GET`) so the frontend refreshes in one call. Errors reuse
   `schemas/api/borrow-tasks/error.schema.json`. New file
   `schemas/api/borrow-tasks/execution-status.schema.json` (does not exist yet —
   confirmed). `execution_enabled` (durable switch) defaults **false** on first
   C migration / empty store.
2. **Credential names + missing-credential behavior.** Adopt
   `BINANCE_BORROW_API_KEY` / `BINANCE_BORROW_API_SECRET` /
   `APP_BORROW_EXECUTOR=disabled|live`. **Missing credentials in `live` mode
   degrades to `blocked`, it does not crash startup**: `can_execute=false`,
   sanitized `block_reason` (e.g. `credentials_missing`). Rationale: allows
   runtime disabled↔live flipping via the durable switch; matches acceptance 1
   ("fails closed without sending a request" = blocked, not process death). An
   *invalid* executor value (not `disabled`/`live`) still raises at startup,
   consistent with current `config.py:182-186`. Read-only keys stay separate
   (`PrivateClient` env).
3. **Missing/invalid `Retry-After` fallback.** Freeze a conservative **60 s**
   global cooldown fallback for missing, non-numeric, non-positive, or
   implausibly large `Retry-After` (clamp the upper bound, e.g. 3600 s, to avoid
   a permanent accidental freeze from garbage); pin it with a test.
4. **Reconciliation read timing.** Evidence-gated. Until official propagation
   latency is captured, freeze a bounded backoff sequence (e.g.
   `[2, 5, 15, 30, 60]` s, max 5 reads) and a dispatch-anchored match window
   (e.g. ±60 s). Unique contract-valid match only → success; zero or multiple
   matches → stay blocked. Exhaustion → task stays blocked (never
   absence-as-failure, never a second POST). Revise when §7 evidence lands.
5. **Restart resume.** Adopt the draft proposal: **resume post-C live-authorized
   tasks** on restart; orphaned pending/unknown attempts remain blocking.
   Consistent with the first-tick immediate-dispatch behavior
   (`service.py:269-271`) and the durable global switch; the operator can Stop
   before restart. Pre-C tasks get a one-time migration to
   `live_authorized=false` and any pre-C `borrowing` → `paused`; explicit Start
   sets `live_authorized=1`.

## 5. Required amendments

- **`00-task.md` → File Boundaries.** Add
  `backend/services/portfolio_margin_borrow_client.py` and
  `backend/services/live_borrow_executor.py`; state `backend/borrow_tasks/**`
  stays network/signing-free and the live executor is injected, not imported, by
  the package.
- **`10-design.md` D4–D6 + acceptance.** Specify the atomic pending-insert
  transaction from P1-4: gate re-check (`status`/`live_authorized`/global switch/
  `unresolved_attempt_id IS NULL`) + set `unresolved_attempt_id` **before** any
  network; marker lifecycle (clear only on non-`unknown` terminal resolution).
- **`10-design.md` D5 + scheduler.** Wrap executor in exception containment
  (P1-3): any exception after pending insert → `unknown`/unresolved; scheduler
  never dies.
- **`10-design.md` D8.** Freeze the status matrix: success must not overwrite
  `deleted` (P1-2); pause/delete/stop **before** POST abort the insert; after
  POST bytes leave the process, resolution is never suppressed.
- **`10-design.md` D7 + `12-breakdown.draft.md` step 5.** Freeze the
  `live_authorized` column DDL, idempotent migration, `create_task`/`post_start`
  defaults, and `list_eligible_tasks` predicate (P2-5).
- **`10-design.md` D5 + `12-breakdown.draft.md` Result contract.** Freeze the
  fail-closed `known_rejection` rule; mark the concrete code set evidence-gated
  (P2-6).
- **`12-breakdown.draft.md` Required Test Scenarios (Client).** Add the explicit
  one-shot POST assertion on 429/418 (P2-7).
- **`12-breakdown.draft.md` Proposed Implementation Sequence (steps 5–6).** Name
  the `config.from_env` raise-removal, the new credential fields, and the
  `server.run` executor-selection branch (P2-8).
- **`11-adr.md` ADR-004/006 + edge cases.** Record the pending-marker durability
  decision, the `deleted`-terminal fix, the restart-resume decision, the
  Retry-After 60 s fallback, and that the A+B `resolve_attempt`
  completed-overwrite is a required fix, not optional polish.

## 6. Lean implementation assessment

The **one-task, serial, no-parallel route is appropriate** and I recommend
keeping it. Rationale: the work is backend-dominant (signer refactor, write
client, executor, migration, reconciliation, gates, tests) with only light
frontend wiring (badge, stop control, pre-submit summary, polling) — exactly the
`claude_glm` "whole mixed task when backend is the large majority" routing in
`stage-delivery.yaml:451-487`. Serial dispatch is already structurally guaranteed
by the single scheduler thread + synchronous `execute` inside `service._lock`
(`service.py:260-300`); concurrency would add rate-coordination and
ambiguous-overlap risk with no UI driver. No app-level caps / allowlist /
`maxBorrowable` preflight is correct per the user's frozen risk model;
reintroducing them would be scope creep, not a safety fix. No proposed component
is unnecessary complexity for the stated goal; the only over-specification risk
is `in_flight_attempt_id` persistence (P3-9 — keep it transient). Do not expand
into repay/hedge, browser scheduling, or app-level USDT caps under the guise of
"safety"; the correctness freezes above are sufficient server-side controls for
the user's chosen exposure model.

## 7. Evidence gaps (official exchange facts to capture before code)

The target directory
`reports/api-samples/2026-07-real-borrow-boundary-c-v1/` **does not exist yet** —
none of the following is captured; all are blockers for freezing
parameter/response/error semantics:

1. **`POST /papi/v1/marginLoan`** — exact path, required params (`asset`,
   `amount`, `recvWindow`, `timestamp`), request weight (recon infers 100 IP —
   re-verify), security type (TRADE/signed), **whether the signature is over
   query string or body**, response shape and `tranId` type/format, and the full
   error-code set.
2. **`GET /papi/v1/margin/marginLoan`** — exact path, params (`asset`, `txId`
   vs `tranId`, time-range fields, `limit`, pagination), weight (recon infers 10
   — re-verify), per-record shape (`principal`, `interest`, `asset`,
   `timestamp`, `txId`).
3. **Identity mapping** — confirm `txId` query matches POST `tranId`.
4. **`known_rejection` code allowlist** — which codes definitively mean "no loan
   created" (only `-51061` evidenced); needed to freeze D5 (P2-6).
5. **Idempotency** — whether any client order id / idempotency key exists (recon
   / design currently assume **none** — confirm). The design already side-steps
   double-borrow with write-ahead intent + fail-closed reconciliation, but
   confirm there is no server-side dedup being implicitly relied upon.
6. **Whether the borrow POST counts against the PM order 1200/min limit** (recon
   Class D, unverified) — affects capacity discussion only, not correctness.
7. **Loan-record propagation latency** — time from a successful POST until
   `tranId`/record is queryable; needed to freeze reconciliation timing (open
   item 4).
8. **`Retry-After` on POST 429/418** — existence, units, and format; needed to
   validate the 60 s fallback (open item 3).
9. **Base URL host** for papi write vs read (`https://papi.binance.com`
   hardcoded) — confirm for both endpoints.

Until these are archived as public official docs (no authenticated samples, no
live POST), treat recon links as **candidate** evidence only, not frozen
contract.

---

### Review Q-by-Q summary

| # | Question | Assessment |
| --- | --- | --- |
| 1 | Duplicate borrow after ambiguous result? | Intent correct; **P1-4** pending marker not durable + pre-POST gate atomic; **P2-7** POST no-retry must be tested. |
| 2 | Migration quarantine old A+B tasks? | Sound; freeze `live_authorized` DDL + idempotent migration + Start=authorization (**P2-5**). |
| 3 | Signer extraction vs GET-only? | Sound; freeze shared module location + security-test rewrite (**P1-1**). |
| 4 | Result classifications fail closed? | Skeleton sound; freeze `known_rejection` conservatively after docs (**P2-6**); executor exception must map to unknown (**P1-3**). |
| 5 | Stop/pause/delete races? | Intent correct; **P1-2** deleted-overwrite fix + **P1-4** atomic pre-POST gate. |
| 6 | Loan-history matching strength? | Unique match only is correct; freeze backoff + window; evidence still missing (**§7**). |
| 7 | Execution API + minimal FE enough? | Yes, if schema frozen and FE stays display-only. |
| 8 | Unnecessary complexity? | No; scope is appropriately minimal. |
| 9 | File boundaries + no-network tests? | Incomplete: live client/executor path unfrozen (**P1-1**); add race/exception/signer/static-host proofs. |
| 10 | Five open items? | Frozen in §4. |

---

```text
当前 Session ID: unavailable (runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/design-review.claude-glm.raw-output.md
本地北京时间: 2026-07-20 21:21:23 CST
下一步模型: human operator
下一步任务: cross-validate with design-review.raw-output.md (Grok 4.5); resolve the P1/P2 freezes into 10-design.md / 11-adr.md and the canonical 12-development-breakdown.md; capture the §7 official public evidence before implementation begins
```
