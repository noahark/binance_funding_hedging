# Design Adjudication Round 2 — Raw Output (Claude Opus 4.8)

## Capture metadata

| Field | Value |
| --- | --- |
| Stage | `2026-07-real-borrow-boundary-c-v1` |
| Role | round-2 read-only design adjudication over the four-review synthesis |
| Prompt | `design-review-round-2.opus.prompt.md` |
| Model name | **Claude Opus 4.8** (`claude-opus-4-8`) |
| Provider | `anthropic` |
| Adapter / runtime | Claude Code CLI |
| Provider-native Session ID | unavailable (runtime does not expose a provider-native Session ID) |
| Session ID source | unavailable |
| Executor | human_operator (operator dispatched the prepared prompt into this session) |
| Captured at (local) | 2026-07-20 21:53:15 CST |
| Product code edited | no |
| Stage files edited | no (this raw-output file only, on explicit operator instruction) |
| Live Binance / credentials | none |
| Models / adapters dispatched | none |

This is **not** formal review-1/review-2 and **not** an implementation
authorization. The same Opus 4.8 provider identity produced round-1
`13-design-review.md`; this round-2 adjudication therefore reviews, among
others, its own prior findings and explicitly overturns two of them (§2.1, §2.6).

## Read set actually consulted

Read in this session before writing:

- `AGENTS.md` (reviewers / dispatch / strong-reviewer sections)
- `14-design-review-synthesis.md`
- All four raw reviews: `13-design-review.md` (Opus 4.8),
  `design-review.raw-output.md` (Grok 4.5),
  `design-review.claude-glm.raw-output.md` (GLM-5.2),
  `design-review.raw-output-kimi.md` (Kimi for Coding)
- `00-task.md`, `10-design.md`, `11-adr.md`, `12-development-breakdown.draft.md`
- Source read for dispute verification: `backend/borrow_tasks/{domain,scheduler,service,store}.py`,
  `backend/config.py`, `backend/app/server.py`, `backend/tests/test_private_client.py`,
  `backend/tests/test_borrow_executor.py`, `frontend/self-check.js`

Two disputed claims were verified against source in this session; both results
are recorded in §2. No recursive read of other stages or `history/`.

---

## 1. Verdict: PASS_TO_DESIGN_AMENDMENT

The synthesis correctly consolidates the four reviews and its 14 freezes are the
right skeleton. It carries **six defects** (§2), all additive rather than
structural: no consolidated freeze is wrong in a way that would need the
synthesis rebuilt, and one of them is a correction to round-1 Opus, not to the
bookkeeper. §3 and §4 below supply every remaining freeze, so the bookkeeper can
proceed directly to amending `00-task.md` / `10-design.md` / `11-adr.md` and
then to the registered breakdown. `REWORK_SYNTHESIS` would be ceremony: the
disputed items are adjudicated here and this document supersedes them.

Implementation remains unauthorized until the evidence gate (§6) closes.

---

## 2. Synthesis corrections

### 2.1 — The resolve matrix omission is a real extra-POST path, and it is created *by* the 3/4 majority (including round-1 Opus)

Consolidated freeze 6 covers only `deleted`. Proposed Adjudication §6 notices the
`paused` disagreement but leaves it open. That gap is not cosmetic:

`store.py:431-437` today sets `completed` when `success_count >= success_target`
**regardless of status**. Opus/Grok/GLM all proposed suppressing that transition
for `paused` (leave the task `paused`). But `post_start` checks only
`status == paused` (`service.py:156-163`), and `list_eligible_tasks` filters only
`status='borrowing' AND unresolved_attempt_id IS NULL` (`store.py:225-234`) —
**neither compares `success_count` to `success_target`.**

So suppressing `paused → completed` produces a task sitting at
`count == target` in status `paused`; a later Start moves it to `borrowing`, it
becomes eligible, and the next tick sends **a real borrow POST beyond the user's
requested successful-attempt count**. That path does not exist today; the 3/4
recommendation would introduce it. Kimi's F7 (`paused → completed` permitted) is
correct and the majority — including round-1 Opus — is wrong.

Adjudicated in §3.7 with a belt-and-braces predicate fix.

### 2.2 — Consolidated freeze 2's eligibility predicate is incomplete

Freeze 2 lists status, `live_authorized`, global switch, cooldown and
`unresolved_attempt_id IS NULL`. It omits `success_count < success_target`.
Given 2.1 that omission is load-bearing, not tidiness. The predicate must be
frozen with the count comparison included.

