# Official Public Contract Slice — Portfolio Margin General Info

Source: Binance Developers, Portfolio Margin General Info, captured
`2026-07-20T15:08:36Z`.

## Request And Signing Facts

- Portfolio Margin REST requests use `https://papi.binance.com`.
- POST parameters may be carried in the query string or an
  `application/x-www-form-urlencoded` body; when a parameter occurs in both,
  the query-string value wins.
- Signed requests use HMAC-SHA256 over `totalParams`, formed from the query
  string followed by the request body. The signature is the final parameter.
- A signed request requires `timestamp`; `recvWindow` defaults to 5000 ms and
  cannot exceed 60000 ms.

Boundary C freezes the endpoint-specific documented body form for the borrow
POST and requires the exact bytes used for signing to be the bytes sent.

## Capacity And Failure Facts

- Portfolio Margin IP request-weight capacity is published as 6000 per minute.
- Used-weight response headers account by IP, not by API key.
- HTTP 429 indicates a request-rate-limit violation.
- Continuing after 429 can lead to HTTP 418 automatic IP bans.
- Published ban duration scales from two minutes to three days.
- The official 5xx/503 guidance includes outcomes whose execution status is
  unknown; a 5xx therefore cannot generally prove that a write did not occur.

The current public page does not document a guaranteed `Retry-After` header
format or its presence for these responses. Boundary C consequently treats a
valid header as advisory and uses a fail-safe local fallback when it is absent
or invalid.
