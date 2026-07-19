PASS

# Embedded Cross-Review — Task A Backend, Round 2 (raw output)

Reviewer: Kimi (`kimi-code/kimi-for-coding`), fresh read-only session (new
interactive session; round-1 transcript not resumed). No file under review was
modified, no commit, no Binance call. Evidence base: reviewer snapshot
`embedded-review-A-round2.diff.patch` (20 files), round-1 raw output and fix
note, the frozen contract set (`00-task.md`, `10-design.md`, `11-adr.md`,
`12-development-breakdown.md`, `13-user-decisions-and-contract-amendment.md`),
`docs/parallel-development-mode.md` R1–R10, current worktree source, and
independent read-only re-execution.

Snapshot fidelity (verified independently): `git apply --check --reverse` of
`embedded-review-A-round2.diff.patch` against the worktree succeeds for all 20
files, so the reviewed bytes are exactly the worktree bytes. The patch file set
is exactly the Task-A allowed scope (`.gitignore`, `backend/app/server.py`,
`backend/config.py`, `backend/borrow_tasks/**` ×6,
`backend/tests/borrow_paper_executor.py` + `test_borrow_*.py` ×5,
`schemas/api/borrow-tasks/*.schema.json` ×5). No frontend or out-of-scope file.

Inter-round delta (verified independently): both round patches were applied to
pristine `HEAD` trees in `/tmp` and diffed; the round-1→round-2 content delta
is exactly the six files named by `embedded-review-A-round1.fix-note.md`
(`store.py`, `server.py`, `service.py`, `domain.py`, `test_borrow_store.py`,
`test_borrow_api.py`). No drive-by edits between rounds.

Commands run (read-only, independently re-executed this round):

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_borrow_domain.py
  backend/tests/test_borrow_store.py backend/tests/test_borrow_scheduler.py
  backend/tests/test_borrow_executor.py backend/tests/test_borrow_api.py
  -q -p no:cacheprovider
  → 113 passed in 15.41s
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
  → 507 passed in 32.13s
git diff --check
  → clean