### 2.3 — `self-check.js` has **two** incompatible guards, not one

Consolidated freeze 13 and Kimi F3 both name only the interval whitelist
(`frontend/self-check.js:3013-3015`, permits 60000/1000 only). Verified in this
session: the same proof block also enforces a **fetch method whitelist**
(`self-check.js:3000-3010`). Its final branch is
`else if (c.method !== 'GET') throw new Error('只读路由非法方法 …')`, so a POST to
`/api/borrow-execution/start` or `/stop` fails the self-check regardless of the
timer question. Both guards need explicit, exact amendments; naming only the
timer will produce a red self-check the implementer is tempted to loosen
wholesale.

### 2.4 — Kimi N2 is half-true, and the half that is true belongs in the record

Kimi claims the port bind already prevents a second scheduler. Verified in
`backend/app/server.py:417-442`: `BorrowTaskService(...)` is constructed at 417,
`build_server(...)` binds the socket at 419, and `borrow_service.start()` only
runs at 442. So a second process with the **same** `APP_BIND_PORT` does die
before its scheduler starts — the common "ran the command twice" accident is
already blocked.

It does **not** hold generally: `APP_BIND_PORT` and `APP_BORROW_DB_PATH` are
independent env-configurable fields (`config.py:188-189`, `config.py:266-271`),
so different port + same database yields two live schedulers. Kimi's own phrase
"effective but accidental" is the accurate reading.

The synthesis promoted single-ownership to a required freeze without recording
either half. Both belong in ADR context: the existing protection is real, it is
incidental to an unrelated bind, and debt-safety must not rest on it.

Secondary detail worth one line in the ADR: a non-owner process still opens the
store before its bind fails, and store open runs the orphan-recovery `UPDATE`
(`store.py:165-171`) against the owner's live database. It is benign — it writes
the marker the owner is about to write anyway — but it means "a second process
touches the DB" is already true today.

### 2.5 — Round-1 Opus's minimum-interval arithmetic was wrong; the synthesis correction is accepted, but it then under-decides

The synthesis is right that a 1-second floor at 100 weight/POST consumes the
entire candidate 6000/min budget and leaves nothing for reads or reconciliation.
Round-1 Opus derived the floor from "structurally impossible" (correct: 0.1s is
10× budget) and then reported the structural boundary itself as the floor
(incorrect: a floor must leave headroom). Correction accepted without defence.

But "keep the principle open pending verified quota math" leaves the most
dangerous configuration knob unfrozen through implementation. The right output
is a **formula plus a conservative interim constant**, both evidence-gated —
frozen in §3.6 — not an open question handed to the breakdown author.

### 2.6 — Two items were dropped from the four reviews without a recorded reason

- **Kimi N4 — borrow POST timeout constant.** Silently reusing
  `config.request_timeout` (15.0s, `config.py:50`, a snapshot-read tuning value)
  makes the timeout/`unknown` boundary a side effect of unrelated tuning. This
  is the exact latency at which an attempt becomes an ambiguous, task-blocking
  unknown; it deserves its own frozen constant. Adopted in §3.4.
- **Kimi F4 — HTTP 400 with business code `-1003` → `rate_limited`.** The
  existing read client already treats `-1003` as rate limiting
  (`private_client.py:191-200`). Consolidated freeze 10 does not mention it, so
  an implementer following freeze 10 literally would classify `-1003` as an
  unlisted 4xx → `unknown`, permanently blocking a task on what is really a
  cooldown condition. Adopted, evidence-gated, in §3.4.

---

## 3. Adjudication table

