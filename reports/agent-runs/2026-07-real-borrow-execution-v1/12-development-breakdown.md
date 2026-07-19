# Development Breakdown — Durable Borrow Tasks A+B

Stage: `2026-07-real-borrow-execution-v1`
Author role: development-breakdown author (`task_planner` skill)
Provider/model: Anthropic Claude / claude-fable-5 (Fable5)

Scope authority: user-approved A+B only (`06-direction-synthesis.md` approved
2026-07-19; `00-task.md`; `10-design.md`; `11-adr.md`). Boundary C is a
separate future stage. This document is design decomposition only; it contains
no implementation, no dispatch execution, and no live-API claims.

Fact vs recommendation convention: statements sourced from the raw stage
artifacts are labeled `[fact]` where the distinction matters; everything under
"frozen contract" and "recommendation" headings is this author's breakdown
decision, made inside the approved design envelope and flagged where it
refines `10-design.md`.

Non-negotiable invariants restated (from the approved scope) `[fact]`:

- A+B sends zero Binance writes and zero authenticated live Binance requests.
- No signing client, credentials, live executor, `marginLoan`,
  `maxBorrowable` preflight/polling, load test, or product-defined scheduler
  minimum/cap may be added.
- The scheduler accepts every positive finite decimal interval (including
  `0.5`), normalizes to integer microseconds, and uses one durable global
  round-robin cursor.
- Ordinary runtime uses a no-network disabled executor; paper execution is
  test-only and deterministic.
- Public-market snapshot behavior and the GET-only role of `PrivateClient`
  stay intact.
- The browser is never the execution clock or task authority.
- Persist only sanitized attempt metadata; never raw private payloads, request
  headers, signatures, credentials, or secrets.

---

## 1. Decision and dependency graph

**Decision: the backend and frontend tasks are safely parallel** under
`docs/parallel-development-mode.md` (v0.4), provided the bookkeeper completes
the dispatch-ready work in §7 first.

Rationale against the three applicability conditions of that document:

1. **≥2 disjoint-scope tasks.** Task A owns `backend/**`,
   `schemas/api/borrow-tasks/**`, and `.gitignore`; Task B owns `frontend/**`
   only. No file is shared (`backend/app/server.py` is backend-only; the
   frontend has no build step and imports no schema file at runtime).
2. **Contract freezable at design time.** Everything the frontend consumes is
   frozen verbatim in §3 of this document: exact routes/methods, JSON document
   shapes, field semantics, statuses, result categories, error shape, cursor
   behavior, and decimal/time representations. There is no "B waits for A's
   output to learn the shape" dependency: Task B codes against §3 and mocks
   every response in `frontend/self-check.js`.
3. **Cross reviewers exist.** Implementer A is `claude_glm` → embedded/formal
   reviewer Kimi; implementer B is `kimi` → embedded/formal reviewer
   Claude-GLM (registry-derived, per parallel-mode v0.4).

`status.json` currently records `parallel_mode.enabled: false` `[fact]`. My
recommendation is to enable it for this stage; if the user or bookkeeper
prefers serial, the same two task boundaries run back-to-back (A then B) with
no other change to this breakdown, at roughly double wall-clock cost. The
harness memory records that the next dual-task stage is intended to trial
parallel-mode v0.4 (dispatch-ready gate + structured `r10_checklist`); this
stage is that dual-task stage.

**What the bookkeeper must validate at dispatch-ready** (before any
implementer starts):

- `status.json.parallel_mode.enabled = true`, with
  `r10_dispatch_tail_required = true` and
  `r4_diff_reconciliation_required = true`.
- Four dispatch files exist and are committed at H_intake:
  `task-A-claude-glm.prompt.md`, `task-B-kimi.prompt.md`,
  `embedded-review-A.prompt.md`, `embedded-review-B.prompt.md`
  (R9 packet structure, immutable PROMPT BODY, R10 tail with real paths).
- `status.json` carries `tasks[].r10_checklist` (or
  `r10_checklists.<task-id>`) for A and B with the v0.4 minimum fields,
  including the exact self-test commands from §5 and the escalation branch.
- Cross-review routing recorded: A→kimi, B→claude_glm; fresh read-only
  sessions; Grok not enabled; Codex not an implementer or fix author.
- `scripts/validate-stage.py 2026-07-real-borrow-execution-v1 --phase
  dispatch-ready` passes and its output is preserved in stage evidence.

Dependency graph:

```text
H_intake (this breakdown + 4 dispatch files + r10_checklists committed;
          dispatch-ready validator PASS)
   ├────────────── parallel ──────────────┐
Task A backend (claude_glm)        Task B frontend (kimi)
   │  self-tests (§5.1)                │  self-check (§5.2)
   │  embedded review by kimi          │  embedded review by claude_glm
   │  (≤2 local rounds, R3/R4)         │  (≤2 local rounds, R3/R4)
   └───────────────┬───────────────────┘
bookkeeper: R4 diff reconciliation → serial commits H_A, H_B
   → full regression (§5.3) → validate-stage pre-review
   → formal review-1-backend (kimi) ∥ review-1-frontend (claude_glm)
   → review-2 (strong-reviewer disclosure path, §6.4)
   → stage_accepted_waiting_user
```

