# Handoff: Public Market Contract V2

## Claude-GLM Backend Contract Prompt

Use this prompt to start the next backend contract task:

```text
You are Claude-GLM acting as backend contract owner for
stage_id=2026-07-public-market-contract-v2.

Goal: verify Binance public endpoint request/response fields and freeze the
Phase 1 backend-to-frontend public market snapshot contract.

Read:
- AGENTS.md
- agents/developer-discipline.md
- docs/product/PRD.md
- docs/api/public-market-contract.md
- schemas/api/public-market/snapshot.schema.json
- llms-full.txt
- reports/agent-runs/2026-07-public-market-contract-v2/00-task.md
- reports/agent-runs/2026-07-public-market-contract-v2/10-design.md

Hard constraints:
- Public data only.
- No API keys.
- No signed endpoints.
- No private account endpoints.
- No order, borrow, repay, transfer, or execution path.
- Do not use Grok for implementation or fixes in this stage.
- Do not create backend implementation modules yet; contract discovery first.
- Before dispatch, record the current git `HEAD` as the review base for this
  stage. Reviewers must recompute `diff_fingerprint` from raw git diff and must
  not rely on Claude-GLM controller summaries as evidence.

Write:
- reports/agent-runs/2026-07-public-market-contract-v2/api-field-matrix.md
- reports/agent-runs/2026-07-public-market-contract-v2/api-sample-index.md
- reports/api-samples/public-market-contract-v2/<timestamp>/raw/*.json
- reports/api-samples/public-market-contract-v2/<timestamp>/normalized/public-market-snapshot.json
- update docs/api/public-market-contract.md if the verified fields differ
- update schemas/api/public-market/snapshot.schema.json if required

Required checks:
- Every frontend-visible field has source endpoint + raw JSON path + observed type.
- Record auth/security status for every endpoint.
- Verify whether GET /sapi/v1/margin/allPairs is public/no-key before using it.
- Also verify GET /sapi/v1/margin/isolated/allPairs and record whether it is
  relevant only as historical FMZ/isolated-margin context or still needed for
  the new Portfolio Margin route model.
- Verify premiumIndex.lastFundingRate semantics; mark ambiguous if not proven.
- Keep asset_tag independent from route_class.
- Produce a normalized sample that validates against the schema.
```

## Kimi Frontend Prompt

Use this only after Claude-GLM freezes the contract:

```text
You are Kimi acting as frontend owner for stage_id=2026-07-public-market-contract-v2.

Goal: build the public market UI against the frozen backend contract.

Read:
- docs/api/public-market-contract.md
- schemas/api/public-market/snapshot.schema.json
- reports/api-samples/public-market-contract-v2/<timestamp>/normalized/public-market-snapshot.json
- docs/product/PRD.md
- prototypes/fake-ui/index.html

Hard constraints:
- Do not call Binance directly.
- Do not invent classification logic.
- If a UI field is missing from the contract, mark it blocked and request a
  contract update.
- Keep the agreed Chinese workstation UI style.

Expected UI:
- 总览持仓 / opportunity overview surface.
- Public market table with funding, route class, bStock tag, and
  negative-funding status.
- Manual-open ticket shell wired to contract fields only.
```

## Review Routing Note

For this stage, `review-2` must use Claude as the final reviewer because Codex
is the stage designer. If Claude is unavailable, stop with
`decision_models_exhausted`; do not fall back to Codex for final review.
