Identity:
- task_id: 02-plan-review-2
- target_role: Planner
- target_model: gpt-5.6-sol
- provider: openai
- status_revision: 4
- required_skill: agents/skills/task-planner.md

Goal:
执行第二次独立的、跨 provider 的只读计划评审（针对 HIGH_RISK 平滑平仓 V1 r2 稿）。
设计文档权威：docs/planning/smooth-close-orders-v1.md。

重点回答以下问题：
1. 第一轮评审发现的 R1 是否确实因 C6 反转（改为“备料失败落 paused + 既有中文暂停原因”）而消解，而非仅被绕过？
2. r2 稿新增的 C13/C14/C15/C16 约束是否有当前代码证据支持的漏洞或不可测试点？
3. (复核) 备料前移的陈旧风险是否被完整表达？
4. (复核) 备料只做一次与阈值 1 组合是否安全应对人工平仓产生的单腿？
5. (复核) 备料方向翻转逻辑的取价和数量档位是否完全正确？

若提出新假设场景，须给出当前代码路径、官方契约或具体并发/单位证据，符合 AGENTS.md §1 Scenario Admission。

Allowed Files:
- reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/02-plan-review-2.handoff.md (创建)
- preflight: `test ! -e reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/02-plan-review-2.handoff.md` 已通过 (文件不存在)

Inputs:
- docs/planning/smooth-close-orders-v1.md
- reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/01-plan-review.handoff.md
- docs/planning/smooth-open-orders-v1.md
- backend/domain/snapshot.py
- backend/hedge_open_tasks/domain.py
- backend/hedge_open_tasks/service.py
- backend/hedge_open_tasks/store.py
- frontend/index.html
- agents/roles.md (Task Handoff Evidence Contract 规范)
- AGENTS.md

Acceptance Checks:
1. 明确回答了 R1 是否消解以及 C13-C16 是否有代码证据支持的漏洞。
2. 明确回答其余原有核心问题。
3. 只读评审，符合隔离要求，未尝试修改代码或文件。
4. 遵循 Task Handoff Evidence Contract 创建 handoff 交接件。
5. 返回 `[TASK_RESULT v2]` 收尾（评审结论 ACCEPT / REWORK 等）。

Stop:
完成计划评审报告，创建 handoff 文件，返回 TASK_RESULT，结束。
