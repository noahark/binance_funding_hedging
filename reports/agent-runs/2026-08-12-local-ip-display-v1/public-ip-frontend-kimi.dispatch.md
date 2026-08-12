# 真实公网出口 IP：前端展示 dispatch — Kimi

## Identity

- task_id: `public-ip-frontend-kimi`
- target_role: `Implementer / Frontend`
- target_model: `kimi / Kimi Code`
- provider: `moonshot`
- status_revision: `9`
- required_skill: `agents/skills/senior-developer.md`

## Goal

把顶部标题右侧的静态预览徽标替换为真实、同源、只读的公网出口 IP 展示。只请求已经核验的
`GET /api/system/public-ip`，显示的是**后端进程**通过主备公开服务观察到的地址；它只供 Human
核对 API 白名单，不能证明币安实际观察到的出口 IP，绝不改变白名单、交易、借贷、划转、还款、
风控或任何 live gate。

页面加载时发起一次 fire-and-forget 同源 GET；不得阻塞、失败或改变既有市场快照加载、刷新按钮、
60 秒刷新节奏、任何定时器或 localStorage。不能调用外部 IP 服务，不能新增重试、轮询或持久化。
不重启服务：当前手动前台进程未加载本 stage 代码；不得把页面实际可访问当作本任务的验收条件。

## Allowed Files

- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-08-12-local-ip-display-v1/status.json`（仅将本 task 的 `current_task.state` 从 `dispatched` 改为 `reported`）
- `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-frontend-kimi.handoff.md`（唯一新建、create-only）
- `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-frontend-kimi-self-check.txt`（本任务原始 self-check 输出）

开始前 handoff 路径必须不存在；若已存在即停止报告：
`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-frontend-kimi.handoff.md`。
Bookkeeper 预检：`test ! -e reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-frontend-kimi.handoff.md` → `ABSENT`（2026-08-12 20:48 CST）。

## Inputs

按以下顺序读取：

1. `AGENTS.md`
2. 本 dispatch：`reports/agent-runs/2026-08-12-local-ip-display-v1/public-ip-frontend-kimi.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-local-ip-display-v1/status.json`
6. `agents/roles.md` 的 `Shared Rules`、`Task Handoff Evidence Contract` 与 `Implementer` 小节
7. `agents/developer-discipline.md`
8. `agents/skills/senior-developer.md`
9. 已接受计划：`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan.md`
10. R2 计划复审：`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude-r2.handoff.md`
11. 已核验后端交接与原始测试：`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-backend-claude-glm.handoff.md`、`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-backend-claude-glm-pytest.txt`
12. 已实现的端点契约：`backend/services/public_ip_service.py`、`backend/app/server.py`（`/api/system/public-ip`）、`docs/api/public-market-contract.md`（v0.19）
13. 要接线的前端与现有自检：`frontend/index.html`、`frontend/self-check.js`

## Acceptance Checks

1. 保留标题右侧现有 `#public-ip-badge`，删除 fake 地址 `203.0.113.42` 和「预览」字样。加载中可显示中性「公网出口 IP 读取中…」；`GET /api/system/public-ip` 的 HTTP 200 且严格符合后端四字段契约时：`status: "ok"` 显示 `公网出口 IP <public_ip>`，`status: "stale"` 显示 `公网出口 IP（上次成功） <public_ip>`；`stale` 的 title 明示最后成功 `checked_at` 和「仅供核对，不能证明币安实际看到的出口 IP」。
2. HTTP 非 200、fetch/json 异常、字段缺失／类型错误、未知 status，或 `unavailable`（其 `public_ip/source/checked_at` 均为 `null`）一律降级为中性 `公网出口 IP 暂不可用`，不向页面错误区写入异常文本，不展示 URL、服务商、请求头或假 IP。`ok`/`stale` 仅接受非空字符串 `public_ip`、`source`、`checked_at`；不要自行校验、格式化或猜测 IP。
3. 请求只能是 `fetch('/api/system/public-ip', { cache: 'no-store' })` 的同源 GET；从 `loadApi()` 或同等初始加载路径 fire-and-forget 调用，内部吞掉失败并更新 badge。不得 `await` 它或让它影响 snapshot、持仓拉取、自动刷新、按钮状态、定时器或 localStorage。
4. 更新 `frontend/self-check.js` 的 mock 与同源 fetch 白名单，覆盖并断言：初始加载恰有一次该 GET；`ok`、`stale`、`unavailable`、HTTP 失败或 schema 异常的可见文字和 title；无 preview 假地址；所有公网 IP 请求均为 GET、同源、`cache: 'no-store'`；不新增 interval/localStorage，快照和既有检查保持通过。
5. 执行并保存原始输出：`node frontend/self-check.js` 到 `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-frontend-kimi-self-check.txt`。另执行 `git diff --check`。仅修改 Allowed Files；不改后端共享端点契约或 API 文档，不加依赖，不发真实公网请求，不重启／部署／push／merge／读取凭据／访问币安或 live DB。
6. 创建一个只含本任务 Allowed Files 的本地提交；handoff 必须符合 Task Handoff Evidence Contract，并把本 task 状态改为 `reported`。交接必须明确：此端点值只代表后端进程观察，尚未重启／部署，不能据此修改币安 API 白名单。

## Stop

完成后停止，不得自行启动评审。控制台以 `AGENTS.md` §7 的 `[TASK_RESULT v2]` 收尾；`下一步模型` 写 `codex / GPT-5（Bookkeeper）`，`下一步任务` 必须为：`读取：reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-frontend-kimi.handoff.md；执行：Bookkeeper 核验前端交付并汇总固定 delivery SHA，准备正式评审；关卡：正式评审 dispatch 就绪后由 Human 决定启动`。
