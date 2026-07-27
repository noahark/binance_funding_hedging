# R4 Diff Reconciliation — Implementation Intake

## Evidence received

- Task A / Claude-GLM raw implementation report:
  `20-implementation-backend.md`. The human operator supplied the runner session
  reference `694ea9e3-20e9-4f42-800e-940f9530a9bb`; its report correctly records
  the GLM provider-native Session ID as unavailable.
- Task B / Kimi K3 raw implementation report:
  `20-implementation-frontend.md`.
- The worktree contains only the owners' allowed source files, their new backend
  modules/tests, and their two raw reports. No forbidden source boundary was
  changed. `git diff --check` passes.

## Reproduced test evidence

- `.venv/bin/python -m pytest backend/tests -q`: **856 passed in 43.12s**.
- `node frontend/self-check.js`: **all assertions passed**.

These results establish that each task's self-tests pass. They do not satisfy
the R4 integration contract by themselves.

## R4 findings requiring backend correction before H_A/H_B commits

### R4-1 — P1: backend does not expose the required attempt timeline document

`00-task.md` Deliverable 5 and PRD §9.2 require the API/UI to show the attempt
timeline, both order IDs/statuses, cumulative quantities/averages, and residual.
The frozen wire shape is `12-development-breakdown.md` §3.4.

The durable tables exist, but `HedgeOpenTaskService.get_logs()` currently returns
only legacy `logs`, each from `log_to_doc()`. Its `payload` is a record-transport
would-send payload (for example `transport`, params, and client IDs), not the
§3.4 attempt document. A live unknown/querying attempt does not create that log
at all. The Kimi UI correctly accepts an additive `attempts` list, but will
otherwise ignore those log entries as not attempt-shaped and render an empty
timeline.

Required correction: retain the existing `logs`/cursor contract unchanged and
add a first-class additive `attempts` projection on the existing read endpoint.
Each attempt document must have the frozen §3.4 fields (`attempt_id`,
`attempt_seq`, `direction`, `q_common`, `pair_outcome`, `spot`, `perp`,
`residual`, `ts`), with task-scoped context where needed. It must include
prepared/querying attempts as well as resolved attempts. Decimal fields remain
strings. Add direct backend API/service tests proving the projection and an
empty/missing leg degrade shape; no frontend change is required because its
extractor already handles `attempts`.

### R4-2 — P1: per-task cadence is still serialized at the task level

`00-task.md`, PRD §6.3, `05-cadence-resolution.md`, and ADR-5 require each
running card to own an independent asynchronous one-second worker, allowing
several tasks to submit in the same second. `service.tick()` now loops over every
eligible task, but invokes `_dispatch_one_for_task()` synchronously for each one.
In live mode that call waits for `LiveHedgeExecutor.dispatch()` to join both
network-leg threads; its client timeout is 10 seconds. A slow first task can
therefore delay all later task cards beyond their own one-second tick.

Required correction: dispatch eligible task work independently within a tick
without weakening the shared Start/rate-limit gate, durable-before-send
transaction, or no-resend rule. Add a deterministic blocking-executor test
proving two eligible tasks enter dispatch before either is released. Do not add a
global product cadence lock or an automatic remediation path.

## Authority resolution recorded during R4

The breakdown's isolated sentence that says disabled means "zero record" is not
adopted as a correction: the higher approved PRD §3 and detailed `10-design.md`
§Scope retain record/dry-run as the safe default and require only zero **real
POST** for disabled/record. The implementation's record default is therefore not
an R4 defect. Likewise, `recvWindow=60000` is inside the archived endpoint's
documented maximum; the later review should assess whether the recon's
recommendation to prefer 5000 needs a stricter product rule, but it does not
block this bounded R4 fix.

## Next action

Do not create H_A/H_B evidence commits or dispatch formal review yet. Human
operator runs `backend-r4-fix.prompt.md` in the original backend owner session
or a fresh Claude-GLM fix session. Task B remains stopped; its compatible
frontend needs no code change for the additive `attempts` response.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/13-r4-diff-reconciliation.md
本地北京时间: 2026-07-23 22:32:36 CST
下一步模型: human operator
下一步任务: execute the bounded Claude-GLM R4 backend fix packet and preserve its raw report
