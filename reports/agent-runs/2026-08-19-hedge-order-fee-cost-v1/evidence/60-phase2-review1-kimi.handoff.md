# Task Handoff: 60-phase2-review1-kimi

## Source Report (author-only; immutable after task end)

- task_id: `60-phase2-review1-kimi`
- role: `Reviewer`
- target model: `kimi`（Moonshot，工作窗 `kimi-review`）
- stage_id: `2026-08-19-hedge-order-fee-cost-v1`
- created_at: 2026-08-20 12:03:01 CST
- base_sha: `f510c562667312a0ebf8d531e4add3f95acbe7e1`
- delivery_sha: `831e255492628fded3720f9bcc68489256410788`

### 任务背景与只读评审范围

阶段二（T3）由 `claude_glm`（zhipu_glm）实现；本次 Review-1 由 `kimi`（moonshot）跨 provider 执行，审查交付区间 `f510c562..831e255` 内的代码与测试：

- `backend/hedge_open_tasks/fee_fetcher.py`（新建）：分组折算、UM 分钟窗、limit=1000 截断禁求和、BNB 冻价、BackfillEngine 断点/节流/running 保护；
- `scripts/backfill-leg-fees.py`（新建）：独立回补 CLI，`--dry-run` 零网络零写入，缺凭证/离线拒绝，429/418 立停落盘；
- `backend/services/hedge_open_live_client.py`：ALLOWLIST 与三个签名 GET 方法（spot/margin/um 成交明细）；
- `backend/adapters/binance_public.py`：公开 `GET /api/v3/klines` 1m close，无签名、不进白名单；
- `backend/hedge_open_tasks/store.py`：`update_leg_fees` 幂等守卫 + `list_legs_missing_fees` 选择器；
- `backend/tests/test_backfill_leg_fees.py`（新建）与 `backend/tests/test_hedge_purity.py`：离线单测与 money-zero 扫描。

### 评审结论

`ACCEPT`。

未发现阻塞交付的 in-range 缺陷。交付代码与 10-design §2.2/§4.1/§4.3/§8 口径一致；验收命令全部通过；money-zero 扫描纳入回补脚本且全绿；评审过程中未执行任何带网络外发的 live 回补。

### 命令与结果

1. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_backfill_leg_fees.py backend/tests/test_hedge_purity.py -q`
   → **68 passed**。
2. `python3 scripts/backfill-leg-fees.py --dry-run`
   → `[dry-run] 候选腿 269 条：...；游标 0（不推进、不写断点）`，exit 0。
3. `git diff --stat f510c562..831e255`
   → 9 files changed, 1486 insertions(+), 5 deletions(-)。

### 观察与建议（非阻塞）

- `fee_fetcher.fetch_leg_fees` 仅捕获 `FeeFetchError`；建议 T5 注入 transport 时严格遵循「非 RateLimited 失败统一抛 `FeeFetchError`」契约，避免未折叠异常导致下单链崩溃。当前脚本 `build_transport` 已满足该契约。
- `scripts/backfill-leg-fees.py --dry-run` 默认读取 `data/hedge-open-tasks.sqlite3` 并构造 Store（可能触发幂等迁移），已在意图内，但 live 首跑仍建议 `--limit 5` 小批试跑。

### 未完成事项

- T5 实时写入路径需复用 `fetch_leg_fees`（断点 3）。
- UM `orderId` 支持性须经一次 Human 授权的只读 live 确认；当前按 B1a「无 orderId」分支实现。
- 对实盘库执行带网络外发的 live 回补须 Human 单独授权。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/60-phase2-review1-kimi.handoff.md`
  2. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/status.json`
- 执行：Bookkeeper 核验 Review-1 结论与验收命令输出，按 §8 准备 Review-2（默认 `opus5`）。
- 关卡：Human 启动 Review-2 窗口；live 回补与合并/部署另需单独授权。
- 不能假设的事实：T5 尚未实现；UM orderId 分支未经验证；>7d 窗与全零佣金按设计 fail-closed。

## Human Brief / Console Receipt Source

[TASK_RESULT v2]
任务 ID: 60-phase2-review1-kimi
执行结果: completed（完成）
评审结论: ACCEPT（接受）
问题记录: none
修复要求: none
结果摘要: 阶段二 T3 交付 Review-1 通过。ALLOWLIST 三条成交明细 GET 与公开 K 线隔离正确；UM 分钟窗、limit=1000 截断禁求和、断点幂等、429/418 立停、running 保护、dry-run 零网络零写入、close_log 不改写均符合 10-design；指定 pytest 68 passed，dry-run 列出 269 候选腿并 exit 0。
产物: [reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/60-phase2-review1-kimi.handoff.md]
检查结果: [验收1 ALLOWLIST 三 GET + K 线公开无签名 pass；验收2 UM 分钟窗与截断守卫 pass；验收3 断点/幂等/限速熔断/运行中保护 pass；验收4 close_log 原样保护 pass；验收5 pytest 68 passed + money-zero 扫描绿 pass；验收6 实跑 dry-run 零网络零写入 exit 0 pass]
阻塞项: [none]
本地北京时间: 2026-08-20 12:03:01 CST
下一步模型: gemini-3.7-flash（Bookkeeper，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/60-phase2-review1-kimi.handoff.md；执行：核验 Review-1 结论与验收输出并按 §8 准备 Review-2；关卡：Human 启动 Review-2 窗口
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- **verification_time**: 2026-08-20 12:06:50 CST
- **source_sha256**: `c00a387b1685f12c1ece14f8ba9cc5481ddb396166944f70a9d6fd74d94d2453`
- **status_revision**: 15 -> 16
- **verdict**: `ACCEPT`
- **rework_count**: 0
- **isolation_check**: pass（implementer=`zhipu_glm`, reviewer=`moonshot`, cross-provider isolation satisfied）
- **verification_status**: `verified`

## Errata (append-only)
