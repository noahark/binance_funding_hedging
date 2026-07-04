# Review-2 (rework round 1, stage-level FINAL GATE) — public-market-bstock-alias-v1

You are Codex/GPT (`gpt-5.5`, xhigh), acting as the `final_reviewer` — the
**final review gate** — in **read-only** sandbox mode. Do not modify any file.

This is a **rework review-2 (round 1 of 3)**, not the first review-2 and not the
evidence-backfill recheck. The prior review-2 RECHECK returned **ACCEPT** bound
to head `b189440` (`status.json.review_2`, output `50-review-2-recheck.md`,
raw `review-2-recheck-codex.raw-output.txt`); that verdict is preserved verbatim
but is **challenged** by a user-directed **external post-review P1 finding**
(`spot_leg_quote_asset_hardcode`, reviewer anthropic/`claude-fable-5`, NO prior
involvement in this stage). Rework round 1 applied a fix (`H_fix` = `548ae0d`).
Review-1 (rework re-review) by Kimi already returned **ACCEPT** on the fix diff
(`30-review-1-fix.md`). You now re-verify the whole stage at the new head and
adjudicate whether the fix genuinely closes the P1 regression. Prior verdicts
are not binding on you.

Read the source evidence verbatim (do not rely on this summary):

- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/post-review-quote-asset-hardcode-finding.md`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/fix-start-prompt-spot-leg-quote-asset.md`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/40-fix-report.md`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/30-review-1-fix.md`

## Disclosure: prior direction-synthesis involvement (strong-reviewer override)

You (Codex/GPT) are the prior direction synthesizer for the covering contract
stage (`2026-07-public-market-contract-v2`, `approved_prior_stage`; no new
direction panel this stage). `reviewer_prior_involvement = direction_synthesis`.
You wrote NO delivery code and NO fix this stage (the fix was authored by
`claude_glm`, the controller/Task A owner). Fable5/Anthropic was reached for the
post-review finding (user-directed, in an Anthropic-authenticated environment,
2026-07-04), so it IS reachable in principle; however the controller dispatch
shell's `claude` CLI auth re-routes to `zhipu_glm`, so from this runner Fable5
is not probed on an Anthropic endpoint (per the Fable5 probe hygiene rule that
is recorded as "Anthropic endpoint not probed (auth re-routed to GLM/Zhipu)",
NOT as Fable5 unavailable). Both implementers (`claude_glm`, `kimi`) are
hard-banned from review-2. Per AGENTS.md review-2 uses GPT/Codex first; with no
provider-unrelated decision model reachable from this runner, you review via the
**strong-reviewer disclosure override**. The hard ban is satisfied (you authored
no delivery code and no fixes).

Top-level requirements (highest authority): the user-approved direction
synthesis, the PRD, the user's 6 amendment points (verbatim in `00-task.md`),
the amended contract (`docs/api/public-market-contract.md`,
`schemas/api/public-market/snapshot.schema.json`), and the **user decision of
2026-07-04** (Phase 1 snapshot covers USDT-quoted pairs only — recorded in
`status.json.user_decisions[0]` and `open_items[2]` RESOLVED).

## What the fix changed (the rework delta)

`base_sha` is unchanged (`d240e43`). The head advanced `b189440 -> 548ae0d`
(`H_fix`). The fix is TWO lines of product code plus tests/fixture/evidence,
folded with the 2026-07-04 user decision:

1. `backend/domain/snapshot.py:70` — the `resolve_spot_leg(...)` call site now
   passes `obj.get("quoteAsset", "")` instead of the literal `"USDT"`
   (call-site contract-faithful). `resolve_spot_leg` and `classify.py` are
   UNCHANGED. `snapshot.py:99` `"quote_asset": "USDT"` output is UNCHANGED (true
   for every retained row after the filter).
2. `backend/services/snapshot_service.py` — the universe filter adds
   `and s.get("quoteAsset") == "USDT"` (user decision 2026-07-04; honors the
   existing frozen `snapshot.schema.json` `row.quote_asset = {"const": "USDT"}`;
   NOT a contract amendment — no schema/doc change) + a faithful one-word
   docstring update.
3. `backend/tests/fixtures/bstock-alias-raw/{fapi-v1-exchangeInfo,api-v3-exchangeInfo}.json`
   — one USDC-quoted PERPETUAL `BTCUSDC` added (futures + spot; `BTCUSDT` spot
   already present as the exact-match decoy).
