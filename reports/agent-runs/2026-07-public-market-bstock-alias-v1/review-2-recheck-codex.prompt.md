# Review-2 RECHECK (stage-level, FINAL GATE) — public-market-bstock-alias-v1

You are Codex/GPT (`gpt-5.5`, xhigh), acting as the `final_reviewer` — the
**final review gate** — in **read-only** sandbox mode. Do not modify any file.

This is a **RECHECK**, not the first review-2. The first review-2 already
returned **ACCEPT** against head `0842820` (synthetic-only scope); that prior
verdict is preserved verbatim as `status.json.review_2_prior` (see `50-review-2.md`
and `review-2-codex.raw-output.txt`). A user-directed **evidence-backfill round**
(2026-07-04) then expanded the stage scope, so the gate must rebind to the new
head. You re-verify the whole stage at the new head; the prior ACCEPT is not
binding on you.

## Disclosure: prior direction-synthesis involvement (strong-reviewer override)

You (Codex/GPT) are the prior direction synthesizer for the covering contract
stage (`2026-07-public-market-contract-v2`, `approved_prior_stage`; no new
direction panel this stage). `reviewer_prior_involvement = direction_synthesis`.
You wrote NO delivery code and NO fix this stage, and NO backfill code. The
backfill was authored by the controller (`claude_glm`). Fable5/Anthropic was not
probed on an Anthropic endpoint this stage (the local `claude` CLI auth is
re-routed to `zhipu_glm`; per the new Fable5 probe hygiene rule that is recorded
as "Anthropic endpoint not probed", not as Fable5 unavailable). Both implementers
(`claude_glm`, `kimi`) are hard-banned from review-2. With no provider-unrelated
decision model, you review via the **strong-reviewer disclosure override**
(AGENTS.md "GPT/Codex first"). The hard ban is satisfied (you wrote no delivery
code and no fixes, including no backfill code).

Top-level requirements (highest authority): the user-approved direction
synthesis, the PRD, the user's 6 amendment points (verbatim in `00-task.md`), and
the amended contract (`docs/api/public-market-contract.md`,
`schemas/api/public-market/snapshot.schema.json`).

## What changed this backfill (the recheck delta)

`base_sha` is unchanged (`d240e43`). The head advanced `0842820 -> b189440`.
Three backfill commits, all **non-product-code**:

1. `0578191` — Harness adapter corrections + two new rules:
   - AGENTS.md Hard Gates: a contract amendment must carry raw public samples
     under `reports/api-samples/<stage>/`; synthetic fixtures supplement, never
     replace fact evidence.
   - docs/model-adapters.md + AGENTS.md: Claude/Fable5 probes must strip
     GLM/Zhipu env vars first; a GLM-endpoint failure is not Fable5-unavailable.
   - Adapter command-template fixes (codex `codex exec --model gpt-5.5`;
     `claude-glm` via `zsh -lic`; kimi `--model kimi-code/kimi-for-coding`,
     `--plan`/`-y` cannot combine with `-p`).
2. `9f4764c` — live public capture
   `reports/api-samples/public-market-bstock-alias-v1/20260703T170827Z/`:
   anonymous `/fapi/v1/exchangeInfo` + `/api/v3/exchangeInfo` (no key / signed /
   private / order / borrow / repay / transfer / websocket). `evidence-index.md`
   cross-verifies the 15 user-listed bStocks (15/15).
3. `b189440` — `verify-on-live-raw.py` (drives the REAL
   `backend.domain.snapshot.build_rows` with the live exchangeInfo; 15/15 bStocks
   PASS; BTCUSDT negative control), `60-test-output.txt` Section 5, `70-handoff.md`
   backfill record + open items.

## What did NOT change (verify this yourself — it is the core of the recheck)

Confirm the backfill touched NO product code and NO contract:

```bash
git diff --stat 0842820ff21d30f563d25a3ff914cd705e6d9002..b1894406cf50173fc110f92b63fc3fe2f7ad7fc1 -- backend frontend schemas docs/api
```

Expected: **empty** (only `docs/model-adapters.md` changed, which is Harness
doc, not the contract). If any `backend/**`, `frontend/**`,
`schemas/api/public-market/snapshot.schema.json`, or
`docs/api/public-market-contract.md` line appears, that is a P1 finding
(REWORK) — the backfill was supposed to be evidence-only.

Because product code + contract are unchanged, the Task A/B product-code ranges
reviewed in review-1 (`d240e43..1f94c84`, `6ea4504..5968c49`) are untouched and
the review-1 task-level verdicts remain valid. The stage-level
`review_1.diff_fingerprint` / `review_2.diff_fingerprint` bindings will be
re-bound to the new head by the controller after your ACCEPT (mechanical rebind
due to head movement, NOT a re-review); confirm that treatment is legitimate.

