# Review-1 Verdict, Round 3 — `backend` (GPT-5 Codex, fresh read-only session)

Raw verdict as returned by the reviewer and supplied by the human operator on
2026-07-28. Terminal soft-wrapping in the pasted output was rejoined; no wording
was altered. Schema-validated against `schemas/review-verdict.schema.json`.

**Bookkeeper errata**: this file was not written when the verdict arrived — the
verdict was recorded into `status.json` and acted on, but the raw artifact was
skipped, and the omission was caught by `scripts/validate-stage.py --phase
pre-review` failing closed on a missing review artifact. Archived here after the
fact, from the operator's paste. The gate did its job.

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-order-truth-v1",
  "role": "first_reviewer",
  "model": "GPT-5 Codex",
  "verdict": "REWORK",
  "diff_fingerprint": "c06c92140a371b3dc577cf7b509f27b61e4a7948:4f1e005f72892df4435c64444668a785f382170c7b49e229c3aea23aef3dcaa9",
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
    "reports/agent-runs/2026-07-hedge-order-truth-v1/60-test-output.txt",
    "backend/services/live_hedge_executor.py",
    "backend/hedge_open_tasks/domain.py",
    "backend/hedge_open_tasks/service.py",
    "backend/hedge_open_tasks/store.py",
    "git diff ecc38418f52b525eb61bf1c72b9b2b41c26130ef..c06c92140a371b3dc577cf7b509f27b61e4a7948"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "drain 阶段的限频订单详情查询没有落库",
      "file": "backend/hedge_open_tasks/service.py",
      "line": 1119,
      "evidence": "classify_query_response 对 429/-1003/418 返回带 rate_limited=True 和 raw_response 的确定信号（live_hedge_executor.py:400-406）。但 _reconcile_own_legs 在 1119-1127 直接 continue，而唯一的 order_query 原始响应持久化在 1145-1150，无法到达。",
      "impact": "收窄后的 T3 明确仍要求保存“限频信号”的订单详情读取，且覆盖 drain 路径；当前代码遗漏该类确定响应，无法在本地数据库还原限频回复。",
      "recommendation": "在 drain 的 rate_limited 分支设置信号后、continue 前，以 source=\"order_query\" 调用既有 _persist_leg_raw。新增服务级回归测试，断言 drain 的 429 原始 body/code/msg 可检索，同时腿保持非终态、任务仍按既有限频规则暂停。"
    },
    {
      "severity": "P1",
      "title": "畸形 2xx 查询会无限增长原始响应表，违反已保留的容量边界",
      "file": "backend/services/live_hedge_executor.py",
      "line": 431,
      "evidence": "无有效 orderId 的 2xx 在 423-431 返回带 raw 的 UNKNOWN_QUERYING，不是 None。drain 会在 service.py:1128-1150 将其更新为非终态并写入 order_query；由于 _query_verdict_terminal 仅对拒绝或接受后的终态返回真（1834-1848），同一腿每轮都会再查询、再插入一行。ADR-T4 承诺每次 attempt 2–6 行，00-task.md 的用户范围决定也明确将畸形 2xx 归为不要求持久化的 inconclusive 查询。",
      "impact": "服务长期运行时，一条持续返回畸形 2xx 的挂起腿可按轮询频率无限写入、每行最高 16KB，推翻 ADR-T4 的有界存储承诺；这也不是当前 T3 必须留下的证据。",
      "recommendation": "让无有效 orderId 的畸形 2xx 返回 None，与 transport/5xx/歧义 4xx 的已接受延后路径一致：继续查询、绝不重发或误判为 absent，但不写原始表。更新单元测试并新增 drain 级回归，验证重复畸形 2xx 不新增 order_query 行。"
    }
  ],
  "required_fixes": [
    "修复 drain 阶段 rate-limit 查询原始响应缺失，且不改变暂停、重发、终态或业务判定。",
    "使无有效 orderId 的畸形 2xx 走已接受的 inconclusive/no-persist 分支，保持原有“继续查询、绝不误判不存在”的安全语义。",
    "补充覆盖两条路径的离线服务级测试，并重跑规定套件与 backend 全量测试。"
  ],
  "residual_risks": [
    "W0 尚未取得真实 UM order-detail GET 样本。当前 NULL + 非终态 drain 合约可防止再写入伪造的 0；若 GET 同样缺少成交字段，腿会显式保持未终态而非静默记错。此轮不将 W0 作为阻塞项。"
  ],
  "fix_start_prompt": "[HARNESS-EXECUTOR-CONTRACT v1]\n你是本次修复的唯一执行者。禁止调用、启动或转派任何其他模型会话或 adapter 命令。不得读取凭据、不得发 Binance 请求、不得创建任务卡/下单/写入 data/hedge-open-tasks.sqlite3，也不得启动或停止服务。\n\n修复 stage 2026-07-hedge-order-truth-v1 的 review-1 round-3 两个 P1。权威验收标准是 reports/agent-runs/2026-07-hedge-order-truth-v1/00-task.md，尤其 T3 和其 2026-07-28 Scope decision。阅读原始证据：01-live-record-evidence.md、02-collateral-cap-finding.md、10-design.md、11-adr.md（ADR-T4）、20-implementation.md、32-review-1-r2.md、34-review-1-r3.dispatch.md、60-test-output.txt，以及固定评审区间 ecc38418f52b525eb61bf1c72b9b2b41c26130ef..c06c92140a371b3dc577cf7b509f27b61e4a7948。\n\nFinding 1：backend/hedge_open_tasks/service.py:1119-1127 的 drain 查询若为 rate-limited，设置 signal 后立即 continue；_persist_leg_raw(..., source=\"order_query\") 在 1145-1150，故永远不执行。classify_query_response 对 429/-1003/418 已生成带 raw_response 的确定 rate-limit 信号。T3 明确要求保存该类订单详情读取。\n\nFinding 2：backend/services/live_hedge_executor.py:423-431 对 2xx 但无有效 orderId 返回带 raw_response 的 UNKNOWN verdict。drain 会将它保持为非终态并每轮写一条 order_query raw；这违反 ADR-T4 的每 attempt 2–6 行容量承诺。用户已明确把 malformed 2xx 纳入“inconclusive、此 stage 不要求留痕”的延后范围。\n\n必须修复：\n1. 在 drain rate-limit 分支 continue 前持久化该 query raw，使用既有 _persist_leg_raw、source=\"order_query\"；不得改变它的 pause、非终态、never-resend 或控制流隔离语义。\n2. 无有效 orderId 的畸形 2xx 必须仍然继续查询、不得误判为 absent、不得重发，但应返回 inconclusive/no-persist，使其不再循环写 raw 表。\n3. 新增离线服务级测试：drain 的 rate-limited query 会保存 body/http_status/code/msg，且任务仍按原规则暂停；重复 malformed 2xx 不产生 order_query 行且腿仍非终态。更新相关单元测试。\n4. 不得修改锁定文件 backend/services/hedge_open_live_client.py、backend/hedge_open_tasks/wire_constraints.py、backend/services/binance_signing.py、backend/hedge_open_tasks/scheduler.py、schemas/**、docs/**、data/** 或前端文件。\n\n允许范围：backend/services/live_hedge_executor.py、backend/hedge_open_tasks/service.py，及最小必要的 backend/tests/test_live_hedge_executor.py、backend/tests/test_hedge_task_local.py；仅在确有必要时修改现有任务允许范围内的其他文件。不得扩大范围。\n\n必须执行：\n.venv/bin/python -m pytest backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py backend/tests/test_hedge_executor.py backend/tests/test_hedge_task_local.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_open_live_client.py backend/tests/test_hedge_purity.py -q 2>&1 | tee reports/agent-runs/2026-07-hedge-order-truth-v1/60-test-output.txt\n.venv/bin/python -m pytest backend/tests -q 2>&1 | tee -a reports/agent-runs/2026-07-hedge-order-truth-v1/60-test-output.txt\n\n完成后追加 20-implementation.md，说明两个 P1 的修复、测试结果，以及订单判定、重发规则、限频暂停和 raw 写失败不影响业务结果均保持不变。不要 commit，不要改 status.json 或 70-handoff.md，停止并交给 bookkeeper。",
  "next_action": "fix"
}
```

---

## Bookkeeper verification

Both findings were confirmed against the code before the fix was dispatched.

**Finding 1** — `_reconcile_own_legs`'s rate-limited branch sets `drain_signal`
and `continue`s, while the only `order_query` persist sits further down the loop
body, so it is unreachable. In scope even after the user's T3 narrowing, because
the narrowed criterion explicitly lists **a rate-limit signal** among the
conclusive verdicts that must be persisted.

**Finding 2** — a 2xx carrying no usable `orderId` returns an UNKNOWN verdict
**with** raw rather than `None`; `_query_verdict_terminal` returns `False` for
it, so drain re-queries every worker round and writes a row each time. Not
theoretical: Binance changed response shapes on 2026-07-14, and a renamed or
moved `orderId` would put every leg on this branch at once.

While confirming Finding 2 the bookkeeper established something the finding did
not state and that matters more: `service.py:1075-1077` returns early while any
leg is non-terminal, so the worker never reaches dispatch — **a stuck leg stalls
that task's order opening entirely**. The row spam was the symptom; the stall is
the consequence. That behaviour is deliberate and safe (opening another pair
while a leg's state is unknown would add exposure blind) and was left untouched.

### The fix does not follow recommendation 2

The reviewer proposed making a malformed 2xx return `None`. **The user rejected
that** as scope drift, since it changes business classification semantics inside
a data-truth stage, and specified a storage-layer rule instead: one raw row per
leg per `source`. That rule closes both findings without touching any verdict —
`live_hedge_executor.py` has a zero diff in the fix commit, which is the
mechanical proof.

Accepted costs, recorded in `00-task.md` and `status.json` rather than left to be
rediscovered: the resolving query's raw text is not kept once that leg has an
`order_query` row, and a later `429` is not stored if an earlier row exists —
「429 就 429，遇到问题我们再分析问题解决问题」.

`rework_count` reached **3 / 3** here, the limit. AGENTS.md routes that to
`human_escalation_required`; the escalation was resolved in-conversation by the
release authority, who authorized the round and set its approach.
