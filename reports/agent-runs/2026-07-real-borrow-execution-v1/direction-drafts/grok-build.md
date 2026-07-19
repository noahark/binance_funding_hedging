# Grok Build Direction Draft — Real Borrow Execution v1

Independent panel lens: challenge the autonomous borrowing concept, surface
failure modes that UI-first work tends to miss, and freeze conservative
constraints before any private write path is designed.

Authority used for this draft: `AGENTS.md`; stage intake
`reports/agent-runs/2026-07-real-borrow-execution-v1/00-intake.md`; finished
fake stage intake
`reports/agent-runs/2026-07-borrow-task-ui-fake-v1/00-intake.md`;
`docs/product/PRD.md`; `docs/architecture/ARCHITECTURE.md`;
`backend/services/private_client.py` (GET-only HMAC whitelist);
`backend/services/snapshot_service.py` (serial background worker);
`frontend/index.html` borrow-task UI (in-memory, no timers, no network side
effects). This draft intentionally does **not** treat other direction drafts
as authority.

---

## Problem Statement

The accepted fake borrow-task UI
(`frontend/index.html`: statuses `borrowing|paused|deleted|completed`, fields
`asset`, `amountPerAttempt`, `successTarget` / `successCount`, fixed “every 30s”
copy, start/pause/delete/edit/filter) must become a system that can create
**real account debt** through a Binance private write API, with durable state,
controlled retries, and operator-visible audit.

The hard problem is not “wire the Confirm button to an endpoint.” The hard
problem is:

1. An unattended retry loop that creates liabilities is a product-class change
   relative to the approved PRD posture (“manual workstation, not an autonomous
   trading bot”; negative-funding notes that repeated borrow failure should
   **not** retry silently).
2. Exchange outcomes are often **ambiguous** after timeout / connection loss;
   blind retry can double-borrow.
3. The current private channel is **explicitly GET-only and deny-by-default**
   (`backend/services/private_client.py`). Any write path is a security and
   architecture break, not a feature toggle.
4. The fake UI’s “success progress” is display fiction: there is no scheduler,
   `successCount` does not advance from real attempts, and amounts are JS
   numbers—unsafe as authority for money.

Without a fail-closed definition of success, authorization, caps, and unknown
outcomes, connecting the existing UI to live borrow is an accident factory.

---

## Target User And Workflow

**User:** sole local operator of this funding-hedging workstation (macOS local
server / launchd path already exists for the read-only server).

**Intended safe workflow (recommended):**

1. Operator creates a **draft** borrow task from an allowlisted asset (initially
   expected: `HOME` only, per fake-stage product intent—**confirm**).
2. System shows maximum projected debt
   (`amount_per_attempt × success_target`, plus interest/risk disclaimer) and
   validation against `userMinBorrow` / precision / max-borrowable **as
   advisory**, never as sole authorization.
3. Operator performs an explicit **armed confirmation** that is distinct from
   “create task” and distinct from private **read** enablement.
4. Backend owns scheduling only while: process-level execution enablement is on,
   global kill switch is off, task desired state is `running`, and no attempt is
   in `outcome_unknown` / reconciliation.
5. Operator can pause, emergency-stop, or delete; UI always renders **server**
   state (progress, last outcome, next eligible time, blocked reason).
6. Task stops at success target, hard failure, cap breach, or human stop—never
   silent unbounded retry.

**Anti-workflow (reject):** browser timer or frontend “while borrowing” loop
calling a signed API; treating 2xx HTTP as final success; auto-resume of
unknown outcomes after restart; multi-task concurrent borrows against the same
asset without a frozen concurrency policy.

---

## Scope

### In scope for this milestone (after user freezes human gates)

1. **Backend-owned durable borrow task** with attempt ledger, versioned
   parameters, desired vs observed state, soft-delete that retains audit.
2. **Conservative authorization model:** default-off local execution enablement;
   per-task arming confirmation; global kill switch; allowlist + numeric caps.
3. **Exchange write adapter boundary** separate from the current GET-only
   private client (do not silently convert `PrivateClient` into a general write
   channel).
4. **Idempotency / unknown-outcome policy** with reconciliation against
   history/account evidence before any further borrow attempt.
5. **API + UI migration** so the fake task page becomes a client of backend
   task state; remove the “前端演示” authority while preserving layout/filters
   where possible.
