# Roadmap

Status: as-built roadmap sync, 2026-07-10

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
6. Manual execution flow. Future.
7. Accounting, reconciliation, and alerting. Future.

## Current Focus

- Canonical docs truth sync for landed read-only behavior.
- Keep `AGENTS.md`, PRD, architecture, roadmap, development guide, and API
  contract status aligned with evidence under `reports/agent-runs/`.
- Avoid starting manual execution or contract-breaking API cleanup inside this
  documentation sync.

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

## Next Product Work

- API route naming and wire version cleanup for the now mixed public/private
  read-only snapshot contract.
- Clearer borrowability state semantics beyond the generic `verified` flag.
- Websocket depth display after operator clicks open.
- Manual open planning hardening and then manual market-order execution.
- Position mismatch monitoring.
- Funding, commission, rebate, and borrow-interest accounting.
