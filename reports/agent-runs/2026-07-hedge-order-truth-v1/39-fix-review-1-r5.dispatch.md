# Fix Dispatch — Review-1 Round 5 (two P1s), approach set by the user

Human operator: run in a **fresh, write-capable Claude-GLM session**
(`glm-5.2[1m]`) on branch `stage/2026-07-hedge-order-truth-v1`.

Both findings are confirmed. Both are consequences of two earlier scope decisions
colliding — this round makes the **code match the criteria**, so `00-task.md`
does not change.

## Fix 1 — delete the M1 migration

`backend/hedge_open_tasks/store.py`, `_migrate`, around lines 424-450.

M1 selects `exchange_status='FILLED' AND cumulative_base_qty > 0 AND
cumulative_quote_amt = '0'` and rewrites those rows to `NULL`. That is exactly
the cross-field inference the user's 2026-07-29 T1 decision put out of scope
(`00-task.md` §T1: *store what the exchange returned verbatim; no cross-field
consistency checking*), applied to historical data. It cannot tell a fabricated
placeholder from a literal `0` the exchange actually sent.

**Delete M1 entirely**, along with its `data_migration` audit write. Do not
narrow it, do not special-case `leg 6`, do not hardcode an `orderId`. History is
not rewritten on a guess; `leg 6` keeps its `0`, and its background is already
documented in `01-live-record-evidence.md`, which is where that knowledge belongs.

⚠️ **M2 stays.** It rewrites `leg_exposure.ts` from the 1970 epoch — that is T5
and has nothing to do with exchange figures. Do not touch it. After the change,
`_migrate` still runs M2 and is still idempotent.

Update `test_migrate_m1_m2_repair_defect_rows_audit_then_idempotent`
(`backend/tests/test_hedge_store.py:545-589`), which currently locks the M1
rewrite. It must now assert the opposite: a `FILLED` row with a positive quantity
and a literal `"0"` **still reads `"0"` after reopening the database**, M2's
timestamp repair still works, and the migration is still idempotent.

## Fix 2 — a decisive response replaces a non-decisive one, still one row

`backend/hedge_open_tasks/store.py`, `append_raw_response` (around 1769-1783),
and its caller `_persist_leg_raw` (`service.py:1682`).

Today the existence check returns early whenever a row exists for
`(attempt_id, leg, source)`. So a first `order_query` row holding a `NEW` or
`PARTIALLY_FILLED` poll blocks the later `FILLED` / confirmed-rejection /
confirmed-absent / rate-limited response — the four verdicts `00-task.md` §T3
names as conclusive and requires to be persisted.

**The rule stays "one row per leg per source."** What changes is which row wins:

> If a row already exists **and** the incoming response is **decisive**, replace
> that row's content in place. Otherwise skip, as now.

### The constraint that makes this correct — do not skip it

**Pass an explicit `decisive` flag into the persistence call. Do not infer it
inside the store, and do not let every later response overwrite.**

Only these four replace an existing row (`00-task.md` §T3):

| Decisive | Not decisive |
| --- | --- |
| a fill (`FILLED`) | `NEW` |
| a confirmed rejection | `PARTIALLY_FILLED` |
| a confirmed absent order (`404` / `-2013`) | anything inconclusive |
| a rate-limit signal (`429` / `-1003` / `418`) | |

Without the flag, a later `NEW` would overwrite an earlier `FILLED` — the same
bug with the sign reversed. **A decisive row is never replaced**, not even by
another decisive response: first decisive wins, so the record cannot churn.

The replacement must happen **inside `append_raw_response`'s own transaction and
lock**, like the existence check it extends. `order_post` and `order_confirm` are
written once per leg and are unaffected either way.

The caller decides decisiveness from the verdict it already has — the drain loop
knows whether the leg reached a terminal state and knows the rate-limited branch;
the immediate-fallback path knows whether `classify_query_response` resolved.
Do not re-derive it from the raw body inside the store.

### Required regression tests (the user named these three)

Service-level, offline, deterministic:

1. First query `NEW` or `PARTIALLY_FILLED`, then `FILLED` → **one** `order_query`
   row for that leg, holding the **FILLED** body.
2. First query non-decisive, then confirmed absent (`404` / `-2013`) → one row,
   holding the absent response.
3. First query non-decisive, then `429` → one row, holding the rate-limited
   response, **and** the task still pauses as today with the leg non-terminal and
   nothing resent.

Plus one guard the user's constraint implies:

4. First query `FILLED` (decisive), then a later non-decisive response → the row
   **still holds the FILLED body**. This is what proves the flag is real and not
   a last-write-wins overwrite.

