# Discovery evidence index — 2026-07-phase2-borrow-sort-v1

- captured_at_utc: `20260704T133406Z`
- captured_by: bookkeeper/controller (claude_glm session, H_intake)
- base_urls: fapi/papi/sapi per Binance public docs (hardcoded in script)
- total HTTP calls: 6 across 5 endpoints
- endpoint call counts (whitelist proof):
  - `GET /fapi/v1/fundingInfo`: 1
  - `GET /papi/v1/margin/maxBorrowable`: 2
  - `GET /sapi/v1/margin/allAssets`: 1
  - `GET /sapi/v1/margin/allPairs`: 1
  - `GET /sapi/v1/margin/crossMarginData`: 1

## Archived files (sha256 of redacted content)

| file | logical path | status | sha256 | account-level | amounts redacted |
|---|---|---|---|---|---|
| `fapi-v1-fundingInfo.json` | `/fapi/v1/fundingInfo` | 200 | `33f61539987942245c8df0c41f9b9ebf8da2dc9eb7946673f830acceefd53287` | False | False |
| `sapi-v1-margin-allPairs.json` | `/sapi/v1/margin/allPairs` | 200 | `00b7238d816a8df7321c9d7a526d1d29e04b7a1bcc8b61665e979ae3acb00c40` | False | False |
| `sapi-v1-margin-allAssets.json` | `/sapi/v1/margin/allAssets` | 200 | `80e67eb96fa82afb7165021faf5111e82339c33d28bcc9bf064f343a40e46a52` | False | False |
| `sapi-v1-margin-crossMarginData.json` | `/sapi/v1/margin/crossMarginData` | 200 | `2cd9ca7192b0456fe6dcc48da08f0e4e589b03c7558b2f02445bb0eaedfe7109` | False | False |
| `papi-v1-margin-maxBorrowable-BTC.json` | `/papi/v1/margin/maxBorrowable` | 200 | `119eff4de9b75cd3410b10a0e3cbc9b1b72a6cb438eb6f51def1a41a645a0bdb` | True | True |
| `papi-v1-margin-maxBorrowable-ETH.json` | `/papi/v1/margin/maxBorrowable` | 200 | `119eff4de9b75cd3410b10a0e3cbc9b1b72a6cb438eb6f51def1a41a645a0bdb` | True | True |

## Redaction policy

- URL query strings stripped from all archived metadata (only logical path kept); key/secret/signature/recvWindow/timestamp never archived.
- Account-level response (maxBorrowable): numeric-string amount fields replaced with literal `<AMOUNT>` (keys, structure and string type preserved); integer error codes (JSON numbers) are not strings and survive on error bodies for diagnosis.
- Market-level responses (allPairs/allAssets/crossMarginData): public market data, no amount redaction.

## maxBorrowable sample assets

- `BTC`: fixed by stage prompt.
- `ETH: highest-abs-daily-rate non-BTC MARGIN_SPOT_CANDIDATE+CRYPTO candidate in Phase 1 fixture (offline last_funding_rate x live fundingInfo interval). ETH: |0.00008142| x 24/8h = 0.00024426

## fundingInfo interval distribution (live, this run)

- 1h: 2 symbols
- 4h: 440 symbols
- 8h: 269 symbols

## Gate status

All 5 endpoints captured successfully; E5 gate PASSED.
