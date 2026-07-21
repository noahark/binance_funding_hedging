# Official Public Contract Slice — Portfolio Margin Error Codes

Source: Binance Developers, Portfolio Margin Error Codes, captured
`2026-07-20T15:08:36Z`.

## Rate/Unknown Codes Used By Boundary C

| Code | Published name | Boundary C evidence use |
| --- | --- | --- |
| `-1003` | `TOO_MANY_REQUESTS` | classify as global rate limiting even when carried in HTTP 400 |
| `-1006` | `UNEXPECTED_RESP` | outcome may be unknown; do not retry borrow |
| `-1007` | `TIMEOUT` | execution status may be unknown; do not retry borrow |

## Frozen Known-Rejection Allowlist

The following published borrow-specific errors prove that the requested new
loan was rejected and are the only Boundary C `known_rejection` codes:

| Code | Published name | Published condition |
| --- | --- | --- |
| `-51006` | `EXCEED_MAX_BORROWABLE` | requested amount exceeds maximum borrowable |
| `-51014` | `ASSET_ADMIN_BAN_BORROW` | asset unavailable for borrowing |
| `-51061` | `INSUFFICIENT_LOANABLE_ASSET` | insufficient loanable asset |

All other 4xx/business codes remain `unknown` unless a later committed public
evidence amendment proves that no loan can have been created. In particular,
`-51007 HAS_PENDING_TRANSACTION`, liquidation/retrieval failures, system-busy
responses, and generic unknown codes are not promoted to `known_rejection` in
this stage.
