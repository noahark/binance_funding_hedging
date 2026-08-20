# 100-phase3-review2-opus5.dispatch.md

## Metadata
- task_id: `100-phase3-review2-opus5`
- stage_id: `2026-08-19-hedge-order-fee-cost-v1`
- stage_title: `成交手续费冻价成本 V1`
- stage_generation: `new-stage`
- phase: `phase3_review2`
- risk_class: `HIGH_RISK`
- target_model: `opus5`（Anthropic，工作窗 `claude-review`，pane `w1:pJ`）
- target_provider: `anthropic`
- role: `Reviewer`
- skill: `agents/skills/reality-checker.md`
- base_sha: `06c00c07e0181c596292c2f163890456abed3d8d`
- delivery_sha: `3bc6acaec6e3bd2b837239d7a925007a29729db6`

## Goal
依据 `AGENTS.md` §8 Review Rules 与 `agents/skills/reality-checker.md`，对阶段三终章（`80-phase3-aggregate-realtime-glm`）读链路真实聚合与实时开平仓手续费写入进行独立的 Review-2 终审（业务实际效果、契约符合性、实盘运行风险与发布就绪状态）：
1. 审查业务需求与实际效果符合性（10-design §3 D1–D11、§4.1、§5、§7.1、§8）：
   - 持仓表聚合 `aggregate_positions`：只汇总 open 有成交腿；均价严格采用 `quote/base`（严禁使用 `avg_price`）；不全时 `trading_fee_usdt` 与 `fee_bnb_qty` 返回 None、`trading_fee_incomplete=True`；
   - 历史结算聚合 `insert_close_log`：平仓关仓插入新日志时，现算该周期全部 open + close 腿，全部完整写 0，任一不全写 1；显式传参原样落库；
   - 实时开平仓写入：三处终态接线（inline 主终态、inline 暂停终态、drain 终态）在 commit 之后触发至多 1 次 GET；失败不影响腿终态，仅详细记录任务日志；
   - D4 实时现价冻结：复用预检价格链（≤300s 缓存 → 公开现价 → None）；
   - UM 零宽窗修正：零宽/倒置窗向前扩 10 分钟回退窗以支持 inline 终态合约腿；
2. 审查前端契约与自检：
   - 确认前端 `index.html` 渲染逻辑与真数据聚合结构无缝对接；
   - `node frontend/self-check.js` 全绿；
3. 审查测试与代码纯度：
   - `pytest backend/tests/test_hedge_store.py backend/tests/test_hedge_api.py backend/tests/test_hedge_service.py backend/tests/test_backfill_leg_fees.py backend/tests/test_hedge_purity.py`（232 passed）；
   - money-zero 纯度守卫全绿；
4. 审查实盘运行风险与发布就绪状态；
5. 创建交接件 `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/100-phase3-review2-opus5.handoff.md`，并在控制台输出包含明确评审结论（`ACCEPT` 或 `REWORK`）的 `[TASK_RESULT v2]` 收口。

## Allowed Files (Reviewer Create-Only)
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/100-phase3-review2-opus5.handoff.md`（仅可创建此文件，禁止修改其他任何文件）

## Read-Only Inputs
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md`（§3、§4.1、§5、§7.1、§8）
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/80-phase3-aggregate-realtime-glm.handoff.md`
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/90-phase3-review1-kimi.handoff.md`
- `backend/hedge_open_tasks/fee_fetcher.py`
- `backend/hedge_open_tasks/store.py`
- `backend/hedge_open_tasks/service.py`
- `backend/tests/test_hedge_store.py`
- `backend/tests/test_hedge_api.py`
- `backend/tests/test_hedge_service.py`
- `backend/tests/test_backfill_leg_fees.py`
- `backend/tests/test_hedge_purity.py`
- `frontend/index.html`
- `frontend/self-check.js`
- `git diff 06c00c07e0181c596292c2f163890456abed3d8d..3bc6acaec6e3bd2b837239d7a925007a29729db6`

## Acceptance Checks
1. **持仓真实聚合**：`aggregate_positions` 折 U 正确，不全时返回 None/None/True，均价严禁使用 avg_price。
2. **关仓全腿聚合**：`insert_close_log` 聚合开+平全部腿，全完整写 0，不全写 1。
3. **实时写入 commit-first**：终态事务先 commit，再发 1 次 GET，失败不影响成交终态。
4. **UM 零宽窗行为**：零宽/倒置窗正确向前回退 10 分钟。
5. **测试全绿与自检**：pytest 232 项通过，self-check 全过。
6. **实跑验证命令**：
   - `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_hedge_store.py backend/tests/test_hedge_api.py backend/tests/test_hedge_service.py backend/tests/test_backfill_leg_fees.py backend/tests/test_hedge_purity.py -q`
   - `node frontend/self-check.js`

## Handoff Target
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/100-phase3-review2-opus5.handoff.md`
