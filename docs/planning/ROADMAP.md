# Roadmap

Status: draft

This file is the canonical approved roadmap.

## Milestones

1. Public market API contract discovery.
2. Public market backend snapshot API.
3. Frontend market table and manual-open planning UI against the frozen backend
   contract.
4. Private account discovery and read-only account validation.
5. Manual execution flow.
6. Accounting, reconciliation, and alerting.

## Current Stage

`2026-07-public-market-contract-v2`

Goal: verify Binance public endpoint request/response fields, freeze the
backend-to-frontend JSON contract, then let Kimi build the frontend against that
contract before backend implementation resumes.

## Later

- Websocket depth display after operator clicks open.
- Private Portfolio Margin borrow/trade validation.
- Manual market-order execution.
- Position mismatch monitoring.
- Funding, commission, rebate, and borrow-interest accounting.
