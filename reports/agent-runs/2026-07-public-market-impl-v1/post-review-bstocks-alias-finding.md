# Post-Review Finding: bStocks B-Suffix Spot/Margin Alias

Stage: `2026-07-public-market-impl-v1`
Finding time: 2026-07-03 22:44 CST
Severity: P1 contract amendment required before user final acceptance

## Summary

After `review-2` accepted the implementation against the frozen
`public-market-contract-v2`, Binance announced and exposed live public data for
15 bStocks margin/collateral assets whose spot/margin symbols use a `B` suffix.
The implementation correctly tags `TRADIFI_PERPETUAL` futures as `BSTOCK`, but
it still joins futures to spot by exact symbol equality. That misses the newly
supported bStocks spot legs.

Examples:

| Futures TRADIFI symbol | Futures baseAsset | Actual bStock spot/margin symbol |
|---|---|---|
| `TSLAUSDT` | `TSLA` | `TSLABUSDT` |
| `MSTRUSDT` | `MSTR` | `MSTRBUSDT` |
| `NVDAUSDT` | `NVDA` | `NVDABUSDT` |

## Live Evidence

Observed via public no-key endpoints on 2026-07-03:

- `GET /fapi/v1/exchangeInfo`: TRADIFI futures exist as non-`B` symbols such as
  `TSLAUSDT`, `MSTRUSDT`, `NVDAUSDT`.
- `GET /api/v3/exchangeInfo`: the corresponding bStocks spot/margin pairs exist
  as `baseAsset + "B" + quoteAsset`, e.g. `TSLABUSDT`, `MSTRBUSDT`,
  `NVDABUSDT`, and report `status=TRADING`, `isMarginTradingAllowed=true`.
- Binance Margin asset table (`/bapi/margin/v1/public/margin/asset/all`) reports
  the 15 bStocks assets as `isMortgageable=true`, `isBorrowable=false`,
  `isAllowOpenLong=true`, `isAllowOpenShort=false`, `leverage="5"`.
- Collateral ratio percentage is not available from the no-key environment:
  official FAQ says bStocks collateral ratios vary by token and may change, and
  `/sapi/v1/margin/crossMarginCollateralRatio`,
  `/sapi/v1/portfolio/collateralRate`, and
  `/sapi/v2/portfolio/collateralRate` returned `-2014 API-key format invalid`
  without credentials.

Current implementation live check:

```text
TSLAUSDT -> route_class=PERP_ONLY_EXCLUDED, spot.symbol=null
MSTRUSDT -> route_class=PERP_ONLY_EXCLUDED, spot.symbol=null
NVDAUSDT -> route_class=PERP_ONLY_EXCLUDED, spot.symbol=null
... all 15 announced bStocks remain PERP_ONLY_EXCLUDED
```

That classification is now stale for positive-funding candidate discovery.

## Required Contract Amendment

The public-market contract must add a bStocks spot-leg alias rule:

1. For normal `PERPETUAL` crypto symbols, join futures to spot by exact symbol:
   `futures.symbol == spot.symbol`.
2. For `TRADIFI_PERPETUAL` / `BSTOCK` symbols, first attempt the bStock alias:
   `futures.baseAsset + "B" + futures.quoteAsset`.
3. If that alias exists in public spot `exchangeInfo` and
   `isMarginTradingAllowed=true`, classify the row as
   `MARGIN_SPOT_CANDIDATE` for positive-funding hedging, while preserving
   `asset_tag=BSTOCK`.
4. Negative-funding execution remains disabled for bStocks because borrowing is
   not currently supported. The expected status is `DISABLED_BSTOCK`, not
   `PRIVATE_BORROW_VALIDATION_REQUIRED`.
5. Expose the actual spot leg symbol in API output and UI, e.g.
   `futures.symbol=TSLAUSDT`, `spot.symbol=TSLABUSDT`, and add a machine-visible
   source such as `spot.match_type=bstock_b_suffix_alias`.
6. Collateral haircut must be dynamic/unknown until a signed or page-backed
   source is integrated. Do not hard-code 100%, 90%, or any other ratio.

## Impact

The completed `review-2` remains valid for the frozen contract it reviewed, but
the frozen contract is now known to be incomplete for live bStocks discovery.
User final acceptance should wait until a follow-up amendment stage updates:

- `docs/api/public-market-contract.md`
- `schemas/api/public-market/snapshot.schema.json` if a new `spot.match_type` or
  collateral fields are added
- backend bStocks matching/classification tests
- frontend display for futures symbol vs bStock spot symbol

## Operational Footer

本地北京时间: 2026-07-03 22:44:49 CST
下一步模型: Claude-GLM controller
下一步任务: Create a bStocks alias contract amendment and repair backend/frontend classification before user final acceptance.
