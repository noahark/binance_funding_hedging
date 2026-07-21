# Multi-Review Synthesis — Boundary C Real Borrowing

Stage: `2026-07-real-borrow-boundary-c-v1`
Role: bookkeeper synthesis of four independent read-only design reviews
Status: **REWORK remains open; this synthesis is not a review gate or an
implementation authorization**

## Source Reviews

This synthesis preserves, and does not replace, the four raw artifacts:

| Reviewer | Provider identity | Raw artifact | Verdict |
| --- | --- | --- | --- |
| Claude Opus 4.8 | `anthropic` | `13-design-review.md` | `REWORK` |
| Grok 4.5 | `xai_grok` | `design-review.raw-output.md` | `REWORK` |
| GLM-5.2 | `zhipu_glm` | `design-review.claude-glm.raw-output.md` | `REWORK` |
| Kimi for Coding | `moonshot` | `design-review.raw-output-kimi.md` | `REWORK` |

The four reviews agree that the Boundary C direction remains lean and viable:
one serial backend-dominant task, no browser scheduler, no app-level USDT cap,
no `maxBorrowable` preflight, and no repay/hedge/order expansion. Their REWORK
verdicts concern missing correctness freezes and contract evidence, not a need
to redesign the product flow.

## Consolidated Outcome

Implementation is not ready. The amended design must make the following
properties explicit and testable before the registered breakdown is written:

1. **One execution owner per database.** A second server process sharing the
   same SQLite database must not start an independent write scheduler. It may
   continue to serve read-only/status APIs and must expose
   `block_reason="not_execution_owner"`. The exact lock mechanism remains for
   round-2 adjudication.
2. **Pending means durably ineligible before network I/O.** The pending-insert
   transaction must re-check task status, `live_authorized`, the durable global
   switch, cooldown, and `unresolved_attempt_id IS NULL`; it then inserts the
   attempt and sets `unresolved_attempt_id` before any POST. A failed check
   creates no network attempt.
3. **Controls are atomic at the dispatch boundary.** Stop/pause/delete before
   the conditional insert prevent the POST. Once request bytes have left the
   process, resolution and audit are never suppressed; controls only prevent a
   later POST.
4. **No historical-tick catch-up.** A skipped, blocked, slow, or cooled-down
   interval is discarded. `_last_tick_mono` advances to `now` after a due tick;
   the scheduler must never burst old ticks after a cooldown.
5. **Unknown never authorizes another POST.** Transport ambiguity, malformed
   success, unclassified 4xx, 5xx, or unexpected execution failure keeps the
   task blocked until a unique loan-record match proves success. There is no
   HTTP force-clear or “retry anyway” route.
6. **`deleted` is terminal.** An in-flight success still increments the durable
   count and is audited, but it never rewrites `deleted` to `completed`.
7. **Executor and scheduler failures are contained.** Exceptions after pending
   insert resolve/remain `unknown`; the scheduler loop also has a last-resort
   guard so a store/projection error cannot silently kill the thread.
8. **One exact signing/network exit.** HMAC construction moves only to
   `backend/services/binance_signing.py`. The narrow PM client and live executor
   have exact, frozen paths under `backend/services/`; `backend/borrow_tasks/**`
   remains network/signing-free. Existing static guards are amended by exact
   filenames, never wildcard or directory exemptions.
9. **The POST transport is one-shot.** Recording-transport tests must prove that
   429/418, timeout, connection reset, 5xx, and malformed responses each cause
   exactly one borrow POST.
10. **Exchange rejection is deny-by-default.** `known_rejection` is available
    only for a stage-archived, evidence-enumerated business-code set. Until the
    evidence proves a code, unlisted 4xx responses are `unknown`; a 2xx without
    a valid normalized `tranId` is also `unknown`.
11. **Migration is an idempotent authorization boundary.** The canonical
    breakdown must freeze a versioned migration, a fail-closed
    `live_authorized` column/default, the exact eligibility predicate, the
    one-time pre-C pause/quarantine, and Start/Confirm authorization semantics.
