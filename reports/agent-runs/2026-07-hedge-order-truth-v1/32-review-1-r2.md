# Review-1 Verdict, Round 2 — `backend` (GPT-5 Codex, fresh read-only session)

Raw verdict as returned by the reviewer and supplied by the human operator on
2026-07-28. Terminal soft-wrapping in the pasted output was rejoined; no wording
was altered. Schema-validated against `schemas/review-verdict.schema.json`.

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-order-truth-v1",
  "role": "first_reviewer",
  "model": "GPT-5 Codex",
  "verdict": "REWORK",
  "diff_fingerprint": "33715ae2bcb4fef427f340780155dc4e4c316e28:f3db91f60350b5e8ba2db2237b89baba2c8e77d4d0c477fc9635602d869fa4ab",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [
    "reports/agent-runs/2026-07-hedge-order-truth-v1/00-task.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/01-live-record-evidence.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/02-collateral-cap-finding.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/10-design.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/11-adr.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/19-r4-reconciliation.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/30-review-1.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/20-implementation.md",
    "reports/agent-runs/2026-07-hedge-order-truth-v1/60-test-output.txt",
    "git diff ecc38418f52b525eb61bf1c72b9b2b41c26130ef..33715ae2bcb4fef427f340780155dc4e4c316e28",
    "git diff 5de9ef394b02df1036341cbac832cfc4f6c72ee3..33715ae2bcb4fef427f340780155dc4e4c316e28",
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
      "severity": "P1",
      "title": "订单详情查询在不确定结果时仍会丢失原始响应",
      "file": "backend/services/live_hedge_executor.py",
      "line": 558,
      "evidence": "_send_one_leg 在 UNKNOWN POST 后无条件发起即时 GET，但只有 classify_query_response 返回 LegDispatch 时才把 resolved.raw_response 放入 query_raw_response；GET 超时、5xx 或其他返回 None 时会直接 return 原 POST verdict（541-590）。同样，query_leg 直接返回 classify_query_response 的结果（717-728），而 service._drain 对 None 立即 continue（1130-1134）；因此这些实际已发出的 order-detail GET 从未到达 _persist_leg_raw。classify_query_response 对 transport_error/http_status=None、5xx 和非明确 absent 的 4xx 都会返回 None（397-424）。现有 test_4h 只覆盖即时 GET 返回 FILLED 的确定结果，test_4f 只覆盖 drain GET 返回确定结果。",
      "impact": "T3 要求完整持久化每次订单详情读取，并且本轮派发特别要求查询失败/超时（transport_error）也必须留痕。当前在最需要诊断的查询超时、5xx 或歧义 4xx 情况下，数据库只保留 POST（或连查询证据也没有），无法从自身记录复原交易所往返事实。",
      "recommendation": "将订单详情 GET 的原始响应与其业务判定分离传递：即时 fallback 与 drain 两条路径均须在查询没有确定 verdict 时仍以 source=order_query 落库该 response-only raw（含 transport_error）；不得改变 UNKNOWN、重发、限频、业务落库或 raw 持久化失败的既有控制流。补服务级回归测试覆盖即时 fallback GET timeout/5xx，以及 drain GET timeout/5xx，断言 raw 表存在 order_query 行且待查询腿仍保持未决。"
    }
  ],
  "required_fixes": [
    "修复即时 fallback 与 drain 的不确定订单详情查询原始响应传递及持久化；每一次实际 GET（含 transport_error、5xx 与歧义 4xx）均须产生 source=order_query 的 response-only 原始记录。",
    "保留现有 order_post、order_confirm、order_query 三种来源的语义分离；GET 不得覆盖 POST，且 POST/confirm 的既有成功路径不得重复或漏写。",
    "新增服务级回归测试覆盖 UNKNOWN POST 后即时 GET 不确定，以及后续 drain GET 不确定；断言 raw 可检索、腿仍非终态、永不重发，且限频与 raw 写失败的业务结果不变。",
    "保持 backend/services/hedge_open_live_client.py 与 backend/hedge_open_tasks/wire_constraints.py 的 diff 为空，并确保请求参数、签名、API key 或其他凭据绝不写入 raw 表。"
  ],
  "residual_risks": [
    "W0 的真实 UM 订单详情样本仍未执行；当前 NULL/非终态兜底避免伪造零值，但订单详情 GET 是否仍携带 cumQuote/avgPrice 仍是未验证前提。"
  ],
  "fix_start_prompt": "[HARNESS-EXECUTOR-CONTRACT v1]\n你是本次修复的唯一执行者。禁止调用、启动或转派其他模型会话或 adapter 命令。不得读取凭据、不得发 Binance 请求、不得创建任务卡/下单/写入 data/hedge-open-tasks.sqlite3，也不得启动或停止服务。\n\n修复 stage 2026-07-hedge-order-truth-v1 的 Review-1 Round-2 P1。最高权威：reports/agent-runs/2026-07-hedge-order-truth-v1/00-task.md 的 T3。必读原始证据：01-live-record-evidence.md、02-collateral-cap-finding.md、10-design.md、11-adr.md、12-development-breakdown.md、19-r4-reconciliation.md、20-implementation.md、30-review-1.md、32-review-1-r2.md、60-test-output.txt；固定审查范围为 ecc38418f52b525eb61bf1c72b9b2b41c26130ef..33715ae2bcb4fef427f340780155dc4e4c316e28。\n\nFinding：backend/services/live_hedge_executor.py 的 _send_one_leg 在 UNKNOWN POST 后发即时 order-detail GET；仅 GET 返回确定 LegDispatch 时才传 query_raw_response。GET 超时、5xx 或歧义 4xx 令 classify_query_response 返回 None，_send_one_leg 返回原 POST verdict，GET raw 被丢弃。drain 路径也有同一问题：query_leg 返回 None，service._drain 立即 continue，因此没有 persist_leg_raw 调用。此问题违反 T3 的完整订单详情读取持久化，且本轮要求明确包括 transport_error。\n\n必须修复：\n1. 每次实际 order-detail GET 都必须以 source=order_query 持久化 response-only raw：即时 fallback 和 drain 均包括成功、确定拒绝、429、transport_error、5xx、畸形 2xx/歧义 4xx。请求参数、签名、API key 和凭据绝不得进入 raw。\n2. 原始响应传递须与业务 verdict 分离；查询不确定时不得把它伪装成确定 verdict，也不得改变 UNKNOWN、重发、限频、腿终态、attempt 判定或业务事务。POST raw 保持 source=order_post，UM inline confirm 保持 source=order_confirm，任何 GET 不得覆盖 POST。\n3. 新增服务级回归测试：至少覆盖 UNKNOWN POST 后即时 GET timeout 或 5xx，以及持久化非终态腿的 drain GET timeout 或 5xx。断言每个实际 GET 都有可检索的 order_query raw 行（含 http_status/transport_error/body），腿保持未决且未重发。保留现有 test_4h 的确定结果契约，并覆盖 raw 持久化失败不会改变业务结果。\n4. 允许范围仅限 backend/services/live_hedge_executor.py、backend/hedge_open_tasks/service.py、backend/hedge_open_tasks/store.py、backend/hedge_open_tasks/domain.py 及允许的 backend/tests/test_hedge{domain,store,service,executor,task_local,api}.py、backend/tests/test_live_hedge_executor.py。禁止改 backend/services/hedge_open_live_client.py、backend/hedge_open_tasks/wire_constraints.py、backend/services/binance_signing.py、backend/hedge_open_tasks/scheduler.py、schemas/、docs/、data/、frontend/ 或其他非范围文件。\n\n必须执行：\ncd \"/Users/ark/Desktop/ai code/funding_hedging\"\n.venv/bin/python -m pytest backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py backend/tests/test_hedge_executor.py backend/tests/test_hedge_task_local.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_open_live_client.py backend/tests/test_hedge_purity.py -q\n.venv/bin/python -m pytest backend/tests -q\n\n完成后将修复说明追加到 reports/agent-runs/2026-07-hedge-order-truth-v1/20-implementation.md，将测试原始输出追加到 reports/agent-runs/2026-07-hedge-order-truth-v1/60-test-output.txt，生成所需 diff patch，不得修改 status.json 或 70-handoff.md，不得 commit，然后停止交给 bookkeeper。",
  "next_action": "fix"
}
```

---

## Bookkeeper verification

### Schema and gate compliance

| Check | Result |
| --- | --- |
| Parses as JSON, validates against the schema (incl. the `REWORK ⇒ fix_start_prompt` conditional) | PASS |
| `diff_fingerprint` identical to `status.diff_fingerprint` (the **round-2** range) | PASS |
| `role` / `verdict` / `next_action` in enum, `schema_version` = 1 | PASS |
| `reviewer_prior_involvement` = `none` | PASS, accurate |

### The finding is CONFIRMED — and the evidence is decisive

`backend/services/live_hedge_executor.py:395-424`:

```python
# T3 (10-design §3): capture the sanitized query response on every verdict
# path (a None return is a genuinely inconclusive retry — no verdict, no row).
raw = _raw_response_dict(response)          # ← built
if response.transport_error is not None or response.http_status is None:
    return None                              # ← and dropped
