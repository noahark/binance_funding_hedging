# API Field Matrix

Status: frozen by Claude-GLM for stage `2026-07-public-market-contract-v2`.

Review base: `2bb47ad13065827ed1ee91d5d0e231cd312fdc0a`.

All raw evidence in this matrix is reproducible from the captured public
samples under:

```text
reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/
```

Captured at `2026-07-03T05:11:29Z` (premiumIndex `time` field), no API key,
no signed endpoint, no private account endpoint.

## Endpoint Auth Matrix

Verified live (no API key) and cross-checked against `llms-full.txt`.

| Endpoint | Auth Required | Signed | Phase 1 Allowed | Live no-key result | Evidence |
|---|---:|---:|---:|---|---|
| `GET /fapi/v1/exchangeInfo` | No | No | Yes | HTTP 200, 818 symbols | `raw/fapi-v1-exchangeInfo.json`, `60-test-output.txt` §6 |
| `GET /fapi/v1/premiumIndex` | No | No | Yes | HTTP 200, 821 entries | `raw/fapi-v1-premiumIndex.json`, `60-test-output.txt` §6 |
| `GET /fapi/v1/fundingRate` | No | No | Yes | HTTP 200 | `raw/fapi-v1-fundingRate-BTCUSDT-limit10.json`, `60-test-output.txt` §6 |
| `GET /api/v3/exchangeInfo` | No | No | Yes | HTTP 200, 3625 symbols | `raw/api-v3-exchangeInfo-curated-BTCETHXVG.json`, `raw/api-v3-exchangeInfo-full-summary.json` |
| `GET /sapi/v1/margin/allPairs` | **Yes (API key)** | No (key only) | **No** | HTTP 400 `{"code":-2014,"msg":"API-key format invalid."}` | `raw/sapi-v1-margin-allPairs-nokey.json` |
| `GET /sapi/v1/margin/isolated/allPairs` | **Yes (API key)** | No (key only) | **No** | HTTP 400 `{"code":-2014,"msg":"API-key format invalid."}` | `raw/sapi-v1-margin-isolated-allPairs-nokey.json` |

Notes:

- `allPairs` / `isolated/allPairs` are `sapi` endpoints. They are not signed,
  but they require the `X-MBX-APIKEY` header. Error `-2014` is returned when the
  header is missing or malformed.
- The spot endpoint is large. The curated capture (`BTCUSDT`,`ETHUSDT`,`XVGUSDT`)
  proves the field shapes; the full 17.2 MB body is intentionally not committed
  and is summarized in `raw/api-v3-exchangeInfo-full-summary.json`.

## Margin Conclusion (task item 3)

`GET /sapi/v1/margin/allPairs` and `GET /sapi/v1/margin/isolated/allPairs`
require an API key. Phase 1 forbids API keys, therefore:

- Phase 1 must NOT call either endpoint.
- Phase 1 must NOT derive `MARGIN_SPOT_CANDIDATE` from the `sapi` margin pair
  lists.
- `margin_public.public_cross_margin_pair` stays `null` and
  `margin_public.source` stays `"unverified"` for every row.
- `MARGIN_SPOT_CANDIDATE` classification in Phase 1 uses only the PUBLIC spot
  field `isMarginTradingAllowed` from `GET /api/v3/exchangeInfo`. That field is a
  candidate signal only; it is not proof that the operator's account can borrow
  or trade on margin, so `negative_funding_status` for those rows stays
  `PRIVATE_BORROW_VALIDATION_REQUIRED`.
- `isolated/allPairs` is relevant only as historical FMZ/isolated-margin context.
  The new Portfolio Margin route model does not need it in Phase 1.

## Funding Semantics (task item 4)

From `llms-full.txt` (premiumIndex response field table, e.g. line 50875):

- `lastFundingRate` — "表示(永续合约的)最近更新的资金费率" / "the most recently
  updated funding rate".
- `nextFundingTime` — "表示(永续合约的)下次资金费时间" / "the next funding time".

Conclusion:

- `nextFundingTime` semantics are clear: millisecond epoch of the next scheduled
  funding settlement. Frontend-safe to display as a timestamp.
- `lastFundingRate` semantics are **`ambiguous`** for "current actionable funding".
  The local doc says "most recently updated" but does not state whether the value
  is (a) the rate applied at the last settlement, or (b) a forward estimate for
  the upcoming settlement. Phase 1 must NOT label it as a guaranteed settled rate
  or as a guaranteed upcoming rate. Frontend copy must read it as
  "最近资金费率（premiumIndex.lastFundingRate，最近更新值）" and must not present it
  as "已结算费率" or "预估下一结算费率" without a settle-time sample. The funding
  history endpoint `GET /fapi/v1/fundingRate` is the authoritative source for
  settled past rates (`fundingTime` + `fundingRate`).

Observed: `lastFundingRate` can be negative (e.g. `ARBUSDC` = `-0.00001235` in
the captured `premiumIndex`).

## bStock / TRADIFI_PERPETUAL (task item 5)

Observed `contractType` distribution in the captured fapi `exchangeInfo`
(818 symbols):

- `PERPETUAL`: 696
- `TRADIFI_PERPETUAL`: 118
- `CURRENT_QUARTER`: 2
- `NEXT_QUARTER`: 2

The 118 `TRADIFI_PERPETUAL` symbols are tokenized equities, ETFs, and
commodities, for example `TSLAUSDT`, `MSTRUSDT`, `COINUSDT`, `NVDAUSDT`,
`METAUSDT`, `GOOGLUSDT`, `HOODUSDT`, `INTCUSDT`, `PAYPUSDT`, `PLTRUSDT`,
`AMZNUSDT`, `XAUUSDT` (gold), `XAGUSDT` (silver), `XPTUSDT` (platinum),
`XPDUSDT` (palladium), `COPPERUSDT`, `CLUSDT` (crude oil), `EWJUSDT`,
`EWYUSDT` (ETFs).

Conclusion:

- Rule: `contractType == "TRADIFI_PERPETUAL"` -> `asset_tag = "BSTOCK"`,
  `asset_tag_source = "futures_contractType_tradifi_perpetual"`,
  `asset_tag_confidence = "HIGH"`. No narrower rule is needed; all 118 observed
  TRADIFI symbols are non-crypto real-world assets.
- Rule: `contractType == "PERPETUAL"` -> `asset_tag = "CRYPTO"`,
  `asset_tag_source = "futures_contractType_perpetual"`, confidence `HIGH`.
- `contractType` not in `{PERPETUAL, TRADIFI_PERPETUAL}` (delivery contracts) ->
  not part of the Phase 1 perpetual universe; if ever emitted, `UNKNOWN` with
  `rule_default_unmapped_contractType` and confidence `LOW`.
- `asset_tag` is independent of `route_class`. Proof in the sample: `MSTRUSDT`
  and `TSLAUSDT` are `asset_tag = BSTOCK` AND `route_class = PERP_ONLY_EXCLUDED`
  (all 118 TRADIFI symbols have no spot leg, so they are excluded from execution
  but still tagged BSTOCK).

## Raw Field -> Normalized Field Matrix

Evidence root: `reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/`.

### Futures source: `GET /fapi/v1/exchangeInfo` (symbol object)

| Normalized field | Raw JSON path | Observed type | Nullable | Semantics | FE safe | Evidence |
|---|---|---|---|---|---|---|
| `symbol` | `symbols[].symbol` | string | no | USDⓈ-M contract symbol | yes | `fapi-v1-exchangeInfo.json` |
| `base_asset` | `symbols[].baseAsset` | string | no | base asset | yes | `fapi-v1-exchangeInfo.json` |
| `quote_asset` | `symbols[].quoteAsset` | string | no | always `USDT` in Phase 1 (filtered) | yes | `fapi-v1-exchangeInfo.json` |
| `futures.status` | `symbols[].status` | string | no | `TRADING`/`SETTLING`/`PENDING_TRADING`; Phase 1 includes `TRADING` only | yes | `fapi-v1-exchangeInfo.json` |
| `futures.contract_type` | `symbols[].contractType` | string | no | `PERPETUAL` or `TRADIFI_PERPETUAL` in Phase 1; also drives `asset_tag` | yes | `fapi-v1-exchangeInfo.json` |
| `futures.step_size` | `symbols[].filters[?(@.filterType=="LOT_SIZE")].stepSize` | decimal string | no | quantity step for futures leg | yes | `fapi-v1-exchangeInfo.json` (BTCUSDT `0.001`) |
| `futures.min_notional` | `symbols[].filters[?(@.filterType=="MIN_NOTIONAL")].notional` | decimal string | no | min notional for futures leg | yes | `fapi-v1-exchangeInfo.json` (BTCUSDT `50`) |

