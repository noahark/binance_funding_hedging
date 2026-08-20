# 90-phase3-review1-kimi.dispatch.md

## Metadata
- task_id: `90-phase3-review1-kimi`
- stage_id: `2026-08-19-hedge-order-fee-cost-v1`
- stage_title: `成交手续费冻价成本 V1`
- stage_generation: `new-stage`
- phase: `phase3_review1`
- risk_class: `HIGH_RISK`
- target_model: `kimi`（Moonshot，工作窗 `kimi-review`，pane `w1:pM`）
- target_provider: `moonshot`
- role: `Reviewer`
- skill: `agents/skills/code-reviewer.md`
- base_sha: `06c00c07e0181c596292c2f163890456abed3d8d`
- delivery_sha: `3bc6acaec6e3bd2b837239d7a925007a29729db6`

## Goal
只读评审阶段三终章（`80-phase3-aggregate-realtime-glm`）读链路真实聚合与实时开平仓手续费写入的交付代码与测试：
1. 审查读链路真实聚合（`store.py`）：
   - `aggregate_positions`：持仓表只汇总 `task_type=open` 且有成交的腿；本币折 U 均价采用 `cumulative_quote_amt / cumulative_base_qty`，严禁使用 `avg_price`；任一开仓腿不全时 `trading_fee_usdt` 与 `fee_bnb_qty` 返回 None，`trading_fee_incomplete=True`；
   - `insert_close_log`：未显式传参时现算开+平全部腿折 U；全部完整时写入 0，任一不全时金额与数量写 NULL、`trading_fee_incomplete=1`；显式传参原样落库；
2. 审查实时写入钩子（`service.py` / `fee_fetcher.py`）：
   - 三处终态接线（inline 主终态、inline 暂停终态、drain 终态）在 commit 之后发至多 1 次 GET；
   - 失败不重试、不阻碍腿终态、只记任务卡日志；
   - D4 实时现价冻结复用预检价格链（≤300s 缓存 → 公开现价 → None）；
   - UM 零宽窗修正（`end <= start` 向前扩 10 分钟回退窗）；
3. 审查测试完整性与前端契约：
   - `pytest backend/tests/test_hedge_store.py backend/tests/test_hedge_api.py backend/tests/test_hedge_service.py backend/tests/test_backfill_leg_fees.py backend/tests/test_hedge_purity.py`（232 passed）；
   - `node frontend/self-check.js` 全绿；
4. 创建交接件 `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/90-phase3-review1-kimi.handoff.md`，并在控制台输出包含明确结论（`ACCEPT` 或 `REWORK`）的 `[TASK_RESULT v2]` 收口。

## Allowed Files (Reviewer Create-Only)
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/90-phase3-review1-kimi.handoff.md`（仅可创建此文件，禁止修改其他任何文件）

## Read-Only Inputs
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md`（§3、§4.1、§5、§7.1、§8）
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/80-phase3-aggregate-realtime-glm.handoff.md`
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
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/90-phase3-review1-kimi.handoff.md`
