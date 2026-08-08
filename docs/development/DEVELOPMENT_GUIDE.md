# Development Guide

Status: as-built hedge execution system with live order, borrow, and asset-transfer paths, 2026-08-08. Current runtime state and live risks: `PROJECT_STATE.md`.

This file is the canonical approved development guide for the project.

Model drafts must not be written here directly. Drafts belong in
`reports/agent-runs/<stage-id>/` and are promoted here only after user approval.

## Project Layout

- `docs/product/PRD.md`: approved product requirements.
- `docs/api/`: approved backend-to-frontend API contracts.
- `schemas/api/`: JSON schemas for API payloads and sample validation.
- `backend/`: stdlib HTTP server, Binance adapters, normalization, hedge-open
  task execution (order/close), borrow tasks, ledger flow, asset transfer,
  private account enrichment, and tests.
- `frontend/`: same-origin static workstation UI and self-check script.
- `reports/agent-runs/<stage-id>/`: stage blackboard, model handoffs, reviews,
  and raw transcripts.
- `reports/archives/`: abandoned or superseded implementation evidence. Archive
  content is not an active implementation base.
- `scripts/run-server.sh`: local server launcher that loads `.env` when present
  and then runs `python -m backend.app.server`.

## Environment

The current application is a lightweight Python stdlib backend plus static
frontend. Runtime defaults bind to `127.0.0.1:8787` and can run without Binance
credentials by using public endpoints or offline fixtures.

Useful environment variables:

- `APP_BIND_HOST` / `FUNDING_HEDGING_BIND_HOST`: server host.
- `APP_BIND_PORT` / `FUNDING_HEDGING_BIND_PORT`: server port.
- `APP_OFFLINE` / `FUNDING_HEDGING_OFFLINE`: use frozen public samples instead
  of live public HTTP calls.
- `APP_OFFLINE_RAW_DIR` / `FUNDING_HEDGING_OFFLINE_RAW_DIR`: fixture directory.
- `BINANCE_PRIVATE_CHANNEL_ENABLED` /
  `FUNDING_HEDGING_PRIVATE_CHANNEL_ENABLED`: opt-in switch for private
  read-only enrichment.
- `BINANCE_API_KEY` and `BINANCE_API_SECRET`: required only when the private
  channel is enabled.
- `BINANCE_BORROW_CHECK_MAX_CALLS`: cap for borrow-validation probes.
- `BINANCE_PRIVATE_CHANNEL_TTL_SECONDS` and
  `BINANCE_PRIVATE_CHANNEL_FAST_TTL_SECONDS`: cache TTLs for private read-only
  data groups.
- `APP_BACKGROUND_REFRESH_ENABLED` /
  `FUNDING_HEDGING_BACKGROUND_REFRESH_ENABLED`: default-on kill switch for the
  serial background refresh worker that owns the single immutable published
  state and all domain-cache writes (default `true`; offline mode never starts
  it). Companion knobs: `APP_BACKGROUND_TICK_SECONDS` (worker sweep cadence),
  `APP_HISTORY_SWEEP_BATCH_SIZE` (default-view history rows refreshed per tick),
  and `APP_SYMBOL_REFRESH_TIMEOUT_SECONDS` (bounded wait for a one-shot
  selected-symbol refresh).
- `APP_FUNDING_HISTORY_CACHE_TTL_SECONDS` /
  `FUNDING_HEDGING_FUNDING_HISTORY_CACHE_TTL_SECONDS`: per-symbol settled-history
  successful-result cache TTL (default 1800s = 30 minutes; failure results are
  not cached). Also used as the Group C component TTL for borrow-rate /
  maxBorrowable business caches.
- `APP_BORROW_EXECUTOR` / `FUNDING_HEDGING_BORROW_EXECUTOR`: `disabled` (default,
  no signed borrow POST) or `live` (exact-path PM borrow client). Live mode still
  requires explicit global Start and per-task live authorization.
- `BINANCE_BORROW_API_KEY` / `BINANCE_BORROW_API_SECRET`: dedicated Portfolio
  Margin borrow credentials (not interchangeable with the read-only private
  channel keys unless the operator deliberately reuses them). Empty keys in live
  mode block dispatch with `borrow_credentials_missing`.
