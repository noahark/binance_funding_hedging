# Stage Task — Hedge Open Live Hardening v1

## Goal

Make the accepted hedge-open path actually executable against Binance, give the
operator a real entry point for the two live controls it lacks, and close the
offline-test blind spot that let a format-class defect reach a real send.

The stage is complete when a real order **could** succeed if a human opened all
three live gates — not when one is opened. This stage grants no live
authorization.

## In Scope

| Id | Sev | Item | Primary surface |
| --- | --- | --- | --- |
| S1 | P0 | `clientOrderId` ≤ 36 chars, legs still distinct and unique | `backend/hedge_open_tasks/executor.py` |
| S2 | P1 | A newly created card must be startable in live mode | `frontend/index.html` (+ backend state if design requires) |
| S3 | P2 | Operator entry point for the durable Start gate | `backend/app/server.py`, `frontend/index.html` |
| S4 | followup | Show `worker_active` / `last_worker_exit_reason`; validate spot+perp both exist at card creation | frontend + backend validation |
| S5 | followup | Offline transport enforces Binance parameter constraints | backend test transport |

Detail and evidence for each item: `00-intake.md`.

## Acceptance Criteria

### S1

- Both legs' `clientOrderId` are ≤ 36 characters for every reachable
  `attempt_id`, distinct from each other, and globally unique.
- The id remains usable for the `clientOrderId`-only reconciliation path ADR-2
  depends on (`reports/agent-runs/2026-07-hedge-open-real-api-v1/11-adr.md`).
- A test asserts the length bound directly, and fails if the derivation is
  changed to exceed it.

### S2

- From a freshly created card in live mode, the operator can start the worker
  without the Pause→Start workaround.
- Dry-run behaviour is unchanged.
- The fix does not make a card auto-dispatch in live mode; H-1's deliberate
  `tick()` no-op stays intact.

### S3

- The durable Start gate can be turned on and off through the application, with
  no direct SQL.
- The write path carries explicit confirmation semantics (exact shape decided in
  `10-design.md` — this is the stage's one open design decision).
- Turning the gate on is auditable: the log records who/when at the same
  fidelity as other live-risk actions.
- The gate's default remains closed, and a fresh install still starts closed.

### S4

- `worker_active` and `last_worker_exit_reason` are visible on the card in
  Chinese, degrading to `—` when the field is absent (matching the existing
  `hedgeText` convention).
- Creating a card for a symbol that lacks either leg is refused at creation
  time with a Chinese message naming which leg is missing, instead of leaving an
  idle card. `KORUUSDT` (perp-only) is the reference case.

### S5

- The offline transport rejects parameters that Binance would reject:
  `newClientOrderId` length and character set, and quantity/price precision
  against the symbol filters already loaded.
- A regression test proves the pre-fix S1 derivation would have failed offline.

## Non-Goals

- Smooth mode (`@bookTicker` gating).
- Auto-close, auto-hedge, auto-borrow, auto-repair.
- 1000x-prefix symbol normalisation (separate recorded follow-up).
- Amending any contract frozen by `2026-07-hedge-open-real-api-v1`.
- Any live activation.

## Tests

Existing suites must stay green:

```text
backend/tests/test_hedge_store.py
backend/tests/test_hedge_service.py
backend/tests/test_hedge_task_local.py
backend/tests/test_hedge_executor*.py
```

New tests are required for S1 (length bound), S3 (gate write path + default
closed), S4 (two-leg existence validation), and S5 (offline constraint
enforcement, including the pre-fix S1 regression).

## Safety

- The service is stopped and `start_gate = 0` as of intake.
- No implementer or reviewer may open a live gate, place an order, or touch
  credentials.
- `APP_HEDGE_EXECUTOR=live`, the durable Start gate, and the first real task
  stay three separate human authorizations.
