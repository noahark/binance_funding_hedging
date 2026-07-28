# Stage Task — Hedge Order Truth And Error Fidelity v1

## Goal

Make the system's record of an order match what actually happened at the
exchange. Today a filled leg records a notional of zero, a real rejection
records no classification, the exchange's own explanation is discarded, and a
live exposure is timestamped 1970. All four are cases of a plausible value being
substituted for information the system had or could have fetched.

The stage is complete when a real order's money figures, classification, raw
evidence and timestamps are trustworthy — **not** when a new order is placed.
This stage grants no live authorization and places no order, with the single
exception of T4's discriminator, which requires its own explicit user
authorization.

## Authority

This file is the top requirements authority for both review gates. Where it
disagrees with `10-design.md`, `11-adr.md`, or any implementation report, this
file wins. Where it disagrees with the raw database rows in
`01-live-record-evidence.md`, the rows win and the discrepancy is a finding.

## In Scope

| Id | Sev | Item | Primary surface |
| --- | --- | --- | --- |
| T1 | P0 | Fill figures must come from a source that still carries them | `backend/services/live_hedge_executor.py`, `backend/hedge_open_tasks/store.py` |
| T2 | P1 | Error classification must cover positive (margin) codes, structurally | `backend/hedge_open_tasks/domain.py` |
| T3 | P1 | Persist the raw order-placement response and the full order-detail read | `backend/hedge_open_tasks/store.py` (+ schema), `live_hedge_executor.py` |
| T5 | P1 | The live exposure timestamp must be real | `backend/hedge_open_tasks/service.py:1688` |
| T4 | P2 | Determine the real cause of `51169`, then fix the preflight | evidence first; `domain.py` preflight only after |

Detail and evidence for each item: `00-intake.md` and
`01-live-record-evidence.md`.

## Acceptance Criteria

### T1

- A UM/CM leg's `cumulative_quote_amt` reflects the actual traded notional. A
  filled leg must never store `0` notional against a non-zero filled quantity.
- The authoritative source for UM/CM fill figures is no longer the `POST`
  response. The design names the replacement (order-detail `GET`, user-data
  stream, or both) and states **when** the read happens relative to a leg
  reaching a terminal state — today `last_query_at_us == dispatched_at_us`,
  meaning the leg is never queried after dispatch.
- The margin/UM asymmetry is explicit: margin still returns
  `cummulativeQuoteQty`, UM/CM return neither it nor `cumQuote` nor `avgPrice`.
  The code must express this as a deliberate per-product rule, not an
  incidental `or` chain.
- **Failing loudly beats substituting.** When the authoritative figure cannot be
  obtained, the leg must not record a fabricated `0`. The design decides the
  representation (null, an explicit `unknown` marker, a retry) and justifies it;
  what is forbidden is a value indistinguishable from a genuine zero.
- A regression test proves that a UM response lacking `cumQuote`/`avgPrice` —
  i.e. the real post-2026-07-14 shape — does not produce a zero notional for a
  filled leg. The 2026-07-27 response shape is the reference case.

### T2

- A positive margin-endpoint error code is classified by the same rules as its
  negative UM/CM counterpart. `51169` must no longer land with
  `error_category = NULL`.
- The fix is **structural**: adding `51169` as a literal is not sufficient. An
  unlisted *margin* code must be handled by a deliberate rule, and the design
  must state what that rule is and why it is safe.
- An unrecognised code must remain distinguishable from a recognised one. The
  current default silently equates them; that is the defect, not just the sign
  mismatch.
- Classification must not become more permissive: no code that stops or pauses a
  task today may become non-fatal as a side effect. Enumerate any changed
  verdict in the implementation report.
- `single_leg_exposure` stays ADVISORY (settled 2026-07-28). T2 must not make a
  single-leg outcome pause or freeze a task.
- Tests cover: a positive fatal code, a positive insufficient-funds code, a
  positive unlisted code, and proof that the existing negative-code verdicts are
  unchanged.

### T3

- The complete body Binance returned to an order-placement `POST` is persisted —
  success **and** failure — including `code` and `msg`. After this stage, a
  rejection like `51169` can be explained from our own records alone.
- The complete body of the order-detail read is persisted.
- The storage shape is a design decision (new columns vs a raw-payload table vs
  `hedge_open_log` rows). Whatever is chosen must state its retention behaviour
  and be justified against the existing schema rather than bolted on.
