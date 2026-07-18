# Kimi Implementation Dispatch — frontend-borrow-task-fake

You are the implementation author for a bounded frontend-only task. Work in `/Users/ark/Desktop/ai code/funding_hedging` on branch `stage/2026-07-borrow-task-ui-fake-v1`.

Read these raw artifacts before editing:

- `AGENTS.md`
- `agents/developer-discipline.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/00-task.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/10-design.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/11-adr.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/status.json`

Implement the task exactly within these allowed source files:

- `frontend/index.html`
- `frontend/self-check.js`

Do not modify `backend/**`, `schemas/**`, `docs/**`, `workflows/**`, `agents/**`, fixtures, API contracts, or the stage intake/design/ADR/dispatch packet.

Required behavior:

1. Add `操作` as the 13th header, immediately to the right of `借贷状态 / 资产`. Every data row must have 13 cells; every table empty/error state must use `colspan="13"`.
2. Each operation cell has exactly two editable inputs: per-attempt borrow amount and successful-borrow target count, plus a confirmation button. Make labels/accessibility clear. Inputs and the confirmation button must not open the row detail drawer.
3. Validate amount as finite numeric > 0 and count as an integer > 0. Invalid input shows a nearby error and creates no task.
4. Valid confirmation creates an in-memory-only fake task using that row's `base_asset`; do not use `fetch`, no private API, no backend code, no persistent storage, and no `setInterval`/automatic retry loop for borrow tasks.
5. Add a second sidebar item immediately after `费率行情`: `借币任务`, with the task count. It switches to a borrow-task view; fee-rate navigation restores the market view.
6. Borrow-task view has empty and populated states. A populated task clearly shows asset, per-attempt amount, success `0 / target`, total target amount, `每 30 秒尝试一次`, and a strong disclaimer that it is a frontend demo and has not sent a real borrow request. It must support `HOME` through generic `base_asset`; never fabricate a `HOMEUSDT` market row.
7. In `maxBorrowableSubline`, remove the separate `已借完` badge/text. Retain `可借 0(已借完)` in the existing negative-funding status badge.
8. Extend `frontend/self-check.js`. It must prove the 13-column layout, no duplicate `已借完` in the max-borrowable subline, validation, fake task creation with a memory-only `HOME` row (1000 and 10), task display values, navigation state, and no borrow `fetch`/retry timer behavior. Keep existing coverage passing.

Run exactly:

```bash
node frontend/self-check.js
git diff --check
```

Do not commit. Capture the complete raw implementation response in `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/20-implementation.md`, including changed files, design decisions, the exact test commands/results, any deviation, and the mandatory footer. Update `status.json`, `70-handoff.md`, and `60-test-output.txt` as required by `AGENTS.md`; record a verified session receipt or explicit unavailable reason. Leave the worktree intact for the bookkeeper's review-gate commit.

当前 Session ID: unavailable (to be recorded by Kimi/operator after execution)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/15-kimi-implementation.dispatch.md
本地北京时间: 2026-07-18 18:26:49 CST
下一步模型: Kimi
下一步任务: 实现并自检 frontend-borrow-task-fake
