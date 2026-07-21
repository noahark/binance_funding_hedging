# Task C Implementation Intake Audit — Fix Required Before Review

Audit role: stage bookkeeper (`codex` / GPT), read-only inspection of the
uncommitted Task C implementation and its fake-only test evidence. This is not
review-1 and does not increment the formal rework counter.

## Disposition

`IMPLEMENTATION_FIX_REQUIRED`

The reported test commands are green, but four frozen-contract gaps remain in
the exercised implementation. The stage stays in `implementing`; no evidence
commit, fingerprint, pre-review validation, or Kimi review-1 dispatch is
authorized until the original implementer fixes them and the bookkeeper
re-audits the result.

## Findings

### BK-C-001 — P1 — Real loan-record responses are never parsed

`PortfolioMarginBorrowClient.records_from` accepts only a top-level JSON list.
The archived public evidence says the endpoint returns an envelope, and the
current official Binance response example is
`{"rows":[...],"total":1}`. Consequently a real successful
`GET /papi/v1/margin/marginLoan` response currently normalizes to `[]`; an
ambiguous POST can never be reconciled to proven success.

The correction must parse the documented `rows` envelope, validate the
contract shape fail-closed, and avoid declaring uniqueness when pagination is
incomplete (`total` exceeds the locally inspected rows) unless all relevant
pages were actually inspected. Tests must use the documented envelope rather
than a synthetic top-level list.

Evidence:

- `reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/raw/query-margin-loan-record.md`
- `backend/services/portfolio_margin_borrow_client.py:220`
- `backend/tests/test_portfolio_margin_borrow_client.py`
- `backend/tests/test_live_borrow_executor.py:190`
- Official current contract and example:
  `https://developers.binance.com/en/docs/catalog/advanced-trading-derivatives-trading-portfolio-margin/api/rest-api/account#query-margin-loan-record-user_data`

### BK-C-002 — P1 — “cross-task” ambiguity is not implemented or tested

The executor filters one response by asset and principal and treats one
remaining row as uniquely attributable. It has no access to, and the service
does not consult, any other task or attempt. The claimed cross-task test only
uses an ETH response while reconciling a BTC task; it does not create two local
tasks or attempts. With two tasks that have the same asset and amount in an
overlapping dispatch window, one history row can therefore be credited to the
wrong task, contrary to the frozen fail-closed rule.

The correction must perform durable local-ledger attribution before resolving
success. At minimum, a candidate already attributed to another attempt, or an
overlapping unresolved attempt from another task with the same asset and exact
Decimal amount, must keep the current task blocked. Add a real two-task test:
one documented-envelope row, same asset and amount, overlapping dispatch
windows, and no automatic success attribution. Keep a positive non-ambiguous
case so the gate does not disable all reconciliation.

Evidence:

- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/10-design.md` (D6)
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.md` (§5.3 and §9.10)
- `backend/services/live_borrow_executor.py:205`
- `backend/borrow_tasks/service.py` (`_reconcile_pass`)
- `backend/tests/test_live_borrow_executor.py:219`

### BK-C-003 — P1 — The 418 minimum cooldown and manual re-arm can be bypassed

`set_execution_enabled(True, now_us)` clears both `requires_rearm` and
`global_cooldown_until_us` immediately. The current test explicitly starts one
microsecond after a simulated 418 and expects the 300-second minimum to vanish.
That violates the frozen “300s minimum local cooldown, then manual Start” rule
and also lets Start erase an active ordinary 429/-1003 cooldown. Separately, a
418 returned by a reconciliation GET is reduced to a generic rate-limit
outcome, so the store never persists `requires_rearm=1` and execution
auto-resumes after 300 seconds.

The correction must make an active exchange cooldown non-bypassable by Start,
require both local expiry and a subsequent manual Start for 418, and preserve
the manual-rearm signal from reconciliation GET through service/store. Add
tests for early Start, post-expiry Start, ordinary cooldown non-bypass, and a
reconciliation-GET 418 that remains blocked after time expiry until manual
re-arm.

Evidence:

- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/10-design.md` (D5)
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.md` (§5.1)
- `backend/borrow_tasks/store.py:426`
- `backend/borrow_tasks/service.py` (`_reconcile_pass`)
- `backend/services/live_borrow_executor.py` (`classify_reconcile_response`)
- `backend/tests/test_borrow_store.py:360`

### BK-C-004 — P2 — Required sanitized startup observability is absent

The server emits only `borrow_execution_mode` with mode and ownership. It does
not emit the frozen distinct missing-credential startup event carrying
`borrow_executor=live` and
`borrow_execution_blocked=borrow_credentials_missing`, and it does not report
the frozen live-authorized/recovered-orphan startup counts. Status API behavior
is present, but it does not replace the required lifecycle evidence.

Add the distinct sanitized event and startup counts without logging either
credential name's value, response bodies, signed data, or environment values.
Cover it through the existing lifecycle test seam in
`backend/tests/test_service_health.py` (allowed conditionally by the original
task packet).

Evidence:

- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/10-design.md` (D2 and D7)
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.md` (§3.4 and §4.2)
- `backend/app/server.py:493`

## Audit Boundaries

- No live or authenticated Binance request was made by this audit.
- No credential source was read.
- No implementation source was edited by the bookkeeper.
- Existing implementation evidence is preserved; the original implementer
  must append its correction evidence and stop again for bookkeeper intake.

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation-bookkeeper-audit.md
本地北京时间: 2026-07-21 08:46:32 CST
下一步模型: human operator → Claude-GLM / GLM-5.2
下一步任务: execute task-C-bookkeeper-fix-1.prompt.md; fix BK-C-001 through BK-C-004 with fake-only tests and stop for bookkeeper re-audit

---

## Fix 1 Re-audit — Partial Closure

Re-audited at `2026-07-21 09:32:08 CST` against the amended implementation,
new tests, raw receipt, and append-only test output.

Disposition: `FIX_2_REQUIRED_BEFORE_REVIEW`

- `BK-C-002`: **CLOSED.** The service now consults a durable store attribution
  gate before crediting a reconciliation match. Candidate transaction IDs
  already claimed elsewhere and another task's unresolved Decimal-equal
  asset/amount attempt block attribution. Unit and two-task service tests cover
  the negative and positive paths. The implementation is deliberately more
  conservative than a timestamp-overlap-only gate, which is fail-closed.
- `BK-C-003`: **CLOSED.** Start preserves an unexpired ordinary/418 cooldown;
  418 remains manually armed after time expiry until a later Start; a
  reconciliation-GET 418 now carries and persists the re-arm signal. Store,
  executor, and service tests cover all four required cases.
- `BK-C-004`: **CLOSED.** Startup emits sanitized recovery counts and a distinct
  `borrow_execution_blocked` event for live mode without dedicated credentials.
  The real wiring derives credential presence from the dedicated client and
  lifecycle tests verify required fields and redaction.
- `BK-C-001`: **PARTIAL.** The real `rows` envelope and the
  `total > len(parsed_rows)` pagination case are fixed, but several malformed
  or mismatched envelopes still prove success instead of failing closed.

### BK-C-001 residual deterministic reproductions

All five inputs below currently return `ReconcileOutcome(matched=True, ...)`:

1. a unique matching row with missing `total`;
2. a unique matching row with boolean `total=true`;
3. one returned row with inconsistent `total=0`;
4. a known-attempt `tran_id="555"` whose response row says `txId="999"`;
5. a unique row missing the documented `timestamp` field.

Root cause:

- `declared_total()` correctly returns `None` for malformed totals, but
  `reconcile()` blocks only when `total is not None and total > len(records)`;
  `None` and `total < len(records)` fall through to success.
- The known-ID path sends `txId` as a query parameter but never verifies
  response-row `txId == attempt.tran_id`.
- Candidate matching does not validate the complete frozen row contract
  (`txId`, `asset`, `principal`, `timestamp`, `status`) before using a row as
  proof.

