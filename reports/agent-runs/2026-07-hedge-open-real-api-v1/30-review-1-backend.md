# Review-1 — Backend Cross-Review (Hedge Open Real API v1)

> **Reviewer:** Claude Opus 4.6 (Thinking), Antigravity CLI.
> **Role:** `first_reviewer` (review-1 backend cross-review; implementer is `claude_glm` / `zhipu_glm`, Anthropic provider-isolated).
> **Disclosure:** This reviewer authored the API reconnaissance
> `reports/api-samples/2026-07-hedge-open-real-api-v1/order-model-and-live-seams-recon.md`
> (read-only factual audit, dated 2026-07-23T14:13). No delivery code, direction
> synthesis, or development breakdown was authored by this reviewer. The recon's
> serial/`quoteOrderQty` forward model was explicitly overridden by the user-approved
> fixed-`q_common` concurrent contract; this review treats the frozen contract as
> authoritative, not the recon's old suggestions.

---

## 0. Review methodology

All assertions below are grounded in actual file reads from the committed range
`bf31e8d757aac72c0ca4318ac606893f1af061ad..d90f2f18acec7fe6286f2ae3fc8e187580bf0793`.
The diff fingerprint was independently recomputed:

```
d90f2f18acec7fe6286f2ae3fc8e187580bf0793:3f22d26e58e6a0c120d17e1612306413c201c568c6d98463dc91d21b4cc6d843
```

This matches the dispatch-specified backend task fingerprint. No file was modified,
no command writing to the repository was executed, and no real Binance request was
made during this review.

