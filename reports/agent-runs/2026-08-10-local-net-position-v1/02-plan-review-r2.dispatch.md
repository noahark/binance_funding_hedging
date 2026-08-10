Identity
- task_id: local-net-position-plan-review-r2
- target_role: Reviewer（独立高风险计划复评）
- target_model: sonnet5
- provider: anthropic
- status_revision: 2
- required_skill: agents/skills/software-architect.md

Goal
- 对首轮 Opus 5 REWORK 的唯一 finding F-1 做窄范围独立复评，并判断 Planner 在 `00-change-plan.md` §8 的 contested 裁定是否成立。
- 复评必须依据完整 live 顺序、UM guard、reduce-only 语义、当前本机证据和 Scenario Admission，而不是因前次 verdict 为 REWORK 就默认维持。
- 若 F-1 不足以阻塞，确认带 §8 澄清的计划能否 `ACCEPT` 并交给 `claude_glm`；若仍 `REWORK`，必须给出能同时满足周期关闭与 live 派发放行的当前证据链。

Allowed Files
- 只允许新建：`reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-plan-review-r2.handoff.md`。
- Bookkeeper preflight 已执行并通过：`test ! -e reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-plan-review-r2.handoff.md`。
- 除上述 create-only handoff 外，仓库完全只读；不得修改计划、状态、源码、测试、文档或现有证据。

Inputs
1. `AGENTS.md`
2. `reports/agent-runs/2026-08-10-local-net-position-v1/02-plan-review-r2.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-10-local-net-position-v1/status.json`
6. `agents/roles.md`（只读 Shared Rules、Task Handoff Evidence Contract、Reviewer）
7. `agents/skills/software-architect.md`
8. `reports/agent-runs/2026-08-10-local-net-position-v1/00-change-plan.md`
9. `reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-plan-review.handoff.md`
10. `reports/agent-runs/2026-08-10-local-net-position-v1/evidence/plan-review-f1-counter-evidence.md`
11. `backend/hedge_open_tasks/store.py`
12. `backend/hedge_open_tasks/service.py`
13. `backend/hedge_open_tasks/domain.py`
14. `backend/hedge_open_tasks/executor.py`
15. `backend/tests/test_hedge_cycle_close.py`
16. `backend/tests/test_hedge_cycle_core.py`
17. `backend/tests/test_hedge_store.py`
18. `backend/tests/test_positions_merge.py`
19. `backend/tests/test_hedge_api.py`
20. `docs/api/public-market-contract.md`

Acceptance Checks
1. 重建 F-1 的完整 live 时序：close 卡创建、周期关闭前提、post_start、fresh preflight、UM guard、prepare_attempt、reduce-only 成交；不得用 dry-run fake 代替交易所可达性。
2. 判断首轮证据是否真正支持“周期已关闭但 UM 门仍会放行”；若主张 stale cache，必须给出当前调用链如何在合法 close_cycle/manual_verify 后保留足量旧仓值的匹配证据，而不是只指出缓存存在。
3. 判断“open 成交为 0 就隐藏整个桶”会不会抹掉异常 close 成交证据；如仍推荐，必须解释为何隐藏优于显式暴露或在派发源头阻断。
4. 核对当前 DB 两项零结果与 10 项 guard 测试的证明边界，不得把当前无实例扩大成永远不可达。
5. 判断 §8 对 R3 的降级处理是否足够：API 文档明确本地净量、交易所 UM 和两个弱标记的边界，但不新增代码标记。
6. 若无其他已准入阻塞项，对完整计划返回 `ACCEPT`；新 finding 必须满足 `AGENTS.md` §1 Scenario Admission。
7. 创建唯一 handoff，结构、delivery SHA=`none`、正式 review closure 与最终 marker 符合 Task Handoff Evidence Contract 和 `TASK_RESULT v2`。

Stop
- 完成窄范围只读计划复评、创建唯一 handoff、输出同源控制台回执后停止。
- 不实现、不修计划、不提交、不启动 GLM、不创建后续 dispatch、不 merge、不 push、不部署、不启动/重启服务、不读取凭证、不访问或修改 live DB。

