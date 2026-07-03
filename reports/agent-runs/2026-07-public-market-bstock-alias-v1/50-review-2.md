# Review-2 (stage-level, FINAL GATE) — public-market-bstock-alias-v1

- **Stage**: `2026-07-public-market-bstock-alias-v1` (contract amendment + backend/frontend repair)
- **Reviewer**: `final_reviewer` — Codex/GPT `gpt5.5`, reasoning effort `xhigh`, sandbox `read-only`
- **Subject**: the whole stage implementation (Task A contract amendment + backend + tests; Task B frontend; Task C integration)
- **Range**: stage `base_sha..head_sha` = `d240e43..0842820` (`H_intake..H_C`), `status.json` excluded
- **Verdict**: **ACCEPT**
- **Raw dispatch capture**: `review-2-codex.raw-output.txt` (full Codex session transcript, 7481 lines)
- **Dispatch brief**: `review-2-codex.prompt.md`

## Routing disclosure (recorded for the gate)

Codex review-2 was dispatched with the locally configured GPT/Codex default
(`gpt5.5`, `xhigh`) per `docs/model-adapters.md`, using the user-specified
invocation form `codex exec --model gpt-5.5` on the locally-configured default
provider (`openai`). Provider availability probes immediately before dispatch:

- `codex exec --model gpt-5.5` (default route) → **available** (this is the route used).
- proxy2233 → 402 Payment Required ("没有有效的订单，请购买token套餐").
- proxy6651 → 403 SUBSCRIPTION_NOT_FOUND ("No active subscription found for this group").

