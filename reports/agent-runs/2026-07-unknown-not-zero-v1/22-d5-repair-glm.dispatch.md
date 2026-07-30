# Dispatch — task1b-d5-repair

```text
Identity:
  task_id:         task1b-d5-repair
  target_role:     Implementer
  target_model:    claude_glm
  provider:        zhipu_glm
  status_revision: 5
  required_skill:  agents/skills/minimal-change-engineer.md
```

Bounded repair of two P1 findings from Bookkeeper verification
(`21-bookkeeper-verification.md`). D1, D2, D3, D4, D6, D7 all passed and are **not
in scope** — do not touch them. This is a repair skill task, not an
implementation task: smallest change that removes the findings.

`rework_count` is 0 and stays 0 (Bookkeeper reading, disclosed in
`21-bookkeeper-verification.md` §3). Your review budget is intact.

## Goal

D5's guard implements a different rule than the dispatch specified, so it does not
catch two of the four defect categories it is credited with. Both findings are
reproduced, with commands, in `21-bookkeeper-verification.md` §2.

**R1 — stop treating `or "0"` and `.get(…, "0")` as safe.**

`10-unknown-not-zero-glm.dispatch.md` D5 point 4 lists five constructs to **flag**:
`_num(`, `_decimal_str(` without `default=None`, `or "0"`, `or '0'`,
`.get(…, "0")`, `.get(…, '0')`. The delivery implements the last two as safe
markers that *suppress* a finding (`test_hedge_purity.py:172-173`, `:192-195`) and
asserts that behaviour in a test (`:372-380`).

Required:
- A money identifier fed by `or "0"` / `or '0'` / `.get(…, "0")` / `.get(…, '0')`
  must be flagged, whether or not `_num(`/`_decimal_str(` also appears on the line.
  Today `_uses_unsafe_coercer` returns early unless a coercer matches first
  (`:188-189`), so `avg_price = D.Decimal(x or "0")` is invisible — that must
  change.
- `default=None` stays the one genuine safe marker. Keep it.
- Fix `test_detector_does_not_flag_allowlisted_or_safe_line` accordingly: an
  allow-listed line and `_decimal_str(v, default=None)` stay unflagged;
  `quote = _num(q) or "0"` must now be **flagged**, not exempt.
- Acceptance evidence: running the detector over
  `git show c4ca4f4:backend/hedge_open_tasks/service.py` must report the `or "0"`
  money sites it currently misses (measured today: 0 hits). Paste the count and
  the flagged lines into your report.

**R2 — cover the subscript / augmented-assignment shape.**

`assign_re` (`:203`) requires a bare identifier target, so
`b["spot_notional"] += q * _num(row["spot_avg_price"])` — the exact shape of **S2,
a must-fix site of this stage** — is never seen.

Required:
- Detect a money-named subscript or attribute target, and augmented assignment
  (`+=`, `-=`, `*=`, `/=`), not only plain `name =`.
- Acceptance evidence: running the detector over
  `git show c4ca4f4:backend/hedge_open_tasks/store.py` must flag lines 1926 and
  1930 in addition to the sites it already flags. Paste the hit list.

**R3 — decide V3 explicitly; a reasoned "leave it" is a complete answer.**

Two blunt-rule artifacts, both P3:
- `_sql_statement_anchor` starts at `idx - 1` (`:232`), so a single-line
  `INSERT INTO … '0'` naming a money column is never anchored.
- The detector flags the already-correct
  `notional = None if quote_raw is None else _num(quote_raw)` (pre-fix
  `store.py:1946`).

Fix either, both, or neither — but state the decision and the reason in your
report. Do not silently leave them unaddressed. If you fix the false positive, do
not do it by widening the safe-marker set that R1 just narrowed.

## Allowed Files

Modify only:

- `backend/tests/test_hedge_purity.py`
- `backend/hedge_open_tasks/store.py` — **only** if R1/R2's widened detector now
  flags a real line that needs an allow-list marker with a reason. Not for logic
  changes. Any product-logic edit here is a scope violation.
- `reports/agent-runs/2026-07-unknown-not-zero-v1/23-task1b-glm-result.md` (create)

Forbidden: everything else, explicitly including
`backend/hedge_open_tasks/domain.py`, `service.py`, `executor.py`,
`backend/services/**`, `backend/tests/test_hedge_store.py` (task1's regressions are
correct — leave them), `frontend/**`, `schemas/**`, `scripts/**`, `docs/**`,
`AGENTS.md`, `agents/**`, `data/**`, `PROJECT_STATE.md`, `ACTIVE.json`.

Carve-out: in this stage's `status.json` you may write only
`current_task.state`, `dispatched` → `reported`.

No network, no credentials, no service control, no write to `data/**`.

Commit on `stage/2026-07-unknown-not-zero-v1` (already checked out). Do not merge.

## Inputs

| Path | Range | Why |
|---|---|---|
| `reports/agent-runs/2026-07-unknown-not-zero-v1/21-bookkeeper-verification.md` | §2 and §3 | The findings, with reproduction commands. Highest authority for this task |
| `reports/agent-runs/2026-07-unknown-not-zero-v1/10-unknown-not-zero-glm.dispatch.md` | D5 only | The five patterns you must match |
| `backend/tests/test_hedge_purity.py` | `160-400` | The detector and its tests |
| `agents/skills/minimal-change-engineer.md` | whole | The one named skill |

Do not re-read the plan, the plan review, or the task1 result report. The findings
are self-contained.

## Acceptance Checks

```text
python3 -m pytest backend/tests/test_hedge_purity.py backend/tests/test_hedge_store.py -q
python3 -m pytest backend/tests -q
```

Pass conditions:

1. Both green. Full-suite total must be ≥ 1087 collected. **Note**:
   `test_hedge_api.py::test_oversized_body_is_body_too_large` is a known
   pre-existing flake (`p3-flaky-oversized-body-test`) that fails intermittently
   with `ConnectionResetError` and passes on isolated re-run. If it fails, re-run
   it alone and report both results. It is not yours to fix.
2. R1 evidence: the detector's hit list over pre-fix `service.py`, non-empty.
3. R2 evidence: the detector's hit list over pre-fix `store.py`, including 1926
   and 1930.
4. The current tree still passes its own guard — `test_no_unmarked_money_zero_coercion_in_tree`
   green. If the widened rule flags a real current line, add an allow-list marker
   with a reason; do not weaken the rule to make the tree pass.
5. R3 decision stated.
6. `git status --short` shows no file outside Allowed Files.

## Stop

Stop after code, tests, commit, and `23-task1b-glm-result.md`. Flip
`current_task.state` to `reported` and nothing else.

Return the `[TASK_RESULT v2]` block from `AGENTS.md` §7 using **only** its nine
mandated Chinese labels — 任务 ID / 执行结果 / 结果摘要 / 产物 / 检查结果 /
阻塞项 / 本地北京时间 / 下一步模型 / 下一步任务 — closing with `[/TASK_RESULT]`.
Do not add `model`, `provider`, `status_revision`, `delivery_sha`, `branch`,
`summary`, `notes`, `handoff_model`, or any other invented field; do not copy the
Identity block into the result; do not write `[/TASK_RESULT v2]`. The first
delivery of task1 did all of these and had to be redone.

`下一步模型: opus5（记账人，Human 转交结果）`.