### Futures source: `GET /fapi/v1/premiumIndex` (per symbol)

| Normalized field | Raw JSON path | Observed type | Nullable | Semantics | FE safe | Evidence |
|---|---|---|---|---|---|---|
| `futures.mark_price` | `[?(@.symbol==X)].markPrice` | decimal string | no | current mark price | yes | `fapi-v1-premiumIndex.json` |
| `futures.index_price` | `[?(@.symbol==X)].indexPrice` | decimal string | no | current index price | yes | `fapi-v1-premiumIndex.json` |
| `futures.last_funding_rate` | `[?(@.symbol==X)].lastFundingRate` | decimal string (can be negative) | no | "most recently updated funding rate"; `ambiguous` settled-vs-estimate (see Funding Semantics) | yes, with caveat label | `fapi-v1-premiumIndex.json` |
| `futures.next_funding_time` | `[?(@.symbol==X)].nextFundingTime` | integer (ms epoch) | no | next scheduled funding settlement time | yes | `fapi-v1-premiumIndex.json` |
| `data_time` (top-level) | `max([*].time)` | integer ms -> ISO string | no | freshness of the funding/mark snapshot | yes | `fapi-v1-premiumIndex.json` |

### Funding history source: `GET /fapi/v1/fundingRate?symbol=<X>`

| Normalized field | Raw JSON path | Observed type | Nullable | Semantics | FE safe | Evidence |
|---|---|---|---|---|---|---|
| `funding_history[].funding_time` | `[].fundingTime` | integer (ms epoch) | no | settled funding event time | yes | `fapi-v1-fundingRate-BTCUSDT-limit10.json` |
| `funding_history[].funding_rate` | `[].fundingRate` | decimal string (can be negative) | no | settled funding rate at that time | yes | `fapi-v1-fundingRate-BTCUSDT-limit10.json` |

### Spot source: `GET /api/v3/exchangeInfo` (symbol object)

| Normalized field | Raw JSON path | Observed type | Nullable | Semantics | FE safe | Evidence |
|---|---|---|---|---|---|---|
| `spot.symbol` | `symbols[].symbol` | string or null | yes (null when no spot leg) | spot pair symbol if present | yes | `api-v3-exchangeInfo-curated-BTCETHXVG.json` |
| `spot.status` | `symbols[].status` | string or null | yes | `TRADING`/`BREAK`; Phase 1 join uses `TRADING` | yes | curated + `api-v3-exchangeInfo-full-summary.json` |
| `spot.exists` | derived from presence of a `TRADING` spot pair for the same symbol | boolean | no | whether a spot leg exists for the perp | yes | computed |
| `spot.step_size` | `symbols[].filters[?(@.filterType=="LOT_SIZE")].stepSize` | decimal string or null | yes | spot quantity step | yes | curated (BTCUSDT `0.00001000`) |
| `spot.min_notional` | `symbols[].filters[?(@.filterType=="NOTIONAL")].minNotional` | decimal string or null | yes | spot min notional; new `NOTIONAL` filter observed on 100% of 3625 symbols, legacy `MIN_NOTIONAL` = 0 | yes | curated (BTCUSDT `5.00000000`) + full-summary |
| `margin_public.*` | n/a | n/a | n/a | `sapi` margin pair lists need a key; `source="unverified"`, `public_cross_margin_pair=null` | yes | `sapi-v1-margin-allPairs-nokey.json` |

