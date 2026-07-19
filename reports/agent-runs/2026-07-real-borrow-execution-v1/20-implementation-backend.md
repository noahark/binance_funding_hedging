# 20 — Implementation Report: Task A Backend (A+B Durable Borrow-Task Core)

- Stage: `2026-07-real-borrow-execution-v1`
- Implementer: Claude-GLM (`glm-5.2`), Task A (backend scope)
- Slice: **A+B only** — zero Binance writes, zero authenticated reads, zero
  signing/credential/live-executor code, zero `maxBorrowable` path, no product
  interval floor/cap.
- Status: implementation complete; self-test suite green; round-1 review patch
  generated; Kimi embedded cross-review is **operator-dispatched** (see R10
  disposition). No commit, no edit to `status.json` / `70-handoff.md`.

## 1. Changed / new files (exact scope)

New (untracked — bookkeeper commits):

- `backend/borrow_tasks/__init__.py` — package exports.
- `backend/borrow_tasks/domain.py` — frozen vocabulary, validation, cursor,
  COALESCE effective-ts key, ISO microsecond representation. Pure, no SQLite.
- `backend/borrow_tasks/executor.py` — `ExecutorResult`, `BorrowExecutor`
  protocol, `DisabledBorrowExecutor` (only runtime-reachable executor).
- `backend/borrow_tasks/store.py` — SQLite task/attempt ledger + settings;
  fail-closed pending recovery; short transactions; RLock-guarded single conn.
- `backend/borrow_tasks/scheduler.py` — pure `select_next_task` + daemon thread.
- `backend/borrow_tasks/service.py` — HTTP-facing orchestration; two-phase
  dispatch (persist pending → invoke executor with no lock → resolve).
- `schemas/api/borrow-tasks/{task,task-list,log-page,scheduler-settings,error}.schema.json`
- `backend/tests/borrow_paper_executor.py` — test-only scripted executor
  (lives in the test tree; not importable from the product package).
- `backend/tests/test_borrow_{domain,store,scheduler,executor,api}.py`

Modified (tracked):

- `backend/app/server.py` — borrow route table + dispatch (`_try_borrow`),
  JSON body reader (size cap, content-type, UTF-8/JSON), 503/405/404 borrow
  routing, `build_server(..., borrow_service=None)`, `run()` wires borrow.
- `backend/config.py` — `borrow_executor` (default `disabled`; `from_env`
  rejects any other selection), `borrow_db_path` (default
  `data/borrow-tasks.sqlite3`).
- `.gitignore` — `data/` (SQLite store path).

Evidence:

- `60-test-output-backend.txt` — captured output of the three required commands.
- `embedded-review-A-round1.diff.patch` — exact review snapshot (scoped to
  Task A allowed paths only; Task B frontend changes excluded).
- `20-implementation-backend.md` — this file.

## 2. Test output summary

Exact commands from the task body, captured in `60-test-output-backend.txt`:

```
COMMAND 1 (borrow slice):  105 passed in 11.16s
COMMAND 2 (full backend):  499 passed in 29.20s
COMMAND 3 (git diff --check): exit 0
```

Coverage by file: domain parsing/validation/cursor/ISO (18), store durability +
per-category effects + cursor pagination + optimistic concurrency (15),
scheduler round-robin / fractional gap / cooldown / unknown-block / completion /
restart cursor (11), executor disabled/paper + zero-network AST proof + runtime
zero-urlopen + no-credential-leak (8), HTTP API — all §3.2 schema-validated
2xx + all 12 §3.7 error codes reachable/determinate + 503-unwired + snapshot/
healthz regression (21), plus the rest of the suite unchanged.

## 3. Contract decisions (deviations worth reviewer attention)

1. **Logs ordering = COALESCE newest-completion-first** (`store.list_attempts_page`,
   `domain.effective_ts_us`/`encode_cursor`). `13-amendment §3` overrides
   `12-breakdown §3.6`'s `id DESC`; the opaque cursor encodes the full
   `(effective_ts, id)` boundary so pages never overlap or skip. Verified by
   `test_pagination_newest_first_with_cursor_boundary` and the API
   `test_logs_pagination_cursor_boundary_and_schema` (disjoint page id sets).

