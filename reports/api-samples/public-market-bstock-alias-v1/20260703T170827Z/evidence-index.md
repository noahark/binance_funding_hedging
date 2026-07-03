# Evidence Index — bStock B-suffix alias (public market)

- Capture id: `20260703T170827Z`
- Stage: `2026-07-public-market-bstock-alias-v1`
- fapi serverTime at capture: `1783094417611` (2026-07-03T16:00:17Z); timezone `UTC`
- spot serverTime at capture: `1783098512988` (2026-07-03T17:08:32Z); timezone `UTC`
- fapi symbols captured: 820; spot symbols captured: 3625

## Source endpoints (PUBLIC, anonymous, read-only)

- `https://fapi.binance.com/fapi/v1/exchangeInfo` (USD-M futures)
- `https://api.binance.com/api/v3/exchangeInfo` (spot / margin)

No API key, signature, cookie, or account token was used. The response
headers are preserved alongside each payload.

## Capture commands (reproducible)

```bash
# from this capture directory (raw/ already created)
curl -sS -m 60 -o raw/fapi-v1-exchangeInfo.json \
  -D raw/fapi-v1-exchangeInfo.headers \
  -w 'http=%{http_code} bytes=%{size_download}\n' \
  https://fapi.binance.com/fapi/v1/exchangeInfo
curl -sS -m 90 -o raw/api-v3-exchangeInfo.json \
  -D raw/api-v3-exchangeInfo.headers \
  -w 'http=%{http_code} bytes=%{size_download}\n' \
  https://api.binance.com/api/v3/exchangeInfo
```

## NOT called (stage hard constraints)

- No signed endpoint, no API key, no private account endpoint, no user
  data stream, no listenKey.
- No `/sapi/*`, no `/fapi/v1/order`, no `/dapi/v1/order`, no borrow, no
  repay, no transfer, no websocket.

## Files (raw/)

| file | bytes | sha256 |
|---|---:|---|
| raw/fapi-v1-exchangeInfo.json | 1012801 | `8688486f1e0526026188c0cc275255028ff8428ed80f9611ab59d14d9dd95664` |
| raw/api-v3-exchangeInfo.json | 17249848 | `a586f74ceaf81856fe105892abc7fcd3c8b68b71e428b4386742474484fb321a` |
| raw/fapi-v1-exchangeInfo.headers | 888 | `302dd2a22d6a55433848f63aa684d34bd2185701361dcf2d6d95c36869d4e391` |
| raw/api-v3-exchangeInfo.headers | 947 | `d3dd38cda17768e3f287bdcd58f2a02a312e3cba15d2e6c659a5d6575bdcec76` |

## Alias rule under test

A bStock futures symbol has baseAsset WITHOUT a trailing `B` and
`contractType=TRADIFI_PERPETUAL`; its public spot/margin leg carries a
trailing `B`, joined as `futures_baseAsset + "B" + quoteAsset`
(e.g. futures `TSLAUSDT` -> spot `TSLABUSDT`). Backend
`resolve_spot_leg` gates this alias on
`contract_type == "TRADIFI_PERPETUAL"`, after exact-symbol matching
fails.

## Cross-verification (15 user-listed bStocks)

