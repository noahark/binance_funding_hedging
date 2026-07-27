# Stage Intake And Complexity — Hedge Open Live Hardening v1

## User Discussion Summary

Continues directly from accepted `2026-07-hedge-open-real-api-v1` (merged to
`main` at `f9809ce`, recorded at `4ce9686`). That stage passed both Review-1
gates and Review-2, then the user configured `APP_HEDGE_EXECUTOR=live` with real
hedge credentials, opened the durable Start gate by direct SQL, and placed one
real COOKIEUSDT order on 2026-07-27. The order was **sent and rejected**. No
position, no single-leg exposure, no in-flight order resulted.

The rejection exposed three live-only defects plus two standing follow-ups. The
user asked to open a new stage covering all of them, and accepted the additional
scope item this session proposed (offline transport should enforce Binance's
known parameter constraints, which is the direct root cause of the P0 escaping
nine review rounds).

Evidence for every item below:
`reports/agent-runs/2026-07-hedge-open-real-api-v1/70-handoff.md` §First live run
and `status.json.live_first_run_findings`.

## Scope — Five Items

### S1 (P0) `clientOrderId` exceeds Binance's 36-char cap

`backend/hedge_open_tasks/executor.py:160` builds `f"hgo-{attempt_id}-s"` /
`f"hgo-{attempt_id}-p"` = 4 + 32 + 2 = 38 chars. Binance caps
`newClientOrderId` at 36. Both legs returned `-4015 CLIENT_ORDER_ID_INVALID`
and were `REJECTED` with no `orderId`; the pair became `confirmed_failed`,
`fail_count=1`, and the task settled to `done` because the planned attempts were
exhausted (the R2-F1 behaviour). **No real order can currently succeed.**

Constraint on the fix: the two legs must stay distinct and globally unique, and
the id must remain usable for the `clientOrderId`-only reconciliation path that
ADR-2 depends on.

### S2 (P1) A freshly created card cannot be started in live mode

`frontend/index.html:3685`:
`startDisabled = (status !== 'paused' && status !== 'exposure_alert')`. A new
card is `running`, so Start is greyed out. In live mode `create_task` does not
start a worker and `tick()` is a deliberate no-op (H-1), so only `post_start`
can launch one — and its button is disabled. Deadlock. Current workaround: press
Pause, then Start. Dry-run hid this entirely, because there `tick()`
auto-dispatches running cards.

### S3 (P2) The Start gate has no operator entry point

`/api/hedge-open-settings` is GET-only (`backend/app/server.py:84`), the
frontend only reads it, and `service.set_start_gate()` has no production caller.
The gate was opened for the live run by direct SQL against
`data/hedge-open-tasks.sqlite3`. This stage must give the operator a real,
auditable entry point. The Start gate is a live-risk control: its write path
needs explicit confirmation semantics, not a silent toggle.

### S4 Standing follow-ups from the previous stage

- Frontend must display `worker_active` and `last_worker_exit_reason` (already
  produced by the backend, never surfaced).
- Card creation must validate that **both** legs exist — spot and USDⓈ-M perp.
  Observed: `KORUUSDT` exists on USD-M futures but not on spot (`-1121 Invalid
  symbol`); preflight correctly failed closed and refused `q_common`, but
  nothing warned at creation time, so the card sat idle with no explanation.
  Related to the recorded 1000x-prefix symbol-mismatch follow-up, but this stage
  covers only the existence check, not prefix normalisation.

### S5 Offline transport must enforce known Binance parameter constraints

The fake/record transport used by the offline tests never validated parameter
length, character set, or precision, and `reports/api-samples/` never recorded
the 36-char cap. That is exactly why S1 survived nine review rounds. This stage
adds those constraints to the offline transport so format-class defects fail in
tests rather than on a real send.

## Non-Goals

- No smooth mode (`@bookTicker` gating) work; that remains its own stage.
- No auto-close, auto-hedge, auto-borrow, or auto-repair.
- No 1000x-prefix symbol normalisation.
- No re-litigation of the accepted `real-api-v1` contracts; this stage repairs
  runtime/integration gaps and does not amend frozen contracts.
- No live activation. `APP_HEDGE_EXECUTOR=live`, the durable Start gate, and the
  first real task remain three separate human authorizations, none of which this
  stage grants.

## Runtime State At Intake

The user authorized closing the live surface before implementation begins:

- The backend service (PID 15780, live mode, running since 08:57) was stopped at
  2026-07-27 17:32 CST.
- The durable Start gate was set to `0` (`hedge_open_settings.version` 2 → 3).
- Backup taken before the write:
  `data/hedge-open-tasks.sqlite3.bak-startgate-close-20260727-*`.

## Classification

- Complexity: `MEDIUM`
- Direction panel required: `false`
- Existing synthesis covers this work: `true`
- User approved lightweight route: `true`
- Lightweight skip allowed: `true`

## Rationale

- All five items are defect repairs and hardening inside the direction already
  frozen and approved for `2026-07-hedge-open-real-api-v1`
  (`06-direction-synthesis.md` of that stage). No new product direction is
  introduced.
- The work spans backend and frontend and touches a live-risk control surface
  (S3), so it is not `LOW`: it needs a development breakdown and both review
  gates.
- The user explicitly approved the lightweight route (skip the direction panel)
  on 2026-07-27.

## Reviewer Pool

The user confirmed on 2026-07-27 that the pool is restored: `codex`,
`claude_glm`, `kimi`, and `claude` (Fable5 → Opus4.8) all have quota. The
previous stage ended down to `codex` alone with nobody able to cross-check it,
which was the second reason its handoff recommended a new stage.

## User Decision 2026-07-27 — S3 Write Surface

The user chose the **symmetric confirmation dialog**:

- The backend gains a write path for the durable Start gate; direct SQL is no
  longer required or acceptable as the operating procedure.
- The frontend offers both directions from the same control. Turning the gate
  **on** and turning it **off** each require exactly one confirmation dialog.
  No typed confirmation word, and no asymmetry between the two directions.
- The design must still specify concurrency safety (the settings row already
  carries `version`) and must keep the gate closed by default on a fresh
  install.

This closes the stage's only blocking design question. Details — endpoint path,
request/response shape, version handling, log record, and the dialog's Chinese
copy — are decided in `10-design.md`.
