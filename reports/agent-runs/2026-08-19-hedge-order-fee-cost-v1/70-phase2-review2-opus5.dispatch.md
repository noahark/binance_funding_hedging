# 70-phase2-review2-opus5.dispatch.md

## Metadata
- task_id: `70-phase2-review2-opus5`
- stage_id: `2026-08-19-hedge-order-fee-cost-v1`
- stage_title: `成交手续费冻价成本 V1`
- stage_generation: `new-stage`
- phase: `phase2_review2`
- risk_class: `HIGH_RISK`
- target_model: `opus5`（Anthropic，工作窗 `claude-review`，pane `w1:pJ`）
- target_provider: `anthropic`
- role: `Reviewer`
- skill: `agents/skills/reality-checker.md`
- base_sha: `f510c562667312a0ebf8d531e4add3f95acbe7e1`
- delivery_sha: `831e255492628fded3720f9bcc68489256410788`

## Goal
依据 `AGENTS.md` §8 Review Rules 与 `agents/skills/reality-checker.md`，对阶段二（`50-phase2-backfill-glm`）历史数据回补脚本与公共成交拉取组件进行独立的 Review-2 终审（业务实际效果、契约符合性、实盘运行风险与发布就绪状态）：
1. 审查业务需求与实际效果符合性（10-design §2.2/§3/§4.3/§7.1 T3/§8）：
   - 断点 3 共享性：`fee_fetcher.py` 分组折算逻辑是否可无缝供后续 T5 实时下单链共用；
   - 断点 1 隔离性：回补是否绝对不改写已关闭历史 `close_log` 记录；
   - 截断保护：`limit=1000` 达到时是否绝对禁止对截断列表求和并判不全；
   - 合约分钟窗：`dispatched_at_us` / `last_query_at_us` 计算与 >7d fail-closed 是否合理；
   - 冻价真实性：回补采用公开 1m K 线收盘价，无签名且不进入签名白名单；
2. 审查实盘运行风险与熔断守卫：
   - 429/418 遇限速立即停止并落盘断点；
   - 检测到 running 对冲任务时拒绝启动；
   - 游标推进与已失败集合重跑不打；
   - `--dry-run` 模式绝对零网络零写入；
3. 审查测试与代码纯度：
   - `pytest backend/tests/test_backfill_leg_fees.py backend/tests/test_hedge_purity.py` 全绿；
   - money-zero 扫描无死角；
4. 核实本次交付与评审过程绝对未向实盘币安外发 live 回补请求（live 执行须待 Human 单独授权）；
5. 创建交接件 `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/70-phase2-review2-opus5.handoff.md`，并在控制台输出包含明确评审结论（`ACCEPT` 或 `REWORK`）的 `[TASK_RESULT v2]` 收口。

## Allowed Files (Reviewer Create-Only)
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/70-phase2-review2-opus5.handoff.md`（仅可创建此文件，禁止修改其他任何文件）

## Read-Only Inputs
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md`（§2.2、§3、§4.3、§7.1、§8）
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/50-phase2-backfill-glm.handoff.md`
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/60-phase2-review1-kimi.handoff.md`
- `backend/hedge_open_tasks/fee_fetcher.py`
- `scripts/backfill-leg-fees.py`
- `backend/tests/test_backfill_leg_fees.py`
- `backend/hedge_open_tasks/store.py`
- `backend/services/hedge_open_live_client.py`
- `backend/adapters/binance_public.py`
- `backend/tests/test_hedge_purity.py`
- `git diff f510c562667312a0ebf8d531e4add3f95acbe7e1..831e255492628fded3720f9bcc68489256410788`

## Acceptance Checks
1. **需求符合性与边界保护**：ALLOWLIST 三条 GET 签名隔离，公开 K 线无签名；UM 分钟窗与截断不全判别合规；回补不碰 `close_log`。
2. **熔断与幂等安全**：429/418 立即停并落盘，running 任务拒绝，已写入/已失败不重复打。
3. **测试与纯度覆盖**：pytest 68 passed，money-zero 扫描全绿。
4. **实跑验证命令**：
   - `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_backfill_leg_fees.py backend/tests/test_hedge_purity.py -q`
   - `python3 scripts/backfill-leg-fees.py --dry-run`
5. **安全红线**：受审交付物未执行任何 live 回补。

## Handoff Target
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/70-phase2-review2-opus5.handoff.md`
