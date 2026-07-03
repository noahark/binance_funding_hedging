# API Sample Index

Status: frozen by Claude-GLM for stage `2026-07-public-market-contract-v2`.

Sample root:

```text
reports/api-samples/public-market-contract-v2/20260703T051738Z/
```

Layout:

```text
raw/
  fapi-v1-exchangeInfo.json
  fapi-v1-premiumIndex.json
  fapi-v1-fundingRate-BTCUSDT-limit10.json
  api-v3-exchangeInfo-curated-BTCETHXVG.json
  api-v3-exchangeInfo-full-summary.json
  sapi-v1-margin-allPairs-nokey.json
  sapi-v1-margin-isolated-allPairs-nokey.json
normalized/
  build-normalized-sample.py
  public-market-snapshot.json
```

Capture time: `2026-07-03T05:11:29Z` (from premiumIndex `time`). No API key, no
signed endpoint, no private account endpoint.

## Raw Samples

| File | Endpoint | Captured At | Auth Used | Request Params | HTTP | Size | Purpose | Notes |
|---|---|---|---|---|---:|---:|---|---|
| `raw/fapi-v1-exchangeInfo.json` | `GET https://fapi.binance.com/fapi/v1/exchangeInfo` | 2026-07-03T05:11Z | none | none | 200 | 1010490 | Futures symbol universe, `contractType`, `status`, filters. | 818 symbols; `?symbol=` filter was not honored by the server, full set captured. |
| `raw/fapi-v1-premiumIndex.json` | `GET https://fapi.binance.com/fapi/v1/premiumIndex` | 2026-07-03T05:11Z | none | none | 200 | 181985 | mark/index price, `lastFundingRate`, `nextFundingTime`. | 821 entries. |
| `raw/fapi-v1-fundingRate-BTCUSDT-limit10.json` | `GET https://fapi.binance.com/fapi/v1/fundingRate` | 2026-07-03T05:17Z | none | `symbol=BTCUSDT&limit=10` | 200 | 1051 | Settled funding history shape. | 10 entries, each `{symbol,fundingTime,fundingRate,markPrice}`. |
| `raw/api-v3-exchangeInfo-curated-BTCETHXVG.json` | `GET https://api.binance.com/api/v3/exchangeInfo` | 2026-07-03T05:11Z | none | `symbols=["BTCUSDT","ETHUSDT","XVGUSDT"]` | 200 | 15117 | Spot field shapes incl. `isMarginTradingAllowed`, `NOTIONAL.minNotional`, `LOT_SIZE.stepSize`. | Covers margin-allowed and spot-only cases. |
| `raw/api-v3-exchangeInfo-full-summary.json` | `GET https://api.binance.com/api/v3/exchangeInfo` | 2026-07-03T05:11Z | none | none | 200 | 17249896 (body not committed) | Full spot universe metadata. | Summary only: 3625 symbols, status/margin distribution, `NOTIONAL` vs legacy `MIN_NOTIONAL`. The 17.2 MB body is intentionally not committed. |
| `raw/sapi-v1-margin-allPairs-nokey.json` | `GET https://api.binance.com/sapi/v1/margin/allPairs` | 2026-07-03T05:17Z | none | none | 400 | 46 | Evidence that this endpoint requires an API key. | Body `{"code":-2014,"msg":"API-key format invalid."}`. Phase 1 must not use it. |
| `raw/sapi-v1-margin-isolated-allPairs-nokey.json` | `GET https://api.binance.com/sapi/v1/margin/isolated/allPairs` | 2026-07-03T05:17Z | none | none | 400 | 46 | Evidence that this endpoint requires an API key. | Body `{"code":-2014,"msg":"API-key format invalid."}`. Historical isolated-margin context only. |

## Normalized Outputs

| File | Schema | Generated From | Validation Command | Result |
|---|---|---|---|---|
| `normalized/public-market-snapshot.json` | `schemas/api/public-market/snapshot.schema.json` | raw samples via `build-normalized-sample.py` | `python3` + `jsonschema` `Draft202012Validator` (see `60-test-output.txt` §3) | PASS |

## Reproducibility

Regenerate the normalized snapshot:

```bash
cd reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized
python3 build-normalized-sample.py "2026-07-03T05:17:38Z"
```

Re-capture a raw public sample (no key):

```bash
curl -sS "https://fapi.binance.com/fapi/v1/premiumIndex" -o premiumIndex.json
```

Re-run schema validation (requires `jsonschema`; install with
`python3 -m pip install --user jsonschema` if missing):

```bash
python3 - <<'PY'
import json
from jsonschema import Draft202012Validator
schema=json.load(open("schemas/api/public-market/snapshot.schema.json"))
inst=json.load(open("reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/public-market-snapshot.json"))
errs=list(Draft202012Validator(schema).iter_errors(inst))
print("PASS" if not errs else f"FAIL {len(errs)}")
PY
```

Full raw command output, including the auth-matrix live checks and negative
schema tests, is in `60-test-output.txt`.
