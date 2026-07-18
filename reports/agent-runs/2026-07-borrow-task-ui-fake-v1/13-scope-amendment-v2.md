# Scope Amendment v2 — Fake Borrow-Task Controls And Filters

## User-Approved Addition

Keep this stage frontend-only and fake, then add to the borrow-task view:

1. Every task has **启动**, **暂停**, and **删除** controls. A task created from the market view starts in `borrowing` / “借币中”; 启动 is disabled and 暂停 is enabled. 暂停 switches it to `paused` / “已暂停”; 暂停 is disabled and 启动 is enabled. 删除 must first stop the fake task and then soft-delete it.
2. The borrow-task list adds its own operation controls: amount, total successful-borrow target, and confirmation. They modify that task in browser memory only.
3. The borrow-task title area filters tasks by 全部, 借币中, 已暂停, 已删除, 已完成.

## Frozen Interpretation For The Fake

- **Deletion is soft deletion.** The task remains in memory with `status: deleted`, is visible in 全部/已删除, and has all state and edit controls disabled. This is required for an 已删除 filter to have meaningful content.
- **No real scheduler exists.** `borrowing` only describes fake UI state; it never calls an API, starts a timer, or changes success progress automatically.
- **Completion has no new UI trigger.** The status model and filter include `completed`, but a newly created fake task has `successCount: 0` and does not become complete automatically. The 已完成 view is initially empty; real or explicit simulated progress is deferred.
- **Edits are allowed for borrowing and paused tasks** and update `amountPerAttempt`, `successTarget`, and rendered total while retaining `successCount`. Deleted and completed tasks are read-only. Invalid edits display a local error and preserve existing values.
- **Completed tasks are not restartable or pausable.** Deletion remains available and changes a completed task to deleted, consistent with the requested delete action.

## Review Consequence

`30-review-1.md` ACCEPT reviewed only `d9c2772..edb2002` and is superseded as a formal gate by this user-approved scope amendment. Its two P3 findings remain review input:

- Pending inputs in the market table can be reset by a 60-second table re-render.
- Focusable controls are nested inside a row with `role="button"`.

Neither P3 is required to be fixed by this amendment; the new review must decide whether the expanded task view changes their severity.

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/13-scope-amendment-v2.md
本地北京时间: 2026-07-18 21:40:44 CST
下一步模型: Claude
下一步任务: 输出 MEDIUM 阶段的开发细化，供 Kimi 实现
