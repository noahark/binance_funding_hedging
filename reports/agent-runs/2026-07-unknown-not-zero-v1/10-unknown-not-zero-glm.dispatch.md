# Dispatch — task1-unknown-not-zero

```text
Identity:
  task_id:         task1-unknown-not-zero
  target_role:     Implementer
  target_model:    claude_glm
  provider:        zhipu_glm
  status_revision: 1
  required_skill:  agents/skills/senior-developer.md
```

## Goal

Close the "a missing exchange figure becomes `0`" defect family in one pass
instead of one site at a time, and stop row-mutating migrations from firing
implicitly. Five deliverables, all backend:

**D1 — S1.** `store.py:1324-1343 _exposure_from_legs`: a `NULL`
`cumulative_quote_amt` must produce `price = None`. A real `"0"` from the
exchange still produces a zero price. Today `_num(NULL)` returns `Decimal(0)` and
the function writes `"0E+1"`.

**D2 — S2.** `store.py:1921-1932` (the `fill_rows` loop): a `FILLED` leg whose
`spot_avg_price` / `perp_avg_price` is `NULL` must not add `0` to
`spot_notional` / `perp_notional`. Use the same policy the adjacent `leg_rows`
loop already uses at `:1941-1958`: skip the notional and set the existing
`spot_incomplete` / `perp_incomplete` flag. Do not invent a new flag, a new
output field, or a cross-field consistency check.

**D3 — S3, the root.** `store.py:292-296 _num` silently turns both `None` and an
unparseable value into `Decimal(0)`. Add a sibling that preserves the unknown
(returning `None`) and use it at every money-figure site. `_num` itself stays for
quantity and comparison callers; state that restriction in its docstring. Do not
rewrite the quantity callers.

**D4 — deduplicate.** `_exposure_from_legs` is a hand copy of
`domain.build_leg_exposure` (`domain.py:1017-1053`) — its docstring says so, and
that drift is what produced S1. Delete the copy: map the two `sqlite3.Row` leg
rows onto the dict shape `build_leg_exposure` expects with a small private helper
in `store.py`, and call the domain function. Constraints:

- Observable output for every currently passing case must not change, except S1's
  `price`.
- A `NULL` `cumulative_base_qty` must never render as the string `"None"`.
- `build_leg_exposure` raises on `ts_us <= 0` while the store copy did not. That
  stricter backstop is intended (it is the T5 fix), but it is a new failure mode
  on the reconcile path — cover it with a test and name it in your report.
- If the adapter cannot be written without changing `domain.build_leg_exposure`'s
  contract, stop and report a blocker. Do not change the domain contract.

**D5 — tripwire.** Add a static guard to `backend/tests/test_hedge_purity.py`,
in the style of that file's existing import and allowlist guards: within
`backend/hedge_open_tasks/**`, no money figure (a target or dict key named
`price`, `avg_price`, `notional`, `quote`, `cumulative_quote*`) may be produced by
a zero-defaulting construct (`_num(`, `or "0"`, `, "0")`). Provide an inline
allow-list marker for a justified exception so exceptions are visible in review.
Demonstrate the guard fails on a deliberately reintroduced coercion, then revert
the probe; report both results.

**D6 — implicit-migration guard.** `HedgeOpenStore.__init__` (`store.py:299-311`)
calls `_migrate()`, which performs additive DDL **and** two row-mutating repairs
(M1 `'0'→NULL`, M2 `1970→real ts`, around `store.py:400-460`). On 2026-07-28 that
rewrote two rows in the production database with no caller intending it. Separate
the row-mutating repairs from construction: DDL stays automatic, the repairs run
only under an explicit keyword argument defaulting to off. No production caller
passes it — M1/M2 have already been applied. Add a test proving a repairable row
survives a default construction unchanged. Do not gate the DDL.

## Allowed Files

Modify only:

- `backend/hedge_open_tasks/store.py`
- `backend/tests/test_hedge_store.py`
- `backend/tests/test_hedge_purity.py`
- `backend/tests/test_hedge_service.py` (only if a service-level regression is
  the honest place for a D1/D4 assertion)
