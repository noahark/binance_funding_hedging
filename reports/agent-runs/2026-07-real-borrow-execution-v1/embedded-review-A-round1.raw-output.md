BLOCKER

# Embedded Cross-Review — Task A Backend (round 1, raw output)

Reviewer: Kimi (`kimi-code/kimi-for-coding`), fresh read-only session. No file
under review was modified; no commit; no Binance call. Evidence base: the raw
reviewer snapshot `embedded-review-A-round1.diff.patch` (3065 lines, read in
full), the frozen contract set (`00-task.md`, `10-design.md`, `11-adr.md`,
`12-development-breakdown.md`, `13-user-decisions-and-contract-amendment.md`),
`docs/parallel-development-mode.md` R1–R10, and independent read-only
re-execution against the worktree.

Snapshot fidelity (verified independently): all 17 new files in the patch are
byte-identical to the worktree, and the 3 tracked-file sections
(`.gitignore`, `backend/app/server.py`, `backend/config.py`) are byte-identical
to a fresh `git diff --binary` over the same paths. The reviewed bytes are the
bytes tested.

Commands run (read-only):

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_borrow_domain.py
  backend/tests/test_borrow_store.py backend/tests/test_borrow_scheduler.py
  backend/tests/test_borrow_executor.py backend/tests/test_borrow_api.py
  -q -p no:cacheprovider
  → 105 passed in 11.67s
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
  → 499 passed in 28.64s
git diff --check
  → clean
