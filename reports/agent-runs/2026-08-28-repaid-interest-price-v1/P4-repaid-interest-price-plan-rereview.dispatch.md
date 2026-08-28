# P4 — Repaid interest price plan re-review

Identity:
- task_id: `P4-repaid-interest-price-plan-rereview`
- target_role: `Reviewer`
- target_model: `opus5`
- provider: `anthropic`
- status_revision: `8`（由 Bookkeeper 修订 `status.json` revision 8 指向本 packet 时生效）
- required_skill: `agents/skills/reality-checker.md`

Goal:
- 实现前只读计划复评（AGENTS.md §8 计划评审门第二轮）：核验
  `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`
  （P3 修订版）是否逐项解决了 P2 handoff 的 F1-F4（均 in-range）、具名 O1-O3，
  并落实 Human 两项固定决定，且未引入新缺陷。verdict 返回 Planner，不触碰
  `rework_count`。本任务属 HIGH_RISK（money/PnL meaning、accounting）。
- Human 固定口径（复评不得改写）：
  1. 部分还款绝不锁价；只要资产仍有借款持仓/未偿余额，所有相关历史利息继续按
     当前价动态折 U；只有可确认借款完全归零时，才按该次完全还款时价格切终态；
     资本化不是结清证据。
  2. F2 路径 A：成功还款返回后立即尝试读取内存快照现货买一价；整个取价/解析
     必须异常隔离，`SnapshotNotReady` 或任何异常只能留下 NULL，绝不能让
     `store.resolve` 的还款终态落库被跳过；该价格只能称为捕获时刻快照买一价，
     不是真实还款成交汇率。
  3. 既有口径不变：未匹配利息当前价动态暂估；还款切换恰一次、其后稳定；禁止
     计提时冻价；无可靠价格 fail-closed；不得为 STORJ 虚构平仓单关系。
- 复评重点（不限于）：修订版 §3.1 归零证据判定
  （`repay_after_borrowed`/`repay_after_interest` 均解析为 0）是否确定、可审计、
  且对部分/反复/同毫秒/`unknown`/`failed`/历史行（含 STORJ）形态完备；
  §3.2.1 双独立异常边界是否在字面上排除「resolve 被跳过」的路径；
  §3.2.2 归零推定 a/b/c 是否存在假终态或不可达分支；§3.4 `list_records()` 形状
  是否让回退结算时刻真正可达；5 列 additive 迁移、NULL-only 幂等回补、回滚、
  双消费者单一折算权威是否一致；§5 测试（尤其 2/3/4/16）是否真能锁住上述性质；
  修订是否为解决 F1-F4 而扩出了无当前证据支撑的范围（§1 Scenario Admission）。
- 发现须按 AGENTS.md §8 范围三分类标注。

Allowed Files:
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P4-repaid-interest-price-plan-rereview.handoff.md`
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
  （八条 Acceptance Checks 为基准）
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/P3-repaid-interest-price-plan-revision.dispatch.md`
  （本修订的任务边界与验收）
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P2-repaid-interest-price-plan-review.handoff.md`
  （F1-F4 原文、O1-O3、Human 决定记录——含其 Errata 段）
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`
  （受审 P3 修订版；其 §9 为发现解决对照表）
- `backend/app/server.py` — margin repayment, PnL series, and position paths
- `backend/margin_repay/store.py`
- `backend/services/hedge_open_live_client.py` — repayment response contract
- `backend/services/private_client.py` — `fetch_unified_balances(force=...)` 契约
- `backend/services/snapshot_service.py` — snapshot readiness/error behavior
- `backend/domain/snapshot.py` — quote freshness and debt/balance fields
- `backend/ledger_flow/domain.py`
- `backend/ledger_flow/service.py`
- `backend/ledger_flow/store.py`
- `backend/tests/test_ledger_flow_domain.py`
- `backend/tests/test_ledger_flow_service.py`
- `backend/tests/test_margin_repay.py`
- `docs/api/public-market-contract.md`

Acceptance Checks:
- `pass`: 评审为只读全新会话；唯一写入是上述 create-only handoff 文件，结构完整
  符合 Task Handoff Evidence Contract——特别注意 `## Human Brief / Console Receipt
  Source` 区块内须包含完整的 `[TASK_RESULT v2]` 起始标记与 `[/TASK_RESULT]` 最终
  闭合标记（P2 曾因缺此标记被 Bookkeeper 拒收），且 `BOOKKEEPER_APPEND_ONLY`
  标记之前的作者区不得含该标记原文以外的重复。
- `pass`: verdict 明确为 `ACCEPT` 或 `REWORK`；逐项给出 F1/F2/F3/F4 是否已解决
  （引用修订版章节），`REWORK` 时每条新发现带范围三分类与证据锚点、修复要求
  落到具体章节。
- `pass`: 明确核对 Human 两项决定被忠实落实：部分还款不锁价（含测试断言存在）、
  归零才切终态、资本化表述已改、F2 双异常边界与「resolve 无条件执行」在计划
  字面上成立、价格命名为捕获时刻快照买一。
- `pass`: 核对 O1-O3 已具名且未因此扩围；修订版仍满足 P1 dispatch 八条
  Acceptance Checks 与 P3 dispatch 八条 Acceptance Checks。
- `pass`: 对修订版新增设计（归零证据列、`fetch_unified_balances(force=True)`
  缺席语义、回补推定 a/b/c、`list_records()` 形状、5 列迁移）独立核实其代码
  依据，不接受计划自述。
- `pass`: 回执含 `评审结论`、`问题记录`、`修复要求` 字段，`下一步任务` 使用
  「读取：…；执行：…；关卡：…」形式；handoff 引用的路径全部存在。

Stop:
- 评审完成、handoff 创建、控制台回执输出后停止。不实现、不修复、不改
  `status.json` / `PROJECT_STATE.md`、不提交、不发送其他终端、不接触生产或凭据。
  verdict 经 Bookkeeper `gpt-5.6-sol`（label `codex`）核验后由 Human 决定是否
  进入实现 dispatch。
