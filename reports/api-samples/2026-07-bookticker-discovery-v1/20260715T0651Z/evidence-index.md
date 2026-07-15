# Evidence Index: BookTicker Discovery (Spot + USDⓈ-M Futures)

Collection: `2026-07-bookticker-discovery-v1`
Timestamp: `20260715T0651Z`
Captured: 2026-07-15T06:51:57Z (UTC) via live no-key `curl`
Purpose: ground a future Group A (60s) bookTicker cache for bid/ask display
Auth: none (public market data only)

## Endpoints captured

| File | Endpoint | Mode | HTTP | Bytes | Shape |
|---|---|---|---|---|---|
| `raw/api-v3-ticker-bookTicker-full.json` | `GET /api/v3/ticker/bookTicker` | full | 200 | 419404 | list[object] len=3639 |
| `raw/api-v3-ticker-bookTicker-full.headers` | (response headers) | | | | includes `x-mbx-used-weight*` |
| `raw/fapi-v1-ticker-bookTicker-full.json` | `GET /fapi/v1/ticker/bookTicker` | full | 200 | 106997 | list[object] len=708 |
| `raw/fapi-v1-ticker-bookTicker-full.headers` | (response headers) | | | | `x-mbx-used-weight-1m: 5` |
| `raw/api-v3-ticker-bookTicker-BTCUSDT.json` | `GET /api/v3/ticker/bookTicker?symbol=BTCUSDT` | single | 200 | 120 | object |
| `raw/fapi-v1-ticker-bookTicker-BTCUSDT.json` | `GET /fapi/v1/ticker/bookTicker?symbol=BTCUSDT` | single | 200 | 150 | object |
| `raw/api-v3-ticker-bookTicker-symbols-batch.json` | `GET /api/v3/ticker/bookTicker?symbols=["BTCUSDT","ETHUSDT","SOLUSDT"]` | batch | 200 | 362 | list len=3 |
| `raw/fapi-v1-ticker-bookTicker-symbols-batch-probe.json` | `GET /fapi/v1/ticker/bookTicker?symbols=[...]` | probe | 200 | ~107k | **full universe** (symbols ignored) |

Normalized:

- `normalized/bookticker-summary.json` — field matrix, counts, samples, integration notes
- `normalized/weight-isolation.json` — sequential IP weight deltas

## Field matrix (observed)

### Spot full / single / batch row

| Field | Type observed | Notes |
|---|---|---|
| `symbol` | string | e.g. `BTCUSDT`, `TSLABUSDT` |
| `bidPrice` | decimal string | buy-1 price; may be `"0.00000000"` on dead pairs |
| `bidQty` | decimal string | buy-1 size |
| `askPrice` | decimal string | sell-1 price |
| `askQty` | decimal string | sell-1 size |

No `time` / `lastUpdateId` on spot bookTicker in this capture.

### Futures full / single row

| Field | Type observed | Notes |
|---|---|---|
| `symbol` | string | e.g. `BTCUSDT`, `XAUUSDT` |
| `bidPrice` | decimal string | buy-1 |
| `bidQty` | decimal string | |
| `askPrice` | decimal string | sell-1 |
| `askQty` | decimal string | |
| `time` | integer ms | book ticker event time |
| `lastUpdateId` | integer | book update id |

## Counts (this capture)

| Market | Rows | `*USDT` suffix | Zero bid | Zero ask | Inverted bid>ask |
|---|---:|---:|---:|---:|---:|
| Spot full | 3639 | 692 | 2282 (all quotes) / 243 of USDT | same pattern | 0 |
| Futures full | 708 | 659 | 1 / 0 of USDT | 0 of USDT | 0 |

Product-relevant samples present:

- Spot bStock legs: `TSLABUSDT`, `MSTRBUSDT`, `NVDABUSDT`, `COINBUSDT` have live bid/ask
- Futures metal: `XAUUSDT`, `XAGUSDT` present on fapi; **no** spot `XAUUSDT`/`XAGUSDT` in this bookTicker (consistent with prior metal no-spot-leg finding); spot `PAXGUSDT` exists

## Weight / rate-limit (measured)

Same-IP sequential headers (spot host and fapi host are **separate** weight pools):

| Call | Observed cumulative / delta |
|---|---|
| Spot full | used-weight-1m reached 14 (minute not proven cold; full weight ≤14) |
| Spot `symbol=BTCUSDT` | **+2** |
| Spot `symbols` batch of 3 | **+4** |
| Futures full | used-weight-1m **5** (matches docs) |
| Futures `symbol=BTCUSDT` | **+2** (matches docs) |

Budget for **once per 60s full pull both sides**:

- Spot: O(1) request, weight on the order of single digits to low teens
- Futures: weight **5**
- Headroom vs typical 6000 IP weight/min: **ample** for 60s cadence

## Batch / multi-symbol findings

1. **Spot** supports `symbols=["A","B",...]` → list of those rows. OK for watchlist.
2. **Futures does NOT honor `symbols=`** in this probe: returned the **full** 708-row payload at full weight 5. Multi-symbol batch is **not** a futures option; only single or full.
3. Therefore for dual-market table refresh: **full×2 is strictly better** than “dozens of single futures calls”.

## Decimal safety

All price/qty fields are JSON strings (spot) or string-like decimals (futures prices). Keep as strings through the wire; do not cast to float.

## Recommended cache shape (for implementers)

```text
_global_source_cache["spot_book_ticker"]    = (monotonic_ts, list_or_map)
_global_source_cache["futures_book_ticker"] = (monotonic_ts, list_or_map)
```

Preferred map form after fetch (join-friendly, no row-loop HTTP):

```json
{
  "BTCUSDT": {
    "bid_price": "64954.00000000",
    "bid_qty": "0.24350000",
    "ask_price": "64954.01000000",
    "ask_qty": "4.91826000"
  }
}
```

Futures may retain `time` / `last_update_id` if useful for freshness display.

## Design fit (current backend)

See `capture.md` § feasibility. Short answer: **yes** — both endpoints are public Group A candidates next to `premium_index` and `price_map`, refreshed on `cache_ttl_seconds` (60).

## Non-goals of this capture

- No contract/schema change
- No production code change
- No private/signed endpoints
- No WebSocket book stream