6. **Deterministic test strategy** with fake/recording adapters only—no live
   account, no credentials in CI/Harness.

### Recommended phased delivery

| Phase | Live debt? | Deliverable |
| --- | --- | --- |
| **P0 — Zero write** | No | Task schema/API, persistence, state machine, fake exchange adapter, UI wired to backend, full restart/race/unknown-outcome tests |
| **P1 — Dry-run / discovery** | No | Capture official endpoint contract + raw samples under `reports/api-samples/<stage>/`; dry-run validates amounts/caps without POST borrow; document exact Binance path for chosen margin mode |
| **P2 — Live behind dual gates** | Yes, tiny | Verified write adapter; one-asset allowlist; tiny caps; process kill switch; reconciliation; operator runbook. Only after P0/P1 accept and explicit human live-enable approval |

Do **not** collapse P0–P2 into “connect UI to Binance.”

### Challenge to the autonomous concept (panel lens)

Autonomous interval retry is **acceptable only as a bounded debt-assembly
tool**, not as a trading bot:

- Prefer **manual single-attempt** first if the operator’s real need is
  occasional borrow before a manual hedge open.
- If automatic retry remains required (user already described interval + target
  success count), constrain it as:
  - max consecutive known failures → `blocked` requiring re-arm;
  - max wall-clock runtime;
  - max total attempts (not only successes);
  - single in-flight attempt per process (or per asset—**freeze**);
  - **no** auto-retry of `outcome_unknown`.

PRD tension must be resolved explicitly in synthesis: either amend the product
posture for “bounded autonomous borrow assembly,” or demote auto-retry to a
later stage and ship manual one-shot first.

---

## Non-goals

- Automatic hedge open/close, market orders, repay, transfer, withdraw, or
  multi-leg execution.
- Multi-user / remote multi-tenant service; public internet exposure of write
  APIs.
- Multi-exchange support; portfolio risk optimization; interest PnL accounting
  beyond audit fields needed for reconciliation.
- Hard-deleting audit history; treating soft-delete as erase.
- Fixing deferred P3 fake-UI issues (unsaved edit wipe on re-render; row a11y).
- Inventing Binance endpoint semantics without raw samples / official docs.
- Storing API keys, secrets, signatures, or full private payloads in repo,
  reports, frontend, or model prompts.
- Using the snapshot background worker as an ad-hoc place to fire borrows
  without a dedicated task engine and ledger.

---

## Domain Assumptions Requiring Confirmation

These are **human gates**, not implementer guesses:

1. **Margin / account mode:** PRD assumes Portfolio Margin; current enrichment
   mixes classic-margin market references (`/sapi/v1/margin/*`) with
   PM-ish reads (`/papi/v1/margin/maxBorrowable`, balances). Which exact borrow
   write endpoint and account surface is authoritative for this stage?
2. **Asset allowlist v1:** Is `HOME` the only live-allowed asset? Are other
   symbols create-able only as draft / blocked?
3. **Success definition:** Is a successful attempt (a) exchange-confirmed loan
   of approximately the requested amount in the intended account, evidenced by
   response identity **and** reconcilable history/balance change, or (b) any
   weaker proxy? (Recommend: only (a).)
4. **Idempotency reality:** If Binance borrow lacks a client-supplied
   idempotency key, accept that **reconciliation is the only duplicate
   defense** and unknown outcomes must pause the task.
5. **Retry semantics:** Confirm interval (fake shows 30s), max known failures,
   max total attempts, and whether partial fills / smaller-than-requested
   borrows count as success, partial, or failure.
6. **Authorization lifetime:** Does arming authorize one task until complete,
   a wall-clock session, or until process restart? Recommend: arming is
   per-task and does **not** survive process restart without re-arm **or** a
   clearly labeled durable “armed until complete” choice frozen by user.
7. **Credential scope:** Write-capable key separate from read-only key? Minimum
   permissions? Withdrawal must remain forbidden. Where are secrets injected
   (env / launchd, never browser)?
8. **Naked borrow risk:** Borrow without subsequent sell/hedge leaves inventory
   and interest risk. Is that explicitly accepted for this stage’s scope?
9. **Local-only binding:** Must write APIs bind only to localhost / same-origin
   local server, and remain disabled when execution flag is off even if read
   credentials exist?
