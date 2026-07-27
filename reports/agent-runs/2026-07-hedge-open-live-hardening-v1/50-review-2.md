# Review-2 — Hedge Open Live Hardening v1

结论：`REWORK`（需要返工）。S1、S2、S3、S4 的实现与冻结契约一致，且实盘验收已独立证明 S1 的订单编号长度修复和 S3 的闸门写入路径可用；但 S5 没有把已加载的交易对数量过滤条件接入离线记录传输层，未达到任务书要求的“离线传输拒绝违反 quantity precision/filter 的参数”。在这个缺口修复并复审前，不能进入用户验收状态。

## 审查范围与证据

- 固定提交范围：`6c5b17002cab189d752177b447ff576356998f58..319d8317bdf180750197c95078d2ae6c60e6badc`。
- 我独立重算的二进制 diff 哈希为 `2a457c0f559fec81cfba8b9d59602c8630bbec73d7b86b28dddab12c4e554efd`，与固定指纹一致。
- 当前分支在该范围之后没有 `backend/` 或 `frontend/` 产品代码差异；审查仍只以固定范围为准。
- 实际阅读了任务书、intake、设计/ADR/开发拆分、R4 对账、两份实现报告、两份 Review-1、合并态测试输出、实盘验收记录、上一 stage 的冻结 entries 词表、源码与测试，以及固定 git diff。
- 本会话重新执行（无网络）：
  - `.venv/bin/python -m pytest backend/tests/test_hedge_wire_constraints.py backend/tests/test_hedge_api.py backend/tests/test_hedge_store.py backend/tests/test_hedge_service.py backend/tests/test_hedge_preflight_provider.py backend/tests/test_hedge_executor.py backend/tests/test_live_hedge_executor.py -q` → `172 passed`。
  - `node frontend/self-check.js` → `122 PASS`，全部自检通过。
  - `git diff --check 6c5b170..319d831` → 通过。

## 逐项复核

- S1：通过。`_client_order_ids()` 的唯一推导改为 `hg{attempt_id}s|p`，固定 35 字符；record 和 live 均复用同一函数，持久化 id 查询的对账路径未变。实盘记录也证明 `-4015` 不再出现且 UM 腿成交。`fmt_decimal()` 使极小 Decimal 不会产生科学计数法，测试覆盖了该行为。
- S2：通过。前端只在 `status === 'running' && worker_active === false` 时放行启动；`null` 的 dry-run 语义和后端的 live `tick()` no-op 均未改变。
- S3：通过。POST 路由、严格 `confirm is True`、版本 CAS、同事务审计、默认关闭和前端每方向一次确认均与设计匹配；409 会刷新 settings 而不自动重试。store 使用 RLock，CAS 更新与日志写入处于同一个 SQLite 事务中。
- S4：通过。三态 probe 仅对成功读取后确认缺失的腿拒绝创建；`None` 不被误当作 `False`。前端正确显示 worker 三态、八个中文退出原因和 `missing_leg` 的中文 detail。
- 冻结契约：通过。状态枚举和 entries 的 `overall_result` / `next_action` 词表未被改写；settings 的 `version` 是允许的 additive 字段。
- 实盘验收暴露的 F-1 至 F-4：同意其不属于本 stage 五项交付代码的判断。它们分别是外部订单响应契约漂移、上一 stage 的错误码分类、未持久化错误消息与尚未定论的保证金系数问题；本次 diff 未引入这些问题。它们的业务风险应在已提议的独立 stage 中处理，不作为本次返工项。

## Findings

### P2 — S5 的 record transport 未校验已加载的数量过滤条件

`backend/hedge_open_tasks/executor.py:300-301` 对两腿调用 `validate_order_params(spot_params)` / `validate_order_params(perp_params)` 时没有传入 `step_size`、`min_qty` 或 `max_qty`。不过这些值在同一次 preflight 形成的 `AttemptContext.preflight_snapshot` / `filter_versions` 中本可获得；`backend/hedge_open_tasks/wire_constraints.py:102-119` 也已经实现了接收这些参数后的检查。

我以 `q_common=0.0005`、两腿 `step_size=min_qty=0.001` 构造了纯内存 `AttemptContext`：record transport 结果为 `category=success`、`error_code=None`、没有 `constraint_violations`；将它输出的同一 `spot_order_params` 传入 `validate_order_params(..., step_size='0.001', min_qty='0.001', max_qty='100')` 后，得到 `quantity is not a whole multiple of step_size` 和 `quantity is below min_qty`。这证明问题在消费者接线，而不是校验器本身。