### Route classification (public) source: `GET /api/v3/exchangeInfo` field

| Normalized field | Raw JSON path | Observed type | Nullable | Semantics | FE safe | Evidence |
|---|---|---|---|---|---|---|
| route input | `symbols[].isMarginTradingAllowed` | boolean | no | PUBLIC margin candidate signal; drives `MARGIN_SPOT_CANDIDATE` vs `SPOT_ONLY_CANDIDATE` | yes (as classification input only) | curated (BTCUSDT true, XVGUSDT false) + full-summary |

## Derived Fields (backend classification rules)

These are computed by the backend from the raw fields above. The frontend must
not re-derive them.

| Field | Rule |
|---|---|
| `asset_tag` | `TRADIFI_PERPETUAL` -> `BSTOCK`; `PERPETUAL` -> `CRYPTO`; otherwise `UNKNOWN`. |
| `asset_tag_source` | `futures_contractType_tradifi_perpetual` / `futures_contractType_perpetual` / `rule_default_unmapped_contractType`. |
| `asset_tag_confidence` | `HIGH` for the two contractType rules; `LOW` for the fallback. |
| `route_class` | perp with `TRADING` spot + `isMarginTradingAllowed` -> `MARGIN_SPOT_CANDIDATE`; perp with `TRADING` spot + not margin -> `SPOT_ONLY_CANDIDATE`; perp without spot leg -> `PERP_ONLY_EXCLUDED`. |
| `positive_funding_enabled` | `true` for `MARGIN_SPOT_CANDIDATE` and `SPOT_ONLY_CANDIDATE`; `false` for `PERP_ONLY_EXCLUDED`. |
| `negative_funding_status` | priority: 1) `PERP_ONLY_EXCLUDED` -> `DISABLED_PERP_ONLY`; 2) `BSTOCK` -> `DISABLED_BSTOCK`; 3) `SPOT_ONLY_CANDIDATE` -> `DISABLED_SPOT_ONLY`; 4) `MARGIN_SPOT_CANDIDATE` -> `PRIVATE_BORROW_VALIDATION_REQUIRED`. |
| `ui_flags` | backend-emitted hints, e.g. `MARGIN_PUBLIC_UNVERIFIED`, `PERP_ONLY_NO_SPOT_LEG`, `TRADIFI_BSTOCK`. |

Phase 1 universe observed counts (USDT, `contractType` in `{PERPETUAL,
TRADIFI_PERPETUAL}`, `status == TRADING`): `PERPETUAL` 529 (360 margin
candidate, 1 spot-only, 168 perp-only), `TRADIFI_PERPETUAL` 118 (all perp-only,
no spot leg).

## Observed Enum Values

- Futures `contractType`: `PERPETUAL`, `TRADIFI_PERPETUAL`, `CURRENT_QUARTER`,
  `NEXT_QUARTER`. Phase 1 emits only `PERPETUAL` and `TRADIFI_PERPETUAL`.
- Futures `status`: `TRADING` (692), `SETTLING` (123), `PENDING_TRADING` (3).
  Phase 1 includes `TRADING` only.
- Spot `status`: `TRADING` (1356), `BREAK` (2269). Phase 1 join uses `TRADING`.
- `isMarginTradingAllowed`: `true` (778) / `false` (2847) across all spot
  symbols; 424 of 680 USDT spot pairs allow margin.

## Open Follow-ups (not blocking Phase 1 contract freeze)

- Confirm `lastFundingRate` settled-vs-estimate with a settle-time sample in a
  later phase. Until then, keep the `ambiguous` label.
- Private-phase validation of `MARGIN_SPOT_CANDIDATE` borrowability via
  `/papi/v1/margin/maxBorrowable` (key + signed) is out of Phase 1.
- TRADIFI spot legs: 0 observed today. If Binance lists TRADIFI spot/margin
  pairs later, the route rule already handles `BSTOCK` + spot leg -> still
  `DISABLED_BSTOCK` per priority.
