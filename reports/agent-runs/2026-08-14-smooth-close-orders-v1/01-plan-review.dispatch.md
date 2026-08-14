Identity:
- task_id: 01-plan-review
- target_role: Planner
- target_model: gpt-5.6-sol
- provider: openai
- status_revision: 3
- required_skill: agents/skills/task-planner.md

Goal:
执行一次独立的、跨 provider 的只读计划评审（HIGH_RISK 平滑平仓 V1）。
设计文档权威：docs/planning/smooth-close-orders-v1.md。

重点回答以下问题：
1. 备料前移（预检 + 合约可平量 + forward 现货余额/划转）后，设计文档 §5 列出的陈旧风险是否被完整表达，是否还有未列出的发单前事实在平滑路径上失去拦截；
2. 「备料只做一次、暂停恢复不重做」与「单腿刹车阈值 1」的组合，是否足以覆盖暂停期间人工平仓导致的单腿场景；
3. 方向翻转复用 `compute_opening_spread_pct` 是否在四种（forward/reverse × close）组合下都取到正确的价格与数量档位；
4. 备料失败落 `deleted` 是否会与人工软删除的卡混淆到影响操作判断，中文原因是否确实可见；
5. 是否存在当前代码证据支持的资金安全缺口、不可测试点或不必要复杂度。

若提出新假设场景，须给出当前代码路径、官方契约或具体并发/单位证据，以及它对本交付的实际影响；对偏好不同、已明确接受的风险或未来扩展不应判为阻塞。

Allowed Files:
- reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/01-plan-review.handoff.md (创建)
- preflight: `test ! -e reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/01-plan-review.handoff.md` 已通过 (文件不存在)

Inputs:
- docs/planning/smooth-close-orders-v1.md
- docs/planning/smooth-open-orders-v1.md
- backend/domain/snapshot.py
- backend/hedge_open_tasks/domain.py
- backend/hedge_open_tasks/service.py
- frontend/index.html
- agents/roles.md (Task Handoff Evidence Contract 规范)
- AGENTS.md

Acceptance Checks:
1. 明确回答了上述 5 个评审重点问题。
2. 只读评审，符合隔离要求，未尝试修改代码或文件。
3. 遵循 Task Handoff Evidence Contract 创建 handoff 交接件。
4. 返回 `[TASK_RESULT v2]` 收尾（评审结论 ACCEPT / REWORK 等）。

Stop:
完成计划评审报告，创建 handoff 文件，返回 TASK_RESULT，结束。