Keep `test_4i` / `test_4j` passing — `test_4j`'s `query_calls > 2` assertion must
still hold, so the bound is still one row under repeated identical polling.

## What must not change

- T1: missing → `NULL`, no derivation; a literal `0` from the exchange stored as
  `0`.
- T2: `51169 → collateral_cap`, `pause_reason=collateral_cap_full`, the frozen
  Chinese copy verbatim.
- T3: the `order_post` / `order_confirm` / immediate-fallback persists.
- T5: the live-path timestamp, and M2.
- Credentials, signatures and API keys never reach the raw table.
- Raw-persistence failure never changes a business result.
- Order verdicts, resend rules, rate-limit pause semantics, terminality.

## Reading scope and budget

**~10 KB / ~3k tokens.** Line ranges, not whole files.

| Anchor | Why |
| --- | --- |
| `backend/hedge_open_tasks/store.py:415-470` | `_migrate` — M1 to delete, M2 to keep |
| `backend/hedge_open_tasks/store.py:1743-1800` | `append_raw_response` — the replace logic |
| `backend/hedge_open_tasks/service.py:1108-1160` | the drain loop and its two persist calls |
| `backend/hedge_open_tasks/service.py:1682-1700` | `_persist_leg_raw` — where the flag threads through |
| `backend/tests/test_hedge_store.py:545-589` | the migration test to invert |
| `00-task.md` §T1 and §T3 (with both Scope decisions) | the authority |

## Commands

```bash
cd "/Users/ark/Desktop/ai code/funding_hedging"
.venv/bin/python -m pytest \
  backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py \
  backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py \
  backend/tests/test_hedge_executor.py backend/tests/test_hedge_task_local.py \
  backend/tests/test_live_hedge_executor.py \
  backend/tests/test_hedge_open_live_client.py backend/tests/test_hedge_purity.py -q \
  2>&1 | tee reports/agent-runs/2026-07-hedge-order-truth-v1/60-test-output.txt
.venv/bin/python -m pytest backend/tests -q 2>&1 \
  | tee -a reports/agent-runs/2026-07-hedge-order-truth-v1/60-test-output.txt
```

Baseline: **1065 passed** (320 in the specified suite). Expect a small increase.

**Known flaky test**: `test_hedge_api.py::test_oversized_body_is_body_too_large`
has been seen failing once with `ConnectionResetError` and passing on re-run. If
you hit it, re-run that test in isolation and **report both results** — do not
"fix" it and do not silence it. It is filed as `p3-flaky-oversized-body-test`.

## File boundaries

**Allowed**: `backend/hedge_open_tasks/store.py`,
`backend/hedge_open_tasks/service.py`, and the minimum necessary among
`backend/tests/test_hedge_store.py`, `test_hedge_task_local.py`,
`test_live_hedge_executor.py`, `test_hedge_service.py`.

**Do not modify**: `backend/services/live_hedge_executor.py` if avoidable — it
has had a zero diff for two rounds; if threading the decisive flag genuinely
requires touching it, keep that change to the flag alone and say so explicitly in
the report. Locked outright: `hedge_open_live_client.py`, `wire_constraints.py`,
`binance_signing.py`, `scheduler.py`, `server.py`, `config.py`,
`test_hedge_purity.py`, `test_hedge_open_live_client.py`, `frontend/**`,
`schemas/**`, `scripts/**`, `docs/**`, `data/**`, and this stage's `status.json`
/ `70-handoff.md`.

## Safety (live surface is open)

Service PID 96409 runs in live mode, the Start gate is `1`, and a real naked
SHORT 10000 NOMUSDT is outstanding. No order, no card, no Start, no credentials,
no service start/stop, no write to `data/hedge-open-tasks.sqlite3`. The migration
change is verified only against temporary test databases.

## Closing

1. Run both commands.
2. **Append** to `20-implementation.md`: what M1's deletion changed and which
   test assertions were inverted; how the decisive flag is threaded and where
   decisiveness is decided; the four tests; and confirmation that everything in
   §What must not change is intact.
3. **Do not commit.** Stop for the bookkeeper.

最后附上下面的 footer。

当前 Session ID: 报告你的 provider-native id，取不到就写 unavailable 并说明原因
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/20-implementation.md（追加章节）
本地北京时间: 用本地 date 命令取
下一步模型: bookkeeper
下一步任务: 核验、重算指纹、重跑 pre-review，然后重派 review-1

---

Current dispatch executor: **human operator**.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/39-fix-review-1-r5.dispatch.md
本地北京时间: 2026-07-29 02:30 CST
下一步模型: human operator
下一步任务: 在全新可写 Claude-GLM 会话执行本 packet
