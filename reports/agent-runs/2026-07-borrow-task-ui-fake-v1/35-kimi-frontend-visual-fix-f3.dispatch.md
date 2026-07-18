# Kimi Implementation Dispatch — Task F3 Borrow-Task Action Visual Fix

You are the implementation author for the user-directed frontend acceptance fix in stage `2026-07-borrow-task-ui-fake-v1`. Work in `/Users/ark/Desktop/ai code/funding_hedging` on branch `stage/2026-07-borrow-task-ui-fake-v1`.

Read before editing:

- `AGENTS.md`
- `agents/developer-discipline.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/00-task.md` (Amendment v4)
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/12-development-breakdown.md` (§3)
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/13-scope-amendment-v2.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/22-implementation-frontend-v2.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/status.json`

You may change only:

- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/23-implementation-frontend-visual-fix.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/64-test-output-frontend-visual-fix.txt`

Do not modify backend/schema/sample/fixture files, `status.json`, `70-handoff.md`, canonical documentation, workflow/agent files, or files outside this list. Do not commit.

Implement only this visual acceptance fix:

1. Preserve the existing lifecycle semantics and ensure rendered state remains exact: for `borrowing`, 启动 has `disabled`; for `paused`, 暂停 has `disabled`. Disabled action buttons must be visibly greyed through an explicit disabled style, not only an implicit browser default.
2. Add clear, reusable action themes in the existing visual system: 启动 uses a green success theme when enabled, 暂停 a grey/neutral theme, 删除 a red danger theme. Disabled buttons override their enabled action colour with the greyed disabled presentation.
3. Do not change task transitions, button availability matrix beyond the two already-correct disabled rules, filters, task edits, placeholders, labels, no-fetch/no-timer/no-storage boundaries, or any backend behavior.
4. Extend `frontend/self-check.js` to prove the rendered classes/styles for green 启动, grey 暂停, red 删除, and the disabled start/pause states for borrowing/paused. Keep all existing checks passing.

Run exactly:

```bash
node frontend/self-check.js
git diff --check
```

Place complete command output in `64-test-output-frontend-visual-fix.txt`. Write `23-implementation-frontend-visual-fix.md` with changed files, rendered acceptance cases, tests/results, and deviations/blockers if any, followed by the mandatory footer. Leave the worktree intact for the bookkeeper's evidence commit and re-bound review gates.

当前 Session ID: unavailable (to be recorded by Kimi/operator after execution)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/35-kimi-frontend-visual-fix-f3.dispatch.md
本地北京时间: 2026-07-19 00:10:24 CST
下一步模型: Kimi
下一步任务: 实现 F3 操作按钮视觉验收修复并运行前端自检
