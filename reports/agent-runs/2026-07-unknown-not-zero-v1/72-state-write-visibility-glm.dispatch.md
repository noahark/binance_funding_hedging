# Dispatch — task1d-state-write-visibility

```text
Identity:
  task_id:         task1d-state-write-visibility
  target_role:     Implementer
  target_model:    claude_glm
  provider:        zhipu_glm
  status_revision: 15
  required_skill:  agents/skills/minimal-change-engineer.md
```

Bounded repair of **five** sites from a closed, independently-audited list
(`71-audit-result-and-scope-decision.md`). `rework_count` is 2 of 3.

**Do not widen this.** Three further class-(A) sites and one UI question are
deferred by Human decision D-10, with reasons, and go to `PROJECT_STATE.md` at stage
close. They are listed in §Out of scope. Touching them is a scope violation, not
initiative.

## Goal

Five post-POST sites discard a failed `self._store.*` state write. Each leaves the
system believing something false about an order or a task, with nothing visible to
the operator. The template already exists in this file and has been reviewed twice:
`service.py:1205` / `:1242` (F2) — catch, record an event, do not fabricate a
conclusion, do not resend, let the next worker round recover.

| # | Site | Discarded call | What breaks today |
|---|---|---|---|
| S1 | `service.py:1178` | `resolve_leg_from_query` | `except Exception: continue` — the terminal query verdict **and** the raw-response capture that follows are both lost; the leg keeps its stale state |
| S2 | `service.py:1723` | `mark_attempt_rate_limited` | The rate-limited fact is lost, so reconcile later charges a 429 against the failure counter the design explicitly exempts |
| S3 | `service.py:1736` | `resolve_attempt` (pause-class settle) | Orders already sent, both legs terminal; the settlement is discarded, `pair_outcome` stays NULL, the in-flight guard stalls the task |
| S4 | `service.py:1758` | `resolve_attempt` (normal settle) | The main path. A real order placed and its conclusion never persisted |
| S5 | `service.py:1780` | `mark_leg_querying` | A leg needing drain is never marked, so an in-flight order is never reconciled by client ID |

### R1 — one uniform mechanism, and do not disturb F2's

Add **one** helper alongside `_record_settlement_failure`, e.g.
`_record_state_write_failure(task_id, attempt_id, operation, exc, now_us)`, emitting
a **new** event kind `state_write_failed` with payload
`{attempt_id, operation, error_type, error}` — `operation` naming the store call
(`resolve_leg_from_query`, `mark_attempt_rate_limited`, `resolve_attempt`,
`mark_leg_querying`).

Constraints:

- **Do not rename or reuse `settlement_failed`.** It is a persisted event kind with
  rows already written by the F2 fix, it is asserted by tests reviewed twice, and it
  would be a false label on `mark_leg_querying`. Two kinds, both accurate, no data
  migration.
- Do not refactor `_record_settlement_failure` or its two call sites. They are
  correct and reviewed; leave them exactly as they are.
- Same discipline as F2: catch (an escaping exception kills the worker and every
  other task), wrap **only** the audit write in a narrow inner guard with a comment
  saying so, no credentials / headers / tokens / request bodies in the payload.

### R2 — S1 must also preserve the raw response

`:1178`'s `continue` skips the `_persist_leg_raw` call immediately after it. Record
the failure **and** stop skipping the raw capture, or state plainly in your report
why the capture cannot run when the leg write failed. Losing the exchange's own words
here is the exact defect family this stage exists to close.

### R3 — S2 needs one ordering guarantee, not just a log line

If the rate-limit stamp fails, the attempt is unstamped and a later reconcile will
settle it as an ordinary failure and consume the failure counter. Recording the
failure does not prevent that.

Required: a failed rate-limit stamp must not let the pair be settled as an ordinary
failure. The cheapest correct shape is a retry of the stamp before settlement on the
next round; the crash-gap loop already re-enters every round.

**If achieving this needs more than recording plus a next-round retry — a new
attempt column, a new status, new operator copy — stop and report a blocker.** Do
not invent product semantics.

### R4 — fault-injection tests, one per site

Deterministic, temp SQLite, no real clock, no network. For each of S1-S5, force the
named store call to raise (monkeypatch or a store double), drive the **real service
path**, and assert:

- the exception does not escape and the worker continues;
- a `state_write_failed` event exists naming that `operation`;
- the state was **not** fabricated — the leg or attempt is still in its
  pre-failure condition (do not "tidy" a test by asserting a settlement that did
  not happen);
- for S1: the raw response is still captured, or the report explains why not;
- for S2: the pair is not settled as an ordinary failure while unstamped.

The mutation check that matters: reverting any one of the five must fail at least one
test. State in your report that you verified this, per site.

## Out of scope — deferred by Human decision D-10

Do not repair, do not "improve while passing", do not add tests for:

- **`service.py:1141`** — an inconclusive query `continue`s with no record. Needs a
  log-rate design ("避免每轮查询都刷日志") and is already the previous stage's
  Human-deferred `p1-inconclusive-query-raw-not-persisted`.
- **`service.py:1632`** — dry-run `resolve_attempt`. **No order is placed** on that
  path; lowest risk of the eight.
- **`live_hedge_executor.py:690-702`** — `_error_leg` takes the send-thread
  exception and never uses it. Fixing it changes the `LegDispatch` data contract.
  Safety is unaffected (the leg still becomes `UNKNOWN_QUERYING` and is drained);
  only diagnosability is lost.
- **The `entries` timeline.** `_ENTRY_EVENT_KINDS` (`service.py:61-67`) excludes
  these events, so they appear on the logs page and not the timeline. Whether they
  should is operator-interface meaning and needs Human approval. **Do not add
  `state_write_failed` or `settlement_failed` to `_ENTRY_EVENT_KINDS`.**
- **`hedge_preflight_provider.py:263/267/270`** — excluded by D-8.
- All class-(B) and class-(C) sites in the audit. They are correct as they are.

## Allowed Files

- `backend/hedge_open_tasks/service.py`
- `backend/tests/test_hedge_task_local.py`
- `backend/tests/test_hedge_service.py` — only if a site's honest test home is there
- `reports/agent-runs/2026-07-unknown-not-zero-v1/73-task1d-glm-result.md` (create)

Forbidden: `backend/hedge_open_tasks/store.py`, `domain.py`, `executor.py`,
`scheduler.py`, `backend/services/**`, `backend/tests/test_hedge_purity.py`,
`backend/tests/test_hedge_store.py`, `frontend/**`, `schemas/**`, `scripts/**`,
`docs/**`, `AGENTS.md`, `agents/**`, `data/**`, `PROJECT_STATE.md`, `ACTIVE.json`.

Carve-out: in this stage's `status.json` you may write only `current_task.state`,
`dispatched` → `reported`.

No network, no credentials, no service control, no write to `data/**`. Commit on
`stage/2026-07-unknown-not-zero-v1` (already checked out). Do not merge.

## Inputs

| Path | Range | Why |
|---|---|---|
| `reports/agent-runs/2026-07-unknown-not-zero-v1/71-audit-result-and-scope-decision.md` | whole | The closed list and its classification. Highest authority for this task |
| `backend/hedge_open_tasks/service.py` | `1130-1300`, `1620-1650`, `1700-1830` | The five sites, F2's template, the existing `raw_persist_failed` pattern at `:1811-1819` |
| `backend/tests/test_hedge_task_local.py` | `460-580` | F2's two fault-injection tests — the shape to follow |
| `backend/hedge_open_tasks/store.py` | `700-720` | The in-flight guard, to understand why a lost `resolve_attempt` stalls a task. **Read only** |
| `agents/skills/minimal-change-engineer.md` | whole | The one named skill |

Do not read the plan, the plan review, or earlier task reports.

## Acceptance Checks

```text
python3 -m pytest backend/tests/test_hedge_task_local.py backend/tests/test_hedge_service.py -q
python3 -m pytest backend/tests -q
```

1. Both green; full-suite total ≥ 1092 collected (measured baseline 1092 passed).
   `test_hedge_api.py::test_oversized_body_is_body_too_large` is a known
   pre-existing flake (`ConnectionResetError`, passes on isolated re-run); if it
   fires, re-run it alone and report both. Not yours to fix.
2. All five sites converted; paste before/after for each.
3. R4's five fault-injection tests exist, and you state the per-site mutation result.
4. `settlement_failed` and its two call sites are byte-identical to before — show
   `git diff` proving it.
5. `_ENTRY_EVENT_KINDS` unchanged; no new pause reason, task status, operator copy,
   or UI field. State this explicitly.
6. `git status --short` shows no file outside Allowed Files.
7. Report which of the five, if any, required more than the template, and why.

## Stop

Stop after code, tests, commit, and `73-task1d-glm-result.md`. Flip
`current_task.state` to `reported` and nothing else.

Return exactly the `[TASK_RESULT v2]` block from `AGENTS.md` §7 — nine mandated
Chinese labels 任务 ID / 执行结果 / 结果摘要 / 产物 / 检查结果 / 阻塞项 /
本地北京时间 / 下一步模型 / 下一步任务 — closing with `[/TASK_RESULT]`. No invented
fields, no Identity block copied in, marker is not `[/TASK_RESULT v2]`.
`结果摘要` ≤ 300 characters, `检查结果` ≤ eight grouped items.

`下一步模型: opus5（记账人，Human 转交结果）`.

Route after this: review-1 (Grok 4.5, cross-provider) then review-2 (Codex,
disclosure per D-6). `rework_count` is 2 of 3 — if a reviewer returns `REWORK`
again, `AGENTS.md:182` routes the next decision to Human.
