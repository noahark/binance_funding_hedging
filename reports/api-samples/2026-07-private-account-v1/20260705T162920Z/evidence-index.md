# Discovery evidence index — 2026-07-private-account-v1

- captured_at_utc: `20260705T162920Z`
- captured_by: bookkeeper (claude_glm fresh session, H_intake)
- base_urls: api.binance.com (sapi/api) / papi.binance.com (papi); hardcoded in script
- total HTTP calls: 14 across 13 logical endpoints
- endpoint call counts (whitelist proof):
  - `GET /api/v3/account`: 1
  - `GET /api/v3/ticker/price`: 1
  - `GET /papi/v1/balance`: 1
  - `GET /papi/v1/margin/marginInterestHistory`: 1
  - `GET /papi/v1/margin/maxBorrowable`: 2
  - `GET /papi/v1/portfolio/interest-history`: 1
  - `GET /papi/v1/um/positionRisk`: 1
  - `GET /sapi/v1/account/info`: 1
  - `GET /sapi/v1/margin/allAssets`: 1
  - `GET /sapi/v1/margin/allPairs`: 1
  - `GET /sapi/v1/margin/crossMarginData`: 1
  - `GET /sapi/v1/margin/interestRateHistory`: 1
  - `GET /sapi/v1/margin/next-hourly-interest-rate`: 1

## Archived files (sha256 of redacted content)

| file | logical path | status | account-level | amounts redacted | sha256 |
|---|---|---|---|---|---|
| `api-v3-ticker-price.json` | `/api/v3/ticker/price` | 200 | False | False | `a4717fcd1370f637818c0ac92bff74f4b40e5c166a8dc28fb9518bafc45149c9` |
| `sapi-v1-margin-allPairs.json` | `/sapi/v1/margin/allPairs` | 400 | False | False | `a1fb51e00fa391ad5ffa6d379ea39743d232ffeafa1121bf95267adefa0b9fb7` |
| `sapi-v1-margin-allAssets.json` | `/sapi/v1/margin/allAssets` | 400 | False | False | `a1fb51e00fa391ad5ffa6d379ea39743d232ffeafa1121bf95267adefa0b9fb7` |
| `sapi-v1-margin-crossMarginData.json` | `/sapi/v1/margin/crossMarginData` | 400 | False | False | `a1fb51e00fa391ad5ffa6d379ea39743d232ffeafa1121bf95267adefa0b9fb7` |
| `sapi-v1-account-info.json` | `/sapi/v1/account/info` | 400 | True | True | `97d258677b0bc4ec53436f7a9da7a26a102b681583fe55a73de5bcc9e88bc783` |
| `sapi-v1-margin-next-hourly-interest-rate.json` | `/sapi/v1/margin/next-hourly-interest-rate` | 400 | True | True | `97d258677b0bc4ec53436f7a9da7a26a102b681583fe55a73de5bcc9e88bc783` |
| `sapi-v1-margin-interestRateHistory.json` | `/sapi/v1/margin/interestRateHistory` | 400 | True | True | `97d258677b0bc4ec53436f7a9da7a26a102b681583fe55a73de5bcc9e88bc783` |
| `papi-v1-balance.json` | `/papi/v1/balance` | 401 | True | True | `5f0d48bafb037b8167f92d647d053a2fdf0d5e56fd39ff0b649d328d26720b42` |
| `papi-v1-um-positionRisk.json` | `/papi/v1/um/positionRisk` | 401 | True | True | `5f0d48bafb037b8167f92d647d053a2fdf0d5e56fd39ff0b649d328d26720b42` |
| `api-v3-account.json` | `/api/v3/account` | 401 | True | True | `97d258677b0bc4ec53436f7a9da7a26a102b681583fe55a73de5bcc9e88bc783` |
| `papi-v1-margin-maxBorrowable-BTC.json` | `/papi/v1/margin/maxBorrowable` | 401 | True | True | `5f0d48bafb037b8167f92d647d053a2fdf0d5e56fd39ff0b649d328d26720b42` |
| `papi-v1-margin-maxBorrowable-ETH.json` | `/papi/v1/margin/maxBorrowable` | 401 | True | True | `5f0d48bafb037b8167f92d647d053a2fdf0d5e56fd39ff0b649d328d26720b42` |
| `papi-v1-margin-marginInterestHistory.json` | `/papi/v1/margin/marginInterestHistory` | 401 | True | True | `5f0d48bafb037b8167f92d647d053a2fdf0d5e56fd39ff0b649d328d26720b42` |
| `papi-v1-portfolio-interest-history.json` | `/papi/v1/portfolio/interest-history` | 401 | True | True | `5f0d48bafb037b8167f92d647d053a2fdf0d5e56fd39ff0b649d328d26720b42` |

