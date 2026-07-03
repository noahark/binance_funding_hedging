# Fix Report

## Fix Implementer

- Model: `grok-composer-2.5-fast` (xai)
- Skill: `minimal_change_engineer`
- Adapter: Grok CLI (write_code)

## Findings Addressed

### P1 — Planning preview over-allocates base quantity after min-notional correction

- **Root cause:** `round_count` was derived from the pre-bump `effective_base`, but each round was later bumped by one coarser step when post-rounding notionals failed min filters. That mismatch let the loop allocate more base quantity than `total_base_quantity`.
- **Fix (`backend/domain/planning.py`):**
  - Added `_bump_qty_for_min_notional()` helper to apply the per-step notional bump once, up front.
  - Compute `actual_per_round` from `effective_base` via that helper, then derive `round_count` from `actual_per_round` (not the un-bumped value).
  - Removed the in-loop bump that could inflate each round without shrinking `round_count`.
  - Existing remainder-merge path unchanged: a sub-minimum final sliver merges into the previous round instead of exceeding the total.
- **Rationale:** Recalculating round count from the true per-round quantity preserves the invariant `sum(round.base_quantity) <= total_base_quantity`; merge handles the trailing sliver.

### P2 — Planning tests did not assert AC-08 invariants

- **Fix (`backend/tests/test_planning.py`):** Added five deterministic tests covering the P1 repro, total-allocation preservation across cases, exact recalculated round count, both-leg post-rounding notional validation, and remainder-merge behavior.
- **Rationale:** The P1 repro now fails the suite if reintroduced; allocation and notional invariants are explicitly asserted.

### UI planning preview duplicated buggy math

- **Fix (`prototypes/fake-ui/index.html`):** Updated `planRounds()` to mirror the corrected backend flow — compute `actualPerRound` after the notional bump, recalculate `roundCount` from it, and use `Math.max(correctedMin/futPrice, correctedMin/spotPrice)` for min-base (matching backend `_min_base_for_notional`). No backend-precomputed planning JSON exists in the loaded fixture, so client-side math was corrected in place while preserving SIMULATION ONLY semantics.
- **Rationale:** Prevents UI drift from the fixed planner without expanding file scope.

## File Changes Summary

| File | Change |
|------|--------|
| `backend/domain/planning.py` | `_bump_qty_for_min_notional`; `actual_per_round` + recalculated `round_count`; removed in-loop bump |
| `backend/tests/test_planning.py` | `_allocated_base` helper; 5 new AC-08 invariant tests |
| `prototypes/fake-ui/index.html` | `planRounds()` aligned to corrected planner logic |

## New Tests Added

1. `test_low_total_high_rounds_no_over_allocation` — P1 repro (`0.005` total, 10 requested rounds → 2 rounds `0.002`+`0.003`, sum == total).
2. `test_total_allocated_base_preserved` — allocation equals total for `1.0`, `0.05`, `0.01`, `0.005` cases.
3. `test_recalculated_round_count_after_min_notional_bump` — exact `round_count == 2` for P1 repro.
4. `test_both_leg_post_rounding_notional_validation` — every round's fut/spot notional ≥ 100.
5. `test_remainder_merge_stays_within_total` — `remainder_merged` true, merged round `0.003`, total preserved.

## Tests Run

Commands executed locally by the fix implementer:

```text
$ .venv/bin/python -m pytest backend/tests -q
...............................                                          [100%]
31 passed in 0.04s

$ .venv/bin/python -m ruff check backend
All checks passed!

$ .venv/bin/python -m mypy backend
Success: no issues found in 18 source files
```

P1 repro verification (post-fix):

```text
$ .venv/bin/python -c "
from decimal import Decimal
from backend.domain.planning import plan_hedge_rounds
p = plan_hedge_rounds(
    total_base_quantity=Decimal('0.005'),
    futures_price=Decimal('60000'), spot_price=Decimal('60000'),
    futures_min_notional=Decimal('100'), spot_min_notional=Decimal('100'),
    futures_step_size=Decimal('0.001'), spot_step_size=Decimal('0.001'),
    requested_rounds=10,
)
alloc = sum(Decimal(r.base_quantity) for r in p.rounds)
assert alloc <= Decimal('0.005'), alloc
print('P1 repro OK: alloc=', alloc)
"
P1 repro OK: alloc= 0.005
```

## Remaining Findings

- None

---

## Round 2

### Findings Addressed

#### P1 — Final round can violate one leg's own min notional (asymmetric legs)

- **Root cause:** Remainder-merge at `planning.py:149` (and `fake-ui:359`) only triggered when `max(futures_notional, spot_notional) < corrected_min`. A round where one leg met the max-based threshold but the other leg was below its own min (e.g. spot_notional=60 < 100 while futures_notional=120) was emitted as executable.
- **Fix:** Added `_leg_below_min_notional()` checking each leg against its own `futures_min_notional` / `spot_min_notional`. Final-remainder merge now fires when either leg is below its own min and a prior round exists.

