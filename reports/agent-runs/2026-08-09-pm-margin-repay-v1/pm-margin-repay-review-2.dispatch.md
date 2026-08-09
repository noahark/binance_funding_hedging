# Dispatch: pm-margin-repay-review-2

## Identity

- task_id: `pm-margin-repay-review-2`
- target_role: `Reviewer`
- target_model: `opus5`
- provider: `anthropic`
- status_revision: `6`
- required_skill: `agents/skills/reality-checker.md`

## Goal

对统一账户全仓杠杆手动还款 v1 做独立 HIGH_RISK review-2（现实核验/发布就绪评审）。以固定
产品交付
`ee0d5320b319a5bacc708eb8680e8156328db338..5a81bdc1c40238053a07736faa64b34cab294987`
为正式代码范围，判断 Human 批准的实际需求是否达成、证据是否可信、两笔真实还款与实现是否
一致、剩余运营风险是否已诚实暴露，以及是否可进入最终 Human 决策。

review-1 已在 Human 修订验收要求后明确 `ACCEPT` 并经 Bookkeeper 核验。Human 已撤销“必须
提交 `_build_margin_repay_client` 组合矩阵测试”的要求；不得仅因缺少该测试阻塞，也不得
换名重提。此勘误不预设 review-2 verdict，Reviewer 仍应对当前交付的实际资金安全、证据和
发布就绪性独立判断。

Human 已在双评审完成前手动部署、开启 `APP_MARGIN_REPAY_ENABLED`，并完成 XLM 指定数量与
INJ 全部还款两笔真实验证。该事实属于 review-2 的现实证据和运营边界，不是新增实盘授权。

## Allowed Files

- 全仓库只读检查；产品评审范围固定为上述 `base_sha..delivery_sha`。后续 stage 控制提交、
  handoff、`PROJECT_STATE.md` 和本地审计库只作证据与上下文，不改变产品交付 SHA。
- 可只读查询 `data/margin-repay.sqlite3`；必须使用 `sqlite3 -readonly`，仅查询
  `margin_repay` 表，不得修改、迁移、复制、清理或写入任何运行数据。
- 唯一写权限（create-only）：
  `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-review-2.handoff.md`
- Bookkeeper 前置检查：
  `test ! -e reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-review-2.handoff.md`
  → `PASS`。若执行时该路径已存在，立即 `blocked`，不得覆盖。
- 禁止修改代码、测试、文档、计划、既有 handoff、数据库、`status.json`、`PROJECT_STATE.md`；
  禁止读取 `.env`/进程环境/凭证，禁止访问币安或本地 HTTP 服务，禁止 commit、push、merge、
  部署、重启、开关闸门、发送还款/划转/订单或启动任何下一模型。

## Inputs

按顺序读取，不扫描 completed stages 或 history：

1. `AGENTS.md`（重点 §1、§3、§7、§8、§9、§10）
2. 本 dispatch
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`（当前运行事实、XLM/INJ 证据、INJ 数量缺失和既有 Live Risks）
5. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/status.json`
6. `agents/roles.md` 的 Shared Rules、Task Handoff Evidence Contract、Reviewer 章节
7. `agents/skills/reality-checker.md`
8. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan.md`
9. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan-review.handoff.md`
10. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-backend-implement.handoff.md`
11. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-frontend-implement.handoff.md`
12. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-review-1.handoff.md`
    （重点 Human acceptance correction 与 Bookkeeper Verification）
13. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-review-1-rerun.handoff.md`
    （明确 `ACCEPT` 与 Bookkeeper Verification）
14. 固定差异：
    `git diff --no-ext-diff ee0d5320b319a5bacc708eb8680e8156328db338..5a81bdc1c40238053a07736faa64b34cab294987`
15. 固定差异涉及的后端、前端、测试和 `docs/api/public-market-contract.md`
16. 本地审计库只读证据：

```text
sqlite3 -readonly -header -column data/margin-repay.sqlite3 \
  "SELECT client_request_id,asset,amount,repay_asset,status,repaid_amount,update_time,error_code,error_message FROM margin_repay WHERE client_request_id IN ('d9b43914-11cf-4652-9c84-ca1ccc8d4839','96e54716-4711-43c7-a9ce-88c32ad3fef1') ORDER BY created_at_us;"
```

