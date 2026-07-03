# ADR: Reset Grok Implementation And Split Backend / Frontend Ownership

Date: 2026-07-03

Status: accepted for next stage

## Context

The Grok-led public-market implementation produced useful evidence but became a
poor active base. It missed real-sample classification details, changed the fake
UI away from the agreed Chinese style, and repeatedly stalled as a CLI child
process during fix rounds.

The project is still early. Rebuilding from the approved PRD and direction
baseline is cheaper than carrying forward implementation trust debt.

## Decision

Archive Grok work and restart Phase 1 with a contract-first split:

- Claude-GLM owns backend public API field verification and backend
  implementation.
- Kimi owns frontend UI and backend API integration.
- Frontend consumes the backend contract only.
- Grok is excluded from core backend, contract, and fix work for this phase.

## Consequences

Positive:

- Binance field semantics have one owner.
- Frontend and backend can work with a stable JSON boundary.
- Review can check contract evidence before implementation grows.
- Grok output remains available as archived evidence without polluting the
  active tree.

Tradeoffs:

- Stage 1 restarts instead of patching the existing implementation.
- Backend implementation waits for contract discovery.
- Some useful tests from the Grok attempt must be reintroduced intentionally
  instead of copied wholesale.
