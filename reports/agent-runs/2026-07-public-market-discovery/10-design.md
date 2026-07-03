# Stage Design

## Summary

Build a small Python `backend/` package that discovers the public Binance
market, classifies each USDⓈ-M perpetual into a route class, and emits a
deterministic candidate table plus a static UI that renders it. The design is
deliberately thin and file-first, matching synthesis section 7:

- `adapters/binance_public.py` is the ONLY network boundary. It requests public
  endpoints, saves raw JSON to `reports/api-samples/public-market/<timestamp>/`,
  and parses them into plain dicts. No credentials, no signing.
- `domain/` holds pure functions: symbol join, funding normalization, route
  classification, trading-rule parsing, planning preview. These take parsed
  dicts / dataclasses and return dataclasses; they never touch the network.
- `services/public_market_discovery.py` orchestrates: read samples (live capture
  or committed fixtures) → build candidate rows → write
  `candidate-classification.{json,csv}`.
- Tests are offline and deterministic, driven by committed fixtures under
  `backend/tests/fixtures/`, so classification can be regenerated and asserted
  without network access.
- The existing `prototypes/fake-ui/index.html` is updated to load the generated
  JSON and render four read-only screens, with the manual-open screen labelled
  simulation-only.

There is no runtime third-party dependency: the adapter uses stdlib
`urllib.request` for GET calls and `decimal.Decimal` for all numeric fields.
Only dev tooling (`pytest`, `ruff`, `mypy`) is added.

## Assumptions

- **Python 3.11** is the pinned interpreter (modern typing, stable `Decimal`,
  broad availability). Implementer creates `.venv` with it.
- Public capture is a one-time evidence step run by a human/controller with
  network access; `pytest` never hits the network. Captured samples are copied
  (redaction is a no-op here since public data carries no credentials) into
  `backend/tests/fixtures/` as committed replay fixtures. A small hand-crafted
  fixture set is also committed to exercise edge cases (bStock, perp-only,
  spot-only-no-margin, stale funding).
- `fapi/v1/premiumIndex` shares `lastFundingRate` / `nextFundingTime` semantics
  documented for `dapi/v1/premiumIndex` in the local docs mirror
  (`llms-full.txt:50875-50876`, and repeated at 56359-56360, 60998-60999,
  66622-66623, 81425-81426): `lastFundingRate` = the most recently *updated*
  funding rate (NOT a guaranteed prediction of the upcoming settlement);
  `nextFundingTime` = the next funding settlement time in epoch ms. The
  normalizer records this explicitly and the capture step re-verifies field
  presence against the sampled JSON before the UI labels anything.
- Public margin support is read from spot `exchangeInfo`
  `isMarginTradingAllowed` when present, else from the `permissions` /
  `permissionSets` arrays containing `MARGIN`. Absence of the field → treated as
  "no public margin indication" (→ `SPOT_ONLY_CANDIDATE`), never as a positive.
- bStock detection is heuristic + curated: a small committed curated list plus a
  symbol/name heuristic. It sets `asset_tag`, `asset_tag_confidence`, and
  `asset_tag_source`; it never silently upgrades tradability.
- Only USDT-quoted symbols are in scope (PRD: quote asset USDT only).

## Design Decisions

- **D1 — Thin adapter, pure domain.** `binance_public.py` does request/parse/
  save/normalize only; `domain/*` are pure and independently testable. Rationale
  and rejected alternatives in `11-adr.md`.
- **D2 — stdlib HTTP, no `requests`/`httpx`.** Keeps the runtime dependency
  surface at zero and avoids a signed-client shape that could later grow auth.
- **D3 — Decimal everywhere, strings at the boundary.** Every quantity/rate/
  notional is `Decimal` internally and serialized as a JSON/CSV string. No
  `float` in any numeric path.
- **D4 — Base-asset quantity is the alignment unit.** Planning aligns by base
  quantity, rounds to the coarser step across legs, then re-validates notional
  filters. Notional is display/validation only.
- **D5 — Deterministic `negative_funding_status` priority as a single pure
  function** with an explicit ordered branch and a dedicated test.
- **D6 — Funding staleness guard.** The normalizer compares `nextFundingTime`
  against the capture `data_timestamp`; if `nextFundingTime <= data_timestamp`
  the row's funding signal is flagged non-actionable/previous-period so the UI
  cannot present it as current.
