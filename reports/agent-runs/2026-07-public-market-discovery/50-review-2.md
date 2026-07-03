# Review 2

## Reviewer

- Model: `codex` (codex-cli 0.142.2)
- Skill: `reality_checker`
- Provider: `openai` (provider-level isolation from designer `anthropic` and implementer `xai`)
- Adapter: `codex exec -s read-only` (OS-enforced read-only sandbox)
- Mode: READ-ONLY. Confirmed two ways: (a) the reviewer ran only `nl` (42), `git` (10),
  `rg` (5), `wc` (2) — zero mutating commands; (b) all implementation + artifact files are
  byte-identical pre/post run (the only hash deltas were controller-authored files written
  before dispatch, measured against a stale baseline snapshot — false positives).
- Verdict collected by: controller (`claude_glm` / `zhipu_glm`).

## Reviewed Artifacts (43)

impl-code.diff, 00-task/10-design/11-adr, direction synthesis, PRD, 20-implementation,
60-test-output, 30-review-1, 70-handoff, status.json, the verdict schema, every
`backend/**/*.py` source + test + fixture, `pyproject.toml`, the UI, and the live
sample-index + its candidate-classification output.

## Findings

### P1 — Planning preview can over-allocate base quantity after min-notional correction

- `backend/domain/planning.py:87` (rounding) and the bump at `123-128`.
- The planner rounds `effective_base` DOWN to the coarser step, derives `round_count` from
  that rounded value, then bumps each notional-failing round by one step WITHOUT
  recalculating `round_count` or constraining cumulative allocation to
  `total_base_quantity`.
- **Controller-independent reproduction (model claim is not evidence — controller ran it):**

  ```
  plan_hedge_rounds(total_base_quantity=Decimal('0.005'),
                    futures_price=spot_price=Decimal('60000'),
                    futures_min_notional=spot_min_notional=Decimal('100'),
                    futures_step_size=spot_step_size=Decimal('0.001'),
                    requested_rounds=10)
  -> 4 rounds of base_quantity=0.002 each, sum = 0.008
  -> total_base_quantity stayed 0.005  =>  OVER-ALLOCATES by 0.003 (+60%)
  ```

- Impact: violates AC-08 and the PRD manual-execution rule — the preview can oversize the
  hedge instead of recalculating rounds and merging the sub-minimum remainder within the
  requested base quantity. The UI duplicates the same planning shape
  (`prototypes/fake-ui/index.html:331-363`).

### P2 — Planning tests do not assert the AC-08 invariants

- `backend/tests/test_planning.py:28`.
- Existing tests assert `corrected_min_notional` and `round_count >= 1` only; they do not
  assert total-allocation preservation, exact recalculated round count, or remainder-merge
  behavior. The P1 repro passes the current suite — so review-1's "AC-08 covered" claim was
  unfounded.

## Verdict

