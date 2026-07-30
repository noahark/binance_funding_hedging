# Task Result — task1b-d5-repair

Bounded repair of the two D5 P1 findings (R1, R2) plus the R3 P3 decision, from
`21-bookkeeper-verification.md`. Implementation is commit `851dd08` on
`stage/2026-07-unknown-not-zero-v1`; this report plus the `status.json` state
flip form a separate ledger commit on the same branch. The dispatch's input
metadata (`task_id` / `model` / `provider` / `status_revision` / `required_skill`)
is not repeated here as result fields — the `[TASK_RESULT v2]` block uses only
`AGENTS.md §7`'s nine mandated labels.

Only `backend/tests/test_hedge_purity.py` changed. `store.py` was **not** touched:
the widened rule flags no live line in the current tree (see §4). Full suite
**1090 passed** (baseline 1087 + 3 new tests), no flake this run.

## R1 (P1) — `or "0"` / `.get(…, "0")` now flag; `default=None` is the only safe marker

**Code.** `_uses_unsafe_coercer` rewritten (`test_hedge_purity.py`):

- `_SAFE_DEFAULT_RE` (`default=None`) stays the **one** genuine keep-unknown
  marker — a hit there returns `False`.
- Otherwise the RHS is unsafe if **any** of `_COERCER_RE` (`_num(` / `_decimal_str(`),
  `_OR_ZERO_RE` (`or "0"` / `or '0'`), or `_GET_ZERO_RE` (`.get(…, "0")` /
  `.get(…, '0')`) matches. `_COERCER_RE` no longer gates the others, so
  `avg_price = D.Decimal(x or "0")` — no `_num(` at all — is now seen.
- The old `_SAFE_OR_ZERO_RE` / `_SAFE_GET_ZERO_RE` suppressors are deleted.

**Test.** `test_detector_does_not_flag_allowlisted_or_safe_line` narrowed to the
two genuinely-safe forms (an allow-listed line and `_decimal_str(v, default=None)`);
the `quote = _num(q) or "0"` case moved out of it. New
`test_detector_flags_or_zero_money_coercion` asserts all four shapes flag:
`avg_price = D.Decimal(x or "0")`, `quote = _num(q) or "0"`,
`notional = d.get('cumulative_quote_amt', '0')`, `price = _decimal_str(v) or '0'`.

### R1 evidence — service.py: an honest disagreement with the dispatch's acceptance

Pass condition 2 asks for a **non-empty** hit list over
`git show c4ca4f4:backend/hedge_open_tasks/service.py`. The measured result is
**0 hits** (public and raw), and this section explains why that is correct rather
than a missed repair.

```text
$ <detector over git show c4ca4f4:backend/hedge_open_tasks/service.py>
public count = 0
raw count    = 0
```

`service.py` does hold seven `or "0"` lines, but **none of them is a money site**.
Each is `base = D.Decimal(leg.get("cumulative_base_qty") or "0")` (lines 214/284/310)
or its `spot_base`/`perp_base` variants (252/253/774/775). The target identifiers
`base` / `spot_base` / `perp_base` are **not** money names (`_is_money_name` →
`False`); the figure being defaulted is `cumulative_base_qty` — a **quantity**,
which D5 point 3 explicitly excludes from scope. A not-yet-filled leg genuinely
fills 0 base, so `or "0"` here is correct, exactly the way `cumulative_base_qty`'s
`'0'` seed is correct (non-goal §3).

The money figures in `service.py` are already handled right — `raw_quote` is read
into `quote_amt = None` / `avg = None` under an explicit `if raw_quote is None:`
guard (lines 216-224, 286-294, 312-320), each commented "NULL notional passes
through as JSON null, not "0" (review-1 r6)". That is the r6 fix, already landed
before this stage's base. There is no `_num(` / `_decimal_str(` / `or "0"` /
`.get(…, "0")` on any `price` / `avg_price` / `notional` / `quote` target in the
file for the detector to flag.

So the **r6 coverage R1 buys is real and is proven by the synthetic meta-test
above** (`test_detector_flags_or_zero_money_coercion`, the API-projection shape),
not by `service.py`. Making `service.py` non-empty would require flagging the
quantity `or "0"` lines, which contradicts D5 point 3 and would report correct
code as a defect. I did not do that. This is filed as a residual acceptance
judgment for the Bookkeeper in `[TASK_RESULT v2]`, not a blocker — the R1 code
defect (the suppressors) is fixed and demonstrated.

