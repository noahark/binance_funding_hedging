# Fix Dispatch — Review-1 Round 6 (one P1: the API layer re-fabricates the zero)

Human operator: run in a **fresh, write-capable Claude-GLM session**
(`glm-5.2[1m]`) on branch `stage/2026-07-hedge-order-truth-v1`.

**Smallest fix of the stage: delete three `or "0"` fallbacks.** Everything else
is tests.

## What is wrong

`backend/hedge_open_tasks/service.py`, three projection helpers — `_leg_to_doc`
(~214-216), `_entry_spot_leg` (~277/285), `_entry_perp_leg` (~295/303) — all do:

```python
base  = D.Decimal(leg.get("cumulative_base_qty") or "0")
quote = D.Decimal(leg.get("cumulative_quote_amt") or "0")   # NULL -> 0
avg   = D.fmt_decimal(quote / base) if base > 0 else None    # 0/10000 -> "0"
```

The store now correctly records an unobtainable notional as `NULL`. These three
functions then hand the API `"0"` for the notional **and** `"0"` for the average
price. **This is the 2026-07-14 defect one layer up** — the same
missing-becomes-zero substitution the stage exists to eliminate, sitting in the
projection layer because the scope was drawn around the executor and the store.

It also breaks a frozen contract: `12-development-breakdown.md:81` fixes the wire
shape as `cumulative_quote_amt: string|null`.

## The fix

In all three helpers:

- When `cumulative_quote_amt` is `NULL`/absent, the projected
  `cumulative_quote_amt` must be **JSON `null`**, not `"0"`.
- When the notional is unknown, `avg_price` must be **`null` too** — do not
  divide, and do not emit a zero average.
- A **real** `"0"` from the exchange still projects as the string `"0"`, and a
  real `0` notional with a real positive quantity still yields whatever the
  existing arithmetic produces. Absent and zero must stay distinguishable on the
  wire exactly as they now are in the database.
- `cumulative_base_qty`'s `or "0"` is a separate question — **leave it alone**.
  A leg with no recorded fill quantity genuinely has zero base filled, and that
  is not in this finding's scope.

Do **not** reinstate any derivation, do **not** add cross-field consistency
checks, and do **not** change the user's settled T1 semantics (verbatim or NULL).

## Required tests

Service-level, **no HTTP listener** — construct the service and call the
projection path directly:

1. `attempts` projection: a `FILLED` leg with a positive `cumulative_base_qty`
   and `NULL` `cumulative_quote_amt` → `cumulative_quote_amt` is `null` **and**
   `avg_price` is `null`.
2. `entries` projection: the same, for both the spot and perp entry helpers.
3. Regression: a real `"0"` still projects as the string `"0"` — this is what
   stops a future "simplification" from turning every zero into `null`.

If the sandbox forbids opening a socket, keep the raw failure text and say so
explicitly — **do not report an environment failure as a code pass**.

## Reading scope and budget

**~5 KB / ~1.5k tokens.**

| Anchor | Why |
| --- | --- |
| `backend/hedge_open_tasks/service.py:205-310` | the three projection helpers |
| `reports/agent-runs/2026-07-hedge-order-truth-v1/40-review-1-r6.md` | the finding |
| `12-development-breakdown.md:70-84` | the frozen wire contract |

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

Baseline: **1069 passed** (324 in the specified suite).

⚠️ Some existing tests may assert the old `"0"` projection. If so, **update them
to the new expectation and state in your report exactly which ones and what they
asserted before** — do not delete them, and do not weaken an assertion to go
green.

**Known flaky test**: `test_hedge_api.py::test_oversized_body_is_body_too_large`
has failed once with `ConnectionResetError` and passed on re-run. If you hit it,
re-run in isolation and report both results. Do not fix or silence it.

## File boundaries

**Allowed**: `backend/hedge_open_tasks/service.py`, plus the minimum necessary
among `backend/tests/test_hedge_service.py`, `test_hedge_api.py`,
`test_hedge_task_local.py`, `test_hedge_store.py`.

**Do not modify**: `backend/services/live_hedge_executor.py` (zero diff for three
rounds — keep it that way), `backend/hedge_open_tasks/store.py` (the persistence
layer is already correct; this is a projection-layer fix),
`hedge_open_live_client.py`, `wire_constraints.py`, `binance_signing.py`,
`scheduler.py`, `server.py`, `config.py`, `test_hedge_purity.py`,
`test_hedge_open_live_client.py`, `frontend/**`, `schemas/**`, `scripts/**`,
`docs/**`, `data/**`, and this stage's `status.json` / `70-handoff.md`.

## Safety (live surface is open)

Service PID 96409 runs in live mode, the Start gate is `1`, and a real naked
SHORT 10000 NOMUSDT is outstanding. No order, no card, no Start, no credentials,
no service start/stop, no write to `data/hedge-open-tasks.sqlite3`.

## Closing

1. Run both commands.
2. **Append** to `20-implementation.md`: the three call sites changed, any
   existing test expectations you updated and what they asserted before, the new
   tests, and confirmation that the store layer, T1's verbatim semantics, T2, T3
   and T5 are untouched.
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
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/41-fix-review-1-r6.dispatch.md
本地北京时间: 2026-07-29 03:40 CST
下一步模型: human operator
下一步任务: 在全新可写 Claude-GLM 会话执行本 packet
