# Fix Dispatch — Review-1 Round 3 (two P1s), scoped by user decision

Human operator: run in a **fresh, write-capable Claude-GLM session**
(`glm-5.2[1m]`) on branch `stage/2026-07-hedge-order-truth-v1`.

`rework_count`: this becomes **3 / 3 — the limit**. The user authorized
continuing (see §User decision). No further rework round is available without a
new explicit decision.

## User decision — this fix is NOT what the reviewer recommended

The reviewer proposed fixing Finding 2 by changing `classify_query_response` so a
malformed 2xx returns `None` instead of an UNKNOWN verdict. **The user rejected
that approach**, calling the malformed-2xx special-casing scope drift, and gave a
single rule instead:

> 这条畸形 2xx完全是脱裤子放屁的漂移需求，按照我说的只存第一条

and earlier:

> 我们先不做重试，只把第一次返回的结果保存留档，后续根据不同的异常我们再做针对的
> 优化，别想着一口就把任务完善完美，需求是在实盘中不断优化的

**The user's call is the better engineering here and that is why it is being
followed, not merely obeyed**: the reviewer's version changes *business
classification semantics* in a data-truth stage, which is riskier than bounding
growth in the storage layer. The user's rule leaves every business verdict, the
query loop, resend rules and rate-limit handling completely untouched.

### The rule, decided by the user 2026-07-28/29

> **One raw row per leg per `source`.** Before writing, check whether a row
> already exists for that leg and that source; if it does, skip.

`order_post` and `order_confirm` happen once per leg anyway, so in practice this
only bites `order_query`, which is the one that repeats.

**Do NOT implement a content digest, a content comparison, a UNIQUE index, a
migration, or a configurable N.** The bookkeeper proposed a digest-based dedupe
so a changed response (`NEW` → `FILLED`) would still record; the user rejected it
as over-design and was right on both counts — it is a digest plus an index plus a
migration plus its own test, and it may not bound anything at all, because
Binance order-detail bodies carry fields like `updateTime` that can differ
between polls, so "identical content" would often be false and the rows would
accumulate anyway. A plain per-leg-per-source cap has neither problem.

What this costs, recorded so it is not rediscovered as a surprise:

- The raw body of the **resolving** query is not kept once an `order_query` row
  exists for that leg. The leg row still records the outcome
  (`exchange_status` / `cumulative_quote_amt` / `order_id`), so the business
  truth is intact; what is lost is the exchange's verbatim text of that final
  read.
- If a leg's first `order_query` row is an uninteresting poll, a later `429` is
  not stored. **The user's explicit call**: 「429 就 429，遇到问题我们再分析问题
  解决问题，不做无谓的猜想适配方案」. Finding 1's fix still adds the missing
  persist call, so a rate-limited verdict is recorded whenever that leg has no
  `order_query` row yet.

### A behaviour to know about, NOT to change in this fix

`backend/hedge_open_tasks/service.py:1075-1077`:

```python
own = self._store.list_non_terminal_legs_for_task(task_id)
if own:
    return False  # still draining this pair; keep querying
```

While any leg is non-terminal the worker never reaches the dispatch branch below,
so **the task opens no further pairs**. A leg stuck on a malformed 2xx therefore
stalls that task's order opening — the row spam was the visible symptom, the
stall is the real consequence.

This is deliberate and correct: opening another pair while a leg's state is
unknown would add exposure blind. **Do not change it in this fix.** It is stated
here only so nobody mistakes the storage cap for a fix to the stall — they are
different things, and the stall is the frozen safe behaviour.

## The two findings, both bookkeeper-confirmed

### Finding 1 — drain's rate-limited query is never persisted

`backend/hedge_open_tasks/service.py`: inside `_reconcile_own_legs`, the
`if getattr(verdict, "rate_limited", False):` branch sets `drain_signal` and then
`continue`s — **before** reaching the `_persist_leg_raw(..., "order_query", ...)`
call further down the loop body. `classify_query_response`
(`live_hedge_executor.py:400-406`) returns a *conclusive* rate-limit verdict
carrying `raw_response`, so the evidence exists and is dropped.

This is in scope even after the user's T3 narrowing, because the narrowed
criterion explicitly lists **a rate-limit signal** among the conclusive verdicts
that must be persisted (`00-task.md` §T3).

**Fix**: persist it inside the rate-limited branch, before `continue`, using the
existing `_persist_leg_raw` with `source="order_query"`. Do **not** change the
branch's pause semantics, its non-terminal leg handling, or its never-resend
guarantee.

### Finding 2 — repeated identical query responses grow the raw table without bound

A 2xx whose body carries no usable `orderId` returns
`_empty_dispatch(leg, LEG_UNKNOWN_QUERYING, raw=raw)` — deliberately, so a
possibly-accepted order is never misjudged as absent. `_query_verdict_terminal`
returns `False` for it, so the leg stays non-terminal, drain re-queries it every
worker interval (~1s), and each round writes another row of up to
`BODY_MAX_BYTES`. Unbounded, and it falsifies `ADR-T4`'s stated bound of 2–6 rows
per attempt.

