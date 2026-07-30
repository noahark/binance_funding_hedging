# Scope Decision Request — how to repair review-2's three findings

Prepared 2026-07-30 by Opus 5 (Bookkeeper) for Human. Verification of all three
findings is in `41-review-2-codex-result.md`; nothing here re-argues them.

`rework_count` is now 1 of 3. Whatever is chosen, the repair re-enters review-1
before returning to review-2 (`AGENTS.md:181` — a review-2 repair that expands
files or changes a contract must pass review-1 again).

## The three findings, sized

| # | What | Files | Risk of fixing |
|---|---|---|---|
| F3 | Three sentences in stage documents overstate the guard | `00-plan.md`, `20-task1-glm-result.md` | None. Documentation only. Mine to write |
| F2 | `except Exception: pass` discards settlement failures, leaving an attempt unsettled, the in-flight guard tripped, and nothing operator-visible. D4 made it reachable by one more path | `service.py`, plus tests | Moderate and bounded. This is a regression this stage introduced on a live settlement path |
| F1 | A partial 2xx balance read becomes `available = 0` → `insufficient_balance`, which is **fatal** and permanently stops the task with a false reason | `hedge_preflight_provider.py`, `domain.py` (the `PreflightResult` contract), `service.py` routing, plus tests | Highest. A different subsystem, a domain-contract change, and an unresolved sub-case |

## Why F1 is not a simple fix

The review's requirement — "a missing balance asset must return
`preflight_incomplete` and `available=None`" — is right for one sub-case and
possibly harmful for the other:

- **Row present but `crossMarginFree` missing/unparseable, or a truncated list** —
  `0` is fabricated. The fix is correct here.
- **Row absent because the balance genuinely is zero** — exchanges commonly omit
  zero-balance assets. Here `0` is the truth, and returning `incomplete` would
  stall a task that should simply report insufficient balance. Trading a false stop
  for a permanent stall is not an improvement.

Which behaviour Binance actually produces is not knowable from the repository. It
needs one authorized read-only observation of a `get_balance` response for an asset
the account does not hold — which is a live signed read, so it needs your explicit
authorization (`AGENTS.md` §3.1). Until that is settled, any F1 fix is guesswork
dressed as rigour, which is the thing this stage exists to remove.

## Options

**A — Repair F2 + F3 here; F1 becomes its own stage.** (Bookkeeper recommendation.)

This stage closes on what it set out to do plus the regression it caused. F2 is a
defect this stage introduced and should not be exported. F3 is honesty about the
deliverable. F1 gets a stage with its own plan, its own evidence-gathering step for
the sub-case question, and its own review — which is what a domain-contract change
to a fatal-stop admission path deserves.

Cost of deferring F1: the false-stop remains live until that stage runs. Its trigger
is a malformed or truncated balance response, which is not routine but is not
exotic either. Mitigation while deferred: it fails *closed* — it stops a task, it
never places an order or moves money.

**B — Repair all three here.** One review cycle instead of two, and the highest-risk
finding is closed sooner. Costs: this stage's file boundary widens into the preflight
subsystem and a domain contract; the F1 sub-case question must still be answered
first, so the stage stalls on an authorized live read anyway; and this stage has
already run one plan review, one Bookkeeper rejection, one review-1 and one review-2
— a fifth round on a widened scope is where the previous stage's seven-round spiral
started.

**C — Repair F3 only, defer F1 and F2.** Cheapest. Not recommended: F2 is a
regression this delivery introduced, and shipping it means exporting a defect that
did not exist at `ac8d493`.

## What I need from you

1. Which option.
2. If A or B: may I request one authorized read-only `get_balance` observation for
   F1's sub-case question — either now (B) or when its stage runs (A)? No order, no
   write, no service control; a signed GET whose response shape is the whole point.
3. F1's fix direction, once the sub-case is known, will change what an operator sees
   when a balance cannot be read. That copy is product meaning and will come back to
   you for approval rather than being chosen by an implementer.
