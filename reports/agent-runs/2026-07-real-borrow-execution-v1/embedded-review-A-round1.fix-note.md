# Embedded Review Round 1 — Fix Note (Task A Backend)

- Stage: `2026-07-real-borrow-execution-v1`
- Implementer: Claude-GLM (`glm-5.2`), Task A
- Reviewer: Kimi (`kimi-code/kimi-for-coding`), round 1 read-only session
- Review verdict: **BLOCKER** — one must-fix invariant (Finding 1) + three minor
  HTTP-validation strictness gaps (Findings 2-4). All four are **scope-contained
  implementation defects inside Task A's allowed files** — explicitly *not* an
  R3 contract/cross-task escalation; no contract amendment needed.
- Driver: `task-A-embedded-review-round1-fix.dispatch.md` (R3/R4 permitted local
  repair, cap 2 rounds).
- Result: all four fixed in-scope; both Task A test commands green
  (`60-test-output-backend.txt`); `git diff --check` clean; round-2 reviewer
  snapshot regenerated. No commit, no edit to `status.json` / `70-handoff.md`,
  no schema/contract change, no frontend touch.

## Summary of changes

| Finding | File(s) changed (all Task-A allowed) |
|---|---|
| 1 — restart preserves unknown block | `backend/borrow_tasks/store.py` |
| 2 — 405 on unsupported methods | `backend/app/server.py` |
| 3 — reject unknown JSON keys | `backend/borrow_tasks/domain.py`, `backend/borrow_tasks/service.py` |
| 4 — 16384-byte cap on body-optional mutations | `backend/app/server.py` |
| regression/proof tests | `backend/tests/test_borrow_store.py`, `backend/tests/test_borrow_api.py` |

No file outside Task A's original allowed scope was modified.

## Finding 1 — Restart silently clears the unknown-outcome block (severity: high)

- **Root cause.** `BorrowTaskStore.__init__` ran an unconditional
  `UPDATE borrow_task SET unresolved_attempt_id = (<pending-subquery>)`. A task
  blocked by a *resolved* `unknown` attempt has `outcome='resolved'` on its
  attempt row, so the pending-subquery yields NULL and the persisted marker was
  wiped — the blocked task silently re-entered the round-robin after a restart.
- **Fix (`backend/borrow_tasks/store.py`).** Wrap the subquery in
  `COALESCE(<pending-subquery>, unresolved_attempt_id)` so a pending-orphan
  marker is still *added* (fail-closed), but an already-persisted marker is
  *preserved*. One-line semantic change; same short transaction at startup.
- **Proof.** `test_restart_preserves_unknown_outcome_block` creates task A →
  paper `unknown` → asserts `unresolved_attempt_id == att_id` and
  `list_eligible_tasks() == []` → `close()` → reopens a fresh store on the same
  path → asserts the marker survived (`== att_id`) and the task is still
  ineligible → test-seam `clear_unresolved` restores eligibility. The existing
  `test_restart_fail_closed_blocks_pending_attempt` still covers the
  pending-orphan half.

## Finding 2 — Unsupported methods answer stdlib 501 HTML, not the frozen 405 (severity: low)

- **Root cause.** `server.py` only defined `do_GET`/`do_POST`/`do_PUT`; any
  other method fell through to `BaseHTTPRequestHandler`'s default 501 HTML on
  borrow paths, breaking §3.1 ("any other method on these paths → 405").
