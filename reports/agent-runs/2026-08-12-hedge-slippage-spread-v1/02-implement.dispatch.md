# Dispatch: 02-implement

## Identity

- task_id: `02-implement`
- target_role: `Implementer`
- target_model: `codex`
- provider: `openai`
- status_revision: `3`
- required_skill: `agents/skills/senior-developer.md`

## Goal

实现已通过独立计划评审的最小修复：历史仓位 `open_slippage` / `close_slippage` 只使用对应
阶段两腿真实成交数量加权均价，统一为
`(卖出腿均价 - 买入腿均价) / min(两腿均价) * 100`，卖价高于买价才为正。

具体要求：

1. 修改 `HedgeOpenStore.cycle_slippage_pct(cycle_id, task_type)`，保持签名与调用方不变；从
   `hedge_open_cycle.direction` 取得方向，复用已有现货腿/合约腿周期加权均价逻辑，不再读取
   task/attempt preflight `est_price`。
2. 卖/买腿映射必须与 `domain.direction_to_leg_actions` 一致：forward open 合约卖/现货买；
   reverse open 现货卖/合约买；forward close 现货卖/合约买；reverse close 合约卖/现货买。
3. 任一腿无真实正数成交均价、周期/方向/task_type 无效或分母非正时返回 `None`，不得臆造零；
   真正零价差返回字符串 `"0.0000"`。全程 `Decimal`，最终保存四位百分数文本。
4. 更新 `store.py` 内同字段的过时 schema/docstring 注释，使其说明两腿真实成交价差百分比；
   不改变 schema 或 API 字段。
5. 用最少测试覆盖四种 open/close×方向映射、跨多个 attempt 的两腿数量加权、缺腿降级、零价差，
   以及 JSTUSDT reverse open `+0.2316%` / reverse close `-0.2192%`。同步更新
   `test_hedge_cycle_close.py` 中旧口径下期待 `None` 的既有断言。

非目标：不补录实盘历史，不重启/部署/控制服务，不操作订单、资金、闸门或数据库，不改 API、
service 功能逻辑、前端逻辑/文案或 docs。前端与 service 的旧口径描述由后续独立文本同步任务处理。

## Allowed Files

- 可修改：`backend/hedge_open_tasks/store.py`
- 可修改：`backend/tests/test_hedge_store.py`
- 可修改：`backend/tests/test_hedge_cycle_close.py`
- 可修改且仅允许把本任务 `current_task.state` 从 `dispatched` 改为 `reported`：
  `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json`
- 唯一新建 handoff：
  `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/02-implement.handoff.md`
- 其余输入全部只读，包括 `AGENTS.md`、`PROJECT_STATE.md`、`reports/agent-runs/ACTIVE.json`、
  本 dispatch、计划评审 handoff、`agents/roles.md`、`agents/developer-discipline.md`、
  `agents/skills/senior-developer.md`、`backend/hedge_open_tasks/domain.py`、
  `backend/hedge_open_tasks/service.py`、`frontend/index.html`。
- Bookkeeper 预检：
  `test ! -e reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/02-implement.handoff.md`
  已通过（`handoff_preflight=absent`）。若执行时路径已存在，立即 `blocked（阻塞）`，不得覆盖。
- 工作区已有 Human 所属未提交改动：`frontend/index.html`、`frontend/self-check.js`。不得编辑、
  暂存、提交或恢复它们；提交前必须用 pathspec 核对 staged files。
- 授权创建恰好一个 delivery commit，仅包含三份实现/测试文件、本任务 handoff 与上述 status 单字段
  状态变化。不得 amend、合并、推送或提交其他文件。

## Inputs

按以下顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/02-implement.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json`
6. `agents/roles.md` 的 Implementer 与 Task Handoff Evidence Contract 相关段落
7. `agents/developer-discipline.md`
8. `agents/skills/senior-developer.md`
9. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/01-plan-review-retry.handoff.md`
10. Allowed Files 中列出的源码与测试

## Acceptance Checks

1. `pass|fail`：公式、四向卖/买腿映射、min 分母、×100 与四位 `Decimal` 文本完全符合 Goal。
2. `pass|fail`：两腿分别跨 attempt 做真实成交数量加权；旧 `est_price` 路径被删除且测试能反证回归。
3. `pass|fail`：缺腿/不可定价/非正均价/无周期或无效输入返回 `None`；真实零价差为 `"0.0000"`。
4. `pass|fail`：JSTUSDT 数据夹具得到 reverse open `0.2316`、reverse close `-0.2192`。
5. `pass|fail`：`.venv/bin/python -m pytest backend/tests/test_hedge_store.py backend/tests/test_hedge_cycle_close.py -q`。
6. `pass|fail`：`.venv/bin/python -m pytest backend/tests -q`。
7. `pass|fail`：`git diff --check`，且最终 delivery commit 仅含 Allowed Files 授权的五个路径。
8. `pass|fail`：零实盘库写入、零服务控制/重启/部署、零订单/资金/闸门动作；API/schema/frontend/service
   功能行为不变。

## Stop

完成实现与测试后，先创建指定 handoff（author source 内 `delivery_sha: pending`），再仅暂存 Allowed
Files 授权的实现/测试、handoff 与 status 单字段变化，创建恰好一个 delivery commit。用
`git rev-parse HEAD` 与 `git show --name-only --format= HEAD` 报告提交和文件集合；不得把 author
source 的 `pending` 改写为 SHA。输出合规 `[TASK_RESULT v2]`，并停止。不得启动、调用或指派
Reviewer；结果返回当前 `status.json.bookkeeper`，由 Human 启动后续终端。
