# Design Review Raw Output — Boundary C Real Borrowing (Kimi)

## Capture metadata

| Field | Value |
| --- | --- |
| Stage | `2026-07-real-borrow-boundary-c-v1` |
| Role | independent read-only design review (not formal Review-1/Review-2) |
| Prompt | `design-review.prompt.md` |
| Model name | **Kimi for Coding** (`kimi-code/kimi-for-coding`) |
| Provider | Moonshot AI (月之暗面) |
| Adapter / runtime | Kimi Code CLI (interactive session) |
| Provider-native Session ID | unavailable (Kimi CLI interactive runtime does not expose a provider-native session ID to the model; operator may record a verified ID in `status.json.session_receipts`) |
| Session ID source | unavailable |
| Executor | human_operator (operator dispatched the prepared prompt into this Kimi session) |
| Captured at (local) | 2026-07-20 21:28:54 CST |
| Product code edited | no |
| Live Binance / credentials | none |

This file is the stage-local raw capture of the design-review response returned
verbatim by the Kimi session. It is the third independent design review archived
for this stage, alongside `13-design-review.md` (Anthropic / Claude Opus 4.8)
and `design-review.raw-output.md` (xAI / Grok 4.5). Bookkeeper reconciliation
into `status.json` / `70-handoff.md` and the canonical
`12-development-breakdown.md` remain subsequent bookkeeper steps.

## Read Set Actually Consulted

Read in this session before writing the review:

- `AGENTS.md` (session bootstrap, roles, hard gates)
- `reports/agent-runs/ACTIVE.json`
- This stage: `design-review.prompt.md`, `00-intake.md`, `00-task.md`,
  `10-design.md`, `11-adr.md`, `12-development-breakdown.draft.md`
- Prior stage (named in the prompt): `06-direction-synthesis.md`,
  `03-grok-borrow-api-capacity-recon.md`, and
  `13-user-decisions-and-contract-amendment.md` (linked from `11-adr.md`)
- `workflows/templates/stage-delivery.yaml` (stage-design and
  development-breakdown sections only)
- `docs/parallel-development-mode.md` (v0.5 R11-R12 only)
- Current source: `backend/borrow_tasks/{domain,executor,scheduler,service,store}.py`,
  `backend/services/private_client.py`, `backend/config.py`,
  `backend/app/server.py`, `schemas/api/borrow-tasks/{task,scheduler-settings}.schema.json`,
  `frontend/index.html` (borrow sections), `frontend/self-check.js` (timer/fetch
  guard proofs), `backend/tests/test_private_client.py` (grep-level guards),
  `backend/tests/test_borrow_executor.py` (AST no-network proof),
  `backend/tests/test_borrow_api.py` (schema-validation harness header),
  `backend/tests/borrow_paper_executor.py`, `backend/tests/fixtures/` listing

No other stages or `history/` directories were read recursively. No product or
stage files were edited during the review itself.

---

# Design Review — Boundary C Real Borrowing (`2026-07-real-borrow-boundary-c-v1`)

## Verdict: REWORK

No re-architecture is needed: the ADRs are sound, the fail-closed posture is right, and the lean serial route is correct. But six P1 gaps must be amended into `00-task.md` / `10-design.md` / `11-adr.md` and the registered `12-development-breakdown.md` before implementation dispatch. All amendments are in-place wording/mechanism freezes, not new components.

## Blocking findings

**F1 (P1, Q1/Q4) — Pending-attempt eligibility window: "pending ⇒ ineligible" is true only after restart, never in-process.**
`insert_pending_attempt` writes the attempt row and advances the cursor but does NOT set `unresolved_attempt_id` (`backend/borrow_tasks/store.py:326-375`); eligibility filters `unresolved_attempt_id IS NULL` (`store.py:225-234`); the marker appears only on `unknown` resolution (`store.py:457-462`) or at startup orphan recovery (`store.py:165-171`). AC6 requires the scheduler to survive executor exceptions; once that containment exists, a failure of `resolve_attempt` itself (transient SQLite error) leaves a dispatched, possibly-accepted attempt with the task still eligible — the next tick sends a second borrow POST after an ambiguous first one. This is exactly the duplicate-debt class the stage exists to prevent. Freeze: transaction 1 atomically sets `unresolved_attempt_id` at pending insert; resolution clears it for `success`/`known_rejection`/`rate_limited` and retains it for `unknown`. Startup recovery then becomes a special case of one invariant instead of a second mechanism.

