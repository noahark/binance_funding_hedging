Identity:
- task_id: 05-backend-p1
- target_role: Implementer
- target_model: glm-5.3
- provider: zhipu_glm
- status_revision: 7
- required_skill: agents/skills/senior-developer.md

Goal:
实现平滑平仓 V1 的后端 P1 阶段。具体内容规格及验收要求直接引用 `reports/agent-runs/2026-08-14-smooth-close-orders-v1/05-backend-p1-spec.md`。

Allowed Files:
- backend/hedge_open_tasks/service.py
- backend/hedge_open_tasks/store.py
- backend/hedge_open_tasks/domain.py
- backend/tests/ (相关测试及 conftest)
- reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/05-backend-p1.handoff.md (创建)
- **明确禁止包含与修改**：`frontend/index.html` 与 `backend/app/server.py`
- preflight: `test ! -e reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/05-backend-p1.handoff.md` 已通过 (文件不存在)

Inputs:
- reports/agent-runs/2026-08-14-smooth-close-orders-v1/05-backend-p1-spec.md
- docs/planning/smooth-close-orders-v1.md
- backend/hedge_open_tasks/service.py
- backend/hedge_open_tasks/store.py
- backend/hedge_open_tasks/domain.py
- backend/tests/
- agents/developer-discipline.md
- agents/roles.md
- AGENTS.md

Acceptance Checks:
参见 `05-backend-p1-spec.md`。完成后必须自测通过所有验收项。

Stop:
完成实现与自测后创建 handoff 文件，返回 TASK_RESULT 并停止。只提交到当前 stage 分支本地（禁止 push / merge）。交付后等待 Bookkeeper 固定 base_sha..delivery_sha 并进入 HIGH_RISK 的 Review-1 + Review-2。
