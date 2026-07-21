# Boundary C Public Contract Evidence Index

## Gate Result

`CLOSED_WITH_FAIL_CLOSED_DEFAULTS`

The exact public POST/GET contract and capacity inputs needed to start the
development breakdown are archived. Facts that the public documentation does
not guarantee remain explicit unknowns with conservative behavior; they are
not represented as verified exchange promises.

## Section 6 Closure Matrix

| Question | Evidence result | Frozen design consequence |
| --- | --- | --- |
| Borrow endpoint, method, host | verified | exact allowlist: `POST https://papi.binance.com/papi/v1/marginLoan` |
| Borrow parameter encoding | verified endpoint example | form body containing `asset`, `amount`, `timestamp`, optional `recvWindow`; sign/send identical serialization |
| Borrow request weight | verified: 100 IP weight | cadence formula uses 100 |
| Portfolio Margin IP budget | verified: 6000/min | half-budget formula yields a 2-second minimum; default remains 5 seconds |
| Success identity | verified: `tranId` int64 | normalize to positive arbitrary-precision decimal string before durable success |
| Documented idempotency key | none in full parameter table | no automatic POST retry; durable intent and reconciliation are mandatory |
| Loan-record endpoint/weight | verified: signed GET, weight 10 | exact second allowlisted path |
| Loan-record identifier mapping | verified: GET `txId` is POST `tranId` | unique ID match is authoritative |
| Loan-record matching fields | verified: `asset`, `principal`, `timestamp`, `status` | response-less matching requires exact asset + Decimal principal + dispatch-anchored window and one unique `CONFIRMED` record |
| Loan-record history bounds | verified | use bounded time windows, page size at most 100, and never infer failure from absence |
| History propagation SLA | not published | preserve `+5/+15/+60/+300/+900s`; exhaustion stays blocked |
| Rate limits | verified: 429 and 418 semantics | global cooldown blocks all signed borrow-client traffic |
| `Retry-After` presence/format | not guaranteed by current page | invalid/missing/non-positive = 60s; valid seconds clamp to `[60,300]` |
| 418 ban duration | verified: 2 minutes to 3 days | 300s cooldown is only a minimum latch; no automatic resume, explicit global Start required |
| Known borrow rejection codes | verified for `-51006`, `-51014`, `-51061` | these three only; every unlisted 4xx is unknown |
| `-1003` | verified rate-limit business code | treat as rate limited under HTTP 400 or 429 |
| 5xx/503 execution certainty | official guidance permits unknown | classify borrow outcome as unknown and reconcile |
| Per-asset precision/minimum | not published on captured endpoint | no speculative client rounding; send validated Decimal text and classify exchange response |
| Whether these calls count toward other limit families | not fully specified | budget as shared IP weight and avoid using the remaining half-budget |

## Design Amendment Trigger

The evidence confirms the adjudicated endpoints and the two-second interval
floor. It also requires these explicit clarifications:

1. Freeze `known_rejection` to `-51006`, `-51014`, and `-51061` only.
2. Treat 418's 300-second value as a minimum local cooldown, not proof that a
   possible exchange ban has expired; explicit Start remains required.
3. Loan history has no published propagation SLA, so the chosen reconciliation
   sequence is a conservative local policy rather than an exchange guarantee.
4. The published POST table contains no idempotency parameter.

No authenticated or live-write evidence was collected. If a later contract
amendment changes any frozen item, it must add a new committed public capture
and re-enter review as required by `AGENTS.md`.
