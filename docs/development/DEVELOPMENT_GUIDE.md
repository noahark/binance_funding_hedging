# Development Guide

Status: as-built hedge execution system with immediate/smooth live order,
borrow, asset-transfer, manual margin-repay, and optional UI/API Basic Auth,
2026-08-27. Current runtime state and live risks:
`PROJECT_STATE.md`.

This file is the canonical approved development guide for the project.

Model drafts must not be written here directly. Drafts belong in
`reports/agent-runs/<stage-id>/` and are promoted here only after user approval.

## Project Layout

- `docs/product/PRD.md`: approved product requirements.
- `docs/api/`: approved backend-to-frontend API contracts.
- `schemas/api/`: JSON schemas for API payloads and sample validation.
- `backend/`: stdlib HTTP server, Binance adapters, normalization, hedge-open
  task execution (order/close), borrow tasks, ledger flow, asset transfer,
  manual margin repayment, private account enrichment, and tests.
- `frontend/`: same-origin static workstation UI and self-check script.
- `reports/agent-runs/<stage-id>/`: stage blackboard, model handoffs, reviews,
  and raw transcripts.
- `reports/archives/`: abandoned or superseded implementation evidence. Archive
  content is not an active implementation base.
- `scripts/run-server.sh`: local server launcher that loads `.env` when present
  and then runs `python -m backend.app.server`.

## Environment

The application is a lightweight Python backend plus static frontend. Runtime
defaults bind to `127.0.0.1:8787`; `requirements.txt` pins `ccxt==4.5.64` for
the public smooth-open best-bid/ask WebSockets. Without CCXT the rest of the
application still starts, but smooth creation fails closed. Offline mode never
constructs the WebSocket provider.

Useful environment variables:

- `APP_BIND_HOST` / `FUNDING_HEDGING_BIND_HOST`: server host.
- `APP_BIND_PORT` / `FUNDING_HEDGING_BIND_PORT`: server port.
- `APP_UI_USERNAME` and `APP_UI_PASSWORD`: optional together on loopback and
  mandatory together for any non-loopback bind. They enable one process-wide
  browser HTTP Basic login for the static UI and all business APIs. The values
  are omitted from config repr/log output; usernames cannot contain `:`.
- `APP_OFFLINE` / `FUNDING_HEDGING_OFFLINE`: use frozen public samples instead
  of live public HTTP calls.
- `APP_OFFLINE_RAW_DIR` / `FUNDING_HEDGING_OFFLINE_RAW_DIR`: fixture directory.
- `BINANCE_PRIVATE_CHANNEL_ENABLED` /
  `FUNDING_HEDGING_PRIVATE_CHANNEL_ENABLED`: opt-in switch for private
  read-only enrichment.
- `BINANCE_API_KEY` and `BINANCE_API_SECRET`: the default credential pair for
  the private read channel and every signed write client (borrow, hedge
  open/close, asset transfer, and margin repayment). Private reads still require
  their independent enable switch, and writes still require their existing
  gates.
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
- `BINANCE_BORROW_API_KEY` / `BINANCE_BORROW_API_SECRET`: optional paired
  Portfolio Margin borrow override. Omit both to use the generic pair. If only
  one is configured, the missing half stays empty and live dispatch is blocked
  with `borrow_credentials_missing`; credentials are never mixed across pairs.
- `APP_BORROW_DB_PATH` / `FUNDING_HEDGING_BORROW_DB_PATH`: SQLite path for durable
  borrow tasks (default `data/borrow-tasks.sqlite3`).
- `APP_HEDGE_EXECUTOR` / `FUNDING_HEDGING_HEDGE_EXECUTOR`: `disabled` (default,
  no signed order POST) or `live` (narrow exact-path PAPI margin/UM order
  adapter). Live mode still requires the global Start gate. Immediate attempts
  use fresh preflight; smooth tasks perform one complete create-time preflight,
  persist paused, and reuse the frozen result after Human Start.
- `BINANCE_HEDGE_API_KEY` / `BINANCE_HEDGE_API_SECRET`: optional paired override
  shared by hedge open/close, asset transfer, and repayment. Omit both to use
  the generic pair. A partial override remains incomplete and blocks the live
  adapter.
