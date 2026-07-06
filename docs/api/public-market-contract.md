# Public Market API Contract

Status: contract v0.3 (Private Account v1 amendment, additive). The wire
`schema_version` stays `public-market-snapshot/v1`; every addition is backward-
compatible. v0.2 additions are in "Phase 2 Amendment (v0.2)"; v0.3 additions
(net yield, cost-leg chain, `private_account`, `sort_basis`) are in
"Private Account v1 Amendment (v0.3)" at the end of this file. Binance public
fields verified 2026-07-03 by Claude-GLM against live no-key public calls and
`llms-full.txt`; private fields verified 2026-07-05 by bookkeeper H_intake live
capture (`reports/api-samples/2026-07-private-account-v1/20260705T232800Z/`).
Verified findings are recorded below in "Verified Findings" and in
`reports/agent-runs/2026-07-public-market-contract-v2/api-field-matrix.md`.

Owner: Claude-GLM for field verification and backend implementation. Kimi may
start frontend integration only after this contract and the matching JSON schema
are frozen for the stage.

## Purpose

Define the backend-to-frontend contract for Phase 1 public market discovery.
This contract lets the frontend show Binance USDⓈ-M perpetual funding
opportunities, spot or margin route candidates, bStock tags, and planning inputs
without calling Binance or interpreting Binance-specific fields directly.

## Phase 1 Scope

Allowed:

- Public Binance REST endpoints only.
- Raw request and response capture for documentation and replay.
- Normalized backend snapshot API for frontend consumption.
- JSON schema validation for backend output.

Forbidden:

- API keys.
- Signed endpoints.
- Private account endpoints.
- User data streams.
- Order, borrow, repay, transfer, or websocket execution paths.
- Frontend direct calls to Binance.

## Binance Source Endpoints To Verify

Claude-GLM must verify each endpoint against `llms-full.txt` and a live/public
or locally captured payload before implementation. If an endpoint requires auth,
record it as out of Phase 1 instead of using it.

| Source | Endpoint | Phase 1 Use |
|---|---|---|
| USDⓈ-M Futures | `GET /fapi/v1/exchangeInfo` | Futures symbols, `contractType`, `status`, assets, and futures filters. |
| USDⓈ-M Futures | `GET /fapi/v1/premiumIndex` | Mark price, index price, current funding-rate field, and next funding time. |
| USDⓈ-M Futures | `GET /fapi/v1/fundingRate` | Recent funding history for ranked or sampled symbols. |
| Spot | `GET /api/v3/exchangeInfo` | Spot symbols, `status`, filters, and public spot/margin indicators if present. |
| Margin | `GET /sapi/v1/margin/allPairs` | Candidate cross-margin pair support only if verified as public/no-key or explicitly marked as out of Phase 1. |
| Margin | `GET /sapi/v1/margin/isolated/allPairs` | Historical FMZ isolated-margin comparison only unless the new Portfolio Margin route model explicitly needs it. Verify auth requirements before use. |

## Verified Findings

Frozen 2026-07-03. Evidence: raw public samples under
`reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/` and live
no-key HTTP checks in
`reports/agent-runs/2026-07-public-market-contract-v2/60-test-output.txt`.

Endpoint auth (no API key used):

- `GET /fapi/v1/exchangeInfo`, `/fapi/v1/premiumIndex`, `/fapi/v1/fundingRate`,
  and `GET /api/v3/exchangeInfo` are public/no-key (HTTP 200 without key) and are
  allowed in Phase 1.
- `GET /sapi/v1/margin/allPairs` and `GET /sapi/v1/margin/isolated/allPairs`
  require an API key: without a key they return HTTP 400 with
  `{"code":-2014,"msg":"API-key format invalid."}`. Phase 1 forbids keys, so they
  are not used.

