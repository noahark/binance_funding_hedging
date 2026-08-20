# T1 前端 Fake 页面与排版验证 dispatch — Kimi / Moonshot

## Identity

- task_id: `30-t1-fake-ui-kimi`
- target_role: `Implementer`
- target_model: `kimi`
- provider: `moonshot`
- status_revision: 9
- required_skill: `agents/skills/senior-developer.md`
- risk_class: `LOW_RISK`（纯前端展示夹具与排版验证，不修改后端代码、不修改数据库、不发起实盘请求）

## Goal

落实 Human 五步实施路径的第 1 步（T1 Fake 页面展示）：
在持仓表与历史仓位表中增加「手续费成本」列，使用已冻结的字段结构（`trading_fee_usdt`, `fee_bnb_qty`, `trading_fee_incomplete`）注入前端展示夹具，验证双行展示效果、空表 `colspan`（持仓 18 / 历史 17）以及缺失数据「—」渲染，并通过 `node frontend/self-check.js` 自动化测试。

本任务为纯前端视觉与结构验证，严禁伪造虚假实盘数据冒充真实网络回包，严禁修改任何后端文件或数据库。

## Allowed Files

- `frontend/index.html`（修改：持仓表与历史表增加列头、渲染逻辑、空表 colspan）
- `frontend/self-check.js`（修改：更新持仓空表 colspan=18 断言，增加手续费列测试用例）
- **唯一允许新建的交接件（create-only）**：
  `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/30-t1-fake-ui-kimi.handoff.md`
- **Bookkeeper 预检（2026-08-20 10:20 CST）**：
  `test ! -e reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/30-t1-fake-ui-kimi.handoff.md` → **ABSENT**，create-only 权威成立。

除上述文件外，严禁修改任何后端 Python 代码、既有文档、`status.json`、`PROJECT_STATE.md`、`ACTIVE.json`；严禁 commit/merge/push、严禁下单、严禁重启服务。

## Inputs

按下列顺序读取：

1. `AGENTS.md`
2. 本 dispatch：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/30-t1-fake-ui-kimi.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. 本 stage `status.json`：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/status.json`
6. `agents/roles.md`（重点阅读 `Shared Rules`、`Task Handoff Evidence Contract`、`Implementer` 节）
7. `agents/developer-discipline.md`
8. `agents/skills/senior-developer.md`（required_skill）
9. Stage 设计正文：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md`（r4，重点阅读 §5.1, §5.2, §7.1 T1）
10. 前端代码：`frontend/index.html` 与 `frontend/self-check.js`

## Acceptance Checks

1. **持仓表（`#positionsTable`）**：
   - 表头在「开单价差率」和「累计资金费」之间新增「手续费成本」列；
   - 空态行 `colspan` 必须由 **17 更新为 18**；
   - 渲染逻辑：主行显示折 U 金额（如 `$0.45`），第二行显示 BNB 数量（如 `0.00075 BNB`）；
   - 当 `trading_fee_incomplete=true` 或金额为 null 时，主行渲染为「—」，不显示第二行数量。
2. **历史仓位（`#closeLogsTable`）**：
   - 表头在「总借币利息 / 总资金费率收益」旁新增「手续费成本」列；
   - 空态行 `colspan` 必须由 **16 更新为 17**；
   - 当 `trading_fee_incomplete=1` 或金额为 null 时渲染为「—」。
3. **前端自动化测试（`self-check.js`）**：
   - 必须更新 `:8588` 的持仓空表 `colspan` 硬断言为 18；
   - 补充针对「手续费成本」列的测试用例（覆盖完整金额+BNB双行、纯USDT单行、incomplete缺失「—」场景）；
   - 运行命令通过：`node frontend/self-check.js` 必须全绿无报错。
4. **Handoff 与回执**：
   - 创建交接件 `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/30-t1-fake-ui-kimi.handoff.md`，包含 `BOOKKEEPER_APPEND_ONLY` 标记；
   - 控制台严格按 `AGENTS.md` §7 输出标准 `[TASK_RESULT v2]`。

## Stop

完成后停止，由 Bookkeeper (`gemini-3.7-flash` / `agy`) 核验。

控制台回执格式：
```text
[TASK_RESULT v2]
任务 ID: 30-t1-fake-ui-kimi
执行结果: completed（完成）
结果摘要: <不超过 300 个总字符>
产物: [frontend/index.html, frontend/self-check.js, reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/30-t1-fake-ui-kimi.handoff.md]
检查结果: [<各项 pass / fail / contested>]
阻塞项: [<none or blockers>]
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: gemini-3.7-flash（Bookkeeper，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/30-t1-fake-ui-kimi.handoff.md；执行：核验 T1 前端 Fake 页面交付，准备 T2 后端建表与读聚合 dispatch（claude_glm）；关卡：Human 页面核对视觉效果并启动 T2
[/TASK_RESULT]
```
闭合标记 `[/TASK_RESULT]` 后不得有任何额外文字。