- `reports/agent-runs/2026-07-unknown-not-zero-v1/20-task1-glm-result.md` (create)

Forbidden, no exception: `backend/hedge_open_tasks/domain.py`,
`backend/hedge_open_tasks/service.py`, `backend/hedge_open_tasks/executor.py`,
`backend/services/**`, `frontend/**`, `schemas/**`, `scripts/**`, `docs/**`,
`AGENTS.md`, `agents/**`, `data/**`, `PROJECT_STATE.md`, `ACTIVE.json`.

One carve-out: in this stage's `status.json` you may write the single field
`current_task.state`, `dispatched` → `reported`, and nothing else. See §Stop.

No network access, no credentials, no starting or stopping the service, no write
of any kind to `data/**`. Read-only queries against `data/**` are also not needed
for this task; do not perform them.

Commit: yes, on the branch Human names at launch, one commit per deliverable
group or one for all — your choice. Do not merge, do not touch `main`.

## Inputs

Read only these, at the given ranges (measured: whole-file reads of `store.py`
alone are 98 KB and would blow the task budget):

| Path | Range | Why |
|---|---|---|
| `reports/agent-runs/2026-07-unknown-not-zero-v1/00-plan.md` | whole (9 KB) | Highest authority for this task. §4 is the closed site list, §3 the non-goals |
| `agents/developer-discipline.md` | whole (3.6 KB) | Required |
| `agents/skills/senior-developer.md` | whole (11 KB) | The one named skill |
| `backend/hedge_open_tasks/store.py` | `285-300`, `790-830`, `1300-1350`, `1580-1620`, `1880-1980`, `299-315`, `395-465` | The sites |
| `backend/hedge_open_tasks/domain.py` | `1017-1053` | `build_leg_exposure` only |
| `backend/tests/test_hedge_purity.py` | whole (6.4 KB) | The guard style to mirror |
| `backend/tests/test_hedge_store.py` | search-only, do not read whole | Find the existing temp-SQLite fixtures and reuse them |

Do not read the archived `2026-07-hedge-order-truth-v1` evidence; §4 of the plan
already carries what you need from it.

## Acceptance Checks

Run exactly these and paste raw output into your result file:

```text
python3 -m pytest backend/tests/test_hedge_store.py backend/tests/test_hedge_purity.py backend/tests/test_hedge_service.py backend/tests/test_hedge_domain.py backend/tests/test_hedge_api.py backend/tests/test_hedge_task_local.py -q
python3 -m pytest backend/tests -q
```

Pass conditions:

1. Both commands green. The full-suite baseline is 1071 passed; a lower total is
   a blocker, a higher total is expected from the new tests.
2. Per-site regressions exist and are deterministic (temp SQLite, no clock or
   network dependence): D1 covers `NULL` quote → `price is None` **and** real
   `"0"` → zero price; D2 covers `NULL avg_price` → notional excluded plus
   incomplete flag set, **and** real `"0"`/real price unaffected; D6 covers the
   untouched repairable row.
3. `grep -n "_num(" backend/hedge_open_tasks/store.py` output appears in your
   report with a one-line classification per remaining caller (money vs
   quantity/comparison). Any money caller left must be justified.
4. The D5 probe result is reported: the guard failed on the reintroduced
   coercion, and the probe is reverted.
5. `git status --short` shows no file outside Allowed Files.

## Stop

Stop after the code, tests, commits, and
`reports/agent-runs/2026-07-unknown-not-zero-v1/20-task1-glm-result.md` are
written. Move `current_task.state` from `dispatched` to `reported` in
`reports/agent-runs/2026-07-unknown-not-zero-v1/status.json` — that single field
is the only state write you may make; do not touch `revision`, `next`,
`delivery_sha`, or any other field.

Do not launch a reviewer, do not prepare another packet, do not merge. Return the
`[TASK_RESULT v2]` block required by `AGENTS.md` §7, including the three Chinese
handoff lines, with `下一步模型: opus5（记账人，Human 转交结果）`.

If the file boundary above is insufficient to satisfy a deliverable, that is a
blocker: report it and stop rather than widening scope.
