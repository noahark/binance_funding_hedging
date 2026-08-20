# 50-phase2-backfill-glm.dispatch.md

## Metadata
- task_id: `50-phase2-backfill-glm`
- stage_id: `2026-08-19-hedge-order-fee-cost-v1`
- stage_title: `成交手续费冻价成本 V1`
- stage_generation: `new-stage`
- phase: `phase2_backfill`
- risk_class: `HIGH_RISK`
- target_model: `claude_glm`（GLM 4.5 / 智谱，工作窗 `claude-glm`，pane `w1:p8`）
- target_provider: `zhipu_glm`
- role: `Implementer`
- skill: `agents/skills/backend-implementer.md`
- discipline: `agents/developer-discipline.md`
- base_sha: `f510c562667312a0ebf8d531e4add3f95acbe7e1`
- delivery_sha: `TBD`

## Goal
依据 `10-design.md`（§2.2、§3、§4.3、§7.1 T3、§8），实现阶段二**历史数据回补脚本与成交拉取公共组件**：
1. **公共成交拉取与折算逻辑**：编写可供回补脚本（T3）与后续下单链（T5）共用的成交拉取与 4 列折算模块（断点 3），禁止脚本与下单链各写一套；
2. **公开 BNB 1m K 线拉取**：在 `binance_public.py` 上增加无签名的 1m K 线收盘价获取方法（用于回补时拉取成交时刻真实历史 BNB 价格冻价）；
3. **独立回补脚本 `scripts/backfill-leg-fees.py`**：
   - 范围：本地 `hedge_open_leg` 中 `exchange_status=FILLED`、`order_id` 非空、四列全空的腿；开仓腿和平仓腿均补；
   - 游标与断点：按 `hedge_open_leg.id` 升序推进，持久化游标与已失败集合（已写入跳过、已失败重跑不重复打）；
   - 控速与防爆：签名 GET ≤ 1 次/秒；遇 429/418 立刻停止并保存断点；有 running 对冲任务时拒绝启动或自动降速；
   - 绝不改写 `close_log` 旧行（断点 1）；
   - 纯离线可测：提供 `--dry-run` 模式，且核心拉取与计算有完整的单元测试；
4. **安全与纯度**：更新 `test_hedge_purity.py` 的 `_MONEY_ZERO_SCOPE`，确保包含 `scripts/backfill-leg-fees.py`；编写完整的单测覆盖纯 BNB、纯 USDT、BNB+USDT、本币折算、第三种资产、合约分钟窗、limit=1000 截断不全等全部场景。

## Assigned Files (Modifiable)
- `backend/hedge_open_tasks/store.py`（若需增加 update_leg_fees 等辅助写入方法）
- `backend/hedge_open_tasks/fee_fetcher.py`（或 `backend/services/` 下的共享成交拉取与手续费计算模块）
- `backend/services/hedge_open_live_client.py`（在 ALLOWLIST 增加 3 条成交明细只读 GET）
- `backend/adapters/binance_public.py`（增加公开 1m K 线获取方法）
- `scripts/backfill-leg-fees.py`（新建独立回补脚本）
- `backend/tests/test_hedge_purity.py`（更新 `_MONEY_ZERO_SCOPE`）
- `backend/tests/test_backfill_leg_fees.py`（新建回补与成交拉取测试）
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/50-phase2-backfill-glm.handoff.md`（新建交接件）

## Read-Only References
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md`（重点看 §2.2 接口限制与合约分钟窗、§3 决策、§4.3 回补规范、§7.1 断点、§8 验收）
- `backend/hedge_open_tasks/store.py`
- `backend/hedge_open_tasks/service.py`
- `backend/services/hedge_open_live_client.py`
- `backend/adapters/binance_public.py`
- `backend/tests/test_hedge_purity.py`

## Forbidden Files
- `frontend/*`
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/status.json`

## Acceptance Checks
1. **ALLOWLIST 完整性**：`hedge_open_live_client.ALLOWLIST` 包含：
   - `("GET", "/api/v3/myTrades")`
   - `("GET", "/papi/v1/margin/myTrades")`
   - `("GET", "/papi/v1/um/userTrades")`
2. **K 线公开无签名**：`BNBUSDT` 1m K 线拉取挂在 `binance_public.py`，绝不进入签名客户端。
3. **合约窗口与截断安全**：合约腿按 `dispatched_at_us` 与 `last_query_at_us` 构造分钟级窗口，`limit=1000`；若返回 1000 条判为截断不全，禁止对截断列表求和。
4. **回补断点与幂等**：已写入腿跳过，已尝试失败腿重跑不再打，游标正常推进，不改写 `close_log`。
5. **控速与保护**：遇 429/418 立即停止并落盘游标；检测到 running 对冲任务拒绝启动。
6. **money-zero 纯度守卫**：`test_hedge_purity.py` 扫描包含 `scripts/backfill-leg-fees.py` 并全绿。
7. **自动化测试**：`pytest backend/tests/test_backfill_leg_fees.py backend/tests/test_hedge_purity.py` 全部通过。
8. **安全红线**：本任务仅交付脚本与单测，**绝不直接在实盘数据库执行带网络外发的 live 回补**；live 执行须待 Review 验收后由 Human 单独授权。

## Handoff Target
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/50-phase2-backfill-glm.handoff.md`
