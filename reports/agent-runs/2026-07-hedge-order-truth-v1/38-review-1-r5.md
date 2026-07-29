# Review-1 Verdict, Round 5 — `backend` (GPT-5 Codex, fresh read-only session)

Raw verdict as returned by the reviewer and supplied by the human operator on
2026-07-29. Terminal soft-wrapping was rejoined; no wording was altered.
Schema-validated. `fix_start_prompt` is stored abbreviated: the user refined the
approach on top of it, and the refined instructions live in
`39-fix-review-1-r5.dispatch.md`. The reviewer's substance is preserved verbatim
in `findings` and `required_fixes`.

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-order-truth-v1",
  "role": "first_reviewer",
  "model": "GPT-5 Codex",
  "verdict": "REWORK",
  "diff_fingerprint": "2712fbaed284d777708a9f74ecb3b1cabe22d155:6f33425af859e34c2b7793d5d08f163deddb506823aeb0d00c016c43a110b6a4",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [
    "reports/agent-runs/2026-07-hedge-order-truth-v1/38-review-1-r5.dispatch.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/00-task.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/01-live-record-evidence.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/02-collateral-cap-finding.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/10-design.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/11-adr.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/19-r4-reconciliation.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/30-review-1.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/32-review-1-r2.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/34-review-1-r3.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/36-review-1-r4.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/20-implementation.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/60-test-output.txt",
    "git diff ecc38418f52b525eb61bf1c72b9b2b41c26130ef..2712fbaed284d777708a9f74ecb3b1cabe22d155",
    "git diff baced322e7871ffdcb2a3ad9208da3d1b5dd2524..2712fbaed284d777708a9f74ecb3b1cabe22d155",
    "backend/hedge_open_tasks/domain.py",
    "backend/hedge_open_tasks/store.py",
    "backend/hedge_open_tasks/service.py",
    "backend/hedge_open_tasks/executor.py",
    "backend/services/live_hedge_executor.py",
    "backend/tests/test_hedge_store.py",
    "backend/tests/test_hedge_task_local.py",
    "backend/tests/test_live_hedge_executor.py"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "M1 迁移会把交易所实际返回的字面 0 改写为 NULL",
      "file": "backend/hedge_open_tasks/store.py",
      "line": 428,
      "evidence": "_migrate 的 M1 以 exchange_status='FILLED'、cumulative_base_qty>0、cumulative_quote_amt='0' 为唯一谓词，将所有匹配行改为 NULL（428-440 行）；它没有、也不可能从这些列判断该 0 是旧客户端缺字段时伪造的占位符，还是交易所实际返回的字面 0。对应回归测试 test_migrate_m1_m2_repair_defect_rows_audit_then_idempotent（backend/tests/test_hedge_store.py:545-589）明确锁定该改写。最高权威 00-task.md T1 的 2026-07-29 Scope decision 要求「交易所返回什么就存什么；没返回就存 NULL」，并明确说正成交量配合字面 0 的跨字段一致性检查不在范围内。",
      "impact": "这会在服务升级时不可逆地篡改历史交易所原话，并将「真实 0」与「未返回」重新混同；同时违反 T1 的 verbatim-only 规则及迁移的旧数据保真要求。生产库中既有的已知伪造 0 不能成为把同形但可能真实的历史 0 全部改写的依据。",
      "recommendation": "删除或收窄 M1，使迁移绝不依据「FILLED + 正成交量 + 0」这一跨字段推断改写 cumulative_quote_amt；保留字面 0。相应更新迁移测试，覆盖真实字面 0 在重开数据库后仍为 0、迁移幂等、以及 M2 不受影响。已知 leg 6 的历史金额未知可保留为显式后续人工处置，不得用无来源的批量转换替代。"
    },
    {
      "severity": "P1",
      "title": "每腿每 source 首行去重会丢弃随后产生的决定性订单详情响应",
      "file": "backend/hedge_open_tasks/store.py",
      "line": 1777,
      "evidence": "append_raw_response 在已有 (attempt_id, leg, source) 行时直接返回，不考察新响应是否为终态或限频判定（1777-1783 行）。drain 中每个非终态 query verdict 都在 resolve_leg_from_query 后调用该方法（backend/hedge_open_tasks/service.py:1138-1160）：例如首次 GET 返回 NEW 或 PARTIALLY_FILLED 时会写 order_query，之后同一腿 GET 返回 FILLED、明确拒绝、404/-2013 或 429 时会被去重跳过。00-task.md T3 明定产生 fill、confirmed rejection、confirmed absent 或 rate-limit 信号的 order-detail read 必须保存完整 body；其 Scope decision 也要求 drain query「when it resolves」留下记录。20-implementation.md 的 r3 章节承认「决定性那条查询的原文不再保留」，但该叙述不能覆盖 00-task.md 的验收标准。",
      "impact": "一个订单可在数据库中被标记为已填充、已拒绝、未找到或被限频，却没有产生该最终判定的交易所原始响应；这直接违背 T3，且使事后无法从自身记录解释最终事实。",
      "recommendation": "在保持有界存储的同时保证决定性 query 的 raw 被保留：例如让 append_raw_response 接收明确的 decisive 标记，并在已有非决定性 order_query 行时以决定性响应原子替换它，或使用另一种有界且可检索的终态记录。覆盖 NEW/PARTIALLY_FILLED 首次 query 后 FILLED、首次非终态后 404/-2013、以及首次非终态后 429；每例断言最终决定性 body/code/msg 可检索且行数仍受界。"
    }
  ],
  "required_fixes": [
    "使 T1 的历史迁移遵循 verbatim-only 规则：不得把可能为交易所实际返回的字面 0 以跨字段推断改写为 NULL；更新迁移和幂等测试。",
    "修复 order_query 的有界存储策略，使每个 T3 指定的决定性 order-detail GET 的完整响应均可检索，同时仍限制重复轮询造成的行增长；补充服务级回归测试覆盖先非终态、后决定性判定的序列。",
    "保留既有 T1 缺失值 NULL、T2 51169->collateral_cap、T3 POST/inline confirm/immediate fallback 持久化、T5 实盘时间戳，以及凭据不落库和 raw 持久化失败不影响业务控制流。",
    "不得修改锁定文件 backend/services/hedge_open_live_client.py、backend/hedge_open_tasks/wire_constraints.py、backend/services/binance_signing.py、backend/hedge_open_tasks/scheduler.py、schemas/、docs/、data/** 或前端。"
  ],
  "residual_risks": [
    "W0 仍未取得真实 UM 订单详情 GET 样本；按派发单要求重新判断后，当前 NULL 兜底避免伪造金额，仍作为非阻塞残余风险。",
    "本评审首次运行派发单指定的 9-suite 命令得到 1 failed, 319 passed：backend/tests/test_hedge_api.py::test_oversized_body_is_body_too_large 因 ConnectionResetError 失败；隔离复跑该测试及三条相关 store 测试均通过。修复后须重跑完整指定套件和 backend/tests 全量套件。"
  ],
  "fix_start_prompt": "[HARNESS-EXECUTOR-CONTRACT v1]\n（完整提示词见 verdict 原文；bookkeeper 未改写其内容，本轮修复方案由用户在其基础上细化——见 39-fix-review-1-r5.dispatch.md。）",
  "next_action": "fix"
}
```

---

## Bookkeeper verification — both CONFIRMED

**Both findings are consequences of the two user scope decisions colliding with
each other, not reviewer nitpicking.**

### Finding 1 — M1 contradicts the T1 narrowing

`store.py:428-441`: the predicate is exactly
`exchange_status='FILLED' AND cumulative_base_qty > 0 AND cumulative_quote_amt = '0'`
→ rewrite to NULL. That is precisely the cross-field inference the user's
2026-07-29 T1 decision put out of scope, applied to historical rows. M1 was
written before that decision; nobody went back to re-check it against the new
rule. The reviewer did.

**M2 is unaffected and must stay.** It rewrites `leg_exposure.ts` from the 1970
epoch and has nothing to do with exchange figures — that is T5, untouched by the
verbatim rule.

### Finding 2 — the dedupe contradicts the T3 narrowing, and that is the
bookkeeper's error

When the bookkeeper narrowed T3 it wrote, in `00-task.md`, that an order-detail
read must be persisted **"whenever that read produces a conclusive verdict — a
fill, a confirmed rejection, a confirmed absent order, or a rate-limit signal"**.
It then wrote the round-3 fix packet specifying "one row per leg per source,
first wins" — which drops exactly those conclusive responses when an earlier
non-conclusive poll already took the slot.

The bookkeeper *did* warn the user at the time that a literal first-only rule
would discard the resolving response, and the user chose it anyway. But the
bookkeeper failed to notice that the rule directly contradicted the T3 text it
had itself written days earlier. **The reviewer caught a contradiction the
bookkeeper created.** Recorded plainly rather than framed as a reviewer
discovery about the implementer's work.

### The resolution keeps both user decisions intact

The user's refinement, 2026-07-29:

- **Finding 1**: delete M1 outright. Do not rewrite history on a cross-field
  guess. `leg 6` keeps its `0`; its background is already documented in
  `01-live-record-evidence.md`, which is where that knowledge belongs.
- **Finding 2**: keep the one-row-per-leg-per-source bound, but let a
  **decisive** response atomically replace an earlier non-decisive
  `order_query` row. Still one row; the row that survives is the one that
  matters.
- **Critical constraint added by the user**: do NOT let every later response
  overwrite. An explicit `decisive` flag must be passed, and replacement happens
  only for the four verdict types T3 names. Otherwise a later `NEW` would
  overwrite an earlier `FILLED` — the same bug with the sign flipped.

This round therefore makes the **code match the criteria**, rather than narrowing
the criteria again. `00-task.md` needs no change.

### Consequence for ADR-T6, disclosed

`11-adr.md` ADR-T6 specifies M1 as part of the historical-data migration. Deleting
M1 supersedes that half of the ADR; M2 stands. Like the earlier design/task
conflicts, the ADR is not rewritten — `00-task.md` governs — and this is recorded
so a reviewer does not file it as a finding.

### The flaky test

The reviewer's first run of the specified suite showed 1 failed / 319 passed:
`test_hedge_api.py::test_oversized_body_is_body_too_large` failing with
`ConnectionResetError`, passing on isolated re-run. The bookkeeper's two
independent full runs on this tree were green (1065 / 320). Recorded as a flaky
test, not a real failure, and filed as follow-up
`p3-flaky-oversized-body-test`.
