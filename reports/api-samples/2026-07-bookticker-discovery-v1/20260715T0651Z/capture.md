# Capture notes: bookTicker discovery

## How captured

```bash
# UTC stamp used for the archive directory
TS=20260715T0651Z
UA=funding-hedging-bookticker-discovery/1.0

curl -sS -A "$UA" -D raw/<name>.headers -o raw/<name>.json \
  "https://api.binance.com/api/v3/ticker/bookTicker"
curl -sS -A "$UA" -D raw/<name>.headers -o raw/<name>.json \
  "https://fapi.binance.com/fapi/v1/ticker/bookTicker"
# plus single-symbol and symbols-batch probes (see evidence-index.md)
```

No API key. Raw bodies + response headers archived under `raw/`.

## Feasibility: 60s loop + cache (current program design)

### Verdict

**Feasible and well-aligned** with the existing live background worker and
Group A source cache. No architectural redesign required.

### Why it fits

1. **Public, no-key** — same class as `premiumIndex` and `ticker/price`
   (`backend/adapters/binance_public.py`).
2. **Independent source_id + TTL** — worker already implements
   `_global_source_cache[source_id] = (monotonic_ts, value)` with
   `_source_due(source_id, now, ttl)` and **success-only timestamp advance**
   (FR-2 / CC-1) in `_refresh_due_sources`
   (`backend/services/snapshot_service.py`).
3. **Group A cadence** — `ttl_a = config.cache_ttl_seconds` (default **60**).
   `premium_index` and `price_map` already use this path. Adding
   `spot_book_ticker` and `futures_book_ticker` as two more Group A sources
   is the natural extension.
4. **Worker tick** — loop wakes every `background_tick_seconds` (default 30s)
   and only fetches sources whose TTL expired. 60s bookTicker refresh does
   not need a new scheduler.
5. **No HTTP in the row loop** — existing rule: fetch once → map → join in
   `build_rows` / assembly. Full bookTicker → `dict[symbol, …]` matches
   `fetch_ticker_price_map`.
6. **Weight** — full fapi bookTicker weight **5**; spot full is low single-digit
   to low teens. Once per 60s is negligible vs IP pools.
7. **Payload size** — ~420 KB spot + ~107 KB futures per minute; fine for a
   local workstation process.

### Suggested integration sketch (not implemented here)

```text
BinancePublicClient
  + fetch_spot_book_ticker()      # GET /api/v3/ticker/bookTicker  (full)
  + fetch_futures_book_ticker()   # GET /fapi/v1/ticker/bookTicker (full)
  optional map helpers → {symbol: {bid, ask, ...}}

SnapshotService._refresh_due_sources (Group A, ttl_a):
  if due("spot_book_ticker"):    cache full spot bookTicker
  if due("futures_book_ticker"): cache full futures bookTicker

Assembly / build_rows:
  join futures.symbol → futures_book_ticker map
  join spot.symbol    → spot_book_ticker map
  (handle only; do not call HTTP)
```

Optional later:

- Click path single-symbol overlay (like `fetch_premium_index_for`) for
  fresher TOB on one row — not required for table 60s freshness.
- Offline fixtures: freeze these raw files into the offline raw dir.

### Caveats for implementers

| Topic | Detail |
|---|---|
| Spot dead pairs | Many non-USDT (and some USDT) rows have zero bid/ask; treat as missing liquidity, not crash |
| Spot vs futures symbol | Join by **resolved leg symbol** (`spot.symbol` may be `TSLABUSDT` while futures is `TSLAUSDT`) |
| Futures multi-symbol | `symbols=` ignored — do not design a multi-symbol futures batch path |
| Mark vs book | `premiumIndex.markPrice` ≠ book mid; keep both if both are shown |
| Contract | Wire schema currently has **no** bid/ask fields; exposing them needs a contract amendment stage |
| Private channel | bookTicker is public; **do not** gate it on `private_channel_enabled` (unlike `price_map` panels today) |
| `price_map` contrast | `price_map` is last trade for USDT valuation and is currently refreshed only when private classic_ref is present; bookTicker for the opportunity table should be **always-on public Group A** |

### Not feasible / not recommended in this design

- Row-loop per-symbol HTTP
- Sub-second REST polling (use WebSocket only if product later requires it)
- Futures “dozens of symbols” multi-GET instead of full (worse weight)

## Sample BTCUSDT (this capture)

Spot:

```json
{"symbol":"BTCUSDT","bidPrice":"64954.00000000","bidQty":"0.24350000","askPrice":"64954.01000000","askQty":"4.91826000"}
```

Futures:

```json
{"symbol":"BTCUSDT","bidPrice":"64925.00","bidQty":"0.103","askPrice":"64925.10","askQty":"14.841","time":1784098317819,"lastUpdateId":11051324939848}
```

Spread and basis differ across markets — expected; do not force equality.