## Measured rate-limit weight headers (per call; G3 budget-table input)

| logical path | status | weight headers |
|---|---|---|
| `/api/v3/ticker/price` | 200 | X-MBX-USED-WEIGHT=6, X-MBX-USED-WEIGHT-1M=6 |
| `/sapi/v1/margin/allPairs` | 400 | (none captured) |
| `/sapi/v1/margin/allAssets` | 400 | (none captured) |
| `/sapi/v1/margin/crossMarginData` | 400 | (none captured) |
| `/sapi/v1/account/info` | 400 | (none captured) |
| `/sapi/v1/margin/next-hourly-interest-rate` | 400 | (none captured) |
| `/sapi/v1/margin/interestRateHistory` | 400 | (none captured) |
| `/papi/v1/balance` | 401 | X-MBX-USED-WEIGHT-1M=20 |
| `/papi/v1/um/positionRisk` | 401 | X-MBX-USED-WEIGHT-1M=25 |
| `/api/v3/account` | 401 | X-MBX-USED-WEIGHT=26, X-MBX-USED-WEIGHT-1M=26 |
| `/papi/v1/margin/maxBorrowable` | 401 | X-MBX-USED-WEIGHT-1M=30 |
| `/papi/v1/margin/maxBorrowable` | 401 | X-MBX-USED-WEIGHT-1M=35 |
| `/papi/v1/margin/marginInterestHistory` | 401 | X-MBX-USED-WEIGHT-1M=45 |
| `/papi/v1/portfolio/interest-history` | 401 | X-MBX-USED-WEIGHT-1M=95 |

## Redaction policy

- URL query strings stripped from all archived metadata (only logical path kept); key/secret/signature/recvWindow/timestamp never archived.
- Account-level responses (E2/E2b/E5/E3/E4/E6/W4/E1/E1b): numeric-string amount fields -> literal `<AMOUNT>`; account-identifier integer fields {uid, vipLevel} -> `<ID>` (keys, structure and types preserved). Integer error codes on error bodies are not amount strings and survive for diagnosis.
- Market-level public responses (allPairs/allAssets/crossMarginData/ticker-price): public market/config data, no account amounts to redact.

## maxBorrowable sample assets

- `BTC`: fixed by stage prompt.
- `ETH`: highest-abs-last_funding_rate non-BTC MARGIN_SPOT_CANDIDATE+CRYPTO candidate in frontend/fixture/public-market-snapshot.json (offline; fundingInfo not whitelisted this run). ETH: |last_funding_rate|=0.00008142

## Cost-leg four-level chain hit tier (10-design §1.3)

- **hit tier 4** -> `borrow_rate_source = vip0_reference`
- rationale: E2/E2b/E5 unavailable; degrade to VIP0 reference (Phase 2 behavior)
- E2/E2b/E5 failures are NON-blocking (chain degrades per design); only E3/E4/E6 block.

## Gate status (G2)

**BLOCKING endpoint FAILED: `/papi/v1/balance`, `/papi/v1/um/positionRisk`, `/api/v3/account`** -> status = blocked; raw error codes archived in the file(s) above; escalate user; NO silent fallback.

Non-blocking failures recorded (do not block H_intake): `/sapi/v1/margin/allPairs`, `/sapi/v1/margin/allAssets`, `/sapi/v1/margin/crossMarginData`, `/sapi/v1/account/info`, `/sapi/v1/margin/next-hourly-interest-rate`, `/sapi/v1/margin/interestRateHistory`, `/papi/v1/margin/maxBorrowable[BTC]`, `/papi/v1/margin/maxBorrowable[ETH]`, `/papi/v1/margin/marginInterestHistory`, `/papi/v1/portfolio/interest-history`.
