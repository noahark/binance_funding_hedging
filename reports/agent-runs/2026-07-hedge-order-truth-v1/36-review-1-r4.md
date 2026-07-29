# Review-1 Verdict, Round 4 — `backend` (GPT-5 Codex, fresh read-only session)

Raw verdict as returned by the reviewer and supplied by the human operator on
2026-07-29. Terminal soft-wrapping was rejoined; no wording was altered.
Schema-validated. **Note**: `fix_start_prompt` is stored abbreviated here — the
full prompt is not reproduced because the fix does NOT follow it (see below);
the reviewer's recommendation is preserved verbatim in `findings[0]` and
`required_fixes`, which is where its substance lives.

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-order-truth-v1",
  "role": "first_reviewer",
  "model": "GPT-5 Codex",
  "verdict": "REWORK",
  "diff_fingerprint": "baced322e7871ffdcb2a3ad9208da3d1b5dd2524:3c4d16f387538c9f7f2afdef32b415c5f355a3ae0a255740870252a43abc7a5f",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [
    "reports/agent-runs/2026-07-hedge-order-truth-v1/00-task.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/01-live-record-evidence.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/02-collateral-cap-finding.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/10-design.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/11-adr.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/19-r4-reconciliation.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/20-implementation.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/30-review-1.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/32-review-1-r2.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/34-review-1-r3.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/60-test-output.txt",
    "git diff ecc38418f52b525eb61bf1c72b9b2b41c26130ef..baced322e7871ffdcb2a3ad9208da3d1b5dd2524",
    "git diff c06c92140a371b3dc577cf7b509f27b61e4a7948..baced322e7871ffdcb2a3ad9208da3d1b5dd2524",
    "backend/hedge_open_tasks/domain.py",
    "backend/hedge_open_tasks/store.py",
    "backend/hedge_open_tasks/service.py",
    "backend/hedge_open_tasks/executor.py",
    "backend/services/live_hedge_executor.py",
    "backend/tests/test_hedge_domain.py",
    "backend/tests/test_hedge_store.py",
    "backend/tests/test_hedge_task_local.py",
    "backend/tests/test_live_hedge_executor.py"
  ],
  "findings": [
    {
      "severity": "P0",
      "title": "正成交量的 FILLED 腿仍可持久化零名义金额",
      "file": "backend/services/live_hedge_executor.py",
      "line": 81,
      "evidence": "_quote_decimal() 将字面值 0 规范化为 \"0\"（81-90 行）；_post_figures() 的 margin 分支和 _query_figures() 的 margin/UM 分支都可在 executedQty>0 时返回该值（100-138 行）。leg_is_terminal_fill() 对 spot 不检查 quote，对 perp 只检查 quote 是否为 None（504-521 行），所以该腿会终态。随后 store._leg_final_fields() 将所有非空 cumulative_quote（包括 \"0\"）原样返回（807-855 行），resolve_attempt() 再将其写入 cumulative_quote_amt（1097-1134 行）。因此一个 FILLED + executedQty>0 + cumQuote/cummulativeQuoteQty=\"0\" 的响应会再次落成零名义；现有测试只锁定 filled_qty=\"0\" 时保留真零，未覆盖这个被 00-task.md T1 明确禁止的组合。",
      "impact": "这直接违反 T1「非零成交量的 FILLED 腿绝不记录 0 名义金额」的验收。面对字段形状或交易所响应再次异常时，系统会把不可能为真的零金额当作已知值，终态结算并污染仓位均价、PnL 和单腿敞口的事实记录。",
      "recommendation": "把「正成交量 + 零累计名义」视为未知/矛盾数据，而非可终态的真实金额：若有可信非零 avgPrice，可按既有真实数据推算；否则 cumulative_quote 必须为 None 且腿保持非终态，进入既有 query-drain、永不重发路径。保留 executedQty=0 时的真零语义。补 margin POST、UM order-detail GET 及服务级持久化回归测试，证明正成交量不会落库 \"0\"。"
    }
  ],
  "required_fixes": [
    "修复 T1 的跨字段一致性处理，使 FILLED 且 executedQty>0 的腿不能因 cumulative quote 为 0 而终态并持久化 0 名义金额。",
    "保留已接受的 executedQty=0 真零语义；不得把所有 0 一概改为未知。",
    "补充覆盖 margin POST、UM order-detail GET 和 service 实盘路径的离线回归测试，断言正成交量的异常零 quote 要么由真实非零 avgPrice 推算，要么为 NULL 且非终态、会继续 query-drain、绝不重发。",
    "保持本轮已核验的 rate-limit 落库、每腿每 source 一行的存储上限、raw 写失败控制流隔离、51169 分类与冻结文案不变；锁定的 hedge_open_live_client.py 与 wire_constraints.py 继续零 diff。"
  ],
  "residual_risks": [
    "W0 尚未执行：UM order-detail GET 是否仍提供 cumQuote/avgPrice 仍是未验证前提。当前 NULL 加非终态 drain 的设计可避免伪造零，但 W0 仍应按既定计划补齐；这不是本裁决的独立阻塞项。",
    "用户明确接受「每腿每 source 仅保留首条 raw」的取舍；本轮核实存在性检查位于 append_raw_response 自己的锁与事务中，限频 persist 位于 continue 前，test_4j 也断言确实多轮查询。该取舍不构成本 finding。"
  ],
  "fix_start_prompt": "[HARNESS-EXECUTOR-CONTRACT v1]\n你是本次修复的唯一执行者。禁止调用、启动或转派任何其他模型会话或 adapter 命令。不得读取凭据、不得发 Binance 请求、不得创建任务卡/下单/写入 data/hedge-open-tasks.sqlite3，也不得启动或停止服务。\n\n修复 stage 2026-07-hedge-order-truth-v1、任务 backend 的 Review-1 Round-4 P0。最高权威为 reports/agent-runs/2026-07-hedge-order-truth-v1/00-task.md，重点是 T1：非零成交量的 FILLED 腿绝不能持久化 \"0\" 名义金额；取不到真实金额必须表示为 NULL/非终态重试，而不是伪造零。（后略：完整提示词见 verdict 原文，bookkeeper 未改写。）",
  "next_action": "fix"
}
```

---

## Bookkeeper verification

### The finding is CONFIRMED as a factual chain

All three steps verified in the code:

1. `_quote_decimal` (`live_hedge_executor.py:81-90`) returns `None` only for a
   missing/empty/unparseable value. A literal `0` becomes `"0"`.
2. `leg_is_terminal_fill` (`:504-521`) does not check the quote for a spot leg at
   all, and for a perp leg checks only `is None` — so `"0"` passes and the leg
   settles as terminal.
3. `_leg_final_fields` (`store.py:826-852`) treats any present, parseable value
   as authoritative and stores it, including `"0"`.

So a response saying `FILLED` + `executedQty > 0` + `cumQuote = "0"` would
persist a zero notional. Against T1 **as it read at the time**, the reviewer was
right, and P0 was the right severity for that criterion.

### It is declined on SCOPE by the user, not disputed on fact

The trigger differs from the defect this stage was opened for. The 2026-07-14
defect was a **missing** field coerced to `0`; this requires the exchange to send
a **self-contradictory** response. It has never been observed — the repository
holds four real legs total.

The user's decision, 2026-07-29:

> 交易所返回 0 没问题吧，到时遇到具体情况再分析呗。而且金额缺失时也不用推算这么
> 麻烦，查询回来是什么就是什么，有问题我会让模型再去排查的

`00-task.md` §T1 is rewritten to that rule — store the exchange's figure
verbatim, `NULL` when absent, no derivation, no cross-field consistency checking
— with the accepted cost recorded there. The P0 is filed as follow-up
`p0-contradictory-zero-notional-not-detected`.

### The user's decision also REMOVES existing code

`_leg_final_fields` currently falls back to `filled_qty × avg_price` when the
figure is absent. Under the new rule that is itself a substitution, so the fix
deletes it: absent → `NULL`, unconditionally. **This round removes logic rather
than adding it**, which is the opposite shape of the previous three.

Bookkeeper check on the deletion's safety: the derivation only fires when the
quote is absent *and* `avg_price` is present. The margin leg reads
`cummulativeQuoteQty` from its POST and does not reach that branch; the UM leg is
designed to take its figures from the order-detail GET, assumed to carry both.
So it covers a case that may not arise. The fix packet instructs the implementer
to stop and report if deleting it changes a currently-tested outcome.

### What is NOT relaxed

The original defect stays fixed. A **missing** field still records `NULL` and
never a coerced `0`, and absent stays distinguishable from zero. Both reviewer
observations about the previous round's work were also re-confirmed as intact:
the rate-limit persist sits before the `continue`, and the one-row-per-leg-per-
source check is inside `append_raw_response`'s own lock and transaction.

### Process state

`rework_count` was already 3/3 before this round. This fix proceeds on the user's
explicit instruction, recorded as the resolution of the escalation.