**F2 (P1, Q5) — Global-stop vs dispatch is not atomic; a POST can go out after a durable Stop.**
`_dispatch_one` reads settings, selects, then inserts in separate steps (`backend/borrow_tasks/service.py:277-300`). A Stop landing between the eligibility check and `insert_pending_attempt` is followed by a real POST — violating the intent of AC9 even though the window is microseconds. Freeze: the execution-switch check and pending insertion happen in ONE store transaction (atomic check-and-insert serialized by the store lock). Also freeze: `execution_enabled` defaults to `false` on fresh databases AND on migrated databases (fail closed; the operator explicitly starts it).

**F3 (P1, Q3/Q9) — Four existing static guards are incompatible with the planned modules, and no document freezes their amendments.**
- `test_single_hmac_exit_in_product_code` (`backend/tests/test_private_client.py:77-87`) forbids `hmac`/`hashlib`/`signature=` outside `private_client.py` → the new `binance_signing.py` violates it.
- `test_urlopen_only_in_designated_http_clients` (`test_private_client.py:90-102`) permits `urlopen` only in `private_client.py`/`binance_public.py` → the new borrow transport module violates it, and its exact module name is never frozen (`00-task.md` allows `backend/borrow_tasks/**` and `backend/services/binance_signing.py` only).
- `test_no_network_or_signing_imports_in_borrow_package` (`backend/tests/test_borrow_executor.py:82-111`) AST-scans all of `backend/borrow_tasks/**` for `urllib/http/socket/hmac/hashlib/ssl/requests` → any live module placed there violates it.
- The frontend self-check "zero new task timer" proof (`frontend/self-check.js:3012-3015`) whitelists only 60000ms/1000ms timers → the designed 2s borrow-view poller violates it.
Without frozen module names and exact amended allow-lists, "deterministic no-network tests complete" is internally inconsistent with the file boundaries. The registered breakdown must name each live module and each guard's new exact whitelist (everything else stays forbidden).

**F4 (P1, Q4) — The `known_rejection` rule is not implementable as written.**
D5's "explicit exchange/business rejection proving no loan" does not say which codes prove no loan or what an unlisted 4xx becomes. An implementer must choose between hot-retrying auth/clock errors (-2014/-2015/-1021) every interval and blocking legitimate pool-empty retries. Freeze before code: `known_rejection` ONLY for an evidence-enumerated business-code set (initial candidates from archived docs/samples, e.g. the 51061 pool-exhaustion class — same discipline as `BORROW_ZERO_BUSINESS_CODES` in `backend/services/private_client.py:94`); every other 4xx → `unknown` (blocked, visible, operator-acted); HTTP 400 with code `-1003` → `rate_limited` alongside 429/418 (confirm representation against archived papi docs); valid `tranId` = non-empty string per the archived response schema (integer IDs stringified).

**F5 (P1, Q2) — Migration mechanism underspecified.**
D7/AC8 state intent but not mechanism. The current store has no migration framework (`store.py:26-74` runs CREATE-IF-NOT-EXISTS plus orphan recovery on every open). Freeze: (a) version marker mechanism (recommend `PRAGMA user_version`; 0 = pre-C); (b) idempotence — the quarantine runs exactly once per version upgrade and never re-pauses a legacy task the operator already re-authorized via Start; (c) the exact eligibility predicate `status='borrowing' AND unresolved_attempt_id IS NULL AND live_authorized=1`; (d) `live_authorized INTEGER NOT NULL DEFAULT 0` so the column fails closed; (e) Start atomically sets `live_authorized=1` (idempotent for post-C tasks). With (a)–(e) the AC8 property "old tasks cannot execute merely because the process changed to live mode" holds.

**F6 (P1, Q7) — Per-task blocked/reconciling state and rate-limit cooldown are invisible in the minimal frontend scope.**
D9/AC12 add only a global execution badge. A task blocked on an `unknown` outcome still renders as plain `borrowing` (status vocabulary unchanged), yet the accepted synthesis freeze requires visibly distinguishing unknown-outcome reconciliation and rate-limit cooldown — and supervised first-live operation depends on seeing "this task is blocked" without reading raw logs. Freeze: (a) task-list rendering surfaces blocked/reconciling state derived from `unresolved_attempt_id` + `latest_result`; (b) the execution-status projection exposes `global_cooldown_until` (nullable ISO string).

**F7 (P2, Q5) — Resolve-time status transition rule not frozen.**
AC10/D8 fix deleted-terminal, but allowed auto-transitions are unstated; current code auto-completes from any non-terminal status (`store.py:431-456`). Freeze: auto-completion permitted from `borrowing` and `paused`; `deleted` is never overwritten; in-flight results on deleted tasks still persist to the ledger.