- `APP_MARGIN_REPAY_ENABLED` /
  `FUNDING_HEDGING_MARGIN_REPAY_ENABLED`: independent boolean gate for
  `POST /api/margin-repay` (default `false`). A real client is injected only
  when this gate is true, `APP_OFFLINE=false`, and both hedge API credentials
  exist. It is independent of `APP_HEDGE_EXECUTOR`. Human final acceptance on
  2026-08-10 keeps this gate enabled in the current manual foreground runtime;
  changing it still requires a service restart.

Docker `--env-file` treats values literally and does not expand shell references.
Do not configure a dedicated override as `${BINANCE_API_KEY}` or
`${BINANCE_API_SECRET}`; omit the dedicated pair to activate the generic
fallback.
- `APP_CACHE_REFRESH_TIMEOUT_SECONDS` /
  `FUNDING_HEDGING_CACHE_REFRESH_TIMEOUT_SECONDS`: bounded wait for the manual
  「更新缓存」 whole-cycle refresh command (default 20s).
- `APP_REQUEST_TIMEOUT` / `FUNDING_HEDGING_REQUEST_TIMEOUT`: upstream HTTP
  client timeout (default 15s).
- `BINANCE_RECV_WINDOW` / `FUNDING_HEDGING_BINANCE_RECV_WINDOW`: signed-request
  recvWindow (default 10000 ms).
- `APP_CACHE_TTL_SECONDS` / `FUNDING_HEDGING_CACHE_TTL_SECONDS`: whole-snapshot
  cache TTL (default 60s).

The private channel is deny-by-default. API keys may exist in the environment,
but signed private GET requests are not used unless
`BINANCE_PRIVATE_CHANNEL_ENABLED=true` or its `FUNDING_HEDGING_` alias is set.

### Cloud login boundary

Run one process per subdomain/account and select its environment file with the
existing launcher:

```bash
ENV_FILE=/etc/funding-hedging/account-a.env scripts/run-server.sh
```

Cloud deployment profiles use a stable configuration name as their identity.
For example, `env_aoke` maps to `/etc/funding-hedging/env_aoke` and
`/var/lib/funding-hedging/env_aoke/data`. Each machine runs exactly one named
profile; a second account uses a different machine and configuration name, not
a second profile in the same process.

Set `APP_BIND_HOST=0.0.0.0`, `APP_UI_USERNAME`, and `APP_UI_PASSWORD` in that
file. Put the application behind an HTTPS reverse proxy; HTTP Basic transmits a
reusable credential on every request and is not safe over plaintext HTTP.
`/healthz` and `/readyz` intentionally remain unauthenticated for probes. The
application does not implement logout, registration, roles, or simultaneous
multi-account switching; changing the account means starting a separate process
with its own environment and data paths.

### Manual margin repayment (as of 2026-08-10)

Borrowed unified-account asset cards call the local
`POST /api/margin-repay`, which is the only caller of Binance
`POST /papi/v1/margin/repay-debt`. Exact input `0` omits upstream `amount` and
requests full repayment; a positive plain decimal is forwarded as the debt
asset quantity. The server fixes `specifyRepayAssets=USDT`, while Binance still
spends same-coin assets first. Requests are stored in
`data/margin-repay.sqlite3` (derived from the borrow DB directory), sent once,
and never automatically retried; `pending`/`unknown` require Human exchange
verification.

Operationally, use one browser tab, avoid concurrent bulk refresh/open activity
around this weight-3000 endpoint, and after full repayment trust the refreshed
borrowed balance rather than expecting `repaid_amount` to be present. XLM 5 and
INJ full repayment were live-verified before final Human acceptance.

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
| 5xx / malformed 2xx (no `tranId`) | `unknown` | Yes — see below |
| Crash orphan (process died before the response) | `unknown` | Yes — see below |

**DEC-2026-08-21:** a POST that returns a usable `tranId` is the ONLY successful
borrow; every other outcome is treated as "did not borrow" and the task stays in
rotation. No task-level state blocks scheduling any more — the loan-record
reconciliation subsystem was removed, and `unresolved_attempt_id` is now purely
an in-process in-flight guard cleared on every resolution and on (owner-gated)
startup recovery. The global rate-limit cooldown and the 418 manual re-arm are
unchanged and still gate every task. Accepted cost: at most one duplicate borrow per orphan, reconciled by
Human from the Binance console.

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
`open_spot_transfer_failed` 弹窗。

