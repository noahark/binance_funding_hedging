Identity:
- task_id: 07-backend-p1-repair-1
- target_role: Implementer
- target_model: glm-5.3
- provider: zhipu_glm
- status_revision: 10
- required_skill: agents/skills/senior-developer.md

Goal:
针对 Review-1 阻塞发现 F1 进行最小修复（当前受审代码：c4ae93a）。
F1 根因：`_start_smooth_close` 对 `SIGNAL_PREFLIGHT_INCOMPLETE` 返回值只抛了错，没有调用 `_pause_preflight_incomplete` 将确切原因落库，导致前端显示旧文案。
修复要求：对 `SIGNAL_PREFLIGHT_INCOMPLETE` 分支先 `_pause_preflight_incomplete` 再返回 HTTP 响应（detail 使用新写入的中文原因）。同时补充测试覆盖 `get_snapshot=None` 时不得回显 `awaiting_manual_start`。

Allowed Files:
- backend/hedge_open_tasks/service.py
- backend/tests/test_smooth_close_p1.py
- reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/07-backend-p1-repair-1.handoff.md (创建)

Inputs:
- reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/06-backend-p1-review-1.handoff.md (重点关注 F1)
- backend/hedge_open_tasks/service.py
- backend/tests/test_smooth_close_p1.py
- agents/developer-discipline.md

Acceptance Checks:
1. 仅针对 F1 做最小修复，不得扩大范围：不加互斥、不改立即平仓的轮次三道门、不改 L1-L3。
2. 修复后运行 `python3 -m pytest backend/tests -q` 必须通过（允许 1 条已知 urlopen 既有失败）。
3. 补测验证：当 `get_snapshot=None` 或出现预检不完整时，`post_start` 能够将确切的中文暂停原因写入数据库并返回在 409 detail 中。

Stop:
完成修复、自测与 handoff 创建后，返回 TASK_RESULT 并停止，不得执行未授权动作（如 push 或 merge）。等待 Bookkeeper 固定新的 delivery_sha，之后将回到 Review-1 复看。