2. **Tick semantics** (`service.tick`): first tick (no last-tick) dispatches
   immediately and seeds the cursor; later ticks dispatch only when
   `now >= last_tick + interval`, advancing `last_tick` by exactly one
   interval (not to `now`) so a 3-task/3s run yields A→B→C→A deterministically
   with an injected fake clock. `test_round_robin_abc_at_3s`.

3. **Two-phase dispatch, no lock across the executor call**
   (`service._dispatch_one`): txn-1 `insert_pending_attempt` (persists pending +
   advances cursor atomically) → executor invoked with **no** store lock /
   transaction → txn-2 `resolve_attempt`. Honors amendment §2.

4. **Fail-closed recovery** (`store.__init__`): on startup, any task with a
   leftover `pending` attempt gets `unresolved_attempt_id` set → ineligible
   until Boundary-C reconciliation. `test_restart_fail_closed_blocks_pending_attempt`.

5. **Store auto-creates its parent dir** (`store.__init__`): the default
   `borrow_db_path` lives under the gitignored `data/` dir, which is absent at
   checkout. The store `os.makedirs(parent, exist_ok=True)` before connecting.
   This prevents a startup `OperationalError` and keeps the three pre-existing
   `test_service_health` lifecycle tests (which call the real `run()`) green.

6. **`run()` calls `build_server(config, service)` 2-arg, then sets
   `_Handler.borrow_service` separately.** `build_server` keeps its 3-arg
   signature (`borrow_service=None` default) for direct / test injection, but
   `run()` preserves the original 2-arg call shape so the pre-existing
   `test_service_health` lifecycle tests — which monkeypatch `build_server` as a
   2-arg lambda — keep working. This was necessary because those tests are
   **outside Task A's allowed file scope** and could not be edited.

