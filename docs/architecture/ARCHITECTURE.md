# Architecture

Status: draft

This file is the canonical approved architecture document for the project.

Model drafts must not be written here directly. Drafts belong in
`reports/agent-runs/<stage-id>/` and are promoted here only after user approval.

## Overview

The project is a manual Binance funding-rate hedging workstation. The immediate
architecture is contract-first:

1. Backend verifies Binance public API fields and freezes a normalized public
   market snapshot contract.
2. Frontend consumes only that backend contract.
3. Private account discovery, websocket execution, and order placement are
   added in later stages.

## System Boundaries

- Backend boundary: Binance API adapters, raw sample capture, normalization,
  classification, API schema ownership, and deterministic tests.
- Frontend boundary: opportunity table, holdings/overview presentation, manual
  open ticket UI, and contract-driven API integration.
- No frontend component calls Binance directly.
- Phase 1 has no private account access and no trading side effects.

## Data Flow

```text
Binance public REST samples
  -> backend adapter field matrix
  -> normalized public market snapshot
  -> JSON schema validation
  -> frontend market table and manual-open planning UI
```

## Key Decisions

See `docs/architecture/ADR/`.

## Risks

- Binance public documentation and live payloads can diverge; every field used
  by the UI must cite raw sample evidence.
- Margin support inferred from public data is only a candidate signal. Private
  account validation is required before negative-funding execution.
- bStocks / tokenized equity products can have different route and borrow
  constraints; asset tagging must stay independent from route classification.
