# 公网出口 IP 前端：状态范围修复 dispatch — Kimi

## Identity

- task_id: `public-ip-frontend-kimi-status-scope-fix`
- target_role: `Implementer / Bounded Finding Repair`
- target_model: `kimi / Kimi Code`
- provider: `moonshot`
- status_revision: `11`
- required_skill: `agents/skills/minimal-change-engineer.md`

## Goal

修复 Bookkeeper 拒收的唯一流程范围问题：前端交付时，implementer 在获准把自身任务置为
`reported` 之外，还将 `status.json.revision` 从 9 改为 10。该 revision 只由 Bookkeeper
维护；本任务不得修改任何产品代码、端点契约、文档、测试或既有前端交付。

Bookkeeper 已建立 revision 11 的本 repair 状态。你的唯一状态写入是把本 task 的
`current_task.state` 从 `dispatched` 改为 `reported`；不得变更 `revision`、SHA、phase、
checkpoint、rework_count、blockers、next 或其他任何 status 字段。

## Allowed Files

- `reports/agent-runs/2026-08-12-local-ip-display-v1/status.json`（仅将本 task 的 `current_task.state` 从 `dispatched` 改为 `reported`）
- `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-frontend-kimi-status-scope-fix.handoff.md`（唯一新建、create-only）

开始前 handoff 路径必须不存在；若已存在即停止报告：
`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-frontend-kimi-status-scope-fix.handoff.md`。
Bookkeeper 预检：`test ! -e reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-frontend-kimi-status-scope-fix.handoff.md` → `ABSENT`（2026-08-12 20:59 CST）。

## Inputs

按以下顺序读取：

1. `AGENTS.md`
2. 本 dispatch：`reports/agent-runs/2026-08-12-local-ip-display-v1/public-ip-frontend-kimi-status-scope-fix.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-local-ip-display-v1/status.json`
6. `agents/roles.md` 的 `Shared Rules`、`Task Handoff Evidence Contract` 与 `Implementer` 小节
7. `agents/developer-discipline.md`
8. `agents/skills/minimal-change-engineer.md`
9. 被拒收的前端交接：`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-frontend-kimi.handoff.md`
10. 已固定的前端交付提交：`frontend/index.html`、`frontend/self-check.js`

## Acceptance Checks

1. `status.json` 只出现 `current_task.state: "dispatched" → "reported"` 这一处业务字段变化；revision 保持 `11`，其余字段逐字不变。
2. 创建符合 Task Handoff Evidence Contract 的 deterministic handoff，Source Report 写明：本任务不改变前端交付、只修复未授权 revision 写入；author `delivery_sha` 可为 `pending`，由 Bookkeeper 在提交后解析。
3. 执行 `git diff --check`；提交前验证 `git diff --cached --name-status` 只包含这两个 Allowed Files，提交后用 `git show --format= --name-status HEAD` 复核同一范围。将命令与结果写入 handoff。
4. 创建只含这两个 Allowed Files 的本地提交；不得 push、merge、重启、部署、运行服务、读取凭据、访问币安、访问 live DB 或发起公网请求。

## Stop

完成后停止，不得自行启动评审。控制台以 `AGENTS.md` §7 的 `[TASK_RESULT v2]` 收尾；`下一步模型` 写 `codex / GPT-5（Bookkeeper）`，`下一步任务` 必须为：`读取：reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-frontend-kimi-status-scope-fix.handoff.md；执行：Bookkeeper 核验最小状态范围修复并汇总固定 delivery SHA，准备正式评审；关卡：正式评审 dispatch 就绪后由 Human 决定启动`。