### Artifacts actually read

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml` (review-1 sections)
- `docs/product/PRD.md` (§3, §6, §9.2)
- `reports/agent-runs/2026-07-hedge-open-real-api-v1/{00-task.md, 05-cadence-resolution.md, 06-direction-synthesis.md, 10-design.md, 11-adr.md, 12-development-breakdown.md, 13-r4-diff-reconciliation.md, 14-r4-verification.md, 20-implementation.md, 20-implementation-backend.md, 40-fix-backend-r4.md, 60-test-output.txt}`
- `reports/api-samples/2026-07-hedge-open-real-api-v1/order-model-and-live-seams-recon.md`
- `schemas/review-verdict.schema.json`
- The full git diff (`--stat` and per-file content) for the backend range
- Complete source of: `backend/services/{hedge_open_live_client.py, live_hedge_executor.py, hedge_preflight_provider.py}`, `backend/hedge_open_tasks/{domain.py, store.py, service.py}`, `backend/config.py`, `backend/app/server.py` (hedge wiring section)
- Complete source of: `backend/tests/{test_hedge_purity.py, test_hedge_open_live_client.py, test_live_hedge_executor.py}`

---

## 1. Summary assessment

The backend delivery is **sound and substantially complete**. It correctly implements the frozen `q_common` concurrent two-leg model, the durable-before-send invariant, the acceptance-based classification (keyed on `orderId`, not fill), the task-snapshotted `>=` threshold pause, the advisory single-leg exposure, the deny-by-default live adapter with single signer reuse, the per-task concurrent scheduling (R4-2), and the additive attempt timeline projection (R4-1). The default-off proof is credible: disabled/record modes are zero-real-POST, the live path requires four independent gates, and CI never constructs a live executor with real credentials.

The implementation correctly resolves the §0 conflict identified in the development breakdown: the recon's serial/`quoteOrderQty` forward model is NOT adopted — both directions use the same concurrent `q_common` with `quantity=` only, matching the frozen contract.

I found **no P0 findings** (blocking safety/correctness issues). I identified **two P2 findings** (non-blocking improvements) and **three P3 findings** (informational). The verdict is **ACCEPT**.

---

## 2. Findings

### P2-1: `recvWindow=60000` is at the API maximum; the recon recommends ≤5000

**File:** `backend/services/hedge_open_live_client.py`, `DEFAULT_RECV_WINDOW_MS = 60_000`

**Evidence:** The recon (§4.1) notes: _"recvWindow: 可选，默认 5000ms，不推荐 >5000"_ (supplied-doc fact L52013, L52030). The implementation uses the documented maximum of 60000ms. While technically valid (Binance accepts it), this creates a 60-second window where a replayed or delayed request could be accepted, which is wider than necessary.

**Impact:** Increased theoretical exposure to clock-drift-related request acceptance. In practice the single-transport-no-retry invariant and the client-ID uniqueness mitigate the residual risk. This is not a correctness bug — the API documentation allows up to 60000.

**Recommendation:** Consider reducing to 5000ms (the API default and the recon's recommendation) in a follow-up. This is not a required fix for stage acceptance; it is an optimization the final reviewer should assess for a product rule.

### P2-2: `_reconcile_pending` queries each non-terminal leg independently per tick without pagination

**File:** `backend/hedge_open_tasks/service.py`, `_reconcile_pending()`

**Evidence:** `list_non_terminal_legs()` returns all non-terminal legs across all tasks. For each one, a signed GET query is issued. If many tasks run concurrently and produce unknown/querying legs (e.g., during a network partition), this could issue many signed GETs in a single tick.

**Impact:** Under heavy load with many unknown legs, the reconcile pass could amplify API weight consumption beyond what the one-second cadence intends. The existing rate-limit cooldown gate mitigates cascading throttles, but the pass itself could trigger one.

**Recommendation:** Add a per-tick cap on reconcile queries (e.g., 5–10 legs per tick) in a follow-up stage. The current behavior is safe for the initial operational scope (few concurrent tasks) and is not a blocking issue.

### P3-1: `tick()` holds `self._lock` during the entire concurrent dispatch + join

**File:** `backend/hedge_open_tasks/service.py`, `tick()` method

**Evidence:** The lock is held from the `with self._lock:` entry through `_dispatch_eligible_concurrently()` (which spawns workers and joins them) and `_reconcile_pending()`. This means that `fill-once`/`fill-all` calls that also acquire `self._lock` will block during a tick's entire execution window.

**Impact:** Minimal — `fill-once`/`fill-all` are operator manual triggers, not automated paths. The lock prevents re-entry of `tick()` which is the correct behavior. The R4 fix report (§3.2) correctly identifies that `store` transactions use their own RLock, so the service lock only serializes the tick itself.

**Recommendation:** Documented and understood; no action needed. Future scaling could narrow the lock scope if fill-once latency becomes noticeable.

### P3-2: Intentional deviation from breakdown §4.3 is correctly documented

**File:** `backend/services/hedge_open_live_client.py` module docstring, `20-implementation-backend.md` §5.1

**Evidence:** The breakdown says preflight should reuse `private_client.py` for signed reads. The implementation correctly identifies that `private_client.py`'s allowlist lacks the needed PAPI endpoints and creates a separate, narrower client. This is recorded as an intentional deviation in both the module docstring and the implementation report.

**Impact:** None — the deviation is sound (avoids widening an existing frozen allowlist) and properly disclosed.

**Recommendation:** No action needed.

### P3-3: `leg_exposure` field survives last SUCCESS without clearing

**File:** `backend/hedge_open_tasks/store.py`, `_apply_task_counters()`

**Evidence:** The implementation report §5.5 notes that `leg_exposure` is not cleared on SUCCESS, retaining the "most recent single-leg exposure snapshot" semantics. This is disclosed as an intentional choice.

**Impact:** None for correctness — `leg_exposure` is advisory only (§4.5) and never gates scheduling. The field accurately represents the last single-leg exposure event.

**Recommendation:** No action needed for this stage; the disclosure is adequate.

---

## 3. Detailed verification of review focus items

### 3.1 Live adapter endpoint/params/signing/filter/Decimal/timeout/5xx query/no-resend

**Verified correct:**
- The 7-endpoint `ALLOWLIST` in `hedge_open_live_client.py` matches the recon's §3.1/§3.2/§4.1 endpoint table exactly. Host is hardcoded `papi.binance.com`, never caller-supplied.
- `_require_whitelisted()` raises `PermissionError` BEFORE any signing primitive runs — the gate-fires-before-signing test (`test_gate_fires_before_signing`) proves this with a boom-urlopen.
- Signing reuses the single `binance_signing.signed_payload` — no second signer exists. The `test_single_signer` purity guard in `test_private_client.py` and the domain package AST guard in `test_hedge_purity.py` enforce this.
- POST body is exact signed payload bytes (signature last); GET query string is exact signed bytes. No parameter split. `test_post_margin_order_body_is_signed_payload_signature_last` verifies this byte-for-byte.
- Write POSTs are one-shot (`_send` calls `urlopen` exactly once). `test_single_transport_attempt_no_retry` asserts `call_count == 1` after a 503.
- Unknown/timeout → query by `origClientOrderId`, never resend the write POST. `_send_one_leg` in `live_hedge_executor.py` classifies an exception as `unknown` → queries once → if still inconclusive, returns `UNKNOWN_QUERYING`. `test_dispatch_unknown_leg_resolved_by_single_client_id_query` proves one query count. `test_dispatch_unknown_leg_stays_unknown_when_query_inconclusive` proves unknown stays unknown.
- Decimal quantities use `_decimal_str` → `Decimal` → `format(d, "f")` end-to-end. No binary float on quantity/price paths. `compute_preflight`, `floor_to_grid`, `decimal_lcm` all operate on `Decimal`.
- Filter fallback: `effective_market_step` uses `MARKET_LOT_SIZE` when enabled, falls back to `LOT_SIZE`, treats zero/missing as "constraint disabled" — matches recon §2.2 / C-7.

### 3.2 Durable-before-send / failure count only on confirmed non-acceptance / task-snapshotted threshold

**Verified correct:**
- `store.prepare_attempt()` commits the immutable attempt + both leg records + both client IDs in a single `with self._lock, self._conn:` transaction BEFORE any executor call. `_dispatch_one_for_task` calls `prepare_attempt` first, then the executor.
- `_apply_task_counters` keys the counter on `classify_attempt()`, which checks `leg_is_accepted()` (= `order_id` is not None). An accepted pair (both `orderId` present) resets `consecutive_submission_failures` to 0 and increments `accepted_pair_count`. A confirmed failed pair (no `orderId` on either or both) increments `consecutive_submission_failures`. `UNKNOWN_QUERYING` does not touch the counter — it stays `querying` until resolved.
- `resolve_status_after_attempt()` uses `>=` comparison: `consecutive_submission_failures >= failure_pause_threshold` → paused. Tests `test_apply_failed_at_threshold_pauses` verify the 3rd failure pauses (not the 4th).
- `failure_pause_threshold` is task-snapshotted at creation time, backfilled to 3 for pre-existing rows. Per-task, configurable, not a module constant.

### 3.3 R4 attempts projection / prepared/querying coverage / legacy logs/cursor no regression / cross-table cursor

**Verified correct:**
- `list_attempts_page()` queries `hedge_open_attempt` + its two `hedge_open_leg` rows, ordered `created_at_us DESC, id DESC`, cursor on `(created_at_us, id)`. This covers PREPARED (no log row yet), QUERYING (legs mid-query), and resolved attempts.
- `get_logs()` returns three keys: `logs`, `attempts`, `next_cursor`. Legacy `logs` and `next_cursor` (tracking `log` rows) are unchanged. `attempts` is additive. `test_get_logs_includes_attempts_projection_for_record_fill` and `test_get_logs_attempts_includes_prepared_querying_attempt` verify both resolved and in-flight cases.
- Cursor is still based on the legacy `logs` table — `attempts` shares the same `(cursor_ts, cursor_id)` parameters but applies them to the `hedge_open_attempt` table's `(created_at_us, id)`. This is documented as an intentional choice (R4 report §6.1): attempts have no independent cursor, front-end consumes them with `limit=100`. For the initial scope this is adequate.

### 3.4 R4-2 per-task concurrency / no slow-card blocking / no same-task re-entry

**Verified correct:**
- `_dispatch_eligible_concurrently()` spawns one daemon worker thread per eligible task, starts all, then joins all. A slow card's executor call runs on its own worker; other workers are not blocked.
- `test_tick_dispatches_eligible_tasks_concurrently` uses a blocking executor with an Event gate: two tasks both enter dispatch (entered_count >= 2) BEFORE release. This is a deterministic concurrency proof (not a sleep race).
- `test_tick_slow_card_does_not_block_other_card_submission` routes one task to a blocking executor and another to a fast executor: the fast task completes while the slow task is still blocked.
- `tick()` holds `self._lock` during the entire join, preventing same-task re-entry across ticks. The store's RLock guards `prepare_attempt` transactions, preventing two workers from double-preparing the same task.

### 3.5 Disabled/record no network write / no real Binance access in tests / no credentials

**Verified correct:**
- Default `disabled` mode constructs `RecordTransportExecutor` — it records would-send params and returns simulated outcomes, never POSTs. `test_full_scenario_makes_zero_urllib_calls` monkeypatches `urlopen` and asserts zero calls.
- Domain package purity: `test_hedge_domain_package_imports_no_network_or_signing_primitive` AST-scans all `.py` files in `hedge_open_tasks/` for forbidden imports (hmac, hashlib, urllib, socket, http, requests, aiohttp). `test_hedge_domain_package_does_not_import_live_adapter` verifies no services-layer imports.
- Test fixtures use `FakeLiveClient` / `_FakeResp` / `_CapturingOpen` — never real credentials or real network access. The live client constructor accepts injectable `urlopen`; CI never passes `urllib.request.urlopen`.
- `test_private_client.py`'s urlopen guard allows only the known modules (extended to include the two new hedge HTTP clients).

### 3.6 Migration / thread-SQLite safety / recovery paths / regression tests

**Verified correct:**
- Migration is additive-forward: `CREATE TABLE IF NOT EXISTS` for new tables, guarded `ALTER TABLE ADD COLUMN` (using `PRAGMA table_info`) for new columns. `failure_pause_threshold` backfills to 3. Round-1 data preserved.
- `test_migrate_adds_new_columns_to_round1_db_and_keeps_rows` verifies idempotent migration on a pre-existing database.
- SQLite access is guarded by `self._lock` (an `RLock`) in `HedgeOpenStore`. All store methods that modify state use `with self._lock, self._conn:`. The RLock permits re-entrant calls within the same thread, which is correct for the worker model.
- Recovery: a post-commit crash leaves legs in `PREPARED`/`DISPATCHING` state. On the next tick, `list_non_terminal_legs()` picks them up and the reconcile pass queries by client ID — never resends the original POST (ADR-2). `_send_one_leg` queries once on unknown; if still inconclusive, leaves the leg for the reconcile pass.

### 3.7 Recon factual endpoint/filter conclusions vs. user-approved concurrent contract distinction

**Verified correct:**
- The recon's serial/`quoteOrderQty` forward model (B-1, C-1 through C-6) is NOT adopted. Both directions use `quantity=q_common` concurrently. The breakdown's §0 conflict resolution is correctly implemented.
- The recon's factual conclusions that ARE used: endpoint/method/weight table (§3.1–3.2), filter zero-value fallback (§2.2), HTTP 503/timeout reconciliation ladder (§3.3), rate-limit/429/418/-1008 facts (§4.4), and absence of PAPI PM testnet (§3.4). These are correctly applied in `classify_leg_response`, `classify_query_response`, and the filter computation pipeline.
- Order parameters correctly match the frozen contract: margin `sideEffectType=NO_SIDE_EFFECT`, UM `positionSide=BOTH`, `newOrderRespType=RESULT`, no `quoteOrderQty`, no `reduceOnly` on opens.

---

## 4. Verdict

The backend implementation is well-structured, correctly maps to the frozen
contract, properly gates real network access behind four independent gates,
maintains the durable-before-send invariant, and resolves both R4 findings.
The two P2 findings are non-blocking improvements for follow-up stages.

当前 Session ID: Antigravity CLI conversation 4094d12a-8eff-4a59-9455-05a05adefcc6
Session ID 来源: Antigravity CLI (Claude Opus 4.6 Thinking)
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/30-review-1-backend.md
本地北京时间: 2026-07-24 00:10 CST
下一步模型: bookkeeper
下一步任务: validate this Review-1 verdict and route ACCEPT to final Review-2 or REWORK to a bounded human-dispatched fix

---

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-open-real-api-v1",
  "role": "first_reviewer",
  "model": "Claude Opus 4.6",
  "verdict": "ACCEPT",
  "diff_fingerprint": "d90f2f18acec7fe6286f2ae3fc8e187580bf0793:3f22d26e58e6a0c120d17e1612306413c201c568c6d98463dc91d21b4cc6d843",
  "reviewer_prior_involvement": "design",
  "reviewer_prior_involvement_notes": "This reviewer authored the API reconnaissance (order-model-and-live-seams-recon.md) prior to this stage's implementation. No delivery code, direction synthesis, or development breakdown was authored. The recon's serial/quoteOrderQty model was overridden by the user-approved concurrent fixed-q_common contract; this review treats the frozen contract as the top-level authority.",
  "reviewed_artifacts": [
    "AGENTS.md",
    "docs/product/PRD.md",
    "schemas/review-verdict.schema.json",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/00-task.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/05-cadence-resolution.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/06-direction-synthesis.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/10-design.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/11-adr.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/13-r4-diff-reconciliation.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/14-r4-verification.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/20-implementation-backend.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-backend-r4.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt",
    "reports/api-samples/2026-07-hedge-open-real-api-v1/order-model-and-live-seams-recon.md",
    "backend/services/hedge_open_live_client.py",
    "backend/services/live_hedge_executor.py",
    "backend/services/hedge_preflight_provider.py",
    "backend/hedge_open_tasks/domain.py",
    "backend/hedge_open_tasks/store.py",
    "backend/hedge_open_tasks/service.py",
    "backend/config.py",
    "backend/app/server.py",
    "backend/tests/test_hedge_purity.py",
    "backend/tests/test_hedge_open_live_client.py",
    "backend/tests/test_live_hedge_executor.py",
    "git diff bf31e8d757aac72c0ca4318ac606893f1af061ad..d90f2f18acec7fe6286f2ae3fc8e187580bf0793"
  ],
  "findings": [
    {
      "severity": "P2",
      "title": "recvWindow=60000 is at the API maximum; recon recommends <=5000",
      "file": "backend/services/hedge_open_live_client.py",
      "line": null,
      "evidence": "DEFAULT_RECV_WINDOW_MS = 60_000. Recon §4.1: 'recvWindow: 可选，默认 5000ms，不推荐 >5000' (supplied-doc fact L52013, L52030). The Binance API default is 5000ms.",
      "impact": "Wider-than-necessary replay/clock-drift window for signed requests. Mitigated by client-ID uniqueness and single-transport-no-retry invariant.",
      "recommendation": "Consider reducing to 5000ms in a follow-up. Not a required fix: the API allows 60000 and the security invariants (client-ID, no retry) hold regardless."
    },
    {
      "severity": "P2",
      "title": "Reconcile pass queries all non-terminal legs per tick without a cap",
      "file": "backend/hedge_open_tasks/service.py",
      "line": null,
      "evidence": "_reconcile_pending() calls list_non_terminal_legs() (returns all non-terminal legs across tasks) and issues a signed GET for each. No per-tick batch limit.",
      "impact": "Under heavy concurrent usage with many unknown legs (e.g. during a network partition), the reconcile pass could issue many signed GETs in one tick, potentially triggering rate limits. The existing rate-limit cooldown gate mitigates cascading throttles.",
      "recommendation": "Add a per-tick cap on reconcile queries (e.g. 5-10 legs per tick) in a follow-up stage. Current behavior is safe for the initial operational scope."
    },
    {
      "severity": "P3",
      "title": "tick() holds service lock during entire concurrent dispatch + join + reconcile",
      "file": "backend/hedge_open_tasks/service.py",
      "line": null,
      "evidence": "The service _lock is acquired at tick() entry and held through _dispatch_eligible_concurrently (spawn + join) and _reconcile_pending. fill-once/fill-all calls that acquire _lock will block during the tick window.",
      "impact": "Minimal — fill-once/fill-all are manual operator triggers, not automated paths. The lock correctly prevents tick re-entry.",
      "recommendation": "No action needed for this stage. Documented and understood."
    },
    {
      "severity": "P3",
      "title": "Intentional deviation from breakdown §4.3 (preflight reads via own client) is correctly documented",
      "file": "backend/services/hedge_open_live_client.py",
      "line": null,
      "evidence": "Module docstring and 20-implementation-backend.md §5.1 both record the deviation: preflight reads use the hedge client's own allowlist rather than private_client.py's frozen allowlist.",
      "impact": "None — the deviation is sound and properly disclosed.",
      "recommendation": "No action needed."
    },
    {
      "severity": "P3",
      "title": "leg_exposure survives last SUCCESS without clearing — disclosed as intentional",
      "file": "backend/hedge_open_tasks/store.py",
      "line": null,
      "evidence": "Implementation report §5.5 documents this as 'most recent single-leg exposure snapshot' semantics. leg_exposure is advisory only (§4.5) and never gates scheduling.",
      "impact": "None for correctness. The field accurately represents the last single-leg exposure event.",
      "recommendation": "No action needed."
    }
  ],
  "required_fixes": [],
  "residual_risks": [
    "recvWindow=60000 is wider than the API default of 5000; consider tightening in a follow-up",
    "Reconcile pass has no per-tick query cap; safe for initial scope but should be bounded before scaling to many concurrent tasks",
    "The frozen contract deliberately accepts single-leg exposure risk (ADR-3); no automatic repair exists by design"
  ],
  "next_action": "continue"
}
```