影响：S5 所承诺的“已加载 symbol filters 的 quantity precision/bounds 离线拒绝”在默认 dry-run record transport 中仍会漏过。现有测试之所以全绿，是因为 grid/bounds 只直接测试校验函数（`test_hedge_wire_constraints.py:121-134`），而 record transport 的端到端测试只覆盖 client ID 过长（同文件 `164-204`）。这不是立即放开实盘闸门的漏洞，但它正是本阶段要关闭的离线回归防线，故定为 P2。

当前 Session ID: unavailable（本 Codex 运行环境未暴露 provider-native Session ID）
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/50-review-2.md
本地北京时间: 2026-07-27 23:30:31 CST
下一步模型: bookkeeper
下一步任务: 按本 verdict 的 fix_start_prompt 派发限定的后端修复，重新跑测试、提交、复核并重开 review-1/review-2

{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-open-live-hardening-v1",
  "role": "final_reviewer",
  "model": "GPT-5 Codex",
  "verdict": "REWORK",
  "diff_fingerprint": "319d8317bdf180750197c95078d2ae6c60e6badc:2a457c0f559fec81cfba8b9d59602c8630bbec73d7b86b28dddab12c4e554efd",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml (review-2)",
    "docs/parallel-development-mode.md (R7 / Review-2)",
    "schemas/review-verdict.schema.json",
    "docs/product/PRD.md",
    "docs/architecture/ARCHITECTURE.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/{00-intake.md,00-task.md,10-design.md,11-adr.md,12-development-breakdown.md,13-implementation-backend.dispatch.md,14-implementation-frontend.dispatch.md,16-r4-diff-reconciliation.md,18-live-acceptance-findings.md,20-implementation-backend.md,20-implementation-frontend.md,30-review-1-backend.md,30-review-1-frontend.md,60-test-output.txt,status.json}",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/{11-adr.md,16-replacement-development-breakdown.md}",
    "git diff --binary 6c5b17002cab189d752177b447ff576356998f58..319d8317bdf180750197c95078d2ae6c60e6badc",
    "backend/hedge_open_tasks/{executor.py,wire_constraints.py,service.py,store.py,domain.py}",
    "backend/services/hedge_preflight_provider.py",
    "backend/tests/{test_hedge_wire_constraints.py,test_hedge_executor.py,test_live_hedge_executor.py,test_hedge_api.py,test_hedge_service.py,test_hedge_store.py,test_hedge_preflight_provider.py}",
    "frontend/{index.html,self-check.js}"
  ],
  "findings": [
    {
      "severity": "P2",
      "title": "S5 的离线记录传输层没有应用交易对数量过滤条件",
      "file": "backend/hedge_open_tasks/executor.py",
      "line": 300,
      "evidence": "RecordTransportExecutor.execute 调用 validate_order_params(spot_params) 和 validate_order_params(perp_params) 时未传 step_size/min_qty/max_qty；wire_constraints.py:102-119 已实现这些可选检查。独立纯内存复现中，q_common=0.0005 且两腿 step_size=min_qty=0.001 仍返回 success、无 constraint_violations；同一 params 传入该三个过滤参数后返回非整步长和低于最小量两项违规。",
      "impact": "任务书 S5 要求的 quantity precision/filter 离线防线在 record transport 中并未生效，未来的过滤参数回归仍可能只在真实发送时被交易所拒绝。",
      "recommendation": "从本次 preflight snapshot 的 spot/perp 有效 MARKET 过滤条件提取每腿 step_size、min_qty、max_qty，并传给 record transport 的两次 validate_order_params 调用；新增端到端断言，证明违反 spot 或 perp 有效 grid/bounds 的参数会产生 offline_constraint，而合法整步长参数仍能模拟成功。"
    }
  ],
  "required_fixes": [
    "让 RecordTransportExecutor 对每条腿使用当前 preflight 的有效 MARKET 数量 step_size、min_qty、max_qty 调用 validate_order_params。",
    "新增端到端 record-transport 回归测试：违反任一腿过滤条件时两腿均以 offline_constraint 拒绝，且合法参数仍通过；不得只测试 validate_order_params 的直接调用。",
    "保留 ADR-H4：不得把 wire_constraints 挂到 live send 路径，不得改变冻结状态/entries 词表或实盘授权结构。"
  ],
  "residual_risks": [
    "实盘验收确认 S1 的 35 字符 id 和 S3 写入路径有效，但发现的 F-1 至 F-4 不在本阶段五项范围，已应转入独立的 order-truth/error-fidelity stage。",
    "Review-1 记录的 confirm 负例容器覆盖与弹窗正文 includes 断言属于 P3 测试紧度问题，不阻塞本次 P2 修复。"
  ],
  "fix_start_prompt": "[HARNESS-EXECUTOR-CONTRACT v1]\n你是本任务唯一的后端修复实现者。禁止调用、启动或转派任何其他模型会话或 adapter 命令；不得访问凭据、发起 Binance 请求、启动服务、改动实盘闸门、下单或提交 git。只在本地源码与测试中完成下列限定修复，结束后运行指定测试、写报告并停止等待 bookkeeper。\n\nStage：2026-07-hedge-open-live-hardening-v1。被复核的固定范围与指纹：6c5b17002cab189d752177b447ff576356998f58..319d8317bdf180750197c95078d2ae6c60e6badc；319d8317bdf180750197c95078d2ae6c60e6badc:2a457c0f559fec81cfba8b9d59602c8630bbec73d7b86b28dddab12c4e554efd。原始终审证据：reports/agent-runs/2026-07-hedge-open-live-hardening-v1/50-review-2.md（其末尾 JSON verdict 是权威，不得用本提示替代或改写它）。需求与设计原文：00-task.md 的 S5、10-design.md §2.5、11-adr.md ADR-H4、12-development-breakdown.md；当前实现与测试：backend/hedge_open_tasks/{executor.py,wire_constraints.py,service.py,domain.py}，backend/tests/test_hedge_wire_constraints.py，backend/tests/test_hedge_executor.py，backend/tests/test_live_hedge_executor.py。\n\nFinding P2（必须修）：RecordTransportExecutor.execute 在 executor.py 约 300 行对 spot/perp 调 validate_order_params 时没有传 step_size/min_qty/max_qty。校验器在 wire_constraints.py:102-119 已支持这些参数，因此 q_common=0.0005 与两腿 step_size=min_qty=0.001 仍被 record transport 模拟为 success；同一 params 带过滤条件直接校验会被拒绝。影响是 S5 的“离线传输拒绝已加载 symbol filters 的 quantity precision/bounds”没有兑现。\n\n必须完成：\n1. 从同一 attempt 的现有 preflight snapshot（或当前已传入且能准确表达该 snapshot 的上下文）为 spot 与 perp 分别解析有效 MARKET quantity step_size、min_qty、max_qty，遵循现有 domain.effective_market_step / quantity-bounds 的 MARKET_LOT_SIZE 优先、LOT_SIZE 回退语义；将结果传入 record transport 对各腿的 validate_order_params。不要重复实现一套不同的过滤选择规则。\n2. 新增端到端行为测试，而非只测 validate_order_params：构造包含过滤条件的 AttemptContext，使任一腿 quantity 违反有效 step/min/max 后 RecordTransportExecutor 返回 offline_constraint、记录 constraint_violations 且不模拟 fill；再证明合法 grid quantity 正常成功。测试需覆盖 spot/perp 过滤条件可不同的情形或等价证明每腿独立采用自己的过滤条件。\n3. 保持 clientOrderId 修复、fmt_decimal、S1-S4、S3 CAS 与所有冻结 API/status/entries 词表不变。ADR-H4 是冻结决定：绝不把 wire_constraints 导入或挂接到 backend/services/live_hedge_executor.py、hedge_open_live_client.py 或真实发送路径。\n\n允许改动：backend/hedge_open_tasks/executor.py；必要时 backend/hedge_open_tasks/wire_constraints.py 或 domain.py（仅复用/暴露现有纯过滤选择语义）；backend/tests/test_hedge_wire_constraints.py、backend/tests/test_hedge_executor.py。若确有必要，可修改与该最小接线直接相关的 backend 测试。\n禁止改动：frontend/**、backend/services/live_hedge_executor.py、backend/services/hedge_open_live_client.py、backend/app/server.py、数据库 schema/迁移、实盘配置/数据、reports 的既有 review 原始证据、status.json、70-handoff.md、任何用户产品/架构文档。禁止网络、凭据和任何真实 POST。\n\n精确测试命令：\n.venv/bin/python -m pytest backend/tests/test_hedge_wire_constraints.py backend/tests/test_hedge_executor.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py backend/tests/test_hedge_store.py backend/tests/test_hedge_preflight_provider.py -q\nnode frontend/self-check.js\ngit diff --check\n\n完成后写 reports/agent-runs/2026-07-hedge-open-live-hardening-v1/40-fix-review-2-s5.md：按 P2 → 修改文件/行 → 新增行为测试 → 每条命令结果逐项映射，包含标准 footer；不要提交、不要更新 status.json 或 70-handoff.md，停止等待 bookkeeper 进行 R4、证据提交与新的隔离 review。",
  "next_action": "fix"
}