The only cross-task consumption is the frozen §3 contract. Any change to §3
discovered mid-implementation is an R3 escalation to the bookkeeper (contract
change = no local fix, both tasks pause on the affected surface).

---

## 2. Task table

### Task A — backend durable borrow-task core

| Item | Value |
| --- | --- |
| Task id | `A` |
| Owner / provider | `claude_glm` (Zhipu GLM via Claude Code CLI), skill `senior_developer` |
| Purpose | Implement the isolated borrow-task module (domain, SQLite store, service, scheduler, executor port), the local same-origin task/log/settings HTTP APIs in the stdlib server, the borrow-task JSON schemas, and the backend test suite proving §5.1 scenarios — all with zero network I/O on any borrow path. |
| Allowed files | `backend/borrow_tasks/**` (new package: `__init__.py`, `domain.py`, `store.py`, `service.py`, `scheduler.py`, `executor.py`); `backend/app/server.py`; `backend/config.py`; `schemas/api/borrow-tasks/*.schema.json` (new); `backend/tests/test_borrow_*.py` (new); `backend/tests/borrow_paper_executor.py` (new); `backend/tests/conftest.py` (only if a shared fixture is strictly needed); `.gitignore` (add the SQLite data path only) |
| Forbidden files | `backend/services/private_client.py`; `backend/services/snapshot_service.py`; `backend/domain/**`; `backend/adapters/**`; `schemas/api/public-market/**`; `frontend/**`; `docs/**`; `workflows/**`; `agents/**`; `scripts/**`; `reports/**` except its own implementation report; `status.json`; `70-handoff.md`; any `.env`/credential/launchd file |
| Forbidden behavior | No `urllib`/socket/HTTP call in any `backend/borrow_tasks/**` code path; no new third-party dependency; no import of `borrow_tasks` from snapshot/private modules or vice versa; no change to existing route semantics, whitelist, or snapshot schema; no live-executor implementation; no git commit; no `status.json` write |
| Prerequisites | H_intake committed (this document + dispatch files); stage branch `stage/2026-07-real-borrow-execution-v1` checked out; dispatch-ready validator PASS |
| Deliverables | Working code within allowed files; implementation report `reports/agent-runs/2026-07-real-borrow-execution-v1/20-implementation-backend.md` (design decisions, tests run, R10 receipt block, embedded-review disposition); self-test raw output `reports/agent-runs/2026-07-real-borrow-execution-v1/60-test-output-backend.txt` |
| Acceptance criteria | Maps to `00-task.md` acceptance 1–5 and the backend half of 7: restart durability; A→B→C→A deterministic round-robin at a 3s setting on a fake clock; `0.5` accepted, stored as `500000` µs, effective gaps logged; at-most-one unresolved attempt per task with other tasks progressing; paper result categories update latest result + exactly one sanitized log row; completion stops later attempts; newest-first cursor pagination; deterministic 4xx JSON validation; all pre-existing backend tests still green; zero-network and no-credential-leak proofs pass; every borrow API response validates against its §3.2 schema file |
| Test/report output paths | `60-test-output-backend.txt` (tee of §5.1 commands); embedded review artifacts `embedded-review-A-round<N>.{diff.patch,dispatch.md,raw-output.md,fix-note.md}` in the stage directory |

### Task B — frontend migration to backend task authority

| Item | Value |
| --- | --- |
| Task id | `B` |
| Owner / provider | `kimi` (`kimi-code/kimi-for-coding`), skill `senior_developer` |
| Purpose | Migrate the borrow page from `state.borrowTasks` browser-memory authority to the frozen same-origin API; add the global interval editor and the `借币任务 | 借币日志` top-level tabs; render latest attempt results and newest-first paginated logs; extend `frontend/self-check.js` with fetch mocks and contract assertions. |
| Allowed files | `frontend/index.html`; `frontend/self-check.js` |
| Forbidden files | Everything else — in particular `backend/**`, `schemas/**`, `reports/**` except its own implementation report, `status.json`, `70-handoff.md` |
| Forbidden behavior | No browser timer that dispatches/simulates/signs/schedules borrow work (the existing snapshot auto-refresh timer stays; §3.8 bounds its reuse); no direct Binance URL; no localStorage task authority; no invented fields beyond §3; no git commit |
| Prerequisites | Same as Task A. Explicitly NOT dependent on Task A's code: all API interactions are mocked in self-check per §3. |
| Deliverables | Working UI within allowed files; implementation report `reports/agent-runs/2026-07-real-borrow-execution-v1/20-implementation-frontend.md` (same required blocks as Task A); self-check raw output `reports/agent-runs/2026-07-real-borrow-execution-v1/60-test-output-frontend.txt` |
| Acceptance criteria | Maps to `00-task.md` acceptance 6 and the frontend half of 7: task view keeps current filter/start/pause/delete/edit semantics over backend state (soft-deleted tasks visible under 全部/已删除); market-row confirm creates a task via `POST /api/borrow-tasks` and surfaces API errors locally; interval editor round-trips GET/PUT scheduler settings; log tab renders newest-first pages with load-more via `next_cursor`; every card shows the latest-result projection incl. 未知/执行未启用 states; `node frontend/self-check.js` green with the §5.2 assertions incl. fetch-URL allowlist proof |
| Test/report output paths | `60-test-output-frontend.txt`; embedded review artifacts `embedded-review-B-round<N>.*` in the stage directory |

