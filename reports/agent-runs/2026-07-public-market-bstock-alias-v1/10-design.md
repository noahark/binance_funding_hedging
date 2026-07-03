# Stage Design: 2026-07-public-market-bstock-alias-v1

Designer of record: the controller (Claude-GLM), because Fable5 was unreachable
this session (`fable5-detail-breakdown.unavailable.md`). This file records the
derived contract-amendment design, the backend spot-leg repair, and the Task A
↔ Task B integration contract. It is review evidence, not higher authority than
the user-approved synthesis / PRD / amended contract.

## Amendment design (Task A — contract half)

The frozen `public-market-snapshot/v1` contract is amended (not replaced).
`schema_version` stays `"public-market-snapshot/v1"`: the change is additive
(one nullable enum field + a clarifying route rule), backward-compatible for
any consumer that ignores unknown/null `match_type`.

1. **Schema** (`snapshot.schema.json`): the `spot` object gains `match_type`.
   ```json
   "match_type": {
     "type": ["string", "null"],
     "enum": ["exact_symbol", "bstock_b_suffix_alias", null]
   }
   ```
   `spot.exists=false` ⟺ `match_type=null` (enforced by backend + tests, not by
   a jsonschema cross-condition, which Draft 2020-12 cannot express compactly).
2. **Contract doc** (`public-market-contract.md`): the descriptive "Post-review
   amendment required" paragraph becomes "Frozen amendment (2026-07-03)",
   stating the route rule formally; `Enums` documents `spot.match_type`; the
   response-shape `spot` example carries `match_type`; `negative_funding_status`
   priority is explicitly re-asserted unchanged (BSTOCK still row 2); Open
   Verification Items updated.
3. **`CONTRACT_WARNINGS`** (served `warnings[]`, contract semantics): row index
   2 changes from "All 118 TRADIFI_PERPETUAL symbols have no spot leg …" to
   "TRADIFI/BSTOCK spot legs are joined via the baseAsset+B+quoteAsset alias;
   bStock collateral ratio is dynamic/unknown and not hard-coded." The other
   two warnings (margin unverified, `lastFundingRate` ambiguity) are unchanged.

## Backend spot-leg repair (Task A — code half)

`backend/domain/normalize.py` gains one pure function (no I/O, mirrors the
existing `filter_of` / `asset_tag_for` style):

```python
def resolve_spot_leg(contract_type, base_asset, quote_asset, spot_by_sym):
    """Return (spot_obj|None, match_type|None).

    1. exact_symbol  : spot_by_sym.get(base_asset + quote_asset)
    2. bstock alias  : only when contract_type == "TRADIFI_PERPETUAL",
                       spot_by_sym.get(base_asset + "B" + quote_asset)
    3. none          : (None, None)
    """
```

`backend/domain/snapshot.py:build_rows` replaces
`spot = spot_by_sym.get(sym)` with `resolve_spot_leg(contract_type,
obj.get("baseAsset",""), "USDT", spot_by_sym)`, threads `match_type` into the
`spot` block, and passes the resolved `spot_symbol` into `classify_route` (so
the existing classifier produces `MARGIN_SPOT_CANDIDATE` for the alias).

The alias fires ONLY for `contract_type == "TRADIFI_PERPETUAL"` so normal crypto
exact-symbol matching is unpolluted. `asset_tag_for` already returns `BSTOCK`
for TRADIFI, so `negative_funding_status` row 2 yields `DISABLED_BSTOCK`
automatically — `classify.py` is untouched.

Data flow (unchanged except the join):

```text
raw (4 endpoints) --resolve_spot_leg--> spot_obj+match_type
   --classify_route(existing)--> route --negative_funding_status(existing)--> status
   --assemble--> snapshot --jsonschema.validate(with match_type)--> serve/cache
```

## Frontend contract (Task B)

- `row.symbol` is the futures symbol (e.g. `TSLAUSDT`); `row.spot.symbol` is
  the actual spot leg (e.g. `TSLABUSDT` for the alias, equal to `row.symbol`
  for normal exact match).
- The 标的 column renders both when `spot.match_type == "bstock_b_suffix_alias"`
  plus a "B 后缀别名" source badge; otherwise the current single-symbol render.
- `frontend/fixture/public-market-snapshot.json` is regenerated to reflect the
  amended classification (bStock rows → MARGIN_SPOT_CANDIDATE + B-suffix spot
  symbol + match_type). It is no longer byte-identical to the contract-v2
  frozen normalized sample (that sample is historical and pre-amendment); this
  is expected and documented. The formal local page still loads from the
  same-origin `/api/public-market/snapshot`.

## Test strategy (Task A, synthetic offline fixture)

New `backend/tests/fixtures/bstock-alias-raw/` (synthetic, no live capture, no
edit to frozen evidence): `fapi-v1-exchangeInfo` (with `TSLAUSDT`
TRADIFI_PERPETUAL), `api-v3-exchangeInfo` (with `TSLABUSDT`,
`isMarginTradingAllowed=true`), `fapi-v1-premiumIndex`, `fapi-v1-fundingRate`.
Tests assert the three `resolve_spot_leg` branches, the TRADIFI-only gating, the
classify regression, and the full `TSLAUSDT` row. The existing offline frozen
fixture path remains the default for the non-bStock regression suite.

## Integration point (Task C)

Offline synthetic-fixture backend run → `GET /api/public-market/snapshot` →
jsonschema validates with `match_type` → assert `TSLAUSDT` row values. No
product code in Task C.

## Review focus

1. Alias must fire only for `TRADIFI_PERPETUAL` (no crypto pollution) — test it.
2. `match_type` must be `null` iff `spot.exists=false` — test the cross-condition.
3. `classify.py` must be unchanged; `DISABLED_BSTOCK` must still win for bStock
   even when route is `MARGIN_SPOT_CANDIDATE` (priority regression).
4. No `float()` on any decimal path; decimal fields stay strings.
5. Contract-v2 frozen samples untouched; only schema + doc amended.
6. No collateral ratio hard-coded; `margin_public.source` stays `"unverified"`.
7. Frontend shows futures-vs-spot symbol distinction only when alias matched.
8. `funding_history` default top-N=20 unchanged.
9. All tests offline; no live HTTP.

本地北京时间: 2026-07-03 23:19:31 CST
下一步模型: Claude-GLM (controller)
下一步任务: Author `11-adr.md`, then build `status.json` and commit `H_intake`.
