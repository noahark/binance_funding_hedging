# Stage ADR

## Context

This is the first real implementation loop after the direction round. The
approved synthesis (`2026-07-initial-direction/06-direction-synthesis.md`) and
the promoted PRD (`docs/product/PRD.md`, commit `ef6afc5`) freeze Phase 1 as
public-market discovery + candidate classification + a simulation-only
funding-opportunity UI, with strict hard constraints (public endpoints only,
`Decimal`-as-strings, base-asset alignment, deterministic negative-funding
priority, and funding-field-semantics evidence).

The repository has NO backend, NO `pyproject.toml`/requirements, and
`docs/development/DEVELOPMENT_GUIDE.md` lists Test/Lint/Typecheck as `TBD`. So
this stage must also pin down the executable command surface (recorded in
`10-design.md`; NOT yet promoted into the guide, which is a separate gated step).

## Decision

Ship a thin, file-first Python `backend/` package:

- One network boundary (`adapters/binance_public.py`) that only GETs the six
  public endpoints via stdlib `urllib.request`, saves raw JSON under
  `reports/api-samples/public-market/<timestamp>/`, and builds `sample-index.json`.
- Pure `domain/` functions (`symbols`, `funding`, `classification`,
  `trading_rules`, `planning`) that operate on parsed data, use `Decimal`
  everywhere, and are covered by offline fixture tests.
- A `services/public_market_discovery.py` orchestrator that emits
  `candidate-classification.{json,csv}` using the section-5 row schema.
- The existing static `prototypes/fake-ui/index.html` updated to render the
  generated JSON across four read-only screens, manual-open labelled
  simulation-only.

Pinned toolchain: Python 3.11; `pyproject.toml` for tool config only
(pytest `pythonpath=["."]`, ruff, mypy strict); zero runtime third-party deps;
dev deps `pytest==8.3.*`, `ruff==0.6.*`, `mypy==1.11.*`. Exact commands live in
`10-design.md`.

## Alternatives Considered

- **`requests`/`httpx` HTTP client.**
  - Why rejected: adds a runtime dependency and a client shape that naturally
    grows auth headers/signing; stdlib `urllib.request` is enough for a handful
    of public GETs and keeps the "no signed path" boundary obvious.
- **Packaged install (`pip install -e .` with a build backend).**
  - Why rejected: unnecessary for a single-repo package; pytest `pythonpath`
    resolves `backend.*` imports without a build backend, keeping setup minimal.
- **Introduce SQLite now for the candidate table.**
  - Why rejected: synthesis explicitly says persist samples as files before a
    database; JSON/CSV outputs are sufficient and reviewable.
- **Rebuild the UI in React/TypeScript now.**
  - Why rejected: React migration is deferred (synthesis 8.2); reuse the static
    prototype and avoid a build toolchain in this stage.
- **Trust `lastFundingRate` as the current actionable funding rate.**
  - Why rejected: the local docs mirror documents it as the "most recently
    updated" rate, not a guaranteed next-settlement prediction; labelling it as
    current could mislead the operator. Hence the staleness guard and recorded
    semantics.
- **Treat public margin support as a proven borrow route.**
  - Why rejected: public `isMarginTradingAllowed` only indicates a candidate;
    borrowability requires later private discovery. Negative funding stays
    `PRIVATE_BORROW_VALIDATION_REQUIRED` for `MARGIN_SPOT_CANDIDATE`.
- **Live-network tests in CI.**
  - Why rejected: non-deterministic and rate-limited; capture once, commit
    fixtures, replay offline.

## Tradeoffs

- **Stdlib HTTP over a client library.**
  - Benefit: zero runtime deps, unmistakable public-only boundary.
  - Cost: slightly more manual request/error handling code.
- **File outputs over a DB.**
  - Benefit: reviewable evidence, simple regeneration/replay.
  - Cost: no indexed querying (not needed in Phase 1).
- **Two extra fields (`funding_signal_status`, `funding_field_semantics`) beyond
  the section-5 list.**
  - Benefit: satisfies the funding-semantics hard constraint and prevents UI
    mislabelling.
  - Cost: a small superset of the frozen schema (called out for reviewers).
