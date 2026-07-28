# Review-1 Verdict — `backend` (GPT-5 Codex, fresh read-only session)

Raw verdict as returned by the reviewer and supplied by the human operator on
2026-07-28. Terminal soft-wrapping in the pasted output was rejoined; no wording
was altered.

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-order-truth-v1",
  "role": "first_reviewer",
  "model": "GPT-5 Codex",
  "verdict": "REWORK",
  "diff_fingerprint": "5de9ef394b02df1036341cbac832cfc4f6c72ee3:8259b7cc6266e5a9e9d0f85e99f4928980f65e31be9b9457e5481c730d1b03c8",
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
    "reports/agent-runs/2026-07-hedge-order-truth-v1/60-test-output.txt",
    "git diff ecc38418f52b525eb61bf1c72b9b2b41c26130ef..5de9ef394b02df1036341cbac832cfc4f6c72ee3",
    "backend/services/live_hedge_executor.py",
    "backend/hedge_open_tasks/service.py",
    "backend/hedge_open_tasks/store.py",
    "backend/hedge_open_tasks/domain.py",
    "backend/tests/test_live_hedge_executor.py",
    "backend/tests/test_hedge_task_local.py",
    "backend/tests/test_hedge_store.py",
    "backend/tests/test_hedge_domain.py"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "首次不确定下单后的即时订单详情 GET 未被持久化",
      "file": "backend/services/live_hedge_executor.py",
      "line": 557,
      "evidence": "_send_one_leg 对 UNKNOWN POST 发起即时订单详情查询（557-560 行）。查询有确定结果时，新建的 LegDispatch 在 581 行仅保留 verdict.raw_response（原 POST），没有保留 resolved.raw_response（该 GET）。service._dispatch_live 只写入 raw_response 和 confirm_raw_response（1585-1599 行），因此此路径的 GET 原始响应不会进入 hedge_open_raw_response。现有测试仅覆盖后续 drain 查询（test_4f）和成功 POST/confirm，未覆盖此即时 fallback GET。",
      "impact": "违反 T3 的明确验收与用户要求：查询订单详情的全量信息必须落库。发生 POST 超时或 5xx、随后的即时 GET 返回 FILLED、404、429 或业务错误时，数据库仅保留 POST 响应，丢失实际决定订单状态的订单详情响应，无法从自身记录复原事实。",
      "recommendation": "为即时 fallback GET 单独保留并以 source=order_query 持久化其 sanitized raw response，同时保留 POST 原始响应；补充服务级回归测试，证明一个 UNKNOWN POST 后被即时 GET 解析的响应会产生两条原始记录，且不改变现有控制流。"
    }
  ],
  "required_fixes": [
    "修复即时 fallback order-detail GET 的原始响应传递和持久化；不得覆盖或替代原 POST 原始响应。",
    "新增覆盖 UNKNOWN POST -> 即时 GET 确定结果的服务级测试，断言 raw 表同时含 order_post 和 order_query，并验证 GET body、code、msg 可检索。",
    "保持 raw 持久化失败不改变业务控制流、请求侧凭据不落库、锁定的 transport/wire 文件零改动。"
  ],
  "residual_risks": [
    "W0 的真实 UM 订单详情样本仍未执行；当前 NULL 兜底可避免伪造零值，按已批准设计不单独阻塞本轮修复。"
  ],
  "next_action": "fix"
}
```

The verdict also carried a `fix_start_prompt`. It is reproduced verbatim in
`31-fix-review-1.dispatch.md` with the bookkeeper's mechanical routing
corrections disclosed there, per AGENTS.md (the bookkeeper may add routing
metadata but must not hide or rewrite reviewer evidence).

---

## Bookkeeper verification

### Schema and gate compliance

| Check | Result |
| --- | --- |
| Parses as JSON | PASS |
| `schema_version` = `1` (schema `const: 1`) | PASS |
| `role` = `first_reviewer` (enum: `designer_review` / `first_reviewer` / `final_reviewer` / `reality_checker`) | PASS |
| `verdict` = `REWORK` (enum: `ACCEPT` / `REWORK` / `BLOCKED`) | PASS |
| `next_action` = `fix` (in enum) | PASS |
| All 11 required fields present | PASS |
| `diff_fingerprint` identical to `status.diff_fingerprint` | PASS |
| `reviewer_prior_involvement` = `none` — Codex had no direction, design or breakdown role this stage | PASS, accurate |
| `fix_start_prompt` present, as AGENTS.md requires on `REWORK` | PASS |

### The finding is CONFIRMED — verified against the code, not accepted on its word

`backend/services/live_hedge_executor.py:558-583`: when a POST comes back
`LEG_UNKNOWN_QUERYING`, `_send_one_leg` immediately calls `querier(...)` and
classifies the result. On a conclusive result it returns a **new** `LegDispatch`
built from `resolved.*` for every business field — but sets
`raw_response=verdict.raw_response` (the POST) and
`confirm_raw_response=verdict.confirm_raw_response`. **`resolved.raw_response`,
the body of the GET that actually decided the leg's fate, is dropped on the
floor.**

`backend/hedge_open_tasks/service.py:1585-1599`: `_dispatch_live` writes exactly
three raw rows — spot `order_post`, perp `order_post`, perp `order_confirm`.
There is no write for the fallback resolution GET.

**The finding is stronger than the reviewer stated: this is an internal
inconsistency, not merely a missing capture.** The drain path already does the
right thing — `service.py:1147` persists its query response with
`source="order_query"`, with a comment citing T3 §3. So the same class of
evidence (an order-detail GET that determines a leg's outcome) is persisted on
one path and discarded on another. The fix therefore has an existing pattern to
follow rather than needing a new one.

**Against `00-task.md` T3** — the authority for this gate — the criterion is:

> The complete body of the order-detail query response is persisted.
> … After this stage, a rejection like `51169` can be explained from our own
> records alone.

The UNKNOWN-POST path is precisely the case where the exchange's own words matter
most: the POST told us nothing conclusive, so the GET is the only record of what
happened. Losing it defeats the criterion in its hardest case. **REWORK is
correct.**

### Severity assessment

P1 is right, not P0. The common paths (conclusive POST, and the UM inline
confirm) do capture their raws, and the drain path captures its query. The gap is
confined to one branch. But that branch is the diagnostically hardest one, so it
is not a P2 either.

### On the residual risk

The reviewer left W0 as a residual risk rather than a blocker, reasoning that the
NULL representation prevents fabricated zeros if the assumption proves wrong.
That judgement is the reviewer's to make and it was made explicitly rather than
by omission — the packet asked for exactly that call. The bookkeeper does not
overturn it. W0 remains outstanding and carries into review-2.

### Verdict on the verdict

Valid, schema-conforming, fingerprint-matched, and substantively correct.
`rework_count` moves to 1/3.