| bstock_base | spot_leg | spot_exists | marginAllowed | futures_leg | fut_exists | contractType | status | underlyingType | quote | alias_match |
|---|---|---|---|---|---|---|---|---|---|---|
| CRCLB | CRCLBUSDT | True | True | CRCLUSDT | True | TRADIFI_PERPETUAL | TRADING | EQUITY | USDT | True |
| MUB | MUBUSDT | True | True | MUUSDT | True | TRADIFI_PERPETUAL | TRADING | EQUITY | USDT | True |
| NVDAB | NVDABUSDT | True | True | NVDAUSDT | True | TRADIFI_PERPETUAL | TRADING | EQUITY | USDT | True |
| SNDKB | SNDKBUSDT | True | True | SNDKUSDT | True | TRADIFI_PERPETUAL | TRADING | EQUITY | USDT | True |
| TSLAB | TSLABUSDT | True | True | TSLAUSDT | True | TRADIFI_PERPETUAL | TRADING | EQUITY | USDT | True |
| SPCXB | SPCXBUSDT | True | True | SPCXUSDT | True | TRADIFI_PERPETUAL | TRADING | EQUITY | USDT | True |
| AMDB | AMDBUSDT | True | True | AMDUSDT | True | TRADIFI_PERPETUAL | TRADING | EQUITY | USDT | True |
| EWYB | EWYBUSDT | True | True | EWYUSDT | True | TRADIFI_PERPETUAL | TRADING | EQUITY | USDT | True |
| INTCB | INTCBUSDT | True | True | INTCUSDT | True | TRADIFI_PERPETUAL | TRADING | EQUITY | USDT | True |
| MSTRB | MSTRBUSDT | True | True | MSTRUSDT | True | TRADIFI_PERPETUAL | TRADING | EQUITY | USDT | True |
| LITEB | LITEBUSDT | True | True | LITEUSDT | True | TRADIFI_PERPETUAL | TRADING | EQUITY | USDT | True |
| METAB | METABUSDT | True | True | METAUSDT | True | TRADIFI_PERPETUAL | TRADING | EQUITY | USDT | True |
| MSFTB | MSFTBUSDT | True | True | MSFTUSDT | True | TRADIFI_PERPETUAL | TRADING | EQUITY | USDT | True |
| PLTRB | PLTRBUSDT | True | True | PLTRUSDT | True | TRADIFI_PERPETUAL | TRADING | EQUITY | USDT | True |
| QQQB | QQQBUSDT | True | True | QQQUSDT | True | TRADIFI_PERPETUAL | TRADING | EQUITY | USDT | True |

## Summary

- spot legs present: 15/15
- `isMarginTradingAllowed=true`: 15/15
- futures legs present: 15/15
- `contractType=TRADIFI_PERPETUAL`: 15/15
- futures_baseAsset + "B" + quoteAsset == spot_symbol: 15/15
- quote assets observed in this batch: ['USDT'] (all USDT — consistent with the current USDT-quote assumption in `build_rows`).

## Context (recorded for completeness; not the verification set)

This capture contains `118` TRADIFI_PERPETUAL contracts in fapi.
The 15 user-listed bStocks above are the verification subset. Full list:

```
AAOIUSDT, AAPLUSDT, ADBEUSDT, ALABUSDT, AMATUSDT, AMDUSDT, AMZNUSDT, ANTHROPICUSDT, ARMUSDT, ASMLUSDT, ASTSUSDT, AVGOUSDT, AXTIUSDT, BABAUSDT, BBXUSDT, BEUSDT, BMNRUSDT, BRKBUSDT, BSPUSDT, BXUSDT, BZUSDT, CATUSDT, CBRSUSDT, CIENUSDT, CLUSDT, COHRUSDT, COINUSDT, COPPERUSDT, COSTUSDT, CRCLUSDT, CRDOUSDT, CRMUSDT, CRWDUSDT, CRWVUSDT, CSCOUSDT, DELLUSDT, DISUSDT, DKNGUSDT, DRAMUSDT, EBAYUSDT, EWJUSDT, EWTUSDT, EWYUSDT, EWZUSDT, FLEXUSDT, FLNCUSDT, GLWUSDT, GMEUSDT, GOOGLUSDT, HDUSDT, HIMSUSDT, HOODUSDT, HPEUSDT, HYUNDAIUSDT, IBMUSDT, INTCUSDT, IRENUSDT, IWMUSDT, JPMUSDT, KLACUSDT, KORUUSDT, KSTRUSDT, LITEUSDT, LLYUSDT, LRCXUSDT, METAUSDT, MRVLUSDT, MSFTUSDT, MSTRUSDT, MUUSDT, MVLLUSDT, NATGASUSDT, NBISUSDT, NFLXUSDT, NOKUSDT, NOWUSDT, NVDAUSDT, NVOUSDT, ONDSUSDT, OPENAIUSDT, ORCLUSDT, PAYPUSDT, PLTRUSDT, QCOMUSDT, QNTXUSDT, QQQUSDT, RIVNUSDT, RKLBUSDT, SAMSUNGUSDT, SKHYNIXUSDT, SMCIUSDT, SNDKUSDT, SONYUSDT, SOXLUSDT, SPCXUSDT, SPYUSDT, SQQQUSDT, STRCUSDT, STXXUSDT, TERUSDT, TQQQUSDT, TSLAUSDT, TSMUSDT, TTWOUSDT, TXNUSDT, UBERUSDT, URNMUSDT, USARUSDT, UVXYUSDT, VUSDT, WDCUSDT, WMTUSDT, XAGUSDT, XAUUSDT, XLEUSDT, XPDUSDT, XPTUSDT, ZMUSDT
```
