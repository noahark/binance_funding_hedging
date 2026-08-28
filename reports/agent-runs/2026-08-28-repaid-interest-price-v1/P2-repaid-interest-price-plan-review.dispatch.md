# P2 — Repaid interest price plan review

Identity:
- task_id: `P2-repaid-interest-price-plan-review`
- target_role: `Reviewer`
- target_model: `opus5`
- provider: `anthropic`
- status_revision: `3`（由 Bookkeeper 修订 `status.json` revision 3 指向本 packet 时生效）
- required_skill: `agents/skills/reality-checker.md`

Goal:
- 实现前只读计划评审（AGENTS.md §8 计划评审门）：审查
  `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`
  是否是可实施、可验证、与 Human 固定口径一致的最小方案。本任务属 HIGH_RISK
  （money/PnL meaning、accounting）；verdict 返回 Planner，不触碰 `rework_count`。
- Human 固定口径（不可被方案或评审改写）：未匹配成功还款的利息按当前价格动态
  暂估；匹配到成功还款的利息切换为还款时价格的终态固定成本；还款时历史重算
  一次是预期结算动作；禁止把利息计提时冻价当默认或回退；无可靠适用价格时净
  收益保持不可用（fail-closed）；不得为 STORJ 之类无对冲周期的资产虚构平仓单
  关系。
- 评审重点（不限于）：匹配规则的确定性与领域证据（时间 FIFO 依赖「一次成功
  还款结清当时已计提利息」，计划 §8.1）；还款时价格两来源（快照买一 / 公共
  1m K 线回补）的可审计性与一致性；`amount="0"`、`repaid_amount` 缺失、
  `unknown` 的字段语义是否被如实使用而非臆造；两消费者（持仓视图与 PnL 曲线）
  是否真正共用单一折算权威；schema 迁移/回补/回滚的最小性与幂等；测试清单
  是否覆盖 P1 派单要求的全部场景且可执行；前端零改动判断是否成立。
- 发现须按 AGENTS.md §8 范围三分类标注；新假设场景阻塞须满足 §1 Scenario
  Admission。

Allowed Files:
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P2-repaid-interest-price-plan-review.handoff.md`
  （create-only：Bookkeeper preflight `test ! -e` 已记录该路径不存在；存在即失败。
  评审者除本文件外零写入。）
- No source, test, schema, state, project-state, documentation, database,
  production, or commit changes.

Inputs:
- `AGENTS.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/status.json`
- `agents/roles.md` — Reviewer 段与 Task Handoff Evidence Contract 段
- `agents/skills/reality-checker.md`
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/P1-repaid-interest-price-plan.dispatch.md`
  （P1 验收标准是本评审的核对基准）
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`
  （受审计划）
- `backend/app/server.py` — `_handle_pnl_series`、`_hedge_open_positions`、
  `_handle_margin_repay_post`、`_dispatch_margin_repay`
- `backend/ledger_flow/domain.py` — `build_pnl_series`
- `backend/ledger_flow/service.py` — `sum_interest_by_asset`
- `backend/ledger_flow/store.py`
- `backend/margin_repay/store.py`
- `backend/hedge_open_tasks/service.py` — `_finalize_close_task`（计划 §3.3
  声明不触碰，需核实该声明）
- `backend/tests/test_ledger_flow_domain.py`
- `backend/tests/test_margin_repay.py`
- `frontend/self-check.js` — 既有 PnL incomplete/display 检查（98d 段）
- `docs/api/public-market-contract.md` — v0.17 Margin Repay、v0.12 flow-log、
  v0.21 net_pnl 章节

Acceptance Checks:
- `pass`: 评审为只读全新会话；唯一写入是上述 create-only handoff 文件，结构符合
  Task Handoff Evidence Contract（Source Report / Required Reading / Human Brief、
  `BOOKKEEPER_APPEND_ONLY` 标记）。
- `pass`: verdict 明确为 `ACCEPT` 或 `REWORK`；`REWORK` 时每条发现带范围三分类
  标注与证据锚点，修复要求可执行并落到计划文档的具体章节。
- `pass`: 明确核对并逐项回答计划是否满足 P1 dispatch 的八条 Acceptance Checks
  （确定性匹配规则、还款时价格权威定义与历史证据、终态稳定与单一折算权威、
  迁移/回补/回滚、bounded 文件清单与可执行测试、切换恰一次断言、评审派单本身、
  零生产改动）。
- `pass`: 对计划 §8 列出的五个风险焦点给出裁定（同意/反对及理由），特别是
  §8.1 时间 FIFO 匹配的领域证据是否充分。
- `pass`: 回执含 `评审结论`、`问题记录`、`修复要求` 字段，`下一步任务` 使用
  「读取：…；执行：…；关卡：…」形式；handoff 引用的路径全部存在。

Stop:
- 评审完成、handoff 创建、控制台回执输出后停止。不实现、不修复、不改
  `status.json` / `PROJECT_STATE.md`、不提交、不发送其他终端、不接触生产或凭据。
  verdict 经 Bookkeeper `gpt-5.6-sol`（label `codex`）核验后由 Human 决定是否
  进入实现 dispatch。
