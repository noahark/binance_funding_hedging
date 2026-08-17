# Public Market API Contract

Status: contract v0.17 as-built (repay amendment added 2026-08-10). The wire
`schema_version` stays `public-market-snapshot/v1`; every addition remains
backward-compatible. "Read-only" no longer describes the whole surface: since
v0.10 this document also covers write routes
(`POST /api/public-market/cache-refresh`, `POST /api/private-ledger/refresh`,
and the money-moving `POST /api/asset-transfer` and gated `POST /api/margin-repay`);
the snapshot/positions GET routes themselves stay pure reads.
The `GET /api/public-market/snapshot` route and `public-market-snapshot/v1`
wire version are historical compatibility names. The payload now represents a
public market snapshot plus optional private read-only enrichment. A route rename
or schema-version bump is a future contract stage, not part of this status sync.

v0.2 additions are in "Phase 2 Amendment (v0.2)"; v0.3 additions (net yield,
cost-leg chain, `private_account`, `sort_basis`) are in "Private Account v1
Amendment (v0.3)"; v0.4 through v0.6 UI/value-display, metal-tag, and
borrowability refinements are in later amendments; v0.7 additive
`opening_quotes` and v0.8 additive `cross_margin_borrowed_value_usdt` are in the
amendments at the end of this file. v0.9 through v0.12 (collateral-cap display,
cache-refresh/`source_checked_at` with the first write route, positions
dual-account balances, dual-ledger flow-log) and v0.13 through v0.16 (asset
transfer, spot-leg identity table, account source availability, max-withdraw)
are likewise in the amendments at the end of this file, as is v0.17 (margin
repay, gated and default-off).
Binance public fields verified
2026-07-03 by Claude-GLM against live no-key public calls and `llms-full.txt`;
private fields verified 2026-07-05 by bookkeeper H_intake live capture
(`reports/api-samples/2026-07-private-account-v1/20260705T232800Z/`). Verified
findings are recorded below in "Verified Findings" and in
`reports/agent-runs/2026-07-public-market-contract-v2/api-field-matrix.md`.

Owner: Claude-GLM for field verification and backend implementation. Kimi may
start frontend integration only after this contract and the matching JSON schema
are frozen for the stage.

## Purpose

Define the backend-to-frontend contract for the read-only funding snapshot.
This contract lets the frontend show Binance USDⓈ-M perpetual funding
opportunities, spot or margin route candidates, bStock and metal tags, optional
private account/borrow enrichment, and planning inputs without calling Binance
or interpreting Binance-specific fields directly.

## Initial Public Baseline Scope

This section records the initial public-only baseline. Later additive sections
extend the same wire contract with optional private read-only fields.

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
  `{"code":-2014,"msg":"API-key format invalid."}`. They require a key, so they
  are not used this round (see the three key-use gates below, not the retired
  blanket "Phase 1 forbids keys").

Key-use gates (replace the retired blanket "Phase 1 forbids keys" — decision
§B-2 / §7.1). Removing the ban without a rule would let scope creep silently; the
ban is replaced by three gates:

1. Keyed endpoints are permitted on the BACKEND only; the browser still never
   calls Binance directly.
2. The DEFAULT class is `MARKET_DATA` — keyed but unsigned, platform-level, no
   account binding. This preserves the invariant that the public snapshot never
   carries account data. A signed `USER_DATA` endpoint (e.g. account-level
   `margin/available-inventory`) is a different class and needs separate Human
   authorization.
3. Each new keyed data source needs explicit Human authorization recorded in its
   stage. This round authorizes exactly one: `restricted-asset` (v0.9 amendment).

Margin conclusion: because the `sapi` margin pair lists require a key, and this
round does NOT adopt `allPairs`/`allAssets`, `margin_public.source` is
`"unverified"` and `public_cross_margin_pair` is `null` for every row — the cause
is "not adopted this round", not "forbidden" (the key-use gates now permit the
backend to use keyed MARKET_DATA sources). `MARGIN_SPOT_CANDIDATE`
classification uses only the PUBLIC spot field `isMarginTradingAllowed` from
`/api/v3/exchangeInfo`, which is a candidate signal only. `negative_funding_status`
for those rows stays `PRIVATE_BORROW_VALIDATION_REQUIRED`.

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

METAL (frozen 2026-07-08, stage `2026-07-ui-filter-balance-metal-v1`): a
real-metal `baseAsset` ∈ {`XAU`, `XAG`, `COPPER`, `XPT`, `XPD`} maps to
`asset_tag = "METAL"` with `asset_tag_source = "base_asset_metal_symbol"`,
`asset_tag_confidence = "HIGH"`. The metal check runs BEFORE the
`TRADIFI_PERPETUAL -> BSTOCK` mapping in `asset_tag_for`, so a metal that ships
as `contractType = "TRADIFI_PERPETUAL"` (XAUUSDT/XAGUSDT/XPTUSDT/XPDUSDT/
COPPERUSDT all do — evidence:
`reports/api-samples/2026-07-ui-filter-balance-metal-v1/20260708T0928Z/normalized/metal-symbol-summary.json`)
is tagged `METAL`, never `BSTOCK`. `METAL` is a product tag, NOT a borrow
prohibition: there is no `DISABLED_METAL`, and a `METAL` row with a margin spot
leg and a negative daily rate falls through the `negative_funding_status`
priority chain to `PRIVATE_BORROW_VALIDATION_REQUIRED` (like `CRYPTO`). In the
current public sample none of the five metals has a public exact or B-suffix
spot leg, so they resolve `PERP_ONLY_EXCLUDED` / `DISABLED_PERP_ONLY`;
borrowability and borrow cost for a candidate METAL row come from the private
read-only API, not from the asset tag.

Frozen amendment (2026-07-03, stage `2026-07-public-market-bstock-alias-v1`):
Binance added bStocks assets as Margin collateral and opened corresponding
bStocks spot/margin pairs. The TRADIFI futures symbols use the underlying equity
symbol (`TSLAUSDT`, `MSTRUSDT`, `NVDAUSDT`), while the spot/margin bStocks
symbols add a `B` suffix (`TSLABUSDT`, `MSTRBUSDT`, `NVDABUSDT`). The route rule
therefore cannot rely only on exact futures/spot symbol equality. The frozen
spot-leg resolution rule is implemented in
`backend/domain/normalize.py:resolve_spot_leg`:

A spot record resolves ONLY when its `status == "TRADING"`. `BREAK`, `HALT`, a
missing `status`, and any other non-`TRADING` value do NOT form a usable spot leg
(frozen evidence: `reports/api-samples/2026-07-tradable-spot-leg-v1/20260718T042314Z/`
— AERGOUSDT/XMRUSDT/LITUSDT remain in spot `exchangeInfo` with `status="BREAK"`
and a zero bookTicker while their perpetuals quote normally). `spot.exists`
therefore means a currently tradable resolved spot leg, not merely that Binance
retains a historical/non-trading exchangeInfo record. For `TRADIFI_PERPETUAL`, a
non-trading exact record is skipped before trying the alias, and the alias
resolves only when it is itself `TRADING`:

1. normal crypto: join by exact symbol (`BTCUSDT` -> `BTCUSDT`), tradable only
   (`status == "TRADING"`) -> `spot.match_type = "exact_symbol"`;
2. `TRADIFI_PERPETUAL` / `BSTOCK`: first try exact (must be `TRADING`), then try
   the alias `futures.baseAsset + "B" + futures.quoteAsset` (`TSLAUSDT` ->
   `TSLABUSDT`), which must also be `TRADING`; on alias hit
   `spot.match_type = "bstock_b_suffix_alias"`. The alias fires ONLY for
   `TRADIFI_PERPETUAL`, so normal crypto exact matching is never polluted;
3. no tradable spot leg found (absent symbol, or any non-`TRADING` status such as
   `BREAK`/`HALT`) -> `spot.exists = false`, `spot.match_type = null`, route
   `PERP_ONLY_EXCLUDED`.

> SUPERSEDED 2026-08-08 by the Spot-Leg Identity Amendment (v0.14, end of this
> file): the rule-2 string-constructed alias no longer exists; resolution is
> exact -> explicit `SPOT_SYMBOL_MAP` -> `(None, None)`. This passage stays as
> history.

Consequences (driven entirely by the existing classifier, unchanged this stage):

- if the alias spot pair exists and public `isMarginTradingAllowed=true`, the row
  becomes `MARGIN_SPOT_CANDIDATE` with `positive_funding_enabled=true`, while
  `asset_tag` stays `BSTOCK`;
- bStock negative-funding execution remains disabled: the existing
  `negative_funding_status` priority ranks `asset_tag=BSTOCK` ahead of the
  candidate route, so a bStock row resolves to `DISABLED_BSTOCK` (Binance states
  borrowing is not currently supported for bStocks) even though its candidate
  route is open;
- the bStock collateral ratio is dynamic/unknown; no ratio is hard-coded and
  `margin_public.source` stays `"unverified"` (cause: not adopted this round, not
  forbidden — see the key-use gates above).

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

The public-market backend exposes three same-origin, read-only JSON endpoints
(no CORS; the frontend never calls Binance). All reuse the canonical published
state; `GET /healthz` (liveness) and `GET /readyz` (readiness) are separate
health endpoints. Success (HTTP 200) responses carry `Cache-Control: no-store`;
503 covers the brief pre-first-publication cold-start window for each route.
(Later amendments extend this surface beyond these three read-only endpoints —
v0.10 adds the first write route, v0.11 the positions endpoint, v0.12 the
private-ledger routes, v0.13 the money-moving asset transfer, v0.16 the
max-withdraw read, v0.17 the gated money-moving margin repay; v0.19 adds the
read-only public-egress IP display. This paragraph
stays as the original baseline.)

### GET /api/public-market/snapshot

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

### GET /api/public-market/funding-history

Same-origin, public read-only settled-history view for ONE eligible snapshot
symbol. The browser never calls Binance; the backend reuses the snapshot
`data_time` boundary and a per-symbol 30-minute successful-result cache. It
carries settled 7D/30D annualization only; it does NOT return the current-period
24h estimate (the selected snapshot row stays authoritative for that).

- Method / path: `GET /api/public-market/funding-history`.
- Input: query param `symbol` (required). A blank/missing value (`?symbol=` or
  no param) is treated as missing and the service returns HTTP 400
  `invalid_symbol`.
- Success (200): body validates against
  `schemas/api/public-market/funding-history.schema.json`
  (`schema_version` = `public-market-funding-history/v1`).
- Body fields (per schema, no others):
  - `schema_version`: `public-market-funding-history/v1` (const).
  - `symbol`: the requested symbol.
  - `data_time`: the shared snapshot time boundary (date-time).
  - `history_status`: `available` | `empty`.
  - `funding_history`: newest-first settled records inside the inclusive 30-day
    window ending at `data_time`; each item `{funding_time (ms int ≥0),
    funding_rate (decimal string)}`. This payload is a **pure projection of the
    already-published snapshot row**: the endpoint issues no upstream fetch for
    this request — it reads `funding_history` straight from the published state
    and sets `history_status` to `empty` whenever that list has no entries.
    `empty` therefore means only "no settled records in the published row"; it
    **does not prove** that this request (or any prior fetch) succeeded. A symbol
    whose row was published but never prewarmed, or whose earlier history fetch
    failed, still projects as `empty` here with no on-demand retry.
  - `annualized_funding_7d`: settled 7-day calendar-window funding-rate sum ×
    (365 / 7), or `null` for an empty window.
  - `annualized_funding_30d`: settled 30-day calendar-window funding-rate sum ×
    (365 / 30), or `null` for an empty window.
- There is deliberately NO `annualized_funding_24h` on this payload: the 24h
  estimate is a current-period figure that lives on the snapshot row, not here.

Schema: `schemas/api/public-market/funding-history.schema.json`.

### GET /api/public-market/symbol-snapshot

One-shot selected-symbol row view. The path taken depends on how the server is
running, and the `row` source is mode-dependent: live responses project from
the latest internal `PublishedState` (last-good), offline responses project
from the synchronously built / cached snapshot (no `PublishedState` is
involved). In neither mode does the row necessarily come from a publication
created by this request:

- Live with the background worker running: the service submits one
  `RefreshSymbolCommand` to its serial worker and waits within a bounded
  timeout, then projects the selected row from the latest published state. A new
  publication is produced only if the command settles in-window with no
  assembly/validation failure; otherwise the row is the previously published
  (last-good) state.
- Live with no worker running: no command is submitted; the service projects the
  selected row from the latest published (last-good) state and returns
  `refresh_status: timeout`.
- Live before the first publication exists: the endpoint returns HTTP 503
  `snapshot_not_ready` before submitting any command — there is no 200
  cold-start response on this endpoint.
- Offline: no worker and no command; the service projects the synchronously
  built / cached row directly (`published_version: 0`, `refresh_status: ok`).

`published_version` is mode-dependent — it is NOT a version carried by the full
snapshot:

- Live (with or without a worker): the revision number of the internal
  `PublishedState` this `row` was projected from.
- Offline: a fixed `0` sentinel by convention. Offline mode never creates a
  `PublishedState` (the row is projected from the synchronously built / cached
  snapshot), so offline `0` is NOT the revision number of any `PublishedState`.