Routing notes `[fact]`: `status.json.model_routing` records backend owner
`claude_glm`, frontend owner `kimi`, `core_work_exclusions: ["codex"]`,
`user_enabled_grok_code: false`. Codex/GPT receives no implementation or fix
ownership; Grok stays disabled. This table conforms.

---

## 3. Contracts frozen before coding

Everything in this section is frozen at H_intake. Implementers must not
extend, rename, or reinterpret it; a needed change is an R3 contract
escalation.

### 3.1 Route/method list (same-origin, 127.0.0.1 only)

```text
GET  /api/borrow-tasks                     → 200 task-list document
POST /api/borrow-tasks                     → 201 task document (create)
POST /api/borrow-tasks/{id}/start          → 200 task document
POST /api/borrow-tasks/{id}/pause          → 200 task document
POST /api/borrow-tasks/{id}/delete         → 200 task document
POST /api/borrow-tasks/{id}/edit           → 200 task document
GET  /api/borrow-logs?cursor=&limit=       → 200 log-page document
GET  /api/borrow-scheduler-settings        → 200 settings document
PUT  /api/borrow-scheduler-settings        → 200 settings document
```

`{id}` is the task UUID string. Any other method on these paths → 405. No
existing route changes. The server gains `do_POST`/`do_PUT` handlers that
dispatch ONLY these paths; unknown POST/PUT paths → 404 JSON
(`{"error":"not_found"}`), preserving GET static/snapshot behavior untouched.

### 3.2 Schema files (new, versioned, never reusing snapshot schema)

```text
schemas/api/borrow-tasks/task.schema.json                (single task document)
schemas/api/borrow-tasks/task-list.schema.json           (GET /api/borrow-tasks)
schemas/api/borrow-tasks/log-page.schema.json            (GET /api/borrow-logs)
schemas/api/borrow-tasks/scheduler-settings.schema.json  (GET/PUT settings)
schemas/api/borrow-tasks/error.schema.json               (all 4xx/5xx bodies)
```

