# API Field Matrix

Status: template, to be completed by Claude-GLM

## Required Columns

| Normalized Field | Source Endpoint | Raw JSON Path | Observed Type | Nullable | Semantics | Frontend Safe | Evidence File | Notes |
|---|---|---|---|---|---|---|---|---|

## Endpoint Auth Matrix

| Endpoint | Auth Required | Signed Required | Phase 1 Allowed | Evidence | Notes |
|---|---:|---:|---:|---|---|
| `GET /fapi/v1/exchangeInfo` | TBD | TBD | TBD | TBD | USDⓈ-M futures metadata. |
| `GET /fapi/v1/premiumIndex` | TBD | TBD | TBD | TBD | Funding display fields. |
| `GET /fapi/v1/fundingRate` | TBD | TBD | TBD | TBD | Funding history. |
| `GET /api/v3/exchangeInfo` | TBD | TBD | TBD | TBD | Spot metadata. |
| `GET /sapi/v1/margin/allPairs` | TBD | TBD | TBD | TBD | Use only if verified public/no-key. |
| `GET /sapi/v1/margin/isolated/allPairs` | TBD | TBD | TBD | TBD | Verify for historical isolated-margin comparison; do not use for Portfolio Margin routing unless explicitly justified. |

## Required Semantic Checks

- `premiumIndex.lastFundingRate` meaning.
- `premiumIndex.nextFundingTime` meaning and units.
- Futures `contractType` values, including `PERPETUAL` and
  `TRADIFI_PERPETUAL`.
- Futures `status` values and which values are included in Phase 1.
- Spot `status` values and which values are included in Phase 1.
- Spot/margin public support indicators and whether they are authoritative or
  only candidate signals.
- bStock / tokenized equity detection rule and confidence source.