Margin conclusion: because the `sapi` margin pair lists require a key,
`margin_public.source` is `"unverified"` and `public_cross_margin_pair` is `null`
for every row. `MARGIN_SPOT_CANDIDATE` classification uses only the PUBLIC spot
field `isMarginTradingAllowed` from `/api/v3/exchangeInfo`, which is a candidate
signal only. `negative_funding_status` for those rows stays
`PRIVATE_BORROW_VALIDATION_REQUIRED`.

Funding semantics: `nextFundingTime` is the millisecond epoch of the next
scheduled funding settlement (clear). `lastFundingRate` is the real-time
estimate for the CURRENT funding period and is charged at `nextFundingTime`; it
drifts until settlement — mid-period divergence from settled history is evidenced
under `reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/`
(cycle-mid ETHUSDT/SOLUSDT estimate != latest settled record; 15-min drift
observed in-session). Settled history comes from `/fapi/v1/fundingRate`
(`funding_history`); the estimate must not be presented as a settled value.

bStock / TRADIFI: `contractType == "TRADIFI_PERPETUAL"` maps to
`asset_tag = "BSTOCK"`. `contractType == "PERPETUAL"` maps to `CRYPTO`.
`asset_tag` is independent of `route_class`.

Frozen amendment (2026-07-03, stage `2026-07-public-market-bstock-alias-v1`):
Binance added bStocks assets as Margin collateral and opened corresponding
bStocks spot/margin pairs. The TRADIFI futures symbols use the underlying equity
symbol (`TSLAUSDT`, `MSTRUSDT`, `NVDAUSDT`), while the spot/margin bStocks
symbols add a `B` suffix (`TSLABUSDT`, `MSTRBUSDT`, `NVDABUSDT`). The route rule
therefore cannot rely only on exact futures/spot symbol equality. The frozen
spot-leg resolution rule is implemented in
`backend/domain/normalize.py:resolve_spot_leg`:

1. normal crypto: join by exact symbol (`BTCUSDT` -> `BTCUSDT`) ->
   `spot.match_type = "exact_symbol"`;
2. `TRADIFI_PERPETUAL` / `BSTOCK`: first try exact, then try the alias
   `futures.baseAsset + "B" + futures.quoteAsset` (`TSLAUSDT` -> `TSLABUSDT`);
   on alias hit `spot.match_type = "bstock_b_suffix_alias"`. The alias fires ONLY
   for `TRADIFI_PERPETUAL`, so normal crypto exact matching is never polluted;
3. no spot leg found -> `spot.exists = false`, `spot.match_type = null`, route
   `PERP_ONLY_EXCLUDED`.

Consequences (driven entirely by the existing classifier, unchanged this stage):

- if the alias spot pair exists and public `isMarginTradingAllowed=true`, the row
  becomes `MARGIN_SPOT_CANDIDATE` with `positive_funding_enabled=true`, while
  `asset_tag` stays `BSTOCK`;
- bStock negative-funding execution remains disabled: the existing
  `negative_funding_status` priority ranks `asset_tag=BSTOCK` ahead of the
  candidate route, so a bStock row resolves to `DISABLED_BSTOCK` (Binance states
  borrowing is not currently supported for bStocks) even though its candidate
  route is open;
- the bStock collateral ratio is dynamic/unknown in Phase 1; no ratio is
  hard-coded and `margin_public.source` stays `"unverified"`.

The actual spot leg symbol and machine-visible match source are exposed as
`spot.symbol` and `spot.match_type` (see Enums).

Spot min notional: all 3625 observed spot symbols use the new `NOTIONAL` filter
(`minNotional` key); the legacy `MIN_NOTIONAL` filter is 0 observed. The backend
extractor reads `NOTIONAL.minNotional`.

## Required Claude-GLM Outputs

Before backend implementation, Claude-GLM must produce:

- `reports/agent-runs/2026-07-public-market-contract-v2/api-field-matrix.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/api-sample-index.md`
- Raw sample files under
  `reports/api-samples/public-market-contract-v2/<timestamp>/raw/`
- Normalized sample files under
  `reports/api-samples/public-market-contract-v2/<timestamp>/normalized/`
- Updated schema files under `schemas/api/public-market/`