## R2 (P1) — subscript / attribute / augmented-assignment targets now visible

**Code.** `_find_python_money_coercions` target regex widened to a bare name,
`obj["key"]`, `obj.attr` (optionally chained), with op `=` or augmented `+=` /
`-=` / `*=` / `/=`. A target is money if **any** of its identifier tokens is a
money name, so `b["spot_notional"]` matches on the `spot_notional` token.

**Test.** New `test_detector_flags_subscript_or_attribute_augmented_money_target`
flags `b["spot_notional"] += q * _num(…)` and `self.cumulative_quote -= fee *
_decimal_str(…)`, and does **not** flag the quantity subscript `b["spot_qty"] += q`.

### R2 evidence — pre-fix store.py now includes 1926 and 1930

```text
$ <detector over git show c4ca4f4:backend/hedge_open_tasks/store.py>
public count = 6
  (1336, 'quote = _num(leg_row["cumulative_quote_amt"])',  money field 'quote')
  (1926, 'b["spot_notional"] += q * _num(row["spot_avg_price"])',  money field 'spot_notional' augmented)
  (1930, 'b["perp_notional"] += q * _num(row["perp_avg_price"])',  money field 'perp_notional' augmented)
  (1946, 'notional = None if quote_raw is None else _num(quote_raw)',  money field 'notional')   <- V3b, see R3
  (748,  '… VALUES (…, \'0\', \'0\', …)',  SQL INSERT money column + '0')   <- S4
  (765,  '… VALUES (…, \'0\', \'0\', …)',  SQL INSERT money column + '0')   <- S4
```

Lines 1926 and 1930 — **S2, this stage's own must-fix site** — are now in the hit
list (they were absent before R2). 1336/748/765 are the S1/S4 defects task1
already fixed; 1946 is the V3b false positive (next).

## R3 (P3) — decisions stated

**R3a — single-line INSERT anchor: fixed.** `_sql_statement_anchor` now starts its
walk at `idx` (the `'0'` line) instead of `idx - 1`, so a single-line
`INSERT INTO … '0'` naming a money column anchors. Verified by new
`test_detector_anchors_single_line_sql_insert`. Multi-line S4 (the real site) and
`CREATE TABLE … DEFAULT '0'` (not a string fragment, never anchored) are
unaffected — confirmed by the unchanged raw output on the current tree.

**R3b — the `notional = None if … is None else _num(…)` false positive: left
unchanged, by decision.** The line exists only in pre-fix `store.py:1946`; in the
current tree D2 replaced it with `notional = _num_or_none(quote_raw)` at `:2004`,
which the detector does not flag. Fixing the historical line would either widen
the safe-marker set (R1 just narrowed it — forbidden) or add a ternary-guard
parser for one already-corrected line. Not warranted. It surfaces as a labelled
false positive in the R2 evidence above only because that evidence deliberately
runs the detector over the pre-fix file.

## §4 — current tree still passes its own guard

```text
$ <detector over current backend/hedge_open_tasks/store.py>
public count = 0
```

The widened rule flags **no** unmarked line in the current tree. The only raw
hits are the two `# money-zero-ok:` lines in `prepare_attempt` (`store.py:774`,
`:791`) — still flagged by the raw detector, so their markers still sit on a
flagged line and `test_every_money_zero_ok_marker_sits_on_a_flagged_line` holds.
No allow-list marker was added and no rule was weakened to make the tree pass.
`store.py` was not edited.

## Acceptance — raw output (both commands, pasted verbatim)

Command 1 (purity + store):

```text
$ python3 -m pytest backend/tests/test_hedge_purity.py backend/tests/test_hedge_store.py -q
..............................................................           [100%]
62 passed in 0.41s
```