- **D7 — Files before DB.** Samples and outputs are files; no SQLite.
- **D8 — Reuse the static prototype.** UI stays a single static HTML page that
  fetches the generated JSON; no build step, no framework.

Detailed rationale, alternatives, and reviewer context are in `11-adr.md`.

## Package Layout

```text
backend/
  __init__.py
  domain/
    __init__.py
    symbols.py          # SymbolInfo, join futures+spot by base/quote
    funding.py          # funding normalization + field-semantics + staleness guard
    classification.py   # route_class, asset_tag, negative_funding_status (pure)
    trading_rules.py    # parse LOT_SIZE/MARKET_LOT_SIZE/MIN_NOTIONAL/NOTIONAL; effective min notional & step
    planning.py         # base-qty alignment, step rounding, post-round notional recheck
  adapters/
    __init__.py
    binance_public.py   # request, parse, save raw JSON, normalize (public endpoints only)
  services/
    __init__.py
    public_market_discovery.py  # orchestrate capture -> rows -> json/csv
  tests/
    __init__.py
    fixtures/           # committed replay JSON (captured slice + crafted edge cases)
    test_classification.py
    test_trading_rules.py
    test_planning.py
    test_funding.py
    test_regenerate_classification.py  # replay determinism over fixtures
```

## Executable Commands (pinned; to be stored in 60-test-output.txt)

The repository currently has no `pyproject.toml`/requirements and
`DEVELOPMENT_GUIDE.md` Commands are all `TBD`. The implementer MUST create the
files below and use exactly these commands. These are the commands a later
user-approved promotion will copy into `DEVELOPMENT_GUIDE.md` (do NOT edit that
doc in this stage).

**1. `pyproject.toml` (repo root) — tool config only, no build backend needed:**

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["backend/tests"]

[tool.ruff]
target-version = "py311"
line-length = 100
src = ["backend"]

[tool.mypy]
python_version = "3.11"
files = ["backend"]
strict = true
```

**2. One-time environment setup (pinned dev tools; zero runtime deps):**

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install "pytest==8.3.*" "ruff==0.6.*" "mypy==1.11.*"
```

**3. Tests (this exact invocation is captured into `60-test-output.txt`):**

```bash
.venv/bin/python -m pytest backend/tests -q
```

**4. Lint:**

```bash
.venv/bin/python -m ruff check backend
```

**5. Typecheck:**

```bash
.venv/bin/python -m mypy backend
```

**6. Public sample capture (network step; run by human/controller, NOT by
pytest). Writes samples + `sample-index.json` + candidate outputs:**

```bash
.venv/bin/python -m backend.services.public_market_discovery
```

Because `backend/` ships `__init__.py` files and pytest sets
`pythonpath = ["."]`, `from backend.domain... import ...` resolves without any
packaging/build backend.

## Candidate Row Schema (synthesis section 5)

One row per in-scope USDⓈ-M perpetual symbol. All numeric fields are `Decimal`
internally and emitted as JSON/CSV **strings**; timestamps are epoch
milliseconds emitted as strings; enums are exact string literals.

