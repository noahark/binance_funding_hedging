# Task Result — task1-unknown-not-zero

Implementation delivered as commit `6c250f4` on branch
`stage/2026-07-unknown-not-zero-v1`; this report plus the `status.json` state
flip form a separate ledger commit on the same branch. The dispatch packet's
input metadata
(`task_id` / `model` / `provider` / `status_revision` / `required_skill`) is not
repeated here as result fields — the formal `[TASK_RESULT v2]` block at the end
of this file uses only the visible fields defined in `AGENTS.md §7`.

The "missing exchange figure becomes `0`" family is closed at the root in one
pass, not site by site, and row-mutating migrations no longer fire implicitly.
Five deliverables (D1–D7), all backend. Full suite **1087 passed**
(baseline 1071 + 16 new tests).

## What changed (per deliverable)

**D1 — S1 (`store.py:1374 _exposure_from_legs`).** Resolved by D4 (delegation),
not by another point edit. A `NULL` `cumulative_quote_amt` now yields
`price = None`; a real exchange `"0"` still yields a zero price. Verified by
`test_exposure_from_legs_null_quote_is_unknown_not_zero_price` (None) and
`test_exposure_from_legs_real_zero_quote_is_zero_price` (zero).

**D2 — S2 (`store.py:1976/1984/1980/1988` fill_rows loop).** `spot_avg`/`perp_avg`
are parsed with `_num_or_none` (was `_num`); when a FILLED leg has a `NULL`
`avg_price`, the notional is skipped and the **existing** `spot_incomplete`/
`perp_incomplete` flags are set — the same policy the adjacent `leg_rows` loop
already used. No new flag, field, or cross-field check. The leg_rows notional at
`store.py:2004` was switched to `_num_or_none` too (was
`None if ... else _num(...)`), so both loops share one parser.
`test_aggregate_positions_fill_null_avg_price_excluded_and_flagged` (missing →
excluded + flagged) and `test_aggregate_positions_fill_real_zero_avg_price_contributes_zero`
(real `"0"` → contributes 0) are the paired cases.

**D3 — S3, the root (`store.py:292 _num`, `store.py:304 _num_or_none`).** `_num`'s
docstring now restricts it to quantity and comparison callers. A new sibling
`_num_or_none` preserves the unknown — `None → None`, unparseable → `None`,
never `Decimal(0)` — and is used at every money-figure site. `_num` itself is
unchanged for the quantity/comparison callers (D3 forbids rewriting them).

**D4 — dedup (`store.py:1351 _leg_row_to_exposure_input`, `store.py:1374 _exposure_from_legs`).**
The hand copy of `domain.build_leg_exposure` is deleted. A small static adapter
maps the two `sqlite3.Row` leg rows onto the dict shape the domain function
expects (`order_id`/`filled_qty`/`avg_price`) and calls `D.build_leg_exposure`.
The adapter computes `avg_price = quote/base`, identical to the deleted copy's
`price = str(quote/base)`, so every currently-passing case is unchanged except
S1's `price` (now `None` for unknown quote). A `NULL` `cumulative_base_qty` is
fed through `_num` → `Decimal(0)` → `"0"`, never `"None"`. The `domain.build_leg_exposure`
contract (`domain.py:1017-1053`) was **not** changed; `domain.py` is forbidden and
was not touched. The stricter `ts_us <= 0` raise (T5 backstop, new on the
reconcile path) is covered by `test_exposure_from_legs_non_positive_ts_raises`.

