# 阶段一：后端加列与 API 键占位 dispatch — Claude-GLM / Zhipu

## Identity

- task_id: `31-phase1-backend-stub-glm`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: 10
- required_skill: `agents/skills/senior-developer.md`
- risk_class: `HIGH_RISK`（数据库加列、API 响应字段字典与账务键占位）

## Goal

落实阶段一的后端部分：
在数据库完成 `hedge_open_leg` 4 列与 `close_log` 3 列的加列迁移，在 `aggregate_positions` 与 `_POSITION_KEYS` 接入 3 个新字段（`trading_fee_usdt`, `fee_bnb_qty`, `trading_fee_incomplete`）的占位与模型映射，并扩充 money-zero 检查名单。

本任务完成后，持仓与历史查询将返回合规的空值/默认值结构，为前端 Kimi 实现视觉排版与解除跨端字段绑定测试提供坚实基础。

## Allowed Files

- `backend/hedge_open_tasks/store.py`（修改：DDL、迁移逻辑、row 映射、`aggregate_positions` 占位、`insert_close_log` 字段扩展）
- `backend/tests/test_hedge_api.py`（修改：`_POSITION_KEYS` 增加 3 个新键）
- `backend/tests/test_hedge_purity.py`（修改：`_MONEY_NAMES` 增加 4 个新字段名）
- `backend/tests/test_hedge_store.py`（修改：若有断言涉及表结构或字段映射）
- **唯一允许新建的交接件（create-only）**：
  `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/31-phase1-backend-stub-glm.handoff.md`
- **Bookkeeper 预检（2026-08-20 10:29 CST）**：
  `test ! -e reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/31-phase1-backend-stub-glm.handoff.md` → **ABSENT**，create-only 权威成立。

除上述文件外，严禁修改任何前端代码、既有文档、`status.json`、`PROJECT_STATE.md`、`ACTIVE.json`；严禁 commit/merge/push、严禁下单、严禁重启服务。

## Inputs

按下列顺序读取：

1. `AGENTS.md`
2. 本 dispatch：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/31-phase1-backend-stub-glm.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. 本 stage `status.json`：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/status.json`
6. `agents/roles.md`（重点阅读 `Shared Rules`、`Task Handoff Evidence Contract`、`Implementer` 节）
7. `agents/developer-discipline.md`
8. `agents/skills/senior-developer.md`（required_skill）
9. Stage 设计正文：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md`（r4，重点阅读 §3 D1-D11, §4.2, §5.1, §5.2）
10. 相关代码：
    - `backend/hedge_open_tasks/store.py`
    - `backend/tests/test_hedge_api.py`
    - `backend/tests/test_frontend_field_binding.py`
    - `backend/tests/test_hedge_purity.py`

## Acceptance Checks

1. **数据库加列（`store.py`）**：
   - `hedge_open_leg` 增加 4 列：`fee_bnb_qty TEXT`, `fee_bnb_price TEXT`, `fee_other_qty TEXT`, `fee_other_asset TEXT`；
   - `close_log` 增加 3 列：`trading_fee_usdt TEXT`, `fee_bnb_qty TEXT`, `trading_fee_incomplete INTEGER NOT NULL DEFAULT 1`；
   - 迁移脚本具备幂等性（若列已存在则跳过，参考仓内既有 `ALTER TABLE … ADD COLUMN` 迁移模式）。
2. **对象映射与读聚合占位**：
   - `_row_to_leg` 与 `_row_to_close_log` 能够正确映射上述新列；
   - `aggregate_positions` 返回的每个 position dict 中必须包含：
     - `"trading_fee_usdt": None`
     - `"fee_bnb_qty": None`
     - `"trading_fee_incomplete": True`
   - `insert_close_log` 写入新列（未传入时默认写入 `trading_fee_incomplete=1`, `trading_fee_usdt=None`, `fee_bnb_qty=None`）。
3. **API 键契约与 money-zero**：
   - `test_hedge_api.py` 的 `_POSITION_KEYS` 集合包含 `"trading_fee_usdt"`, `"fee_bnb_qty"`, `"trading_fee_incomplete"`；
   - `test_hedge_purity.py` 的 `_MONEY_NAMES` 包含 `"fee_bnb_price"`, `"fee_bnb_qty"`, `"fee_other_qty"`, `"trading_fee_usdt"`。
4. **自动化测试**：
   - 运行并全绿：
     ```bash
     PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_hedge_api.py backend/tests/test_frontend_field_binding.py backend/tests/test_hedge_store.py backend/tests/test_hedge_purity.py
     ```
5. **Handoff 与回执**：
   - 创建交接件 `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/31-phase1-backend-stub-glm.handoff.md`，包含 `BOOKKEEPER_APPEND_ONLY` 标记；
   - 控制台严格按 `AGENTS.md` §7 输出标准 `[TASK_RESULT v2]`。

## Stop

完成后停止，由 Bookkeeper (`gemini-3.7-flash` / `agy`) 核验。

控制台回执格式：
```text
[TASK_RESULT v2]
任务 ID: 31-phase1-backend-stub-glm
执行结果: completed（完成）
结果摘要: <不超过 300 个总字符>
产物: [backend/hedge_open_tasks/store.py, backend/tests/test_hedge_api.py, backend/tests/test_hedge_purity.py, reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/31-phase1-backend-stub-glm.handoff.md]
检查结果: [<各项 pass / fail / contested>]
阻塞项: [<none or blockers>]
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: gemini-3.7-flash（Bookkeeper，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/31-phase1-backend-stub-glm.handoff.md；执行：核验阶段一后端加列与占位交付，派发阶段一前端展示任务（32-phase1-frontend-ui-kimi）；关卡：Human 启动 kimi 窗口执行前端展示
[/TASK_RESULT]
```
闭合标记 `[/TASK_RESULT]` 后不得有任何额外文字。
