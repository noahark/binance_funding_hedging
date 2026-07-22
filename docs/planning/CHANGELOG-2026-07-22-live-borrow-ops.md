# Session changelog — 2026-07-22 live borrow ops & market UI

Status: user-directed product ops polish after Boundary C merge to local main.
Owner: User / Grok (implementation session).
Decisions: see `docs/planning/DECISIONS.md` (`DEC-2026-07-22-001` … `003`).

This file records **what landed in code/docs this session** so agents and
operators can resume without re-deriving chat history. It is not a formal stage
blackboard; formal Harness stages remain under `reports/agent-runs/`.

## Context

Boundary C live borrow (`APP_BORROW_EXECUTOR=live`) was already merged to local
main. Operator validation against real DEXE/CETUS traffic exposed classification,
logging, and UI issues. Changes were made as **fast product patches** with user
approval; formal dual-review stage delivery was deferred by the user.

## Product decisions (summary)

1. **Known rejection expands** so ordinary failures do not freeze the task:
   - All definite HTTP **4xx** (after rate-limit handling) → `known_rejection`
     (includes pool codes `51006/51014/51061` either sign, and auth `401/-2015`).
   - **Transport failures** (`timeout` / `connection_error` / missing status) →
     also `known_rejection` (**Scheme C**). Operator accepts possible over-borrow
     on ambiguous POST for high-frequency empty-pool hunting.
   - **5xx** and **malformed 2xx** (no valid `tranId`) remain `unknown` and still
     block for reconciliation.

2. **Borrow attempt log coalesce**: same task + same failure signature
   (`result_category` + `reason` + `business_code`) does not keep a second log
   row; only `finished_at` (and latency) on the previous failure row is refreshed.
   Success always keeps its own row. Unknown never coalesces.

3. **Display-only Binance error map** for common codes (auth + PM borrow family).

4. **Unified balance liability**: map `crossMarginBorrowed` →
   `private_account.balances_unified[].cross_margin_borrowed` and show on cards.

## Backend changes

| Area | Path | Change |
|------|------|--------|
| Live classify | `backend/services/live_borrow_executor.py` | 4xx → known_rejection; transport → known_rejection (Scheme C); 2xx/5xx unknown rules unchanged |
| Attempt resolve | `backend/borrow_tasks/store.py` | Same-failure coalesce against task `latest_result_*` |
| Coalesce set | `backend/borrow_tasks/domain.py` | `COALESCEABLE_FAILURE_CATEGORIES` |
| Error labels | `backend/borrow_tasks/binance_error_codes.py` | Curated map (not full official dump) |
| API projection | `backend/borrow_tasks/service.py` | Additive `business_code_name` / `_message` / `_message_zh` on tasks & logs |
| Private account | `backend/domain/snapshot.py` | `cross_margin_borrowed` from `crossMarginBorrowed` |
| Private client doc | `backend/services/private_client.py` | Documents liability mapping |
| Schemas | `schemas/api/borrow-tasks/*.json`, `schemas/api/public-market/snapshot.schema.json` | Additive fields |
| Tests | `backend/tests/test_live_borrow_executor.py`, `test_borrow_store.py`, `test_borrow_api.py`, `test_borrow_scheduler.py`, `test_binance_error_codes.py`, `test_private_account_v1.py` | Coverage for above |

## Frontend changes

| Area | Change |
|------|--------|
| Task card blocked UI | 「待对账·暂停调度」only when `unresolved` **and** `latest_result === unknown` (no flash during in-flight pending) |
| Nav badge | Count **`borrowing` only**; load tasks at boot so market view is not stuck at 0 |
| Default filter | Entering borrow view selects **借币中**, not 全部 |
| Official error text | Log + task note show curated zh/en labels when mapped |
| Create preview | Empty-state “创建预览：资产 X。输入…” removed; full preview only when amount+count set |
| Op column | `BSTOCK` and `PERP_ONLY_EXCLUDED` rows show `—` (no create controls) |
| Borrow status badge | Positive daily funding + classic borrowable → **正费率** (not green 已验证可借) |
| Market meta | Removed 「数据说明」panel; snapshot times under **市场表** title as **Beijing time** |
| Opening quotes | Prices use trailing-zero trim (`formatPriceTrimZeros`) |
| Unified balances | Show `已借: …`; **red** when borrowed amount &gt; 0 |

## Operator / data notes (local)

- Historical `execution_disabled` attempt spam and all borrow tasks were cleared
  during the session (local SQLite under `data/borrow-tasks.sqlite3`; backups
  named `*.bak-*` if still present).
- Tasks stuck on old `transport_error:*` as `unknown` were mechanically unblocked
  once to match Scheme C (marker cleared; category rewritten to known_rejection).
- **No durable `fail_count`**: only `success_count` + attempt ledger (with
  coalesce). Failure tallies require aggregating logs with awareness of coalesce.

## Explicitly not changed

- Manual order / spot-sell / full accounting execution.
- 5xx / malformed-2xx still block via `unknown` + recon.
- Crash-orphan pending → `crash_orphan_responseless` path still exists.
- Group C maxBorrowable still FR-4 only (~30 min component TTL); green
  「已验证可借」on negative-rate verified rows unchanged semantics except
  positive-rate rows now show 正费率.
- Formal Harness dual-review stage packaging for this session’s patches
  (user deferred).

## How to verify

```bash
# Backend
.venv/bin/python -m pytest backend/tests/test_live_borrow_executor.py \
  backend/tests/test_borrow_store.py backend/tests/test_private_account_v1.py -q

# Frontend
node frontend/self-check.js

# Runtime
# APP_BORROW_EXECUTOR=live + borrow keys + private channel as needed; restart server
```

## Related canonical docs updated this session

- `docs/planning/DECISIONS.md` — DEC-2026-07-22-001…003
- `docs/planning/ROADMAP.md` — as-built note
- `docs/development/DEVELOPMENT_GUIDE.md` — live borrow env & ops
- `docs/api/public-market-contract.md` — `cross_margin_borrowed`
