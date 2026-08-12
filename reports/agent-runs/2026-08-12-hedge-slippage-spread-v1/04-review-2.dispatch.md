# Dispatch: 04-review-2

## Identity

- task_id: `04-review-2`
- target_role: `Reviewer`
- target_model: `sonnet5`
- provider: `anthropic`
- status_revision: `7`
- required_skill: `agents/skills/reality-checker.md`

## Goal

在全新的 Sonnet 5 只读终端中，对固定提交区间
`7da67bc87261386c117b98f2b63c6ac6083fd291..db552a7b224fcebc84bb23a087ff2b28a350bf04`
执行 HIGH_RISK review-2，判断 Human 需求、实际交付效果、证据、运行风险与发布就绪度。

需求口径：同一开单或平单阶段分别聚合现货/合约两腿真实成交数量加权均价，按
`(卖出腿均价 - 买入腿均价) / min(两腿均价) * 100` 计算；卖价高于买价为正；forward/reverse
开平四向映射与 `domain.direction_to_leg_actions` 一致；四位 Decimal 文本；缺腿、非法、非正
返回 `None`，真实零价差为 `"0.0000"`，不得依赖 `est_price`。JSTUSDT 期望 open `0.2316`、
close `-0.2192`。

Review-1 的产品结论由 Opus 5 给出 `ACCEPT` 与八项 `pass`；其复用原终端的偏差已经完整披露，
Human 于 `2026-08-12 09:20:37 CST` 明确接受该一次性偏差，Bookkeeper 已在同一 handoff 追加记录。
Review-2 必须自行判断，不得把该 Human 例外扩大到本终端或发布动作。

必须具名评估：O-1（有 avg、无 quote 时滑点仍为 `—`）、O-4（drain 的合约终态规则可能永久
保留未知 notional）及其实际影响/重开条件；O-2 旧 tooltip/注释与新口径相反，已排入本阶段
合并/发布前文本同步，尚未完成。历史 JSTUSDT 行不会因重启自动回填，补录须单独 Human 授权。

## Allowed Files

- 全部只读：`AGENTS.md`、`PROJECT_STATE.md`、`reports/agent-runs/ACTIVE.json`、本 dispatch、
  `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json`、`agents/roles.md` 的 Reviewer
  与 Task Handoff Evidence Contract 相关段落、`agents/skills/reality-checker.md`。
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
  `db552a7b224fcebc84bb23a087ff2b28a350bf04`。受审产品事实须使用
  `git show <sha>:<path>` / `git diff <base>..<delivery>`；工作区两个未提交前端文件不属于交付。
- 唯一 create-only 写权限：
  `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/04-review-2.handoff.md`
- Bookkeeper 预检：
  `test ! -e reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/04-review-2.handoff.md`
  已通过（`handoff_preflight=absent`）。若执行时已存在，立即阻塞，不得覆盖。
- 不得修改代码、测试、现有证据、status、PROJECT_STATE、Git 或未提交前端文件；测试须禁用 repo
  内 bytecode/cache 写入；不得读取或写入实盘数据库，不得控制服务、订单或资金动作。

## Inputs

按以下顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/04-review-2.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json`
6. `agents/roles.md` 的 Reviewer 与 Task Handoff Evidence Contract 相关段落
7. `agents/skills/reality-checker.md`
8. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/01-plan-review-retry.handoff.md`
9. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/02-implement.handoff.md`
10. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/03-review-1.handoff.md`
11. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/03-review-1-retry.handoff.md`
12. 固定 SHA 的源码、测试与 diff

## Acceptance Checks

1. `pass|fail`：独立核对 Human 需求与实际公式、正负号、四向腿映射及四位输出完全一致。
2. `pass|fail`：JSTUSDT `0.2316/-0.2192`、零价差、跨 attempt 与缺腿降级证据足以证明实际效果。
3. `pass|fail`：固定 delivery、schema/API/caller 边界与两级测试证据可信，未把控制提交或工作区
   未提交前端改动当成交付。
4. `pass|fail`：评估 O-1/O-4 的当前可达性、fail-closed 效果、用户影响、重开条件与是否阻塞发布。
5. `pass|fail`：确认 O-2 旧口径文案尚未同步，明确其合并/发布 gate；不得把 review ACCEPT 解释为
   文案已修复。
6. `pass|fail`：确认历史 close-log 不会被本次代码自动重算，重启不会回填 JSTUSDT，补录仍需
   独立 Human 授权与备份/行级核验。
7. `pass|fail`：无订单、资金、数据库写入、服务控制、部署或风险参数副作用；给出实际发布就绪结论。
8. `pass|fail`：发现按范围三分类并附证据；新假设满足 Scenario Admission；明确最终
   `ACCEPT|REWORK` 及 Human 仍需决定的事项。

## Stop

只读完成 review-2，创建且仅创建指定 handoff；Reviewer handoff 的 `delivery_sha` 必须固定为
`db552a7b224fcebc84bb23a087ff2b28a350bf04`。输出合规 `[TASK_RESULT v2]` 及明确
`评审结论: ACCEPT（接受）|REWORK（返工）`、问题记录、修复要求，然后停止。不得启动下一模型、
修改文本同步项或执行任何实盘/发布动作。
