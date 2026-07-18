# Kimi Implementation Dispatch — Task F2 Borrow-Task UI v2

You are the implementation author for frontend Task F2. Work in `/Users/ark/Desktop/ai code/funding_hedging` on branch `stage/2026-07-borrow-task-ui-fake-v1`, beginning from the committed backend dependency `623d059b52723d9ee412519db054a2a25cedf504`.

Before editing, read the raw artifacts below and inspect the existing frontend implementation yourself:

- `AGENTS.md`
- `agents/developer-discipline.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/00-task.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/10-design.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/11-adr.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/12-development-breakdown.md` (§3 is authoritative task detail)
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/13-scope-amendment-v2.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/14-user-min-borrow-contract-amendment.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/21-implementation-backend.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/status.json`

You may change only:

- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/22-implementation-frontend-v2.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/62-test-output-frontend-v2.txt`

Do not modify backend/schema/sample/fixture files, `status.json`, `70-handoff.md`, canonical documentation, workflow/agent files, or files outside that list. Do not commit.

Implement precisely these UI-only requirements:

1. Every created task has `status` in `{borrowing, paused, deleted, completed}`. New tasks are `borrowing` / `借币中`. The list controls are exactly: 
   - borrowing: 启动 disabled, 暂停 enabled, 删除 enabled, edit confirmation enabled;
   - paused: 启动 enabled, 暂停 disabled, 删除 enabled, edit confirmation enabled;
   - completed: 启动/暂停 disabled, 删除 enabled, edit confirmation disabled/read-only;
   - deleted: all lifecycle and edit controls disabled/read-only.
2. `暂停` transitions borrowing → paused; `启动` transitions paused → borrowing. `删除` first applies the local stop semantics where applicable and then soft-deletes: set `deleted`, never remove the object. A completed task may also become deleted. These transitions never fetch, schedule work, modify progress, or claim a real borrow happened.
3. Add title-level working filters: 全部、借币中、已暂停、已删除、已完成. 全部 includes every task including soft-deleted items; counts and list membership derive only from the canonical in-memory `state.borrowTasks`. Completed is displayable/filterable but has no production UI action or fake scheduler that moves a task into it.
4. Each task list item has its own amount and success-target edit inputs plus confirmation. Pre-fill exact current values. A valid edit applies only to that task, retains `successCount`, and recalculates its displayed target total. Invalid values (amount must be finite >0; target must be integer >0) or readonly edits preserve state and show a nearby local error.
5. Consume the committed backend fields only in the market operation **amount input placeholder**, keeping that input's value empty:
   - raw `user_min_borrow` and `user_min_borrow_value_usdt` strings: `最小借币量 X (≈ Y USDT)`;
   - raw string with null/missing value: `最小借币量 X (≈ — USDT)`;
   - raw null/missing: `最小借币量 —`.
   Include the real raw-zero case `"0"` / `"0.00"`. Escape any API-derived text. Do not affect task-list edit inputs, user validation, task creation, or imply current availability.
6. Preserve all v1 behavior: 13-column table/empty `colspan=13`; generic `HOME` path without inventing a market row; operation controls do not open the row drawer; exactly two market inputs plus confirmation; no duplicate max-borrowable `已借完` label; sidebar/navigation and explicit frontend-demo disclaimer.
7. There must be no new `fetch`, private API call, borrow request, `setInterval`/timer retry, `localStorage`, persistence, simulated-success button, or non-UI backend behavior.

Extend `frontend/self-check.js` (after the existing coverage) to prove the full button matrix, pause/start round trip, soft deletion and deleted visibility, completed read-only/delete behavior (through a test-only helper/fixture only), all filter membership/counts, valid/invalid edits and progress preservation, all three placeholders including zero with an empty input value, unaffected task-list edit fields, event isolation, and no new fetch/timer/persistence behavior. Keep every existing self-check passing.

Run exactly:

```bash
node frontend/self-check.js
git diff --check
```

Put complete command output in `62-test-output-frontend-v2.txt`. Write `22-implementation-frontend-v2.md` with changed files, decisions, manual visual checks performed, tests and results, deviations/blockers if any, and the mandatory footer. Leave the worktree intact for the bookkeeper's evidence commit and the formal cross-review gates.

当前 Session ID: unavailable (to be recorded by Kimi/operator after execution)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/29-kimi-frontend-f2.dispatch.md
本地北京时间: 2026-07-18 22:35:55 CST
下一步模型: Kimi
下一步任务: 实现 Task F2、运行前端自检并留下原始报告与日志