7. **borrow_tasks docstrings scrubbed of literal forbidden module names.** The
   pre-existing `test_private_client.test_single_hmac_exit_in_product_code` and
   `test_private_account_v1.test_single_hmac_exit_unchased_after_v03` grep ALL
   backend product code for the tokens `hmac`/`hashlib`/`signature =`. Documenting
   the prohibition by naming those modules in a docstring tripped the guards.
   Reworded to convey the same prohibition without the literal tokens. The
   Task-A zero-network proof is **AST-based** (`test_no_network_or_signing_imports_in_borrow_package`
   walks each module's import nodes), which is stricter and unambiguous vs a
   substring grep. (`test_private_*` are out of scope and were not edited.)

8. **Config rejects every non-`disabled` executor** (`config.from_env`): any
   `APP_BORROW_EXECUTOR` / `FUNDING_HEDGING_BORROW_EXECUTOR` value other than
   `disabled` raises `ValueError`. `PaperBorrowExecutor` is constructor-injected
   only and not exported from the product package
   (`test_paper_executor_lives_outside_product_package`).

9. **`POST /api/borrow-tasks` creates `borrowing` immediately** (no Start click
   needed); the backend scheduler can select it. In A+B runtime the only
   selectable executor is `DisabledBorrowExecutor`, which persists one sanitized
   `execution_disabled` row per attempt and performs zero I/O
   (`test_runtime_disabled_executor_persists_sanitized_row`).

## 4. Known limitations (A+B scope, by design)

- The **only** runtime-reachable executor is `DisabledBorrowExecutor`. There is
  no live Binance adapter, no signing, no `maxBorrowable`, no authenticated read.
  Boundary-C live execution is a separate stage.
- **Unknown-outcome unblock has no HTTP endpoint.** `service.clear_unresolved`
  is a Python-level test/operator seam; reconciliation of a genuinely unknown
  outcome is Boundary C.
- The scheduler thread is started by `run()`; with the disabled executor and
  eligible tasks it persists `execution_disabled` rows on the configured
  cadence. It is decoupled from the snapshot worker (neither imports the other).
- `latency_ms` / `effective_gap_us` are integer microseconds / ms derived from
  the wall clock; sub-millisecond latencies truncate toward zero — acceptable
  for A+B (no real network latency exists).

## 5. R10 disposition

- Round-1 review snapshot generated and scoped to Task A allowed paths:
  `embedded-review-A-round1.diff.patch` (20 file headers; no `frontend/**`,
  no `reports/**`, no out-of-scope files). Produced via `git add -N` (intent-to-
  add, non-committing) so the exact `git diff --binary -- <paths>` command
  captures untracked new files; the index was reset afterward, leaving the
  working tree pristine for the bookkeeper.
- Per the immutable Task A body (lines 114-119), **the Kimi embedded review is
  operator-dispatched**. The implementer terminal must not run the cross-model
  review in place of the operator; the bookkeeper reconciles afterward
  (`embedded-review-A.prompt.md` receipt `next_dispatch: executor: bookkeeper`).
  The operator command, verbatim from the task body:
  ```bash
  kimi --model kimi-code/kimi-for-coding -p "$(cat reports/agent-runs/2026-07-real-borrow-execution-v1/embedded-review-A.prompt.md)" | tee reports/agent-runs/2026-07-real-borrow-execution-v1/embedded-review-A-round1.raw-output.md
  ```
- This report deliberately does **not** end on a bare "waiting for review": it
  ships the full implementation, green tests, the scoped patch, and the
  reviewer-checklist self-audit below. Implementer-side, no blockers remain.

### 5.1 Self-audit against the embedded-reviewer checklist

| Reviewer concern | State | Evidence |
|---|---|---|
| Zero network / signing / credential path | ✅ | AST import scan `test_no_network_or_signing_imports_in_borrow_package`; runtime zero-urlopen `test_full_scenario_makes_zero_urllib_calls`; no-secret `test_poisoned_env_secrets_never_leak` |
| Disabled-only runtime executor | ✅ | `config.from_env` rejects non-`disabled`; `test_service_default_executor_is_disabled`; `test_runtime_disabled_executor_persists_sanitized_row` |
| Task creation immediately `borrowing` | ✅ | `test_create_task_returns_201_schema_valid_and_borrowing` |
| Decimal / microsecond handling | ✅ | `test_parse_interval_*`, `test_validate_amount_*`, `test_decimal_amount_echoed_verbatim_no_float`, `test_us_to_iso_*` |
| Transactional cursor/attempt invariants | ✅ | `insert_pending_attempt` is one atomic txn (pending row + cursor); `test_restart_fail_closed_blocks_pending_attempt` |
| No store lock during executor call | ✅ | `service._dispatch_one` releases txn-1 before `execute`; no `with self._lock`/`with self._conn` around the call |
| Unknown outcome blocks only its task | ✅ | `test_unknown_blocks_only_its_task_and_seam_unblocks`; `test_resolve_unknown_blocks_task` |
| Newest-completion-first opaque cursor | ✅ | `test_pagination_newest_first_with_cursor_boundary`; API disjoint-page test |
| Restart safety | ✅ | `test_restart_preserves_tasks_settings_cursor_attempts`; `test_cursor_survives_restart_mid_cycle` |
| Sanitized logs | ✅ | `log-page.schema.json` + `test_logs_pagination_*`; reasons are controlled vocabulary |
| Snapshot / PrivateClient contracts unchanged | ✅ | full suite (incl. all `test_private_*`, `test_snapshot*`, `test_*_endpoint`) green; `test_borrow_wiring_does_not_shadow_healthz_or_snapshot` |
| HTTP / schema / error behavior | ✅ | all 2xx validated against §3.2 schemas; all 12 §3.7 error codes reachable + validated against `error.schema.json` |
| No scope drift | ✅ | patch file headers are exactly Task A allowed paths; `frontend/**` (Task B) excluded |

## 6. Handoff

Next step (operator): run the Kimi command above, retain the unedited raw output
at `embedded-review-A-round1.raw-output.md`. On `PASS`, hand to the bookkeeper
to reconcile Task A. On a scope-contained `BLOCKER`, the implementer fixes only
allowed files, writes `embedded-review-A-round1.fix-note.md`, regenerates the
patch, and runs one more round (`embedded-review-A-round2.dispatch.md`). On a
contract/schema/cross-task/shared-surface issue, write an escalated
`embedded-review-A-round1.dispatch.md` and stop for the bookkeeper. The
implementer does not commit and does not write `status.json`.
