# Public Sample Request Manifest

Collection window started at `2026-07-18T04:23:14Z`. All requests were unsigned public GETs;
no account headers, credentials, cookies, or private endpoints were used.

## Requests

1. `GET https://api.binance.com/api/v3/exchangeInfo`
   - Query: `symbols=["AERGOUSDT","XMRUSDT","LITUSDT"]`
   - Query: `showPermissionSets=false`
   - Raw: `raw/api-v3-exchangeInfo-symbols.json`
2. `GET https://api.binance.com/api/v3/ticker/bookTicker`
   - Query: `symbols=["AERGOUSDT","XMRUSDT","LITUSDT"]`
   - Raw: `raw/api-v3-ticker-bookTicker-symbols.json`
3. `GET https://fapi.binance.com/fapi/v1/ticker/bookTicker`
   - One request per query: `symbol=AERGOUSDT`, `symbol=XMRUSDT`, `symbol=LITUSDT`
   - Raw: `raw/fapi-v1-ticker-bookTicker-<symbol>.json`

The server timestamps embedded in the raw responses are the authoritative capture-time evidence.