| # | Topic | Exact decision |
| --- | --- | --- |
| 1 | Single execution owner | **DB-path advisory `fcntl.flock`**, not a SQLite boot-token/lease. Detail in §3.1. |
| 2 | Routes | **Kimi's unified prefix**: `GET /api/borrow-execution/status`, `POST /api/borrow-execution/start`, `POST /api/borrow-execution/stop`. Detail in §3.2. |
| 3 | Missing credentials | **Blocked-but-service-starts** (3/4). Invalid mode still hard-fails at config load. Detail in §3.3. |
| 4 | Retry-After / 418 | Missing/invalid → **60s**. Valid values clamped to **[60s, 300s]**. 418 → **300s + manual confirmation**. Rate-limit cooldown **does** block reconciliation GETs; operator Stop **does not**. Detail in §3.4. |
| 5 | Reconciliation | Bounded **5 reads at +5s / +15s / +60s / +300s / +900s**, then terminal `reconciliation_exhausted`, blocked and visible. Never a second POST. Detail in §3.5. |
| 6 | Cadence | "Never replay historical ticks" **confirmed**. Minimum interval **required**, frozen by formula with interim constant **2s** (default stays 5s). Detail in §3.6. |
| 7 | Resolve matrix | Auto-complete permitted from **`borrowing` and `paused`**; `deleted` never overwritten; eligibility and Start both gain `success_count < success_target`. Detail in §3.7. |
| 8 | Status semantics | `in_flight_attempt_id` **transient in-memory**; `unresolved_attempt_id` **durable**. `global_cooldown_until` **must** be exposed and **must not** fold into `can_execute`. Detail in §3.8. |
| 9 | Security / file boundary | Both live modules under `backend/services/`, injected through the existing seam. **Five** static guards, each amended by exact filename only. Detail in §3.9. |
| 10 | Consolidated freezes 1–14 | See §4 freeze matrix. |

### 3.1 Single execution owner

**Mechanism: `fcntl.flock(LOCK_EX | LOCK_NB)` on a sidecar file `<borrow_db_path>.lock`.**

Rejected alternative: SQLite boot-token/lease. A lease needs a heartbeat, an
expiry constant, wall-clock trust, and stale-lease recovery — and a crashed
owner keeps the lease until it expires, so the product is *less* available
exactly when it failed. `flock` is released by the kernel on process death, so
crash recovery is free and needs no constant.

The lock is taken on a **sidecar file, not the database file**. SQLite manages
its own locking on the DB file; adding an advisory lock there risks interacting
with it.

Frozen semantics:

- **Acquisition:** non-blocking, in `BorrowTaskService.__init__` or immediately
  before `start()`, always before the scheduler thread exists. Held for process
  lifetime; never re-acquired per tick.
- **Second process:** starts normally and serves every read and task-mutation
  API. It does **not** start a scheduler. `can_execute=false`,
  `block_reason="not_execution_owner"`. Its mutations remain durable and are
  honoured by the owner.
- **Crash recovery:** kernel releases the lock; the next process acquires it.
  Orphaned pending attempts already block their tasks through
  `unresolved_attempt_id`; ownership adds nothing to that path and must not.
- **Release:** on `close()`/process exit. Never released while the scheduler runs.
- **Status projection:** owner and non-owner return the identical document
  shape; only `can_execute`/`block_reason` differ.
- **Deterministic test:** one test process opens two services on the same
  `db_path`; assert the second reports `not_execution_owner`, that its scheduler
  thread is absent, and that a forced tick on it dispatches nothing. `flock` is
  per open-file-description, so two `open()` calls in one process reproduce this
  without subprocesses.

ADR must also record §2.4: the incidental port-bind protection exists, covers
the common case, and is not the safety mechanism.

### 3.2 Routes

Adopt Kimi's unified prefix. The 3/4 count for the mixed names carries no weight
here — no implementation exists, nothing has been built against either shape, and
the majority gave no technical reason beyond having reviewed the draft. The
unified prefix adds exactly one entry to `_is_borrow_path` (`server.py:47-55`)
instead of two, and matches the existing `/api/borrow-tasks/...` prefix-dispatch
style. Renaming later would be churn; renaming now is free.

```text
GET  /api/borrow-execution/status
POST /api/borrow-execution/start
POST /api/borrow-execution/stop
```

Frozen body (`schemas/api/borrow-tasks/execution-status.schema.json`,
`schema_version = "borrow-execution/v1"`, `additionalProperties: false`):

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

- `start`/`stop` take no body, are **idempotent**, and return 200 with this same
  document. No optimistic-concurrency `version` on either: a Stop must never
  fail because of a concurrency check.
- `execution_enabled` defaults **false** on a fresh database and on a migrated
  database.
- `block_reason` is a sanitized enum: `executor_disabled`, `globally_stopped`,
  `borrow_credentials_missing`, `not_execution_owner`, `rate_limited`,
  `invalid_configuration`. Never environment values.
- Errors reuse `schemas/api/borrow-tasks/error.schema.json`.

### 3.3 Missing credentials

Adopt the 3/4 outcome; Kimi's hard-fail is rejected.

- `APP_BORROW_EXECUTOR` not in `{disabled, live}` → `ValueError` at config load,
  before any bind. Preserves `config.py:182-186` behaviour.
