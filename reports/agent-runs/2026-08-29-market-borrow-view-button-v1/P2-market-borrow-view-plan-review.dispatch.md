# P2 — Market borrow view button plan review

Identity:
- task_id: `P2-market-borrow-view-plan-review`
- target_role: `Reviewer` (pre-implementation plan review)
- target_model: `opus5`
- provider: `anthropic`
- target_window: `claude`
- status_revision: `2`
- required_skill: `agents/skills/software-architect.md`

Goal:
- Perform one fresh, independent, read-only pre-implementation review of the fixed plan for adding the Market Table "查看借币" button.
- Decide whether the plan is the smallest sufficient change and is executable against the current frontend seams without ambiguity.
- Verify the exact visibility predicate, deterministic 1-to-N selection, cache-to-market projection, task-tab/filter synchronization, safe DOM lookup, smooth scroll, transient focus behavior, explicit click/keydown event isolation, and self-check coverage.
- Return an explicit `ACCEPT（接受）` or `REWORK（返工）`; do not implement, edit the plan, prepare implementation code, or act as the next workflow model.

Fixed Review Target:
- Plan artifact: `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/market-borrow-view.plan.md`
- Expected SHA-256: `eeea31bff46dac3b65b6ecdff4d8a4aef7f29d79cc51bd90570a8bd7e9f69ab4`
- Repository baseline: `7bb70a74e4e97a5c0b136bc6146167a360f0debb`
- Before review, verify both values exactly. A mismatch is non-accepting and must be reported; do not review a moving substitute.

Allowed Files:
- Create only: `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P2-market-borrow-view-plan-review.handoff.md`.
- Bookkeeper preflight recorded by the preparing Planner: `test ! -e reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P2-market-borrow-view-plan-review.handoff.md` returned success on 2026-08-29.
- Read-only otherwise. Do not modify `market-borrow-view.plan.md`, `frontend/index.html`, `frontend/self-check.js`, any existing evidence, `status.json`, `PROJECT_STATE.md`, dispatch packets, source, tests, schema, database, configuration, or git history.

Inputs (read in startup order, then only these task materials):
- `AGENTS.md`
- this dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/status.json`
- `agents/roles.md` — Reviewer section and Task Handoff Evidence Contract section
- `agents/skills/software-architect.md`
- `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P1-market-borrow-view-plan.handoff.md`
- `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/market-borrow-view.plan.md`
- `frontend/index.html` — only the CSS for borrow controls/cards and the current `state.borrowTasks`, `renderBorrowOpCell`, `attachRowHandlers`, `loadBorrowTasks`, `mutateBorrowTask`, `setBorrowTab`, `setBorrowTaskFilter`, `renderBorrowTasks`, `renderBorrowTaskCard`, `setActiveView`, `renderTable`, `captureMarketOpInputs`, and `restoreMarketOpInputs` seams
- `frontend/self-check.js` — only the mock DOM, task fixtures, operation-cell assertions, borrow navigation/filter tests, and helper seams needed to judge the proposed checks

Current Verified Facts:
- P1 author/provider: `gpt-5.6-sol` / `openai`; P2 reviewer `opus5` / `anthropic` is cross-provider and did not author the plan.
- `state.borrowTasks` is an in-memory rendering cache populated from the existing same-origin task-list API; this feature must not add a backend contract or external call.
- `setActiveView('borrow-tasks')` resets the task filter to `borrowing`, renders cache synchronously, and starts asynchronous refreshes; `borrowTab` can still be `logs` from prior use.
- `renderBorrowTasks()` rebuilds `.borrow-task-card[data-task-id]`; `sortTasksNewestFirst()` already defines created-time then ID descending order.
- Market-table redraw already preserves operation inputs through `captureMarketOpInputs()` / `restoreMarketOpInputs()`.
- P1 is planning only. There is no implementation delivery SHA to review, and this task must not invent one.

Review Questions / Acceptance Checks:
- `pass`: The plan's button predicate is exactly `task.asset === row.base_asset && (task.status === 'borrowing' || task.status === 'paused')`; `completed`, `deleted`, unknown status, other assets, and an empty list cannot render the button.
- `pass`: The DOM and CSS plan puts the conditional button immediately to the right of the existing Confirm button without changing table columns, input semantics, or disabled-row behavior.
- `pass`: Multiple matches resolve deterministically to latest `created_at`, then descending `id`, reusing the existing task-list order rather than creating a conflicting rule.
- `pass`: The jump sequence handles the existing view reset, a previously active logs tab, paused filtering, asynchronous card rerender, safe task-ID lookup, exact `scrollIntoView({ behavior: 'smooth', block: 'center' })`, and approximately 1.5-second recognizable focus including reduced-motion behavior.
- `pass`: Both the new button's click and keydown handlers explicitly call `stopPropagation`; native button keyboard activation remains intact and the market row drawer cannot open from the control.
- `pass`: Cache changes make the market button projection timely while reusing existing input-preserving table redraw; no polling, backend, schema, store, executor, order, borrow, or money behavior is introduced.
- `pass`: `frontend/self-check.js` cases are executable, cover show/hide, deterministic target, live cache projection, borrowing and paused jump flows, logs-to-tasks recovery, scrolling/focus, and runtime event isolation without false-green substring-only proof.
- `pass`: Scope, non-goals, files, implementation stop point, and post-plan-review routing are unambiguous and minimal. Any reviewer-introduced hypothetical that would block must satisfy `AGENTS.md` §1 Scenario Admission with a matching evidence anchor and current practical impact.

Verdict And Evidence Requirements:
- Create exactly the allowed P2 handoff following the Task Handoff Evidence Contract. Use `delivery_sha: none` because this is a read-only plan review with no delivery commit.
- Cite commands and raw repository-relative evidence. Classify every `REWORK` finding under `AGENTS.md` §8 and give executable repair requirements.
- For `ACCEPT`, use `问题记录: none` unless the handoff contains a concrete non-blocking observation; use `修复要求: none`.
- For `REWORK`, set both `问题记录` and `修复要求` to the P2 handoff path and put the detailed findings/repairs in its Source Report.
- The immediate recipient is Bookkeeper `gemini-3.7-flash` in window `agy`; only Bookkeeper may verify the handoff and advance `status.json`.

Stop:
- Stop after the read-only plan review, the single create-only handoff, and the formal console receipt. Do not edit the plan, implement code, commit, merge, deploy, launch the implementation task, or wait for another model.

reply_to: agy
After emitting the normal console receipt, send that same receipt once to the reply_to window per `HERDR.md`, then stop.
