# Dispatch — task1-unknown-not-zero

```text
Identity:
  task_id:         task1-unknown-not-zero
  target_role:     Implementer
  target_model:    claude_glm
  provider:        zhipu_glm
  status_revision: 4
  required_skill:  agents/skills/senior-developer.md
```

Revised 2026-07-30 after the plan review (`07-plan-review-verdict.md`) returned
`REWORK` on the first version of this packet: D5 rewritten as an executable rule,
D6 corrected to M2-only, D7 added. This is a pre-dispatch packet correction, not a
repair round — `rework_count` stays 0 and your full budget is intact.

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

**D5 — tripwire.** Add a static guard to `backend/tests/test_hedge_purity.py`, in
the style of that file's existing import and allowlist guards. The first version
of this deliverable was prose and the plan review rejected it as under-specified;
S4 (D7) proved a SQL literal escapes it. Build it to this exact shape:

1. **Structure.** A pure function, e.g. `find_money_zero_defaults(source, path)`,
   returning `(line_number, matched_text, reason)` tuples. Tests call it over both
   real repository files and synthetic snippets, so it must be callable — do not
   inline it in one test body.
2. **Scope.** Every `.py` file under `backend/hedge_open_tasks/`, plus
   `backend/services/live_hedge_executor.py`. That second path is r4's layer and
   was wrongly excluded before.
3. **Money identifiers.** `price`, `avg_price`, `notional`, `quote`,
   `cumulative_quote_amt`, `cumulative_quote`, and any name ending `_notional`,
   `_avg_price`, or `_quote`. Quantity names are explicitly **not** money:
   `filled_qty`, `cumulative_base_qty`, `base_qty`, `executed_qty`, `qty`.
4. **Two detections.**
   - *Python*: a money identifier assigned from, or a dict entry keyed by a money
     identifier whose value contains, `_num(`, `_decimal_str(` without an explicit
     `default=None`, `or "0"`, `or '0'`, or `.get(…, "0")` / `.get(…, '0')`.
   - *SQL*: inside a string containing `INSERT INTO` or `UPDATE`, a `'0'` literal
     positionally corresponding to a money column named in that statement's column
     list. If positional mapping proves unreliable across this repository's
     statements, fall back to the deliberately blunt rule "a money column name
     appears in the column list of an `INSERT`/`UPDATE` whose values contain a
     `'0'` literal" and allow-list the justified cases. A blunt rule with visible
     exceptions is acceptable; a rule that misses S4 is not.
5. **Allow-list.** Exactly one format: a trailing same-line comment
   `# money-zero-ok: <reason>`. The guard must also assert that every marker in
   the tree still sits on a line its own detector flags, so a marker cannot
   survive as a blanket exemption after the code beneath it moves.
6. **Meta-tests — three, permanent, not a manual probe.** Feed the function
   synthetic sources and assert it flags: (a) a Python coercion into `avg_price`;
   (b) a SQL `INSERT` seeding a money column with `'0'`; (c) a construct in
   `backend/services/live_hedge_executor.py`'s scope. Also assert it does **not**
   flag a quantity default or an allow-listed line.

State in your report which historical rounds this guard would have caught. Do not
claim it catches r5 (the migration that over-nulled a real `'0'`) — no static
pattern can, and that inflated claim is the kind of thing this stage exists to
remove.

**D6 — implicit-migration guard.** `HedgeOpenStore.__init__` (`store.py:299-311`)
calls `_migrate()`, which performs additive DDL **and** one row-mutating repair.
On 2026-07-28 that rewrote two rows in the production database with no caller
intending it.

⚠️ **Corrected fact — read before touching the migration.** Only **M2** exists:
the `leg_exposure.ts` `1970 → real timestamp` UPDATE at `store.py:472-478`. **M1
was deleted deliberately at commit `95ac1a5`** during the previous stage. An
earlier version of this packet said "M1/M2"; that was a Planner error. **Do not
recreate, restore, or reimplement M1 under any reading of this deliverable.** If
you believe a deliverable requires M1, that is a blocker.

Move M2's row UPDATE behind an explicit keyword argument defaulting to off. DDL
stays automatic and ungated. No production caller passes the flag — M2 has already
been applied. Add a test proving a repairable row survives a default construction
unchanged.