| Field | Type (internal) | Serialized | Notes |
| --- | --- | --- | --- |
| `symbol` | str | str | e.g. `BTCUSDT` |
| `base_asset` | str | str | |
| `quote_asset` | str | str | USDT only in scope |
| `perp_status` | str | str | futures `status` (e.g. `TRADING`) |
| `spot_status` | str \| None | str \| null | spot `status` or null if no spot |
| `route_class` | enum | str | `MARGIN_SPOT_CANDIDATE`/`SPOT_ONLY_CANDIDATE`/`PERP_ONLY_EXCLUDED` |
| `asset_tag` | enum | str | `CRYPTO`/`BSTOCK`/`UNKNOWN` |
| `asset_tag_confidence` | enum | str | `HIGH`/`MEDIUM`/`LOW` |
| `asset_tag_source` | str | str | `exchangeInfo`/`curated_list`/`heuristic`/`manual_override` |
| `positive_funding_candidate` | bool | bool | true only when a spot leg exists |
| `negative_funding_status` | enum | str | see priority function |
| `current_funding_rate` | Decimal | str | from `lastFundingRate`; semantics recorded |
| `next_funding_time` | int(ms) \| None | str \| null | from `nextFundingTime` |
| `funding_history_summary` | Decimal-map | obj of str | e.g. recent-avg / min / max as strings |
| `futures_min_notional` | Decimal \| None | str \| null | from futures `MIN_NOTIONAL` |
| `spot_min_notional` | Decimal \| None | str \| null | from spot `MIN_NOTIONAL`/`NOTIONAL` |
| `effective_min_notional` | Decimal \| None | str \| null | stricter across legs (max), no uplift here |
| `futures_step_size` | Decimal \| None | str \| null | from futures `LOT_SIZE`/`MARKET_LOT_SIZE` |
| `spot_step_size` | Decimal \| None | str \| null | from spot `LOT_SIZE`/`MARKET_LOT_SIZE` |
| `data_timestamp` | int(ms) | str | capture time (UTC) |
| `source_files` | list[str] | list[str] | relative paths under the sample dir |
| `exclusion_reason` | str \| None | str \| null | e.g. `NO_SPOT_MARKET` for perp-only |
| `funding_signal_status` | enum | str | `CURRENT_ACTIONABLE`/`STALE_OR_PREVIOUS_PERIOD` (D6; drives UI labelling) |

`funding_signal_status` plus a top-level `funding_field_semantics` descriptor
(chosen field = `lastFundingRate` = "most recently updated funding rate";
`nextFundingTime` = "next funding settlement time, epoch ms"; with the docs
citation) are the only additions to the section-5 field list; they exist so the
UI cannot mislabel stale data (AC-07). All other fields are exactly the
section-5 list.

### `negative_funding_status` priority (deterministic)

```text
if route_class == PERP_ONLY_EXCLUDED:      DISABLED_PERP_ONLY
elif asset_tag == BSTOCK:                  DISABLED_BSTOCK
elif route_class == SPOT_ONLY_CANDIDATE:   DISABLED_SPOT_ONLY
else:  # remaining MARGIN_SPOT_CANDIDATE   PRIVATE_BORROW_VALIDATION_REQUIRED
```

Priority order: `PERP_ONLY > BSTOCK > SPOT_ONLY > PRIVATE_BORROW_VALIDATION_REQUIRED`.

## Sample Capture And Indexing

Directory: `reports/api-samples/public-market/<timestamp>/` where `<timestamp>`
is compact UTC, e.g. `20260703T101500Z`.

Files (only those actually fetched are written; depth is optional):

```text
fapi_exchange_info.json
fapi_premium_index.json
fapi_funding_rate_<SYMBOL>.json   # per ranked/selected symbol
spot_exchange_info.json
fapi_depth_<SYMBOL>.json          # optional
spot_depth_<SYMBOL>.json          # optional
sample-index.json
candidate-classification.json
candidate-classification.csv
```

`sample-index.json` records, per saved file:

- `endpoint` (e.g. `GET /fapi/v1/exchangeInfo`) and full request `url`
  (public host + path + query; no credentials, no headers),
- `file` (relative name), `http_status`, `byte_size`, `sha256`,
- `symbol` for per-symbol files,
- top-level `captured_at` (UTC ISO-8601), `data_timestamp` (epoch ms), and the
  `funding_field_semantics` descriptor.

The adapter asserts that no request carries `X-MBX-APIKEY`, `signature`,
`timestamp`, or `recvWindow`, and that the host is a public futures/spot host
(fail-closed if a non-public path is ever passed).

## Task Breakdown

- **T1 Adapter** `binance_public.py`: GET the six public endpoints via stdlib,
  save raw JSON, build `sample-index.json`. → verify: capture writes the
  documented files; `sample-index.json` sha256s match; no credential fields in
  any request.
- **T2 Trading rules** `trading_rules.py`: parse `LOT_SIZE`,
  `MARKET_LOT_SIZE`, `MIN_NOTIONAL`, `NOTIONAL`; compute `effective_min_notional`
  (stricter/max across legs) and coarser step. → verify: `test_trading_rules.py`
  over crafted filters incl. missing-filter and futures-vs-spot mismatch.
- **T3 Funding** `funding.py`: normalize `lastFundingRate`/`nextFundingTime`,
  summarize `fundingRate` history (Decimal), set `funding_signal_status` via the
  staleness guard, and emit the `funding_field_semantics` descriptor. → verify:
  `test_funding.py` incl. a `nextFundingTime <= data_timestamp` stale case.
