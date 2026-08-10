Identity
- task_id: local-net-position-quantity-implement
- target_role: Implementer
- target_model: claude_glm
- provider: zhipu_glm
- status_revision: 3
- required_skill: agents/skills/senior-developer.md

Goal
- 用现有 `hedge_open_leg` 成交账本修正活跃周期的本地剩余持仓量：每条腿分别按 `Σ(open cumulative_base_qty) - Σ(close cumulative_base_qty)` 输出。
- 保持开仓成本基、API 字段集合和下游 merge 代码不变；修复 XVG 部分平仓误报，并让 XLM 型单腿平仓第一次能由本地账本触发既有失衡标记。
- 只做中央聚合、现有测试和 API 语义文档的最小改动。

Allowed Files
- `backend/hedge_open_tasks/store.py`
- `backend/tests/test_hedge_cycle_close.py`
- `backend/tests/test_hedge_cycle_core.py`
- `backend/tests/test_hedge_store.py`
- `backend/tests/test_positions_merge.py`
- `backend/tests/test_hedge_api.py`
- `docs/api/public-market-contract.md`
- `reports/agent-runs/2026-08-10-local-net-position-v1/status.json`（仅允许本任务结束时把自己的 `current_task.state` 从 `dispatched` 改为 `reported`；其他字段不得改）
- 只允许新建：`reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-quantity-implement.handoff.md`
- Bookkeeper preflight 已执行并通过：`test ! -e reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-quantity-implement.handoff.md`。
- 允许在 stage 分支创建一个包含实现、测试、API 文档、handoff 和上述单一状态变化的 delivery commit。
- 上述清单外全部只读；范围不足即 `blocked`，不得自行扩域。

Inputs
1. `AGENTS.md`
2. `reports/agent-runs/2026-08-10-local-net-position-v1/03-implement.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-10-local-net-position-v1/status.json`
6. `agents/roles.md`（只读 Shared Rules、Task Handoff Evidence Contract、Implementer）
7. `agents/developer-discipline.md`
8. `agents/skills/senior-developer.md`
9. `reports/agent-runs/2026-08-10-local-net-position-v1/00-change-plan.md`
10. `reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-plan-review.handoff.md`
11. `reports/agent-runs/2026-08-10-local-net-position-v1/evidence/plan-review-f1-counter-evidence.md`
12. `reports/agent-runs/2026-08-10-local-net-position-v1/evidence/plan-review-f1-human-adjudication.md`
13. `backend/hedge_open_tasks/store.py`
14. `backend/hedge_open_tasks/domain.py`（只读：确认下游自然消费净量，不修改）
15. `backend/tests/test_hedge_cycle_close.py`
16. `backend/tests/test_hedge_cycle_core.py`
17. `backend/tests/test_hedge_store.py`
18. `backend/tests/test_positions_merge.py`
19. `backend/tests/test_hedge_api.py`
20. `docs/api/public-market-contract.md`

Acceptance Checks
1. `aggregate_positions()` 的现行 leg 查询同时读取 active cycle 的 open/close 腿并带出 `t.task_type`；已关闭周期过滤和 legacy `hedge_open_fill` 告警策略不变。
2. 每条腿只按真实 `cumulative_base_qty > 0` 计量：open 为 `+q`、close 为 `-q`；不得用 task status、pair outcome、目标数量或 accepted/success counter 代替实际成交。
3. `spot_notional/perp_notional` 与 `spot_qty_priced/perp_qty_priced` 仍只由 open 腿贡献；close 腿不得进入 `spot_avg/perp_avg` 的分子或分母。
4. 输出字段集合不变：`spot_qty/perp_qty` 是本地账本剩余绝对量，`position_qty` 仍按 forward 负、reverse 正表示剩余合约方向；不得修改 `domain.py` 或前端。
5. XVG 回归：open `50000` + 两次双腿 close 各 `10000` → 两腿 `30000`、forward `position_qty=-30000`、开仓均价不变；账户也为 `30000` 时既有 `drift=false`、`single_leg_exposure=false`。
6. XLM 型回归：reverse open 双腿 `100`，close 只有 perp 实际成交 `100`、spot 零成交 → 剩余 spot `100` / perp `0`，既有 `single_leg_exposure=true`；不得因 pair 失败忽略 perp 成交。
7. 至少覆盖：双腿部分平仓、单腿 close、literal status 非 FILLED 但累计成交为正、零成交失败、reverse、部分平仓后同周期再加仓、已删除但真实成交仍计入、周期关闭后不展示。
8. 不新增“open 成交为 0 就隐藏桶”的代码。首轮 F-1 已由 Human/Planner 降为不准入的观察；若实现中发现真实可执行反例，停止并按 handoff 报告，不静默扩域。
9. `docs/api/public-market-contract.md` 追加既有三个本地数量字段的新语义，并明确：它们不是交易所对账；`um_position_amt` 是同次账户快照的交易所合约量；`single_leg_exposure=false` 与 `drift=false` 都不能解读为完全一致。
10. 运行并保存完整结果：`.venv/bin/python -m pytest backend/tests/test_hedge_cycle_close.py backend/tests/test_hedge_cycle_core.py backend/tests/test_hedge_store.py backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py`。
11. 运行 `git diff --check`；确认无 schema migration、无 DB/data 变化、无服务/闸门/订单/借还款/划转路径变化。
12. 创建唯一 handoff：`base_sha` 必须等于 status 中固定值，`delivery_sha=pending`；列出真实改动、测试原始结果、未完成事项与下一步 Kimi review-1 所需读取路径。随后仅把 status state 改为 `reported`，创建一个 delivery commit，并输出同源 `TASK_RESULT v2`。

Stop
- 完成实现、自测、唯一 handoff、`reported` 状态和一个 delivery commit 后停止。
- 不启动或联系 Reviewer，不创建 review dispatch，不自评 ACCEPT，不 merge、不 push、不部署、不启动/重启服务、不修改闸门、不读取凭证、不访问或修改 live DB。
