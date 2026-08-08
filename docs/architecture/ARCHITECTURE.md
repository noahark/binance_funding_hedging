# Architecture

Status: as-built snapshot, 2026-08-08

This document describes an evolving system; where it and the code disagree,
the code and `PROJECT_STATE.md` are authoritative.

This file is the canonical approved architecture document for the project.

Model drafts must not be written here directly. Drafts belong in
`reports/agent-runs/<stage-id>/` and are promoted here only after user approval.

## Overview

The project is a manual Binance funding-rate hedging workstation. Beyond the
read-only snapshot and operator review surface, it now includes live,
human-gated execution (hedge open/close, borrowing, and asset transfer):

1. Backend fetches or replays Binance public market data and normalizes it into
   a backend-owned snapshot contract.
2. When explicitly enabled with credentials, backend uses deny-by-default
   whitelisted private signed channels: read-only GETs for account, balance,
   position, borrowability, and borrow-cost enrichment
   (`backend/services/private_client.py`), plus explicitly whitelisted POST
   writes for orders, borrowing, and transfer, reachable only through gated
   executors (`backend/services/hedge_open_live_client.py`,
   `backend/services/portfolio_margin_borrow_client.py`).
3. Backend serves the normalized snapshot from
   `GET /api/public-market/snapshot`.
4. Frontend consumes only the backend snapshot contract. It does not call
   Binance directly.
5. Live order placement, manual close, live borrowing, and asset transfer are
   delivered and human-gated; websocket execution and automatic repayment
   remain future stages. Current gates and live risks: `PROJECT_STATE.md`.

The `/api/public-market/snapshot` route name is historical and
backward-compatible. The payload now includes additive private read-only fields
when the private channel is enabled; route renaming or a wire version bump is a
future contract stage.

## System Boundaries

- Backend boundary: Binance API adapters, raw sample capture, normalization,
  classification, optional private signed enrichment, API schema ownership,
  durable SQLite task/ledger stores (`data/*.sqlite3`), gated live execution,
  and deterministic tests.
- Frontend boundary: opportunity table, private read-only account panels,
  borrowability display, holdings/overview presentation, task/flow-log/history
  views, asset-transfer form, and contract-driven API integration.
- No frontend component calls Binance directly.
- The private channels are disabled by default and, when enabled, are limited
  to explicit deny-by-default whitelists: signed GETs for reads, plus a small
  set of signed POST write paths (order, borrow, transfer) reachable only
  through gated executors.
- Live trading side effects exist and are human-gated: hedge open/close tasks
  with a 1s scheduler and close worker (`backend/hedge_open_tasks/`), borrow
  tasks (`backend/borrow_tasks/`), the interest and UM income ledger
  (`backend/ledger_flow/`), idempotent asset transfer
  (`backend/asset_transfer/`), and the live executor
  (`backend/services/live_hedge_executor.py`). See `PROJECT_STATE.md` for the
  current gates, operating premises, and live risks.

## Data Flow

```text
Binance public REST or frozen public samples
  -> public adapter and normalizer
  -> route, asset-tag, funding, and trading-rule fields
  -> paired full bookTicker (spot + USDⓈ-M) cached as a public Group A source
       -> additive row-level opening_quotes (about-60s reference bid/ask spreads)
  -> optional private signed enrichment (read-only GETs:
       account, balances, positions, borrow validation, borrow cost)
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

`docs/architecture/ADR/` contains only `0000-template.md`; no ADR documents
were ever written there. The `ADR-N` references in the code are stage-local:
they point to each stage's `11-adr.md` under `reports/agent-runs/<stage-id>/`
(completed stages are preserved under their `archive/` references).
Cross-stage product and technical decisions are logged in
`docs/planning/DECISIONS.md`.

## Risks

- Binance public documentation and live payloads can diverge; every field used
  by the UI must cite raw sample evidence.
- Margin support inferred from public data is only a candidate signal. Private
  account validation is required before negative-funding execution.
- bStocks / tokenized equity products can have different route and borrow
  constraints; asset tagging must stay independent from route classification.
