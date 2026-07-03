# Intake: Public Market Contract V2

Stage ID: `2026-07-public-market-contract-v2`

Status: ready for backend contract discovery

Initial reset base SHA: `0c2bfcbf86db8a7b0da69702b56f714210eb5174`

Actual review base for contract discovery:
`2bb47ad13065827ed1ee91d5d0e231cd312fdc0a`

The contract discovery diff must be computed from this base.

## User Decision

Stop the current Grok-led development loop. Archive the Grok implementation and
restart from the last approved PRD/direction baseline.

New model allocation:

- Claude-GLM: backend Binance public API contract discovery and backend
  implementation.
- Kimi: frontend UI and integration against Claude-GLM's frozen backend API.
- Grok: excluded from core backend, contract, and fix work for this phase.

## Immediate Goal

Before building more UI or backend logic, verify Binance public endpoint request
and response fields, define the normalized backend API JSON, and provide schema
and sample fixtures that the frontend can consume without guessing Binance
semantics.
