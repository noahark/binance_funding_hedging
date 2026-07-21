# Official Public Contract Slice — Query Margin Loan Record

Source: Binance Developers, Query Margin Loan Record, captured
`2026-07-20T15:08:36Z`.

## Endpoint Table

| Contract item | Published value |
| --- | --- |
| Base URL | `https://papi.binance.com` |
| Method and path | `GET /papi/v1/margin/marginLoan` |
| Security | signed endpoint |
| IP request weight | `10` |
| Required parameters | `asset` string, `timestamp` int64 |
| Selection parameters | `txId` int64, or `startTime`/`endTime` int64 |
| Pagination | `current` int32; `size` int32, maximum `100` |
| Other optional parameters | `archived` boolean, `recvWindow` int64 maximum `60000` ms |

The official table explicitly describes `txId` as the `tranId` returned by
`POST /papi/v1/marginLoan`. When both transaction ID and time selection are
present, transaction ID takes precedence. Results are descending by time; a
time window is limited to 30 days, the default query is the latest seven days,
and `archived=true` selects records older than six months.

## Published Record Shape

Each row exposes these contract fields:

| Field | Type/meaning |
| --- | --- |
| `txId` | int64 transaction identifier |
| `asset` | string |
| `principal` | decimal string |
| `timestamp` | int64 |
| `status` | `PENDING`, `CONFIRMED`, or `FAILED` |

The envelope also publishes `total` as int64. The documentation does not state
a propagation-time service level after POST, so an empty early query is not
proof that the borrow failed.