`--output-schema` is unusable on this route: the OpenAI structured-output
endpoint rejects `schemas/review-verdict.schema.json`'s shape
(`invalid_json_schema: ... 'required' is required to be supplied and to be an
array including every key in properties. Missing 'file'.`). The reviewer was
therefore instructed in the prompt to emit a fenced ```json verdict block by
instruction; the controller extracts and validates it post-hoc against
`schemas/review-verdict.schema.json` (validation result below).

`reviewer_prior_involvement = direction_synthesis`: Codex/GPT is the prior
direction synthesizer for the covering contract stage
(`approved_prior_stage`, no new direction panel this stage), with NO
design/breakdown/code/fix involvement this stage. Fable5/Anthropic was
unreachable (`claude` CLI auth → `zhipu_glm`; `--model claude-fable-5` → error
1211). Both implementers (`claude_glm`, `kimi`) hard-banned. With no
provider-unrelated decision model available, Codex reviews via the
strong-reviewer disclosure override (AGENTS.md "GPT/Codex first"). The
implementer/fix-author hard ban is satisfied (Codex wrote no delivery code).

## Codex narrative (verbatim, final assistant turn)

> Verdict: ACCEPT.
>
> I recomputed the stage fingerprint and Task A/B fingerprints; all match the
> recorded values. Boundaries are clean: Task A stayed in amendable
> contract/backend/test files, Task B stayed in frontend/report files, Task C
> added only stage evidence, and frozen historical samples were untouched.
>
> The alias behavior, schema/doc amendment, unchanged classifier priority,
> frontend display guard, decimal discipline, and offline synthetic integration
> evidence all check out. `node frontend/self-check.js` passed 11/11. The exact
> pytest command could not start because this read-only sandbox has no usable
> temp directory for pytest capture, but the same backend suite with
> capture/cache disabled passed: `52 passed`.
>
> One process note: `scripts/validate-stage.py ... --phase pre-review` currently
> fails because the active review-2 prompt/raw-output files are untracked. That
> is current review capture bookkeeping outside the reviewed implementation
> range; the controller should commit review-2 evidence before pre-accept
> validation.

Codex independently recomputed, from raw `git diff`:

- **Stage `diff_fingerprint`** = `0842820…9002:24ce862a…b9ac` → matches `status.json.diff_fingerprint`.
- **Task A** (`d240e43..1f94c84`) = `fe6d0bd9…c815` → matches `status.json.tasks.A.diff_fingerprint`.
- **Task B** (`6ea4504..5968c49`) = `8c5d685e…c7d0` → matches `status.json.tasks.B.diff_fingerprint`.
- Boundaries clean; `classify.py` diff empty; classifier priority intact; alias
  semantic closure (TSLA → `MARGIN_SPOT_CANDIDATE` + `DISABLED_BSTOCK`,
  positive rate candidate / negative rate disabled) verified without any
  classifier change; collateral ratio not hard-coded; `margin_public.source`
  still `unverified`; schema `match_type` nullable + not in `required`; frontend
  alias guard fires only for `bstock_b_suffix_alias`; decimal discipline clean.

> 本地北京时间: 2026-07-04 00:29:01 CST
> 下一步模型: Claude-GLM controller
> 下一步任务: Commit review-2 evidence, run pre-accept validation, then update accepted-stage bookkeeping.

## Controller verification (post-hoc, independent of Codex's narrative)

- **Schema validity**: the extracted verdict JSON was validated by the controller
  against `schemas/review-verdict.schema.json` via `jsonschema` → **valid**.
- **Fingerprint match**: `verdict.diff_fingerprint == status.json.diff_fingerprint`
  → **true** (`0842820…9002:24ce862a…b9ac`).
- **Independent test rerun (controller, normal capture)**:
  `.venv/bin/python -m pytest backend/tests -q` → **52 passed**;
  `node frontend/self-check.js` → **11/11 PASS**;
  `grep -RnE '\bfloat\(' backend --include='*.py'` → clean;
  `git diff d240e43..0842820 -- backend/domain/classify.py` → empty.
  (Codex's pytest-capture note is a read-only-sandbox artifact only; the suite
  passes under normal capture.)
- **Pre-review gate note**: `validate --phase pre-review` will fail until the
  review-2 evidence files are committed (untracked artifacts, outside the
  reviewed `d240e43..0842820` range). The controller commits them before
  `--phase pre-accept`.

## Residual risks (carry forward, non-blocking; recorded by Codex)

- The bStock alias rule is verified only against synthetic offline fixtures; no
  live Binance bStock spot/margin payload was captured this stage.
- The alias logic assumes quote asset `USDT` (`build_rows` passes `"USDT"` to
  `resolve_spot_leg`); non-USDT bStocks would require revisiting the alias
  construction.
- The frontend fixture covers 6 rows (one `bstock_b_suffix_alias` row); the live
  endpoint serves 688 rows. Rendering is row-count-agnostic.
- The live HTTP path is unchanged and not exercised this stage.
- The impl-v1 `post_review_findings` backfill is intentionally deferred until
  this review-2 ACCEPT and pre-accept validation pass.

## Verdict (canonical JSON, schema-validated)

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-public-market-bstock-alias-v1",
  "role": "final_reviewer",
  "model": "gpt5.5",
  "verdict": "ACCEPT",
  "diff_fingerprint": "0842820ff21d30f563d25a3ff914cd705e6d9002:24ce862a277987871fadbeb7e46ee3e59db923904ff28468ac84482ac48fb9ac",
  "reviewer_prior_involvement": "direction_synthesis",
  "reviewer_prior_involvement_notes": "Codex/GPT had prior direction-synthesis involvement for the approved prior covering contract stage; that approved_prior_stage synthesis covers this amendment stage and no new direction panel ran here. Codex/GPT had no stage-design, development-breakdown, implementation, or fix-authorship involvement in this stage. Fable5/Anthropic was unreachable and has no involvement this stage. The strong-reviewer disclosure override is invoked; review-2 hard ban is satisfied because Codex/GPT wrote no delivery code and no fixes in this stage.",
  "reviewed_artifacts": [
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/00-task.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/10-design.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/11-adr.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/fable5-detail-breakdown.unavailable.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/20-implementation.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/20-implementation-backend.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/20-implementation-frontend.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/30-review-1.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/30-review-1-backend.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/30-review-1-frontend.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/task-c-integration-check.py",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/integration-snapshot-bstock-alias.json",
    "backend/domain/normalize.py",
    "backend/domain/snapshot.py",
    "backend/domain/classify.py",
    "backend/tests/test_classify.py",
    "backend/tests/test_normalize.py",
    "backend/tests/test_snapshot.py",
    "backend/tests/test_negative_schema.py",
    "backend/tests/conftest.py",
    "backend/tests/fixtures/bstock-alias-raw/*.json",
    "frontend/index.html",
    "frontend/self-check.js",
    "frontend/fixture/public-market-snapshot.json",
    "schemas/api/public-market/snapshot.schema.json",
    "docs/api/public-market-contract.md",
    "git diff --binary d240e43e75034a6718ede79bc295d39e77cd860e..0842820ff21d30f563d25a3ff914cd705e6d9002 -- . ':(exclude)reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json'"
  ],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [
    "The bStock alias rule is verified only against synthetic offline fixtures; no live Binance bStock spot/margin payload was captured in this stage.",
    "The alias logic currently assumes quote asset USDT because build_rows passes USDT to resolve_spot_leg; non-USDT bStocks would require revisiting the alias construction.",
    "The frontend fixture covers 6 rows with one bstock_b_suffix_alias row, while the live endpoint serves 688 rows; rendering is row-count-agnostic.",
    "The live HTTP path is unchanged and was not exercised in this stage.",
    "The impl-v1 post_review_findings backfill is intentionally deferred until this review-2 ACCEPT and pre-accept validation pass."
  ],
  "next_action": "continue"
}
```

## Stage gate outcome

Review-2 (final gate) = **ACCEPT**, schema-valid, fingerprint binding verified.
On commit of this evidence + `status.json` update, the controller runs
`scripts/validate-stage.py … --phase pre-accept`, then holds the stage at
`stage_accepted_waiting_user` (the controller does **not** declare final
acceptance; `can_accept_final = false`). After pre-accept passes, the controller
backfills the impl-v1 finding closure (`bstocks_b_suffix_spot_margin_alias` →
`resolved_by_stage`, referencing this stage id + head), which is excluded from
impl-v1's hash and does not alter its review verdicts.
