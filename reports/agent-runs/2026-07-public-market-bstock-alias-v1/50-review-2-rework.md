# Review-2 (rework round 1, stage-level FINAL GATE) — public-market-bstock-alias-v1

This is the **rework round 1 (of 3) review-2**. The prior review-2 RECHECK
returned ACCEPT bound to head `b189440` (`50-review-2-recheck.md`, preserved
verbatim in `status.json.review_2`); a user-directed **external post-review P1
finding** (`spot_leg_quote_asset_hardcode`, reviewer anthropic/`claude-fable-5`,
NO prior involvement) then challenged it. Rework round 1 applied a fix
(`H_fix` = `548ae0d`). Review-1 (rework re-review) by Kimi already ACCEPTed the
fix diff (`30-review-1-fix.md`). This final gate re-ran bound to the new head
and adjudicates whether the fix closes the P1 regression.

- **Stage**: `2026-07-public-market-bstock-alias-v1` (contract amendment + backend/frontend repair + evidence backfill + rework round 1 fix)
- **Reviewer**: `final_reviewer` — Codex/GPT `gpt-5.5`, reasoning effort `xhigh`, sandbox `read-only`
- **Subject**: the whole stage at the new head, with focus on the rework fix delta `b189440..548ae0d`
- **Range**: stage `base_sha..head_sha` = `d240e43..548ae0d` (`H_intake..H_fix`), `status.json` excluded
- **Verdict**: **ACCEPT**
- **Raw dispatch capture**: `review-2-rework-codex.raw-output.txt` (full Codex session transcript)
- **Dispatch brief**: `review-2-rework-codex.prompt.md`

## Routing disclosure (recorded for the gate)

