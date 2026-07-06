# Discovery evidence index — 2026-07-private-account-v1

- captured_at_utc: `20260705T232800Z`
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
| `api-v3-ticker-price.json` | `/api/v3/ticker/price` | 200 | False | False | `72bee62112c743de881d906e33aae80d706dbe4088b159180dc30f7750ae2786` |
| `sapi-v1-margin-allPairs.json` | `/sapi/v1/margin/allPairs` | 200 | False | False | `00b7238d816a8df7321c9d7a526d1d29e04b7a1bcc8b61665e979ae3acb00c40` |
| `sapi-v1-margin-allAssets.json` | `/sapi/v1/margin/allAssets` | 200 | False | False | `80e67eb96fa82afb7165021faf5111e82339c33d28bcc9bf064f343a40e46a52` |
| `sapi-v1-margin-crossMarginData.json` | `/sapi/v1/margin/crossMarginData` | 200 | False | False | `6e705099d984988ddcb9210b6c509e8b23f45fec99fa42b62b1cfd0c08b6e027` |
| `sapi-v1-account-info.json` | `/sapi/v1/account/info` | 200 | True | True | `70bc7f81776e8d24d9f11d9a0fbbe5c0d80ac2a192369e7534a682db9682f933` |
| `sapi-v1-margin-next-hourly-interest-rate.json` | `/sapi/v1/margin/next-hourly-interest-rate` | 200 | True | True | `40b7cdd6928e82204d16d24c29e22d4b2a45e6c76e166ab79c53be114ec59fbb` |
| `sapi-v1-margin-interestRateHistory.json` | `/sapi/v1/margin/interestRateHistory` | 200 | True | True | `e5ee7e334116ea76bfe3b7e713dd2ff7f16435386ed118057330cbd59915bad2` |
| `papi-v1-balance.json` | `/papi/v1/balance` | 200 | True | True | `0da74240b2da516bedbd23e77bdf0224e823d6319acd1c128679f6eb43422f79` |
| `papi-v1-um-positionRisk.json` | `/papi/v1/um/positionRisk` | 200 | True | True | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| `api-v3-account.json` | `/api/v3/account` | 200 | True | True | `68c905f56495c3c68f423e17895dac94eb965553c163dc400053f456454fab0a` |
| `papi-v1-margin-maxBorrowable-BTC.json` | `/papi/v1/margin/maxBorrowable` | 200 | True | True | `119eff4de9b75cd3410b10a0e3cbc9b1b72a6cb438eb6f51def1a41a645a0bdb` |
| `papi-v1-margin-maxBorrowable-ETH.json` | `/papi/v1/margin/maxBorrowable` | 200 | True | True | `119eff4de9b75cd3410b10a0e3cbc9b1b72a6cb438eb6f51def1a41a645a0bdb` |
| `papi-v1-margin-marginInterestHistory.json` | `/papi/v1/margin/marginInterestHistory` | 200 | True | True | `517b863a2d82e71bc400730dd9f76569a3f9137193ace4d47677b0c986bb5392` |
| `papi-v1-portfolio-interest-history.json` | `/papi/v1/portfolio/interest-history` | 200 | True | True | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

## Measured rate-limit weight headers (per call; G3 budget-table input)

| logical path | status | weight headers |
|---|---|---|
| `/api/v3/ticker/price` | 200 | X-MBX-USED-WEIGHT=4, X-MBX-USED-WEIGHT-1M=4 |
| `/sapi/v1/margin/allPairs` | 200 | X-SAPI-USED-IP-WEIGHT-1M=1 |
| `/sapi/v1/margin/allAssets` | 200 | X-SAPI-USED-IP-WEIGHT-1M=1 |
| `/sapi/v1/margin/crossMarginData` | 200 | X-SAPI-USED-IP-WEIGHT-1M=50 |
| `/sapi/v1/account/info` | 200 | X-SAPI-USED-IP-WEIGHT-1M=1 |
| `/sapi/v1/margin/next-hourly-interest-rate` | 200 | X-SAPI-USED-IP-WEIGHT-1M=100 |
| `/sapi/v1/margin/interestRateHistory` | 200 | X-SAPI-USED-UID-WEIGHT-1M=60 |
| `/papi/v1/balance` | 200 | X-MBX-USED-WEIGHT-1M=20 |
| `/papi/v1/um/positionRisk` | 200 | X-MBX-USED-WEIGHT-1M=25 |
| `/api/v3/account` | 200 | X-MBX-USED-WEIGHT=24, X-MBX-USED-WEIGHT-1M=24 |
| `/papi/v1/margin/maxBorrowable` | 200 | X-MBX-USED-WEIGHT-1M=30 |
| `/papi/v1/margin/maxBorrowable` | 200 | X-MBX-USED-WEIGHT-1M=35 |
| `/papi/v1/margin/marginInterestHistory` | 200 | X-MBX-USED-WEIGHT-1M=45 |
| `/papi/v1/portfolio/interest-history` | 200 | X-MBX-USED-WEIGHT-1M=95 |

## Redaction policy

- URL query strings stripped from all archived metadata (only logical path kept); key/secret/signature/recvWindow/timestamp never archived.
- Account-level responses (E2/E2b/E5/E3/E4/E6/W4/E1/E1b): numeric-string amount fields -> literal `<AMOUNT>`; account-identifier integer fields {uid, vipLevel} -> `<ID>` (keys, structure and types preserved). Integer error codes on error bodies are not amount strings and survive for diagnosis.
- Market-level public responses (allPairs/allAssets/crossMarginData/ticker-price): public market/config data, no account amounts to redact.

## maxBorrowable sample assets

- `BTC`: fixed by stage prompt.
- `ETH`: highest-abs-last_funding_rate non-BTC MARGIN_SPOT_CANDIDATE+CRYPTO candidate in frontend/fixture/public-market-snapshot.json (offline; fundingInfo not whitelisted this run). ETH: |last_funding_rate|=0.00008142

## Cost-leg four-level chain hit tier (10-design §1.3)

- **hit tier 1** -> `borrow_rate_source = next_hourly`
- rationale: E2 /sapi/v1/margin/next-hourly-interest-rate returned usable rate(s)
- E2/E2b/E5 failures are NON-blocking (chain degrades per design); only E3/E4/E6 block.

## Gate status (G2)

All blocking endpoints (E3/E4/E6) captured successfully; G2 blocking gate PASSED.
