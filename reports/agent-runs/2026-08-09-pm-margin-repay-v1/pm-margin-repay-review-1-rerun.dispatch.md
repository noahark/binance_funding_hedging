# Dispatch: pm-margin-repay-review-1-rerun

## Identity

- task_id: `pm-margin-repay-review-1-rerun`
- target_role: `Reviewer`
- target_model: `codex`
- provider: `openai`
- status_revision: `5`
- required_skill: `agents/skills/code-reviewer.md`

## Goal

在 Human 2026-08-10 修订验收要求后，对统一账户全仓杠杆还款 v1 的固定完整交付
`ee0d5320b319a5bacc708eb8680e8156328db338..5a81bdc1c40238053a07736faa64b34cab294987`
重新执行独立 HIGH_RISK review-1。

Human 已明确撤销“必须提交 `_build_margin_repay_client` 组合根闸门参数化测试”的要求，接受
当前源码、既有测试和前次 Reviewer 的只读组合 probe 作为该配置设计的足够证据；不得仅因
缺少该测试再次 `REWORK`。这不是预设本轮 verdict：Reviewer 仍独立检查其余资金出口、幂等、
四态、前后端接缝、真实响应差异和固定交付范围，并给出明确 `ACCEPT` 或 `REWORK`。

Human 已在双评审前手动部署、开闸并成功完成 XLM 指定数量及 INJ 全部还款。Reviewer 只读
核对证据，不得启动/重启服务、读取凭证、访问币安、发送请求、改闸门或进行任何资金操作。

## Allowed Files

- 全仓库只读检查；唯一正式产品差异是上述固定 `base_sha..delivery_sha`。
- 唯一写权限（create-only）：
  `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-review-1-rerun.handoff.md`
- Bookkeeper 前置检查：
  `test ! -e reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-review-1-rerun.handoff.md`
  → `PASS`。若执行时路径已存在，立即 `blocked`，不得覆盖。
- 禁止修改代码、测试、文档、计划、既有 handoff、`status.json`、`PROJECT_STATE.md`；禁止
  commit、push、merge、部署、重启、开关闸门、实盘或启动 review-2。

## Inputs

按顺序读取，不扫描历史 stage：

1. `AGENTS.md`（重点 §1、§3、§7、§8）
2. 本 dispatch
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`（含 2026-08-10 两笔实盘事实与 INJ `repaid_amount=null`）
5. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/status.json`
6. `agents/roles.md` 的 Shared Rules、Task Handoff Evidence Contract、Reviewer 章节
7. `agents/skills/code-reviewer.md`
8. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-review-1.handoff.md`
   （必须读取末尾 Human acceptance correction 与 Bookkeeper Verification）
9. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan.md`
10. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan-review.handoff.md`
11. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-backend-implement.handoff.md`
12. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-frontend-implement.handoff.md`
13. 固定差异：
    `git diff --no-ext-diff ee0d5320b319a5bacc708eb8680e8156328db338..5a81bdc1c40238053a07736faa64b34cab294987`
14. 交付代码、测试与 `docs/api/public-market-contract.md`（按固定差异所列文件）
15. 币安官方契约：
    <https://developers.binance.com/zh-CN/docs/catalog/advanced-trading-derivatives-trading-portfolio-margin/api/rest-api/trade#margin-account-repay-debt>

区间内 stage 控制文件仅作上下文。创建 handoff 前遵守 Task Handoff Evidence Contract。

## Acceptance Checks

1. **固定资金出口与金额语义**：仅 one-shot
   `POST https://papi.binance.com/papi/v1/margin/repay-debt`，固定 USDT；精确 `"0"` 省略
   上游 `amount`，正十进制原样透传；无 `/repayLoan`、float、自动重试或可注入 host/path。
2. **当前闸门行为（Human 修订口径）**：源码应保持显式还款开关、非离线、双凭证才注入，
   且独立于 `APP_HEDGE_EXECUTOR`。可核对当前代码、已有配置/503 测试和前次只读 probe；
   **不要求**新增或存在 `_build_margin_repay_client` 组合矩阵提交级测试，缺少该测试本身不得
   阻塞。除非有当前行为错误的可执行证据，不得围绕 Human 已拒绝的配置设计扩展场景。
3. **幂等与结果不明安全**：SQLite 先 pending、请求号唯一、锁外 one-shot；同 UUID 不重发；
   严格成功/failed/unknown/pending 分类与前端锁定不得诱导重复还款。
4. **前后端接缝**：二次确认、POST 前 localStorage、恰四字段、全局防连点、同号 GET 恢复、
   成功刷新后解锁以及 failed/unknown/pending 行为与公共契约一致。
5. **实盘事实与诚实展示**：XLM 指定 5 的本地审计为 `succeeded/repaid_amount=5`；INJ
   `amount="0"` 为单一成功请求，刷新后 `cross_margin_borrowed="0.0"`，但
   `repaid_amount=null`。核对当前契约“实际数量字段存在时展示”和成功判定是否诚实；不得把
   `repay_asset=USDT` 宣称为实际只扣 USDT，也不得把缺失实际数量编造成精确值。
6. **现有回归证据**：至少运行并记录：

```text
git diff --check ee0d5320b319a5bacc708eb8680e8156328db338..5a81bdc1c40238053a07736faa64b34cab294987
node frontend/self-check.js
python3 -m pytest -q backend/tests/test_config.py backend/tests/test_hedge_open_live_client.py backend/tests/test_margin_repay.py backend/tests/test_asset_transfer.py backend/tests/test_service_health.py backend/tests/test_frontend_field_binding.py
python3 -m pytest -q backend/tests
```

7. **范围和结论**：Human 验收勘误不改变固定产品交付，也不授权 Reviewer 修代码。任何新的
   `REWORK` 必须满足 `AGENTS.md` §1/§8，给出当前证据、实际影响、范围分类与最小修复；不得
   将已撤销的 R1 换名重提。
8. 创建合规 handoff：记录固定 SHA、逐项证据、原始测试结果和明确 verdict；Human Brief
   输出合规 `[TASK_RESULT v2]`。

## Stop

只完成本次 fresh review-1 并创建指定 handoff 后停止。`ACCEPT` 仅允许 Bookkeeper 核验并
准备独立 review-2；`REWORK` 仅返回具名发现。不得修改、部署、开闸、实盘、合并或启动下一
模型。
