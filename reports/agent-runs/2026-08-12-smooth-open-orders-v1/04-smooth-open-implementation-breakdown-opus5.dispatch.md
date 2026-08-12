Identity:
- task_id: smooth-open-implementation-breakdown-opus5
- target_role: Planner
- target_model: claude-opus-5
- provider: anthropic
- status_revision: 6
- required_skill: agents/skills/task-planner.md

Goal

Turn the Human-frozen smooth-open V1 design, the verified CCXT 4.5.64 public
proof, and the Bookkeeper's coarse development checklist into the smallest
safe implementation breakdown. The Human intends to use two GPT-5.6-sol
(reasoning high) terminals and one Claude-GLM terminal. Determine from the
actual code and file ownership whether all three tasks can genuinely run in
parallel; if not, prescribe the fastest honest dependency graph. Produce exact
worktree/file/task/acceptance boundaries and copy-ready draft startup texts for
later Human manual launch. This is planning only and grants no implementation,
dependency installation, service control, order, deployment, or live action.

Allowed Files

- docs/planning/smooth-open-orders-v1-development-checklist.md

Inputs

- AGENTS.md
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/04-smooth-open-implementation-breakdown-opus5.dispatch.md
- reports/agent-runs/ACTIVE.json
- PROJECT_STATE.md
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json
- agents/roles.md (Planner section)
- agents/skills/task-planner.md
- docs/planning/smooth-open-orders-v1.md
- docs/planning/smooth-open-orders-v1-development-checklist.md
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm.handoff.md
- docs/planning/ccxt-bookticker-recon-2026-08-13.md
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm-output.txt
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/01-advisory-design-reviews.md
- backend/domain/snapshot.py
- backend/hedge_open_tasks/domain.py
- backend/hedge_open_tasks/store.py
- backend/hedge_open_tasks/service.py
- backend/hedge_open_tasks/scheduler.py
- backend/app/server.py
- backend/tests/test_book_ticker.py
- backend/tests/test_hedge_domain.py
- backend/tests/test_hedge_store.py
- backend/tests/test_hedge_service.py
- backend/tests/test_hedge_api.py
- backend/tests/test_hedge_cycle_core.py
- frontend/index.html
- frontend/self-check.js

Acceptance Checks

- pass: preserve every Human-frozen product decision and explicitly separate it
  from implementation choices. Do not reopen watchOrderBook, threshold, 80%,
  five-minute fallback, current-gate-only fill-once, or immediate executor reuse
  without current contradictory evidence.
- pass: trace the real create/fill-once/read/worker/prepare-attempt/dispatch and
  shutdown call chains, name exact methods and current tests, and use that trace
  to decide whether the proposed three lanes are truly independently testable.
- pass: choose exactly one topology: three genuinely parallel tasks, or two
  parallel tasks followed by one dependent task. Explain concrete shared-file,
  contract, or test-fixture reasons; do not preserve three-way parallelism by
  adding adapters, compatibility shims, duplicate types, or speculative layers.
- pass: freeze the minimum cross-task contracts: public snapshot fields and
  Decimal/raw rules; subscribe/release/close behavior; generation invalidation;
  gate store operations and transaction boundary; worker consumption; create,
  fill-once, task and smooth-market read models. Every field has one owner.
- pass: produce three bounded task packets for exactly two `gpt-5.6-sol`
  reasoning-high implementers and one `claude-glm` implementer. Each names its
  goal, committed input dependency, unique Allowed Files, forbidden shared/core
  files, exact executable checks, failure stop, one local commit, and no push.
- pass: define an independent worktree/branch/stage arrangement that prevents
  the three terminals from sharing Git index, `ACTIVE.json`, `status.json`, or
  uncommitted files. State how the Bookkeeper fills final base/ledger SHAs only
  after formal plan review ACCEPT; do not create any worktree now.
- pass: assign `service.py`, `scheduler.py`, schema migration, dependency
  manifest, existing tests, and new test files to at most one implementation
  owner each. If a task depends on a not-yet-landed interface, make it dependent
  instead of asking it to compile against a guessed local duplicate.
- pass: turn every P0 evidence limit into a runnable P1 acceptance check:
  watcher exception/reconnect generation, delayed consumer isolation, shared
  symbol refcount, last-release cancel, multi-symbol behavior, close/join with
  zero CCXT-owned task, malformed/missing raw fields, normalized-float exclusion,
  spot local time, non-1/unknown contractSize, and 1000x fail-closed.
- pass: choose the repository's single runtime dependency manifest name and
  owner, pin `ccxt==4.5.64`, name installation and rollback boundaries, and
  explicitly prohibit planning-time or production-environment installation.
- pass: define the one-owner integration/cherry-pick order, conflict checks,
  exact fixed-base review range, full deterministic regression matrix, and the
  later frontend contract task. No branch may touch live executor order/query/
  settlement behavior except the final minimal service wiring needed to call
  the existing dispatch path.
- pass: include three copy-ready Human startup-text drafts, but mark them
  inactive until a later Bookkeeper replaces placeholders with committed
  worktree paths, branches, base SHA, status revision, and dispatch paths after
  formal plan review ACCEPT.
- pass: include a copy-ready cross-provider formal plan-review request covering
  parallel topology, units/precision, provider lifecycle, gate atomicity,
  natural/manual/timeout and 10/10 races, restart seams, immediate/close
  isolation, and evidence sufficiency. It must request an explicit ACCEPT or
  REWORK and must not review implementation that does not yet exist.
- pass: keep the plan at the smallest sufficient scope. Do not design private
  WebSocket, generic multi-exchange execution, full order books, dynamic
  thresholds, immediate-all, a second executor, or any unrequested framework.
- pass: modify only the one Allowed File and run `git diff --check`. Return the
  required `[TASK_RESULT v2]` in Chinese; do not commit, push, or change status.

Stop

Stop after completing the detailed checklist, three inactive startup-text
drafts, formal plan-review request, `git diff --check`, and Task Result. Do not
implement code, create worktrees/branches/stages, install dependencies, edit
status, commit, send another model, start/restart a service, read credentials,
connect WebSocket, call private/order/account/asset endpoints, deploy, merge, or
authorize live behavior.
