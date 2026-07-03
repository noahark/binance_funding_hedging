# Review-2 (stage-level, FINAL GATE) — public-market-bstock-alias-v1

You are Codex/GPT (`gpt5.5`, xhigh), acting as the `final_reviewer` — the
**final review gate** — in **read-only** sandbox mode. Do not modify any file.

Stage: `2026-07-public-market-bstock-alias-v1`. This is a **contract amendment
+ implementation repair** stage. It amends the previously frozen
`public-market-snapshot/v1` contract to add the bStock B-suffix spot-leg alias
rule, repairs the backend spot-match join, adds the frontend alias display, and
closes the P1 finding `bstocks_b_suffix_spot_margin_alias` raised against the
prior stage `2026-07-public-market-impl-v1`.

You review the **whole stage implementation** (Task A contract amendment +
backend + tests; Task B frontend; Task C integration), not a single task.
Review-1 (two task-level verdicts, both ACCEPT) already ran; you may read those
verdicts but you are NOT bound by them — re-verify the material claims yourself.

## Disclosure: prior direction-synthesis involvement (strong-reviewer override)

You (Codex/GPT) are the **prior direction synthesizer** for the covering
contract stage (`2026-07-public-market-contract-v2`), whose user-approved
direction synthesis covers Phase 1 public market, which this amendment stage
operates within (`direction_synthesis.status = approved_prior_stage`;
`complexity.direction_panel_required = false`; no new direction panel ran this
stage). You therefore have **prior direction-synthesis involvement**, not
`none`.

You have **NO** stage-design, development-breakdown, implementation, or
fix-authorship involvement this stage:

- Designer + breakdown author = the stage controller (`claude_glm`), via
  controller-direct design (`10-design.md`, `11-adr.md`). Fable5 (the usual
  breakdown author) was **unreachable** this session (`claude` CLI auth routes
  to `zhipu_glm`; `--model claude-fable-5` returns error 1211; see
  `fable5-detail-breakdown.unavailable.md`). Fable5 has NO involvement this
  stage.
- Task A contract + backend implementer = `claude_glm` (glm-5.2[1m]).
- Task B frontend implementer = `kimi` (kimi-2.7).
- Task C integration = the stage controller (`claude_glm`), no product code.

You did not write any delivery code in this stage, so the review-2
implementer/fix-author hard ban is satisfied. Per AGENTS.md, because no
provider-unrelated decision model exists for this stage (decision pool =
{GPT/Codex, Anthropic}; Codex=prior direction only; Fable5=unavailable; both
implementers `claude_glm`/`kimi` hard-banned), you review via the
**strong-reviewer disclosure override**. This is the AGENTS.md-preferred
"GPT/Codex first" path.

**You MUST set `reviewer_prior_involvement: "direction_synthesis"`** and
disclose the above in `reviewer_prior_involvement_notes`.

Per AGENTS.md, treat the **user-approved direction synthesis, the PRD, the
user's 6 amendment points (verbatim in `00-task.md`), and the amended
contract** (`docs/api/public-market-contract.md`,
`schemas/api/public-market/snapshot.schema.json`) as the **top-level
requirements**. The controller-direct design artifacts are **reviewed
evidence, not the highest authority** — if design and contract disagree, the
contract wins.

## User's 6 amendment points (this is what the stage MUST deliver)

From `00-task.md`, verbatim intent:

1. **TRADIFI/BSTOCK spot legs are matched via `baseAsset + "B" + quoteAsset`**
   (e.g. futures `TSLAUSDT` → spot `TSLABUSDT`).
2. `spot.match_type = "bstock_b_suffix_alias"` for the alias join; exact crypto
   joins stay `"exact_symbol"`.
3. **bStock positive funding rate is a candidate** (`positive_funding_enabled = true`).
4. **bStock negative funding rate stays disabled** (cannot borrow the coin →
   `negative_funding_status = DISABLED_BSTOCK`).
5. **Collateral ratio stays dynamic/unknown — NOT hard-coded** to any fixed
   proportion; `margin_public.source` stays `"unverified"`.
6. `classify.py` logic and the `negative_funding_status` priority sequence are
   NOT changed (regression-asserted only). The fix is the spot-match join, not
   the classifier.

## Review subject (recompute this yourself — do not trust this summary)

The stage-level commit range:

- base_sha: `d240e43e75034a6718ede79bc295d39e77cd860e` (`H_intake`)
- head_sha: `0842820ff21d30f563d25a3ff914cd705e6d9002` (`H_C`)

Recompute the stage `diff_fingerprint` from a clean shell in the repo root:

```bash
git diff --binary d240e43e75034a6718ede79bc295d39e77cd860e..0842820ff21d30f563d25a3ff914cd705e6d9002 -- . ':(exclude)reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json' | shasum -a 256
```

Expected (recorded in `status.json.diff_fingerprint`):

```text
0842820ff21d30f563d25a3ff914cd705e6d9002:24ce862a277987871fadbeb7e46ee3e59db923904ff28468ac84482ac48fb9ac
```

If your recomputed value differs, that is a P0/P1 finding — return REWORK.

Also recompute and confirm the **task-level boundaries** (each task's diff must
contain only its owner's files; `status.json` excluded):

- Task A (`d240e43e..1f94c84`): expect
  `fe6d0bd9d16ea2e75c54b59ed9469f206c5e733dc4d159ba35c959d63ad4c815`, 14 files:
  `schemas/api/public-market/snapshot.schema.json` (amendable),
  `docs/api/public-market-contract.md` (amendable),
  `backend/domain/normalize.py`, `backend/domain/snapshot.py`,
  `backend/tests/conftest.py`, `backend/tests/test_normalize.py`,
  `backend/tests/test_snapshot.py`, `backend/tests/test_negative_schema.py`,
  `backend/tests/fixtures/bstock-alias-raw/*.json` (4 synthetic),
  `20-implementation-backend.md`, `60-test-output.txt`.
- Task B (`6ea4504..5968c49`): expect
  `8c5d685eb8a51ea3261cb85cda97cfa000b2fb66ccddf49d3b0f0031a4b7c7d0`, 5 files:
  `frontend/index.html`, `frontend/self-check.js`,
  `frontend/fixture/public-market-snapshot.json`, `20-implementation-frontend.md`,
  `task-b-kimi-prompt.md`.
- Task C (`a57581e..0842820`): stage summary + test-output Section 4 +
  integration sample + handoff; **no product code**.

**NOTE on amendable contract files:** Unlike a fresh implementation stage, THIS
stage is *permitted* to edit `schemas/api/public-market/snapshot.schema.json`
and `docs/api/public-market-contract.md` (the amendment). Those two edits inside
Task A's diff are EXPECTED, not a boundary violation. What MUST stay read-only is
`reports/api-samples/public-market-contract-v2/**` (frozen historical evidence)
and the prior stage `2026-07-public-market-impl-v1/**` historical evidence.

Any cross-task leakage (frontend file in Task A's diff, backend file in Task B's
diff, product code in Task C's diff, or a touch to frozen historical samples) is
a P1 finding — return REWORK.

## Raw artifacts to inspect directly (do not rely on controller summaries)

Read these yourself:

- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/00-task.md` (scope, the 6 amendment points, acceptance)
- `10-design.md`, `11-adr.md`, `fable5-detail-breakdown.unavailable.md`
- `20-implementation.md` (stage summary), `20-implementation-backend.md`, `20-implementation-frontend.md`
- `30-review-1.md` (aggregate), `30-review-1-backend.md`, `30-review-1-frontend.md`
- `60-test-output.txt` (raw test evidence), `task-c-integration-check.py`, `integration-snapshot-bstock-alias.json`
- `status.json`
- `backend/domain/normalize.py` (`resolve_spot_leg`), `backend/domain/snapshot.py` (`build_rows`, `CONTRACT_WARNINGS`)
- `backend/domain/classify.py` (verify UNCHANGED), `backend/tests/test_classify.py` (verify UNCHANGED)
- `backend/tests/test_normalize.py`, `backend/tests/test_snapshot.py`, `backend/tests/test_negative_schema.py`, `backend/tests/conftest.py`
- `backend/tests/fixtures/bstock-alias-raw/*.json` (4 synthetic offline fixtures)
- `frontend/index.html`, `frontend/self-check.js`, `frontend/fixture/public-market-snapshot.json`
- `schemas/api/public-market/snapshot.schema.json` (amended contract / top authority)
- `docs/api/public-market-contract.md` (amended contract / top authority)
- The frozen stage diff:
  `git diff --binary d240e43e..0842820 -- . ':(exclude)reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json'`

## What to verify (each is a checkpoint)

### A. Hard constraints (security/safety — any breach is REWORK)

1. **No API key, signed endpoint, private account endpoint, user data stream.**
   Grep the diff + `backend/**`: `grep -RniE 'apikey|api_key|secret|signature|userDataStream|listenKey|/sapi/|/dapi/v1/order|/fapi/v1/order' backend` (expect none functional).
2. **No order / borrow-action / repay / transfer / websocket.** The ONLY
   acceptable "borrow" string is the `PRIVATE_BORROW_VALIDATION_REQUIRED` enum
   rendered as a display badge. No websocket client anywhere.
3. **Frozen historical samples untouched.** Confirm the stage diff does NOT
   modify `reports/api-samples/public-market-contract-v2/**` nor
   `reports/agent-runs/2026-07-public-market-impl-v1/**` historical evidence
   (raw outputs, integration samples). The amendable contract files
   (`snapshot.schema.json` + `public-market-contract.md`) ARE edited by design.
4. **Same-origin formal page.** The frontend default load fetches the relative
   `/api/public-market/snapshot`; the fixture is a manual offline fallback.
5. **funding_history default top-N=20** unchanged.
6. **No live HTTP this stage.** Tests are offline against synthetic fixtures
   only.

### B. Amendment correctness (the core of this stage)

7. **`resolve_spot_leg`** (`backend/domain/normalize.py`) is a pure function with
   three branches: exact `base+quote` → `("exact_symbol")`; only when
   `contract_type == "TRADIFI_PERPETUAL"`, alias `base+"B"+quote` →
   `("bstock_b_suffix_alias")`; else `(None, None)`. Exact is tried FIRST, so a
   TRADIFI symbol with an exact spot leg never aliases. Normal `PERPETUAL` never
   aliases. The alias must NOT pollute crypto exact matches.
8. **`build_rows`** (`backend/domain/snapshot.py`) calls `resolve_spot_leg`,
   fills `spot.match_type`, and the downstream `classify_route` /
   `negative_funding_status` calls are UNCHANGED. `CONTRACT_WARNINGS[2]` states
   the alias rule, contains `TRADIFI_PERPETUAL`, and says the collateral ratio
   is dynamic/unknown and NOT hard-coded.
9. **`classify.py` UNCHANGED** — `git diff d240e43..0842820 --
   backend/domain/classify.py` is EMPTY. The priority sequence
   (PERP_ONLY→DISABLED_PERP_ONLY beats BSTOCK→DISABLED_BSTOCK beats
   SPOT_ONLY→DISABLED_SPOT_ONLY beats default PRIVATE_BORROW_VALIDATION_REQUIRED)
   is intact.
10. **Semantic closure** (re-derive yourself from the synthetic fixture): a
    TRADIFI futures `TSLAUSDT` with a B-suffix spot/margin leg `TSLABUSDT`
    (`isMarginTradingAllowed=true`) resolves to
    `route_class=MARGIN_SPOT_CANDIDATE`, `positive_funding_enabled=true`,
    `spot.symbol=TSLABUSDT`, `spot.match_type=bstock_b_suffix_alias`, and —
    because `asset_tag=BSTOCK` takes priority in `negative_funding_status` —
    `negative_funding_status=DISABLED_BSTOCK` (negative rate still disabled,
    cannot borrow). This must hold WITHOUT any `classify.py` change. A
    negative-rate bStock must stay disabled; a positive-rate bStock becomes a
    candidate. This is the user's points 3 & 4.
11. **Collateral ratio NOT hard-coded**; `margin_public.source == "unverified"`
    in every row; `public_cross_margin_pair` still null. No fixed proportion
    anywhere. (User point 5.)
12. **Schema amendment** — `spot.match_type` is a nullable enum
    `["exact_symbol", "bstock_b_suffix_alias", null]` and is **NOT** in
    `spot.required`. The frozen curated sample (which has no `match_type`)
    therefore remains schema-valid. When `spot.exists=false`, `match_type=null`.
13. **Contract doc** — `docs/api/public-market-contract.md` upgrades the bStock
    note to a frozen amendment dated 2026-07-03 referencing this stage, records
    the `resolve_spot_leg` rule, states the priority sequence is unaffected by
    the amendment, and the response example shows `match_type`. Open
    Verification Items RESOLVED.

### C. Decimal discipline (any float() on a price/rate/quantity path is REWORK)

14. `grep -RnE '\bfloat\(' backend --include='*.py'` returns no matches (clean).
    Decimal fields remain strings from raw JSON; ranking via `Decimal`.

### D. Frontend (Task B)

15. The symbol cell shows the actual spot leg + a "B 后缀别名" badge **only when**
    `row.spot.match_type === "bstock_b_suffix_alias"` AND `row.spot.symbol`
    exists AND `row.spot.symbol !== row.symbol`. `exact_symbol` and no-leg rows
    are untouched. Reuses existing badge styles (no CSS rewrite).
16. Default same-origin fetch; fixture is the manual offline fallback. No
    trading / open-position / account / order / borrow-action UI. Row-count-agnostic.
17. Fixture + self-check consistent: TSLAUSDT alias row wired as a candidate
    (`MARGIN_SPOT_CANDIDATE`, positive rate, `DISABLED_BSTOCK`, `TSLABUSDT`,
    `bstock_b_suffix_alias`, `PERP_ONLY_NO_SPOT_LEG` removed); MSTRUSDT stays
    PERP_ONLY; every spot block carries `match_type`; summary counts match the
    6 rows; `warnings[2]` synced to the backend verbatim.

### E. Integration & test evidence

18. `60-test-output.txt` Section 4 / `task-c-integration-check.py`: the synthetic
    fixture assembled via `build_rows` + `assemble_snapshot` is jsonschema-valid
    (with `match_type`); the 4 alias cases assert correctly.
19. Re-run the suites yourself:
    - `.venv/bin/python -m pytest backend/tests -q` (expect 52 passed)
    - `node frontend/self-check.js` (expect 11 PASS)
20. Review-1 scrutiny: both review-1 verdicts are ACCEPT — confirm the material
    claims (fingerprints, boundaries, no `classify.py` change, decimal
    discipline, alias semantic closure) hold independently. Do not rubber-stamp.

### F. Known non-blocking residuals (carry forward, do not block)

- The bStock alias rule is verified only against the **synthetic offline
  fixture**; no live Binance bStock spot/margin payload is captured this stage.
- The alias logic assumes quote asset `USDT` (`build_rows` passes `"USDT"` to
  `resolve_spot_leg`); non-USDT bStocks would require revisiting the alias
  construction.
- The frontend is tested on a 6-row fixture (one `bstock_b_suffix_alias` row);
  the live endpoint serves 688 rows. Rendering is row-count-agnostic.
- The live HTTP path is unchanged and not exercised this stage.
- This stage does NOT close the impl-v1 finding in impl-v1's `status.json` yet;
  that backfill happens by the controller only after THIS review-2 ACCEPTs and
  pre-accept passes (it updates impl-v1 `post_review_findings`, excluded from
  its hash). If you ACCEPT, the controller does that backfill; if you REWORK,
  it does not.

If you find a genuine correctness/safety/boundary defect, return `REWORK` with a
`fix_start_prompt`. Otherwise return `ACCEPT`.

## Boundary (read-only)

You may read anything in the repository. You may NOT modify any file. You may
NOT be swayed by controller or review-1 narratives — recompute fingerprints and
re-check rules yourself against the raw code, the raw diff, and the amended
contract.

## Output contract (strict)

Emit your review narrative, then a single JSON verdict object that must conform
to `schemas/review-verdict.schema.json`. You are NOT invoked with
`--output-schema` (the OpenAI structured-output endpoint rejects this schema's
shape), so you must produce the JSON BY INSTRUCTION, as a fenced ```json block
as the FINAL part of your reply. The controller extracts that block and
validates it against `schemas/review-verdict.schema.json` post-hoc; a
schema-invalid or missing block fails the gate. Use:

- `schema_version`: `1`
- `stage_id`: `2026-07-public-market-bstock-alias-v1`
- `role`: `final_reviewer`
- `model`: `gpt5.5`
- `verdict`: `ACCEPT` or `REWORK` (or `BLOCKED`)
- `diff_fingerprint`: your recomputed **stage-level** value
  (`0842820…9002:<your sha256>`)
- `reviewer_prior_involvement`: **`direction_synthesis`** (NOT none — you are the
  prior direction synthesizer; disclose in notes)
- `reviewer_prior_involvement_notes`: disclose prior direction synthesis
  (approved_prior_stage, covers this stage, no new panel this stage), no
  design/breakdown/code involvement this stage, Fable5 unreachable so no
  anthropic design involvement, strong-reviewer override invoked, hard ban
  satisfied.
- `reviewed_artifacts`: the paths you actually inspected
- `findings`: ordered by severity (P0 first); empty array allowed for ACCEPT
- `required_fixes`: empty for ACCEPT; concrete for REWORK
- `residual_risks`: the synthetic-fixture-only / USDT-quote-assumption /
  6-vs-688-row / live-HTTP-not-exercised notes
- `next_action`: `continue` for ACCEPT, `fix` for REWORK

If `verdict` is `REWORK`, you MUST include `fix_start_prompt` with raw paths,
ordered findings, required fixes, allowed boundaries, forbidden paths, and the
exact post-fix commands (`pytest backend/tests -q`, `node frontend/self-check.js`).

Emit the JSON verdict as the final block of your reply, fenced in ```json.
