# 公网出口 IP fake 展示 dispatch — Kimi

## Identity

- task_id: `local-ip-display-fake-kimi`
- target_role: `Implementer / Frontend`
- target_model: `kimi / kimi-code-for-coding`
- provider: `moonshot`
- status_revision: `2`
- required_skill: `agents/skills/senior-developer.md`

## Goal

制作可供 Human 观察的最小静态 fake：在「资金费率对冲工作台」标题文字的紧邻右侧，以既有 badge 视觉语言展示 `公网出口 IP（预览） 203.0.113.42`。`203.0.113.42` 是文档保留地址，必须保留「预览」标识；本任务不取得真实 IP。

这是纯展示、无网络调用、无资金/订单/账务语义改动的 `LOW_RISK` 原型。不得把本次 fake 描述为真实公网出口 IP 功能。

## Allowed Files

- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-08-12-local-ip-display-v1/status.json`（仅将本 task 的 `current_task.state` 从 `dispatched` 改为 `reported`）
- `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/local-ip-display-fake-kimi.handoff.md`（唯一新建、create-only）

在开始时，以下确定性 handoff 路径必须不存在；若已存在则停止并报告：
`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/local-ip-display-fake-kimi.handoff.md`。
Bookkeeper 预检：`test ! -e reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/local-ip-display-fake-kimi.handoff.md` → `ABSENT`（2026-08-12 19:28 CST）。

## Inputs

1. `AGENTS.md`
2. 本 dispatch：`reports/agent-runs/2026-08-12-local-ip-display-v1/local-ip-display-fake-kimi.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-local-ip-display-v1/status.json`
6. `agents/roles.md` 的 `Shared Rules`、`Task Handoff Evidence Contract` 与 `Implementer` 小节
7. `agents/developer-discipline.md`
8. `agents/skills/senior-developer.md`
9. `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/stage-intake.md`
10. `frontend/index.html` 与 `frontend/self-check.js`

## Acceptance Checks

1. 标题本身与 IP badge 位于同一个标题行容器内，badge 在标题的紧邻右侧；不得放入右侧的刷新/排序控件区。
2. 静态文案同时包含「公网出口 IP」「预览」和 `203.0.113.42`；该地址不得被呈现为真实值。
3. 窄屏时标题行可换行；不得以固定宽度遮挡标题或现有右侧控件。
4. 不新增 `fetch`、定时器、localStorage 键、后端路由、依赖或任何外域请求。
5. `frontend/self-check.js` 新增针对上述静态标题 badge 的断言；`node frontend/self-check.js` 通过，且既有同源 fetch 白名单检查继续通过。
6. `git diff --check` 通过；只修改 Allowed Files；创建符合 `agents/roles.md` Task Handoff Evidence Contract 的确定性 handoff，并将本 task state 写为 `reported`。
7. 创建一个只含本 task Allowed Files 的提交；不得 push、merge、部署、重启或控制服务。

## Stop

完成静态 fake、自检、handoff、状态更新和本地提交后停止。控制台以 `AGENTS.md` §7 的 `[TASK_RESULT v2]` 收尾；`下一步模型` 写 `codex / GPT-5（Bookkeeper）`，`下一步任务` 使用：`读取：reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/local-ip-display-fake-kimi.handoff.md；执行：Bookkeeper 核验 fake 交付并交 Human 观察；关卡：Human 确认版式后再决定真实公网 IP 实现范围`。不得启动评审、接入真实 IP 查询、或自行扩展任务。