The full snapshot v1 wire payload (`snapshot.schema.json`) has no
`published_version` field at all, so there is no client-verifiable equality
between this value and anything in a `/api/public-market/snapshot` response;
two independent HTTP reads may also straddle a later publication, so there is no
atomic cross-request same-version guarantee. What IS preserved (live mode only):
this `row` is selected from the same internal `PublishedState.snapshot` a
`/snapshot` read projects from, so within a single read the row is identical in
shape and content to the matching element of `snapshot.rows[]`. This payload
NEVER contains a `rows` array.

- Method / path: `GET /api/public-market/symbol-snapshot`.
- Input: query param `symbol` (required). A blank/missing value is treated as
  missing and the service returns HTTP 400 `invalid_symbol`.
- Success (200): body validates against
  `schemas/api/public-market/symbol-snapshot.schema.json`
  (`schema_version` = `public-market-symbol-snapshot/v1`).
- Body fields (per schema, no others):
  - `schema_version`: `public-market-symbol-snapshot/v1` (const).
  - `symbol`: the requested symbol.
  - `published_version`: integer ≥0. Live mode: the revision number of the
    internal `PublishedState` this `row` was projected from. Offline mode: the
    fixed `0` sentinel — no `PublishedState` exists or is created offline. The
    full snapshot v1 wire payload exposes no comparable field, so this is NOT
    verifiable against a `/api/public-market/snapshot` response and gives no
    cross-request equality guarantee (see the mode note above).
  - `data_time`, `generated_at`: date-times.
  - `refresh_status`: `ok` | `partial` | `timeout`. It reflects what happened on
    this request's refresh attempt (if any); regardless of status, the projected
    `row` comes from the mode's row source above (live: latest published state;
    offline: the synchronously built / cached snapshot), and is not proof that a
    new publication was created by this request.
    - `ok`: either offline (the synchronously-built row, `published_version: 0`,
      no command), or a live worker command that completed a publication with no
      per-source `warnings`.
    - `partial`: a live worker command completed a publication but at least one
      source emitted a `warnings` entry — e.g. `premium_refresh_failed:<symbol>`,
      `funding_history_unavailable:<symbol>`, `borrow_rate_refresh_failed:<asset>`,
      or `max_borrowable_refresh_failed:<asset>`. `partial` does NOT imply that
      the public/history figures are fresh; read `warnings` for the actual failed
      source(s).
    - `timeout`: this request produced no new publication; the (live) row is
      the previously published (last-good) state. The contract deliberately
      does not enumerate the possible causes: `warnings` may carry a diagnostic
      reason string or none at all — internal failure reasons are recorded only
      in a server-internal `cmd.error` that is NOT exposed on the response.
      `timeout` therefore does not prove that only a deadline expired.
  - `warnings`: array of diagnostic reason strings actually serialized for this
    response. The vocabulary is open-ended and NON-exhaustive: clients must not
    assume completeness and must not branch on undocumented values; a `timeout`
    may carry no warning at all. `refresh_status` remains the authoritative
    outcome field. Non-normative examples seen in practice: the per-source
    tokens above (which can also accompany a `timeout` when a command fails
    after collecting them), `refresh_deadline_exceeded`,
    `refresh_command_expired:<symbol>`, and `worker_not_running`.
  - `row`: a single element from the mode's row source above (live: the latest
    `PublishedState.snapshot`; offline: the synchronously built / cached
    snapshot), identical in shape to a `snapshot.rows[]` element (see
    `snapshot.schema.json#/$defs/row`, incl. `opening_quotes` and the annualized
    funding fields below). There is never a `rows` array on this payload.

Schema: `schemas/api/public-market/symbol-snapshot.schema.json`.

### Annualized funding fields (row-level, as-built)

`snapshot.rows[]` carries three additive, optional annualization fields (already
in `snapshot.schema.json`; a legacy row may omit them and still validate). They
are decimal strings or `null`; `float` never touches a value path.

- `annualized_funding_24h`: **estimate-derived** —
  `daily_funding_rate × 365`, or `null` when `daily_funding_rate` is `null`.
  Settled history never mixes in; this is the current-period 24h figure.
- `annualized_funding_7d`: **settled** — 7-day calendar-window funding-rate sum
  × (365 / 7), or `null` for an empty window. The current-period estimate /
  `lastFundingRate` never mixes in.
- `annualized_funding_30d`: **settled** — 30-day calendar-window funding-rate
  sum × (365 / 30), or `null` for an empty window.

The settled 7D/30D figures are also returned (those two only, never 24h) on the
`GET /api/public-market/funding-history` payload; the current-period 24h
estimate is exclusive to the snapshot row. This estimate-vs-settled split mirrors
the `lastFundingRate` vs `funding_history` discipline (see Verified Findings).

## Enums

`asset_tag`:

- `CRYPTO`
- `BSTOCK`
- `METAL`
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
There is no `DISABLED_METAL`: `METAL` is not a borrow prohibition, so a `METAL`
candidate row falls through to position 4 (`PRIVATE_BORROW_VALIDATION_REQUIRED`).

`spot.match_type` (nullable; `null` when `spot.exists = false`):

- `exact_symbol`
- `bstock_b_suffix_alias`

> SUPERSEDED 2026-08-08 by v0.14 (end of this file): the enum gained
> `multiplier_strip_alias`, and the values now come from the explicit
> `SPOT_SYMBOL_MAP`, not from any constructed-alias rule.

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
addition is **additive** (the v0.1 frozen normalized sample and v0.2/v0.3 snapshots
still validate). Evidence: H_intake live discovery (14/14 calls HTTP 200,
E3/E4/E6 PASS) under
`reports/api-samples/2026-07-private-account-v1/20260705T232800Z/`
(`evidence-index.md` + sha256 table + per-call measured weight headers + capture-
time-redacted samples); frozen field matrix + budget in
`reports/agent-runs/2026-07-private-account-v1/10-design.md §2.A`.
Authority order: `10-design.md` > this contract section.

### Whitelist (deny-by-default, GET-only, single HMAC exit)