4. `backend/tests/test_snapshot.py` — two new tests
   (`test_build_rows_usdc_perp_exact_match_not_aliased_to_usdt`,
   `test_service_universe_filter_excludes_non_usdt_quote`); no existing test
   altered.
5. `60-test-output.txt` Section 6 — offline replay of the SAME committed live
   raw (NO new HTTP) asserting universe==648 all-USDT rows, zero
   `exact_symbol` rows with `spot.symbol != futures.symbol`, 15/15 bStock alias
   unchanged.
6. `40-fix-report.md` (finding→fix mapping); `status.json` bookkeeping.

## What did NOT change (verify this yourself — it is the core of the gate)

```bash
git diff --stat b1894406cf50173fc110f92b63fc3fe2f7ad7fc1..548ae0d382c0010c9ab1d0dc26f11ca7a0f47de9 -- backend/domain/normalize.py backend/domain/classify.py schemas docs frontend reports/api-samples
```

Expected: **empty**. `resolve_spot_leg` (the pure function) and `classify.py`
(the priority sequence incl. BSTOCK→DISABLED_BSTOCK) must be byte-identical over
this range; the frozen `snapshot.schema.json` / `public-market-contract.md` must
be unchanged; `reports/api-samples/**` (historical + live capture evidence)
read-only; `frontend/**` untouched. Any hit here is a P1 finding (REWORK).

## Review subject (recompute this yourself)

- base_sha: `d240e43e75034a6718ede79bc295d39e77cd860e`
- head_sha: `548ae0d382c0010c9ab1d0dc26f11ca7a0f47de9`

Recompute the stage `diff_fingerprint`:

```bash
git diff --binary d240e43e75034a6718ede79bc295d39e77cd860e..548ae0d382c0010c9ab1d0dc26f11ca7a0f47de9 -- . ':(exclude)reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json' | shasum -a 256
```

Expected (`status.json.diff_fingerprint`):
`548ae0d382c0010c9ab1d0dc26f11ca7a0f47de9:97ac2539a3c044e56499a9731115be3d16fb024ffed6ac0620f7e4e60ce33a5f`.
A mismatch is P0/P1 — return REWORK.

## What to verify (checkpoints)

### A. The fix genuinely closes the P1 regression (the point of this rework)

1. `snapshot.py:70` passes the row's real `quoteAsset` to `resolve_spot_leg`.
   Independently confirm the pre-fix bug is gone: with the USDC-quoted `BTCUSDC`
   row fed DIRECTLY to `build_rows` (bypassing the filter),
   `spot.symbol=="BTCUSDC"`, `match_type=="exact_symbol"`, `exists is True`, and
   `spot.symbol != "BTCUSDT"`. Reproduce:
   `.venv/bin/python -m pytest backend/tests/test_snapshot.py::test_build_rows_usdc_perp_exact_match_not_aliased_to_usdt -q`.
   The pre-fix behavior (`BTCUSDC`→`BTCUSDT`) was the regression.
2. `snapshot_service.py` universe filter excludes non-USDT rows through the REAL
   pipeline. Reproduce:
   `.venv/bin/python -m pytest backend/tests/test_snapshot.py::test_service_universe_filter_excludes_non_usdt_quote -q`.
   Every retained row must have `quote_asset=="USDT"` (honoring the frozen
   schema const).
3. The `resolve_spot_leg` three-branch logic (exact / TRADIFI-only B-suffix
   alias / none) and the `classify.py` priority (BSTOCK→DISABLED_BSTOCK at
   priority 2) are UNCHANGED — the fix is purely at the call site + filter, not
   in classification.
4. Live-raw replay (`60-test-output.txt` Section 6): universe==648 all-USDT (43
   non-USDT excluded), ZERO `exact_symbol` mismatch, 15/15 bStock alias
   unchanged. The previously-broken rows (BTCUSDC→BTCUSDT, ETHBTC→ETHUSDT,
   PNUTUSDC SPOT_ONLY→MARGIN_SPOT flip) are now excluded upstream AND the call
   site is contract-faithful (so the bug cannot recur for any retained row).
   Reproduce the heredoc in Section 6 against
   `reports/api-samples/public-market-bstock-alias-v1/20260703T170827Z/raw/`.