```

Plus three targeted read-only probes (SQLite in `/tmp`, in-process server on an
ephemeral loopback port) cited per finding below.

---

## Finding 1 — BLOCKER (severity: high; scope-contained; NOT an R3 escalation)

**Restart silently clears the unknown-outcome block.**

- Evidence: `backend/borrow_tasks/store.py:158-165` (patch lines 1126-1133).
  `BorrowTaskStore.__init__` runs
  `UPDATE borrow_task SET unresolved_attempt_id = (SELECT MAX(a.id) FROM
  borrow_attempt a WHERE a.task_id = borrow_task.id AND a.outcome = 'pending')`
  unconditionally. A task blocked by a *resolved* `unknown` attempt (the normal
  unknown-outcome path: attempt row has `outcome='resolved'`) matches no pending
  row, so the subquery yields NULL and the persisted marker is wiped.
- Independent repro (read-only, DB in `/tmp`): create task A → paper `unknown`
  → `unresolved_attempt_id = 1`, `list_eligible_tasks() = []`; close and reopen
  the store → `unresolved_attempt_id = None`, `list_eligible_tasks() = ['A']`.
  The blocked task silently re-enters the round-robin after a backend restart.
- Contract violation: `12-development-breakdown.md` §3.8 ("on startup the store
  reloads tasks, settings, cursor, and **unresolved markers as persisted**"),
  §6.1-1 ("unresolved ⇒ ineligible; **the invariant holds across restart**"),
  `00-task.md` acceptance 4 ("unknown outcome stays blocked until a test
  executor resolves it"), and the ADR-004 fail-closed intent ("a
  timeout/ambiguous response must never be treated as safe to retry"). The
  startup UPDATE correctly adds fail-closed markers for orphaned *pending*
  attempts, but it must not overwrite an already-persisted marker (e.g.
  `COALESCE(unresolved_attempt_id, <pending-subquery>)`, or restrict the UPDATE
  to tasks that actually have a pending row). A regression test (unknown-block
  survives close/reopen) is missing — the existing restart test covers only the
  pending-orphan case.
- Scope containment: entirely inside Task A allowed files
  (`backend/borrow_tasks/store.py`, `backend/tests/test_borrow_store.py`). No
  contract, schema, or cross-task surface is affected. Fix locally per R3 and
  re-run round 2.

## Finding 2 — minor (severity: low; scope-contained)

**Non-GET/POST/PUT methods on borrow paths answer 501 HTML, not the frozen 405
JSON.** Evidence: `backend/app/server.py` defines only `do_GET`/`do_POST`/
`do_PUT` (`:67`,`:88`,`:93`); other methods fall through to
`BaseHTTPRequestHandler`'s default. Live probe: `DELETE /api/borrow-tasks` and
`PATCH /api/borrow-logs` both return `501 text/html`. Contract:
`12-development-breakdown.md` §3.1 "Any other method on these paths → 405" with
the §3.7 JSON error shape. Fix inside `server.py` (e.g. route `do_DELETE`/
`do_PATCH`/`do_HEAD`/`do_OPTIONS` through `_try_borrow`'s 405 path for borrow
prefixes).

## Finding 3 — minor (severity: low; scope-contained)

**Unknown body fields are silently accepted.** Live probe:
`POST /api/borrow-tasks` with `{"asset":"BTC","amount_per_attempt":"1",
"success_target":1,"bogus_field":1}` → `201`. Contract: §3.7
"Unknown/missing/mistyped fields → `invalid_field` with the field name in
`detail`". Same gap in `post_edit` and `put_settings`
(`backend/borrow_tasks/service.py:137`, `:180-201`, `:244-249`). Fix inside
`service.py` (whitelist-check body keys before field validation).

## Finding 4 — minor (severity: low; scope-contained)

**The 16384-byte body cap is not enforced on body-optional mutations.**
Evidence: `_drain_body` (`backend/app/server.py:263-269`) reads
`Content-Length` unbounded. Live probe: `POST /api/borrow-tasks/{id}/pause`
with a 17000-byte body → `200` (cap would require `413 body_too_large`, §3.7).
Fix inside `server.py` (apply the same `BODY_MAX_BYTES` check in
`_drain_body`).

---

## Verified OK against the frozen contract (no findings)

- Zero network/signing/credential: `backend/borrow_tasks/**` imports only
  stdlib non-network modules; AST import proof, runtime `urlopen`-boom proof
  and poisoned-env no-leak proof all present and green; config surface adds no
  credential path.
- Disabled-only runtime executor: `Config.borrow_executor` defaults to
  `"disabled"`; `from_env` raises `ValueError` for any other selection;
  `PaperBorrowExecutor` lives in `backend/tests/` only and is not exported from
  the product package; service default is `DisabledBorrowExecutor` returning
  sanitized `execution_disabled` with zero I/O.
- Creation is immediately `borrowing` (store insert + 201 API test), matching
  amendment §1.
- Decimal/microsecond discipline: interval is string-only at the boundary
  (JSON number rejected `invalid_interval`), regex + `Decimal` + exact integer
  µs normalization (`"0.5"`→500000, `"0.0000001"` rejected), no product
  floor/cap; amounts echoed verbatim; no float on value paths.
- Transactional invariants: pending attempt + cursor advance in one short
  transaction before dispatch; executor invoked with no store lock/transaction
  held (amendment §2); resolution in a second short transaction; no-eligible
  ticks record nothing and keep the cursor.
- Unknown blocks only its task while others keep rotating; Python-only
  `clear_unresolved` test seam; no HTTP unblock endpoint. (Restart half of this
  invariant is Finding 1.)
- Log ordering: `ORDER BY COALESCE(finished_at, dispatched_at, scheduled_at)
  DESC, id DESC` with opaque cursor encoding the full `(ts, id)` boundary —
  conforms to amendment §3 (which supersedes the breakdown's `id DESC`).
- Restart durability of tasks/settings/cursor/soft-deletion/latest-result and
  fail-closed pending-orphan recovery are tested and pass.
- Sanitized ledger: closed result-category vocabulary, typed `ExecutorResult`
  fields only, no headers/queries/signatures/raw payloads stored or exposed.
- Snapshot/PrivateClient/public-market schema untouched; `server.py` diff is
  additive and borrow dispatch cannot shadow existing GET routes (regression
  test green).
- HTTP/schema/errors: all 12 §3.7 codes reachable, deterministic and
  schema-valid; every 2xx validated against the §3.2 schema files;
  503-when-unwired works. (Edge gaps are Findings 2-4.)
- No scope drift: patch touches exactly the allowed file set; no `conftest.py`
  change; `.gitignore` gains only `data/`; no frontend/snapshot/private-client
  file in the diff.

## Verdict

**BLOCKER.** One must-fix invariant violation (Finding 1) plus three minor
HTTP-validation strictness gaps (Findings 2-4). All four are scope-contained
implementation defects inside Task A's allowed files — this is **not** an R3
contract/cross-task escalation; no contract amendment is needed. Per R10:
implementer fixes within `backend/borrow_tasks/store.py` (+ regression test),
`backend/app/server.py`, `backend/borrow_tasks/service.py`, writes
`embedded-review-A-round1.fix-note.md`, regenerates the patch, and re-runs one
more round (cap 2).

当前 Session ID: unavailable (interactive Kimi session; provider-native session ID not exposed to the model — operator may backfill per docs/model-adapters.md)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/embedded-review-A-round1.raw-output.md
本地北京时间: 2026-07-19 18:42:46 CST
下一步模型: Claude-GLM（Task A 实现者）
下一步任务: scope 内修复 Finding 1-4，写 fix-note，重新生成 diff.patch，按 R10 触发 round 2 预审