The field matrix must list, for every field used by backend or frontend:

- Source endpoint.
- Raw JSON path.
- Type observed in sample.
- Nullability.
- Semantic meaning.
- Whether the field is safe for frontend display.
- Any ambiguity or required follow-up.

## Backend API

Initial endpoint for Kimi frontend integration:

```text
GET /api/public-market/snapshot
```

Response shape:

```json
{
  "schema_version": "public-market-snapshot/v1",
  "generated_at": "2026-07-03T00:00:00Z",
  "data_time": "2026-07-03T00:00:00Z",
  "source_sample_id": "20260703T000000Z",
  "summary": {
    "total_rows": 0,
    "route_counts": {},
    "asset_tag_counts": {},
    "negative_funding_status_counts": {}
  },
  "rows": [],
  "warnings": []
}
```

Each `rows[]` item must include:

```json
{
  "symbol": "BTCUSDT",
  "base_asset": "BTC",
  "quote_asset": "USDT",
  "asset_tag": "CRYPTO",
  "asset_tag_source": "exchange_or_rule",
  "asset_tag_confidence": "HIGH",
  "route_class": "MARGIN_SPOT_CANDIDATE",
  "positive_funding_enabled": true,
  "negative_funding_status": "PRIVATE_BORROW_VALIDATION_REQUIRED",
  "futures": {
    "symbol": "BTCUSDT",
    "status": "TRADING",
    "contract_type": "PERPETUAL",
    "mark_price": "0",
    "index_price": "0",
    "last_funding_rate": "0",
    "next_funding_time": 0,
    "min_notional": "0",
    "step_size": "0"
  },
  "spot": {
    "symbol": "BTCUSDT",
    "status": "TRADING",
    "exists": true,
    "match_type": "exact_symbol",
    "min_notional": "0",
    "step_size": "0"
  },
  "margin_public": {
    "public_cross_margin_pair": null,
    "source": "unverified"
  },
  "funding_history": [],
  "ui_flags": []
}
```

## Enums

`asset_tag`:

- `CRYPTO`
- `BSTOCK`
- `UNKNOWN`

`asset_tag_confidence`:

- `HIGH`
- `MEDIUM`
- `LOW`

`route_class`:

- `MARGIN_SPOT_CANDIDATE`
- `SPOT_ONLY_CANDIDATE`
- `PERP_ONLY_EXCLUDED`

`negative_funding_status`:

- `PRIVATE_BORROW_VALIDATION_REQUIRED`
- `DISABLED_BSTOCK`
- `DISABLED_SPOT_ONLY`
- `DISABLED_PERP_ONLY`

Priority for `negative_funding_status`:

1. `PERP_ONLY_EXCLUDED` -> `DISABLED_PERP_ONLY`
2. `asset_tag = BSTOCK` -> `DISABLED_BSTOCK`
3. `SPOT_ONLY_CANDIDATE` -> `DISABLED_SPOT_ONLY`
4. `MARGIN_SPOT_CANDIDATE` -> `PRIVATE_BORROW_VALIDATION_REQUIRED`

This priority is unchanged by the bStock alias amendment; BSTOCK stays in
position 2, so a bStock candidate row still resolves to `DISABLED_BSTOCK`.

`spot.match_type` (nullable; `null` when `spot.exists = false`):

- `exact_symbol`
- `bstock_b_suffix_alias`

## Frontend Integration Rules

- Kimi must consume only `GET /api/public-market/snapshot` or matching fixture
  JSON generated from this schema.
- Kimi must not call Binance directly.
- Kimi must not invent route or asset classification logic.
- If a required UI field is absent from the contract, Kimi must mark the
  integration blocked and request a contract update.
- UI copy must keep the agreed Chinese workstation style.

## Open Verification Items

Resolution status as of 2026-07-03 (see "Verified Findings" and
`api-field-matrix.md` for evidence):

- RESOLVED: `GET /sapi/v1/margin/allPairs` requires an API key (HTTP 400 code
  `-2014` without key). Phase 1 does not use it.
