# Raw Evidence Capture — BTCUSDT 30-day settled funding history

Stage: `2026-07-funding-annualized-history-v1` (Task A)
Captured: 2026-07-10 06:14:19 UTC (stamp `20260710T061419Z`)

## Endpoint and request

Public, no API key, read-only.

```
GET https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&startTime=<now-30d>&endTime=<now>&limit=1000
```

This is the exact deep-history request shape the snapshot service now sends
(`backend/services/snapshot_service.py::_fetch_history_for`):
`symbol`, `startTime = t_end - 30*86_400_000`, `endTime = t_end`, `limit = 1000`.

## File

- `raw/fapi-v1-fundingRate-BTCUSDT-limit1000.json` — verbatim JSON response body.

## Facts

- Entry count: **90** settled funding events (8h cadence).
- Window span: **29.67 days** (multi-week; covers both 7D and 30D windows).
- First: `fundingTime=1781078400011` (≈ 2026-06-10), `fundingRate=-0.00003385`.
- Last:  `fundingTime=1783641600000` (≈ 2026-07-10), `fundingRate=0.00009058`.
- Each item shape (Binance raw):
  `{symbol, fundingTime, fundingRate, markPrice}`.

## Purpose

Grounds the frozen-contract amendment that adds the three optional additive row
properties `annualized_funding_24h`, `annualized_funding_7d`,
`annualized_funding_30d`; current service output always emits all three keys
(acceptance #4, ADR-3). Per AGENTS.md a contract amendment must carry raw
public samples; synthetic vectors under
`backend/tests/fixtures/funding-history/` supplement but do not replace this
evidence. `backend/tests/test_funding_history.py::test_real_btcusdt_sample_processes_through_pipeline`
replays this sample through `build_rows` + schema validation.
