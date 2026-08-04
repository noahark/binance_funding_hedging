Identity:
- task_id: `plan-review-r2-dual-ledger-flow-log-v1`
- target_role: `Reviewer`（计划评审，只读）
- target_model: `deepseek`
- provider: `deepseek`
- status_revision: `5`
- required_skill: `agents/skills/software-architect.md`

Goal

按 `AGENTS.md` §8「计划评审」与设计 `docs/planning/2026-08-04-dual-ledger-flow-log-design.md` §17.3，对**修订后的设计定稿 v1.2 与修订后的三份实现 dispatch** 做第二轮独立、跨 provider 只读计划评审。第一轮（`plan-review-dual-ledger-flow-log-v1`）verdict 为 `REWORK`，F1–F6 已由 Planner 在 v1.2 逐条修订。本轮对象为**修订增量**：F1–F6 的落实、两处具名偏离、O1–O8 落档、A/B packet 措辞对齐。HIGH_RISK：本轮 `ACCEPT` 前实现不得开始。

**必须额外确认的三件事（设计 §17.3 新增，第一轮没有）**：

1. **F6(b) 具名偏离**：设计 §15.2 未采纳评审第一轮的「截断即整栏丢弃、不提交明细」推荐，改为「提交已拉行 + coverage 只推进到『已证明连续覆盖』处 + 左栏（interestHistory 降序，缺口在旧端）记空洞、右栏（um/income 升序，缺口在新端）`coverage_end = newest_fetched_ms` 不记空洞、下一轮自动续拉」。Planner 理由：整栏丢弃会造成「同一窗口每轮截断、每轮丢弃、数据永远落不了库」的不可自愈停滞。此偏离是否成立？左右两栏按返回顺序分开的规则是否正确？
2. **v1.2 新引入的分源 coverage**（§13.2 规则 7 / §15.2）：按源分别记账（`coverage.by_source` + `coverage.gaps` 空洞列表），聚合取两源交集。是否真的消除了「一栏连续失败 >3 小时而另一栏照常推进」的静默空洞？聚合取交集是否在正常运行时产生过度告警？
3. **空态与三态判定表**（§13.2 规则 13/14 + `scheduler_enabled`）：空库空态形状（`last_run: null`、coverage 三值 null/false、`delta.complete: false`、`scheduler_enabled` 区分「没开通道」与「真没流水」）加上五行三态判定表后，前端是否已确定性可判、无歧义分支？

**必须按 v1.2 复核的第一轮七问**（§17.3 下段，逐条复核修订后是否仍成立，重点核对 F1–F6 是否真的消除了原缺口）：

1. 「本次新增」按入库时间、手动刷新不移动基准——资金费分批/延迟到账下是否误导？3 小时重叠窗口够不够（结合 v1.2 的 `pending_tail_ms` 与「尽力而为捕获边界」§17.4）？
2. `coverage` 护栏（v1.2 分源 + gaps + `complete` 判定重写 + `pending_tail_ms` 不参与判定）是否足以防止「本地没拉到」被读成「交易所没发生」？
3. 幂等键与「已存在的行绝不覆盖」是否保证增量不重复计数（含 v1.2 F1 事务模型下「run 记录必落库 + 明细按栏各自事务」是否破坏该保证）？
4. 定时线程判据在重启/时钟跳变/休眠唤醒下是否漏跑或重复跑（v1.2 无变化，按 v1.2 复核）？
5. 三任务文件边界是否仍零重叠（v1.2 §16 已注明 status.json 语义例外；B 对 A 依赖经 A 交接件列公开签名传递）？
6. 金额 TEXT + Decimal、禁止 SQL 聚合——v1.2 增加 `localcontext(prec ≥ 40)` 后有无遗漏泄漏点？
7. 独立调度线程边界是否可接受（v1.2 无变化）？