- `APP_BORROW_DB_PATH` / `FUNDING_HEDGING_BORROW_DB_PATH`: SQLite path for durable
  borrow tasks (default `data/borrow-tasks.sqlite3`).
- `APP_HEDGE_EXECUTOR` / `FUNDING_HEDGING_HEDGE_EXECUTOR`: `disabled` (default,
  no signed order POST) or `live` (narrow exact-path PAPI margin/UM order
  adapter). Live mode still requires the global Start gate and a fresh
  preflight per task.
- `BINANCE_HEDGE_API_KEY` / `BINANCE_HEDGE_API_SECRET`: dedicated hedge-open
  credentials. Empty keys in live mode block dispatch (the live adapter never
  POSTs).
- `APP_CACHE_REFRESH_TIMEOUT_SECONDS` /
  `FUNDING_HEDGING_CACHE_REFRESH_TIMEOUT_SECONDS`: bounded wait for the manual
  「更新缓存」 whole-cycle refresh command (default 20s).
- `APP_REQUEST_TIMEOUT` / `FUNDING_HEDGING_REQUEST_TIMEOUT`: upstream HTTP
  client timeout (default 15s).
- `BINANCE_RECV_WINDOW` / `FUNDING_HEDGING_BINANCE_RECV_WINDOW`: signed-request
  recvWindow (default 10000 ms).
- `APP_TOP_N` / `FUNDING_HEDGING_TOP_N`: funding-history top-N (default 20).
- `APP_CACHE_TTL_SECONDS` / `FUNDING_HEDGING_CACHE_TTL_SECONDS`: whole-snapshot
  cache TTL (default 60s).

The private channel is deny-by-default. API keys may exist in the environment,
but signed private GET requests are not used unless
`BINANCE_PRIVATE_CHANNEL_ENABLED=true` or its `FUNDING_HEDGING_` alias is set.

### Market table filters & 近 24h (as of 2026-07-22)

Product decisions: `DEC-2026-07-22-004`…`006` and
`docs/planning/CHANGELOG-2026-07-22-market-table-filters.md`.

- Column **近 24h** = `funding_sum_24h` (inclusive 24h settled sum, not annualized).
- **可开优先展示** = frontend re-rank after filters (not a hard hide).
- Hide **|日费率| ≤ 0.03%** uses abs; hide **日净收益 ≤ 0.03%** uses signed `≤`.
- Filters do not re-fetch; they operate on the current snapshot in memory.

### Live borrow ops (as of 2026-07-22)

Product decisions: `DEC-2026-07-22-001`…`003` and
`docs/planning/CHANGELOG-2026-07-22-live-borrow-ops.md`.

**Classification (POST `/papi/v1/marginLoan`):**

| Observation | `result_category` | Task stays in rotation? |
|---|---|---|
| Valid `tranId` on 2xx | `success` | Yes (until success target) |
| HTTP 4xx (incl. 401/-2015, 51061 either sign) | `known_rejection` | Yes |
| Transport timeout / connection_error | `known_rejection` (Scheme C) | Yes — over-borrow risk accepted |
| 429 / 400+`-1003` / 418 | `rate_limited` | Global cooldown |
| 5xx / malformed 2xx (no `tranId`) | `unknown` | **No** — recon block |

**Logging:** same-task same-failure coalesce updates last failure time only.
There is no durable `fail_count`; count failures from the attempt ledger with
coalesce in mind.

**Private balances:** unified cards show `total_balance` and
`cross_margin_borrowed` (red when &gt; 0). Source field is Binance
`crossMarginBorrowed` on `GET /papi/v1/balance`.

**Local DB hygiene:** attempt spam and soft-deleted tasks may be cleared by the
operator on a stopped server; always take a `.bak` copy first.

### Hedge-open regular_spot 预划转 (as of 2026-08-08)