- `live` + missing/empty `BINANCE_BORROW_API_KEY` or `BINANCE_BORROW_API_SECRET`
  → process starts; `mode="live"`, `can_execute=false`,
  `block_reason="borrow_credentials_missing"`; zero signed traffic from the
  borrow client.
- `disabled` + credentials present → normal start; credentials never read,
  never logged.

Kimi's concern (a hard failure is louder for an operator present at startup) is
legitimate and is answered without killing the unrelated snapshot/UI service:
`_emit_lifecycle` must emit a distinct startup event carrying
`borrow_executor=live` and `borrow_execution_blocked=borrow_credentials_missing`,
and the frontend badge must render the blocked state unmissably. Availability of
the read-only product outranks startup volume; blocked is equally fail-closed.

### 3.4 Retry-After / 418 / cooldown scope

- Missing, unparseable, non-numeric, or non-positive `Retry-After` → **60s**
  (4/4 consensus).
- Valid value → **clamped to [60s, 300s]**. Adjudicating the open clamp: the
  lower bound at 60s because the PM budget is a *per-minute* window and a
  shorter cooldown can re-enter the same window that just rejected us; the upper
  bound at 300s rather than the 3600s that Grok/GLM proposed because a
  five-minute freeze is already far beyond any plausible per-minute recovery,
  while an hour-long freeze from one malformed header silently kills the
  product for a supervised operator who cannot tell it apart from a hang.
- **418 → 300s and no automatic recovery.** The cooldown expiring does not
  resume dispatch; `block_reason` stays `rate_limited` until the operator calls
  `start` again. Rationale: 418 is a ban, not a throttle, and its duration is an
  unarchived fact (§6). Auto-resuming into a ban risks extending it.
- **HTTP 400 with business code `-1003` → `rate_limited`**, consistent with
  `private_client.py:191-200`. Evidence-gated on the papi representation (§6).
- **Cooldown scope:** a rate-limit cooldown blocks **all** signed borrow-client
  traffic, including reconciliation GETs, because the budget is IP-level and
  shared and the exchange asked for backoff. An operator **Stop** blocks only
  POSTs; reconciliation GETs continue, because Stop means "create no new debt",
  and the operator needs the truth about attempts already in flight. This is the
  separation the synthesis asked for in its question 4.
- **Borrow POST timeout: frozen module-level constant, 10 seconds**,
  test-overridable, **not** env-configurable, and explicitly not
  `config.request_timeout` (§2.6). Adopting Kimi N4.

### 3.5 Reconciliation

Bounded; Kimi's uncapped loop is rejected (it produces indefinite background
private traffic without ever strengthening the proof).

Delays measured from the moment the attempt became unresolved:

```text
+5s → +15s → +60s → +300s → +900s   (5 reads, ~21 min total)
```

then stop automatically and enter terminal `reconciliation_exhausted`.

- Cost is negligible: weight 10 × 5 = 50 against a candidate 6000/min budget.
- No read earlier than 5s: propagation latency is unarchived (§6), and an early
  empty read is indistinguishable from a real absence.
- The long tail at 900s exists because a late read costs almost nothing and is
  the last chance to catch a delayed record before giving up.
- Exhaustion leaves the task **blocked and visible**, never eligible. It
  authorizes nothing. The only operator exit remains delete; no HTTP
  force-clear, no "retry anyway" route, ever (Grok P1-2 adopted verbatim).
- Matching: unique `txId` match when a `tranId` is known; otherwise a unique
  contract-valid record in a dispatch-anchored window with exact asset and
  `Decimal` amount equality. Zero or multiple matches → stay blocked.
  Cross-task ambiguity (another task could have produced the record) → stay
  blocked. Balance deltas are corroboration only, never authority.
- On a reconciliation-proven success, persist the matched id into the attempt's
  `tran_id` and set `reason="reconciled_unique_txid_match"` so audit
  distinguishes response-proven from history-inferred success (Kimi N1 adopted).
- Window width and record field names are evidence-gated (§6); until archived,
  implementers must not invent multi-hour windows or loose amount matching.

### 3.6 Cadence

- **"Never replay historical ticks" is confirmed as a hard invariant.** On a
  skipped, blocked, cooled-down, or slow interval, `_last_tick_mono` advances to
  `now` (`service.py:272-275`), never by accumulated intervals. Regression test:
  after a 60s cooldown at a 5s interval, assert ≤1 dispatch in the following
  3 seconds.
