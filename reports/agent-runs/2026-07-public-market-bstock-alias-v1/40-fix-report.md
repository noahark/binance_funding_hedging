# Fix Report — rework round 1: spot-leg quoteAsset hardcode

- **Stage**: `2026-07-public-market-bstock-alias-v1`
- **Rework round**: 1 of 3 (user-directed, after a P1 external post-review)
- **Finding id**: `spot_leg_quote_asset_hardcode` (severity P1 regression)
- **Reviewer of record**: anthropic / `claude-fable-5` (user-directed external
  post-review; NO prior involvement in this stage; Fable5 reachable as of
  2026-07-04)
- **Controller / Task A owner**: `claude_glm` (`glm-5.2[1m]`)
- **Reviewed diff (pre-fix)**: base `d240e43` .. head `b189440`
  (stage `diff_fingerprint` `b1894406…:9d6569d1…0aba`)
- **Status transition**: `fixing` -> `review_1` -> `review_2` ->
  `stage_accepted_waiting_user`. Controller does NOT declare final acceptance
  (`can_accept_final=false`).

Source evidence (read verbatim, not paraphrased):

- `post-review-quote-asset-hardcode-finding.md`
- `fix-start-prompt-spot-leg-quote-asset.md`
- `status.json` `post_review_findings` + `user_decisions`

## Finding summary

`backend/domain/snapshot.py:70` passed the literal `"USDT"` as the `quote_asset`
argument to `resolve_spot_leg` instead of the row's own `obj.get("quoteAsset")`.
Because the upstream universe filter (`backend/services/snapshot_service.py`)
did NOT filter on `quoteAsset`, every non-USDT-quoted perpetual resolved its
spot leg as `baseAsset + "USDT"` and was labeled `match_type="exact_symbol"`
even though the futures and spot symbols differed. On this stage's own captured
live raw (691 eligible TRADING perpetuals/TRADIFI; quoteAsset dist USDT 648 /
USDC 38 / USD1 2 / U 2 / BTC 1), 39 of the 43 non-USDT rows had observably
wrong output — e.g. `BTCUSDC`->`BTCUSDT`, `ETHBTC`->`ETHUSDT`, and
`PNUTUSDC`'s route flipped `SPOT_ONLY_CANDIDATE` -> `MARGIN_SPOT_CANDIDATE`
(its margin flag was read from the wrong pair). `resolve_spot_leg` itself and
the 15/15 bStock alias closure were correct; the defect was the single call
site.

The user decided on 2026-07-04 (folded into this rework, `user_decisions[0]`,
`open_items[2]` RESOLVED): **Phase 1 snapshot covers USDT-quoted pairs only**.
The universe filter gains `quoteAsset == "USDT"`, which honors the existing
frozen `snapshot.schema.json` `row.quote_asset = {"const": "USDT"}` and is NOT
a contract amendment (no schema/doc change). Other stablecoin-quoted pairs
(USDC/USD1/U/…) are deferred to a future stage.

## Finding -> fix mapping

| # | Finding item | Fix | Landing point | Verification | Result |
|---|---|---|---|---|---|
| 1 | P1: `snapshot.py:70` hardcodes `quote_asset="USDT"` | Pass `obj.get("quoteAsset", "")` at the call site | `backend/domain/snapshot.py:70` (one arg) | `test_build_rows_usdc_perp_exact_match_not_aliased_to_usdt`: feeding the USDC-quoted `BTCUSDC` row directly resolves `spot.symbol=="BTCUSDC"` / `match_type=="exact_symbol"`, never `BTCUSDT` | PASS |
| 2 | User decision 2026-07-04: Phase 1 = USDT-quoted only | Universe filter adds `s.get("quoteAsset") == "USDT"` | `backend/services/snapshot_service.py` `build_snapshot` (one filter clause) + module docstring faithful update | `test_service_universe_filter_excludes_non_usdt_quote`: real `SnapshotService` pipeline (stub client injecting the bstock fixture) excludes `BTCUSDC`, retains `BTCUSDT`, every retained row `quote_asset=="USDT"` | PASS |
| 3 | Regression coverage gap (fixtures/checks were USDT-only) | Synthetic fixture adds a USDC-quoted PERPETUAL | `backend/tests/fixtures/bstock-alias-raw/fapi-v1-exchangeInfo.json` (+`BTCUSDC` futures), `api-v3-exchangeInfo.json` (+`BTCUSDC` spot; `BTCUSDT` spot already present as the decoy) | Two-layer assertions: service-level exclusion + build_rows-level exact match (item 1). Existing bStock alias + USDT exact cases unchanged | PASS |
| 4 | Live raw re-verification (no new HTTP) | Replay the committed live raw through the fixed pipeline | `60-test-output.txt` Section 6 (replayable heredoc) | universe == 648 all-USDT (43 non-USDT excluded); ZERO `match_type=="exact_symbol"` with `spot.symbol != futures.symbol`; 15/15 bStock alias unchanged | PASS |

