# Stage Task: 2026-07-public-market-impl-v1

Authoritative for file boundaries and acceptance in this stage. Derived from the
approved development breakdown
(`fable5-detail-breakdown.md`). When this file and the breakdown disagree, the
user-approved direction synthesis, `docs/product/PRD.md`, and
`docs/api/public-market-contract.md` are higher authority; surface the conflict,
do not silently pick.

## Goal

Turn the frozen `public-market-snapshot/v1` contract into a runnable system:

1. Task A — Claude-GLM implements a backend snapshot service that fetches public
   Binance endpoints, normalizes/classifies, and serves schema-valid JSON at
   `GET /api/public-market/snapshot`.
2. Task B — Kimi implements a frontend market-table workstation page that
   consumes only that contract.
3. Task C — controller runs scripted integration verification (no product code).

Acceptance boundary for the stage: Task A and Task B each pass task-level
review-1, plus reproducible integration evidence (Task C), plus one stage-level
review-2.

## Non-goals (forbidden this stage)

- Any signed endpoint, API key, private account endpoint, or user data stream.
- Any order, borrow, repay, transfer, or close-position code path.
- The open/close planning calculator UI (PRD §6.4 quantity alignment, notional
  checks, round count, slippage). Pure domain logic needing its own contract
  freeze; this stage is market-table display only.
- Manual-open ticket, planner prototype, order button, leg-prompt, position
  management entry. The frontend must not stub these interactions ahead of time.
- WebSocket, depth/order-book, auto-refresh polling (a manual refresh button is
  allowed).
- Database. File cache + in-memory only.
- Deployment, process supervisor, public exposure. The service binds
  `127.0.0.1` only.
- Changing the frozen contract: `schemas/api/public-market/**`,
  `docs/api/public-market-contract.md`, and
  `reports/api-samples/public-market-contract-v2/**` are read-only. If a needed
  field is missing, mark the task blocked and request a contract update; do not
  silently modify the frozen artifacts.

## Ownership and file boundaries

| Path | Owner | Rule |
|---|---|---|
| `backend/**` | Claude-GLM (Task A) | Kimi must not write here. |
| `frontend/**` | Kimi (Task B) | Claude-GLM may add only a static-host route pointing at this dir; must not edit its contents. |
| `schemas/api/public-market/**` | frozen | Both read-only; a change = contract change → task blocked. |
| `docs/api/public-market-contract.md` | frozen | Same as above. |
| `reports/api-samples/public-market-contract-v2/**` | frozen evidence | Read-only. |
| `prototypes/fake-ui/index.html` | frozen reference | Read-only baseline for the Chinese workstation visual style. |
| `reports/agent-runs/2026-07-public-market-impl-v1/**` | controller | Per-owner report files (`20-implementation-backend.md`, `20-implementation-frontend.md`, etc.). |
| `docs/`, `agents/`, `workflows/`, `scripts/` | untouched this stage | Harness problems go to escalation, not opportunistic fixes. |

A boundary crossing is REWORK regardless of code quality.

## Task A — backend snapshot service (Claude-GLM, `senior_developer`)

Scope: `backend/**` plus `reports/agent-runs/2026-07-public-market-impl-v1/20-implementation-backend.md`.

Deliverables:

- A `backend/` Python package. Dependencies minimized: standard library +
  `jsonschema`. HTTP framework: standard-library `http.server` was chosen (see
  `11-adr.md`); FastAPI/uvicorn is not used. Tests use `pytest==8.3.*` (version
  pinned — the previous Grok run self-tested on pytest 9.x).
- Data flow: fetch (`/fapi/v1/exchangeInfo`, `/fapi/v1/premiumIndex`,
  `/fapi/v1/fundingRate`, `/api/v3/exchangeInfo`) → normalize → classify →
  assemble snapshot → validate against the frozen schema before serving; on
  validation failure return HTTP 503 and log a warning. Never serve an
  invalid snapshot.