17. 币安官方契约：
    <https://developers.binance.com/zh-CN/docs/catalog/advanced-trading-derivatives-trading-portfolio-margin/api/rest-api/trade#margin-account-repay-debt>

## Acceptance Checks

1. **需求与实际效果**：确认交付只实现借款资产卡上的 Human 手动还款；`"0"` 表示全部、
   正十进制表示指定负债数量、指定后备偿还资产固定 USDT 且同币优先。不得存在自动/定时
   还款、可编辑偿还资产、`/repayLoan` 或交付外资金功能。
2. **真实资金安全**：确认后才生成请求号，POST 前本地持久化，SQLite 主键幂等、one-shot
   不重试；HTTP/业务四态和 unknown/pending 锁不得把结果不明诱导成第二笔还款。判断实际
   使用中刷新、重载、网络丢响应和连续点击是否有重复还款风险。
3. **真实证据闭环**：核对本地只读审计中 XLM 请求 5/成功/实际 5，以及 INJ 请求 0/成功/
   `repaid_amount=null` 均各只有一笔且无错误；结合已记录刷新后 INJ 负债为 0 的证据判断
   “全部还款成功”是否有足够依据。不得把 INJ 精确还款数量或实际扣款币种编造出来。
4. **币安契约与诚实性**：核对固定 host/path、权重 3000、50,000 USD 上限由交易所终判、
   同币优先、USDT 后备以及费用/价格/滑点未披露的页面与文档表达。真实响应缺少 `amount`
   时，成功判定、数据库、页面和公共契约必须保持诚实。
5. **运营与发布边界**：明确记录代码在双评审前已被 Human 部署并开闸、目前没有“自动还款”
   行为；评估当前闸门可能仍开启、SQLite 本地审计、请求权重和人工核对流程对正式使用的
   实际影响。Reviewer 只给发布就绪结论，不得自行关闭闸门或做任何运行操作。
6. **证据完整性与回归**：核对两次 review-1、T1/T2 handoff、固定 SHA、产品文件自 delivery
   后未变。至少运行并记录：

```text
git diff --check ee0d5320b319a5bacc708eb8680e8156328db338..5a81bdc1c40238053a07736faa64b34cab294987
git diff --exit-code 5a81bdc1c40238053a07736faa64b34cab294987 -- backend/app/server.py backend/config.py backend/margin_repay backend/services/hedge_open_live_client.py backend/tests/test_config.py backend/tests/test_frontend_field_binding.py backend/tests/test_hedge_open_live_client.py backend/tests/test_hedge_purity.py backend/tests/test_margin_repay.py docs/api/public-market-contract.md frontend/index.html frontend/self-check.js
node frontend/self-check.js
python3 -m pytest -q backend/tests/test_config.py backend/tests/test_hedge_open_live_client.py backend/tests/test_margin_repay.py backend/tests/test_asset_transfer.py backend/tests/test_service_health.py backend/tests/test_frontend_field_binding.py
python3 -m pytest -q backend/tests
```

7. **发现分类和 Human 决策**：任何 `REWORK` 必须满足 `AGENTS.md` §1/§8，给出当前证据、
   实际发布影响、范围分类与最小修复；不得以 Human 已撤销的组合测试要求阻塞。若仅剩已知
   运营限制，应清楚解释实际影响、临时操作边界和最终 Human 选择，而不是制造新需求。
8. **结论与 handoff**：创建合规 handoff，给出明确 `ACCEPT` 或 `REWORK`。`ACCEPT` 仅表示
   可进入最终 Human 决策，不授权合并、push、部署、闸门变更或任何新增实盘；`REWORK` 必须
   提供可执行修复要求。

## Stop

只完成固定范围 review-2 并创建指定 handoff 后停止。不得修代码、改文档、触碰运行状态、
启动 Bookkeeper 或替 Human 作最终业务接受。由 Human 启动本任务；结果返回 Bookkeeper 核验。
