# Dispatch: pm-margin-repay-plan-review

## Identity

- task_id: `pm-margin-repay-plan-review`
- target_role: `Reviewer`
- target_model: `grok45`
- provider: `xai`
- status_revision: `1`
- required_skill: `agents/skills/reality-checker.md`

## Goal

对统一账户全仓杠杆还款 v1 的实现计划做独立、跨 provider、只读的上线前计划评审。
确认方案准确映射币安 `POST /papi/v1/margin/repay-debt`，以最小范围覆盖 Human 已决定的
“欠款资产卡手动还款、`0` 自动还所有、首版 USDT 跨资产偿还”目标，并在任何实现开始前
找出会导致重复还款、误导费用/扣款资产、结果不明时重发、错误开启实盘通道或无法验证的
计划缺口。

## Allowed Files

- 全仓库只读检查。
- 唯一写权限（create-only）：
  `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan-review.handoff.md`
- Bookkeeper 已执行前置检查：
  `test ! -e reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan-review.handoff.md`
  返回 `PASS`。若执行时该路径已存在，立即 `blocked`，不得覆盖。
- 禁止修改实现、计划、既有证据、`status.json`、`PROJECT_STATE.md`；禁止 commit、push、
  部署、启动服务或访问真实币安账户。

## Inputs

按顺序读取：

1. `AGENTS.md`（重点 §1、§3、§7、§8）
2. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/status.json`
3. `agents/roles.md` 的 Shared Rules、Task Handoff Evidence Contract、Reviewer 章节
4. `agents/skills/reality-checker.md`
5. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan.md`
6. `PROJECT_STATE.md`
7. `docs/api/public-market-contract.md` 中统一账户余额卡和资产划转契约
8. `backend/app/server.py` 的资产划转 handler/注入路径
9. `backend/asset_transfer/store.py`
10. `backend/services/hedge_open_live_client.py` 的 allowlist、签名 POST、资产划转方法
11. `frontend/index.html` 的还款预览和资产划转交互
12. 币安官方端点契约：
    <https://developers.binance.com/zh-CN/docs/catalog/advanced-trading-derivatives-trading-portfolio-margin/api/rest-api/trade#margin-account-repay>

创建 handoff 前必须遵守 `agents/roles.md` 的 Task Handoff Evidence Contract；Reviewer 只可
创建上面指定的唯一文件。

## Acceptance Checks

1. `pass/fail`：计划是否准确冻结 `asset`、可选 `amount`、`specifyRepayAssets`、同币资产
   优先、50,000 USD 上限、IP 权重 3000 和严格成功响应语义；不得把不公开的费用/滑点
   当成已知事实。
2. `pass/fail`：`0` 是否只在本地表示全部并保证外发省略 `amount`，正数是否保持十进制
   字符串且不经过 float；固定 USDT 是否无法由客户端覆盖。
3. `pass/fail`：默认关闭闸门、显式确认、SQLite 幂等、one-shot、四态、418/429 与歧义
   响应归 `unknown`、刷新恢复和人工核对解锁，是否足以防止重复还款与误判成功。
4. `pass/fail`：本地 POST/GET、快照借款资产白名单、页面持久化未决请求和成功后强制刷新
   的接缝是否自洽；指出任何会使用户刷新页面后重新还款或无法继续操作的明确路径。
5. `pass/fail`：T1/T2 的 owner、Allowed Files、先后顺序、测试 oracle 和 docs 同步义务是否
   完整且保持最小范围；不得为假设需求添加通用资金框架。
6. `pass/fail`：计划是否明确禁止实现/测试期间的真实币安调用，并把部署、开闸门、真实
   还款留给后续 Human 授权。
7. 生成符合 Task Handoff Evidence Contract 的唯一 handoff；Source Report 给出逐项结论、
   证据路径和必要修订。Human Brief 输出合规 `[TASK_RESULT v2]`，并附明确
   `评审结论: ACCEPT|REWORK`、`问题记录`、`修复要求`。

## Stop

只完成计划评审并创建指定 handoff 后停止。不得实现任何代码、改写计划、启动下一模型、
提交或推送。`ACCEPT` 仅允许 Bookkeeper 准备 T1 dispatch；不授权资金操作、合并、部署或
开启还款闸门。