### Historical leg fee backfill script (`scripts/backfill-leg-fees.py`)

- **Usage**: `python3 scripts/backfill-leg-fees.py [--db PATH] [--progress PATH] [--limit N] [--dry-run]`
- **Idempotency & Red Lines**:
  - Updates only `hedge_open_leg` via atomic `WHERE id = ? AND fee_bnb_qty IS NULL AND fee_bnb_price IS NULL AND fee_other_qty IS NULL AND fee_other_asset IS NULL`.
  - Never touches or rewrites `hedge_open_cycle_close_log` (Breakpoint 1).
  - Fetches trades via `backend/hedge_open_tasks/fee_fetcher.py`.
  - BNB price is frozen at order fill time using Binance 1m K-line close price from `binance_public`.
- **Progress Tracking & Operational Note**:
  - Breakpoint progress is stored in `data/backfill-leg-fees-progress.json`.
  - If backfill code logic or Binance query window calculations are patched, delete or reset the progress file so previously failed candidate legs can be re-evaluated.

`open_spot_transfer_failed`。preflight 对 regular_spot forward 余额门放行；dispatch
下单前核验 `fresh=regular_spot` 时建卡固化的 frozen route 必须也是 `regular_spot`
（即已备款），否则暂停不发单防裸空。开完不自动回流，残余 USDT 人工收尾（Human 决断
不做幂等/tranId/恢复链）。详见
`docs/planning/open-spot-usdt-transfer-2026-08-08.review-request.md`。

## Commands

- Install the pinned runtime dependency:

  ```bash
  python3 -m pip install -r requirements.txt
  ```

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

- Smooth-open provider, gate, executor, API, and UI-binding regression:

  ```bash
  python3 -m pytest backend/tests/test_best_bid_ask_provider.py \
    backend/tests/test_smooth_gate_store.py backend/tests/test_smooth_gate_worker.py \
    backend/tests/test_smooth_api.py backend/tests/test_live_hedge_executor.py \
    backend/tests/test_frontend_field_binding.py -q
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
  agent `com.aoke.funding-hedging.server`. **Not in use: by decision 2026-08-15
  the local service runs as a manual foreground process (`scripts/run-server.sh`)
  and launchd is not being repaired; hosting moves to a systemd unit at server
  deployment.** The script and plist rendering are retained unchanged.
  `render` / `status` / `doctor` are read-only; `install` / `start` / `stop` /
  `restart` / `uninstall` require `--confirm`:

  ```bash
  python3 scripts/service-control.py render
  python3 scripts/service-control.py install --confirm
  python3 scripts/service-control.py restart --confirm
  python3 scripts/service-control.py status
  python3 scripts/service-control.py doctor
  ```

  The plist runs `scripts/run-server.sh` with `KeepAlive=true`; `install` and
  `restart` poll `/healthz` and `/readyz` before claiming success.

### Remote deployment (`scripts/deploy.sh`, as of 2026-08-29)

Production hosts run the application as a **Docker container managed by
systemd**, not from a checkout — there is no git repository on either server.
The image tag IS the commit sha and is written inline in the unit's
`ExecStart`, so `/etc/systemd/system/funding-hedging.service` is itself the
version record. Upgrading therefore means **building a new image**, never
`git pull`.

#### Deployed instances

Both hosts run the same image built by the same `deploy.sh`, under the same
unit name (`funding-hedging.service`) and image name (`funding-hedging`). They
differ only in the profile they load and the web layer in front of them, so
targeting one or the other is purely `DEPLOY_HOST`.

| | `aoke` | `maizi_vip8` |
|---|---|---|
| SSH alias | `funding-prod` (47.240.168.162) | `funding-maizi` (149.129.102.152) |
| URL | `https://aoke.kengbi.pro` | `https://maizi.kengbi.pro` |
| env file | `/etc/funding-hedging/env_aoke` | `/etc/funding-hedging/env_maizi_vip8` |
| Data volume | `/var/lib/funding-hedging/env_aoke/data` | `/var/lib/funding-hedging/env_maizi_vip8/data` |
| HTTPS | Caddy in Docker (`funding-hedging-proxy.service`), owns `:443` | **pre-existing system nginx + certbot**, reverse-proxies to `127.0.0.1:8787` |
| Binance account | its own | its own, separate |
| Host | 1 CPU / 1.8GiB, no swap | 1 CPU / 1.9GiB, **2G swap file**, Alibaba Cloud Linux 3 |

