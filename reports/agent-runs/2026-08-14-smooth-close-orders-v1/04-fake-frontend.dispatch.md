Identity:
- task_id: 04-fake-frontend
- target_role: Implementer
- target_model: grok-4.6
- provider: xai
- status_revision: 6
- required_skill: agents/skills/senior-developer.md

Goal:
实现平滑平仓 V1 的前端 fake 样式。功能与规格要求直接引用 reports/agent-runs/2026-08-14-smooth-close-orders-v1/04-fake-frontend-spec.md。

Allowed Files:
- frontend/index.html
- reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/04-fake-frontend.handoff.md (创建)
- preflight: `test ! -e reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/04-fake-frontend.handoff.md` 已通过 (文件不存在)

Inputs:
- reports/agent-runs/2026-08-14-smooth-close-orders-v1/04-fake-frontend-spec.md
- docs/planning/smooth-close-orders-v1.md
- frontend/index.html
- agents/developer-discipline.md
- agents/roles.md (Task Handoff Evidence Contract 规范)
- AGENTS.md

Acceptance Checks:
参见 `04-fake-frontend-spec.md` 中定义的验收矩阵。实现必须通过其中的所有验收项。

Stop:
完成前端样式实现并创建 handoff 文件后，输出 TASK_RESULT 并停止。
只提交到当前 stage 分支，禁止 push、禁止 merge，且**不启动后端实现**。