#### P1b — Total too small for any min-compliant round (Case B)

- **Root cause:** When `actual_per_round > total_base_quantity` (or a sole final round is below min with no prior round to merge), the planner still emitted a below-min round with no signal.
- **Fix:** Early return when `actual_per_round > total_base_quantity`; late return when the sole below-min final round has no merge target. Both return `feasible=False`, `status="infeasible"`, `round_count=0`, empty `rounds`.

#### P2 — Tests missed asymmetric-leg and too-small-total cases

- **Fix:** Added three deterministic tests (see below) that fail on pre-round-2 code.

### New `PlanningPreview` Fields

| Field | Type | Values | Purpose |
|-------|------|--------|---------|
| `feasible` | `bool` | `True` / `False` | Whether the plan is executable under min-notional constraints |
| `status` | `str` | `"ok"` / `"infeasible"` | Explicit signal when total cannot form a min-compliant plan |

Both fields are included in `planning_preview_to_dict()` for JSON serialization. Defaults (`feasible=True`, `status="ok"`) preserve backward compatibility for feasible plans.

### File Changes Summary (Round 2)

| File | Change |
|------|--------|
| `backend/domain/planning.py` | `_leg_below_min_notional()`; per-leg remainder-merge; early/late infeasible returns; `feasible` + `status` on `PlanningPreview` and `planning_preview_to_dict()` |
| `backend/tests/test_planning.py` | 3 new tests: asymmetric prices (Case A), too-small total (Case B), asymmetric coarser-step remainder merge |
| `prototypes/fake-ui/index.html` | `legBelowMin()` helper; per-leg merge; early infeasible guard; status/feasible display in plan preview |

### New Tests Added (Round 2)

1. `test_asymmetric_prices_final_round_merges_per_leg_min` — Case A (`fut=120000, spot=60000, total=0.005`): no round violates either leg's min; remainder merged.
2. `test_total_below_single_min_compliant_round_infeasible` — Case B (`total=0.001`): `feasible=False`, `status="infeasible"`, zero rounds.
3. `test_asymmetric_coarser_step_remainder_merge` — `spot_step=0.002`, `spot_min=150`, asymmetric prices: coarser-step remainder merges, both legs meet mins.

### Tests Run (Round 2)

Commands executed locally by the fix implementer:

```text
$ .venv/bin/python -m pytest backend/tests -q
..................................                                       [100%]
34 passed in 0.04s

$ .venv/bin/python -m ruff check backend
All checks passed!

$ .venv/bin/python -m mypy backend
Success: no issues found in 18 source files
```

Reproduction verification (post-fix):

```text
$ .venv/bin/python -c "
from decimal import Decimal
from backend.domain.planning import plan_hedge_rounds

# Case A: asymmetric prices
p = plan_hedge_rounds(total_base_quantity=Decimal('0.005'), requested_rounds=10,
    futures_price=Decimal('120000'), spot_price=Decimal('60000'),
    futures_min_notional=Decimal('100'), spot_min_notional=Decimal('100'),
    futures_step_size=Decimal('0.001'), spot_step_size=Decimal('0.001'))
print('Case A:', [(r.base_quantity, r.futures_notional, r.spot_notional) for r in p.rounds])
print('  feasible:', p.feasible, 'merged:', p.remainder_merged)

# Case B: total too small
p2 = plan_hedge_rounds(total_base_quantity=Decimal('0.001'), requested_rounds=1,
    futures_price=Decimal('60000'), spot_price=Decimal('60000'),
    futures_min_notional=Decimal('100'), spot_min_notional=Decimal('100'),
    futures_step_size=Decimal('0.001'), spot_step_size=Decimal('0.001'))
print('Case B:', p2.feasible, p2.status, p2.rounds)

# Round 1 invariant preserved
p3 = plan_hedge_rounds(total_base_quantity=Decimal('0.005'), requested_rounds=10,
    futures_price=Decimal('60000'), spot_price=Decimal('60000'),
    futures_min_notional=Decimal('100'), spot_min_notional=Decimal('100'),
    futures_step_size=Decimal('0.001'), spot_step_size=Decimal('0.001'))
alloc = sum(Decimal(r.base_quantity) for r in p3.rounds)
print('Round1 invariant:', alloc, [r.base_quantity for r in p3.rounds])
"
Case A: [('0.002', '240.000', '120.000'), ('0.003', '360.000', '180.000')]
  feasible: True merged: True
Case B: False infeasible []
Round1 invariant: 0.005 ['0.002', '0.003']
```

### Remaining Findings (Round 2)

- None