```bash
scripts/deploy.sh                              # aoke (the DEPLOY_HOST default)
DEPLOY_HOST=funding-maizi scripts/deploy.sh    # maizi_vip8
```

The volume path segment is the **env file name** (`env_aoke`, not `aoke`) —
that is what the existing units already use.

`maizi_vip8` is **not a dedicated box**: it also runs an unrelated live trading
system (`/opt/permanent_investment_strategy_binance/`, units `grid-live`,
`grid-fill-sync`, `shadow-dashboard`, `stage17-*`) plus an FMZ `robot`, and its
nginx already serves `ops.kengbi.pro`. Hence no Caddy there (`:443` is taken)
and hence the swap file: an OOM on that box would pick a victim among someone
else's money-moving processes. Do not install a second web server on it, and
check free memory before anything build-heavy.

The two accounts are separate, so both instances may hold execution rights at
the same time; the "never two instances with execution rights" rule in
`PROJECT_STATE.md` is about one account, not one image.

```bash
scripts/deploy.sh                 # deploy current origin/main
scripts/deploy.sh <commit-ish>    # deploy a specific commit
DEPLOY_HOST=root@host scripts/deploy.sh
```

The script runs on the developer machine and does: refuse a dirty worktree →
**refuse any commit not on `origin/main`** (the deployed version must stay
traceable) → `git archive` the four paths the image needs (`backend`,
`frontend`, `schemas`, `requirements.txt`) → build remotely over stdin → `sed`
the new tag into the unit → `daemon-reload` + `restart` → poll `/readyz` until
200 → **roll back to the previous tag automatically on any failure** → prune old
images keeping the last `KEEP_IMAGES` (default 3).

Secrets never enter the image: `--env-file /etc/funding-hedging/env_aoke` is
mounted at run time, and the data volume lives at
`/var/lib/funding-hedging/<profile>/data`.

#### SSH access

Authentication uses a **dedicated deployment key** with no passphrase, so the
script runs unattended. It is deliberately NOT the developer's personal or
GitHub key: revoking it later is one line in `authorized_keys` and touches
nothing else.

```
~/.ssh/id_ed25519_funding_deploy        # private, chmod 600, no passphrase
~/.ssh/id_ed25519_funding_deploy.pub    # appended to the server's authorized_keys
```

`~/.ssh/config` carries one alias per host; both share the same deployment key.

```
Host funding-prod
    HostName 47.240.168.162
    User root
    IdentityFile ~/.ssh/id_ed25519_funding_deploy
    IdentitiesOnly yes

Host funding-maizi
    HostName 149.129.102.152
    User root
    IdentityFile ~/.ssh/id_ed25519_funding_deploy
    IdentitiesOnly yes
```

`IdentitiesOnly yes` matters: without it ssh offers every loaded key in turn and
can exhaust the server's auth-attempt limit before reaching the right one.

To provision the key on a new host (idempotent; re-running adds nothing):

```bash
PUB="$(cat ~/.ssh/id_ed25519_funding_deploy.pub)"
ssh root@<host> "mkdir -p ~/.ssh && chmod 700 ~/.ssh
  touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys
  grep -qF '$PUB' ~/.ssh/authorized_keys || echo '$PUB' >> ~/.ssh/authorized_keys
  command -v restorecon >/dev/null && restorecon -R ~/.ssh 2>/dev/null || true"
```

`restorecon` is there for CentOS/RHEL: SELinux otherwise mislabels a freshly
created `~/.ssh` and sshd silently ignores the key.

**Password login stays available.** Adding the key does not touch
`/etc/ssh/sshd_config`; `PasswordAuthentication yes` and `PermitRootLogin yes`
remain as they were, which is the recovery path if the key is ever lost. On a
machine without the key, the script accepts a password through the `SSHPASS`
environment variable (requires `sshpass`); the password is never written to the
script, a file, a log, or the server.

```bash
SSHPASS='...' scripts/deploy.sh    # fallback only
```

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
  `PROJECT_STATE.md` Live Risks). The same exact-path adapter also contains the
  independently gated manual `repay-debt` path; there is still no automatic
  repayment, user-data stream, or websocket order execution.
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
