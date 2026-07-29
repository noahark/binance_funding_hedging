# Fix Dispatch — Review-1 Round 4, by user scope decision

Human operator: run in a **fresh, write-capable Claude-GLM session**
(`glm-5.2[1m]`) on branch `stage/2026-07-hedge-order-truth-v1`.

This round is **smaller than any previous one**: it deletes logic. Nothing is
added except a test.

## What the user decided, and why the reviewer's P0 is not being fixed

Review-1 round 4 raised a P0: a `FILLED` leg with a positive quantity can still
persist a literal `0` notional if the exchange sends one. **The reviewer's chain
is factually correct** — the bookkeeper verified all three steps — but the user
declined it on scope:

> 交易所返回 0 没问题吧，到时遇到具体情况再分析呗。而且金额缺失时也不用推算这么
> 麻烦，查询回来是什么就是什么，有问题我会让模型再去排查的

The rule is now one line:

> **交易所返回什么就存什么；没返回就存 NULL。不推算、不换算、不加工。**

`00-task.md` §T1 has been rewritten to match, with the accepted cost recorded.
Read it before starting — **it is the authority, not this packet's summary.**

## The one change

`backend/hedge_open_tasks/store.py`, `_leg_final_fields` (around line 826-852):

```python
if cumulative_quote is None or cumulative_quote == "":
    # Missing figure: derive from real data if possible, else NULL (unknown).
    if filled_qty > 0 and avg_price is not None:
        quote = filled_qty * _num(avg_price)      # ← DELETE this derivation
    else:
        quote = None
else:
    ...
```

**Delete the derivation.** An absent figure becomes `NULL`, unconditionally. The
`else` branch that stores a present value as-is is already correct and stays
exactly as it is — including for a literal `"0"`, which is now the intended
behaviour.

The unparseable-value branch (`except InvalidOperation: quote = None`) also stays
as-is: an unparseable value is not something the exchange meaningfully said.

That is the whole change. Do not add a cross-field consistency check, do not
touch `_quote_decimal`, do not touch `leg_is_terminal_fill`, do not touch
terminality, and do not change `live_hedge_executor.py` at all.

## Why deleting it is safe (verified by the bookkeeper, but re-check it yourself)

The derivation only fires when the quote figure is absent **and** `avg_price` is
present. The margin leg reads `cummulativeQuoteQty` from its POST, so it does not
reach that branch; the UM leg is designed to take its figures from the
order-detail GET, which is assumed to carry both fields. So the branch covers a
case that may not exist in practice. If you find a path where deleting it changes
a currently-tested outcome, **stop and report** rather than working around it.

## Reading scope and budget

**~6 KB / ~2k tokens.** Line ranges, not whole files.

| Anchor | Why |
| --- | --- |
| `backend/hedge_open_tasks/store.py:800-860` | `_leg_final_fields` — the only code change |
| `reports/agent-runs/2026-07-hedge-order-truth-v1/00-task.md` §T1 | the rewritten criterion and the scope decision — **the authority** |
| `reports/agent-runs/2026-07-hedge-order-truth-v1/36-review-1-r4.md` | the declined P0, for context |

Do not re-read whole files. If you materially exceed this budget, stop and report.

## Tests

Adjust existing tests that assert the derivation, and add one:

1. An absent quote figure with a positive `filled_qty` **and** a present
   `avg_price` now records `NULL` — not `filled_qty × avg_price`. This is the
   behaviour change; it needs an explicit lock so nobody reinstates the
   derivation later.
2. A literal `"0"` from the exchange is stored as `"0"` — the intended behaviour
   under the new rule.
3. The 2026-07-14 defect stays fixed: a UM response lacking `cumQuote`/`avgPrice`
   records `NULL`, never a coerced `0`.

Any existing test that asserts a derived notional must be updated to the new
expectation, **not deleted**. State in the report which tests you changed and
what they asserted before.

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

Baseline: **1064 passed** (319 in the specified suite). The count may move by a
test or two here — that is expected this round, since existing assertions change.
Report the delta and why.

## File boundaries

**Allowed**: `backend/hedge_open_tasks/store.py`, and the minimum necessary among
`backend/tests/test_hedge_store.py`, `test_hedge_task_local.py`,
`test_live_hedge_executor.py`, `test_hedge_service.py`.

**Do not modify**: `backend/services/live_hedge_executor.py` (zero diff again
this round), `hedge_open_live_client.py`, `wire_constraints.py`,
`binance_signing.py`, `scheduler.py`, `server.py`, `config.py`,
`test_hedge_purity.py`, `test_hedge_open_live_client.py`, `frontend/**`,
`schemas/**`, `scripts/**`, `docs/**`, `data/**`, and this stage's `status.json`
/ `70-handoff.md`.

Also unchanged and not to be touched: the `51169 → collateral_cap` mapping and
its frozen Chinese copy, the rate-limit persist, the one-row-per-leg-per-source
cap, and raw-write-failure isolation.

## Safety (live surface is open)

Service PID 96409 runs in live mode, the Start gate is `1`, and a real naked
SHORT 10000 NOMUSDT is outstanding. No order, no card, no Start, no credentials,
no service start/stop, no write to `data/hedge-open-tasks.sqlite3`.

## Closing

1. Run both commands.
2. **Append** to `20-implementation.md`: what was deleted, which existing tests
   changed and what they used to assert, the new test, and confirmation that
   terminality, order verdicts, resend rules, rate-limit handling and raw
   persistence are all untouched.
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
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/37-fix-review-1-r4.dispatch.md
本地北京时间: 2026-07-29 01:30 CST
下一步模型: human operator
下一步任务: 在全新可写 Claude-GLM 会话执行本 packet