**F8 (P2, Q1/Q5) — Exception containment points unnamed.**
AC6 states the outcome but not where containment lives. Freeze: containment wraps `executor.execute` inside `_dispatch_one` (resolve `unknown`), AND the scheduler loop gets its own guard — `BorrowScheduler._loop` (`backend/borrow_tasks/scheduler.py:64-71`) currently lets any store-level exception kill the thread silently.

**F9 (P2, Q7) — `in_flight_attempt_id` derivation.**
Freeze that the status projection derives in-flight state from the durable ledger (pending attempt rows), not from executor/service memory — correct across restarts and never false after a crash.

## Non-blocking findings

- **N1 (P3, Q6):** When reconciliation resolves a success, persist the matched record id into the attempt's `tran_id` and mark `reason` (e.g. `reconciled_unique_txid_match`) so audit distinguishes response-proven from history-inferred success.
- **N2 (P3, Q1):** Add to Risks: serial dispatch is per-process; the product assumes exactly one server process per SQLite file. The port bind currently makes a second default instance fail before scheduler start — effective but accidental.
- **N3 (P3, Q7):** Tasks created while `mode=disabled` become immediately live-runnable once both gates open (a consequence of Confirm-is-authorization). State this in the UI copy/badge so it never surprises.
- **N4 (P3):** Freeze a module-level borrow POST timeout constant (suggest 10s, test-overridable, not env-configurable) instead of silently reusing the 15s snapshot `request_timeout`.
- **N5 (P3):** One Risks sentence: sub-second intervals are exchange-throttled by design (weight 100/POST vs 6000/min ⇒ 429 + Retry-After becomes the effective cadence), so the interval input is not read as a product promise.
- **N6 (P3, Q8):** No proposed component is unnecessary. Signer module, separate client, durable switch, status projection, migration marker, reconciliation, and the three small frontend additions each map to a frozen acceptance criterion; the design already rejected caps, preflight, draft/arm lifecycle, async workers, and a general write client.

## Open-item decisions

1. **Routes and schema.** Unify under one prefix: `GET /api/borrow-execution/status`, `POST /api/borrow-execution/start`, `POST /api/borrow-execution/stop` (single prefix matches the existing prefix-dispatch style in `_is_borrow_path`, `backend/app/server.py:47-55`; avoids the mixed `borrow-execution-status` + `borrow-execution/*` shape). Status body: `{schema_version: "borrow-execution/v1", mode, execution_enabled, can_execute, block_reason, in_flight_attempt_id, global_cooldown_until, updated_at}`. `can_execute = (mode=="live") && execution_enabled && credentials_present` (cooldown reported separately, not folded into `can_execute`). Start/stop return 200 + the same status projection; errors use the existing `{error, detail}` envelope. New schema file `schemas/api/borrow-tasks/execution-status.schema.json`.
2. **Credentials and startup.** Confirm `BINANCE_BORROW_API_KEY` / `BINANCE_BORROW_API_SECRET` and `APP_BORROW_EXECUTOR=disabled|live`. Decision: **fail startup** (`ValueError` at config load, before any socket bind) when `live` is selected and either credential is missing/empty — consistent with the existing unknown-value behavior and louder than a silent blocked badge for an operator who is present at startup. `disabled` with credentials present starts normally (credentials ignored, never logged). All new env names covered by startup redaction tests; `.env.example` carries placeholders only.
3. **Retry-After fallback.** Freeze 60s when the header is missing, unparseable, or non-positive (429 and 418 alike); honor valid values clamped to [1, 3600] seconds; cooldown is global and durable via the existing settings row. Rationale: weight-100 POSTs make hot retries quota-expensive; 60s ≫ the 5s default interval; bounded.
4. **Reconciliation timing.** No separate thread and no new API: one reconciliation read per service tick for the oldest unresolved attempt, gated by live mode, global cooldown, and per-task spacing — first read ≥3s after the attempt became unresolved, then backoff 5s→15s→60s capped at 60s, no total attempt cap (weight-10 reads ≈ +10 weight/min/task steady state, negligible vs 6000). Match: by `txId` when a `tranId` is known; otherwise a unique record in `[dispatched_at − 60s, now]` with exact asset + exact amount, requiring record timestamp ≥ `dispatched_at − 5s` skew tolerance if the archived contract provides per-record timestamps (if it does not, record the evidence gap and rely on txId/asset/amount uniqueness alone). Unique match resolves success (persist matched id as `tran_id`); zero or multiple matches keep the task blocked; absence is never reinterpreted as failure. Constants adjustable within [3s, 300s] by the registered breakdown against the archived official evidence.
5. **Restart policy.** Adopt the draft: normal restart resumes post-C live-authorized tasks (durable automation; the A+B amendment already rejected per-restart re-arm); orphaned pending attempts block and enter reconciliation before any new dispatch of that task. The pre-C quarantine is a one-time migration event, not a restart policy. No re-arm-on-restart.