`open+forward+regular_spot` 建仓（collateral-cap / bStock / SPOT_ONLY 标的）时，
`create_task` 内从统一账户一次性划转 `truncate(q×N×price×1.03)` USDT 到普通现货账户
（1.03 缓冲覆盖价格漂移，向下截两位）；划转失败则不建卡，前端弹
`open_spot_transfer_failed`。preflight 对 regular_spot forward 余额门放行；dispatch
下单前核验 `fresh=regular_spot` 时建卡固化的 frozen route 必须也是 `regular_spot`
（即已备款），否则暂停不发单防裸空。开完不自动回流，残余 USDT 人工收尾（Human 决断
不做幂等/tranId/恢复链）。详见
`docs/planning/open-spot-usdt-transfer-2026-08-08.review-request.md`。

## Commands

- Backend tests without bytecode/cache churn:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
  ```

- Service-control script tests (launchd plist rendering, status parsing):

  ```bash
  python3 -m pytest scripts/tests
  ```

- Opening-quotes (paired bookTicker) targeted verification — adapter pair cache,
  spread formulas, status truth table, Group A cadence, ~120s usability cutoff,
  click no-extra-I/O, and schema compatibility:

  ```bash
  python3 -m pytest backend/tests/test_book_ticker.py backend/tests/test_snapshot.py \
    backend/tests/test_background_worker.py backend/tests/test_symbol_snapshot_endpoint.py \
    backend/tests/test_negative_schema.py -q
  ```

- Funding-history (settled 7D/30D projection + endpoint) targeted verification —
  the per-symbol settled-history window, annualization, `history_status`, the
  `symbol` query-param contract, and the funding-history schema:

  ```bash
  python3 -m pytest backend/tests/test_funding_history.py \
    backend/tests/test_funding_history_endpoint.py -q
  ```

- Frontend contract/UI self-check:

  ```bash
  node frontend/self-check.js
  ```

- Start the local server:

  ```bash
  scripts/run-server.sh
  ```

  Equivalent direct command:

  ```bash
  python3 -m backend.app.server
  ```

- Offline local server using frozen samples:

  ```bash
  APP_OFFLINE=true scripts/run-server.sh
  ```

- Optional private read-only startup, requiring a local `.env` or exported
  environment with API credentials:

  ```bash
  BINANCE_PRIVATE_CHANNEL_ENABLED=true scripts/run-server.sh
  ```

- macOS launchd local service, managed by `scripts/service-control.py` for the
  agent `com.aoke.funding-hedging.server`. `render` / `status` / `doctor` are
  read-only; `install` / `start` / `stop` / `restart` / `uninstall` require
  `--confirm`:

  ```bash
  python3 scripts/service-control.py render
  python3 scripts/service-control.py install --confirm
  python3 scripts/service-control.py restart --confirm
  python3 scripts/service-control.py status
  python3 scripts/service-control.py doctor
  ```

  The plist runs `scripts/run-server.sh` with `KeepAlive=true`; `install` and
  `restart` poll `/healthz` and `/readyz` before claiming success.

No project-wide lint or typecheck command is currently defined.

## Coding Rules

- Frontend code must not call Binance directly and must not infer Binance field
  semantics. It consumes only the backend API contract under `docs/api/` and
  `schemas/api/`.
- Backend code owns Binance request/response sampling, normalization, field
  semantics, and classification rules.
- Private account access is deny-by-default. The whitelist is no longer
  read-only: it now includes signed write paths — PM borrow
  (`POST /papi/v1/marginLoan`, gated by `APP_BORROW_EXECUTOR`), hedge open/close
  orders and account transfers (`backend/services/hedge_open_live_client.py`,
  gated by `APP_HEDGE_EXECUTOR`), and the asset-transfer endpoint
  (`POST /api/asset-transfer`, which has no executor gate; see
  `PROJECT_STATE.md` Live Risks). There are still no repay paths and no user
  data streams or websocket order execution.
- Raw samples must be stored under `reports/api-samples/<scope>/<timestamp>/`
  with a sample index that records source endpoint, capture time, and auth
  requirements.
- Contract changes must update both human documentation and JSON schema before
  frontend integration starts.

## Model Routing

Active model routing and provider identity live only in `agents/roles.md`. This
guide does not maintain a second route table or model-specific exception; apply
the roles file when assigning implementer or review work.

## Review And Release

- Any backend contract change must be reviewed against raw Binance samples and
  schema validation output.
- Any frontend change must be reviewed against the frozen contract and the
  agreed Chinese workstation UI style.
