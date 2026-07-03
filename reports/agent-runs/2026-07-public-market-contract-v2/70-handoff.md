# Handoff: Public Market Contract V2

## Checkpoint: contract discovery frozen for review_1

Status: `review_1`. Implementer: Claude-GLM (`glm-5.2[1m]`).
Current review-1 reviewer: Kimi (`kimi-2.7`) under the Kimi/Claude-GLM
cross-review policy.

Branch: `main` (local only, not pushed; `ahead of origin/main`). Review baseline:

- `base_sha`: `2bb47ad13065827ed1ee91d5d0e231cd312fdc0a`
- `head_sha`: `d73eb10187f34696aec4aea8f596c0d3578a1dcf` (commit
  `Fix contract evidence fingerprint note`)
- `diff_fingerprint`:
  `d73eb10187f34696aec4aea8f596c0d3578a1dcf:de0c199bd7b9121ec2539c6a891f3167043bc1f4412704c3276fe6171b3fdd46`

The contract discovery products are committed locally as the review baseline;
`head_sha` is the reviewed subject commit. Later Harness commits may advance the
working branch, so review must use the recorded `base_sha..head_sha` range, not
the moving symbolic `HEAD`.

`head_sha` and `diff_fingerprint` are recorded in `status.json` (and above) after
the product commit. A commit cannot embed a hash of a file that contains that
same hash, so the standard fingerprint excludes this stage's `status.json`.
Review uses the standard formula:

```text
diff_fingerprint = head_sha + ":" + sha256(git diff --binary <base_sha>..<head_sha> -- . ":(exclude)reports/agent-runs/<stage-id>/status.json")
```

Reproduce the hash with:

```text
git diff --binary 2bb47ad13065827ed1ee91d5d0e231cd312fdc0a..d73eb10187f34696aec4aea8f596c0d3578a1dcf -- . ":(exclude)reports/agent-runs/2026-07-public-market-contract-v2/status.json" | shasum -a 256
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

review-1 now uses cross-review. Because the implementer is `claude_glm`, the
updated Harness selects Kimi (`kimi-2.7`) with the `code_reviewer` skill in
read-only/plan mode. Inputs include the raw artifacts, raw samples,
`60-test-output.txt`, `api-field-matrix.md`, `docs/api/public-market-contract.md`,
the schema, and the standard git diff (`git diff --binary <base_sha>..<head_sha>
-- . ":(exclude)<stage>/status.json"`). review-1 reviews raw artifacts and the
standard diff only; it must not trust this controller summary as evidence.

### Historical Grok review-1 dispatch result: `model_unavailable`

Dispatched Grok Build review-1 (prompt file
`reports/agent-runs/2026-07-public-market-contract-v2/review-1-grok-timeout.prompt.md`;
command per `docs/model-adapters.md`). The runner-level adapter check passed
first (`grok models` -> `grok-build (default)` + `grok-composer-2.5-fast`;
logged in with grok.com), and `validate-stage.py --phase pre-review` PASSED — so
this is **not** `adapter_missing`. The dispatched `grok` process then hung:
`state=S`, `%CPU=0.0`, **0 bytes captured output** after ~1052s, no working
child process; no schema-valid verdict within the 900s timeout. The controller
stopped the process. This failure is preserved as historical dispatch evidence in
`30-review-1.md`; raw captured output (empty) is in
`review-1-grok-timeout.raw-output.txt`.

After user approval, the Harness default was changed so Grok is no longer a
review gate. The human escalation is resolved by re-routing this stage to Kimi
review-1.

Open follow-ups (non-blocking): settle-time sample for `lastFundingRate`;
private borrowability validation in Phase 2.

### Kimi review-1 result: `REWORK`

Kimi review-1 completed with a schema-valid `REWORK` verdict. It found one P1:
`20-implementation.md` still described the obsolete uncommitted worktree
fingerprint protocol (`HEAD == base`, working-tree hash, untracked files). The
contract artifacts themselves were otherwise judged materially sound.

### Fix result

The P1 was fixed in `20-implementation.md` and mapped in `40-fix-report.md`.
The evidence note now points reviewers to the committed subject range recorded in
`status.json` / this handoff and no longer describes `HEAD == base`, worktree
fingerprints, or untracked-file hashing.

Next action: `route_to_review_1_kimi_recheck`. Ask Kimi to re-run review-1
against the updated fingerprint above. Backend implementation stays gated; Kimi
frontend work stays gated until the contract is accepted.

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
git diff --binary 2bb47ad13065827ed1ee91d5d0e231cd312fdc0a..d73eb10187f34696aec4aea8f596c0d3578a1dcf -- . ":(exclude)reports/agent-runs/2026-07-public-market-contract-v2/status.json"

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