## Required amendments

1. `00-task.md` AC3/AC6 + `10-design.md` D4/D6 → write the F1 insert-time unresolved-marking invariant.
2. `00-task.md` AC9 + `10-design.md` D2 → write the F2 atomic check-and-insert rule and `execution_enabled=false` defaults.
3. `10-design.md` D2 → replace route names with `/api/borrow-execution/{status,start,stop}`; add `global_cooldown_until` to the status body.
4. `10-design.md` D5 + `12-development-breakdown.draft.md` "Result contract" → write the F4 enumerated-rejection/unlisted-4xx/`-1003`/`tranId` rules.
5. `10-design.md` D7 + `11-adr.md` ADR-006 → write the F5 migration mechanism, idempotence, predicate, column default, Start semantics.
6. `10-design.md` D9 + `00-task.md` scope/AC12 → add per-task blocked/reconciling rendering and cooldown visibility (F6).
7. `10-design.md` D8 → write the F7 transition rule.
8. `12-development-breakdown.draft.md` → freeze exact live module names (one choice, e.g. `backend/borrow_tasks/live_executor.py` + `backend/borrow_tasks/pm_borrow_client.py`), the four exact guard amendments (F3), containment points (F8), ledger-derived in-flight projection (F9), the five open-item decisions above, and "construct the pre-C schema in-test via raw SQL, no binary fixture".
9. `10-design.md` Risks → add the single-process assumption and exchange-throttled sub-second note (N2/N5).

## Lean implementation assessment

The one-serial-task, no-parallel route is **appropriate**. The slice has a single natural owner (backend-dominant with light frontend wiring, matching the AGENTS.md routing rule that dispatches the whole bounded task to Claude-GLM), no separable second workload that would benefit from parallel tasks, and deterministic no-network tests that need no cross-task contract negotiation. Embedded review off is consistent with serial delivery; committed-state review-1 (fresh Kimi, cross-provider from Claude-GLM) plus an eligible review-2 remains the real gate. If Codex performs review-2, its stage-design/bookkeeper involvement must go through the documented strong-reviewer disclosure (it applies to design involvement only, never to implementation authorship, which Codex is correctly excluded from).

## Evidence gaps

Official exchange facts that must be archived under `reports/api-samples/2026-07-real-borrow-boundary-c-v1/` before parameter/weight/response assumptions freeze:

1. `POST /papi/v1/marginLoan` doc archive: security type, request weight (100 IP), full parameter list and encoding for a signed POST (query vs body), response JSON shape and `tranId` type, per-endpoint error table, timestamp/recvWindow semantics.
2. `GET /papi/v1/margin/marginLoan` doc archive: required/optional params (`asset`, `txId`, time-window params, `limit`), weight (10), per-record fields (`txId`, asset, principal/amount, timestamp), and the documented `txId == tranId` correspondence.
3. 429/418 and `Retry-After` header semantics on papi (header name, seconds semantics), and whether `-1003` surfaces as a 400 body code or as 429 on papi.
4. Whether `marginLoan` counts against the 1200/min PM order limit (recon Class D unknown).
5. Idempotency: confirmation that no client-supplied idempotency key exists (the design assumes none; this must be evidence, not absence of memory).
6. Borrow rejection business-code candidates (pool-exhaustion 51061 class, under-minimum, over-limit) from the official error list or archived raw 4xx samples — this feeds the F4 enumerated set.
7. Per-asset minimum amount / precision rules for `marginLoan`, if documented, and their violation rejection code.

---

当前 Session ID: unavailable (Kimi CLI 交互会话，运行时未向模型暴露 provider-native Session ID；可由 operator 核验后记入 status.json.session_receipts)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/design-review.raw-output-kimi.md
本地北京时间: 2026-07-20 21:28:54 CST
下一步模型: registered breakdown author (Claude provider, Fable5 first), human-operator dispatched
下一步任务: bookkeeper reconcile this third review into stage state; breakdown author applies the required amendments and produces the canonical 12-development-breakdown.md
