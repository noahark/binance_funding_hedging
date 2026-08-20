# 成交手续费冻价成本 V1 第三轮计划复评 dispatch — Opus 5 / Anthropic

## Identity

- task_id: `22-plan-review-r3`
- target_role: `Reviewer`
- target_model: `opus5`
- provider: `anthropic`
- status_revision: 7
- required_skill: `agents/skills/reality-checker.md`

## Goal

对 Planner（Grok 4.6 / xAI）最新修订的 `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md`（r3 修订版，commit `248e968`）执行第三轮独立、跨 provider 的只读**计划复评**。

重点核验第二轮计划评审交接件（`evidence/21-plan-review-r2.handoff.md`）中的两处阻塞项（B1a UM 约 10 分钟窗口收敛与 limit=1000 截断不全判据、B1b `fee_bnb_qty` 随 `incomplete` 一并置 NULL）以及相关优化项（D11 `DEFAULT 1`、持仓空表 `colspan="18"`、回补跳过已失败腿等）是否已完整闭环，出具最终的计划评审判定（ACCEPT / REWORK）。

本任务为交付前只读计划评审，按 `AGENTS.md` §8 与 `agents/roles.md`，不触碰 `rework_count`。verdict 回到 Bookkeeper (`gemini-3.7-flash` / `agy`)。

## 隔离披露

- 设计作者：Grok 4.6 / xAI（provider `xai`）。
- Bookkeeper：Gemini 3.7 Flash / Google（provider `google`，窗口 `agy`）。
- 本 Reviewer：Opus 5 / Anthropic（provider `anthropic`，窗口 `claude` / `claude-review`；备选 Codex / OpenAI）。三方跨 provider 隔离成立。

## Allowed Files

Reviewer 完全只读，除下面唯一确定性 handoff 文件外零写入：

- **唯一允许新建（create-only）**：
  `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/22-plan-review-r3.handoff.md`
- **Bookkeeper 预检（2026-08-20 00:48 CST）**：
  `test ! -e reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/22-plan-review-r3.handoff.md` → **ABSENT**，create-only 权威成立。
  该路径在开始前不存在；若开始时已存在即任务失败。

Reviewer 不得修改任何代码、测试、既有文档、`status.json`、`PROJECT_STATE.md`、`ACTIVE.json`；严禁 commit/merge/push、严禁下单、严禁重启服务、严禁部署、严禁访问真实凭据与 live DB。

handoff 必须遵守 `agents/roles.md` 的 Task Handoff Evidence Contract：包含 Source Report、Required Reading for the Next Task、Human Brief / Console Receipt Source，并在末尾保留 `<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->` 标记。

## Inputs

按下列顺序读取：

1. `AGENTS.md`
2. 本 dispatch：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/22-plan-review-r3.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. 本 stage `status.json`：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/status.json`
6. `agents/roles.md`（重点阅读 `Shared Rules`、`Task Handoff Evidence Contract`、`Reviewer` 节）
7. `agents/skills/reality-checker.md`（required_skill）
8. 第二轮计划评审交接件：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/21-plan-review-r2.handoff.md`
9. Stage 设计正文（r3 修订版）：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md`（commit `248e968`）
10. Stage intake：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/00-intake.md`
11. 真实存在的代码及既有契约参考（只读）：
    - `backend/hedge_open_tasks/store.py`
    - `backend/hedge_open_tasks/service.py`
    - `backend/services/hedge_open_live_client.py`
    - `backend/services/live_hedge_executor.py`
    - `frontend/index.html` 与 `frontend/self-check.js`
    - `docs/api/public-market-contract.md` 与 `docs/product/PRD.md`

## Acceptance Checks

Reviewer 须逐项核查以下内容并在 handoff 中给出明确检查结果（pass / fail / contested）：

1. **B1a 落实**：§2.2 / §4.1 中 UM 合约成交拉取是否已收敛为约 10 分钟窗口，且明确 `limit=1000` 并在达到 1000 时判定为不全（禁止对截断列表求和）？
2. **B1b 落实**：§5.1 / §5.2 / D11 中是否明确当 `incomplete=1`（或 `true`）时，`trading_fee_usdt` 与 `fee_bnb_qty` **一并置 NULL**，杜绝半截数量歧义？
3. **D11 数据库迁移**：`trading_fee_incomplete` 加列是否明确指定 `DEFAULT 1`（fail-closed）？
4. **前端列数同步**：持仓表空态 `colspan` 17 改 18 及 `self-check.js:8588` 断言同步要求是否已写入设计？历史表 16 改 17 是否明确？
5. **回补与其余优化项**：回补跳过已失败腿、K 线接口归属 `binance_public`、现货/合约交易对符号取值等是否自洽？
6. **拆包就绪度**：后端（`claude_glm`）与前端（`kimi`）的契约与职责是否已完全清晰可执行？
7. **Handoff 与任务回执规范**：产物为指定 handoff 路径，包含 `BOOKKEEPER_APPEND_ONLY` 标记，控制台输出标准 review 版 `[TASK_RESULT v2]`。

## Stop

完成后停止，由 Bookkeeper (`gemini-3.7-flash` / `agy`) 核验。Reviewer 除指定 handoff 外零写入。

控制台严格按 `AGENTS.md` §7 输出 review 版 `[TASK_RESULT v2]`：
```text
[TASK_RESULT v2]
任务 ID: 22-plan-review-r3
执行结果: completed（完成）
结果摘要: <不超过 300 个总字符>
产物: [reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/22-plan-review-r3.handoff.md]
检查结果: [<各项 pass / fail / contested>]
评审结论: ACCEPT（接受） | REWORK（返工）
问题记录: <path | none>
修复要求: <path | none>
阻塞项: [<none or blockers>]
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: gemini-3.7-flash（Bookkeeper，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/22-plan-review-r3.handoff.md；执行：核验第三轮计划评审结论；关卡：若 ACCEPT 且经 Human 批准后，拆分后端与前端实现 dispatch
[/TASK_RESULT]
```
闭合标记 `[/TASK_RESULT]` 后不得有任何额外文字。