10. **Concurrency:** One global borrow attempt at a time? One per asset? Parallel
    tasks allowed but serialized at the adapter?

---

## Recommendation — Safety Model (freeze before code)

### 1. What “real borrow task” means (user-visible)

A **real borrow task** is a backend-persisted job that may, only when fully
armed and enabled, request the exchange to increase borrowed balance for a
single asset by a fixed per-attempt quantity, up to a fixed number of
**confirmed** successes.

**Successful request (count toward `successCount`) only when all hold:**

- Local attempt row exists with unique `attempt_id` **before** dispatch.
- Exchange response (or reconciling history row) is linked to that attempt with
  non-secret identifiers (exchange loan/tran id if available, timestamps,
  amounts as **decimal strings**).
- Reconciliation does not show a conflicting unexplained extra borrow in the
  safety window.
- Persistence of the success transition commits; if commit fails after exchange
  success, state is `outcome_unknown` / `needs_reconcile`, **not** “retry
  another borrow.”

**Persist / audit minimum:**

- Task: id, asset, account/mode, amount_per_attempt, success_target,
  success_count, attempt_count, desired_state, observed_state, version,
  created_at, armed_at, last_error_class, next_eligible_at, terminal_reason.
- Attempt ledger: attempt_id, task_id, seq, requested_amount, dispatch_at,
  outcome (`accepted|rejected|outcome_unknown|reconciled_success|…`),
  exchange_ref (nullable), redacted error class, latency_ms.
- Never log secrets, signatures, full signed query strings, or raw credential
  material.

### 2. Authorization and confirmation

| Control | Recommendation |
| --- | --- |
| Default | Execution **off**. Read-only private channel enablement must **not** imply write enablement. |
| Process enablement | Explicit env/config flag e.g. `BORROW_EXECUTION_ENABLED=false` default; kill switch forces immediate no-dispatch. |
| Task create | Allowed as draft/paused; may validate amounts. |
| Task start/arm | Second step with UI summary of max debt, interval, caps; server rejects start if flags/caps fail. |
| Caps | Allowlist; per-attempt max; per-task max cumulative; global max concurrent runnable tasks; global max outstanding projected debt; max attempts; max consecutive failures. |
| Interval | Server-owned; floor + ceiling; not browser-trusted. |
| Pause | Desired state `paused`; no new dispatch after ack; in-flight attempt finishes to terminal attempt outcome. |
| Delete | Cancel schedule → wait/settle in-flight → soft-delete; ledger retained. |
| Edit | Versioned; apply only between attempts; reject if would breach caps or if task completed/deleted. |
| Race | Server is authority; optimistic version / If-Match; UI re-fetches. |

### 3. Correctness

- **One in-flight attempt per task** (and likely process-wide single borrow
  dispatch lock for v1).
- **Unknown outcomes fail closed:** timeout, TCP reset after send, unparseable
  body, 5xx after possible accept → `outcome_unknown` → pause dispatch →
  reconcile via history/balance endpoints (to be verified; interest-history
  paths already appear as discovery-only in whitelist notes).
- **Known reject** (business code: insufficient inventory, below min, etc.):
  may wait for next interval only if code is in an explicit retryable set;
  unknown codes → block.
- **Restart:** reload tasks; never re-dispatch an attempt still marked
  in-flight without reconciliation; durable next_eligible_at.
- **Decimals:** strings / Decimal end-to-end; abandon JS number authority from
  the fake UI.

### 4. Security / operations

- Keep HMAC signing in a **narrow write-capable adapter** with its own
  method+path whitelist (POST borrow + necessary GET recon only). Prefer not
  to weaken the existing GET-only client’s security story; either split
  modules or enforce method-level gates with separate enable flags.
- Local service only; no browser signing; frontend never sees secrets.
- Redacted structured audit; operator-visible last error classes.
- Crash recovery via ledger, not “resume whatever the browser thought.”
- Rate limits: respect exchange weights; local min interval; backoff on 429.
- Alerting v1: UI badges + server log for `blocked` / `outcome_unknown` /
  kill-switch; full external alerting can wait.
- Tests: fake clock, fake adapter, property/race tests for start/pause/delete,
  fingerprint-free fixtures; **zero** live credentials in tests.

### 5. API / frontend contract and rollout

