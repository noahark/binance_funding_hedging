# 阶段一：前端排版展示与自检断言 dispatch — Kimi / Moonshot

## Identity

- task_id: `32-phase1-frontend-ui-kimi`
- target_role: `Implementer`
- target_model: `kimi`
- provider: `moonshot`
- status_revision: 11
- required_skill: `agents/skills/senior-developer.md`
- risk_class: `LOW_RISK`（阶段一纯前端展示与排版自检，后端字段占位已由 31-phase1-backend-stub-glm 交付合流）

## Goal

落实阶段一的前端页面展示与自动化自检断言：
1. 在 `frontend/index.html` 的持仓表（`#positionsTable`）与历史仓位表（`#closeLogsTable`）增加「手续费成本」列；
2. 更新空表 `colspan`（持仓 17 改 18，历史 16 改 17）；
3. 接入已冻结的字段键名（`p.trading_fee_usdt`, `p.fee_bnb_qty`, `p.trading_fee_incomplete`），实现未全展示「—」、完整展示折 U 金额与双行 BNB 数量；
4. 更新 `frontend/self-check.js`（同步 `:8588` colspan=18 断言并增加手续费渲染自检用例）；
5. 顺带修复 `backend/tests/test_frontend_field_binding.py` 既有的 `loadHedgeTasks` 签名测试锚点，确保所有跨端绑定与前端自检全部跑绿。

## Allowed Files

- `frontend/index.html`（修改：持仓表与历史表增加列头、渲染逻辑、空表 colspan）
- `frontend/self-check.js`（修改：更新持仓空表 colspan=18 断言，增加手续费列测试用例）
- `backend/tests/test_frontend_field_binding.py`（修改：仅限修复 `test_expanded_log_poll_includes_all_running_tasks_and_retains_non_running_expanded` 中对 `loadHedgeTasks` 签名的锚点）
- **唯一允许新建的交接件（create-only）**：
  `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/32-phase1-frontend-ui-kimi.handoff.md`
- **Bookkeeper 预检（2026-08-20 10:45 CST）**：
  `test ! -e reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/32-phase1-frontend-ui-kimi.handoff.md` → **ABSENT**，create-only 权威成立。

除上述文件外，严禁修改任何后端业务 Python 代码、既有文档、`status.json`、`PROJECT_STATE.md`、`ACTIVE.json`；严禁 commit/merge/push、严禁下单、严禁重启服务。

## Inputs

按下列顺序读取：

1. `AGENTS.md`
2. 本 dispatch：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/32-phase1-frontend-ui-kimi.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. 本 stage `status.json`：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/status.json`
6. `agents/roles.md`（重点阅读 `Shared Rules`、`Task Handoff Evidence Contract`、`Implementer` 节）
7. `agents/developer-discipline.md`
8. `agents/skills/senior-developer.md`（required_skill）
9. 上一任务交接件：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/31-phase1-backend-stub-glm.handoff.md`
10. Stage 设计正文：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md`（r4，重点阅读 §5.1, §5.2, §7.1）
11. 相关代码：
    - `frontend/index.html`
    - `frontend/self-check.js`
    - `backend/tests/test_frontend_field_binding.py`

## Acceptance Checks

1. **持仓表（`#positionsTable`）渲染**：
   - 表头在「开单价差率」和「累计资金费」之间新增「手续费成本」列；
   - 空态行 `colspan` 必须由 **17 更新为 18**；
   - 当 `p.trading_fee_incomplete === true` 或金额为 null 时，主行渲染为「—」，不显示第二行；
   - 当 `p.trading_fee_incomplete === false`（或 0）且金额不为 null 时，主行显示折 U 金额，若有 `p.fee_bnb_qty` 则第二行显示 BNB 数量（如 `0.00075 BNB`）。
2. **历史仓位（`#closeLogsTable`）渲染**：
   - 表头在「总借币利息 / 总资金费率收益」旁新增「手续费成本」列；
   - 空态行 `colspan` 必须由 **16 更新为 17**；
   - 当 `r.trading_fee_incomplete == 1` 或金额为 null 时渲染为「—」；完整时显示折 U 金额（及 BNB 数量）。
3. **自动化测试全部通过**：
   - 运行并全绿：
     ```bash
     node frontend/self-check.js
     PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_frontend_field_binding.py backend/tests/test_hedge_api.py
     ```
4. **Handoff 与回执**：
   - 创建交接件 `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/32-phase1-frontend-ui-kimi.handoff.md`，包含 `BOOKKEEPER_APPEND_ONLY` 标记；
   - 控制台严格按 `AGENTS.md` §7 输出标准 `[TASK_RESULT v2]`。

## Stop

完成后停止，由 Bookkeeper (`gemini-3.7-flash` / `agy`) 核验。

控制台回执格式：
```text
[TASK_RESULT v2]
任务 ID: 32-phase1-frontend-ui-kimi
执行结果: completed（完成）
结果摘要: <不超过 300 个总字符>
产物: [frontend/index.html, frontend/self-check.js, backend/tests/test_frontend_field_binding.py, reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/32-phase1-frontend-ui-kimi.handoff.md]
检查结果: [<各项 pass / fail / contested>]
阻塞项: [<none or blockers>]
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: gemini-3.7-flash（Bookkeeper，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/32-phase1-frontend-ui-kimi.handoff.md；执行：核验阶段一前端交付并派发阶段一 Review-1 评审任务（Opus 5）；关卡：Opus 5 Review-1 ACCEPT 且经 Human 确认页面排版后进入阶段二
[/TASK_RESULT]
```
闭合标记 `[/TASK_RESULT]` 后不得有任何额外文字。
