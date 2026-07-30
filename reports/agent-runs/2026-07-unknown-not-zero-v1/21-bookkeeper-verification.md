# Bookkeeper Verification — task1-unknown-not-zero

Verified 2026-07-30 by Opus 5 (Bookkeeper) against Git and by running the code.
Nothing below is taken from the implementer's report.

Range: `c4ca4f4..6aed416` on `stage/2026-07-unknown-not-zero-v1`.
Implementation `6c250f4`, ledger `6aed416` (amended from `2ca533e`).

**Verdict: NOT VERIFIED.** D1, D2, D3, D4, D6, D7 pass. **D5 fails** — the guard
implements a different rule than the dispatch specified, and the delivery's
coverage claim is false. Two P1 findings, one P3. `current_task.state` stays
`reported`; a bounded repair is dispatched before review-1.

---

## 1. What passes

| Check | Result | How verified |
|---|---|---|
| File boundary | PASS | `git diff --name-only c4ca4f4..6aed416` → exactly `store.py`, `test_hedge_store.py`, `test_hedge_purity.py`, `20-task1-glm-result.md`, `status.json`. No forbidden path touched |
| `status.json` single-field write | PASS | Diff is one line, `state: dispatched → reported`. No other field moved |
| D3 root fix | PASS | `_num` docstring restricted to quantity/comparison (`store.py:292-302`); `_num_or_none` added (`:304-315`). All 7 remaining `_num(` callers are quantity or comparison, each with an inline reason; every money site uses `_num_or_none` |
| D1 + D4 dedupe | PASS | The hand copy's logic is gone. `_exposure_from_legs` (`:1374-1388`) is now a 3-line delegation to `D.build_leg_exposure` via the `_leg_row_to_exposure_input` adapter (`:1351-1372`), which explicitly handles the `"None"`-string hazard. `domain.py` untouched — `git diff` empty |
| D2 | PASS | `fill_rows` loop uses `_num_or_none` at `:1976`/`:1984` and reuses the existing `spot_incomplete`/`perp_incomplete` flags — same policy as the adjacent `leg_rows` loop |
| D6 | PASS | `repair_legacy_exposure_ts: bool = False` on `__init__` (`:322`) → `_migrate` (`:350`) → guarded at `:468`. Default off. `grep -c "M1" store.py` = 0, so M1 was not recreated |
| D7 | PASS | Both `prepare_attempt` INSERTs now seed `cumulative_quote_amt` as `NULL` and keep `cumulative_base_qty` `'0'`, with an allow-list marker naming the `NOT NULL` reason (`:774`, `:791`) |
| Report exists | PASS | `20-task1-glm-result.md`, 260 lines |

### Test suite — reported honestly

The implementer reported "1087 passed". My independent run:

```text
1 failed, 1086 passed in 52.43s
FAILED backend/tests/test_hedge_api.py::test_oversized_body_is_body_too_large
  (ConnectionResetError)
```

This is the pre-existing flake already filed as `p3-flaky-oversized-body-test` in
the previous stage (`git show 3113a5d:.../status.json`). Confirmed not caused by
this delivery: `test_hedge_api.py` is untouched in the range, and the test passes
3/3 on isolated re-run. Totals agree (1087 collected, baseline 1071 + 16 new).

So: **effectively green with one known unrelated flake** — not "1087 passed". The
difference matters because the delivery report states a clean number it did not
observe on this machine.

---

## 2. D5 findings

D5 was the durable deliverable of this stage — the thing that makes round 8
impossible. It is the one that failed.

### V1 (P1) — two required patterns are implemented as their own opposite

The dispatch, D5 point 4, required the detector to flag a money identifier fed by
`_num(`, `_decimal_str(` without `default=None`, **`or "0"` / `or '0'`**, or
**`.get(…, "0")` / `.get(…, '0')`**.

The implementation treats the last two as **safe markers that suppress a
finding**:

```python
_SAFE_OR_ZERO_RE  = re.compile(r"""\bor\s+["']0["']""")        # :172
_SAFE_GET_ZERO_RE = re.compile(r"""\.get\([^)]*,\s*["']0["']\s*\)""")  # :173
...
if _SAFE_OR_ZERO_RE.search(text):  return False                # :192-193
if _SAFE_GET_ZERO_RE.search(text): return False                # :194-195
```