12. **Reconciliation matching is strict.** `tranId`/`txId` uses one
    large-integer-safe string normalization path; amount comparison uses
    `Decimal`; response and history representations share the same normalizer;
    cross-task or external-loan ambiguity remains blocked. Signing and sending
    must use the same serialized payload bytes.
13. **Supervision exposes real blockers.** The frontend/task projection shows
    unresolved/reconciling tasks, while execution status exposes the global
    cooldown. The new two-second display poll requires an explicit amendment
    to the current frontend timer self-check; it remains display-only.
14. **Official public contract evidence is a pre-code gate.** The exact POST
    and loan-history GET docs, parameters/encoding, security type, weights,
    response IDs, error semantics, `Retry-After`, idempotency, and history
    fields must be archived under the stage API-sample path. No authenticated
    sample or live POST is required or authorized.

## Agreement Matrix

| Topic | Review alignment | Synthesis treatment |
| --- | --- | --- |
| One serial implementation task; parallel mode off | 4/4 | Adopt |
| Pending marker + atomic pre-POST gate | 4/4 | Adopt as DB invariant |
| `deleted` terminal while retaining audit/count | 4/4 | Adopt |
| Evidence-enumerated `known_rejection` | 4/4 | Adopt; empty set is valid |
| Exact signer/client security boundaries | 4/4 | Adopt |
| Public official contract evidence before code | 4/4 | Adopt as hard dependency |
| Missing/invalid `Retry-After` fallback = 60s | 4/4 | Adopt fallback; clamp remains open |
| Normal restart resumes post-C authorized tasks | 4/4 | Adopt; pre-C quarantine remains one-time |
| Missing live credentials report blocked, not process death | Opus/Grok/GLM vs Kimi | Prefer 3/4 blocked behavior |
| Existing mixed execution route names | Opus/Grok/GLM vs Kimi | Prefer 3/4 existing names |
| Bounded reconciliation attempts | Opus/Grok/GLM vs Kimi | Prefer bounded; exact delays evidence-gated |
| Cross-process execution ownership | Opus blocker; Kimi notes assumption | Promote to required correctness freeze |
| Never catch up missed scheduler ticks | Opus only, directly source-confirmed | Promote to required correctness freeze |
| Hard minimum interval | Opus proposes 1s; Grok/Kimi resist | Keep principle open pending verified quota math |

## Proposed Adjudication Of Conflicts

These are synthesis recommendations for the Opus round-2 discussion, not yet
user-approved product freezes.

### 1. Execution routes and status

Keep the three paths already reviewed by three models:

```text
GET  /api/borrow-execution-status
POST /api/borrow-execution/start
POST /api/borrow-execution/stop
```

Start and Stop accept no body, are idempotent, and return the same status shape
as GET. Keep `schema_version = "borrow-execution/v1"`; add
`global_cooldown_until` because a supervised operator otherwise cannot explain
why enabled execution is not dispatching. `in_flight_attempt_id` should mean a
request currently executing in this process and therefore be transient; a
durable pending/orphan is represented by the task's `unresolved_attempt_id`,
not mislabeled as still in flight after restart.

### 2. Missing credentials

Prefer the Opus/Grok/GLM outcome: invalid `APP_BORROW_EXECUTOR` fails startup,
but `live` with missing dedicated credentials starts the snapshot/UI service in
a fail-closed state with `can_execute=false` and a sanitized
`block_reason="borrow_credentials_missing"`. This preserves availability
without weakening the zero-POST guarantee.

### 3. Retry-After and 418

Freeze 60 seconds only as the missing/invalid fallback. The upper clamp and 418
recovery policy still need evidence and round-2 adjudication. Opus's proposed
300-second upper clamp is safer for liveness; the other reviews propose up to
3600 seconds. A valid short header also raises a policy question: honor the
exchange value or impose a 60-second minimum. Do not hide this choice inside
implementation.

### 4. Reconciliation cadence