Required closure is narrowly specified in
`task-C-bookkeeper-fix-2.prompt.md`. No evidence commit or review dispatch is
authorized until these reproductions become `matched=False` and the complete
fake-only suite is green.

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation-bookkeeper-audit.md
本地北京时间: 2026-07-21 09:32:08 CST
下一步模型: human operator → Claude-GLM / GLM-5.2
下一步任务: execute task-C-bookkeeper-fix-2.prompt.md; close the residual BK-C-001 fail-closed gaps, rerun fake-only tests, and stop for bookkeeper re-audit

---

## Fix 2 Re-audit — Code Closed, One Evidence Test Correction Required

Re-audited at `2026-07-21 10:12:03 CST`.

Disposition: `MICRO_FIX_3_TEST_EVIDENCE_REQUIRED`

The residual BK-C-001 implementation behavior is now closed:

- all six deterministic negative reproductions return `matched=False`;
- complete-envelope and known-ID positives still return the expected canonical
  transaction IDs;
- raw rows are retained for whole-envelope validation;
- malformed/missing/inconsistent totals, malformed members, known-ID mismatch,
  and out-of-window response-less candidates fail closed.

One frozen required-test scenario was accidentally weakened by the stricter row
contract. In
`test_reconcile_multiple_confirmed_not_matched`, the second CONFIRMED row lacks
`timestamp`. The test therefore returns `matched=False` at the earlier
malformed-row gate; it no longer proves that **two fully contract-valid matching
CONFIRMED rows** stay ambiguous. The new independent
`test_reconcile_malformed_row_not_silently_dropped` already covers malformed
members, so these are distinct evidence obligations.

The original implementer must make the second row contract-valid (including a
timestamp) and keep both otherwise matching the same task/amount, then rerun the
specified fake-only checks. No product source change is authorized. This is
prepared in `task-C-bookkeeper-fix-3.prompt.md`.

Bookkeeper also removed a model-added paste-ready adapter command from the
fix-2 receipt's immutable Prepared Packet section. The prompt authorized the
implementer to fill only the Receipt; the executed receipt content itself is
preserved.

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation-bookkeeper-audit.md
本地北京时间: 2026-07-21 10:12:03 CST
下一步模型: human operator → Claude-GLM / GLM-5.2
下一步任务: execute task-C-bookkeeper-fix-3.prompt.md; restore the fully contract-valid multiple-candidate ambiguity test, rerun fake-only checks, and stop for bookkeeper

---

## Fix 3 Re-audit — Intake Closed

Re-audited at `2026-07-21 10:30:57 CST` against the one-line test-data diff,
the filled human-operator receipt, the amended implementation report, and the
append-only test evidence.

Disposition: `CLOSED_READY_FOR_COMMITTED_REVIEW_EVIDENCE`

- The second row in `test_reconcile_multiple_confirmed_not_matched` now carries
  `timestamp=1500`. Both returned rows satisfy the frozen five-field row
  contract, both match the same BTC / exact-Decimal principal, their transaction
  IDs differ, and `total == len(rows) == 2`. The negative result therefore
  reaches and proves the intended multiple-candidate ambiguity gate.
- `test_reconcile_malformed_row_not_silently_dropped` remains independently
  present, so malformed-envelope and fully valid ambiguity obligations are not
  conflated.
- The micro fix changed no product source. The bookkeeper independently reran
  parser/matcher tests (`59 passed`), the complete backend suite (`624 passed`),
  Harness validator tests (`114 passed`), frontend self-check, byte compilation,
  and the whitespace check; all passed.
- `BK-C-001`, `BK-C-002`, `BK-C-003`, and `BK-C-004` are closed. There are no
  remaining bookkeeper intake findings. This closure authorizes only local
  committed evidence preparation and fresh Kimi review-1 dispatch preparation;
  it does not declare review, acceptance, merge approval, or live Binance write
  authorization.

No real/authenticated/production-reachable Binance request was made, and no
credential source was read.

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation-bookkeeper-audit.md
本地北京时间: 2026-07-21 10:30:57 CST
下一步模型: bookkeeper → human operator → fresh Kimi
下一步任务: create committed review evidence and fixed diff fingerprint, pass pre-review validation, then have the human operator execute the prepared Kimi review-1 packet