- New task REST surface under backend ownership (paths TBD in design after
  synthesis approval)—**not** hidden inside
  `GET /api/public-market/snapshot`.
- Frontend: drop in-memory authoritative `state.borrowTasks` progression; poll
  or fetch task list; show `outcome_unknown` / `blocked` / `reconciling`
  distinctly from ordinary pause.
- Keep filter UX and card layout; replace “前端演示” disclaimer with live
  status/disclaimer driven by server (`execution_disabled`, `armed`, etc.).
- Rollout: ship P0 to main only after review; P2 live enable remains operator
  config off-by-default forever unless user changes policy.

### 6. Explicit alternatives considered

| Alternative | Verdict |
| --- | --- |
| A. Browser-owned timer + thin backend proxy | **Reject.** Unreliable, hard to audit, secrets risk, lost on refresh. |
| B. Manual one-shot borrow only (no auto-retry) | **Strong conservative default** if auto-retry is not frozen as mandatory. |
| C. Backend task engine + auto-retry with fail-closed unknown handling | **Recommended if** user insists on fake-UI semantics (interval + N successes). |
| D. Full negative-funding hedge bot (borrow+sell+futures) | **Out of scope**; much larger milestone. |

---

## Acceptance Criteria

Direction is only ready for design/implementation after user approval of
synthesis. Delivery acceptance (for later stages) should require:

1. No frontend path can sign or directly call Binance private APIs.
2. With execution enablement off, no code path can dispatch a borrow write
   (negative tests).
3. Task create/start/pause/delete/edit are server-authoritative, versioned, and
   leave an attempt/audit trail.
4. Unknown exchange outcomes never auto-retry a new borrow before
   reconciliation resolves the prior attempt.
5. Caps, allowlist, and kill switch are enforced server-side.
6. Restart recovers durable state without double-borrow under the tested race
   matrix.
7. UI shows server progress and distinct blocked/unknown states; fake-only
   success counters are gone when wired.
8. CI/Harness tests never create live debt or embed credentials.
9. Deferred P3 UI issues remain out of scope and do not block acceptance.
10. Live P2 remains off by default and requires explicit human enablement beyond
    code merge.

---

## Open Questions And Human Gates

**Must freeze before coding (and before stage branch per intake):**

1. Exact Binance account/margin mode + borrow write endpoint family (and recon
   GETs), grounded in official docs + later raw samples—not model memory.
2. Initial asset allowlist (`HOME` only?).
3. Whether v1 is **manual one-shot** or **bounded auto-retry**; if auto-retry,
   freeze interval, max attempts, max consecutive failures, max runtime.
4. Success/partial-success rules and decimal precision source of truth.
5. Dual enablement: process flag + per-task arming; restart re-arm policy.
6. Numeric caps (per attempt, per task, global) and concurrency.
7. Credential model (separate write key? permission checklist).
8. Accept naked-borrow risk without automatic sell/hedge.
9. Audit retention and where ledgers live (local sqlite/files—design choice
    after synthesis).
10. Whether PRD non-autonomy language is formally amended for this bounded
    borrow assembler.

**Hard bans for this stage of work (already in intake):**

- No implementation of live borrow, no simulated private write that pretends to
  hit Binance, no credentials in artifacts, no stage-branch delivery until
  synthesis is user-approved.

---

## Assumptions (panel member)

- Operator is single-user local; launchd may keep the process alive unattended—
  therefore kill switch and default-off execution matter more than in a
  click-driven script.
- Fake UI’s 30s interval and HOME focus are product signals, not contracts.
- Existing serial snapshot worker is a pattern for **process discipline**, not
  a place to bolt writes without a ledger.
- Codex and other panel drafts may converge on backend ownership; this draft’s
  distinctive claim is: **challenge autonomy first, force P0 zero-write, and
  treat unknown outcomes as the primary safety cliff.**

---

当前 Session ID: 019f778f-4efe-7ce0-ab37-483ed47b51c2
Session ID 来源: active_session_registry
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/direction-drafts/grok-build.md
本地北京时间: 2026-07-19 07:29:31 CST
下一步模型: human operator → Claude、Claude-GLM、Kimi（剩余 panel）；全部到齐后 Codex 综合
下一步任务: 保存其余独立方向草案；五份齐备后由 Codex 写 `06-direction-synthesis.md` 供用户审批
