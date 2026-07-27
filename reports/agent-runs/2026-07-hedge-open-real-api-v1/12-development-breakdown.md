# Development Breakdown — Hedge Open Real API v1

Author role: development-breakdown author (Claude Opus 4.8). Design-only. No
product code, `status.json`, `70-handoff.md`, PRD, or source file was modified in
producing this document. All facts below are grounded in the artifact paths cited
inline; unverified points are marked as risks or open items, not stated as fact.

Inputs read: `AGENTS.md`; `docs/product/PRD.md`;
`docs/architecture/ARCHITECTURE.md`; this stage's `00-task.md`, `10-design.md`,
`11-adr.md`, `06-direction-synthesis.md`, `04-user-execution-policy.md`;
`reports/api-samples/2026-07-hedge-open-real-api-v1/order-model-and-live-seams-recon.md`;
`backend/hedge_open_tasks/{domain,store,service,executor,scheduler}.py`;
`backend/app/server.py`; `backend/config.py`;
`backend/services/{binance_signing,portfolio_margin_borrow_client,live_borrow_executor,private_client}.py`;
`frontend/index.html`; `frontend/self-check.js`; hedge tests under
`backend/tests/`; `docs/parallel-development-mode.md` (v0.5).

Stage branch at authoring time: `stage/2026-07-hedge-open-real-api-v1`, HEAD
`fc4cdce`.

---

## 0. One contract conflict the implementers MUST NOT silently resolve

There is a factual conflict between two frozen inputs, and it is the single most
important thing this breakdown pins down. Getting it wrong reverses the entire
execution model.

- **The recon** (`order-model-and-live-seams-recon.md`, Claude Opus 4.6, dated
  2026-07-23T14:13) concludes the **forward** leg must send spot `quoteOrderQty`
  (USDT), which makes forward legs **serial** (spot fills first, UM `quantity`
  derived from the spot `executedQty`), and lists blockers B-1…B-6 built on that
  premise. Its C-1…C-7 "must change" list is written for the quoteOrderQty model.
- **The frozen contract** — PRD §6.2, `00-task.md` "Frozen Requirements",
  `10-design.md`, `11-adr.md` ADR-1, `06-direction-synthesis.md` §1, and the
  user's own `04-user-execution-policy.md` — **overrides that**. It explicitly
  states: both legs send the same Decimal `q_common`; both legs are submitted
  **concurrently**; `quoteOrderQty` "is a valid Binance capability but is **not**
  part of this stage's execution contract."

**Resolution for implementers (do not re-decide):** the frozen `q_common` +
concurrent model wins. The recon's serial/`quoteOrderQty` forward model is **NOT
adopted** this stage. This is legal against the API: the recon itself (§1.1)
records that `POST /papi/v1/margin/order` MARKET BUY accepts **`quantity` OR
`quoteOrderQty`**, so forward BUY with `quantity=q_common` is a valid request.
Both directions therefore use the same `q_common` common-grid model already built
in `domain.py` (`decimal_lcm`/`floor_to_grid`/`compute_preflight`).

**What the recon is still authoritative for** (use it as fact, keep the citations
in code comments): the endpoint/method/weight table (§3.1–3.2), filter values and
`MARKET_LOT_SIZE.stepSize=0` → fall back to `LOT_SIZE` (§2.2, C-7 — already
implemented in `domain.effective_market_step`), the HTTP-503/timeout
query-before-classify reconciliation sequence (§3.3), the rate-limit / 429 / 418
/ -1008 facts (§4.4), and **the confirmed absence of any PAPI PM testnet** (§3.4).

**A consciously accepted residual.** The recon's B-2/B-4 single-leg / residual
exposure risk is real and is **deliberately accepted** by the user policy:
outcomes are recorded, never auto-repaired; the only scheduler guard is confirmed
consecutive *submission* failures. Implementers must not reintroduce any residual
tolerance, notional cap, or auto-remediation to "fix" this exposure — doing so
violates ADR-3 and `04-user-execution-policy.md` §Consequence.

---

## 1. Frozen contract, non-goals, and the dry-run code that must change

### 1.1 Frozen contract (restated, authoritative)

- Regular Portfolio Margin, USDT quote, USDⓈ-M perpetual, one-way position mode,
  UM `positionSide=BOTH`. A non-one-way (hedge-mode) or unhealthy account **fails
  preflight** and never triggers a mode switch (PRD §5; recon §4.3).
- Both legs use Decimal-filtered `q_common`; per-constraint effective filter is
  `MARKET_LOT_SIZE` when its field is enabled, else `LOT_SIZE`; a zero/missing
  field disables **only that constraint** (PRD §6.2, `10-design` §Preflight).
- Direction mapping (locked, ADR-1 / already in `domain.direction_to_leg_actions`):
  forward = margin BUY + UM SELL; reverse = margin SELL + UM BUY; every margin leg
  is `NO_SIDE_EFFECT`; no `quoteOrderQty`; `reduceOnly` never set on opens.
