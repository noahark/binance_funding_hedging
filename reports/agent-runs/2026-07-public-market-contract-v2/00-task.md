# Task: Binance Public Market API Contract

## Objective

Produce a verified public-market API contract for Phase 1.

Claude-GLM must inspect local Binance docs and public samples, then write a
field matrix and normalized JSON contract for:

- Futures symbol metadata.
- Funding-rate display fields.
- Funding history.
- Spot leg availability.
- Public margin-pair candidate signal if verified as public/no-key.
- bStock / tokenized equity tagging.
- Route class and negative-funding status.

## Scope

Allowed files for the contract discovery task:

- `docs/api/public-market-contract.md`
- `schemas/api/public-market/*.schema.json`
- `reports/agent-runs/2026-07-public-market-contract-v2/*`
- `reports/api-samples/public-market-contract-v2/**`

Backend implementation files are not allowed until the contract is reviewed.

## Hard Boundaries

- No API keys.
- No signed endpoints.
- No private account endpoints.
- No order, borrow, repay, transfer, or execution path.
- No frontend Binance calls.
- No Grok development for this stage.

## Acceptance Criteria

- Every frontend-visible field has a source endpoint and raw JSON path.
- Auth requirements are explicitly recorded for every Binance endpoint.
- `premiumIndex.lastFundingRate` semantics are documented with evidence.
- bStock detection rules are documented separately from route class rules.
- JSON schema validates a representative normalized sample.
- Kimi can build the frontend using only the frozen contract and sample JSON.
