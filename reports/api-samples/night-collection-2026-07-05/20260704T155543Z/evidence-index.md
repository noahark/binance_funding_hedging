# Night collection evidence index

- captured_at_utc: `2026-07-04T15:56:44Z`
- captured_by: Kimi (night-collection goal)
- source: `reports/api-samples/night-collection-2026-07-05/`
- total HTTP calls: 15

## Endpoint call counts

- `https://api.binance.com/api/v3/exchangeInfo`: 1
- `https://api.binance.com/sapi/v1/margin/allAssets`: 1
- `https://api.binance.com/sapi/v1/margin/allPairs`: 1
- `https://api.binance.com/sapi/v1/margin/crossMarginData`: 1
- `https://fapi.binance.com/fapi/v1/exchangeInfo`: 1
- `https://fapi.binance.com/fapi/v1/fundingInfo`: 1
- `https://fapi.binance.com/fapi/v1/fundingRate`: 6
- `https://fapi.binance.com/fapi/v1/premiumIndex`: 1
- `https://papi.binance.com/papi/v1/margin/maxBorrowable`: 2

## Archived files

| file | logical path | type | status | sha256 |
|---|---|---|---|---|
| `fapi-v1-exchangeInfo.json` | `https://fapi.binance.com/fapi/v1/exchangeInfo` | public | 200 | `8c639129432878dda8f5749a699fd4bab18077e6501328e1a5f754be847a8cf8` |
| `fapi-v1-premiumIndex.json` | `https://fapi.binance.com/fapi/v1/premiumIndex` | public | 200 | `36264683e8266e14b124cf1e324e4871f1ff0df5963e4dda185bd8d848d00578` |
| `fapi-v1-fundingInfo.json` | `https://fapi.binance.com/fapi/v1/fundingInfo` | public | 200 | `a9d411bf010882a9c235e37655765f0f7d83be318d0144d7fbc4bddbc8efa197` |
| `api-v3-exchangeInfo.json` | `https://api.binance.com/api/v3/exchangeInfo` | public | 200 | `d241e0186087622f1dba46f74f0c05953777f444734fc5ae5b3a832026caaf71` |
| `fapi-v1-fundingRate-BTCUSDT-limit20.json` | `https://fapi.binance.com/fapi/v1/fundingRate` | public | 200 | `3b3595ee52020cd551d0b22c21e1c5494766889b589fdcee6bc57fc8e7a55579` |
| `fapi-v1-fundingRate-ETHUSDT-limit20.json` | `https://fapi.binance.com/fapi/v1/fundingRate` | public | 200 | `61442a8270e5b9b24384469ff17decc55416d5b42cb162f2e1b1b18703a9a952` |
| `fapi-v1-fundingRate-SOLUSDT-limit20.json` | `https://fapi.binance.com/fapi/v1/fundingRate` | public | 200 | `5c06e77dd9e2ee558e8de0b9068b0f66463da86eaed58fd25561532de8df7039` |
| `fapi-v1-fundingRate-XRPUSDT-limit20.json` | `https://fapi.binance.com/fapi/v1/fundingRate` | public | 200 | `7f9d68e9c79dafa326ed4707b9e8cd2af20a0aa87e79c979697db06b28dd65e1` |
| `fapi-v1-fundingRate-DOGEUSDT-limit20.json` | `https://fapi.binance.com/fapi/v1/fundingRate` | public | 200 | `b47ec82f763ae5a88960fb33d49877dd4296eaa51274c3ddbb3c5f7457c14ef5` |
| `fapi-v1-fundingRate-BNBUSDT-limit20.json` | `https://fapi.binance.com/fapi/v1/fundingRate` | public | 200 | `a726183ee9947c373450068f6e7a6d215ab7b099d510adb5a7483fc802689fec` |
| `classic_allPairs.json` | `https://api.binance.com/sapi/v1/margin/allPairs` | private | 200 | `15dcff73cdee9f826ed92d60234f9b3c96bb751404c8c736840d62b11e39436b` |
| `classic_allAssets.json` | `https://api.binance.com/sapi/v1/margin/allAssets` | private | 200 | `58de526099bed9636d6ea0bf2922767671da49b8ff4576fed9480eac4c20f2e4` |
| `classic_crossMarginData.json` | `https://api.binance.com/sapi/v1/margin/crossMarginData` | private | 200 | `4da974f912d91f17907163a1bf5225cf0c2696c55f075f1e42acda53855bed6b` |
| `portfolio_maxBorrowable_BTC.json` | `https://papi.binance.com/papi/v1/margin/maxBorrowable` | private | 200 | `d0b34158936190cbe2e66f936ec3a875785e8a522763fad57d1e27f223c80bce` |
| `portfolio_maxBorrowable_ETH.json` | `https://papi.binance.com/papi/v1/margin/maxBorrowable` | private | 200 | `d0b34158936190cbe2e66f936ec3a875785e8a522763fad57d1e27f223c80bce` |

## Redaction policy

- URL query strings stripped from all archived metadata (only logical path kept); key/secret/signature/recvWindow/timestamp never archived.
- Account-level `maxBorrowable` responses: `amount` and `borrowLimit` numeric-string fields replaced with placeholders; structure and string type preserved.
- Market-level responses are public market data; no amount redaction.

## Gate status

All configured endpoints captured successfully; no credentials detected in archived files.
