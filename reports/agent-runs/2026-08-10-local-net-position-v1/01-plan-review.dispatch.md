Identity
- task_id: local-net-position-plan-review
- target_role: Reviewer（独立高风险计划评审）
- target_model: opus5
- provider: anthropic
- status_revision: 1
- required_skill: agents/skills/software-architect.md

Goal
- 只读评审 `00-change-plan.md` 是否以最小且可验证的方式修复部分平仓后的本地剩余持仓量。
- 核对逐腿 `open cumulative fill - close cumulative fill` 的语义是否覆盖即时结算、查询补录、限流结算、部分成交和单腿成交，同时保持开仓成本基不变。
- 核对计划的文件边界、测试矩阵与非目标是否足以交给 `claude_glm` 实现。
- 返回明确 `ACCEPT` 或 `REWORK`；`REWORK` 必须给出当前代码/测试证据和可直接改写计划的具体要求。

Allowed Files
- 只允许新建：`reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-plan-review.handoff.md`。
- Bookkeeper preflight 已执行并通过：`test ! -e reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-plan-review.handoff.md`。
- 除上述 create-only handoff 外，仓库完全只读；不得修改计划、状态、源码、测试、文档或现有证据。

Inputs
1. `AGENTS.md`
2. `reports/agent-runs/2026-08-10-local-net-position-v1/01-plan-review.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-10-local-net-position-v1/status.json`
6. `agents/roles.md`（只读 Shared Rules、Task Handoff Evidence Contract、Reviewer）
7. `agents/skills/software-architect.md`
8. `reports/agent-runs/2026-08-10-local-net-position-v1/00-change-plan.md`
9. `backend/hedge_open_tasks/store.py`
10. `backend/hedge_open_tasks/domain.py`
11. `backend/tests/test_hedge_cycle_close.py`
12. `backend/tests/test_hedge_cycle_core.py`
13. `backend/tests/test_hedge_store.py`
14. `backend/tests/test_positions_merge.py`
15. `backend/tests/test_hedge_api.py`
16. `docs/api/public-market-contract.md`

Acceptance Checks
1. 对照真实代码路径判断计划是否覆盖所有会最终写入 `cumulative_base_qty` 的结算路径；不得只凭任务成功状态判断。
2. 明确判断仅改中央聚合是否成立；若要求扩域，必须指出具体调用链和缺失行为。
3. 明确判断 close 数量进入净额但不进入 open 成本分子/分母的设计是否自洽。
4. 用 XVG 双腿部分平仓与 XLM 单腿平仓两个已观察事实核对验收检查能否区分误报与真实失衡。
5. 检查 reverse、部分成交、已删除成交、同周期再加仓、关闭周期过滤和 API 固定字段是否有可执行验证。
6. 新假设场景只有满足 `AGENTS.md` §1 Scenario Admission 才能阻塞；否则不得扩域。
7. 创建唯一 handoff，源区块、Human Brief、marker、delivery SHA=`none` 与正式 review closure 字段全部符合 Task Handoff Evidence Contract 和 `TASK_RESULT v2`。

Stop
- 完成只读计划评审、创建唯一 handoff、输出同源控制台回执后停止。
- 不实现、不修计划、不提交、不启动 GLM、不创建后续 dispatch、不 merge、不 push、不部署、不启动/重启服务、不读取凭证、不访问或修改 live DB。