Accuracy requirement for your report: D6 buys "no semantic row rewrite on default
construction". It does **not** buy "never writes the database file" — additive DDL
still writes. The `hedge_open_leg` rebuild at `store.py:379-420` is separately
guarded by a `PRAGMA table_info` probe (`store.py:367-378`) and no-ops on an
already-migrated database; leave that guard exactly as it is.

**D7 — S4, the seeded zero (found by the plan review).** `prepare_attempt` inserts
both PREPARED legs with the SQL literal `cumulative_quote_amt = '0'`
(`store.py:748` and `:765`) — a figure the system authors for itself before any
exchange contact. Change both to `NULL`. The column is already nullable
(`store.py:92`); no migration is involved.

Why this matters, so you size it correctly: the dispatch-state update at
`store.py:1155` never touches either figure column, so a leg that has been sent,
holds a real `order_id`, and sits at `exchange_status = NEW` keeps that
self-authored zero — and `list_attempts_page` projects in-flight legs to the UI on
purpose (`store.py:1366-1372`).

Do **not** change `cumulative_base_qty`'s `'0'` seed. That column is
`TEXT NOT NULL DEFAULT '0'` (`store.py:91`); changing it needs a live-table schema
rebuild and Human ruled it out of this stage (`00-plan.md` §3).

Expect existing tests to assert the old `'0'`. Update those assertions — but if one
encodes a product rule rather than an incidental value, stop and report it instead
of rewriting the rule.

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

Commit: yes, on branch `stage/2026-07-unknown-not-zero-v1` (Human selected it; it
already exists and points at this stage's latest bookkeeping commit). Check it
out before the first edit and verify with `git branch --show-current`. One commit per deliverable group or one
for all — your choice. Do not merge, do not touch `main`.

## Inputs

Read only these, at the given ranges (measured: whole-file reads of `store.py`
alone are 98 KB and would blow the task budget):

| Path | Range | Why |
|---|---|---|
| `reports/agent-runs/2026-07-unknown-not-zero-v1/00-plan.md` | whole (9 KB) | Highest authority for this task. §4 is the closed site list, §3 the non-goals |
| `agents/developer-discipline.md` | whole (3.6 KB) | Required |
| `agents/skills/senior-developer.md` | whole (11 KB) | The one named skill |
| `reports/agent-runs/2026-07-unknown-not-zero-v1/07-plan-review-verdict.md` | whole | Why D5/D6/D7 read as they do, and what must not be weakened |
| `backend/hedge_open_tasks/store.py` | `285-300`, `299-315`, `360-420`, `465-485`, `735-780`, `790-830`, `1080-1100`, `1145-1165`, `1300-1350`, `1525-1550`, `1580-1620`, `1880-1980` | The sites. `735-780` is D7, `1145-1165` is the update path that never overwrites the figures, `360-420`/`465-485` is D6 |
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
2. Per-site regressions exist, deterministic (temp SQLite, no clock or network
   dependence), and **paired** — one case for the missing figure and one for a
   real exchange `'0'`, at every site. The pairing is what covers the one defect
   category D5's static guard cannot reach:
   - D1: `NULL` quote → `price is None`; real `"0"` → zero price.
   - D2: `NULL avg_price` → notional excluded and the incomplete flag set; real
     `"0"` and a real price unaffected.
   - D7: a freshly prepared leg has `cumulative_quote_amt is None`; and an
     in-flight leg — dispatched, real `order_id`, `exchange_status = NEW`, not yet
     resolved — still reports an unknown notional rather than zero, through
     whatever projection the API layer uses.
   - D6: the repairable row is untouched by a default construction.
3. `grep -n "_num(" backend/hedge_open_tasks/store.py` output appears in your
   report with a one-line classification per remaining caller (money vs
   quantity/comparison). Any money caller left must be justified.
4. The three D5 meta-tests are present and named in your report, with the
   statement of which historical rounds the guard covers and which it cannot.
5. `git status --short` shows no file outside Allowed Files.
6. Your report states plainly that D6 prevents semantic row rewriting and does
   not prevent all writes.

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
