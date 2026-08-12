Identity:
- task_id: smooth-open-plan-micro-repair-opus5
- target_role: Planner
- target_model: claude-opus-5
- provider: anthropic
- status_revision: 14
- required_skill: agents/skills/task-planner.md

Goal

对 `docs/planning/smooth-open-orders-v1-development-checklist.md` 做一次两处微型返修，只关闭 DeepSeek 定向复核的 T1/T2。不得重写、重排或重新评估任何其他内容；R1/R3、单 Implementer 方案、Human 冻结语义与 O1/O2/O3 已通过，不得重开。本轮是实现前计划修订，不增加 `rework_count`，也不授权实现或外部动作。

Allowed Files

- `docs/planning/smooth-open-orders-v1-development-checklist.md`

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/09-smooth-open-plan-micro-repair-opus5.dispatch.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`（核对 revision `14`、本 task_id、`base_sha=55008d30f4a0673112b7593adf7bef9e9dc46532`）
- `agents/roles.md` 的 Planner 段
- `agents/skills/task-planner.md`
- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-targeted-plan-rereview-deepseek-v4-pro.handoff.md`（只读 T1/T2 与 Required Reading）
- `docs/planning/smooth-open-orders-v1-development-checklist.md`

Acceptance Checks

- pass: **只改 T1**：把 §4.2.4 第 5 条改成可抓住错误实现的非空 sentinel 测试。先将 task 置为 `deleted`/`done`/`stopped` 终态，再由 test fixture 在同一个隔离 test DB 中直接写入三个明确非空 sentinel（例如 `smooth_gate_seq=777`、`smooth_gate_started_at_us=123456789`、`smooth_gate_force_requested=1`），分别调用 `pause_task` 与 `stop_task_fatal`，断言条件 UPDATE 未命中、status 不变、三个 sentinel 逐值保持。必须说明直接 SQL 只用于构造原本由正常 API 不会产生的观察态，以证明 miss 分支完全不写；不得以三个 NULL 作断言。
- pass: **只改 T2**：把 §6 表格“维护者”一句改成唯一口径：本交付由当前获 dispatch 的 Implementer 创建；此后任何依赖变更也只能由获专门 dispatch 的 Implementer 修改；Bookkeeper 只核验和记账，绝不修改 `requirements.txt`。生产安装仍须 Human 单独授权，其他行不变。
- pass: 除 §4.2.4 第 5 条与 §6“维护者”单元格外不改变任何正文、字段、验收、角色、路径、版本、启动文稿或停止线。不要处理非阻塞 T-O1；正式实现 dispatch 会以 Allowed Files 为准明确 status 权限。
- pass: `git diff --word-diff=plain` 能清楚显示只有上述两处语义改动；`git diff --check` 无输出；只修改唯一 Allowed File。
- pass: 返回合规中文 `[TASK_RESULT v2]`。Planner 不创建 handoff、不提交、不改 status、不创建 worktree/分支、不安装依赖、不联网、不启服务、不发送模型。

Stop

两处文字修订和 `git diff --check` 完成后立即停止。不得实施代码、扩大规划、修改状态、提交、发送其他模型、安装依赖、联网、启动服务、下单、合并或部署。