- **A minimum interval is required**, and it is an exchange-capacity contract
  constraint, not an app-level exposure cap — the user's frozen risk model
  covers principal/amount/count, not request rate. The decisive argument is
  shared-resource damage: 418 is an **IP** ban, so a sub-second borrow cadence
  takes down the read-only snapshot channel on the same IP. That is collateral
  correctness damage, not a risk preference.
- **Formula (authoritative):**

  ```text
  min_interval_seconds = ceil( 60 / (0.5 × ip_budget_per_min / post_weight) )
  ```

  Half the documented IP budget is reserved for reads and reconciliation.
- **Interim constant: 2 seconds**, from the candidate values `6000/min` and
  weight `100` (→ 30 POST/min → 2s). The default stays **5s** and is unchanged.
- Both the constant and the formula inputs are evidence-gated (§6). If the
  archive contradicts weight 100 or budget 6000, the constant is recomputed from
  the formula, not renegotiated.
- Kimi N5's risk sentence is adopted **in addition**, not instead: the interval
  input is not a product throughput promise.

### 3.7 Resolve matrix

| Status when the result resolves | `success_count` | Status transition |
| --- | --- | --- |
| `borrowing`, count < target | +1 | stays `borrowing` |
| `borrowing`, count reaches target | +1 | → `completed` |
| `paused`, count < target | +1 | stays `paused` |
| `paused`, count reaches target | +1 | → `completed` |
| `deleted` | +1 | **stays `deleted`, always** |
| `completed` | +1 | stays `completed` |

Auto-completion is permitted from `borrowing` **and** `paused` (§2.1). Adopting
Kimi F7 and overturning Opus/Grok/GLM, including round-1 Opus.

Non-success categories never change status. `unknown` sets/retains the
reconciliation marker regardless of status, including on paused and deleted
tasks. Every dispatched attempt is always resolved and audited; controls only
prevent the *next* POST.

**Zero-extra-POST guarantee** — belt and braces, both required:

1. Eligibility predicate gains the count comparison:
   `status='borrowing' AND unresolved_attempt_id IS NULL AND live_authorized=1
   AND success_count < success_target`.
2. `post_start` (`service.py:156-163`) must refuse to move a task to `borrowing`
   when `success_count >= success_target`; it returns the task as `completed`
   instead. Idempotent, no error path needed for the ordinary case.

With the transition rule alone, a legacy row already at target could still be
Started; with the predicate alone, a Started at-target task would sit eligible-
looking in the UI forever. Both are cheap; freeze both.

### 3.8 Status semantics

- `in_flight_attempt_id` is **transient and in-memory**: set immediately before
  `executor.execute`, cleared in the resolve path including the exception
  branch. It is absent after a restart, which is correct.
- `unresolved_attempt_id` is the **durable** blocker: set inside the pending-
  insert transaction, cleared only on a terminal non-`unknown` resolution.
- **Kimi F9 is rejected.** Deriving in-flight state from pending ledger rows is
  wrong in exactly the case Kimi claims it is right: after a crash a pending row
  is an *orphan*, not an in-flight request, and reporting it as in-flight tells a
  supervising operator a request is running when no process is running it. The
  synthesis reached the correct conclusion; this confirms it as binding.
- `global_cooldown_until` (nullable ISO string) **must** be exposed. Without it a
  supervised operator cannot explain why enabled execution is not dispatching.
- Cooldown **must not** fold into `can_execute`. `can_execute` answers "is this
  process configured and authorized to borrow" — a stable operator-facing fact;
  cooldown is a transient exchange condition. Collapsing them makes the badge
  flicker between enabled and disabled during normal 429 handling and trains the
  operator to ignore it. Frozen:
  `can_execute = (mode=="live") AND execution_enabled AND credentials_present
  AND is_execution_owner`.

### 3.9 Security and file boundary

- **Both live modules under `backend/services/`**, exact frozen names, injected
  through the existing `BorrowTaskService(executor=…)` seam
  (`service.py:104-120`). `backend/borrow_tasks/**` stays network- and
  signing-free. Kimi's suggestion of `backend/borrow_tasks/pm_borrow_client.py`
  is rejected — it contradicts that same review's own AST-purity finding, as the
  synthesis already noted.
