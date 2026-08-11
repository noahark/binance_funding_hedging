# Dispatch: 01-plan-review

## Identity

- task_id: `01-plan-review`
- target_role: `Reviewer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `1`
- required_skill: `agents/skills/code-reviewer.md`

## Goal

对以下最小实现计划做独立、跨 provider、只读的 HIGH_RISK 计划评审；本任务不实现代码：

1. 保留现有 `hedge_open_cycle_close_log.open_slippage` / `close_slippage` 字段和 API 形状，
   把 `HedgeOpenStore.cycle_slippage_pct` 从“合约腿成交价对 task preflight `est_price`”改为
   “同一周期、同一 task_type 的现货腿与合约腿真实成交数量加权均价之差”。
2. 统一公式为 `(卖出腿加权均价 - 买入腿加权均价) / min(两腿加权均价) * 100`：
   - forward open：合约卖出、现货买入；
   - reverse open：现货卖出、合约买入；
   - forward close：现货卖出、合约买入；
   - reverse close：合约卖出、现货买入。
3. 复用已有周期腿加权均价逻辑；任一腿无真实正数成交均价时返回 `None`，前端继续显示 `—`。
   全程使用 `Decimal`，最终保存四位百分数文本；不再读取 `est_price`。
4. 预计实现只改 `backend/hedge_open_tasks/store.py` 与最少的后端测试。不得修改 schema、API
   字段、前端、实盘数据库、服务进程、闸门、订单、资金或历史记录。
5. 实现测试至少钉住四个方向/阶段映射、跨多 attempt 的两腿数量加权、缺腿降级，以及真实
   JSTUSDT 样本：reverse open `+0.2316%`、reverse close `-0.2192%`。

评审须判断该计划是否满足 Human 已确认的产品含义、是否存在方向/单位/精度/加权错误、最小
文件边界是否足够、测试是否能阻止旧的 `est_price` 算法回归。返回明确 `ACCEPT` 或 `REWORK`。

## Allowed Files

- 只读：`AGENTS.md`
- 只读：`agents/roles.md` 的 Reviewer 与 Task Handoff Evidence Contract 相关段落
- 只读：`agents/skills/code-reviewer.md`
- 只读：`PROJECT_STATE.md`
- 只读：`reports/agent-runs/ACTIVE.json`
- 只读：`reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json`
- 只读：`reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/01-plan-review.dispatch.md`
- 只读：`backend/hedge_open_tasks/store.py`
- 只读：`backend/hedge_open_tasks/service.py`
- 只读：`backend/tests/test_hedge_store.py`
- 只读：`backend/tests/test_hedge_cycle_close.py`
- 只读：`frontend/index.html`
- 唯一 create-only 写权限：
  `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/01-plan-review.handoff.md`
- Bookkeeper 预检：
  `test ! -e reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/01-plan-review.handoff.md`
  已通过（`handoff_preflight=absent`）。若执行时路径已存在，立即 `blocked`，不得覆盖。

## Inputs

按以下顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/01-plan-review.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json`
6. `agents/roles.md` 的 Reviewer 与 Task Handoff Evidence Contract 相关段落
7. `agents/skills/code-reviewer.md`
8. Allowed Files 中列出的源码与测试

正式结果写入唯一 handoff；结构、immutable source、Human Brief、Bookkeeper append marker 与
create-only 规则以 `agents/roles.md` 的 Task Handoff Evidence Contract 为唯一权威。

## Acceptance Checks

1. `pass|fail`：公式仅使用两腿真实成交数量加权均价，完全不依赖 preflight `est_price`。
2. `pass|fail`：open/close × forward/reverse 的卖腿、买腿映射与 Human 定义完全一致。
3. `pass|fail`：分母为两腿加权均价较低者；结果乘 100、使用 `Decimal`、保存四位百分数文本。
4. `pass|fail`：跨多个 attempt 分别聚合两腿；任一腿缺失、非正数或无真实成交均价时返回
   `None`，不臆造零。
5. `pass|fail`：最小实现边界足够，且无需 schema、API、前端或 service 改动。
6. `pass|fail`：测试计划覆盖四种映射、数量加权、缺腿降级与 JSTUSDT 两个期望值。
7. `pass|fail`：明确排除实盘库补录、服务重启、部署及任何资金/订单动作；它们保留为后续
   Human 独立授权关卡。
8. `pass|fail`：检查 `docs/` 活文档在 stage 收口时应更新的最小权威位置，不能把旧错误口径
   留在活文档。

## Stop

只读完成计划评审，创建且仅创建指定 handoff，输出合规 `[TASK_RESULT v2]` 与
`评审结论: ACCEPT|REWORK`。不得修改源码、测试、状态、PROJECT_STATE、现有证据或 git；不得
启动、调用或指派下一模型。结果返回当前 `status.json.bookkeeper`，由 Human 启动后续终端。