Dispatched with `codex exec -C <repo> -m gpt-5.5 -s read-only` on the
locally-configured default provider (the one available gpt-5.5 route).
`--output-schema` is unusable on this route (same as the prior review-2: the
OpenAI structured-output endpoint rejects `schemas/review-verdict.schema.json`'s
shape), so the verdict was emitted as a fenced ```json block by instruction;
the controller extracts and validates it post-hoc (validation result below).

`reviewer_prior_involvement = direction_synthesis`: Codex/GPT is the prior
direction synthesizer for `2026-07-public-market-contract-v2`
(`approved_prior_stage`; no new direction panel this stage), with NO
design/breakdown/code/fix involvement this stage. The fix (`H_fix`) was authored
by `claude_glm` (controller/Task A owner). Fable5/Anthropic **was reached** for
the user-directed external post-review finding (in an Anthropic-authenticated
environment, 2026-07-04), so it is reachable in principle; however, from this
controller dispatch runner the local `claude` CLI auth is re-routed to
`zhipu_glm`, so an Anthropic endpoint was not probed here — per the Fable5 probe
hygiene rule that is recorded as "Anthropic endpoint not probed (auth re-routed
to GLM/Zhipu)", NOT as Fable5 unavailable. Both implementers (`claude_glm`,
`kimi`) are hard-banned from review-2. Per AGENTS.md review-2 uses GPT/Codex
first; with no provider-unrelated decision model reachable from this runner,
Codex reviews via the **strong-reviewer disclosure override**. The hard ban is
satisfied (Codex authored no delivery code and no fixes).

## Codex narrative (verbatim, final assistant turn)

> Verdict: ACCEPT.
>
> I recomputed the stage fingerprint for `d240e43..548ae0d`; it matches
> `548ae0d382c0010c9ab1d0dc26f11ca7a0f47de9:97ac2539a3c044e56499a9731115be3d16fb024ffed6ac0620f7e4e60ce33a5f`.
>
> The rework closes the P1: `snapshot.py` now passes the real `quoteAsset`, the
> service filters Phase 1 to USDT-quoted rows, `normalize.py` and `classify.py`
> are unchanged, and the live-raw replay gives 648 all-USDT rows, zero
> exact-symbol mismatches, and 15/15 bStock alias matches. Full backend tests
> passed with read-only-safe pytest flags (`54 passed`), `grep "float("
> backend/domain backend/services` is clean, and frontend self-check remains
> 11/11.
>
> One bookkeeping note: rerunning `validate-stage.py --phase pre-review` fails
> only because this active review's prompt/raw-output files are currently
> untracked. That matches the controller capture pattern and is not a product or
> bound-diff defect; the controller should commit/reconcile those files when
> recording this verdict.

Codex independently recomputed, from raw `git diff`:

- **Stage `diff_fingerprint`** = `548ae0d…47de9:97ac2539…3a5f` → matches
  `status.json.diff_fingerprint`.
- The rework fix delta `b189440..548ae0d` touches `backend/domain/snapshot.py`
  (call site), `backend/services/snapshot_service.py` (universe filter +
  docstring), `backend/tests/**` (+USDC fixture, +2 tests), and stage evidence;
  `normalize.py` and `classify.py` are **unchanged** over the range; `schemas`,
  `docs/api`, `frontend`, `reports/api-samples` are untouched.
- The fix genuinely closes the P1: feeding the USDC-quoted `BTCUSDC` row directly
  resolves `spot.symbol=="BTCUSDC"` / `match_type=="exact_symbol"` (not
  `BTCUSDT`); the service universe filter excludes non-USDT rows; the live-raw
  replay yields 648 all-USDT rows with zero exact-symbol mismatches and 15/15
  bStock alias.
- Re-ran `.venv/bin/python -m pytest backend/tests -q` (read-only-safe flags) →
  54 passed; `node frontend/self-check.js` → 11/11 PASS; `grep "float("
  backend/domain backend/services` → clean.

## Controller verification (post-hoc, independent of Codex's narrative)

- **Schema validity**: the extracted verdict JSON validated by the controller
  against `schemas/review-verdict.schema.json` (Draft 2020-12) → **valid**.
- **Fingerprint match**: `verdict.diff_fingerprint == status.json.diff_fingerprint`
  → **true** (`548ae0d…47de9:97ac2539…3a5f`).
- **Forbidden-paths isolation** (the core gate claim):
  `git diff --stat b189440..548ae0d -- backend/domain/normalize.py
  backend/domain/classify.py schemas docs frontend reports/api-samples` →
  empty. `resolve_spot_leg` and the `classify.py` priority sequence are
  byte-identical over the fix range; the frozen schema/contract, frontend, and
  api-samples evidence are untouched.
- **review-1 (rework) consistency**: Kimi's review-1 ACCEPT on the same fix diff
  (`30-review-1-fix.md`, same fingerprint) is independent agreement.

## Residual risks (carry forward, non-blocking; recorded by Codex)

- Non-USDT-quoted perpetuals are intentionally excluded from Phase 1 by the
  2026-07-04 user decision; future multi-quote support requires a later
  contract/stage.
- bStock token vs US-equity 1:1 equivalence remains unproven by public
  exchangeInfo; correctly deferred to later position-opening planning
  (`status.json.open_items`).
- bStock spot/margin session behavior vs TRADIFI perpetual 7x24 trading remains
  deferred to pre-trade planning (`status.json.open_items`).
- Current-session bookkeeping: the active review-2 prompt/raw-output files were
  untracked at review time, so a live `--phase pre-review` rerun failed only on
  those untracked artifacts. The controller commits them when recording this
  verdict (this commit), after which the gate is clean.

## Verdict (canonical JSON, schema-validated)

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-public-market-bstock-alias-v1",
  "role": "final_reviewer",
  "model": "gpt-5.5",
  "verdict": "ACCEPT",
  "diff_fingerprint": "548ae0d382c0010c9ab1d0dc26f11ca7a0f47de9:97ac2539a3c044e56499a9731115be3d16fb024ffed6ac0620f7e4e60ce33a5f",
  "reviewer_prior_involvement": "direction_synthesis",
  "reviewer_prior_involvement_notes": "Codex/GPT was the prior direction synthesizer for approved_prior_stage 2026-07-public-market-contract-v2, which covers this stage; no new direction panel ran for this stage. Codex/GPT had no design, breakdown, implementation, delivery-code, or fix involvement in this stage. Fable5/Anthropic was reached for the user-directed external post-review finding, but from this controller runner the local claude CLI auth is re-routed to GLM/Zhipu, so an Anthropic endpoint was not probed and this is not recorded as true Fable5 unavailability. Both implementation/fix providers, claude_glm and kimi, are hard-banned from review-2. This review uses the strong-reviewer disclosure override; the implementer/fix-author hard ban is satisfied.",
  "reviewed_artifacts": [
    "AGENTS.md",
    "reports/agent-runs/2026-07-initial-direction/06-direction-synthesis.md",
    "docs/product/PRD.md",
    "docs/api/public-market-contract.md",
    "schemas/api/public-market/snapshot.schema.json",
    "schemas/review-verdict.schema.json",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/00-task.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/10-design.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/11-adr.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/post-review-quote-asset-hardcode-finding.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/fix-start-prompt-spot-leg-quote-asset.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/40-fix-report.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/30-review-1-fix.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/50-review-2-recheck.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/60-test-output.txt",
    "backend/domain/snapshot.py",
    "backend/services/snapshot_service.py",
    "backend/domain/normalize.py",
    "backend/domain/classify.py",
    "backend/tests/test_snapshot.py",
    "backend/tests/fixtures/bstock-alias-raw/fapi-v1-exchangeInfo.json",
    "backend/tests/fixtures/bstock-alias-raw/api-v3-exchangeInfo.json",
    "frontend/index.html",
    "frontend/self-check.js",
    "git diff --binary d240e43..548ae0d -- . :(exclude)reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json",
    "git diff b189440..548ae0d -- backend/domain/normalize.py backend/domain/classify.py schemas docs frontend reports/api-samples",
    "PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -s -p no:cacheprovider backend/tests -q",
    "node frontend/self-check.js"
  ],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [
    "Non-USDT-quoted perpetuals are intentionally excluded from Phase 1 by the 2026-07-04 user decision; future multi-quote support requires a later contract/stage.",
    "bStock token versus underlying US-equity 1:1 equivalence remains unproven by public exchangeInfo and is deferred to later position-opening planning.",
    "bStock spot/margin session behavior versus TRADIFI perpetual 7x24 trading remains deferred to pre-trade planning.",
    "The active checkout has untracked current review-2 prompt/raw-output files, so a live validator rerun fails only on those review-capture artifacts; the controller should commit or reconcile them when recording this verdict."
  ],
  "next_action": "stage_accepted_waiting_user"
}
```

## Stage gate outcome

Review-2 (rework round 1, final gate) = **ACCEPT**, schema-valid, fingerprint
binding to `548ae0d` verified, P1 regression `spot_leg_quote_asset_hardcode`
confirmed closed. The controller records this verdict, rebinds `review_2` to the
new head/fingerprint, sets `status=stage_accepted_waiting_user`, marks
`post_review_findings[spot_leg_quote_asset_hardcode].status=resolved_by_rework_review_2`,
and runs `scripts/validate-stage.py --phase pre-accept`. The controller does
**not** declare final acceptance (`can_accept_final=false`); the stage awaits
the user.

本地北京时间: 2026-07-04 11:27 CST
下一步模型: Claude-GLM controller
下一步任务: Record this review-2 ACCEPT, commit review capture + status.json bookkeeping, run pre-accept validation (must PASS), mark the finding resolved, then hold for the user.
