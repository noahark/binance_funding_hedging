Identity
- task_id: local-net-position-review-1
- target_role: Reviewer
- target_model: kimi
- provider: moonshot
- status_revision: 4
- required_skill: agents/skills/code-reviewer.md

Goal
- 对固定区间 `53ed646f4b97d07ea478a834ed8eb6acb83bbedf..b67862aa188d96247db7c807d33846ce4750e8e2` 做独立只读 review-1，核验中央本地净持仓聚合的正确性、API 契约、测试覆盖和集成边界。
- 重点确认 open/close 腿只影响剩余数量、close 不污染开仓成本基，并能区分 XVG 双腿部分平仓与 XLM 单腿平仓。
- 输出明确 `ACCEPT` 或 `REWORK`；不实现修复，不判断部署或实盘启用。

Allowed Files
- 只允许新建：`reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-review-1.handoff.md`。
- Bookkeeper preflight 已执行并通过：`test ! -e reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-review-1.handoff.md`。
- 该路径是 Task Handoff Evidence Contract 规定的 Reviewer create-only 例外；除创建此唯一 handoff 外，仓库全部只读，不得修改 status、代码、文档、既有 evidence 或 Git 历史。

Inputs
1. `AGENTS.md`
2. `reports/agent-runs/2026-08-10-local-net-position-v1/04-review-1.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-10-local-net-position-v1/status.json`
6. `agents/roles.md`（只读 Shared Rules、Task Handoff Evidence Contract、Reviewer）
7. `agents/skills/code-reviewer.md`
8. `reports/agent-runs/2026-08-10-local-net-position-v1/00-change-plan.md`
9. `reports/agent-runs/2026-08-10-local-net-position-v1/03-implement.dispatch.md`
10. `reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-plan-review.handoff.md`
11. `reports/agent-runs/2026-08-10-local-net-position-v1/evidence/plan-review-f1-counter-evidence.md`
12. `reports/agent-runs/2026-08-10-local-net-position-v1/evidence/plan-review-f1-human-adjudication.md`
13. `reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-quantity-implement.handoff.md`
14. 固定 Git 区间 `53ed646f4b97d07ea478a834ed8eb6acb83bbedf..b67862aa188d96247db7c807d33846ce4750e8e2` 的原始 diff 与提交列表；区间内 stage 控制文件只作上下文，实际交付代码、测试与 API 文档是受审对象。
15. `backend/hedge_open_tasks/store.py`
16. `backend/hedge_open_tasks/domain.py`（只读集成边界）
17. `backend/tests/test_hedge_cycle_close.py`
18. `backend/tests/test_hedge_cycle_core.py`
19. `backend/tests/test_hedge_store.py`
20. `backend/tests/test_positions_merge.py`
21. `backend/tests/test_hedge_api.py`
22. `docs/api/public-market-contract.md`

Acceptance Checks
1. 先核对 status revision、stage、target model/provider 与固定 `base_sha..delivery_sha`；评审只锚定这两个 SHA，不使用移动的 HEAD 代替。
2. 检查 `aggregate_positions()` 同读活跃周期 open/close 腿并带出 `task_type`；已关闭周期过滤、legacy fill 告警、删除任务的成交保留及 identity 语义没有被意外改变。
3. 检查数量仅以每腿真实 `cumulative_base_qty > 0` 为准，open `+q`、close `-q`；不得受 task status、pair outcome、目标量或 success/accepted 计数替代。
4. 检查 `spot_notional/perp_notional` 与 priced 分母仅累计 open 腿；close 报价不能改变 `spot_avg/perp_avg` 或 incomplete 语义。
5. 检查输出字段集合与下游契约不变：`spot_qty/perp_qty` 为本地剩余量，`position_qty` 保持 forward 负、reverse 正；`domain.py`、前端和下单/闸门未改。
6. 核验 XVG 回归（50000−10000−10000=30000，双腿及均价正确）和 XLM 回归（reverse open 100，perp close 100、spot close 0 → spot 100/perp 0），以及既有 `single_leg_exposure`/drift 的消费结果。
7. 核验部分成交状态但正成交、零成交、reverse、同周期再开、已删除任务成交、关闭周期过滤等边界测试；评估 `task_type` 的合法值假设是否与 domain/store 写路径一致。
8. 核验 v0.18 文档没有把本地净量误写成交易所对账，并清楚区分 `um_position_amt`；两个弱标记为 false 不代表完全一致。
9. 独立运行：`.venv/bin/python -m pytest backend/tests/test_hedge_cycle_close.py backend/tests/test_hedge_cycle_core.py backend/tests/test_hedge_store.py backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py`，并运行 `git diff --check 53ed646f4b97d07ea478a834ed8eb6acb83bbedf..b67862aa188d96247db7c807d33846ce4750e8e2`；在 handoff 保留原始命令与结果。
10. 对每条 finding 按 `AGENTS.md` §8 标注范围三分类并给出证据；Reviewer 自提新假设若要阻塞，必须通过 Scenario Admission，说明对当前交付的实际影响及本轮必须修的理由。F-1 已由 Human 降级，不得仅凭同一未准入假设重新阻塞。
11. 创建唯一 review handoff，作者区 `base_sha` 与 `delivery_sha` 必须分别为上述固定 SHA；Human Brief 给出合规 `TASK_RESULT v2` 和明确 `评审结论: ACCEPT（接受） | REWORK（返工）`。若 REWORK，问题记录和可执行修复要求均指向该 handoff。
12. 本 stage 的 review-2 已获 Human 一次性豁免；review-1 `ACCEPT` 只把结果交给 Bookkeeper 核验，Reviewer 不执行合并。合并、部署、重启和实盘仍是独立权限边界。

Stop
- 完成一次完整只读评审、创建唯一 handoff 并输出与其 Human Brief 同源的控制台回执后停止。
- 不修改交付、不修复 finding、不修改 status/PROJECT_STATE/既有 evidence、不 commit、不 merge、不 push、不部署、不启动/重启服务、不修改闸门、不读取凭证、不访问 live DB，也不启动或联系其他模型。
