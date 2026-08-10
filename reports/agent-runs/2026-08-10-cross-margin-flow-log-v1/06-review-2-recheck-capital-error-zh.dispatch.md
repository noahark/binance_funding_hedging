Identity
- task_id: review-2-recheck-capital-error-zh-v1
- target_role: Reviewer（review-2 窄修复复审）
- target_model: sonnet5
- provider: anthropic
- status_revision: 7
- required_skill: agents/skills/reality-checker.md

Goal
- 对 F-1 窄修复后的封存区间 `a11a8734a3da988501fa5cac5baa52dcea3ea2ef..cf247fbf7060e18afeda0c6366c5724b27ef0ce0` 做只读 review-2 复审。
- 重点核对：review-2 F-1 是否已关闭（`FLOW_LOG_ERROR_ZH` 两码中文；中栏失败态不露 snake_case）；修复是否仍保持窄范围（仅前端、无契约/后端/隔离回退）。
- 原交付其余结论可沿用实现/review-1/首轮 review-2 的已核验证据，本轮不必重做全量账务隔离论证，除非发现修复扩大了范围。
- 返回明确 `ACCEPT` 或 `REWORK`。

Allowed Files
- Bookkeeper preflight：`test ! -e reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/review-2-recheck-capital-error-zh-v1.handoff.md` → 结果：absent；create-only，已存在即任务失败。
- create-only handoff：`reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/review-2-recheck-capital-error-zh-v1.handoff.md`
- 除上述 handoff 外仓库**完全只读**。

Inputs
1. `AGENTS.md`
2. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/06-review-2-recheck-capital-error-zh.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/status.json`
6. `agents/roles.md`（Shared Rules、Task Handoff Evidence Contract、Reviewer）
7. `agents/skills/reality-checker.md`
8. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/review-2-cross-margin-capital-flow-v1.handoff.md`（F-1 权威）
9. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/fix-capital-flow-error-zh-v1.handoff.md`（含 Bookkeeper 核验）
10. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/implement-cross-margin-capital-flow-v1.handoff.md`
11. 固定 diff：`git show cf247fbf7060e18afeda0c6366c5724b27ef0ce0` 与 `git diff a11a8734a3da988501fa5cac5baa52dcea3ea2ef..cf247fbf7060e18afeda0c6366c5724b27ef0ce0 --stat`
12. `frontend/index.html`（`FLOW_LOG_ERROR_ZH`）
13. `frontend/self-check.js`（F-1 断言）

Acceptance Checks
1. F-1 关闭：`capital_flow_failed`/`capital_internal_error` 有中文；失败态不露 snake_case。
2. 修复范围仍窄：diff 仅前端（及可选 self-check）；无后端/契约/schema/隔离回退。
3. self-check 含 F-1 回归路径且全绿（可独立复跑 `node frontend/self-check.js`）。
4. 唯一 handoff；delivery_sha=`cf247fbf7060e18afeda0c6366c5724b27ef0ce0`；ACCEPT 或 REWORK 合规。

Stop
- 完成只读复审、创建 handoff、输出控制台回执后停止。
- 不实现、不修代码、不 merge、不 push、不部署。

Note
- §8 窄 review-2 修复后直接回 review-2；不重新 review-1。
- provider 仍为 anthropic（sonnet5），与实现 zhipu_glm、review-1 moonshot 均不同。