## Files changed (boundary-respecting)

Product code (Task A scope):

- `backend/domain/snapshot.py` — **only** the `resolve_spot_leg(...)` call site
  at line 70 (the `quote_asset` argument). `snapshot.py:99` `"quote_asset":
  "USDT"` output is UNCHANGED (true for every retained row after the filter).
- `backend/services/snapshot_service.py` — **only** the universe filter clause
  (`and s.get("quoteAsset") == "USDT"`) + a one-word faithful update of the
  module docstring pipeline line ("TRADING USDT-quoted perpetuals/TRADIFI").
- `backend/tests/test_snapshot.py` — two new tests (build_rows-level +
  service-level); no existing test altered.
- `backend/tests/fixtures/bstock-alias-raw/{fapi-v1-exchangeInfo.json,
  api-v3-exchangeInfo.json}` — one `BTCUSDC` entry each.

Stage evidence (this stage's directory):

- `40-fix-report.md` (this file), `60-test-output.txt` (Section 6 appended),
  `status.json` (controller bookkeeping).

Untouched (forbidden, verified): `backend/domain/normalize.py`
(`resolve_spot_leg` pure function unchanged), `backend/domain/classify.py`
(regression-asserted only), `schemas/**`, `docs/**`, `frontend/**`,
`agents/**`, `workflows/**`, `scripts/**`, `reports/api-samples/**` (read-only
historical evidence). No live HTTP / key / signed / order / borrow / repay /
transfer / websocket.

## Verification (all required commands, post-fix)

```
$ python3 -m pytest backend/tests -q
54 passed in 0.76s          # was 52; +2 rework tests, all green

$ grep -rn "float(" backend/domain backend/services
CLEAN                        # decimal discipline preserved

$ node frontend/self-check.js
全部自检通过                 # 11/11 PASS (frontend untouched)

$ python3 scripts/validate-stage.py 2026-07-public-market-bstock-alias-v1 --phase checkpoint
STAGE VALIDATION PASSED      # status=fixing; fingerprint = b189440:9d6569d1…
```

Plus the live-raw re-verification (`60-test-output.txt` Section 6): universe
648 all-USDT, zero exact_symbol mismatch, 15/15 bStock alias.

## Preserved behavior / non-regression

- `resolve_spot_leg` and `classify.py`: zero diff over `d240e43..H_fix`
  (`negative_funding_status` priority unchanged; bStock closure intact).
- The 15/15 bStock alias closure (`MARGIN_SPOT_CANDIDATE` +
  `bstock_b_suffix_alias` + `DISABLED_BSTOCK`) holds on live raw (Section 6).
- BTCUSDT exact match (negative control) unchanged.
- Existing 52 tests stayed green; only 2 tests were added.

## Open items (carry forward, do NOT block this rework)

- **RESOLVED BY USER DECISION (2026-07-04)**: the `quote_asset` const vs
  unfiltered-universe inconsistency is resolved inside this rework (USDT-only
  universe filter). Non-USDT stablecoin-quoted pairs deferred to a future
  stage/contract amendment. (`open_items[2]`, `user_decisions[0]`.)
- Still deferred to a later position-opening planning contract pre-trade
  verification (unchanged from prior rounds): bStock token vs US-equity 1:1
  equivalence; bStock spot/margin session vs TRADIFI perpetual 7x24.

## Closeout protocol (fingerprint + re-review)

- Commit the fix as `H_fix`; recompute the task-A-level and stage-level
  `diff_fingerprint` under the single existing protocol
  (`head_sha + ':' + sha256(git diff --binary <base>..<head> --
  . ':(exclude)reports/agent-runs/<stage-id>/status.json')`). `base_sha`
  (`d240e43`) is unchanged; `head_sha` advances to `H_fix`.
- `status.json` bookkeeping: `post_review_findings[spot_leg_quote_asset_hardcode].status`
  -> `fix_applied_pending_review`; `rework_count=1`; head/fingerprint rebound;
  status -> `review_1`.
- review-1 (task-level, Kimi, cross-review) re-verdicts on the fix diff.
- review-2 (final gate) re-runs bound to the new head. **Decision pool
  re-evaluation per AGENTS.md**: Fable5 (anthropic) is reachable as of
  2026-07-04 and had NO prior involvement in this stage, so it is now a
  provider-unrelated decision model for review-2 (no strong-reviewer override
  required if Fable5 reviews). The prior "Fable5 unavailable" routing records
  no longer apply. Both implementers (`claude_glm`, `kimi`) remain hard-banned
  from review-2.
- Controller does NOT declare final acceptance (`can_accept_final=false`).

本地北京时间: 2026-07-04 (rework round 1)
下一步模型: Kimi (review-1 on the fix diff) -> then review-2 (final gate, decision pool re-evaluated; Fable5/anthropic now reachable)
下一步任务: Commit H_fix, recompute + rebind fingerprints, status -> review_1, dispatch review-1 (Kimi) on the fix diff, then review-2 bound to the new head.
