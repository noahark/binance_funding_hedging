<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status:        pending
target_model:  claude_glm / glm-5.2
adapter_cmd:   claude-glm --model glm-5.2 -p "$(cat reports/agent-runs/2026-07-real-borrow-execution-v1/task-A-embedded-review-round1-fix.dispatch.md)"
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       pending
next_dispatch: executor: self — embedded-review-A.prompt.md round 2 after all fixes and tests pass
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable，设计期定稿后不得修改） ===== -->

# Task A — Scope-Contained Repair After Embedded Review Round 1

You are the original Task A backend implementer, Claude-GLM (`glm-5.2`). This
is one permitted local repair round under R3/R4. Read the raw reviewer evidence
first; do not rely on this summary alone:

- `AGENTS.md`, `docs/parallel-development-mode.md` R3/R4/R10
- `task-A-claude-glm.prompt.md` (original frozen scope and prohibitions)
- `embedded-review-A-round1.raw-output.md`
- `embedded-review-A-round1.diff.patch`
- the changed Task A files and tests.

Do not edit any file outside Task A’s original allowed scope. Do not change a
schema/contract, frontend code, `status.json`, `70-handoff.md`, Harness files,
or commit. This is A+B only: no Binance request, signing, credential, live
executor, `maxBorrowable`, or frequency limit.

## Required Fixes

All four findings are scope-contained and mandatory:

1. **Fail closed across restart.** Do not clear a persisted
   `unresolved_attempt_id` that represents a resolved `unknown` outcome when
   reopening SQLite. Startup recovery may add a marker for an orphaned pending
   attempt, but must preserve an existing marker. Add a regression proving an
   unknown outcome remains scheduler-ineligible after close/reopen until the
   test seam resolves it.
2. **Unsupported methods.** Every unsupported HTTP method on every borrow API
   path returns the frozen `405 method_not_allowed` JSON body, not stdlib 501
   HTML. Cover at least DELETE and PATCH in an in-process API test.
3. **Reject unexpected JSON fields.** Create, edit and scheduler-settings
   mutation bodies must reject unknown keys deterministically as 400
   `invalid_field`, with the field named in `detail`; do not silently ignore
   them. Add tests.
4. **Apply the 16384-byte cap everywhere.** Body-optional task mutations must
   enforce the same body cap and return 413 JSON; add a pause (or equivalent)
   oversized-body test.

Re-run the original exact Task A tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_borrow_domain.py backend/tests/test_borrow_store.py backend/tests/test_borrow_scheduler.py backend/tests/test_borrow_executor.py backend/tests/test_borrow_api.py -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
git diff --check
```

Append or replace the Task A command capture at
`60-test-output-backend.txt`. Write the required round explanation at
`embedded-review-A-round1.fix-note.md`: each finding, exact files changed,
tests proving it, and confirmation no contract/scope expansion occurred.

## R10 Round 2 Tail

Regenerate the full Task A reviewer snapshot, including the untracked new
backend files, at:

```bash
git diff --binary -- backend/borrow_tasks backend/app/server.py backend/config.py schemas/api/borrow-tasks backend/tests .gitignore > reports/agent-runs/2026-07-real-borrow-execution-v1/embedded-review-A-round2.diff.patch
```

The human operator must launch a **fresh Kimi read-only** session using the
immutable `embedded-review-A.prompt.md` body and preserve its raw output as
`embedded-review-A-round2.raw-output.md`. Record that invocation in
`embedded-review-A-round2.dispatch.md`, including a provider-native Session ID
or an explicit unavailable reason. If the result is PASS, stop for the
bookkeeper. If a scope-contained issue remains, do not begin a third local
round: escalate to the bookkeeper because R4 permits at most two rounds. A
contract/schema/cross-task issue is immediately R3 escalation.

当前 Session ID: unavailable (target Claude-GLM session is created by operator)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/task-A-embedded-review-round1-fix.dispatch.md
本地北京时间: 2026-07-19 18:49:41 CST
下一步模型: Claude-GLM
下一步任务: 修复 Task A round-1 四项范围内 finding，完成测试、fix note 与 Kimi round-2 预审