- **Five static guards**, not four (§2.3). Each may be amended **only** by
  adding exact filenames; no wildcard, prefix, or directory exemption; each
  amendment must add a dual assertion so the guard is narrowed, never merely
  widened:

  | Guard | Location | Exact amendment |
  | --- | --- | --- |
  | single HMAC exit | `test_private_client.py:77-87` | allow exactly `binance_signing.py`; assert neither client constructs HMAC inline |
  | urlopen confinement | `test_private_client.py:90-102` | allow exactly the one new borrow-client filename |
  | borrow-package AST purity | `test_borrow_executor.py:82-111` | unchanged — it must keep failing if a live module lands in `borrow_tasks/` |
  | self-check interval whitelist | `self-check.js:3013-3015` | add exactly the borrow-view poll delay |
  | self-check fetch-method whitelist | `self-check.js:3000-3010` | add exactly the two `/api/borrow-execution/{start,stop}` POST routes |

- The new client needs its **own** gate-fires-before-signing negative test; it
  does not inherit `test_private_client.py:164`.
- Signing and sending must use one serialized payload string produced by one
  function.
- The POST transport is **one-shot**: an explicit recording-transport test must
  assert that 429/418, timeout, connection reset, 5xx, and malformed responses
  each produce exactly one POST (Grok/GLM P2-7).

---

## 4. Freeze matrix

| # | Synthesis freeze | Ruling | Note |
| --- | --- | --- | --- |
| 1 | One execution owner per database | **AMEND** | Adopt as required; freeze mechanism = sidecar `flock` (§3.1); ADR records the incidental port-bind protection and its limit (§2.4) |
| 2 | Pending means durably ineligible before I/O | **AMEND** | Add `success_count < success_target` to the predicate (§2.2) |
| 3 | Controls atomic at the dispatch boundary | **ADOPT** | — |
| 4 | No historical-tick catch-up | **ADOPT** | Confirmed as hard invariant; regression test specified (§3.6) |
| 5 | Unknown never authorizes another POST | **ADOPT** | Includes the no-force-clear-API rule |
| 6 | `deleted` is terminal | **AMEND** | Correct but incomplete; replace with the full resolve matrix and the zero-extra-POST guarantee (§3.7) |
| 7 | Executor and scheduler failures contained | **ADOPT** | Containment at `_dispatch_one` **and** `BorrowScheduler._loop` |
| 8 | One exact signing/network exit | **AMEND** | Five guards, not four; dual-assertion requirement (§3.9, §2.3) |
| 9 | POST transport is one-shot | **ADOPT** | — |
| 10 | Exchange rejection deny-by-default | **AMEND** | Add `-1003` → `rate_limited` (§2.6); empty allowlist remains valid |
| 11 | Migration is an idempotent authorization boundary | **ADOPT** | `PRAGMA user_version`; `live_authorized INTEGER NOT NULL DEFAULT 0` |
| 12 | Reconciliation matching is strict | **ADOPT** | Extended by the §3.5 cadence and audit-reason freezes |
| 13 | Supervision exposes real blockers | **AMEND** | Two self-check guards (§2.3); `global_cooldown_until` exposed but excluded from `can_execute` (§3.8) |
| 14 | Official contract evidence is a pre-code gate | **ADOPT** | Extended by §6 |

Nothing is `DROP`.

---

## 5. Exact document amendments

### `00-task.md`

1. **File Boundaries** — add `backend/services/binance_signing.py` (already
   present), the frozen borrow-client filename, the frozen live-executor
   filename, and their test files. State that `backend/borrow_tasks/**` stays
   network/signing-free and the executor is injected, not imported.
2. **AC3 / AC6** — the pending-insert transaction re-checks status,
   `live_authorized`, global switch, cooldown, ownership,
   `unresolved_attempt_id IS NULL`, and `success_count < success_target`, and
   sets `unresolved_attempt_id` before any network I/O; a failed check creates
   no attempt row and no POST.
3. **AC5** — `known_rejection` only for the evidence-enumerated code set;
   unlisted 4xx → `unknown`; `-1003` → `rate_limited`; 2xx without a valid
   normalized `tranId` → `unknown`.
4. **AC9** — Stop is atomic with the conditional insert; add the ownership gate.
5. **AC10** — replace with the §3.7 resolve matrix plus the zero-extra-POST
   guarantee.
6. **AC12** — add per-task blocked/reconciling rendering and cooldown
   visibility.
7. **New AC** — exactly one execution owner per database; a second process
   serves read/mutation APIs, starts no scheduler, reports
   `not_execution_owner`.

### `10-design.md`

