# Fable5 Development-Breakdown Dispatch — A+B Durable Borrow Tasks

## Operator Instructions

Dispatch this prompt manually to the registered development-breakdown author:

```bash
claude --model claude-fable-5 --permission-mode acceptEdits \
  -p "$(cat reports/agent-runs/2026-07-real-borrow-execution-v1/09-fable5-development-breakdown.dispatch.md)"
```

If Fable5 is quota-exhausted, capture the runner-level failure evidence and
then use the configured fallback `opus4.8`; do not treat a Zhipu/GLM-rerouted
CLI failure as Anthropic availability evidence. Record the provider-native
session ID, its source, and the raw output path after execution. Do not let the
model modify `status.json`; the bookkeeper records state and receipts.

## Prompt Body

You are the development-breakdown author for stage
`2026-07-real-borrow-execution-v1`. Use the `task_planner` skill by reading
`agents/skills/task-planner.md` in full. You are doing design decomposition
only: **do not implement, edit source code, run a server, call Binance, or
create any task dispatches.**

Read these raw inputs before writing:

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml` — `development-breakdown` and
  `task-breakdown` sections
- `docs/parallel-development-mode.md` — only if you recommend parallel tasks
- `reports/agent-runs/2026-07-real-borrow-execution-v1/06-direction-synthesis.md`
- `reports/agent-runs/2026-07-real-borrow-execution-v1/03-grok-borrow-api-capacity-recon.md`
- `reports/agent-runs/2026-07-real-borrow-execution-v1/00-task.md`
- `reports/agent-runs/2026-07-real-borrow-execution-v1/10-design.md`
- `reports/agent-runs/2026-07-real-borrow-execution-v1/11-adr.md`
- `docs/product/PRD.md`
- `docs/architecture/ARCHITECTURE.md`
- relevant existing code and tests, especially `backend/app/server.py`,
  `backend/services/private_client.py`, `backend/tests/`,
  `frontend/index.html`, and `frontend/self-check.js`.

The user has approved **only A+B**. Boundary C is a separate future stage. The
following are non-negotiable for this work:

- A+B sends zero Binance writes and zero authenticated live Binance requests.
- Do not add a signing client, credentials, a live executor, `marginLoan`,
  `maxBorrowable` preflight/polling, a load test, or a product-defined
  scheduler minimum/cap.
- The scheduler accepts every positive finite decimal interval, including
  `0.5`, normalizes it to integer microseconds, and uses one durable global
  round-robin cursor.
- Ordinary runtime uses a no-network disabled executor; paper execution is
  test-only and deterministic.
- Existing public-market snapshot behavior and the GET-only role of
  `PrivateClient` must stay intact.
- The browser is never the execution clock or task authority.
- Persist only sanitized attempt metadata; never raw private payloads,
  request headers, signatures, credentials, or secrets.

Write exactly one new artifact:

`reports/agent-runs/2026-07-real-borrow-execution-v1/12-development-breakdown.md`

Do not edit any other file, including `status.json` and `70-handoff.md`.
Use the following structure and make every item concrete enough for the
bookkeeper to produce implementation packets without interpretation:

1. **Decision and dependency graph** — decide whether the backend and frontend
   tasks are safely parallel. If yes, identify the frozen API/schema boundary
   they share and what the bookkeeper must validate at dispatch-ready. If no,
   state the serial dependency and why.
2. **Task table** — one bounded backend task for Claude-GLM and one bounded
   frontend task for Kimi. For each: owner/provider, purpose, exact allowed
   files or permitted directory globs, explicitly forbidden files, prerequisites,
   deliverables, acceptance criteria, and exact report/test-output paths. Do
   not give Codex/GPT implementation ownership and do not enable Grok.
3. **Contracts frozen before coding** — precise local route/method list,
   JSON document/schema filenames and minimum field semantics, task statuses,
   result categories, response/error shape, cursor behavior, decimal and time
   representations, and the no-network executor seam. Call out any choice that
   must be made in the backend task rather than silently leaving it vague.
4. **Integration and ownership safety** — explain how `server.py`, config,
   schema files, backend tests, `frontend/index.html`, and
   `frontend/self-check.js` are owned without concurrent edit collisions.
   Identify whether the frontend should consume stable API mocks only, and how
   it will bind to the real backend contract afterward without scope creep.
5. **Deterministic verification plan** — exact backend/frontend commands and
   required scenario coverage: SQLite restart, round-robin A→B→C→A, 0.5-second
   representation/effective-gap logs, lifecycle/soft deletion, unknown
   per-task block, known results/cooldown/completion, newest-first cursor
   pagination, HTTP validation, UI tabs/filter/edit/latest result/log paging,
   and proof of zero Binance/network/credential leakage. Include regression
   commands and `git diff --check`.
6. **Risks and review focus** — specific invariants and source hotspots for
   embedded cross-review and formal Review-1/Review-2. Include the later
   Boundary C handoff risks but do not broaden A+B.
7. **Recommended next workflow action** — a short, explicit recommendation for
   the bookkeeper: serial dispatch or the exact R10/parallel dispatch work that
   remains. This recommendation is not an implementation dispatch.

Distinguish facts read from the raw artifacts from your recommendations. Do
not claim live API behavior was tested. At the end of your Markdown report,
add the required navigation footer from `AGENTS.md`, with your actual
provider-native session ID only if available; otherwise state unavailable and
why.

当前 Session ID: unavailable (prepared by Codex; target Fable5 session is created by operator)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/09-fable5-development-breakdown.dispatch.md
本地北京时间: 2026-07-19 16:03:02 CST
下一步模型: Fable5
下一步任务: 仅写入 12-development-breakdown.md，完成 A+B 实现拆分