### B. Hard constraints (any breach is REWORK)

5. No live HTTP / API key / signed / private account / user data stream / order
   / borrow / repay / transfer / websocket was issued this rework (Section 6 is
   a REPLAY of already-committed live raw).
6. `classify.py` logic and `negative_funding_status` priority unchanged
   (`git diff b189440..548ae0d -- backend/domain/classify.py` empty);
   `resolve_spot_leg` unchanged. No collateral ratio hard-coded;
   `margin_public.source` stays unverified. `funding_history` default top-N=20
   unchanged.
7. The formal local page still loads data from the same-origin
   `/api/public-market/snapshot` (frontend untouched).

### C. Scope discipline (the fix must not widen)

8. `git diff --name-only b189440..548ae0d` product-code paths are exactly:
   `backend/domain/snapshot.py`, `backend/services/snapshot_service.py`,
   `backend/tests/test_snapshot.py`, and the two `bstock-alias-raw` fixtures.
   The only other changes are stage-evidence files
   (`40-fix-report.md`, `60-test-output.txt` Section 6, `status.json`,
   `30-review-1-fix.md`, the rework-intake finding/fix-start-prompt committed in
   intermediate commits). No schema/doc/contract amendment disguised as a fix;
   the user decision (USDT-only) deliberately honors the existing frozen const.

### D. Bookkeeping integrity

9. `status.json.review_2` (the prior b189440 ACCEPT recheck) is preserved
   verbatim with a `post_review_finding_note` disclosing it is challenged by the
   finding; it is NOT altered. `rework.round=1`, `fix_commit=548ae0d`,
   `post_review_findings[spot_leg_quote_asset_hardcode].status` reflects the
   rework state. The pre-rework Task A review-1 verdict (head `1f94c84`) is
   preserved in `tasks.A.review_1.pre_rework_verdict`; Task B (frontend) was
   untouched by the fix so its review-1 verdict (head `5968c49`) stands.

### E. Decimal/float discipline + full suite

10. `grep -rn "float(" backend/domain backend/services` → CLEAN (decimal fields
    stay strings). `.venv/bin/python -m pytest backend/tests -q` → 54 passed
    (52 + 2 rework tests). `node frontend/self-check.js` → 11/11 (frontend
    untouched, regression guard).

If you find a genuine correctness/safety/boundary defect — e.g. the fix fails
to close the regression, the filter is wrong, classification silently changed,
or a hard constraint is breached — return `REWORK` with a `fix_start_prompt`.
Otherwise return `ACCEPT`.

## Boundary (read-only)

Read anything. Modify nothing. Recompute fingerprints and re-check the fix
yourself against raw code, raw diff, the live-raw replay, and the amended
contract.

## Output contract (strict)

Emit your review narrative, then a single JSON verdict object conforming to
`schemas/review-verdict.schema.json`. You are NOT invoked with `--output-schema`
(the OpenAI structured-output endpoint rejects this schema's shape), so produce
the JSON BY INSTRUCTION as a fenced ```json block as the FINAL part of your
reply. The controller extracts and validates it post-hoc. Use:

- `schema_version`: `1`
- `stage_id`: `2026-07-public-market-bstock-alias-v1`
- `role`: `final_reviewer`
- `model`: `gpt-5.5`
- `verdict`: `ACCEPT` or `REWORK` (or `BLOCKED`)
- `diff_fingerprint`: your recomputed stage-level value
  (`548ae0d…:<your sha256>`)
- `reviewer_prior_involvement`: **`direction_synthesis`**
- `reviewer_prior_involvement_notes`: disclose prior direction synthesis
  (approved_prior_stage, covers this stage, no new panel), no
  design/breakdown/code/fix involvement this stage; Fable5 reached for the
  user-directed finding but not probed from this runner (claude CLI auth
  re-routed to GLM/Zhipu); strong-reviewer override; hard ban satisfied.
- `reviewed_artifacts`: the paths you inspected
- `findings`: ordered by severity (empty allowed for ACCEPT)
- `required_fixes`: empty for ACCEPT
- `residual_risks`: carry-forward notes
- `next_action`: `stage_accepted_waiting_user` for ACCEPT, `fix` for REWORK

Emit the JSON verdict as the final block of your reply, fenced in ```json.
