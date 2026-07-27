<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: pending
target_model: claude_glm/glm-5.2[1m]
adapter_cmd: (write-capable Claude-GLM session; filled in by the operator on execution)
executor: human_operator
started_at: unavailable:not yet executed
completed_at: unavailable:not yet executed
session_id: unavailable:not yet executed
outputs: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/40-fix-review-2-s5.md
next_dispatch: re-review after the fix (backend review-1 + review-2 on the NEW pinned range)
receipt_sealed_by: bookkeeper (Claude Opus 5). The PROMPT BODY below is the final reviewer's own fix_start_prompt, copied VERBATIM from the verdict JSON in 50-review-2.md. The bookkeeper added routing metadata only and rewrote nothing.
===== END RECEIPT ===== -->

# Fix Dispatch — Review-2 REWORK (S5 filter wiring) — Hedge Open Live Hardening v1

Human operator: run this in a fresh **write-capable Claude-GLM** (`glm-5.2[1m]`)
session. Claude-GLM authored the backend originally; a fix author may be the
original implementer (AGENTS.md bans only reviewer==implementer), and Review-1
for the reworked code stays provider-isolated from it.

Save the raw report as: `reports/agent-runs/2026-07-hedge-open-live-hardening-v1/40-fix-review-2-s5.md`

## Why this packet exists

Review-2 (GPT-5 Codex) returned **REWORK** on the pinned range
`6c5b170..319d831`. One P2 finding, verified independently by the bookkeeper
against the code:

`RecordTransportExecutor.execute` calls `validate_order_params(spot_params)` and
`validate_order_params(perp_params)` (`executor.py:303-304`) **without** passing
`step_size` / `min_qty` / `max_qty`, even though `wire_constraints.py:101-119`
implements all three checks. So a quantity that violates the symbol's grid or
bounds is still simulated as a successful fill offline.

`00-task.md` S5's acceptance criterion says the offline transport must reject
*"quantity/price precision **against the symbol filters already loaded**"* — the
second half is not met. The validator was built and then not wired in.

**Note for the record**: the backend Review-1 (grok-4.5) observed this same fact
but filed it as a residual risk rather than a finding, reasoning that it matched
10-design §2.5's optional-grid wording. Review-2 measured against the acceptance
criteria instead, which is the correct authority order. That is a genuine
Review-1 miss, recorded in `status.json.review_1_miss`.

## Prompt body — the final reviewer's own fix_start_prompt, VERBATIM

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务唯一的后端修复实现者。禁止调用、启动或转派任何其他模型会话或 adapter 命令；不得访问凭据、发起 Binance 请求、启动服务、改动实盘闸门、下单或提交 git。只在本地源码与测试中完成下列限定修复，结束后运行指定测试、写报告并停止等待 bookkeeper。

Stage：2026-07-hedge-open-live-hardening-v1。被复核的固定范围与指纹：6c5b17002cab189d752177b447ff576356998f58..319d8317bdf180750197c95078d2ae6c60e6badc；319d8317bdf180750197c95078d2ae6c60e6badc:2a457c0f559fec81cfba8b9d59602c8630bbec73d7b86b28dddab12c4e554efd。原始终审证据：reports/agent-runs/2026-07-hedge-open-live-hardening-v1/50-review-2.md（其末尾 JSON verdict 是权威，不得用本提示替代或改写它）。需求与设计原文：00-task.md 的 S5、10-design.md §2.5、11-adr.md ADR-H4、12-development-breakdown.md；当前实现与测试：backend/hedge_open_tasks/{executor.py,wire_constraints.py,service.py,domain.py}，backend/tests/test_hedge_wire_constraints.py，backend/tests/test_hedge_executor.py，backend/tests/test_live_hedge_executor.py。

Finding P2（必须修）：RecordTransportExecutor.execute 在 executor.py 约 300 行对 spot/perp 调 validate_order_params 时没有传 step_size/min_qty/max_qty。校验器在 wire_constraints.py:102-119 已支持这些参数，因此 q_common=0.0005 与两腿 step_size=min_qty=0.001 仍被 record transport 模拟为 success；同一 params 带过滤条件直接校验会被拒绝。影响是 S5 的“离线传输拒绝已加载 symbol filters 的 quantity precision/bounds”没有兑现。

必须完成：
1. 从同一 attempt 的现有 preflight snapshot（或当前已传入且能准确表达该 snapshot 的上下文）为 spot 与 perp 分别解析有效 MARKET quantity step_size、min_qty、max_qty，遵循现有 domain.effective_market_step / quantity-bounds 的 MARKET_LOT_SIZE 优先、LOT_SIZE 回退语义；将结果传入 record transport 对各腿的 validate_order_params。不要重复实现一套不同的过滤选择规则。
2. 新增端到端行为测试，而非只测 validate_order_params：构造包含过滤条件的 AttemptContext，使任一腿 quantity 违反有效 step/min/max 后 RecordTransportExecutor 返回 offline_constraint、记录 constraint_violations 且不模拟 fill；再证明合法 grid quantity 正常成功。测试需覆盖 spot/perp 过滤条件可不同的情形或等价证明每腿独立采用自己的过滤条件。
3. 保持 clientOrderId 修复、fmt_decimal、S1-S4、S3 CAS 与所有冻结 API/status/entries 词表不变。ADR-H4 是冻结决定：绝不把 wire_constraints 导入或挂接到 backend/services/live_hedge_executor.py、hedge_open_live_client.py 或真实发送路径。

允许改动：backend/hedge_open_tasks/executor.py；必要时 backend/hedge_open_tasks/wire_constraints.py 或 domain.py（仅复用/暴露现有纯过滤选择语义）；backend/tests/test_hedge_wire_constraints.py、backend/tests/test_hedge_executor.py。若确有必要，可修改与该最小接线直接相关的 backend 测试。
禁止改动：frontend/**、backend/services/live_hedge_executor.py、backend/services/hedge_open_live_client.py、backend/app/server.py、数据库 schema/迁移、实盘配置/数据、reports 的既有 review 原始证据、status.json、70-handoff.md、任何用户产品/架构文档。禁止网络、凭据和任何真实 POST。

精确测试命令：
.venv/bin/python -m pytest backend/tests/test_hedge_wire_constraints.py backend/tests/test_hedge_executor.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py backend/tests/test_hedge_store.py backend/tests/test_hedge_preflight_provider.py -q
node frontend/self-check.js
git diff --check

完成后写 reports/agent-runs/2026-07-hedge-open-live-hardening-v1/40-fix-review-2-s5.md：按 P2 → 修改文件/行 → 新增行为测试 → 每条命令结果逐项映射，包含标准 footer；不要提交、不要更新 status.json 或 70-handoff.md，停止等待 bookkeeper 进行 R4、证据提交与新的隔离 review。
```

Current dispatch executor: **human operator**. The bookkeeper does not execute
Claude-GLM commands or relay this prompt to a model.

## After the fix returns

The diff will move, so the current fingerprint dies with it. Sequence:
bookkeeper R4 reconciliation → merged-state rerun → evidence commit → NEW
`base..head` and fingerprint → backend Review-1 on the new range (provider
isolated from claude_glm) → Review-2 again. `rework_count` is now 1 of 3.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/60-fix-review-2-s5.dispatch.md
本地北京时间: 2026-07-27 22:40:00 CST
下一步模型: human operator
下一步任务: 在全新写权限 Claude-GLM 终端执行本 packet，产出 40-fix-review-2-s5.md
