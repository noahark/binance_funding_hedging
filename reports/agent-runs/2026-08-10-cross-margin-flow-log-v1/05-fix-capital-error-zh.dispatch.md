Identity
- task_id: fix-capital-flow-error-zh-v1
- target_role: Implementer（窄修复，原交付作者）
- target_model: claude_glm
- provider: zhipu_glm
- status_revision: 6
- required_skill: agents/skills/senior-developer.md

Goal
- 修复 review-2 F-1：为 capital 失败短码补齐前端中文映射，使中栏失败态与利息/合约栏一致显示中文。
- 最小改动：仅在 `frontend/index.html` 的 `FLOW_LOG_ERROR_ZH` 增加两个 key（建议文案见下）；可选在 `frontend/self-check.js` 加一条失败态中文断言（非必需）。
- 不扩大范围、不改后端/契约/schema、不触碰 capital 拉取/隔离逻辑。
- 自测、提交、写 handoff 后停止；按 §8 窄发现，修复后**直接回 review-2**（不重新 review-1）。

Allowed Files
- Bookkeeper preflight：`test ! -e reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/fix-capital-flow-error-zh-v1.handoff.md` → 结果：absent；create-only，已存在即任务失败。
- `frontend/index.html`（仅 `FLOW_LOG_ERROR_ZH` 及相关失败态展示所需的最小改动）
- `frontend/self-check.js`（可选：失败态中文断言；不得改与 F-1 无关逻辑）
- create-only handoff：`reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/fix-capital-flow-error-zh-v1.handoff.md`
- 禁止：改 `backend/**`、`docs/**`、`data/**`、其它前端功能、部署/重启/实盘写。

Inputs
1. `AGENTS.md`
2. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/05-fix-capital-error-zh.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/status.json`
6. `agents/roles.md`（Implementer + Shared Rules + Task Handoff Evidence Contract）
7. `agents/developer-discipline.md`
8. `agents/skills/senior-developer.md`
9. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/review-2-cross-margin-capital-flow-v1.handoff.md`（F-1 与修复要求权威）
10. `frontend/index.html`（`FLOW_LOG_ERROR_ZH`、`flowLogErrorZh`、`renderFlowLogCapitalCol` 失败文案）
11. `backend/ledger_flow/service.py`（只读：确认短码字面量 `capital_flow_failed` / `capital_internal_error`）

Acceptance Checks
1. `FLOW_LOG_ERROR_ZH` 含：
   - `capital_flow_failed` → 中文（建议：`全仓流水拉取失败`）
   - `capital_internal_error` → 中文（建议：`全仓流水内部错误`）
2. 中栏在 `last_run.status=error` 时经 `flowLogErrorZh` 显示上述中文，**不**原样露出 snake_case 短码。
3. 既有四条错误中文映射不变；无其它无关 diff。
4. `node frontend/self-check.js` 全绿；若加了失败态断言则一并绿。
5. 创建唯一 handoff；顺序 实现→自测→提交→写 handoff；`delivery_sha` 填本次修复提交的实际 `git rev-parse`（非 pending）。

Stop
- 修复、自测、提交、写 handoff、控制台 TASK_RESULT 后停止。
- 不启动 review、不 merge、不 push、不部署、不重启服务。
