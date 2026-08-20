# 60-phase2-review1-kimi.dispatch.md

## Metadata
- task_id: `60-phase2-review1-kimi`
- stage_id: `2026-08-19-hedge-order-fee-cost-v1`
- stage_title: `成交手续费冻价成本 V1`
- stage_generation: `new-stage`
- phase: `phase2_review1`
- risk_class: `HIGH_RISK`
- target_model: `kimi`（Moonshot，工作窗 `kimi-review`，pane `w1:pM`）
- target_provider: `moonshot`
- role: `Reviewer`
- skill: `agents/skills/code-reviewer.md`
- base_sha: `f510c562667312a0ebf8d531e4add3f95acbe7e1`
- delivery_sha: `831e255492628fded3720f9bcc68489256410788`

## Goal
只读评审阶段二（`50-phase2-backfill-glm`）历史回补脚本与公共成交拉取组件的交付代码与测试：
1. 审查 `backend/hedge_open_tasks/fee_fetcher.py`：
   - 分组逻辑：BNB、恰一种 ∈{USDT, base}、多种或第三种资产标不全；
   - 合约分钟级时间窗构造（`dispatched_at_us` 与 `last_query_at_us`，缺列回退 ±10min，>7d clamp 并判不全）；
   - `limit=1000` 截断检查：达到 limit 判不全禁止对截断列表求和；
   - UM 本地 `orderId` 过滤：滤空视为未知；
   - `BackfillEngine` 游标推进、已写入跳过、已失败重跑不重复打、429/418 立即停并落盘断点、running 对冲任务拒绝启动；
2. 审查 `scripts/backfill-leg-fees.py`：
   - `--dry-run` 模式零网络零写入断点；
   - 绝不改写 `close_log` 旧行；
   - 缺凭证/offline 模式安全拒绝启动；
3. 审查 `backend/services/hedge_open_live_client.py` 与 `backend/adapters/binance_public.py`：
   - 签名白名单与方法实现（3 条成交明细 GET）；
   - 公开 1m K 线拉取无签名、不进签名白名单；
4. 审查 `backend/tests/test_backfill_leg_fees.py` 与 `backend/tests/test_hedge_purity.py`：
   - 单测覆盖率与 money-zero 纯度守卫；
5. 核实受审范围内未对实盘环境执行带网络外发的 live 回补；
6. 创建交接件 `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/60-phase2-review1-kimi.handoff.md`，并在控制台给出明确的评审结论（`ACCEPT` 或 `REWORK`）。

## Allowed Files (Reviewer Create-Only)
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/60-phase2-review1-kimi.handoff.md`（仅可创建此文件，禁止修改其他任何文件）

## Read-Only Inputs
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md`（§2.2、§3、§4.3、§7.1 T3、§8）
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/50-phase2-backfill-glm.handoff.md`
- `backend/hedge_open_tasks/fee_fetcher.py`
- `scripts/backfill-leg-fees.py`
- `backend/tests/test_backfill_leg_fees.py`
- `backend/hedge_open_tasks/store.py`
- `backend/services/hedge_open_live_client.py`
- `backend/adapters/binance_public.py`
- `backend/tests/test_hedge_purity.py`
- `git diff f510c562667312a0ebf8d531e4add3f95acbe7e1..831e255492628fded3720f9bcc68489256410788`

## Forbidden Actions
- 禁止修改任何交付代码或已有证据文件；
- 禁止执行带网络外发的 live 回补或下单命令。

## Acceptance Checks
1. **ALLOWLIST 完整性与签名隔离**：3 条 GET 签名端点正确登记，公开 1m K 线拉取无签名。
2. **UM 分钟窗与截断守卫**：分钟窗计算正确，limit=1000 截断禁止求和。
3. **断点幂等与控速熔断**：游标推进正常，已写入跳过，429/418 立即停并落盘。
4. **close_log 保护**：回补逻辑绝不改写 `close_log`。
5. **单测与纯度**：pytest 全部通过，money-zero 扫描无漏洞。
6. **实跑验证命令**：
   - `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_backfill_leg_fees.py backend/tests/test_hedge_purity.py -q`
   - `python3 scripts/backfill-leg-fees.py --dry-run --db <tmp_db> --progress <tmp_progress>`

## Handoff Target
- `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/60-phase2-review1-kimi.handoff.md`
