# Dispatch — task1c-f2-settlement-visibility

```text
Identity:
  task_id:         task1c-f2-settlement-visibility
  target_role:     Implementer
  target_model:    claude_glm
  provider:        zhipu_glm
  status_revision: 10
  required_skill:  agents/skills/minimal-change-engineer.md
```

Bounded repair of **one** review-2 finding. `rework_count` is 1 of 3.

Scope of the other two findings, so you do not act on them:

- **F1 (balance-missing → fabricated zero) is OUT OF SCOPE** by Human decision D-8.
  Do not touch `hedge_preflight_provider.py` or `domain.py`'s balance gate. Context
  and the eventual fix pattern are preserved in `43-balance-shape-evidence.md` for a
  future stage. If you believe F2's fix requires touching the balance path, that is
  a blocker.
- **F3 (documents overstating the guard) is already done** by the Bookkeeper —
  `00-plan.md` corrected in place, an erratum appended to your own
  `20-task1-glm-result.md` without editing your prose. Nothing for you there.

## Goal

**F2 — a discarded settlement failure silently stalls the task.**

Confirmed chain (`41-review-2-codex-result.md` §F2, verified against the code):

1. `store.finalize_attempt` → `_exposure_from_legs` → `domain.build_leg_exposure`,
   which raises on `ts_us <= 0`. That raise is deliberate (it is the T5 backstop,
   introduced by D4 of the previous task) and **must stay**.
2. `service.py:1204-1206` and `service.py:1237-1239` wrap the settlement calls in
   `except Exception: pass`.
3. So **any** exception from settlement — the timestamp one, a DB error, a future
   bug in the rollup — is discarded. The attempt keeps `pair_outcome = NULL`.
4. `pair_outcome IS NULL` is precisely `prepare_attempt`'s in-flight guard
   (`store.py:712-717`), so the task is silently barred from ever opening another
   pair.
5. The second bare except sits in the **crash-gap recovery loop** — the mechanism
   designed to unstick exactly this state — so recovery cannot recover it either.
6. Nothing is visible to the operator at any point.

The defect is the discarding, not the timestamp. Fix the discarding.

### Required

**R1 — stop discarding.** At both sites, a settlement exception must produce an
operator-visible record before execution continues. Use the existing
`record_task_event` channel that the logs page already reads; do not invent a new
storage mechanism, a new table, or a new API field.

The event must carry enough to diagnose: the task, the attempt, and the exception
type and message. It must **not** carry credentials, headers, tokens, or a full
request body.

**R2 — the worker must not die, and recording must not become the new failure.**
Keep catching (an escaping exception would take down the worker and with it every
other task). Wrap the recording itself so that a failure to record cannot raise —
but that inner guard must be narrow and commented, not a second blanket
`except: pass` around business logic.

**R3 — keep it recoverable, and do not invent new product semantics.** The
crash-gap loop already retries every worker round; a transient cause therefore
self-heals and a permanent one produces a repeated, visible event. That is
sufficient for this repair.

Do **not** add a new `pause_reason`, a new task status, new operator-facing Chinese
copy, or a UI change. Those are product meaning and need Human approval. If you
conclude visibility is impossible without one, stop and report a blocker rather
than choosing one.

**R4 — test the runtime consequence, not the helper.** The existing coverage only
asserts that `build_leg_exposure` raises. Add a deterministic test that drives the
**real service settlement path** with an injected clock returning `0`
(`HedgeOpenService(..., wall_us=lambda: 0)` — the constructor already accepts it,
`service.py:385-388`) over a terminal single-leg attempt, and asserts:

- the settlement exception did not escape;
- an operator-visible event was recorded and names the failure;
- the worker continued;
- the attempt is still unsettled (that is correct — do **not** fabricate a
  settlement to make the test tidy).

Cover the crash-gap loop site as well as the drain site. Temp SQLite only; no
network, no `data/**`, no real clock dependence.

## Allowed Files

- `backend/hedge_open_tasks/service.py`
- `backend/tests/test_hedge_service.py`
- `backend/tests/test_hedge_task_local.py` — only if the crash-gap loop's existing
  coverage lives there and is the honest home for R4's second case
- `reports/agent-runs/2026-07-unknown-not-zero-v1/45-task1c-glm-result.md` (create)

Forbidden: `backend/hedge_open_tasks/store.py`, `domain.py`, `executor.py`,
`backend/services/**` (including `hedge_preflight_provider.py`),
`backend/tests/test_hedge_purity.py`, `backend/tests/test_hedge_store.py`,
`frontend/**`, `schemas/**`, `scripts/**`, `docs/**`, `AGENTS.md`, `agents/**`,
`data/**`, `PROJECT_STATE.md`, `ACTIVE.json`.

Do not weaken or remove `build_leg_exposure`'s `ts_us <= 0` raise, and do not
restore the old behaviour of silently emitting a 1970 timestamp.

Carve-out: in this stage's `status.json` you may write only `current_task.state`,
`dispatched` → `reported`.

No network, no credentials, no service control, no write to `data/**`. Commit on
`stage/2026-07-unknown-not-zero-v1` (already checked out). Do not merge.

## Inputs

| Path | Range | Why |
|---|---|---|
| `reports/agent-runs/2026-07-unknown-not-zero-v1/41-review-2-codex-result.md` | §F2 | The finding and its verified chain. Highest authority for this task |
| `backend/hedge_open_tasks/service.py` | `1180-1245`, `380-395` | The two sites and the injectable clock |
| `backend/hedge_open_tasks/store.py` | `700-720`, `1230-1250` | The in-flight guard and the raising path — read only, do not edit |
| `backend/tests/test_hedge_service.py` | search-only | Existing fixtures to reuse |
| `agents/skills/minimal-change-engineer.md` | whole | The one named skill |

Do not read the plan, the plan review, or the earlier task reports. The finding is
self-contained.

## Acceptance Checks

```text
python3 -m pytest backend/tests/test_hedge_service.py backend/tests/test_hedge_task_local.py -q
python3 -m pytest backend/tests -q
```

Pass conditions:

1. Both green; full-suite total ≥ 1090 collected (measured baseline: 1090 passed).
   `test_hedge_api.py::test_oversized_body_is_body_too_large` is a known
   pre-existing flake (`ConnectionResetError`, passes on isolated re-run) — if it
   fires, re-run it alone and report both results. Not yours to fix.
2. R4's tests exist, are deterministic, and drive the real service path with an
   injected zero clock — not the helper in isolation.
3. Neither bare `except Exception: pass` remains at the two named sites. Show the
   before/after of both.
4. No new pause reason, task status, operator copy, or UI field was introduced.
   State this explicitly.
5. `git status --short` shows no file outside Allowed Files.

## Stop

Stop after code, tests, commit, and `45-task1c-glm-result.md`. Flip
`current_task.state` to `reported` and nothing else.

Return exactly the `[TASK_RESULT v2]` block from `AGENTS.md` §7 using only its nine
mandated Chinese labels — 任务 ID / 执行结果 / 结果摘要 / 产物 / 检查结果 / 阻塞项 /
本地北京时间 / 下一步模型 / 下一步任务 — closing with `[/TASK_RESULT]`. No invented
fields, no Identity block copied into the result, and the marker is not
`[/TASK_RESULT v2]`. `结果摘要` ≤ 300 characters, `检查结果` ≤ eight grouped items.

`下一步模型: opus5（记账人，Human 转交结果）`.

After this repair the route is review-1 again (Grok 4.5, cross-provider) and then
back to review-2 (`AGENTS.md:181`), because the repair touches a file that was
forbidden in the reviewed range.
