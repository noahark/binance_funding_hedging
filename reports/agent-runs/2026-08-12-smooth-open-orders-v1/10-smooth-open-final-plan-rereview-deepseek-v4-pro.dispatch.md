Identity:
- task_id: smooth-open-final-plan-rereview-deepseek-v4-pro
- target_role: Reviewer
- target_model: deepseek-v4-pro
- provider: deepseek
- status_revision: 16
- required_skill: agents/skills/code-reviewer.md

Goal

对平滑开单 V1 计划的最后两处微型返修做一次最终、只读、两点复核：T1 非空 sentinel 回归是否可抓住条件 UPDATE 未命中却误清 gate 的错误实现；T2 是否已明确依赖文件只能由获 dispatch 的 Implementer 修改、Bookkeeper 只核验。除此之外不得重开任何结论。

上一轮已明确通过 R1、R3、单 Implementer 任务范围、Human 冻结语义及 O1/O2/O3，R2 的四路径穷举与第四路径豁免也已通过。本轮返修作者为 Opus 5（provider `anthropic`），复核者为 DeepSeek V4 Pro（provider `deepseek`），跨 provider 成立。本轮不授权实现、worktree/分支、依赖安装、联网、服务控制、下单、提交、集成、合并或部署。

Allowed Files

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-final-plan-rereview-deepseek-v4-pro.handoff.md`（唯一允许写入；create-only）

除创建上述唯一 handoff 外完全只读。不得修改计划、源码、既有 evidence、`status.json`、`ACTIVE.json`、`PROJECT_STATE.md`；不得调用其他模型或执行任何外部动作。

Bookkeeper 已执行 create-only 预检：

```text
test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-final-plan-rereview-deepseek-v4-pro.handoff.md
exit 0（路径不存在，可由本复核创建）
```

Inputs

固定受审范围：

- `base_sha`: `55008d30f4a0673112b7593adf7bef9e9dc46532`
- `delivery_sha`: `ad887db6157d74359d28b31c36e936125c746850`
- 唯一计划差异：`git diff 55008d30f4a0673112b7593adf7bef9e9dc46532..ad887db6157d74359d28b31c36e936125c746850 -- docs/planning/smooth-open-orders-v1-development-checklist.md`

按以下顺序读取：

1. `AGENTS.md`；
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/10-smooth-open-final-plan-rereview-deepseek-v4-pro.dispatch.md`；
3. `reports/agent-runs/ACTIVE.json`；
4. `PROJECT_STATE.md`；
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`，核对 revision `16`、本 task_id 与固定 SHA；
6. `agents/roles.md` 的 Task Handoff Evidence Contract 与 Reviewer 段；
7. `agents/skills/code-reviewer.md`；
8. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-targeted-plan-rereview-deepseek-v4-pro.handoff.md`，只读 T1/T2 修复要求及“不得重开”边界；
9. 用 `git show ad887db6157d74359d28b31c36e936125c746850:docs/planning/smooth-open-orders-v1-development-checklist.md` 读取 §4.2.4 第 5 条与 §6“维护者”单元格；
10. 用上面的固定 diff 确认计划正文仅有 4 增 2 删且只落在这两处。

不需要读取或扫描产品源码、其他计划段落、其他阶段、运行时数据、仓库外文件或移动中的历史。固定范围中的 dispatch/status 属控制上下文，不是计划交付主体。

Acceptance Checks

- pass: **T1**：§4.2.4 第 5 条先构造 `deleted`/`done`/`stopped` 终态，再由同一隔离 test DB 的 fixture 直接写入三个明确非空 sentinel：`smooth_gate_seq=777`、`smooth_gate_started_at_us=123456789`、`smooth_gate_force_requested=1`；分别调用 `pause_task`/`stop_task_fatal` 后断言条件写未命中、status 不变、三个 sentinel 逐值保持。
- pass: T1 明确解释直接 SQL 仅用于构造正常 API 不会产生的观察态，使 miss 分支的“完全不写”可观测；明确禁止以三个本来就是 NULL 的值形成空断言。若错误实现把 gate 清理放在条件 UPDATE 之外，测试必须变红。
- pass: **T2**：§6 唯一口径为本交付及未来依赖变更都由获相应 dispatch 的 Implementer 修改；Bookkeeper 只核验和记账，绝不修改 `requirements.txt`；生产安装仍须 Human 单独授权。
- pass: 固定 diff 的计划正文只有 T1/T2 两处语义变更，没有改动其他产品、架构、任务范围、验收或角色决定。
- pass: R1/R3、单任务方案、冻结语义、O1/O2/O3、R2 四路径及第四路径豁免均不得重开；非阻塞 T-O1 留给正式实现 dispatch 以 Allowed Files 给出单一权限口径，不构成本轮 `REWORK`。
- pass: 若 T1/T2 均满足且没有由这两处新增文本直接引入、有当前证据支撑的缺陷，必须返回 `ACCEPT`；偏好、未来扩展或与这两处无关的观察不得阻塞。任何新阻塞场景仍须满足 `AGENTS.md` §1 Scenario Admission。
- pass: 创建唯一 handoff，写完整 Source Report、Required Reading、Human Brief、marker；返回合规 `[TASK_RESULT v2]` 与明确 `评审结论: ACCEPT | REWORK`。`REWORK` 只能引用 T1/T2 当前文本的具体未满足点；计划复核不改变 `rework_count`。`ACCEPT` 也不授权实现或外部动作。

Stop

完成 T1/T2 两点只读复核、创建唯一 handoff 并返回结果后停止。最后一个非空白输出必须是 `[/TASK_RESULT]`。不得扩大评审、修改受审内容或状态、准备/启动实现、创建 worktree/分支、安装依赖、联网、控制服务、下单、提交、合并、推送或部署。
