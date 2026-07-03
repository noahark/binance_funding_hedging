# Public Market API Contract

Status: contract v0.1, response shape unchanged. Binance public fields verified
2026-07-03 by Claude-GLM against live no-key public calls and `llms-full.txt`.
Verified findings are recorded below in "Verified Findings" and in
`reports/agent-runs/2026-07-public-market-contract-v2/api-field-matrix.md`.

Owner: Claude-GLM for field verification and backend implementation. Kimi may
start frontend integration only after this contract and the matching JSON schema
are frozen for the stage.

## Purpose

Define the backend-to-frontend contract for Phase 1 public market discovery.
This contract lets the frontend show Binance USDⓈ-M perpetual funding
opportunities, spot or margin route candidates, bStock tags, and planning inputs
without calling Binance or interpreting Binance-specific fields directly.

## Phase 1 Scope

Allowed:

- Public Binance REST endpoints only.
- Raw request and response capture for documentation and replay.
- Normalized backend snapshot API for frontend consumption.
- JSON schema validation for backend output.

Forbidden:

- API keys.
- Signed endpoints.
- Private account endpoints.
- User data streams.
- Order, borrow, repay, transfer, or websocket execution paths.
- Frontend direct calls to Binance.

## Binance Source Endpoints To Verify

Claude-GLM must verify each endpoint against `llms-full.txt` and a live/public
or locally captured payload before implementation. If an endpoint requires auth,
record it as out of Phase 1 instead of using it.

| Source | Endpoint | Phase 1 Use |
|---|---|---|
| USDⓈ-M Futures | `GET /fapi/v1/exchangeInfo` | Futures symbols, `contractType`, `status`, assets, and futures filters. |
| USDⓈ-M Futures | `GET /fapi/v1/premiumIndex` | Mark price, index price, current funding-rate field, and next funding time. |
| USDⓈ-M Futures | `GET /fapi/v1/fundingRate` | Recent funding history for ranked or sampled symbols. |
| Spot | `GET /api/v3/exchangeInfo` | Spot symbols, `status`, filters, and public spot/margin indicators if present. |
| Margin | `GET /sapi/v1/margin/allPairs` | Candidate cross-margin pair support only if verified as public/no-key or explicitly marked as out of Phase 1. |
| Margin | `GET /sapi/v1/margin/isolated/allPairs` | Historical FMZ isolated-margin comparison only unless the new Portfolio Margin route model explicitly needs it. Verify auth requirements before use. |

## Verified Findings

Frozen 2026-07-03. Evidence: raw public samples under
`reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/` and live
no-key HTTP checks in
`reports/agent-runs/2026-07-public-market-contract-v2/60-test-output.txt`.

Endpoint auth (no API key used):

- `GET /fapi/v1/exchangeInfo`, `/fapi/v1/premiumIndex`, `/fapi/v1/fundingRate`,
  and `GET /api/v3/exchangeInfo` are public/no-key (HTTP 200 without key) and are
  allowed in Phase 1.
- `GET /sapi/v1/margin/allPairs` and `GET /sapi/v1/margin/isolated/allPairs`
  require an API key: without a key they return HTTP 400 with
  `{"code":-2014,"msg":"API-key format invalid."}`. Phase 1 forbids keys, so they
  are not used.

Margin conclusion: because the `sapi` margin pair lists require a key,
`margin_public.source` is `"unverified"` and `public_cross_margin_pair` is `null`
for every row. `MARGIN_SPOT_CANDIDATE` classification uses only the PUBLIC spot
field `isMarginTradingAllowed` from `/api/v3/exchangeInfo`, which is a candidate
signal only. `negative_funding_status` for those rows stays
`PRIVATE_BORROW_VALIDATION_REQUIRED`.

Funding semantics: `nextFundingTime` is the millisecond epoch of the next
scheduled funding settlement (clear). `lastFundingRate` is documented by Binance
as "the most recently updated funding rate"; the settled-vs-estimate distinction
is `ambiguous`, so the field must be displayed as "最近资金费率（最近更新值）" and
must not be labeled as a guaranteed settled or upcoming rate. Settled past rates
come from `/fapi/v1/fundingRate` (`funding_history`).

bStock / TRADIFI: `contractType == "TRADIFI_PERPETUAL"` maps to
`asset_tag = "BSTOCK"` (118 observed symbols, all tokenized equities/ETFs/
commodities, all without a spot leg). `contractType == "PERPETUAL"` maps to
`CRYPTO`. `asset_tag` is independent of `route_class`; the sample contains
`MSTRUSDT` / `TSLAUSDT` rows that are `BSTOCK` + `PERP_ONLY_EXCLUDED`.

Spot min notional: all 3625 observed spot symbols use the new `NOTIONAL` filter
(`minNotional` key); the legacy `MIN_NOTIONAL` filter is 0 observed. The backend
extractor reads `NOTIONAL.minNotional`.

## Required Claude-GLM Outputs

Before backend implementation, Claude-GLM must produce:

- `reports/agent-runs/2026-07-public-market-contract-v2/api-field-matrix.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/api-sample-index.md`
- Raw sample files under
  `reports/api-samples/public-market-contract-v2/<timestamp>/raw/`
- Normalized sample files under
  `reports/api-samples/public-market-contract-v2/<timestamp>/normalized/`
- Updated schema files under `schemas/api/public-market/`

The field matrix must list, for every field used by backend or frontend:

- Source endpoint.
- Raw JSON path.
- Type observed in sample.
- Nullability.
- Semantic meaning.
- Whether the field is safe for frontend display.
- Any ambiguity or required follow-up.

## Backend API

Initial endpoint for Kimi frontend integration:

```text
GET /api/public-market/snapshot
```

Response shape:

```json
{
  "schema_version": "public-market-snapshot/v1",
  "generated_at": "2026-07-03T00:00:00Z",
  "data_time": "2026-07-03T00:00:00Z",
  "source_sample_id": "20260703T000000Z",
  "summary": {
    "total_rows": 0,
    "route_counts": {},
    "asset_tag_counts": {},
    "negative_funding_status_counts": {}
  },
  "rows": [],
  "warnings": []
}
```

Each `rows[]` item must include:

```json
{
  "symbol": "BTCUSDT",
  "base_asset": "BTC",
  "quote_asset": "USDT",
  "asset_tag": "CRYPTO",
  "asset_tag_source": "exchange_or_rule",
  "asset_tag_confidence": "HIGH",
  "route_class": "MARGIN_SPOT_CANDIDATE",
  "positive_funding_enabled": true,
  "negative_funding_status": "PRIVATE_BORROW_VALIDATION_REQUIRED",
  "futures": {
    "symbol": "BTCUSDT",
    "status": "TRADING",
    "contract_type": "PERPETUAL",
    "mark_price": "0",
    "index_price": "0",
    "last_funding_rate": "0",
    "next_funding_time": 0,
    "min_notional": "0",
    "step_size": "0"
  },
  "spot": {
    "symbol": "BTCUSDT",
    "status": "TRADING",
    "exists": true,
    "min_notional": "0",
    "step_size": "0"
  },
  "margin_public": {
    "public_cross_margin_pair": null,
    "source": "unverified"
  },
  "funding_history": [],
  "ui_flags": []
}
```

## Enums

`asset_tag`:

- `CRYPTO`
- `BSTOCK`
- `UNKNOWN`

`asset_tag_confidence`:

- `HIGH`
- `MEDIUM`
- `LOW`

`route_class`:

- `MARGIN_SPOT_CANDIDATE`
- `SPOT_ONLY_CANDIDATE`
- `PERP_ONLY_EXCLUDED`

`negative_funding_status`:

- `PRIVATE_BORROW_VALIDATION_REQUIRED`
- `DISABLED_BSTOCK`
- `DISABLED_SPOT_ONLY`
- `DISABLED_PERP_ONLY`

Priority for `negative_funding_status`:

1. `PERP_ONLY_EXCLUDED` -> `DISABLED_PERP_ONLY`
2. `asset_tag = BSTOCK` -> `DISABLED_BSTOCK`
3. `SPOT_ONLY_CANDIDATE` -> `DISABLED_SPOT_ONLY`
4. `MARGIN_SPOT_CANDIDATE` -> `PRIVATE_BORROW_VALIDATION_REQUIRED`

## Frontend Integration Rules

- Kimi must consume only `GET /api/public-market/snapshot` or matching fixture
  JSON generated from this schema.
- Kimi must not call Binance directly.
- Kimi must not invent route or asset classification logic.
- If a required UI field is absent from the contract, Kimi must mark the
  integration blocked and request a contract update.
- UI copy must keep the agreed Chinese workstation style.

## Open Verification Items

Resolution status as of 2026-07-03 (see "Verified Findings" and
`api-field-matrix.md` for evidence):

- RESOLVED: `GET /sapi/v1/margin/allPairs` requires an API key (HTTP 400 code
  `-2014` without key). Phase 1 does not use it.
- RESOLVED: `GET /sapi/v1/margin/isolated/allPairs` has the same key requirement
  and is treated as historical FMZ/isolated-margin context only. The Portfolio
  Margin route model does not need it in Phase 1.
- RESOLVED: because the margin endpoints require a key, Phase 1 keeps
  `margin_public.source = "unverified"` and does not produce
  `MARGIN_SPOT_CANDIDATE` from the `sapi` lists. It uses only the public spot
  `isMarginTradingAllowed` field.
- PARTIALLY RESOLVED: `nextFundingTime` is clear. `lastFundingRate` is
  "most recently updated funding rate" and its settled-vs-estimate meaning is
  `ambiguous`; it is not labeled as settled funding.
- RESOLVED: all observed `TRADIFI_PERPETUAL` symbols are tagged `BSTOCK`; no
  narrower rule is needed.

Remaining (non-blocking, later phase):

- Settle-time sample to remove the `lastFundingRate` ambiguity.
- Private borrowability validation for `MARGIN_SPOT_CANDIDATE`.