- Behavior rules (all sourced from the frozen contract/PRD; these are the review
  checkpoints):
  - Include only futures with `status == "TRADING"` and `contractType` in
    `{PERPETUAL, TRADIFI_PERPETUAL}`.
  - `TRADIFI_PERPETUAL` → `asset_tag=BSTOCK`; `PERPETUAL` → `CRYPTO`;
    otherwise `UNKNOWN`. `asset_tag` is independent of `route_class`.
  - `route_class`: spot leg present and `isMarginTradingAllowed=true` →
    `MARGIN_SPOT_CANDIDATE`; spot present, margin not allowed →
    `SPOT_ONLY_CANDIDATE`; no spot → `PERP_ONLY_EXCLUDED`. Keep
    `margin_public.source = "unverified"`.
  - `negative_funding_status` priority: PERP_ONLY → BSTOCK → SPOT_ONLY →
    PRIVATE_BORROW_VALIDATION_REQUIRED. Implement as an explicit ordered
    sequence; the order is not interchangeable.
  - All decimal fields are handled as `Decimal` internally and serialized as
    strings. `float()` must not appear on any price/rate/quantity path.
  - `funding_history`: take only the top-N symbols by `|last_funding_rate|`
    (default N=20, configurable). Others get an empty array. This bounds
    `/fapi/v1/fundingRate` call volume. Default 20 is design-confirmed; do not
    change it without an explicit user change. The implementation report must
    record observed request counts and rate-limit headroom.
  - `summary` counts must equal aggregation over `rows`; never computed twice
    and left unchecked.
  - Disk cache with configurable TTL (default 60s). `--offline` reads the frozen
    raw-sample directory. Tests and CI are always offline; no network.
  - The three contract-stage warnings (margin unverified, `lastFundingRate`
    semantics, BSTOCK no spot leg) must be preserved verbatim in the output.
- Tests: normalize/classify pure-function unit tests (frozen raw samples as
  fixtures, covering non-TRADING, TRADIFI_PERPETUAL, no-spot-leg edges),
  schema positive/negative validation, and one offline end-to-end run.

Acceptance for Task A: offline tests pass; the served offline snapshot validates
against `schemas/api/public-market/snapshot.schema.json` with 0 errors; warnings
preserved; no `float()` on decimal paths; `summary` matches `rows` aggregation.

## Task B — frontend market table (Kimi, `minimal_change_engineer`)

Scope: `frontend/**` plus `reports/agent-runs/2026-07-public-market-impl-v1/20-implementation-frontend.md`.

Full rules and dispatch prompt: see `fable5-detail-breakdown.md` §4 Task B and
`reports/agent-runs/2026-07-public-market-impl-v1/task-b-kimi-frontend.prompt.md`.

Key constraints: build-tool-free static page; data source is only
`fetch('/api/public-market/snapshot')` (same-origin via backend static host) and
a fixture mode that is a byte-level copy of the frozen normalized sample; the
formal local page must load real data from the same-origin backend API (fixture
is for offline tests / no-backend self-checks only). UI copy for
`last_funding_rate` must read "最近更新的资金费率", never "已结算"/"预测".
`warnings[]` must be visible. BSTOCK rows visibly tagged; PERP_ONLY_EXCLUDED
filterable by default. No ticket/planner/order/account/position interactions.

## Task C — integration verification (controller, no product code)

Scope: `reports/agent-runs/2026-07-public-market-impl-v1/60-test-output.txt`
and a timestamped snapshot response under the stage dir.

Start the backend (offline or live, record which) →
`curl http://127.0.0.1:<port>/api/public-market/snapshot` saved as raw response
→ `jsonschema` validates 0 errors → load the frontend page from the same origin
and confirm it renders from that endpoint. All commands and output go into
`60-test-output.txt`, reproducible. Run after Tasks A and B pass their
task-level review-1.

## Fingerprint protocol (unchanged)

Single standard protocol; applied at two scopes (task-level and stage-level),
never a second protocol:

```text
diff_fingerprint = head_sha + ":" + sha256(git diff --binary <base_sha>..<head_sha> -- . ":(exclude)reports/agent-runs/<stage-id>/status.json")
```

- Task-level: each of A/B records its own `base_sha`/`head_sha`/`diff_fingerprint`
  in `status.json.tasks.<id>` over its owner-scoped commit range, used at
  task-level review-1.
- Stage-level: the top-level `status.json` `base_sha`/`head_sha`/`diff_fingerprint`
  covers the whole stage implementation diff (backend + frontend + integration
  evidence) and is the value review-2 and `pre-accept` bind to. Per
  `scripts/validate-stage.py`, `review_1`/`review_2`/top-level fingerprints must
  match for pre-accept.

本地北京时间: 2026-07-03 20:30:00 CST
下一步模型: Claude-GLM (controller)
下一步任务: Build `status.json` task records (A/B/C) and the design/ADR files.