**Fix**: the dedupe rule above, in the storage layer.
**Do NOT change `classify_query_response`'s return values** — the malformed-2xx
branch keeps returning an UNKNOWN verdict with its raw, exactly as today.

## Where to implement

In the raw-persistence path — `store.append_raw_response`
(`backend/hedge_open_tasks/store.py:1743`) or its caller `_persist_leg_raw`
(`backend/hedge_open_tasks/service.py:1682`), whichever keeps the check inside
the existing short transaction.

The check is one existence test:

> Is there already a row for this `(attempt_id, leg, source)`? If yes, return
> without inserting.

Constraints:

- Stay inside `append_raw_response`'s **own short transaction**, so this can
  never touch the business write. That isolation is absolute and is already
  documented in the method's docstring.
- **No schema change.** No digest column, no UNIQUE index, no migration. If you
  believe one is warranted, stop and hand back rather than adding it.
- A skip is not an error: the caller must not log it as a failure or treat it as
  `raw_persist_failed`.

## Reading scope and budget

Line ranges, not whole files. **~10 KB / ~3k tokens.**

| Anchor | Why |
| --- | --- |
| `backend/hedge_open_tasks/service.py:1108-1155` | `_reconcile_own_legs`: the rate-limited branch and the existing `order_query` persist |
| `backend/hedge_open_tasks/store.py:1743-1800` | `append_raw_response` — where dedupe goes |
| `backend/services/live_hedge_executor.py:395-435` | `classify_query_response` — **read only to confirm you must NOT change it** |
| `reports/agent-runs/2026-07-hedge-order-truth-v1/00-task.md` §T3 | the narrowed criterion and the user's scope decision |
| `reports/agent-runs/2026-07-hedge-order-truth-v1/34-review-1-r3.md` | the verdict and the bookkeeper's confirmation |

Do not re-read whole files you have already inspected. If you materially exceed
this budget, stop and report.

## Required tests

Offline and deterministic; service-level where the behaviour is service-level.
Keep it to these three — do not build a suite:

1. A drain query returning 429 produces a retrievable `order_query` row when that
   leg has none yet, **and** the task still pauses exactly as today, the leg
   stays non-terminal, and nothing is resent.
2. Repeated malformed-2xx drain responses across several worker rounds produce
   **exactly one** `order_query` row for that leg — not one per round — and the
   leg still stays non-terminal and is still re-queried.
3. Existing `test_4f` / `test_4h` contracts still hold, and a raw-persistence
   failure still changes no business result.

Do **not** add a test asserting that a changed response writes a second row —
under this rule it does not, by design.

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

Baseline to beat: **1062 passed** (317 in the specified suite).
`test_hedge_open_live_client.py` and `test_hedge_purity.py` are must-run and
must-not-modify.

## File boundaries

**Allowed**: `backend/hedge_open_tasks/store.py`,
`backend/hedge_open_tasks/service.py`, and the minimum necessary among
`backend/tests/test_hedge_store.py`, `test_hedge_task_local.py`,
`test_live_hedge_executor.py`, `test_hedge_service.py`.

**Do not modify**: `backend/services/live_hedge_executor.py` — this fix
deliberately does not touch business classification; if you believe you must,
stop and hand back rather than widening scope. Also locked:
`hedge_open_live_client.py`, `wire_constraints.py`, `binance_signing.py`,
`scheduler.py`, `server.py`, `config.py`, `test_hedge_purity.py`,
`test_hedge_open_live_client.py`, `frontend/**`, `schemas/**`, `scripts/**`,
`docs/**`, `data/**`, and this stage's `status.json` / `70-handoff.md`.

## Safety (live surface is open)

Service PID 96409 runs in live mode, the Start gate is `1`, and a real naked
SHORT 10000 NOMUSDT is outstanding. No order, no card, no Start, no credentials,
no service start/stop, no write to `data/hedge-open-tasks.sqlite3`. Migrations
run only against temporary test databases.

## Closing

1. Run both commands; `60-test-output.txt` is overwritten then appended.
2. **Append** a section to `20-implementation.md`: what changed, the dedupe
   mechanism you chose and why, the new tests, and explicit confirmation that
   order verdicts, resend rules, rate-limit pause behaviour and
   raw-write-failure isolation are all unchanged.
3. **Do not commit.** Stop for the bookkeeper.

最后附上下面的 footer。

当前 Session ID: 报告你的 provider-native id，取不到就写 unavailable 并说明原因
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/20-implementation.md（追加章节）
本地北京时间: 用本地 date 命令取
下一步模型: bookkeeper
下一步任务: 核验修复、重算指纹、重跑 pre-review，然后重派 review-1

---

Current dispatch executor: **human operator**.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/35-fix-review-1-r3.dispatch.md
本地北京时间: 2026-07-28 23:20 CST
下一步模型: human operator
下一步任务: 在全新可写 Claude-GLM 会话执行本 packet
