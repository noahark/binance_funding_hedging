<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status:        pending
target_model:  claude_glm / glm-5.2
adapter_cmd:   claude-glm --model glm-5.2 -p "$(cat reports/agent-runs/2026-07-real-borrow-execution-v1/task-A-claude-glm.prompt.md)"
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       pending
next_dispatch: executor: self — embedded-review-A.prompt.md after Task A self-tests pass
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable，设计期定稿后不得修改） ===== -->

# Task A — Backend Durable Borrow-Task Core (A+B Only)

You are the backend implementer, Claude-GLM (`glm-5.2`), using the
`senior_developer` skill. Implement this bounded task only. Read in full before
editing:

- `AGENTS.md` and `agents/developer-discipline.md`
- `reports/agent-runs/2026-07-real-borrow-execution-v1/00-task.md`
- `10-design.md`, `11-adr.md`, `12-development-breakdown.md`, and
  `13-user-decisions-and-contract-amendment.md`
- `docs/parallel-development-mode.md` (R1–R10)
- relevant existing backend source and tests.

## Scope And Ownership

Allowed files only:

- `backend/borrow_tasks/**` (new package)
- `backend/app/server.py`
- `backend/config.py`
- `schemas/api/borrow-tasks/*.schema.json` (new)
- `backend/tests/test_borrow_*.py` (new)
- `backend/tests/borrow_paper_executor.py` (new)
- `backend/tests/conftest.py` only if a shared fixture is essential
- `.gitignore` only for the SQLite data path
- your own implementation evidence:
  `reports/agent-runs/2026-07-real-borrow-execution-v1/20-implementation-backend.md`
  and `60-test-output-backend.txt`, plus the R10 artifacts named below.

Everything else is forbidden, especially `frontend/**`, snapshot/private
client modules, public-market schemas, `status.json`, `70-handoff.md`,
workflow/Harness files, credentials, and git commits.

## Frozen Product/Contract Requirements

- This is A+B: zero Binance writes, zero authenticated Binance reads, zero
  signing/credential/live-executor code, zero `maxBorrowable` path, and no
  product interval floor or cap.
- Implement the isolated SQLite-backed task service, task/attempt ledger,
  decimal microsecond global round-robin scheduler, local API routes and JSON
  schemas exactly as frozen by `12-development-breakdown.md` §3, as amended by
  `13-user-decisions-and-contract-amendment.md`.
- `POST /api/borrow-tasks` creates `borrowing` immediately. This means the
  **backend** scheduler can select it immediately; no frontend Start click is
  needed. In normal A+B runtime, the only selectable executor is
  `DisabledBorrowExecutor`, which produces a persisted, sanitized
  `execution_disabled` result with no I/O.
- `PaperBorrowExecutor` is test-only and constructor-injected; configuration
  accepts only `disabled` and rejects every other executor selection.
- Preserve short store transactions: persist the attempt before executor
  invocation, but never hold a SQLite transaction or store lock while invoking
  it. A+B synchronous disabled execution is not a commitment to a synchronous
  future-C live adapter.
- `GET /api/borrow-logs` uses newest-completed-first ordering:
  `COALESCE(finished_at, dispatched_at, scheduled_at) DESC, id DESC`; its
  opaque cursor carries the full timestamp/id boundary.
- Existing snapshot endpoints, `PrivateClient` GET-only behavior and
  public-market schema remain unchanged. No third-party dependency.

Implement all frozen local routes, schemas and error shapes. Keep decimal
amounts/intervals as strings at the HTTP boundary and `Decimal`/integer
microseconds internally. Tasks must survive restart, soft delete, expose latest
sanitized result, prevent a second unresolved attempt for the same task and
round-robin eligible tasks A→B→C→A. Unknown outcome blocks only its task;
known rejection and execution-disabled remain runnable; paper rate limit uses
the typed retry-after cooldown; paper success with tranId increments and can
complete a task.

## Required Tests And Evidence

Add deterministic tests for all backend acceptance cases in the task/design:
restart, fractional interval, lifecycle/edit version conflict, unknown block,
cooldown, completion, newest-first cursor pagination, HTTP errors/schema
validation, existing-route regression, and no-network/no-secret proof.

Run exactly:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_borrow_domain.py backend/tests/test_borrow_store.py backend/tests/test_borrow_scheduler.py backend/tests/test_borrow_executor.py backend/tests/test_borrow_api.py -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
git diff --check
```

Capture command output in
`reports/agent-runs/2026-07-real-borrow-execution-v1/60-test-output-backend.txt`.
Write `20-implementation-backend.md` with changed files, contract decisions,
test output summary, known limitations, and the R10 disposition. Do not edit
the shared stage state or commit.

## R10 Mandatory Completion Tail

After implementation and the commands above pass, generate the exact review
snapshot (do not include Task B’s frontend files):

```bash
git diff --binary -- backend/borrow_tasks backend/app/server.py backend/config.py schemas/api/borrow-tasks backend/tests .gitignore > reports/agent-runs/2026-07-real-borrow-execution-v1/embedded-review-A-round1.diff.patch
```

Use the immutable prewritten embedded-review prompt at
`reports/agent-runs/2026-07-real-borrow-execution-v1/embedded-review-A.prompt.md`.
The human operator must run the following fresh Kimi review command and retain
the unedited raw output at the stated path:

```bash
kimi --model kimi-code/kimi-for-coding -p "$(cat reports/agent-runs/2026-07-real-borrow-execution-v1/embedded-review-A.prompt.md)" | tee reports/agent-runs/2026-07-real-borrow-execution-v1/embedded-review-A-round1.raw-output.md
```

The Kimi reviewer sees the patch above and returns PASS or BLOCKER. If PASS,
finish your implementation report and stop for the bookkeeper; do not commit.
If it finds a scope-contained issue, fix only your allowed files, write
`embedded-review-A-round1.fix-note.md`, regenerate the patch, and repeat only
one more round using `embedded-review-A-round2.dispatch.md`. If it identifies a
contract/schema/cross-task/shared-surface issue, do not fix locally: write an
escalated `embedded-review-A-round1.dispatch.md` naming the issue and stop for
the bookkeeper. If the review command cannot run, record its failure class
(`model_unavailable`, `adapter_missing`, `command_error`, `permission_error`,
`timeout`, `invalid_pre_review_output`, or `scope_or_contract_dispute`) in that
same dispatch artifact. Never report only “waiting for review”.

当前 Session ID: unavailable (target Claude-GLM session is created by operator)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/task-A-claude-glm.prompt.md
本地北京时间: 2026-07-19 16:30:21 CST
下一步模型: Claude-GLM
下一步任务: 在允许的后端范围内实现 A+B 持久化借币任务核心，并触发预写 Kimi 嵌入预审
