Identity:
- task_id: 08-integration-p2
- target_role: Implementer
- target_model: grok-4.6
- provider: xai
- status_revision: 11
- required_skill: agents/skills/senior-developer.md

Goal:
实现平滑平仓 V1 的前后端串联开发（P2）。
基于目前已冻结的核心能力（包含 05-backend-p1 交付与 07 修复的 API），打通前后端通信链路。暴露 server.py 路由并在 frontend/index.html 中发起真实请求。

Allowed Files:
- frontend/index.html
- backend/app/server.py
- reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/08-integration-p2.handoff.md (创建)

Inputs:
- docs/planning/smooth-close-orders-v1.md
- reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/05-backend-p1.handoff.md (重点参考“冻结的 API 契约”和“读模型对 close 的语义”约定)
- reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/07-backend-p1-repair-1.handoff.md
- frontend/index.html
- backend/app/server.py
- agents/developer-discipline.md

Acceptance Checks:
1. 在 `frontend/index.html` 中替换静态点击行为，向后端真实发送 POST 建卡、状态查询、与强制启动请求。
2. 确保在 `backend/app/server.py` 暴露所有平滑平仓相关 REST 与 WebSocket 接口路由，且命名、请求体结构符合已冻结 API 契约。
3. 维持所有前后台既有功能的隔离与自测试绿灯 (`node frontend/self-check.js`)。

Stop:
完成实现及本地自测后，产出 handoff 交接件并返回 TASK_RESULT，结束任务并等待 Human 启动应用进行端到端检验。
