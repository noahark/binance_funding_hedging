# Stage Task

## Stage ID

`2026-07-public-market-discovery`

## Goal

Implement Phase 1 public market discovery, deterministic candidate
classification, and a simulation-only funding-opportunity UI, exactly as frozen
in `reports/agent-runs/2026-07-initial-direction/06-direction-synthesis.md`
(section 10 deliverables/acceptance, section 7 spine, section 5 row schema,
section 3 route classes) and promoted into `docs/product/PRD.md` (Phase 1 scope,
Public Route Classification, Phase 1 Acceptance Criteria).

Concretely, this stage must:

1. Add a thin public Binance adapter (`backend/adapters/binance_public.py`) that
   requests, parses, saves raw JSON, and normalizes ONLY public endpoints.
2. Capture public samples under
   `reports/api-samples/public-market/<timestamp>/` with a `sample-index.json`.
3. Join USDⓈ-M perpetuals against spot exchangeInfo and produce a deterministic
   route-classified candidate table
   (`candidate-classification.json` + `candidate-classification.csv`) using the
   section-5 row schema, with all amounts/rates/notionals as `Decimal`
   serialized externally as strings.
4. Normalize funding fields and record their chosen semantics so the UI cannot
   mislabel stale/previous-period data as a current actionable funding signal.
5. Provide pure classifier, trading-rule normalizer, and planning-preview
   functions with fixture-based `pytest` tests.
6. Update the existing `prototypes/fake-ui/` prototype to render the generated
   public-market data and clearly mark the manual-open preview as simulation
   only.

## Non-Goals

- No API keys, signed requests, `X-MBX-APIKEY`, timestamp/signature, or
  `recvWindow` handling.
- No private/PAPI/account/user-stream/listenKey/order/borrow/repay/transfer/
  fee-burn code path anywhere in the diff.
- No real trading, no automatic open, no automatic close, no leg repair.
- No websocket subscription (public depth is a plain REST snapshot only, and
  only if sampled).
- No database / SQLite (persist samples as files first).
- No React migration; reuse the existing static HTML prototype.
- No new domain math, fee/rebate accounting, or position reconciliation (those
  are later phases).
- Do NOT promote commands into `docs/development/DEVELOPMENT_GUIDE.md` in this
  stage; promotion is a separate user-gated step.
- No edits to frozen direction/design artifacts, `AGENTS.md`, workflow YAML,
  schemas, or the registry.

## File Boundaries

Allowed files (implementation stage):

- `backend/**` — new package: `domain/{symbols,funding,classification,trading_rules,planning}.py`,
  `adapters/binance_public.py`, `services/public_market_discovery.py`,
  `tests/**` (including `tests/fixtures/**` committed replay fixtures).
- `pyproject.toml` — new; tool config (pytest `pythonpath`, ruff, mypy) only.
- `reports/api-samples/public-market/**` — generated public samples and
  `sample-index.json`, plus generated `candidate-classification.{json,csv}`.
- `prototypes/fake-ui/**` — UI update for public-market screens.
- `reports/agent-runs/2026-07-public-market-discovery/20-implementation.md`
- `reports/agent-runs/2026-07-public-market-discovery/60-test-output.txt`
- `reports/agent-runs/2026-07-public-market-discovery/70-handoff.md`
- `reports/agent-runs/2026-07-public-market-discovery/status.json`

Forbidden / out-of-scope files:

- `reports/agent-runs/2026-07-public-market-discovery/00-task.md`,
  `10-design.md`, `11-adr.md` — designer-owned, frozen after this stage-design.
- `docs/**` — including `docs/development/DEVELOPMENT_GUIDE.md`,
  `docs/product/PRD.md`, `docs/architecture/**`. Canonical docs change only via
  a separate user-approved promotion step.
- `AGENTS.md`, `agents/**`, `workflows/**`, `schemas/**`,
  `harness-manifest.yaml`, `.harness-version`.
- `reports/agent-runs/2026-07-initial-direction/**` and any other stage
  directory.
- `llms-full.txt`, `币安套费率策略，逐仓杠杆.js` (read-only reference inputs;
  gitignored, keep uncommitted).