- **T4 Symbols + classification** `symbols.py` + `classification.py`: join
  futures↔spot; compute `route_class`, `asset_tag`(+confidence/source),
  `positive_funding_candidate`, `negative_funding_status`. → verify:
  `test_classification.py` covers all three route classes, bStock, and the full
  priority order.
- **T5 Planning** `planning.py`: base-qty per round; min-notional correction
  `max(required_min_notional)*1.02` with round-count recalculation; coarser
  step rounding; post-round notional recheck; merge sub-min final remainder. →
  verify: `test_planning.py` with base-qty alignment, step rounding, and
  post-rounding notional rechecks (deterministic).
- **T6 Service** `public_market_discovery.py`: orchestrate capture/fixtures →
  rows → `candidate-classification.{json,csv}`. → verify:
  `test_regenerate_classification.py` regenerates identical rows from committed
  fixtures (AC-02 determinism).
- **T7 UI** update `prototypes/fake-ui/index.html`: Market Overview, Funding
  Opportunities (sortable), Candidate Detail (raw sample refs, funding-field
  labelling), Manual Open Preview (simulation-only banner, base-qty planning,
  min-notional correction, 10-minute timeout + hard-slippage rule text). →
  verify: page loads generated JSON and renders counts/rows; manual-open marked
  simulation-only.
- **T8 Config + evidence**: add `pyproject.toml`; run tests/lint/typecheck;
  capture into `60-test-output.txt`; write `20-implementation.md`,
  `70-handoff.md`; update `status.json`.

## Test Strategy

- **Unit tests (pure, offline):** `test_classification.py`,
  `test_trading_rules.py`, `test_planning.py`, `test_funding.py`. Cover the five
  PRD-required areas: classification, trading-rule parsing, funding-field
  normalization, minimum-notional selection, planning preview (AC-10, P9).
- **Integration tests:** none against the live network in CI; the capture
  command is a manual evidence step run once by a human/controller.
- **Replay/backtest checks:** `test_regenerate_classification.py` rebuilds the
  candidate table from committed fixtures and asserts stable output (AC-02).
  A serialization guard test asserts every numeric field in the emitted JSON is
  a string and round-trips through `Decimal` (AC-18). A constraint-guard test
  asserts the adapter rejects/omits any credentialed field and only targets
  public hosts (supports AC-11..AC-17).
- **Manual checks:** open the updated prototype against a captured
  `candidate-classification.json`; confirm the four screens and the
  simulation-only labelling on manual-open.

## Risks

- **R1 Network variability / rate limits during capture.** Mitigation: capture
  once, commit a fixture slice; tests never call the network.
- **R2 Funding-field mislabelling.** Mitigation: staleness guard (D6),
  recorded semantics descriptor, docs citation, and a stale-case test (AC-07).
- **R3 Spot margin indicator variance** (`isMarginTradingAllowed` vs
  `permissions`/`permissionSets`). Mitigation: check both, treat absence as no
  margin, fixture cases for each shape.
- **R4 bStock false negatives/positives.** Mitigation: curated list + heuristic,
  explicit `asset_tag_confidence`/`asset_tag_source`, never auto-upgrades
  tradability; negative funding disabled for BSTOCK regardless.
- **R5 Scope creep toward private endpoints.** Mitigation: adapter fail-closed
  on non-public paths; constraint-guard test; file boundaries in `00-task.md`.
- **R6 Decimal/float leakage.** Mitigation: no `float` in numeric paths;
  serialization guard test; mypy strict.

## Raw Artifact Requirements For Review

- `00-task.md`
- `10-design.md`
- `11-adr.md`
- `reports/agent-runs/2026-07-initial-direction/06-direction-synthesis.md`
- `docs/product/PRD.md` (Phase 1 sections)
- git diff or patch of `backend/**`, `pyproject.toml`, `prototypes/fake-ui/**`
- `20-implementation.md` (implementation report)
- `60-test-output.txt` (exact pytest/ruff/mypy invocations and output)
- `reports/api-samples/public-market/<timestamp>/` samples + `sample-index.json`
  + `candidate-classification.{json,csv}`
- relevant source files under `backend/`