- RESOLVED: `GET /sapi/v1/margin/isolated/allPairs` has the same key requirement
  and is treated as historical FMZ/isolated-margin context only. The Portfolio
  Margin route model does not need it in Phase 1.
- RESOLVED: because the margin endpoints require a key, Phase 1 keeps
  `margin_public.source = "unverified"` and does not produce
  `MARGIN_SPOT_CANDIDATE` from the `sapi` lists. It uses only the public spot
  `isMarginTradingAllowed` field.
- RESOLVED (2026-07-04, stage `2026-07-public-market-ui-cn-v1`): `nextFundingTime`
  is clear. `lastFundingRate` is the real-time estimate for the current funding
  period, charged at `nextFundingTime`, drifting until settlement; proven by the
  mid-period divergence evidence under
  `reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/`
  (`verify-funding-semantics.py` PASS). It is not a settled value; settled history
  comes from `/fapi/v1/fundingRate`.
- RESOLVED (amended 2026-07-03, stage `2026-07-public-market-bstock-alias-v1`):
  `TRADIFI_PERPETUAL` symbols are tagged `BSTOCK`, and their spot legs are joined
  via the `baseAsset + "B" + quoteAsset` alias. The positive-funding candidate
  route is open when the alias spot pair has `isMarginTradingAllowed=true`;
  bStock negative funding stays `DISABLED_BSTOCK`. The bStock collateral ratio
  remains dynamic/unknown (not hard-coded).

Remaining (non-blocking, later phase):

- Settle-time sample to remove the `lastFundingRate` ambiguity.
- Private borrowability validation for `MARGIN_SPOT_CANDIDATE`.

## Phase 2 Amendment (v0.2, stage `2026-07-phase2-borrow-sort-v1`)

Frozen 2026-07-04. Response shape extended additively (backward-compatible: the
v0.1 field set and enums are unchanged). Evidence: H_intake discovery under
`reports/api-samples/2026-07-phase2-borrow-sort-v1/20260704T133406Z/`
(`evidence-index.md` + sha256 table + redacted samples); raw-field freeze in
`reports/agent-runs/2026-07-phase2-borrow-sort-v1/10-design.md §2.A`.

### New public row fields

- `funding_interval_hours`: int ∈ {1, 4, 8}. Source `GET /fapi/v1/fundingInfo`
  (public, no key). Symbols listed in the response use their
  `fundingIntervalHours`; unlisted symbols default to 8 (Binance default). Offline
  mode (no frozen fundingInfo sample) -> all symbols 8h.
- `daily_funding_rate`: string (8-place, same format as `last_funding_rate`) or
  null. Computed `Decimal(lastFundingRate) × (24 / interval)` — Decimal-only, no
  float; `quantize(Decimal('1E-8'))`, no scientific notation; negative zero is
  normalized to `0.00000000`. Missing/empty `lastFundingRate` -> null.

### Row order (frozen)

`rows` are returned sorted by `abs(Decimal(daily_funding_rate))` DESC; rows with
null `daily_funding_rate` sort last; ties break by `symbol` ASC. This is a
deterministic total order and IS the payload order. The frontend must not reorder
(filters only hide).

### New private block `borrow_validation` (frontend does not consume this stage)

Three states:

1. private channel disabled or request failed: `verified=false`, all data fields
   null, `error` carries the reason;
2. verified, pair not in the classic list: `verified=true`, `pair_listed=false`,
   asset/interest fields null;
3. verified, pair listed: `verified=true`, `pair_listed=true` + asset/interest.

`checked_at` is the request-success moment (not the data-effective moment). All
numeric fields are strings.

`portfolio_account` is populated only for the bounded candidate set — the top-N
`MARGIN_SPOT_CANDIDATE` + `CRYPTO` baseAssets by abs daily rate (default N=10,
`Config.borrow_check_top_n`). Other rows keep null amount fields (the block is
still present with its `source`). bStock rows are excluded from account-level
probing (`asset_tag != CRYPTO`).

