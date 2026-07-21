# Official Public Contract Slice — Margin Account Borrow

Source: Binance Developers, Margin Account Borrow, captured
`2026-07-20T15:08:36Z`.

## Endpoint Table

| Contract item | Published value |
| --- | --- |
| Base URL | `https://papi.binance.com` |
| Method and path | `POST /papi/v1/marginLoan` |
| Security | signed endpoint |
| IP request weight | `100` |
| Required parameters | `asset` string, `amount` number/float, `timestamp` int64 |
| Optional parameter | `recvWindow` int64, maximum `60000` ms |
| Success response identifier | `tranId` int64 |

The official endpoint example submits `asset`, `amount`, and `timestamp` as an
`application/x-www-form-urlencoded` request body. Its public response sample is:

```json
{
  "tranId": 100000001
}
```

The published request table contains no client request ID or idempotency-key
parameter. That absence is evidence only for the documented contract; Boundary
C therefore must not assume server-side idempotency.