1. **D1** — minimum interval: formula plus interim 2s constant; default stays 5s.
2. **D2** — replace the three route names with the unified prefix; add
   `global_cooldown_until` and `live_authorized_task_count`; freeze the
   `can_execute` expression excluding cooldown; `execution_enabled` defaults
   false on fresh and migrated databases; freeze the `block_reason` enum.
3. **D3** — one serialization function shared by signing and sending; frozen
   module locations; the new client's own gate-before-signing test.
4. **D4** — delete "a slow request makes observed cadence slower"; replace with
   the never-replay invariant; add the ownership lock and its acquisition point.
5. **D5** — deny-by-default classification table; `-1003`; the 10s POST timeout
   constant; exception containment at both `_dispatch_one` and
   `BorrowScheduler._loop`.
6. **D6** — the §3.5 bounded sequence; cooldown blocks reconciliation GETs while
   operator Stop does not; `Decimal` amount comparison; cross-task ambiguity
   stays blocked; the reconciled-success audit reason; terminal
   `reconciliation_exhausted`.
7. **D7** — `PRAGMA user_version` migration, `live_authorized` DDL and default,
   `create_task`/`post_start` semantics, the full eligibility predicate.
8. **D8** — the §3.7 resolve matrix table verbatim.
9. **D9** — per-task blocked/reconciling rendering; both self-check guard
   amendments named explicitly.
10. **Risks** — single-owner assumption and where the incidental port-bind
    protection fails; sub-second cadence is exchange-throttled and the interval
    input is not a throughput promise.

### `11-adr.md`

1. **New ADR-008 — single execution owner.** `flock` chosen over lease, with the
   rejected-alternative reasoning; acquisition/release/crash semantics;
   read-only second-process behaviour; §2.4 recorded as context.
2. **ADR-004** — pending-marker durability; the A+B `resolve_attempt`
   overwrite is a **required fix**, not optional polish; the 60s fallback with
   the [60s, 300s] clamp; 418 requires manual re-arm.
3. **ADR-006** — split into two rules: one-time pre-C quarantine (explicit Start
   authorizes) versus ordinary restart resume (state preserved, orphans
   blocked, recovery counts reported).
4. **New edge cases** — Stop/pause/delete landing between selection and POST;
   `deleted` terminal; `paused → completed` permitted and *why* suppressing it
   would create an extra-POST path; Start refused at target.
5. **ADR-005** — record the tightening relative to `06-direction-synthesis.md`,
   which permitted concurrent in-flight tasks (GLM P3-13).

### `12-development-breakdown.md` (canonical)

1. All five draft open items are closed by §3; the breakdown records the
   decisions, it does not re-open them.
2. Freeze the exact live module filenames and the five guard amendments with
   their dual assertions.
3. Name the wiring work explicitly: remove the `config.py:182-186` raise for
   `live`, add credential fields, add the `server.run` executor-selection branch
   and the ownership-lock acquisition point (GLM P2-8).
4. Required tests, at minimum: two-owner ownership test; gate re-check aborts
   insert with zero POST; success-after-delete keeps `deleted`;
   success-at-target-while-paused → `completed`; Start refused at target;
   no-catch-up after cooldown; one-shot POST per error class; exception
   containment keeps the scheduler alive; migration idempotence via
   `user_version`; reconciliation unique/zero/multiple/cross-task/exhausted;
   `Decimal` amount matching; large-integer `tranId` normalization; redaction of
   both new env names; both self-check guards.
5. Build the pre-C schema fixture in-test via raw SQL; no binary fixture.

---

## 6. Evidence gate

Nothing below may be frozen from memory. Each row states the fail-closed default
that holds if the archive under
`reports/api-samples/2026-07-real-borrow-boundary-c-v1/` cannot establish it.

