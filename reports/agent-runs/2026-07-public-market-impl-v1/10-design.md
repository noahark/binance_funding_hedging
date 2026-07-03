# Stage Design: 2026-07-public-market-impl-v1

Designer of record: this stage's design is the approved Fable5 development
breakdown (`fable5-detail-breakdown.md`). This file records the derived backend
architecture and the integration contract between Task A and Task B. It is
review evidence, not higher authority than the user-approved synthesis/PRD.

## Backend architecture (Task A)

Layered, dependency-light. Public-data-only; binds `127.0.0.1`.

```text
backend/
  __init__.py
  config.py            # defaults: top_n=20, cache_ttl=60s, bind 127.0.0.1:8787,
                       #   offline fixture dir = frozen raw sample dir
  adapters/
    binance_public.py  # fetch_raw(): live (urllib, no key) OR offline (read
                       #   frozen raw JSON dir). Returns raw dicts. Decimal-safe:
                       #   never converts price/rate/quantity to float.
  domain/
    normalize.py       # pure functions: asset_tag_for, filter_of, iso_from_ms,
                       #   to_decimal_string. No I/O.
    classify.py        # pure functions: classify_route, negative_funding_status.
                       #   Explicit ordered priority; unit-tested.
    snapshot.py        # build_rows(raw) -> list[row]; assemble_snapshot() ->
                       #   snapshot dict; summary aggregated from rows and
                       #   asserted equal.
  services/
    snapshot_service.py# build_snapshot(): fetch -> normalize/classify ->
                       #   assemble -> jsonschema-validate (raise on invalid).
                       #   Disk cache keyed by source_sample_id / data_time.
  app/
    server.py          # http.server.ThreadingHTTPServer on 127.0.0.1.
                       #   GET /api/public-market/snapshot -> snapshot or 503.
                       #   GET / and static assets -> frontend/ (Task B).
  tests/               # pytest==8.3.*; always offline.
```

Data flow:

```text
raw (4 endpoints) --normalize--> rows --classify--> rows w/ route+status
   --assemble--> snapshot --jsonschema.validate--> serve / cache
```

- Normalization reproduces the field mapping proven in the frozen
  `build-normalized-sample.py`: futures `min_notional` from
  `filterType=MIN_NOTIONAL` key `notional`; spot `min_notional` from
  `filterType=NOTIONAL` key `minNotional`; `step_size` from `LOT_SIZE.stepSize`.
  Decimal fields are passed through as strings from raw JSON (already strings in
  Binance output); `Decimal` is used wherever arithmetic is unavoidable.
- `data_time` is derived from `max(premiumIndex.time)` and rendered as second
  ISO via integer division of the ms epoch (no float on the time path either).
- `funding_history`: rank futures symbols by `abs(last_funding_rate)`; fetch
  `/fapi/v1/fundingRate` only for the top-N (default 20); others get `[]`.
  Offline mode can only fulfill history for symbols whose funding-rate fixture
  exists; missing history stays `[]`.
- Cache: snapshot cached on disk under a stage-local cache dir with TTL
  (default 60s); `generated_at`/`data_time` reflect real fetch time so the
  frontend can show data age, never "real-time".

## Frontend contract (Task B)

- Single same-origin endpoint: `GET /api/public-market/snapshot`.
- The backend statically hosts `frontend/` at `/` so the page and API share an
  origin (no CORS).
- Fixture mode is a byte-level copy of the frozen normalized snapshot for
  offline/no-backend self-checks; the formal local page must hit the live
  same-origin endpoint.
- The frontend must not invent classification/conversion beyond display
  formatting; any missing contract field → blocked + contract-update request.

## Integration point (Task C)

Backend serves API + static frontend on one `127.0.0.1` port. Integration
verification curls the endpoint, validates the response against the schema, and
loads the page to confirm it renders from the endpoint. All scripted; no product
code in Task C.

## Review focus (carried from breakdown §6)

1. Decimal discipline — any `float()` on a price/rate/quantity path is P1.
2. `negative_funding_status` priority order must be an explicit sequence.
3. Non-TRADING symbol leakage (the prior Grok failure mode) must have a test.
4. `summary` vs `rows` consistency must be asserted, not assumed.
5. Frontend must not reinterpret `lastFundingRate` semantics.
6. `/fapi/v1/fundingRate` volume must be bounded by top-N + cache; report counts.
7. `data_time`/`generated_at` must reflect real fetch time, not "real-time".
8. Any non-offline network in tests is REWORK.
9. `__pycache__`/`.pyc` must stay out of the diff (already in `.gitignore`).

本地北京时间: 2026-07-03 20:30:00 CST
下一步模型: Claude-GLM (controller)
下一步任务: Finalize `11-adr.md`, then build `status.json`.
