# Stage Task

## Stage ID

`2026-07-cache-refresh-scheduler-v2`

## Goal

Refactor the live read-only snapshot refresh path into three explicit endpoint
cadence groups while preserving the existing wire contract:

1. 60-second fast sources;
2. fixed 30-minute shared/unified sources;
3. a 30-second homepage sweep of at most 10 symbols, refreshing only missing or
   at-least-1800-second-old per-symbol/per-asset components.

## Non-Goals

- No 25-minute refresh-ahead window.
- No strict guarantee that a symbol is refreshed at exactly 1800 seconds; queue
  position may extend normal successful-path age to approximately 30-35 minutes.
- No new last-good retention policy for request failures.
- No protection against a successful empty or partial response replacing prior
  cached content.
- No endpoint-response completeness audit or requested-vs-returned asset check.
- No frontend changes and no API/schema changes.
- No change to one-shot row-click refresh semantics.
- No persistence across process restarts.
- No order, borrow, repay, transfer, or other trading action.

## File Boundaries

Expected implementation files:

- `backend/config.py`
- `backend/adapters/binance_public.py`
- `backend/services/private_client.py`
- `backend/services/snapshot_service.py`
- `backend/tests/test_config.py`
- `backend/tests/test_background_worker.py`
- `backend/tests/test_private_client.py`
- additional backend tests only when required by the bounded design

Forbidden or out of scope:

- `frontend/**`
- `schemas/api/**`
- trading or mutation endpoints
- credential files and environment dumps
- canonical `docs/**` promotion before user approval

## Acceptance Criteria

1. Every scheduled upstream endpoint is assigned to exactly one normal cadence
   group or explicitly recorded as fallback/manual/discovery-only.
2. The 60-second group refreshes dynamic all-market and account inputs
   independently from the two slower groups.
3. The fixed 30-minute group refreshes the frozen shared/unified endpoint list
   without consuming symbol-sweep slots.
4. Every 30 seconds the homepage sweep examines at most 10 eligible symbols.
5. History, borrow rate, and max-borrowable freshness are checked independently;
   one fresh component cannot suppress refresh of another missing/expired one.
6. Batch borrow-rate responses are unpacked into per-base-asset business cache
   entries with independent update timestamps.
7. Current API response fields and frontend behavior remain unchanged.
8. Existing manual selected-symbol refresh behavior remains unchanged.
9. Deterministic tests pin cadence separation, component-level skip/update, and
   per-asset batch-cache timestamp behavior.

## Human Gates

- Human approval of the frozen design after external model cross-check.
- Human-executed implementation dispatch after the required MEDIUM breakdown.
- Explicit user acceptance before eventual merge to `main`.

## Designer

- Model: OpenAI Codex / GPT-5
- Skill: software architect
- Date: 2026-07-14

