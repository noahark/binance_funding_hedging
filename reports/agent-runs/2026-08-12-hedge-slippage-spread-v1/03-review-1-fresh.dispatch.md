# Dispatch: 03-review-1-fresh

## Identity

- task_id: `03-review-1-fresh`
- target_role: `Reviewer`
- target_model: `opus5`
- provider: `anthropic`
- status_revision: `6`
- required_skill: `agents/skills/code-reviewer.md`

## Goal

在一个不含 `03-review-1` 或 `03-review-1-retry` 会话上下文的全新 Opus 5 只读终端中，
对固定提交区间
`7da67bc87261386c117b98f2b63c6ac6083fd291..db552a7b224fcebc84bb23a087ff2b28a350bf04`
重新执行独立、跨 provider 的 HIGH_RISK review-1。前两份 review-1 handoff 仅作为已披露问题与
范围提示，不得沿用其 verdict 或测试结果；本轮必须独立检查并重新形成结论。若当前终端曾执行
前两次 review，立即返回 `blocked（阻塞）`，不得继续。

产品目标不变：`open_slippage` / `close_slippage` 使用同阶段现货/合约两腿真实成交数量加权均价，
按 `(卖出腿均价 - 买入腿均价) / min(两腿均价) * 100` 计算，卖价高于买价为正；四向腿映射与
`domain.direction_to_leg_actions` 一致，输出四位 `Decimal` 百分数文本，缺腿/非法/非正返回
`None`，真实零价差为 `"0.0000"`，完全移除 `est_price` 依赖。

O-2 旧口径 tooltip/注释须作为合并/发布前文本同步事项复核；O-1 与 O-4 须按证据独立判断并在
适用时带入 review-2/Human。历史 JSTUSDT 补录、部署、重启、实盘数据库和订单资金动作不在范围。

## Allowed Files

- 全部只读：`AGENTS.md`、`PROJECT_STATE.md`、`reports/agent-runs/ACTIVE.json`、本 dispatch、
  `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json`、`agents/roles.md` 的 Reviewer
  与 Task Handoff Evidence Contract 相关段落、`agents/skills/code-reviewer.md`。
- 只读证据：
  `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/01-plan-review-retry.handoff.md`、
  `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/02-implement.handoff.md`、
  `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/03-review-1.handoff.md`、
  `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/03-review-1-retry.handoff.md`。
- 只读源码/测试：`backend/hedge_open_tasks/store.py`、`backend/hedge_open_tasks/domain.py`、
  `backend/hedge_open_tasks/service.py`、`backend/services/live_hedge_executor.py`、
  `backend/tests/test_hedge_store.py`、`backend/tests/test_hedge_cycle_close.py`、`frontend/index.html`。
- 只读 Git 对象与固定 diff：base
  `7da67bc87261386c117b98f2b63c6ac6083fd291`，delivery
  `db552a7b224fcebc84bb23a087ff2b28a350bf04`。读取受审文件时使用
  `git show <sha>:<path>` / `git diff <base>..<delivery>`，不得以移动 HEAD 或未提交工作树替代。
- 唯一 create-only 写权限：
  `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/03-review-1-fresh.handoff.md`
- Bookkeeper 预检：
  `test ! -e reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/03-review-1-fresh.handoff.md`
  已通过（`handoff_preflight=absent`）。若执行时已存在，立即阻塞，不得覆盖。
- 不得修改源码、测试、现有证据、status、PROJECT_STATE、Git 或未提交前端文件；测试须禁用 repo
  内 bytecode/cache 写入；不得读取实盘数据库或控制服务。

## Inputs

按以下顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/03-review-1-fresh.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json`
6. `agents/roles.md` 的 Reviewer 与 Task Handoff Evidence Contract 相关段落
7. `agents/skills/code-reviewer.md`
8. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/01-plan-review-retry.handoff.md`
9. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/02-implement.handoff.md`
10. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/03-review-1.handoff.md`
11. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/03-review-1-retry.handoff.md`
12. 固定 SHA 的源码、测试与 diff

## Acceptance Checks

1. `pass|fail`：确认当前是与前两次 review 无上下文共享的 fresh read-only session；否则阻塞。
2. `pass|fail`：固定 delivery 仅含授权五路径，status 迁移合规，控制提交不误算产品交付。
3. `pass|fail`：两腿真实成交加权均价、卖减买、min 分母、×100、四位 Decimal 与四向映射正确。
4. `pass|fail`：跨 attempt 聚合及无周期/非法/非正/缺腿降级不存在假零或异常泄漏。
5. `pass|fail`：JSTUSDT open `0.2316`、close `-0.2192` 及零价差回归被真实测试钉住。
6. `pass|fail`：旧 `est_price` 路径已删除，schema/API 字段与 service 调用契约未改变；以只读方式
   重新运行定向测试与 `backend/tests` 全量测试，不沿用前两轮结果。
7. `pass|fail`：检查锁/事务、Decimal 精度、方向来源、数据生产缝与既有调用者，无订单、资金、
   schema、服务控制或恢复链副作用。
8. `pass|fail`：发现按 `in-range` / `pre-existing-independent` /
   `pre-existing-release-critical` 分类并给证据；独立复核 O-1、O-2、O-4，新假设满足 Scenario Admission。

## Stop

只读完成 fresh review-1，创建且仅创建指定 handoff；Reviewer handoff 的 `delivery_sha` 必须固定为
`db552a7b224fcebc84bb23a087ff2b28a350bf04`。输出合规 `[TASK_RESULT v2]` 及明确
`评审结论: ACCEPT（接受）|REWORK（返工）`、问题记录、修复要求，然后停止。不得启动下一模型。
