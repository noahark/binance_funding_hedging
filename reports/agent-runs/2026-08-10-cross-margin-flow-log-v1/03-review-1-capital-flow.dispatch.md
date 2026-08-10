Identity
- task_id: review-1-cross-margin-capital-flow-v1
- target_role: Reviewer（review-1，代码/契约/测试/接缝）
- target_model: kimi
- provider: moonshot
- status_revision: 4
- required_skill: agents/skills/code-reviewer.md

Goal
- 对已封存交付区间 `a11a8734a3da988501fa5cac5baa52dcea3ea2ef..9a4e0198ee7f7d2102ab1b9550c39e79a76e24fa` 做只读 review-1。
- 重点核对：capital-flow 全仓接入、幂等 `id`、独立 meta、不污染 coverage aggregate / flow_refresh_runs / delta / last_run、前端真数据与缺块空态、schema_version 仍 v2、与 `00-change-plan.md` 冻结条款一致。
- 返回明确 `ACCEPT` 或 `REWORK`；`REWORK` 须含可执行修复要求与发现范围三分类。

Allowed Files
- Bookkeeper preflight：`test ! -e reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/review-1-cross-margin-capital-flow-v1.handoff.md` → 结果：absent；该路径 create-only，已存在即任务失败。
- create-only handoff：`reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/review-1-cross-margin-capital-flow-v1.handoff.md`
- 除上述 handoff 外仓库**完全只读**；不得改计划、status、源码、测试、文档、现有证据。

Inputs
1. `AGENTS.md`
2. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/03-review-1-capital-flow.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/status.json`
6. `agents/roles.md`（Shared Rules、Task Handoff Evidence Contract、Reviewer）
7. `agents/skills/code-reviewer.md`
8. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/00-change-plan.md`
9. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/implement-cross-margin-capital-flow-v1.handoff.md`（含 Bookkeeper 核验块）
10. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/cross-margin-flow-log-plan-review.handoff.md`
11. 固定 diff：`git diff a11a8734a3da988501fa5cac5baa52dcea3ea2ef..9a4e0198ee7f7d2102ab1b9550c39e79a76e24fa`（代码交付以 `9a4e019` 为主；中间控制提交为上下文）
12. `git show 9a4e019 --stat`
13. `backend/ledger_flow/service.py` / `store.py` / `domain.py`
14. `backend/services/private_client.py`
15. `backend/app/server.py`（只读：`coverage_for_window` 消费点，确认未改坏）
16. `frontend/index.html` / `frontend/self-check.js`
17. `docs/api/public-market-contract.md`
18. `backend/tests/test_ledger_flow_*.py` / `test_private_client.py` 相关新增断言

Acceptance Checks
1. 对照 `00-change-plan.md` §4.1/§4.2/§9：隔离、1 天窗口、limit=1000、无翻页、新表+meta、v2 不 bump 是否在代码中成立。
2. 核对 P0-1：`_build_coverage` / `coverage_for_window` 是否仍与 capital 成功/失败无关；测试是否真正挡住回归。
3. 核对幂等与多 type 同 tran_id；失败不推进 capital coverage end；满 1000 标记语义。
4. 前端：无假数据残留；缺 `capital_flow` 空态；筛选与入/出全仓；self-check 路径合理。
5. 发现范围三分类；新假设场景须满足 Scenario Admission。
6. 创建唯一 handoff；delivery_sha 填已封存的 `9a4e0198ee7f7d2102ab1b9550c39e79a76e24fa`；评审结论 ACCEPT 或 REWORK 合规。

Stop
- 完成只读评审、创建 handoff、输出控制台回执后停止。
- 不实现、不修代码、不提交业务修复、不 merge、不 push、不部署。

Note（provider 隔离）
- 实现 provider：`zhipu_glm`（claude_glm）。本 review-1 必须为不同 provider；指定 `kimi`/`moonshot`。
- Bookkeeper/派工方 `grok4.5`（xai）参与过本 stage 调度设计，**不得**兼任本轮 review-1。
