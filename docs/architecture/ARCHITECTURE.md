# Architecture

Status: as-built read-only snapshot, 2026-07-10

This file is the canonical approved architecture document for the project.

Model drafts must not be written here directly. Drafts belong in
`reports/agent-runs/<stage-id>/` and are promoted here only after user approval.

## Overview

The project is a manual Binance funding-rate hedging workstation. The current
implementation is a read-only snapshot and operator review surface:

1. Backend fetches or replays Binance public market data and normalizes it into
   a backend-owned snapshot contract.
2. When explicitly enabled with credentials, backend uses a whitelisted private
   signed GET channel for read-only account, balance, position, borrowability,
   and borrow-cost enrichment.
3. Backend serves the normalized snapshot from
   `GET /api/public-market/snapshot`.
4. Frontend consumes only the backend snapshot contract. It does not call
   Binance directly.
5. Websocket execution, order placement, borrowing, repayment, transfer, and
   close flows remain future stages.

The `/api/public-market/snapshot` route name is historical and
backward-compatible. The payload now includes additive private read-only fields
when the private channel is enabled; route renaming or a wire version bump is a
future contract stage.

## System Boundaries

- Backend boundary: Binance API adapters, raw sample capture, normalization,
  classification, optional read-only private signed GET enrichment, API schema
  ownership, and deterministic tests.
- Frontend boundary: opportunity table, private read-only account panels,
  borrowability display, holdings/overview presentation, and contract-driven
  API integration.
- No frontend component calls Binance directly.
- The private channel is disabled by default and, when enabled, is limited to
  signed GET requests through an explicit whitelist.
- The current product has no trading side effects: no order, borrow, repay,
  transfer, or execution endpoints are exposed.

## Data Flow

```text
Binance public REST or frozen public samples
  -> public adapter and normalizer
  -> route, asset-tag, funding, and trading-rule fields
  -> paired full bookTicker (spot + USDⓈ-M) cached as a public Group A source
       -> additive row-level opening_quotes (about-60s reference bid/ask spreads)
  -> optional private signed GET enrichment
       (account, balances, positions, borrow validation, borrow cost)
  -> normalized read-only snapshot
  -> JSON schema validation
  -> same-origin backend API
  -> frontend opportunity table and private read-only panels
```

The paired bookTicker source is public and always-on (independent of the private
channel). It reuses `cache_ttl_seconds` (default 60s) as its Group A cadence and
publishes last-good quotes for at most `2 * cache_ttl_seconds` (default 120s)
before the row-level `opening_quotes.status` goes `stale`; a selected-symbol
click reuses the canonical row's quotes and adds no bookTicker HTTP.

## Key Decisions

See `docs/architecture/ADR/`.

## Risks

- Binance public documentation and live payloads can diverge; every field used
  by the UI must cite raw sample evidence.
- Margin support inferred from public data is only a candidate signal. Private
  account validation is required before negative-funding execution.
- bStocks / tokenized equity products can have different route and borrow
  constraints; asset tagging must stay independent from route classification.
