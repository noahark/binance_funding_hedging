Identity:
- task_id: smooth-open-plan-repair-opus5
- target_role: Planner
- target_model: claude-opus-5
- provider: anthropic
- status_revision: 10
- required_skill: agents/skills/task-planner.md

Goal

对 `docs/planning/smooth-open-orders-v1-development-checklist.md` 做一次最小、定向的计划返修，关闭 DeepSeek 正式计划评审的 R1/R2/R3，并落实 Human 最新开发路由决定：**不再拆成 A/B/C/D 多终端任务，由一个 `gpt-5.6-sol`、reasoning `xhigh`、provider `openai` 的 Implementer 在一个独立 worktree/分支内完成平滑开单 V1 的 provider、gate/store、worker/API 与前端真实接线。**

这是规划修订，不授权实现、创建 worktree/分支、安装 CCXT、连接网络、启动服务、下单、合并或部署。不要重新设计 Human 已冻结的产品语义，不做全文重写，不增加协调框架。把旧的并行拓扑、四任务包、四 worktree、cherry-pick 流程和三份启动文稿从**活动方案**中删除或明确作废，形成一个单 owner、单 `current_task`、单交付区间的可执行计划。

Allowed Files

- `docs/planning/smooth-open-orders-v1-development-checklist.md`

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/07-smooth-open-plan-repair-opus5.dispatch.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`（必须核对 revision `10`、本 task_id、`base_sha=2e5902347c5f0ac81638c67dc7a1bf20a9141ac9`）
- `agents/roles.md` 的 Planner 段；为修 R1/R3，按需读取 Task Handoff Evidence Contract 与 Bookkeeper 段的 Minimal State、Task State、SHA Discipline、Required Behavior
- `agents/skills/task-planner.md`
- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-formal-plan-review-deepseek-v4-pro.handoff.md`
- `docs/planning/smooth-open-orders-v1-development-checklist.md`
- `docs/planning/smooth-open-orders-v1.md`
- 为修 R2 只读固定代码事实：`backend/hedge_open_tasks/store.py` 的 `set_task_status`、`pause_task`、`stop_task_fatal`，以及 `backend/hedge_open_tasks/service.py` 的 `_pause_task_local`、`_stop_task_fatal_preflight`、`_dispatch_one_for_task`
- 原计划已列出的 provider/API/frontend 源码与测试，只在核对单任务 Allowed Files、命令和依赖顺序时按需读取；不要扩展到无关文件

Acceptance Checks

- pass: 原样保留 Human 冻结的 `bookTicker/watchBidsAsks` 一档、signed threshold 严格 `>`、两腿各 80% 覆盖、每轮 5 分钟、timeout 回退既有立即链、`成交1次` 仅放行当前 gate、两腿异步提交并同步等返回、立即/单腿后续复用等产品语义。
- pass: 把活动实施拓扑改为**一个** `gpt-5.6-sol` reasoning `xhigh` Implementer、一个 worktree、一个分支、一个 dispatch、一个 `status.json.current_task` 和一个 handoff；不存在第二个同时在途 implementation task，因此 R1 不再依赖 handoff 替代在途状态，也不新增状态数组、并行 ledger 或新 schema。
- pass: 单 Implementer 的任务覆盖原 A+B+C+D 的完整必要范围，但仍以内部实现顺序说明依赖：先 provider 与 gate/store，再 worker/API，最后前端真实接线；这些只是同一任务内 checkpoint，不是独立 dispatch、stage、owner 或并行工作流。
- pass: 给出一个精确 task_id（建议 `smooth-open-v1-fullstack-gpt56sol-xhigh`）、目标模型/provider/reasoning、唯一 worktree/branch 占位符、唯一 committed input SHA、完整 Allowed Files 联集、明确 forbidden files、唯一 handoff 路径、一个本地 delivery commit 与全量验收命令。实现者可按 Harness 仅把自己的 status 从 `dispatched` 改为 `reported`，不得写 `verified` 或选择后继模型。
- pass: R2 必须按真实代码修正。删除“`set_task_status` 是全仓唯一状态迁移收口”的错误结论；明确枚举至少 `set_task_status`、`pause_task`、`stop_task_fatal` 三条 `running → 非 running` 写路径，并要求每条**仅在其状态 UPDATE 成功时**于同一 SQLite 事务清空 `smooth_gate_seq`、`smooth_gate_started_at_us`、`smooth_gate_force_requested`。保留 `clear_smooth_gate` 只处理 task 仍 `running` 但 Start gate 关闭。
- pass: 为 R2 增加确定性回归：有活动/已 force gate 的 smooth task 经 `pause_task` 后三列清空，Human resume 后同一未调度 seq 建立新的 started_at 与完整 5 分钟窗口且 force=False；`stop_task_fatal` 和 `set_task_status(non-running)` 同样清空；条件 UPDATE 因 delete/done 竞争未命中时不得误清或复活状态；immediate 路径零行为变化。
- pass: R3 通过取消跨分支集成自然关闭：Bookkeeper 只核验 handoff/commit/tests、固定 `base_sha..delivery_sha`、准备 review dispatch；不得创建集成分支、cherry-pick 或合出交付。单 Implementer 直接在唯一 implementation branch 上形成 delivery commit，不再出现“C 唯一集成者”与 Bookkeeper 集成的双 owner。
- pass: 把旧 A/B/C/D 四包、四 worktree、分阶段 cherry-pick 和三份 Human 启动文稿从活动计划中删除或放入一句明确的“已由 Human 决定作废”历史说明；不得让后续模型在新旧两套方案中选择。
- pass: 生成一份新的、单终端、copy-ready 但 `INACTIVE` 的 Human 启动文稿草案。必须写明 `gpt-5.6-sol` + `xhigh`、唯一 worktree/branch/base SHA/status revision/dispatch 占位符、禁止安装依赖/联网/启服务/读凭证/下单/push/merge、只改 Allowed Files、完成 fake/确定性回归、写唯一 handoff、提交一个本地 delivery commit并停止。占位符仅在修订计划评审 ACCEPT 且 Human 授权实现后由 Bookkeeper 填充。
- pass: 保留 provider/gate/API/frontend 的最小跨层契约和原 P0→P1 验收，不因改成单 owner 删除资金安全门；可以删除只为跨任务协作而存在的 owner/consumer、接口冻结、cherry-pick、冲突检查和兼容说明。
- pass: 顺手关闭 DeepSeek 非阻塞 O1–O3，但不扩范围：`latest` 契约钉死一种返回语义；provider 放 `services/` 的纯度依据引用准确；明确生产 provider 缺失时 smooth 创建 400 与测试注入 fake provider 可创建 smooth 的区别。
- pass: 更新正式计划复核请求为**仅针对本轮改动的定向复核**：逐条核验 R1/R2/R3 已关闭、新单任务 Allowed Files/验收无缺口、Human 冻结语义未回归；不要再次要求从零做一轮大而全设计评审。结论仍须 `ACCEPT | REWORK`，因为 `AGENTS.md` 对 HIGH_RISK 的计划评审门仍生效。
- pass: 运行 `git diff --check`；只修改唯一 Allowed File。返回合规中文 `[TASK_RESULT v2]`。Planner 不创建 handoff、不提交、不改 status、不准备真实实现 worktree/dispatch、不发送模型。

Stop

完成上述定向改稿、单 Implementer 活动方案、单终端 INACTIVE 启动文稿和定向复核请求后停止。不得实施代码、创建 worktree/分支、安装依赖、连接行情或订单接口、启动服务、修改状态、提交、发送其他模型、合并或部署。
