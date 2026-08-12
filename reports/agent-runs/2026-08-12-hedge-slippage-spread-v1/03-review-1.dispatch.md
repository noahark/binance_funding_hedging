# Dispatch: 03-review-1

## Identity

- task_id: `03-review-1`
- target_role: `Reviewer`
- target_model: `opus5`
- provider: `anthropic`
- status_revision: `4`
- required_skill: `agents/skills/code-reviewer.md`

## Goal

对固定提交区间
`7da67bc87261386c117b98f2b63c6ac6083fd291..db552a7b224fcebc84bb23a087ff2b28a350bf04`
执行独立、跨 provider、只读的 HIGH_RISK review-1。实现作者为 Codex/OpenAI；Reviewer 为
Opus 5/Anthropic。检查代码、契约、测试与集成缝，不依据摘要替代原始 diff/测试。

本交付目标：`open_slippage` / `close_slippage` 使用同阶段现货/合约两腿真实成交数量加权均价，
统一为 `(卖出腿均价 - 买入腿均价) / min(两腿均价) * 100`，卖价高于买价为正；四向腿映射
与 `domain.direction_to_leg_actions` 一致，输出四位 `Decimal` 百分数文本，缺腿/非法/非正返回
`None`，真实零价差为 `"0.0000"`，完全移除 `est_price` 依赖。

`base_sha..delivery_sha` 含本 stage 控制提交，它们仅为上下文；受审产品交付是 delivery commit
`db552a7…` 中的 `store.py` 与两份测试。工作区另有未提交 `frontend/index.html`、
`frontend/self-check.js`，不属于固定 delivery，不得把移动工作树当作受审事实。实现范围按计划
不含前端/service 文本；旧 `est_price` tooltip/注释已具名保留为本 stage 后续文本同步任务，
Reviewer 须判断它对当前交付/后续 release gate 的实际影响，不得默认其已修复。

## Allowed Files

- 全部只读：`AGENTS.md`、`PROJECT_STATE.md`、`reports/agent-runs/ACTIVE.json`、本 dispatch、
  `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json`、`agents/roles.md` 的 Reviewer
  与 Task Handoff Evidence Contract 相关段落、`agents/skills/code-reviewer.md`。
- 只读证据：
  `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/01-plan-review-retry.handoff.md`、
  `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/02-implement.handoff.md`。
- 只读源码/测试：`backend/hedge_open_tasks/store.py`、`backend/hedge_open_tasks/domain.py`、
  `backend/hedge_open_tasks/service.py`、`backend/tests/test_hedge_store.py`、
  `backend/tests/test_hedge_cycle_close.py`、`frontend/index.html`。
- 只读 Git 对象与固定 diff：base
  `7da67bc87261386c117b98f2b63c6ac6083fd291`，delivery
  `db552a7b224fcebc84bb23a087ff2b28a350bf04`。不得用移动 HEAD 替换 delivery SHA；读取受审文件
  时优先 `git show <sha>:<path>` / `git diff <base>..<delivery>`，隔离未提交工作树。
- 唯一 create-only 写权限：
  `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/03-review-1.handoff.md`
- Bookkeeper 预检：
  `test ! -e reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/03-review-1.handoff.md`
  已通过（`handoff_preflight=absent`）。若执行时路径已存在，立即 `blocked（阻塞）`，不得覆盖。
- Reviewer 不得修改源码、测试、现有证据、status、PROJECT_STATE、git 或未提交前端文件；测试命令
  必须禁用 repo 内 bytecode/cache 写入。

## Inputs

按以下顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/03-review-1.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json`
6. `agents/roles.md` 的 Reviewer 与 Task Handoff Evidence Contract 相关段落
7. `agents/skills/code-reviewer.md`
8. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/01-plan-review-retry.handoff.md`
9. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/02-implement.handoff.md`
10. 固定 SHA 的源码、测试与 diff

## Acceptance Checks

1. `pass|fail`：固定 delivery 只含授权五路径，status 仅 `dispatched→reported`，控制提交不误算产品交付。
2. `pass|fail`：两腿真实成交加权均价、卖减买、min 分母、×100、四位 Decimal 与四向映射正确。
3. `pass|fail`：跨 attempt 聚合、unknown-vs-zero、无周期/非法/非正/缺腿降级不存在假零或异常泄漏。
4. `pass|fail`：JSTUSDT reverse open `0.2316`、reverse close `-0.2192` 及零价差回归被真实测试钉住。
5. `pass|fail`：旧 `est_price` 计算路径已从生产函数删除，schema/API 字段与 service 调用契约未改变。
6. `pass|fail`：以只读方式运行
   `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider backend/tests/test_hedge_store.py backend/tests/test_hedge_cycle_close.py -q`
   和 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider backend/tests -q`。
7. `pass|fail`：检查锁/事务、Decimal 精度、方向来源、异常输入与既有调用者，不引入订单、资金、数据库
   schema、服务控制或恢复链副作用。
8. `pass|fail`：每条发现按 `in-range` / `pre-existing-independent` /
   `pre-existing-release-critical` 分类并给证据；新假设场景必须满足 AGENTS.md §1 Scenario Admission。

## Stop

只读完成 review-1，创建且仅创建指定 handoff；Reviewer handoff 的 `delivery_sha` 必须是固定
`db552a7b224fcebc84bb23a087ff2b28a350bf04`，不得为 pending/HEAD。输出合规
`[TASK_RESULT v2]`、`评审结论: ACCEPT（接受）|REWORK（返工）`、问题记录与修复要求，并停止。
不得修改或启动下一模型。结果返回当前 `status.json.bookkeeper`，由 Human 启动后续终端。
