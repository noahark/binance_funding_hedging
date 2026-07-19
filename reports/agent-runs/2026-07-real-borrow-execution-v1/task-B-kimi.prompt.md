<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status:        pending
target_model:  kimi / kimi-code/kimi-for-coding
adapter_cmd:   kimi --model kimi-code/kimi-for-coding -p "$(cat reports/agent-runs/2026-07-real-borrow-execution-v1/task-B-kimi.prompt.md)"
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       pending
next_dispatch: executor: self — embedded-review-B.prompt.md after Task B self-check passes
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable，设计期定稿后不得修改） ===== -->

# Task B — Frontend Backend-Authority Migration (A+B Only)

You are the frontend implementer, Kimi (`kimi-code/kimi-for-coding`), using the
`senior_developer` skill. Implement this bounded task only. Read in full before
editing:

- `AGENTS.md` and `agents/developer-discipline.md`
- `reports/agent-runs/2026-07-real-borrow-execution-v1/00-task.md`
- `10-design.md`, `11-adr.md`, `12-development-breakdown.md`, and
  `13-user-decisions-and-contract-amendment.md`
- `docs/parallel-development-mode.md` (R1–R10)
- the existing `frontend/index.html` and `frontend/self-check.js`.

## Scope And Ownership

Allowed files only:

- `frontend/index.html`
- `frontend/self-check.js`
- your own implementation evidence:
  `reports/agent-runs/2026-07-real-borrow-execution-v1/20-implementation-frontend.md`
  and `60-test-output-frontend.txt`, plus the R10 artifacts named below.

Everything else is forbidden: no backend/schema edits, no `status.json` or
`70-handoff.md`, no task dispatch edits, no credential files, and no git
commit.

## Frozen UI/API Requirements

- The frontend is an API client only. Backend SQLite state is authoritative;
  `state.borrowTasks` may be a render cache but never task authority.
- Market-row confirmation sends `POST /api/borrow-tasks` and the resulting task
  is already `borrowing`: it is immediately eligible for the **backend**
  scheduler, with no navigation or second Start click. Display the returned
  server state.
- Use only the same-origin routes and JSON fields frozen in
  `12-development-breakdown.md` §3 plus
  `13-user-decisions-and-contract-amendment.md`. Do not invent API fields or
  client-side task outcomes.
- Add global interval GET/PUT editor, accepting the user-entered decimal string
  and rendering local API errors. There is no browser borrowing timer,
  simulator, signer, Binance URL, or localStorage task authority.
- Add top-level `借币任务 | 借币日志` tabs. Keep status filters inside the task
  tab. Log tab loads newest-first pages and supports `next_cursor` load-more.
- Every task card shows backend latest result and appropriately labels
  `execution_disabled` as `执行未启用`; it must not claim a real borrow occurred.
  Show the unknown/unresolved blocking state and all four existing lifecycle
  statuses. Preserve the accepted start/pause/delete visual semantics.
- Replace old fake/browser-memory disclaimers with truthful persisted-task,
  execution-disabled A+B wording. Existing snapshot refresh may remain, but it
  must never become a task execution clock.

Mock the frozen API contract in `frontend/self-check.js`; Task B is parallel
with Task A and must not wait for backend source. Cover create/start/pause/
delete/edit, API errors, interval update, filters, latest categories,
unknown-block badge, task/log tabs, cursor paging, and an allowlist proving no
foreign/Binance fetch and no new task timer.

## Required Tests And Evidence

Run exactly:

```bash
node frontend/self-check.js
git diff --check
```

Capture output in
`reports/agent-runs/2026-07-real-borrow-execution-v1/60-test-output-frontend.txt`.
Write `20-implementation-frontend.md` with changed files, API/mock contract,
test summary, known limitations, and R10 disposition. Do not edit shared stage
state or commit.

## R10 Mandatory Completion Tail

After the commands above pass, generate the exact reviewer snapshot:

```bash
git diff --binary -- frontend/index.html frontend/self-check.js > reports/agent-runs/2026-07-real-borrow-execution-v1/embedded-review-B-round1.diff.patch
```

Use the immutable prompt at
`reports/agent-runs/2026-07-real-borrow-execution-v1/embedded-review-B.prompt.md`.
The human operator must run the following fresh Claude-GLM read-only review
command and retain the unedited raw output at the stated path:

```bash
claude-glm --model glm-5.2 --permission-mode plan -p "$(cat reports/agent-runs/2026-07-real-borrow-execution-v1/embedded-review-B.prompt.md)" | tee reports/agent-runs/2026-07-real-borrow-execution-v1/embedded-review-B-round1.raw-output.md
```

If the reviewer returns PASS, finish your implementation report and stop for
the bookkeeper; do not commit. If it identifies a scope-contained issue, fix
only your two allowed files, write `embedded-review-B-round1.fix-note.md`,
regenerate the patch, and repeat only one more round using
`embedded-review-B-round2.dispatch.md`. A contract/schema/cross-task issue is
R3: write an escalated `embedded-review-B-round1.dispatch.md` and stop for the
bookkeeper. If the review command cannot run, record its failure class
(`model_unavailable`, `adapter_missing`, `command_error`, `permission_error`,
`timeout`, `invalid_pre_review_output`, or `scope_or_contract_dispute`) in that
dispatch artifact. Never report only “waiting for review”.

当前 Session ID: unavailable (target Kimi session is created by operator)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/task-B-kimi.prompt.md
本地北京时间: 2026-07-19 16:30:21 CST
下一步模型: Kimi
下一步任务: 在允许的前端范围内完成 API 接入、任务/日志界面与自检，并触发预写 Claude-GLM 嵌入预审