| Fact needed | Consumer | Fail-closed default if unarchived |
| --- | --- | --- |
| `POST /papi/v1/marginLoan` params, security type, encoding (query vs body) | §3.9 signing | **Implementation blocked.** No safe default exists. |
| POST request weight | §3.6 formula | **Implementation blocked** for the interval floor; the 2s interim assumes weight 100 |
| PM IP budget per minute | §3.6 formula | Assume the recon candidate 6000/min; record as inference |
| `tranId` type and magnitude | §3.5 normalization | Treat as arbitrary-precision integer; stringify; never parse as float |
| `GET /papi/v1/margin/marginLoan` params, pagination, history depth | §3.5 matching | **Reconciliation blocked**; unknown attempts stay blocked with no auto-resolution |
| Loan-record per-record fields incl. the principal/amount field name and timestamp | §3.5 matching | Match by `txId` **only**; response-less unknowns are never auto-resolved |
| `txId == tranId` correspondence | §3.5 fast path | Treat as unproven; response-proven success still stands on the POST body alone |
| Business codes proving "no loan created" | §3.4 classification | **Empty allowlist.** Every 4xx → `unknown`. This is a valid shipping state. |
| `-1003` representation on papi (400 body vs 429) | §3.4 | Handle both; classify either as `rate_limited` |
| `Retry-After` presence, units, format on papi | §3.4 | 60s fallback covers every parse failure |
| 418 semantics and duration | §3.4 | 300s + manual re-arm; never auto-resume |
| Loan-record propagation latency | §3.5 sequence | No official SLA → the +5s/+15s/+60s/+300s/+900s series stands as a conservative guess and is labelled as such |
| Idempotency key existence | ADR-004 | Assume none; write-ahead intent + fail-closed reconciliation is the whole defence |
| Whether `marginLoan` counts against the 1200/min order limit | capacity note only | Assume it may; does not affect correctness |
| Per-asset minimum amount / precision rules | rejection taxonomy | Unknown → the rejection code lands in the unlisted-4xx bucket → `unknown` |
| papi write base URL | §3.9 allowlist | Hardcode `https://papi.binance.com`; never caller-supplied |

Two rows are **hard implementation blockers** (POST parameter contract; POST
weight for the floor). The rest have safe fail-closed defaults, several of which
ship a deliberately degraded product — an empty `known_rejection` allowlist and
`txId`-only matching are both acceptable first-live states.

No authenticated sample and no live POST is required or authorized to close this
gate. Public documentation only.

---

## 7. Lean-scope check

**Still one serial backend-dominant task; parallel and embedded review stay off.**
4/4 reviews agreed and round 2 does not disturb it. The frontend surface is a
badge, a stop control, a pre-submit summary, per-task blocked rendering, and one
poll — light integration with no separable second workload, and it now depends on
backend contracts (`block_reason` enum, `global_cooldown_until`, blocked-state
derivation) that would have to be frozen across a task boundary for no gain.

**New components introduced by round 2: exactly one** — the sidecar `flock`
ownership lock (§3.1). It is correctness-necessary, roughly a dozen lines, adds
no constant, no thread, no clock dependency, and no crash-recovery path.

**Explicitly *not* added**, having been considered and rejected as unnecessary
complexity:

- lease/heartbeat ownership (rejected in §3.1 for the constant and the
  stale-lease recovery path it drags in);
- a reconciliation thread — reconciliation runs on the existing service tick;
- persisting `in_flight_attempt_id` (§3.8);
- any HTTP unblock/force-clear/retry route (§3.5);
- app-level USDT caps, asset allowlists, `maxBorrowable` preflight, draft/arm
  lifecycle, concurrent POST workers, browser scheduling — all remain out, and
  the minimum interval in §3.6 is deliberately framed as an exchange-capacity
  contract constraint so it is not mistaken for a reintroduced risk cap.

Two round-2 freezes **reduce** implementation scope rather than adding to it:
the deny-by-default classification permits an empty allowlist, and the evidence
gate's fail-closed defaults let the stage ship with `txId`-only reconciliation
rather than waiting on propagation facts that may never be archived.

---

## Execution record

Read-only round-2 adjudication. In this session: no product code or stage file
was edited other than this raw-output file, written on explicit operator
instruction; no model session or adapter was invoked, launched, or relayed to;
no `.env`, key file, cookie, or private payload was read; no authenticated
request and no Binance POST was sent; no Binance contract fact was supplied from
memory — every unarchived fact is routed to §6. Every `file:line` citation
corresponds to a file actually read in this session. Two disputed claims
(§2.3, §2.4) were verified against source before ruling, and both rulings differ
from what the synthesis recorded.

```text
当前 Session ID: unavailable (runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
评审模型: Anthropic / Claude Opus 4.8 (`claude-opus-4-8`)
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/design-review-round-2.opus.raw-output.md
本地北京时间: 2026-07-20 21:53:15 CST
下一步模型: bookkeeper (Codex/GPT) → registered breakdown author (Claude provider, Fable5 first)
下一步任务: apply §5 to 00-task.md / 10-design.md / 11-adr.md; close the §6 evidence gate with public official documentation; then produce the canonical 12-development-breakdown.md. Implementation remains unauthorized until both are done.
```
