# Handoff: Public Market Contract V2

## Checkpoint: contract discovery re-entered review_2

Status: `review_2`. Review-1 stands at `ACCEPT` (Kimi `kimi-2.7`).
Implementer: Claude-GLM (`glm-5.2[1m]`). The previous Claude/Fable5 review-2
dispatch failed at runner level and is preserved as evidence in
`review-2-claude-dispatch-failure.md` plus
`review-2-claude-dispatch.raw-output.txt`.

Per the 2026-07-03 stage-delivery Harness update, the user approved re-entering
review-2 under the strong-reviewer disclosure override: Codex/GPT may perform
final review despite prior stage design involvement because the unrelated
decision reviewer (Claude/Fable5) is unavailable and Codex did not implement or
fix any reviewed delivery code. The review must treat the user-approved
direction synthesis and PRD as higher authority than `00-task.md`/`10-design.md`.

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

### Kimi review-1 recheck result: `ACCEPT`

Kimi re-ran review-1 against the updated committed subject range
(`2bb47ad..d73eb10`, excluding `status.json`) and returned a schema-valid
`ACCEPT` verdict. Because the controller and implementer share provider
(`claude_glm`), the controller independently re-derived the evidence instead of
trusting the reviewer: recomputed `sha256(git diff --binary 2bb47ad..d73eb10 -- .
":(exclude)<stage>/status.json")` = `de0c199b…`, which matches the
`diff_fingerprint` Kimi recorded; and validated the verdict JSON against
`schemas/review-verdict.schema.json` (0 errors). Identity is compliant: Kimi
(`moonshot_kimi`) differs from both implementer (`claude_glm`/`zhipu_glm`) and
designer (`codex`/`openai`).

The recheck carries one non-blocking **P3**: the ten negative schema tests in
`60-test-output.txt` are not replayable from a committed script (only the
positive-sample generator is committed). `required_fixes` is empty. Two residual
risks are carried forward: `lastFundingRate` settled-vs-estimate ambiguity, and
`MARGIN_SPOT_CANDIDATE` private borrowability (Phase 2). The full verdict JSON is
at the end of `30-review-1.md`.

The review subject stays `d73eb10` for review-2 as well (review-1 and review-2
examine the same fixed product). This acceptance-logging commit advances `HEAD`
past `head_sha`, so review-2 must use the recorded `base_sha..head_sha`, not the
moving `HEAD`.

Next action: `run_review_2_codex_disclosure_override` (final gate).
`status.json.review_2` records `reviewer_prior_involvement=design`,
`fallback_reason`, and
`unrelated_reviewer_unavailable_evidence=reports/agent-runs/2026-07-public-market-contract-v2/review-2-claude-dispatch-failure.md`.
Backend implementation and Kimi frontend remain gated until review-2 accepts.

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

For this stage, `review-2` now uses Codex/GPT as a disclosed strong-reviewer
override. Prior involvement is `design`. The unrelated decision model
Claude/Fable5 is unavailable; evidence is preserved in
`review-2-claude-dispatch-failure.md` and
`review-2-claude-dispatch.raw-output.txt`. Codex/GPT is eligible because it did
not implement or fix any reviewed delivery code.

### Historical Claude/Fable5 review-2 dispatch result: unavailable

Review-2 was dispatched to Claude `claude-fable-5` (`reality_checker`,
read-only/plan) per `docs/model-adapters.md` and registry
`adapters.claude.read_only_review_command` (background task `birc9183w`, exit
code 1). The dispatch failed at the runner level with two independent,
disqualifying causes:

1. `service_unavailable` — the active gateway rejected the model:
   `API Error: 400 [1211][模型不存在，请检查模型代码。]`.
2. `anti_self_review_ineligible` — the local `claude` binary is hijacked by
   `ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic` (Zhipu BigModel),
   so its runtime provider is `zhipu_glm`, identical to the implementer
   (`claude_glm`). Per AGENTS.md, provider identity is the model vendor, not the
   CLI wrapper; using it for review-2 would be a self-review.

The review-2 fallback chain (`registry.yaml` `review_2: {primary: codex,
fallback: claude}`) is exhausted: `codex` is excluded as the stage designer
(`final_review_2_must_differ_from_designer`), and `claude` is unavailable for
the two reasons above. No third final reviewer is registered, and the controller
did not silently substitute another model into review-2. Full evidence, the
runner-level adapter check, and the frozen-subject reproduce command are in
`review-2-claude-dispatch-failure.md`; the raw dispatch output (290 bytes) is in
`review-2-claude-dispatch.raw-output.txt`.

The frozen contract (`2bb47ad..d73eb10`, fingerprint `de0c199b…`) is unchanged.
The historical dispatch failure is no longer terminal because the user approved
the new disclosure override path. The controller still cannot declare final
acceptance; only schema-valid review-2 and pre-accept validation can advance the
stage.

本地北京时间: 2026-07-03 18:43:35 CST
下一步模型: Codex/GPT
下一步任务: Run review-2 under strong-reviewer disclosure override against raw artifacts and the frozen 2bb47ad..d73eb10 diff.
