# 80-phase3-aggregate-realtime-glm.dispatch.md

## Metadata
- task_id: `80-phase3-aggregate-realtime-glm`
- stage_id: `2026-08-19-hedge-order-fee-cost-v1`
- stage_title: `成交手续费冻价成本 V1`
- stage_generation: `new-stage`
- phase: `phase3_implementation`
- risk_class: `HIGH_RISK`
- target_model: `claude_glm`（GLM / 智谱，工作窗 `claude-glm`，pane `w1:p8`）
- target_provider: `zhipu_glm`
- role: `Implementer`
- skill: `agents/skills/senior-developer.md`
- discipline: `agents/developer-discipline.md`
- base_sha: `06c00c07e0181c596292c2f163890456abed3d8d`
- delivery_sha: `TBD`

## Goal
依据 `10-design.md`（§3 D1–D11、§4.1 实时写入、§5 展示聚合、§7.1 T2后半+T4+T5、§8 验收），实现阶段三**读链路真实聚合与开平仓实时手续费写入**：

### 1. 后端读链路真实聚合（`store.py`）：
- **持仓表聚合（`aggregate_positions`）**：
  - 遍历未平仓周期，仅汇总该周期 `task_type=open` 且有成交的腿（§5.1）；
  - 折算逻辑：`Σ(fee_bnb_qty × fee_bnb_price)` + `Σ(USDT 的 fee_other_qty)` + `Σ(本币可定价 fee_other_qty × 该腿均价)`；
  - 该腿均价计算：`cumulative_quote_amt ÷ cumulative_base_qty`，**严禁使用 `hedge_open_leg.avg_price`**；
  - 缺失守卫（D10/D11）：任一参与开仓腿缺必需构成量（四列全空、缺 BNB 价格、第三种不可折算资产）→ `trading_fee_incomplete=True`，且 `trading_fee_usdt=None`、`fee_bnb_qty=None`（严禁输出半截金额或半截 BNB 数量）；只有全腿完整时才输出折 U 字符串与 BNB 数量。
- **历史结算聚合（`insert_close_log`）**：
  - 平仓关仓插入 `close_log` 时，聚合该周期全部 open + close 腿；
  - 全部腿完整时写真实 `trading_fee_usdt`、`fee_bnb_qty`，且 `trading_fee_incomplete=0`；任一腿不全时金额与数量写 NULL、`trading_fee_incomplete=1`。

### 2. 实时开单/平仓成交写入（T5，`store.py` / `service.py`）：
- 复用阶段二已验证的 `fee_fetcher.py`（断点 3，严禁另写一套）；
- **两个写入站点**：
  1. `store.py` 的 inline `resolve_attempt` 终态提交之后；
  2. `service.py` 的 background drain `resolve_leg_from_query` 终态提交之后；
- **执行规则（§4.1）**：
  - 先 commit 终态事务，再发至多 1 次成交历史 GET；
  - 实时 BNB 冻价（D4）：进程内 `price_map["BNBUSDT"]`（max_age ≤ 300s）→ 缺则公开拉一次现价 → 仍缺则价格留空、数量仍记；
  - 失败不重试、不进 drain 循环、不阻碍腿终态、任何异常仅记录日志；
  - 符号对应：现货/杠杆腿用 `task.spot_symbol`，合约腿用 `task.coin`；
  - 权重与上限：每腿至多 1 次 GET；平滑任务 20 对腿最坏 ≤ 40 次。

### 3. 前端与测试验证：
- 确认前端 `index.html` 与 `self-check.js` 在真数据下完全正常运行；
- 编写全面的单元测试与回归测试，涵盖完整 BNB、完整 USDT、混合、不全回退、实时 commit-first、失败非阻塞等场景；
- 确保 `test_hedge_purity.py` money-zero 扫描全绿；
- 创建交接件 `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/80-phase3-aggregate-realtime-glm.handoff.md`。

## Assigned Files (Modifiable)
- `backend/hedge_open_tasks/store.py`
- `backend/hedge_open_tasks/service.py`
- `backend/hedge_open_tasks/fee_fetcher.py`
- `frontend/index.html`（若需排版微调）
- `frontend/self-check.js`
- `backend/tests/test_hedge_store.py`
- `backend/tests/test_hedge_api.py`
- `backend/tests/test_hedge_service.py`
- `backend/tests/test_backfill_leg_fees.py`
- `backend/tests/test_hedge_purity.py`
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/80-phase3-aggregate-realtime-glm.handoff.md`

## Read-Only References
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md`（§3、§4.1、§5、§7.1、§8）
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/50-phase2-backfill-glm.handoff.md`
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/70-phase2-review2-opus5.handoff.md`
- `backend/services/hedge_open_live_client.py`
- `backend/adapters/binance_public.py`

## Forbidden Files
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/status.json`

## Acceptance Checks
1. **持仓真实聚合**：`aggregate_positions` 对回补及新成交腿正确计算折 U 与 BNB 数量；不全时 `trading_fee_usdt` 与 `fee_bnb_qty` 均为 None，`trading_fee_incomplete=True`。
2. **均价不用 avg_price**：本币折 U 严格使用 `cumulative_quote_amt / cumulative_base_qty`。
3. **历史关仓聚合**：新关仓 `insert_close_log` 聚合开+平全部腿；完整写 0，不全写 1。
4. **实时双站点 commit-first**：`resolve_attempt` 与 `resolve_leg_from_query` 在终态 commit 之后才发手续费 GET，失败不影响腿终态，单腿至多 1 次。
5. **D4 现价冻结**：实时写入使用进程内 `price_map`（≤300s）或公开现价。
6. **自动化测试**：
   - `pytest backend/tests/test_hedge_store.py backend/tests/test_hedge_api.py backend/tests/test_hedge_service.py backend/tests/test_backfill_leg_fees.py backend/tests/test_hedge_purity.py` 全部通过。
   - `node frontend/self-check.js` 全部通过。

## Handoff Target
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/80-phase3-aggregate-realtime-glm.handoff.md`
