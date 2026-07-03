# Handoff: Public Market Contract V2

## Checkpoint: contract discovery frozen for review_1

Status: `review_1`. Implementer: Claude-GLM (`glm-5.2[1m]`).

Branch: `main`. Review base (`base_sha`):
`2bb47ad13065827ed1ee91d5d0e231cd312fdc0a`. The contract discovery products are
committed locally (not pushed) as the review baseline; HEAD advances past
`base_sha`, so the standard diff is non-empty.

`head_sha` and `diff_fingerprint` are recorded in `status.json` immediately after
the product commit. A commit cannot embed its own sha or fingerprint
(self-referential hash has no fixed point), so this handoff does not duplicate
those literal values. Review uses the standard formula:

```text
diff_fingerprint = head_sha + ":" + sha256(git diff --binary <base_sha>..HEAD)
```

Reproduce the hash with:

```text
git diff --binary 2bb47ad13065827ed1ee91d5d0e231cd312fdc0a..HEAD | shasum -a 256
```

Produced artifacts (review inputs):

- `api-field-matrix.md` — field matrix, endpoint auth matrix, margin/funding/
  bStock conclusions, observed enums.
- `api-sample-index.md` — raw sample inventory and reproducibility commands.
- `20-implementation.md` — implementation report and evidence-integrity note.
- `60-test-output.txt` — raw schema validation, negative tests, generator
  reproducibility, live no-key auth matrix.
- `reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/*.json` —
  real public samples plus the two margin no-key error bodies.
- `reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/` —
  `build-normalized-sample.py` and the schema-valid `public-market-snapshot.json`.
- `docs/api/public-market-contract.md` — verified findings frozen.
- `schemas/api/public-market/snapshot.schema.json` — unchanged; sample validates.

Key conclusions: margin `sapi` endpoints require an API key (not used in Phase 1);
`lastFundingRate` settled-vs-estimate is `ambiguous`; `TRADIFI_PERPETUAL` -> `BSTOCK`;
`asset_tag` independent of `route_class`.

Test status: schema validation PASS (jsonschema Draft202012Validator); 10/10
negative tests reject; generator reproducible.

review-1 (Grok Build, `code_reviewer`, read-only, 900s) inputs must include the
raw artifacts, raw samples, `60-test-output.txt`, `api-field-matrix.md`,
`docs/api/public-market-contract.md`, the schema, and the standard git diff
(`git diff --binary <base_sha>..HEAD`). review-1 reviews raw artifacts and the
standard diff only; it must not trust this controller summary as evidence. If
Grok Build produces no schema-valid verdict or the CLI hangs past 900s, mark
`model_unavailable` and route to `human_escalation_required`.

Open follow-ups (non-blocking): settle-time sample for `lastFundingRate`;
private borrowability validation in Phase 2.

Next action: `route_to_review_1_grok_build`. Backend implementation stays gated
until review passes; Kimi frontend work stays gated until the contract is
accepted.

## Claude-GLM Backend Contract Prompt

Use this prompt to start the next backend contract task:

```text
You are Claude-GLM acting as backend contract owner for
stage_id=2026-07-public-market-contract-v2.

Goal: verify Binance public endpoint request/response fields and freeze the
Phase 1 backend-to-frontend public market snapshot contract.

Actual review base:
2bb47ad13065827ed1ee91d5d0e231cd312fdc0a

All implementation/review diffs for this contract discovery task must use:
git diff --binary 2bb47ad13065827ed1ee91d5d0e231cd312fdc0a..HEAD

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
- Reviewers must recompute `diff_fingerprint` from raw git diff using the
  actual review base above and must not rely on Claude-GLM controller summaries
  as evidence.

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
