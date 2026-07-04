# Review-1 (rework round 1, Task A fix) — public-market-bstock-alias-v1

Stage: `2026-07-public-market-bstock-alias-v1`
Reviewer: `kimi-2.7` (`first_reviewer`, `code_reviewer`)
Subject: rework round 1 fix for finding `spot_leg_quote_asset_hardcode` (Task A)
Range: `b1894406cf50173fc110f92b63fc3fe2f7ad7fc1..548ae0d382c0010c9ab1d0dc26f11ca7a0f47de9`

## Fingerprint recomputation

```bash
git diff --binary d240e43e75034a6718ede79bc295d39e77cd860e..548ae0d382c0010c9ab1d0dc26f11ca7a0f47de9 -- . ':(exclude)reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json' | shasum -a 256
```

Result: `97ac2539a3c044e56499a9731115be3d16fb024ffed6ac0620f7e4e60ce33a5f`

Task-A/stage `diff_fingerprint`: `548ae0d382c0010c9ab1d0dc26f11ca7a0f47de9:97ac2539a3c044e56499a9731115be3d16fb024ffed6ac0620f7e4e60ce33a5f`

This **matches** the value recorded in `status.json.diff_fingerprint` and `status.json.tasks.A.diff_fingerprint` (`fingerprint_matches_status=true`).

## Fix delta boundary check

```bash
git diff --name-only b1894406cf50173fc110f92b63fc3fe2f7ad7fc1..548ae0d382c0010c9ab1d0dc26f11ca7a0f47de9
```

Returns 13 paths, grouped as follows:

**Product code / fixtures / tests (expected fix delta):**

- `backend/domain/snapshot.py`
- `backend/services/snapshot_service.py`
- `backend/tests/test_snapshot.py`
- `backend/tests/fixtures/bstock-alias-raw/api-v3-exchangeInfo.json`
- `backend/tests/fixtures/bstock-alias-raw/fapi-v1-exchangeInfo.json`

**Stage evidence / bookkeeping (expected):**

- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/40-fix-report.md`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/60-test-output.txt`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json`

**Additional Harness bookkeeping files committed in the same fix commit (not product code):**

- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/50-review-2-recheck.md`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/70-handoff.md`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/fix-start-prompt-spot-leg-quote-asset.md`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/post-review-quote-asset-hardcode-finding.md`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/review-2-recheck-codex.prompt.md`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/review-2-recheck-codex.raw-output.txt`

These extra report artifacts are all under `reports/agent-runs/<stage-id>/` and consist of previously untracked review-2 recheck capture plus the handoff update; none touch product code or forbidden paths. The fix-scope product boundaries are clean.

**Forbidden-path verification (all empty diff):**

```bash
git diff b189440..548ae0d -- backend/domain/normalize.py backend/domain/classify.py schemas docs frontend reports/api-samples
```

Output empty. `backend/domain/normalize.py` (`resolve_spot_leg`) and `backend/domain/classify.py` are unchanged, as are `schemas/**`, `docs/**`, `frontend/**`, and `reports/api-samples/**`.

## Artifacts inspected

- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/post-review-quote-asset-hardcode-finding.md`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/fix-start-prompt-spot-leg-quote-asset.md`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/40-fix-report.md`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/60-test-output.txt`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/70-handoff.md`
- `backend/domain/snapshot.py` (commit `548ae0d`)
- `backend/services/snapshot_service.py` (commit `548ae0d`)
- `backend/domain/normalize.py` (commit `548ae0d`)
- `backend/domain/classify.py` (commit `548ae0d`)
- `backend/tests/test_snapshot.py` (commit `548ae0d`)
- `backend/tests/fixtures/bstock-alias-raw/fapi-v1-exchangeInfo.json`
- `backend/tests/fixtures/bstock-alias-raw/api-v3-exchangeInfo.json`
- `schemas/api/public-market/snapshot.schema.json`
- `docs/api/public-market-contract.md`
- the raw fix diff (`git diff --binary b189440..548ae0d`)

## Fix review findings

### 1. `backend/domain/snapshot.py:70` call site

The hard-coded `"USDT"` is replaced by `obj.get("quoteAsset", "")`:

```python
spot, match_type = resolve_spot_leg(
    contract_type, obj.get("baseAsset", ""), obj.get("quoteAsset", ""), spot_by_sym
)
```

- The exact-symbol branch now resolves `base+quote` → `exact_symbol` using the row's real quote asset.
- The `TRADIFI_PERPETUAL` branch still uses `base+"B"+quote` → `bstock_b_suffix_alias`, unchanged.
- `snapshot.py:99` `"quote_asset": "USDT"` output is unchanged; this is correct because the upstream universe filter now guarantees every retained row is USDT-quoted.
- `resolve_spot_leg`, `classify_route`, and `negative_funding_status` are untouched.

### 2. `backend/services/snapshot_service.py` universe filter

Added one clause:

```python
and s.get("quoteAsset") == "USDT"
```

- `ELIGIBLE_CONTRACT_TYPES` is defined once in the service and imported by the live-raw replay script; not duplicated.
- The module docstring is updated faithfully to "TRADING USDT-quoted perpetuals/TRADIFI".
- This implements the 2026-07-04 user decision (Phase 1 = USDT-quoted only) and honors the existing frozen schema `row.quote_asset = {"const": "USDT"}` without any schema/doc amendment.

### 3. Regression fixture + two-layer assertions

- Synthetic fixture now contains a USDC-quoted PERPETUAL `BTCUSDC` in both futures and spot fixtures, alongside the existing `BTCUSDT` spot decoy.
- `test_build_rows_usdc_perp_exact_match_not_aliased_to_usdt` feeds the `BTCUSDC` futures row directly into `build_rows` (bypassing the filter) and asserts `spot.symbol == "BTCUSDC"`, `match_type == "exact_symbol"`, and `spot.symbol != "BTCUSDT"`. This pins the call-site fix independently of the filter.
- `test_service_universe_filter_excludes_non_usdt_quote` uses a stub `SnapshotService` client injecting the bstock fixture and asserts `BTCUSDC` is excluded, `BTCUSDT` is retained, and every retained row has `quote_asset == "USDT"`.
- Existing tests `test_bstock_alias_classification`, `test_crypto_exact_match_not_aliased`, etc., are unmodified.

### 4. Offline live-raw re-verification (Section 6 of `60-test-output.txt`)

Replayable heredoc against the committed live raw (`reports/api-samples/public-market-bstock-alias-v1/20260703T170827Z/raw/`), no new HTTP:

- Eligible universe before quote filter: 691 TRADING perpetuals/TRADIFI (USDT 648, USDC 38, USD1 2, U 2, BTC 1).
- After `quoteAsset == "USDT"` filter: **648 rows, all USDT** (43 non-USDT excluded).
- `exact_symbol` mismatch rows (`spot.symbol != futures.symbol`): **0**.
- bStock alias closure: **15/15** unchanged.

Result: PASS.

## Independent test rerun

```bash
.venv/bin/python -m pytest backend/tests -q
```

Result:

```
......................................................                   [100%]
54 passed in 0.75s
```

(Previously 52; +2 rework tests, all green.)

```bash
grep -rn "float(" backend/domain backend/services
```

Result: no output → CLEAN. Decimal discipline preserved.

```bash
node frontend/self-check.js
```

Result: 11/11 PASS (frontend untouched by this fix).

## No new collateral-ratio hardcoding

The fix touches only the `quote_asset` argument and the universe filter. No `maintMarginPercent` / `requiredMarginPercent` / collateral-ratio constants are introduced in domain or service code.

## Residual risks (carry forward)

- Non-USDT-quoted perpetuals (USDC/USD1/U/BTC) are excluded from Phase 1 snapshots by user decision; support for them is deferred to a future contract/stage.
- bStock token vs US-equity 1:1 equivalence remains unproven by public exchangeInfo alone; deferred to later position-opening planning.
- bStock spot/margin session hours vs TRADIFI perpetual 7x24 continuity implications remain deferred to pre-trade planning.

## Disclosure

I am the Task B (frontend) implementer for this stage and performed the original Task A review-1; however, I had no involvement in the rework round 1 fix implementation, and no involvement in this stage's direction synthesis, development breakdown, or design. The cross-review pool assigned Task A review-1 to Kimi because the fix implementer is `claude_glm`.

本地北京时间: 2026-07-04 11:12:53 CST
下一步模型: review-2 最终门（决策池按 AGENTS.md 重新评估）
下一步任务: 对 head `548ae0d` 重新运行 review-2，绑定新 diff_fingerprint，controller 不声明最终验收。

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-public-market-bstock-alias-v1",
  "role": "first_reviewer",
  "model": "kimi-2.7",
  "verdict": "ACCEPT",
  "diff_fingerprint": "548ae0d382c0010c9ab1d0dc26f11ca7a0f47de9:97ac2539a3c044e56499a9731115be3d16fb024ffed6ac0620f7e4e60ce33a5f",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "我是本阶段 Task B（前端）实现者，且做过原 Task A 的 review-1；但本次复审的是 rework round 1 的 fix diff（由 claude_glm 实现），我未参与该 fix 的实现，也未参与本阶段的 direction synthesis / development breakdown / design。跨审查池因 Task A 实现者是 claude_glm 而把 review-1 分配给 Kimi。",
  "reviewed_artifacts": [
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/post-review-quote-asset-hardcode-finding.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/fix-start-prompt-spot-leg-quote-asset.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/40-fix-report.md",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json",
    "reports/agent-runs/2026-07-public-market-bstock-alias-v1/70-handoff.md",
    "backend/domain/snapshot.py",
    "backend/services/snapshot_service.py",
    "backend/domain/normalize.py",
    "backend/domain/classify.py",
    "backend/tests/test_snapshot.py",
    "backend/tests/fixtures/bstock-alias-raw/fapi-v1-exchangeInfo.json",
    "backend/tests/fixtures/bstock-alias-raw/api-v3-exchangeInfo.json",
    "schemas/api/public-market/snapshot.schema.json",
    "docs/api/public-market-contract.md",
    "git diff --binary b1894406cf50173fc110f92b63fc3fe2f7ad7fc1..548ae0d382c0010c9ab1d0dc26f11ca7a0f47de9"
  ],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [
    "Non-USDT-quoted perpetuals (USDC/USD1/U/BTC) are excluded from Phase 1 snapshots by user decision; support deferred to a future contract/stage.",
    "bStock token vs US-equity 1:1 equivalence remains unproven by public exchangeInfo alone; deferred to later position-opening planning.",
    "bStock spot/margin session hours vs TRADIFI perpetual 7x24 continuity implications remain deferred to pre-trade planning."
  ],
  "next_action": "continue"
}
```
