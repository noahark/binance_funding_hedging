# Roadmap

Status: as-built roadmap sync, 2026-08-02

This file is the canonical approved roadmap.

## Milestones

1. Public market API contract discovery. Done.
2. Public market backend snapshot API. Done.
3. Frontend market table and manual-open planning UI against the frozen backend
   contract. Done.
4. Private account discovery and read-only account validation. Done for the
   current snapshot surface.
5. Borrow-cost display, private-account UI polish, and borrowability edge-case
   mapping. Done for current read-only scope.
6. Real PM borrow execution (Boundary C live path, durable tasks, global Start).
   Landed on local main; operator live validation ongoing. See
   `docs/planning/CHANGELOG-2026-07-22-live-borrow-ops.md` and
   DEC-2026-07-22-001…003.
7. Manual open planning + market-order execution (spot/perp hedge). **Live and
   in use, with known limitations.** Durable hedge-open tasks, a task-local
   worker, real PAPI order dispatch behind the Start gate, an inline per-attempt
   log, and a backend-merged position table have all shipped. Real orders have
   been placed. The open items are display honesty and runtime verification, not
   capability — see Current Focus and `PROJECT_STATE.md`.
8. Accounting, reconciliation, and alerting. Future.

## Current Focus

Hedge-open display honesty, then runtime verification. Detail and acceptance
state for every item below live in `PROJECT_STATE.md`.

- **F4 — the position table claims "exchange has no position" without checking.**
  Highest priority: it fires from the same outage that makes a task ask the
  operator to go verify on the exchange, so the moment you most need the table is
  the moment it is least trustworthy. Fix fully specified; scheduled on its own
  rather than waiting for the deferred lifecycle rework.
- **Task-card pause reasons render 1 of 7 in Chinese** — the frontend never reads
  the `pause_reason_zh` the backend already returns. Two-line change.
- **Run the read-only smoke checklist** (`archive/2026-07-31-hedge-task-lifecycle-v1`
  file `49-`). Never executed; now a hard prerequisite for the next live
  activation. Nothing in the hedge-open path has runtime evidence.
- The lifecycle rework (deadlock fix, five-reason auto-delete, `rate_limited`
  backoff) is designed and deliberately deferred — DEC-2026-08-02-003 and
  `docs/planning/deferred-hedge-task-lifecycle.md`.
- Keep canonical docs aligned with as-built code (this roadmap, DECISIONS,
  DEVELOPMENT_GUIDE, public-market contract).

## Done (Selected)

- `2026-07-public-market-contract-v2`: public endpoint field verification and
  initial backend-to-frontend snapshot contract.
- `2026-07-public-market-impl-v1`: backend snapshot implementation.
- `2026-07-public-market-ui-cn-v1`: Chinese workstation UI over the snapshot
  contract.
- `2026-07-public-market-bstock-alias-v1`: bStock route alias amendment.
- `2026-07-private-account-v1`: optional private read-only signed GET channel,
  account blocks, borrow validation, and borrow-cost enrichment.
- `2026-07-private-account-ui-polish-v1`: private-account UI and value display
  polish.
- `2026-07-phase2-borrow-sort-v1`: borrow-aware sort basis.
- `2026-07-ui-filter-balance-metal-v1`: metal asset tagging and UI balance
  updates.
- `2026-07-borrow-cost-coverage-v2`: borrow-cost coverage updates.
- `2026-07-borrowability-error-zero-mapping-v1`: maps borrowability error
  `51061` into the zero-borrowable display path.
- `2026-07-real-borrow-boundary-c-v1` (+ execution stages): durable borrow
  tasks, live PM `marginLoan` path, execution gates, recon skeleton.
- 2026-07-22 live-ops patches (session changelog): Scheme A/C classification,
  attempt-log coalesce, error-code labels, `cross_margin_borrowed` UI, market
  workstation polish (正费率 badge, opening-quote price trim, snapshot meta).
- Hedge open, 2026-07-22 → 2026-08-02: fake UI, dry-run skeleton, the real-API
  round (first real order rejected on a 38-char clientOrderId), live hardening,
  order-truth, the inline per-attempt log, the backend-merged position table, and
  the 500ms re-query cadence with a ten-try retry budget. DEC-2026-07-30-001…003
  and DEC-2026-08-02-001…003.

## Next Product Work

- Optional: durable `fail_count` / true attempt counters if coalesce-aware stats
  are needed on the task card.
- Optional: surface `crossMarginInterest` next to borrowed principal.
- API route naming and wire version cleanup for the now mixed public/private
  read-only snapshot contract.
- Clearer borrowability state semantics beyond the generic `verified` flag
  (green「已验证可借」still does not mean maxBorrowable was probed).
- Websocket depth display after operator clicks open.
- Position mismatch monitoring beyond the current merged table (the single-leg
  marker under-reports partial imbalance; drift detection reads the wrong
  account pool and is permanently inert).
- Funding, commission, rebate, and borrow-interest accounting.
