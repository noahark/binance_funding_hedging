# Development Breakdown — Hedge Open Live v1 (Round 1)

Breakdown author: Claude / Opus 4.8 (via Claude Code), `anthropic`. Design-
involvement artifact for review-2 disclosure. Author is NOT an implementer/fix
author. Grounded in `10-design.md`, `11-adr.md`, `design-inputs.md` (DI-1..DI-4),
and the two recon reports.

## Parallel mode: ENABLED (`docs/parallel-development-mode.md`, v0.5)
Two disjoint tasks with a design-frozen interface:
- **hedge-be** — backend `hedge_open_tasks` module + API + backend tests.
- **hedge-fe** — frontend wiring of the stage-1 UI to the frozen API + self-check.
Scopes are disjoint (`backend/**` vs `frontend/**`). The FE consumes only the
**frozen API contract in §3** (it does not wait for BE internals), so both run
concurrently. Embedded cross-review: OFF this round (standard committed-state
review-1 per task). Run `scripts/validate-stage.py <stage> --phase dispatch-ready`
before implementers start.

## 1. Owner split
| Task | Owner | Domain |
|---|---|---|
| hedge-be | **Claude-GLM** (`zhipu_glm`) | backend |
| hedge-fe | **Kimi** (`moonshot_kimi`) | frontend |

## 2. File boundaries (hard)
**hedge-be allowed:** `backend/hedge_open_tasks/**` (new), `backend/app/server.py`
(add hedge-open routes only, alongside borrow routes), `backend/tests/**` (new
hedge-open tests only), `schemas/api/hedge-open/**` (new schema files if added).
**hedge-fe allowed:** `frontend/index.html`, `frontend/self-check.js`.
**Both forbidden:** the other task's files; `borrow_tasks`/borrow routes;
`docs/**`, `reports/**` (bookkeeper), `AGENTS.md`, `.env*`, root config; any new
dependency; any real Binance network call in code or tests.

## 3. FROZEN interface contract (cross-task; implement verbatim)
Base path `/api/hedge-open-*`. All list/among JSON uses these exact field names.

### 3.1 Endpoints
- `POST /api/hedge-open-tasks` body `{coin, direction, mode, single_amount, target_n}`
  — **`single_amount` is a decimal STRING** `^[0-9]+(\.[0-9]+)?$` (money precision;
  post the raw user-entered string, never `Number(...)`); `target_n` is an
  integer; `mode="immediate"` this round. (R4-001 contract amendment 2026-07-23.)
  → `201` Task JSON. Preflight runs here; insufficient balance → `400`
  `{error:"insufficient_balance", direction, required, available}` (FE shows the
  stage-1 modal copy `正向开单 USDT 余额不足` / `反向开单现货余额不足`). Other
  invalid input → `400 {error:"invalid_field", field}`.
- `GET /api/hedge-open-tasks?status=<all|running|paused|deleted|done>` →
  `{tasks:[Task]}` (default excludes `deleted` unless `status=deleted|all`).
- `POST /api/hedge-open-tasks/<id>/{pause|start|delete|fill-once|fill-all}` → Task
  JSON. `delete` = soft delete (`status="deleted"`). Actions on a `deleted` task →
  `409 {error:"invalid_state"}`.
- `GET /api/hedge-open-settings` → `{executor_mode:"disabled"|"live", start_gate:bool, interval_seconds:1}`.
- `GET /api/hedge-open-logs?cursor=&limit=` → `{logs:[...], next_cursor}`.
- `GET /api/hedge-open-positions` → `{positions:[Position]}`.

### 3.2 Task JSON (stage-1 names + round-2-additions)
`{id, coin, direction:"forward"|"reverse", mode:"immediate"|"smooth",
single_amount, target_n, success_count, fail_count,
status:"running"|"paused"|"done"|"exposure_alert"|"deleted",
q_common, position_side_mode:"BOTH"|"hedge", leg_exposure:null|{leg,qty,price,ts},
created_at, updated_at}`

### 3.3 Fill JSON
`{id, task_id, ts, attempt_id,
spot:{client_order_id, order_id, status, filled_qty, avg_price},
perp:{client_order_id, order_id, status, filled_qty, avg_price}}`

### 3.4 Position JSON (stage-1 aggregation)
`{coin, direction, position_qty, spot_avg, perp_avg, open_basis_rate,
price_pnl, accrued_funding, borrow_interest, net_pnl}`

