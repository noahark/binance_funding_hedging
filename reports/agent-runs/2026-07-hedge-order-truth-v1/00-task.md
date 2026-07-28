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
| T4 | P2 | `51169`'s cause is **found**; remaining work is a read-only recon, then the preflight decision follows from it | evidence first; `domain.py` preflight only after |

Detail and evidence for each item: `00-intake.md`,
`01-live-record-evidence.md`, and `02-collateral-cap-finding.md`.

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

**`51169` specifically** — its cause is now known (`02-collateral-cap-finding.md`),
which turns it from an unclassified code into a case with a required verdict. It
is:

- **not** an insufficient-funds condition of this account — adding balance does
  nothing;
- **not** usefully retryable within a task's retry window — the cap is consumed
  platform-wide and will not clear in seconds;
- **not** permanent either — it can clear later, so the coin must not be
  permanently blacklisted;
- **coin- and direction-specific** — it blocks the forward direction's spot leg
  for that asset while the perp leg is unaffected.

The design must decide the task-level outcome and the operator's Chinese message,
and that message must say what is true: *this coin's platform collateral cap is
full, the spot leg cannot be bought into the margin account right now, try another
coin or try later.* Reporting it as 保证金不足 would be actively misleading.

One nuance the design must not flatten: between 90% and 100% of the cap a
**smaller** order can still succeed (capped at 50,000 USD equivalent). So `51169`
does not universally mean "no size works" — for NOM today it does, because NOM is
above 100%.

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

### T4 — REVISED 2026-07-28: the cause is found, the paid experiment is cancelled

`51169`'s cause is established. **NOM is above Binance's platform-wide Maximum
Collateral Limit**, a per-asset cap shared across all users that explicitly
covers Portfolio Margin. Above 100% utilisation, buying or transferring that
asset into a margin account is blocked outright — the user's own Binance app
reports a maximum buy quantity of `0` for NOM. Full evidence, official quotes and
reasoning: `02-collateral-cap-finding.md`.

This also explains the 2026-07-27 asymmetry: the UM perpetual SELL does not need
NOM as collateral, so it filled; the margin BUY does, so it was blocked.

**The discriminator order is cancelled.** Its pre-registered interpretation said
`same 51169 ⇒ coefficient or wallet placement, not contention` — which is the
branch already reached. Running it would spend real money to confirm a known
answer. No order is placed by this stage.

Remaining T4 work, all read-only:

- Recon whether **any** API surface exposes the per-asset collateral cap or its
  current utilisation. Two official FAQ pages name none; that is not proof of
  absence in the API. Public documentation reads and signed **GET** reads only —
  no order, no write. Raw evidence lands under
  `reports/api-samples/2026-07-hedge-order-truth-v1/`.
- The preflight decision follows the recon's answer and only then:
  - **endpoint exists** → the design specifies a real preflight gate against it;
  - **no endpoint exists** → the preflight *cannot* see this constraint and must
    not pretend to. Handling then belongs entirely to T2, and the design must say
    so explicitly rather than adding a gate that guesses.
- The recon must record that the condition is **time-varying** — the cap is
  consumed by all users' holdings, so an asset blocked today may clear later. Do
  not design anything that caches it as a static property of a coin.
- Do not design around a PAPI test-order endpoint. There is none.

Acceptance for T4 is the recon evidence plus a design decision that follows from
it. If the recon finds nothing, "the preflight is deliberately not changed, and
here is why" is a complete and acceptable T4 outcome.

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
- **This stage now places no order at all.** T4's discriminator was cancelled on
  2026-07-28 once the root cause was established from the exchange's UI and
  documentation; T4's remaining work is read-only recon. Signed **GET** reads are
  permitted for that recon; nothing else.