- **Fix (`backend/app/server.py`).** Added `do_DELETE`/`do_PATCH`/`do_HEAD`/
  `do_OPTIONS`, each routing through `_try_borrow(<method>)` so a borrow-prefix
  path answers the frozen `405 method_not_allowed` JSON (method not in any
  route's allowed set) and a non-borrow path answers the same `404 not_found`
  JSON as `do_POST`/`do_PUT`. `_send_borrow` now omits the message body for
  `HEAD` (RFC 9110 §9.3.2) while still advertising `Content-Length`.
- **Proof.** Parametrized `test_static_error_codes_...` gains
  `method_not_allowed_delete_collection` (`DELETE /api/borrow-tasks` → 405) and
  `method_not_allowed_patch_logs` (`PATCH /api/borrow-logs` → 405), each
  validated against `error.schema.json`. Plus a dedicated
  `test_unsupported_head_on_borrow_path_returns_405` proving HEAD also returns
  405 JSON with an empty body.

## Finding 3 — Unknown JSON fields silently accepted (severity: low)

- **Root cause.** `create_task` / `post_edit` / `put_settings` read named keys
  off the body via `body.get(...)` and ignored anything else, so a typo'd or
  extra key was silently dropped (§3.7 wants `invalid_field` naming the field).
- **Fix.** New helper `domain.reject_unknown_keys(body, allowed)` raises
  `invalid_field` naming the first unexpected key (sorted, all extras listed in
  `detail`). `service.py` calls it **before** field validation for all three
  mutations, against whitelists `_CREATE_BODY_KEYS` / `_EDIT_BODY_KEYS` /
  `_SETTINGS_BODY_KEYS` defined at module scope.
- **Proof.** `test_static_error_codes_...` gains
  `invalid_field_unknown_key_create` (`POST /api/borrow-tasks` with
  `bogus_field` → 400 `invalid_field`, schema-valid). Dedicated
  `test_edit_rejects_unknown_field` and `test_settings_rejects_unknown_field`
  assert 400 + `invalid_field` + the offending name in `detail`.

## Finding 4 — 16384-byte cap not enforced on body-optional mutations (severity: low)

- **Root cause.** `_drain_body` read `Content-Length` unbounded for the
  body-optional task mutations (start/pause/delete), so a 17000-byte pause body
  was swallowed and answered 200 instead of 413.
- **Fix (`backend/app/server.py`).** `_drain_body` now returns a
  `(status, payload)` error tuple for an oversized (`413 body_too_large`) or
  malformed (`400 invalid_json`) body using the same `BODY_MAX_BYTES` cap, else
  drains and returns `None`. The three callers (`_borrow_start`/`_borrow_pause`/
  `_borrow_delete`) send the error and short-circuit before dispatching.
- **Proof.** `test_pause_oversized_body_returns_413` sends a 17000-byte pause
  body (no content-type, as body-optional) and asserts `413 body_too_large`,
  schema-valid. The existing parametrized `body_too_large` case (create) still
  covers the body-required path.

## No contract / scope expansion occurred

- The four fixes are pure implementation strictness: one durability invariant
  tightened, one HTTP method coverage completed to the existing §3.1 contract,
  one input-validation gap closed against the existing §3.7 contract, one body
  cap extended to a sibling code path. No schema file, no error code, no route,
  no status machine, no executor, and no config surface changed.
- A+B invariants are untouched: still zero Binance writes / authenticated reads
  / signing / credential / live-executor / `maxBorrowable` / product interval
  floor-or-cap; still `disabled`-only configuration; still two-phase dispatch
  with no store lock held across the executor call.
- Files touched are exactly the Task-A allowed set; `frontend/**`, snapshot /
  private-client modules, public-market schemas, `status.json`, `70-handoff.md`,
  Harness/workflow files, and credentials were not modified; nothing committed.

## Test results (full capture in `60-test-output-backend.txt`)

```
COMMAND 1 (borrow slice):  113 passed   (was 105; +8 round-1 fix tests)
COMMAND 2 (full backend):  507 passed   (was 499; +8, no regressions)
COMMAND 3 (git diff --check): exit 0
```

## R10 round-2 tail

- Reviewer snapshot regenerated (including untracked new backend files via
  `git add -N`, non-committing) at `embedded-review-A-round2.diff.patch`, scoped
  to the same Task-A paths. Index reset afterward so the working tree is
  pristine for the bookkeeper.
- Per the dispatch, the fresh Kimi read-only round-2 review is
  **operator-launched** against the immutable `embedded-review-A.prompt.md`,
  with raw output preserved as `embedded-review-A-round2.raw-output.md` and the
  invocation recorded in `embedded-review-A-round2.dispatch.md`. On PASS, stop
  for the bookkeeper. A remaining scope-contained issue must NOT start a third
  local round — escalate to the bookkeeper (R4 caps at two). Any
  contract/schema/cross-task issue is an immediate R3 escalation.
