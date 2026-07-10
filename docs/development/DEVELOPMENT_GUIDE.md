# Development Guide

Status: as-built read-only workstation, 2026-07-10

This file is the canonical approved development guide for the project.

Model drafts must not be written here directly. Drafts belong in
`reports/agent-runs/<stage-id>/` and are promoted here only after user approval.

## Project Layout

- `docs/product/PRD.md`: approved product requirements.
- `docs/api/`: approved backend-to-frontend API contracts.
- `schemas/api/`: JSON schemas for API payloads and sample validation.
- `backend/`: stdlib HTTP server, Binance adapters, normalization, private
  read-only enrichment, and tests.
- `frontend/`: same-origin static workstation UI and self-check script.
- `reports/agent-runs/<stage-id>/`: stage blackboard, model handoffs, reviews,
  and raw transcripts.
- `reports/archives/`: abandoned or superseded implementation evidence. Archive
  content is not an active implementation base.
- `scripts/run-server.sh`: local server launcher that loads `.env` when present
  and then runs `python -m backend.app.server`.

## Environment

The current application is a lightweight Python stdlib backend plus static
frontend. Runtime defaults bind to `127.0.0.1:8787` and can run without Binance
credentials by using public endpoints or offline fixtures.

Useful environment variables:

- `APP_BIND_HOST` / `FUNDING_HEDGING_BIND_HOST`: server host.
- `APP_BIND_PORT` / `FUNDING_HEDGING_BIND_PORT`: server port.
- `APP_OFFLINE` / `FUNDING_HEDGING_OFFLINE`: use frozen public samples instead
  of live public HTTP calls.
- `APP_OFFLINE_RAW_DIR` / `FUNDING_HEDGING_OFFLINE_RAW_DIR`: fixture directory.
- `BINANCE_PRIVATE_CHANNEL_ENABLED` /
  `FUNDING_HEDGING_PRIVATE_CHANNEL_ENABLED`: opt-in switch for private
  read-only enrichment.
- `BINANCE_API_KEY` and `BINANCE_API_SECRET`: required only when the private
  channel is enabled.
- `BINANCE_BORROW_CHECK_MAX_CALLS`: cap for borrow-validation probes.
- `BINANCE_PRIVATE_CHANNEL_TTL_SECONDS` and
  `BINANCE_PRIVATE_CHANNEL_FAST_TTL_SECONDS`: cache TTLs for private read-only
  data groups.

The private channel is deny-by-default. API keys may exist in the environment,
but signed private GET requests are not used unless
`BINANCE_PRIVATE_CHANNEL_ENABLED=true` or its `FUNDING_HEDGING_` alias is set.

## Commands

- Backend tests without bytecode/cache churn:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
  ```

- Frontend contract/UI self-check:

  ```bash
  node frontend/self-check.js
  ```

- Start the local server:

  ```bash
  scripts/run-server.sh
  ```

  Equivalent direct command:

  ```bash
  python3 -m backend.app.server
  ```

- Offline local server using frozen samples:

  ```bash
  APP_OFFLINE=true scripts/run-server.sh
  ```

- Optional private read-only startup, requiring a local `.env` or exported
  environment with API credentials:

  ```bash
  BINANCE_PRIVATE_CHANNEL_ENABLED=true scripts/run-server.sh
  ```

No project-wide lint or typecheck command is currently defined.

## Coding Rules

- Frontend code must not call Binance directly and must not infer Binance field
  semantics. It consumes only the backend API contract under `docs/api/` and
  `schemas/api/`.
- Backend code owns Binance request/response sampling, normalization, field
  semantics, and classification rules.
- Private account access is optional, disabled by default, and restricted to
  signed GET endpoints on the explicit backend whitelist. There are still no
  user data streams, websocket order execution, borrow, repay, transfer, or
  order-placement paths.
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
- Codex is not an implementation or fix author.
- If backend/API/schema/normalization work is the large majority and frontend
  work is light integration or display wiring, dispatch the whole bounded task
  to Claude-GLM.
- If frontend/UI/client-integration work is the large majority and backend work
  is light endpoint or schema glue, dispatch the whole bounded task to Kimi.
- If backend and frontend work are both substantial and separable, split
  implementation by domain owner.
- Grok is excluded from core backend, contract, and fix tasks for the current
  public-market phase. It may be used only for non-critical UI sketches after
  explicit user approval.

## Review And Release

- Any backend contract change must be reviewed against raw Binance samples and
  schema validation output.
- Any frontend change must be reviewed against the frozen contract and the
  agreed Chinese workstation UI style.
