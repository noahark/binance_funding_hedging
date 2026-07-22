# Roadmap

Status: as-built roadmap sync, 2026-07-22

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
7. Manual open planning + market-order execution (spot/perp hedge). Future.
8. Accounting, reconciliation, and alerting. Future.

## Current Focus

- Stabilize live borrow ops UX under operator-accepted risk choices (4xx and
  transport failures keep rotating; log coalesce; liability display).
- Market table ops polish (accepted locally 2026-07-22): **近 24h** sum column,
  **可开优先展示** re-rank, dual hide filters (abs daily vs signed net). See
  `docs/planning/CHANGELOG-2026-07-22-market-table-filters.md` and
  DEC-2026-07-22-004…006.
- Keep canonical docs aligned with as-built code (this roadmap, DECISIONS,
  DEVELOPMENT_GUIDE, public-market contract).
- Formal Harness dual-review packaging for the 2026-07-22 fast patches remains
  optional unless the operator requests a stage seal.

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

## Next Product Work

- Optional: durable `fail_count` / true attempt counters if coalesce-aware stats
  are needed on the task card.
- Optional: surface `crossMarginInterest` next to borrowed principal.
- API route naming and wire version cleanup for the now mixed public/private
  read-only snapshot contract.
- Clearer borrowability state semantics beyond the generic `verified` flag
  (green「已验证可借」still does not mean maxBorrowable was probed).
- Websocket depth display after operator clicks open.
- Manual open planning hardening and then manual market-order execution.
- Position mismatch monitoring.
- Funding, commission, rebate, and borrow-interest accounting.
