# Review-1 Verdict, Round 7 — `backend` (GPT-5 Codex, fresh read-only session)

Raw verdict as returned by the reviewer, supplied by the human operator on
2026-07-29 by pasting it into the bookkeeper session. Provenance note: the
paste arrived terminal-wrapped — hard newlines plus indentation had been
inserted mid-string by the operator's terminal, which made the paste invalid
JSON as received. The bookkeeper mechanically rejoined the wrapped lines
(removing only the wrap-inserted newline+indent runs; no word, figure, path or
punctuation was altered) and re-validated the result against
`schemas/review-verdict.schema.json`: VALID. This mirrors the round-6 shell
mangling repaired in commit 865ca33.

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-order-truth-v1",
  "role": "first_reviewer",
  "model": "GPT-5 Codex",
  "verdict": "REWORK",
  "diff_fingerprint": "34ad0ca47f1f802030a694a798e8bb49ef8b55c6:05d0233047696ff966c3fa6d682f96c8cf9bd3a0df08f59882a4f06b1b97fef2",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [
    "reports/agent-runs/2026-07-hedge-order-truth-v1/00-task.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/01-live-record-evidence.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/02-collateral-cap-finding.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/42-production-db-write-incident.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/10-design.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/11-adr.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/19-r4-reconciliation.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/20-implementation.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/30-review-1.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/32-review-1-r2.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/34-review-1-r3.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/36-review-1-r4.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/38-review-1-r5.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/40-review-1-r6.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/60-test-output.txt",
    "backend/hedge_open_tasks/domain.py",
    "backend/hedge_open_tasks/store.py",
    "backend/hedge_open_tasks/service.py",
    "backend/services/live_hedge_executor.py",
    "git diff ecc38418f52b525eb61bf1c72b9b2b41c26130ef..34ad0ca47f1f802030a694a798e8bb49ef8b55c6"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "延后查询结算的单腿暴露仍把未知金额伪造成零价格",
      "file": "backend/hedge_open_tasks/store.py",
      "line": 1336,
      "evidence": "_exposure_from_legs 在 1336 行将 cumulative_quote_amt=NULL 传给 _num，后者返回 Decimal(0)，随后 1337 行以该值除以正成交量并写入 leg_exposure.price。独立临时 SQLite 复现：已成交 spot（base=0.5、quote=NULL）加拒绝 perp 经 finalize_attempt 后，持久化 leg_exposure 为 {'leg':'spot','qty':'0.5','price':'0E+1',...}。task_to_doc 会原样把该 leg_exposure 返回给 API。直接实盘路径的 service._dispatch_to_outcome 已正确保留 avg_price=None，故缺口只在延后查询并 finalize_attempt 的路径。",
      "impact": "这再次违反 T1 的“交易所未返回即 NULL，绝不替代为 0”规则。特别是在 POST/确认后进入 drain（延后查询）并形成单腿成交时，操作者看到的暴露价格会是零，而不是未知；这是与第六轮 API 投影缺陷同类、但位于另一条用户可见链路。",
      "recommendation": "在 _exposure_from_legs 中保留原始 quote 的 None 语义：quote 为 NULL 时 price 必须为 None，不得调用 _num 生成零；真实字符串 '0' 仍按既有语义产生零价格。新增临时 SQLite 回归，覆盖 resolve_leg_from_query（FILLED+正 base+NULL quote）→ finalize_attempt 的单腿暴露，并断言持久化/API 文档中的 price 为 null；同时保留真实 '0' 的回归。"
    }
  ],
  "required_fixes": [
    "修复 backend/hedge_open_tasks/store.py 的 _exposure_from_legs：NULL cumulative_quote_amt 必须得到 price=None，真实 '0' 仍可计算为零。",
    "在 backend/tests/test_hedge_store.py 或现有服务级测试中补充延后查询结算的单腿回归：已成交腿 base>0、quote=NULL、另一腿拒绝，finalize_attempt 后 leg_exposure.price 为 None；补充真实 '0' 不被误改为 NULL 的断言。",
    "重新运行 dispatch 指定的九个测试套件与 backend/tests 全量测试，更新实现报告和 60-test-output.txt；不得触碰 data/、服务进程、凭据或任何网络路径。"
  ],
  "residual_risks": [
    "W0 的真实 UM order-detail GET 样本仍未取得；派发包已将其定为接受的非阻塞风险，若字段不存在，当前合约仍以 NULL 防止伪造值。",
    "42-production-db-write-incident.md 所述两处既有生产数据库变更是已披露事实；本轮未发现当前代码继续触发 M1 写入的路径，且该事故按派发要求不作为本轮阻塞 finding。"
  ],
  "fix_start_prompt": "[HARNESS-EXECUTOR-CONTRACT v1]\n你是 stage `2026-07-hedge-order-truth-v1` 的受限修复实现者。禁止调用、启动或转派任何其他模型会话或 adapter 命令；不得访问网络、凭据、服务进程或 data/hedge-open-tasks.sqlite3；不得 commit。只在允许文件内修改，完成测试、报告后停止给 bookkeeper。\n\n修复来源：Review-1 Round 7，目标范围为 ecc38418f52b525eb61bf1c72b9b2b41c26130ef..34ad0ca47f1f802030a694a798e8bb49ef8b55c6，指纹为 34ad0ca47f1f802030a694a798e8bb49ef8b55c6:05d0233047696ff966c3fa6d682f96c8cf9bd3a0df08f59882a4f06b1b97fef2。\n\n必读原始依据：reports/agent-runs/2026-07-hedge-order-truth-v1/00-task.md（最高权威，尤其 T1 的“原话或 NULL”范围决定）、43-review-1-r7.md、42-production-db-write-incident.md、20-implementation.md、60-test-output.txt，以及 backend/hedge_open_tasks/store.py。\n\nFinding：store.py:_exposure_from_legs 当前以 _num(NULL) 得到 0，再为正 base 计算 price，从而在“延后查询后 finalize_attempt 的单腿成交”路径把未知 notional 显示成 0E+1。它与 T1 的 NULL 合约冲突；service._dispatch_to_outcome 的即时路径已正确，不得回退该行为。\n\n允许改动：backend/hedge_open_tasks/store.py；backend/tests/test_hedge_store.py（必要时 backend/tests/test_hedge_service.py）。禁止改动：backend/services/hedge_open_live_client.py、backend/hedge_open_tasks/wire_constraints.py、backend/services/binance_signing.py、frontend/**、schemas/**、scripts/**、docs/**、reports/ 之外的文件、data/**。\n\n要求：\n1. 当 cumulative_quote_amt is NULL 时，_exposure_from_legs 的 price 必须为 None；不得把缺失金额转换、推导或替换为零。\n2. 真实字符串 '0' 仍是交易所返回的真实值，必须保留现有零价格语义；不得新增跨字段一致性检查或金额推算。\n3. 新增确定性临时 SQLite 回归，覆盖 prepare_attempt → resolve_leg_from_query（FILLED、base>0、quote=None）+ 另一腿 REJECTED → finalize_attempt，并断言 task leg_exposure.price is None。再覆盖真实 '0' 不变。\n4. 不得通过修改生产数据库或运行 live 服务验证。\n\n测试命令：\npython3 -m pytest backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py backend/tests/test_hedge_executor.py backend/tests/test_hedge_task_local.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_open_live_client.py backend/tests/test_hedge_purity.py -q\npython3 -m pytest backend/tests -q\n\n输出：更新 reports/agent-runs/2026-07-hedge-order-truth-v1/20-implementation.md 与 60-test-output.txt，报告变更文件、测试结果、未解决风险，并停止等待 bookkeeper。此阶段已到 3/3 rework 上限；只有人类明确授权后才能执行该额外修复。",
  "next_action": "human_escalation_required"
}
```

## Bookkeeper verification — CONFIRMED

The chain is verified against the code, not accepted on the reviewer's word:

- `backend/hedge_open_tasks/store.py:292-296` — `_num(None)` returns
  `Decimal(0)`; that is the coercion.
- `backend/hedge_open_tasks/store.py:1334-1337` — `_exposure_from_legs` feeds
  `cumulative_quote_amt` through `_num`, then computes
  `price = str(quote / base)` whenever `base > 0`. A `NULL` quote therefore
  yields `price = "0E+1"` instead of `None`.
- Both call sites (`store.py:1212`, `store.py:1276`) are the deferred-query
  reconciliation paths — exactly the reviewer's claim that the gap is only in
  the drain/finalize route. The direct live path
  (`service._dispatch_to_outcome`) preserves `avg_price=None` and is not
  affected; the reviewer is right that it must not be regressed.

Severity: P1 is right. It is the same defect family as round 6 (a fabricated
zero at a projection boundary) on a third layer — wire (round 4), API
projection (round 6), and now the reconciled-exposure builder. It is
user-visible but moves no money and mis-places no order.

## User decision, 2026-07-29 — fix DECLINED, stage closed by user authority

The verdict's `next_action` was `human_escalation_required` (the 3/3 rework
cap was already exhausted at round 3). The user is the escalation authority
and resolved it in the bookkeeper session:

> 你来接管 bookkeeper 做最后通牒的执行，然后不管结果如何，直接合并到 main
> 上。这个小问题感觉非常无所谓，不如等以后遇到了再解决，不需要在一个臆想场
> 景不断的浪费 token

Consequences, all deliberate:

1. **The round-7 P1 is declined on scope, not disputed on fact.** The
   bookkeeper confirmed the chain above. The user judges the triggering
   scenario (a single-leg fill resolved by deferred query whose quote is
   `NULL`) speculative until it is actually observed in the field, and
   declines to spend another fix round on it. Filed as follow-up
   `p1-deferred-exposure-null-quote-zero-price` in `status.json`.
2. **No round 8.** Review-1 for this stage terminates at round 7 with a final
   verdict of `REWORK`.
3. **Merge to `main` is by explicit user acceptance.** AGENTS.md's own words:
   merge back to `main` "requires explicit user acceptance after review" —
   that acceptance is the quote above.

## Gate consequence, disclosed so nobody mistakes this for a green gate

- Review-1 never reached `ACCEPT`; review-2 was never dispatched.
- `scripts/validate-stage.py --phase accept` therefore CANNOT pass, and
  AGENTS.md RC4 v1 admits **no** class-2 authorized exception (waiving
  `verdict == ACCEPT`). No `authorized_exceptions[]` record is fabricated for
  this — the mechanism explicitly does not cover it.
- The stage is closed `accepted` **by user authority over the harness**, with
  the failing gate preserved in the evidence rather than painted green. The
  precedent is stage 1 of this programme, where the user explicitly waived
  review-2; this goes one step further (review-1 non-accepting) and says so
  plainly.
- What was true at the last green pre-review gate stays true: the full test
  suite passed on the reviewed range (see `60-test-output.txt`), and the
  fingerprint pinned by this verdict recomputes exactly
  (`34ad0ca4…:05d02330…`, verified 2026-07-29).