另请核查：A/B packet 修订后与设计 §13.2/§13.5/§14/§15.2/§15.3/§15.4 措辞是否一致（验收项、硬规则、响应字段名如 `by_source`/`gaps`/`pending_tail_ms`/`scheduler_enabled`）；C packet 的 pre-dispatch correction（Bookkeeper 已按 §13.7 待办框补齐覆盖文案分情形渲染）是否与设计 §13.7 一致；F1 事务模型「run 记录必落库 + 明细按栏各自事务 + 禁止两源明细绑同一事务」是否可被 A/B 的存储层实现且不产生半截账；F2 连续失败计数（含 `disabled` 不计）是否确定可判。

Allowed Files

- 只读：受审对象 `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（定稿 v1.2，§11–§18 与 §10 修订记录）与三份实现 dispatch（A/B 修订后、C 含 Bookkeeper 的 pre-dispatch correction）
- 只读参考：第一轮评审交接件 `evidence/plan-review-dual-ledger-flow-log-v1.handoff.md`（F1–F6 原文与修改要求）、修订交接件 `evidence/plan-revise-dual-ledger-flow-log-v1.handoff.md`（含 Bookkeeper Verification）、`evidence/plan-dual-ledger-flow-log-v1.handoff.md`、两份 recon、相关代码只读（`backend/services/private_client.py`、`backend/services/snapshot_service.py`、`backend/app/server.py`、`backend/borrow_tasks/scheduler.py`、`frontend/index.html`、`frontend/self-check.js`）
- 唯一可写：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-review-r2-dual-ledger-flow-log-v1.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`，结果为通过；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件，只含你自己的结论与证据路径）
- **不得**修改：任何受审设计/代码/测试/其他 packet、`status.json`、`PROJECT_STATE.md`、git 提交

Inputs

- `AGENTS.md`（§3 安全内核、§7 任务结果协议、§8 评审规则与范围三分类）
- `agents/roles.md` 的 Reviewer 章节与 Task Handoff Evidence Contract 章节
- `agents/skills/software-architect.md`
- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（v1.2，§13/§14/§15/§17.3/§17.4 为重点）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-review-dual-ledger-flow-log-v1.handoff.md`（第一轮）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-revise-dual-ledger-flow-log-v1.handoff.md`（修订事实）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-store-fetch-v1.dispatch.md`、`backend-ledger-schedule-api-v1.dispatch.md`、`frontend-dual-ledger-flow-log-v1.dispatch.md`
- `reports/api-samples/2026-08-borrow-interest-history-recon-v1/20260804T0008Z/recon.md`、`reports/api-samples/2026-08-um-income-funding-recon-v1/20260804T0015Z/recon.md`

Acceptance Checks

1. 逐条回答 Goal 的「三个确认问题」与「按 v1.2 复核的七问」+ 补充核查，每项给出明确判断与依据（引用 § 号或 文件:行号）。
2. 每条发现按 `AGENTS.md` §8 标注范围三分类（`in-range` / `pre-existing-independent` / `pre-existing-release-critical`，后者须附引入提交引用）；本轮对象是修订增量，第一轮已确认的事实不必重复长述，只复核修订是否闭环。
3. 对每条问题标注严重度（阻塞实现 / 建议修改 / 观察）；阻塞项须给出可执行的修改要求。
4. 结论：`评审结论: ACCEPT（接受） | REWORK（返工）`，附 `问题记录: <path | none>` 与 `修复要求: <path | none>`。计划评审 REWORK 不触 `rework_count`；verdict 返回 Planner（经 Human 转交 Bookkeeper 落盘）。
5. 创建唯一交接件 `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-review-r2-dual-ledger-flow-log-v1.handoff.md`（Source Report + Human Brief，含 `TASK_RESULT v2` 与三行中文交接；`delivery_sha` 写 `none`）；控制台回执与 Human Brief 一致。
6. 全程只读：不修改受审对象、不启动其他终端、不访问网络、不读凭据、不做实盘操作。

Stop

评审是只读的；唯一写是创建上述 create-only 交接件。不改代码、不改设计、不改 packet、不改 `status.json`、不建分支、不提交。不替 Human 做合并/部署/实盘决策。评审完成后停止，等待 Human 把 verdict 转交 Bookkeeper。