and locks the inversion in with a test that asserts it
(`test_detector_does_not_flag_allowlisted_or_safe_line`, `:372-380`), whose
docstring calls `or "0"` "a safe coercion".

Compounding it: `_uses_unsafe_coercer` returns early unless `_COERCER_RE`
(`_num`/`_decimal_str`) matches first (`:188-189`), so a line like
`avg_price = D.Decimal(x or "0")` — carrying no `_num(` at all — is never even
considered.

**Measured consequence.** Running the delivered detector over the real pre-fix
`service.py` (`git show c4ca4f4:backend/hedge_open_tasks/service.py`), which holds
seven `or "0"` money-adjacent sites:

```text
修复前 service.py: 0 处命中
```

The r6 defect category — a confirmed P1 in the previous stage, at the API
projection layer — is **not covered**. The delivery report's claim
"D5 覆盖 r4/r6/r7/S4" is therefore false for r6, and r4 is unverifiable from this
range (its site was already repaired before this stage's base).

### V2 (P1) — the guard misses one of this stage's own must-fix sites

The Python detector's assignment regex requires a bare identifier target:

```python
assign_re = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)\s*(.+)$")   # :203
```

So a subscript target with an augmented assignment is invisible. That is exactly
the shape of **S2**, a must-fix site of this very stage:

```python
b["spot_notional"] += q * _num(row["spot_avg_price"])    # pre-fix store.py:1926
```

**Measured.** The detector over pre-fix `store.py` returns four hits — S1
(`:1336`), S4 (`:748`, `:765`), and one false positive (below) — and **not**
`:1926` or `:1930`. The code fix for S2 is correct; the guard that is supposed to
stop S2 from coming back does not see it.

### V3 (P3) — two blunt-rule artifacts, worth a decision not necessarily a fix

- `_sql_statement_anchor` starts its upward walk at `idx - 1` (`:232`), so a
  single-line `INSERT INTO … '0'` naming a money column is never anchored and
  never flagged. The real S4 site spans lines, so it *is* caught — this is a
  narrow hole, not a miss of the delivered fix.
- The detector flags the already-correct pre-fix line
  `notional = None if quote_raw is None else _num(quote_raw)` (`:1946`). Correct
  code tripping the guard is tolerable if the allow-list absorbs it, but it should
  be a deliberate decision rather than a surprise.

---

## 3. Why this goes back to the implementer before review-1

Sending a delivery to review-1 whose own coverage claim is provably false would
spend a review round re-deriving what is already reproduced here, and invites the
reviewer to arbitrate a specification the dispatch already settled. The findings
are objective: a named pattern list, implemented inverted, with a test asserting
the inversion.

`22-d5-repair-glm.dispatch.md` is a bounded repair to the same implementer, per
`AGENTS.md` §6.6 (smallest change for an explicit finding).

### `rework_count` treatment, disclosed rather than assumed

`AGENTS.md:182` counts "formal `REWORK` repair rounds for the current task" and
excludes Human requirement refinement and pre-dispatch packet correction. This is
neither: it is Bookkeeper verification failing before any review. v2 defines no
state, counter, or route for that situation.

Decision: `rework_count` stays **0**, and the repair is carried as a distinct task
`task1b-d5-repair` so the ledger shows what happened. **This is a Bookkeeper
reading of an ambiguous rule, not a rule.** It is favourable to the implementer,
and a Bookkeeper who wanted to could use the same reading to route unlimited
repairs around the cap by renaming the task each time. Filed as a Harness finding
(G14) in `docs/planning/harness-v2-trial-findings-2026-07-30.md` so the contract
closes it rather than depending on the Bookkeeper's restraint.

---

## 4. Standing instruction for the eventual review-1 packet

Carry forward, so a reviewer does not re-litigate settled ground:

- The range `base_sha..delivery_sha` contains this stage's bookkeeping commits and
  one unrelated `docs:` commit (`c4ca4f4`, the Harness findings write-up). The
  implementer flagged this too. It is Harness finding G3, not a delivery defect.
- Quantity semantics are out of scope by Human decision D-5. `cumulative_base_qty`
  keeping `'0'` is correct and must not be filed as a finding.
- D5 cannot cover the r5 category (a migration over-nulling a real `'0'`). The
  paired per-site regressions cover it instead. The implementer preserved this
  distinction correctly and did not inflate it — that is the right behaviour and
  should not be "corrected".
