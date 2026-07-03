# Stage Task: 2026-07-public-market-bstock-alias-v1

Authoritative for file boundaries and acceptance in this stage. Authored by the
controller (Claude-GLM) as design record, since Fable5 was unreachable this
session (see `00-intake.md` and `fable5-detail-breakdown.unavailable.md`).
When this file and the user-approved direction synthesis / PRD / amended
contract disagree, the latter are higher authority; surface the conflict, do
not silently pick.

## Goal

Close the impl-v1 post-review P1 finding `bstocks_b_suffix_spot_margin_alias`
by promoting the bStock B-suffix spot/margin alias rule from a descriptive
note into a frozen contract amendment plus a runnable repair:

1. Task A — Claude-GLM amends the contract (`snapshot.schema.json` +
   `public-market-contract.md`) and repairs the backend so TRADIFI/BSTOCK
   futures join their spot leg via `baseAsset + "B" + quoteAsset`, exposing
   `spot.match_type`. Tests added from a synthetic offline fixture.
2. Task B — Kimi updates the frontend so the table distinguishes the futures
   symbol from the actual bStock spot symbol and shows the match source.
3. Task C — controller runs scripted integration verification (no product code).

Acceptance boundary for the stage: Task A and Task B each pass task-level
review-1, plus reproducible integration evidence (Task C), plus one
stage-level review-2.

## Semantic core (why `classify.py` is NOT changed)

The user's 6 amendment points include "bStock positive funding → candidate /
negative funding → still disabled". Once the correct spot symbol is fed into
`classify_route`, this holds automatically via the EXISTING
`negative_funding_status` priority:

- `classify_route(TRADIFI_PERPETUAL, spot_symbol="TSLABUSDT", spot_margin=True)`
  → `MARGIN_SPOT_CANDIDATE` (positive-funding hedge route) ✓
- `positive_funding_enabled = route in (MARGIN_SPOT_CANDIDATE, SPOT_ONLY_CANDIDATE)`
  → `True` ✓
- `negative_funding_status(MARGIN_SPOT_CANDIDATE, BSTOCK)` — priority row 2
  `asset_tag==BSTOCK` → `DISABLED_BSTOCK` (not borrowable; negative funding
  disabled) ✓

**The real fix is the spot-leg join**, not the classifier. `classify.py` stays
unchanged (regression-asserted only).

## Non-goals (forbidden this stage)

- Any signed endpoint, API key, private account endpoint, or user data stream.
- Any order, borrow, repay, transfer, or close-position code path.
- Changing `negative_funding_status` priority order or `classify.py` logic.
- Hard-coding any collateral ratio (bStock collateral stays dynamic/unknown;
  no 100%/90%/etc.). `margin_public.source` stays `"unverified"`.
- Changing `funding_history` default top-N=20.
- Touching `reports/api-samples/public-market-contract-v2/**` (contract-v2
  frozen historical evidence — the curated spot fixture there has no bStock, so
  tests use a synthetic fixture instead).
- Live HTTP this stage (offline synthetic fixture only).
- Deployment, public exposure. Service binds `127.0.0.1` only.

## Ownership and file boundaries

| Path | Owner | Rule |
|---|---|---|
| `backend/**` | Claude-GLM (Task A) | Kimi must not write here. |
| `frontend/**` | Kimi (Task B) | Claude-GLM must not edit its contents. |
| `schemas/api/public-market/snapshot.schema.json` | Claude-GLM (Task A) | **Amendable this stage** (was frozen in impl-v1; the amendment adds `spot.match_type`). |
| `docs/api/public-market-contract.md` | Claude-GLM (Task A) | **Amendable this stage** (upgrade the post-review note to a frozen rule). |
| `reports/api-samples/public-market-contract-v2/**` | frozen historical | Read-only. |
| `reports/agent-runs/2026-07-public-market-bstock-alias-v1/**` | controller | Per-owner report files. |
| `backend/tests/fixtures/bstock-alias-raw/**` | Claude-GLM (Task A) | New synthetic raw fixtures; no live capture. |
| `docs/`, `agents/`, `workflows/`, `scripts/` | untouched this stage | Harness problems go to escalation. |

A boundary crossing is REWORK regardless of code quality.

## Task A — contract amendment + backend repair (Claude-GLM, `senior_developer`)

Scope: `schemas/api/public-market/snapshot.schema.json`,
`docs/api/public-market-contract.md`, `backend/domain/{snapshot,normalize}.py`,
`backend/tests/**`, `backend/tests/fixtures/bstock-alias-raw/**`, plus
`20-implementation-backend.md`.

Deliverables:

- **Schema amendment**: `spot` object gains
  `"match_type": {"type": ["string","null"], "enum": ["exact_symbol", "bstock_b_suffix_alias", null]}`
  (`match_type=null` when `spot.exists=false`; cross-constraint enforced by
  backend logic + tests).
- **Contract doc amendment**: the "Post-review amendment required (2026-07-03)"
  paragraph is upgraded to "Frozen amendment (2026-07-03)" written as a formal
  route rule; `Enums` gets `spot.match_type`; the response-shape `spot` example
  gains `match_type`; `negative_funding_status` priority declared unchanged;
  Open Verification Items updated (bStock alias live, collateral still dynamic).
- **`normalize.py`**: add pure function
  `resolve_spot_leg(contract_type, base_asset, quote_asset, spot_by_sym) ->
  (spot_obj|None, match_type|None)`:
  1. exact `base_asset+quote_asset` → `("exact_symbol")`;
  2. if `contract_type=="TRADIFI_PERPETUAL"`, try `base_asset+"B"+quote_asset`
     → `("bstock_b_suffix_alias")`;
  3. else `(None, None)`. No I/O; unit-tested.
- **`snapshot.py`**: `build_rows` replaces `spot = spot_by_sym.get(sym)` with
  `resolve_spot_leg(...)`; writes `match_type` into the `spot` block; updates
  `CONTRACT_WARNINGS[2]` from the stale "no spot leg" text to "TRADIFI/BSTOCK
  spot leg joined via baseAsset+B+quoteAsset alias; collateral dynamic/unknown".
  `classify_route` / `negative_funding_status` / `funding_history` /
  `margin_public` / decimal discipline / summary aggregation unchanged.
- **Tests**: synthetic `backend/tests/fixtures/bstock-alias-raw/` (futures
  `TSLAUSDT` TRADIFI + spot `TSLABUSDT` `isMarginTradingAllowed=true` +
  premium/funding); `test_normalize.py` (`resolve_spot_leg` 3 branches + TRADIFI
  gating), `test_classify.py` (BSTOCK+MARGIN_SPOT_CANDIDATE→DISABLED_BSTOCK
  regression), `test_snapshot.py` (TSLAUSDT row full assertions),
  `test_negative_schema.py` (new schema). `float()` audit clean.

Acceptance: offline pytest green; served snapshot schema-valid with
`match_type`; `TSLAUSDT` → route `MARGIN_SPOT_CANDIDATE`,
`spot.symbol=TSLABUSDT`, `match_type=bstock_b_suffix_alias`,
`negative_funding_status=DISABLED_BSTOCK`, `positive_funding_enabled=True`;
warnings preserved; no `float()` on decimal paths.

## Task B — frontend display (Kimi, `minimal_change_engineer`)

Scope: `frontend/**` plus `20-implementation-frontend.md`. Depends on Task A
freezing the `match_type` schema field.

Key constraints: in the 标的 column, when `spot.match_type=="bstock_b_suffix_alias"`,
show BOTH the futures symbol (`row.symbol`, e.g. `TSLAUSDT`) and the actual
spot symbol (`row.spot.symbol`, e.g. `TSLABUSDT`) with a "B 后缀别名" source
badge; normal exact match keeps current display. Update `self-check.js` +
`fixture/public-market-snapshot.json` so the bStock rows reflect the new
classification (MARGIN_SPOT_CANDIDATE + spot.symbol with B + match_type). Same-
origin default, no trade/order/account UI, Chinese workstation copy unchanged.
Full dispatch prompt: `task-b-kimi-frontend.prompt.md`.

## Task C — integration verification (controller, no product code)

Scope: `60-test-output.txt` Section 4 + timestamped integration snapshot +
`20-implementation.md`. Offline synthetic-fixture backend run → jsonschema
validates (with `match_type`) → assert the `TSLAUSDT` row's
route/spot/match_type/negative_funding_status. Reproducible; no product code.

## Fingerprint protocol (unchanged)

Single standard protocol; two scopes (task-level, stage-level):

```text
diff_fingerprint = head_sha + ":" + sha256(git diff --binary <base_sha>..<head_sha> -- . ":(exclude)reports/agent-runs/<stage-id>/status.json")
```

Task-level A/B/C each record their own `base_sha`/`head_sha`/`diff_fingerprint`
in `status.json.tasks.<id>`. Stage-level top-level triple covers the whole
stage diff and binds review-2 + pre-accept. `status.json` excluded from hash.
Controller commits serially (`H_intake` → `H_A` → `H_B` → `H_C`) to keep each
task's diff owner-scoped.

本地北京时间: 2026-07-03 23:19:31 CST
下一步模型: Claude-GLM (controller)
下一步任务: Author `10-design.md` + `11-adr.md`, then build `status.json` and commit `H_intake`.
