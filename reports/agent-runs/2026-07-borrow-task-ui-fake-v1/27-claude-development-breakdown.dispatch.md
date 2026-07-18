# Development Breakdown Dispatch — Fake Borrow-Task v2

You are the development-breakdown author for a MEDIUM frontend-only fake UI amendment. Work read/write only in the stage evidence directory; do not modify application source, tests, backend, API contracts, schemas, fixtures, documents outside the stage evidence, credentials, or any external service.

Repository: `/Users/ark/Desktop/ai code/funding_hedging`

Read these raw artifacts before writing:

- `AGENTS.md`
- `agents/developer-discipline.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/00-intake.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/00-task.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/10-design.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/11-adr.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/13-scope-amendment-v2.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/30-review-1.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/status.json`

Write `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/12-development-breakdown.md`. It must define one Kimi-owned implementation task with:

- allowed and forbidden files;
- the task status model (`borrowing`, `paused`, `deleted`, `completed`), exact start/pause/delete transition and button-enable rules;
- soft deletion and filter semantics (全部 includes deleted);
- task-list edit input/validation/update rules;
- the completed-state limitation (no scheduler or UI simulation trigger);
- no-fetch/no-timer/no-persistence/non-backend boundaries;
- self-check cases, manual visual checks, risks, and review focus;
- treatment of the old review-1 ACCEPT as superseded by the user scope amendment.

Do not make up a backend contract, retry behavior, API endpoint, storage model, simulated-success button, or a fake HOME market row. Retain the two P3 notes from old review-1 as optional review inputs, not mandatory work unless your breakdown identifies a direct conflict.

Then update only this stage's `status.json` to record you as `breakdown_author` and append a session receipt with verified provider-native Session ID or explicit unavailable reason. Update `70-handoff.md` with the next action. Include the mandatory footer in the breakdown report.

当前 Session ID: unavailable (to be captured by Claude/operator after execution)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/27-claude-development-breakdown.dispatch.md
本地北京时间: 2026-07-18 21:40:44 CST
下一步模型: Claude
下一步任务: 输出 12-development-breakdown.md，供 Kimi 实现 fake UI v2
