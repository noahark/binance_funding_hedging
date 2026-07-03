# Task A Implementation — Contract Amendment + Backend bStock Alias Repair

Stage: `2026-07-public-market-bstock-alias-v1`
Task: A (owner Claude-GLM, `glm-5.2[1m]`)
Base: `H_intake` (`d240e43`). Head: `H_A` (filled at commit; fingerprint below).

This task closes impl-v1 post-review P1 finding
`bstocks_b_suffix_spot_margin_alias`. It amends the frozen
`public-market-snapshot/v1` contract (the alias rule was a descriptive note;
impl-v1's review-2 against the OLD frozen contract is NOT altered) and repairs
the backend so a TRADIFI futures symbol joins its `B`-suffixed spot/margin leg.

## What changed (every line traces to the user's 6 amendment points)

### Contract amendment (writable this stage)

1. `schemas/api/public-market/snapshot.schema.json` — added `spot.match_type`:
   nullable enum `["exact_symbol", "bstock_b_suffix_alias", null]`. Deliberately
   NOT in `required`, so the frozen curated sample (no `match_type` field) stays
   schema-valid backward.
2. `docs/api/public-market-contract.md` — promoted the "Post-review amendment
   required" descriptive note to a **Frozen amendment (2026-07-03)** rule with
   the exact spot-leg resolution order; added `match_type` to the response-shape
   example; added the `spot.match_type` enum; stated the
   `negative_funding_status` priority is unchanged; updated the bStock Open
   Verification Item to RESOLVED (amended).

### Backend repair

3. `backend/domain/normalize.py` — new pure function `resolve_spot_leg(contract_type,
   base_asset, quote_asset, spot_by_sym) -> (spot_obj|None, match_type|None)`:
   - exact `base_asset + quote_asset` -> `"exact_symbol"`;
   - else, ONLY when `contract_type == "TRADIFI_PERPETUAL"`, alias
     `base_asset + "B" + quote_asset` -> `"bstock_b_suffix_alias"`;
   - else `(None, None)`.
   No I/O; mirrors the existing `filter_of` / `asset_tag_for` pure-helper style.
4. `backend/domain/snapshot.py`:
   - import `resolve_spot_leg`;
   - `build_rows` replaced `spot = spot_by_sym.get(sym)` (the exact-symbol-only
     join that was the root cause) with a `resolve_spot_leg` call;
   - `build_rows` fills `spot.match_type`;
   - `CONTRACT_WARNINGS[2]` updated from the obsolete "All 118 TRADIFI ... have
     no spot leg" to the alias rule + "collateral ratio dynamic/unknown, not
     hard-coded".

### Tests (synthetic offline fixture — no live HTTP)

5. `backend/tests/fixtures/bstock-alias-raw/**` — synthetic raw covering 4 cases:
   - `TSLAUSDT` (TRADIFI, positive rate) -> `TSLABUSDT` margin spot (alias);
   - `AAPLUSDT` (TRADIFI, negative rate) -> `AAPLBUSDT` margin spot (alias,
     bStock-negative-rate case);
   - `BTCUSDT` (PERPETUAL) -> `BTCUSDT` (exact);
   - `NVDAUSDT` (TRADIFI) -> no spot leg (none).
   Each file carries a top-level `_synthetic` marker and mirrors the frozen raw
   field shapes.
6. `backend/tests/conftest.py` — `BSTOCK_RAW_DIR` + `bstock_raw_inputs` session
   fixture (same loader shape as `raw_inputs`; offline).
7. `backend/tests/test_normalize.py` — 5 `resolve_spot_leg` tests: exact, alias
   for TRADIFI, alias NOT triggered for PERPETUAL, none, exact-beats-alias.
8. `backend/tests/test_snapshot.py` — 6 bStock alias tests on the synthetic
   fixture: alias classification, bStock-negative-rate-still-disabled, crypto
   exact-not-aliased, no-spot match_type null, schema-valid snapshot, funding
   history.
9. `backend/tests/test_negative_schema.py` — `BASE_ROW.spot` carries
   `match_type`; `test_reject_invalid_match_type`; `test_match_type_null_is_valid`.

## Why `classify.py` is unchanged (the semantic core)

`backend/domain/classify.py` is NOT touched this stage. The user's points
"bStocks positive rate can be a candidate / negative rate stays disabled" are
satisfied automatically once the correct spot symbol reaches `classify_route`:

- `classify_route("TRADIFI_PERPETUAL", "TSLABUSDT", True)` ->
  `MARGIN_SPOT_CANDIDATE` -> `positive_funding_enabled=True` (candidate route).
- `negative_funding_status("MARGIN_SPOT_CANDIDATE", "BSTOCK")`: priority rank 2
  (`asset_tag==BSTOCK`) beats rank 4 -> `DISABLED_BSTOCK` (cannot borrow).

`backend/tests/test_classify.py::test_negative_bstock_when_route_has_spot`
already asserts this; it is untouched regression protection. The real fix is the
spot-leg join, which is exactly what `resolve_spot_leg` + `build_rows` now do.

## Untouched (regression-asserted, not modified)

- `backend/domain/classify.py` — logic and priority unchanged.
- `backend/config.py` — `funding_history` default top-N=20 unchanged.
- Frozen curated fixture / contract-v2 samples — read-only historical evidence
  (no bStock exists there, hence the synthetic fixture).
- `margin_public.source` stays `"unverified"`; no collateral ratio hard-coded.

## Verification (raw, replayable)

```text
=== pytest -q (full backend suite) ===
52 passed in 0.79s

=== focused -v (normalize + snapshot + negative_schema) ===
43 passed in 0.77s
... new bStock/alias tests all PASSED:
  test_resolve_spot_leg_exact_symbol
  test_resolve_spot_leg_bstock_alias_for_tradifi
  test_resolve_spot_leg_alias_not_triggered_for_perpetual
  test_resolve_spot_leg_none_when_no_spot
  test_resolve_spot_leg_exact_beats_alias_for_tradifi
  test_bstock_alias_classification
  test_bstock_negative_rate_still_disabled
  test_crypto_exact_match_not_aliased
  test_bstock_no_spot_match_type_null
  test_bstock_alias_snapshot_validates
  test_bstock_alias_has_funding_history
  test_reject_invalid_match_type
  test_match_type_null_is_valid
... frozen-sample regression still PASSED:
  test_classification_matches_frozen_six
  test_data_time_matches_frozen_sample
  test_three_contract_warnings_preserved

=== float() audit ===
grep -RnE '\bfloat\(' backend --include='*.py'  ->  CLEAN (no float() anywhere)

=== smoke_server.py (single process) ===
GET /api/public-market/snapshot -> HTTP 200, schema-valid
  rows=688 warnings=3 total_rows=688
  data_time=2026-07-03T05:11:29Z generated_at=2026-07-03T05:17:38Z source_sample_id=20260703T051738Z
SMOKE OK
```

`warnings=3` and the frozen `data_time`/`generated_at` confirm the frozen path
is unchanged; only the BSTOCK warning text moved (still 3 warnings, still
contains `TRADIFI_PERPETUAL`).

## Boundary compliance

Only Task A scope files written: `snapshot.schema.json`,
`docs/api/public-market.md`, `backend/domain/{normalize,snapshot}.py`,
`backend/tests/**`, `backend/tests/fixtures/bstock-alias-raw/**`, and this
report. `frontend/**`, `classify.py`, and the contract-v2 frozen samples were
not touched.

## Task A fingerprint

Filled at commit `H_A`:
- `base_sha`: `d240e43` (`H_intake`)
- `head_sha`: `<H_A>`
- `diff_fingerprint`: `head_sha + ':' + sha256(git diff --binary <base>..<head> -- . ':(exclude)reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json')`