Reject unbounded automatic reconciliation. It creates permanent background
private traffic without stronger success proof. Prefer a finite series followed
by a visibly blocked terminal reconciliation condition. The exact delays cannot
be honestly selected from the repository today because the public archive has
no propagation SLA; freeze them only after the contract-evidence pass. Global
Stop should block new POSTs, not safe history reconciliation, unless the
evidence establishes a shared cooldown reason to defer the GET.

### 5. Scheduler rate contract

Adopt “never catch up old ticks” immediately. Do not yet freeze Opus's proposed
one-second product minimum: the cited arithmetic consumes the entire candidate
6000-weight/min budget at 100 weight per POST and leaves no headroom for
reconciliation or other IP-weight traffic. After official weights and limits
are archived, the design must either derive a conservative minimum with
headroom or explicitly record that the operator may configure a cadence that
will be exchange-throttled. This is an exchange-capacity contract question, not
an app-level exposure cap.

### 6. Resolve-time status

All reviews agree that `deleted` is never overwritten. They do not agree on a
success arriving after Pause and reaching `success_target`: some preserve
`paused`, while Kimi permits `paused -> completed`. Round 2 should freeze the
matrix and also say what a later Start does when `success_count >=
success_target`, so no extra POST can occur.

### 7. Single execution owner

The atomic pending marker prevents two processes from dispatching the same task,
but it does not prevent concurrent POSTs for different tasks, duplicated
schedulers, or ambiguous cross-task history matching. Preserve Opus's
single-owner requirement. Round 2 should select a lean mechanism and define
acquisition, release, crash recovery, read-only second-process behavior, and
deterministic tests.

## Suggestions Not Adopted As Written

- Kimi's example of placing the network client/executor under
  `backend/borrow_tasks/` contradicts the same review's AST purity finding.
  Freeze both live modules under `backend/services/` and inject the executor
  through the existing service seam.
- Kimi's hard startup failure for missing credentials loses the unrelated
  snapshot/UI service while three reviews identify an equally fail-closed
  blocked mode. The blocked mode is preferred.
- Kimi's no-total-cap reconciliation loop conflicts with the draft's bounded
  design and produces indefinite traffic. Keep reconciliation finite.
- Treating sub-second cadence as something 429 will naturally regulate is not a
  correctness contract. At minimum, missed ticks must never be replayed; the
  configured-rate decision remains explicit and evidence-gated.
- A durable ledger row cannot by itself prove a request is currently in flight
  after a crash. Keep `in_flight_attempt_id` distinct from unresolved/orphan
  state.

## Questions For Opus 4.8 Round 2

1. Is a DB-path advisory process lock sufficient for single execution ownership,
   or should ownership live in SQLite with a boot token/lease? Freeze the exact
   failure and crash-recovery semantics.
2. Confirm or amend the 3/4 decisions on route names and blocked-on-missing-
   credentials startup.
3. Freeze `Retry-After` valid-value bounds and the 418 branch using only
   archived facts or an explicitly conservative fallback.
4. Decide the bounded reconciliation sequence after separating “safe GET may
   continue while globally stopped” from “shared rate-limit cooldown blocks all
   signed traffic.”
5. Decide whether Boundary C needs a verified quota-derived minimum interval;
   if yes, select one with headroom rather than exactly consuming the candidate
   limit.
6. Freeze the resolve matrix for `borrowing`, `paused`, and `deleted`, including
   Start when the count already meets the target.
7. Confirm the split between transient `in_flight_attempt_id` and durable
   `unresolved_attempt_id`.
8. Confirm that the 14 consolidated freezes are sufficient to amend
   `00-task.md`, `10-design.md`, and `11-adr.md` before the registered breakdown,
   and identify any item that is still unnecessary complexity.

The send-ready human-operated prompt is
`design-review-round-2.opus.prompt.md`. Core design files remain unchanged
until this adjudication returns, so disputed choices are not silently promoted
into stage requirements.

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/14-design-review-synthesis.md
本地北京时间: 2026-07-20 21:39:03 CST
下一步模型: human operator → Claude Opus 4.8
下一步任务: execute the prepared round-2 prompt in Opus 4.8 and archive its raw adjudication; no implementation dispatch