**D5 — tripwire (`backend/tests/test_hedge_purity.py`).** A pure function
`find_money_zero_defaults(source, path)` returns `(line_number, matched_text, reason)`
tuples. Scope: every `.py` under `backend/hedge_open_tasks/` plus
`backend/services/live_hedge_executor.py` (r4's layer, previously excluded). Two
detections: (Python) a money identifier assigned from, or a dict entry keyed by
one whose value contains, `_num(` / `_decimal_str(` without a safe marker
(`default=None` / `or "0"` / `.get(...,"0")`); (SQL) a `'0'` literal inside an
`INSERT INTO`/`UPDATE` whose column list names a money column. Money identifiers:
`price`, `avg_price`, `notional`, `quote`, `cumulative_quote_amt`,
`cumulative_quote`, and any name ending `_notional`/`_avg_price`/`_quote`.
Quantity (`filled_qty`/`cumulative_base_qty`/`base_qty`/`executed_qty`/`qty`) is
explicitly not money. Allow-list: exactly one format, a trailing
`# money-zero-ok: <reason>`; the guard also asserts every marker still sits on a
line its own detector flags (raw), so a marker cannot widen into a blanket
exemption.

The three required meta-tests, all permanent (not a manual probe):

- (a) `test_detector_flags_python_coercion_into_avg_price` — Python coercion
  into `avg_price` is flagged.
- (b) `test_detector_flags_sql_insert_seeding_money_column_with_zero` — a SQL
  `INSERT` seeding a money column with `'0'` is flagged.
- (c) `test_detector_flags_money_coercion_in_executor_scope` — a `_decimal_str`
  money coercion in `live_hedge_executor.py`'s scope is flagged.
- negatives: `test_detector_does_not_flag_quantity_default`,
  `test_detector_does_not_flag_allowlisted_or_safe_line`.
- tree guards: `test_no_unmarked_money_zero_coercion_in_tree`,
  `test_every_money_zero_ok_marker_sits_on_a_flagged_line`.

**Which historical rounds this guard would have caught.** r4 (wire coercion in
`live_hedge_executor` — `_decimal_str` into a money field), r6 (API projection —
`_num` into a money field in a list/projection), r7 (the store exposure copy —
`_num` on a `NULL` quote, i.e. S1), and S4 (the seeded SQL `'0'` in
`prepare_attempt`). It **cannot** catch r5 — whose defect was a migration
*over-nulling a real exchange `'0'`*; no static pattern can tell a fabricated
zero from a real one at rest. r5 is covered only by the paired regressions below
(one missing-figure case + one real `"0"` case at every site). That claim is not
inflated.

**D6 — implicit-migration guard (`store.py:322`, `store.py:350`, `store.py:468`).**
M2's `leg_exposure.ts` `1970 → real timestamp` UPDATE is moved behind an explicit
`repair_legacy_exposure_ts: bool = False` argument; `__init__` passes it through
to `_migrate`, and the M2 block now runs only `if repair_legacy_exposure_ts:`.
DDL stays automatic and ungated. No production caller passes the flag — M2 has
already been applied. `test_default_construction_leaves_legacy_exposure_ts_untouched`
proves a repairable row survives a default construction unchanged. **M1 was
deleted at `95ac1a5` and was not recreated, restored, or reimplemented.**

Accuracy, stated plainly (pass criterion 6): **D6 buys "no semantic row rewrite
on default construction". It does NOT buy "never writes the database file"** —
additive DDL (`ALTER TABLE … ADD COLUMN`) still runs at construction and still
writes. The `hedge_open_leg` rebuild (`CREATE new / INSERT SELECT / DROP / RENAME`)
is separately guarded by the existing `PRAGMA table_info` probe and no-ops on an
already-migrated database; that guard was left exactly as it was.

**D7 — S4, the seeded zero (`store.py:774`, `store.py:791`).** Both PREPARED-leg
INSERTs in `prepare_attempt` now seed `NULL` for `cumulative_quote_amt` (was the
SQL literal `'0'`). The `'0'` that remains on each line seeds
`cumulative_base_qty` only — quantity, `TEXT NOT NULL DEFAULT '0'`, ruled out by
non-goal §3 — and each carries a `# money-zero-ok:` marker so D5's blunt SQL rule
treats it as justified. `test_prepare_attempt_seeds_unknown_quote_not_zero` (a
fresh PREPARED leg has `cumulative_quote_amt is None`) and
`test_inflight_leg_projects_unknown_notional_not_zero` (a dispatched leg, real
`order_id`, `exchange_status = NEW`, not yet resolved, projects an unknown
notional, not zero) cover the live consequence.

## Acceptance — raw output (both commands, pasted verbatim)

Command 1 (the focused six):

```text
$ python3 -m pytest backend/tests/test_hedge_store.py backend/tests/test_hedge_purity.py backend/tests/test_hedge_service.py backend/tests/test_hedge_domain.py backend/tests/test_hedge_api.py backend/tests/test_hedge_task_local.py -q
........................................................................ [ 27%]
........................................................................ [ 54%]
........................................................................ [ 82%]
...............................................                          [100%]
263 passed in 20.71s
```

Command 2 (the full suite):

```text
$ python3 -m pytest backend/tests -q
........................................................................ [  6%]
........................................................................ [ 13%]
........................................................................ [ 19%]
........................................................................ [ 26%]
........................................................................ [ 33%]
........................................................................ [ 39%]
........................................................................ [ 46%]
........................................................................ [ 52%]
................................................................________ [ 59%]
........................................................................ [ 66%]
........................................................................ [ 72%]
........................................................................ [ 79%]
........................................................................ [ 86%]
........................................................................ [ 92%]
........................................................................ [ 99%]
.......                                                                  [100%]
1087 passed in 57.61s
```

Both green. Baseline was 1071; 1087 = 1071 + 16 new tests (9 in
`test_hedge_store.py`, 7 in `test_hedge_purity.py`). No lower total, no failure.

## `_num(` classification (pass criterion 3)

```text
$ grep -n "_num(" backend/hedge_open_tasks/store.py
292:def _num(value) -> Decimal:
836:        filled_qty = _num(leg_outcome.get("filled_qty"))
1364:        base = _num(base_raw)  # quantity: _num is correct (NULL -> Decimal(0) guard)
1970:                q = _num(row["spot_filled_qty"])
1982:                q = _num(row["perp_filled_qty"])
1995:            if _num(row["cumulative_base_qty"]) <= 0:
1998:            q = _num(row["cumulative_base_qty"])
```

| line | caller | class |
|---|---|---|
| 292 | `def _num` | definition (docstring now limits to qty/comparison) |
| 836 | `filled_qty` | **quantity** |
| 1364 | `base = _num(base_raw)` (adapter, `cumulative_base_qty`) | **quantity** (commented) |
| 1970 | `q = _num(spot_filled_qty)` | **quantity** |
| 1982 | `q = _num(perp_filled_qty)` | **quantity** |
| 1995 | `if _num(cumulative_base_qty) <= 0` | **comparison** (quantity) |
| 1998 | `q = _num(cumulative_base_qty)` | **quantity** |

Every remaining `_num(` caller is a quantity or a comparison — **no money caller
left**. Money sites use `_num_or_none` (`_leg_row_to_exposure_input:1365`, the
fill_rows loop `1976/1984`, leg_rows notional `2004`). `_num_or_none(` does not
match the `_num(` grep and is the money-safe path.

## Paired regressions (pass criterion 2 — the r5 cover D5 cannot reach)

| site | missing figure | real exchange `"0"` |
|---|---|---|
| D1 | `…_null_quote_is_unknown_not_zero_price` (price None) | `…_real_zero_quote_is_zero_price` (price 0) + `…_real_figure_price_is_quote_over_base` (quote/base) |
| D2 | `…_fill_null_avg_price_excluded_and_flagged` | `…_fill_real_zero_avg_price_contributes_zero` |
| D7 | `test_prepare_attempt_seeds_unknown_quote_not_zero` + `test_inflight_leg_projects_unknown_notional_not_zero` | (the `'0'` qty seed is kept; only the money column moved to NULL) |
| D6 | `test_default_construction_leaves_legacy_exposure_ts_untouched` | — |
| D4 | `test_exposure_from_legs_non_positive_ts_raises` (new `ts_us<=0` failure mode) | — |

All deterministic, temp-SQLite only, no clock or network dependence.

## File boundary (pass criterion 5)

`git status --short` shows nothing outside Allowed Files. (Filled after the
status flip and result write — see the live output appended below.) Only these
files were modified or created:

- `backend/hedge_open_tasks/store.py` (modified)
- `backend/tests/test_hedge_store.py` (modified)
- `backend/tests/test_hedge_purity.py` (modified)
- `reports/agent-runs/2026-07-unknown-not-zero-v1/20-task1-glm-result.md` (created)
- `reports/agent-runs/2026-07-unknown-not-zero-v1/status.json` — the single allowed
  carve-out: `current_task.state` `dispatched` → `reported`, nothing else
  (`revision`, `next`, `delivery_sha`, `base_sha`, `ledger_sha` untouched)

Forbidden files were not touched: `domain.py`, `service.py`, `executor.py`,
`backend/services/**`, `frontend/**`, `schemas/**`, `scripts/**`, `docs/**`,
`AGENTS.md`, `agents/**`, `data/**`, `PROJECT_STATE.md`, `ACTIVE.json`. The
`domain.build_leg_exposure` contract was not changed; `cumulative_base_qty`'s `'0'`
seed was not changed.

### live `git status --short` / log after the flip

```text
$ git status --short
 M reports/agent-runs/2026-07-unknown-not-zero-v1/status.json
?? reports/agent-runs/2026-07-unknown-not-zero-v1/20-task1-glm-result.md

$ git log --oneline -4
6c250f4 task1-unknown-not-zero: close the money-zero family (D1-D7)
c4ca4f4 docs: harness v2 trial findings from the first live stage
6471873 bookkeeper: task0 plan review REWORK verified, plan and task1 packet revised (revision 4)
4cdc01b bookkeeper: dispatch task0 plan review to codex (revision 3)
```

Implementation landed in `6c250f4`. The only uncommitted entries are the result
file (created) and the `status.json` state flip (the allowed carve-out). Nothing
outside the allowed set. Note: `base_sha` (`ac8d493`) .. `delivery_sha` (`6c250f4`)
spans this stage's bookkeeping commits plus one unrelated `docs:` commit — not a
clean implementation-only range (the `base_sha` anti-self-reference caveat in
`roles.md`); the review packet should say so.

## Safety kernel §3

- No network access, no credentials, no service start/stop.
- No read or write of any kind against `data/**`.
- M1 (deleted at `95ac1a5`) was not recreated, restored, or reimplemented. Only
  M2 exists; it is now opt-in.
- Committed on `stage/2026-07-unknown-not-zero-v1`; `main` was not touched; no
  merge.

```text
[TASK_RESULT v2]
任务 ID: task1-unknown-not-zero
执行结果: completed（完成）
结果摘要: 一次过关闭「缺失交易数值变 0」缺陷族（D1–D7）：未知金钱数值各处保 None、真实交易所 "0" 仍记零；腿位暴露规则合并为一份（store 委托 domain）；money-zero 静态触发器 + 3 个 meta-test 上线；行变更迁移 M2 改为 opt-in 默认 off。全套 1087 passed（基线 1071 + 16），无文件越界，无网络/凭证/data 活动。
产物: [backend/hedge_open_tasks/store.py, backend/tests/test_hedge_store.py, backend/tests/test_hedge_purity.py, reports/agent-runs/2026-07-unknown-not-zero-v1/20-task1-glm-result.md]
检查结果: [聚焦六文件 263 passed、全套 1087 passed（基线 1071+16）；grep "_num(" store.py 全为数量/比较/定义，无 money caller；D5 覆盖 r4/r6/r7/S4、不含 r5（仅靠每站点「缺失值 + 真实 '0'」配对回归兜底）；D6 防默认构造语义行重写、不防所有写（additive DDL 仍写）；git status 仅触及允许文件、未碰 forbidden；domain.build_leg_exposure 契约未改、M1 未重建、cumulative_base_qty '0' seed 未改；status.json 仅 current_task.state dispatched→reported，其余字段未动]
阻塞项: none
本地北京时间: 2026-07-30 14:11:49 CST
下一步模型: opus5（记账人，Human 转交结果）
下一步任务: 证据 reports/agent-runs/2026-07-unknown-not-zero-v1/20-task1-glm-result.md；状态 current_task.state dispatched→reported（delivery_sha 6c250f4）；先由 Bookkeeper（opus5）核对 base_sha..delivery_sha 范围与文件边界，再交 review-1（Kimi 优先，Grok 4.5 兜底）；review-2 终审模型待 Human 决策（roles.md §125：Opus5 兼任 Planner/记账人，倾向未参与规划者）。
[/TASK_RESULT]
```