`backend/services/private_client.py:WHITELIST` maps `(GET, exact-path)` pairs
to hardcoded base URLs (anti-injection); that dict is the sole live authority
for the entry list and its count — 16 entries as of 2026-08-08 (added after
this amendment froze at 12: E3b `/papi/v1/account`, the two v0.12 flow-log
sources, and the v0.16 `/papi/v1/margin/maxWithdraw`; do not restate the
number anywhere else). This
amendment added: E2/E2b/E5 (sapi →
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
asset_tag ∈ {CRYPTO, METAL}` (METAL included from stage
`2026-07-ui-filter-balance-metal-v1`; `BSTOCK` stays excluded), deduped by
`base_asset`. The pool is split into two
independent budgets (borrow-cost-coverage-v2):

- **Rate coverage** (`rate_probe_assets`, the FULL pool, NOT capped) drives the
  next-hourly interest-rate lookup. A candidate beyond the borrowability cap
  still gets its borrow rate (no `-`).
- **Borrowability coverage** (`borrowability_probe_assets`, the first
  `Config.borrow_check_max_calls` candidates by abs daily rate DESC) drives the
  per-asset `maxBorrowable` probe.

`borrow_validation.coverage = {probed, skipped, reason="rate_limit_budget"|null}`
reports the **borrowability** coverage (`probed` = borrowability-probed,
`skipped` = borrowability-unprobed). When `skipped > 0`, a top-level `warnings`
entry is appended ("部分资产可借额度未探测（利率仍覆盖）" /
"N asset(s) borrowability not probed (rate still covered)") — rate coverage is
unaffected.

`error` on per-row `borrow_validation`:

- `borrowability_not_probed`: borrowability not probed (beyond the
  `maxBorrowable` budget), but `classic_margin.daily_interest_account` and
  `net_daily_yield` are STILL filled; only the `portfolio_account` amount fields
  are null; `checked_at` is kept; `verified=false`.
- `not_probed_this_round` (legacy): rate also not covered; all chain fields null.

### `private_account` block (§1.4, three-state)

Top-level `private_account`: `verified`, `balances_unified` (E3
`totalWalletBalance` + additive `cross_margin_borrowed`/`cross_margin_free`/
`cross_margin_locked`), `balances_spot` (E6 `free`/`locked`), `um_positions` (E4
exposure view), `total_value_usdt`, `valuation.{price_source, priced_at}`,
`checked_at`, `error`. Env-missing / both-balance-sources-failed → `verified=false`,
three arrays empty, `total_value_usdt` null, `error` carries the reason; the public
snapshot still renders. A single failed source degrades to an empty array (block
stays `verified=true`).

Each `balances_unified[]` item carries additive **`cross_margin_borrowed`**
(raw decimal string | null): Portfolio Margin full-cross margin liability from
`GET /papi/v1/balance` field `crossMarginBorrowed`. Display-only; never counted
into `total_value_usdt` (liability is not an asset). Frontend balance cards show
`已借: <amount>` and highlight in red when the amount is strictly greater than
zero (2026-07-22 ops patch). A positive-borrow card also shows a frontend-only
repay amount input (`0 自动还所有`) and a repay button. Until a backend repay
contract is delivered, clicking it only reports that the backend is not connected
and must not issue a request. The unified-card net-value line uses the danger
color only when the computed net value is below zero; zero and positive values
use the normal secondary text color.

Each item also carries additive **`cross_margin_free`** (raw decimal string |
null): the unencumbered full-cross balance from `GET /papi/v1/balance` field
`crossMarginFree` — the same field the hedge preflight and the live executor
already read to size what the unified account can actually move. Additive and
optional: frozen pre-2026-08 samples omit the key (absent ≠ zero). Display-only,
never counted into `total_value_usdt` (which takes the unified side from
`actual_equity_usdt`, not from per-asset balance rows). **It is an availability
figure, not a max-transferable quote:** a
transfer out of the unified account must additionally clear the account's
uniMMR / collateral constraints, so the exchange may reject an amount that fits
within `cross_margin_free`. Sizing a real transfer must be validated
server-side, never from this cached display value alone.

Each item also carries additive **`cross_margin_locked`** (raw decimal string |
null), projected from `GET /papi/v1/balance` field `crossMarginLocked`. It is the
full-cross quantity currently locked (for example, by a pending sell), distinct
from `cross_margin_free`, `cross_margin_borrowed`, and `cross_margin_interest`.
The field is optional for compatibility with frozen
older samples; current snapshots emit it on every unified row and use null when
the upstream key is absent. It is display/validation-only and never changes
valuation, ordering, totals, warnings, refresh, or transport behavior.

### Outstanding interest amendment (2026-08-16)

Each `balances_unified[]` item carries additive **`cross_margin_interest`** (raw
decimal string | null), projected from `GET /papi/v1/balance` field
`crossMarginInterest`, plus backend-computed
**`cross_margin_interest_value_usdt`** (8dp string | null) using the same
amount→USDT routing as `cross_margin_borrowed_value_usdt` (stable assets at 1,
price map otherwise; null/blank/zero amount → `"0.00000000"`; invalid amount or
non-zero amount without a usable price → null).

`cross_margin_interest` is **interest accrued and not yet repaid** — a live
liability that sits *beside* the `cross_margin_borrowed` principal, not inside
it. It is the only field in the system that answers "how much interest is owed
right now": it decreases on repayment and reaches zero when the debt is settled.

**Never cross-validate it against the interest-history ledger.** The flow-log
ledger (`/sapi/v1/margin/interestHistory` → `interest_rows`) answers a different
question — how much interest was ever *charged* over a window — and keeps
already-repaid interest in the sum. After any interest repayment
`Σ history > cross_margin_interest` necessarily holds; treating a divergence as
a defect is a category error (dual-ledger flow-log design, §108).

Both keys are additive/optional: frozen pre-2026-08-16 samples omit them (absent
≠ zero) and still validate. Neither enters `total_value_usdt`, and this
amendment changes no classification, ordering, refresh, or transport behavior.
The unified card renders `利息: <amount> ≈ <value> USDT` under the `已借` line
when the amount is strictly greater than zero; zero and absent render nothing
(a zero interest row carries no information and must not be drawn as `0`).

**Debt now includes outstanding interest.** `pm_account.total_debt_usdt` is
`Σ((crossMarginBorrowed + crossMarginInterest) priced)`, the unified card's
net-value line subtracts both, and the small-balance filter keeps a card whose
`cross_margin_interest > 0` even when the principal has been fully repaid (an
interest-only debt must never be hidden together with its repay entry).

The two amounts do **not** overlap, verified against live account data on
2026-08-16: `crossMarginBorrowed` absorbs only the interest that had already
accrued at the moment of a *past* repayment, while `crossMarginInterest` carries
what accrued since. Evidence — SNX borrowed 100, repaid 50 at
`2026-08-16T00:55:31Z`; interest accrued strictly before that instant summed to
`0.10709571`, which equals `crossMarginBorrowed (50.10709571) − principal (50)`
to all 8 decimal places, and the 11 hourly accruals after it
(`0.01026885`) were reported separately under `crossMarginInterest`. Summing
both therefore counts each debt exactly once.

Net-value three-state (frontend `unifiedNetValueLine`): key absent (frozen
pre-2026-08-16 samples) → net stays on the old principal-only formula; explicit
null (non-zero interest with no usable price) → net renders `≈ — USDT`, never
silently dropping an unpriceable liability to zero.

### Total composition (v0.x additive amendment, 2026-08-17)

**Hard rule (test-asserted):** `total_value_usdt` is a **partial sum over the
account sources that read this round**:

```text
total_value_usdt = spot_value_usdt + pm_account.actual_equity_usdt
```

Priced via the P5 price map (full, fetched once; `futures.*/spot.*` HTTP never
fires in the row loop). `um_positions` nominal value is NEVER counted (exposure
view only). USDT/USDC price at 1; missing price → counted at 0 + warning.

**A source that did not read contributes nothing, and there is NO fallback to
another basis.** Substituting either neighbour would report a number on a
different accounting basis while the label claims otherwise — the false-claim
shape fixed on 2026-08-07:

- `accountEquity` is collateral-discounted — measured ~4% below `actualEquity`
  on 2026-08-16.
- `unified_wallet_value_usdt` is a per-asset wallet sum, **not** net worth, and
  the gap is neither small nor of a fixed sign: measured 2026-08-17, gross
  `100.68845086` against net worth `191.41755452`. The pre-2026-08-17 fallback
  would therefore have *understated* the total by ~90 USDT — reading on screen
  as a loss that never happened.

The frontend renders the incomplete total red and names the missing side; the
unified net-worth card renders `—`.

Detection differs per side because the data shapes differ: the unified side is a
single value, so `actual_equity_usdt === null` alone distinguishes "did not
read" (and covers an upstream field rename too); the spot side is a sum where
`0` is indistinguishable from a genuinely empty account, so it is detected via
`unavailable_sources` containing `spot_balances`.

`unified_wallet_value_usdt` remains `Σ(unified totalWalletBalance priced)` as its
own field and does **not** enter `total_value_usdt`.

⚠️ **`totalWalletBalance` does NOT cover the um/cm sub-accounts** — settled
2026-08-17, overturning a long-standing claim in this document. Proof by
contradiction from one live snapshot, no new endpoint needed:

```text
wallet gross  Σ(totalWalletBalance priced)   100.82
unified debt  total_debt_usdt                 52.48
gross − debt                                  48.34   ← should ≈ net worth
actual net worth  actualEquity               187.97
shortfall                                    139.63
```

Net worth exceeds `gross − debt` by `139.63`. Equity cannot exceed the assets it
is computed from, so the wallet sum must be missing that value — the margin and
unrealised PnL sitting in the futures sub-accounts (9 UM positions open at the
time of measurement). The per-asset rows confirm it: every non-zero row was a
plainly held asset (USDT/BNB/1000CAT/SNX/WLD/AVNT), none of it futures margin.

**Consequences.** Nothing in the current contract depends on this — the field
feeds no total since the basis change below. But it means the field is a
*partial* wallet view, not "everything in the unified account": do not use it for
reconciliation, position cost, or any "how much is in there" question without
adding the futures wallets. This also quantifies why the pre-2026-08-17 fallback
was removed: falling back to gross understated the total by a three-digit USDT
amount, which read on screen as a loss that never happened.

⚠️ **Basis change, 2026-08-17.** Before this date the unified side used
`accountEquity` and fell back to wallet gross when the account endpoint was
unavailable. Totals recorded earlier are not comparable across this date. On the
measurement that triggered the change: `total_value_usdt` `571.13` → `579.64`
(+`8.51`), `pm_account` unified net worth `185.91` → `194.42`, `leverage_ratio`
`3.07207789` → `2.98142928`.

### PM account equity fields

- `pm_account.actual_equity_usdt` — papi `actualEquity`, unified account **net
  worth**, the figure the Binance App shows. It is the unified side of
  `total_value_usdt` and the divisor of `leverage_ratio`. Null = the source did
  not read; consumers degrade to an explicit unknown, never to another basis.
- `pm_account.account_equity_usdt` — papi `accountEquity`, the
  collateral-discounted risk figure. Carried for its own sake; never a net-worth
  substitute, never inside `total_value_usdt`. Do not assume a fixed ordering
  between the two: live data has `accountEquity` lower, but that is a property of
  the current collateral mix, not a contract.
- `pm_account.leverage_ratio` — `total_value_usdt / actual_equity_usdt`, but only
  when the total is **complete**. Null whenever the spot source did not read or
  `actual_equity_usdt` is absent, **even though both operands are then positive**:
  with spot gone the numerator degenerates to the net worth itself and the ratio
  reads a tidy `1.00`, which is indistinguishable from a genuinely unleveraged
  account. A `spot_balances` fetch that returned a genuinely empty array is NOT
  missing — that yields a real `1.00`. Numerator and divisor share one equity
  source so the on-screen division stays self-consistent.
  ⚠️ Do not "fix" this back to a plain both-positive check: that reinstates the
  false `1.00×` removed on 2026-08-17.

### Decimal discipline + E4 open item (unchanged approach)

All rate/price/amount fields are raw strings (Binance returns strings); no float
touches any value path; `quantize(1E-8)`, no scientific notation. E4 `position_side`
(LONG/SHORT) has no direct papi field — inferred from `positionAmt` sign; to be
re-verified live when a real position appears (R3 upgrade口, 10-design §2.A.3).

### Regression red lines (still unchanged)

`negative_funding_status` / `route_class` / `asset_tag` enums and priority,
`classify.py`, `normalize.py`, and the v0.1/v0.2 field set are unchanged. All v0.3
additions are parallel/additive and never alter classification or route derivation.

## Private Account UI Polish Amendment (v0.4, stage `2026-07-private-account-ui-polish-v1`)

Frozen 2026-07-07. Wire `schema_version` stays `public-market-snapshot/v1`; every
addition is **additive** (the v0.1 frozen normalized sample and v0.2/v0.3 snapshots
still validate). Evidence: current-stage raw public sample under
`reports/api-samples/2026-07-private-account-ui-polish-v1/` (no-key
`GET /api/v3/ticker/price` + `evidence-index.md`); prior v0.3 evidence under
`reports/api-samples/2026-07-private-account-v1/20260705T232800Z/`.
Authority order: `10-design.md` > this contract section.

### New per-balance valuation fields

- `private_account.balances_unified[].value_usdt`: 8-place decimal string | null.
  Backend-computed USDT value of `total_balance` using the same P5
  `/api/v3/ticker/price` map as `total_value_usdt`. Stable USD assets use price
  1. `null` means valuation is unavailable because amount or price is missing or
  invalid; `"0.00000000"` means a valid priced zero value.
- `private_account.balances_spot[].value_usdt`: 8-place decimal string | null.
  Backend-computed USDT value of `free + locked` using the same valuation rules.
- `private_account.um_positions[]` remains an exposure view. It does not carry
  `value_usdt` and its notional value is never included in `total_value_usdt`.

The frontend renders `value_usdt` as display-only data and must not recompute
`total_value_usdt` or derive trading decisions from per-row values.

### Balance array display order (v1.1-ui-polish-2 addendum; net-value sort v0.8)

`private_account.balances_unified[]` and `private_account.balances_spot[]` are
emitted by **`abs(net value)` DESC**, null last, `asset` ASC (original input
order retained for the same asset). Net value for sort:

- unified: `value_usdt − cross_margin_borrowed_value_usdt` when both are known;
  if either is null/missing/invalid, the row sorts with nulls last
- spot: `value_usdt` (no borrow field)

This is an additive display convention only; it does not change the frozen market
`rows` order or `sort_basis` semantics, and `schema_version` remains
`public-market-snapshot/v1`.

## METAL Asset Tag + UI Amendments (v0.5, stage `2026-07-ui-filter-balance-metal-v1`)

Frozen 2026-07-08. Wire `schema_version` stays `public-market-snapshot/v1`; every
change is **additive** (the v0.1–v0.4 normalized samples still validate). Evidence:
public exchangeInfo + spot-symbol-query capture under
`reports/api-samples/2026-07-ui-filter-balance-metal-v1/20260708T0928Z/normalized/metal-symbol-summary.json`
(all five target baseAssets `XAU/XAG/COPPER/XPT/XPD` ship as `TRADIFI_PERPETUAL`
USDT symbols; no public exact or B-suffix spot leg is listed). Authority order:
`20-implementation.md` > this contract section.

### R3 — METAL asset tag (backend + schema)

`asset_tag` enum gains `METAL`. `asset_tag_for(contract_type, base_asset)` (in
`backend/domain/normalize.py`) checks `baseAsset ∈ {XAU, XAG, COPPER, XPT, XPD}`
(case-insensitive) BEFORE the `TRADIFI_PERPETUAL -> BSTOCK` mapping and returns
`("METAL", "base_asset_metal_symbol", "HIGH")`. A metal `TRADIFI_PERPETUAL` is
therefore `METAL`, never `BSTOCK`. `snapshot.schema.json` `asset_tag` enum is
`["CRYPTO", "BSTOCK", "METAL", "UNKNOWN"]`. No `DISABLED_METAL` is introduced;
`METAL` is a product tag, not a borrow prohibition, and a `METAL` candidate row
resolves to `PRIVATE_BORROW_VALIDATION_REQUIRED` via the existing priority chain.

### R3 — borrow-candidate inclusion widened to {CRYPTO, METAL}

`select_borrow_candidates` (in `backend/domain/snapshot.py`) now admits
`asset_tag ∈ {CRYPTO, METAL}` (previously `CRYPTO` only); `BSTOCK` stays excluded.
This supersedes the earlier CRYPTO-only probe-range wording in the Phase 2
`borrow_validation` block. A qualified `METAL` row (`MARGIN_SPOT_CANDIDATE` with a
negative daily rate) now enters `rate_probe_assets` and
`borrowability_probe_assets`; its borrowability and borrow cost still come from the
private read-only API (the asset tag never implies borrowability). The runtime
borrow-probe loop in `backend/services/snapshot_service.py` consumes the candidate
set directly (no re-filter), so this single predicate change closes the loop.

### R1 — low-daily-rate filter (frontend, no float)

`frontend/index.html` adds a default-ON market-table filter "隐藏 |日费率| ≤
0.03%" that hides rows whose `abs(daily_funding_rate) ≤ 0.00030000` (boundary
inclusive). The threshold comparison is pure string/BigInt
(`absDailyRateAtOrBelowThreshold`); no `Number()`/`parseFloat()` touches the
threshold comparison (float boundary drift avoided). `null`/empty/invalid
`daily_funding_rate` is never hidden by this filter.

### R2 — balance card three-line layout (frontend)

Private-account balance cards switch from the inline `【: ... USDT】` suffix to a
three-line layout: asset / amount / `≈ value USDT`. The amount line applies
thousands separators to the INTEGER part only and preserves the raw fractional
string exactly (no rounding, no trailing-zero trimming); privacy-hidden amount →
`****`. The `≈ value USDT` line: hidden → `≈ **** USDT`; null/invalid value →
`≈ — USDT`; valid → `≈ <formatUsdt2> USDT`. Spot cards show `free` as the amount
plus a separate `冻结:` line and their own `≈ value USDT` line. Spot and unified
cards use the same `冻结:` display rule: a valid positive amount shows the line,
a valid zero omits it, and null/invalid input shows `冻结: —` rather than
masquerading as zero.

### Regression red lines (still unchanged)

`negative_funding_status` / `route_class` enums and their priority order,
`classify.py`, the v0.1–v0.4 field set, and `sort_basis` semantics are unchanged.
`METAL` is additive; `bStock` remains disabled for negative-funding arbitrage.

## Borrowability Zero-Mapping Amendment (v0.6, stage `2026-07-borrowability-error-zero-mapping-v1`)

Frozen 2026-07-09. Wire `schema_version` stays `public-market-snapshot/v1`; every
change is **additive** (the v0.1–v0.5 normalized samples still validate). The
Binance 51061 "insufficient loanable assets" pool-exhausted business error was
previously surfaced as `portfolio_account.max_borrowable=null` even though it is a
*confirmed 0*, not an unknown. This amendment maps it to a definite `"0"` plus an
`error_code`, and adds an additive ≈USDT valuation of the borrowable amount.
Evidence: live SPELLUSDT capture
(`HTTP 400 {"code":51061,"msg":"...insufficient loanable assets..."}`) in
`reports/follow-ups/2026-07-borrowability-51061-zero-mapping.md`. Authority order:
`10-design.md` > this contract section.

### `portfolio_account` three-state semantics (revised)

`portfolio_account` gains two additive fields, both `string | null`, and both added
to `required` (all three backend exits emit them stably):

- `error_code`: the Binance business code string when the pool is confirmed
  exhausted (`"51061"`), else `null`.
- `max_borrowable_value_usdt`: backend-computed ≈USDT value of `max_borrowable` via
  the same `{asset}USDT` price map as `private_account.*.value_usdt` (8-place
  string; stable USD assets priced at 1; `"0.00000000"` when the amount is a valid
  zero). `null` when `max_borrowable` is null/blank or price is unavailable.

`max_borrowable` + `error_code` together express the three borrowability states:

| state | `max_borrowable` | `error_code` | `borrow_validation.error` |
|---|---|---|---|
| exhausted (confirmed 0) | `"0"` | `"51061"` | `null` |
| has quota (>0) | `">0"` string | `null` | `null` |
| not probed (truncated) | `null` | `null` | `"borrowability_not_probed"` |
| system error / unconfigured | `null` | `null` | the system error string, or `null` (verified branch) |

- `max_borrowable="0"` + `error_code="51061"` — probed and confirmed exhausted. The
  400 body is `{code,msg}` with no `borrowLimit` field, so `borrow_limit` is `null`.
- `max_borrowable=null` + `error="borrowability_not_probed"` — borrowability not
  probed (beyond the `maxBorrowable` budget). `null` is reserved for "unknown".
- Frontend badge note (2026-07-22): when classic margin reports pair listed +
  asset borrowable and `verified=true`, but **daily funding rate is strictly
  positive**, the market table shows **正费率** instead of green **已验证可借**.
  Negative/zero rate rows keep the prior green verified-borrowable badge when
  max is not the confirmed-zero state. Green still does **not** require a
  non-null `max_borrowable` (classic-only verification remains possible).
- A non-51061 business error, network failure, 5xx, or `-1003` retry-exhausted
  failure → `max_borrowable=null`, `error_code=null`. An *unknown* business code (a
  real Binance `code` not in the confirmed-zero set) is **not** enumerated today: it
  falls to `null` and is logged in the backend `last_error` as
  `max_borrowable_business_error:<asset>:<code>` so a real sample can surface later.
  Only `51061` is mapped to `"0"`; extending the set is a single-element change to
  `BORROW_ZERO_BUSINESS_CODES` once a raw sample confirms a code.

### `verified` semantics (unchanged)

`verified` keeps its existing definition: classic reference available +
`pair_listed` + `asset_borrowable`. It does **not** consult `max_borrowable`. A row
may therefore be `verified=true` with `max_borrowable="0"` + `error_code="51061"`
(classic reference validated, but the pool is exhausted); the frontend renders a
non-success "可借 0(已借完)" badge instead of the green "已验证可借".

### Regression red lines (still unchanged)

`negative_funding_status` / `route_class` / `asset_tag` enums and their priority,
`classify.py`, `normalize.py`, the v0.1–v0.5 field set, and `sort_basis` semantics
are unchanged. All v0.6 additions are additive; `max_borrowable` moving from `null`
to `"0"` under 51061 is a bug-fix of a confirmed-zero state, not a shape change.
`bStock` remains disabled for negative-funding arbitrage.

## Opening Quotes Amendment (v0.7, stage `2026-07-bookticker-open-columns-v1`)

Frozen 2026-07-15. Wire `schema_version` stays `public-market-snapshot/v1`; every
change is **additive** (the v0.1–v0.6 normalized samples still validate). Adds an
optional row-level `opening_quotes` block carrying about-60s reference cross-
market bid/ask quotes so the workstation can show a one-level forward/reverse
opening spread without the frontend calling Binance. Evidence: paired public
`bookTicker` discovery under
`reports/api-samples/2026-07-bookticker-discovery-v1/20260715T0651Z/`
(`evidence-index.md` + normalized bookTicker summary). Authority order:
`10-design.md` > this contract section.

### Public source: paired full bookTicker (Group A, always-on)

A new public source `book_ticker_pair` fetches the two full-universe bookTicker
endpoints sequentially with **no parameters** each Group A cycle:

- Spot: `GET /api/v3/ticker/bookTicker`
- USDⓈ-M Futures: `GET /fapi/v1/ticker/bookTicker`

Each call bumps its own request-log key (`GET /api/v3/ticker/bookTicker`,
`GET /fapi/v1/ticker/bookTicker`). The source is **public and always-on** — it is
NOT gated by the private channel or the classic reference. It reuses
`cache_ttl_seconds` (default 60s) as its cadence and is capability-checked, so a
legacy client without the seam stays never-succeeded without raising.

**Atomic pair cache:** both payloads must be a non-empty list that normalizes to a
non-empty map. Either side failing (transport, shape, or empty map) raises and
advances neither the timestamp nor the map — one side failing never partially
commits (FR-2: failure is not cached, last-good is retained).

**Decimal discipline:** a raw `bidPrice`/`askPrice` enters the map ONLY when its
JSON value is a string. A number-typed price is rejected (never `str(number)`-
coerced) and that symbol's quote is simply unavailable. Prices stay raw decimal
strings; `float` never touches a value path.

### Join and usability projection

Per row, the cache is joined by the row's resolved leg symbols: the futures quote
by `row.futures.symbol`, the spot quote by the already-resolved `row.spot.symbol`
(so bStock reuses its B-suffix alias, e.g. futures `TSLAUSDT` -> spot `TSLABUSDT`;
no economic substitute asset is ever guessed). A `None` spot leg yields
`incomplete` without a substitute.

The usability cutoff is a monotonic projection recomputed **every assembly**, not
a fetch-failure side effect: `age < 2 * cache_ttl_seconds` (default `< 120s`) is
`usable`; `age >= 2 * cache_ttl_seconds` is `stale`. A pair that crosses 120s
flips to `stale` on the next assembly without waiting for another fetch.

### New row field `opening_quotes`

Optional row-level object (the current producer always emits a complete object; a
legacy row may omit the whole object and still validate). Its nested fields are all
`required` and `additionalProperties=false`:

- `status`: enum `fresh | incomplete | stale | unavailable`.
- `updated_at`: UTC completion time of the most recent successful paired bookTicker
  fetch (ISO-8601 `Z`); `null` ONLY when the pair never succeeded (`unavailable`);
  retained on `stale`/`incomplete`.
- `spot_bid_price` / `spot_ask_price` / `futures_bid_price` / `futures_ask_price`:
  raw decimal string of the individually-valid `>0` price, or `null` when
  missing/zero/non-string.
- `forward_spread_pct`: `(futures_bid − spot_ask) / spot_ask × 100`,
  `ROUND_HALF_UP` to 2 places.
- `reverse_spread_pct`: `(spot_bid − futures_ask) / futures_ask × 100`,
  `ROUND_HALF_UP` to 2 places.

`*_spread_pct` are **already-multiplied percentage-point** decimal strings (e.g.
`"-0.04"` means −0.04%), with no `%` char — the frontend must NOT multiply by 100
again. Decimal-only; strict `(bid − ask) / ask × 100` operation order; quantize to
`0.01` only on the final result; `-0.00` normalized to `0.00`.

### Status truth table

| status | trigger | prices | spreads | `updated_at` |
|---|---|---|---|---|
| `unavailable` | pair never succeeded (`usable=false`, no `updated_at`) | all null | all null | null |
| `stale` | age `>= 2*ttl` (`usable=false`, `updated_at` retained) | all null | all null | retained |
| `fresh` | usable AND all four prices valid `>0` | all present | both computed | retained |
| `incomplete` | usable AND any price missing/zero/non-string | valid prices kept | per-direction | retained |

Each spread direction is computed independently from its own two operands (forward
needs `futures_bid` + `spot_ask`; reverse needs `spot_bid` + `futures_ask`), so one
missing leg never blanks the other direction. `"0.00000000"` is missing liquidity,
not a computable zero: that price is `null` and only the direction it gates is
blanked.

### Click path (D7, no extra I/O)

The selected-symbol click reuses the canonical row's `opening_quotes`: it reads the
SAME `book_ticker_pair` cache the scheduled tick filled, so it issues NO new
bookTicker HTTP. The projected symbol-snapshot row's `opening_quotes` is identical
to the full-snapshot row's.

### Regression red lines (still unchanged)

`negative_funding_status` / `route_class` / `asset_tag` enums and their priority,
`classify.py`, `normalize.py`, the v0.1–v0.6 field set, and `sort_basis` semantics
are unchanged. `opening_quotes` is additive and optional; the `symbol-snapshot`
schema inherits it automatically via the shared row `$ref` (no change to that
file). No new config/env, no per-symbol HTTP, no WebSocket, no execution path.

## Unified Borrowed Value Amendment (v0.8, stage `2026-08-02-frontend-display-tweaks-v1`)

Frozen 2026-08-02. Wire `schema_version` stays `public-market-snapshot/v1`; every
change is **additive** (the v0.1–v0.7 normalized samples still validate). Adds an
optional per-row liability valuation on unified balances so the workstation can
show hold value, borrowed value, and net value without the frontend reverse-
engineering a unit price. Authority order: `10-design.md` > this contract section.

### New field `private_account.balances_unified[].cross_margin_borrowed_value_usdt`

Optional property on each unified balance item (not in `required`;
`additionalProperties` remains `false`). Type: **8-place decimal string | null**
(same precision as `value_usdt`, not the 2dp `user_min_borrow_value_usdt` path).

Semantics (backend):

- `cross_margin_borrowed` is null, blank, or a valid zero →
  `cross_margin_borrowed_value_usdt = "0.00000000"` (no effective borrow).
- `cross_margin_borrowed` is a non-empty invalid decimal → `null`.
- non-zero valid borrow and the asset price is missing/invalid → `null`.
- non-zero valid borrow and price is usable → Decimal multiply then quantize once
  to 8dp (`_quantize_rate`). Stable USD assets (USDT/USDC) price at 1; other
  assets use the same P5 `/api/v3/ticker/price` map key `{asset}USDT` as
  `value_usdt`.

Hard rules:

- **Display-only.** The field is not included in `total_value_usdt` and must not
  drive trading, borrow, repay, or risk decisions.
- The producer always emits the key on every unified balance row (value may be
  null). Historical samples without the key remain schema-valid because the
  property is optional.
- No warnings are emitted for valuation gaps (same class as
  `max_borrowable_value_usdt`).

### Frontend display and array order

Hold value continues to use backend `value_usdt`. Borrowed value uses the new
field. Net value is display-only:

`net = value_usdt − cross_margin_borrowed_value_usdt`

with fixed 8dp integer arithmetic, then a single ROUND_HALF_UP to 2dp for display.
When either operand is null/missing, net shows `≈ —` (fail-closed; never treat
unknown borrow value as zero). Negative net retains its sign. Privacy-hidden
state short-circuits all three value lines to `≈ **** USDT` before any
subtraction or 2dp formatting.

Both unified and spot balance cards show a net-value line; spot net equals
`value_usdt`. Backend balance arrays are ordered by `abs(net)` DESC (see Balance
array display order above) so heavily long or short-net rows surface first.

## Collateral Cap Amendment (v0.9, stage `2026-08-02-spot-order-routing-cap-display-v1`)

Frozen 2026-08-03. Wire `schema_version` stays `public-market-snapshot/v1`; every
change is **additive** (the v0.1–v0.8 normalized samples still validate). Adds a
per-row `collateral_cap` block from the platform `restricted-asset` list
(`maxCollateralExceededAsset`) so the workstation can show, before a task is
created, that an asset's platform collateral cap is full and its positive-funding
BUY will route through the standard spot account instead of PAPI cross margin.
本契约为对外权威；接口约定仅为实现期输入，归档后不再引用。

### Key-use gates (replace the retired "Phase 1 forbids keys")

This round adopts one keyed `MARKET_DATA` source: `GET /sapi/v1/margin/restricted-
asset` (API-key only, unsigned, platform-level, no account binding, weight 1).
The retired blanket "Phase 1 forbids keys" is replaced by the three gates in
Verified Findings above (backend-only; default `MARKET_DATA` class; per-source
Human authorization). The browser still never calls Binance directly.

### New row field `collateral_cap`

Optional property on each row (not in `required`; `additionalProperties` stays
`false`). The producer ALWAYS emits the key (value may carry nulls); historical
samples without the key remain schema-valid because the property is optional.

```json
"collateral_cap": { "exceeded": true, "asset": "TSLAB", "checked_at": "2026-08-03T04:15:22Z" }
```

| field | type | semantics |
| --- | --- | --- |
| `exceeded` | `true \| false \| null` | `true` = the resolved spot base asset is on `maxCollateralExceededAsset`; `false` = read succeeded and not on it; `null` = read failed (unknown) OR the row has no tradable spot leg (see `asset`) |
| `asset` | `string \| null` | the resolved SPOT base asset used for the match (bStock = the B-suffix pair's base, e.g. `TSLAB`, never the contract `TSLA`); `null` only when the row has no tradable spot leg |
| `checked_at` | `string \| null` | the platform read's UTC completion moment (`YYYY-MM-DDTHH:MM:SSZ`), shared by EVERY row in a snapshot; `null` when the read failed |

### Three-state truth table (no fifth combination is emitted)

| # | exceeded | asset | checked_at | ui_flags | meaning |
| --- | --- | --- | --- | --- | --- |
| 1 | `true` | non-null | non-null | `COLLATERAL_CAP_EXCEEDED` | asset on the cap list |
| 2 | `false` | non-null | non-null | (no cap flag) | read ok, not on the list |
| 3 | `null` | non-null | `null` | `COLLATERAL_CAP_UNKNOWN` | read failed (network / rate limit / auth / no key / offline) |
| 4 | `null` | `null` | = global | (no cap flag) | no tradable spot leg — not applicable |

Frontend fail-closed: any out-of-table combination renders as unknown, never as
"not full". "Not full" (state 2) means only "no cap-full observed this read"; it
does NOT assert PAPI margin-buy will succeed or that `51169` cannot occur.

### `ui_flags` (two new values, derived from the block)

| flag | when emitted |
| --- | --- |
| `COLLATERAL_CAP_EXCEEDED` | state 1 (asset non-null and on the list) |
| `COLLATERAL_CAP_UNKNOWN` | state 3 (asset non-null and read unknown) |

No `..._NOT_EXCEEDED` / `..._NOT_APPLICABLE` flag is added: the block is the
authority; the same fact in two places would drift. Flags are appended after the
existing ones; the frontend MUST test with `includes()`, never by index.

### Hard rules

- **Display-only.** `collateral_cap` never drives routing, sorting, filtering,
  open/borrow gating, or button state. The positive-funding route decision reads
  the list FRESH in the order preflight (a separate call, never this cache).
- **Single match rule.** The match input is the resolved SPOT base asset from
  `resolve_spot_leg` (the same pure function the preflight path uses); exact
  membership, no normalization, no case-folding, no multiplier-prefix stripping.
- **No direction filter.** A hit highlights on BOTH positive- and negative-funding
  rows (decision §E-3); direction only affects the order route, not the display.
- **Failure is unknown.** Any refresh failure emits state 3 and clears
  `checked_at`, even if a last-good value is retained internally for the next
  retry — last-good is NEVER projected to the page (decision §E-4). Offline mode
  or a missing/invalid hedge API key leaves the whole column unknown.
- **Cache isolation.** The display cache NEVER feeds the order preflight, and the
  preflight's fresh read NEVER back-fills the display cache (decision §B-3-1 /
  §6.4). Crossing them would route a just-capped asset through PAPI → contract
  leg fills, spot leg rejected → naked short.
- `summary` adds no count; `warnings` adds no entry; the public endpoint shapes
  and the Start gate are unchanged; no database migration.

## Cache Refresh + Source Freshness Amendment (v0.10, stage `2026-08-03-hedge-status-account-refresh-v1`)

Frozen 2026-08-03. Wire `schema_version` stays `public-market-snapshot/v1`;
every change is **additive** (the v0.1–v0.9 normalized samples still validate,
except that `private_account.source_checked_at` is now `required` whenever a
`private_account` block is present — the producer always emits it, so every
live/assembled snapshot still validates; a hand-built `private_account` without
it now correctly fails schema validation). Authority order: the approved design
`docs/planning/hedge-status-account-refresh-v4.md` > this contract section.

Three triggers share ONE worker-only refresh cycle (design §3.1): the ~60s
scheduled tick, the manual 「更新缓存」 button (`POST /api/public-market/cache-
refresh`), and the open-task `running → 非 running` status hook. The button and
the status hook run the cycle with the account/valuation panel group FORCED:
`price_map` / `unified_balances` / `um_positions` / `spot_balances` /
`pm_account` are read regardless of their source due, and the four private
fetchers evict their single transport-cache key (one fresh signed GET each);
every other source and all of Group C keep their existing due behavior. The
cycle reuses the existing compose → eligible → Group C sweep → assemble
(funding-history overlay + collateral-cap projection intact) → validate →
publish — there is no second cache, worker, or assemble/publish path.

### New field `private_account.source_checked_at`

`required` on `private_account` (the producer always emits it). A fixed-shape
object with exactly five keys; each value is a UTC ISO-8601 `date-time` string
or `null`:

```json
"source_checked_at": {
  "price_map": "2026-08-03T07:34:50Z",
  "unified_balances": "2026-08-03T07:34:50Z",
  "um_positions": "2026-08-03T07:20:00Z",
  "spot_balances": "2026-08-03T07:34:50Z",
  "pm_account": "2026-08-03T07:34:50Z"
}
```

Semantics:

- Each value is the moment this service last **successfully obtained AND wrote
  that source into its cache** — NOT a page-render time, NOT the snapshot
  publish time, NOT the Binance data-effective time.
- A key advances ONLY on a successful cache write; a failed read keeps the
  last-good value and its OLD time (does not advance). Process-wide never-
  succeeded stays `null` (cold start).
- `pm_account` is `null` when the PM capability (`GET /papi/v1/account`) is
  absent; the key is still present.
- This is a source-read success clock, NOT a quote-freshness clock. It does not
  change `private_account.checked_at` or `valuation.priced_at`, which keep their
  existing aggregate account-snapshot semantics (the kept-back right-corner
  overview time). `price_map`'s success time is exposed here (for completeness
  classification and the partial-source notice), not as a per-account panel
  title.

### `POST /api/public-market/cache-refresh` (first public-market write route)

```text
POST /api/public-market/cache-refresh
```

The first WRITE route in the public-market namespace. Its ONLY side effect is
local: enqueue (or coalesce) one `RefreshCacheCommand` and bounded-wait its
completion (`cache_refresh_timeout_seconds`, default 20s, decoupled from the
single-symbol click timeout). It performs NO upstream fetch and writes no cache
directly — all Binance I/O happens inside the snapshot worker. The route takes
no body fields; any posted body is drained and ignored.

- Worker not running (offline / kill-switch off / before bootstrap): HTTP 503
  `cache_refresh_unavailable` (honest failure — a cache command needs the
  worker to run the cycle).
- Command settled within the bounded wait: HTTP 200
  `{"published": <bool>, "account_panels": "complete" | "partial" | "not_attempted"}`.
  - `published` reports only whether a snapshot published; it NEVER alone equals
    "account data refreshed".
  - `account_panels`: `complete` = under force, `price_map` +
    `unified_balances` + `um_positions` + `spot_balances` all succeeded AND
    `pm_account` succeeded when the PM capability exists; `partial` = the panel
    group was attempted but at least one required source did not succeed;
    `not_attempted` = private channel disabled / classic_reference not ready /
    cold start (base_raw not ready).
- Still queued or running at the timeout: HTTP 202 `{"status": "queued",
  "detail": "refresh still in progress"}`. The worker keeps refreshing in the
  background; no auto-polling is added. The frontend cancels loading and tells
  the operator it is still refreshing; the page's `source_checked_at` times are
  the real read evidence afterwards.

Coalescing (design §4.2): while one cache command is in flight, a second submit
(button or status hook) reuses the SAME command rather than stacking. This is an
accepted low-frequency merge: if an event lands in the short window after the
command's account read finished but before the command ends, it does NOT get an
extra post-event read — it falls back to the ~60s tick guarantee. The page shows
the actual `source_checked_at` times; it is never reported as "read after this
click".

The actual per-source success times come from the subsequent `GET /snapshot`
(`private_account.source_checked_at`); the frontend re-reads after the POST and
uses those times as the real read evidence. No GET on this namespace performs
upstream I/O — `GET /snapshot` and `GET /hedge-open-positions` stay pure reads
of the published state.

The frontend's existing ~60s display timer re-reads BOTH endpoints with the
browser cache bypassed; there is no separate positions timer and neither GET
causes upstream I/O. Displayed account-source times and the market table's
generated/data times become bold red only when their age is strictly greater
than 90 seconds.

### `GET /api/hedge-open-positions` account meta

The `account` meta object gains `source_checked_at` — the SAME fixed five-key
object passed through from `private_account.source_checked_at`. When the
snapshot / `private_account` is absent (cold start) the fixed all-null
five-key shape is still emitted so the five keys are always present. This is a
post-merge attachment in the composition root; `merge_positions` is unchanged.

## Positions Dual-Account Balance Amendment (v0.11, stage `2026-08-03-hedge-status-account-refresh-v1`)

Frozen 2026-08-03. Wire `schema_version` stays `public-market-snapshot/v1`;
every change is **additive** and belongs ONLY to the `GET /api/hedge-open-
positions` response — the snapshot JSON schema is NOT modified (these fields
are not on `private_account` or any `rows[]` element). Authority order: the
approved design `docs/planning/hedge-status-account-refresh-v4.md` §9.2 > this
contract section.

### New per-position account-derived balance fields

Each merged position row of `GET /api/hedge-open-positions` gains four
nullable decimal-string account-derived fields. They are **display-only**: they
drive no order, borrow, risk, routing, or cache-write decision. They are a pure
projection, inside the existing pure function `merge_positions`, of the SAME
already-published `private_account` rows — no extra read, no snapshot-cache
change, and the endpoint stays zero-upstream.

| field | source | semantics |
| --- | --- | --- |
| `spot_balance` (existing) | `balances_spot[asset].free + locked` | spot (regular) account balance. |
| `spot_balance_value_usdt` (new) | the SAME `balances_spot` row's existing `value_usdt` | spot balance's existing valuation; never recomputed by the consumer. |
| `unified_balance` (new) | `balances_unified[asset].total_balance` | unified-account full-cross (leveraged) balance — NOT `cross_margin_borrowed`. |
| `unified_balance_value_usdt` (new) | the SAME `balances_unified` row's existing `value_usdt` | unified balance's existing valuation; never recomputed. |

`asset` is the row's resolved base asset via the existing `_merge_base_asset`
rule (strip the `USDT` suffix; the 1000x multiplier prefix is NOT stripped, so
`1000PEPEUSDT` does NOT auto-align to the spot/unified asset `PEPE` — the
honest "no automatic alignment" outcome is unchanged).

> SUPERSEDED 2026-08-08 by v0.14 (end of this file): balance alignment now
> follows the task-frozen identity first (`spot_base_asset`), falling back to
> the asset map and only then to the `_merge_base_asset` suffix strip as the
> honest last resort.

### null / true-zero semantics

- `private_account.verified = false` or the account not ready: all four account
  fields are `null` on every row (the local bookkeeping rows are still
  returned).
- Account ready but the asset is absent from ONE side (spot or unified): only
  THAT side's amount and value are `null`; the other side keeps its figures.
- A valid real zero stays a decimal string and is never degraded to `null`:
  `total_balance = "0"` -> `unified_balance = "0"`; `value_usdt = "0.00000000"`
  -> the `*_value_usdt` field is `"0.00000000"`. `null` is reserved for
  "unknown / not present", exactly as on the source `private_account` rows.
- `cross_margin_borrowed` keeps its existing meaning (full-cross borrow) and is
  shown as the third line of the spot-balance column; it is never folded into
  `unified_balance`. Its approximate USDT value reuses the matching unified
  asset row's existing `cross_margin_borrowed_value_usdt` and is never recomputed
  by the frontend. Because the positions endpoint and page snapshot refresh
  independently, the frontend uses that valuation only when both sources carry
  the exact same raw `cross_margin_borrowed` string; otherwise it renders
  `≈ — U` instead of pairing values from different refresh generations.
- The source `private_account` is never mutated by the projection.

### What does not change

- The snapshot JSON schema (`snapshot.schema.json`) is unchanged; these four
  fields exist only on the hedge-open positions endpoint.
- The ~60s scheduled refresh, the cache-refresh POST/command, the source success
  times (`source_checked_at`), and the zero-upstream GET contract are unchanged.
- No new API, independent polling timer, SSE, WebSocket, or upstream I/O; no order, borrow,
  transfer, Start-gate, or risk-limit change; no aggregation of multiple
  accounts; the 1000x non-alignment rule is preserved.

## Dual-Ledger Flow-Log Amendment (v0.12, stage `2026-08-04-dual-ledger-flow-log-v1`)

A new **read-only** sub-contract under `/api/private-ledger/*`, separate from the
public-market snapshot. The frozen authority is
`docs/planning/2026-08-04-dual-ledger-flow-log-design.md` §13–§15 (v1.2); this
section restates only the wire contract. The snapshot JSON schema, the ~60s
snapshot cadence, cache-refresh, and every existing endpoint are unchanged.

### Routes

| Method & path | Upstream I/O | Purpose |
|---|---|---|
| `GET /api/private-ledger/flow-log?start=<ms>&end=<ms>` | **none** (pure local-ledger read) | window detail + summary + coverage + last run + delta + today |
| `POST /api/private-ledger/refresh` | one manual read-only run (signed GET only) | trigger a `kind="manual"` pull run |

- Same-origin, `127.0.0.1` only. `GET` registers only in `do_GET`; `POST` only
  in `do_POST`; other methods fall through (404). The window has **no 30-day
  cap** (the page reads the local ledger).
- `POST` reads **no** request-body field (any body is drained and discarded) and
  accepts no window parameter; the service computes the window per §15.2.
- Both routes' `200` responses carry `Cache-Control: no-store` (like
  `/api/public-market/snapshot`).

### `GET flow-log` non-200

| Case | Status | Body |
|---|---|---|
| `start`/`end` missing, non-numeric, or `start >= end` | `400` | `{"error":"invalid_window","detail":"…"}` |
| service not wired | `503` | `{"error":"flow_log_unavailable","detail":"flow-log service not configured"}` |

### `GET flow-log` 200 response (`schema_version: "private-ledger/v2"`)

Top-level: `schema_version`, `served_at_ms`, `scheduler_enabled`, `window{start_ms,end_ms}`,
`coverage`, `last_run`, `delta`, `today`, `interest`, `um_income`, `capital_flow`.

- **`scheduler_enabled`** (bool): whether the hourly cadence thread has started.
  `false` when the private channel is off / offline (§15.3). History is still
  served when present.
- **`coverage`** (honesty guardrail, §13.2 rule 7): `start_ms`/`end_ms` are the
  **aggregate** continuous range — `start_ms` = the *later* of the two sources'
  starts, `end_ms` = the *earlier* of the two ends (either is `null` ⇒ aggregate
  `null`). `by_source.{interest,income}` each gives that source's
  `{start_ms,end_ms}` or `null` (never succeeded). `complete` is `true` **iff**
  `window.start_ms >= coverage.start_ms` **and** no recorded gap intersects the
  window — a window fully inside a gap is `false` (never "no records"). `gaps`
  lists only gaps intersecting this window, ≤20, `start_ms` ascending.
  `pending_tail_ms = max(0, window.end_ms - coverage.end_ms)` (or `null` when
  coverage end is `null`) is shown separately and **never** counts toward
  `complete` — the query end is usually "now" while coverage stops at the last
  refresh.
- **`last_run`** (§13.2 rule 9–10): the most recent finished run or `null` (no
  run ever). Fields: `run_id, kind, finished_at_ms, interest_status,
  interest_error, income_status, income_error, truncated,
  consecutive_failure_count`. `*_status ∈ {ok,error,disabled}`; `*_error` is a
  stable short code, never a Binance body/URL.
- **`delta`** (§15.4 / F3): `baseline_ms` = the `finished_at_ms` of the
  **second-most-recent** "success run" (`kind ∈ {scheduled,startup_catchup,
  backfill}` **and** both panes `ok`; `manual` never counts). `complete` is
  `false` and `baseline_ms` `null` when fewer than two success runs exist — no
  potentially-misleading numbers are sent. `interest_by_asset`,
  `income_by_type_asset`, `funding_by_symbol`, and the `*_new_row_count` fields
  cover rows with `first_seen_at_ms > baseline_ms` (ingress-time attribution).
  A manual refresh does **not** move the baseline; its rows stay in the current
  delta window.
- **`today`** (§15.4): cumulative by **occurred** time within the Beijing
  calendar day (`day_start_ms` = Beijing 00:00). Different attribution from
  `delta` (ingress); the two are never mixed.
- **`interest` / `um_income`**: `rows` (≤500, time-desc), `summary_*` (always
  computed on the **full** window set), `row_count` (full count), and
  `row_limit_applied` (`row_count > 500`).

### Empty state (§13.2 rule 13, frozen)

Never-run / channel-off / empty ledger still returns **200** with `last_run:
null`, `coverage {start_ms:null, end_ms:null, complete:false, pending_tail_ms:null,
by_source:{interest:null,income:null}, gaps:[]}`, `delta {complete:false,
baseline_ms:null, …empty lists, 0 counts}`, and both panes `rows:[]`,
`row_count:0`, `row_limit_applied:false`. Never 503, never a missing field.

### Hard rules (carried from §13.2 / §14)

- **All IDs are strings** (`tx_id`, `tran_id` are 19-digit longs `> 2^53`; a
  JSON number would be silently mutated by a browser `JSON.parse`).
- **Amounts/rates pass through verbatim** as strings — no round/quantize/float/
  zero-pad; missing ⇒ `null` (empty `symbol`/`trade_id`/`isolated_symbol` ⇒
  `null`). Never fabricate `"0"`/`""`.
- **No SQL aggregation on amount columns.** Summaries are Python `Decimal`
  sums under an explicit `localcontext(prec ≥ 40)`, emitted via
  `format(total, "f")`. A group with any unparseable amount ⇒ `*_total` is
  `null` and `unparsed_row_count > 0` (never a partial sum).
- **Sort keys** (final display order): interest `(accrued_at_ms, tx_id) DESC`;
  income `(time_ms, income_type, tran_id) DESC`. Dedup keys: `tx_id`;
  `(income_type, tran_id)`.

### Upstream pull (§13.5 / §15; only the run uses it)

Left `GET /sapi/v1/margin/interestHistory` (`size≤100`, `current` from 1, ≤40
pages; response `{total, rows[]}`, **descending**); right `GET /papi/v1/um/income`
(`limit≤1000`, `page` from 1, ≤10 pages, no `incomeType`/`symbol`; response is an
array, **ascending**). Per-source window: `window_end = now`,
`window_start = max(<src>_coverage_end_ms - 3h, now - 30d)` (first-ever ⇒ 1-day
backfill). A page failure ⇒ that pane is `error`, zero rows, coverage unchanged;
the other pane is unaffected. On truncation (`truncated=true`): rows are still
written, but coverage advances only to the proven-continuous point — left pane
keeps `coverage_end = window_end`, does **not** move `start` to `window_start`,
and records a gap `[window_start, oldest_fetched]`; right pane sets
`coverage_end = newest_fetched` (not `window_end`) and records no gap (self-heals
next run). Error short codes: `interest_history_failed`, `um_income_failed`,
`rate_limited`, `private_channel_disabled`.

### `POST refresh` response (§13.4)

| Case | Status | Body |
|---|---|---|
| done (panes may differ) | `200` | `{run_id, kind:"manual", finished_at_ms, interest_status, interest_error, interest_new_row_count, income_status, income_error, income_new_row_count, truncated, capital_flow:{status,error,fetched_row_count,new_row_count,possibly_incomplete}}` |
| a run is in flight | `429` | `{"error":"flow_log_busy","detail":"另一次流水拉取正在进行"}` |
| private channel off | `409` | `{"error":"private_channel_disabled","detail":"私有只读通道未启用"}` |
| service not wired | `503` | `{"error":"flow_log_unavailable","detail":"…"}` |

`consecutive_failure_count` (§13.2 rule 10) is computed live from the run table:
count consecutive most-recent runs where either pane is `error`, stopping at the
first run with neither pane in error; `disabled` is not a failure; no runs ⇒ `0`.
It is not a stored column.

### Cross-margin capital-flow source (additive, stage `2026-08-10-cross-margin-flow-log-v1`)

A third read-only ledger source added to `GET flow-log` as an **additive**
top-level block. `schema_version` stays `private-ledger/v2` (NOT bumped). The
middle pane renders it between interest and `um_income`.

- **Endpoint.** `GET /sapi/v1/margin/capital-flow` (sapi, `api.binance.com`,
  100 IP weight). **全仓**: `symbol` is OMITTED (cross-margin / PM wallet);
  per-symbol (isolated) is a non-goal. Response is a bare JSON array; each row
  has `id, tranId, timestamp, asset, type, amount` (`amount` signed: `+` into
  the cross-margin wallet, `−` out — the recon is from the cross-margin
  wallet's viewpoint, so MAIN↔UM/CM direct transfers that bypass it do not
  appear here).
- **Single page, no paging.** One request per run, `limit=1000`, **no
  `fromId`** paging, no 7-day slicing. A full page (`== 1000`) sets
  `possibly_incomplete: true` (a flag, not a failure); the next hourly run's
  3h overlap re-pulls. Window: first-ever `[now-1d, now]`; thereafter
  `[capital_flow_coverage_end_ms - 3h, now]`.
- **`capital_flow` block**: `{rows (≤500, time-desc), row_count,
  row_limit_applied, last_run}`. `last_run` is capital's own run state
  (`{finished_at_ms, status, error, fetched_row_count, new_row_count,
  possibly_incomplete, window_start_ms, window_end_ms}` or `null` when never
  pulled) — it is NOT the two-source `last_run`. There is **no** Decimal
  amount summary: summing capital `amount` across `type` values has no clear
  product meaning, so the pane shows a per-type row COUNT only.
- **Hard isolation.** Capital lives in its own table
  (`margin_capital_flow_rows`, PK `id`) and its own `ledger_meta` keys
  (`capital_flow_coverage_start_ms` / `_end_ms` / `_last_run`). It **never**
  enters `flow_refresh_runs` (no new column, no new row), the shared
  `coverage_gaps` list, the coverage **aggregate** (`start_ms`/`end_ms`/
  `complete`/`pending_tail_ms`), the delta baseline, success-run
  classification, or the two-source `last_run`. A capital failure is recorded
  only in capital's own `last_run` and advances nothing; the interest/income
  run is unaffected. The cross-margin idempotency key is `id` (a Binance flow
  id); the same `tranId` with different `type` has different `id` and is fully
  retained (multiple rows per tranId).
- **`coverage.by_source.capital_flow`** is display-only (`{start_ms, end_ms}`
  or `null`); it is merged in AFTER the two-source aggregate is computed, so
  `coverage_for_window` — the gate the hedging net-PnL display consumes — is
  provably unchanged whether capital never succeeded or is failing. Empty
  state: `by_source.capital_flow: null`, `capital_flow: {rows:[], row_count:0,
  last_run:null}` (empty-state, NOT an error state). Error short code:
  `capital_flow_failed` (plus `rate_limited` / `capital_internal_error`).


## Asset Transfer Amendment (v0.13, stage `2026-08-06-asset-transfer-live-v1`)

Frozen 2026-08-08 (delivered 2026-08-06/07; Human live acceptance passed and
merge authorized 2026-08-07). This is the first MONEY-MOVING route in this
document's scope; for this one route only it supersedes the initial baseline's
blanket "Forbidden: … transfer …" line (the baseline stays as the Phase-1
historical scope). Implementation authority: `backend/app/server.py`
(`_handle_asset_transfer`, `_parse_asset_transfer_request`,
`_dispatch_asset_transfer`) and `backend/asset_transfer/store.py`; the accepted
exposure is recorded in `PROJECT_STATE.md` (Live Risks, 2026-08-07).

### `POST /api/asset-transfer`

Controlled transfer between the unified (Portfolio Margin) account and the
regular spot account, reusing Binance `universal_transfer`
(`POST /sapi/v1/asset/transfer`) with zero change to that client call.
Registered only in `do_POST`.

Request body — a JSON object with ALL six fields required:

| field | rule |
|---|---|
| `client_request_id` | UUID-format string; the idempotency key, generated by the caller |
| `from_account` / `to_account` | each `"unified"` or `"spot"`, and they must differ. The Binance transfer type is mapped SERVER-side from this pair (frozen enum) — the body never carries a Binance type |
| `asset` | non-empty string; must appear in the FROM account's current snapshot balance list (else `400 unknown_asset`; snapshot not ready → `503 snapshot_not_ready`) |
| `amount` | positive decimal string (`^\d+(\.\d+)?$` — no sign, no scientific notation, no whitespace) |
| `confirm` | must be exactly `true` (the only gate; `400 confirm_required` otherwise) |

Other missing/invalid fields → `400 invalid_request`. Shape validation only —
NO balance-sufficiency precheck (the snapshot cache may be 60s old; an
insufficient balance comes back as a Binance error code and is relayed
verbatim).

### Idempotency and the four-state conclusion

Binance `asset/transfer` has NO idempotency key — a resubmission really moves
money twice. The idempotency key is local: `client_request_id` is the PRIMARY
KEY of the `asset_transfer` table in `data/asset-transfer.sqlite3`. The handler
first records `pending`; a unique-constraint hit replays the stored record and
NEVER re-sends upstream. The outbound call is one-shot — no retry.

`status` concludes in one of four states:

- `succeeded` — HTTP 200 with a `tranId` (relayed as the string `tran_id`).
- `failed` — a 4xx other than 418/429; Binance `code`/`msg` relayed verbatim
  (`error_code` / `error_message`, the latter prefixed with a plain-language
  HTTP-status meaning).
- `unknown` — transport error/exception, 5xx, 418/429 (rate-limit/IP-ban), or
  HTTP 200 WITHOUT a `tranId`. An explicit state, NOT a failure: the money may
  have moved; never auto-retry (a retry requires a NEW `client_request_id`,
  which is exactly why `failed` must not be claimed here) — a human verifies on
  the exchange.
- `pending` — the pre-dispatch record. A record stuck in `pending` is NOT
  auto-resolved (decision R3); it is handled manually against the audit table.

A processed request answers HTTP 200 with the record (`client_request_id`,
`from_account`, `to_account`, `asset`, `amount`, `status`, `tran_id`,
`error_code`, `error_message`); amounts pass through as strings. When the
channel is not configured the route answers `503 asset_transfer_unavailable`.

### Exposure surface (accepted; recorded honestly)

This route is NOT controlled by `APP_HEDGE_EXECUTOR` — that switch governs only
hedge order placement, while a transfer is a user-initiated standalone action.
Enablement = not offline + hedge API key present; there is no separate switch
and no per-transfer amount limit (Human decisions O-1/O-2, 2026-08-06). The
only threshold is `confirm: true` — any local process that can reach
`127.0.0.1:8787` can move real funds. Startup prints a visibility banner in
both the enabled and disabled branches (a notice, not a gate). Human accepted
this exposure 2026-08-07; every transfer lands in the audit table for
after-the-fact review. Live verification so far covers ONLY the
`unified → spot` success path (three real USDT transfers with exchange
`tranId`s); the `spot → unified`, `failed`, and `unknown` paths have offline
evidence only.

## Spot-Leg Identity Amendment (v0.14, 2026-08-07, Human-directed, no stage)

Frozen 2026-08-08 (delivered 2026-08-07: the pure-table resolver commit
`8ee6d3c` plus the symbol-identity-unification line; live-verified by the
SNXXUSDT/SNXXBUSDT open+close round-trip). Design:
`docs/planning/symbol-identity-unification-2026-08-07.opus5.md`; implementation
authority: `backend/domain/normalize.py` (`resolve_spot_leg`,
`resolve_spot_identity`, `SPOT_SYMBOL_MAP`) and `PROJECT_STATE.md` (Current
Status, 2026-08-07).

### Spot-leg resolution is now a pure table lookup (supersedes the frozen bStock alias rule)

The resolution rule frozen in "Verified Findings" (the 2026-07-03 bStock-alias
amendment, steps 1–3) and the `spot.match_type` enum under "Enums" are
SUPERSEDED — those passages stay as history; this section is the live rule.
`resolve_spot_leg` now resolves:

1. `exact_symbol` — `spot_by_sym[base_asset + quote_asset]` (unchanged);
2. the `SPOT_SYMBOL_MAP` entry keyed on the exact contract symbol — the
   explicit exception table for bStocks (`TSLAUSDT` → `TSLABUSDT`,
   `bstock_b_suffix_alias`) and multiplier-prefixed contracts
   (`1000BONKUSDT` → `BONKUSDT`, `multiplier_strip_alias`);
3. `(None, None)` — fail-closed: an unlisted symbol means NO resolvable spot
   leg, never a guessed one.

Every candidate is still gated on `status == "TRADING"` (`_tradable_spot`,
unchanged). The old string-derived guesses (`baseAsset + "B" + quoteAsset`,
and the `base[4:]` multiplier-prefix strip) are DELETED: contract `BUSDT`
(baseAsset `B`) mis-resolved onto spot `BBUSDT` (BounceBit — a different coin,
indistinguishable from a real bStock suffix at the string level), and the
4-char strip mangled the `1000000`-prefixed family (`1000000MOG` → `000MOG`).

`spot.match_type` gains `multiplier_strip_alias` (already in
`snapshot.schema.json`). The table (71 entries at this writing: 65 bStock + 6
multiplier) is machine-generated from live `exchangeInfo`; the code is the
authority, not any count restated here. Maintenance:
`scripts/check-spot-symbol-map.py --emit` regenerates the table literal;
`--verify` diffs the committed table against the exchange and reports
STALE/MISSING/SUSPECT (SUSPECT is never auto-admitted). A companion
`SPOT_SYMBOL_DENY` set records human-confirmed non-matches (e.g. `BUSDT`) so
the verifier stops re-reporting them; the resolver itself never reads it.

### Identity vs existence, and task-frozen identity

Identity (what the spot leg is CALLED) comes from the static table — stable and
freezable; existence (whether that leg trades NOW) is probed live at task
creation (`check_symbol_legs`). The two are deliberately not conflated:
`resolve_spot_identity(contract_symbol)` (pure lookup, zero I/O) answers
identity only and NEVER returns None; it raises `ValueError` on a
non-USDT-margined input. At hedge-open task creation the resolved identity is
FROZEN onto the task (`spot_symbol` / `spot_base_asset` / `symbol_match_type`);
open, close (inherited via `cycle.first_task_id`), and display read the frozen
value — a later table change never silently re-resolves an open hedge (drift is
alarmed via `identity_drift` / `identity_conflict`, not switched).

### New row field `spot.base_asset`

Each snapshot row's `spot` object gains optional nullable `base_asset`: the
resolved SPOT leg's base asset (`SNXXB` for a bStock, `BONK` for
`1000BONKUSDT`) — the single-point truth the positions merge now shares.
Additive/optional; legacy rows without the key still validate.

### New position-row fields `spot_symbol` / `spot_base_asset`

Each merged row of `GET /api/hedge-open-positions` gains the task-frozen spot
identity — an intentional contract extension pinned by
`backend/tests/test_hedge_api.py`. Rows backed by a task record carry the
values; `no_task` rows carry `null` (they have no task columns; balance
alignment keeps using the snapshot asset map). This lets the UI show the leg
actually hedged (`SNXXBUSDT`, not the contract name `SNXXUSDT`).

The same delivery also supersedes the v0.11 description of balance alignment:
the merge's spot-asset lookup is now three-level (task-frozen
`spot_base_asset` → the snapshot row's resolved `spot.base_asset` via the
asset map → the `_merge_base_asset` suffix strip as the honest last-resort
fallback); the v0.11 text, which presents the suffix strip as THE rule, stays
as history.

### 1000x multiplier contracts: open-task creation is fail-closed

Creating an OPEN hedge task for a `multiplier_strip_alias` symbol is rejected
`400 multiplier_contract_unsupported` (in the hedge-open task API, not in this
snapshot contract): the execution chain sends ONE shared quantity to both legs
while 1 contract = 1000 spot units, which would leave a 999× naked short, and
the leg-quantity conversion is NOT implemented. Close tasks are not blocked by
this gate, but that is not a safety statement — close shares the same
single-quantity preflight, so an existing such position must be closed manually
on the exchange. The full conversion scope (eight sites) and its
Human-authorization gate live in `PROJECT_STATE.md` (Live Risks / Open
Follow-ups, 2026-08-07); this contract does not restate them.

## Account Source Availability Amendment (v0.15, F4, 2026-08-07/08, Human-directed, no stage)

Frozen 2026-08-08. Wire `schema_version` stays `public-market-snapshot/v1`;
every change is **additive** — with the same compatibility exception as v0.10:
`private_account.unavailable_sources` is now `required` whenever a
`private_account` block is present. The producer always emits it, so every
live/assembled snapshot still validates; a hand-built `private_account` without
it now correctly FAILS schema validation. Implementation authority:
`backend/domain/snapshot.py` (`assemble_private_account`) and
`backend/app/server.py` (account-meta passthrough); plan and dual reviews:
`docs/planning/f4-exchange-no-position-claim-2026-08-07.opus5.md`.

### New field `private_account.unavailable_sources`

`required`, always emitted. A unique-item array drawn from exactly
`["unified_balances", "um_positions", "spot_balances", "pm_account"]` — the
`source_checked_at` keys minus `price_map` (not an account source).

Semantics — "not read" and "known empty" are different facts:

- The judgement is the fetcher input being `None` (disabled/failed), NEVER the
  array being empty: `[]` is the true value "read it, genuinely empty", and
  using it as a failure signal would false-alarm precisely when the account is
  really flat — swapping one false claim for another.
- An empty `unavailable_sources` therefore means EVERY account source was
  obtained; it must never be read as "unknown".
- When the whole account block is unavailable (the `verified=false` path), all
  four names are listed; on cold start with no snapshot at all, the passthrough
  below likewise lists all four — an empty list on that path would be another
  false claim.

### Passthrough into `GET /api/hedge-open-positions` account meta

The `account` meta object gains `unavailable_sources`, passed through from
`private_account.unavailable_sources` in the composition root (the same
post-merge attachment point as `source_checked_at` in v0.10; `merge_positions`
is unchanged — the field is display-only and drives no row-level judgement). A
legacy/test block without the key degrades to `[]` ("all available"), never to
an alarm. The frontend keeps the positions TABLE (local bookkeeping is most
useful exactly during an outage) and adds one red notice line when sources are
unavailable or `verified === false`, instead of the former per-row "exchange
has no position" claim.

## Max-Withdraw + Sample-Validity Amendment (v0.16, Q4, 2026-08-07, Human-directed, no stage)

Frozen 2026-08-08. Adds one on-demand read-only route and corrects one stale
sample claim in this document. Implementation authority:
`backend/app/server.py` (`_handle_max_withdraw`,
`_MAX_WITHDRAW_ASSET_CAP = 30`) and `backend/services/private_client.py`
(`fetch_max_withdraw`, `WHITELIST`); final form and the no-frontend-consumer
decision: `PROJECT_STATE.md` (Current Status, Q4 entry, 2026-08-07).

### `GET /api/private-account/max-withdraw?assets=X,Y,...`

Batch per-asset max-transferable amounts out of the unified account (upstream
`GET /papi/v1/margin/maxWithdraw`; whitelist 15→16). Binance has NO batch
variant — N assets = N signed requests — so the loop sits behind ONE backend
request, which controls the upstream cadence. Registered only in `do_GET`.

- Input: query param `assets` (required, comma-separated, alphanumeric).
  Missing/invalid → `400 invalid_asset`; more than 30 assets →
  `400 too_many_assets` (the cap keeps a malformed query from draining the PAPI
  IP weight pool — a measured 18-asset account already takes ~10s serial, and
  the bottleneck is latency, not weight). Private channel off →
  `503 private_account_unavailable`.
- Success (200): `{"results": [{"asset", "max_withdraw", "error"}, ...]}`,
  duplicates removed. Per-asset failure isolation: one asset failing does not
  affect the others — that item carries `max_withdraw: null` plus an `error`
  string and the overall response stays 200. `null` means UNREADABLE; a real
  `"0"` (fully collateralized) is a valid, important answer and is never
  collapsed into `null`.
- On-demand read, deliberately NOT in the snapshot: the value moves with price,
  so a cached copy would be stale exactly when a transfer is being sized.

Consumer status (recorded honestly): the transfer dropdown and unified-account
USDT asset card read the backend account-cache snapshot with zero frontend
requests. USDT shows the account-level `total_available_balance_usdt` labeled
「可转」/「可转余额」 — valid only because USDT is the quote unit and explicitly
not generalizable; other assets show
`cross_margin_free` labeled 「可用」, the wording following the data source).
This route remains the only source of exact per-asset transferable amounts; it
was removed from the frontend same-origin whitelist, so a future frontend call
is an explicit decision the self-check guard will catch, not a silent
regression.

### Correction: the frontend fixture was orphaned and has been removed

The "Frontend Integration Rules" line above ("or matching fixture JSON
generated from this schema") predates reality:
`frontend/fixture/public-market-snapshot.json` had no runtime consumer —
neither the frontend nor `self-check.js` loaded it (self-check uses
`backend/tests/fixtures/private-account-v1-design.json`; the historical Phase-2
script is retained in Git with samples under
`reports/api-samples/2026-07-phase2-borrow-sort-v1/`, while
`scripts/discovery-capture-private-v1.py` still attempts that path inside
try/except with a fallback) —
and it FAILED schema
validation (5 violations: `cross_margin_borrowed` missing on
four unified-balance items, `notional_usdt` missing on a UM position). It was
deleted on 2026-08-08 (Human-authorized doc catch-up; the `smoke_server.py`
fetch check went with it). The frozen normalized samples under
`reports/api-samples/` remain the historical references.

## Margin Repay Amendment (v0.17, stage `2026-08-09-pm-margin-repay-v1`)

Delivered 2026-08-09/10 as one delivery range (T1 backend + T2 frontend wiring;
the earlier frontend preview's "repay backend not wired yet" state is superseded
— the controls now drive the real local route). This is the SECOND MONEY-MOVING
route in this document's scope and the first one that repays debt.
The delivery itself did not authorize deployment or live use; Human separately
deployed it, enabled `APP_MARGIN_REPAY_ENABLED`, completed XLM specified-amount
and INJ full-repayment live checks, accepted both independent reviews, and on
2026-08-10 gave final business acceptance with the repayment gate kept enabled.
This is ongoing authorization for Human-confirmed manual use, not for models to
change the gate or initiate money movement. Implementation authority:
`backend/app/server.py`
(`_parse_margin_repay_request`, `_handle_margin_repay_post`,
`_handle_margin_repay_get`, `_dispatch_margin_repay`),
`backend/margin_repay/store.py`,
`backend/services/hedge_open_live_client.py` (`repay_margin_debt`), and
`frontend/index.html` (repay wiring on the unified-account borrowed-asset cards).

Upstream: Binance `POST /papi/v1/margin/repay-debt` (signed TRADE, weight 3000,
single repayment value ≤ 50,000 USD enforced by the exchange). `asset` is the
debt asset; omitting `amount` repays the full debt when the repay assets suffice;
`specifyRepayAssets` is fixed SERVER-side to `USDT` — and Binance still spends
same-coin assets FIRST, using the specified USDT only afterwards. Binance
discloses no conversion price, fee, or slippage for the cross-asset leg, and
offers no client idempotency key and no public by-id result query.

Live evidence at final acceptance: the local audit contains exactly two
successful requests — XLM requested/repaid `5`, and INJ requested with local
amount `"0"` and refreshed to zero debt. Binance omitted response `amount` for
the INJ full repayment, so `repaid_amount` is honestly `null`; its exact repaid
quantity and actual spend asset cannot be reconstructed from the local record.
Operationally use one browser tab, verify full repayment from the refreshed
debt balance, and avoid concurrent bulk refresh/open activity around this
weight-3000 endpoint.

### `POST /api/margin-repay`

Registered only in `do_POST`. The route has its OWN gate,
`APP_MARGIN_REPAY_ENABLED` (default OFF), independent of `APP_HEDGE_EXECUTOR`:
the client is injected only when the gate is on AND the service is not offline
AND hedge API credentials exist; otherwise the route answers
`503 margin_repay_unavailable` with zero upstream calls. Startup prints a
credential-free banner in both branches.

Request body — a JSON object with ALL four fields required and NO others:

| field | rule |
|---|---|
| `client_request_id` | UUID-format string; the idempotency key, generated by the caller |
| `asset` | must exactly hit a current unified-account snapshot asset with `cross_margin_borrowed > 0` (else `400 unknown_asset`; snapshot not ready → `503 snapshot_not_ready`, zero upstream) |
| `amount` | unsigned plain decimal string (`^\d+(\.\d+)?$` — no sign, no scientific notation, no whitespace). The exact string `"0"` means REPAY ALL (the outbound Binance call then OMITS `amount`; the literal `0` is never sent upstream). Any other value must be strictly greater than zero — `"0.0"`, `"0.00"`, `"00"` and similar numeric zeros are rejected (`400 invalid_request`). Never processed as float |
| `confirm` | must be exactly `true` (`400 confirm_required` otherwise) |

Any extra field — including `specifyRepayAssets` or any repay-asset override —
is rejected (`400 invalid_request`); the repay asset is not client-negotiable.
No cached-debt sufficiency precheck: the debt moves with interest, and the
exchange makes the final call.

### Idempotency and the four-state conclusion

Binance `repay-debt` has NO idempotency key — a resubmission really repays
twice. The local key is `client_request_id`, PRIMARY KEY of the `margin_repay`
table in `data/margin-repay.sqlite3` (amounts stored as TEXT; no key/secret/
signature is ever recorded). The handler records `pending` first; a
unique-constraint hit replays the stored record and NEVER re-sends upstream.
The outbound call is one-shot — no automatic retry.

`status` concludes in one of four states:

- `succeeded` — ONLY HTTP 200 + JSON object + `success is true` + response
  `asset` equal to the request asset; relays `amount`/`updateTime` as
  `repaid_amount`/`update_time` strings.
- `failed` — a plain 4xx rejection (408/418/429 excluded); Binance
  `code`/`msg` relayed via `error_code`/`error_message`.
- `unknown` — transport error/timeout, 5xx, 408/418/429, non-JSON, or a 200
  that fails the strict-success rule. An explicit state, NOT a failure: the
  money may have moved; never auto-retry — a human verifies on the exchange.
- `pending` — the pre-dispatch record; never auto-resolved.

A processed request answers HTTP 200 with the record (`client_request_id`,
`asset`, `amount` (`"0"` kept for audit), `repay_asset` (fixed `USDT`),
`status`, `repaid_amount`, `update_time`, `error_code`, `error_message`);
business conclusions never ride the HTTP status. Validation/channel errors use
4xx/503 as listed above.

### `GET /api/margin-repay?client_request_id=<UUID>`

Pure-local recovery query: reads ONLY the SQLite record, zero upstream calls.
Registered only in `do_GET`. Exactly one `client_request_id` parameter
(400 otherwise and for malformed UUIDs); unknown id → `404 not_found`; store
not configured → `503`. It exists so a page reload — or a lost response between
the browser and the local service — can recover the SAME request instead of
issuing a new one.

### Frontend behavior (frozen seam)

The repay input/button still appears only on unified-account cards with
`cross_margin_borrowed > 0` (placeholder `0 自动还所有`; the ~60s re-render
refills unsubmitted inputs and pending state from memory). Clicking 还款 opens
a confirmation that states the debt asset and 全部/指定数量, that Binance spends
same-coin assets first and the specified USDT only afterwards, that the
cross-asset conversion price/fee/slippage is undisclosed and cannot be
estimated by the page, and that account data is a ~60s cache that may lag — it
never claims "only USDT is deducted" or that USDT is necessarily sufficient.
Cancelling the confirmation sends nothing, generates no id, and writes no
pending record.

Only AFTER the human confirms does the page generate the UUID (reusing the
live-verified `newTransferRequestId` assembler, never `crypto.randomUUID()`),
persist `{client_request_id, asset, amount}` per debt asset to
`localStorage['funding_hedging_margin_repay_pending']` BEFORE the POST (if
persistence fails the request is not sent), and POST a body of exactly the four
frozen fields with the original `amount` string. During any one submission all
repay buttons are disabled (weight-3000 anti-spam). The four-state display
trusts `body.status` only — HTTP 200 alone is never success.

On startup/reload every pending record is recovered with ONE local GET per
record (no polling). `failed` shows the exchange code/message and ends the
request (the next attempt requires a fresh confirmation). `pending`/`unknown`
lock the asset — no new request is generated — and offer a manual
「我已到币安核对」 unlock that clears local state only (zero requests).
`succeeded` shows the actual repaid asset/amount when present, forces an
account-snapshot refresh, and clears the pending record (unlocking the asset)
ONLY after a complete refresh; a failed refresh keeps both the success result
and the lock, with a retry-refresh / page-reload recovery path, so a stale debt
card cannot induce a duplicate repayment. A GET 404 or request-layer error
during recovery never claims "not repaid" and never clears the pending id.
There is no automatic retry, no polling, no scheduled repayment, no
`/repayLoan`, and no editable repay-asset parameter anywhere in the page.
The pending lock is page-memory-backed after startup and is not synchronized
across already-open tabs; concurrent repayment work must therefore use a single
tab. Reopen this limitation if automated submission or multi-tab/multi-device
operation becomes a real requirement.

## Local Net Position Quantity Amendment (v0.18, stage `2026-08-10-local-net-position-v1`)

Frozen 2026-08-10. Wire `schema_version` stays `public-market-snapshot/v1`; this
amendment adds NO field and changes NO shape — it restates the semantics of three
ALREADY-EXISTING local quantity fields on each merged position row of
`GET /api/hedge-open-positions`. Authority order: the stage change plan
`reports/agent-runs/2026-08-10-local-net-position-v1/00-change-plan.md` > this
contract section. The fix corrects a partial-close misreport: the local ledger
previously read only open legs, so `spot_qty`/`perp_qty` stayed at the cumulative
OPENED qty even after a close (e.g. XVGUSDT showed 50000 after two 10000 closes
instead of the real 30000, falsely triggering `drift`).

### Restated semantics of the three local quantity fields

For each not-closed `cycle_id` bucket, per leg, the backend now computes from the
existing `hedge_open_leg` fill ledger:

```text
spot_qty   = Σ(open spot cumulative_base_qty) − Σ(close spot cumulative_base_qty)
perp_qty   = Σ(open perp cumulative_base_qty) − Σ(close perp cumulative_base_qty)
position_qty = direction_sign × perp_qty        # forward = −1 (SELL short), reverse = +1 (BUY long)
```

- These three fields are the **application's own fill-ledger REMAINING quantity**
  (open minus close), not an exchange reconciliation. A real fill is recognized
  solely by `cumulative_base_qty > 0` regardless of the literal exchange status —
  a `PARTIALLY_FILLED`/`CANCELED`/`EXPIRED` leg that filled partially, a single
  leg whose pair failed, and a leg later written by UNKNOWN reconcile all count;
  a zero-fill failed leg contributes nothing. Deleted tasks' real fills still
  count (`includes_deleted_task` flags the mixed source).
- The open-cost basis is kept separate: `spot_avg`/`perp_avg` (and the
  `*_avg_price_incomplete` flags) are still computed from OPEN legs only. A close
  leg reduces the remaining `spot_qty`/`perp_qty` but never enters the avg's
  notional numerator or priced-qty denominator, so partial close never drags the
  displayed open avg.
- Already-closed cycles stay excluded from the position table at the source query
  (unchanged); they appear only on the history page via `hedge_open_cycle_close_log`.
- The wire field set, the merge layer, `domain.py`, and the frontend are
  unchanged — only the values of these three existing fields now mean "remaining".

### These are NOT an exchange reconcile — read `um_position_amt` for the exchange side

`spot_qty`/`perp_qty`/`position_qty` reflect the LOCAL fill ledger, which can
diverge from the exchange: a manual exchange-side reduction (e.g. a reverse
auto-close settled by hand at the exchange but recorded only in the close log)
is not subtracted here, so the local remaining qty can read HIGHER than what the
exchange actually holds. The exchange-side contract quantity from the SAME
account snapshot is `um_position_amt` (the matched USDⓈ-M position on the merged
row) — that field, not these three, is what the exchange reports for the perp
leg this round.

### `single_leg_exposure=false` and `drift=false` do NOT mean "reconciled"

Both markers are computed from these local remaining quantities against the same
account snapshot, and both are intentionally weak/advisory:

- `single_leg_exposure=false` means only that the local remaining `spot_qty` and
  `perp_qty` are within the 1% tolerance band of each other (a precision/rounding
  band, not an allowance). It does NOT assert the position is fully hedged at the
  exchange, and it is silent whenever both remaining quantities are ≤ 0.
- `drift` is direction-specific. For `forward`, the existing strict comparison
  is unchanged: `held = regular spot (free + locked) + unified total_balance`,
  and the marker fires only when the account is readable, local `spot_qty > 0`,
  and `held < spot_qty`.
- For `reverse`, all active local rows for the same resolved spot base asset are
  grouped once: `R = Σ spot_qty`, while account actual sold exposure is
  `A = max(cross_margin_borrowed - cross_margin_free - cross_margin_locked, 0)`.
  Closed cycles and `no_task` rows do not consume the account balance. The same
  verdict is applied to every row in the group. `crossMarginInterest` and local
  `borrow_interest` are deliberately excluded because interest growth does not
  change the originally sold spot quantity.
- Reverse drift fires only when `R - A > R × 0.01`, using Decimal arithmetic and
  the existing 1% precision/rounding band. Exactly 1% is not drift; strictly more
  is. This can hide a shortage of up to 1% and is not a business allowance.
  Missing, blank, unparsable, non-finite, or negative borrowed/free/locked/local
  spot inputs, a missing unified asset row, or an unreadable account leave the
  affected reverse group at `drift=false` without partial arithmetic. No ordinary
  spot balance, `totalWalletBalance`, or interest value substitutes for missing
  reverse inputs.
- `drift=false` means only that this round has no provable advisory alert; it is
  NOT a strong guarantee that the account matches the record. Forward can still
  be masked by unrelated same-asset holdings or unified sub-wallet balances, and
  reverse deliberately fails closed on unknown/invalid data.

Therefore neither `single_leg_exposure=false` nor `drift=false` may be read as
"the local ledger and the exchange are reconciled and consistent." The honest
exchange-side read remains `um_position_amt` from the same snapshot; full
agreement requires comparing the local remaining qty against that figure, not
relying on either weak marker's absence.

### Regression red lines (still unchanged)

`negative_funding_status` / `route_class` / `asset_tag` enums and priority,
`classify.py`, `normalize.py`, the v0.1–v0.17 field set, `sort_basis` semantics,
the ~60s refresh cadence, and the zero-upstream GET contract are unchanged. No
new field, schema, DB migration, service/gate/order/borrow/repay/transfer path,
or frontend behavior is introduced; only the value semantics of three existing
local quantity fields is corrected.

## Public Egress IP Display Amendment (v0.19, stage `2026-08-12-local-ip-display-v1`)

Additive, read-only, same-origin. Adds one route so the page can show the public
egress IP the **backend process** observes, for Human to cross-check the Binance
API IP allowlist. This is NOT a market snapshot field and is NOT merged into any
snapshot/positions response. Implementation authority: `backend/app/server.py`
(`_handle_public_ip`) and `backend/services/public_ip_service.py`.

### `GET /api/system/public-ip`

Returns a fixed four-field, three-state body with `Cache-Control: no-store` on
HTTP 200. The service is a process-local, lazily-fetched, in-process cache; it
issues no request at construction and no background thread.

| field | meaning |
|---|---|
| `status` | one of `ok` \| `stale` \| `unavailable` |
| `public_ip` | the observed public IP string, or `null` |
| `source` | `api.ipify.org` \| `checkip.amazonaws.com` \| `null` |
| `checked_at` | last successful read as UTC ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ`), or `null` |

States:

- `ok` — a value was obtained this cycle.
- `stale` — both sources failed this cycle but a prior success exists; the prior
  `public_ip` / `source` / `checked_at` are returned unchanged (`checked_at` does
  not advance on failure).
- `unavailable` — both sources failed and no prior success exists; `public_ip`,
  `source`, and `checked_at` are all `null`. No value is guessed or synthesized.

Sources are queried in a fixed order with a single attempt each per cache cycle:
primary `https://api.ipify.org?format=json` (JSON `ip`), and only on a primary
exception, non-dict body, missing/non-string `ip`, or an invalid/non-public IP
does it fall back to `https://checkip.amazonaws.com/` (whitespace-stripped plain
text). Each call is a GET, no request body, 2-second timeout, reading at most 64
bytes. Every candidate must pass `ipaddress.ip_address` (IPv4 or IPv6) and is
rejected if private/loopback — a captive-portal local value must never pose as
the public egress IP. Exception text, URLs, and headers are never exposed to the
browser.

The single shared instance caches both success and failure for 5 minutes; a lock
serializes cache misses so each cycle hits each source at most once, preventing
the ~60-second page refresh from turning into repeated outbound calls. When the
public-ip service is not injected (isolated/offline wiring), the route answers a
fixed `503 {"error":"public_ip_unavailable"}` and makes no outbound call.

### Boundary — display only, never an allowlist authority

This value reflects one observation by this machine's backend process and ONLY
helps Human cross-check the API allowlist. It CANNOT prove the IP Binance
actually observes: a VPN, proxy, or different route between this machine and
Binance can make the two differ. It must never drive an IP-allowlist change, an
order, borrowing, repayment, transfer, any live gate, or any risk action. No new
credential is read, no Binance endpoint is called, and no money path is touched.

### Regression red lines (still unchanged)

`negative_funding_status` / `route_class` / `asset_tag` enums and priority,
`classify.py`, `normalize.py`, the v0.1–v0.18 field set, `sort_basis` semantics,
the snapshot/positions contracts, the ~60s refresh cadence, and the
zero-upstream GET contract on market routes are unchanged. No new market field,
schema, DB migration, gate, order/borrow/repay/transfer path, or credential read
is introduced.

## Smooth-open paused create and dispatch audit (v0.20, stage `2026-08-12-smooth-open-orders-v1`)

Additive hedge-open task contract. Does not change snapshot/positions routes.

### `POST /api/hedge-open-tasks` with `mode=smooth`

A successful open+smooth create is `201` with `status=paused`,
`pause_reason=awaiting_manual_start`, and Chinese reason
「任务首次执行必须点击启动」. The create response does not start a worker,
subscribe public bookTicker, open a gate, or send an order. First complete
preflight, frozen identity/quantity/route, and regular-spot forward USDT
pre-transfer (when that route is selected) still happen at create time.
Immediate-open create remains `running`.

`POST /api/hedge-open-tasks/{id}/fill-once` on a smooth card that has not yet
been Human-started returns `409 start_required`. Human `POST .../start` is the
only first-run path.

### `GET /api/hedge-open-logs?task_id=...`

The existing task-id log document adds `smooth_dispatch_audits`, an array of
`kind=smooth_dispatch_audit` log docs (`log_to_doc` shape: id, task_id, ts,
attempt_id, kind, payload). Missing history is `[]`. Present rows are ordered
by `ts_us`, then `id`. Payload Decimals are decimal strings. Payload records
the same-round gate snapshot and monotonic-microsecond stage marks; it does
not contain API keys, signatures, full private URLs, credentials, or private
raw responses. Immediate/close tasks do not create these rows. Existing
`logs`, `attempts`, and `smooth_market` fields are unchanged.