Raw-to-contract field mapping (raw camelCase -> contract snake_case; raw key
names frozen in 10-design §2.A — note E3 keys on `assetName`, E4 on `coin`, not
`asset`):

- `classic_margin.pair_listed` <- `allPairs[].isMarginTrade` (matched by symbol);
- `classic_margin.asset_borrowable` <- `allAssets[].isBorrowable` (key `assetName`);
- `classic_margin.daily_interest_vip0` <- `crossMarginData[].dailyInterest` where
  `vipLevel == 0` (key `coin`); only the VIP0 tier is present in the captured
  account shape;
- `portfolio_account.max_borrowable` <- `maxBorrowable.amount`;
- `portfolio_account.borrow_limit` <- `maxBorrowable.borrowLimit`.

### Snapshot metadata

- `private_channel` (top-level): `"enabled"` | `"disabled"`. `"enabled"` iff the
  private borrow-validation channel returned a classic reference.

### Regression red lines (unchanged)

`negative_funding_status` / `route_class` / `asset_tag` enums and their priority
order, `classify.py`, and `normalize.py` are unchanged. `borrow_validation` is a
parallel output block and never alters classification or route derivation.

## Private Account v1 Amendment (v0.3, stage `2026-07-private-account-v1`)

Frozen 2026-07-06. Wire `schema_version` stays `public-market-snapshot/v1`; every
addition is **additive** (the v0.1 frozen normalized sample and v0.2 snapshots
still validate). Evidence: H_intake live discovery (14/14 calls HTTP 200,
E3/E4/E6 PASS) under
`reports/api-samples/2026-07-private-account-v1/20260705T232800Z/`
(`evidence-index.md` + sha256 table + per-call measured weight headers + capture-
time-redacted samples); frozen field matrix + budget in
`reports/agent-runs/2026-07-private-account-v1/10-design.md §2.A`.
Authority order: `10-design.md` > this contract section.

### Whitelist widened to 12 (deny-by-default, GET-only, single HMAC exit)

`backend/services/private_client.py:WHITELIST` now maps 12 `(GET, exact-path)`
pairs to hardcoded base URLs (anti-injection). Added: E2/E2b/E5 (sapi →
`api.binance.com`), E6 (`/api/v3/account` → `api.binance.com`), E3/E4 (→
`papi.binance.com`), and the discovery-only E1/E1b (registered, **not** called by
snapshot assembly this stage). Any non-whitelisted path or non-GET method raises
in `_require_whitelisted` BEFORE a signature is constructed. `private_client.py`
remains the repo's only HMAC-SHA256 exit (grep-guarded). Two independent TTL
groups (§1.6): the 1h rate-chain/maxBorrowable group and the 60s account-balance
group (E3/E4/E6), aligned with the public refresh cadence. P5
`/api/v3/ticker/price` (full, once) is PUBLIC (no key) and goes through
`binance_public.py`, not the private whitelist.

### New row fields

- `net_daily_yield`: 8-place string | null — opportunity-quality score (§0/§1.1).
  `daily_funding_rate < 0` row: `abs(daily_funding_rate) − daily_borrow_rate`
  (may be negative, output as-is); `daily_borrow_rate` null → null.
  `daily_funding_rate ≥ 0` row: `= daily_funding_rate` (no borrow leg). null
  `daily_funding_rate` → null. Decimal-only, `quantize(1E-8)`, negative-zero →
  `"0.00000000"`.
- `borrow_rate_source`: enum `next_hourly | rate_history | cross_margin_tier |
  vip0_reference` | null. Only negative-funding borrow candidates whose cost-leg
  tier produced a rate carry a value; positive-funding / unavailable rows = null.
- `borrow_validation.classic_margin.daily_interest_account`: 8-place string | null
  — the account-level daily borrow rate (same value as the net-leg borrow rate).

### `sort_basis` + row order (ADR-3 revision, user-approved)

New top-level `sort_basis`: enum `net_daily_yield | abs_daily_funding_rate`.
Snapshot-level single basis:

- private cost leg available (incl. `vip0_reference`) → `net_daily_yield`: rows
  sorted by net value DESC (signed), nulls last, `symbol` ASC tie-break. Lets a
  negative-funding row with cheap borrow rank above a higher-abs-rate row with
  expensive borrow (§3.5 net-reversal core assertion).
- private channel disabled / chain fully broken → `abs_daily_funding_rate`:
  Phase 2 total order (abs daily DESC, nulls last, symbol ASC), regression-pinned.

The frontend remains zero-sort (renders payload order, labels `sort_basis`).

### Cost-leg chain (`borrow_validation` aggregate)

Snapshot-level single tier is selected once (§1.3; no per-row endpoint probing);
per-asset daily rates are looked up from the hit tier's table. Tier order:
① `next_hourly` (E2 `nextHourlyInterestRate × 24`, comma-joined `assets`,
`isIsolated=false` REQUIRED) → ② `rate_history` (E2b latest `dailyInterestRate`,
single-asset probe) → ③ `cross_margin_tier` (crossMarginData row at E5 `vipLevel`)
→ ④ `vip0_reference` (crossMarginData VIP0 row; Phase 2 behavior). All-chain-broken
→ `daily_interest_account=null`, negative-funding `net_daily_yield=null`,
`borrow_rate_source=null`.

The top-level `borrow_validation` aggregate block (distinct from the per-row
`rows[].borrow_validation` — same JSON key, different path/shape) carries:
`coverage` (`{probed, skipped, reason}`), `chain_hit_tier` (1-4|null),
`chain_hit_source` (enum|null), and
`classic_margin_daily_interest_account_available` (bool).

### `coverage` / warnings (§1.5)

Probe range = `daily_funding_rate < 0 ∧ route_class==MARGIN_SPOT_CANDIDATE ∧
asset_tag==CRYPTO`, deduped by `base_asset`, capped at
`Config.borrow_check_max_calls` (default 50, supersedes the Phase 2 N=10);
truncation priority is abs daily rate DESC. Truncated candidates render
`verified=false` / `error="not_probed_this_round"` (no silent truncation).
`borrow_validation.coverage = {probed, skipped, reason="rate_limit_budget"|null}`.
A top-level `warnings` entry is appended when truncation occurs.

### `private_account` block (§1.4, three-state)

Top-level `private_account`: `verified`, `balances_unified` (E3
`totalWalletBalance`), `balances_spot` (E6 `free`/`locked`), `um_positions` (E4
exposure view), `total_value_usdt`, `valuation.{price_source, priced_at}`,
`checked_at`, `error`. Env-missing / both-balance-sources-failed → `verified=false`,
three arrays empty, `total_value_usdt` null, `error` carries the reason; the public
snapshot still renders. A single failed source degrades to an empty array (block
stays `verified=true`).

**Anti-double-count hard rule (test-asserted):** `total_value_usdt = Σ(unified
totalWalletBalance priced) + Σ(spot free+locked priced)`, priced via the P5 price
map (full, fetched once; `futures.*/spot.*` HTTP never fires in the row loop).
`totalWalletBalance` already includes um/cm/crossMargin sub-accounts (never
re-added); `um_positions` nominal value is NEVER counted (exposure view only).
USDT/USDC price at 1; missing price → counted at 0 + warning.

### Decimal discipline + E4 open item (unchanged approach)

All rate/price/amount fields are raw strings (Binance returns strings); no float
touches any value path; `quantize(1E-8)`, no scientific notation. E4 `position_side`
(LONG/SHORT) has no direct papi field — inferred from `positionAmt` sign; to be
re-verified live when a real position appears (R3 upgrade口, 10-design §2.A.3).

### Regression red lines (still unchanged)

`negative_funding_status` / `route_class` / `asset_tag` enums and priority,
`classify.py`, `normalize.py`, and the v0.1/v0.2 field set are unchanged. All v0.3
additions are parallel/additive and never alter classification or route derivation.