- Anywhere: any signed, private, PAPI, user-stream, order, borrow, repay,
  transfer, or fee-burn path.

## Acceptance Criteria

Every criterion is traceable to its source: `[S#]` = synthesis section 10
"Acceptance should require" list; `[P#]` = PRD "Phase 1 Acceptance Criteria".
No source criterion is dropped; overlapping S/P items are merged and tagged with
both sources.

- **AC-01** Public discovery uses no API key and writes raw JSON samples under
  `reports/api-samples/public-market/<timestamp>/`, referenced by a
  `sample-index.json`. `[S1][P1]`
- **AC-02** Candidate classification can be regenerated deterministically from
  the saved public samples (proven by a replay test over committed fixtures).
  `[S2][P2]`
- **AC-03** The candidate table separates `MARGIN_SPOT_CANDIDATE`,
  `SPOT_ONLY_CANDIDATE`, and `PERP_ONLY_EXCLUDED` via a `route_class` field.
  `[S3][P3]`
- **AC-04** bStocks / potential bStocks are tagged with `asset_tag=BSTOCK`,
  plus `asset_tag_confidence` and `asset_tag_source`. `[S4][P4]`
- **AC-05** Positive and negative funding statuses are explicit
  (`positive_funding_candidate`, `negative_funding_status`) on every row.
  `[S5][P5]`
- **AC-06** `negative_funding_status` follows the deterministic priority
  `PERP_ONLY_EXCLUDED → DISABLED_PERP_ONLY` >
  `asset_tag=BSTOCK → DISABLED_BSTOCK` >
  `SPOT_ONLY_CANDIDATE → DISABLED_SPOT_ONLY` >
  remaining `MARGIN_SPOT_CANDIDATE → PRIVATE_BORROW_VALIDATION_REQUIRED`, with a
  dedicated ordered-priority test. `[S6][P5]`
- **AC-07** Funding-rate field semantics for `premiumIndex.lastFundingRate` and
  `nextFundingTime` are documented from sampled files and/or the local docs
  mirror, recorded by the normalizer, and the UI labels the chosen funding
  fields accurately (stale/previous-period vs current-actionable). `[S7][P6]`
- **AC-08** Planning preview aligns hedge size by base-asset quantity, rounds to
  the coarser required step size across both legs, and rechecks both legs
  against notional filters after rounding, with deterministic tests. `[S8][P7]`
- **AC-09** UI prototype shows the public market discovery screens (Market
  Overview, Funding Opportunities, Candidate Detail, Manual Open Preview) with
  realistic public sample data and clearly labels manual open as
  simulation-only. `[P8]`
- **AC-10** Tests cover classification, trading-rule parsing, funding-field
  normalization, minimum-notional selection, and planning preview, and all pass.
  `[S9][P9]`
- **AC-11** No API credentials are added. `[P10]`
- **AC-12** No private account endpoints or user data streams are used. `[P11]`
- **AC-13** No signed endpoint is used. `[S10][P12]`
- **AC-14** No order, borrow, repay, transfer, or fee-burn endpoint is
  implemented. `[S10][P13]`
- **AC-15** No real trading code is introduced. `[P14]`
- **AC-16** No automatic open or close is introduced. `[P15]`
- **AC-17** No private websocket / listenKey path exists in the diff. `[S10]`
- **AC-18** All amounts, quantities, rates, and notionals use `Decimal` and are
  serialized externally as strings. (Hard constraint; verified by schema + a
  serialization test.)

## Human Gates

- No new product/domain/credential/deploy approval is required for this stage;
  the direction was already user-approved and promoted to the PRD
  (commit `ef6afc5`).
- Standing hard constraints act as execution gates. Any need to (a) touch a
  private/signed/credentialed endpoint, (b) add an API key, (c) introduce a
  database, or (d) promote commands into `docs/development/DEVELOPMENT_GUIDE.md`
  or any other canonical doc, must STOP and request human approval rather than
  proceed.
- Controller checkpoint confirmation is requested after stage-design and before
  implementation (per `00-intake.md`).

## Designer

- Provider: `claude` (provider_identity: `anthropic`)
- Model: `claude-opus-4-8`
- Skill: `software_architect`
- Date: 2026-07-02
