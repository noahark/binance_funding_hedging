# 阶段一（排版、建表加列与占位）Review-1 独立评审 dispatch — Opus 5 / Anthropic

## Identity

- task_id: `40-phase1-review1-opus5`
- target_role: `Reviewer`
- target_model: `opus5`
- provider: `anthropic`
- status_revision: 12
- required_skill: `agents/skills/code-reviewer.md`

## Goal

对阶段一（排版与读链路骨架：后端加列占位 + 前端表格排版与自检）的交付执行独立的 Review-1 代码与契约评审。

受审交付范围：
`aa2b9cf6a005728b1d00dec22a48f78c96d7cae4..a0bf7c520a27762513ad5e3513d99ac752e64dce`
（包含后端加列占位提交 `6d83f05` 与前端排版展示提交 `a0bf7c5`）

重点核验：
1. `backend/hedge_open_tasks/store.py` 中 `hedge_open_leg` 4 列与 `close_log` 3 列加列迁移的幂等性，`trading_fee_incomplete` 是否严格采用 `DEFAULT 1`（fail-closed）；
2. `aggregate_positions` 占位三键（`trading_fee_usdt: None`, `fee_bnb_qty: None`, `trading_fee_incomplete: True`）与 `_POSITION_KEYS` 契约完整性；
3. `frontend/index.html` 持仓表（colspan=18）与历史仓位表（colspan=17）的表头位置、未全「—」渲染、完整双行渲染逻辑；
4. `frontend/self-check.js` 断言与跨端绑定测试全绿；
5. 确认阶段一未引入任何非预期的实盘下单逻辑、真实网络调用或越界写入。

## 隔离披露

- 设计作者：Grok 4.6 / xAI（provider `xai`）。
- 阶段一后端实现：Claude-GLM / Zhipu（provider `zhipu_glm`）。
- 阶段一前端实现：Kimi / Moonshot（provider `moonshot`）。
- Bookkeeper：Gemini 3.7 Flash / Google（provider `google`，窗口 `agy`）。
- 本 Reviewer：Opus 5 / Anthropic（provider `anthropic`，窗口 `claude-review`）。多方跨 provider 隔离成立。

## Allowed Files

Reviewer 完全只读，除下面唯一确定性 handoff 文件外零写入：

- **唯一允许新建（create-only）**：
  `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/40-phase1-review1-opus5.handoff.md`
- **Bookkeeper 预检（2026-08-20 11:05 CST）**：
  `test ! -e reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/40-phase1-review1-opus5.handoff.md` → **ABSENT**，create-only 权威成立。

Reviewer 不得修改任何代码、测试、既有文档、`status.json`、`PROJECT_STATE.md`、`ACTIVE.json`；严禁 commit/merge/push、严禁下单、严禁重启服务、严禁部署。

## Inputs

按下列顺序读取：

1. `AGENTS.md`
2. 本 dispatch：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/40-phase1-review1-opus5.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. 本 stage `status.json`：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/status.json`
6. `agents/roles.md`（重点阅读 `Shared Rules`、`Task Handoff Evidence Contract`、`Reviewer` 节）
7. `agents/skills/code-reviewer.md`（required_skill）
8. 阶段一后端交接件：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/31-phase1-backend-stub-glm.handoff.md`
9. 阶段一前端交接件：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/32-phase1-frontend-ui-kimi.handoff.md`
10. Stage 设计正文：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md`（r4）
11. 受审 Diff：`git diff aa2b9cf6a005728b1d00dec22a48f78c96d7cae4..a0bf7c520a27762513ad5e3513d99ac752e64dce`

## Acceptance Checks

1. **数据库加列与幂等迁移**：核验 `hedge_open_leg` 4 列与 `close_log` 3 列，`trading_fee_incomplete` 严格为 `NOT NULL DEFAULT 1`；
2. **读占位与字段契约**：`aggregate_positions` 返回占位 3 键，`_POSITION_KEYS` 严格同步；
3. **前端渲染与排版**：持仓表空态 `colspan=18`，历史表空态 `colspan=17`，未全单行「—」，完整双行 USDT+BNB；
4. **自动化测试**：执行并通过：
   ```bash
   node frontend/self-check.js
   PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_frontend_field_binding.py backend/tests/test_hedge_api.py backend/tests/test_hedge_store.py backend/tests/test_hedge_purity.py
   ```
5. **Handoff 与任务回执**：产物为指定交接件路径，包含 `BOOKKEEPER_APPEND_ONLY` 标记，控制台输出标准 review 版 `[TASK_RESULT v2]`。

## Stop

完成后停止，由 Bookkeeper (`gemini-3.7-flash` / `agy`) 核验。

控制台回执格式：
```text
[TASK_RESULT v2]
任务 ID: 40-phase1-review1-opus5
执行结果: completed（完成）
结果摘要: <不超过 300 个总字符>
产物: [reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/40-phase1-review1-opus5.handoff.md]
检查结果: [<各项 pass / fail / contested>]
评审结论: ACCEPT（接受） | REWORK（返工）
问题记录: <path | none>
修复要求: <path | none>
阻塞项: [<none or blockers>]
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: gemini-3.7-flash（Bookkeeper，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/40-phase1-review1-opus5.handoff.md；执行：核验阶段一 Review-1 评审结论；关卡：若 ACCEPT，请 Human 页面核对排版后授权开启阶段二（历史数据回补）
[/TASK_RESULT]
```
闭合标记 `[/TASK_RESULT]` 后不得有任何额外文字。
