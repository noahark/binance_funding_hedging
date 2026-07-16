# Public Market API Contract

Status: contract v0.7 as-built read-only snapshot. The wire `schema_version`
stays `public-market-snapshot/v1`; every addition remains backward-compatible.
The `GET /api/public-market/snapshot` route and `public-market-snapshot/v1`
wire version are historical compatibility names. The payload now represents a
public market snapshot plus optional private read-only enrichment. A route rename
or schema-version bump is a future contract stage, not part of this status sync.

v0.2 additions are in "Phase 2 Amendment (v0.2)"; v0.3 additions (net yield,
cost-leg chain, `private_account`, `sort_basis`) are in "Private Account v1
Amendment (v0.3)"; v0.4 through v0.6 UI/value-display, metal-tag, and
borrowability refinements are in later amendments; v0.7 additive
`opening_quotes` is in the final amendment at the end of this file.
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

The public-market backend exposes three same-origin, read-only JSON endpoints
(no CORS; the frontend never calls Binance). All reuse the canonical published
state; `GET /healthz` (liveness) and `GET /readyz` (readiness) are separate
health endpoints. Success (HTTP 200) responses carry `Cache-Control: no-store`;
503 covers the brief pre-first-publication cold-start window for each route.

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
- Schema-prose drift (deferred): `funding-history.schema.json` line 34 still
  attributes `funding_history`'s emptiness to a *successful* upstream fetch over
  an empty window — narrower than the as-built pure projection above. This stage
  is docs-only and does not alter schema; aligning that schema prose is a
  deferred contract-amendment item (see Residual Risks).

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

- Schema-prose drift (deferred): `symbol-snapshot.schema.json` carries three
  stale prose claims across two lines. Line 5 (top-level `description`) still
  asserts an unconditional submit-a-command + project-from-a-new-publication
  flow that does not hold for the offline or worker-not-running paths above,
  and still asserts a same-version guarantee tying the row's `published_version`
  to the full snapshot — but the full snapshot v1 wire payload has no
  `published_version` field and there is no client-verifiable cross-request
  equality guarantee (see the path and `published_version` notes above). Line 39
  (`refresh_status` `description`) still narrows `partial` to a borrow-source
  fallback and `timeout` to the shared deadline expiring — narrower than the
  as-built behavior above (which also maps premium/history failures to
  `partial`, and worker-absence / assembly / validation failures to `timeout`).
  This stage is docs-only and does not alter schema; aligning that schema prose
  is a deferred contract-amendment item (see Residual Risks).

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

### Balance array display order (v1.1-ui-polish-2 addendum)

`private_account.balances_unified[]` and `private_account.balances_spot[]` are
emitted by `value_usdt` DESC, null last, `asset` ASC. This is an additive display
convention only; it does not change the frozen market `rows` order or `sort_basis`
semantics, and `schema_version` remains `public-market-snapshot/v1`.

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
plus a separate `冻结:` line and their own `≈ value USDT` line.

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