- One concurrent pair per second per running task until `target_n` attempts are
  *issued* or the task pauses; a prior pair's fill/residual/partial/pending query
  never blocks the next pair (PRD §6.3, user policy #2).
- Durable-before-send: one SQLite transaction persists the immutable attempt +
  both deterministic client IDs + sanitized request shapes + preflight snapshot
  **before either POST** (PRD §6.3.3, ADR-2).
- A returned `orderId` = **accepted** (not filled); persist it, then poll to a
  terminal state. Timeout/missing/ambiguous 5xx is **not** a confirmed failure and
  is **never blindly resent**: query by persisted client ID first (PRD §6.4, user
  policy #3, recon §3.3).
- `consecutive_failure_pause_threshold` — **task-snapshotted, configurable,
  default 3**. Two accepted order IDs = an accepted pair → reset the counter; a
  confirmed failed pair → increment; reaching the threshold pauses future opening.
  It "may later be changed to 1 or 2" (PRD §6.4, ADR-3, user policy #4).
- Per-leg accounting: persist order/client IDs, terminal state, actual base qty,
  cumulative quote amount, fees when available, timestamps, signed residual;
  `weighted_average_price = cumulative_quote_amount / cumulative_base_quantity`
  (PRD §6.5).
- Real POST requires all of: `APP_HEDGE_EXECUTOR=live`, durable global Start on, a
  runnable task with passing factual preflight, no browser/bulk bypass, and
  **separate human first-live authorization**. **No real order is authorized
  during implementation or tests** (PRD §6.6, ADR-4, `00-task.md`).

### 1.2 Non-goals (hard boundaries; a diff touching these is out of scope)

Smooth/WebSocket mode; user data streams; PM-Pro; normal-spot fallback; automatic
borrow/repay/transfer; manual close; full accounting; and **real-order
validation** (no live POST evidence is produced this stage). No product-level
amount/count/margin/aggregate-notional/residual/slippage cap. No auto repair,
cancel/replace, close, borrow, repay, transfer. Public snapshot route/schema and
borrow-task behavior are **forbidden from change** (`10-design` §Scope).

### 1.3 Dry-run code that must change (this is item-1 of the dispatch)

The round-1 skeleton encodes an **older, now-superseded** outcome model
("success = both legs FILLED; one-leg fill → `exposure_alert` pause; hardcoded
threshold 3"). The frozen policy is different ("accepted = orderId returned;
one-leg fill is recorded, not a pause; pause only on confirmed consecutive
*submission* failures; threshold is task-snapshotted"). The following named
symbols/behaviors **must be reworked**, not extended:

| File:location | Current behavior | Required change | Grounding |
|---|---|---|---|
| `domain.py:104 FAIL_TERMINATE_THRESHOLD = 3` (module constant) | Global hardcoded 3, compared with `>` (`>3` = 4th) | Task-snapshotted `consecutive_failure_pause_threshold`, default 3, compared so reaching it (`>=`, i.e. the 3rd) pauses; per PRD §6.4 "Reaching it pauses" | PRD §6.4; ADR-3; user #4 |
| `domain.py:85-94 ATTEMPT_*` + `classify_attempt` (both FILLED→success, one→exposure) | Classifies on **fill**, treats one-leg fill as a special pause state | Reclassify on **acceptance** (orderId present) for the scheduler counter; fill state becomes observational accounting, not the pair-success signal | user #1/#3; PRD §6.4 |
| `domain.py:40-47 STATUS_EXPOSURE_ALERT` + `resolve_status_after_attempt` (single-leg → EXPOSURE_ALERT) | Single-leg fill freezes the task | Single-leg fill must NOT freeze scheduling; the counter/pause path keys off confirmed submission failure only. Decide whether to retire `exposure_alert` or repurpose it as a **non-blocking** advisory (see §4.5) | user policy Consequence; ADR-3 |
| `service.py:281-311 post_fill_all` synchronous `while` loop | A single HTTP call spins many attempts inline | In live mode this bulk synchronous dispatch is **prohibited**: every send must pass the one-second scheduler + Start/executor gate (`10-design` §Scope: "Live `fill-all` must not retain synchronous bulk dispatch"). See §4.6 | `10-design` §Scope; F-006 |
| `executor.py` `RecordTransportExecutor._simulate_leg` (fabricates a FILLED price) | Simulates fills locally | The **live** executor must derive fill state only from real order/query responses; the record transport stays for tests but must not be the live path | ADR-4; F-005 |
| `service.py:668 _build_hedge_service` (live mode still builds record transport) | `live` mode silently downgrades to record transport | `live` must construct the real gated executor + adapter + preflight provider (still default-off by env), else the stage delivers nothing real | `00-task.md` Deliverable 3 |
| `service.py:365 tick()` dispatches `eligible[0]` only (one attempt across all tasks per tick) | One attempt per second *total* | Confirm/adjust to one pair per second **per running task** and concurrent two-leg send within a pair (frozen "one concurrent pair per second"). See §4.4 open item | PRD §6.3 |

The **record** and **disabled** transports and their zero-network proof are a
regression boundary and must keep passing unchanged.

---

## 2. Serial vs parallel, and the shared contract freeze

**Recommendation: parallel, split ONLY at the backend/frontend seam.** Enable
`docs/parallel-development-mode.md` (v0.5). Rationale:

- The work decomposes cleanly into (A) a **large, internally-sequential backend**
  and (B) a **lighter additive frontend** that consumes a JSON contract and has
  its own mock harness (`frontend/self-check.js` already stubs every hedge route).
- Per `AGENTS.md` §Implementers domain routing: **Claude-GLM owns backend**
  (adapter/schema/domain/service/scheduler/config/tests); **Kimi owns frontend**
  (display of new fields, executor/Start state, attempt timeline). Both domains
  are substantial and separable, so split by owner.
- The backend is **not** further parallelized: schema → store → executor/adapter →
  service → scheduler is a hard internal dependency chain and belongs to one
  owner working serially inside Task A. Splitting it would create cross-seam churn
  (the round-2 stage already recorded three cross-seam drift fixes on a serial
  build — see memory `hedge-open-close-system`).

**Dependency:** Task B (frontend) depends on **Task A's frozen API contract
(§3.4), not on Task A's code.** B builds against the frozen field names + the
self-check mocks and integration-tests against the running backend once A lands.

**Shared contract freeze (frozen before either implementer starts — this is the
R3-critical surface; a change here is an R3 escalation, never a local fix):**

1. The additive hedge JSON field set of §3.4 (task/list/log/position/settings
   docs), including exact field names and decimal-string discipline.
2. The route table is **unchanged** (`server.py:75-89`); no new route, no renamed
   route. Additions are new **fields** in existing payloads only.
3. `single_amount` stays base-asset quantity for **both** directions (no
   quoteOrderQty; no USDT-amount input semantics). Frontend labels/inputs must not
   introduce a USDT-amount field.
4. `executor_mode` / `start_gate` / `interval_seconds` settings shape
   (`settings_to_doc`, `service.py:100`) is stable; frontend renders it read-only.

---

## 3. Task A — Backend (owner: Claude-GLM / `zhipu_glm`)

### 3.1 Scope and file boundary

**Allowed to change:**

- `backend/hedge_open_tasks/domain.py` — threshold→task-snapshot, acceptance-based
  classification, attempt/leg vocabulary, no-quoteOrderQty confirmation.
- `backend/hedge_open_tasks/store.py` — attempt/leg schema (new tables/columns,
  §3.3), cumulative accounting, threshold snapshot column, migration.
- `backend/hedge_open_tasks/executor.py` — keep record/disabled transports; add
  the **live executor seam** interface (the real executor itself lives under
  `backend/services/`, imported via injection, never imported by
  `hedge_open_tasks/**`).
- `backend/hedge_open_tasks/service.py` — preflight provider wiring, durable
  attempt persistence before send, concurrent two-leg dispatch, reconciliation
  orchestration, failure counter/pause, live `fill-all` prohibition, doc
  serialization of new fields.
- `backend/hedge_open_tasks/scheduler.py` — one-second per-task cadence if §4.4
  open item resolves to per-task.
- **New** `backend/services/hedge_open_live_client.py` — the narrow default-off
  PAPI margin/UM POST+query transport (allowlist; mirrors
  `portfolio_margin_borrow_client.py`).
- **New** `backend/services/live_hedge_executor.py` — typed live executor that
  classifies real responses into the attempt/leg vocabulary (mirrors
  `live_borrow_executor.py`).
- **New** `backend/services/hedge_preflight_provider.py` — read-only preflight
  data source (reuses `private_client.py` signed-GET + public filter reads).
- `backend/config.py` — add validated `APP_HEDGE_EXECUTOR` (`disabled`|`live`)
  and, if used, dedicated hedge credential env reads (mirror
  `borrow_executor`/borrow-credentials pattern at `config.py:180-189`).
- `backend/app/server.py` — `_build_hedge_service` (server.py:657) must, in `live`
  mode, construct the live executor + preflight provider + credentials; add a
  sanitized `hedge_open_execution_mode`/`_blocked` lifecycle event mirroring the
  borrow one (server.py:687-712). No route change.
- `backend/tests/test_hedge_*.py` (all five) + a **new**
  `backend/tests/test_hedge_open_live_client.py` and
  `backend/tests/test_live_hedge_executor.py`.

**Forbidden to change (hard):** `frontend/**` (Task B); `backend/services/binance_signing.py`
(the single signer — reuse, do not fork; the static guard in
`test_private_client.py` forbids a second signer); `backend/services/private_client.py`
allowlist except read-only reuse; `backend/borrow_tasks/**`; any public snapshot
route/schema; `docs/product/PRD.md`; `docs/architecture/**`; `reports/api-samples/**`
(raw samples are evidence, not editable). No new dependency; standard library +
existing `jsonschema` only (ARCHITECTURE §10.1).

### 3.2 API / data contracts owned by A (see §3.4 for the exact field set)

A owns the additive JSON contract, the SQLite schema + forward migration, the
config env contract, and the live-adapter allowlist. A must keep the frozen route
table byte-stable and keep the disabled/record transports' zero-network proof.

### 3.3 Attempt / leg schema (concrete — item-4 of the dispatch)

Round-1 has one `hedge_open_fill` row per attempt with inline spot/perp columns
(`store.py:49-66`). The real stage needs a durable **attempt** that exists
*before* any POST and mutable **legs** that advance through query cycles. Two
workable shapes — A picks one and records the choice; the migration must be
additive-forward (new tables/columns; do not drop round-1 data):

**Recommended: a dedicated `hedge_open_attempt` + `hedge_open_leg` pair.**

`hedge_open_attempt` (immutable core, written in the pre-send transaction):

```text
id                  INTEGER PK AUTOINCREMENT
task_id             TEXT NOT NULL
attempt_seq         INTEGER NOT NULL         -- per-task monotonic sequence
attempt_uuid        TEXT NOT NULL UNIQUE     -- basis of both client IDs
direction           TEXT NOT NULL            -- forward | reverse
q_common            TEXT NOT NULL            -- decimal string, the sent quantity
preflight_fingerprint TEXT NOT NULL          -- sanitized snapshot hash/JSON ref
position_side_mode  TEXT NOT NULL            -- BOTH (frozen); reject hedge
created_at_us       INTEGER NOT NULL
pair_outcome        TEXT                     -- NULL until resolved: accepted_pair |
                                             --   confirmed_failed | querying
```

`hedge_open_leg` (one row per leg, mutable through reconciliation):

```text
id                  INTEGER PK AUTOINCREMENT
attempt_id          INTEGER NOT NULL         -- FK hedge_open_attempt.id
leg                 TEXT NOT NULL            -- spot | perp
client_order_id     TEXT NOT NULL UNIQUE     -- deterministic, persisted pre-send
endpoint            TEXT NOT NULL            -- /papi/v1/margin/order | /papi/v1/um/order
request_shape       TEXT NOT NULL            -- sanitized would-send params (no secrets)
dispatch_state      TEXT NOT NULL            -- PREPARED|DISPATCHING|ACCEPTED_OR_QUERYING|
                                             --   UNKNOWN_QUERYING|TERMINAL_RECORDED
order_id            TEXT                     -- set when accepted (proof of acceptance)
exchange_status     TEXT                     -- FILLED|NEW|PARTIALLY_FILLED|REJECTED|EXPIRED|UNKNOWN
cumulative_base_qty TEXT NOT NULL DEFAULT '0'
cumulative_quote_amt TEXT NOT NULL DEFAULT '0'
fee_amount          TEXT                     -- when available
fee_asset           TEXT
dispatched_at_us    INTEGER
last_query_at_us    INTEGER
terminal            INTEGER NOT NULL DEFAULT 0
```

Task-level additions to `hedge_open_task`:

```text
scheduled_attempt_count           INTEGER NOT NULL DEFAULT 0   -- pairs issued
accepted_pair_count               INTEGER NOT NULL DEFAULT 0
consecutive_submission_failures   INTEGER NOT NULL DEFAULT 0
failure_pause_threshold           INTEGER NOT NULL             -- task snapshot, default 3
pause_reason                      TEXT                         -- e.g. consecutive_submission_failure
```

Per-leg cumulative fields let `weighted_average_price = cumulative_quote_amt /
cumulative_base_qty` be computed by the store/position aggregation (already
present as `aggregate_positions`, `store.py:451` — extend to read the leg rows).
`signed residual` = per-attempt `spot cumulative_base_qty − perp cumulative_base_qty`
(sign per direction), recorded/displayed, never a gate.

The alternative (keep `hedge_open_fill`, add nullable columns + a separate
pre-send `hedge_open_attempt` marker) is acceptable if A prefers a smaller
migration, provided the pre-send durable record and the mutable leg-query fields
both exist. A must not weaken the durable-before-send invariant to reuse the old
single-row model.

### 3.4 Frozen additive JSON contract (owned by A, consumed by B)

Additive fields on existing docs (`service.py` `task_to_doc`/`fill_to_doc`/
`settings_to_doc`). Names are frozen here; decimals are strings; no field is
removed.

`task_to_doc` gains: `q_common` (already present), `failure_pause_threshold`,
`consecutive_submission_failures`, `accepted_pair_count`,
`scheduled_attempt_count`, `pause_reason`. `leg_exposure` stays for
backward-compat rendering but is advisory (§4.5).

New per-attempt doc (surfaced under the existing logs/fills read; B renders an
attempt timeline):

```json
{
  "attempt_id": "…", "attempt_seq": 7, "direction": "forward",
  "q_common": "0.003", "pair_outcome": "accepted_pair",
  "spot": {"client_order_id": "hgo-…-s", "order_id": "…", "status": "FILLED",
           "cumulative_base_qty": "0.003", "cumulative_quote_amt": "…",
           "avg_price": "…", "fee_amount": "…", "fee_asset": "BNB"},
  "perp": {"client_order_id": "hgo-…-p", "order_id": "…", "status": "FILLED",
           "cumulative_base_qty": "0.003", "cumulative_quote_amt": "…",
           "avg_price": "…"},
  "residual": "0", "ts": "…Z"
}
```

`settings_to_doc` shape unchanged; `positions` gains real `spot_avg`/`perp_avg`
from cumulative leg data (the `"0"` placeholders for funding/borrow/pnl stay).

### 3.5 Client-ID query behavior (concrete — item-4)

- Deterministic client IDs derive from `attempt_uuid` (round-1 already does
  `hgo-{attempt}-s` / `-p`, `executor.py:146`). They are persisted in the
  pre-send transaction and **never regenerated**.
- After a timeout / missing / ambiguous 5xx on a POST, the leg goes
  `UNKNOWN_QUERYING`. The live executor calls
  `GET /papi/v1/margin/order?origClientOrderId=<cid>` (spot) /
  `GET /papi/v1/um/order?origClientOrderId=<cid>` (perp) — **not** by orderId,
  which may be unknown (recon §3.3). Read-query retries may be bounded; **write
  POSTs never auto-retry** (`10-design` §Live Adapter Boundary).
- Query result mapping (recon §3.3): `FILLED` → terminal accepted+filled;
  `NEW`/`PARTIALLY_FILLED` → keep querying; 404/absent → the order was never
  accepted → this leg counts toward a confirmed submission failure; query itself
  times out → stays `UNKNOWN`, keep querying, **not** yet a failure. HTTP 503
  "Unknown error" = state unknown, must query, never resend; 503 "Service
  Unavailable"/-1008 = definite failure, may back off.
- Restart recovery: on startup, any leg left `DISPATCHING`/`UNKNOWN_QUERYING`
  (non-terminal, `order_id` unknown) creates a **query obligation**, resolved by
  client-ID lookup — never by resending the original request (ADR-2).

### 3.6 Failure counter and one-second scheduling (concrete — item-4)

- **Counter:** an attempt whose **both legs return an orderId** (accepted) is an
  accepted pair → `accepted_pair_count++`, `consecutive_submission_failures = 0`.
  An attempt where required client-ID lookup proves a leg **never accepted** is a
  confirmed failed pair → `consecutive_submission_failures++`. An attempt still
  `UNKNOWN_QUERYING` is neither yet — it does not touch the counter until resolved
  (`10-design` §Dispatch and Reconciliation).
- **Pause:** `consecutive_submission_failures >= failure_pause_threshold` (task
  snapshot, default 3) → set status paused, `pause_reason =
  "consecutive_submission_failure"`. No amount/notional/margin/residual cap is
  ever introduced by this path.
- **One-second scheduling:** the scheduler issues one concurrent pair per second
  per running task; a prior pair's fill/residual/partial/pending query does **not**
  block the next pair. Start gate, executor mode, task pause/done, and exchange
  rate-limit cooldown (429/418/-1008) still block new sends (PRD §6.3, user #2).

### 3.7 Fake / live separation (concrete — item-4)

- **`disabled`** (default): `DisabledHedgeExecutor`, zero I/O, zero record.
- **record/dry-run**: `RecordTransportExecutor`, records would-send params +
  simulated outcome, **no POST** — retained for CI/tests only.
- **`live`**: `LiveHedgeExecutor` (new, under `backend/services/`) is the **only**
  path that may POST, and only when `APP_HEDGE_EXECUTOR=live` **AND** durable Start
  on **AND** a passing fresh preflight context is handed to it immediately before
  send (`10-design` §Live Adapter Boundary). The `hedge_open_tasks/**` package
  must never import the live client/executor or a signing/network primitive — the
  existing grep-based purity guard (mirror borrow `test_private_client.py` static
  guard) must be extended to cover the hedge domain package.
- No PAPI PM testnet exists (recon §3.4). Therefore **CI proves behavior with
  fake/record transports only**; any real POST/private read/credential access/first
  real task is a separate human authorization outside this stage.

### 3.8 Live `fill-all` prohibition (concrete — item-4)

`post_fill_all` (`service.py:287`) currently runs a synchronous `while` loop that
dispatches many attempts inline. In **live** mode this is prohibited: it would
bypass the one-second cadence and the per-send gate. Required behavior: in live
mode `fill-all` must not synchronously bulk-POST; every send is owned by the
one-second scheduler and passes the same executor/Start gate (F-006,
`06-direction-synthesis` §F-006, `10-design` §Scope). Options for A: (a) make
`fill-all` a no-op-plus-409 in live mode with a message directing the operator to
the Start gate + scheduler; or (b) reduce it to "arm the task" (ensure running)
and let the scheduler drive. A records the choice; either way, **no synchronous
loop may POST**. The record/dry-run transport may keep a bounded synchronous
`fill-all` for tests since it never POSTs.

### 3.9 Migration / compatibility plan

- SQLite: additive-forward only. New tables (`hedge_open_attempt`,
  `hedge_open_leg`) and new nullable/defaulted columns on `hedge_open_task` /
  `hedge_open_settings` via `CREATE TABLE IF NOT EXISTS` + guarded `ALTER TABLE`
  (mirror the round-1 `_SCHEMA` idempotent pattern, `store.py:30`). Existing
  round-1 fills/tasks remain readable. `failure_pause_threshold` backfills to the
  default 3 for pre-existing rows.
- Config: `APP_HEDGE_EXECUTOR` default `disabled` preserves current behavior;
  invalid value clamps to `disabled` (server currently does this at
  `server.py:669`; move validation into `config.py` for parity with
  `borrow_executor`).
- API: additive fields only; existing consumers/tests that don't read them keep
  passing. Route table unchanged.

### 3.10 Deterministic test commands (A)

```text
python -m pytest backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py \
  backend/tests/test_hedge_executor.py backend/tests/test_hedge_service.py \
  backend/tests/test_hedge_api.py -q
python -m pytest backend/tests/test_hedge_open_live_client.py \
  backend/tests/test_live_hedge_executor.py -q
python -m pytest backend/tests/test_private_client.py -q   # purity/signer guard still green
python -m pytest backend/tests -q                          # full backend regression
```

(Exact runner path is A's to confirm from the repo's existing invocation; the
bookkeeper writes the pinned command into the R10 checklist, not the implementer.)

### 3.11 Risks and review focus (A)

- **Highest:** independent two-leg execution can leave a single filled leg. Policy
  = record + no auto-action; review must confirm no hidden residual gate,
  auto-repair, or fill-equality check was reintroduced (ADR-3).
- Durable-before-send atomicity: attempt + both legs must commit in one
  transaction with the executor invoked **outside** the lock (round-1 discipline,
  `store.py` header / `service.py:394`).
- No-resend invariant on unknown transport results; client-ID lookup before any
  classification.
- Purity: `hedge_open_tasks/**` imports no network/signing primitive; the live
  path lives only under `backend/services/`.
- Live gate correctness: real POST unreachable unless env+Start+preflight all hold;
  default config sends zero signed traffic.
- Decimal discipline end-to-end; no binary float on a quantity/price path.

---

## 4. Concrete cross-cutting decisions (consolidated)

### 4.1 Order-parameter model — FINAL

Both directions send `quantity=q_common`; margin leg `sideEffectType=NO_SIDE_EFFECT`,
`newOrderRespType=RESULT`; UM leg `positionSide=BOTH`, no `reduceOnly`. **No
`quoteOrderQty` anywhere.** (§0 resolution; PRD §6.2; ADR-1.)

### 4.2 Dispatch state machine

`PREPARED → DISPATCHING → ACCEPTED_OR_QUERYING → TERMINAL_RECORDED`, with a
`DISPATCHING → UNKNOWN_QUERYING → (ACCEPTED_OR_QUERYING | confirmed-absent)`
branch (`10-design` §Dispatch). Legs advance independently.

### 4.3 Preflight per pair

Fresh public filters (spot `GET /api/v3/exchangeInfo`, UM `GET /fapi/v1/exchangeInfo`),
directional PM balance, one-way position mode (`GET /papi/v1/um/positionSide/dual`),
PAPI order-rate availability (`GET /papi/v1/rateLimit/order`), and a conservative
price for min-notional. Reuse the existing signed-GET reader (`private_client.py`)
for private reads; do not fork the signer. A hedge-mode account or a missing
step/filter fails the pair closed (`domain.compute_preflight` already returns a
rejection when a market step is unreadable).

### 4.4 One-pair-per-second cadence — OPEN ITEM for A to resolve within the frozen contract

The round-1 `tick()` dispatches only `eligible[0]` — one attempt per tick across
all tasks. The frozen contract says "a task schedules one concurrent pair every
second." Two readings are consistent with the contract: (a) one pair per second
**per running task** (dispatch one attempt for **each** eligible task per tick),
or (b) the operator runs one task at a time and the single-eligible dispatch
suffices. **A should implement (a)** unless the bookkeeper/user narrows it,
because the PRD wording is per-task; A records the decision in the implementation
report. Either way the two legs **within** a pair are sent concurrently (frozen
§6.3.4). This is a scheduling nuance, not a contract change, so it is A's to
decide and disclose — not an R3 escalation.

### 4.5 `exposure_alert` / single-leg — advisory, not a scheduler gate

The frozen policy forbids single-leg fill from freezing scheduling. A must
**either** retire `STATUS_EXPOSURE_ALERT` **or** keep it as a non-blocking
advisory flag that does not stop the one-second loop and is not counted toward the
failure threshold. A must NOT keep the round-1 behavior where `post_start`/
`_require_fillable` (service.py:258/304) refuse to run an `exposure_alert` task —
that contradicts user policy #2. A records which path it took; review-2 checks it
against `04-user-execution-policy.md`.

### 4.6 Live fill-all — see §3.8. No synchronous POST loop in live mode.

---

## 5. Task B — Frontend (owner: Kimi)

### 5.1 Scope and file boundary

**Allowed:** `frontend/index.html`, `frontend/self-check.js` only.

**Forbidden:** all `backend/**`, all `docs/**`, the API contract itself (B renders
what A serves; a needed field that is missing is an A/contract question routed
through the bookkeeper, not a frontend-invented field).

### 5.2 What B renders (PRD §9.2, `00-task.md` Deliverable 5)

Additive display in the existing hedge task view (`index.html:1133` `#hedge-task-view`,
state at `index.html:1247` `hedgeTasks`/`hedgePositions`/`hedgeSettings`):
fixed base amount + planned attempt count + effective `q_common`; task / Start /
executor state; attempt timeline (per-attempt seq, direction, both legs'
order IDs + statuses); per-leg cumulative base/quote + weighted averages;
`consecutive_submission_failures` + `failure_pause_threshold` + `pause_reason`;
observed residual. The browser **never** signs, schedules, or contacts Binance
directly (ARCHITECTURE §System Boundaries; PRD §9.2). UI is Chinese-first per the
standing user decision (memory `ui-chinese-first`).

### 5.3 Contract self-check

`frontend/self-check.js` already mocks every hedge route (self-check.js:402-536).
B extends the mocks + DOM-id registry (self-check.js:161) to cover the new fields
and the attempt timeline, keeping the no-build vanilla-JS discipline (no
framework, no CDN).

### 5.4 Deterministic test command (B)

```text
node frontend/self-check.js      # (or the repo's existing self-check invocation)
```

Plus a manual same-origin smoke against the running backend once A lands (browser
load of the hedge view with `executor_mode=disabled`, asserting the new fields
render and no Binance call is made). The bookkeeper pins the exact command in the
R10 checklist.

### 5.5 Risks and review focus (B)

- No Binance/signing/scheduling logic leaks into the browser (hard boundary).
- Decimal strings rendered verbatim (no JS float reformatting of quantities/prices).
- Read-only executor/Start display; no UI affordance implies it can enable live.
- Backward-compatible rendering when a field is absent (graceful, no crash).

---

## 6. Parallel-development-mode: enablement + R10 checklist inputs

**Enable `docs/parallel-development-mode.md` (v0.5): YES.** Two tasks, one
per domain owner, `dispatch_protocol: "human-operator/v1"`.

**Embedded pre-review: recommend OFF (opt-out)** for this stage. Reason: backend
is single-owner (no intra-backend seam to pre-review), and the formal cross-review
gate (review-1 Kimi↔Claude-GLM) plus review-2 already cover the diff. If the
bookkeeper/user wants the extra checkpoint, it can be opted in per that document's
§ embedded-review rules; the R10 fields marked "opt-in only" then become required.
The R10 checklist below is written for the **opt-out** case.

### 6.1 R10 checklist inputs (machine-readable; belongs in `status.json`
`tasks[].r10_checklist`, NOT in the immutable PROMPT BODY — R10 v0.4 rule)

Task A (backend):

```json
{
  "task_prompt_path": "task-A-claude-glm.prompt.md",
  "self_tests_command": "python -m pytest backend/tests -q",
  "next_dispatch_executor": "human_operator",
  "max_rounds": 2,
  "pass_branch": "report PASS and stop for bookkeeper",
  "blocker_branch": "scope-contained fix then rerun self-tests; contract/schema/shared-field/live-gate changes escalate (R3)",
  "unavailable_branch": {
    "failure_classes": ["model_unavailable", "adapter_missing", "command_error", "permission_error", "timeout"],
    "escalation_artifact": "task-A-round1.dispatch.md"
  }
}
```

Task B (frontend):

```json
{
  "task_prompt_path": "task-B-kimi.prompt.md",
  "self_tests_command": "node frontend/self-check.js",
  "next_dispatch_executor": "human_operator",
  "max_rounds": 2,
  "pass_branch": "report PASS and stop for bookkeeper",
  "blocker_branch": "scope-contained fix then rerun self-check; any missing/renamed backend field escalates (R3) — never invent a field",
  "unavailable_branch": {
    "failure_classes": ["model_unavailable", "adapter_missing", "command_error", "permission_error", "timeout"],
    "escalation_artifact": "task-B-round1.dispatch.md"
  }
}
```

(`embedded_review_prompt_path`, `diff_patch_*`, `cross_review_*` are omitted
because embedded pre-review is opt-out for this stage.)

### 6.2 Human-operated dispatch / review packets the bookkeeper must prepare

I do **not** write implementation prompts (dispatch contract item 5). The
bookkeeper prepares, and the **human operator** executes, these packets — each
beginning with the fixed `[HARNESS-EXECUTOR-CONTRACT v1]` preamble (R11):

1. `task-A-claude-glm.prompt.md` — backend implementation (R9 packet + R10 tail
   with the pinned self-test command + landing paths + stop-for-bookkeeper).
2. `task-B-kimi.prompt.md` — frontend implementation (same structure, frontend
   paths).
3. After H_A/H_B commits + `diff_fingerprint` + `pre-review` validator:
   `30-review-1-backend.md` dispatch (implementer Claude-GLM → reviewer **Kimi**)
   and `30-review-1-frontend.md` dispatch (implementer Kimi → reviewer
   **Claude-GLM**) — provider-cross per `AGENTS.md` review-1 rule.
4. `50-review-2.md` dispatch — final gate, GPT/Codex first. **Reviewer-eligibility
   note:** the final reviewer should differ from designer / direction synthesizer /
   breakdown author. This breakdown was authored by **Claude Opus 4.8**
   (Anthropic). To keep review-2 provider-isolated from design involvement,
   **prefer GPT/Codex** for review-2; Claude may serve as review-2 only through
   the documented strong-reviewer disclosure override after a runner-level
   availability check fails (`AGENTS.md` §Reviewers / Strong-reviewer override),
   recording `reviewer_prior_involvement`.

### 6.3 dispatch-ready gate

Before any implementer starts:
`scripts/validate-stage.py 2026-07-hedge-open-real-api-v1 --phase dispatch-ready`
must pass (R10 checklist present, task/preamble paths, cross-review routing,
escalation branches) and the output preserved in stage evidence (Hard Gates).

---

## 7. Implementation sequence

1. **Freeze the §3.4 API contract + §3.3 schema** (bookkeeper records; this is the
   B-unblocking artifact). → verify: contract written into stage evidence; B may
   start against it + self-check mocks.
2. **A-1 domain**: task-snapshot threshold, acceptance-based classification,
   attempt/leg vocabulary, no-quoteOrderQty confirm. → verify: `test_hedge_domain.py`.
3. **A-2 store**: attempt/leg tables + task columns + additive migration +
   cumulative accounting. → verify: `test_hedge_store.py`.
4. **A-3 live client + executor + preflight provider** under `backend/services/`
   with allowlist + reused signer. → verify:
   `test_hedge_open_live_client.py` + `test_live_hedge_executor.py`; purity guard.
5. **A-4 service/scheduler**: durable-before-send, concurrent two-leg dispatch,
   reconciliation, failure counter/pause, live fill-all prohibition, one-second
   per-task cadence (§4.4). → verify: `test_hedge_service.py`.
6. **A-5 config + server wiring**: `APP_HEDGE_EXECUTOR` validation, live executor
   construction, sanitized lifecycle event; default-off proof. → verify:
   `test_hedge_api.py` + full `backend/tests`.
7. **B (parallel from step 1)**: render new fields + attempt timeline + executor/
   Start state; extend self-check. → verify: `node frontend/self-check.js`.
8. **Integration** (§8) once A + B land. → verify: §8 plan green.

Steps 2→6 are the serial backend chain owned by A; step 7 runs in parallel on the
frozen contract.

---

## 8. Integration test plan and strict no-real-POST constraints

### 8.1 Integration coverage (fake/record transports only)

- **Filter fallback**: `MARKET_LOT_SIZE.stepSize=0` → `LOT_SIZE` per constraint;
  zero/missing disables only that constraint (recon §2.2; already in
  `effective_market_step`).
- **Decimal format**: fixed-point serialization, no scientific notation, no float
  on quantity/price.
- **Direction shapes**: forward margin BUY + UM SELL; reverse margin SELL + UM
  BUY; `NO_SIDE_EFFECT`; `positionSide=BOTH`; no `quoteOrderQty`.
- **Durable-before-send**: assert attempt + both leg rows + both client IDs are
  committed before any executor send (inject a crash between commit and send;
  recovery queries by client ID, never resends).
- **Concurrent two-leg**: both legs dispatched for one pair; the next pair is not
  blocked by the prior pair's pending query/residual.
- **Client-ID reconciliation / no-resend**: timeout/5xx → `UNKNOWN_QUERYING` →
  client-ID query resolves accepted vs absent; write POST never auto-retried.
- **Failure counter/pause**: two accepted legs reset; confirmed-absent legs
  increment; reaching the task-snapshotted threshold pauses; threshold
  configurable (test with 1 and 3).
- **One-second scheduling**: monotonic-clock injection proves one pair per second
  per running task; missed time not replayed as a burst (round-1 `tick()` cursor
  discipline).
- **Rate-limit cooldown**: 429/418/-1008 blocks new sends without a fill-equality
  check.
- **Live bulk prohibition**: `fill-all` performs no synchronous POST loop in live
  mode.
- **Default zero real POST**: with `APP_HEDGE_EXECUTOR` unset/`disabled` and in
  `record`, assert **zero** network POST (the executor seam is a fake; a static
  purity guard asserts `hedge_open_tasks/**` imports no network/signing module).
- **Regression boundary**: public snapshot, borrow tasks, disabled + record
  transports unchanged.
- **Frontend**: `self-check.js` mocks assert the new fields + timeline render and
  the browser issues no Binance call.

### 8.2 Strict constraints (non-negotiable, enforced by tests + review)

- **No real POST** to Binance in any test or during implementation. All order/
  query traffic goes through injected fake/record transports.
- **No credential access**: tests never read real API keys; the live client accepts
  injected `urlopen`/credentials and is never given real ones in CI (mirror
  `portfolio_margin_borrow_client` constructor injection).
- **No private request**: no signed GET/POST leaves the process in CI. Preflight
  private reads are faked.
- **Signer reuse**: exactly one signer (`binance_signing.py`); the static guard
  must fail the build if a second signing primitive appears or if
  `hedge_open_tasks/**` imports hmac/hashlib/urllib.
- A live POST, a real private read, credential access, enabling `live`, turning on
  Start, or placing a first real task are **separate human authorizations** outside
  this stage (PRD §6.6, §11.2; ADR-4).

---

## 9. Summary for the bookkeeper

- Classify: MILESTONE (already so treated); parallel-development-mode ON, embedded
  pre-review OFF (opt-out).
- Two owners: **A = Claude-GLM (backend, the large serial chain)**, **B = Kimi
  (frontend, additive display)**; split only at the API seam; freeze §3.4 contract
  + §3.3 schema first.
- The §0 conflict is resolved: **frozen concurrent `q_common`, no `quoteOrderQty`**
  — implementers must not revert to the recon's serial/quoteOrderQty model.
- The round-1 dry-run outcome model (fill-based success, exposure pause, hardcoded
  threshold 3, synchronous fill-all) is the primary rework surface (§1.3).
- Review-2 should prefer GPT/Codex (this breakdown is Claude-authored; keep the
  final gate provider-isolated from design involvement).
- No code was written or changed in producing this breakdown.

---

当前 Session ID: unavailable (Claude Code CLI 未向本会话暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/12-development-breakdown.md
本地北京时间: 2026-07-23 19:57:00 CST
下一步模型: bookkeeper
下一步任务: archive this raw development breakdown; do not implement code