```

The raw is constructed and then discarded on every `None` path: transport error /
no status (timeout), `>= 500`, ambiguous 4xx that is not an explicit
404/`-2013`, and a malformed 2xx.

Both call sites drop it:

- `_send_one_leg` — `resolved is None` falls through to `return verdict`, i.e. the
  POST verdict, carrying no query raw.
- drain — `service.py:1116-1117`, `if verdict is None: continue  # inconclusive`,
  so `_persist_leg_raw` is never reached.

**The in-code comment is the crux**: *"a None return is a genuinely inconclusive
retry — no verdict, no row."* The implementer made a deliberate choice to key
persistence off **verdicts**. But `00-task.md` T3 keys it off **reads**:

> The complete body of the order-detail query response is persisted.
> … After this stage, a rejection like `51169` can be explained from our own
> records alone.

A timeout has no body, but it is still a fact: *we asked at T and could not find
out*. Recording it is the difference between 「查过且没有」 and 「没查」 — the
same distinction this stage's own T4 recon discipline insists on. And this is the
third instance of the stage's recurring theme: **evidence the system already held
was thrown away.**

### Round-2 severity and process notes

- P1, same as round 1: no money is lost and no order misbehaves; the damage is
  that the hardest-to-diagnose cases leave no trace.
- **This is a genuinely new defect, not a re-report.** Round 1 covered the
  *conclusive* fallback GET; this covers the *inconclusive* case on **both**
  paths. The round-2 packet explicitly asked for a systematic sweep of every
  exchange round-trip "including the case where the query itself fails or times
  out" — the widened question is what surfaced it.
- The reviewer again declined to block on W0, restating it as a residual risk. It
  re-derived that judgement this round rather than inheriting it, as the packet
  required.

### A gap in the fix requirements that the bookkeeper must add

Neither the finding nor `required_fixes` addresses **row growth**, and the fix
cannot be written without deciding it.

`ADR-T4` bounds the raw table by asserting 「每 attempt 2–6 行」. Drain re-queries
a non-terminal leg every worker round (`service.py:986`,
`while not self._worker_round(task_id)`). If every inconclusive query writes a
row, a leg stuck UNKNOWN — exactly the scenario this fix targets — produces
unbounded rows and falsifies ADR-T4's own bounding argument.

The fix must therefore either bound the persistence (dedupe, first-N, or
collapse-with-count) or amend ADR-T4's stated bound with a new one. **Silently
breaking the ADR's bound is not acceptable**, and neither is dropping the
evidence again to preserve it. This is added to the fix packet as an explicit
requirement, disclosed as a bookkeeper addition rather than presented as the
reviewer's words.

### Verdict on the verdict

Valid, schema-conforming, fingerprint-matched, substantively correct.
`rework_count` moves to **2 / 3**.