- **verdict: REWORK** (review-1's ACCEPT was premature)
- next_action: `fix`
- diff_fingerprint echoed: matches controller-computed value.
- findings: 2 (one P1, one P2); required_fixes: 3.

## Required Fixes (from verdict)

1. Fix `backend/domain/planning.py` so min-notional correction, coarser-step rounding,
   round-count recalculation, post-rounding notional checks, and remainder merge preserve
   a coherent base-quantity plan (sum of rounds must not exceed the requested total unless
   an explicit adjusted-total is signalled).
2. Update `prototypes/fake-ui/index.html` planning preview to match the corrected planner
   behavior (preferred: consume backend-precomputed planning values rather than recompute
   client-side, to avoid drift).
3. Strengthen `backend/tests/test_planning.py` with assertions for the failing
   low-total/high-round case, total allocated base, exact recalculated round count,
   both-leg post-rounding notional validation, and remainder-merge behavior.

## Controller Validation

- [x] JSON verdict parses and is schema-valid (`schemas/review-verdict.schema.json`):
  role=`reality_checker` (valid enum), verdict=`REWORK` (valid), next_action=`fix` (valid),
  schema_version=1, stage_id correct.
- [x] diff_fingerprint matches controller-computed value.
- [x] Reviewer read-only integrity confirmed (command audit + sandbox).
- [x] **P1 independently reproduced by the controller** — the over-allocation is real, not a
  hallucinated finding. This justifies entering the fix loop.

## Strict JSON Verdict

The final content in this file must be one JSON object matching
`schemas/review-verdict.schema.json`.

```json
{"schema_version":1,"stage_id":"2026-07-public-market-discovery","role":"reality_checker","model":"codex","verdict":"REWORK","diff_fingerprint":"d8e12dd6ce3b5dc9e63a6d81176da5f5ce0704eb:7e089ca54191545631e9e5e822508008142fb49c8c87b27b98d5edf1802cc927","reviewed_artifacts":["raw-transcripts/impl-code.diff","00-task.md","10-design.md","11-adr.md","reports/agent-runs/2026-07-initial-direction/06-direction-synthesis.md","docs/product/PRD.md","20-implementation.md","60-test-output.txt","30-review-1.md","70-handoff.md","status.json","schemas/review-verdict.schema.json","backend/**/*.py","backend/tests/fixtures/*","pyproject.toml","prototypes/fake-ui/index.html","reports/api-samples/public-market/20260702T163929Z/sample-index.json","reports/api-samples/public-market/20260702T163929Z/candidate-classification.json"],"findings":[{"severity":"P1","title":"Planning preview can over-allocate base quantity after min-notional correction","file":"backend/domain/planning.py","line":87,"evidence":"Planner rounds effective_base down to coarser step (87-93), derives round_count from rounded value (95-101), then bumps each failing round by one step (123-128) without recalculating round_count or remaining allocation. Controller repro: total_base_quantity=0.005 returned 4 rounds of 0.002 (sum 0.008) > 0.005.","impact":"Violates AC-08 + PRD manual execution rule; preview can oversize the hedge by 60%.","recommendation":"Recompute round_count from actual per-round qty after any min-notional bump; cap cumulative allocation at total_base_quantity; merge sub-min remainder."},{"severity":"P2","title":"Planning tests do not assert the invariants required by AC-08","file":"backend/tests/test_planning.py","line":28,"evidence":"Tests assert corrected_min_notional and round_count>=1 only; the P1 repro passes the current suite.","impact":"AC-08 coverage claim was unfounded.","recommendation":"Add deterministic tests for low-total/high-round, total-allocation preservation, exact round count, both-leg post-rounding notional, remainder merge."}],"required_fixes":["Fix backend/domain/planning.py so min-notional correction, coarser-step rounding, round-count recalculation, post-rounding notional checks, and remainder merge preserve a coherent base-quantity plan.","Update prototypes/fake-ui/index preview to match the corrected planner behavior or avoid duplicating planner math inaccurately.","Strengthen backend/tests/test_planning.py with assertions covering the failing low-total/high-round case, total allocated base, exact recalculated round count, both-leg notional validation after rounding, and remainder merge behavior."],"next_action":"fix"}
```

## Routing Decision

- REWORK → **fix loop** (rework_count 0 → 1; max_rework = 3, budget remaining = 3).
- Fix dispatched to original implementer `grok-composer-2.5-fast` (skill
  `minimal_change_engineer`) with codex's repro + required_fixes + controller-confirmed
  root cause.
- After fix: controller re-runs the pinned toolchain (must stay green, including new AC-08
  invariant tests), recomputes the diff fingerprint, and re-dispatches review-2 (codex,
  reality_checker) on the NEW diff to confirm resolution with no regression.
- review-1's prior ACCEPT is superseded by the changed diff + this REWORK.

## Raw Verdict (round 0)

- Raw transcript: `raw-transcripts/review-2-codex.txt`
- Extracted JSON: `raw-transcripts/review-2-verdict.json`

---

## Re-review (round 1, after fix #1) — verdict: REWORK

- Reviewer: `codex` (reality_checker), read-only sandbox `codex exec`, on the POST-FIX diff
  (fingerprint `...:9db37ac5...`).
- Read-only confirmed: codex ran only `rg` / `git` / `pwd` — zero writes.
- diff_fingerprint echoed: matches the post-fix value.
- verdict: **REWORK** (fix #1 resolved the original symmetric over-allocation but left two
  issues, both CONFIRMED by the controller's own reproduction).
- next_action: `fix` (fix round 2; rework_count 1 → 2; budget remaining 1).

### New P1 — Planner/UI can still emit a final round below ONE leg's min notional

- `backend/domain/planning.py:149` (remainder-merge condition) and `fake-ui:359`.
- The remainder-merge triggers only when `max(futures_notional, spot_notional) <
  corrected_min`, so a round with ONE leg below its own min (e.g. spot_notional=60 < 100
  while futures_notional=120) is NOT corrected and is emitted as executable.
- Controller-independent reproduction (CONFIRMED):
  - `total=0.005, fut_price=120000, spot_price=60000, both min=100, step=0.001, rounds=10`
    → 3 rounds; round[2] base=0.001, fut_notional=120 (ok), **spot_notional=60 (< 100)**. BUG.
  - `total=0.001` → 1 round with both notionals=60 (< 100), no infeasible signal. BUG.

### New P2 — AC-08 tests still miss asymmetric-leg and too-small-total cases

- `backend/tests/test_planning.py:129` — round-1 tests use symmetric prices; the asymmetric
  repro above passes the current suite.

### Required fixes (4)

1. `planning.py`: final-remainder handling must check EACH leg's own min_notional (not max).
2. `planning.py`: explicit infeasible/adjusted-total signal when the total can't form a
   min-compliant round without exceeding `total_base_quantity`.
3. `fake-ui`: mirror the corrected invariant; keep SIMULATION ONLY.
4. `test_planning.py`: add asymmetric price/step, final-remainder, and below-single-min-total
   cases that FAIL on the current code.

### Controller validation

- [x] JSON verdict schema-valid; role=`reality_checker`; verdict=`REWORK`; next_action=`fix`.
- [x] diff_fingerprint matches post-fix value.
- [x] Reviewer read-only (command audit).
- [x] **New P1 independently reproduced by controller** (both cases above) before fix #2.

Raw: `raw-transcripts/review-2-codex-rereview.txt` + `raw-transcripts/review-2-rereview-verdict.json`.

---

## Re-review (round 2, after fix #2) — verdict: ACCEPT (stage PASSES review-2)

- Reviewer: `codex` (reality_checker), read-only sandbox `codex exec`, on the POST-FIX #2
  diff (fingerprint `...:46ea7835...`).
- Read-only confirmed: codex ran only read-only commands (`rg`, `git`, `wc`, and
  `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python` repros) — zero writes; working-tree hash
  confirms no source changes.
- diff_fingerprint echoed: matches the post-fix #2 value.
- verdict: **ACCEPT** — both round-1 findings genuinely resolved, no regression, no new
  hard-constraint violation.
- next_action: `stage_accepted_waiting_user`.
- findings: 0; required_fixes: 0; residual_risks: none.

### Controller validation (final)

- [x] JSON verdict schema-valid; role=`reality_checker`; verdict=`ACCEPT`;
  next_action=`stage_accepted_waiting_user`.
- [x] diff_fingerprint matches post-fix #2 value.
- [x] Reviewer read-only (command audit + working-tree hash).
- [x] Controller independently confirmed both round-1 repros fixed (asymmetric per-leg min;
  too-small total → `feasible=False, status="infeasible"`) and no round-0 over-allocation
  regression.
- [x] Final hard-constraint audit clean: only public hosts/endpoints; no
  api-key/signed/private/order/borrow/repay/transfer/websocket code path (grep hits are the
  classification enum `PRIVATE_BORROW_VALIDATION_REQUIRED` and the fail-closed `signature`
  reject pattern — both legitimate).

### Stage outcome

The fix loop converged in 2 rounds (rework_count 2 of 3). review-2 (mandatory provider-level
isolation gate) returns ACCEPT. The stage advances to `stage_accepted_waiting_user`:
implementation is complete and verified but UNCOMMITTED, awaiting user commit approval.

Raw: `raw-transcripts/review-2-codex-rereview2.txt` + `raw-transcripts/review-2-rereview2-verdict.json`.
