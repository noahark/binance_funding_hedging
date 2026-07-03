# Development Guide

Status: draft

This file is the canonical approved development guide for the project.

Model drafts must not be written here directly. Drafts belong in
`reports/agent-runs/<stage-id>/` and are promoted here only after user approval.

## Project Layout

- `docs/product/PRD.md`: approved product requirements.
- `docs/api/`: approved backend-to-frontend API contracts.
- `schemas/api/`: JSON schemas for API payloads and sample validation.
- `reports/agent-runs/<stage-id>/`: stage blackboard, model handoffs, reviews,
  and raw transcripts.
- `reports/archives/`: abandoned or superseded implementation evidence. Archive
  content is not an active implementation base.
- `prototypes/fake-ui/`: frontend prototype and UI validation surface until the
  production frontend stack is selected.

## Environment

TBD after the backend and frontend stacks are re-selected in the contract-first
stage.

## Commands

- Test: TBD
- Lint: TBD
- Typecheck: TBD

## Coding Rules

- Frontend code must not call Binance directly and must not infer Binance field
  semantics. It consumes only the backend API contract under `docs/api/` and
  `schemas/api/`.
- Backend code owns Binance request/response sampling, normalization, field
  semantics, and classification rules.
- Phase 1 remains public-data only. No API keys, signed endpoints, private
  account endpoints, user data streams, websocket order execution, borrow,
  repay, transfer, or order placement.
- Raw samples must be stored under `reports/api-samples/<scope>/<timestamp>/`
  with a sample index that records source endpoint, capture time, and auth
  requirements.
- Contract changes must update both human documentation and JSON schema before
  frontend integration starts.

## Model Routing

- Claude-GLM owns backend API contract discovery, backend implementation, and
  Binance field semantics.
- Kimi owns frontend UI and backend API integration after the contract is
  frozen.
- Grok is excluded from core backend, contract, and fix tasks for the current
  public-market phase. It may be used only for non-critical UI sketches after
  explicit user approval.

## Review And Release

- Any backend contract change must be reviewed against raw Binance samples and
  schema validation output.
- Any frontend change must be reviewed against the frozen contract and the
  agreed Chinese workstation UI style.
