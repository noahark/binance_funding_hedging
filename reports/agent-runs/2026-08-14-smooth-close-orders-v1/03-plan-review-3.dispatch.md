Identity:
- task_id: 03-plan-review-3
- target_role: Planner
- target_model: gpt-5.6-sol
- provider: openai
- status_revision: 5
- required_skill: agents/skills/task-planner.md

Goal:
执行第三次独立的、跨 provider 的只读计划评审（针对 HIGH_RISK 平滑平仓 V1 r3 稿）。
设计文档权威：docs/planning/smooth-close-orders-v1.md (HEAD 177f806)。

重点回答以下问题：
1. (a) R2（并发重复划转）作为 Human 具名接受的残余风险，其在 r3 §5.6 中的表述是否完整？该风险的边界是否与当前代码事实相符？【注意：不得仅因其未被代码/设计修复而再次判为阻塞】
2. (b) r3 新增的 C14 条件写机制是否真的封住了已删除任务被并发意外复活的缝隙？
3. (c) r3 新增的 C10 解禁（store gate 去除写死的 open-only）与 C15 的 fail-closed 处置是否可测？它们的设计是否足够严密，以防被“测试全绿但功能全废”的伪实现骗过？
4. (d) r3 的其它修订（C5前置、C12两处补齐、C13置灰、C17备料状态展示）是否引入了新的、有当前代码证据支持的资金缺口或逻辑漏洞？

若提出新假设场景，须符合 AGENTS.md §1 Scenario Admission。

Allowed Files:
- reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/03-plan-review-3.handoff.md (创建)
- preflight: `test ! -e reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/03-plan-review-3.handoff.md` 已通过 (文件不存在)

Inputs:
- docs/planning/smooth-close-orders-v1.md
- reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/01-plan-review.handoff.md
- reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/02-plan-review-2.handoff.md
- docs/planning/smooth-open-orders-v1.md
- backend/domain/snapshot.py
- backend/hedge_open_tasks/domain.py
- backend/hedge_open_tasks/service.py
- backend/hedge_open_tasks/store.py
- backend/app/server.py
- frontend/index.html
- agents/roles.md (Task Handoff Evidence Contract 规范)
- AGENTS.md

Acceptance Checks:
1. 明确回答了 R2 风险的表述完整性与边界相符情况，未违规阻塞。
2. 明确评估了 C14 的防复活效力、C10/C15 的可测性与防作弊性。
3. 明确回答了 r3 其它修订是否有新缺口。
4. 只读评审，符合隔离要求，未尝试修改代码或文件。
5. 遵循 Task Handoff Evidence Contract 创建 handoff 交接件。
6. 返回 `[TASK_RESULT v2]` 收尾（评审结论 ACCEPT / REWORK 等）。

Stop:
完成计划评审报告，创建 handoff 文件，返回 TASK_RESULT，结束。