Command 2 (full suite):

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
........................................................................ [ 59%]
........................................................................ [ 66%]
........................................................................ [ 72%]
................................................................________ [ 79%]
........................................................................ [ 85%]
........................................................................ [ 92%]
........................................................................ [ 99%]
..........                                                               [100%]
1090 passed in 57.14s
```

Both green. 1090 = baseline 1087 + 3 new tests (the R1/R2/R3a meta-tests). The
known flake `test_hedge_api.py::test_oversized_body_is_body_too_large`
(`p3-flaky-oversized-body-test`) did **not** fire this run.

## File boundary (pass condition 6)

```text
$ git status --short
 M backend/tests/test_hedge_purity.py
?? reports/agent-runs/2026-07-unknown-not-zero-v1/23-task1b-glm-result.md
```

(Shown before the status flip; after the flip `status.json` joins as the single
allowed carve-out.) Only `backend/tests/test_hedge_purity.py` was modified;
`store.py` was not touched (no live line needed a marker). `23-task1b-glm-result.md`
is created. Forbidden files untouched: `domain.py`, `service.py`, `executor.py`,
`backend/services/**`, `backend/tests/test_hedge_store.py`, `frontend/**`,
`schemas/**`, `scripts/**`, `docs/**`, `AGENTS.md`, `agents/**`, `data/**`,
`PROJECT_STATE.md`, `ACTIVE.json`.

## Safety kernel §3

- No network, no credentials, no service control, no read or write of `data/**`.
- D1/D2/D3/D4/D6/D7 were not in scope and were not touched — this is a D5-only
  repair. `domain.build_leg_exposure` contract, M1 (not recreated), and
  `cumulative_base_qty`'s `'0'` seed are all unchanged.
- Committed on `stage/2026-07-unknown-not-zero-v1`; `main` not touched; no merge.

```text
[TASK_RESULT v2]
任务 ID: task1b-d5-repair
执行结果: completed（完成）
结果摘要: 有界修复 D5 两个 P1：R1 让 or "0"/.get(…,"0") 对 money 标识符 flag（default=None 仍是唯一 safe），_uses_unsafe_coercer 不再要求先命中 _num(；R2 目标支持 subscript/attribute + 增强赋值，pre-fix store.py 的 S2（1926/1930）现已可见；R3a 单行 INSERT 锚定修复、R3b 按决策留置（当前树 D2 已用 _num_or_none，假阳性不在）。当前树 public=0、marker 仍 raw-flagged。全套 1090 passed（基线 1087+3），无 flake。
产物: [backend/tests/test_hedge_purity.py, reports/agent-runs/2026-07-unknown-not-zero-v1/23-task1b-glm-result.md]
检查结果: [聚焦 purity+store 62 passed、全套 1090 passed（基线 1087+3）；R2 证据 pre-fix store.py 6 命中含 1926/1930（S2 现可见）；当前 store.py public=0、774/791 marker 仍 raw-flagged，无需加 marker、未碰 store.py；R3a 单行 INSERT 由 idx 起锚（meta-test 证明），R3b 留置并述理由；git status 仅 test_hedge_purity.py + 结果文件，未碰 forbidden；R1 代码缺陷（suppress）已修并由 4 形态合成测试证明；一处与验收的客观分歧：R1 evidence 跑 pre-fix service.py 仍 0 命中（public/raw），因其 7 处 or "0" 全作用于 cumulative_base_qty（quantity，D5 point3 排除）、目标 base/spot_base/perp_base 非 money identifier，money 字段已 if raw_quote is None 正确处理（r6 早修），令其非空需把 quantity 误标为缺陷——故留待记账人裁决，非 R1 未修]
阻塞项: none（R1/R2/R3 代码缺陷均已修并证明；service.py「non-empty」为验收 evidence 选择分歧，已客观陈述并附替代 r6 覆盖证明，留待 opus5 裁决，不阻断本任务完成）
本地北京时间: 2026-07-30 16:15:46 CST
下一步模型: opus5（记账人，Human 转交结果）
下一步任务: 证据 reports/agent-runs/2026-07-unknown-not-zero-v1/23-task1b-glm-result.md；状态 current_task.state dispatched→reported（delivery_sha 851dd08）；请 opus5 复核 base_sha..delivery_sha 范围与文件边界，并裁决一处 R1 acceptance 分歧：pre-fix service.py 仍 0 命中（其 or "0" 全为 quantity），R1 代码缺陷已由 4 形态合成测试证明修复；裁决后再定 review-1 路由。
[/TASK_RESULT]
```
