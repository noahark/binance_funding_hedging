# Identity

- task_id: `smooth-open-v1-repair-plan-opus5-r3`
- target_role: `Planner`
- target_model: `claude-opus-5`
- provider: `anthropic`
- status_revision: `29`
- required_skill: `agents/skills/task-planner.md`

# Goal

对当前未提交的平滑开单返修计划执行第三轮、也是达到上限的一次穷举根因扫描式微修。必须原样引用并关闭同根因：**“合法超长 threshold 的成功/错误分类在同一计划内未穷举，连续两轮局部修改后仍残留把合法超长值写成 400 的站点。”** 同时统一活动 `rework_count` 与达到上限后的下一关卡。不得重做设计或实现代码。

这是首次代码交付后的第三个正式返修任务，`rework_count=3`。按 `AGENTS.md` §8，本轮后不得自动进入代码实现；即使后续窄计划复核 `ACCEPT`，也须先由 Human 选择缩窄、重设计、接受限制或停止。本任务不授权计划评审、代码实现、依赖安装、联网、服务控制、凭证、任务、订单、commit、push、merge、部署或实盘。

# Allowed Files

仅允许修改当前工作树中已有未提交改动的：

- `docs/planning/smooth-open-orders-v1.md`
- `docs/planning/smooth-open-orders-v1-development-checklist.md`

仅允许新建唯一交接件：

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-opus5-r3.handoff.md`
- Bookkeeper 预检：`test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-opus5-r3.handoff.md` 已通过。

预期既有未提交文件只有上述两份 planning 文件与两份只读 handoff：

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-opus5.handoff.md`
- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-opus5-r2.handoff.md`

不得编辑既有 handoff。禁止修改源码、测试、其他文档、dispatch、`status.json`、`ACTIVE.json`、`PROJECT_STATE.md`、`.venv`；禁止 commit/amend/push/merge。

# Inputs

严格按顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/17-smooth-open-v1-repair-plan-opus5-r3.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`
6. `agents/roles.md` 的 Planner 与 Task Handoff Evidence Contract 两节
7. `agents/skills/task-planner.md`
8. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-opus5-r2.handoff.md` 的 Bookkeeper Verification
9. `docs/planning/smooth-open-orders-v1.md`
10. `docs/planning/smooth-open-orders-v1-development-checklist.md`

启动核对：cwd `/Users/ark/Desktop/ai code/funding_hedging-smooth-v1`，分支 `smooth/v1-fullstack`，status revision `29`、本 task/model/provider 一致，`base_sha=db173ae394a3ab22782fae1f1e2cbd77ec482726`，`rework_count=3`，工作树已有变更恰为两份 planning 文件与两份既有 handoff，新 handoff 不存在。任一不一致即 blocked。

# Acceptance Checks

1. **同根因穷举，不得再点补丁**：对两份 planning 文件执行并在 handoff 逐项列出 `rg -n -i 'threshold|阈值|超长|InvalidOperation|400|500|201' ...` 的相关站点；每个与“合法超长 signed 阈值”有关的站点必须标注“应改”或“不适用 + 理由”。至少修正：
   - 设计 §16.2 必修 3：不得再写成合法超长值正确结果是 400；须明确当前缺陷是合法超长值逃逸成 500，目标是正常规范化并由 API 接受，而非改成 400。
   - 清单 §13 copy-ready 复核正文：把“超长整数 400 断言”改成同时可验证“合法超长值 201、格式非法值 400”的准确表述。
   - 清单 §12.3 已正确的合法超长 201 / 格式非法 400 口径保持不变。
   provider 不可用 400、`close+smooth` 400 等无关站点不得误改。最终不得存在任何把**合法**超长整数要求为 400 的文字。
2. **记账与后续关卡穷举**：对两份 planning 文件穷举 `rework_count`、当前返修轮次及“计划复核 ACCEPT 后自动派发实现”的活动表述。历史 §1–§11 可保留原事实，但必须明确标为历史、不得被当前 Bookkeeper 使用；活动 §12.1 必须与 `status.json.rework_count=3` 一致。凡当前口径声称计划复核 `ACCEPT` 后可直接准备/启动 Implementer 的地方，改为：先由 Human 按 `AGENTS.md` §8 在达到上限后选择缩窄、重设计、接受限制或停止；未经该决定不得派发代码实现。
3. 除上述穷举后确认的矛盾站点外，不改变 D15/D16、L1/L2/L3、五项必修根因与实现规格、Allowed Files、测试路径、验收命令、角色/模型或其他产品决定。不得把已关闭的 T2/T3/T4 重开。
4. `git diff --check` 无输出；tracked 改动仍恰为两份 planning 文件。创建合规唯一 handoff，记录穷举命令、逐站点分类、本轮精确修改和未修改理由；不提交、不改状态、不启动 Reviewer，返回 Human Brief 的 `[TASK_RESULT v2]`。

# Stop

穷举扫描、必要文字修正、自检和唯一 handoff 完成后立即停止。不得实现代码、准备或启动计划 Reviewer、安装依赖、联网、启停服务、读取凭证、创建任务、下单、提交、push、merge、部署或实盘。
