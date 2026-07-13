# Raw Evidence Capture — public per-symbol click-refresh contract

Stage: `2026-07-history-background-refresh-v1`
Captured: 2026-07-13 (stamp `20260713T000000Z`)

## Scope

This capture grounds the contract amendment for the selected-symbol row-snapshot
(`public-market-symbol-snapshot/v1`) and the worker's per-symbol public refresh
path (`backend/adapters/binance_public.py::fetch_premium_index_for` +
`fetch_funding_rate`). Both requests are **public, no API key, read-only**.

Per `AGENTS.md` hard gate, a contract amendment must carry raw public samples
that ground the change; synthetic test fixtures under `backend/tests/` supplement
but never replace this evidence.

## Files

- `raw/fapi-v1-premiumIndex-BTCUSDT.json` — verbatim `GET /fapi/v1/premiumIndex?symbol=BTCUSDT`.
  Grounds the new per-symbol public adapter that refreshes only the selected
  row's premium/mark fields WITHOUT calling full-universe `fetch_raw()`
  (`10-design.md` D3, `12-development-breakdown.md` §6).
- `raw/fapi-v1-fundingRate-BTCUSDT-limit1000.json` — verbatim
  `GET /fapi/v1/fundingRate?symbol=BTCUSDT&startTime=<t_end-30d>&endTime=<t_end>&limit=1000`,
  the exact 30-day settled-history request shape reused by the worker's
  selected-symbol and scheduled-default refresh (`§6`, `§4.4`).

## Facts (BTCUSDT, captured live)

- `premiumIndex.time` = `1783875671000`; `lastFundingRate` = `0.00007013`.
- `fundingRate` entry count = **90** (8h cadence, ~30d window).
- Window: first `fundingTime=1781308800000`, last `fundingTime=1783872000000`.
- Item shape (Binance raw): `{symbol, fundingTime, fundingRate, markPrice}`.

## Pending live signed evidence (NOT captured here)

The force-TTL exact-key private behavior
(`fetch_max_borrowable(asset, force=True)` +
`fetch_cost_leg_chain([asset], force=True)`, evicting only the three single-asset
keys `maxBorrowable` / `next-hourly-interest-rate{assets=<asset>}` /
`interestRateHistory{asset=<asset>}`) touches **signed** endpoints. Per stage
rules, signed live calls require an explicit operator-authorized safe
environment; none was authorized for this implementation pass, so no live signed
capture is included.

A sanitized audit-log schema template (field names only; never key/secret/
signature/query/headers/balances/positions) is documented in
`signed-audit-template.json` to anchor the contract shape; it is explicitly
labeled a template, not fact evidence. Live signed evidence is flagged as a
follow-up for the bookkeeper/operator to capture under authorization.