## 4. hedge-be internal contract (backend only)
- Module shape mirrors `borrow_tasks` (domain/store/service/executor). SQLite
  tables per `10-design §2`. Direction map / NO_SIDE_EFFECT / positionSide per
  `ADR-3` + DI-4. Common-grid `q_common` rounding per `ADR-2`/`10-design §4`
  (decimal fixed-point; reject on min/max/notional violation; never per-leg).
- Preflight `10-design §5` (exchangeInfo + balance + positionSide/dual +
  rateLimit/order; any read failure blocks Start).
- Immediate engine `10-design §6` (1s durable scheduler; concurrent dual-leg;
  **dry-run record transport, no network POST**; the live executor is only
  reachable with `APP_HEDGE_EXECUTOR=live` AND global Start ON).
- **Injectable dry-run outcome** (`10-design §6`, user decision): a seedable seam
  can force single-leg failures/exposures; default = balanced dual-leg fills.
- Single-leg exposure state machine + `>3`-fail termination per `ADR-4` /
  `10-design §7` (query order/trades/positionRisk by client id; never trust POST
  return alone; never resend same client id; no auto-remediation).
- Rate-limit throttle per `10-design §8`.

## 5. hedge-fe contract (frontend only)
- Replace the stage-1 fake engine with `fetch` calls to §3 endpoints; keep ALL
  UI (open columns, task cards, filters, `deleted` soft-delete, positions,
  balance modal). 立即开单 → `POST /api/hedge-open-tasks`. 平滑开单 → present but
  `disabled` with a `下一轮` hint. Execution badge shows `executor_mode` +
  `start_gate`. All new logic in the first `<script>` block (self-check parses it).
- `self-check.js`: mock the §3 API (same-origin) and assert create/lifecycle,
  soft-delete, positions-from-fills, disabled 平滑开单, exposure_alert rendering,
  and zero new cross-origin fetch. No real network.

## 6. Test evidence (required before stop)
- hedge-be: `python -m pytest backend/tests -q` green; include the new hedge-open
  tests (domain: direction map, common-grid rounding incl. mismatched steps,
  preflight accept/reject, single-leg classification, `>3`-fail, `deleted`;
  store round-trip + fills aggregation; record-transport asserts **no network
  POST**; safety: live path unreachable without both gates; injectable single-leg
  exposure exercised). Paste into `60-test-output.txt`.
- hedge-fe: `node frontend/self-check.js` exit 0, all existing + new `[PASS]`.
- Hard rule: **no test performs a real Binance request.**

## 7. Risk points (review focus)
1. **Common-grid rounding** (ADR-2): mismatched spot/perp steps must yield one
   equal `q_common`; independent rounding = exposure. Top correctness risk.
2. **Safety gate** (ADR-5): prove real POST unreachable unless
   `APP_HEDGE_EXECUTOR=live` AND global Start ON; no secrets in logs/record
   transport.
3. **Single-leg state machine** (ADR-4): reconcile via queries, not POST return;
   no resend of same client id; no auto-remediation.
4. **NO_SIDE_EFFECT / reverse no-auto-borrow** (ADR-3): reverse preflight uses
   `crossMarginFree`, not `maxBorrowable`.
5. **FE/BE contract fidelity**: FE consumes §3 field names verbatim; BE returns
   them verbatim. Any drift breaks the parallel seam.
6. **self-check coupling** (FE): new logic in the first `<script>`; existing
   `[PASS]` all preserved; no new cross-origin fetch/uncleared timers.
7. **Scope**: no websocket/smooth gate (next round), no repay/close, no new deps.

## 8. R10 dispatch tail (both task prompts must carry)
Each implementation prompt ends with: exact self-test command(s) above; the exact
artifact paths (`20-implementation-<task>.md` + shared `60-test-output.txt`);
and the stop-for-bookkeeper instruction (no commit, no status.json edit, no
relay). Prompts also carry the `[HARNESS-EXECUTOR-CONTRACT v1]` preamble.

## 9. Cross-review routing
- hedge-be (Claude-GLM) → review-1 **Kimi** (cross-provider).
- hedge-fe (Kimi) → review-1 **Claude-GLM** (cross-provider).
- review-2 (final, whole stage): Codex/GPT first (quota permitting), else Claude
  fallback with disclosure. Real-funds stage — apply full review discipline.

## 10. Dispatch
Human-operator-executed only. Bookkeeper prepares `task-hedge-be-claude-glm.
prompt.md` + `task-hedge-fe-kimi.prompt.md` (+ receipts), runs
`--phase dispatch-ready`, then the operator dispatches. R4 diff reconciliation
by the bookkeeper before H_A/H_B evidence commits.