Every 2xx response carries `"schema_version": "borrow-tasks/v1"` at the top
level. Backend HTTP tests must validate live handler output against these
files with `jsonschema` (already the repo's only runtime dependency).

### 3.3 Task document (minimum field semantics)

```json
{
  "schema_version": "borrow-tasks/v1",
  "id": "uuid4-string",
  "asset": "HOME",
  "amount_per_attempt": "12.5",
  "success_target": 3,
  "success_count": 1,
  "status": "borrowing",
  "version": 4,
  "unresolved_attempt_id": null,
  "latest_result": {
    "result_category": "execution_disabled",
    "business_code": null,
    "reason": "executor_disabled",
    "tran_id": null,
    "finished_at": "2026-07-19T08:00:00.123456Z"
  },
  "created_at": "2026-07-19T07:59:55.000000Z",
  "updated_at": "2026-07-19T08:00:00.123456Z"
}
```

- `status` ∈ `borrowing | paused | deleted | completed` — exactly the four
  user-facing states already in the UI `[fact: 10-design domain model]`.
  "Blocked on unknown outcome" is NOT a status: it is the derived condition
  `unresolved_attempt_id != null`, and such a task is scheduler-ineligible
  regardless of `status`.
- `version` is a monotonic integer bumped by every persisted mutation;
  `edit` requires it (optimistic concurrency), other mutations don't.
- `latest_result` is `null` until the first resolved attempt; it is a compact
  projection, never a log substitute.
- `amount_per_attempt`: decimal string matching `^[0-9]+(\.[0-9]+)?$`,
  value > 0, parsed with `decimal.Decimal`, stored and echoed verbatim
  (no float anywhere on the value path).
- Task list document: `{"schema_version":"borrow-tasks/v1","tasks":[…]}`,
  ordered by creation sequence ascending, **including** soft-deleted tasks
  (the UI's 全部 filter counts them `[fact: current UI semantics]`).

**Called-out decision (not left to the implementer): creation status.**
`POST /api/borrow-tasks` creates the task with `status: "borrowing"`. This
preserves the approved current UI semantics ("market-row confirm creates a
backend task", acceptance 6 keeps current lifecycle semantics `[fact:
00-task]`). The synthesis line "new tasks default to draft/paused before the
process gate" `[fact: 06-synthesis freeze #2]` is the Boundary-C live-arming
control; in A+B a `borrowing` task can never reach Binance because the only
runtime executor is `DisabledBorrowExecutor`. Reviewers should check this
interpretation explicitly rather than discover it.

### 3.4 Task statuses, transitions, and mutation bodies

```text
create : (new) → borrowing        body {"asset","amount_per_attempt","success_target"}
start  : paused → borrowing       body optional/ignored ({} allowed)
pause  : borrowing → paused       body optional/ignored
delete : borrowing|paused|completed → deleted   (soft; row retained)
edit   : borrowing|paused only    body {"amount_per_attempt","success_target","version"}
auto   : borrowing → completed    when success_count reaches success_target
```

- `asset` on create: non-empty string, uppercased A–Z0–9, taken from the
  market row's `base_asset` by the UI; the backend validates shape only (no
  allowlist in A+B — no product cap may be invented).
- `edit` keeps `success_count`; new `success_target` must be strictly greater
  than current `success_count`, else 400 `invalid_field` (a lower target would
  imply silent completion; the operator's tool for ending a task is delete).
- `edit` with stale `version` → 409 `version_conflict`.
- Illegal transition (e.g. start on `deleted`) → 409 `invalid_transition`.
- Unknown `{id}` → 404 `unknown_task`.
- All mutations return the full updated task document.

### 3.5 Scheduler settings document and interval rules

```json
{
  "schema_version": "borrow-tasks/v1",
  "interval_seconds": "0.5",
  "interval_us": 500000,
  "round_robin_cursor": "uuid-of-last-dispatched-task-or-null",
  "global_cooldown_until": null,
  "version": 2,
  "updated_at": "2026-07-19T08:00:00.000000Z"
}
```

- `PUT` body: `{"interval_seconds": "<decimal string>"}`. JSON **string**
  required; a JSON number is rejected 400 `invalid_interval` (decimal
  discipline — no float crosses the boundary). Accepted iff it matches
  `^[0-9]+(\.[0-9]+)?$`, is finite and > 0 under `Decimal`.
- Normalization: `interval_us = interval_seconds × 10^6`, which must be an
  exact integer ≥ 1; finer-than-microsecond values (e.g. `"0.0000001"`)
  → 400 `invalid_interval`. No upper bound, no product minimum `[fact:
  approved scope]`. Default seed row: `interval_seconds "5"` /
  `interval_us 5000000` `[fact]`.
- Interval changes take effect at the next tick computation; no restart
  needed.
- `global_cooldown_until`: null in ordinary A+B runtime; set only when an
  executor result carries `retry_after_seconds` (paper tests exercise this;
  the future C adapter is its real source `[fact: 10-design]`). While set and
  in the future, ticks dispatch nothing.

### 3.6 Attempt ledger entry and log page

Log page (`GET /api/borrow-logs`):

```json
{
  "schema_version": "borrow-tasks/v1",
  "entries": [
    {
      "id": 42,
      "task_id": "uuid4-string",
      "asset": "HOME",
      "sequence": 7,
      "outcome": "resolved",
      "result_category": "success",
      "business_code": null,
      "reason": null,
      "http_status": null,
      "tran_id": "paper-1",
      "requested_amount": "12.5",
      "scheduled_at": "2026-07-19T08:00:00.000000Z",
      "dispatched_at": "2026-07-19T08:00:00.001000Z",
      "finished_at": "2026-07-19T08:00:00.002000Z",
      "latency_ms": 1,
      "effective_gap_us": 500123
    }
  ],
  "next_cursor": "b64url-or-null"
}
```

- `id`: global monotonically increasing integer (SQLite
  `INTEGER PRIMARY KEY AUTOINCREMENT`); `sequence`: per-task attempt counter
  from 1. Attempt row is inserted (`outcome:"pending"`, result fields null,
  `finished_at` null) **before** executor invocation, then resolved in a
  second short transaction `[fact: write-ahead design]`.
- `outcome` ∈ `pending | resolved`. `result_category` (null while pending) ∈
  `success | known_rejection | rate_limited | unknown | execution_disabled` —
  the closed vocabulary from `10-design` `[fact]`; nothing else may cross the
  persistence/API boundary. `reason`/`business_code` are short sanitized
  strings from the executor's typed result; never headers, queries,
  signatures, credentials, or raw payload fragments.
- `effective_gap_us`: `dispatched_at(this) − dispatched_at(previous attempt
  globally)` in µs; null for the first attempt. This is the observable
  evidence that a requested `0.5` cadence did or did not hold `[fact: design
  requires requested vs actual to be distinguishable]`.
- **Ordering and cursor (called-out refinement of 10-design):** newest-first
  by `id DESC`. `10-design` says "descending by (finished_at, id)"; frozen
  here as `id DESC` because ids are assigned in scheduled order in an
  append-only ledger, and unresolved attempts (`finished_at` null) must appear
  in their true position instead of sorting to the end. Reviewers should
  treat this as a deliberate, disclosed deviation with equivalent intent.
- `cursor`: opaque `base64url(ascii(last_returned_id))`; response
  `next_cursor` is null when no older rows remain. Invalid/undecodable cursor
  → 400 `invalid_cursor`.
- `limit`: integer 1–200, default 50; out-of-range/non-integer → 400
  `invalid_limit`.
- The ledger is append-only: no update except pending→resolved, no delete;
  task soft-deletion never touches its attempts.

### 3.7 Error shape, HTTP validation, and body limits

All non-2xx borrow-API responses:

```json
{"error": "<code>", "detail": "<sanitized human-readable text>"}
```

Frozen `error` codes and statuses:

```text
400 invalid_json | invalid_field | invalid_interval | invalid_cursor | invalid_limit
404 unknown_task | not_found
405 method_not_allowed
409 invalid_transition | version_conflict
413 body_too_large            (request body cap: 16384 bytes)
503 borrow_service_unavailable (server built without a borrow service)
```

Malformed/absent JSON where a body is required, wrong content type, or
undecodable UTF-8 → `invalid_json`. Unknown/missing/mistyped fields →
`invalid_field` with the field name in `detail`. Deterministic: same input,
same body.

### 3.8 Scheduler, cursor, and eligibility semantics

- One dedicated scheduler thread inside `BorrowTaskService` (no coupling to
  the snapshot worker; neither module imports the other `[fact: design]`).
  Injectable clock pair: monotonic clock for tick spacing, wall clock for
  timestamps — tests drive both deterministically.
- Tick loop: next_due = last_tick + `interval_us` on the monotonic clock. On
  each due tick: if `global_cooldown_until` is future → no dispatch; else pick
  the first eligible task strictly after `round_robin_cursor` in stable
  creation order (internal integer creation seq, wrapping), advance the cursor
  transactionally **before** dispatch, insert the pending attempt, invoke the
  executor synchronously, resolve. A tick with no eligible task records
  nothing and does not move the cursor.
- Eligible = `status == "borrowing"` AND `unresolved_attempt_id` is null.
  `paused`/`deleted`/`completed` are never selected `[fact]`.
- Success resolution: increment `success_count`; if it reaches
  `success_target`, set `status = "completed"` in the same transaction.
  `known_rejection`/`execution_disabled` leave the task runnable.
  `rate_limited` sets `global_cooldown_until` from the executor's
  `retry_after_seconds` and leaves the task runnable. `unknown` leaves the
  attempt `pending`-equivalent? — No: `unknown` resolves the attempt row with
  category `unknown` but sets the task's `unresolved_attempt_id` to that
  attempt and keeps it set until a test-injected resolution clears it; the
  task is blocked from further selection `[fact: at-most-one-unresolved
  invariant]`. The service exposes a Python-level (not HTTP) test seam to
  clear an unresolved marker; A+B deliberately ships **no HTTP endpoint** to
  unblock, since reconciliation is Boundary C. Operator escape hatch in
  runtime: task delete.
- Restart recovery: on startup the store reloads tasks, settings, cursor, and
  unresolved markers as persisted. A `pending` attempt found at startup stays
  pending and its task stays blocked (fail-closed; no auto-resolution in A+B
  `[fact: design risk table]`).

### 3.9 Executor seam (the no-network port)

```python
class ExecutorResult:   # frozen dataclass fields
    result_category: str            # closed vocabulary of §3.6
    business_code: str | None
    reason: str | None
    http_status: int | None
    tran_id: str | None
    retry_after_seconds: Decimal | None

class BorrowExecutor(Protocol):
    def execute(self, task, attempt) -> ExecutorResult: ...
```

- `DisabledBorrowExecutor` (in `backend/borrow_tasks/executor.py`): returns
  `execution_disabled` / reason `"executor_disabled"` with zero I/O. This is
  the ONLY executor reachable from configuration.
- `PaperBorrowExecutor` lives in **`backend/tests/borrow_paper_executor.py`**
  (test tree, not the product package) so no runtime config can ever select
  it; tests inject it via the `BorrowTaskService` constructor. It replays a
  scripted deterministic result list covering every category.
- Config: `Config.borrow_executor: str = "disabled"` (env
  `APP_BORROW_EXECUTOR`); `from_env` raises `ValueError` for ANY other value
  — a "live" selection is rejected, not implemented `[fact: dispatch hard
  rule]`.
- New config fields (Task A, `backend/config.py`): `borrow_executor` as
  above; `borrow_db_path: Path = REPO_ROOT / "data/borrow-tasks.sqlite3"`
  (env `APP_BORROW_DB_PATH`; tests use `TemporaryDirectory`); `.gitignore`
  gains `data/`. No other knobs — in particular NO interval min/max/cap.
- Attempts in ordinary runtime: the scheduler runs and each dispatch of a
  `borrowing` task records one `execution_disabled` attempt row. This is
  deliberate (real-cadence observability with zero risk) but grows the local
  ledger without bound at fast intervals; §6 lists it as an accepted,
  user-visible risk — do NOT invent a retention cap in A+B.

### 3.10 Server wiring and time representation

- `build_server(config, service, borrow_service=None)`: third parameter added
  with default `None` so every existing test/callsite stays valid; when
  `None`, all §3.1 routes answer 503 `borrow_service_unavailable`. `run()`
  constructs `BorrowTaskService`, starts its scheduler after
  `service.start_worker()`, and stops it in the same `finally` cleanup.
- Handlers delegate to the injected service only — no SQL, no executor access
  in `server.py` `[fact: design]`.
- All API timestamps: UTC ISO-8601 with microsecond precision and `Z` suffix
  (`YYYY-MM-DDTHH:MM:SS.ffffffZ`). Internal storage: integer microseconds
  since epoch for `scheduled_at`/`dispatched_at`/`finished_at` (needed to make
  0.5 s gaps observable); task/settings `created_at`/`updated_at` same format.

### 3.11 Frontend contract bindings (Task B consumes only the above)

- Task truth = `GET /api/borrow-tasks`; `state.borrowTasks` becomes a render
  cache of the last response, never an authority. Numbers shown for progress
  come from backend fields verbatim; `amount_per_attempt` renders the decimal
  string as-is (no float re-parse for display math beyond the existing
  formatting helper).
- Refresh policy (bounded, frozen): refetch the task list (a) on entering the
  borrow view, (b) after every successful mutation (use the returned document
  to patch, then refetch), and (c) on the EXISTING snapshot auto-refresh tick
  only while the borrow-task view is active. No new timer; no polling of
  logs. Log page 1 loads on tab activation and on an explicit refresh action;
  older pages only via 加载更多 with `next_cursor`. The browser never
  schedules, simulates, or dispatches attempts `[fact: hard rule]`.
- Latest-result label map (frozen; UI is Chinese-first): `success` → `成功`,
  `known_rejection` → `已知拒绝`, `rate_limited` → `限频冷却`, `unknown` →
  `未知·待对账`, `execution_disabled` → `执行未启用`. A task with
  `unresolved_attempt_id != null` shows a blocking badge (`待对账·暂停调度`)
  and its start/pause buttons reflect that it will not be scheduled.
- The `前端演示/浏览器内存` disclaimers are replaced with truthful copy:
  tasks are backend-persisted; this stage performs no real borrowing
  (execution disabled). The static strategy line ("每 30 秒尝试一次") is
  replaced by the live global interval from the settings document.
- Interval editor at the top of the borrow page: shows
  `interval_seconds`, input accepts a decimal string, 确认 sends `PUT`;
  400 `invalid_interval` renders its `detail` locally.
- Tabs: within the existing borrow view, a top-level two-tab switch
  `借币任务 | 借币日志`; the existing status filters live inside the 借币任务
  tab only `[fact: 00-task]`.

---

## 4. Integration and ownership safety

- **`backend/app/server.py`** — Task A only. Task B never edits backend
  files, so the only historically shared integration point has a single
  writer this stage.
- **`backend/config.py` / `schemas/api/borrow-tasks/**` / backend tests** —
  Task A only. The public-market schema directory is forbidden to both tasks.
- **`frontend/index.html` / `frontend/self-check.js`** — Task B only. Task A
  never edits frontend files.
- **`.gitignore`** — Task A only (single line for `data/`).
- **Mocks-only frontend rule: yes.** Task B consumes stable API mocks built
  verbatim from §3's example documents inside `frontend/self-check.js`
  (the existing pattern already mocks `fetch` and records `fetchCallLog`
  `[fact]`). It does not read the schema files and does not depend on Task A
  landing first.
- **Binding to the real backend afterward, without scope creep:** both sides
  implement the same frozen text; Task A's HTTP tests validate real handler
  output against the §3.2 schema files, which pins the backend to the same
  shapes the frontend mocked. After H_A/H_B land, the bookkeeper runs a
  read-only integration smoke (start the server offline, exercise each §3.1
  route once with `curl`, validate each response against its schema file) and
  stores the transcript in the stage evidence. Any mismatch is a formal
  review finding, not a license for either implementer to renegotiate the
  contract.
- Single-writer discipline: neither implementer commits, touches
  `status.json`, or computes fingerprints; the bookkeeper performs R4 diff
  reconciliation against each task's last `embedded-review-*.diff.patch`
  before creating H_A and H_B serial commits `[fact: parallel-mode R4/R6]`.

---

## 5. Deterministic verification plan

### 5.1 Backend (Task A self-tests; bookkeeper re-runs identical commands)

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_borrow_domain.py \
  backend/tests/test_borrow_store.py \
  backend/tests/test_borrow_scheduler.py \
  backend/tests/test_borrow_executor.py \
  backend/tests/test_borrow_api.py \
  -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
git diff --check
```

Required scenario coverage (each is at least one named test):

1. **SQLite restart** — create tasks/settings/attempts in a
   `TemporaryDirectory` store, close, reopen: tasks, `interval_us`, cursor,
   soft-deleted rows, latest results, and unresolved markers survive
   (acceptance 1).
2. **Round-robin** — three eligible tasks A/B/C, interval `"3"`, fake clock:
   dispatch order A→B→C→A at 0/3/6/9 s; paused/deleted/completed/blocked
   tasks are skipped; cursor survives restart mid-cycle (acceptance 2).
3. **Fractional interval** — `PUT "0.5"` → stored `interval_us == 500000`;
   ticks on the fake clock produce attempts whose `effective_gap_us` records
   the actual gap; `"0.0000001"`, `"0"`, `"-1"`, `"abc"`, JSON number `0.5`
   all rejected `invalid_interval` (acceptance 2).
4. **Lifecycle / soft deletion** — full §3.4 transition matrix, positive and
   negative (409 paths), delete retains the row and its attempts; edit
   version conflict → 409.
5. **Unknown per-task block** — paper script yields `unknown` for task A:
   A's `unresolved_attempt_id` set, A never re-selected, B/C keep rotating;
   test-seam resolution unblocks A (acceptance 4).
6. **Known results / cooldown / completion** — each §3.6 category: exactly
   one ledger row per attempt, latest-result projection updates,
   `rate_limited` sets `global_cooldown_until` and suppresses dispatch until
   expiry, `success` with paper `tran_id` increments and completes at target,
   completed task never dispatched again (acceptance 5).
7. **Cursor pagination** — >2 pages of attempts: `id DESC` order, opaque
   cursor round-trip, `next_cursor` null at the end, `invalid_cursor` /
   `invalid_limit` 400s (acceptance 6, backend half).
8. **HTTP validation** — in-process server (existing pattern of
   `test_symbol_snapshot_endpoint.py`): every §3.7 error code reachable and
   deterministic; every 2xx validated against its §3.2 schema; existing
   snapshot/static routes unchanged (regression).
9. **Zero Binance / zero network / zero credential** — (a) grep-level test:
   no `urllib`, `http.client`, `socket`, `hmac`, `hashlib` import in
   `backend/borrow_tasks/**` (mirror of the private-client single-HMAC-exit
   test pattern `[fact]`); (b) runtime proof: monkeypatched
   `urllib.request.urlopen` that raises on any call while a full
   scheduler/executor/API scenario runs; (c) assert no attempt row or API
   body contains key/secret/signature-like content from a poisoned
   environment (acceptance 3 and 7).

### 5.2 Frontend (Task B self-test)

```bash
node frontend/self-check.js
git diff --check
```

Required added assertions (all against §3-shaped mock responses):

1. Tabs: `借币任务 | 借币日志` switch renders/hides the right containers;
   status filters exist only inside the task tab.
2. Task list renders from mocked `GET /api/borrow-tasks` (not from local
   creation state); 全部 count includes soft-deleted.
3. Create/start/pause/delete/edit each issue exactly the frozen route/method
   with the frozen body shape, and re-render from the mocked response;
   a mocked 409/400 renders its `detail` locally without state corruption.
4. Interval editor: renders mocked `"5"`, PUT `"0.5"` flows, mocked
   `invalid_interval` 400 shown locally.
5. Latest-result: all five categories render their frozen Chinese labels;
   `unresolved_attempt_id` shows the blocking badge.
6. Log paging: two mocked pages stitched via `next_cursor`, newest-first
   order preserved, 加载更多 hidden when `next_cursor` null.
7. No-leak proof: after the full run, `fetchCallLog` contains ONLY same-origin
   paths from §3.1 plus the pre-existing snapshot routes — no `binance`
   substring, no absolute foreign origin; no new `setInterval` registration
   beyond the pre-existing snapshot timer (acceptance 3 and 7, frontend
   half).

### 5.3 Stage-level regression (bookkeeper, before review gates)

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
node frontend/self-check.js
git diff --check
python3 scripts/validate-stage.py 2026-07-real-borrow-execution-v1 --phase pre-review
```

Outputs land in `60-test-output.txt` (canonical) with per-task raw logs in
`60-test-output-backend.txt` / `60-test-output-frontend.txt`.

---

## 6. Risks and review focus

### 6.1 Invariants reviewers must actively check

1. At-most-one unresolved attempt per task; unresolved ⇒ ineligible; the
   invariant holds across restart.
2. Cursor advance and attempt insertion are transactional and ordered
   (cursor moves before dispatch — crash cannot double-dispatch one turn).
3. No import edge in either direction between `backend/borrow_tasks/**` and
   `backend/services/**` / `backend/domain/**`; `PrivateClient` WHITELIST and
   GET-only surface byte-identical.
4. No network/signing primitives in the borrow package (grep + runtime
   proofs, §5.1-9); `PaperBorrowExecutor` unreachable from config;
   `APP_BORROW_EXECUTOR` rejects everything but `"disabled"`.
5. Decimal discipline end-to-end: no float parse of amounts/intervals in
   backend paths; JSON-number interval rejected.
6. Interval normalization exactness (µs), no invented min/cap anywhere.
7. Snapshot routes, schema, and `public-market-snapshot/v1` untouched
   (diff-level check).
8. Frontend has no execution clock: mutation/dispatch only ever originates
   from user action or the backend scheduler; self-check timer assertions
   not weakened.

### 6.2 Source hotspots for embedded cross-review and review-1

- `backend/borrow_tasks/scheduler.py`: tick arithmetic under fractional
  intervals; cooldown interaction; skip-vs-advance cursor behavior on
  no-eligible ticks; thread shutdown.
- `backend/borrow_tasks/store.py`: transaction boundaries under
  `ThreadingHTTPServer` concurrency (single connection + lock is the frozen
  concurrency answer); restart/init idempotence; append-only ledger
  enforcement.
- `backend/app/server.py` diff: new `do_POST`/`do_PUT` must not perturb GET
  static/snapshot dispatch; 503-when-unwired path.
- `frontend/index.html`: removal of the fake authority without leaving a
  second source of truth; error rendering does not lose backend state;
  soft-deleted rendering semantics preserved.
- `frontend/self-check.js`: mocks must copy §3 example documents verbatim —
  a hand-tweaked mock silently forks the contract.

### 6.3 Accepted/known risks (do not "fix" in-scope)

- Unbounded ledger growth in ordinary runtime (`execution_disabled` row per
  tick per eligible task; §3.9). User-approved behavior; retention is a
  future decision.
- A `pending` attempt orphaned by a crash blocks its task until deletion
  (fail-closed by design; reconciliation is Boundary C).
- Requested cadence may exceed achievable cadence; logs expose reality —
  reviewers should reject any claim that requested == achieved `[fact:
  ADR-003]`.
- The two user-deferred P3 fake-UI findings stay deferred `[fact]`.

### 6.4 Formal review structure (disclosure)

- Review-1: backend diff → Kimi; frontend diff → Claude-GLM (cross pool,
  fresh read-only sessions, committed `base_sha..head_sha` from
  `status.json`).
- Review-2: every decision-capable provider has design involvement this stage
  (Codex = designer/synthesizer; Claude/Fable5 = this breakdown), and
  implementers are claude_glm/kimi, so review-2 will require the
  strong-reviewer disclosure override of `AGENTS.md` — runner-level failure
  evidence for the preferred unrelated model, `reviewer_prior_involvement`
  in the verdict, and review against the user-approved synthesis + PRD as
  top authority. The bookkeeper should plan that evidence path now rather
  than discover it at the gate.
- Boundary C handoff risks to note in review narratives (not to widen A+B):
  the executor seam's category mapping is the future live-adapter contract;
  `retry_after_seconds` sourcing, `tran_id` reconciliation, idempotency under
  timeout, and marginLoan order-limit applicability remain UNVERIFIED
  `[fact: 03-recon Class D]` and must re-enter review with raw evidence in
  the C stage.

---

## 7. Recommended next workflow action

**Recommendation (not an implementation dispatch): run this stage in
parallel mode, after completing the remaining R9/R10 dispatch work.**

Exact remaining work, in order:

1. Prompt authoring (parallel-mode role: designer/breakdown/prompt author —
   Fable5 by default): write the four immutable dispatch files from this
   breakdown — `task-A-claude-glm.prompt.md`, `task-B-kimi.prompt.md`,
   `embedded-review-A.prompt.md` (reviewer kimi),
   `embedded-review-B.prompt.md` (reviewer claude_glm) — each with the R9
   receipt block and, for the task prompts, the R10 tail with the exact §5
   commands, exact `git diff` patch commands/paths, exact adapter commands
   from `agents/registry.yaml`/`docs/model-adapters.md`, and the
   PASS/BLOCKER/unavailable branches.
2. Bookkeeper: set `parallel_mode.enabled = true`, record
   `tasks[].r10_checklist` for A and B, record `breakdown_author`
   (= Anthropic Claude / claude-fable-5, with this file's session receipt)
   and the embedded/formal review routing in `status.json`; commit H_intake
   evidence on the stage branch.
3. Bookkeeper: run `scripts/validate-stage.py 2026-07-real-borrow-execution-v1
   --phase dispatch-ready`, preserve the output, and only then hand the two
   task prompts to the human operator for execution in the claude-glm and
   kimi terminals.

If the user prefers serial instead, dispatch Task A first, then Task B, with
unchanged boundaries and tests; no part of §§2–6 changes.

---

## Navigation footer

Per `AGENTS.md`. The provider-native Session ID is not exposed inside this
Claude Code runtime turn; the operator may backfill the verified ID into
`status.json.session_receipts` per
`docs/model-adapters.md#session-id-capture-and-execution-receipts`.

```text
当前 Session ID: unavailable (Claude Code runtime does not expose the provider-native session ID to the model; operator may backfill from CLI evidence)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/12-development-breakdown.md
本地北京时间: 2026-07-19 16:10:24 CST
下一步模型: Fable5（并行模式四份 dispatch 文件预写）或 bookkeeper（若用户选择串行路线）
下一步任务: 按 §7 完成 R9/R10 dispatch 预写与 r10_checklist 记账，过 dispatch-ready 门后由人工操作员派发双实现任务
```