- **Static HTML UI.**
  - Benefit: no build step, fast to review, matches "reuse fake UI".
  - Cost: less componentized than a framework UI (acceptable for a prototype).

## Edge Cases Or Constraints

- **Hard constraint — public endpoints only.** Allowed: `GET /fapi/v1/exchangeInfo`,
  `GET /fapi/v1/premiumIndex`, `GET /fapi/v1/fundingRate`,
  `GET /api/v3/exchangeInfo`, optional `GET /fapi/v1/depth`, `GET /api/v3/depth`.
  No API key; no signed/private/PAPI/user-stream/order/borrow/repay/transfer/
  fee-burn path anywhere. Adapter fails closed on any non-public path.
- **Hard constraint — Decimal-as-strings.** All amounts/quantities/rates/
  notionals are `Decimal` internally, serialized as strings.
- **Hard constraint — base-asset quantity alignment.** Planning aligns by base
  quantity; notional is display/filter-validation only.
- **Hard constraint — deterministic negative-funding priority.**
  `PERP_ONLY_EXCLUDED → DISABLED_PERP_ONLY` > `BSTOCK → DISABLED_BSTOCK` >
  `SPOT_ONLY_CANDIDATE → DISABLED_SPOT_ONLY` >
  `MARGIN_SPOT_CANDIDATE → PRIVATE_BORROW_VALIDATION_REQUIRED`.
- **Hard constraint — funding-field semantics.** `lastFundingRate` /
  `nextFundingTime` semantics are validated from sampled files and/or the local
  docs mirror (`llms-full.txt`, which is gitignored/on-disk — not assumed) and
  recorded by the normalizer; the UI must not mislabel stale/previous-period
  data as current-actionable.
- **Missing filters / no spot market.** Perp-only symbols → `PERP_ONLY_EXCLUDED`
  with `exclusion_reason=NO_SPOT_MARKET`; missing notional/step filters serialize
  as null and never crash classification.
- **Rework limit 3; no product/domain/credential decisions in scope** — those
  were settled in the direction round.

## Links To Prior Direction

- Direction synthesis:
  `reports/agent-runs/2026-07-initial-direction/06-direction-synthesis.md`
  (section 3 route classes, section 5 row schema, section 6 UI, section 7 spine,
  section 10 deliverables/acceptance).
- Product docs: `docs/product/PRD.md` — Phase 1 scope, Public Route
  Classification, Manual Execution Flow, Interface Discovery > Phase 1 Public
  Market Discovery, Phase 1 Acceptance Criteria.
- Stage intake: `reports/agent-runs/2026-07-public-market-discovery/00-intake.md`.

## Reviewer Notes

Things that may look odd in the diff but are intentional:

- **stdlib `urllib.request`, not `requests`/`httpx`** — deliberate, to keep zero
  runtime deps and an obvious public-only boundary (D2).
- **No `[project]`/build backend in `pyproject.toml`** — intentional; imports
  resolve via pytest `pythonpath=["."]`. The file carries tool config only.
- **`DEVELOPMENT_GUIDE.md` is left untouched** even though it still says `TBD`.
  Promoting the pinned commands into it is a separate user-gated step; editing
  canonical docs here would violate the file boundaries in `00-task.md`.
- **Schema superset:** the candidate rows add `funding_signal_status` and a
  top-level `funding_field_semantics` descriptor on top of the section-5 field
  list, solely to satisfy the funding-semantics hard constraint.
- **`llms-full.txt` is cited by line number but not committed** (gitignored,
  on-disk reference). Field semantics are re-verified against the sampled JSON at
  capture time, so the design does not depend on the mirror being present.
- **Committed fixtures include hand-crafted edge cases** (bStock, perp-only,
  spot-only-no-margin, stale funding) alongside a captured real slice, so the
  determinism/priority/staleness tests are self-contained and offline.
- **Manual-open UI is simulation-only** and does not read any credential or
  private data; the 10-minute timeout + hard-slippage text is a labelled future
  execution rule, not live behavior.
- **Reviewer isolation:** designer provider is Anthropic (`claude-opus-4-8`);
  Codex is kept clean for review-2 primary to preserve provider-level isolation.
