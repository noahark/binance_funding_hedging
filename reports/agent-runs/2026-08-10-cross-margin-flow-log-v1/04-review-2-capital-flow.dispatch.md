Identity
- task_id: review-2-cross-margin-capital-flow-v1
- target_role: Reviewer（review-2，需求/实际效果/证据/运行风险/发布就绪）
- target_model: sonnet5
- provider: anthropic
- status_revision: 5
- required_skill: agents/skills/reality-checker.md

Goal
- 对已封存交付 `base_sha..delivery_sha` =
  `a11a8734a3da988501fa5cac5baa52dcea3ea2ef..9a4e0198ee7f7d2102ab1b9550c39e79a76e24fa`
  做只读 review-2（reality check）。
- 对照 Human 已确认的改写计划与 review-1 ACCEPT：判断实际效果是否满足「全仓 capital-flow 本地缓存 + 流水中栏真数据」、隔离是否守住（对冲净盈亏不因 capital 变「暂无」）、证据是否足以进入 Human 合并决策。
- 返回明确 `ACCEPT` 或 `REWORK`；`REWORK` 须可执行。

Allowed Files
- Bookkeeper preflight：`test ! -e reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/review-2-cross-margin-capital-flow-v1.handoff.md` → 结果：absent；create-only，已存在即任务失败。
- create-only handoff：`reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/review-2-cross-margin-capital-flow-v1.handoff.md`
- 除上述 handoff 外仓库**完全只读**。

Inputs
1. `AGENTS.md`
2. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/04-review-2-capital-flow.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/status.json`
6. `agents/roles.md`（Shared Rules、Task Handoff Evidence Contract、Reviewer）
7. `agents/skills/reality-checker.md`
8. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/00-change-plan.md`
9. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/implement-cross-margin-capital-flow-v1.handoff.md`
10. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/review-1-cross-margin-capital-flow-v1.handoff.md`（含 Bookkeeper ACCEPT 核验）
11. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/cross-margin-flow-log-plan-review.handoff.md`
12. 固定 diff：`git diff a11a8734a3da988501fa5cac5baa52dcea3ea2ef..9a4e0198ee7f7d2102ab1b9550c39e79a76e24fa`（代码交付以 `9a4e019` 为主）
13. `git show 9a4e019 --stat`
14. `backend/ledger_flow/service.py` / `store.py` / `domain.py`
15. `backend/services/private_client.py`
16. `backend/app/server.py`（只读：coverage_for_window 消费点）
17. `frontend/index.html` / `frontend/self-check.js`
18. `docs/api/public-market-contract.md`
19. recon（运行时语境）：`reports/api-samples/2026-08-margin-account-flow-recon-v1/20260810T062742Z/recon.md`

Acceptance Checks
1. 需求对齐：1 天首窗、小时增量、不分页、全仓单源、中栏真数据、假数据已去，是否与交付一致。
2. 运行/账务风险：隔离是否守住（不污染 coverage aggregate / flow_refresh_runs / delta / last_run）；对冲净盈亏路径是否仍 fail-closed 于既有两源。
3. 证据充分性：review-1 复跑与实现自测是否可信；是否还有必须本轮修的缺口（非「可观测后续」）。
4. 发布就绪：schema_version 未 bump、additive API、无部署/实盘写义务是否诚实记录。
5. 发现范围三分类；Scenario Admission 门。
6. 唯一 handoff；delivery_sha=`9a4e0198ee7f7d2102ab1b9550c39e79a76e24fa`；评审结论 ACCEPT 或 REWORK 合规。

Stop
- 完成只读评审、创建 handoff、输出控制台回执后停止。
- 不实现、不修代码、不 merge、不 push、不部署、不重启服务。

Note（provider 隔离）
- 实现：`claude_glm` / zhipu_glm；review-1：`kimi` / moonshot。
- 本 review-2 必须为第三 provider：默认 `sonnet5` / anthropic。
- Bookkeeper `grok4.5`（xai）已参与本 stage 派工，**不得**兼任本轮 review-2。
