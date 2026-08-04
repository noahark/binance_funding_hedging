Identity:
- task_id: `plan-review-dual-ledger-flow-log-v1`
- target_role: `Reviewer`（计划评审，只读）
- target_model: `deepseek`
- provider: `deepseek`
- status_revision: `3`
- required_skill: `agents/skills/software-architect.md`

Goal

按 `AGENTS.md` §8「计划评审」与设计 `docs/planning/2026-08-04-dual-ledger-flow-log-design.md` §17.3，对「双栏流水日志」的**设计定稿 v1.1 与三份实现 dispatch** 做一次独立的、跨 provider 的只读计划评审，判断实现开始前计划是否成立。HIGH_RISK（资金流水/PnL/账务语义 + 本地账本 + 定时上游拉取）：评审不过则实现不得开始。

**必须回答的七个问题（设计 §17.3）**：

1. 「本次新增」按**入库时间**归属、且手动刷新不移动基准——该口径在资金费**分批/延迟到账**下是否可能给出误导数字？3 小时重叠回拉窗口是否够？
2. `coverage` 护栏是否足以防止「本地没拉到」被读成「交易所没发生」？
3. 幂等键（`txId` / `(incomeType, tranId)`）与「已存在的行绝不覆盖」是否足以保证增量不重复计数？
4. 定时线程「每 20 秒醒一次 + 当前自然小时是否已有成功 run」的判据，在重启、时钟跳变、休眠唤醒下是否有漏跑或重复跑？
5. 三个任务（A 取数与账本 → B 调度与接口 → C 前端）的文件边界是否真的零重叠？B 对 A 的接口依赖是否已在设计 §14/§16 写死？
6. 金额全程 TEXT + Python `Decimal`、禁止 SQL 聚合——是否有遗漏的精度泄漏点？
7. 定时上游拉取相对既有「上游 I/O 归 snapshot worker」约定新增了独立调度线程（借币调度器已有同类先例）——该边界是否可接受？

另请核查（评审者视角补充，不限于七问）：冻结接口契约 `private-ledger/v2`（设计 §13）在 `GET` 纯读本地库 / `POST refresh` 手动触发、ID 字符串化、缺失即 `null` 不造 0、`*_total` 含不可解析行即为 `null`、`row_limit_applied` 与全量 `row_count`/`summary` 并存、`coverage.complete=false` 如实下发等硬规则上是否有自相矛盾或实现时必撞的坑；需求 1 的按钮移动（设计 §11）是否会破坏既有 self-check 或 `#private-pm-source-time` 的位置约定。

Allowed Files

- 只读：受审对象 `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（§11–§18）与三份实现 dispatch（`backend-ledger-store-fetch-v1`、`backend-ledger-schedule-api-v1`、`frontend-dual-ledger-flow-log-v1`）
- 只读参考：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/plan-dual-ledger-flow-log-v1.handoff.md`（计划作者勘误后的交付事实）、两份 recon、`backend/services/private_client.py`、`backend/services/snapshot_service.py`、`backend/app/server.py`、`backend/borrow_tasks/scheduler.py`、`frontend/index.html`、`frontend/self-check.js`
- 唯一可写：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-review-dual-ledger-flow-log-v1.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`，结果为通过；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件，只含你自己的结论与证据路径）
- **不得**修改：任何受审设计/代码/测试/其他 packet、`status.json`、`PROJECT_STATE.md`、git 提交

Inputs

- `AGENTS.md`（§3 安全内核、§7 任务结果协议、§8 评审规则与范围三分类）
- `agents/roles.md` 的 Reviewer 章节与 Task Handoff Evidence Contract 章节
- `agents/skills/software-architect.md`
- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（§11–§18，受审主体）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-store-fetch-v1.dispatch.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-schedule-api-v1.dispatch.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/frontend-dual-ledger-flow-log-v1.dispatch.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/plan-dual-ledger-flow-log-v1.handoff.md`
- `reports/api-samples/2026-08-borrow-interest-history-recon-v1/20260804T0008Z/recon.md`、`reports/api-samples/2026-08-um-income-funding-recon-v1/20260804T0015Z/recon.md`

Acceptance Checks

1. 逐条回答 Goal 的七个必答问题 + 补充核查，每项给出明确判断与依据（引用 文件:行号 或 § 号）。
2. 每条发现按 `AGENTS.md` §8 标注范围三分类（`in-range` / `pre-existing-independent` / `pre-existing-release-critical`，后者须附引入提交引用）；计划评审对象是设计+packet，代码问题若在 `base_sha`（`dc4cc6d`）前已存在须按范围外标注。
3. 对每条问题标注严重度（阻塞实现 / 建议修改 / 观察）；阻塞项须给出可执行的修改要求。
4. 结论：`评审结论: ACCEPT（接受） | REWORK（返工）`，附 `问题记录: <path | none>` 与 `修复要求: <path | none>`（按 `AGENTS.md` §7）。计划评审的 `REWORK` 表示 packet 需修订后才可实现，**不计入 `rework_count`**；verdict 返回 Planner（经 Human 转交 Bookkeeper 落盘）。
5. 创建唯一交接件 `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-review-dual-ledger-flow-log-v1.handoff.md`（Source Report + Human Brief，含 `TASK_RESULT v2` 与三行中文交接；`delivery_sha` 写 `none`）；控制台回执与 Human Brief 一致。
6. 全程只读：不修改受审对象、不启动其他终端、不访问网络、不读凭据、不做实盘操作。

Stop

评审是只读的；唯一写是创建上述 create-only 交接件。不改代码、不改设计、不改 packet、不改 `status.json`、不建分支、不提交。不替 Human 做合并/部署/实盘决策。评审完成后停止，等待 Human 把 verdict 转交 Bookkeeper。