```

Plus an independent 17-assertion probe (SQLite in `/tmp`, in-process server on
an ephemeral loopback port; script kept outside the repo): ALL-OK.

---

## Round-1 repair verification (all four confirmed fixed)

1. **Resolved `unknown` keeps its persisted marker across close/reopen —
   FIXED.** `backend/borrow_tasks/store.py:165-171` now wraps the startup
   recovery subquery in `COALESCE(<pending-subquery>, unresolved_attempt_id)`:
   a pending-orphan marker is still added (fail-closed) while an
   already-persisted marker survives. Regression test
   `test_restart_preserves_unknown_outcome_block`
   (`backend/tests/test_borrow_store.py:79-101`) covers reopen-preservation
   plus test-seam unblock; the pending-orphan half stays covered by
   `test_restart_fail_closed_blocks_pending_attempt`. Independent probe:
   task A + resolved-unknown → marker set, ineligible → close/reopen → marker
   `== att.id` preserved, still ineligible → `clear_unresolved` restores
   eligibility. Satisfies breakdown §3.8/§6.1-1 and acceptance 4.
2. **Unsupported methods follow the frozen 405 JSON — FIXED.**
   `backend/app/server.py:98-116` adds `do_DELETE`/`do_PATCH`/`do_HEAD`/
   `do_OPTIONS`, each routed through `_try_borrow`; borrow-prefix paths answer
   `405 method_not_allowed` JSON, non-borrow paths answer the same 404 JSON as
   `do_POST`/`do_PUT`, and `_send_borrow` (`server.py:250-253`) omits the body
   for HEAD. Independent probe: `DELETE /api/borrow-tasks`,
   `PATCH /api/borrow-logs`, `HEAD /api/borrow-tasks` (empty body, JSON
   content-type), `OPTIONS /api/borrow-scheduler-settings`,
   `DELETE /api/borrow-tasks/{id}/pause` all → 405 JSON; non-borrow DELETE →
   404 `not_found` JSON. No stdlib 501 HTML anywhere on these paths.
3. **Unknown body keys rejected as 400 `invalid_field` — FIXED.**
   `domain.reject_unknown_keys` (`domain.py:150-159`) names the offending
   field; called before field validation in `create_task`
   (`service.py:143`), `post_edit` (`service.py:186`) and `put_settings`
   (`service.py:251`) against module-scope whitelists. Independent probe:
   `bogus_field` on create, `zzz` on edit, `bogus` on settings → each 400
   `invalid_field` with the field named in `detail`.
4. **16384-byte cap enforced on body-optional mutations before mutation —
   FIXED.** `_drain_body` (`server.py:286-307`) enforces `BODY_MAX_BYTES` and
   returns a 413 tuple; `_borrow_start`/`_borrow_pause`/`_borrow_delete`
   short-circuit on the error before dispatching (`server.py:325-344`).
   Independent probe: 17000-byte pause body → 413 `body_too_large` JSON, and
   the task status is unchanged (`borrowing` before and after — no state
   mutation); a subsequent normal pause still returns 200.

## High-risk Task A invariants re-checked (no findings)

- Zero network/signing/credential: grep of `backend/borrow_tasks/**` shows no
  `urllib`/`http.client`/`socket`/`hmac`/`hashlib`/`requests`/`ssl` import;
  `test_borrow_executor.py` retains the AST import proof
  (`test_no_network_or_signing_imports_in_borrow_package`), the runtime
  `urlopen`-boom proof (`test_full_scenario_makes_zero_urllib_calls`) and the
  poisoned-env no-leak proof; that file is byte-untouched between rounds.
- Disabled-only runtime executor: `Config.borrow_executor` default `"disabled"`,
  `from_env` raises `ValueError` for any other selection
  (`backend/config.py:174-186`); `PaperBorrowExecutor` exists only under
  `backend/tests/` and is not referenced by any product module.
- Immediate `borrowing` creation (`store.py:194-200`, 201 test green) per
  amendment §1.
- Decimal/microsecond discipline unchanged: string-only interval at the
  boundary, regex+`Decimal`, exact integer µs (`"0.5"`→500000,
  `"0.0000001"` rejected), no product floor/cap; amounts echoed verbatim.
- Dispatch two-phase split intact (`service.py:277-300`): pending attempt +
  cursor advance in one short transaction, executor invoked with no store
  lock/transaction held (amendment §2), resolution in a second short
  transaction. The round-2 edits did not touch this path.
- Per-task unknown block: `resolve_attempt` sets `unresolved_attempt_id` only
  for `unknown` (`store.py:457-462`); eligibility excludes marked tasks; no
  HTTP unblock endpoint; Python-only test seam.
- Newest-completion cursor semantics intact (`store.py:477-499`,
  `ORDER BY COALESCE(finished_at_us, dispatched_at_us, scheduled_at_us) DESC,
  id DESC` with the opaque cursor encoding the full `(ts, id)` boundary —
  amendment §3); pagination tests green.
- Restart safety: tasks/settings/cursor/soft-deletion/latest-result plus both
  unresolved-marker halves (pending-orphan add, resolved-unknown preserve)
  tested and green.
- Sanitized ledger: closed result-category vocabulary, typed `ExecutorResult`
  fields only; no headers/queries/signatures/raw payloads.
- Snapshot/PrivateClient/public-market surface untouched: `git diff --stat
  HEAD -- backend/services backend/domain backend/adapters
  schemas/api/public-market` is empty; `server.py`'s round-2 hunks are
  additive to the borrow dispatch only; existing-route regression test green.
- HTTP/schema/errors: all §3.7 codes reachable/deterministic/schema-valid,
  every 2xx validated against the five §3.2 schema files, 503-when-unwired
  works; 507/507 full-suite green.
- No scope drift: patch touches exactly the allowed file set; `.gitignore`
  gains only `data/`; no frontend file in the Task-A patch.

## Verdict

**PASS.** All four round-1 findings are verifiably repaired in scope, the
inter-round delta is confined to the six fix-note files, the frozen A+B
invariants hold, and both test commands plus `git diff --check` are green.
Per R4 the two-round local cap is now consumed; on this PASS the next step is
the bookkeeper's R4 diff reconciliation and serial H_A commit. This is an
embedded checkpoint, not formal Review-1.

当前 Session ID: unavailable (interactive Kimi session; provider-native session ID not exposed to the model — operator may backfill per docs/model-adapters.md)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/embedded-review-A-round2-retry-1.raw-output.md
本地北京时间: 2026-07-19 19:45:00 CST
下一步模型: bookkeeper（人工/记账会话）
下一步任务: 对 Task A 执行 R4 落盘前 diff 对账，生成 H_A 提交并推进串行落盘流程