## Review subject (recompute this yourself)

- base_sha: `d240e43e75034a6718ede79bc295d39e77cd860e`
- head_sha: `b1894406cf50173fc110f92b63fc3fe2f7ad7fc1`

Recompute the stage `diff_fingerprint`:

```bash
git diff --binary d240e43e75034a6718ede79bc295d39e77cd860e..b1894406cf50173fc110f92b63fc3fe2f7ad7fc1 -- . ':(exclude)reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json' | shasum -a 256
```

Expected (`status.json.diff_fingerprint`):
`b1894406cf50173fc110f92b63fc3fe2f7ad7fc1:9d6569d15b987c10eaa008b8b9b344f11c70aeaea7fe84d82dbb6030c89f0aba`.
A mismatch is P0/P1 — return REWORK.

## What to verify (checkpoints)

### A. Hard constraints (any breach is REWORK)

1. The live capture used NO API key / signed / private / order / borrow / repay
   / transfer / websocket. Inspect
   `reports/api-samples/public-market-bstock-alias-v1/20260703T170827Z/` (the
   two `.headers` files show standard public response headers, no auth token).
2. Frozen historical samples still untouched:
   `reports/api-samples/public-market-contract-v2/**` and
   `reports/agent-runs/2026-07-public-market-impl-v1/**` historical evidence are
   not modified by the backfill (the impl-v1 status.json finding-closure edit
   happened in a PRIOR commit `a218303`, already inside the range; it is a
   finding-status update, not a review-verdict alteration — confirm impl-v1
   review_1/review_2 verdicts + diff_fingerprint are intact).

### B. Live evidence correctness (the point of the backfill)

3. `evidence-index.md`: the 15 user-listed bStocks each have a spot leg
   (`XB+USDT`, `isMarginTradingAllowed=true`), a futures leg (`X+USDT`,
   `contractType=TRADIFI_PERPETUAL`, `status=TRADING`), and satisfy
   `futures_baseAsset+"B"+quoteAsset == spot_symbol`. 15/15.
4. `verify-on-live-raw.py` drives the REAL `build_rows` (not a stub) with the
   live exchangeInfo. Reproduce it:
   `.venv/bin/python reports/api-samples/public-market-bstock-alias-v1/20260703T170827Z/verify-on-live-raw.py`
   → 15/15 bStocks `MARGIN_SPOT_CANDIDATE` + `bstock_b_suffix_alias` +
   `DISABLED_BSTOCK`; BTCUSDT negative control `exact_symbol` (alias does NOT
   pollute crypto); assembled snapshot jsonschema-valid against the amended
   `snapshot.schema.json`. The semantic closure (positive-rate candidate /
   negative-rate disabled) holds on LIVE data with NO `classify.py` change.

### C. Harness rule correctness

5. The new Hard Gates rule (contract amendments must carry raw public samples)
   and the Fable5 probe hygiene rule are sound and do not weaken any existing
   gate. The adapter command templates match actual local CLI behavior.

### D. Bookkeeping integrity

6. `status.json.review_2_prior` preserves the prior ACCEPT verbatim (not
   altered); `review_2.status=recheck_pending`; `evidence_backfill` +
   `open_items` recorded. `classify.py` still unchanged
   (`git diff d240e43..b189440 -- backend/domain/classify.py` empty).
7. Open items (bStock token 1:1 equity equivalence; spot session vs perpetual
   7x24) are correctly deferred to a later position-opening planning contract
   and do not block this evidence backfill.

If you find a genuine correctness/safety/boundary defect, return `REWORK` with a
`fix_start_prompt`. Otherwise return `ACCEPT`.

## Boundary (read-only)

Read anything. Modify nothing. Recompute fingerprints and re-check rules
yourself against raw code, raw diff, raw capture, and the amended contract.

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
  (`b1894406…:<your sha256>`)
- `reviewer_prior_involvement`: **`direction_synthesis`**
- `reviewer_prior_involvement_notes`: disclose prior direction synthesis
  (approved_prior_stage, covers this stage, no new panel), no
  design/breakdown/code involvement this stage or this backfill, Fable5 not
  probed on an Anthropic endpoint (auth re-routed to GLM), strong-reviewer
  override, hard ban satisfied.
- `reviewed_artifacts`: the paths you inspected
- `findings`: ordered by severity (empty allowed for ACCEPT)
- `required_fixes`: empty for ACCEPT
- `residual_risks`: carry-forward notes
- `next_action`: `continue` for ACCEPT, `fix` for REWORK

Emit the JSON verdict as the final block of your reply, fenced in ```json.
