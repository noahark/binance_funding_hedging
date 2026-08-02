Identity:
- task_id: f4-account-availability-plan-v1
- target_role: Planner
- target_model: codex
- provider: openai
- status_revision: 1
- required_skill: agents/skills/software-architect.md

Goal:
为 F4（账户不可用时持仓表错误断言“交易所无仓”）形成可执行的最小实现计划，并准备下一阶段实现 dispatch。严格以归档 `46-` §3.3 的四条原文为契约：只有账户侧成功读取时才允许 `match_status="no_um"`；N2 路径不得出现“交易所无仓”及强平/手工平 `title`；补齐三组可失败测试；同步 `21-` §11.2 与 `10-design.md` §5。`account_unavailable` 是 `match_status` 的中性枚举值，不是任务 `STATUS_*` 新状态。不得把 F4 扩展为生命周期重做、任务卡暂停原因修复、exposure_alert 或其他 follow-up。

计划必须明确：
1. 后端契约、前端 N2 展示、self-check、后端测试及两份文档的最小文件边界；
2. 混合任务的唯一实现 owner 与理由（契约/后端语义占主导时可由 `claude_glm` 全包，前后端必须同版本上线）；
3. `HIGH_RISK` 路由：实现前跨 provider 计划评审，交付后 review-1 + review-2；当前 Codex 参与计划/Bookkeeper 的设计参与必须在后续评审 packet 中披露；
4. 与并行 stage `2026-08-02-frontend-display-tweaks-v1` 的边界：其 dispatch commit `9511319140e3120ef7c05fd2ca50a129eb423241` 同样批准了 `frontend/index.html` 与 `frontend/self-check.js`。计划须给出不覆盖另一终端工作、可复现 diff 检查、以及后续交付/合并顺序；
5. 禁止访问或写入真实 `data/`，禁止订单、凭证、服务控制、部署、merge、push 和 live 操作。

Allowed Files:
- reports/agent-runs/2026-08-02-hedge-f4-account-availability-v1/02-f4-plan.md
- reports/agent-runs/2026-08-02-hedge-f4-account-availability-v1/02-f4-implementation-v1.dispatch.md

Inputs:
- AGENTS.md §3、§4、§8、§9；
- PROJECT_STATE.md：F4 已接受限制、并行运行限制、真实 data/ 只读规则；
- docs/planning/DECISIONS.md：DEC-2026-07-30-001…003、DEC-2026-08-02-001…003；
- docs/planning/ROADMAP.md：Current Focus 的 F4；
- docs/planning/handoff-to-codex-bookkeeper-2026-08-02.md；
- archive/2026-07-31-hedge-task-lifecycle-v1:reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/46-review-1-grok-task1-r3.md §3.3 及 §4 的 F4 修复要求；
- backend/hedge_open_tasks/domain.py；
- backend/tests/test_positions_merge.py；
- frontend/index.html；
- frontend/self-check.js；
- reports/agent-runs/2026-08-02-frontend-display-tweaks-v1/01-frontend-task-card-pause-reason-zh-v1.dispatch.md（可用 `git show 9511319:<path>` 读取并核对并行边界）；
- git base：`git rev-parse HEAD` 已核验为 `54438aa94f1ba56acf42d77a4244d59676b6f3e4`。

Acceptance Checks:
1. `02-f4-plan.md` 逐项保留四条 F4 原始验收意图，并说明 `verified=false` / `private_account=None` 的中性输出与 `verified=true` 无 UM 的 `no_um` 对照。
2. 计划给出明确的实现文件、测试命令、失败注入/破坏验证方法、文档同步点，以及不得回退的现有契约（精确键集、merge 纯度、N2 表可见、G2/G5/G6/G7）。
3. 计划把 `match_status` 新枚举与任务状态枚举分开，并要求前端对未知 `match_status` 保持中性兜底。
4. 计划识别并处理与 `2026-08-02-frontend-display-tweaks-v1` 在两个前端文件上的并行占用；不得声称文件边界已互不重叠。
5. `02-f4-implementation-v1.dispatch.md` 符合 Bookkeeper dispatch shape，包含唯一 owner、Allowed Files、可失败验收、review 路由、基线 SHA 约束和停止条件；不得授权实现者修改 status/ACTIVE/PROJECT_STATE 或启动其他模型。
6. 仅修改本 packet 的两个 Allowed Files，不修改产品代码、ACTIVE.json、status.json 或 PROJECT_STATE.md。

Stop:
- 只做计划与下一 dispatch，不实现 F4，不运行会触碰真实 `data/` 的命令。
- 不启动、调用、转交或模拟任何其他模型；Human 负责启动本 packet。
- 若现有代码或并行边界不足以形成安全的单 owner 计划，返回 `blocked` 并指出具体证据路径。
- 按 AGENTS.md 返回完整 `[TASK_RESULT v2]`；计划完成后停止，等待 Human 将结果交回 Bookkeeper。
