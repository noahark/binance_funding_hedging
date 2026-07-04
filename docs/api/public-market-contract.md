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
scheduled funding settlement (clear). `lastFundingRate` is the real-time
estimate for the CURRENT funding period and is charged at `nextFundingTime`; it
drifts until settlement — mid-period divergence from settled history is evidenced
under `reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/`
(cycle-mid ETHUSDT/SOLUSDT estimate != latest settled record; 15-min drift
observed in-session). Settled history comes from `/fapi/v1/fundingRate`
(`funding_history`); the estimate must not be presented as a settled value.

bStock / TRADIFI: `contractType == "TRADIFI_PERPETUAL"` maps to
`asset_tag = "BSTOCK"`. `contractType == "PERPETUAL"` maps to `CRYPTO`.
`asset_tag` is independent of `route_class`.

Frozen amendment (2026-07-03, stage `2026-07-public-market-bstock-alias-v1`):
Binance added bStocks assets as Margin collateral and opened corresponding
bStocks spot/margin pairs. The TRADIFI futures symbols use the underlying equity
symbol (`TSLAUSDT`, `MSTRUSDT`, `NVDAUSDT`), while the spot/margin bStocks
symbols add a `B` suffix (`TSLABUSDT`, `MSTRBUSDT`, `NVDABUSDT`). The route rule
therefore cannot rely only on exact futures/spot symbol equality. The frozen
spot-leg resolution rule is implemented in
`backend/domain/normalize.py:resolve_spot_leg`:

1. normal crypto: join by exact symbol (`BTCUSDT` -> `BTCUSDT`) ->
   `spot.match_type = "exact_symbol"`;
2. `TRADIFI_PERPETUAL` / `BSTOCK`: first try exact, then try the alias
   `futures.baseAsset + "B" + futures.quoteAsset` (`TSLAUSDT` -> `TSLABUSDT`);
   on alias hit `spot.match_type = "bstock_b_suffix_alias"`. The alias fires ONLY
   for `TRADIFI_PERPETUAL`, so normal crypto exact matching is never polluted;
3. no spot leg found -> `spot.exists = false`, `spot.match_type = null`, route
   `PERP_ONLY_EXCLUDED`.

Consequences (driven entirely by the existing classifier, unchanged this stage):

- if the alias spot pair exists and public `isMarginTradingAllowed=true`, the row
  becomes `MARGIN_SPOT_CANDIDATE` with `positive_funding_enabled=true`, while
  `asset_tag` stays `BSTOCK`;
- bStock negative-funding execution remains disabled: the existing
  `negative_funding_status` priority ranks `asset_tag=BSTOCK` ahead of the
  candidate route, so a bStock row resolves to `DISABLED_BSTOCK` (Binance states
  borrowing is not currently supported for bStocks) even though its candidate
  route is open;
- the bStock collateral ratio is dynamic/unknown in Phase 1; no ratio is
  hard-coded and `margin_public.source` stays `"unverified"`.

The actual spot leg symbol and machine-visible match source are exposed as
`spot.symbol` and `spot.match_type` (see Enums).

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
    "match_type": "exact_symbol",
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

This priority is unchanged by the bStock alias amendment; BSTOCK stays in
position 2, so a bStock candidate row still resolves to `DISABLED_BSTOCK`.

`spot.match_type` (nullable; `null` when `spot.exists = false`):

- `exact_symbol`
- `bstock_b_suffix_alias`

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
- RESOLVED (2026-07-04, stage `2026-07-public-market-ui-cn-v1`): `nextFundingTime`
  is clear. `lastFundingRate` is the real-time estimate for the current funding
  period, charged at `nextFundingTime`, drifting until settlement; proven by the
  mid-period divergence evidence under
  `reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/`
  (`verify-funding-semantics.py` PASS). It is not a settled value; settled history
  comes from `/fapi/v1/fundingRate`.
- RESOLVED (amended 2026-07-03, stage `2026-07-public-market-bstock-alias-v1`):
  `TRADIFI_PERPETUAL` symbols are tagged `BSTOCK`, and their spot legs are joined
  via the `baseAsset + "B" + quoteAsset` alias. The positive-funding candidate
  route is open when the alias spot pair has `isMarginTradingAllowed=true`;
  bStock negative funding stays `DISABLED_BSTOCK`. The bStock collateral ratio
  remains dynamic/unknown (not hard-coded).

Remaining (non-blocking, later phase):

- Settle-time sample to remove the `lastFundingRate` ambiguity.
- Private borrowability validation for `MARGIN_SPOT_CANDIDATE`.