- The design states whether raw bodies can contain anything requiring redaction,
  and if so what is redacted. Credentials, signatures and API keys must never be
  persisted.
- Persisting must not change control flow: a storage failure must not turn a
  successful order into a failed one, and the raw record must be written for the
  legs that already reach `TERMINAL_RECORDED`.
- A test asserts that a rejection's `msg` is retrievable from the database after
  the fact.

### T5

- A live single-leg exposure records the real event time, not the epoch.
- The dry-run and live paths derive the timestamp the same way; the divergence
  at `service.py:1688` versus `executor.py:342` is closed rather than
  duplicated.
- A regression test covers the **live** path specifically. The existing offline
  suite passes today precisely because it exercises the other path — a test that
  only covers `executor.py` does not satisfy this criterion.
- `leg_exposure.price` is expected to stop being `null` as a consequence of T1.
  The implementation report states whether it does; if T1's fix does not restore
  it, that is reported, not silently patched here.

### T4

T4 is **evidence-gated and authorization-gated**. It is not implementation work
until its discriminator has run.

- No preflight change may be designed or implemented before the discriminator
  result exists. Fixing the preflight against an unproven cause is how the
  current gate was written.
- The discriminator is one real margin BUY on NOMUSDT with no concurrent UM
  order. It requires explicit user authorization separate from opening this
  stage, and the human operator executes it. It only buys, so it creates no new
  naked exposure — but it spends real money.
- The raw request and response land under
  `reports/api-samples/2026-07-hedge-order-truth-v1/`.
- Interpretation is fixed in advance so the result cannot be rationalised after
  the fact: **success ⇒** concurrency contention with the UM leg is real;
  **same `51169` ⇒** the cause is the collateral coefficient or wallet
  placement, not contention.
- If the user declines or defers, T1/T2/T3/T5 ship and T4 defers with the
  preflight untouched. That is an acceptable stage outcome, recorded as a
  follow-up rather than a failure.
- Do not design around a PAPI test-order endpoint. There is none.

## Non-Goals

- Close / unwind functionality. The outstanding naked SHORT 10000 NOMUSDT is
  **not** resolved by this stage.
- Smooth mode (`@bookTicker` gating).
- Re-litigating `single_leg_exposure` being ADVISORY.
- UI work of any kind, including surfacing the newly persisted raw payloads or
  the exchange's verbatim message. T2 restores a meaningful `error_category`,
  which the card already consumes.
- Redesigning the preflight before T4's discriminator has run.
- Amending any contract frozen by `2026-07-hedge-open-real-api-v1` beyond what
  T1 and T3 necessarily change; where an amendment is unavoidable, it needs an
  ADR entry and raw samples under `reports/api-samples/`.
- Any live activation, any change to the currently open Start gate, and any
  write to `data/hedge-open-tasks.sqlite3`.

## Tests

Existing suites must stay green:

```text
backend/tests/test_hedge_domain.py
backend/tests/test_hedge_store.py
backend/tests/test_hedge_service.py
backend/tests/test_hedge_api.py
backend/tests/test_hedge_executor.py
backend/tests/test_hedge_task_local.py
backend/tests/test_live_hedge_executor.py
backend/tests/test_hedge_open_live_client.py
backend/tests/test_hedge_purity.py
```

New tests are required for T1 (post-2026-07-14 UM response shape), T2 (positive
fatal / insufficient / unlisted codes plus negative-code non-regression), T3
(raw response retrievable, including a rejection's `msg`), and T5 (the **live**
path's timestamp).

## Safety — The Live Surface Is Open This Time

Unlike the previous stage, the service is **running in live mode** (PID 96409)
and the durable Start gate is **OPEN** (`start_gate=1`, `version=4`). The user
was offered closing both and chose to leave them.

Therefore, for every agent working this stage:

- Do not create a task card, press Start, or place an order.
- Do not write to `data/hedge-open-tasks.sqlite3` — not the settings row, not a
  task row, not a leg row. Read-only access for evidence is permitted.
- Do not read, print, store, or request credentials.
- Do not start, stop, or restart the backend service.
- `APP_HEDGE_EXECUTOR=live`, the durable Start gate, and any real order remain
  separate human authorizations. This stage grants none of them.
- T4's discriminator is the sole exception and is executed by the human operator
  after explicit authorization.
