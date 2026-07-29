# Review-1 Verdict, Round 6 — `backend` (GPT-5 Codex, fresh read-only session)

Raw verdict as returned by the reviewer, supplied by the human operator on
2026-07-29. Soft-wrapping rejoined; no wording altered. Schema-validated.
`fix_start_prompt` stored abbreviated — the operative instructions are in
`41-fix-review-1-r6.dispatch.md`; the reviewer's substance is verbatim in
`findings` and `required_fixes`.

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-order-truth-v1",
  "role": "first_reviewer",
  "model": "GPT-5 Codex",
  "verdict": "REWORK",
  "diff_fingerprint": "95ac1a549c640f7ff01cf7773e577228ffc663e8:1ea0690a232325b25ce2ed02c24a85aa825378d1ac60e7f478b65df5ce56455b",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [
    "reports/agent-runs/2026-07-hedge-order-truth-v1/00-task.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/10-design.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/11-adr.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/19-r4-reconciliation.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/20-implementation.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/30-review-1.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/32-review-1-r2.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/34-review-1-r3.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/36-review-1-r4.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/38-review-1-r5.md",
    "backend/hedge_open_tasks/domain.py",
    "backend/hedge_open_tasks/store.py",
    "backend/hedge_open_tasks/service.py",
    "backend/services/live_hedge_executor.py",
    "git diff ecc38418f52b525eb61bf1c72b9b2b41c26130ef..95ac1a549c640f7ff01cf7773e577228ffc663e8"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "未知金额在 API 投影层又被伪造成零",
      "file": "backend/hedge_open_tasks/service.py",
      "line": 215,
      "evidence": "T1 的持久化层已正确把缺失金额保存为 NULL（store.py:815-830），但 _leg_to_doc 在 215、222 行以 or \"0\" 读取并输出它；entries 的 _entry_spot_leg（277、285）与 _entry_perp_leg（295、303）重复同一转换。于是 FILLED 且 cumulative_quote_amt=NULL 的腿，数据库中为未知，HTTP/API 时间线却返回 \"0\" 和零均价。12-development-breakdown.md:81 明确冻结 wire 合约为 cumulative_quote_amt: string|null。",
      "impact": "这重新引入本阶段要消除的「缺失与真实零不可区分」问题：API/前端消费者会把交易所未返回的金额当作交易所返回的零，违背 T1 的「只记录交易所原话或 NULL」要求。",
      "recommendation": "三个腿投影函数必须保留 None：当 cumulative_quote_amt 为 NULL 时返回 JSON null，且 base>0 时 avg_price 也必须为 null；只有真实的字符串 \"0\" 才输出 \"0\"。新增无 HTTP 监听的服务层回归测试，覆盖 attempts 与 entries 两种投影中 FILLED+正 base+NULL quote 的 null 透传，并保留真实 \"0\" 的回归。"
    }
  ],
  "required_fixes": [
    "修复 _leg_to_doc、_entry_spot_leg、_entry_perp_leg 的 NULL 透传，禁止用 or \"0\" 把未知 quote 转成零。",
    "为 attempts 与 entries 的 API 文档投影补回归测试：NULL quote 输出 null、avg_price 输出 null；真实 \"0\" 仍输出字符串 \"0\"。",
    "重新运行任务相关测试并更新实现报告与测试证据；保持 T1 的用户范围决定不变，不新增跨字段推断。"
  ],
  "residual_risks": [
    "W0 的真实 UM order-detail GET 样本仍未取得；此前已作为非阻塞残余风险接受。",
    "用户已接受交易所实际返回矛盾性零金额时按原样存储；本 finding 仅修复缺失值在 wire 层被伪造成零。"
  ],
  "fix_start_prompt": "[HARNESS-EXECUTOR-CONTRACT v1]\n（完整提示词见 verdict 原文；bookkeeper 未改写其内容，本轮修复指令见 41-fix-review-1-r6.dispatch.md。）",
  "next_action": "fix"
}
```

---

## Bookkeeper verification — CONFIRMED, and this is the sharpest finding of the six rounds

`backend/hedge_open_tasks/service.py:214-216` (and the same two lines repeated in
`_entry_spot_leg` and `_entry_perp_leg`):

```python
base  = D.Decimal(leg.get("cumulative_base_qty") or "0")
quote = D.Decimal(leg.get("cumulative_quote_amt") or "0")   # ← NULL becomes 0
avg   = D.fmt_decimal(quote / base) if base > 0 else None    # ← and so 0/10000 = 0
```

So a leg the database honestly records as **unknown** is served to the API as
`cumulative_quote_amt: "0"` **and** `avg_price: "0"`.

**This is the original defect, one layer up.** The 2026-07-14 bug was
`_decimal_str(None) → "0"` in the executor. The stage fixed the executor and the
store — and the identical pattern sat untouched in the projection layer the whole
time, because the scope was drawn around the executor and store. Three
occurrences, never examined.

It also violates a **frozen** contract: `12-development-breakdown.md:81` fixes the
wire shape as `cumulative_quote_amt: string|null`.

**Why it matters more than its size suggests**: the database being right is
invisible. What the operator actually looks at is the screen, and the screen
shows a fabricated `0` for both the notional and the average price — the position
table's average price being precisely the figure this stage was opened to make
trustworthy.

### This one is NOT a scope-collision artifact

Rounds 3 and 5 were driven by the criteria moving under already-written text.
This is a genuine, previously-unexamined instance of exactly the defect class the
stage exists to eliminate. The reviewer earned this one.

### User decision

The user's first instinct was to skip it — a `0` on screen can be investigated
when it actually appears, and T3 now makes that investigation possible for the
first time, since the exchange's own response is in `hedge_open_raw_response`.
That reasoning is sound and the bookkeeper recorded it as such.

The bookkeeper supplied one fact that changed the calculus: **narrowing the
criteria would itself require another review-1 round**, exactly as fixing does.
The two paths cost the same number of rounds; the fix costs about six lines more.
On that basis the user chose to fix it.

`00-task.md` is therefore **unchanged** this round — the code moves to meet the
criteria, as in round 5.
